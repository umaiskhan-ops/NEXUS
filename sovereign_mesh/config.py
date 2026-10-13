"""Runtime configuration, loaded from environment variables."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

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
    host: str = "0.0.0.0"
    port: int = 8443
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

        owner = os.environ.get("OWNER_TELEGRAM_ID", "").strip()
        if not owner.lstrip("-").isdigit():
            raise ConfigError("OWNER_TELEGRAM_ID must be your numeric Telegram user id")

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
            mesh = json.loads(os.environ["MESH_CONFIG_JSON"])

        peers: List[dict] = []
        peers_file = os.environ.get("PEERS_FILE", "").strip()
        if peers_file and Path(peers_file).exists():
            peers = json.loads(Path(peers_file).read_text(encoding="utf-8")).get("peers", [])

        collaborators: Dict[int, str] = {}
        for item in filter(None, os.environ.get("COLLABORATORS", "").split(",")):
            uid, _, role = item.partition(":")
            collaborators[int(uid.strip())] = (role.strip() or "observer").lower()

        return cls(
            owner_telegram_id=int(owner),
            master_passphrase_hash=pw_hash,
            telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
            webhook_secret=os.environ.get("TELEGRAM_WEBHOOK_SECRET", ""),
            public_webhook_url=os.environ.get("PUBLIC_WEBHOOK_URL", ""),
            dashboard_token=os.environ.get("DASHBOARD_TOKEN", ""),
            peer_shared_secret=os.environ.get("PEER_SHARED_SECRET", ""),
            host=os.environ.get("HOST", "0.0.0.0"),
            port=int(os.environ.get("PORT", "8443")),
            ollama_url=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
            llm_api_key=(os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
                         or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("GROQ_API_KEY") or "").strip(),
            llm_base_url=(os.environ.get("LLM_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
                          or "https://openrouter.ai/api/v1").strip(),
            llm_timeout_s=float(os.environ.get("LLM_TIMEOUT_S", "120")),
            mesh=mesh,
            data_dir=Path(os.environ.get("DATA_DIR", "./data")),
            peers=peers,
            collaborators=collaborators,
            enable_code_execution=_env_bool("ENABLE_CODE_EXECUTION"),
            simulate_offline_consensus=_env_bool("SIMULATE_OFFLINE_CONSENSUS"),
            token_budget=int(os.environ.get("TOKEN_BUDGET", "500000")),
        )
