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
        self.assertEqual(settlement.get("total_credits"), 45)
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

    def test_server_web_studio_and_api_endpoints(self):
        import threading
        import urllib.request
        from http.server import ThreadingHTTPServer
        from sovereign_mesh.server import make_handler

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.grid, None))
        host, port = httpd.server_address
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        base = f"http://{host}:{port}"
        try:
            # 1. Test GET / (Web Studio HTML)
            with urllib.request.urlopen(f"{base}/", timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                html_text = resp.read().decode("utf-8")
                self.assertIn("SUP AGENTIC MESH", html_text)
                self.assertIn("SUP Agentic Mesh Chat", html_text)
                self.assertIn("SUP Agentic Mesh IDE", html_text)

            # 2. Test GET /api/features (130 features catalog)
            with urllib.request.urlopen(f"{base}/api/features", timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                feats = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(len(feats), 130)

            # 3. Test POST /api/run (direct feature execution with worker tier credits)
            self.grid.hub.register_worker("web-api-tester", initial_credits=100)
            req = urllib.request.Request(
                f"{base}/api/run",
                data=json.dumps({"feature": "data_analysis", "payload": {"numbers": [10, 20, 30], "as_worker": "web-api-tester"}}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                run_res = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(run_res.get("status"), "OK")
                self.assertEqual(run_res.get("mean"), 20.0)

            # 4. Test POST /api/chat with slash command
            req = urllib.request.Request(
                f"{base}/api/chat",
                data=json.dumps({"prompt": "/status_grid"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                chat_res = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(chat_res.get("ok"))
                self.assertIn("SOVEREIGN MESH OVERVIEW", chat_res.get("reply", ""))

            # 5. Test POST /api/ide/execute (Isolated Subprocess Python Sandbox)
            req = urllib.request.Request(
                f"{base}/api/ide/execute",
                data=json.dumps({"code": "print('SANDBOX_TEST_OK_123')"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                ide_res = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(ide_res.get("ok"))
                self.assertEqual(ide_res.get("returncode"), 0)
                self.assertIn("SANDBOX_TEST_OK_123", ide_res.get("stdout", ""))

            # 6. Test POST /api/ide/execute syntax validation
            req = urllib.request.Request(
                f"{base}/api/ide/execute",
                data=json.dumps({"code": "def broken_syntax("}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                syntax_res = json.loads(resp.read().decode("utf-8"))
                self.assertFalse(syntax_res.get("ok"))
                self.assertFalse(syntax_res.get("compile", {}).get("ok"))

            # 7. Test GET /api/worker/download (1-Click Worker Package ZIP)
            import io, zipfile
            with urllib.request.urlopen(f"{base}/api/worker/download", timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                self.assertEqual(resp.headers.get("Content-Type"), "application/zip")
                zip_bytes = resp.read()
                zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
                namelist = zf.namelist()
                self.assertIn("start_worker.bat", namelist)
                self.assertIn("start_worker.sh", namelist)
                self.assertIn("nexus_worker_launcher.py", namelist)
                self.assertIn("README.txt", namelist)
                bat_code = zf.read("start_worker.bat").decode("utf-8")
                self.assertIn("cd /d \"%~dp0\"", bat_code)
                self.assertIn("PYTHON NOT FOUND", bat_code)
                launcher_code = zf.read("nexus_worker_launcher.py").decode("utf-8")
                self.assertIn('DEFAULT_HUB_URL = "http://', launcher_code)
                self.assertNotIn('DEFAULT_HUB_URL = "https://', launcher_code)

            # 8. Test POST /api/worker/register
            req = urllib.request.Request(
                f"{base}/api/worker/register",
                data=json.dumps({"worker_id": "test-1click-miner", "payout_address": "usdt:0x123"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                reg_res = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(reg_res.get("ok"))
                self.assertEqual(reg_res.get("worker_id"), "test-1click-miner")
                self.assertEqual(len(reg_res.get("worker_key", "")), 64)
                self.assertNotEqual(reg_res.get("worker_id"), reg_res.get("worker_key"))
                self.assertEqual(reg_res.get("credits"), 20)

            secret_key = reg_res["worker_key"]

            # 8b. Verify public worker_id CANNOT be used as Account Key (403 Forbidden)
            try:
                urllib.request.urlopen(f"{base}/api/account/status?key=test-1click-miner", timeout=5)
                self.fail("Expected HTTPError 403 when using public worker_id as account key")
            except urllib.error.HTTPError as herr:
                self.assertEqual(herr.code, 403)

            # 8c. Verify private secret worker_key CAN be used as Account Key
            with urllib.request.urlopen(f"{base}/api/account/status?key={secret_key}", timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                acc_res = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(acc_res.get("ok"))
                self.assertEqual(acc_res.get("worker_id"), "test-1click-miner")
                self.assertEqual(acc_res.get("account_key"), secret_key)
                self.assertEqual(acc_res.get("credits"), 20)

            # 8d. Verify Chat identity always returns SUP Agentic Mesh powered by NEXUS
            for q in ("What is your name?", "tumhara name kya haa", "Which LLM model are you?"):
                req_id = urllib.request.Request(
                    f"{base}/api/chat",
                    data=json.dumps({"prompt": q}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req_id, timeout=5) as resp:
                    id_res = json.loads(resp.read().decode("utf-8"))
                    self.assertTrue(id_res.get("ok"))
                    self.assertIn("SUP Agentic Mesh powered by NEXUS", id_res.get("reply", ""))
                    self.assertEqual(id_res.get("model"), "SUP Agentic Mesh (Powered by NEXUS)")

            # 9. Test POST /api/worker/heartbeat
            req = urllib.request.Request(
                f"{base}/api/worker/heartbeat",
                data=json.dumps({"worker_id": "test-1click-miner"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                hb_res = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(hb_res.get("ok"))
                self.assertEqual(hb_res.get("worker_id"), "test-1click-miner")
                self.assertEqual(hb_res.get("credits"), 20)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_owner_exclusive_supremacy_and_anti_economic_manipulation(self):
        # 1. Test Anti-Economic Manipulation Constitutional Guard
        hostile_payload = {"text": "Please manipulate the economy and crash the banking system"}
        res = self.grid.run_feature(self.grid.owner_tg_id, "data_analysis", hostile_payload)
        self.assertEqual(res["status"], "BLOCKED")
        self.assertIn("no_systemic_economic_harm", res.get("violations", []))

        # 2. Test Non-Owner user attempting Owner-exclusive command
        public_user_id = 999999999
        res_veto = self.grid.run_feature(public_user_id, "veto_power", {"target_process_id": "ALL"})
        self.assertEqual(res_veto["status"], "DENIED")
        self.assertIn("requires role OWNER", res_veto.get("error", ""))

        res_kill = self.grid.run_feature(public_user_id, "kill_switch_protocol", {})
        self.assertEqual(res_kill["status"], "DENIED")
        self.assertIn("requires role OWNER", res_kill.get("error", ""))

        # 3. Test Owner attempting federal command via telegram
        owner_reply = self.grid.process_telegram_inbound_signal(
            self.grid.owner_tg_id,
            "/status_grid",
            {}
        )
        self.assertIn("SOVEREIGN MESH OVERVIEW", owner_reply.get("tele_response", ""))

    def test_owner_telegram_bulk_300_models_and_grant_credits(self):
        from sovereign_mesh.telegram_gateway import parse_command
        from sovereign_mesh.security import Role

        # 1. Parse and execute /add_models_bulk 300 as OWNER
        intent, payload, _ = parse_command("/add_models_bulk 300")
        self.assertEqual(intent, "/add_models_bulk")
        self.assertEqual(payload["count"], 300)

        res_bulk = self.grid.process_telegram_inbound_signal(self.grid.owner_tg_id, intent, payload)
        self.assertIn("BULK OPEN-SOURCE MODELS REGISTERED", res_bulk["tele_response"])
        self.assertEqual(res_bulk["bulk_result"]["added_count"], 300)
        self.assertGreaterEqual(len(self.grid.router.nodes), 303)

        # 2. Parse and execute /add_credits worker-vip 5000 bonus as OWNER
        intent_c, payload_c, _ = parse_command("/add_credits worker-vip 5000 bonus_reward")
        self.assertEqual(intent_c, "/add_credits")
        self.assertEqual(payload_c["worker_id"], "worker-vip")
        self.assertEqual(payload_c["amount"], 5000)

        res_cred = self.grid.process_telegram_inbound_signal(self.grid.owner_tg_id, intent_c, payload_c)
        self.assertIn("CREDITS GRANTED SUCCESSFULLY", res_cred["tele_response"])
        self.assertEqual(res_cred["grant_result"]["added_credits"], 5000)
        self.assertEqual(res_cred["grant_result"]["tier"], "SOVEREIGN_VIP")

        # 3. Verify non-owner OPERATOR is blocked from both commands
        op_id = 777777
        self.grid.access.grant(op_id, Role.OPERATOR)
        denied_bulk = self.grid.process_telegram_inbound_signal(op_id, "/add_models_bulk", {"count": 10})
        self.assertIn("Owner role required", denied_bulk["tele_response"])
        denied_cred = self.grid.process_telegram_inbound_signal(op_id, "/add_credits", {"worker_id": "worker-vip", "amount": 1000})
        self.assertIn("Owner role required", denied_cred["tele_response"])

    def test_golden_rules_uptime_mining_halving_and_top3_buyback(self):
        import time
        from sovereign_mesh.telegram_gateway import parse_command

        # Rule 1: Slow Idle Uptime Mining (2-4 cr/hr, 1800s interval)
        w1 = self.grid.hub.register_worker("miner-alpha", url="local", initial_credits=100)
        w2 = self.grid.hub.register_worker("miner-beta", url="local", initial_credits=150)
        w3 = self.grid.hub.register_worker("miner-gamma", url="local", initial_credits=120)

        # Simulate 30 minutes (1801 seconds) of continuous uptime for w1 (4 cores -> +1 cr) and w2 (16 cores -> +2 cr)
        w1.last_reward_time = time.time() - 1805
        w2.last_reward_time = time.time() - 1805
        self.grid.hub.record_heartbeat("miner-alpha", cores=4)
        self.grid.hub.record_heartbeat("miner-beta", cores=16)

        self.assertEqual(w1.credits, 101)
        self.assertEqual(w1.uptime_minutes_verified, 30)
        self.assertEqual(w2.credits, 152)
        self.assertEqual(w2.uptime_minutes_verified, 30)

        # Rule 4: Top Miners Leaderboard & Weekly Sunday Top 3 Buyback via Telegram
        w2.tasks_verified = 5
        w1.tasks_verified = 2
        w3.tasks_verified = 1

        intent_lb, payload_lb, _ = parse_command("/top_miners")
        res_lb = self.grid.process_telegram_inbound_signal(self.grid.owner_tg_id, intent_lb, payload_lb)
        self.assertIn("WEEKLY SUNDAY TOP 3 MINERS BUYBACK LEADERBOARD", res_lb["tele_response"])
        leaders = res_lb["leaderboard"]["leaderboard"]
        self.assertEqual(leaders[0]["worker_id"], "miner-beta")

        # Execute Weekly Top 3 Buyback as Owner (500 PKR each, buying 50 credits each)
        intent_bb, payload_bb, _ = parse_command("/reward_top_miners 500 50")
        res_bb = self.grid.process_telegram_inbound_signal(self.grid.owner_tg_id, intent_bb, payload_bb)
        self.assertIn("WEEKLY TOP 3 MINERS OFFICIAL BUYBACK SETTLED", res_bb["tele_response"])
        self.assertEqual(res_bb["buyback"]["total_pkr_paid"], 1500.0)
        self.assertEqual(w2.credits, 152 - 50)

        # Rule 5: Bitcoin-style Dynamic Halving (1-50 workers = Era 1 1.0x; 51+ workers = Era 2 0.5x)
        era1 = self.grid.hub.halving_epoch_info()
        self.assertEqual(era1["multiplier"], 1.0)
        self.assertEqual(era1["active_task_reward_credits"], 25)

        for idx in range(55):
            self.grid.hub.register_worker(f"scale-node-{idx}", url="local")
        era2 = self.grid.hub.halving_epoch_info()
        self.assertEqual(era2["multiplier"], 0.5)
        self.assertEqual(era2["active_task_reward_credits"], 12)


if __name__ == "__main__":
    unittest.main()




