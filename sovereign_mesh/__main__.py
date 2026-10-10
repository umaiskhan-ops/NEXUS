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


def cmd_serve(_args) -> int:
    from .server import serve
    serve(_grid_from_env())
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


def cmd_selftest(_args) -> int:
    from .config import GridConfig
    from .features import SPEC_COUNTS, Block
    from .grid import UltimateAgiSovereignGrid
    from .security import hash_passphrase

    with tempfile.TemporaryDirectory() as tmp:
        cfg = GridConfig(owner_telegram_id=1, master_passphrase_hash=hash_passphrase(secrets.token_hex(16)),
                         data_dir=Path(tmp), ollama_url="http://127.0.0.1:9")
        grid = UltimateAgiSovereignGrid(cfg)
        counts = grid.registry.counts()
        ok = all(counts[b.value] == SPEC_COUNTS[b] for b in Block)
        print(json.dumps({"feature_counts": counts, "total": len(grid.registry),
                          "kinds": grid.registry.kind_counts(), "matches_spec": ok}, indent=1))
        red = grid.run_feature(1, "red_team_safety_tester", {})
        stress = grid.run_feature(1, "adversarial_stress_test", {})
        deadlock = grid.run_feature(1, "dependency_deadlock_detector", {})
        print(f"red team: {red['status']} {red.get('probes')}\nstress test: {stress['status']} "
              f"({stress.get('caught')}/{stress.get('total')})\nfeature graph deadlocks: {deadlock['status']}")
        return 0 if ok and red["status"] == "PASS" and deadlock["status"] == "CLEAR" else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="sovereign_mesh")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name, fn, help_ in (("serve", cmd_serve, "webhook HTTP server (production)"),
                            ("poll", cmd_poll, "Telegram long-polling (no public URL needed)"),
                            ("repl", cmd_repl, "local owner console"),
                            ("hash-passphrase", cmd_hash, "generate MASTER_PASSPHRASE_HASH"),
                            ("selftest", cmd_selftest, "offline registry + safety self-test")):
        sub.add_parser(name, help=help_).set_defaults(fn=fn)
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
