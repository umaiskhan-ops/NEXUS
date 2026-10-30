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
    def __init__(self, token: str, timeout: float = 40.0, base_url: str = ""):
        import os
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        root = (base_url or os.environ.get("TELEGRAM_API_BASE", "https://api.telegram.org")).rstrip("/")
        self._base = f"{root}/bot{token}"
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
    if intent == "/add_model":
        parts = rest.split()
        if len(parts) >= 3:
            return intent, {"name": parts[0], "role": parts[1], "model": parts[2]}, None
        elif len(parts) == 2:
            return intent, {"name": parts[0], "role": "Validator", "model": parts[1]}, None
        return intent, {"text": rest}, None
    if intent in {"/add_models_bulk", "/add_300_models"}:
        cnt = 300
        if rest.strip().isdigit():
            cnt = int(rest.strip())
        return "/add_models_bulk", {"count": cnt}, None
    if intent == "/remove_model":
        return intent, {"name": rest.strip()}, None
    if intent == "/register_worker":
        parts = rest.split()
        wid = parts[0] if len(parts) >= 1 else ""
        url = parts[1] if len(parts) >= 2 else "local"
        ref = parts[2] if len(parts) >= 3 else ""
        return intent, {"worker_id": wid, "url": url, "referred_by": ref}, None
    if intent == "/dispatch_worker":
        wid, _, rem = rest.partition(" ")
        fkey, _, body = rem.strip().partition(" ")
        return intent, {"worker_id": wid.strip(), "feature": fkey.strip(), "task_payload": _parse_json_or_text(body)}, None
    if intent in {"/balance", "/my_tier", "/referral", "/referrals"}:
        return intent, {"worker_id": rest.strip()} if rest else {}, None
    if intent in {"/add_credits", "/grant_credits"}:
        parts = rest.split(None, 2)
        if len(parts) >= 2:
            try:
                return "/add_credits", {"worker_id": parts[0], "amount": int(parts[1]), "reason": parts[2] if len(parts) > 2 else "owner_grant"}, None
            except ValueError:
                pass
        return "/add_credits", _parse_json_or_text(rest), None
    if intent == "/spend_credits":
        parts = rest.split(None, 2)
        if len(parts) >= 2:
            try:
                return intent, {"worker_id": parts[0], "amount": int(parts[1]), "reason": parts[2] if len(parts) > 2 else "manual_spend"}, None
            except ValueError:
                pass
        return intent, {"text": rest}, None
    if intent == "/transfer_credits":
        parts = rest.split()
        if len(parts) >= 3:
            try:
                return intent, {"from_worker": parts[0], "to_worker": parts[1], "amount": int(parts[2])}, None
            except ValueError:
                pass
        return intent, {"text": rest}, None
    if intent == "/barter_task":
        wid, _, rem = rest.partition(" ")
        fkey, _, body = rem.strip().partition(" ")
        return intent, {"worker_id": wid.strip(), "feature": fkey.strip(), "task_payload": _parse_json_or_text(body)}, None
    if intent == "/set_payout":
        wid, _, addr = rest.partition(" ")
        return intent, {"worker_id": wid.strip(), "address": addr.strip()}, None
    if intent == "/deposit_revenue":
        parts = rest.split()
        if len(parts) >= 2:
            try:
                return intent, {"client": parts[0], "amount": float(parts[1]), "job_id": parts[2] if len(parts) > 2 else ""}, None
            except ValueError:
                pass
        return intent, {"text": rest}, None
    if intent == "/settle_revenue":
        try:
            ratio = float(rest.strip()) if rest.strip() else 0.70
        except ValueError:
            ratio = 0.70
        return intent, {"split_ratio": ratio}, None
    if intent in {"/top_miners", "/leaderboard"}:
        limit = int(rest.strip()) if rest.strip().isdigit() else 10
        return "/top_miners", {"limit": limit}, None
    if intent in {"/reward_top_miners", "/buyback_top3"}:
        parts = rest.split()
        pkr = float(parts[0]) if len(parts) >= 1 and parts[0].replace(".", "", 1).isdigit() else 500.0
        cr = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 100
        return "/reward_top_miners", {"reward_pkr_each": pkr, "credits_bought_each": cr}, None
    if intent == "/p2p_sell":
        parts = rest.split(None, 3)
        if len(parts) >= 3:
            try:
                return intent, {
                    "worker_id": parts[0],
                    "amount": int(parts[1]),
                    "price": float(parts[2]),
                    "payment_method": parts[3] if len(parts) > 3 else "EasyPaisa / JazzCash",
                }, None
            except ValueError:
                pass
        return intent, {"text": rest}, None
    if intent == "/p2p_buy_order":
        parts = rest.split(None, 3)
        if len(parts) >= 3:
            try:
                return intent, {
                    "buyer_id": parts[0],
                    "amount": int(parts[1]),
                    "price": float(parts[2]),
                    "payment_method": parts[3] if len(parts) > 3 else "EasyPaisa / JazzCash",
                }, None
            except ValueError:
                pass
        return intent, {"text": rest}, None
    if intent == "/p2p_sell_to_buyer":
        parts = rest.split(None, 2)
        if len(parts) >= 2:
            return intent, {
                "order_id": parts[0],
                "seller_id": parts[1],
                "payment_method": parts[2] if len(parts) > 2 else "",
            }, None
        return intent, {"text": rest}, None
    if intent == "/p2p_buy":
        parts = rest.split()
        if len(parts) >= 2:
            return intent, {"order_id": parts[0], "buyer_id": parts[1]}, None
        return intent, {"text": rest}, None
    if intent == "/p2p_pay":
        parts = rest.split(None, 2)
        if len(parts) >= 3:
            return intent, {"order_id": parts[0], "buyer_id": parts[1], "ref": parts[2]}, None
        return intent, {"text": rest}, None
    if intent in {"/dispute", "/p2p_dispute"}:
        parts = rest.split(None, 2)
        if len(parts) >= 2:
            return "/dispute", {"order_id": parts[0], "caller_id": parts[1], "reason": parts[2] if len(parts) > 2 else "Payment / Screenshot Dispute"}, None
        elif len(parts) == 1:
            return "/dispute", {"order_id": parts[0], "reason": "Payment / Screenshot Dispute"}, None
        return "/dispute", {"text": rest}, None
    if intent in {"/p2p_release", "/p2p_cancel"}:
        parts = rest.split()
        if len(parts) >= 1:
            return intent, {"order_id": parts[0], "seller_id": parts[1] if len(parts) > 1 else ""}, None
        return intent, {"text": rest}, None
    if intent in {"/brain_matrix", "/brain"}:
        return "/brain_matrix", {}, None
    if intent == "/self_play":
        return "/self_play", {"topic": rest.strip() or "Distributed Consensus & Sovereign Mesh Autonomy"}, None
    if intent in {"/brain_sync"}:
        parts = rest.split()
        shard = parts[0] if len(parts) >= 1 else "CODE_DEBUG_EXEC"
        return "/brain_sync", {"domain_shard": shard}, None
    if intent in {"/debate", "/roundtable"}:
        return "/debate", {"question": rest.strip()}, None
    if intent in {"/vote", "/consensus", "/verify_task"}:
        return "/vote", {"proposal": rest.strip()}, None
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
        raw_nlu = result.get("result") if payload.get("feature") == "natural_language_understanding" else None
        nlu = raw_nlu if isinstance(raw_nlu, dict) else {}
        if nlu.get("intent") in NLU_SAFE_INTENTS:
            result = grid.process_telegram_inbound_signal(sender, nlu["intent"], {}, None)

    chat_id = chat.get("id")
    if client and secret_bearing and msg.get("message_id") and chat_id is not None:
        client.delete_message(chat_id, msg["message_id"])  # scrub the passphrase from chat history

    reply_text = result.get("tele_response")
    if result.get("drop") or not reply_text or grid.silent_observer:
        return None
    if client and chat_id is not None:
        client.send_message(chat_id, reply_text)
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
