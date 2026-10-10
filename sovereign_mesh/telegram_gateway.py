"""Telegram Bot API gateway (stdlib only): command parsing, webhook/long-poll handling, replies."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Optional, Tuple

PASSPHRASE_COMMANDS = {"/federal_veto", "/emergency_override"}
NLU_SAFE_INTENTS = {"/status_grid", "/tasks", "/features", "/audit"}


class TelegramClient:
    def __init__(self, token: str, timeout: float = 40.0):
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        self._base = f"https://api.telegram.org/bot{token}"
        self._timeout = timeout

    def call(self, method: str, **params) -> dict:
        req = urllib.request.Request(f"{self._base}/{method}", data=json.dumps(params).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            return {"ok": False, "error": exc.code, "description": exc.read().decode("utf-8", "replace")[:300]}
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return {"ok": False, "description": str(exc)}

    def send_message(self, chat_id: int, text: str) -> None:
        for i in range(0, max(1, len(text)), 4000):  # Telegram limit is 4096 chars
            self.call("sendMessage", chat_id=chat_id, text=text[i:i + 4000], disable_web_page_preview=True)

    def delete_message(self, chat_id: int, message_id: int) -> None:
        self.call("deleteMessage", chat_id=chat_id, message_id=message_id)

    def set_webhook(self, url: str, secret: str) -> dict:
        return self.call("setWebhook", url=url, secret_token=secret, allowed_updates=["message"],
                         drop_pending_updates=True)

    def delete_webhook(self) -> dict:
        return self.call("deleteWebhook")

    def get_updates(self, offset: int, timeout: int = 30) -> list:
        res = self.call("getUpdates", offset=offset, timeout=timeout, allowed_updates=["message"])
        return res.get("result", []) if res.get("ok") else []


def _parse_json_or_text(rest: str) -> dict:
    rest = rest.strip()
    if rest.startswith("{"):
        try:
            obj = json.loads(rest)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    return {"text": rest} if rest else {}


def parse_command(text: str) -> Tuple[str, dict, Optional[str]]:
    """Returns (intent, payload, passphrase)."""
    head, _, rest = text.strip().partition(" ")
    intent = head.split("@", 1)[0].lower()
    rest = rest.strip()
    if intent == "/run":
        key, _, body = rest.partition(" ")
        payload = _parse_json_or_text(body)
        passphrase = payload.pop("passphrase", None)
        payload["feature"] = key
        return intent, payload, passphrase
    if intent == "/execute_autonomous_task":
        name, _, js = rest.partition("|")
        payload = _parse_json_or_text(js) if js.strip().startswith("{") else {}
        payload["task_name"] = name.strip() or payload.get("task_name", "Generic Task")
        return intent, payload, None
    if intent == "/federal_veto":
        target, _, phrase = rest.partition(" ")
        return intent, {"target_process_id": target or "ALL"}, phrase or None
    if intent == "/emergency_override":
        return intent, {}, rest or None
    if intent in {"/approve", "/reject"}:
        return intent, {"id": rest}, None
    if intent == "/features":
        return intent, {"block": rest} if rest else {}, None
    return intent, {"text": rest} if rest else {}, None


def handle_update(grid, client: Optional[TelegramClient], update: dict) -> Optional[str]:
    msg = update.get("message") or {}
    text = msg.get("text")
    sender = (msg.get("from") or {}).get("id")
    chat = msg.get("chat") or {}
    if not text or sender is None:
        return None

    if text.startswith("/"):
        intent, payload, passphrase = parse_command(text)
    else:
        intent, payload, passphrase = "/run", {"feature": "natural_language_understanding", "text": text}, None

    secret_bearing = intent in PASSPHRASE_COMMANDS or passphrase is not None
    if secret_bearing and chat.get("type") != "private":
        reply = "❌ Passphrase commands are only accepted in a private chat with the bot."
        passphrase = None
        intent = "/noop"
    if intent == "/noop":
        result = {"tele_response": reply}
    else:
        result = grid.process_telegram_inbound_signal(sender, intent, payload, passphrase)
        # Free-text NLU: follow through for read-only intents only.
        nlu = result.get("result", {}) if payload.get("feature") == "natural_language_understanding" else {}
        if nlu.get("intent") in NLU_SAFE_INTENTS:
            result = grid.process_telegram_inbound_signal(sender, nlu["intent"], {}, None)

    if client and secret_bearing and msg.get("message_id"):
        client.delete_message(chat["id"], msg["message_id"])  # scrub the passphrase from chat history

    reply_text = result.get("tele_response")
    if result.get("drop") or not reply_text or grid.silent_observer:
        return None
    if client:
        client.send_message(chat["id"], reply_text)
    return reply_text


def run_long_polling(grid, client: TelegramClient) -> None:
    client.delete_webhook()
    offset = 0
    print("[TELEGRAM] long-polling started")
    while not grid.shutdown_event.is_set():
        for upd in client.get_updates(offset):
            offset = max(offset, upd["update_id"] + 1)
            try:
                handle_update(grid, client, upd)
            except Exception as exc:  # noqa: BLE001 - keep polling on handler failures
                print(f"[TELEGRAM] handler error: {exc!r}")
        time.sleep(0.2)
