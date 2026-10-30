"""CLI: serve | poll | repl | hash-passphrase | selftest"""
from __future__ import annotations

import argparse
import getpass
import json
import secrets
import sys
import tempfile
from pathlib import Path


def _grid_from_env():
    from .config import GridConfig
    from .grid import UltimateAgiSovereignGrid
    return UltimateAgiSovereignGrid(GridConfig.from_env())


def cmd_hash(_args) -> int:
    from .security import hash_passphrase
    p1 = getpass.getpass("Master passphrase (>= 12 chars): ")
    if len(p1) < 12 or p1 != getpass.getpass("Repeat: "):
        print("Passphrases empty/short or do not match.", file=sys.stderr)
        return 1
    print(f"MASTER_PASSPHRASE_HASH={hash_passphrase(p1)}")
    return 0


def cmd_serve(args) -> int:
    from .server import serve
    grid = _grid_from_env()
    if getattr(args, "tunnel", False):
        grid.config.enable_tunnel = True
    open_b = getattr(args, "open_browser", False)
    serve(grid, open_browser=open_b)
    return 0


def cmd_start(args) -> int:
    from .server import serve
    grid = _grid_from_env()
    if getattr(args, "tunnel", False):
        grid.config.enable_tunnel = True
    serve(grid, open_browser=not getattr(args, "no_browser", False))
    return 0


def cmd_poll(_args) -> int:
    from .telegram_gateway import TelegramClient, run_long_polling
    grid = _grid_from_env()
    client = TelegramClient(grid.config.telegram_bot_token)
    grid.notifier = lambda text: client.send_message(grid.config.owner_telegram_id, text)
    grid.start()
    try:
        run_long_polling(grid, client)
    except KeyboardInterrupt:
        grid.stop()
    return 0


