"""Peer-to-Peer (P2P) Credits Marketplace & Escrow Engine.

Allows users needing compute credits to buy from miners/contributors selling credits
in exchange for local fiat (EasyPaisa, JazzCash, Raast, Bank Transfer, USDT).
Features ledger-audited programmatic credit escrow with anti-replay TID validation
and anti-griefing dispute arbitration.
"""
from __future__ import annotations

import dataclasses
import json
import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .ledger import HashChainLedger, interprocess_file_lock


@dataclass
class P2POffer:
    order_id: str
    seller_id: str
    amount_credits: int
    price_fiat: float
    currency: str = "PKR"  # PKR, USD, USDT
    payment_method: str = "EasyPaisa"  # e.g. "EasyPaisa: 0300-1234567 (Ali)"
    status: str = "OPEN"  # OPEN | IN_ESCROW | PAYMENT_SUBMITTED | COMPLETED | CANCELLED | DISPUTED
    buyer_id: str = ""
    payment_reference: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    escrow_locked: bool = True
    order_type: str = "SELL"  # SELL (Seller offers credits) | BUY (Buyer requests credits)
    dispute_reason: str = ""
    disputed_by: str = ""
    payment_receipt_hmac: str = ""
    receipt_recorded: bool = False
    payment_verified: bool = False
    verification_method: str = "UNVERIFIED"

    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d["created_at_str"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.created_at))
        d["price_per_credit"] = round(self.price_fiat / max(1, self.amount_credits), 2)
        return d


MIN_CREDITS_TO_SELL = 150
MAX_DAILY_SELL_RATIO = 0.20
MAX_OPEN_ORDERS_PER_SELLER = 1


