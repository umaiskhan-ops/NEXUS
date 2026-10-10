"""HTTP server: Telegram webhook, health check, token-protected dashboard/API, HMAC-authenticated peer endpoint."""
from __future__ import annotations

import hmac
import html
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .telegram_gateway import TelegramClient, handle_update

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

        def _bearer_ok(self) -> bool:
            if not cfg.dashboard_token:
                return False
            supplied = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            return hmac.compare_digest(supplied, cfg.dashboard_token)

        def do_GET(self):  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path == "/healthz":
                return self._send(200, {"ok": True, "node": grid.node_id, "lockdown": grid.system_lockdown})
            if path == "/p2p/head":
                return self._p2p_head()
            if path in {"/dashboard", "/api/status"}:
                if not self._bearer_ok():
                    return self._send(401, {"error": "unauthorized"})
                status = {
                    "node_id": grid.node_id, "uptime_s": int(time.time() - grid.started_at),
                    "lockdown": grid.system_lockdown, "autonomous": grid.autonomous_mode,
                    "nodes": [n.to_dict() for n in grid.router.nodes], "features": grid.registry.counts(),
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
            if self.path.split("?", 1)[0] != "/telegram/webhook":
                return self._send(404, {"error": "not found"})
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

        @staticmethod
        def _process(update):
            try:
                handle_update(grid, client, update)
            except Exception as exc:  # noqa: BLE001
                print(f"[HTTP] update handler error: {exc!r}")

    return Handler


def serve(grid) -> None:
    cfg = grid.config
    if not cfg.webhook_secret:
        raise SystemExit("TELEGRAM_WEBHOOK_SECRET is required in webhook mode")
    client = TelegramClient(cfg.telegram_bot_token) if cfg.telegram_bot_token else None
    if client:
        grid.notifier = lambda text: client.send_message(cfg.owner_telegram_id, text)
        if cfg.public_webhook_url:
            res = client.set_webhook(cfg.public_webhook_url.rstrip("/") + "/telegram/webhook", cfg.webhook_secret)
            print(f"[TELEGRAM] setWebhook -> {res.get('ok')} {res.get('description', '')}")
    httpd = ThreadingHTTPServer((cfg.host, cfg.port), make_handler(grid, client))
    grid.start()
    threading.Thread(target=lambda: (grid.shutdown_event.wait(), httpd.shutdown()), daemon=True).start()
    print(f"[HTTP] listening on {cfg.host}:{cfg.port}")
    httpd.serve_forever()
