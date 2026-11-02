"""Runtime configuration, loaded from environment variables."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# NOTE: "Llama-3.2-8B" does not exist (Llama 3.2 ships 1B/3B/11B/90B); the 8B model is Llama 3.1.
DEFAULT_MESH: List[dict] = [
    {"name": "Llama-3.1-8B-Node", "role": "Validator", "model": "llama3.1:8b"},
    {"name": "Mistral-7B-Instruct", "role": "Analysis Engine", "model": "mistral:7b-instruct"},
    {"name": "GPT-OSS-Core", "role": "JIT Compiler", "model": "gpt-oss:20b"},
]


class ConfigError(ValueError):
    pass


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


@dataclass
class GridConfig:
    owner_telegram_id: int
    master_passphrase_hash: str
    telegram_bot_token: str = ""
    webhook_secret: str = ""
    public_webhook_url: str = ""
    dashboard_token: str = ""
    peer_shared_secret: str = ""
    host: str = "127.0.0.1"
    port: int = 8443
    tls_cert_file: str = ""
    tls_key_file: str = ""
    ollama_url: str = "http://localhost:11434"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_timeout_s: float = 120.0
    mesh: List[dict] = field(default_factory=lambda: [dict(m) for m in DEFAULT_MESH])
    data_dir: Path = Path("./data")
    peers: List[dict] = field(default_factory=list)
    collaborators: Dict[int, str] = field(default_factory=dict)
    enable_code_execution: bool = False
    simulate_offline_consensus: bool = False
    token_budget: int = 500_000
    enable_tunnel: bool = False
    public_hub_url: str = ""
    bootstrap_anchor_url: str = ""
    github_gist_id: str = ""
    github_gist_token: str = ""

    @classmethod
    def from_env(cls, env_path: Optional[Path] = None) -> "GridConfig":
        from .security import hash_passphrase

        p = env_path or Path(".env")
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k = k.strip()
                v = v.strip().strip("'").strip('"')
                if k and k not in os.environ:
                    os.environ[k] = v

        owner_raw = os.environ.get("OWNER_TELEGRAM_ID", "").strip()
        try:
            owner_id = int(owner_raw)
        except ValueError as exc:
            raise ConfigError("OWNER_TELEGRAM_ID must be your numeric Telegram user id") from exc

        pw_hash = os.environ.get("MASTER_PASSPHRASE_HASH", "").strip()
        if not pw_hash:
            plain = os.environ.pop("MASTER_PASSPHRASE", "")
            if len(plain) < 12:
                raise ConfigError(
                    "Set MASTER_PASSPHRASE_HASH (preferred; see `python -m sovereign_mesh hash-passphrase`) "
                    "or MASTER_PASSPHRASE (>= 12 chars)"
                )
            pw_hash = hash_passphrase(plain)
            del plain

        mesh = [dict(m) for m in DEFAULT_MESH]
        if os.environ.get("MESH_CONFIG_JSON"):
            try:
                mesh = json.loads(os.environ["MESH_CONFIG_JSON"])
            except ValueError as exc:
                raise ConfigError(f"Invalid MESH_CONFIG_JSON: {exc}") from exc

        peers: List[dict] = []
        peers_file = os.environ.get("PEERS_FILE", "").strip()
        if peers_file and Path(peers_file).exists():
            try:
                raw_peers = json.loads(Path(peers_file).read_text(encoding="utf-8"))
                peers = raw_peers.get("peers", []) if isinstance(raw_peers, dict) else []
            except ValueError as exc:
                raise ConfigError(f"Invalid PEERS_FILE JSON: {exc}") from exc

        collaborators: Dict[int, str] = {}
        for item in filter(None, os.environ.get("COLLABORATORS", "").split(",")):
            uid, _, role = item.partition(":")
            try:
                collaborators[int(uid.strip())] = (role.strip() or "observer").lower()
            except ValueError as exc:
                raise ConfigError(f"Invalid COLLABORATORS entry {item!r}: {exc}") from exc

        try:
            port_val = int(os.environ.get("PORT") or "8443")
            timeout_val = float(os.environ.get("LLM_TIMEOUT_S") or "120")
            budget_val = int(os.environ.get("TOKEN_BUDGET") or "500000")
        except ValueError as exc:
            raise ConfigError(f"Invalid numeric config in PORT/LLM_TIMEOUT_S/TOKEN_BUDGET: {exc}") from exc

        host_val = (os.environ.get("HOST") or "127.0.0.1").strip()
        dash_token = os.environ.get("DASHBOARD_TOKEN", "").strip()
        if host_val not in ("127.0.0.1", "localhost", "::1") and not dash_token:
            raise ConfigError(
                f"Security Error (C2): DASHBOARD_TOKEN must be set when binding to non-loopback HOST={host_val!r}"
            )
        data_dir_path = Path(os.environ.get("DATA_DIR") or "./data")
        tls_cert = os.environ.get("TLS_CERT_FILE", "").strip()
        tls_key = os.environ.get("TLS_KEY_FILE", "").strip()
        if (host_val not in ("127.0.0.1", "localhost", "::1") or _env_bool("ENABLE_TLS", False)) and not _env_bool("NEXUS_ALLOW_INSECURE_HTTP", False):
            if not tls_cert or not tls_key:
                from .server import ensure_tls_certificates
                tls_cert, tls_key = ensure_tls_certificates(data_dir_path)

        return cls(
            owner_telegram_id=owner_id,
            master_passphrase_hash=pw_hash,
            telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
            webhook_secret=os.environ.get("TELEGRAM_WEBHOOK_SECRET", ""),
            public_webhook_url=os.environ.get("PUBLIC_WEBHOOK_URL", ""),
            dashboard_token=dash_token,
            peer_shared_secret=os.environ.get("PEER_SHARED_SECRET", ""),
            host=host_val,
            port=port_val,
            tls_cert_file=tls_cert,
            tls_key_file=tls_key,
            ollama_url=os.environ.get("OLLAMA_URL") or "http://localhost:11434",
            llm_api_key=(os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
                         or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("GROQ_API_KEY") or "").strip(),
            llm_base_url=(os.environ.get("LLM_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
                          or "https://openrouter.ai/api/v1").strip(),
            llm_timeout_s=timeout_val,
            mesh=mesh,
            data_dir=data_dir_path,
            peers=peers,
            collaborators=collaborators,
            enable_code_execution=_env_bool("ENABLE_CODE_EXECUTION"),
            simulate_offline_consensus=_env_bool("SIMULATE_OFFLINE_CONSENSUS"),
            token_budget=budget_val,
            enable_tunnel=_env_bool("ENABLE_TUNNEL"),
            public_hub_url=(os.environ.get("PUBLIC_HUB_URL") or os.environ.get("CLOUDFLARE_TUNNEL_URL") or "").strip(),
            bootstrap_anchor_url=(os.environ.get("BOOTSTRAP_ANCHOR_URL") or os.environ.get("NEXUS_BOOTSTRAP_URL") or "").strip(),
            github_gist_id=(os.environ.get("GITHUB_GIST_ID") or os.environ.get("NEXUS_GIST_ID") or "").strip(),
            github_gist_token=(os.environ.get("GITHUB_GIST_TOKEN") or os.environ.get("NEXUS_GIST_TOKEN") or "").strip(),
        )
