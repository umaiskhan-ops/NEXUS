"""The Token Sink Engine: Gamified Consumption, Deflationary Lottery & Staking Vault.

Prevents market dumps by providing irresistible internal utilities for earned credits:
1. AI Chat & Autonomous IDE Access (Free ChatGPT Plus & Cursor Pro alternative for students/devs).
2. The Deflationary Credit Lottery Pool (5 Credits ticket -> 45 Credits Jackpot + 5 Credits Burned).
3. The Credit Staking Vault (Yield, VIP Task Scheduling & 2x Luck Multiplier).
"""
from __future__ import annotations

import dataclasses
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .ledger import HashChainLedger, interprocess_file_lock

TICKET_PRICE_CREDITS = 5
DEFAULT_TARGET_POOL_TICKETS = 10  # 10 tickets = 50 credits
JACKPOT_WINNER_SHARE = 0.90       # 90% (45 credits) to lucky winner
DEFLATIONARY_BURN_SHARE = 0.10    # 10% (5 credits) permanently burned forever!
DEFAULT_STAKE_LOCK_SECONDS = 86400.0  # 24-hour lock window (H3 Fix)


@dataclass
class LotteryTicket:
    ticket_id: str
    round_number: int
    worker_id: str
    bought_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclass
class StakingRecord:
    worker_id: str
    staked_amount: int
    staked_at: float = field(default_factory=time.time)
    tier: str = "BRONZE"  # BRONZE | SILVER | GOLD
    locked_until: float = 0.0
    last_lottery_round_used: int = 0

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


