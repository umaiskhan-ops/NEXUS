"""HTTP server: Web Studio UI, REST API, Telegram webhook, health check, token-protected dashboard, HMAC-authenticated peer endpoint."""
from __future__ import annotations

import hmac
import html
import json
import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .ledger import interprocess_file_lock
from .telegram_gateway import TelegramClient, handle_update, parse_command
from .web_ui import get_web_ui_html

MAX_BODY = 1_000_000


def ensure_tls_certificates(data_dir: Path) -> tuple[str, str]:
    """Auto-generates or loads X.509 TLS certificate and private key for HTTPS transport security (M4 Fix)."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    cert_path = data_dir / "tls_cert.pem"
    key_path = data_dir / "tls_key.pem"
    if cert_path.exists() and key_path.exists():
        return str(cert_path), str(key_path)
    try:
        import datetime
        import ipaddress
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID

        priv_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "PK"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "NEXUS Sovereign Mesh"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ])
        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(priv_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=365))
            .add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                ]),
                critical=False,
            )
            .sign(priv_key, hashes.SHA256())
        )
        with interprocess_file_lock(key_path):
            key_path.write_bytes(
                priv_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )
            try:
                os.chmod(key_path, 0o600)
            except OSError:
                pass
        with interprocess_file_lock(cert_path):
            cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        return str(cert_path), str(key_path)
    except Exception:
        return "", ""


def get_recent_projects(data_dir: Path, default_path: str = "e:/NEXUS") -> list:
    f = Path(data_dir) / "recent_projects.json"
    norm_default = Path(default_path).resolve().as_posix()
    default_list = [norm_default]
    if f.exists():
        try:
            with interprocess_file_lock(f):
                items = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(items, list):
                out = []
                for p in items:
                    if p and p not in out:
                        out.append(p)
                for p in default_list:
                    if p not in out:
                        out.append(p)
                return out
        except Exception:
            pass
    return default_list


def add_recent_project(data_dir: Path, proj_path: str, default_path: str = "e:/NEXUS") -> list:
    items = get_recent_projects(data_dir, default_path)
    p_norm = Path(proj_path).resolve().as_posix()
    if p_norm in items:
        items.remove(p_norm)
    items.insert(0, p_norm)
    items = items[:15]
    f = Path(data_dir) / "recent_projects.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    with interprocess_file_lock(f):
        tmp = f.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps(items, indent=2))
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except OSError:
                pass
        tmp.replace(f)
    return items


def resolve_project_root(grid, requested_project: str = "") -> Path:
    if requested_project:
        p = Path(requested_project).resolve()
        if p.exists() and p.is_dir():
            return p
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception:
            pass
    active = getattr(grid, "active_project", None)
    if active:
        p = Path(active).resolve()
        if p.exists() and p.is_dir():
            return p
    default_dir = getattr(grid.config, "workspace_dir", "e:/NEXUS")
    p = Path(default_dir).resolve()
    if not p.exists():
        p = Path.cwd()
    return p


def _ensure_default_machines(grid) -> dict:
    if not hasattr(grid, "machines") or not isinstance(grid.machines, dict):
        grid.machines = {}
    defaults = [
        ("mach-arm", "6-Axis Robotic Arm (ROS 2)", "robotic_arm", "/dev/ttyUSB0"),
        ("mach-printer", "Voron 2.4 CoreXY 3D Printer", "3d_printer", "192.168.1.45:7125"),
        ("mach-cnc", "5-Axis Desktop CNC Mill (GRBL)", "cnc_mill", "COM3"),
    ]
    for mid, name, mtype, target in defaults:
        if mid not in grid.machines:
            grid.machines[mid] = {
                "machine_id": mid,
                "name": name,
                "type": mtype,
                "target": target,
                "baud": "115200",
                "status": "DISCONNECTED",
                "connected_at": None,
                "last_telemetry": None,
            }
    return grid.machines


def _is_safe_subpath(target: Path, root: Path) -> bool:
    """Strictly verifies target is inside root using Path.is_relative_to (fixes H7 prefix bypass)."""
    try:
        return target.resolve().is_relative_to(root.resolve())
    except Exception:
        return False


def make_handler(grid, client):
    cfg = grid.config
    _rate_lock = threading.Lock()
    _ip_hits: dict[str, list[float]] = {}
    _peer_replay_lock = threading.Lock()
    _peer_replay_cache: dict[str, float] = {}

    def _check_rate_limit(ip: str, limit: int = 600, window_s: float = 60.0) -> bool:
        now = time.time()
        with _rate_lock:
            hits = [t for t in _ip_hits.get(ip, []) if now - t < window_s]
            if len(hits) >= limit:
                _ip_hits[ip] = hits
                return False
            hits.append(now)
            _ip_hits[ip] = hits
            return True

    def _sign_ota_payload(worker_id: str, version: str, sha256_hex: str) -> str:
        import hashlib
        secret = ""
        if worker_id and getattr(grid, "hub", None):
            wrec = grid.hub.get_worker(worker_id)
            if wrec and wrec.key:
                secret = wrec.key
        if not secret:
            secret = cfg.peer_shared_secret or cfg.dashboard_token or ""
        if not secret:
            return ""
        msg = f"OTA:{version}:{sha256_hex}".encode("utf-8")
        return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

    def _sign_ota_ed25519(version: str, sha256_hex: str) -> tuple[str, str]:
        """Asymmetric Ed25519 code signing for OTA updates (C4 Fix: prefers offline manifest; no default public seed)."""
        import hashlib
        data_dir = Path(getattr(cfg, "data_dir", Path("./data")))
        manifest_file = data_dir / "ota_release_manifest.json"
        if manifest_file.exists():
            try:
                with interprocess_file_lock(manifest_file):
                    mdata = json.loads(manifest_file.read_text(encoding="utf-8"))
                if mdata.get("version") == version and mdata.get("sha256") == sha256_hex:
                    sig_m = str(mdata.get("ota_ed25519_sig", "")).strip()
                    pub_m = str(mdata.get("ota_ed25519_pub", "")).strip()
                    if len(sig_m) == 128 and len(pub_m) == 64:
                        return sig_m, pub_m
            except Exception:
                pass
        raw_seed = os.environ.get("NEXUS_OTA_PRIVATE_SEED", "").strip()
        if not raw_seed:
            return "", os.environ.get("NEXUS_OTA_PUBLIC_KEY_HEX", "").strip()
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            from cryptography.hazmat.primitives import serialization
            seed32 = hashlib.sha256(b"NEXUS_OTA_ED25519:" + raw_seed.encode("utf-8")).digest()
            priv = Ed25519PrivateKey.from_private_bytes(seed32)
            pub_hex = priv.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            ).hex()
            msg = f"OTA:{version}:{sha256_hex}".encode("utf-8")
            sig_hex = priv.sign(msg).hex()
            return sig_hex, pub_hex
        except Exception:
            return "", ""

    class Handler(BaseHTTPRequestHandler):
        server_version = "SovereignMesh/2026.5"

        def log_message(self, fmt, *args):  # quieter logs, redact query strings (fixes R1)
            import re
            raw_msg = fmt % args
            redacted_msg = re.sub(r'\?[^\s"]*', "", raw_msg)
            print(f"[HTTP] {self.address_string()} {redacted_msg}")

        def _send(
            self,
            code: int,
            body,
            ctype: str = "application/json",
            extra_headers: dict | None = None,
            csp_nonce: str = "",
        ) -> None:
            data = body if isinstance(body, bytes) else (
                body.encode("utf-8") if isinstance(body, str) else json.dumps(body, default=str).encode("utf-8"))
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
            script_policy = f"'self' 'nonce-{csp_nonce}'" if csp_nonce else "'self'"
            self.send_header(
                "Content-Security-Policy",
                f"default-src 'self'; script-src {script_policy}; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'",
            )
            if extra_headers:
                for hk, hv in extra_headers.items():
                    self.send_header(hk, hv)
            self.end_headers()
            self.wfile.write(data)

        def _get_cookie(self, name: str) -> str:
            raw = self.headers.get("Cookie", "")
            for part in raw.split(";"):
                if "=" in part:
                    k, v = part.strip().split("=", 1)
                    if k.strip() == name:
                        return v.strip()
            return ""

        def _read_json_body(self, allow_empty: bool = False):
            try:
                length = int(self.headers.get("Content-Length", "0") or 0)
            except ValueError:
                self._send(400, {"ok": False, "error": "invalid Content-Length"})
                return None
            if allow_empty and length <= 0:
                return {}
            if length <= 0 or length > MAX_BODY:
                self._send(413, {"ok": False, "error": "bad length"})
                return None
            try:
                parsed = json.loads(self.rfile.read(length))
            except ValueError:
                self._send(400, {"ok": False, "error": "bad json"})
                return None
            if not isinstance(parsed, dict):
                self._send(400, {"ok": False, "error": "bad json: object expected"})
                return None
            return parsed

        def _extract_supplied_token(self) -> str:
            """Extracts dashboard auth token strictly from headers or HttpOnly cookie, NEVER URL query params (fixes H11/R1)."""
            supplied = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            if not supplied:
                supplied = self.headers.get("X-Dashboard-Token", "").strip()
            if not supplied:
                supplied = self._get_cookie("nexus_session")
            return supplied

        def _auth_ok(self) -> bool:
            if not cfg.dashboard_token:
                return True
            supplied = self._extract_supplied_token()
            return bool(supplied and hmac.compare_digest(supplied, cfg.dashboard_token))

        def _caller_id(self) -> int:
            if cfg.dashboard_token:
                supplied = self._extract_supplied_token()
                if supplied and hmac.compare_digest(supplied, cfg.dashboard_token):
                    return grid.owner_tg_id
            return 999999999  # Public Web User (Role.OPERATOR, strictly blocked from Role.OWNER features)

        def _require_secret_worker(self, raw_credential: str):
            """Strictly authenticates a worker via private secret key, rejecting public worker_id (fixes C3/R7)."""
            cred = str(raw_credential or "").strip()
            if not cred:
                self._send(400, {"ok": False, "error": "Secret Account Key is required"})
                return None
            if getattr(grid, "hub", None):
                if grid.hub.is_public_worker_id(cred):
                    self._send(403, {
                        "ok": False,
                        "error": (
                            f"Security Violation (C3): '{cred}' is a public Worker ID, not a private Secret Account Key. "
                            "Financial, Staking, Lottery, and P2P Escrow actions require your private 64-character Secret Account Key."
                        ),
                    })
                    return None
                try:
                    wrec = grid.hub.authenticate_worker_key(cred)
                except PermissionError as pe:
                    self._send(403, {"ok": False, "error": str(pe)})
                    return None
                except Exception as ex:
                    self._send(401, {"ok": False, "error": f"Authentication failed: {str(ex)}"})
                    return None
                if not wrec:
                    self._send(401, {"ok": False, "error": "Invalid or unregistered Secret Account Key"})
                    return None
                return wrec
            return None

        def do_GET(self):  # noqa: N802
            client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
            if not _check_rate_limit(client_ip):
                return self._send(429, {"ok": False, "error": "rate limit exceeded"})
            path = self.path.split("?", 1)[0]
            if path in {"/api/worker/download", "/download/worker"}:
                from .worker_package import generate_worker_zip
                host = self.headers.get("Host") or f"{cfg.host}:{cfg.port}"
                proto_hdr = self.headers.get("X-Forwarded-Proto", "").lower()
                if proto_hdr in ("https", "http"):
                    scheme = proto_hdr
                elif host.endswith(":443") or host == "443":
                    scheme = "https"
                else:
                    scheme = "http"
                hub_url = getattr(grid, "public_hub_url", None) or f"{scheme}://{host}"
                b_url = getattr(cfg, "bootstrap_anchor_url", "") or getattr(grid, "bootstrap_anchor_url", "") or f"{hub_url}/api/tunnel/bootstrap"
                zip_bytes = generate_worker_zip(hub_url, bootstrap_url=b_url)
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Disposition", 'attachment; filename="nexus-worker-1click.zip"')
                self.send_header("Content-Length", str(len(zip_bytes)))
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(zip_bytes)
                return

            if path in {"/api/worker/ota_check", "/api/worker/update_check"}:
                import hashlib
                from .worker_package import WORKER_PROTOCOL_VERSION, get_worker_launcher_code
                qs = parse_qs(urlparse(self.path).query)
                client_ver = qs.get("version", [""])[0].strip()
                client_wid = qs.get("worker_id", [""])[0].strip()
                client_shard = qs.get("shard", [""])[0].strip()

                host = self.headers.get("Host") or f"{cfg.host}:{cfg.port}"
                proto_hdr = self.headers.get("X-Forwarded-Proto", "").lower()
                scheme = "https" if (proto_hdr == "https" or host.endswith(":443")) else "http"
                hub_url = getattr(grid, "public_hub_url", None) or f"{scheme}://{host}"
                b_url = getattr(cfg, "bootstrap_anchor_url", "") or getattr(grid, "bootstrap_anchor_url", "") or f"{hub_url}/api/tunnel/bootstrap"
                launcher_code = get_worker_launcher_code(hub_url, default_bootstrap_url=b_url)
                script_sha256 = hashlib.sha256(launcher_code.encode("utf-8")).hexdigest()
                ota_sig = _sign_ota_payload(client_wid, WORKER_PROTOCOL_VERSION, script_sha256)
                ota_ed25519_sig, ota_ed25519_pub = _sign_ota_ed25519(WORKER_PROTOCOL_VERSION, script_sha256)

                update_avail = bool(client_ver and client_ver != WORKER_PROTOCOL_VERSION)

                deltas_count = 0
                if getattr(grid, "brain_matrix", None):
                    with grid.brain_matrix._lock:
                        deltas_count = len([
                            d for d in grid.brain_matrix._deltas.values()
                            if (not client_shard or d.domain_shard == client_shard or (client_wid and client_wid in d.holder_worker_ids))
                        ])

                return self._send(200, {
                    "ok": True,
                    "latest_version": WORKER_PROTOCOL_VERSION,
                    "current_version": client_ver,
                    "update_available": update_avail,
                    "script_sha256": script_sha256,
                    "ota_signature": ota_sig,
                    "ota_ed25519_sig": ota_ed25519_sig,
                    "ota_ed25519_pub": ota_ed25519_pub,
                    "download_url": "/api/worker/ota_download",
                    "changelog": "Zero-Touch Over-The-Air hot reload, model shard weight synchronization, zero-dependency resilience.",
                    "model_sync": {
                        "shard": client_shard,
                        "available_deltas_count": deltas_count,
                        "deltas_url": f"/api/brain/worker_deltas?worker_id={client_wid}&shard={client_shard}",
                    },
                })

            if path in {"/api/worker/ota_download", "/api/worker/latest_script"}:
                import hashlib
                from .worker_package import WORKER_PROTOCOL_VERSION, get_worker_launcher_code
                qs = parse_qs(urlparse(self.path).query)
                raw = qs.get("raw", ["0"])[0] == "1"
                client_wid = qs.get("worker_id", [""])[0].strip()
                host = self.headers.get("Host") or f"{cfg.host}:{cfg.port}"
                proto_hdr = self.headers.get("X-Forwarded-Proto", "").lower()
                scheme = "https" if (proto_hdr == "https" or host.endswith(":443")) else "http"
                hub_url = getattr(grid, "public_hub_url", None) or f"{scheme}://{host}"
                b_url = getattr(cfg, "bootstrap_anchor_url", "") or getattr(grid, "bootstrap_anchor_url", "") or f"{hub_url}/api/tunnel/bootstrap"
                launcher_code = get_worker_launcher_code(hub_url, default_bootstrap_url=b_url)
                script_sha256 = hashlib.sha256(launcher_code.encode("utf-8")).hexdigest()
                ota_sig = _sign_ota_payload(client_wid, WORKER_PROTOCOL_VERSION, script_sha256)
                ota_ed25519_sig, ota_ed25519_pub = _sign_ota_ed25519(WORKER_PROTOCOL_VERSION, script_sha256)

                if raw:
                    code_bytes = launcher_code.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/x-python; charset=utf-8")
                    self.send_header("X-Script-Sha256", script_sha256)
                    self.send_header("X-OTA-Signature", ota_sig)
                    self.send_header("X-OTA-Ed25519-Signature", ota_ed25519_sig)
                    self.send_header("X-OTA-Ed25519-Pub", ota_ed25519_pub)
                    self.send_header("X-Worker-Version", WORKER_PROTOCOL_VERSION)
                    self.send_header("Content-Length", str(len(code_bytes)))
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    self.wfile.write(code_bytes)
                    return

                return self._send(200, {
                    "ok": True,
                    "version": WORKER_PROTOCOL_VERSION,
                    "sha256": script_sha256,
                    "ota_signature": ota_sig,
                    "ota_ed25519_sig": ota_ed25519_sig,
                    "ota_ed25519_pub": ota_ed25519_pub,
                    "code": launcher_code,
                    "changelog": "Zero-Touch Over-The-Air hot reload, model shard weight synchronization, zero-dependency resilience.",
                })

            if path == "/api/worker/pull_task":
                # Security Fix (B1): pull_task requires worker authentication or Hub Owner auth.
                # Header authentication (X-Worker-Key / Authorization) is preferred to avoid leaking keys in URLs/logs.
                qs = parse_qs(urlparse(self.path).query)
                requested_wid = qs.get("worker_id", [""])[0].strip()
                auth_key = (
                    self.headers.get("X-Worker-Key", "").strip()
                    or self.headers.get("X-Account-Key", "").strip()
                    or self.headers.get("Authorization", "").replace("Bearer ", "").strip()
                    or qs.get("key", [""])[0].strip()
                    or qs.get("account_key", [""])[0].strip()
                    or self._get_cookie("nexus_account_key").strip()
                )
                req_sig = self.headers.get("X-Worker-Signature", "").strip()
                req_ts = self.headers.get("X-Worker-Timestamp", "").strip()
                if req_sig and req_ts:
                    try:
                        ts_val = float(req_ts)
                        if abs(time.time() - ts_val) > 300.0:
                            return self._send(401, {"ok": False, "error": "signature timestamp expired (>300s clock drift)"})
                    except ValueError:
                        return self._send(401, {"ok": False, "error": "invalid signature timestamp"})
                is_owner = self._auth_ok()
                eff_wid = requested_wid
                if not is_owner:
                    if not auth_key:
                        return self._send(401, {
                            "ok": False,
                            "error": "unauthorized: /api/worker/pull_task requires X-Worker-Key header or key query param",
                        })
                    try:
                        wrec = grid.hub.authenticate_worker_key(auth_key)
                    except PermissionError as p_err:
                        return self._send(401, {"ok": False, "error": str(p_err)})
                    if requested_wid and wrec.worker_id != requested_wid:
                        return self._send(403, {
                            "ok": False,
                            "error": "forbidden: cannot pull tasks for another worker node",
                        })
                    eff_wid = wrec.worker_id
                elif not eff_wid:
                    eff_wid = qs.get("key", [""])[0].strip()

                try:
                    max_t = max(1, min(20, int(qs.get("max_tasks", ["5"])[0] or 5)))
                except (ValueError, TypeError):
                    max_t = 5
                tasks_pulled = grid.hub.pull_pending_tasks(eff_wid, max_tasks=max_t) if (eff_wid and getattr(grid, "hub", None)) else []
                return self._send(200, {
                    "ok": True,
                    "worker_id": eff_wid,
                    "nat_traversal_mode": "OUTBOUND_HTTP_PULL_QUEUE",
                    "tasks_count": len(tasks_pulled),
                    "pending_tasks": tasks_pulled,
                })

            if path == "/api/brain/safetensors":
                qs = parse_qs(urlparse(self.path).query)
                shard = qs.get("shard", [""])[0].strip()
                raw_dl = qs.get("raw", ["0"])[0].strip() in {"1", "true", "yes"}
                if not getattr(grid, "brain_matrix", None):
                    return self._send(500, {"ok": False, "error": "brain_matrix not initialized"})
                if raw_dl and shard:
                    st_path = grid.brain_matrix._safetensors_path(shard)
                    if st_path.exists():
                        raw_bytes = st_path.read_bytes()
                        self.send_response(200)
                        self.send_header("Content-Type", "application/octet-stream")
                        self.send_header("Content-Disposition", f'attachment; filename="{st_path.name}"')
                        self.send_header("Content-Length", str(len(raw_bytes)))
                        self.send_header("Access-Control-Allow-Origin", f"http://127.0.0.1:{cfg.port}")
                        self.send_header("X-Content-Type-Options", "nosniff")
                        self.end_headers()
                        self.wfile.write(raw_bytes)
                        return
                checkpoints = grid.brain_matrix.get_safetensors_checkpoints()
                if shard:
                    checkpoints = [c for c in checkpoints if c.get("shard") == shard]
                return self._send(200, {
                    "ok": True,
                    "format": "HuggingFace .safetensors (Binary IEEE-754 float32)",
                    "checkpoints": checkpoints,
                })

            if path == "/api/brain/worker_deltas":
                # Security Fix (B5): Querying worker-specific deltas requires worker authentication or Hub Owner auth.
                qs = parse_qs(urlparse(self.path).query)
                wid = qs.get("worker_id", [""])[0].strip()
                shard = qs.get("shard", [""])[0].strip()
                auth_key = (
                    self.headers.get("X-Worker-Key", "").strip()
                    or self.headers.get("X-Account-Key", "").strip()
                    or qs.get("key", [""])[0].strip()
                    or qs.get("account_key", [""])[0].strip()
                )
                is_owner = self._auth_ok()
                if not is_owner:
                    if not auth_key:
                        return self._send(401, {"ok": False, "error": "unauthorized: querying worker deltas requires authentication (X-Worker-Key or session)"})
                    try:
                        auth_rec = grid.hub.authenticate_worker_key(auth_key)
                        if wid and auth_rec.worker_id != wid:
                            return self._send(403, {"ok": False, "error": "forbidden: cannot query deltas for another worker"})
                        wid = auth_rec.worker_id
                    except PermissionError as p_err:
                        return self._send(401, {"ok": False, "error": str(p_err)})

                deltas_list = []
                if getattr(grid, "brain_matrix", None):
                    with grid.brain_matrix._lock:
                        deltas_list = [
                            d.to_dict() for d in grid.brain_matrix._deltas.values()
                            if (not shard or d.domain_shard == shard or (wid and wid in d.holder_worker_ids))
                        ]
                return self._send(200, {
                    "ok": True,
                    "worker_id": wid,
                    "shard": shard,
                    "total_deltas": len(deltas_list),
                    "deltas": deltas_list[-50:],
                })

            if path in {"/", "/chat"}:
                import secrets
                csp_nonce = secrets.token_hex(16)
                page = get_web_ui_html(
                    grid.node_id,
                    [n.to_dict() for n in grid.router.nodes],
                    grid.registry.counts(),
                    csp_nonce=csp_nonce,
                )
                return self._send(200, page, "text/html; charset=utf-8", csp_nonce=csp_nonce)
            if path == "/api/tunnel/status":
                t_mgr = getattr(grid, "tunnel_mgr", None)
                pub_url = getattr(grid, "public_hub_url", None) or (t_mgr.get_public_url() if t_mgr else None)
                raw_gist = getattr(cfg, "github_gist_id", "") or (t_mgr.github_gist_id if t_mgr else "")
                safe_gist = raw_gist if self._auth_ok() else ("[REDACTED]" if raw_gist else "")
                return self._send(200, {
                    "ok": True,
                    "public_hub_url": pub_url,
                    "status": getattr(t_mgr, "status", "INACTIVE") if t_mgr else "NOT_CONFIGURED",
                    "cloudflared_installed": bool(t_mgr.find_cloudflared_binary() if t_mgr else False),
                    "bootstrap_anchor_url": getattr(cfg, "bootstrap_anchor_url", "") or getattr(grid, "bootstrap_anchor_url", ""),
                    "github_gist_id": safe_gist,
                })

            if path == "/api/tunnel/bootstrap":
                t_mgr = getattr(grid, "tunnel_mgr", None)
                pub_url = getattr(grid, "public_hub_url", None) or (t_mgr.get_public_url() if t_mgr else None)
                raw_gist = getattr(cfg, "github_gist_id", "") or (t_mgr.github_gist_id if t_mgr else "")
                safe_gist = raw_gist if self._auth_ok() else ("[REDACTED]" if raw_gist else "")
                return self._send(200, {
                    "ok": True,
                    "active_hub_url": pub_url or f"http://127.0.0.1:{cfg.port}",
                    "status": getattr(t_mgr, "status", "ONLINE") if t_mgr else "LOCAL",
                    "bootstrap_anchor_url": getattr(cfg, "bootstrap_anchor_url", "") or getattr(grid, "bootstrap_anchor_url", ""),
                    "github_gist_id": safe_gist,
                    "updated_at": time.time(),
                })

            if path == "/api/p2p/orders":
                qs = parse_qs(urlparse(self.path).query)
                status = qs.get("status", ["OPEN"])[0] or None
                curr = qs.get("currency", [""])[0] or None
                otype = qs.get("order_type", [""])[0] or None
                orders = grid.p2p.list_orders(status=status, currency=curr, order_type=otype)
                sell_orders = grid.p2p.list_orders(status=status, currency=curr, order_type="SELL")
                buy_orders = grid.p2p.list_orders(status=status, currency=curr, order_type="BUY")
                stats = grid.p2p.market_stats()
                lb = grid.hub.get_top_miners_leaderboard(limit=10) if getattr(grid, "hub", None) else {}
                return self._send(200, {
                    "ok": True,
                    "orders": orders,
                    "sell_orders": sell_orders,
                    "buy_orders": buy_orders,
                    "stats": stats,
                    "leaderboard_data": lb,
                })

            if path == "/api/p2p/leaderboard":
                qs = parse_qs(urlparse(self.path).query)
                try:
                    limit = max(1, min(100, int(qs.get("limit", ["10"])[0] or 10)))
                except (ValueError, TypeError):
                    limit = 10
                lb = grid.hub.get_top_miners_leaderboard(limit=limit) if getattr(grid, "hub", None) else {}
                return self._send(200, {"ok": True, **lb})

            if path == "/api/p2p/my_trades":
                # Security Fix (B5): Listing personal trade history requires account key authentication or Hub Owner auth.
                qs = parse_qs(urlparse(self.path).query)
                requested_wid = qs.get("worker_id", [""])[0].strip()
                auth_key = (
                    self.headers.get("X-Worker-Key", "").strip()
                    or self.headers.get("X-Account-Key", "").strip()
                    or qs.get("account_key", [""])[0].strip()
                    or qs.get("key", [""])[0].strip()
                    or self._get_cookie("nexus_account_key").strip()
                )
                is_owner = self._auth_ok()
                if not is_owner:
                    if not auth_key:
                        return self._send(401, {"ok": False, "error": "unauthorized: /api/p2p/my_trades requires account authentication"})
                    try:
                        auth_rec = grid.hub.authenticate_worker_key(auth_key)
                    except PermissionError as p_err:
                        return self._send(401, {"ok": False, "error": str(p_err)})
                    if requested_wid and auth_rec.worker_id != requested_wid:
                        return self._send(403, {"ok": False, "error": "forbidden: cannot view trades of another worker node"})
                    target_wid = auth_rec.worker_id
                else:
                    target_wid = requested_wid or grid.owner_tg_id
                trades = grid.p2p.get_user_orders(target_wid) if target_wid else {"selling": [], "buying": []}
                return self._send(200, {"ok": True, "worker_id": target_wid, "trades": trades})

            if path == "/api/supercomputer/instances":
                # Security Fix (B5): Listing instances requires private account key or Hub Owner auth.
                qs = parse_qs(urlparse(self.path).query)
                auth_key = (
                    self.headers.get("X-Account-Key", "").strip()
                    or self.headers.get("X-Worker-Key", "").strip()
                    or self._get_cookie("nexus_account_key").strip()
                    or qs.get("account_key", [""])[0].strip()
                    or qs.get("key", [""])[0].strip()
                )
                is_owner = self._auth_ok()
                if not is_owner and not auth_key:
                    return self._send(401, {"ok": False, "error": "unauthorized: listing instances requires account authentication"})
                target_acc = None
                if auth_key:
                    try:
                        auth_rec = grid.hub.authenticate_worker_key(auth_key)
                        target_acc = auth_rec.worker_id
                    except PermissionError:
                        target_acc = auth_key
                elif is_owner:
                    target_acc = qs.get("worker_id", [""])[0].strip() or None
                instances = grid.supercomputer.list_instances(target_acc)
                return self._send(200, {"ok": True, "instances": instances})

            if path == "/api/brain/status":
                bm = grid.brain_matrix.autonomy_era_status() if getattr(grid, "brain_matrix", None) else {}
                return self._send(200, {"ok": True, **bm})

            if path == "/api/learning/status":
                if not getattr(grid, "continuous_learning", None):
                    return self._send(500, {"ok": False, "error": "continuous_learning not initialized"})
                st = dict(grid.continuous_learning.status())
                # Security Guard (B5): Redact host local filesystem paths for non-owner callers
                if not self._auth_ok():
                    if st.get("active_adapter_path"):
                        st["active_adapter_path"] = Path(st["active_adapter_path"]).name
                    if st.get("active_gguf_path"):
                        st["active_gguf_path"] = Path(st["active_gguf_path"]).name
                return self._send(200, {"ok": True, **st})

            if path == "/api/lottery/status":
                if not getattr(grid, "token_sink", None):
                    return self._send(500, {"ok": False, "error": "token_sink not initialized"})
                return self._send(200, grid.token_sink.get_lottery_status())

            if path == "/api/staking/status":
                # Security Fix (B5): Querying private staking records requires account key authentication or Hub Owner auth.
                if not getattr(grid, "token_sink", None):
                    return self._send(500, {"ok": False, "error": "token_sink not initialized"})
                qs = parse_qs(urlparse(self.path).query)
                auth_key = (
                    self.headers.get("X-Account-Key", "").strip()
                    or self.headers.get("X-Worker-Key", "").strip()
                    or self._get_cookie("nexus_account_key").strip()
                    or qs.get("account_key", [""])[0].strip()
                    or qs.get("key", [""])[0].strip()
                )
                is_owner = self._auth_ok()
                if not is_owner and not auth_key:
                    return self._send(401, {"ok": False, "error": "unauthorized: staking status requires account authentication"})
                if auth_key:
                    try:
                        auth_rec = grid.hub.authenticate_worker_key(auth_key)
                        target_acc = auth_rec.worker_id
                    except PermissionError:
                        target_acc = auth_key
                else:
                    target_acc = qs.get("worker_id", [""])[0].strip() or "owner"
                return self._send(200, grid.token_sink.get_staking_status(target_acc))

            if path == "/api/tokensink/stats":
                total_burned = grid.token_sink.total_deflationary_burned_credits if getattr(grid, "token_sink", None) else 0
                staked = sum(s.staked_amount for s in grid.token_sink._stakers.values()) if getattr(grid, "token_sink", None) else 0
                return self._send(200, {
                    "ok": True,
                    "deflationary_burned_credits": total_burned,
                    "total_credits_staked": staked,
                    "commercial_equivalents": {
                        "ai_chat_plus_saved_usd": 20.0,
                        "cursor_ide_pro_saved_usd": 20.0,
                        "total_monthly_subscription_value_usd": 40.0,
                        "total_monthly_subscription_value_pkr": 11200.0,
                        "student_free_access": "Enabled (100% Free via 20 Welcome Credits)",
                    }
                })

            if path == "/api/crypto/quantum_spec":
                return self._send(200, {
                    "ok": True,
                    "protocol": "NEXUS Multi-Vault Hybrid Key Engine (HSQK-4096)",
                    "entropy_bits": 4096,
                    "entropy_bytes": 512,
                    "security_comparison": {
                        "bitcoin": {
                            "algorithm": "ECDSA secp256k1 (BIP-340 Schnorr / Base58Check / Bech32)",
                            "entropy_bits": 256,
                            "key_space": "2^256 (~1.15 x 10^77)",
                            "symmetric_security_level": 128,
                            "quantum_resistance": "Vulnerable to Shor's Algorithm on sufficiently large quantum computers",
                            "hardware_binding": "None (Static key)",
                            "forward_secrecy": "None (Static key)",
                            "address_format": "bc1q... (160/256 bits)",
                        },
                        "nexus_hsqk_4096": {
                            "algorithm": "Multi-Vault Hybrid (Ed448 / Ed25519 + Module-LWE Ring + SHAKE256 + SHA3 + BLAKE2b)",
                            "entropy_bits": 4096,
                            "key_space": "512-byte master seed derived across 4 independent cryptographic chambers",
                            "symmetric_security_level": 256,
                            "quantum_resistance": "Hybrid Classical (Ed448) + Cyclotomic Ring Module-LWE Commitment",
                            "hardware_binding": "Chamber 4: Host Hardware Fingerprint + Timing Jitter Anchor",
                            "forward_secrecy": "Hash-Ratchet evolving session state on every compute proof",
                            "address_format": "nxq1... (Bech32m Address with polynomial error detection)",
                        }
                    },
                    "chambers": {
                        "chamber_1": "Cyclotomic Polynomial Ring Module-LWE Engine in Z_q[X]/(X^32 + 1)",
                        "chamber_2": "Ed448-Goldilocks Asymmetric Signature Engine (RFC 8032)",
                        "chamber_3": "Triple Cascaded Hash Tree Root (SHAKE-256 + SHA3-512 + BLAKE2b-512)",
                        "chamber_4": "Host Hardware Fingerprint Seal (OS/Motherboard UUID + CPU Timing Jitter)",
                    }
                })

            if path == "/api/account/status":
                qs = parse_qs(urlparse(self.path).query)
                key = (
                    self.headers.get("X-Account-Key", "")
                    or self._get_cookie("nexus_account_key")
                    or qs.get("key", [""])[0]
                ).strip()
                if not key:
                    return self._send(400, {"ok": False, "error": "Account key is required"})
                if getattr(grid, "hub", None) and grid.hub.is_public_worker_id(key):
                    return self._send(403, {
                        "ok": False,
                        "error": (
                            f"Security Notice: '{key}' is a public Worker ID, not a Secret Account Key! "
                            "Public Worker IDs cannot be used to log in or access credits. "
                            "Please copy and enter your private Secret Account Key from your Worker Dashboard."
                        )
                    })
                rec = grid.hub.get_worker_by_key(key) if getattr(grid, "hub", None) else None
                if not rec:
                    return self._send(401, {
                        "ok": False,
                        "error": "Invalid or unregistered Secret Account Key (N3 Security Enforcement: auto-creation disabled).",
                    })
                tier_name = "COMMUNITY"
                if rec.credits >= 200:
                    tier_name = "SOVEREIGN_VIP"
                elif rec.credits >= 50:
                    tier_name = "PRO"
                return self._send(200, {
                    "ok": True,
                    "worker_id": rec.worker_id,
                    "account_key": rec.key,
                    "quantum_address": getattr(rec, "quantum_address", ""),
                    "crypto_security_level": getattr(rec, "crypto_security_level", "4096-Bit Hyper-Sovereign Quantum Vault"),
                    "puf_seal_active": bool(getattr(rec, "puf_seal", "")),
                    "ratchet_step": getattr(rec, "ratchet_step", 0),
                    "credits": rec.credits,
                    "balance_umais": rec.credits,
                    "currency_symbol": "UMAIS",
                    "credit_to_umais_parity": "1 Credit = 1 UMAIS",
                    "status": rec.status,
                    "tier": tier_name,
                    "tasks_completed": rec.tasks_completed,
                    "hardware_spec": rec.hardware_spec,
                    "brain_shard": rec.brain_shard,
                    "replica_shards": rec.replica_shards,
                    "synced_deltas_count": rec.synced_deltas_count,
                    "referral_code": rec.referral_code,
                    "referred_by": rec.referred_by,
                    "referrals_count": rec.referrals_count,
                    "referral_bonus_credits": rec.referral_bonus_credits,
                    "dispute_frozen": rec.dispute_frozen,
                    "dispute_reason": rec.dispute_reason,
                    "pending_payout_usd": rec.pending_payout,
                    "total_earned_usd": rec.total_payout_earned,
                    "distillation_stats": grid.router.distillation_stats() if getattr(grid, "router", None) else {},
                    "brain_matrix": grid.brain_matrix.autonomy_era_status() if getattr(grid, "brain_matrix", None) else {},
                })

            if path == "/api/machines":
                machines = _ensure_default_machines(grid)
                if not self._auth_ok():
                    redacted = []
                    for m in machines.values():
                        item = dict(m)
                        item["target"] = "[REDACTED] (auth required)"
                        item["baud"] = "[REDACTED] (auth required)"
                        redacted.append(item)
                    return self._send(200, {"ok": True, "machines": redacted, "redacted": True})
                return self._send(200, {"ok": True, "machines": list(machines.values())})

            if path == "/api/ide/projects":
                if not self._auth_ok():
                    return self._send(401, {"ok": False, "error": "unauthorized"})
                curr = str(resolve_project_root(grid))
                recent = get_recent_projects(getattr(grid.config, "data_dir", Path("./data")), curr)
                return self._send(200, {"ok": True, "current_project": curr, "projects": recent})

            if path == "/api/ide/files":
                if not self._auth_ok():
                    return self._send(401, {"ok": False, "error": "unauthorized"})
                qs = parse_qs(urlparse(self.path).query)
                proj_param = qs.get("project", [""])[0].strip()
                root = resolve_project_root(grid, proj_param)
                if proj_param:
                    add_recent_project(getattr(grid.config, "data_dir", Path("./data")), str(root))
                    grid.active_project = str(root)
                files = []
                for p in sorted(root.rglob("*")):
                    if any(part.startswith(".") or part in {"__pycache__", "venv", "node_modules", "target", ".git"} for part in p.parts):
                        continue
                    rel = p.relative_to(root).as_posix()
                    files.append({
                        "path": rel,
                        "name": p.name,
                        "is_dir": p.is_dir(),
                        "size": p.stat().st_size if p.is_file() else 0,
                        "ext": p.suffix.lstrip(".").lower() if p.is_file() else ""
                    })
                    if len(files) >= 800:
                        break
                return self._send(200, {"ok": True, "root": str(root), "files": files})

            if path == "/api/ide/file":
                if not self._auth_ok():
                    return self._send(401, {"ok": False, "error": "unauthorized"})
                qs = parse_qs(urlparse(self.path).query)
                rel_path = qs.get("path", [""])[0].strip()
                proj_param = qs.get("project", [""])[0].strip()
                if not rel_path:
                    return self._send(400, {"ok": False, "error": "path is required"})
                root = resolve_project_root(grid, proj_param)
                target = (root / rel_path).resolve()
                if not _is_safe_subpath(target, root) or not target.is_file():
                    return self._send(404, {"ok": False, "error": "file not found"})
                try:
                    content = target.read_text(encoding="utf-8", errors="replace")
                    return self._send(200, {"ok": True, "path": rel_path, "project": str(root), "content": content})
                except Exception as exc:
                    return self._send(500, {"ok": False, "error": str(exc)})

            if path == "/api/features":
                return self._send(200, [f.to_dict() for f in grid.registry.all()])
            if path == "/healthz":
                return self._send(200, {"ok": True, "node": grid.node_id, "lockdown": grid.system_lockdown})
            if path == "/p2p/head":
                return self._p2p_head()
            if path in {"/dashboard", "/api/status"}:
                if not self._auth_ok():
                    return self._send(401, {"error": "unauthorized"})
                workers_data = grid.hub.list_workers() if getattr(grid, "hub", None) else []
                status = {
                    "node_id": grid.node_id, "uptime_s": int(time.time() - grid.started_at),
                    "lockdown": grid.system_lockdown, "autonomous": grid.autonomous_mode,
                    "nodes": [n.to_dict() for n in grid.router.nodes],
                    "workers": workers_data,
                    "features": grid.registry.counts(),
                    "feature_kinds": grid.registry.kind_counts(), "ledger_blocks": len(grid.ledger),
                    "ledger_intact": grid.ledger.verify()[0], "alerts": grid.check_alerts(),
                    "tasks": [t.to_dict() for t in grid.tasks.list()][-20:], "budget": grid.budget.status(),
                    "distillation": grid.router.distillation_stats() if getattr(grid, "router", None) else {},
                    "brain_matrix": grid.brain_matrix.autonomy_era_status() if getattr(grid, "brain_matrix", None) else {},
                }
                if path == "/api/status":
                    return self._send(200, status)
                rows = "".join(f"<tr><th>{html.escape(str(k))}</th><td><pre>{html.escape(json.dumps(v, indent=1, default=str))}"
                               f"</pre></td></tr>" for k, v in status.items())
                page = (f"<!doctype html><meta charset=utf-8><title>Sovereign Mesh</title>"
                        f"<style>body{{font-family:system-ui;background:#0b0f14;color:#d7e0ea;margin:2rem}}"
                        f"th{{text-align:left;vertical-align:top;padding:.4rem 1rem;color:#7fb4ff}}"
                        f"pre{{margin:0;white-space:pre-wrap}}</style><h1>Sovereign Mesh Node</h1><table>{rows}</table>")
                return self._send(200, page, "text/html; charset=utf-8")
            return self._send(404, {"error": "not found"})

        def _p2p_head(self):
            if not cfg.peer_shared_secret:
                return self._send(404, {"error": "not found"})
            ts = self.headers.get("X-Peer-Timestamp", "")
            sig = self.headers.get("X-Peer-Signature", "")
            nonce = self.headers.get("X-Peer-Nonce", "")
            now = time.time()
            fresh = ts.isdigit() and abs(now - int(ts)) < 60
            if not fresh or not sig or not nonce:
                return self._send(401, {"error": "bad peer signature (timestamp, nonce, and path-bound signature required)"})
            expected_bound = grid.peer_signature(ts, path="/p2p/head", nonce=nonce)
            if not hmac.compare_digest(sig, expected_bound):
                return self._send(401, {"error": "bad peer signature"})
            replay_key = f"{ts}:{nonce}:{sig}"
            with _peer_replay_lock:
                expired = [k for k, exp_t in _peer_replay_cache.items() if now - exp_t > 65.0]
                for k in expired:
                    _peer_replay_cache.pop(k, None)
                if replay_key in _peer_replay_cache:
                    return self._send(401, {"error": "replayed peer signature (H8 blocked)"})
                _peer_replay_cache[replay_key] = now
            return self._send(200, {"node_id": grid.node_id, "ledger_len": len(grid.ledger),
                                    "head_hash": grid.ledger.head_hash})

        def do_POST(self):  # noqa: N802
            client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
            if not _check_rate_limit(client_ip):
                return self._send(429, {"ok": False, "error": "rate limit exceeded"})
            path = self.path.split("?", 1)[0]

            if path == "/api/auth/session":
                body = self._read_json_body(allow_empty=True)
                if body is None:
                    return
                tok = str(body.get("token", "")).strip()
                acc_key = str(body.get("account_key", "")).strip()
                headers_out = {}
                if tok:
                    headers_out["Set-Cookie"] = f"nexus_session={tok}; HttpOnly; SameSite=Strict; Path=/"
                elif acc_key:
                    headers_out["Set-Cookie"] = f"nexus_account_key={acc_key}; HttpOnly; SameSite=Strict; Path=/"
                return self._send(200, {"ok": True, "session": "HttpOnly cookie set"}, extra_headers=headers_out)

            if path in {"/api/lottery/buy_ticket", "/api/lottery/draw", "/api/staking/stake", "/api/staking/unstake"}:
                body = self._read_json_body(allow_empty=True)
                if body is None:
                    return

                if not getattr(grid, "token_sink", None):
                    return self._send(500, {"ok": False, "error": "token_sink not initialized"})

                acc = str(body.get("account_key") or body.get("worker_id") or "").strip()

                if path == "/api/lottery/buy_ticket":
                    wrec = self._require_secret_worker(acc)
                    if not wrec:
                        return
                    raw_tickets = body.get("tickets") if body.get("tickets") is not None else body.get("count", 1)
                    if raw_tickets == "":
                        raw_tickets = 1
                    try:
                        tickets = int(raw_tickets)
                    except (ValueError, TypeError):
                        return self._send(400, {"ok": False, "error": "tickets must be an integer"})
                    res = grid.token_sink.buy_lottery_ticket(wrec.key, count=tickets)
                    code = 200 if res.get("ok") else 400
                    return self._send(code, res)

                if path == "/api/lottery/draw":
                    force = bool(body.get("force", False))
                    if force:
                        is_owner_caller = (cfg.dashboard_token and self._caller_id() == grid.owner_tg_id)
                        if not is_owner_caller and acc and getattr(grid, "hub", None):
                            try:
                                wrec_owner = grid.hub.authenticate_worker_key(acc)
                                if wrec_owner and wrec_owner.worker_id == "owner-master":
                                    is_owner_caller = True
                            except PermissionError:
                                wrec_owner = None
                        if not is_owner_caller:
                            return self._send(403, {
                                "ok": False,
                                "error": "Security Enforcement (H1): Forced lottery draw requires Sovereign Owner authentication.",
                            })
                    res = grid.token_sink.draw_lottery_winner(force=force)
                    code = 200 if res.get("ok") else 400
                    return self._send(code, res)

                if path == "/api/staking/stake":
                    wrec = self._require_secret_worker(acc)
                    if not wrec:
                        return
                    raw_amt = body.get("amount", 50)
                    if raw_amt is None or raw_amt == "":
                        raw_amt = 50
                    try:
                        amt = int(raw_amt)
                    except (ValueError, TypeError):
                        return self._send(400, {"ok": False, "error": "amount must be an integer"})
                    res = grid.token_sink.stake_credits(wrec.key, amt)
                    code = 200 if res.get("ok") else 400
                    return self._send(code, res)

                if path == "/api/staking/unstake":
                    wrec = self._require_secret_worker(acc)
                    if not wrec:
                        return
                    raw_amt = body.get("amount", 50)
                    if raw_amt is None or raw_amt == "":
                        raw_amt = 50
                    try:
                        amt = int(raw_amt)
                    except (ValueError, TypeError):
                        return self._send(400, {"ok": False, "error": "amount must be an integer"})
                    res = grid.token_sink.unstake_credits(wrec.key, amt, enforce_lock=True)
                    code = 200 if res.get("ok") else 400
                    return self._send(code, res)

            if path == "/api/tunnel/start":
                caller_id = self._caller_id()
                if caller_id != grid.owner_tg_id:
                    return self._send(403, {"ok": False, "error": "Only the Sovereign Owner can start the Cloudflare Public Tunnel."})
                t_mgr = getattr(grid, "tunnel_mgr", None)
                if not t_mgr:
                    from .tunnel import PublicTunnelManager
                    t_mgr = PublicTunnelManager(
                        local_port=cfg.port,
                        data_dir=getattr(cfg, "data_dir", Path("./data")),
                        bootstrap_anchor_url=getattr(cfg, "bootstrap_anchor_url", ""),
                        github_gist_id=getattr(cfg, "github_gist_id", ""),
                        github_gist_token=getattr(cfg, "github_gist_token", ""),
                    )
                    grid.tunnel_mgr = t_mgr
                pub_url = t_mgr.start()
                if pub_url:
                    grid.public_hub_url = pub_url
                return self._send(200, {
                    "ok": True,
                    "public_hub_url": pub_url or t_mgr.get_public_url(),
                    "status": t_mgr.status,
                })

            if path in {"/api/brain/self_play", "/api/brain/sync", "/api/brain/route", "/api/brain/fedavg", "/api/brain/swarm_infer"}:
                if not self._auth_ok():
                    return self._send(401, {"ok": False, "error": "unauthorized"})
                body = self._read_json_body(allow_empty=True)
                if body is None:
                    return
                if not getattr(grid, "brain_matrix", None):
                    return self._send(500, {"ok": False, "error": "brain_matrix not initialized"})
                if path == "/api/brain/self_play":
                    topic = str(body.get("topic") or body.get("prompt") or "Distributed Consensus & Sovereign Mesh Autonomy").strip()
                    sol = str(body.get("seed_solution") or f"[Sovereign Verified Solution]\nTopic: {topic}").strip()
                    try:
                        num_vars = int(body.get("num_variations", 4) or 4)
                    except (ValueError, TypeError):
                        num_vars = 4
                    res = grid.brain_matrix.run_self_play_freedom_loop(
                        seed_prompt=topic,
                        seed_solution=sol,
                        source_tier="Sovereign-Self-Play-Engine",
                        num_variations=num_vars,
                    )
                    return self._send(200, {
                        "ok": True,
                        **res,
                        "brain_matrix": grid.brain_matrix.autonomy_era_status(),
                    })
                if path == "/api/brain/sync":
                    shard = str(body.get("domain_shard") or "CODE_DEBUG_EXEC").strip()
                    try:
                        samples = int(body.get("synthetic_samples_added", 4) or 4)
                    except (ValueError, TypeError):
                        samples = 4
                    worker_grads = body.get("worker_gradients") if isinstance(body.get("worker_gradients"), list) else None
                    pkt = grid.brain_matrix.sync_p2p_weight_delta(
                        domain_shard=shard,
                        source_tier="Sovereign-P2P-Sync",
                        synthetic_samples_added=samples,
                        worker_gradients=worker_grads,
                    )
                    return self._send(200, {
                        "ok": True,
                        "delta_packet": pkt.to_dict() if hasattr(pkt, "to_dict") else pkt,
                        "survivability": grid.brain_matrix.verify_brain_survivability(),
                        "safetensors_checkpoints": grid.brain_matrix.get_safetensors_checkpoints(),
                        "brain_matrix": grid.brain_matrix.autonomy_era_status(),
                    })
                if path == "/api/brain/fedavg":
                    shard = str(body.get("domain_shard") or "CODE_DEBUG_EXEC").strip()
                    worker_grads = body.get("worker_gradients") if isinstance(body.get("worker_gradients"), list) else []
                    fed_res = grid.brain_matrix.federated_average_lora_deltas(
                        domain_shard=shard,
                        worker_packets=worker_grads,
                    )
                    return self._send(200 if fed_res.get("ok") else 400, {
                        **fed_res,
                        "brain_matrix": grid.brain_matrix.autonomy_era_status(),
                    })
                if path == "/api/brain/swarm_infer":
                    prompt_q = str(body.get("prompt") or "Synthesize sovereign mesh consensus").strip()
                    swarm_res = grid.brain_matrix.execute_parallel_swarm_reasoning(prompt_q)
                    return self._send(200, swarm_res)
                if path == "/api/brain/route":
                    prompt = str(body.get("prompt") or "").strip()
                    return self._send(200, {"ok": True, "route": grid.brain_matrix.route_attention(prompt)})

            if path in {
                "/api/learning/verify",
                "/api/learning/train",
                "/api/learning/approve_candidate",
                "/api/learning/reject_candidate",
                "/api/learning/kill_switch",
                "/api/learning/auto_gpu",
            }:
                if not self._auth_ok():
                    return self._send(401, {"ok": False, "error": "unauthorized"})
                body = self._read_json_body(allow_empty=True)
                if body is None:
                    return
                if not getattr(grid, "continuous_learning", None):
                    return self._send(500, {"ok": False, "error": "continuous_learning not initialized"})

                if path == "/api/learning/approve_candidate":
                    res = grid.continuous_learning.approve_staged_candidate(
                        approved_by=str(body.get("approved_by", "owner"))
                    )
                    return self._send(200 if res.get("ok") else 400, res)

                if path == "/api/learning/reject_candidate":
                    res = grid.continuous_learning.reject_staged_candidate(
                        reason=str(body.get("reason", "Rejected by Owner"))
                    )
                    return self._send(200 if res.get("ok") else 400, res)

                if path == "/api/learning/kill_switch":
                    engage = bool(body.get("engage", True))
                    if engage:
                        res = grid.continuous_learning.engage_kill_switch(
                            reason=str(body.get("reason", "Manual kill switch engaged via API"))
                        )
                    else:
                        res = grid.continuous_learning.release_kill_switch()
                    return self._send(200, res)

                if path == "/api/learning/auto_gpu":
                    lvl = int(body.get("level", 1) or 1)
                    if lvl <= 1:
                        grid.continuous_learning.stop_auto_gpu_training_daemon()
                        return self._send(200, grid.continuous_learning.start_auto_gpu_training_daemon(level=1))
                    res = grid.continuous_learning.start_auto_gpu_training_daemon(
                        level=lvl,
                        min_samples=int(body.get("min_samples", 100) or 100),
                        eval_limit=int(body.get("eval_limit", 140) or 140),
                        samples_per_task=max(5, int(body.get("samples_per_task", 5) or 5)),
                    )
                    return self._send(200 if res.get("ok") else 400, res)

                if path == "/api/learning/verify":
                    task_type = str(body.get("type", "code")).strip().lower()
                    if task_type == "code":
                        code = str(body.get("code", "")).strip()
                        assertions = str(body.get("test_assertions", "")).strip()
                        res = grid.continuous_learning.verifier.verify_code(code, test_assertions=assertions)
                    elif task_type == "math":
                        expr = str(body.get("expression", "")).strip()
                        exp_val = body.get("expected_value")
                        res = grid.continuous_learning.verifier.verify_math(expr, expected_val=exp_val)
                    elif task_type == "schema":
                        raw_json = str(body.get("raw_json", "")).strip()
                        keys = body.get("required_keys") if isinstance(body.get("required_keys"), list) else []
                        res = grid.continuous_learning.verifier.verify_json_schema(raw_json, keys)
                    else:
                        return self._send(400, {"ok": False, "error": f"Unknown verification type: {task_type}"})

                    if res.get("verified") and body.get("save_to_dataset"):
                        prompt_text = str(body.get("prompt", "Verified Objective Task")).strip()
                        sol_text = str(body.get("code") or body.get("expression") or body.get("raw_json", "")).strip()
                        proof_copy = dict(res)
                        saved = grid.continuous_learning.dataset_store.record_verified(
                            prompt=prompt_text,
                            solution=sol_text,
                            domain=str(body.get("domain", "GENERAL")),
                            proof=proof_copy,
                        )
                        res["saved_sample_id"] = saved.get("id")

                    return self._send(200 if res.get("verified") else 400, {"ok": bool(res.get("verified")), **res})

                if path == "/api/learning/train":
                    try:
                        epochs = int(body.get("epochs", 4) or 4)
                        min_samples = int(body.get("min_samples", 2) or 2)
                        res = grid.continuous_learning.run_training_and_deploy_cycle(epochs=epochs, min_samples=min_samples)
                        return self._send(200 if res.get("ok") else 400, res)
                    except RuntimeError as r_err:
                        if "TRAINING_UNAVAILABLE" in str(r_err):
                            return self._send(503, {"ok": False, "error": str(r_err), "status": "TRAINING_UNAVAILABLE"})
                        return self._send(500, {"ok": False, "error": str(r_err)})

            if path in {"/api/worker/register", "/api/worker/heartbeat", "/api/worker/submit_result", "/api/worker/enqueue_task"}:
                import secrets
                body = self._read_json_body(allow_empty=True)
                if body is None:
                    return

                if path == "/api/worker/submit_result":
                    settled = grid.hub.verify_and_settle(body) if getattr(grid, "hub", None) else {"ok": False, "error": "hub unavailable"}
                    return self._send(200 if settled.get("ok") else 400, settled)

                if path == "/api/worker/enqueue_task":
                    # Security & Economy Fix: enqueue_task requires Hub Owner auth OR a funded requester account key
                    is_owner = self._auth_ok()
                    funded_by_key = str(
                        body.get("funded_by_key")
                        or body.get("requester_key")
                        or self.headers.get("X-Worker-Key", "")
                    ).strip()
                    if not is_owner and not funded_by_key:
                        return self._send(401, {
                            "ok": False,
                            "error": "unauthorized: /api/worker/enqueue_task requires Hub Owner Bearer token or funded requester key",
                        })
                    wid = str(body.get("worker_id") or "").strip()
                    fkey = str(body.get("feature_key") or "brain_inference").strip()
                    payload_data = body.get("payload") if isinstance(body.get("payload"), dict) else {"prompt": str(body.get("prompt") or "")}
                    if not wid:
                        return self._send(400, {"ok": False, "error": "worker_id is required"})
                    funded_by_id = "owner_hub"
                    if not is_owner:
                        try:
                            req_worker = grid.hub.authenticate_worker_key(funded_by_key)
                        except PermissionError as p_err:
                            return self._send(401, {"ok": False, "error": str(p_err)})
                        if req_worker.worker_id == wid:
                            return self._send(403, {
                                "ok": False,
                                "error": "self_enqueued_task_forbidden: workers cannot enqueue or fund tasks for themselves",
                            })
                        funded_by_id = req_worker.worker_id
                    elif body.get("funded_by"):
                        funded_by_id = str(body.get("funded_by")).strip()
                    try:
                        pkt = grid.hub.enqueue_nat_task(wid, fkey, payload_data, funded_by=funded_by_id)
                        # Never leak nonce or hub_signature in enqueue_task HTTP response
                        safe_summary = {
                            "task_id": pkt["task_id"],
                            "worker_id": pkt["worker_id"],
                            "feature": pkt["feature"],
                            "issued_at": pkt["issued_at"],
                            "funded_by": pkt.get("funded_by", funded_by_id),
                            "funded_credits": pkt.get("funded_credits", 0),
                            "status": "QUEUED",
                        }
                        return self._send(200, {"ok": True, "queued_packet": safe_summary})
                    except PermissionError as p_err:
                        return self._send(403, {"ok": False, "error": str(p_err)})
                    except Exception as exc:
                        return self._send(400, {"ok": False, "error": str(exc)})

                if path == "/api/worker/register":
                    wid = body.get("worker_id") or f"worker-{secrets.token_hex(8)}"
                    wurl = body.get("url", "local")
                    payout = body.get("payout_address", "")
                    hw_uuid = body.get("hardware_uuid", "")
                    hw_spec = body.get("hardware_spec", "")
                    referred_by = body.get("referred_by", "")
                    client_ver = body.get("version", "")
                    q_addr = body.get("quantum_address", "")
                    q_pub = body.get("quantum_vault_pub") or {}
                    puf_seal = body.get("puf_seal", "")
                    pub_ip = body.get("public_ip") or (self.client_address[0] if self.client_address else "")
                    try:
                        rec = grid.hub.register_worker(
                            wid,
                            url=wurl,
                            hardware_uuid=hw_uuid,
                            public_ip=pub_ip,
                            hardware_spec=hw_spec,
                            referred_by=referred_by,
                            version=client_ver,
                            quantum_address=q_addr,
                            quantum_vault_pub=q_pub,
                            puf_seal=puf_seal,
                        )
                        if payout:
                            grid.hub.set_payout_address(wid, payout)
                        return self._send(200, {
                            "ok": True,
                            "worker_id": rec.worker_id,
                            "worker_key": rec.key,
                            "quantum_address": getattr(rec, "quantum_address", ""),
                            "crypto_security_level": getattr(rec, "crypto_security_level", "4096-Bit Hyper-Sovereign Quantum Vault"),
                            "puf_seal_active": bool(getattr(rec, "puf_seal", "")),
                            "credits": rec.credits,
                            "status": rec.status,
                            "payout_address": rec.payout_address,
                            "pow_challenge": rec.pow_challenge,
                            "hardware_spec": rec.hardware_spec,
                            "brain_shard": rec.brain_shard,
                            "replica_shards": rec.replica_shards,
                            "synced_deltas_count": rec.synced_deltas_count,
                            "referral_code": rec.referral_code,
                            "referred_by": rec.referred_by,
                            "referrals_count": rec.referrals_count,
                            "referral_bonus_credits": rec.referral_bonus_credits,
                            "protocol_version": getattr(rec, "protocol_version", "2026.5.0"),
                        })
                    except Exception as exc:
                        return self._send(400, {"ok": False, "error": str(exc)})

                if path == "/api/worker/heartbeat":
                    import hashlib
                    from .worker_package import WORKER_PROTOCOL_VERSION, get_worker_launcher_code
                    wid = str(body.get("worker_id", ""))
                    try:
                        cores = int(body.get("cores", 4) or 4)
                    except (ValueError, TypeError):
                        cores = 4
                    pow_nonce = body.get("pow_nonce")
                    hw_spec = str(body.get("hardware_spec", ""))
                    client_ver = str(body.get("version") or "").strip()
                    try:
                        client_deltas_count = int(body.get("synced_deltas_count", 0) or 0)
                    except (ValueError, TypeError):
                        client_deltas_count = 0
                    try:
                        rec = grid.hub.record_heartbeat(
                            wid, cores=cores, pow_nonce=pow_nonce, hardware_spec=hw_spec,
                            synced_deltas_count=client_deltas_count,
                        ) if getattr(grid, "hub", None) else None
                    except PermissionError as exc:
                        return self._send(403, {"ok": False, "pow_rejected": True, "error": str(exc)})
                    if not rec:
                        return self._send(404, {"ok": False, "error": "unknown worker"})

                    host = self.headers.get("Host") or f"{cfg.host}:{cfg.port}"
                    proto_hdr = self.headers.get("X-Forwarded-Proto", "").lower()
                    scheme = "https" if (proto_hdr == "https" or host.endswith(":443")) else "http"
                    hub_url = f"{scheme}://{host}"
                    launcher_code = get_worker_launcher_code(hub_url)
                    script_sha256 = hashlib.sha256(launcher_code.encode("utf-8")).hexdigest()
                    ota_sig = _sign_ota_payload(rec.worker_id, WORKER_PROTOCOL_VERSION, script_sha256)
                    ota_ed25519_sig, ota_ed25519_pub = _sign_ota_ed25519(WORKER_PROTOCOL_VERSION, script_sha256)

                    update_avail = bool(client_ver and client_ver != WORKER_PROTOCOL_VERSION)

                    deltas_count = 0
                    if getattr(grid, "brain_matrix", None):
                        with grid.brain_matrix._lock:
                            deltas_count = len([
                                d for d in grid.brain_matrix._deltas.values()
                                if rec.worker_id in d.holder_worker_ids or d.domain_shard == rec.brain_shard
                            ])
                    model_sync_available = (deltas_count > client_deltas_count)

                    halving = grid.hub.halving_epoch_info() if getattr(grid, "hub", None) else {}
                    pending_nat_tasks = grid.hub.pull_pending_tasks(rec.worker_id, max_tasks=3) if getattr(grid, "hub", None) else []
                    return self._send(200, {
                        "ok": True,
                        "worker_id": rec.worker_id,
                        "status": rec.status,
                        "credits": rec.credits,
                        "uptime_minutes_verified": rec.uptime_minutes_verified,
                        "pow_challenge": rec.pow_challenge,
                        "pow_verified_count": rec.pow_verified_count,
                        "hardware_spec": rec.hardware_spec,
                        "brain_shard": rec.brain_shard,
                        "replica_shards": rec.replica_shards,
                        "synced_deltas_count": rec.synced_deltas_count,
                        "referral_code": rec.referral_code,
                        "referrals_count": rec.referrals_count,
                        "referral_bonus_credits": rec.referral_bonus_credits,
                        "pending_payout_usd": rec.pending_payout,
                        "total_payout_earned_usd": rec.total_payout_earned,
                        "tasks_completed": rec.tasks_completed,
                        "tasks_verified": rec.tasks_verified,
                        "halving": halving,
                        "latest_version": WORKER_PROTOCOL_VERSION,
                        "update_available": update_avail,
                        "script_sha256": script_sha256,
                        "ota_signature": ota_sig,
                        "ota_ed25519_sig": ota_ed25519_sig,
                        "ota_ed25519_pub": ota_ed25519_pub,
                        "model_sync_available": model_sync_available,
                        "latest_deltas_count": deltas_count,
                        "ota_download_url": "/api/worker/ota_download",
                        "pending_tasks": pending_nat_tasks,
                        "nat_traversal_mode": "OUTBOUND_HTTP_PULL_QUEUE",
                    })

            if path.startswith("/api/p2p/"):
                body = self._read_json_body()
                if body is None:
                    return

                caller_id = self._caller_id()
                is_owner = (caller_id == grid.owner_tg_id)

                if path == "/api/p2p/buyback":
                    acc = str(body.get("account_key") or body.get("worker_id", "")).strip()
                    try:
                        wrec = grid.hub.authenticate_worker_key(acc) if (acc and getattr(grid, "hub", None)) else None
                    except PermissionError:
                        wrec = None
                    if not is_owner and (not wrec or wrec.worker_id != "owner-master"):
                        return self._send(403, {"ok": False, "error": "Only the Sovereign Owner (owner-master) can execute the Weekly Top 3 Miners Buyback."})
                    try:
                        pkr_each = float(body.get("reward_pkr_each", 500.0) or 500.0)
                        cr_each = int(body.get("credits_bought_each", 100) or 100)
                    except (ValueError, TypeError):
                        return self._send(400, {"ok": False, "error": "invalid numeric parameters"})
                    res = grid.hub.execute_weekly_top3_buyback(reward_pkr_each=pkr_each, credits_bought_each=cr_each)
                    return self._send(200 if res.get("ok") else 400, res)

                if path == "/api/p2p/sell":
                    raw_cred = str(body.get("account_key") or body.get("worker_id", ""))
                    wrec = self._require_secret_worker(raw_cred)
                    if not wrec:
                        return
                    method = str(body.get("payment_method", ""))
                    curr = str(body.get("currency", "PKR"))
                    try:
                        amt = int(body.get("amount", 0) or 0)
                        price = float(body.get("price", 0.0) or 0.0)
                        res = grid.p2p.create_sell_order(wrec.key, amt, price, method, currency=curr)
                        return self._send(200 if res.get("ok") else 400, res)
                    except Exception as exc:
                        return self._send(400, {"ok": False, "error": str(exc)})

                if path == "/api/p2p/buy_order":
                    raw_cred = str(body.get("account_key") or body.get("buyer_id") or body.get("worker_id", ""))
                    wrec = self._require_secret_worker(raw_cred)
                    if not wrec:
                        return
                    method = str(body.get("payment_method", "EasyPaisa / JazzCash"))
                    curr = str(body.get("currency", "PKR"))
                    try:
                        amt = int(body.get("amount", 0) or 0)
                        price = float(body.get("price", 0.0) or 0.0)
                        res = grid.p2p.create_buy_order(wrec.key, amt, price, method, currency=curr)
                        return self._send(200 if res.get("ok") else 400, res)
                    except Exception as exc:
                        return self._send(400, {"ok": False, "error": str(exc)})

                if path == "/api/p2p/accept_buy_order":
                    oid = body.get("order_id", "")
                    raw_cred = str(body.get("account_key") or body.get("seller_id") or body.get("worker_id", ""))
                    wrec = self._require_secret_worker(raw_cred)
                    if not wrec:
                        return
                    method = body.get("payment_method", "")
                    try:
                        res = grid.p2p.accept_buy_order(oid, wrec.key, seller_payment_method=method)
                        return self._send(200 if res.get("ok") else 400, res)
                    except Exception as exc:
                        return self._send(400, {"ok": False, "error": str(exc)})

                if path == "/api/p2p/buy":
                    oid = body.get("order_id", "")
                    raw_cred = str(body.get("account_key") or body.get("buyer_id") or body.get("worker_id", ""))
                    wrec = self._require_secret_worker(raw_cred)
                    if not wrec:
                        return
                    try:
                        res = grid.p2p.initiate_buy(oid, wrec.key)
                        return self._send(200 if res.get("ok") else 400, res)
                    except Exception as exc:
                        return self._send(400, {"ok": False, "error": str(exc)})

                if path == "/api/p2p/pay":
                    oid = body.get("order_id", "")
                    raw_cred = str(body.get("account_key") or body.get("buyer_id") or body.get("worker_id", ""))
                    wrec = self._require_secret_worker(raw_cred)
                    if not wrec:
                        return
                    ref = body.get("payment_reference", "")
                    try:
                        res = grid.p2p.submit_payment(oid, wrec.key, ref)
                        return self._send(200 if res.get("ok") else 400, res)
                    except Exception as exc:
                        return self._send(400, {"ok": False, "error": str(exc)})

                if path == "/api/p2p/dispute":
                    oid = body.get("order_id", "")
                    raw_cred = str(body.get("account_key") or body.get("caller_id") or body.get("worker_id", ""))
                    if not is_owner:
                        wrec = self._require_secret_worker(raw_cred)
                        if not wrec:
                            return
                        cid = wrec.key
                    else:
                        cid = raw_cred or "owner"
                    reason = body.get("reason", "Payment / Screenshot Dispute")
                    try:
                        res = grid.p2p.raise_dispute(oid, cid, reason=reason, is_owner=is_owner)
                        return self._send(200 if res.get("ok") else 400, res)
                    except Exception as exc:
                        return self._send(400, {"ok": False, "error": str(exc)})

                if path == "/api/p2p/release":
                    oid = body.get("order_id", "")
                    raw_cred = str(body.get("account_key") or body.get("seller_id") or body.get("worker_id", ""))
                    if not is_owner:
                        wrec = self._require_secret_worker(raw_cred)
                        if not wrec:
                            return
                        sid = wrec.key
                    else:
                        sid = raw_cred or "owner"
                    try:
                        res = grid.p2p.confirm_and_release(oid, sid, is_owner=is_owner)
                        return self._send(200 if res.get("ok") else 400, res)
                    except Exception as exc:
                        return self._send(400, {"ok": False, "error": str(exc)})

                if path == "/api/p2p/cancel":
                    oid = body.get("order_id", "")
                    raw_cred = str(body.get("account_key") or body.get("seller_id") or body.get("worker_id", ""))
                    if not is_owner:
                        wrec = self._require_secret_worker(raw_cred)
                        if not wrec:
                            return
                        sid = wrec.key
                    else:
                        sid = raw_cred or "owner"
                    try:
                        res = grid.p2p.cancel_order(oid, sid, is_owner=is_owner)
                        return self._send(200 if res.get("ok") else 400, res)
                    except Exception as exc:
                        return self._send(400, {"ok": False, "error": str(exc)})

                if path == "/api/p2p/transfer":
                    from_cred = str(body.get("account_key") or body.get("from_worker", ""))
                    wrec = self._require_secret_worker(from_cred)
                    if not wrec:
                        return
                    to_w = str(body.get("to_worker", ""))
                    try:
                        amt = int(body.get("amount", 0) or 0)
                        res = grid.hub.transfer_credits(wrec.worker_id, to_w, amt)
                        ok = bool(res.get("ok", res.get("status") == "TRANSFERRED"))
                        return self._send(200 if ok else 400, {"ok": ok, **res})
                    except Exception as exc:
                        return self._send(400, {"ok": False, "error": str(exc)})

            if path in {"/api/machine/connect", "/api/machine/command"}:
                if not self._auth_ok():
                    return self._send(401, {"ok": False, "error": "unauthorized"})
                import secrets
                body = self._read_json_body()
                if body is None:
                    return

                _ensure_default_machines(grid)

                if path == "/api/machine/connect":
                    mid = body.get("machine_id") or f"mach-{secrets.token_hex(6)}"
                    name = body.get("name", "Physical Machine")
                    mtype = body.get("type", "robotic_arm")
                    target = body.get("target", "COM3")
                    baud = body.get("baud", "115200")
                    fkey = "printer_3d_control" if mtype in ("3d_printer", "printer_3d") else ("robotic_arm_ros2" if mtype in ("robotic_arm", "arm") else "cnc_machine_control")

                    adapter = grid.adapters.get(fkey) if hasattr(grid, "adapters") else None
                    if adapter is None:
                        machine_record = {
                            "machine_id": mid,
                            "name": name,
                            "type": mtype,
                            "target": target,
                            "baud": baud,
                            "status": "ADAPTER_NOT_CONFIGURED",
                            "connected_at": None,
                            "last_telemetry": None,
                        }
                        grid.machines[mid] = machine_record
                        grid.ledger.append("machine_connect_failed", {"machine_id": mid, "reason": f"No active adapter registered for {fkey}"})
                        return self._send(400, {
                            "ok": False,
                            "status": "ADAPTER_NOT_CONFIGURED",
                            "machine": machine_record,
                            "error": f"Physical adapter for '{fkey}' is not configured. Connect requires real hardware handshake via grid.register_adapter('{fkey}', fn)."
                        })

                    try:
                        handshake = adapter(grid, {"command": "PING", "target": target, "baud": baud})
                        is_online = isinstance(handshake, dict) and handshake.get("status") in {"OK", "ONLINE"}
                    except Exception as exc:
                        handshake = {"status": "ERROR", "error": str(exc)}
                        is_online = False

                    status = "ONLINE" if is_online else "OFFLINE"
                    telemetry = handshake.get("telemetry") if is_online and isinstance(handshake, dict) else None
                    machine_record = {
                        "machine_id": mid,
                        "name": name,
                        "type": mtype,
                        "target": target,
                        "baud": baud,
                        "status": status,
                        "connected_at": time.time() if is_online else None,
                        "last_telemetry": telemetry,
                    }
                    grid.machines[mid] = machine_record
                    grid.ledger.append("machine_connected" if is_online else "machine_connect_failed", machine_record)
                    return self._send(200 if is_online else 400, {"ok": is_online, "machine": machine_record})

                if path == "/api/machine/command":
                    mid = str(body.get("machine_id", "")).strip()
                    cmd = str(body.get("command", "")).strip()
                    if mid.lower() == "all" and cmd in {"E-STOP", "EMERGENCY_STOP"}:
                        for m_obj in grid.machines.values():
                            m_obj["status"] = "HALTED"
                        grid.ledger.append("machine_estop_all", {"machines_halted": list(grid.machines.keys()), "time": time.time()})
                        return self._send(200, {"ok": True, "status": "HALTED", "message": "🛑 GLOBAL EMERGENCY STOP TRIPPED. All physical machines halted."})
                    m = grid.machines.get(mid)
                    if not m:
                        return self._send(404, {"ok": False, "error": f"Machine {mid} not found"})
                    if cmd in {"E-STOP", "EMERGENCY_STOP"}:
                        m["status"] = "HALTED"
                        grid.ledger.append("machine_estop", {"machine_id": mid, "time": time.time()})
                        return self._send(200, {"ok": True, "status": "HALTED", "message": "🛑 EMERGENCY STOP TRIPPED. Machine halted."})

                    fkey = "printer_3d_control" if m["type"] in ("3d_printer", "printer_3d") else ("robotic_arm_ros2" if m["type"] in ("robotic_arm", "arm") else "cnc_machine_control")
                    res = grid.run_feature(grid.owner_tg_id, fkey, {"command": cmd, "target": m["target"]})
                    inner_status = res.get("status", "UNKNOWN") if isinstance(res, dict) else "OK"
                    grid.ledger.append("machine_command_dispatched", {"machine_id": mid, "command": cmd, "status": inner_status, "result": res})
                    if inner_status == "PENDING_APPROVAL":
                        return self._send(202, {
                            "ok": True,
                            "machine_id": mid,
                            "command": cmd,
                            "status": "PENDING_APPROVAL",
                            "approval_id": res.get("approval_id"),
                            "result": res,
                        })
                    if inner_status in {"OK", "APPROVED_AND_EXECUTED"}:
                        return self._send(200, {
                            "ok": True,
                            "machine_id": mid,
                            "command": cmd,
                            "status": "EXECUTED",
                            "result": res,
                        })
                    return self._send(400, {
                        "ok": False,
                        "machine_id": mid,
                        "command": cmd,
                        "status": inner_status,
                        "result": res,
                    })

            if path in {
                "/api/supercomputer/rent",
                "/api/supercomputer/connect",
                "/api/supercomputer/job",
                "/api/supercomputer/pause",
                "/api/supercomputer/resume",
                "/api/supercomputer/terminate",
            }:
                body = self._read_json_body()
                if body is None:
                    return

                try:
                    if path == "/api/supercomputer/rent":
                        acc = str(body.get("account_key") or body.get("worker_id", "")).strip()
                        wrec = self._require_secret_worker(acc)
                        if not wrec:
                            return
                        tier = str(body.get("tier_name", "Cluster Node"))
                        cores = int(body.get("cores", 8) or 8)
                        ram = int(body.get("ram_gb", 32) or 32)
                        duration = int(body.get("duration_hours", 1) or 1)
                        auto_renew = bool(body.get("auto_renew", True))
                        res = grid.supercomputer.provision_server(wrec.key, tier, cores, ram, duration, auto_renew=auto_renew)
                        return self._send(200 if res.get("ok") else 400, res)

                    if path == "/api/supercomputer/connect":
                        iid = str(body.get("instance_id") or body.get("access_key_id", "")).strip()
                        secret = str(body.get("server_secret_key") or body.get("password", "")).strip()
                        res = grid.supercomputer.connect_server(iid, secret)
                        return self._send(200 if res.get("ok") else 403, res)

                    if path == "/api/supercomputer/job":
                        iid = str(body.get("instance_id") or body.get("access_key_id", "")).strip()
                        acc = str(body.get("account_key") or body.get("worker_id", "")).strip()
                        secret = str(body.get("server_secret_key") or body.get("password", "")).strip()
                        if acc and not secret:
                            wrec = self._require_secret_worker(acc)
                            if not wrec:
                                return
                            acc = wrec.key
                        job_name = str(body.get("job_name", "Distributed Task"))
                        code = str(body.get("payload_code", ""))
                        req_cores = int(body.get("requested_cores", 0) or 0)
                        res = grid.supercomputer.dispatch_job(
                            iid, acc, job_name, code, server_secret_key=secret, requested_cores=req_cores
                        )
                        return self._send(200 if res.get("ok") else 400, res)

                    if path in {"/api/supercomputer/pause", "/api/supercomputer/resume", "/api/supercomputer/terminate"}:
                        iid = str(body.get("instance_id") or body.get("access_key_id", "")).strip()
                        acc = str(body.get("account_key") or body.get("worker_id", "")).strip()
                        secret = str(body.get("server_secret_key") or body.get("password", "")).strip()
                        if not acc and not secret and self._caller_id() != grid.owner_tg_id:
                            return self._send(403, {"ok": False, "error": "Account Key or Server Secret Key is required"})
                        if acc and not secret:
                            wrec = self._require_secret_worker(acc)
                            if not wrec:
                                return
                            acc = wrec.key
                        if path == "/api/supercomputer/pause":
                            res = grid.supercomputer.pause_server(iid, acc, server_secret_key=secret)
                        elif path == "/api/supercomputer/resume":
                            res = grid.supercomputer.resume_server(iid, acc, server_secret_key=secret)
                        else:
                            res = grid.supercomputer.terminate_server(iid, acc, server_secret_key=secret)
                        return self._send(200 if res.get("ok") else 400, res)
                except (ValueError, TypeError, PermissionError, KeyError) as exc:
                    return self._send(400, {"ok": False, "error": str(exc)})

            if path == "/telegram/webhook":
                supplied = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
                if not cfg.webhook_secret or not hmac.compare_digest(supplied, cfg.webhook_secret):
                    return self._send(401, {"error": "unauthorized"})
                try:
                    length = int(self.headers.get("Content-Length", "0") or 0)
                except ValueError:
                    return self._send(400, {"error": "invalid Content-Length"})
                if length <= 0 or length > MAX_BODY:
                    return self._send(413, {"error": "bad length"})
                try:
                    update = json.loads(self.rfile.read(length))
                except ValueError:
                    return self._send(400, {"error": "bad json"})
                self._send(200, {"ok": True})  # ack fast; Telegram retries slow webhooks
                threading.Thread(target=self._process, args=(update,), daemon=True).start()
                return

            if path in {"/api/chat", "/api/run", "/api/ide/generate", "/api/ide/execute", "/api/ide/test",
                        "/api/ide/review", "/api/ide/agent_control", "/api/ide/file/save", "/api/ide/launch_vscode",
                        "/api/ide/projects/open", "/api/ide/projects/create"}:
                if not self._auth_ok():
                    return self._send(401, {"error": "unauthorized"})
                body = self._read_json_body()
                if body is None:
                    return

                acc_key = str(
                    body.get("account_key", "")
                    or self.headers.get("X-Account-Key", "")
                    or self._get_cookie("nexus_account_key")
                ).strip()
                user_ns = f"ip_{client_ip}"
                credits_info = None
                _free_paths = {"/api/ide/file/save", "/api/ide/launch_vscode", "/api/ide/projects/open", "/api/ide/projects/create"}
                if acc_key and getattr(grid, "hub", None) and path not in _free_paths:
                    from .models import compute_task_credit_cost, is_frontier_complex_task
                    if grid.hub.is_public_worker_id(acc_key):
                        return self._send(403, {
                            "ok": False,
                            "error": f"Security Notice: '{acc_key}' is a public Worker ID and cannot be used to spend credits. Please connect your private Secret Account Key."
                        })
                    wrec = grid.hub.get_worker_by_key(acc_key)
                    if not wrec:
                        return self._send(401, {
                            "ok": False,
                            "error": "Invalid or unregistered Secret Account Key (N3 Security Enforcement: auto-creation disabled).",
                        })
                    user_ns = wrec.worker_id

                    prompt_or_instr = (body.get("prompt") or body.get("instruction") or "").strip()
                    mode_str = (body.get("mode") or body.get("model_tier") or ("frontier" if body.get("frontier_mode") else "")).strip()
                    is_frontier_req = is_frontier_complex_task(prompt_or_instr, mode_str) if not prompt_or_instr.startswith("/") else False
                    is_cached_locally = False
                    if is_frontier_req and getattr(grid, "router", None) and grid.router.distillation_cache:
                        is_cached_locally = bool(grid.router.distillation_cache.find_similar(prompt_or_instr, namespace=user_ns))
                    required_credits = compute_task_credit_cost(prompt_or_instr, mode_str, cached_locally=is_cached_locally) if not prompt_or_instr.startswith("/") else 1

                    if wrec.credits < required_credits:
                        tier_note = (
                            "Hyper-Complex Frontier Task (GPT-6 Astra / Claude 5.5 Opus reasoning tier)"
                            if required_credits > 1 else "Standard Distributed Mesh Task"
                        )
                        return self._send(200, {
                            "ok": False,
                            "insufficient_credits": True,
                            "required_credits": required_credits,
                            "frontier_complex_task": required_credits > 1,
                            "error": (
                                f"Insufficient credits on account '{wrec.worker_id}' (Balance: {wrec.credits} cr, "
                                f"Required: {required_credits} cr for {tier_note}). "
                                f"Please buy credits on P2P Market or run your 1-click worker node."
                            ),
                        })
                    try:
                        spent = grid.hub.spend_credits(
                            wrec.worker_id,
                            required_credits,
                            reason=f"compute:{path}:{'frontier_cot' if required_credits > 1 else ('distilled_cache' if is_cached_locally else 'standard')}",
                        )
                    except PermissionError as exc:
                        return self._send(403, {"ok": False, "dispute_frozen": True, "error": str(exc)})
                    credits_info = {
                        "worker_id": wrec.worker_id,
                        "credits_charged": required_credits,
                        "task_tier": "LOCAL_DISTILLED" if is_cached_locally else ("FRONTIER_COMPLEX" if required_credits > 1 else "STANDARD_MESH"),
                        "distilled_from_cache": is_cached_locally,
                        "remaining_credits": spent.get("remaining_credits", wrec.credits),
                    }

                if path == "/api/ide/projects/open":
                    target_path = body.get("path", "").strip()
                    if not target_path:
                        return self._send(400, {"ok": False, "error": "path is required"})
                    p = Path(target_path).resolve()
                    try:
                        p.mkdir(parents=True, exist_ok=True)
                    except Exception as exc:
                        return self._send(400, {"ok": False, "error": f"Cannot access or create directory: {exc}"})
                    grid.active_project = str(p)
                    data_dir = getattr(grid.config, "data_dir", Path("./data"))
                    recent = add_recent_project(data_dir, str(p))
                    grid.ledger.append("project_opened", {"path": str(p)})
                    return self._send(200, {"ok": True, "project": str(p), "projects": recent, "message": f"Project opened: {p}"})

                if path == "/api/ide/projects/create":
                    name = body.get("name", "").strip()
                    folder = body.get("path", "").strip()
                    template = body.get("template", "python").lower()
                    if not folder and not name:
                        return self._send(400, {"ok": False, "error": "name or path is required"})
                    if folder:
                        p = Path(folder).resolve()
                    else:
                        base = Path(getattr(grid.config, "workspace_dir", "e:/NEXUS")) / "projects"
                        p = (base / name).resolve()
                    p.mkdir(parents=True, exist_ok=True)
                    main_py = p / "main.py"
                    if not main_py.exists():
                        if template == "fastapi":
                            main_py.write_text(
                                'from fastapi import FastAPI\n\napp = FastAPI(title="' + (name or p.name) + '")\n\n@app.get("/")\ndef read_root():\n    return {"message": "Hello from ' + (name or p.name) + '"}\n\nif __name__ == "__main__":\n    import uvicorn\n    uvicorn.run(app, host="127.0.0.1", port=8000)\n',
                                encoding="utf-8"
                            )
                        else:
                            main_py.write_text(
                                f'"""\nProject: {name or p.name}\nCreated with SUP Agentic Mesh IDE\n"""\n\ndef main():\n    print("Welcome to {name or p.name}!")\n\nif __name__ == "__main__":\n    main()\n',
                                encoding="utf-8"
                            )
                    readme_md = p / "README.md"
                    if not readme_md.exists():
                        readme_md.write_text(
                            f"# {name or p.name}\n\nCreated with SUP Agentic Mesh IDE.\nAutonomous agents have full capability to develop, test, and maintain this project.\n",
                            encoding="utf-8"
                        )
                    req_txt = p / "requirements.txt"
                    if not req_txt.exists():
                        req_txt.write_text("# Project dependencies\n", encoding="utf-8")

                    grid.active_project = str(p)
                    data_dir = getattr(grid.config, "data_dir", Path("./data"))
                    recent = add_recent_project(data_dir, str(p))
                    grid.ledger.append("project_created", {"path": str(p), "template": template})
                    return self._send(200, {"ok": True, "project": str(p), "projects": recent, "message": f"Project created successfully: {p}"})

                if path == "/api/ide/execute":
                    code = str(body.get("code", "")).strip()
                    if not code:
                        return self._send(400, {"error": "code is required"})
                    root = resolve_project_root(grid, str(body.get("project", "")).strip())
                    from .sandbox import compile_check, run_python
                    chk = compile_check(code)
                    if not chk["ok"]:
                        return self._send(200, {"ok": False, "compile": chk, "stdout": "", "stderr": chk.get("error", "SyntaxError")})
                    try:
                        timeout_val = float(body.get("timeout", 10.0) or 10.0)
                    except (ValueError, TypeError):
                        timeout_val = 10.0
                    res = run_python(code, enabled=bool(cfg.enable_code_execution), timeout=timeout_val, cwd=str(root))
                    if res.get("security_blocked"):
                        caller_acc = str(body.get("account_key", "")).strip()
                        if caller_acc and getattr(grid, "hub", None):
                            grid.hub.slash_worker(caller_acc, f"Malicious code in IDE execution: {res.get('error')}")
                        return self._send(403, {"ok": False, "security_blocked": True, "error": res.get("error")})
                    return self._send(200, {"ok": res["ok"], "compile": chk, "returncode": res.get("returncode"),
                                            "stdout": res.get("stdout", ""), "stderr": res.get("stderr", ""),
                                            "infinite_loop_caught": res.get("infinite_loop_caught", False)})

                if path == "/api/ide/generate":
                    prompt = str(body.get("prompt", "")).strip()
                    if not prompt:
                        return self._send(400, {"error": "prompt is required"})
                    mode = body.get("mode", "generate")
                    from .features.registry import extract_code
                    if mode == "debug_fix":
                        try:
                            max_iter = int(body.get("max_iterations", 3) or 3)
                        except (ValueError, TypeError):
                            max_iter = 3
                        res = grid.run_feature(grid.owner_tg_id, "code_debug_fix_loop", {
                            "text": prompt,
                            "code": body.get("code") or None,
                            "max_iterations": max_iter
                        })
                        return self._send(200, {"ok": res.get("status") in {"FIXED", "OK"}, "status": res.get("status"),
                                                "code": res.get("code", ""), "history": res.get("history", [])})
                    else:
                        try:
                            ask_res = grid.router.ask(
                                f"Write a complete, working Python script for: {prompt}\nInclude necessary imports and test code.",
                                system="Return ONLY executable Python code inside a ```python ``` code block. No extra conversational text.",
                                role="JIT Compiler"
                            )
                            code = extract_code(ask_res.get("text", ""))
                            return self._send(200, {"ok": True, "code": code, "model": ask_res.get("model")})
                        except Exception as exc:
                            res = grid.run_feature(grid.owner_tg_id, "code_generation_core", {"text": prompt})
                            code = extract_code(str(res.get("output", "")))
                            return self._send(200, {"ok": True, "code": code, "backend_note": str(exc)[:200]})

                if path == "/api/ide/test":
                    code = body.get("code", "").strip()
                    if not code:
                        return self._send(400, {"error": "code is required"})
                    from .features.registry import extract_code
                    from .sandbox import run_python
                    try:
                        test_gen = grid.router.ask(
                            f"Write a comprehensive unittest test script for the following Python code:\n```python\n{code}\n```\nMake sure tests run with unittest.main().",
                            system="Return ONLY the unittest Python code inside a ```python ``` code block.",
                            role="JIT Compiler"
                        )
                        test_code = extract_code(test_gen.get("text", ""))
                    except Exception:
                        res = grid.run_feature(grid.owner_tg_id, "test_generation_sandbox", {"text": code})
                        test_code = extract_code(str(res.get("output", "")))

                    root = resolve_project_root(grid, body.get("project", "").strip())
                    combined = f"{code}\n\n# --- AUTO-GENERATED TEST SUITE ---\n{test_code}"
                    exec_res = run_python(combined, enabled=bool(cfg.enable_code_execution), timeout=12.0, cwd=str(root))
                    return self._send(200, {
                        "ok": exec_res["ok"],
                        "test_code": test_code,
                        "returncode": exec_res.get("returncode"),
                        "stdout": exec_res.get("stdout", ""),
                        "stderr": exec_res.get("stderr", "")
                    })

                if path == "/api/ide/review":
                    code = body.get("code", "").strip()
                    if not code:
                        return self._send(400, {"error": "code is required"})
                    try:
                        rev_res = grid.router.ask(
                            f"Review this Python code for bugs, security vulnerabilities, and optimizations:\n```python\n{code}\n```",
                            system="Give severity-ranked findings: 1. Bugs/Flaws, 2. Security Risks, 3. Performance & Cleanliness.",
                            role="Validator"
                        )
                        return self._send(200, {"ok": True, "review": rev_res.get("text")})
                    except Exception:
                        res = grid.run_feature(grid.owner_tg_id, "automated_code_review", {"text": code})
                        return self._send(200, {"ok": True, "review": res.get("output", "")})

                if path == "/api/ide/launch_vscode":
                    import os, shutil
                    root = resolve_project_root(grid, body.get("project", "").strip())
                    try:
                        vscode_candidates = [
                            shutil.which("code"),
                            str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Microsoft VS Code" / "Code.exe"),
                            str(Path(os.environ.get("ProgramFiles", "")) / "Microsoft VS Code" / "Code.exe"),
                        ]
                        vscode_exe = next((c for c in vscode_candidates if c and Path(c).exists()), None)
                        if vscode_exe:
                            subprocess.Popen([vscode_exe, str(root)])
                        else:
                            subprocess.Popen(["code", str(root)])
                        return self._send(200, {"ok": True, "project": str(root), "message": f"Visual Studio Code Desktop launched for {root}"})
                    except Exception as exc:
                        return self._send(500, {"ok": False, "error": f"Failed to launch VS Code: {exc}"})

                if path == "/api/ide/file/save":
                    rel_path = body.get("path", "").strip()
                    content = body.get("content", "")
                    if not rel_path:
                        return self._send(400, {"ok": False, "error": "path is required"})
                    root = resolve_project_root(grid, body.get("project", "").strip())
                    target = (root / rel_path).resolve()
                    if not _is_safe_subpath(target, root):
                        return self._send(403, {"ok": False, "error": "access denied (path traversal blocked)"})
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(content, encoding="utf-8")
                    grid.ledger.append("ide_file_saved", {"path": rel_path, "project": str(root), "bytes": len(content)})
                    return self._send(200, {"ok": True, "path": rel_path, "project": str(root), "message": "File saved to disk successfully"})

                if path == "/api/ide/agent_control":
                    instruction = str(body.get("instruction", "")).strip()
                    target_file = str(body.get("target_file", "")).strip()
                    if not instruction:
                        return self._send(400, {"ok": False, "error": "instruction is required"})

                    if credits_info is None and acc_key and hasattr(grid, "hub") and grid.hub:
                        try:
                            credits_info = grid.hub.get_balance(acc_key)
                        except Exception:
                            pass

                    root = resolve_project_root(grid, body.get("project", "").strip())

                    existing_code = ""
                    if target_file:
                        tf_path = (root / target_file).resolve()
                        if _is_safe_subpath(tf_path, root) and tf_path.exists() and tf_path.is_file():
                            existing_code = tf_path.read_text(encoding="utf-8", errors="ignore")[:3500]

                    from .features.registry import extract_code
                    t0 = time.perf_counter()
                    prompt_agent = (
                        f"You are the Sovereign Mesh Autonomous Lead Developer Agent with full control over the workspace.\n"
                        f"User Goal: {instruction}\n"
                        f"Active Target File: {target_file or 'auto-select'}\n"
                        f"Current File Context:\n```\n{existing_code}\n```\n\n"
                        f"Implement the complete, production-ready solution. "
                        f"Return ONLY executable Python code inside a ```python ``` block."
                    )

                    try:
                        ask_res = grid.router.ask(prompt_agent, system="You are an autonomous AGI engineer. Return ONLY executable python code in code block.", role="JIT Compiler")
                        generated_code = extract_code(ask_res.get("text", ""))
                        plan_note = f"Agent analyzed requirement and generated {len(generated_code.splitlines())} lines of code."
                    except Exception as exc:
                        res = grid.run_feature(grid.owner_tg_id, "code_generation_core", {"text": instruction})
                        generated_code = extract_code(str(res.get("output", "")))
                        plan_note = f"Synthesized code via core JIT engine ({exc})."

                    dest_str = target_file if target_file else "agent_workspace_output.py"
                    dest_file = (root / dest_str).resolve()
                    file_saved = False
                    if _is_safe_subpath(dest_file, root) and generated_code:
                        dest_file.parent.mkdir(parents=True, exist_ok=True)
                        dest_file.write_text(generated_code, encoding="utf-8")
                        file_saved = True

                    from .sandbox import compile_check, run_python
                    chk = compile_check(generated_code)
                    test_output = ""
                    if chk["ok"] and generated_code:
                        run_res = run_python(generated_code, enabled=bool(cfg.enable_code_execution), timeout=10.0)
                        test_output = run_res.get("stdout", "") or run_res.get("stderr", "")

                    elapsed = round((time.perf_counter() - t0) * 1000 + 15.0, 1)

                    ledger_entry = grid.ledger.append("agent_autonomous_mission", {
                        "instruction": instruction,
                        "file": dest_str,
                        "file_saved": file_saved,
                        "lines": len(generated_code.splitlines()),
                        "compile_ok": chk["ok"],
                        "elapsed_ms": elapsed
                    })

                    return self._send(200, {
                        "ok": True,
                        "instruction": instruction,
                        "target_file": dest_str,
                        "file_saved": file_saved,
                        "code": generated_code,
                        "plan_note": plan_note,
                        "compile_check": chk,
                        "test_output": test_output[:1200],
                        "elapsed_ms": elapsed,
                        "ledger_block": ledger_entry["hash"][:16],
                        "credits_info": credits_info
                    })

                caller_id = self._caller_id()
                if credits_info and credits_info.get("worker_id") == "owner-master":
                    caller_id = grid.owner_tg_id

                if path == "/api/run":
                    feature_key = body.get("feature", "")
                    payload = body.get("payload", {})
                    if not feature_key:
                        return self._send(400, {"error": "feature is required"})
                    if isinstance(payload, dict) and "session" not in payload:
                        payload = {**payload, "session": user_ns}
                    res = grid.run_feature(caller_id, feature_key, payload)
                    return self._send(200, res)

                # /api/chat
                prompt = body.get("prompt", "").strip()
                if not prompt:
                    return self._send(400, {"error": "prompt is required"})
                if len(prompt) > 16000:
                    return self._send(413, {"ok": False, "error": "Prompt exceeds 16,000 character Cost-DoS safety limit (H12)."})
                if prompt.startswith("/"):
                    intent, p_load, passph = parse_command(prompt)
                    res = grid.process_telegram_inbound_signal(caller_id, intent, p_load, passph)
                    return self._send(200, {"ok": True, "reply": res.get("tele_response"), "result": res, "credits_info": credits_info})

                feature = body.get("feature")
                if feature:
                    feat_payload = body.get("payload") or {"prompt": prompt}
                    if isinstance(feat_payload, dict) and "session" not in feat_payload:
                        feat_payload = {**feat_payload, "session": user_ns}
                    res = grid.run_feature(caller_id, feature, feat_payload)
                    return self._send(200, {"ok": True, "feature": feature, "result": res, "credits_info": credits_info})

                from .models import enforce_brand_identity, is_identity_question
                if is_identity_question(prompt):
                    return self._send(200, {
                        "ok": True,
                        "reply": enforce_brand_identity(prompt, ""),
                        "model": "SUP Agentic Mesh (Powered by NEXUS)",
                        "credits_info": credits_info
                    })

                # Try LLM ask, fall back to NLU (with CoT Knowledge Distillation Cache)
                from .models import is_frontier_complex_task
                mode_str = (body.get("mode") or body.get("model_tier") or ("frontier" if body.get("frontier_mode") else "")).strip()
                frontier_flag = is_frontier_complex_task(prompt, mode_str)
                if frontier_flag and caller_id != grid.owner_tg_id and credits_info is None:
                    return self._send(401, {
                        "ok": False,
                        "error": "Security Enforcement (H12): Frontier LLM reasoning requires a valid Secret Account Key with credits.",
                    })
                swarm_parallel = grid.brain_matrix.execute_parallel_swarm_reasoning(prompt) if getattr(grid, "brain_matrix", None) else None
                try:
                    ask_res = grid.router.ask(
                        prompt,
                        system="You are SUP Agentic Mesh powered by NEXUS. Answer helpfully, accurately, and concisely.",
                        frontier_mode=frontier_flag,
                        namespace=user_ns,
                        user_id=user_ns,
                    )
                    return self._send(200, {
                        "ok": True,
                        "reply": enforce_brand_identity(prompt, ask_res.get("text", "")),
                        "model": "SUP Agentic Mesh (Powered by NEXUS)",
                        "latency_s": ask_res.get("latency_s"),
                        "distilled_from_cache": ask_res.get("distilled_from_cache", False),
                        "cot_reasoning": ask_res.get("cot_reasoning", ""),
                        "attention_route": ask_res.get("attention_route"),
                        "self_play_freedom_loop": ask_res.get("self_play_freedom_loop"),
                        "swarm_parallel": swarm_parallel,
                        "distillation_stats": grid.router.distillation_stats() if getattr(grid, "router", None) else {},
                        "brain_matrix": grid.brain_matrix.autonomy_era_status() if getattr(grid, "brain_matrix", None) else {},
                        "credits_info": credits_info,
                    })
                except Exception as exc:
                    nlu_res = grid.run_feature(grid.owner_tg_id, "natural_language_understanding", {"text": prompt, "session": user_ns})
                    raw_reply = enforce_brand_identity(prompt, str(nlu_res.get("output") or nlu_res.get("intent") or nlu_res))
                    cot_reasoning = ""
                    att_route = grid.brain_matrix.route_attention(prompt) if getattr(grid, "brain_matrix", None) else None
                    sp_res = None
                    if frontier_flag and getattr(grid, "router", None) and grid.router.distillation_cache:
                        cot_reasoning = (
                            f"[Frontier CoT Distillation -> Local Mesh Fine-Tuning]\n"
                            f"1. Task Analysis: {prompt[:160]}\n"
                            f"2. Synthesized Solution cached locally for zero-API future reuse."
                        )
                        grid.router.distillation_cache.record(
                            prompt=prompt,
                            response_text=raw_reply,
                            cot_reasoning=cot_reasoning,
                            source_tier="Local-CoT-Distiller",
                            namespace=user_ns,
                        )
                        if getattr(grid, "brain_matrix", None):
                            sp_res = grid.brain_matrix.run_self_play_freedom_loop(
                                seed_prompt=prompt,
                                seed_solution=raw_reply,
                                source_tier="Local-CoT-Distiller",
                                num_variations=3,
                            )
                    return self._send(200, {
                        "ok": True,
                        "reply": raw_reply,
                        "model": "SUP Agentic Mesh (Powered by NEXUS)",
                        "result": nlu_res,
                        "distilled_from_cache": False,
                        "cot_reasoning": cot_reasoning,
                        "attention_route": att_route,
                        "self_play_freedom_loop": sp_res,
                        "swarm_parallel": swarm_parallel,
                        "distillation_stats": grid.router.distillation_stats() if getattr(grid, "router", None) else {},
                        "brain_matrix": grid.brain_matrix.autonomy_era_status() if getattr(grid, "brain_matrix", None) else {},
                        "credits_info": credits_info,
                        "backend_note": str(exc)[:200],
                    })

            return self._send(404, {"error": "not found"})

        @staticmethod
        def _process(update):
            try:
                handle_update(grid, client, update)
            except Exception as exc:  # noqa: BLE001
                print(f"[HTTP] update handler error: {exc!r}")

    return Handler


class _ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    _conn_semaphore = threading.BoundedSemaphore(64)

    def process_request_thread(self, request, client_address):
        with self._conn_semaphore:
            super().process_request_thread(request, client_address)


def _start_builtin_spoke_worker(grid) -> tuple[str, int]:
    """Starts a built-in local Spoke Worker Node in a daemon thread and registers it with the Hub."""
    from .hub_spoke import LightweightWorkerNode

    worker_id = "worker-local-01"
    rec = grid.hub.get_worker(worker_id)
    if not rec:
        rec = grid.hub.register_worker(worker_id, url="http://127.0.0.1:8444", initial_credits=100)
    worker_node = LightweightWorkerNode(worker_id, rec.key, grid)

    class _LocalWorkerHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def do_GET(self):  # noqa: N802
            clean_path = self.path.split("?", 1)[0]
            if clean_path in {"/", "/dashboard"}:
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:8443/?account_key={rec.key}")
                self.end_headers()
                return
            if clean_path == "/status":
                html_page = f"<html><body><h2>NEXUS Built-in Worker Online</h2><p>Worker ID: {worker_id}</p><p><a href='http://127.0.0.1:8443/?account_key={rec.key}'>Open Studio</a></p></body></html>"
                data = html_page.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:8443")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(data)
                return
            if clean_path == "/api/status":
                payload = {
                    "ok": True,
                    "worker_id": worker_id,
                    "worker_key": rec.key,
                    "credits": rec.credits,
                    "jobs_completed": rec.tasks_completed,
                    "pending_payout": rec.pending_payout,
                    "total_earned": rec.total_payout_earned,
                    "payout_address": rec.payout_address,
                    "hardware_spec": rec.hardware_spec,
                    "brain_shard": rec.brain_shard,
                    "replica_shards": list(rec.replica_shards),
                    "synced_deltas_count": rec.synced_deltas_count,
                    "referral_code": rec.referral_code,
                    "referred_by": rec.referred_by,
                    "referral_bonus_credits": rec.referral_bonus_credits,
                    "hub_url": "http://127.0.0.1:8443",
                }
                out = json.dumps(payload, default=str).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:8443")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(out)
                return
            self.send_response(404)
            self.end_headers()

        def do_POST(self):  # noqa: N802
            if self.path != "/worker/execute":
                self.send_response(404)
                self.end_headers()
                return
            try:
                length = int(self.headers.get("Content-Length", "0") or 0)
            except ValueError:
                self.send_response(400)
                self.end_headers()
                return
            if length < 0 or length > MAX_BODY:
                self.send_response(413)
                self.end_headers()
                return
            try:
                packet = json.loads(self.rfile.read(length)) if length > 0 else {}
            except ValueError:
                self.send_response(400)
                self.end_headers()
                return
            out = json.dumps(worker_node.execute_signed_task(packet), default=str).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(out)

    bound_port = 0
    for candidate_port in range(8444, 8465):
        try:
            srv = _ReusableThreadingHTTPServer(("127.0.0.1", candidate_port), _LocalWorkerHandler)
            bound_port = candidate_port
            rec.url = f"http://127.0.0.1:{bound_port}"
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            threading.Thread(target=lambda: (grid.shutdown_event.wait(), srv.shutdown()), daemon=True).start()
            break
        except OSError:
            continue
    return worker_id, bound_port


def _ensure_owner_studio_account(grid) -> tuple[str, str, int]:
    """Ensures a persistent Owner Studio account exists and returns (worker_id, secret_key, credits)."""
    data_dir = Path(getattr(grid.config, "data_dir", Path("./data")))
    data_dir.mkdir(parents=True, exist_ok=True)
    owner_file = data_dir / "owner_account.json"
    saved_key = ""
    if owner_file.exists():
        try:
            with interprocess_file_lock(owner_file):
                saved_key = json.loads(owner_file.read_text(encoding="utf-8")).get("account_key", "")
        except Exception:
            pass
    rec = grid.hub.get_worker("owner-master")
    if not rec:
        rec = grid.hub.register_worker("owner-master", url="local", initial_credits=1000)
        if saved_key and len(saved_key) >= 32:
            rec.key = saved_key
            if hasattr(grid.hub, "_flush"):
                grid.hub._flush()
    with interprocess_file_lock(owner_file):
        tmp = owner_file.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "worker_id": rec.worker_id,
                "account_key": rec.key,
            }, indent=2))
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except OSError:
                pass
        tmp.replace(owner_file)
    return rec.worker_id, rec.key, rec.credits


def serve(grid, open_browser: bool = False) -> None:
    import os
    import ssl
    import sys
    import webbrowser

    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    cfg = grid.config
    owner_wid, owner_key, owner_credits = _ensure_owner_studio_account(grid)
    spoke_id, spoke_port = _start_builtin_spoke_worker(grid)

    client = TelegramClient(cfg.telegram_bot_token) if cfg.telegram_bot_token else None
    tg_status = "DISABLED (No TELEGRAM_BOT_TOKEN in .env)"
    if client:
        grid.notifier = lambda text: client.send_message(cfg.owner_telegram_id, text)
        if cfg.public_webhook_url and cfg.webhook_secret:
            res = client.set_webhook(cfg.public_webhook_url.rstrip("/") + "/telegram/webhook", cfg.webhook_secret)
            tg_status = f"WEBHOOK ACTIVE ({res.get('ok')})"
        else:
            from .telegram_gateway import run_long_polling
            t_poll = threading.Thread(target=run_long_polling, args=(grid, client), daemon=True)
            t_poll.start()
            tg_status = f"ONLINE & POLLING (Owner Telegram ID: {cfg.owner_telegram_id})"

        # Send non-blocking startup notification to Owner Telegram
        def _notify_startup():
            try:
                client.send_message(
                    cfg.owner_telegram_id,
                    f"⚡ SUP Agentic Mesh (Powered by NEXUS) is ONLINE!\n"
                    f"🌐 Web Studio: http://localhost:{cfg.port}\n"
                    f"🔑 Owner Account ID: {owner_wid} ({owner_credits} Credits)\n"
                    f"🖥️ Local Spoke Worker: {spoke_id} (port {spoke_port})\n"
                    f"🛡️ All 130 Features, P2P Market & Supercomputer Cluster Ready."
                )
            except Exception:
                pass

        threading.Thread(target=_notify_startup, daemon=True).start()

    from .tunnel import PublicTunnelManager
    tunnel_mgr = PublicTunnelManager(
        local_port=cfg.port,
        data_dir=getattr(cfg, "data_dir", Path("./data")),
        bootstrap_anchor_url=getattr(cfg, "bootstrap_anchor_url", ""),
        github_gist_id=getattr(cfg, "github_gist_id", ""),
        github_gist_token=getattr(cfg, "github_gist_token", ""),
    )
    grid.tunnel_mgr = tunnel_mgr
    grid.public_hub_url = None
    if getattr(cfg, "enable_tunnel", False) or os.environ.get("ENABLE_TUNNEL", "").strip() in {"1", "true", "yes"} or os.environ.get("PUBLIC_HUB_URL") or os.environ.get("CLOUDFLARE_TUNNEL_URL"):
        grid.public_hub_url = tunnel_mgr.start()
    else:
        grid.public_hub_url = tunnel_mgr.get_public_url()

    httpd = _ReusableThreadingHTTPServer((cfg.host, cfg.port), make_handler(grid, client))
    scheme = "http"
    tls_cert = getattr(cfg, "tls_cert_file", "")
    tls_key = getattr(cfg, "tls_key_file", "")
    is_non_loopback = cfg.host not in ("127.0.0.1", "localhost", "::1")
    enable_tls = bool(tls_cert and tls_key) or is_non_loopback or os.environ.get("ENABLE_TLS", "").strip().lower() in {"1", "true", "yes"}
    if enable_tls and os.environ.get("NEXUS_ALLOW_INSECURE_HTTP", "") != "1":
        if not (tls_cert and tls_key and Path(tls_cert).exists() and Path(tls_key).exists()):
            tls_cert, tls_key = ensure_tls_certificates(getattr(cfg, "data_dir", Path("./data")))
    if tls_cert and tls_key and Path(tls_cert).exists() and Path(tls_key).exists():
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ssl_ctx.load_cert_chain(certfile=tls_cert, keyfile=tls_key)
        httpd.socket = ssl_ctx.wrap_socket(httpd.socket, server_side=True)
        scheme = "https"

    grid.start()
    threading.Thread(target=lambda: (grid.shutdown_event.wait(), tunnel_mgr.stop(), httpd.shutdown()), daemon=True).start()

    studio_url = f"{scheme}://localhost:{cfg.port}"
    auto_login_url = f"{studio_url}/?account_key={owner_key}"
    masked_owner_key = f"{owner_key[:6]}...{owner_key[-4:]} (saved in data/owner_account.json)" if len(owner_key) >= 12 else "[REDACTED]"
    public_status_line = grid.public_hub_url if grid.public_hub_url else "Localhost Only (Use --tunnel or ENABLE_TUNNEL=1 for Cloudflare HTTPS)"

    print("=" * 72)
    print("  [*] SUP AGENTIC MESH (POWERED BY NEXUS) - ALL SYSTEMS ONLINE")
    print("=" * 72)
    print(f"  [1] Main Web Studio & IDE : {studio_url}")
    print(f"  [2] Owner Auto-Login URL  : {studio_url}/ (key stored in data/owner_account.json)")
    print(f"  [3] Owner Secret Key      : {masked_owner_key}")
    print(f"  [4] Owner Telegram Bot    : {tg_status}")
    print(f"  [5] Built-in Worker Node  : {spoke_id} (http://127.0.0.1:{spoke_port})")
    print(f"  [6] Capabilities Active   : {len(grid.registry)} Features | P2P Market | Supercomputer")
    print(f"  [7] Public Cloud HTTPS    : {public_status_line}")
    print("=" * 72, flush=True)

    if open_browser and os.environ.get("NO_BROWSER", "").strip() not in {"1", "true", "yes"}:
        try:
            webbrowser.open(auto_login_url)
        except Exception:
            pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Shutting down SUP Agentic Mesh gracefully...")
        grid.stop()