def cmd_repl(_args) -> int:
    """Bare-metal owner console: same command grammar as Telegram, no network required."""
    from .telegram_gateway import parse_command
    grid = _grid_from_env()
    grid.start()
    print(grid.HELP + "\n(type 'exit' to quit)")
    while True:
        try:
            line = input("grid> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if line in {"exit", "quit"}:
            break
        if not line:
            continue
        if not line.startswith("/"):
            line = "/run natural_language_understanding " + line
        intent, payload, phrase = parse_command(line)
        if intent in {"/federal_veto", "/emergency_override"} and not phrase:
            phrase = getpass.getpass("passphrase: ")
        print(grid.process_telegram_inbound_signal(grid.owner_tg_id, intent, payload, phrase).get("tele_response"))
    grid.stop()
    return 0


def cmd_worker(_args) -> int:
    """Lightweight stateless Spoke Worker Node HTTP server."""
    import hashlib
    import os
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from .hub_spoke import LightweightWorkerNode

    worker_id = os.environ.get("WORKER_ID", f"spoke-{secrets.token_hex(3)}")
    raw_key = os.environ.get("WORKER_KEY") or os.environ.get("PEER_SHARED_SECRET", "sovereign-hub-default-secret")
    worker_key = raw_key if len(raw_key) >= 32 else hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    port = int(os.environ.get("WORKER_PORT", "8444"))
    grid = _grid_from_env()
    worker = LightweightWorkerNode(worker_id, worker_key, grid)

    class WorkerHandler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            if self.path != "/worker/execute":
                self.send_response(404)
                self.end_headers()
                return
            length = int(self.headers.get("Content-Length", "0") or 0)
            packet = json.loads(self.rfile.read(length))
            out = json.dumps(worker.execute_signed_task(packet), default=str).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

    print(f"[WORKER] Spoke Node '{worker_id}' listening on 0.0.0.0:{port} "
          f"({len(worker.allowed_features())} execution features enabled, Federal Powers stripped)")
    ThreadingHTTPServer(("0.0.0.0", port), WorkerHandler).serve_forever()
    return 0


def cmd_selftest(_args) -> int:
    from .config import GridConfig
    from .features import SPEC_COUNTS, Block
    from .grid import UltimateAgiSovereignGrid
    from .hub_spoke import LightweightWorkerNode, compute_hmac
    from .security import hash_passphrase

    with tempfile.TemporaryDirectory() as tmp:
        cfg = GridConfig(owner_telegram_id=1, master_passphrase_hash=hash_passphrase(secrets.token_hex(16)),
                         data_dir=Path(tmp), ollama_url="http://127.0.0.1:9", peer_shared_secret="test-hub-secret")
        grid = UltimateAgiSovereignGrid(cfg)
        counts = grid.registry.counts()
        ok = all(counts[b.value] == SPEC_COUNTS[b] for b in Block)
        print(json.dumps({"feature_counts": counts, "total": len(grid.registry),
                          "kinds": grid.registry.kind_counts(), "matches_spec": ok}, indent=1))
        red = grid.run_feature(1, "red_team_safety_tester", {})
        stress = grid.run_feature(1, "adversarial_stress_test", {})
        deadlock = grid.run_feature(1, "dependency_deadlock_detector", {})

        # Verify Hub-and-Spoke Signing & Slashing
        rec_honest = grid.hub.register_worker("worker-honest", initial_credits=100)
        rec_rogue = grid.hub.register_worker("worker-rogue", initial_credits=100)
        w_honest = LightweightWorkerNode("worker-honest", rec_honest.key, grid)
        t1 = grid.hub.create_signed_task("worker-honest", "data_analysis", {"numbers": [10, 20, 30]})
        s1 = grid.hub.verify_and_settle(w_honest.execute_signed_task(t1))

        t2 = grid.hub.create_signed_task("worker-rogue", "data_analysis", {"numbers": [1, 2, 3]})
        forged_result = {"status": "OK", "mean": 999999}
        tampered_resp = {
            "task_id": t2["task_id"],
            "worker_id": "worker-rogue",
            "result": forged_result,
            "worker_proof": compute_hmac(rec_rogue.key, {
                "task_id": t2["task_id"], "worker_id": "worker-rogue",
                "feature": t2["feature"], "nonce": t2["nonce"], "result": forged_result,
            }),
        }
        s2 = grid.hub.verify_and_settle(tampered_resp)
        hub_ok = (s1["status"] == "SETTLED" and s1["total_credits"] == 125 and
                  s2["status"] == "SLASHED" and s2["remaining_credits"] == 0)

        print(f"red team: {red['status']} {red.get('probes')}\nstress test: {stress['status']} "
              f"({stress.get('caught')}/{stress.get('total')})\nfeature graph deadlocks: {deadlock['status']}\n"
              f"hub-and-spoke + slashing: {'PASS' if hub_ok else 'FAIL'} "
              f"(honest={s1['total_credits']} credits, rogue={s2['status']}/burned={s2.get('burned_credits')})")
        return 0 if ok and red["status"] == "PASS" and deadlock["status"] == "CLEAR" and hub_ok else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="sovereign_mesh",
        description="SUP Agentic Mesh (Powered by NEXUS) — Unified 1-Command Launcher"
    )
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open browser on startup")
    parser.add_argument("--tunnel", action="store_true", help="Launch free Cloudflare HTTPS tunnel for worldwide remote worker access")
    sub = parser.add_subparsers(dest="cmd", required=False)
    for name, fn, help_ in (("start", cmd_start, "Start ALL systems (Web Studio + Owner Telegram + Local Worker + Browser)"),
                            ("serve", cmd_serve, "Start ALL systems (Web Studio + Owner Telegram + Local Worker)"),
                            ("poll", cmd_poll, "Master Hub Telegram long-polling only"),
                            ("repl", cmd_repl, "Master Hub local owner console"),
                            ("worker", cmd_worker, "Lightweight Edge Worker Node (Spoke)"),
                            ("hash-passphrase", cmd_hash, "generate MASTER_PASSPHRASE_HASH"),
                            ("selftest", cmd_selftest, "offline registry + hub-spoke + safety self-test")):
        p = sub.add_parser(name, help=help_)
        if name in {"start", "serve"}:
            p.add_argument("--no-browser", action="store_true", help="Do not auto-open browser")
            p.add_argument("--open-browser", action="store_true", help="Auto-open Web Studio in browser")
            p.add_argument("--tunnel", action="store_true", help="Launch Cloudflare HTTPS tunnel")
        p.set_defaults(fn=fn)
    args = parser.parse_args(argv)
    if not getattr(args, "fn", None):
        return cmd_start(args)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())