class TokenSinkManager:
    """Manages the Deflationary Lottery Pool, Staking Vault, and Utility Consumption metrics."""

    def __init__(
        self,
        hub: Any,
        ledger: HashChainLedger,
        storage_path: Optional[Path] = None,
        ticket_price: int = TICKET_PRICE_CREDITS,
        target_pool_tickets: int = DEFAULT_TARGET_POOL_TICKETS,
        min_stake_lock_seconds: float = DEFAULT_STAKE_LOCK_SECONDS,
    ):
        self.hub = hub
        self.ledger = ledger
        self._path = storage_path
        self.ticket_price = ticket_price
        self.target_pool_tickets = target_pool_tickets
        self.min_stake_lock_seconds = float(min_stake_lock_seconds)
        self._lock = threading.RLock()

        # Lottery State & Commit-Reveal Beacon (H2 Fix)
        self.current_round: int = 1
        self.current_tickets: List[LotteryTicket] = []
        self.past_winners: List[dict] = []
        self.total_lottery_rounds_completed: int = 0
        self.total_deflationary_burned_credits: int = 0
        self.total_jackpot_credits_awarded: int = 0
        self._round_seed_secret: str = secrets.token_hex(32)
        self.round_seed_commit: str = hashlib.sha256(self._round_seed_secret.encode("utf-8")).hexdigest()

        # Staking State
        self._stakers: Dict[str, StakingRecord] = {}

        self._load()

    def _load(self) -> None:
        if self._path and self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                self.current_round = int(data.get("current_round", 1))
                self.total_lottery_rounds_completed = int(data.get("total_lottery_rounds_completed", 0))
                self.total_deflationary_burned_credits = int(data.get("total_deflationary_burned_credits", 0))
                self.total_jackpot_credits_awarded = int(data.get("total_jackpot_credits_awarded", 0))
                self.past_winners = list(data.get("past_winners", []))

                for t in data.get("current_tickets", []):
                    self.current_tickets.append(LotteryTicket(**t))

                valid_staker_fields = {f.name for f in dataclasses.fields(StakingRecord)}
                for wid, s in data.get("stakers", {}).items():
                    self._stakers[wid] = StakingRecord(**{k: v for k, v in s.items() if k in valid_staker_fields})
                if data.get("round_seed_secret"):
                    self._round_seed_secret = str(data["round_seed_secret"])
                    self.round_seed_commit = hashlib.sha256(self._round_seed_secret.encode("utf-8")).hexdigest()
            except Exception:
                pass

    def _flush(self) -> None:
        if not self._path:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with interprocess_file_lock(self._path):
                tmp = self._path.with_suffix(".tmp")
                payload = {
                    "current_round": self.current_round,
                    "round_seed_commit": self.round_seed_commit,
                    "round_seed_secret": self._round_seed_secret,
                    "total_lottery_rounds_completed": self.total_lottery_rounds_completed,
                    "total_deflationary_burned_credits": self.total_deflationary_burned_credits,
                    "total_jackpot_credits_awarded": self.total_jackpot_credits_awarded,
                    "past_winners": self.past_winners[-50:],
                    "current_tickets": [t.to_dict() for t in self.current_tickets],
                    "stakers": {wid: s.to_dict() for wid, s in self._stakers.items()},
                }
                with tmp.open("w", encoding="utf-8") as fh:
                    fh.write(json.dumps(payload, indent=2, default=str))
                    fh.flush()
                    try:
                        os.fsync(fh.fileno())
                    except OSError:
                        pass
                tmp.replace(self._path)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 1. DEFLATIONARY CREDIT LOTTERY & JACKPOT POOL
    # ------------------------------------------------------------------
    def buy_lottery_ticket(self, worker_id_or_key: str, count: int = 1) -> dict:
        """Enters 1 or more tickets into the active 50-credit Lottery Pool (5 credits/ticket)."""
        count = max(1, int(count or 1))
        cost = count * self.ticket_price

        with self._lock:
            worker = None
            if hasattr(self.hub, "get_worker_by_key"):
                worker = self.hub.get_worker_by_key(worker_id_or_key)
            if not worker and hasattr(self.hub, "get_worker"):
                worker = self.hub.get_worker(worker_id_or_key)

            if not worker:
                return {"ok": False, "error": f"Worker account '{worker_id_or_key}' not found"}
            if worker.status == "SLASHED":
                return {"ok": False, "error": f"Worker '{worker.worker_id}' is SLASHED and blacklisted"}
            if getattr(worker, "dispute_frozen", False):
                return {"ok": False, "error": f"Worker '{worker.worker_id}' is FROZEN under active dispute"}

            if worker.credits < cost:
                return {
                    "ok": False,
                    "insufficient_credits": True,
                    "balance": worker.credits,
                    "required": cost,
                    "error": f"Insufficient credits! You have {worker.credits} credits, need {cost} credits for {count} ticket(s)."
                }

            # Deduct credits from user
            spent_res = self.hub.spend_credits(
                worker.worker_id,
                cost,
                reason=f"lottery_tickets_round_{self.current_round}"
            )

            # Generate tickets & lock staker position if staked in this round (H3 Fix)
            staker_rec = self._stakers.get(worker.worker_id)
            if staker_rec:
                staker_rec.last_lottery_round_used = self.current_round
                staker_rec.locked_until = max(staker_rec.locked_until, time.time() + max(60.0, self.min_stake_lock_seconds))

            new_ticket_ids = []
            for _ in range(count):
                tid = f"ticket-{secrets.token_hex(4)}"
                ticket = LotteryTicket(
                    ticket_id=tid,
                    round_number=self.current_round,
                    worker_id=worker.worker_id,
                )
                self.current_tickets.append(ticket)
                new_ticket_ids.append(tid)

            # Ledger record
            block = self.ledger.append("lottery_ticket_purchased", {
                "round_number": self.current_round,
                "round_seed_commit": self.round_seed_commit,
                "worker_id": worker.worker_id,
                "ticket_count": count,
                "credits_spent": cost,
                "ticket_ids": new_ticket_ids,
                "total_pool_tickets": len(self.current_tickets),
            })

            draw_info = None
            # Auto-draw if target pool reached (e.g. 10 tickets = 50 credits)
            if len(self.current_tickets) >= self.target_pool_tickets:
                draw_info = self.draw_lottery_winner()

            self._flush()

            pool_val = len(self.current_tickets) * self.ticket_price
            return {
                "ok": True,
                "status": "TICKETS_PURCHASED",
                "round_number": self.current_round,
                "round_seed_commit": self.round_seed_commit,
                "worker_id": worker.worker_id,
                "tickets_bought": count,
                "cost_credits": cost,
                "remaining_credits": spent_res["remaining_credits"],
                "current_pool_credits": pool_val,
                "target_pool_credits": self.target_pool_tickets * self.ticket_price,
                "tickets_needed_for_draw": max(0, self.target_pool_tickets - len(self.current_tickets)),
                "ledger_block": block["hash"][:16],
                "auto_drawn": bool(draw_info),
                "draw_result": draw_info,
            }

    @staticmethod
    def verify_draw_proof(draw_entry: dict) -> bool:
        """Publicly verifies the Commit-Reveal lottery beacon (H2 Fix)."""
        try:
            revealed_seed = str(draw_entry["revealed_seed"])
            seed_commit = str(draw_entry["seed_commit"])
            if hashlib.sha256(revealed_seed.encode("utf-8")).hexdigest() != seed_commit:
                return False
            raw_entropy = f"{draw_entry['round_number']}:{draw_entry['tail_hash']}:{draw_entry['total_tickets']}:{revealed_seed}"
            expected_beacon = hashlib.sha256(raw_entropy.encode("utf-8")).hexdigest()
            return hmac.compare_digest(expected_beacon, str(draw_entry["beacon_hash"]))
        except Exception:
            return False

    def draw_lottery_winner(self, force: bool = False) -> dict:
        """Selects 1 lucky winner via Commit-Reveal Verifiable Random Beacon, awards 90% and permanently burns 10%."""
        with self._lock:
            if not self.current_tickets:
                return {"ok": False, "error": "No tickets in the current lottery pool"}
            if len(self.current_tickets) < self.target_pool_tickets and not force:
                return {
                    "ok": False,
                    "error": f"Lottery pool requires {self.target_pool_tickets} tickets for automatic draw (currently {len(self.current_tickets)})",
                }
            if len(self.current_tickets) < 2 and not force:
                return {"ok": False, "error": "Need at least 2 tickets in the pool to trigger lottery draw"}

            total_pot = len(self.current_tickets) * self.ticket_price
            jackpot_amount = int(round(total_pot * JACKPOT_WINNER_SHARE))
            burn_amount = total_pot - jackpot_amount

            # Commit-Reveal Verifiable Random Consensus Beacon (H2 Fix: deterministic & publicly verifiable)
            ledger_tail = self.ledger.tail(1)
            tail_hash = ledger_tail[0]["hash"] if ledger_tail else "genesis_seed"
            total_tickets_count = len(self.current_tickets)
            revealed_seed = self._round_seed_secret
            seed_commit = self.round_seed_commit
            raw_entropy = f"{self.current_round}:{tail_hash}:{total_tickets_count}:{revealed_seed}"
            beacon_hash = hashlib.sha256(raw_entropy.encode("utf-8")).hexdigest()

            # Account for staker luck multipliers if staker bought tickets AND stake has matured >= min_stake_lock_seconds (H3 Fix)
            now = time.time()
            ticket_pool = []
            for t in self.current_tickets:
                ticket_pool.append(t)
                staker_rec = self._stakers.get(t.worker_id)
                if staker_rec:
                    staker_rec.last_lottery_round_used = self.current_round
                    staker_rec.locked_until = max(staker_rec.locked_until, now + max(60.0, self.min_stake_lock_seconds))
                    if staker_rec.tier == "GOLD" and (now - staker_rec.staked_at) >= self.min_stake_lock_seconds:
                        ticket_pool.append(t)  # Extra winning weight only for matured Gold Stakers

            winning_index = int(beacon_hash[:8], 16) % len(ticket_pool)
            winning_ticket = ticket_pool[winning_index]
            winner_wid = winning_ticket.worker_id

            # Award 90% jackpot to lucky winner
            grant_res = self.hub.grant_credits(
                winner_wid,
                jackpot_amount,
                reason=f"lottery_jackpot_round_{self.current_round}"
            )

            # Deflationary Burn: 10% permanently destroyed from total supply
            self.total_deflationary_burned_credits += burn_amount
            self.total_jackpot_credits_awarded += jackpot_amount
            self.total_lottery_rounds_completed += 1

            # Ledger Blocks
            block_jackpot = self.ledger.append("lottery_jackpot_won", {
                "round_number": self.current_round,
                "winner_worker_id": winner_wid,
                "winning_ticket_id": winning_ticket.ticket_id,
                "jackpot_amount": jackpot_amount,
                "deflationary_burned_amount": burn_amount,
                "total_pot": total_pot,
                "beacon_hash": beacon_hash,
                "seed_commit": seed_commit,
                "revealed_seed": revealed_seed,
                "tail_hash": tail_hash,
                "participants_count": len(set(t.worker_id for t in self.current_tickets)),
                "total_tickets": total_tickets_count,
            })

            result_entry = {
                "round_number": self.current_round,
                "winner_worker_id": winner_wid,
                "winning_ticket_id": winning_ticket.ticket_id,
                "jackpot_credits": jackpot_amount,
                "burned_credits": burn_amount,
                "total_pot_credits": total_pot,
                "total_tickets": total_tickets_count,
                "winner_new_balance": grant_res.get("new_balance"),
                "beacon_hash": beacon_hash,
                "seed_commit": seed_commit,
                "revealed_seed": revealed_seed,
                "tail_hash": tail_hash,
                "drawn_at": now,
                "ledger_block": block_jackpot["hash"][:16],
            }
            self.past_winners.append(result_entry)

            # Advance to next round and generate new Commit-Reveal seed
            self.current_round += 1
            self.current_tickets = []
            self._round_seed_secret = secrets.token_hex(32)
            self.round_seed_commit = hashlib.sha256(self._round_seed_secret.encode("utf-8")).hexdigest()
            self._flush()

            return {
                "ok": True,
                "status": "JACKPOT_DRAWN",
                **result_entry
            }

    def get_lottery_status(self) -> dict:
        with self._lock:
            pool_val = len(self.current_tickets) * self.ticket_price
            target_val = self.target_pool_tickets * self.ticket_price
            return {
                "ok": True,
                "currency_symbol": "UMAIS",
                "credit_to_umais_parity": "1 Credit = 1 UMAIS",
                "current_round": self.current_round,
                "round_seed_commit": self.round_seed_commit,
                "ticket_price_credits": self.ticket_price,
                "ticket_price_umais": self.ticket_price,
                "current_pool_credits": pool_val,
                "current_pool_umais": pool_val,
                "target_pool_credits": target_val,
                "target_pool_tickets": self.target_pool_tickets,
                "tickets_sold_in_round": len(self.current_tickets),
                "tickets_needed_for_draw": max(0, self.target_pool_tickets - len(self.current_tickets)),
                "estimated_jackpot_payout": int(round(max(pool_val, target_val) * JACKPOT_WINNER_SHARE)),
                "estimated_burn_payout": int(round(max(pool_val, target_val) * DEFLATIONARY_BURN_SHARE)),
                "total_rounds_completed": self.total_lottery_rounds_completed,
                "total_deflationary_burned_credits": self.total_deflationary_burned_credits,
                "total_jackpot_credits_awarded": self.total_jackpot_credits_awarded,
                "recent_winners": self.past_winners[-5:],
            }

    # ------------------------------------------------------------------
    # 2. CREDIT STAKING VAULT (YIELD & VIP QUEUE)
    # ------------------------------------------------------------------
    def stake_credits(self, worker_id_or_key: str, amount: int) -> dict:
        amount = int(amount or 0)
        if amount <= 0:
            return {"ok": False, "error": "Stake amount must be positive"}

        with self._lock:
            worker = None
            if hasattr(self.hub, "get_worker_by_key"):
                worker = self.hub.get_worker_by_key(worker_id_or_key)
            if not worker and hasattr(self.hub, "get_worker"):
                worker = self.hub.get_worker(worker_id_or_key)

            if not worker:
                return {"ok": False, "error": f"Worker account '{worker_id_or_key}' not found"}
            if worker.status == "SLASHED":
                return {"ok": False, "error": "Slashed nodes cannot stake credits"}
            if getattr(worker, "dispute_frozen", False):
                return {"ok": False, "error": f"Account '{worker.worker_id}' is frozen due to an active P2P dispute"}
            if worker.credits < amount:
                return {
                    "ok": False,
                    "insufficient_credits": True,
                    "balance": worker.credits,
                    "required": amount,
                    "error": f"Insufficient credits to stake! Balance: {worker.credits}, Required: {amount}"
                }

            # Deduct from active balance and lock in vault
            spent = self.hub.spend_credits(worker.worker_id, amount, reason="staking_vault_deposit")

            current_rec = self._stakers.get(worker.worker_id)
            new_amount = (current_rec.staked_amount if current_rec else 0) + amount

            now = time.time()
            has_active_tickets = any(t.worker_id == worker.worker_id for t in self.current_tickets)
            tier = "GOLD" if new_amount >= 150 else ("SILVER" if new_amount >= 50 else "BRONZE")
            self._stakers[worker.worker_id] = StakingRecord(
                worker_id=worker.worker_id,
                staked_amount=new_amount,
                tier=tier,
                staked_at=now,
                locked_until=now + self.min_stake_lock_seconds,
                last_lottery_round_used=self.current_round if has_active_tickets else (current_rec.last_lottery_round_used if current_rec else 0),
            )
            self._flush()

            block = self.ledger.append("credits_staked_vault", {
                "worker_id": worker.worker_id,
                "amount_staked": amount,
                "total_staked": new_amount,
                "tier": tier,
                "locked_until": now + self.min_stake_lock_seconds,
            })

            perks = {
                "BRONZE": "+5% Compute Task Yield Bonus",
                "SILVER": "+10% Compute Task Yield + Priority Supercomputer Task Dispatch",
                "GOLD": "+20% Compute Task Yield + 2x Lottery Luck Odds (after 24h maturity) + Gold Sovereign Badge",
            }

            return {
                "ok": True,
                "status": "STAKED",
                "worker_id": worker.worker_id,
                "amount_staked_now": amount,
                "total_staked": new_amount,
                "remaining_credits": spent["remaining_credits"],
                "tier": tier,
                "locked_until": now + self.min_stake_lock_seconds,
                "perks": perks[tier],
                "ledger_block": block["hash"][:16],
            }

    def unstake_credits(self, worker_id_or_key: str, amount: int, enforce_lock: bool = False) -> dict:
        amount = int(amount or 0)
        if amount <= 0:
            return {"ok": False, "error": "Unstake amount must be positive"}

        with self._lock:
            worker = None
            if hasattr(self.hub, "get_worker_by_key"):
                worker = self.hub.get_worker_by_key(worker_id_or_key)
            if not worker and hasattr(self.hub, "get_worker"):
                worker = self.hub.get_worker(worker_id_or_key)

            if not worker:
                return {"ok": False, "error": f"Worker account '{worker_id_or_key}' not found"}
            if worker.status == "SLASHED":
                return {"ok": False, "error": "Slashed nodes cannot unstake credits (forfeited under slashing protocol)"}
            if getattr(worker, "dispute_frozen", False):
                return {"ok": False, "error": f"Account '{worker.worker_id}' is frozen due to an active P2P dispute"}

            rec = self._stakers.get(worker.worker_id)
            if not rec or rec.staked_amount < amount:
                curr = rec.staked_amount if rec else 0
                return {"ok": False, "error": f"Insufficient staked balance (Staked: {curr}, Requested: {amount})"}

            # H3 Anti-Flash-Stake Lock Enforcement:
            # Block unstaking if caller has active lottery tickets in the current round, participated in a lottery draw
            # during their lock window, or when enforce_lock=True (HTTP API) and lock period has not elapsed.
            now = time.time()
            has_active_round_tickets = any(t.worker_id == worker.worker_id for t in self.current_tickets)
            if has_active_round_tickets or rec.last_lottery_round_used > 0 or enforce_lock:
                effective_lock_until = rec.locked_until or (rec.staked_at + self.min_stake_lock_seconds)
                if now < effective_lock_until:
                    rem_s = int(max(1.0, effective_lock_until - now))
                    return {
                        "ok": False,
                        "stake_locked": True,
                        "locked_until": effective_lock_until,
                        "remaining_lock_seconds": rem_s,
                        "error": (
                            f"Staking Lock Active (H3 Anti-Flash-Stake Guard): Cannot unstake for {rem_s}s "
                            f"(locked until lottery/vault maturity period completes)."
                        ),
                    }

            rec.staked_amount -= amount
            if rec.staked_amount == 0:
                self._stakers.pop(worker.worker_id, None)
            else:
                rec.tier = "GOLD" if rec.staked_amount >= 150 else ("SILVER" if rec.staked_amount >= 50 else "BRONZE")

            # Refund back to worker active balance
            grant = self.hub.grant_credits(worker.worker_id, amount, reason="staking_vault_withdrawal")
            self._flush()

            block = self.ledger.append("credits_unstaked_vault", {
                "worker_id": worker.worker_id,
                "amount_unstaked": amount,
                "remaining_staked": rec.staked_amount if rec else 0,
            })

            return {
                "ok": True,
                "status": "UNSTAKED",
                "worker_id": worker.worker_id,
                "amount_unstaked": amount,
                "remaining_staked": rec.staked_amount if rec else 0,
                "active_credits": grant["new_balance"],
                "ledger_block": block["hash"][:16],
            }

    def get_staking_status(self, worker_id_or_key: str = "") -> dict:
        with self._lock:
            total_staked = sum(s.staked_amount for s in self._stakers.values())
            user_staked = 0
            user_tier = "NONE"
            if worker_id_or_key:
                wid = worker_id_or_key
                if hasattr(self.hub, "get_worker_by_key"):
                    w = self.hub.get_worker_by_key(worker_id_or_key)
                    if w:
                        wid = w.worker_id
                rec = self._stakers.get(wid)
                if rec:
                    user_staked = rec.staked_amount
                    user_tier = rec.tier

            return {
                "ok": True,
                "total_staked_in_vault": total_staked,
                "total_active_stakers": len(self._stakers),
                "user_staked": user_staked,
                "user_tier": user_tier,
            }
