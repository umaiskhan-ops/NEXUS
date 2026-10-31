"""Code execution helpers with Security Sandbox & Anti-Malware Safeguards.
Execution is OFF by default (ENABLE_CODE_EXECUTION=false).

WARNING: a subprocess with a timeout is NOT a security boundary. Only enable execution
when the node itself runs inside a disposable container (see Dockerfile).
"""
from __future__ import annotations

import ast
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
    # Dunder sandbox escape & reflection vectors
    r"(?i)(?:__subclasses__|__globals__|__builtins__|__mro__|__code__)",
]

_BLOCKED_IMPORTS = {
    "subprocess", "socket", "pty", "ctypes", "shutil", "urllib", "http",
    "ftplib", "telnetlib", "smtplib", "smtpd", "xmlrpc", "winreg",
    "webbrowser", "importlib", "builtins", "multiprocessing", "signal",
}

_BLOCKED_OS_ATTRS = {
    "system", "popen", "fork", "forkpty", "kill", "killpg",
    "remove", "unlink", "rmdir", "removedirs", "rename", "replace",
    "chmod", "chown", "chroot", "listdir", "scandir", "walk", "environ",
    "execl", "execle", "execlp", "execlpe", "execv", "execve", "execvp", "execvpe",
    "spawnl", "spawnle", "spawnlp", "spawnlpe", "spawnv", "spawnve", "spawnvp", "spawnvpe",
    "startfile",
}

_BLOCKED_CALLS = {
    "__import__", "eval", "exec", "breakpoint", "input",
}

_BLOCKED_DUNDERS = {
    "__subclasses__", "__globals__", "__builtins__", "__mro__", "__bases__", "__code__", "__closure__",
}


def _ast_security_scan(source: str) -> dict:
    """AST-based static inspection to prevent regex bypasses via aliasing or string concatenation (C6 Fix)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Let compile_check or interpreter report syntax errors normally
        return {"safe": True}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_mod = (alias.name or "").split(".")[0]
                if top_mod in _BLOCKED_IMPORTS:
                    return {
                        "safe": False,
                        "violation": f"import {alias.name}",
                        "reason": f"Host security violation: Restricted module '{top_mod}' is prohibited in sandbox",
                    }
        elif isinstance(node, ast.ImportFrom):
            top_mod = (node.module or "").split(".")[0]
            if top_mod in _BLOCKED_IMPORTS:
                return {
                    "safe": False,
                    "violation": f"from {node.module} import ...",
                    "reason": f"Host security violation: Restricted module '{top_mod}' is prohibited in sandbox",
                }
            if top_mod == "os":
                for alias in node.names:
                    if alias.name in _BLOCKED_OS_ATTRS or alias.name == "*":
                        return {
                            "safe": False,
                            "violation": f"from os import {alias.name}",
                            "reason": f"Host security violation: Restricted os function '{alias.name}' is prohibited",
                        }
        elif isinstance(node, ast.Attribute):
            if node.attr in _BLOCKED_DUNDERS:
                return {
                    "safe": False,
                    "violation": node.attr,
                    "reason": f"Host security violation: Dunder introspection '{node.attr}' is prohibited in sandbox",
                }
            if isinstance(node.value, ast.Name) and node.value.id == "os" and node.attr in _BLOCKED_OS_ATTRS:
                return {
                    "safe": False,
                    "violation": f"os.{node.attr}",
                    "reason": f"Host security violation: OS operation 'os.{node.attr}' is prohibited in sandbox",
                }
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                fname = node.func.id
                if fname in _BLOCKED_CALLS:
                    return {
                        "safe": False,
                        "violation": f"{fname}()",
                        "reason": f"Host security violation: Dynamic execution '{fname}()' is prohibited in sandbox",
                    }
                if fname == "open" and node.args:
                    first_arg = node.args[0]
                    if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                        p_str = first_arg.value
                        if ".." in p_str or p_str.startswith("/") or re.match(r"^[a-zA-Z]:[\\/]", p_str) or "~" in p_str:
                            return {
                                "safe": False,
                                "violation": f"open({p_str!r})",
                                "reason": "Host security violation: Unauthorized host filesystem access outside sandbox",
                            }
                    else:
                        # Block open(os.path.expanduser(...)) or non-literal path expressions targeting host
                        return {
                            "safe": False,
                            "violation": "open(<dynamic_path>)",
                            "reason": "Host security violation: Dynamic host file open is prohibited in sandbox",
                        }
    return {"safe": True}


def security_scan(source: str) -> dict:
    """Scans code for destructive malware, reverse shells, and host escape vectors (Regex + AST)."""
    for pat in DANGEROUS_PATTERNS:
        if re.search(pat, source):
            return {
                "safe": False,
                "violation": pat,
                "reason": "Host security violation: Unauthorized system access or destructive payload detected",
            }
    return _ast_security_scan(source)


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
                cmd = [sys.executable, "-B", str(script)]
            else:
                # -I flag isolates Python from host user site-packages & current directory injection
                cmd = [sys.executable, "-I", "-B", str(script)]

            run_kwargs: dict = {}
            if os.name == "nt":
                # BELOW_NORMAL_PRIORITY_CLASS (0x00004000) | CREATE_NO_WINDOW (0x08000000)
                run_kwargs["creationflags"] = 0x00004000 | 0x08000000
            else:
                def _apply_posix_rlimits():
                    try:
                        import resource
                        cpu_lim = max(1, int(timeout) + 1)
                        resource.setrlimit(resource.RLIMIT_CPU, (cpu_lim, cpu_lim + 1))
                        mem_bytes = 512 * 1024 * 1024  # 512 MB address space cap
                        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
                        fsize_bytes = 10 * 1024 * 1024  # 10 MB file write cap
                        resource.setrlimit(resource.RLIMIT_FSIZE, (fsize_bytes, fsize_bytes))
                    except Exception:
                        pass
                run_kwargs["preexec_fn"] = _apply_posix_rlimits

            proc = subprocess.run(
                cmd, cwd=exec_cwd, env=env,
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                **run_kwargs,
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
