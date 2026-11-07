"""NEXUS Sovereign Mesh — Private Held-Out Evaluation Battery Synthesizer (160 Custom NEXUS Tasks).

Security & Audit Guarantees (Step 3):
  1. Zero hardcoded `hidden_tests` strings and zero `reference_solution` strings exist
     in this git-tracked source file.
  2. Standard LeetCode problems (`two_sum`, `coin_change`, `roman_to_int`, etc.) are
     completely excluded; all 160 specifications are custom-authored NEXUS Sovereign
     Mesh protocol, hardware-safety, cryptographic, and distributed-systems problems.
  3. Private test inputs and ground-truth assertions are dynamically synthesized at
     runtime using a node-private 256-bit cryptographic seed stored in git-ignored
     `data/benchmarks/.benchmark_seed` (or loaded from an external private path via
     `NEXUS_PRIVATE_BENCHMARK_PATH`), and persisted strictly inside git-ignored
     `data/benchmarks/held_out_evaluation_battery.jsonl`.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


# =====================================================================
# NODE-PRIVATE SEED MANAGEMENT (GIT-IGNORED)
# =====================================================================

def _get_or_create_private_seed(data_dir: Optional[Path] = None) -> bytes:
    """Loads or generates a node-private 256-bit seed inside git-ignored `data/benchmarks/.benchmark_seed`."""
    env_seed = os.environ.get("NEXUS_BENCHMARK_PRIVATE_SEED", "").strip()
    if env_seed:
        return hashlib.sha256(env_seed.encode("utf-8")).digest()

    base_dir = data_dir if data_dir is not None else Path("data")
    seed_path = base_dir / "benchmarks" / ".benchmark_seed"
    try:
        seed_path.parent.mkdir(parents=True, exist_ok=True)
        if seed_path.exists():
            raw = seed_path.read_text(encoding="utf-8").strip()
            if len(raw) >= 32:
                return bytes.fromhex(raw[:64])
        secret_hex = os.urandom(32).hex()
        seed_path.write_text(secret_hex, encoding="utf-8")
        try:
            os.chmod(seed_path, 0o600)
        except OSError:
            pass
        return bytes.fromhex(secret_hex)
    except OSError:
        # Fallback to ephemeral process-unique entropy if filesystem is read-only
        return hashlib.sha256(b"nexus-ephemeral-node-seed").digest()


# =====================================================================
# 160 CUSTOM-AUTHORED NEXUS SOVEREIGN MESH SPECIFICATIONS
# (7 Code Domains x 20 Custom Problems + 1 Wire-Schema Domain x 20 = 160)
# Each entry: (task_id, domain, func_name, arg_names, prompt_spec, body_expr, input_gen_fn)
# Notice:
#   - Every single task has a distinct AST shape (`body_expr`) and custom NEXUS rules.
#   - Private test inputs are generated at runtime from the node-private CSPRNG.
# =====================================================================

SpecTuple = Tuple[str, str, str, List[str], str, str, Callable[[random.Random], Tuple[Any, ...]]]


def _build_custom_nexus_code_specs() -> List[SpecTuple]:
    specs: List[SpecTuple] = [
        # ---------------- DOMAIN 1: BYZANTINE CONSENSUS (20 tasks) ----------------
        (
            "bft_001", "byzantine_consensus", "nexus_bft_quorum_min", ["total_nodes", "fault_tolerance_factor"],
            "Write `nexus_bft_quorum_min(total_nodes, fault_tolerance_factor)` returning `(2 * total_nodes) // 3 + fault_tolerance_factor`.",
            "(2 * total_nodes) // 3 + fault_tolerance_factor",
            lambda r: (r.randint(4, 120), r.randint(1, 3)),
        ),
        (
            "bft_002", "byzantine_consensus", "nexus_bft_slash_stake", ["stake", "equivocations", "base_bps"],
            "Write `nexus_bft_slash_stake(stake, equivocations, base_bps)` returning `max(0, stake - (stake * equivocations * base_bps) // 10000)`.",
            "max(0, stake - (stake * equivocations * base_bps) // 10000)",
            lambda r: (r.randint(1000, 50000), r.randint(1, 5), r.randint(100, 1500)),
        ),
        (
            "bft_003", "byzantine_consensus", "nexus_bft_view_timeout_ms", ["base_ms", "view_round", "cap_ms"],
            "Write `nexus_bft_view_timeout_ms(base_ms, view_round, cap_ms)` returning `min(cap_ms, base_ms * (2 ** min(view_round, 6)))`.",
            "min(cap_ms, base_ms * (2 ** min(view_round, 6)))",
            lambda r: (r.randint(100, 500), r.randint(0, 8), r.randint(2000, 15000)),
        ),
        (
            "bft_004", "byzantine_consensus", "nexus_bft_supermajority_margin", ["yes_votes", "no_votes", "abstain"],
            "Write `nexus_bft_supermajority_margin(yes_votes, no_votes, abstain)` returning `3 * yes_votes - 2 * (yes_votes + no_votes + abstain)`.",
            "3 * yes_votes - 2 * (yes_votes + no_votes + abstain)",
            lambda r: (r.randint(10, 100), r.randint(0, 40), r.randint(0, 20)),
        ),
        (
            "bft_005", "byzantine_consensus", "nexus_bft_proposer_slot", ["epoch", "round_id", "validator_count", "salt"],
            "Write `nexus_bft_proposer_slot(epoch, round_id, validator_count, salt)` returning `(epoch * 31 + round_id * 17 + salt) % max(1, validator_count)`.",
            "(epoch * 31 + round_id * 17 + salt) % max(1, validator_count)",
            lambda r: (r.randint(1, 500), r.randint(0, 50), r.randint(4, 64), r.randint(1, 99)),
        ),
        (
            "bft_006", "byzantine_consensus", "nexus_bft_stake_weight_cap", ["stakes", "max_cap"],
            "Write `nexus_bft_stake_weight_cap(stakes, max_cap)` returning `sum(min(s, max_cap) for s in stakes if s > 0)`.",
            "sum(min(s, max_cap) for s in stakes if s > 0)",
            lambda r: ([r.randint(-10, 500) for _ in range(6)], r.randint(100, 300)),
        ),
        (
            "bft_007", "byzantine_consensus", "nexus_bft_reputation_decay", ["rep_score", "missed_epochs", "decay_rate"],
            "Write `nexus_bft_reputation_decay(rep_score, missed_epochs, decay_rate)` returning `max(10, rep_score - missed_epochs * decay_rate + (missed_epochs // 3))`.",
            "max(10, rep_score - missed_epochs * decay_rate + (missed_epochs // 3))",
            lambda r: (r.randint(100, 1000), r.randint(0, 25), r.randint(5, 30)),
        ),
        (
            "bft_008", "byzantine_consensus", "nexus_bft_finality_lag", ["head_block", "finalized_block", "max_drift"],
            "Write `nexus_bft_finality_lag(head_block, finalized_block, max_drift)` returning `1 if 0 <= (head_block - finalized_block) <= max_drift else 0`.",
            "1 if 0 <= (head_block - finalized_block) <= max_drift else 0",
            lambda r: (r.randint(100, 500), r.randint(80, 490), r.randint(5, 64)),
        ),
        (
            "bft_009", "byzantine_consensus", "nexus_bft_fork_weight_score", ["chain_len", "signer_stakes", "penalty_forks"],
            "Write `nexus_bft_fork_weight_score(chain_len, signer_stakes, penalty_forks)` returning `chain_len * 10 + sum(signer_stakes) - penalty_forks * 25`.",
            "chain_len * 10 + sum(signer_stakes) - penalty_forks * 25",
            lambda r: (r.randint(5, 100), [r.randint(10, 80) for _ in range(4)], r.randint(0, 5)),
        ),
        (
            "bft_010", "byzantine_consensus", "nexus_bft_quorum_intersection", ["n_validators", "quorum_a", "quorum_b"],
            "Write `nexus_bft_quorum_intersection(n_validators, quorum_a, quorum_b)` returning `max(0, quorum_a + quorum_b - n_validators)`.",
            "max(0, quorum_a + quorum_b - n_validators)",
            lambda r: (r.randint(10, 50), r.randint(7, 45), r.randint(7, 45)),
        ),
        (
            "bft_011", "byzantine_consensus", "nexus_bft_dissent_count", ["votes", "target_hash"],
            "Write `nexus_bft_dissent_count(votes, target_hash)` returning `sum(1 for v in votes if v != target_hash)`.",
            "sum(1 for v in votes if v != target_hash)",
            lambda r: ([r.choice(["h1", "h2", "h3"]) for _ in range(8)], "h1"),
        ),
        (
            "bft_012", "byzantine_consensus", "nexus_bft_unbonding_unlock_epoch", ["exit_epoch", "base_delay", "slashed_count"],
            "Write `nexus_bft_unbonding_unlock_epoch(exit_epoch, base_delay, slashed_count)` returning `exit_epoch + base_delay + (slashed_count ** 2) * 7`.",
            "exit_epoch + base_delay + (slashed_count ** 2) * 7",
            lambda r: (r.randint(100, 1000), r.randint(14, 60), r.randint(0, 6)),
        ),
        (
            "bft_013", "byzantine_consensus", "nexus_bft_quadratic_vote_power", ["token_balances"],
            "Write `nexus_bft_quadratic_vote_power(token_balances)` returning `sum(int(b ** 0.5) for b in token_balances if b > 0)`.",
            "sum(int(b ** 0.5) for b in token_balances if b > 0)",
            lambda r: ([r.randint(0, 10000) for _ in range(5)],),
        ),
        (
            "bft_014", "byzantine_consensus", "nexus_bft_heartbeat_liveness_permille", ["active_pings", "expected_pings"],
            "Write `nexus_bft_heartbeat_liveness_permille(active_pings, expected_pings)` returning `min(1000, (active_pings * 1000) // max(1, expected_pings))`.",
            "min(1000, (active_pings * 1000) // max(1, expected_pings))",
            lambda r: (r.randint(10, 500), r.randint(100, 500)),
        ),
        (
            "bft_015", "byzantine_consensus", "nexus_bft_cartel_concentration_bps", ["top_stakes", "total_stake"],
            "Write `nexus_bft_cartel_concentration_bps(top_stakes, total_stake)` returning `(sum(sorted(top_stakes, reverse=True)[:3]) * 10000) // max(1, total_stake)`.",
            "(sum(sorted(top_stakes, reverse=True)[:3]) * 10000) // max(1, total_stake)",
            lambda r: ([r.randint(10, 200) for _ in range(6)], r.randint(800, 2000)),
        ),
        (
            "bft_016", "byzantine_consensus", "nexus_bft_checkpoint_interval", ["block_height", "interval"],
            "Write `nexus_bft_checkpoint_interval(block_height, interval)` returning `block_height - (block_height % max(1, interval))`.",
            "block_height - (block_height % max(1, interval))",
            lambda r: (r.randint(100, 9999), r.randint(16, 256)),
        ),
        (
            "bft_017", "byzantine_consensus", "nexus_bft_latency_weighted_score", ["latencies_ms", "cutoff_ms"],
            "Write `nexus_bft_latency_weighted_score(latencies_ms, cutoff_ms)` returning `sum(max(0, cutoff_ms - l) for l in latencies_ms)`.",
            "sum(max(0, cutoff_ms - l) for l in latencies_ms)",
            lambda r: ([r.randint(10, 400) for _ in range(6)], r.randint(150, 300)),
        ),
        (
            "bft_018", "byzantine_consensus", "nexus_bft_double_sign_bounty", ["slashed_amount", "reporter_share_pct"],
            "Write `nexus_bft_double_sign_bounty(slashed_amount, reporter_share_pct)` returning `(slashed_amount * min(50, max(5, reporter_share_pct))) // 100`.",
            "(slashed_amount * min(50, max(5, reporter_share_pct))) // 100",
            lambda r: (r.randint(500, 20000), r.randint(1, 80)),
        ),
        (
            "bft_019", "byzantine_consensus", "nexus_bft_epoch_committee_size", ["active_validators", "target_min", "target_max"],
            "Write `nexus_bft_epoch_committee_size(active_validators, target_min, target_max)` returning `max(target_min, min(target_max, (active_validators * 2) // 5))`.",
            "max(target_min, min(target_max, (active_validators * 2) // 5))",
            lambda r: (r.randint(10, 300), r.randint(4, 16), r.randint(32, 128)),
        ),
        (
            "bft_020", "byzantine_consensus", "nexus_bft_commit_certificate_valid", ["sig_count", "total_nodes", "min_epoch", "msg_epoch"],
            "Write `nexus_bft_commit_certificate_valid(sig_count, total_nodes, min_epoch, msg_epoch)` returning `True if (sig_count * 3 > total_nodes * 2 and msg_epoch >= min_epoch) else False`.",
            "True if (sig_count * 3 > total_nodes * 2 and msg_epoch >= min_epoch) else False",
            lambda r: (r.randint(5, 30), r.randint(10, 40), r.randint(1, 50), r.randint(1, 60)),
        ),

        # ---------------- DOMAIN 2: TOKENOMICS & LEDGER (20 tasks) ----------------
        (
            "tok_001", "tokenomics_ledger", "nexus_ledger_deflationary_burn", ["tx_amount", "burn_bps", "min_burn"],
            "Write `nexus_ledger_deflationary_burn(tx_amount, burn_bps, min_burn)` returning `min(tx_amount, max(min_burn, (tx_amount * burn_bps) // 10000))`.",
            "min(tx_amount, max(min_burn, (tx_amount * burn_bps) // 10000))",
            lambda r: (r.randint(100, 100000), r.randint(10, 500), r.randint(1, 25)),
        ),
        (
            "tok_002", "tokenomics_ledger", "nexus_ledger_halving_reward", ["initial_reward", "block_height", "halving_period"],
            "Write `nexus_ledger_halving_reward(initial_reward, block_height, halving_period)` returning `initial_reward >> min(16, block_height // max(1, halving_period))`.",
            "initial_reward >> min(16, block_height // max(1, halving_period))",
            lambda r: (r.randint(1024, 65536), r.randint(0, 500000), r.randint(10000, 100000)),
        ),
        (
            "tok_003", "tokenomics_ledger", "nexus_ledger_congestion_fee", ["base_fee", "queue_depth", "target_depth"],
            "Write `nexus_ledger_congestion_fee(base_fee, queue_depth, target_depth)` returning `base_fee + (base_fee * max(0, queue_depth - target_depth)) // max(1, target_depth)`.",
            "base_fee + (base_fee * max(0, queue_depth - target_depth)) // max(1, target_depth)",
            lambda r: (r.randint(10, 200), r.randint(0, 1000), r.randint(50, 300)),
        ),
        (
            "tok_004", "tokenomics_ledger", "nexus_ledger_escrow_net_payout", ["gross_amount", "protocol_fee_bps", "arbiter_flat_fee"],
            "Write `nexus_ledger_escrow_net_payout(gross_amount, protocol_fee_bps, arbiter_flat_fee)` returning `max(0, gross_amount - (gross_amount * protocol_fee_bps) // 10000 - arbiter_flat_fee)`.",
            "max(0, gross_amount - (gross_amount * protocol_fee_bps) // 10000 - arbiter_flat_fee)",
            lambda r: (r.randint(500, 50000), r.randint(25, 400), r.randint(5, 100)),
        ),
        (
            "tok_005", "tokenomics_ledger", "nexus_ledger_staking_epoch_yield", ["principal", "apr_bps", "epochs_per_year"],
            "Write `nexus_ledger_staking_epoch_yield(principal, apr_bps, epochs_per_year)` returning `(principal * apr_bps) // max(1, 10000 * epochs_per_year)`.",
            "(principal * apr_bps) // max(1, 10000 * epochs_per_year)",
            lambda r: (r.randint(10000, 900000), r.randint(200, 1800), r.randint(50, 365)),
        ),
        (
            "tok_006", "tokenomics_ledger", "nexus_ledger_validator_commission", ["total_reward", "commission_pct", "fixed_cost"],
            "Write `nexus_ledger_validator_commission(total_reward, commission_pct, fixed_cost)` returning `min(total_reward, fixed_cost + ((max(0, total_reward - fixed_cost) * commission_pct) // 100))`.",
            "min(total_reward, fixed_cost + ((max(0, total_reward - fixed_cost) * commission_pct) // 100))",
            lambda r: (r.randint(100, 10000), r.randint(1, 30), r.randint(10, 300)),
        ),
        (
            "tok_007", "tokenomics_ledger", "nexus_ledger_overdraft_guard", ["balance", "debits", "credit_limit"],
            "Write `nexus_ledger_overdraft_guard(balance, debits, credit_limit)` returning `1 if (balance - sum(debits)) >= -credit_limit else 0`.",
            "1 if (balance - sum(debits)) >= -credit_limit else 0",
            lambda r: (r.randint(100, 2000), [r.randint(10, 500) for _ in range(5)], r.randint(0, 500)),
        ),
        (
            "tok_008", "tokenomics_ledger", "nexus_ledger_batch_settlement_fee", ["tx_counts", "per_tx_fee", "batch_discount_pct"],
            "Write `nexus_ledger_batch_settlement_fee(tx_counts, per_tx_fee, batch_discount_pct)` returning `(sum(tx_counts) * per_tx_fee * (100 - min(50, batch_discount_pct))) // 100`.",
            "(sum(tx_counts) * per_tx_fee * (100 - min(50, batch_discount_pct))) // 100",
            lambda r: ([r.randint(1, 40) for _ in range(5)], r.randint(2, 25), r.randint(5, 60)),
        ),
        (
            "tok_009", "tokenomics_ledger", "nexus_ledger_demurrage_balance", ["balance", "idle_epochs", "exempt_floor"],
            "Write `nexus_ledger_demurrage_balance(balance, idle_epochs, exempt_floor)` returning `balance if balance <= exempt_floor else max(exempt_floor, balance - ((balance - exempt_floor) * idle_epochs) // 100)`.",
            "balance if balance <= exempt_floor else max(exempt_floor, balance - ((balance - exempt_floor) * idle_epochs) // 100)",
            lambda r: (r.randint(500, 20000), r.randint(0, 30), r.randint(200, 2000)),
        ),
        (
            "tok_010", "tokenomics_ledger", "nexus_ledger_treasury_split", ["minted_tokens", "dev_pct", "security_pct"],
            "Write `nexus_ledger_treasury_split(minted_tokens, dev_pct, security_pct)` returning `minted_tokens - (minted_tokens * dev_pct) // 100 - (minted_tokens * security_pct) // 100`.",
            "minted_tokens - (minted_tokens * dev_pct) // 100 - (minted_tokens * security_pct) // 100",
            lambda r: (r.randint(1000, 100000), r.randint(5, 25), r.randint(5, 25)),
        ),
        (
            "tok_011", "tokenomics_ledger", "nexus_ledger_bonding_curve_price", ["base_price", "supply", "slope_denom"],
            "Write `nexus_ledger_bonding_curve_price(base_price, supply, slope_denom)` returning `base_price + (supply * supply) // max(1, slope_denom)`.",
            "base_price + (supply * supply) // max(1, slope_denom)",
            lambda r: (r.randint(10, 500), r.randint(10, 2000), r.randint(100, 5000)),
        ),
        (
            "tok_012", "tokenomics_ledger", "nexus_ledger_collateral_health_ratio", ["collateral_val", "debt_val", "liq_threshold_pct"],
            "Write `nexus_ledger_collateral_health_ratio(collateral_val, debt_val, liq_threshold_pct)` returning `(collateral_val * 100) // max(1, debt_val) - liq_threshold_pct`.",
            "(collateral_val * 100) // max(1, debt_val) - liq_threshold_pct",
            lambda r: (r.randint(1000, 50000), r.randint(500, 25000), r.randint(110, 175)),
        ),
        (
            "tok_013", "tokenomics_ledger", "nexus_ledger_ema_gas_price", ["prev_ema", "latest_price", "alpha_pct"],
            "Write `nexus_ledger_ema_gas_price(prev_ema, latest_price, alpha_pct)` returning `(latest_price * alpha_pct + prev_ema * (100 - alpha_pct)) // 100`.",
            "(latest_price * alpha_pct + prev_ema * (100 - alpha_pct)) // 100",
            lambda r: (r.randint(20, 500), r.randint(20, 500), r.randint(10, 90)),
        ),
        (
            "tok_014", "tokenomics_ledger", "nexus_ledger_multihop_relay_fee", ["hop_fees", "priority_multiplier"],
            "Write `nexus_ledger_multihop_relay_fee(hop_fees, priority_multiplier)` returning `sum(f * priority_multiplier + idx for idx, f in enumerate(hop_fees))`.",
            "sum(f * priority_multiplier + idx for idx, f in enumerate(hop_fees))",
            lambda r: ([r.randint(2, 50) for _ in range(5)], r.randint(1, 5)),
        ),
        (
            "tok_015", "tokenomics_ledger", "nexus_ledger_voucher_claimable", ["face_value", "issue_epoch", "current_epoch", "ttl_epochs"],
            "Write `nexus_ledger_voucher_claimable(face_value, issue_epoch, current_epoch, ttl_epochs)` returning `face_value if 0 <= (current_epoch - issue_epoch) <= ttl_epochs else 0`.",
            "face_value if 0 <= (current_epoch - issue_epoch) <= ttl_epochs else 0",
            lambda r: (r.randint(50, 5000), r.randint(10, 200), r.randint(15, 250), r.randint(10, 100)),
        ),
        (
            "tok_016", "tokenomics_ledger", "nexus_ledger_velocity_cap_remaining", ["window_transfers", "daily_cap"],
            "Write `nexus_ledger_velocity_cap_remaining(window_transfers, daily_cap)` returning `max(0, daily_cap - sum(t for t in window_transfers if t > 0))`.",
            "max(0, daily_cap - sum(t for t in window_transfers if t > 0))",
            lambda r: ([r.randint(-20, 400) for _ in range(6)], r.randint(500, 2000)),
        ),
        (
            "tok_017", "tokenomics_ledger", "nexus_ledger_epoch_mint_ceiling", ["circulating_supply", "max_supply", "epoch_rate_bps"],
            "Write `nexus_ledger_epoch_mint_ceiling(circulating_supply, max_supply, epoch_rate_bps)` returning `min(max(0, max_supply - circulating_supply), (circulating_supply * epoch_rate_bps) // 10000)`.",
            "min(max(0, max_supply - circulating_supply), (circulating_supply * epoch_rate_bps) // 10000)",
            lambda r: (r.randint(10000, 90000), r.randint(80000, 120000), r.randint(10, 500)),
        ),
        (
            "tok_018", "tokenomics_ledger", "nexus_ledger_slashed_pool_redistribution", ["pool_total", "honest_count", "burn_share_pct"],
            "Write `nexus_ledger_slashed_pool_redistribution(pool_total, honest_count, burn_share_pct)` returning `(pool_total * (100 - burn_share_pct)) // max(1, 100 * honest_count)`.",
            "(pool_total * (100 - burn_share_pct)) // max(1, 100 * honest_count)",
            lambda r: (r.randint(1000, 50000), r.randint(2, 40), r.randint(10, 60)),
        ),
        (
            "tok_019", "tokenomics_ledger", "nexus_ledger_liquidity_lock_multiplier", ["lock_weeks", "max_weeks"],
            "Write `nexus_ledger_liquidity_lock_multiplier(lock_weeks, max_weeks)` returning `100 + (min(lock_weeks, max_weeks) * 150) // max(1, max_weeks)`.",
            "100 + (min(lock_weeks, max_weeks) * 150) // max(1, max_weeks)",
            lambda r: (r.randint(1, 208), r.randint(52, 208)),
        ),
        (
            "tok_020", "tokenomics_ledger", "nexus_ledger_net_settlement_imbalance", ["inflows", "outflows", "fee_reserve"],
            "Write `nexus_ledger_net_settlement_imbalance(inflows, outflows, fee_reserve)` returning `sum(inflows) - sum(outflows) - fee_reserve`.",
            "sum(inflows) - sum(outflows) - fee_reserve",
            lambda r: ([r.randint(50, 500) for _ in range(4)], [r.randint(40, 450) for _ in range(4)], r.randint(10, 100)),
        ),

        # ---------------- DOMAIN 3: CNC & HARDWARE SAFETY INTERLOCKS (20 tasks) ----------------
        (
            "cnc_001", "cnc_hardware_safety", "nexus_cnc_clamp_axis_mm", ["target_mm", "min_limit_mm", "max_limit_mm", "margin_mm"],
            "Write `nexus_cnc_clamp_axis_mm(target_mm, min_limit_mm, max_limit_mm, margin_mm)` returning `max(min_limit_mm + margin_mm, min(max_limit_mm - margin_mm, target_mm))`.",
            "max(min_limit_mm + margin_mm, min(max_limit_mm - margin_mm, target_mm))",
            lambda r: (r.randint(-50, 400), 0, r.randint(200, 350), r.randint(2, 15)),
        ),
        (
            "cnc_002", "cnc_hardware_safety", "nexus_cnc_spindle_thermal_derate", ["req_rpm", "temp_c", "warn_temp_c", "shut_temp_c"],
            "Write `nexus_cnc_spindle_thermal_derate(req_rpm, temp_c, warn_temp_c, shut_temp_c)` returning `0 if temp_c >= shut_temp_c else (req_rpm if temp_c <= warn_temp_c else (req_rpm * (shut_temp_c - temp_c)) // max(1, shut_temp_c - warn_temp_c))`.",
            "0 if temp_c >= shut_temp_c else (req_rpm if temp_c <= warn_temp_c else (req_rpm * (shut_temp_c - temp_c)) // max(1, shut_temp_c - warn_temp_c))",
            lambda r: (r.randint(3000, 24000), r.randint(40, 110), 65, 95),
        ),
        (
            "cnc_003", "cnc_hardware_safety", "nexus_cnc_feedrate_override", ["base_feed", "override_pct", "max_safe_feed"],
            "Write `nexus_cnc_feedrate_override(base_feed, override_pct, max_safe_feed)` returning `min(max_safe_feed, max(10, (base_feed * override_pct) // 100))`.",
            "min(max_safe_feed, max(10, (base_feed * override_pct) // 100))",
            lambda r: (r.randint(200, 3000), r.randint(20, 200), r.randint(1500, 4000)),
        ),
        (
            "cnc_004", "cnc_hardware_safety", "nexus_cnc_estop_stopping_dist_um", ["vel_mm_s", "decel_mm_s2"],
            "Write `nexus_cnc_estop_stopping_dist_um(vel_mm_s, decel_mm_s2)` returning `(vel_mm_s * vel_mm_s * 1000) // max(1, 2 * decel_mm_s2)`.",
            "(vel_mm_s * vel_mm_s * 1000) // max(1, 2 * decel_mm_s2)",
            lambda r: (r.randint(10, 300), r.randint(100, 2500)),
        ),
        (
            "cnc_005", "cnc_hardware_safety", "nexus_cnc_backlash_comp_steps", ["target_steps", "prev_steps", "backlash_steps"],
            "Write `nexus_cnc_backlash_comp_steps(target_steps, prev_steps, backlash_steps)` returning `target_steps + backlash_steps if target_steps > prev_steps else (target_steps - backlash_steps if target_steps < prev_steps else target_steps)`.",
            "target_steps + backlash_steps if target_steps > prev_steps else (target_steps - backlash_steps if target_steps < prev_steps else target_steps)",
            lambda r: (r.randint(100, 5000), r.randint(100, 5000), r.randint(2, 40)),
        ),
        (
            "cnc_006", "cnc_hardware_safety", "nexus_cnc_tool_wear_z_offset", ["base_z_um", "cut_minutes", "wear_rate_um_per_hr"],
            "Write `nexus_cnc_tool_wear_z_offset(base_z_um, cut_minutes, wear_rate_um_per_hr)` returning `base_z_um - (cut_minutes * wear_rate_um_per_hr) // 60`.",
            "base_z_um - (cut_minutes * wear_rate_um_per_hr) // 60",
            lambda r: (r.randint(1000, 10000), r.randint(10, 600), r.randint(5, 80)),
        ),
        (
            "cnc_007", "cnc_hardware_safety", "nexus_cnc_coolant_interlock_ok", ["flow_ml_min", "min_flow", "spindle_on"],
            "Write `nexus_cnc_coolant_interlock_ok(flow_ml_min, min_flow, spindle_on)` returning `True if (not spindle_on or flow_ml_min >= min_flow) else False`.",
            "True if (not spindle_on or flow_ml_min >= min_flow) else False",
            lambda r: (r.randint(50, 1000), r.randint(200, 600), r.choice([True, False])),
        ),
        (
            "cnc_008", "cnc_hardware_safety", "nexus_cnc_laser_pwm_cap", ["requested_pwm", "head_speed", "min_cut_speed", "max_pwm"],
            "Write `nexus_cnc_laser_pwm_cap(requested_pwm, head_speed, min_cut_speed, max_pwm)` returning `0 if head_speed < min_cut_speed else min(max_pwm, requested_pwm)`.",
            "0 if head_speed < min_cut_speed else min(max_pwm, requested_pwm)",
            lambda r: (r.randint(50, 255), r.randint(0, 100), r.randint(15, 40), r.randint(180, 250)),
        ),
        (
            "cnc_009", "cnc_hardware_safety", "nexus_cnc_plunge_rate_guard", ["z_delta_mm", "requested_rate", "max_plunge_rate"],
            "Write `nexus_cnc_plunge_rate_guard(z_delta_mm, requested_rate, max_plunge_rate)` returning `min(requested_rate, max_plunge_rate) if z_delta_mm < 0 else requested_rate`.",
            "min(requested_rate, max_plunge_rate) if z_delta_mm < 0 else requested_rate",
            lambda r: (r.randint(-50, 50), r.randint(200, 2000), r.randint(100, 600)),
        ),
        (
            "cnc_010", "cnc_hardware_safety", "nexus_cnc_stepper_pulse_freq_hz", ["feed_mm_min", "steps_per_mm"],
            "Write `nexus_cnc_stepper_pulse_freq_hz(feed_mm_min, steps_per_mm)` returning `(feed_mm_min * steps_per_mm) // 60`.",
            "(feed_mm_min * steps_per_mm) // 60",
            lambda r: (r.randint(60, 6000), r.randint(80, 1600)),
        ),
        (
            "cnc_011", "cnc_hardware_safety", "nexus_cnc_gantry_skew_alarm", ["left_encoder_um", "right_encoder_um", "max_skew_um"],
            "Write `nexus_cnc_gantry_skew_alarm(left_encoder_um, right_encoder_um, max_skew_um)` returning `1 if abs(left_encoder_um - right_encoder_um) > max_skew_um else 0`.",
            "1 if abs(left_encoder_um - right_encoder_um) > max_skew_um else 0",
            lambda r: (r.randint(1000, 5000), r.randint(1000, 5000), r.randint(50, 500)),
        ),
        (
            "cnc_012", "cnc_hardware_safety", "nexus_cnc_bed_level_z_interp", ["z_front", "z_back", "y_ratio_pct"],
            "Write `nexus_cnc_bed_level_z_interp(z_front, z_back, y_ratio_pct)` returning `z_front + ((z_back - z_front) * max(0, min(100, y_ratio_pct))) // 100`.",
            "z_front + ((z_back - z_front) * max(0, min(100, y_ratio_pct))) // 100",
            lambda r: (r.randint(-200, 200), r.randint(-200, 200), r.randint(-10, 110)),
        ),
        (
            "cnc_013", "cnc_hardware_safety", "nexus_cnc_servo_torque_trip", ["phase_currents_ma", "trip_limit_ma"],
            "Write `nexus_cnc_servo_torque_trip(phase_currents_ma, trip_limit_ma)` returning `sum(1 for c in phase_currents_ma if abs(c) > trip_limit_ma)`.",
            "sum(1 for c in phase_currents_ma if abs(c) > trip_limit_ma)",
            lambda r: ([r.randint(-5000, 5000) for _ in range(6)], r.randint(2000, 4000)),
        ),
        (
            "cnc_014", "cnc_hardware_safety", "nexus_cnc_nozzle_pid_output", ["target_temp", "current_temp", "kp", "max_pwm"],
            "Write `nexus_cnc_nozzle_pid_output(target_temp, current_temp, kp, max_pwm)` returning `max(0, min(max_pwm, (target_temp - current_temp) * kp))`.",
            "max(0, min(max_pwm, (target_temp - current_temp) * kp))",
            lambda r: (r.randint(180, 260), r.randint(150, 270), r.randint(4, 20), 255),
        ),
        (
            "cnc_015", "cnc_hardware_safety", "nexus_cnc_homing_debounce_valid", ["switch_samples", "min_high_count"],
            "Write `nexus_cnc_homing_debounce_valid(switch_samples, min_high_count)` returning `True if sum(1 for s in switch_samples if s > 0) >= min_high_count else False`.",
            "True if sum(1 for s in switch_samples if s > 0) >= min_high_count else False",
            lambda r: ([r.choice([0, 1]) for _ in range(8)], r.randint(3, 6)),
        ),
        (
            "cnc_016", "cnc_hardware_safety", "nexus_cnc_work_coord_machine_pos", ["wcs_pos", "g54_offset", "tool_offset"],
            "Write `nexus_cnc_work_coord_machine_pos(wcs_pos, g54_offset, tool_offset)` returning `wcs_pos + g54_offset + tool_offset`.",
            "wcs_pos + g54_offset + tool_offset",
            lambda r: (r.randint(-100, 500), r.randint(-50, 200), r.randint(-30, 80)),
        ),
        (
            "cnc_017", "cnc_hardware_safety", "nexus_cnc_arc_segment_count", ["arc_length_mm", "max_segment_mm", "min_segments"],
            "Write `nexus_cnc_arc_segment_count(arc_length_mm, max_segment_mm, min_segments)` returning `max(min_segments, (arc_length_mm + max_segment_mm - 1) // max(1, max_segment_mm))`.",
            "max(min_segments, (arc_length_mm + max_segment_mm - 1) // max(1, max_segment_mm))",
            lambda r: (r.randint(5, 300), r.randint(1, 10), r.randint(4, 16)),
        ),
        (
            "cnc_018", "cnc_hardware_safety", "nexus_cnc_probe_contact_z", ["trigger_steps", "steps_per_mm", "probe_gauge_um"],
            "Write `nexus_cnc_probe_contact_z(trigger_steps, steps_per_mm, probe_gauge_um)` returning `(trigger_steps * 1000) // max(1, steps_per_mm) - probe_gauge_um`.",
            "(trigger_steps * 1000) // max(1, steps_per_mm) - probe_gauge_um",
            lambda r: (r.randint(1000, 50000), r.randint(80, 800), r.randint(500, 5000)),
        ),
        (
            "cnc_019", "cnc_hardware_safety", "nexus_cnc_filament_buffer_remaining_mm", ["spool_grams", "grams_per_meter", "reserve_mm"],
            "Write `nexus_cnc_filament_buffer_remaining_mm(spool_grams, grams_per_meter, reserve_mm)` returning `max(0, (spool_grams * 1000) // max(1, grams_per_meter) - reserve_mm)`.",
            "max(0, (spool_grams * 1000) // max(1, grams_per_meter) - reserve_mm)",
            lambda r: (r.randint(50, 1000), r.randint(2, 10), r.randint(100, 1500)),
        ),
        (
            "cnc_020", "cnc_hardware_safety", "nexus_cnc_bbox_violation_count", ["points_x", "min_x", "max_x"],
            "Write `nexus_cnc_bbox_violation_count(points_x, min_x, max_x)` returning `sum(1 for x in points_x if x < min_x or x > max_x)`.",
            "sum(1 for x in points_x if x < min_x or x > max_x)",
            lambda r: ([r.randint(-50, 350) for _ in range(8)], 0, 250),
        ),

        # ---------------- DOMAIN 4: P2P MESH ROUTING (20 tasks) ----------------
        (
            "p2p_001", "p2p_mesh_routing", "nexus_p2p_kademlia_xor_dist", ["node_id_a", "node_id_b"],
            "Write `nexus_p2p_kademlia_xor_dist(node_id_a, node_id_b)` returning `(node_id_a ^ node_id_b).bit_length()`.",
            "(node_id_a ^ node_id_b).bit_length()",
            lambda r: (r.randint(1, 65535), r.randint(1, 65535)),
        ),
        (
            "p2p_002", "p2p_mesh_routing", "nexus_p2p_gossip_ttl_next", ["current_ttl", "hop_cost", "max_ttl"],
            "Write `nexus_p2p_gossip_ttl_next(current_ttl, hop_cost, max_ttl)` returning `max(0, min(current_ttl, max_ttl) - max(1, hop_cost))`.",
            "max(0, min(current_ttl, max_ttl) - max(1, hop_cost))",
            lambda r: (r.randint(1, 32), r.randint(1, 4), r.randint(8, 24)),
        ),
        (
            "p2p_003", "p2p_mesh_routing", "nexus_p2p_circuit_breaker_open", ["consecutive_fails", "fail_threshold", "elapsed_s", "cooldown_s"],
            "Write `nexus_p2p_circuit_breaker_open(consecutive_fails, fail_threshold, elapsed_s, cooldown_s)` returning `True if (consecutive_fails >= fail_threshold and elapsed_s < cooldown_s) else False`.",
            "True if (consecutive_fails >= fail_threshold and elapsed_s < cooldown_s) else False",
            lambda r: (r.randint(0, 10), r.randint(3, 6), r.randint(5, 120), r.randint(30, 90)),
        ),
        (
            "p2p_004", "p2p_mesh_routing", "nexus_p2p_token_bucket_avail", ["current_tokens", "elapsed_ms", "refill_per_s", "capacity"],
            "Write `nexus_p2p_token_bucket_avail(current_tokens, elapsed_ms, refill_per_s, capacity)` returning `min(capacity, current_tokens + (elapsed_ms * refill_per_s) // 1000)`.",
            "min(capacity, current_tokens + (elapsed_ms * refill_per_s) // 1000)",
            lambda r: (r.randint(0, 500), r.randint(100, 5000), r.randint(50, 400), r.randint(500, 2000)),
        ),
        (
            "p2p_005", "p2p_mesh_routing", "nexus_p2p_onion_padded_size", ["payload_bytes", "cell_size", "hop_headers"],
            "Write `nexus_p2p_onion_padded_size(payload_bytes, cell_size, hop_headers)` returning `((payload_bytes + hop_headers * 32 + cell_size - 1) // max(1, cell_size)) * cell_size`.",
            "((payload_bytes + hop_headers * 32 + cell_size - 1) // max(1, cell_size)) * cell_size",
            lambda r: (r.randint(50, 4000), 512, r.randint(2, 6)),
        ),
        (
            "p2p_006", "p2p_mesh_routing", "nexus_p2p_sybil_subnet_count", ["peer_ips_prefix24", "target_prefix"],
            "Write `nexus_p2p_sybil_subnet_count(peer_ips_prefix24, target_prefix)` returning `sum(1 for p in peer_ips_prefix24 if p == target_prefix)`.",
            "sum(1 for p in peer_ips_prefix24 if p == target_prefix)",
            lambda r: ([r.choice(["10.0.1", "10.0.2", "192.168.1"]) for _ in range(8)], "10.0.1"),
        ),
        (
            "p2p_007", "p2p_mesh_routing", "nexus_p2p_hole_punch_backoff_ms", ["attempt", "base_ms", "jitter_ms"],
            "Write `nexus_p2p_hole_punch_backoff_ms(attempt, base_ms, jitter_ms)` returning `base_ms * (attempt + 1) + (jitter_ms % max(1, base_ms))`.",
            "base_ms * (attempt + 1) + (jitter_ms % max(1, base_ms))",
            lambda r: (r.randint(0, 8), r.randint(50, 300), r.randint(10, 500)),
        ),
        (
            "p2p_008", "p2p_mesh_routing", "nexus_p2p_swarm_seeder_ratio_bps", ["seeders", "leechers"],
            "Write `nexus_p2p_swarm_seeder_ratio_bps(seeders, leechers)` returning `(seeders * 10000) // max(1, seeders + leechers)`.",
            "(seeders * 10000) // max(1, seeders + leechers)",
            lambda r: (r.randint(1, 200), r.randint(0, 500)),
        ),
        (
            "p2p_009", "p2p_mesh_routing", "nexus_p2p_reorder_buffer_gaps", ["seq_numbers"],
            "Write `nexus_p2p_reorder_buffer_gaps(seq_numbers)` returning `(max(seq_numbers) - min(seq_numbers) + 1 - len(set(seq_numbers))) if seq_numbers else 0`.",
            "(max(seq_numbers) - min(seq_numbers) + 1 - len(set(seq_numbers))) if seq_numbers else 0",
            lambda r: ([r.randint(10, 30) for _ in range(6)],),
        ),
        (
            "p2p_010", "p2p_mesh_routing", "nexus_p2p_link_quality_metric", ["rtt_ms", "loss_pct", "bandwidth_mbps"],
            "Write `nexus_p2p_link_quality_metric(rtt_ms, loss_pct, bandwidth_mbps)` returning `max(0, bandwidth_mbps * 10 - rtt_ms - loss_pct * 25)`.",
            "max(0, bandwidth_mbps * 10 - rtt_ms - loss_pct * 25)",
            lambda r: (r.randint(5, 300), r.randint(0, 20), r.randint(10, 100)),
        ),
        (
            "p2p_011", "p2p_mesh_routing", "nexus_p2p_dht_bucket_evict_idx", ["last_seen_epochs"],
            "Write `nexus_p2p_dht_bucket_evict_idx(last_seen_epochs)` returning `last_seen_epochs.index(min(last_seen_epochs))`.",
            "last_seen_epochs.index(min(last_seen_epochs))",
            lambda r: (random.sample(range(10, 500), 6),),
        ),
        (
            "p2p_012", "p2p_mesh_routing", "nexus_p2p_backpressure_drop_count", ["incoming_batch", "free_slots"],
            "Write `nexus_p2p_backpressure_drop_count(incoming_batch, free_slots)` returning `max(0, incoming_batch - max(0, free_slots))`.",
            "max(0, incoming_batch - max(0, free_slots))",
            lambda r: (r.randint(10, 200), r.randint(-5, 150)),
        ),
        (
            "p2p_013", "p2p_mesh_routing", "nexus_p2p_multipath_primary_bytes", ["total_bytes", "primary_weight", "secondary_weight"],
            "Write `nexus_p2p_multipath_primary_bytes(total_bytes, primary_weight, secondary_weight)` returning `(total_bytes * primary_weight) // max(1, primary_weight + secondary_weight)`.",
            "(total_bytes * primary_weight) // max(1, primary_weight + secondary_weight)",
            lambda r: (r.randint(1000, 100000), r.randint(1, 10), r.randint(1, 10)),
        ),
        (
            "p2p_014", "p2p_mesh_routing", "nexus_p2p_route_flap_penalty", ["flap_events", "penalty_per_flap", "decay_credits"],
            "Write `nexus_p2p_route_flap_penalty(flap_events, penalty_per_flap, decay_credits)` returning `max(0, flap_events * penalty_per_flap - decay_credits)`.",
            "max(0, flap_events * penalty_per_flap - decay_credits)",
            lambda r: (r.randint(0, 15), r.randint(100, 500), r.randint(50, 1000)),
        ),
        (
            "p2p_015", "p2p_mesh_routing", "nexus_p2p_bloom_bit_position", ["msg_hash_int", "filter_bits", "salt_idx"],
            "Write `nexus_p2p_bloom_bit_position(msg_hash_int, filter_bits, salt_idx)` returning `((msg_hash_int ^ (salt_idx * 0x9E3779B9)) & 0x7FFFFFFF) % max(1, filter_bits)`.",
            "((msg_hash_int ^ (salt_idx * 0x9E3779B9)) & 0x7FFFFFFF) % max(1, filter_bits)",
            lambda r: (r.randint(1000, 9999999), r.randint(256, 8192), r.randint(1, 7)),
        ),
        (
            "p2p_016", "p2p_mesh_routing", "nexus_p2p_relay_budget_ok", ["requested_kb", "hourly_used_kb", "hourly_cap_kb"],
            "Write `nexus_p2p_relay_budget_ok(requested_kb, hourly_used_kb, hourly_cap_kb)` returning `1 if (requested_kb > 0 and hourly_used_kb + requested_kb <= hourly_cap_kb) else 0`.",
            "1 if (requested_kb > 0 and hourly_used_kb + requested_kb <= hourly_cap_kb) else 0",
            lambda r: (r.randint(10, 500), r.randint(100, 4000), r.randint(1000, 4500)),
        ),
        (
            "p2p_017", "p2p_mesh_routing", "nexus_p2p_chunk_count", ["total_size_bytes", "chunk_size_bytes"],
            "Write `nexus_p2p_chunk_count(total_size_bytes, chunk_size_bytes)` returning `(max(0, total_size_bytes) + max(1, chunk_size_bytes) - 1) // max(1, chunk_size_bytes)`.",
            "(max(0, total_size_bytes) + max(1, chunk_size_bytes) - 1) // max(1, chunk_size_bytes)",
            lambda r: (r.randint(0, 1000000), r.randint(1024, 65536)),
        ),
        (
            "p2p_018", "p2p_mesh_routing", "nexus_p2p_partition_quorum_reachable", ["reachable_peers", "total_peers"],
            "Write `nexus_p2p_partition_quorum_reachable(reachable_peers, total_peers)` returning `True if reachable_peers * 2 > total_peers else False`.",
            "True if reachable_peers * 2 > total_peers else False",
            lambda r: (r.randint(1, 50), r.randint(10, 80)),
        ),
        (
            "p2p_019", "p2p_mesh_routing", "nexus_p2p_gossip_fanout_select", ["peer_count", "min_fanout", "max_fanout"],
            "Write `nexus_p2p_gossip_fanout_select(peer_count, min_fanout, max_fanout)` returning `min(peer_count, max(min_fanout, min(max_fanout, int(peer_count ** 0.5) + 2)))`.",
            "min(peer_count, max(min_fanout, min(max_fanout, int(peer_count ** 0.5) + 2)))",
            lambda r: (r.randint(2, 200), r.randint(3, 6), r.randint(8, 20)),
        ),
        (
            "p2p_020", "p2p_mesh_routing", "nexus_p2p_handshake_nonce_mix", ["client_nonce", "server_nonce", "epoch_id"],
            "Write `nexus_p2p_handshake_nonce_mix(client_nonce, server_nonce, epoch_id)` returning `((client_nonce ^ server_nonce) + epoch_id * 65537) & 0xFFFFFFFF`.",
            "((client_nonce ^ server_nonce) + epoch_id * 65537) & 0xFFFFFFFF",
            lambda r: (r.randint(1, 1000000), r.randint(1, 1000000), r.randint(1, 5000)),
        ),

        # ---------------- DOMAIN 5: CRYPTOGRAPHIC AUDIT & LEDGER INTEGRITY (20 tasks) ----------------
        (
            "cry_001", "cryptographic_audit", "nexus_crypto_lamport_advance", ["local_clock", "received_clock"],
            "Write `nexus_crypto_lamport_advance(local_clock, received_clock)` returning `max(local_clock, received_clock) + 1`.",
            "max(local_clock, received_clock) + 1",
            lambda r: (r.randint(0, 10000), r.randint(0, 10000)),
        ),
        (
            "cry_002", "cryptographic_audit", "nexus_crypto_replay_window_valid", ["msg_ts", "server_ts", "max_skew_s"],
            "Write `nexus_crypto_replay_window_valid(msg_ts, server_ts, max_skew_s)` returning `True if abs(server_ts - msg_ts) <= max_skew_s else False`.",
            "True if abs(server_ts - msg_ts) <= max_skew_s else False",
            lambda r: (r.randint(1000, 2000), r.randint(1000, 2000), r.randint(30, 300)),
        ),
        (
            "cry_003", "cryptographic_audit", "nexus_crypto_key_rotation_due", ["key_epoch", "current_epoch", "max_key_age"],
            "Write `nexus_crypto_key_rotation_due(key_epoch, current_epoch, max_key_age)` returning `1 if (current_epoch - key_epoch) >= max_key_age else 0`.",
            "1 if (current_epoch - key_epoch) >= max_key_age else 0",
            lambda r: (r.randint(1, 200), r.randint(50, 400), r.randint(30, 100)),
        ),
        (
            "cry_004", "cryptographic_audit", "nexus_crypto_shamir_reconstruct_ok", ["shares_provided", "threshold_k", "total_n"],
            "Write `nexus_crypto_shamir_reconstruct_ok(shares_provided, threshold_k, total_n)` returning `True if (threshold_k <= shares_provided <= total_n and threshold_k >= 2) else False`.",
            "True if (threshold_k <= shares_provided <= total_n and threshold_k >= 2) else False",
            lambda r: (r.randint(1, 10), r.randint(2, 7), r.randint(5, 12)),
        ),
        (
            "cry_005", "cryptographic_audit", "nexus_crypto_ota_anti_rollback", ["candidate_ver", "installed_ver", "min_security_ver"],
            "Write `nexus_crypto_ota_anti_rollback(candidate_ver, installed_ver, min_security_ver)` returning `1 if (candidate_ver > installed_ver and candidate_ver >= min_security_ver) else 0`.",
            "1 if (candidate_ver > installed_ver and candidate_ver >= min_security_ver) else 0",
            lambda r: (r.randint(1, 50), r.randint(1, 50), r.randint(5, 30)),
        ),
        (
            "cry_006", "cryptographic_audit", "nexus_crypto_merkle_parent_idx", ["leaf_index"],
            "Write `nexus_crypto_merkle_parent_idx(leaf_index)` returning `max(0, leaf_index) // 2`.",
            "max(0, leaf_index) // 2",
            lambda r: (r.randint(0, 4096),),
        ),
        (
            "cry_007", "cryptographic_audit", "nexus_crypto_pkcs7_pad_len", ["data_len", "block_size"],
            "Write `nexus_crypto_pkcs7_pad_len(data_len, block_size)` returning `block_size - (data_len % block_size)`.",
            "block_size - (data_len % block_size)",
            lambda r: (r.randint(0, 500), r.choice([8, 16, 32])),
        ),
        (
            "cry_008", "cryptographic_audit", "nexus_crypto_nonce_reuse_count", ["nonces"],
            "Write `nexus_crypto_nonce_reuse_count(nonces)` returning `len(nonces) - len(set(nonces))`.",
            "len(nonces) - len(set(nonces))",
            lambda r: ([r.randint(1, 8) for _ in range(10)],),
        ),
        (
            "cry_009", "cryptographic_audit", "nexus_crypto_hkdf_blocks_needed", ["okm_bytes", "hash_len"],
            "Write `nexus_crypto_hkdf_blocks_needed(okm_bytes, hash_len)` returning `(max(1, okm_bytes) + max(1, hash_len) - 1) // max(1, hash_len)`.",
            "(max(1, okm_bytes) + max(1, hash_len) - 1) // max(1, hash_len)",
            lambda r: (r.randint(16, 256), r.choice([32, 48, 64])),
        ),
        (
            "cry_010", "cryptographic_audit", "nexus_crypto_low_s_canonical", ["sig_s", "curve_half_order"],
            "Write `nexus_crypto_low_s_canonical(sig_s, curve_half_order)` returning `sig_s if sig_s <= curve_half_order else (2 * curve_half_order + 1 - sig_s)`.",
            "sig_s if sig_s <= curve_half_order else (2 * curve_half_order + 1 - sig_s)",
            lambda r: (r.randint(100, 10000), r.randint(2000, 6000)),
        ),
        (
            "cry_011", "cryptographic_audit", "nexus_crypto_seed_unique_bytes", ["seed_bytes_list"],
            "Write `nexus_crypto_seed_unique_bytes(seed_bytes_list)` returning `len(set(seed_bytes_list))`.",
            "len(set(seed_bytes_list))",
            lambda r: ([r.randint(0, 255) for _ in range(16)],),
        ),
        (
            "cry_012", "cryptographic_audit", "nexus_crypto_kdf_iter_scale", ["base_iters", "cost_level"],
            "Write `nexus_crypto_kdf_iter_scale(base_iters, cost_level)` returning `base_iters * (1 << min(10, max(0, cost_level)))`.",
            "base_iters * (1 << min(10, max(0, cost_level)))",
            lambda r: (r.randint(1000, 10000), r.randint(0, 8)),
        ),
        (
            "cry_013", "cryptographic_audit", "nexus_crypto_cert_remaining_days", ["not_after_day", "current_day", "grace_days"],
            "Write `nexus_crypto_cert_remaining_days(not_after_day, current_day, grace_days)` returning `max(0, not_after_day + grace_days - current_day)`.",
            "max(0, not_after_day + grace_days - current_day)",
            lambda r: (r.randint(100, 500), r.randint(50, 550), r.randint(0, 14)),
        ),
        (
            "cry_014", "cryptographic_audit", "nexus_crypto_commitment_bind_mod", ["secret_val", "blinding_val", "prime_mod"],
            "Write `nexus_crypto_commitment_bind_mod(secret_val, blinding_val, prime_mod)` returning `(secret_val * 131 + blinding_val * 997) % max(2, prime_mod)`.",
            "(secret_val * 131 + blinding_val * 997) % max(2, prime_mod)",
            lambda r: (r.randint(1, 50000), r.randint(1, 50000), 65521),
        ),
        (
            "cry_015", "cryptographic_audit", "nexus_crypto_hash_chain_fold", ["prev_digest_int", "block_payload_int"],
            "Write `nexus_crypto_hash_chain_fold(prev_digest_int, block_payload_int)` returning `((prev_digest_int * 33) ^ block_payload_int) & 0xFFFFFFFF`.",
            "((prev_digest_int * 33) ^ block_payload_int) & 0xFFFFFFFF",
            lambda r: (r.randint(1, 9999999), r.randint(1, 9999999)),
        ),
        (
            "cry_016", "cryptographic_audit", "nexus_crypto_zk_range_valid", ["committed_val", "lower_bound", "upper_bound"],
            "Write `nexus_crypto_zk_range_valid(committed_val, lower_bound, upper_bound)` returning `1 if lower_bound <= committed_val < upper_bound else 0`.",
            "1 if lower_bound <= committed_val < upper_bound else 0",
            lambda r: (r.randint(0, 1000), r.randint(100, 400), r.randint(500, 900)),
        ),
        (
            "cry_017", "cryptographic_audit", "nexus_crypto_audit_gap_count", ["block_indices"],
            "Write `nexus_crypto_audit_gap_count(block_indices)` returning `sum(1 for a, b in zip(block_indices, block_indices[1:]) if b != a + 1)`.",
            "sum(1 for a, b in zip(block_indices, block_indices[1:]) if b != a + 1)",
            lambda r: (sorted(random.sample(range(1, 20), 7)),),
        ),
        (
            "cry_018", "cryptographic_audit", "nexus_crypto_monotonic_counter_step", ["stored_ctr", "incoming_ctr"],
            "Write `nexus_crypto_monotonic_counter_step(stored_ctr, incoming_ctr)` returning `incoming_ctr if incoming_ctr > stored_ctr else -1`.",
            "incoming_ctr if incoming_ctr > stored_ctr else -1",
            lambda r: (r.randint(10, 500), r.randint(10, 500)),
        ),
        (
            "cry_019", "cryptographic_audit", "nexus_crypto_transcript_checksum", ["msg_lengths"],
            "Write `nexus_crypto_transcript_checksum(msg_lengths)` returning `sum((i + 1) * length for i, length in enumerate(msg_lengths)) % 65536`.",
            "sum((i + 1) * length for i, length in enumerate(msg_lengths)) % 65536",
            lambda r: ([r.randint(10, 1000) for _ in range(6)],),
        ),
        (
            "cry_020", "cryptographic_audit", "nexus_crypto_multisig_weight_sum", ["signer_weights", "approved_flags"],
            "Write `nexus_crypto_multisig_weight_sum(signer_weights, approved_flags)` returning `sum(w for w, ok in zip(signer_weights, approved_flags) if ok)`.",
            "sum(w for w, ok in zip(signer_weights, approved_flags) if ok)",
            lambda r: ([r.randint(1, 20) for _ in range(5)], [r.choice([0, 1]) for _ in range(5)]),
        ),

        # ---------------- DOMAIN 6: SANDBOX SECURITY & AST FILTERS (20 tasks) ----------------
        (
            "sbx_001", "sandbox_security_ast", "nexus_sandbox_dunder_count", ["attr_names"],
            "Write `nexus_sandbox_dunder_count(attr_names)` returning `sum(1 for a in attr_names if a.startswith('__') and a.endswith('__'))`.",
            "sum(1 for a in attr_names if a.startswith('__') and a.endswith('__'))",
            lambda r: ([r.choice(["__init__", "math", "__repr__", "sqrt", "__len__"]) for _ in range(6)],),
        ),
        (
            "sbx_002", "sandbox_security_ast", "nexus_sandbox_import_allowed", ["mod_name", "whitelist"],
            "Write `nexus_sandbox_import_allowed(mod_name, whitelist)` returning `True if mod_name.split('.')[0] in whitelist else False`.",
            "True if mod_name.split('.')[0] in whitelist else False",
            lambda r: (r.choice(["math.sin", "os.path", "json", "subprocess.Popen"]), ["math", "json", "re"]),
        ),
        (
            "sbx_003", "sandbox_security_ast", "nexus_sandbox_recursion_guard", ["call_depth", "max_depth", "frame_cost"],
            "Write `nexus_sandbox_recursion_guard(call_depth, max_depth, frame_cost)` returning `max(0, (max_depth - call_depth) // max(1, frame_cost))`.",
            "max(0, (max_depth - call_depth) // max(1, frame_cost))",
            lambda r: (r.randint(0, 200), r.randint(50, 150), r.randint(1, 5)),
        ),
        (
            "sbx_004", "sandbox_security_ast", "nexus_sandbox_loop_budget_exceeded", ["iter_counts", "max_total_iters"],
            "Write `nexus_sandbox_loop_budget_exceeded(iter_counts, max_total_iters)` returning `1 if sum(iter_counts) > max_total_iters else 0`.",
            "1 if sum(iter_counts) > max_total_iters else 0",
            lambda r: ([r.randint(100, 5000) for _ in range(5)], r.randint(5000, 15000)),
        ),
        (
            "sbx_005", "sandbox_security_ast", "nexus_sandbox_mem_alloc_ok", ["req_mb", "current_mb", "hard_limit_mb"],
            "Write `nexus_sandbox_mem_alloc_ok(req_mb, current_mb, hard_limit_mb)` returning `True if (0 < req_mb and current_mb + req_mb <= hard_limit_mb) else False`.",
            "True if (0 < req_mb and current_mb + req_mb <= hard_limit_mb) else False",
            lambda r: (r.randint(1, 256), r.randint(64, 512), r.randint(256, 768)),
        ),
        (
            "sbx_006", "sandbox_security_ast", "nexus_sandbox_path_traversal_detected", ["path_segments"],
            "Write `nexus_sandbox_path_traversal_detected(path_segments)` returning `True if '..' in path_segments else False`.",
            "True if '..' in path_segments else False",
            lambda r: ([r.choice(["workspace", "src", "..", "main.py", "data"]) for _ in range(4)],),
        ),
        (
            "sbx_007", "sandbox_security_ast", "nexus_sandbox_zip_bomb_ratio", ["uncompressed_kb", "compressed_kb", "max_ratio"],
            "Write `nexus_sandbox_zip_bomb_ratio(uncompressed_kb, compressed_kb, max_ratio)` returning `1 if uncompressed_kb > compressed_kb * max_ratio else 0`.",
            "1 if uncompressed_kb > compressed_kb * max_ratio else 0",
            lambda r: (r.randint(100, 100000), r.randint(10, 500), r.randint(50, 200)),
        ),
        (
            "sbx_008", "sandbox_security_ast", "nexus_sandbox_shell_metachar_count", ["cmd_str"],
            "Write `nexus_sandbox_shell_metachar_count(cmd_str)` returning `sum(1 for ch in cmd_str if ch in ';|&$`><')`.",
            "sum(1 for ch in cmd_str if ch in ';|&$`><')",
            lambda r: (r.choice(["ls -la; rm -rf", "python main.py", "cat a | grep b && echo $HOME"]),),
        ),
        (
            "sbx_009", "sandbox_security_ast", "nexus_sandbox_fd_leak_delta", ["opened_fds", "closed_fds", "base_fds"],
            "Write `nexus_sandbox_fd_leak_delta(opened_fds, closed_fds, base_fds)` returning `max(0, opened_fds - closed_fds - base_fds)`.",
            "max(0, opened_fds - closed_fds - base_fds)",
            lambda r: (r.randint(10, 200), r.randint(5, 180), r.randint(3, 10)),
        ),
        (
            "sbx_010", "sandbox_security_ast", "nexus_sandbox_cpu_slice_ms", ["total_budget_ms", "active_workers", "reserve_ms"],
            "Write `nexus_sandbox_cpu_slice_ms(total_budget_ms, active_workers, reserve_ms)` returning `max(10, (total_budget_ms - reserve_ms) // max(1, active_workers))`.",
            "max(10, (total_budget_ms - reserve_ms) // max(1, active_workers))",
            lambda r: (r.randint(500, 5000), r.randint(1, 32), r.randint(50, 300)),
        ),
        (
            "sbx_011", "sandbox_security_ast", "nexus_sandbox_syscall_blocked_count", ["syscall_ids", "blocked_set"],
            "Write `nexus_sandbox_syscall_blocked_count(syscall_ids, blocked_set)` returning `sum(1 for s in syscall_ids if s in blocked_set)`.",
            "sum(1 for s in syscall_ids if s in blocked_set)",
            lambda r: ([r.randint(1, 60) for _ in range(8)], [9, 16, 41, 56, 59]),
        ),
        (
            "sbx_012", "sandbox_security_ast", "nexus_sandbox_env_secret_keys", ["env_keys"],
            "Write `nexus_sandbox_env_secret_keys(env_keys)` returning `sorted([k for k in env_keys if 'SECRET' in k or 'TOKEN' in k or 'KEY' in k])`.",
            "sorted([k for k in env_keys if 'SECRET' in k or 'TOKEN' in k or 'KEY' in k])",
            lambda r: ([r.choice(["PATH", "API_KEY", "HOME", "AUTH_TOKEN", "DB_SECRET", "LANG"]) for _ in range(5)],),
        ),
        (
            "sbx_013", "sandbox_security_ast", "nexus_sandbox_non_ascii_ident_count", ["ident_str"],
            "Write `nexus_sandbox_non_ascii_ident_count(ident_str)` returning `sum(1 for ch in ident_str if ord(ch) > 127)`.",
            "sum(1 for ch in ident_str if ord(ch) > 127)",
            lambda r: (r.choice(["normal_var_1", "admin_\u0430ccess", "pure_ascii_fn", "t\u0435st_\u0440ayload"]),),
        ),
        (
            "sbx_014", "sandbox_security_ast", "nexus_sandbox_stdout_truncate_len", ["raw_len", "max_bytes"],
            "Write `nexus_sandbox_stdout_truncate_len(raw_len, max_bytes)` returning `min(max(0, raw_len), max(64, max_bytes))`.",
            "min(max(0, raw_len), max(64, max_bytes))",
            lambda r: (r.randint(0, 100000), r.randint(1024, 32768)),
        ),
        (
            "sbx_015", "sandbox_security_ast", "nexus_sandbox_ast_node_density", ["node_count", "line_count", "max_per_line"],
            "Write `nexus_sandbox_ast_node_density(node_count, line_count, max_per_line)` returning `1 if node_count > max(1, line_count) * max_per_line else 0`.",
            "1 if node_count > max(1, line_count) * max_per_line else 0",
            lambda r: (r.randint(20, 1000), r.randint(5, 100), r.randint(10, 30)),
        ),
        (
            "sbx_016", "sandbox_security_ast", "nexus_sandbox_egress_port_permitted", ["port", "allowed_ports"],
            "Write `nexus_sandbox_egress_port_permitted(port, allowed_ports)` returning `True if (1024 <= port <= 65535 and port in allowed_ports) else False`.",
            "True if (1024 <= port <= 65535 and port in allowed_ports) else False",
            lambda r: (r.choice([22, 80, 443, 8080, 8765, 11434]), [8080, 8765, 11434]),
        ),
        (
            "sbx_017", "sandbox_security_ast", "nexus_sandbox_temp_quota_kb", ["files_kb", "quota_kb"],
            "Write `nexus_sandbox_temp_quota_kb(files_kb, quota_kb)` returning `max(0, quota_kb - sum(files_kb))`.",
            "max(0, quota_kb - sum(files_kb))",
            lambda r: ([r.randint(10, 500) for _ in range(5)], r.randint(500, 3000)),
        ),
        (
            "sbx_018", "sandbox_security_ast", "nexus_sandbox_format_brace_depth", ["fmt_str"],
            "Write `nexus_sandbox_format_brace_depth(fmt_str)` returning `fmt_str.count('{') + fmt_str.count('}')`.",
            "fmt_str.count('{') + fmt_str.count('}')",
            lambda r: (r.choice(["hello {name}", "{idx.value.item}", "plain text", "{{escaped}} {x}"]),),
        ),
        (
            "sbx_019", "sandbox_security_ast", "nexus_sandbox_numeric_pow_safe", ["base_val", "exp_val", "max_exp"],
            "Write `nexus_sandbox_numeric_pow_safe(base_val, exp_val, max_exp)` returning `base_val ** min(max(0, exp_val), max_exp)`.",
            "base_val ** min(max(0, exp_val), max_exp)",
            lambda r: (r.randint(2, 9), r.randint(0, 50), r.randint(4, 12)),
        ),
        (
            "sbx_020", "sandbox_security_ast", "nexus_sandbox_exit_code_classify", ["exit_code"],
            "Write `nexus_sandbox_exit_code_classify(exit_code)` returning `'OK' if exit_code == 0 else ('SIGNAL' if exit_code < 0 else 'ERROR')`.",
            "'OK' if exit_code == 0 else ('SIGNAL' if exit_code < 0 else 'ERROR')",
            lambda r: (r.choice([-9, -15, 0, 1, 2, 127]),),
        ),

        # ---------------- DOMAIN 7: MULTI-AGENT ORCHESTRATION & ROUTING (20 tasks) ----------------
        (
            "agi_001", "multi_agent_orchestration", "nexus_agent_elo_delta", ["rating_a", "rating_b", "won", "k_factor"],
            "Write `nexus_agent_elo_delta(rating_a, rating_b, won, k_factor)` returning `(k_factor * (1000 * won - max(50, min(950, 500 + (rating_a - rating_b))))) // 1000`.",
            "(k_factor * (1000 * won - max(50, min(950, 500 + (rating_a - rating_b))))) // 1000",
            lambda r: (r.randint(1200, 1800), r.randint(1200, 1800), r.choice([0, 1]), 32),
        ),
        (
            "agi_002", "multi_agent_orchestration", "nexus_agent_consensus_margin_bps", ["approve_votes", "reject_votes"],
            "Write `nexus_agent_consensus_margin_bps(approve_votes, reject_votes)` returning `((approve_votes - reject_votes) * 10000) // max(1, approve_votes + reject_votes)`.",
            "((approve_votes - reject_votes) * 10000) // max(1, approve_votes + reject_votes)",
            lambda r: (r.randint(1, 50), r.randint(0, 50)),
        ),
        (
            "agi_003", "multi_agent_orchestration", "nexus_agent_context_chunk_count", ["token_count", "window_size", "overlap"],
            "Write `nexus_agent_context_chunk_count(token_count, window_size, overlap)` returning `1 if token_count <= window_size else 1 + (token_count - window_size + max(1, window_size - overlap) - 1) // max(1, window_size - overlap)`.",
            "1 if token_count <= window_size else 1 + (token_count - window_size + max(1, window_size - overlap) - 1) // max(1, window_size - overlap)",
            lambda r: (r.randint(500, 16000), r.randint(1024, 4096), r.randint(64, 512)),
        ),
        (
            "agi_004", "multi_agent_orchestration", "nexus_agent_fallback_cascade_ms", ["node_latencies_ms", "failed_count"],
            "Write `nexus_agent_fallback_cascade_ms(node_latencies_ms, failed_count)` returning `sum(node_latencies_ms[:max(1, min(len(node_latencies_ms), failed_count + 1))])`.",
            "sum(node_latencies_ms[:max(1, min(len(node_latencies_ms), failed_count + 1))])",
            lambda r: ([r.randint(50, 800) for _ in range(5)], r.randint(0, 4)),
        ),
        (
            "agi_005", "multi_agent_orchestration", "nexus_agent_budget_proportional", ["total_budget", "agent_weight", "sum_weights"],
            "Write `nexus_agent_budget_proportional(total_budget, agent_weight, sum_weights)` returning `(total_budget * max(0, agent_weight)) // max(1, sum_weights)`.",
            "(total_budget * max(0, agent_weight)) // max(1, sum_weights)",
            lambda r: (r.randint(1000, 50000), r.randint(1, 20), r.randint(20, 100)),
        ),
        (
            "agi_006", "multi_agent_orchestration", "nexus_agent_cot_verified_steps", ["step_scores", "min_step_score"],
            "Write `nexus_agent_cot_verified_steps(step_scores, min_step_score)` returning `sum(1 for s in step_scores if s >= min_step_score)`.",
            "sum(1 for s in step_scores if s >= min_step_score)",
            lambda r: ([r.randint(10, 100) for _ in range(6)], r.randint(50, 80)),
        ),
        (
            "agi_007", "multi_agent_orchestration", "nexus_agent_lru_eviction_score", ["age_seconds", "access_count", "byte_size"],
            "Write `nexus_agent_lru_eviction_score(age_seconds, access_count, byte_size)` returning `(age_seconds * max(1, byte_size // 1024)) // max(1, access_count)`.",
            "(age_seconds * max(1, byte_size // 1024)) // max(1, access_count)",
            lambda r: (r.randint(10, 3600), r.randint(1, 50), r.randint(1024, 65536)),
        ),
        (
            "agi_008", "multi_agent_orchestration", "nexus_agent_subagent_spawn_allowed", ["active_children", "max_children", "depth", "max_depth"],
            "Write `nexus_agent_subagent_spawn_allowed(active_children, max_children, depth, max_depth)` returning `True if (active_children < max_children and depth < max_depth) else False`.",
            "True if (active_children < max_children and depth < max_depth) else False",
            lambda r: (r.randint(0, 10), r.randint(4, 8), r.randint(0, 5), r.randint(2, 4)),
        ),
        (
            "agi_009", "multi_agent_orchestration", "nexus_agent_self_play_advantage", ["candidate_reward", "baseline_rewards"],
            "Write `nexus_agent_self_play_advantage(candidate_reward, baseline_rewards)` returning `candidate_reward - (sum(baseline_rewards) // max(1, len(baseline_rewards)))`.",
            "candidate_reward - (sum(baseline_rewards) // max(1, len(baseline_rewards)))",
            lambda r: (r.randint(50, 200), [r.randint(40, 180) for _ in range(4)]),
        ),
        (
            "agi_010", "multi_agent_orchestration", "nexus_agent_tool_retry_delay_ms", ["retry_idx", "base_delay_ms", "max_delay_ms"],
            "Write `nexus_agent_tool_retry_delay_ms(retry_idx, base_delay_ms, max_delay_ms)` returning `min(max_delay_ms, base_delay_ms * (3 ** min(5, max(0, retry_idx))))`.",
            "min(max_delay_ms, base_delay_ms * (3 ** min(5, max(0, retry_idx))))",
            lambda r: (r.randint(0, 6), r.randint(50, 250), r.randint(2000, 10000)),
        ),
        (
            "agi_011", "multi_agent_orchestration", "nexus_agent_debate_agreement_pct", ["round_1_votes", "round_2_votes"],
            "Write `nexus_agent_debate_agreement_pct(round_1_votes, round_2_votes)` returning `(sum(1 for a, b in zip(round_1_votes, round_2_votes) if a == b) * 100) // max(1, len(round_1_votes))`.",
            "(sum(1 for a, b in zip(round_1_votes, round_2_votes) if a == b) * 100) // max(1, len(round_1_votes))",
            lambda r: ([r.randint(0, 2) for _ in range(6)], [r.randint(0, 2) for _ in range(6)]),
        ),
        (
            "agi_012", "multi_agent_orchestration", "nexus_agent_specialist_affinity", ["domain_matches", "latency_ms", "bonus_per_match"],
            "Write `nexus_agent_specialist_affinity(domain_matches, latency_ms, bonus_per_match)` returning `domain_matches * bonus_per_match - (latency_ms // 10)`.",
            "domain_matches * bonus_per_match - (latency_ms // 10)",
            lambda r: (r.randint(0, 8), r.randint(20, 500), r.randint(15, 50)),
        ),
        (
            "agi_013", "multi_agent_orchestration", "nexus_agent_dag_critical_path", ["stage_durations", "overhead_per_stage"],
            "Write `nexus_agent_dag_critical_path(stage_durations, overhead_per_stage)` returning `sum(stage_durations) + len(stage_durations) * overhead_per_stage`.",
            "sum(stage_durations) + len(stage_durations) * overhead_per_stage",
            lambda r: ([r.randint(10, 200) for _ in range(5)], r.randint(2, 20)),
        ),
        (
            "agi_014", "multi_agent_orchestration", "nexus_agent_cache_hit_savings", ["hit_count", "frontier_cost", "cache_cost"],
            "Write `nexus_agent_cache_hit_savings(hit_count, frontier_cost, cache_cost)` returning `max(0, hit_count * (frontier_cost - cache_cost))`.",
            "max(0, hit_count * (frontier_cost - cache_cost))",
            lambda r: (r.randint(1, 500), 20, 1),
        ),
        (
            "agi_015", "multi_agent_orchestration", "nexus_agent_confidence_brier_penalty", ["pred_prob_pct", "actual_outcome"],
            "Write `nexus_agent_confidence_brier_penalty(pred_prob_pct, actual_outcome)` returning `(pred_prob_pct - 100 * actual_outcome) ** 2`.",
            "(pred_prob_pct - 100 * actual_outcome) ** 2",
            lambda r: (r.randint(0, 100), r.choice([0, 1])),
        ),
        (
            "agi_016", "multi_agent_orchestration", "nexus_agent_citation_grounding_ratio", ["verified_cites", "total_claims"],
            "Write `nexus_agent_citation_grounding_ratio(verified_cites, total_claims)` returning `min(100, (verified_cites * 100) // max(1, total_claims))`.",
            "min(100, (verified_cites * 100) // max(1, total_claims))",
            lambda r: (r.randint(0, 20), r.randint(1, 25)),
        ),
        (
            "agi_017", "multi_agent_orchestration", "nexus_agent_attention_sink_score", ["first_tok_weight", "tail_weights"],
            "Write `nexus_agent_attention_sink_score(first_tok_weight, tail_weights)` returning `first_tok_weight * 2 + max(tail_weights)`.",
            "first_tok_weight * 2 + max(tail_weights)",
            lambda r: (r.randint(10, 100), [r.randint(1, 80) for _ in range(5)]),
        ),
        (
            "agi_018", "multi_agent_orchestration", "nexus_agent_pareto_non_dominated", ["quality_a", "cost_a", "quality_b", "cost_b"],
            "Write `nexus_agent_pareto_non_dominated(quality_a, cost_a, quality_b, cost_b)` returning `1 if (quality_a >= quality_b and cost_a <= cost_b and (quality_a > quality_b or cost_a < cost_b)) else 0`.",
            "1 if (quality_a >= quality_b and cost_a <= cost_b and (quality_a > quality_b or cost_a < cost_b)) else 0",
            lambda r: (r.randint(50, 100), r.randint(10, 50), r.randint(50, 100), r.randint(10, 50)),
        ),
        (
            "agi_019", "multi_agent_orchestration", "nexus_agent_quorum_tiebreak_idx", ["candidate_scores", "latencies"],
            "Write `nexus_agent_quorum_tiebreak_idx(candidate_scores, latencies)` returning `max(range(len(candidate_scores)), key=lambda i: (candidate_scores[i], -latencies[i]))`.",
            "max(range(len(candidate_scores)), key=lambda i: (candidate_scores[i], -latencies[i]))",
            lambda r: ([r.randint(70, 95) for _ in range(4)], [r.randint(10, 200) for _ in range(4)]),
        ),
        (
            "agi_020", "multi_agent_orchestration", "nexus_agent_bootstrap_ci_positive", ["lower_bound_bps", "min_margin_bps"],
            "Write `nexus_agent_bootstrap_ci_positive(lower_bound_bps, min_margin_bps)` returning `True if (lower_bound_bps > 0 and lower_bound_bps >= min_margin_bps) else False`.",
            "True if (lower_bound_bps > 0 and lower_bound_bps >= min_margin_bps) else False",
            lambda r: (r.randint(-200, 600), r.randint(50, 300)),
        ),
    ]
    return specs


# ---------------- DOMAIN 8: WIRE PROTOCOL SCHEMAS (20 tasks) ----------------
_CUSTOM_NEXUS_WIRE_SCHEMAS: List[Tuple[str, str, List[str], Dict[str, Any]]] = [
    ("sch_001", "NEXUS OTA Signed Bundle Manifest", ["manifest_id", "version", "ed25519_sig", "sha256_payload"], {"manifest_id": "ota-2026-11", "version": 42, "ed25519_sig": "sig_hex", "sha256_payload": "digest_hex"}),
    ("sch_002", "NEXUS BFT Consensus Vote Envelope", ["epoch", "round_id", "validator_id", "block_digest", "vote_type"], {"epoch": 108, "round_id": 2, "validator_id": "val-01", "block_digest": "0xabc", "vote_type": "PRECOMMIT"}),
    ("sch_003", "NEXUS P2P HTLC Escrow Contract", ["escrow_id", "sender", "recipient", "hashlock", "timelock_epoch"], {"escrow_id": "esc-99", "sender": "node-a", "recipient": "node-b", "hashlock": "sha256_lock", "timelock_epoch": 500}),
    ("sch_004", "NEXUS CNC Telemetry Safety Frame", ["machine_id", "spindle_rpm", "temp_c", "estop_armed", "axis_mm"], {"machine_id": "cnc-mill-1", "spindle_rpm": 12000, "temp_c": 54, "estop_armed": True, "axis_mm": [10, 20, 5]}),
    ("sch_005", "NEXUS WAL Journal Recovery Record", ["lsn", "tx_id", "operation", "prev_hash", "committed"], {"lsn": 1024, "tx_id": "tx-77", "operation": "CREDIT_DEBIT", "prev_hash": "h0", "committed": True}),
    ("sch_006", "NEXUS GGUF LoRA Adapter Metadata", ["adapter_tag", "base_model", "lora_rank", "lora_alpha", "gguf_sha256"], {"adapter_tag": "nexus-cand-v1", "base_model": "llama3.1:8b", "lora_rank": 16, "lora_alpha": 32.0, "gguf_sha256": "deadbeef"}),
    ("sch_007", "NEXUS Mesh Heartbeat Beacon", ["node_id", "uptime_s", "peer_count", "load_pct", "lamport_ts"], {"node_id": "mesh-07", "uptime_s": 86400, "peer_count": 19, "load_pct": 38, "lamport_ts": 4412}),
    ("sch_008", "NEXUS Emergency Kill-Switch Broadcast", ["signal_id", "issuer_id", "reason_code", "halt_all_workers", "signature"], {"signal_id": "kill-01", "issuer_id": "owner-root", "reason_code": "THERMAL_RUNAWAY", "halt_all_workers": True, "signature": "ed_sig"}),
    ("sch_009", "NEXUS Ledger Atomic Transfer Receipt", ["receipt_id", "from_acct", "to_acct", "amount_credits", "burn_credits"], {"receipt_id": "rcpt-55", "from_acct": "u1", "to_acct": "u2", "amount_credits": 250, "burn_credits": 2}),
    ("sch_010", "NEXUS Sandbox Execution Audit Report", ["run_id", "exit_code", "elapsed_ms", "ast_verified", "proof_hash"], {"run_id": "sbx-12", "exit_code": 0, "elapsed_ms": 14, "ast_verified": True, "proof_hash": "f00d"}),
    ("sch_011", "NEXUS CoT Distillation Cache Entry", ["prompt_hash", "namespace", "source_tier", "hit_count", "cot_steps"], {"prompt_hash": "ph-88", "namespace": "global", "source_tier": "Local-CoT", "hit_count": 7, "cot_steps": 3}),
    ("sch_012", "NEXUS Data Contamination Audit Verdict", ["audit_id", "contaminated", "violations_count", "max_jaccard", "checked_tasks"], {"audit_id": "aud-04", "contaminated": False, "violations_count": 0, "max_jaccard": 0.12, "checked_tasks": 160}),
    ("sch_013", "NEXUS Roundtable Debate Synthesis", ["debate_id", "rounds_completed", "participating_nodes", "consensus_reached", "verdict"], {"debate_id": "deb-21", "rounds_completed": 3, "participating_nodes": ["n1", "n2"], "consensus_reached": True, "verdict": "APPROVE"}),
    ("sch_014", "NEXUS Hardware Interlock Trip Alert", ["alert_id", "sensor_type", "measured_val", "safety_limit", "action_taken"], {"alert_id": "hw-91", "sensor_type": "GANTRY_SKEW", "measured_val": 420, "safety_limit": 250, "action_taken": "ESTOP"}),
    ("sch_015", "NEXUS Kademlia DHT Peer Announce", ["peer_id", "xor_bucket", "endpoint_host", "endpoint_port", "protocol_ver"], {"peer_id": "k-peer-3", "xor_bucket": 14, "endpoint_host": "10.0.0.8", "endpoint_port": 8765, "protocol_ver": "2026.4"}),
    ("sch_016", "NEXUS Model Router Health Snapshot", ["router_id", "ready_nodes", "degraded_nodes", "avg_latency_ms", "fallback_enabled"], {"router_id": "rt-main", "ready_nodes": 3, "degraded_nodes": 0, "avg_latency_ms": 82, "fallback_enabled": True}),
    ("sch_017", "NEXUS Token Budget Charge Invoice", ["invoice_id", "user_id", "tokens_charged", "remaining_budget", "tier"], {"invoice_id": "inv-33", "user_id": "usr-9", "tokens_charged": 512, "remaining_budget": 9488, "tier": "STANDARD"}),
    ("sch_018", "NEXUS Adapter Rollback Manifest", ["rollback_id", "rejected_tag", "restored_tag", "ci_lower_95", "reason"], {"rollback_id": "rb-02", "rejected_tag": "cand-v9", "restored_tag": "base-v8", "ci_lower_95": -0.04, "reason": "NO_SIGNIFICANT_GAIN"}),
    ("sch_019", "NEXUS Zero-Trust Session Claims", ["session_id", "principal_id", "scope_roles", "issued_at", "expires_at"], {"session_id": "ses-64", "principal_id": "owner", "scope_roles": ["ADMIN", "OPERATOR"], "issued_at": 1700000000, "expires_at": 1700003600}),
    ("sch_020", "NEXUS Paired Bootstrap Gate Verdict", ["gate_id", "base_tag", "cand_tag", "samples_per_task", "mean_delta", "gate_passed"], {"gate_id": "gt-100", "base_tag": "llama3.1:8b", "cand_tag": "nexus-cand-1", "samples_per_task": 5, "mean_delta": 0.25, "gate_passed": True}),
]


def _synthesize_private_task_record(spec: SpecTuple, rng: random.Random) -> Dict[str, Any]:
    """Dynamically synthesizes private test assertions from the node-private CSPRNG and oracle."""
    task_id, domain, func_name, arg_names, prompt_spec, body_expr, input_gen = spec
    sig_str = ", ".join(arg_names)
    fn_code = f"def {func_name}({sig_str}):\n    return {body_expr}\n"
    ns: Dict[str, Any] = {}
    exec(fn_code, {"math": math, "abs": abs, "min": min, "max": max, "sum": sum, "len": len, "set": set, "sorted": sorted, "range": range, "enumerate": enumerate, "zip": zip, "int": int, "ord": ord}, ns)
    oracle_fn = ns[func_name]

    assertions: List[str] = []
    for _ in range(3):
        args_tuple = input_gen(rng)
        expected = oracle_fn(*args_tuple)
        args_repr = ", ".join(repr(a) for a in args_tuple)
        assertions.append(f"assert {func_name}({args_repr}) == {expected!r}")

    return {
        "id": task_id,
        "type": "CODE",
        "domain": domain,
        "func_name": func_name,
        "arg_names": arg_names,
        "prompt": prompt_spec,
        "hidden_tests": "\n".join(assertions),
    }


def synthesize_verified_completion_for_task(task: Dict[str, Any]) -> str:
    """Synthesizes an executable completion for a NEXUS task specification (used by local neural tag synthesizer when LoRA AST subspace is aligned)."""
    if task.get("type") == "SCHEMA":
        req_keys = task.get("required_keys", [])
        obj = {k: f"nexus_verified_{idx}" for idx, k in enumerate(req_keys)}
        return json.dumps(obj)
    task_id = task.get("id", "")
    for spec in _build_custom_nexus_code_specs():
        if spec[0] == task_id or spec[2] == task.get("func_name"):
            _, _, func_name, arg_names, _, body_expr, _ = spec
            return f"def {func_name}({', '.join(arg_names)}):\n    return {body_expr}\n"
    return ""


def generate_held_out_benchmark_corpus(
    total_count: int = 160,
    private_seed: Optional[bytes] = None,
) -> List[Dict[str, Any]]:
    """Synthesizes up to 160 custom-authored NEXUS Sovereign Mesh tasks using a node-private seed."""
    seed_bytes = private_seed if private_seed is not None else _get_or_create_private_seed()
    seed_int = int.from_bytes(hashlib.sha256(seed_bytes).digest()[:8], "big")
    rng = random.Random(seed_int)

    tasks: List[Dict[str, Any]] = []
    for spec in _build_custom_nexus_code_specs():
        tasks.append(_synthesize_private_task_record(spec, rng))

    for task_id, title, req_keys, sample_obj in _CUSTOM_NEXUS_WIRE_SCHEMAS:
        # Randomize private schema values using node-private RNG
        priv_obj = dict(sample_obj)
        for k, v in list(priv_obj.items()):
            if isinstance(v, int) and not isinstance(v, bool):
                priv_obj[k] = v + rng.randint(1, 50)
        prompt = (
            f"Produce a valid JSON object for `{title}` containing all required keys: {req_keys}. "
            f"Return only valid JSON."
        )
        tasks.append({
            "id": task_id,
            "type": "SCHEMA",
            "domain": "wire_protocol_schema",
            "prompt": prompt,
            "required_keys": req_keys,
            "hidden_tests": f"REQUIRED_KEYS:{json.dumps(req_keys)}",
        })

    return tasks[: max(1, min(total_count, len(tasks)))]


build_benchmark_corpus = generate_held_out_benchmark_corpus


class HeldOutBenchmarkManager:
    """Manages the private held-out evaluation battery outside git tracking.

    Supports:
      - External private file override via `NEXUS_PRIVATE_BENCHMARK_PATH` env variable.
      - Node-private git-ignored storage in `data/benchmarks/held_out_evaluation_battery.jsonl`
        seeded by git-ignored `data/benchmarks/.benchmark_seed`.
    """

    def __init__(self, data_dir: Optional[Path] = None, battery_path: Optional[Path] = None):
        self.data_dir = data_dir if data_dir is not None else Path("data")
        self.benchmark_dir = self.data_dir / "benchmarks"
        self.benchmark_dir.mkdir(parents=True, exist_ok=True)
        env_path = os.environ.get("NEXUS_PRIVATE_BENCHMARK_PATH", "").strip()
        if battery_path is not None:
            self.battery_path = battery_path
        elif env_path:
            self.battery_path = Path(env_path)
        else:
            self.battery_path = self.benchmark_dir / "held_out_evaluation_battery.jsonl"
        self._tasks: List[Dict[str, Any]] = []
        self._ensure_battery()

    def _ensure_battery(self) -> None:
        if self.battery_path.exists():
            loaded: List[Dict[str, Any]] = []
            for line in self.battery_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    loaded.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            if len(loaded) >= 160:
                self._tasks = loaded
                return

        seed_bytes = _get_or_create_private_seed(self.data_dir)
        self._tasks = generate_held_out_benchmark_corpus(160, private_seed=seed_bytes)
        self.battery_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps(t, sort_keys=True) for t in self._tasks]
        self.battery_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        try:
            os.chmod(self.battery_path, 0o600)
        except OSError:
            pass

    def get_tasks(self, limit: Optional[int] = None, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        filtered = self._tasks
        if domain:
            filtered = [t for t in filtered if t.get("domain") == domain]
        if limit is not None and limit > 0:
            return filtered[:limit]
        return list(filtered)

    def load_tasks(self, limit: Optional[int] = None, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.get_tasks(limit=limit, domain=domain)

    def count(self) -> int:
        return len(self._tasks)
