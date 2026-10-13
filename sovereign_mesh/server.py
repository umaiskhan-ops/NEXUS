"""HTTP server: Web Studio UI, REST API, Telegram webhook, health check, token-protected dashboard, HMAC-authenticated peer endpoint."""
from __future__ import annotations

import hmac
import html
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .telegram_gateway import TelegramClient, handle_update, parse_command
from .web_ui import get_web_ui_html

MAX_BODY = 1_000_000


def make_handler(grid, client):
    cfg = grid.config

    class Handler(BaseHTTPRequestHandler):
        server_version = "SovereignMesh/2026.4"

        def log_message(self, fmt, *args):  # quieter logs, no request bodies
            print(f"[HTTP] {self.address_string()} {fmt % args}")

        def _send(self, code: int, body, ctype: str = "application/json") -> None:
            data = body if isinstance(body, bytes) else (
                body.encode("utf-8") if isinstance(body, str) else json.dumps(body, default=str).encode("utf-8"))
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def _auth_ok(self) -> bool:
            if not cfg.dashboard_token:
                return True
            supplied = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            if not supplied and "?" in self.path:
                qs = parse_qs(urlparse(self.path).query)
                supplied = qs.get("token", [""])[0]
            return bool(supplied and hmac.compare_digest(supplied, cfg.dashboard_token))

        def do_GET(self):  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path in {"/", "/chat"}:
                page = get_web_ui_html(grid.node_id, [n.to_dict() for n in grid.router.nodes], grid.registry.counts())
                return self._send(200, page, "text/html; charset=utf-8")
            if path == "/api/features":
                return self._send(200, [f.to_dict() for f in grid.registry.all()])
            if path == "/healthz":
                return self._send(200, {"ok": True, "node": grid.node_id, "lockdown": grid.system_lockdown})
            if path == "/p2p/head":
                return self._p2p_head()
            if path in {"/dashboard", "/api/status"}:
                if not self._auth_ok():
                    return self._send(401, {"error": "unauthorized"})
                workers_data = [w.to_dict() for w in grid.hub.workers] if getattr(grid, "hub", None) else []
                status = {
                    "node_id": grid.node_id, "uptime_s": int(time.time() - grid.started_at),
                    "lockdown": grid.system_lockdown, "autonomous": grid.autonomous_mode,
                    "nodes": [n.to_dict() for n in grid.router.nodes],
                    "workers": workers_data,
                    "features": grid.registry.counts(),
                    "feature_kinds": grid.registry.kind_counts(), "ledger_blocks": len(grid.ledger),
                    "ledger_intact": grid.ledger.verify()[0], "alerts": grid.check_alerts(),
                    "tasks": [t.to_dict() for t in grid.tasks.list()][-20:], "budget": grid.budget.status(),
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
            fresh = ts.isdigit() and abs(time.time() - int(ts)) < 60
            if not fresh or not hmac.compare_digest(sig, grid.peer_signature(ts)):
                return self._send(401, {"error": "bad peer signature"})
            return self._send(200, {"node_id": grid.node_id, "ledger_len": len(grid.ledger),
                                    "head_hash": grid.ledger.head_hash})

        def do_POST(self):  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path == "/telegram/webhook":
                supplied = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
                if not cfg.webhook_secret or not hmac.compare_digest(supplied, cfg.webhook_secret):
                    return self._send(401, {"error": "unauthorized"})
                length = int(self.headers.get("Content-Length", "0") or 0)
                if length <= 0 or length > MAX_BODY:
                    return self._send(413, {"error": "bad length"})
                try:
                    update = json.loads(self.rfile.read(length))
                except ValueError:
                    return self._send(400, {"error": "bad json"})
                self._send(200, {"ok": True})  # ack fast; Telegram retries slow webhooks
                threading.Thread(target=self._process, args=(update,), daemon=True).start()
                return

            if path in {"/api/chat", "/api/run", "/api/ide/generate", "/api/ide/execute", "/api/ide/test", "/api/ide/review"}:
                if not self._auth_ok():
                    return self._send(401, {"error": "unauthorized"})
                length = int(self.headers.get("Content-Length", "0") or 0)
                if length <= 0 or length > MAX_BODY:
                    return self._send(413, {"error": "bad length"})
                try:
                    body = json.loads(self.rfile.read(length))
                except ValueError:
                    return self._send(400, {"error": "bad json"})

                if path == "/api/ide/execute":
                    code = body.get("code", "").strip()
                    if not code:
                        return self._send(400, {"error": "code is required"})
                    from .sandbox import compile_check, run_python
                    chk = compile_check(code)
                    if not chk["ok"]:
                        return self._send(200, {"ok": False, "compile": chk, "stdout": "", "stderr": chk.get("error", "SyntaxError")})
                    res = run_python(code, enabled=True, timeout=float(body.get("timeout", 10.0)))
                    return self._send(200, {"ok": res["ok"], "compile": chk, "returncode": res.get("returncode"),
                                            "stdout": res.get("stdout", ""), "stderr": res.get("stderr", "")})

                if path == "/api/ide/generate":
                    prompt = body.get("prompt", "").strip()
                    if not prompt:
                        return self._send(400, {"error": "prompt is required"})
                    mode = body.get("mode", "generate")
                    from .features.registry import extract_code
                    if mode == "debug_fix":
                        res = grid.run_feature(grid.owner_tg_id, "code_debug_fix_loop", {
                            "text": prompt,
                            "code": body.get("code") or None,
                            "max_iterations": int(body.get("max_iterations", 3))
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

                    combined = f"{code}\n\n# --- AUTO-GENERATED TEST SUITE ---\n{test_code}"
                    exec_res = run_python(combined, enabled=True, timeout=12.0)
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

                if path == "/api/run":
                    feature_key = body.get("feature", "")
                    payload = body.get("payload", {})
                    if not feature_key:
                        return self._send(400, {"error": "feature is required"})
                    res = grid.run_feature(grid.owner_tg_id, feature_key, payload)
                    return self._send(200, res)

                # /api/chat
                prompt = body.get("prompt", "").strip()
                if not prompt:
                    return self._send(400, {"error": "prompt is required"})
                if prompt.startswith("/"):
                    intent, p_load, passph = parse_command(prompt)
                    res = grid.process_telegram_inbound_signal(grid.owner_tg_id, intent, p_load, passph)
                    return self._send(200, {"ok": True, "reply": res.get("tele_response"), "result": res})

                feature = body.get("feature")
                if feature:
                    res = grid.run_feature(grid.owner_tg_id, feature, body.get("payload") or {"prompt": prompt})
                    return self._send(200, {"ok": True, "feature": feature, "result": res})

                # Try LLM ask, fall back to NLU
                try:
                    ask_res = grid.router.ask(prompt, system="You are the Sovereign Mesh AGI assistant. Answer helpfully, accurately, and concisely.")
                    return self._send(200, {"ok": True, "reply": ask_res.get("text"), "model": ask_res.get("model"),
                                            "latency_s": ask_res.get("latency_s")})
                except Exception as exc:
                    nlu_res = grid.run_feature(grid.owner_tg_id, "natural_language_understanding", {"text": prompt})
                    return self._send(200, {"ok": True, "reply": str(nlu_res.get("output") or nlu_res.get("intent") or nlu_res),
                                            "result": nlu_res, "backend_note": str(exc)[:200]})

            return self._send(404, {"error": "not found"})

        @staticmethod
        def _process(update):
            try:
                handle_update(grid, client, update)
            except Exception as exc:  # noqa: BLE001
                print(f"[HTTP] update handler error: {exc!r}")

    return Handler


def serve(grid) -> None:
    cfg = grid.config
    client = TelegramClient(cfg.telegram_bot_token) if cfg.telegram_bot_token else None
    if client:
        grid.notifier = lambda text: client.send_message(cfg.owner_telegram_id, text)
        if cfg.public_webhook_url and cfg.webhook_secret:
            res = client.set_webhook(cfg.public_webhook_url.rstrip("/") + "/telegram/webhook", cfg.webhook_secret)
            print(f"[TELEGRAM] setWebhook -> {res.get('ok')} {res.get('description', '')}")
    httpd = ThreadingHTTPServer((cfg.host, cfg.port), make_handler(grid, client))
    grid.start()
    threading.Thread(target=lambda: (grid.shutdown_event.wait(), httpd.shutdown()), daemon=True).start()
    print(f"[HTTP] NEXUS Sovereign Mesh listening on http://{cfg.host}:{cfg.port}")
    httpd.serve_forever()

