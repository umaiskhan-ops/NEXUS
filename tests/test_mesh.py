"""Comprehensive test suite for the Sovereign Agentic Mesh (130 Features)."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sovereign_mesh.config import GridConfig
from sovereign_mesh.features import Block, build_registry
from sovereign_mesh.grid import UltimateAgiSovereignGrid
from sovereign_mesh.ledger import GENESIS_HASH, HashChainLedger
from sovereign_mesh.security import AuthGuard, Role, hash_passphrase, sanitize_payload


class MockBackend:
    """Mock LLM backend for deterministic testing without live Ollama."""

    def __init__(self):
        self.history = []

    def chat(self, model: str, system: str, prompt: str, timeout: float) -> str:
        self.history.append({"model": model, "system": system, "prompt": prompt})
        if "APPROVE or REJECT" in system:
            return "APPROVE: Feasible and adheres to node safety protocols."
        if "Choose the best option" in system or "best candidate" in system:
            return "1. Best option with optimal performance."
        if "5-Whys" in system:
            return "Root cause: unhandled boundary condition in data ingestion."
        return f"Mock response from {model} for: {prompt[:30]}..."

    def list_models(self, timeout: float = 3.0):
        return ["llama3.1:8b", "mistral:7b-instruct", "gpt-oss:20b"]


class SovereignMeshTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="mesh_test_")
        self.data_dir = Path(self.tmp_dir)
        self.passphrase = "MasterSecurePassphrase2026!"
        self.pw_hash = hash_passphrase(self.passphrase)
        self.backend = MockBackend()
        self.config = GridConfig(
            owner_telegram_id=999888,
            master_passphrase_hash=self.pw_hash,
            data_dir=self.data_dir,
            enable_code_execution=True,
            simulate_offline_consensus=False,
            token_budget=1_000_000,
        )
        self.grid = UltimateAgiSovereignGrid(self.config, backend=self.backend)

    def tearDown(self):
        self.grid.stop()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_feature_registry_exact_130_count(self):
        registry = build_registry()
        self.assertEqual(len(registry), 130)
        counts = registry.counts()
        self.assertEqual(counts[Block.CORE.value], 10)
        self.assertEqual(counts[Block.DISCOVERY.value], 21)
        self.assertEqual(counts[Block.CODING.value], 10)
        self.assertEqual(counts[Block.ADVANCED.value], 26)
        self.assertEqual(counts[Block.GOVERNANCE.value], 63)

    def test_ledger_hash_chain_integrity(self):
        ledger = self.grid.ledger
        b1 = ledger.append("task_1", {"v": 1})
        b2 = ledger.append("task_2", {"v": 2})
        b3 = ledger.append("task_3", {"v": 3})
        self.assertEqual(b1["data"]["prev_hash"], GENESIS_HASH)
        self.assertEqual(b2["data"]["prev_hash"], b1["hash"])
        self.assertEqual(b3["data"]["prev_hash"], b2["hash"])

        ok, bad = ledger.verify()
        self.assertTrue(ok)
        self.assertIsNone(bad)

        # Tampering detection
        ledger._blocks[1]["data"]["payload"]["v"] = 999
        tampered_ok, bad_idx = ledger.verify()
        self.assertFalse(tampered_ok)
        self.assertEqual(bad_idx, 1)

    def test_auth_guard_brute_force_lockout(self):
        guard = AuthGuard(self.pw_hash, max_failures=3, lockout_s=10.0)
        ok, res = guard.verify("wrong1")
        self.assertFalse(ok)
        self.assertEqual(res, "INVALID")

        ok, res = guard.verify("wrong2")
        self.assertFalse(ok)

        ok, res = guard.verify("wrong3")
        self.assertFalse(ok)
        self.assertEqual(res, "AUTH_LOCKED")

        # Even correct passphrase is rejected while locked
        ok, res = guard.verify(self.passphrase)
        self.assertFalse(ok)
        self.assertEqual(res, "AUTH_LOCKED")

    def test_telegram_security_intruder_mitigation(self):
        # Unknown sender
        intruder_id = 12345
        resp = self.grid.process_telegram_inbound_signal(intruder_id, "/status_grid", {})
        self.assertTrue(resp.get("drop"))
        self.assertIsNone(resp.get("tele_response"))
        self.assertGreater(self.grid.intrusion_count, 0)

    def test_consensus_voting_via_mock_models(self):
        res = self.grid.router.vote("Deploy mission alpha")
        self.assertTrue(res["passed"])
        self.assertEqual(res["approvals"], 3)
        self.assertEqual(res["total"], 3)

    def test_data_analysis_feature(self):
        res = self.grid.run_feature(
            self.grid.owner_tg_id,
            "data_analysis",
            {"numbers": [10, 20, 30, 40, 50]},
        )
        self.assertEqual(res["status"], "OK")
        self.assertEqual(res["count"], 5)
        self.assertEqual(res["mean"], 30.0)
        self.assertEqual(res["median"], 30.0)
        self.assertEqual(res["min"], 10.0)
        self.assertEqual(res["max"], 50.0)

    def test_trend_forecasting_feature(self):
        res = self.grid.run_feature(
            self.grid.owner_tg_id,
            "trend_forecasting",
            {"series": [10, 15, 20, 25, 30]},
        )
        self.assertEqual(res["status"], "OK")
        self.assertEqual(res["trend"], "UPWARD")
        self.assertGreater(res["slope"], 0)

    def test_final_say_executive_override(self):
        res = self.grid.run_feature(
            self.grid.owner_tg_id,
            "final_say_protocol",
            {"decision": "Proceed immediately under emergency charter."},
            passphrase=self.passphrase,
        )
        self.assertEqual(res["status"], "EXECUTIVE_RULING_RECORDED")
        self.assertEqual(res["authority"], "OWNER_ABSOLUTE")

    def test_sanitization_and_guardian_block(self):
        bad_payload = {"text": "rm -rf / --no-preserve-root"}
        res = self.grid.run_feature(self.grid.owner_tg_id, "knowledge_synthesis", bad_payload)
        self.assertEqual(res["status"], "BLOCKED")
        self.assertIn("no_destructive_commands", res["violations"])

    def test_approval_gate_for_hardware(self):
        # Physical actuation requires approval
        res = self.grid.run_feature(self.grid.owner_tg_id, "printer_3d_control", {})
        self.assertEqual(res["status"], "PENDING_APPROVAL")
        req_id = res["approval_id"]

    def test_dynamic_model_registration_and_removal(self):
        # 1. Add model dynamically
        add_resp = self.grid.process_telegram_inbound_signal(
            self.grid.owner_tg_id,
            "/add_model",
            {"name": "DeepSeek-R1-Node", "role": "Reasoning", "model": "deepseek-r1:8b"}
        )
        self.assertIn("DeepSeek-R1-Node", add_resp.get("tele_response", ""))
        self.assertIsNotNone(self.grid.router.node("DeepSeek-R1-Node"))
        self.assertEqual(len(self.grid.router.nodes), 4)

        # 2. List models
        list_resp = self.grid.process_telegram_inbound_signal(
            self.grid.owner_tg_id,
            "/models",
            {}
        )
        self.assertIn("DeepSeek-R1-Node", list_resp.get("tele_response", ""))

        # 3. Remove model dynamically
        del_resp = self.grid.process_telegram_inbound_signal(
            self.grid.owner_tg_id,
            "/remove_model",
            {"name": "DeepSeek-R1-Node"}
        )
        self.assertIn("removed", del_resp.get("tele_response", "").lower())
        self.assertIsNone(self.grid.router.node("DeepSeek-R1-Node"))
        self.assertEqual(len(self.grid.router.nodes), 3)

    def test_hub_and_spoke_signed_execution_and_reward(self):
        self.grid.process_telegram_inbound_signal(
            self.grid.owner_tg_id, "/register_worker", {"worker_id": "spoke-alpha"}
        )
        resp = self.grid.process_telegram_inbound_signal(
            self.grid.owner_tg_id,
            "/dispatch_worker",
            {"worker_id": "spoke-alpha", "feature": "data_analysis", "task_payload": {"numbers": [5, 10, 15]}},
        )
        settlement = resp.get("settlement", {})
        self.assertEqual(settlement.get("status"), "SETTLED")
        self.assertEqual(settlement.get("total_credits"), 125)
        self.assertEqual(settlement["result"]["mean"], 10.0)

    def test_hub_blocks_federal_powers_on_worker(self):
        self.grid.hub.register_worker("spoke-beta")
        with self.assertRaises(PermissionError):
            self.grid.hub.create_signed_task("spoke-beta", "veto_power", {"target_process_id": "ALL"})
        with self.assertRaises(PermissionError):
            self.grid.hub.create_signed_task("spoke-beta", "emergency_override", {})

    def test_hub_slashing_logic_on_tampered_worker_proof(self):
        from sovereign_mesh.hub_spoke import compute_hmac

        rec = self.grid.hub.register_worker("spoke-rogue", initial_credits=250)
        task = self.grid.hub.create_signed_task("spoke-rogue", "data_analysis", {"numbers": [1, 2, 3]})

        # 1. Invalid HMAC proof (unattributable network garbage) is REJECTED without burning honest credits
        bad_sig_packet = {
            "task_id": task["task_id"],
            "worker_id": "spoke-rogue",
            "result": {"status": "OK", "mean": 999999.0},
            "worker_proof": "tampered_hmac_proof_string",
        }
        rejected = self.grid.hub.verify_and_settle(bad_sig_packet)
        self.assertEqual(rejected["status"], "REJECTED")

        # 2. Rogue worker modifies output and signs it with its valid worker key -> Spot-check catches & SLASHES
        forged_result = {"status": "OK", "mean": 999999.0}
        forged_packet = {
            "task_id": task["task_id"],
            "worker_id": "spoke-rogue",
            "result": forged_result,
            "worker_proof": compute_hmac(rec.key, {
                "task_id": task["task_id"], "worker_id": "spoke-rogue",
                "feature": task["feature"], "nonce": task["nonce"], "result": forged_result,
            }),
        }
        slashed = self.grid.hub.verify_and_settle(forged_packet)
        self.assertEqual(slashed["status"], "SLASHED")
        self.assertEqual(slashed["burned_credits"], 250)
        self.assertEqual(slashed["remaining_credits"], 0)

        # Verify rogue worker is now permanently blocked from receiving new tasks
        worker_rec = self.grid.hub.get_worker("spoke-rogue")
        self.assertEqual(worker_rec.status, "SLASHED")
        with self.assertRaises(PermissionError):
            self.grid.hub.create_signed_task("spoke-rogue", "data_analysis", {"numbers": [1, 2]})

    def test_model_1_compute_barter_credit_economy(self):
        # Register workers
        w1 = self.grid.hub.register_worker("barter-alice", initial_credits=100)
        w2 = self.grid.hub.register_worker("barter-bob", initial_credits=20)

        # Alice spends 30 credits
        res_spend = self.grid.hub.spend_credits("barter-alice", 30, reason="test_compute")
        self.assertEqual(res_spend["status"], "SPENT")
        self.assertEqual(res_spend["remaining_credits"], 70)

        # Bob tries to spend 50 credits -> INSUFFICIENT_CREDITS
        res_fail = self.grid.hub.spend_credits("barter-bob", 50, reason="test_heavy")
        self.assertEqual(res_fail["status"], "INSUFFICIENT_CREDITS")

        # Alice transfers 40 credits to Bob
        res_tx = self.grid.hub.transfer_credits("barter-alice", "barter-bob", 40)
        self.assertEqual(res_tx["status"], "TRANSFERRED")
        self.assertEqual(res_tx["from_balance"], 30)
        self.assertEqual(res_tx["to_balance"], 60)

        # Barter task execution via telegram gateway
        resp = self.grid.process_telegram_inbound_signal(
            self.grid.owner_tg_id, "/barter_task",
            {"worker_id": "barter-bob", "feature": "data_analysis", "task_payload": {"numbers": [1, 2, 3]}}
        )
        self.assertEqual(resp["barter"]["status"], "SPENT")
        self.assertEqual(resp["barter"]["remaining_credits"], 40)

    def test_model_2_tiered_vip_feature_access(self):
        from sovereign_mesh.features.registry import FeatureTier

        # 1. Tier counts check
        counts = self.grid.registry.tier_counts()
        self.assertGreater(counts[FeatureTier.COMMUNITY.value], 0)
        self.assertGreater(counts[FeatureTier.PRO.value], 0)
        self.assertGreater(counts[FeatureTier.SOVEREIGN_VIP.value], 0)

        # 2. Telegram /tiers overview
        tiers_resp = self.grid.process_telegram_inbound_signal(self.grid.owner_tg_id, "/tiers")
        self.assertIn("SYSTEM ACCESS TIERS", tiers_resp["tele_response"])

        # 3. Non-owner with 0 credits tries to run a PRO feature -> TIER_LOCKED
        from sovereign_mesh.security import Role
        self.grid.access.grant(999999, Role.OPERATOR)
        self.grid.hub.register_worker("tier-novice", initial_credits=0)
        locked_res = self.grid.run_feature(
            999999, "data_analysis", {"as_worker": "tier-novice", "numbers": [1, 2, 3]}
        )
        self.assertEqual(locked_res["status"], "TIER_LOCKED")
        self.assertEqual(locked_res["tier_required"], "PRO")

        # 4. Worker with 50+ credits runs PRO feature successfully
        self.grid.hub.register_worker("tier-pro-user", initial_credits=60)
        unlocked_res = self.grid.run_feature(
            999999, "data_analysis", {"as_worker": "tier-pro-user", "numbers": [10, 20]}
        )
        self.assertEqual(unlocked_res["status"], "OK")

        # 5. Owner has unconditional access to all tiers
        owner_res = self.grid.run_feature(
            self.grid.owner_tg_id, "data_analysis", {"numbers": [10, 20]}
        )
        self.assertEqual(owner_res["status"], "OK")

    def test_model_3_commercial_revenue_sharing_and_payouts(self):
        from sovereign_mesh.hub_spoke import LightweightWorkerNode

        # Register workers & set payout addresses
        rec = self.grid.hub.register_worker("commercial-miner", initial_credits=50)
        self.grid.hub.set_payout_address("commercial-miner", "paypal:miner@nexus.network")

        # Worker performs a verified task
        w_node = LightweightWorkerNode("commercial-miner", rec.key, self.grid)
        task = self.grid.hub.create_signed_task("commercial-miner", "data_analysis", {"numbers": [2, 4, 6]})
        settled = self.grid.hub.verify_and_settle(w_node.execute_signed_task(task))
        self.assertTrue(settled["verified"])

        # Deposit $1000 commercial revenue from Enterprise client
        dep = self.grid.hub.deposit_commercial_revenue(1000.0, client_name="EnterpriseCorp", job_id="job-101")
        self.assertEqual(dep["status"], "DEPOSITED")
        self.assertEqual(dep["commercial_revenue_pool_usd"], 1000.0)

        # Settle revenue epoch: 70% ($700) to workers, 30% ($300) to treasury
        settle_res = self.grid.hub.settle_epoch_revenue_split(0.70)
        self.assertEqual(settle_res["status"], "SETTLED")
        self.assertEqual(settle_res["total_revenue_usd"], 1000.0)
        self.assertEqual(settle_res["workers_pool_usd"], 700.0)
        self.assertEqual(settle_res["treasury_pool_usd"], 300.0)

        # Check miner received their pending payout
        bal = self.grid.hub.get_balance("commercial-miner")
        self.assertEqual(bal["pending_payout_usd"], 700.0)
        self.assertEqual(bal["total_payout_earned_usd"], 700.0)
        self.assertEqual(bal["payout_address"], "paypal:miner@nexus.network")

        # Payout stats overview
        stats = self.grid.hub.payout_stats()
        self.assertEqual(stats["treasury_balance_usd"], 300.0)
        self.assertEqual(stats["commercial_revenue_pool_usd"], 0.0)


if __name__ == "__main__":
    unittest.main()

