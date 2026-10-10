"""Code execution helpers. Execution is OFF by default (ENABLE_CODE_EXECUTION=false).

WARNING: a subprocess with a timeout is NOT a security boundary. Only enable execution
when the node itself runs inside a disposable container (see Dockerfile)."""
from __future__ import annotations

import dis
import io
import os
import subprocess
import sys
import tempfile
from pathlib import Path

MAX_OUTPUT = 8_000


def compile_check(source: str, filename: str = "<grid>") -> dict:
    try:
        code = compile(source, filename, "exec")
    except SyntaxError as exc:
        return {"ok": False, "error": f"SyntaxError: {exc.msg}", "line": exc.lineno, "offset": exc.offset}
    buf = io.StringIO()
    dis.dis(code, file=buf)
    listing = buf.getvalue()
    return {"ok": True, "bytecode_instructions": listing.count("\n"), "disassembly_preview": listing[:1500]}


def run_python(source: str, enabled: bool, timeout: float = 10.0) -> dict:
    if not enabled:
        return {"ok": False, "disabled": True, "error": "code execution disabled (set ENABLE_CODE_EXECUTION=true)"}
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8"}
    if os.name == "nt":
        env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", r"C:\Windows")
    with tempfile.TemporaryDirectory(prefix="grid_sbx_") as tmp:
        script = Path(tmp) / "main.py"
        script.write_text(source, encoding="utf-8")
        try:
            proc = subprocess.run([sys.executable, "-I", str(script)], cwd=tmp, env=env,
                                  capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"timeout after {timeout}s"}
    return {"ok": proc.returncode == 0, "returncode": proc.returncode,
            "stdout": proc.stdout[-MAX_OUTPUT:], "stderr": proc.stderr[-MAX_OUTPUT:]}
