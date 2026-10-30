"""Cloudflare Tunnel & Public HTTPS Gateway Manager for Sovereign Mesh.

Enables any Sovereign Mesh Hub running on localhost to become instantly reachable
worldwide over a secure public HTTPS/WSS URL without requiring port forwarding,
static IPs, dynamic DNS, or VPS expenditures.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Dict, Any


class PublicTunnelManager:
    """Manages an automatic Cloudflare Tunnel (cloudflared) process and zero-cost Dynamic Bootstrap Anchors."""

    def __init__(
        self,
        local_port: int = 8443,
        data_dir: Optional[Path] = None,
        bootstrap_anchor_url: str = "",
        github_gist_id: str = "",
        github_gist_token: str = "",
    ):
        self.local_port = int(local_port)
        self.data_dir = Path(data_dir) if data_dir else Path("./data")
        self.bootstrap_anchor_url = (bootstrap_anchor_url or os.environ.get("BOOTSTRAP_ANCHOR_URL") or os.environ.get("NEXUS_BOOTSTRAP_URL") or "").strip()
        self.github_gist_id = (github_gist_id or os.environ.get("GITHUB_GIST_ID") or os.environ.get("NEXUS_GIST_ID") or "").strip()
        self.github_gist_token = (github_gist_token or os.environ.get("GITHUB_GIST_TOKEN") or os.environ.get("NEXUS_GIST_TOKEN") or "").strip()
        self.public_url: Optional[str] = None
        self._proc: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self.status = "IDLE"

    def get_public_url(self) -> Optional[str]:
        # 1. Check explicit environment override
        env_url = (os.environ.get("PUBLIC_HUB_URL") or os.environ.get("CLOUDFLARE_TUNNEL_URL") or "").strip()
        if env_url:
            return env_url.rstrip("/")
        with self._lock:
            return self.public_url

    def publish_to_bootstrap(self, public_url: str) -> Dict[str, Any]:
        """Publishes the newly minted public HTTPS URL to local state and remote fixed Bootstrap Anchors (e.g. GitHub Gist)."""
        clean_url = (public_url or "").strip().rstrip("/")
        if not clean_url:
            return {"ok": False, "error": "empty_url"}

        results = {"ok": True, "public_url": clean_url, "local_state_saved": False, "gist_updated": False}

        # 1. Always record in local persistent data directory
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            active_file = self.data_dir / "public_tunnel_active.json"
            active_file.write_text(json.dumps({
                "active_hub_url": clean_url,
                "local_port": self.local_port,
                "status": "ONLINE",
                "updated_at": time.time(),
                "iso_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }, indent=2), encoding="utf-8")
            results["local_state_saved"] = True
        except Exception as exc:
            results["local_save_error"] = str(exc)

        # 2. If GitHub Gist ID and Token are configured, update the fixed GitHub Gist (Problem #2 Zero-Cost Hal)
        if self.github_gist_id and self.github_gist_token:
            try:
                gist_url = f"https://api.github.com/gists/{self.github_gist_id}"
                gist_payload = json.dumps({
                    "description": "NEXUS Sovereign Mesh - Autonomous Dynamic Hub Bootstrap Anchor",
                    "files": {
                        "nexus_hub_endpoint.json": {
                            "content": json.dumps({
                                "active_hub_url": clean_url,
                                "local_port": self.local_port,
                                "status": "ONLINE",
                                "updated_at": time.time(),
                                "protocol_version": "2026.4.2",
                            }, indent=2)
                        }
                    }
                }).encode("utf-8")
                req = urllib.request.Request(
                    gist_url,
                    data=gist_payload,
                    method="PATCH",
                    headers={
                        "Authorization": f"token {self.github_gist_token}",
                        "Accept": "application/vnd.github+json",
                        "Content-Type": "application/json",
                        "User-Agent": "Nexus-Bootstrap-Publisher/2026.4.2",
                    },
                )
                with urllib.request.urlopen(req, timeout=6.0) as resp:
                    if resp.status in (200, 201):
                        results["gist_updated"] = True
                        print(f"[+] [Bootstrap-Anchor] Successfully updated GitHub Gist ({self.github_gist_id}) with new Hub URL: {clean_url}")
            except Exception as exc:
                results["gist_update_error"] = str(exc)
                print(f"[!] [Bootstrap-Anchor] Gist publication notice: {exc}")

        return results

    @staticmethod
    def resolve_bootstrap_hub_url(bootstrap_source: str) -> Optional[str]:
        """Resolves the current active Hub URL from a remote fixed anchor (GitHub Gist raw URL, Pastebin, or JSON endpoint)."""
        source = (bootstrap_source or "").strip()
        if not source:
            return None
        try:
            req = urllib.request.Request(
                source,
                headers={"User-Agent": "Nexus-Worker-Bootstrap-Resolver/2026.4.2", "Accept": "*/*"}
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                raw = resp.read().decode("utf-8").strip()
                # Case 1: JSON payload with active_hub_url
                if raw.startswith("{"):
                    data = json.loads(raw)
                    if isinstance(data, dict):
                        found = data.get("active_hub_url") or data.get("hub_url") or data.get("url")
                        if found and str(found).startswith("http"):
                            return str(found).strip().rstrip("/")
                # Case 2: Plain text URL
                for line in raw.splitlines():
                    clean = line.strip()
                    if clean.startswith("http://") or clean.startswith("https://"):
                        return clean.rstrip("/")
        except Exception:
            pass
        return None

    def find_cloudflared_binary(self) -> Optional[str]:
        # Check PATH
        path_bin = shutil.which("cloudflared")
        if path_bin and Path(path_bin).exists():
            return path_bin

        # Check local data dir or standard Windows/Linux locations
        candidates = [
            self.data_dir / "bin" / ("cloudflared.exe" if sys.platform == "win32" else "cloudflared"),
            Path("./cloudflared.exe"),
            Path("./bin/cloudflared.exe"),
            Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "cloudflared" / "cloudflared.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "cloudflared" / "cloudflared.exe",
        ]
        for c in candidates:
            if c.exists() and c.is_file():
                return str(c.resolve())
        return None

    def start(self, auto_download: bool = False) -> Optional[str]:
        """Starts cloudflared quick-tunnel and returns public HTTPS URL."""
        existing = self.get_public_url()
        if existing:
            self.status = "ACTIVE_ENV_OVERRIDE"
            self.publish_to_bootstrap(existing)
            return existing

        bin_path = self.find_cloudflared_binary()
        if not bin_path:
            self.status = "CLOUDFLARED_NOT_FOUND"
            print(f"[*] [Public-Tunnel] Notice: cloudflared binary not found in PATH or {self.data_dir}.")
            print(f"[*] [Public-Tunnel] To enable free worldwide HTTPS access: run 'cloudflared tunnel --url http://127.0.0.1:{self.local_port}' or set PUBLIC_HUB_URL=https://your-domain.com")
            return None

        cmd = [bin_path, "tunnel", "--url", f"http://127.0.0.1:{self.local_port}"]
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            self.status = "STARTING"
            print(f"[*] [Public-Tunnel] Launching Cloudflare Tunnel for port {self.local_port}...")
            
            # Read stderr/stdout in background to capture https://*.trycloudflare.com
            found_event = threading.Event()

            def _reader():
                url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
                stream = self._proc.stderr if self._proc and self._proc.stderr else self._proc.stdout
                if not stream:
                    return
                for line in iter(stream.readline, ""):
                    if self._stop_event.is_set():
                        break
                    match = url_pattern.search(line)
                    if match:
                        with self._lock:
                            self.public_url = match.group(0).strip()
                            self.status = "ONLINE"
                        self.publish_to_bootstrap(self.public_url)
                        print(f"\n⚡ [Public-Tunnel] Public HTTPS Endpoint Active: {self.public_url}")
                        print(f"🌐 [Public-Tunnel] Remote edge workers anywhere in the world can now connect!\n")
                        found_event.set()

            self._thread = threading.Thread(target=_reader, daemon=True)
            self._thread.start()
            found_event.wait(timeout=10.0)
            return self.get_public_url()
        except Exception as exc:
            self.status = f"ERROR: {exc}"
            print(f"[!] [Public-Tunnel] Failed to spawn cloudflared: {exc}")
            return None

    def stop(self) -> None:
        self._stop_event.set()
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=2.0)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None
        self.status = "STOPPED"