class P2PMarketplace:
    """Thread-safe P2P Credit Exchange with Escrow & Ledger Auditing."""

    def __init__(self, hub: Any, ledger: HashChainLedger, storage_path: Optional[Path] = None,
                 owner_id: int = 8106812195, min_credits_to_sell: int = MIN_CREDITS_TO_SELL,
                 max_daily_sell_ratio: float = MAX_DAILY_SELL_RATIO,
                 max_open_orders_per_seller: int = MAX_OPEN_ORDERS_PER_SELLER,
                 notifier: Optional[Any] = None):
        self.hub = hub
        self.ledger = ledger
        self._path = storage_path
        self.owner_id = owner_id
        self.min_credits_to_sell = min_credits_to_sell
        self.max_daily_sell_ratio = max_daily_sell_ratio
        self.max_open_orders_per_seller = max_open_orders_per_seller
        self.notifier = notifier
        self._orders: Dict[str, P2POffer] = {}
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        if self._path and self._path.exists():
            try:
                with interprocess_file_lock(self._path):
                    data = json.loads(self._path.read_text(encoding="utf-8"))
                for d in data:
                    order = P2POffer(**{k: v for k, v in d.items() if k in {f.name for f in dataclasses.fields(P2POffer)}})
                    self._orders[order.order_id] = order
            except Exception:
                pass

    def _flush(self) -> None:
        if not self._path:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with interprocess_file_lock(self._path):
            tmp = self._path.with_suffix(".tmp")
            data = [o.to_dict() for o in self._orders.values()]
            with tmp.open("w", encoding="utf-8") as fh:
                fh.write(json.dumps(data, indent=2, default=str))
                fh.flush()
                try:
                    os.fsync(fh.fileno())
                except OSError:
                    pass
            tmp.replace(self._path)

    # ------------------------------------------------------------------ Market Operations
    def list_orders(self, status: Optional[str] = "OPEN", currency: Optional[str] = None,
                    order_type: Optional[str] = None) -> List[dict]:
        with self._lock:
            res = []
            for o in sorted(self._orders.values(), key=lambda x: x.created_at, reverse=True):
                if status and o.status != status:
                    continue
                if currency and o.currency.upper() != currency.upper():
                    continue
                if order_type and o.order_type.upper() != order_type.upper():
                    continue
                res.append(o.to_dict())
            return res

    def get_order(self, order_id: str) -> Optional[P2POffer]:
        with self._lock:
            return self._orders.get(order_id)

    def _resolve_worker(self, id_or_key: str):
        if not id_or_key or not self.hub:
            return None
        w = self.hub.get_worker(id_or_key) if hasattr(self.hub, "get_worker") else None
        if not w and hasattr(self.hub, "get_worker_by_key"):
            w = self.hub.get_worker_by_key(id_or_key)
        return w

    def _resolve_wid(self, id_or_key: str) -> str:
        if not id_or_key:
            return ""
        w = self._resolve_worker(id_or_key)
        return w.worker_id if w else id_or_key

    def _unfreeze_if_no_active_disputes(self, worker_id: str) -> None:
        if not worker_id or not self.hub:
            return
        w = self._resolve_worker(worker_id)
        if not w:
            return
        still_disputed = any(
            o.status == "DISPUTED" and (o.seller_id == w.worker_id or o.buyer_id == w.worker_id)
            for o in self._orders.values()
        )
        if not still_disputed:
            w.dispute_frozen = False
            w.dispute_account_locked = False
            w.dispute_escrow_locked_credits = 0
            w.dispute_reason = ""
            if hasattr(self.hub, "_flush"):
                self.hub._flush()

    def compute_payment_receipt_hmac(self, order_id: str, payment_ref: str) -> str:
        """Computes HMAC-SHA256 receipt record over order parameters + TID (H5 Fix: no public default secret)."""
        import hashlib
        import hmac
        order = self._orders.get(order_id)
        if not order:
            return ""
        buyer = self._resolve_worker(order.buyer_id)
        raw_secret = (buyer.key if buyer and buyer.key else os.environ.get("PEER_SHARED_SECRET", "")).strip()
        if not raw_secret:
            return ""
        msg = f"P2P_RECEIPT:{order.order_id}:{order.seller_id}:{order.buyer_id}:{order.amount_credits}:{order.price_fiat}:{order.currency}:{payment_ref.strip().upper()}".encode("utf-8")
        return hmac.new(raw_secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

    def verify_payment_via_provider_webhook(self, order_id: str, payment_ref: str, provider_signature: str) -> dict:
        """Verifies payment receipt via payment provider webhook HMAC (NEXUS_PAYMENT_WEBHOOK_SECRET) (H5 Fix)."""
        import hashlib
        import hmac
        webhook_secret = os.environ.get("NEXUS_PAYMENT_WEBHOOK_SECRET", "").strip()
        if not webhook_secret:
            return {"ok": False, "payment_verified": False, "error": "NEXUS_PAYMENT_WEBHOOK_SECRET not configured"}
        with self._lock:
            order = self._orders.get(order_id)
            if not order:
                raise KeyError(f"Order {order_id!r} not found")
            msg = f"WEBHOOK_PAID:{order.order_id}:{order.amount_credits}:{order.price_fiat}:{order.currency}:{payment_ref.strip().upper()}".encode("utf-8")
            expected = hmac.new(webhook_secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
            if not provider_signature or not hmac.compare_digest(provider_signature.strip(), expected):
                return {"ok": False, "payment_verified": False, "error": "Invalid payment provider webhook signature"}
            order.payment_verified = True
            order.verification_method = "PAYMENT_PROVIDER_WEBHOOK"
            order.updated_at = time.time()
            self._flush()
            return {"ok": True, "order_id": order_id, "payment_verified": True, "verification_method": order.verification_method}

    def get_user_orders(self, worker_id: str) -> Dict[str, List[dict]]:
        with self._lock:
            wid = self._resolve_wid(worker_id)
            as_seller = [o.to_dict() for o in self._orders.values() if o.seller_id in {worker_id, wid}]
            as_buyer = [o.to_dict() for o in self._orders.values() if o.buyer_id in {worker_id, wid}]
            return {
                "selling": sorted(as_seller, key=lambda x: x["created_at"], reverse=True),
                "buying": sorted(as_buyer, key=lambda x: x["created_at"], reverse=True),
            }

    def create_sell_order(self, seller_id: str, amount_credits: int, price_fiat: float,
                          payment_method: str, currency: str = "PKR") -> dict:
        """Locks seller's credits into escrow and publishes the sell listing."""
        if amount_credits <= 0:
            raise ValueError("Amount of credits must be positive")
        if price_fiat <= 0:
            raise ValueError("Price must be positive")
        payment_method = payment_method.strip()
        if not payment_method:
            raise ValueError("Payment method details (e.g. EasyPaisa / JazzCash) are required")

        with self._lock:
            # Check seller balance
            seller = self._resolve_worker(seller_id)
            if not seller:
                raise KeyError(f"Worker account {seller_id!r} not found. Please register worker node first.")
            if seller.status == "SLASHED":
                raise PermissionError("Slashed nodes cannot sell credits.")
            if getattr(seller, "dispute_frozen", False):
                return {
                    "ok": False,
                    "dispute_frozen": True,
                    "error": f"Account {seller.worker_id!r} is FROZEN due to an active P2P Dispute ({seller.dispute_reason}). Awaiting Sovereign Owner arbitration."
                }
            if seller.credits < amount_credits:
                return {
                    "ok": False,
                    "error": f"Insufficient credits! You have {seller.credits} credits, requested {amount_credits}."
                }
            seller_wid = seller.worker_id
            if seller_wid != "owner-master":
                if seller.credits < self.min_credits_to_sell:
                    return {
                        "ok": False,
                        "min_threshold_locked": True,
                        "required_threshold": self.min_credits_to_sell,
                        "current_credits": seller.credits,
                        "error": (
                            f"P2P Selling Locked: Minimum {self.min_credits_to_sell} credits balance required to sell on P2P Market "
                            f"(Your current balance: {seller.credits} credits). Welcome starter credits cannot be sold — keep your "
                            f"1-Click Worker running on your PC/Server to earn at least {self.min_credits_to_sell} credits first!"
                        ),
                    }

                # Rule 2A: Max 1 Active Open Sell Order per seller at a time
                active_seller_orders = [
                    o for o in self._orders.values()
                    if o.seller_id == seller_wid and o.status in {"OPEN", "IN_ESCROW", "PAYMENT_SUBMITTED", "DISPUTED"}
                ]
                if len(active_seller_orders) >= self.max_open_orders_per_seller:
                    return {
                        "ok": False,
                        "open_order_limit_reached": True,
                        "max_open_orders": self.max_open_orders_per_seller,
                        "active_order_id": active_seller_orders[0].order_id,
                        "error": (
                            f"Anti-Dump Orderbook Policy: Only {self.max_open_orders_per_seller} active Sell Order is allowed per worker "
                            f"at a time (Active order: {active_seller_orders[0].order_id}). Please wait for your current order to complete or cancel it first."
                        ),
                    }

                # Rule 2B: Max 20% Daily Sell Limit (Anti-Dump Vesting)
                now = time.time()
                sold_last_24h = sum(
                    o.amount_credits for o in self._orders.values()
                    if o.seller_id == seller_wid and o.status != "CANCELLED" and (now - o.created_at) < 86400.0
                )
                effective_balance = seller.credits + sold_last_24h
                max_daily_credits = max(1, int(effective_balance * self.max_daily_sell_ratio))
                remaining_daily_allowance = max(0, max_daily_credits - sold_last_24h)
                if amount_credits > remaining_daily_allowance:
                    pct = int(round(self.max_daily_sell_ratio * 100))
                    return {
                        "ok": False,
                        "daily_vesting_locked": True,
                        "max_daily_sell_ratio": self.max_daily_sell_ratio,
                        "max_sellable_today": remaining_daily_allowance,
                        "current_credits": seller.credits,
                        "error": (
                            f"Anti-Dump Vesting Limit (Max {pct}% Daily Sell): "
                            f"To protect market stability, each worker can sell at most {pct}% of their balance per 24 hours "
                            f"(Your max sellable today: {remaining_daily_allowance} credits out of {effective_balance} credits). "
                            f"You requested {amount_credits} credits — please enter {remaining_daily_allowance} credits or less."
                        ),
                    }

            # Deduct credits from seller and hold in Escrow
            seller.credits -= amount_credits
            if hasattr(self.hub, "_flush"):
                self.hub._flush()

            order_id = f"p2p-{secrets.token_hex(4)}"
            order = P2POffer(
                order_id=order_id,
                seller_id=seller_wid,
                amount_credits=amount_credits,
                price_fiat=round(float(price_fiat), 2),
                currency=currency.upper(),
                payment_method=payment_method,
                status="OPEN",
                escrow_locked=True
            )
            self._orders[order_id] = order
            self._flush()

            block = self.ledger.append("p2p_sell_order_created", {
                "order_id": order_id,
                "seller_id": seller_wid,
                "amount_credits": amount_credits,
                "price_fiat": price_fiat,
                "currency": currency,
                "seller_remaining_credits": seller.credits
            })

            return {
                "ok": True,
                "status": "OPEN",
                "order_id": order_id,
                "seller_id": seller_wid,
                "amount_credits": amount_credits,
                "price_fiat": price_fiat,
                "currency": currency,
                "escrow_locked": True,
                "seller_balance": seller.credits,
                "ledger_block": block["hash"][:16]
            }

    def create_buy_order(self, buyer_id: str, amount_credits: int, price_fiat: float,
                         payment_method: str = "EasyPaisa / JazzCash", currency: str = "PKR") -> dict:
        """Publishes a Buyer's Want-to-Buy order so any Miner/Seller can fulfill it."""
        buyer_id = buyer_id.strip()
        if not buyer_id:
            raise ValueError("Buyer Account Key or Worker ID is required")
        if amount_credits <= 0:
            raise ValueError("Amount of credits to buy must be positive")
        if price_fiat <= 0:
            raise ValueError("Offered price must be positive")
        payment_method = payment_method.strip() or "EasyPaisa / JazzCash"

        with self._lock:
            buyer_rec = self._resolve_worker(buyer_id)
            if not buyer_rec and hasattr(self.hub, "register_worker"):
                buyer_rec = self.hub.register_worker(buyer_id, url="local", initial_credits=0)
            buyer_wid = buyer_rec.worker_id if buyer_rec else buyer_id
            if buyer_rec and buyer_rec.status == "SLASHED":
                raise PermissionError("Slashed nodes cannot post buy orders.")
            if buyer_rec and getattr(buyer_rec, "dispute_frozen", False):
                return {
                    "ok": False,
                    "dispute_frozen": True,
                    "error": f"Account {buyer_wid!r} is FROZEN due to an active P2P Dispute ({buyer_rec.dispute_reason})."
                }

            open_buy_orders = [
                o for o in self._orders.values()
                if o.buyer_id == buyer_wid and o.order_type == "BUY" and o.status == "OPEN"
            ]
            if len(open_buy_orders) >= 3:
                return {
                    "ok": False,
                    "error": f"You already have {len(open_buy_orders)} open Buy Orders. Please wait for a seller or cancel an existing buy order first."
                }

            order_id = f"p2p-buy-{secrets.token_hex(4)}"
            order = P2POffer(
                order_id=order_id,
                seller_id="",
                buyer_id=buyer_wid,
                amount_credits=int(amount_credits),
                price_fiat=round(float(price_fiat), 2),
                currency=currency.upper(),
                payment_method=payment_method,
                status="OPEN",
                escrow_locked=False,
                order_type="BUY",
            )
            self._orders[order_id] = order
            self._flush()

            block = self.ledger.append("p2p_buy_order_created", {
                "order_id": order_id,
                "buyer_id": buyer_wid,
                "amount_credits": amount_credits,
                "price_fiat": price_fiat,
                "currency": currency,
                "payment_method": payment_method,
            })

            return {
                "ok": True,
                "order_type": "BUY",
                "status": "OPEN",
                "order_id": order_id,
                "buyer_id": buyer_wid,
                "amount_credits": amount_credits,
                "price_fiat": price_fiat,
                "currency": currency.upper(),
                "payment_method": payment_method,
                "ledger_block": block["hash"][:16],
            }

    def accept_buy_order(self, order_id: str, seller_id: str, seller_payment_method: str = "") -> dict:
        """Seller accepts a Buyer's open BUY order, locking Seller's credits into Escrow."""
        seller_id = seller_id.strip()
        if not seller_id:
            raise ValueError("Seller Account Key or Worker ID is required")

        with self._lock:
            order = self._orders.get(order_id)
            if not order:
                raise KeyError(f"Order {order_id!r} not found")
            if order.order_type != "BUY":
                return {"ok": False, "error": "This is a Sell Offer, not a Buy Order. Use 'Buy Now' instead."}
            if order.status != "OPEN":
                return {"ok": False, "error": f"Buy Order is already {order.status}"}

            seller = self._resolve_worker(seller_id)
            if not seller:
                raise KeyError(f"Seller account {seller_id!r} not found. Please register worker node first.")
            if seller.status == "SLASHED":
                raise PermissionError("Slashed nodes cannot sell credits.")
            if getattr(seller, "dispute_frozen", False):
                return {
                    "ok": False,
                    "dispute_frozen": True,
                    "error": f"Account {seller.worker_id!r} is FROZEN due to an active P2P Dispute ({seller.dispute_reason}). Awaiting Sovereign Owner arbitration."
                }

            seller_wid = seller.worker_id
            if seller_wid == order.buyer_id:
                return {"ok": False, "error": "You cannot fulfill your own buy order"}

            amount_credits = order.amount_credits
            if seller.credits < amount_credits:
                return {
                    "ok": False,
                    "error": f"Insufficient credits! You have {seller.credits} credits, Buy Order requires {amount_credits} credits."
                }

            if seller_wid != "owner-master":
                if seller.credits < self.min_credits_to_sell:
                    return {
                        "ok": False,
                        "min_threshold_locked": True,
                        "required_threshold": self.min_credits_to_sell,
                        "current_credits": seller.credits,
                        "error": (
                            f"P2P Selling Locked: Minimum {self.min_credits_to_sell} credits balance required to sell on P2P Market "
                            f"(Your current balance: {seller.credits} credits)."
                        ),
                    }
                active_seller_orders = [
                    o for o in self._orders.values()
                    if o.seller_id == seller_wid and o.status in {"OPEN", "IN_ESCROW", "PAYMENT_SUBMITTED", "DISPUTED"}
                ]
                if len(active_seller_orders) >= self.max_open_orders_per_seller:
                    return {
                        "ok": False,
                        "open_order_limit_reached": True,
                        "error": (
                            f"Anti-Dump Orderbook Policy: Only {self.max_open_orders_per_seller} active Sell Order/Escrow is allowed per worker "
                            f"at a time (Active order: {active_seller_orders[0].order_id})."
                        ),
                    }
                now = time.time()
                sold_last_24h = sum(
                    o.amount_credits for o in self._orders.values()
                    if o.seller_id == seller_wid and o.status != "CANCELLED" and (now - o.created_at) < 86400.0
                )
                effective_balance = seller.credits + sold_last_24h
                max_daily_credits = max(1, int(effective_balance * self.max_daily_sell_ratio))
                remaining_daily_allowance = max(0, max_daily_credits - sold_last_24h)
                if amount_credits > remaining_daily_allowance:
                    pct = int(round(self.max_daily_sell_ratio * 100))
                    return {
                        "ok": False,
                        "daily_vesting_locked": True,
                        "max_sellable_today": remaining_daily_allowance,
                        "error": (
                            f"Anti-Dump Vesting Limit (Max {pct}% Daily Sell): "
                            f"Your max sellable today is {remaining_daily_allowance} credits (20% of {effective_balance}), "
                            f"but this Buy Order is for {amount_credits} credits."
                        ),
                    }

            # Lock Seller's credits into Escrow
            seller.credits -= amount_credits
            if hasattr(self.hub, "_flush"):
                self.hub._flush()

            order.seller_id = seller_wid
            if seller_payment_method.strip():
                order.payment_method = seller_payment_method.strip()
            order.status = "IN_ESCROW"
            order.escrow_locked = True
            order.updated_at = time.time()
            self._flush()

            block = self.ledger.append("p2p_buy_order_accepted", {
                "order_id": order_id,
                "seller_id": seller_wid,
                "buyer_id": order.buyer_id,
                "amount_credits": amount_credits,
                "price_fiat": order.price_fiat,
                "currency": order.currency,
                "seller_remaining_credits": seller.credits,
            })

            return {
                "ok": True,
                "status": "IN_ESCROW",
                "order_id": order_id,
                "seller_id": seller_wid,
                "buyer_id": order.buyer_id,
                "amount_credits": amount_credits,
                "price_fiat": order.price_fiat,
                "currency": order.currency,
                "payment_method": order.payment_method,
                "seller_balance": seller.credits,
                "ledger_block": block["hash"][:16],
            }

    def initiate_buy(self, order_id: str, buyer_id: str) -> dict:
        """Buyer selects an open sell offer to buy credits."""
        buyer_id = buyer_id.strip()
        if not buyer_id:
            raise ValueError("Buyer worker ID is required")

        with self._lock:
            order = self._orders.get(order_id)
            if not order:
                raise KeyError(f"Order {order_id!r} not found")
            if order.order_type == "BUY":
                return {"ok": False, "error": "This is a Buy Order, not a Sell Offer. Use 'accept_buy_order' to fulfill it."}
            if order.status != "OPEN":
                return {"ok": False, "error": f"Order is already {order.status}"}

            # Auto-register buyer if not in hub yet
            buyer_rec = self._resolve_worker(buyer_id)
            if not buyer_rec and hasattr(self.hub, "register_worker"):
                buyer_rec = self.hub.register_worker(buyer_id, url="local", initial_credits=0)
            buyer_wid = buyer_rec.worker_id if buyer_rec else buyer_id
            if buyer_rec and buyer_rec.status == "SLASHED":
                raise PermissionError("Slashed nodes cannot buy credits.")
            if buyer_rec and getattr(buyer_rec, "dispute_frozen", False):
                return {
                    "ok": False,
                    "dispute_frozen": True,
                    "error": f"Account {buyer_wid!r} is FROZEN due to an active P2P Dispute ({buyer_rec.dispute_reason})."
                }

            if order.seller_id == buyer_wid:
                return {"ok": False, "error": "You cannot buy your own sell order"}

            order.buyer_id = buyer_wid
            order.status = "IN_ESCROW"
            order.updated_at = time.time()
            self._flush()

            block = self.ledger.append("p2p_buy_initiated", {
                "order_id": order_id,
                "seller_id": order.seller_id,
                "buyer_id": buyer_wid,
                "amount_credits": order.amount_credits,
                "price_fiat": order.price_fiat,
                "currency": order.currency
            })

            return {
                "ok": True,
                "status": "IN_ESCROW",
                "order_id": order_id,
                "seller_id": order.seller_id,
                "buyer_id": buyer_wid,
                "amount_credits": order.amount_credits,
                "price_fiat": order.price_fiat,
                "currency": order.currency,
                "payment_method": order.payment_method,
                "instructions": (
                    f"Please send {order.currency} {order.price_fiat} to the seller via {order.payment_method}. "
                    "Then enter your Transaction ID (TID) / reference code."
                ),
                "ledger_block": block["hash"][:16]
            }

    def submit_payment(self, order_id: str, buyer_id: str, payment_ref: str) -> dict:
        """Buyer marks that they sent the payment and submits receipt reference."""
        payment_ref = (payment_ref or "").strip()
        if not payment_ref or len(payment_ref) < 5:
            raise ValueError("Valid Payment reference / Transaction ID (TID >= 5 chars) is required")

        with self._lock:
            order = self._orders.get(order_id)
            if not order:
                raise KeyError(f"Order {order_id!r} not found")
            buyer_wid = self._resolve_wid(buyer_id)
            if order.buyer_id not in {buyer_id, buyer_wid}:
                raise PermissionError("Only the assigned buyer can submit payment")
            if order.status not in {"IN_ESCROW", "PAYMENT_SUBMITTED"}:
                return {"ok": False, "error": f"Order status is {order.status}, cannot submit payment"}

            # H5 Anti-Replay Guard: Prevent reusing the same TID across multiple orders
            ref_norm = payment_ref.upper()
            for other in self._orders.values():
                if other.order_id != order_id and other.status != "CANCELLED":
                    if other.payment_reference and other.payment_reference.strip().upper() == ref_norm:
                        return {
                            "ok": False,
                            "duplicate_payment_reference": True,
                            "error": f"Payment reference '{payment_ref}' has already been submitted on another order (H5 Anti-Replay Guard).",
                        }

            order.payment_reference = payment_ref
            order.payment_receipt_hmac = self.compute_payment_receipt_hmac(order_id, payment_ref)
            order.receipt_recorded = True
            order.payment_verified = False
            order.verification_method = "AWAITING_SELLER_OR_PROVIDER_CONFIRMATION"
            order.status = "PAYMENT_SUBMITTED"
            order.updated_at = time.time()
            self._flush()

            block = self.ledger.append("p2p_payment_submitted", {
                "order_id": order_id,
                "seller_id": order.seller_id,
                "buyer_id": order.buyer_id,
                "payment_reference": payment_ref,
                "payment_receipt_hmac": order.payment_receipt_hmac[:24],
                "receipt_recorded": True,
                "payment_verified": False,
            })

            return {
                "ok": True,
                "status": "PAYMENT_SUBMITTED",
                "order_id": order_id,
                "payment_reference": payment_ref,
                "payment_receipt_hmac": order.payment_receipt_hmac,
                "receipt_recorded": order.receipt_recorded,
                "payment_verified": order.payment_verified,
                "verification_method": order.verification_method,
                "message": "Payment TID receipt recorded! Payment is NOT verified until Seller manual confirmation or Payment Provider API webhook.",
                "ledger_block": block["hash"][:16]
            }

    def raise_dispute(self, order_id: str, caller_id: str, reason: str = "Payment / TID verification dispute",
                      is_owner: bool = False) -> dict:
        """Freezes the disputed order's escrow (order-scoped freeze, H6 Fix) and locks accused scammer buyer if raised by seller."""
        reason = (reason or "Payment / TID verification dispute").strip()
        with self._lock:
            order = self._orders.get(order_id)
            if not order:
                raise KeyError(f"Order {order_id!r} not found")
            caller_wid = self._resolve_wid(caller_id)
            if not is_owner and caller_wid not in {order.seller_id, order.buyer_id} and caller_id not in {order.seller_id, order.buyer_id}:
                raise PermissionError("Only the Buyer, Seller, or Sovereign Owner of this order can raise a dispute")
            if order.status == "IN_ESCROW" and not is_owner:
                return {
                    "ok": False,
                    "griefing_blocked": True,
                    "error": "Cannot raise a dispute before a payment reference (TID) has been submitted (H6 Anti-Griefing Guard).",
                }
            if order.status not in {"PAYMENT_SUBMITTED", "DISPUTED"} and not is_owner:
                return {"ok": False, "error": f"Cannot dispute order in status {order.status}"}
            if not is_owner:
                active_disputes = sum(
                    1 for o in self._orders.values()
                    if o.order_id != order_id and o.status == "DISPUTED" and (o.disputed_by == caller_wid or o.buyer_id == caller_wid)
                )
                if active_disputes >= 1:
                    return {
                        "ok": False,
                        "griefing_blocked": True,
                        "error": "You already have an unresolved P2P dispute pending arbitration (H6 Anti-Griefing Guard).",
                    }

            order.status = "DISPUTED"
            order.escrow_locked = True
            order.dispute_reason = reason
            order.disputed_by = caller_wid or caller_id
            order.updated_at = time.time()

            frozen_accounts = []
            # H6 Fix: Seller's order credits are already locked in order.escrow_locked (order-level freeze),
            # so seller's un-escrowed balance is NOT account-locked (dispute_account_locked=False).
            # Only the accused buyer who submitted a disputed fake TID gets dispute_account_locked=True.
            for wid in (order.seller_id, order.buyer_id):
                if wid and self.hub:
                    w = self._resolve_worker(wid)
                    if w:
                        w.dispute_frozen = True
                        w.dispute_reason = f"Dispute on {order_id}: {reason}"
                        if w.worker_id == order.seller_id:
                            w.dispute_escrow_locked_credits = int(order.amount_credits)
                            w.dispute_account_locked = False
                        elif w.worker_id == order.buyer_id and order.disputed_by == order.seller_id:
                            w.dispute_account_locked = True
                        frozen_accounts.append(w.worker_id)
            if hasattr(self.hub, "_flush"):
                self.hub._flush()
            self._flush()

            block = self.ledger.append("p2p_order_disputed", {
                "order_id": order_id,
                "seller_id": order.seller_id,
                "buyer_id": order.buyer_id,
                "disputed_by": order.disputed_by,
                "reason": reason,
                "amount_credits": order.amount_credits,
                "price_fiat": order.price_fiat,
                "payment_reference": order.payment_reference,
                "frozen_accounts": frozen_accounts,
            })

            alert_msg = (
                f"🚨 P2P ESCROW DISPUTE ESCALATION [{order_id}]\n"
                f"• Raised By: {order.disputed_by}\n"
                f"• Seller: {order.seller_id} | Buyer: {order.buyer_id}\n"
                f"• Amount: {order.amount_credits} Credits for {order.currency} {order.price_fiat:.2f}\n"
                f"• Payment Method: {order.payment_method}\n"
                f"• Submitted TID / Proof: {order.payment_reference or '(none)'}\n"
                f"• Reason: {reason}\n"
                f"❄️ Accounts Frozen: {', '.join(frozen_accounts)}\n\n"
                f"👑 Owner Arbitration Commands:\n"
                f"  Release to Buyer: /p2p_release {order_id}\n"
                f"  Refund to Seller: /p2p_cancel {order_id}"
            )
            if callable(self.notifier):
                try:
                    self.notifier(alert_msg)
                except Exception:
                    pass

            return {
                "ok": True,
                "status": "DISPUTED",
                "order_id": order_id,
                "seller_id": order.seller_id,
                "buyer_id": order.buyer_id,
                "disputed_by": order.disputed_by,
                "reason": reason,
                "frozen_accounts": frozen_accounts,
                "owner_notified": True,
                "message": (
                    f"Order {order_id} is now DISPUTED. Both Buyer ({order.buyer_id}) and Seller ({order.seller_id}) "
                    f"accounts are temporarily FROZEN and the Sovereign Owner has been alerted on Telegram for arbitration."
                ),
                "ledger_block": block["hash"][:16],
            }

    def confirm_and_release(self, order_id: str, caller_id: str, is_owner: bool = False) -> dict:
        """Seller verifies money received in EasyPaisa/JazzCash and releases escrowed credits to buyer."""
        with self._lock:
            order = self._orders.get(order_id)
            if not order:
                raise KeyError(f"Order {order_id!r} not found")
            caller_wid = self._resolve_wid(caller_id)
            if not is_owner and order.seller_id not in {caller_id, caller_wid}:
                raise PermissionError("Only the seller (or Sovereign Owner) can release escrow")
            if order.status == "DISPUTED" and not is_owner:
                return {
                    "ok": False,
                    "error": "Order is DISPUTED and frozen. Only the Sovereign Owner can arbitrate and release a disputed order.",
                }
            if order.status not in {"IN_ESCROW", "PAYMENT_SUBMITTED", "DISPUTED"}:
                return {"ok": False, "error": f"Order status is {order.status}, cannot release"}

            # Transfer escrowed credits to buyer
            buyer = self._resolve_worker(order.buyer_id)
            if not buyer:
                # If buyer not found, register them
                buyer = self.hub.register_worker(order.buyer_id, url="local", initial_credits=0)

            buyer.credits += order.amount_credits
            if hasattr(self.hub, "_flush"):
                self.hub._flush()

            order.status = "COMPLETED"
            order.escrow_locked = False
            order.payment_verified = True
            if order.verification_method in {"UNVERIFIED", "AWAITING_SELLER_OR_PROVIDER_CONFIRMATION"}:
                order.verification_method = "OWNER_ARBITRATION_CONFIRMATION" if is_owner else "SELLER_MANUAL_CONFIRMATION"
            order.updated_at = time.time()
            self._unfreeze_if_no_active_disputes(order.seller_id)
            self._unfreeze_if_no_active_disputes(order.buyer_id)
            self._flush()

            block = self.ledger.append("p2p_trade_settled", {
                "order_id": order_id,
                "seller_id": order.seller_id,
                "buyer_id": order.buyer_id,
                "credits_transferred": order.amount_credits,
                "price_fiat": order.price_fiat,
                "currency": order.currency,
                "payment_reference": order.payment_reference,
                "released_by": "OWNER" if is_owner else "SELLER",
                "payment_verified": True,
                "verification_method": order.verification_method,
                "buyer_new_balance": buyer.credits
            })

            return {
                "ok": True,
                "status": "COMPLETED",
                "order_id": order_id,
                "credits_released": order.amount_credits,
                "buyer_id": order.buyer_id,
                "buyer_new_balance": buyer.credits,
                "payment_verified": True,
                "verification_method": order.verification_method,
                "ledger_block": block["hash"][:16]
            }

    def cancel_order(self, order_id: str, caller_id: str, is_owner: bool = False) -> dict:
        """Cancels sell or buy order and returns escrowed credits back to the seller if locked."""
        with self._lock:
            order = self._orders.get(order_id)
            if not order:
                raise KeyError(f"Order {order_id!r} not found")
            caller_wid = self._resolve_wid(caller_id)
            is_buyer_cancelling_open_buy = (
                order.order_type == "BUY"
                and order.status == "OPEN"
                and not order.escrow_locked
                and order.buyer_id in {caller_id, caller_wid}
            )
            if not is_owner and not is_buyer_cancelling_open_buy and order.seller_id not in {caller_id, caller_wid}:
                raise PermissionError("Only the seller, order creator, or Sovereign Owner can cancel the order")
            if order.status == "COMPLETED":
                return {"ok": False, "error": "Cannot cancel completed trade"}
            if order.status == "CANCELLED":
                return {"ok": False, "error": "Order is already cancelled"}
            if order.status in {"PAYMENT_SUBMITTED", "DISPUTED"} and not is_owner:
                return {"ok": False, "error": "Cannot cancel after buyer has submitted payment proof or raised a dispute. Sovereign Owner arbitration required."}

            # Refund escrowed credits back to seller if locked
            refunded = 0
            seller = self.hub.get_worker(order.seller_id) if (order.seller_id and hasattr(self.hub, "get_worker")) else None
            if seller and order.escrow_locked:
                seller.credits += order.amount_credits
                refunded = order.amount_credits
                if hasattr(self.hub, "_flush"):
                    self.hub._flush()

            order.status = "CANCELLED"
            order.escrow_locked = False
            order.updated_at = time.time()
            self._unfreeze_if_no_active_disputes(order.seller_id)
            self._unfreeze_if_no_active_disputes(order.buyer_id)
            self._flush()

            block = self.ledger.append("p2p_order_cancelled", {
                "order_id": order_id,
                "order_type": order.order_type,
                "seller_id": order.seller_id,
                "buyer_id": order.buyer_id,
                "refunded_credits": refunded,
                "cancelled_by": "OWNER" if is_owner else ("BUYER" if is_buyer_cancelling_open_buy else "SELLER")
            })

            return {
                "ok": True,
                "status": "CANCELLED",
                "order_id": order_id,
                "refunded_credits": refunded,
                "seller_id": order.seller_id,
                "buyer_id": order.buyer_id,
                "ledger_block": block["hash"][:16]
            }

    def market_stats(self) -> dict:
        with self._lock:
            orders = list(self._orders.values())
            open_orders = [o for o in orders if o.status == "OPEN"]
            completed = [o for o in orders if o.status == "COMPLETED"]
            disputed = [o for o in orders if o.status == "DISPUTED"]
            total_escrow = sum(o.amount_credits for o in orders if o.escrow_locked)
            total_traded = sum(o.amount_credits for o in completed)
            total_volume_fiat = sum(o.price_fiat for o in completed)

            avg_rate_pkr = 0.0
            pkr_orders = [o for o in open_orders if o.currency == "PKR"]
            if pkr_orders:
                avg_rate_pkr = round(sum(o.price_fiat / o.amount_credits for o in pkr_orders) / len(pkr_orders), 2)

            return {
                "open_orders_count": len(open_orders),
                "completed_trades_count": len(completed),
                "disputed_orders_count": len(disputed),
                "credits_in_escrow": total_escrow,
                "total_credits_traded": total_traded,
                "total_volume_fiat": total_volume_fiat,
                "suggested_rate_pkr_per_credit": avg_rate_pkr or 5.0,
                "min_credits_to_sell": self.min_credits_to_sell,
                "max_daily_sell_ratio": self.max_daily_sell_ratio,
                "max_open_orders_per_seller": self.max_open_orders_per_seller,
            }
