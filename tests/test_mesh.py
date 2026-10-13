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
        self.grid.hub.register_worker("spoke-rogue", initial_credits=250)
        task = self.grid.hub.create_signed_task("spoke-rogue", "data_analysis", {"numbers": [1, 2, 3]})

        # Rogue worker modifies output or returns corrupted proof
        forged_packet = {
            "task_id": task["task_id"],
            "worker_id": "spoke-rogue",
            "result": {"status": "OK", "mean": 999999.0},
            "worker_proof": "tampered_hmac_proof_string",
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


if __name__ == "__main__":
    unittest.main()

