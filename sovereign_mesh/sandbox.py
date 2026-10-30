"""Code execution helpers with Security Sandbox & Anti-Malware Safeguards.
Execution is OFF by default (ENABLE_CODE_EXECUTION=false).

WARNING: a subprocess with a timeout is NOT a security boundary. Only enable execution
when the node itself runs inside a disposable container (see Dockerfile).
"""
from __future__ import annotations

import dis
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MAX_OUTPUT = 8_000

DANGEROUS_PATTERNS = [
    # SSH keys & credentials exfiltration
    r"(?i)(?:id_rsa|id_ed25519|\.ssh[/\\]|authorized_keys)",
    # OS account hashes & SAM registry
    r"(?i)(?:/etc/shadow|/etc/passwd|System32[/\\]config[/\\]SAM)",
    # Interactive / reverse shell spawning
    r"(?i)(?:pty\.spawn|socket\.socket.*connect.*(?:sh|cmd|bash)|nc\s+-[e|c])",
    # Fork bomb attempts
    r"(?i)(?::\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:|os\.fork\(\)\s*while)",
    # Raw filesystem wipe / ransomware payloads
    r"(?i)(?:format\s+[c-z]:|rm\s+-rf\s+/[^\s]*|del\s+/f\s+/s\s+/q\s+c:\\)",
]


def security_scan(source: str) -> dict:
    """Scans code for destructive malware, reverse shells, and host escape vectors."""
    for pat in DANGEROUS_PATTERNS:
        if re.search(pat, source):
            return {
                "safe": False,
                "violation": pat,
                "reason": "Host security violation: Unauthorized system access or destructive payload detected",
            }
    return {"safe": True}


def compile_check(source: str, filename: str = "<grid>") -> dict:
    try:
        code = compile(source, filename, "exec")
    except SyntaxError as exc:
        return {"ok": False, "error": f"SyntaxError: {exc.msg}", "line": exc.lineno, "offset": exc.offset}
    except (ValueError, TypeError, RecursionError, MemoryError) as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "line": None, "offset": None}
    buf = io.StringIO()
    dis.dis(code, file=buf)
    listing = buf.getvalue()
    return {"ok": True, "bytecode_instructions": listing.count("\n"), "disassembly_preview": listing[:1500]}


def run_python(source: str, enabled: bool, timeout: float = 10.0, cwd: str | None = None) -> dict:
    if not enabled:
        return {"ok": False, "disabled": True, "error": "code execution disabled (set ENABLE_CODE_EXECUTION=true)"}

    # Pre-execution security heuristic check
    scan = security_scan(source)
    if not scan["safe"]:
        return {
            "ok": False,
            "security_blocked": True,
            "error": f"Security Sandbox Exception: {scan['reason']} (pattern: {scan['violation']})",
            "host_protected": True,
        }

    env = {"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8"}
    if os.name == "nt":
        env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", r"C:\Windows")

    sbx_base = Path(__file__).resolve().parent.parent / "data" / ".tmp"
    try:
        sbx_base.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.mkdtemp(prefix="grid_sbx_", dir=str(sbx_base))
    except OSError:
        tmp = tempfile.mkdtemp(prefix="grid_sbx_")

    try:
        script = Path(tmp) / "main.py"
        script.write_text(source, encoding="utf-8")
        try:
            has_custom_cwd = bool(cwd and Path(cwd).is_dir())
            exec_cwd = str(Path(cwd).resolve()) if has_custom_cwd else tmp
            if has_custom_cwd:
                env["PYTHONPATH"] = exec_cwd
                cmd = [sys.executable, str(script)]
            else:
                # -I flag isolates Python from host user site-packages & current directory injection
                cmd = [sys.executable, "-I", str(script)]
            proc = subprocess.run(
                cmd, cwd=exec_cwd, env=env,
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "timeout": True,
                "infinite_loop_caught": True,
                "error": f"timeout after {timeout}s: infinite loop or execution deadline exceeded",
            }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    return {"ok": proc.returncode == 0, "returncode": proc.returncode,
            "stdout": (proc.stdout or "")[-MAX_OUTPUT:], "stderr": (proc.stderr or "")[-MAX_OUTPUT:]}
