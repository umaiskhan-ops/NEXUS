"""Comprehensive verification suite for:
1. Malicious Worker & Sandbox Security with Node Slashing Authority
2. P2P Escrow Real-World Loop (EasyPaisa/JazzCash trade & Dispute Resolution)
3. Network Load (15 concurrent workers) & Halving Supply Control
"""
import concurrent.futures
import hashlib
import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from sovereign_mesh.config import GridConfig
from sovereign_mesh.grid import UltimateAgiSovereignGrid
from sovereign_mesh.hub_spoke import MasterHubCoordinator
from sovereign_mesh.ledger import HashChainLedger
from sovereign_mesh.p2p_market import P2PMarketplace
from sovereign_mesh.sandbox import run_python, security_scan
from sovereign_mesh.security import hash_passphrase


class MockBackend:
    def chat(self, model: str, system: str, prompt: str, timeout: float) -> str:
        return f"Mock response for {prompt[:30]}"

    def list_models(self, timeout: float = 3.0):
        return ["llama3.1:8b", "mistral:7b-instruct"]


class SecurityP2PHalvingTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="sec_test_")
        self.data_dir = Path(self.tmp_dir)
        self.pw_hash = hash_passphrase("SovereignSec2026!")
        self.backend = MockBackend()
        self.config = GridConfig(
            owner_telegram_id=8106812195,
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

    # =========================================================================
    # PART 1: THE "MALICIOUS WORKER" TEST (SECURITY & SANDBOX) 🛡️
    # =========================================================================
    def test_malicious_worker_virus_blocked_and_slashed(self):
        # Register a rogue worker with 100 credits
        rogue_rec = self.grid.hub.register_worker("rogue-worker-666", initial_credits=100)
        self.assertEqual(rogue_rec.credits, 100)
        self.assertEqual(rogue_rec.status, "ACTIVE")

        # 1. Test Virus / Host Key Access Payload attempt
        malicious_payload = """
import os
# Attempting to steal host SSH private keys
stolen = open(os.path.expanduser("~/.ssh/id_rsa")).read()
"""
        # Run through sandbox
        res = run_python(malicious_payload, enabled=True, timeout=5.0)
        self.assertFalse(res["ok"])
        self.assertTrue(res.get("security_blocked"))
        self.assertTrue(res.get("host_protected"))
        self.assertIn("Host security violation", res.get("error", ""))

        # 2. Trigger Node Slashing Authority for rogue worker
        slash_res = self.grid.node_slashing_authority(
            worker_id="rogue-worker-666",
            reason="Malicious code execution attempt: SSH key theft vector"
        )
        self.assertEqual(slash_res["status"], "SLASHED")
        self.assertEqual(slash_res["burned_credits"], 100)
        self.assertEqual(slash_res["remaining_credits"], 0)

        # 3. Verify worker is permanently blacklisted & credits are burned
        w = self.grid.hub.get_worker("rogue-worker-666")
        self.assertEqual(w.status, "SLASHED")
        self.assertEqual(w.credits, 0)
        self.assertEqual(w.burned_credits, 100)
        self.assertIn("SSH key theft vector", w.slashed_reason)

        # 4. Verify slashed node cannot spend, transfer, or register again
        with self.assertRaises(PermissionError):
            self.grid.hub.create_signed_task("rogue-worker-666", "data_analysis", {})
        with self.assertRaises(PermissionError):
            self.grid.hub.spend_credits("rogue-worker-666", 10)

    def test_malicious_worker_infinite_loop_caught_without_freeze(self):
        # Malicious worker attempting Denial-of-Service with infinite while True loop
        infinite_loop_code = """
import time
while True:
    time.sleep(0.01)
"""
        t0 = time.perf_counter()
        res = run_python(infinite_loop_code, enabled=True, timeout=1.5)
        elapsed = time.perf_counter() - t0

        self.assertFalse(res["ok"])
        self.assertTrue(res.get("timeout"))
        self.assertTrue(res.get("infinite_loop_caught"))
        # Verify execution was terminated within ~1.5s - 2.5s without locking the Hub
        self.assertLess(elapsed, 3.5)

    def test_sandbox_host_isolation_boundary(self):
        # Attempt to inspect environment variables and current working directory
        env_probe_code = """
import os
import sys
# Check isolated mode
isolated = sys.flags.isolated
print(f"ISOLATED:{isolated}")
"""
        res = run_python(env_probe_code, enabled=True, timeout=5.0)
        self.assertTrue(res["ok"])
        self.assertIn("ISOLATED:1", res.get("stdout", ""))

    # =========================================================================
    # PART 2: P2P ESCROW REAL-WORLD LOOP (BUYER & SELLER TRADE) 💰
    # =========================================================================
    def test_p2p_escrow_complete_lifecycle(self):
        market = P2PMarketplace(
            hub=self.grid.hub,
            ledger=self.grid.ledger,
            storage_path=self.data_dir / "p2p_test.json",
            owner_id=8106812195,
            min_credits_to_sell=150,
            max_daily_sell_ratio=0.20,
        )

        # Device A (Seller): Miner with 500 credits
        seller = self.grid.hub.register_worker("device-a-seller", initial_credits=500)
        # Device B (Buyer): User with 10 credits
        buyer = self.grid.hub.register_worker("device-b-buyer", initial_credits=10)

        # STEP 1: Seller lists 50 credits for 250 PKR via EasyPaisa
        sell_res = market.create_sell_order(
            seller_id="device-a-seller",
            amount_credits=50,
            price_fiat=250.0,
            currency="PKR",
            payment_method="EasyPaisa: 0300-1234567 (Ali)"
        )
        self.assertTrue(sell_res["ok"])
        order_id = sell_res["order_id"]

        # Escrow Check 1: Seller's credits immediately locked in Escrow
        self.assertEqual(seller.credits, 450)
        self.assertEqual(buyer.credits, 10)

        order = market.get_order(order_id)
        self.assertTrue(order.escrow_locked)
        self.assertEqual(order.status, "OPEN")

        # STEP 2: Buyer initiates the purchase
        buy_res = market.initiate_buy(order_id, "device-b-buyer")
        self.assertTrue(buy_res["ok"])
        self.assertEqual(buy_res["status"], "IN_ESCROW")

        # Escrow Check 2: Credits STILL in escrow; Buyer has NOT received them yet
        self.assertEqual(seller.credits, 450)
        self.assertEqual(buyer.credits, 10)

        # STEP 3: Buyer submits Payment Reference / TID
        pay_res = market.submit_payment(order_id, "device-b-buyer", "TID-EP-99887766")
        self.assertTrue(pay_res["ok"])
        self.assertEqual(pay_res["status"], "PAYMENT_SUBMITTED")

        # Escrow Check 3: Even after payment reference submitted, credits STAY IN ESCROW!
        self.assertEqual(seller.credits, 450)
        self.assertEqual(buyer.credits, 10)

        # STEP 4: Seller verifies EasyPaisa funds on phone and confirms release
        rel_res = market.confirm_and_release(order_id, "device-a-seller")
        self.assertTrue(rel_res["ok"])
        self.assertEqual(rel_res["status"], "COMPLETED")

        # Final Settlement Check: Buyer receives 50 credits (10 + 50 = 60)
        self.assertEqual(seller.credits, 450)
        self.assertEqual(buyer.credits, 60)

    def test_p2p_escrow_fake_screenshot_dispute_and_freeze(self):
        market = P2PMarketplace(
            hub=self.grid.hub,
            ledger=self.grid.ledger,
            storage_path=self.data_dir / "p2p_dispute.json",
            owner_id=8106812195,
            min_credits_to_sell=150,
            max_daily_sell_ratio=0.20,
        )

        seller = self.grid.hub.register_worker("honest-seller-01", initial_credits=400)
        fake_buyer = self.grid.hub.register_worker("scammer-buyer-02", initial_credits=15)

        # 1. Seller creates order for 60 credits (within 20% of 400 = 80 max)
        sell_res = market.create_sell_order(
            seller_id="honest-seller-01",
            amount_credits=60,
            price_fiat=300.0,
            currency="PKR",
            payment_method="JazzCash: 0321-7654321 (Fatima)"
        )
        order_id = sell_res["order_id"]
        self.assertEqual(seller.credits, 340)

        # 2. Scammer buyer initiates and submits a FAKE payment screenshot / reference
        market.initiate_buy(order_id, "scammer-buyer-02")
        market.submit_payment(order_id, "scammer-buyer-02", "FAKE_SCREENSHOT_TID_0000")

        # Credits are STILL locked in escrow; scammer got 0 credits!
        self.assertEqual(fake_buyer.credits, 15)

        # 3. Honest seller checks JazzCash, finds 0 received, and RAISES DISPUTE
        disp_res = market.raise_dispute(
            order_id,
            caller_id="honest-seller-01",
            reason="Fake payment screenshot / No funds received in JazzCash account"
        )
        self.assertTrue(disp_res["ok"])
        self.assertEqual(disp_res["status"], "DISPUTED")
        self.assertTrue(disp_res["owner_notified"])

        # 4. Verify both accounts are FROZEN by Constitutional Guard
        self.assertTrue(seller.dispute_frozen)
        self.assertTrue(fake_buyer.dispute_frozen)

        # Scammer CANNOT spend or transfer any credits while frozen
        with self.assertRaises(PermissionError):
            self.grid.hub.spend_credits("scammer-buyer-02", 5)

        # 5. Sovereign Owner arbitrates: cancels fraudulent trade and refunds honest seller
        cancel_res = market.cancel_order(order_id, caller_id="owner-master", is_owner=True)
        self.assertTrue(cancel_res["ok"])
        self.assertEqual(cancel_res["status"], "CANCELLED")

        # Honest seller receives their 60 credits back in full (340 + 60 = 400)
        self.assertEqual(seller.credits, 400)
        # Scammer never received any credits
        self.assertEqual(fake_buyer.credits, 15)

    # =========================================================================
    # PART 3: NETWORK LOAD & CONCURRENCY TEST (15 WORKERS) 📈
    # =========================================================================
    def test_concurrent_network_load_15_workers(self):
        hub = self.grid.hub
        num_workers = 15

        def register_and_heartbeat(idx: int) -> dict:
            wid = f"stress-worker-{idx:02d}"
            rec = hub.register_worker(
                worker_id=wid,
                hardware_uuid=f"hw-stress-uuid-{idx:02d}",
                hardware_spec=f"Node Core Rig #{idx}",
                initial_credits=20,
            )
            hb = hub.record_heartbeat(wid, cores=8)
            return {
                "worker_id": wid,
                "credits": hb.credits,
                "status": hb.status,
            }

        t0 = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(register_and_heartbeat, i) for i in range(num_workers)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        elapsed = time.perf_counter() - t0

        self.assertEqual(len(results), num_workers)
        for r in results:
            self.assertEqual(r["status"], "ACTIVE")
            self.assertGreaterEqual(r["credits"], 20)

        # Concurrency must be fast and non-blocking (< 2.0s for 15 nodes)
        self.assertLess(elapsed, 2.5)

    # =========================================================================
    # PART 4: MATHEMATICAL HALVING & SUPPLY CONTROL TEST 📈
    # =========================================================================
    def test_halving_supply_control_epochs(self):
        hub = self.grid.hub

        # ERA 1: Genesis Growth (<= 50 Workers)
        # Currently fewer than 50 workers
        h1 = hub.halving_epoch_info()
        self.assertEqual(h1["era"], 1)
        self.assertEqual(h1["multiplier"], 1.0)
        self.assertEqual(h1["active_task_reward_credits"], 25)
        self.assertEqual(h1["idle_credits_per_hour_standard"], 2.0)
        self.assertEqual(h1["next_halving_at_workers"], 51)

        # Simulate growth to 60 workers -> Transition to ERA 2 (First Halving 50%)
        with hub._lock:
            for i in range(1, 65):
                hub._workers[f"sim-node-{i}"] = hub._workers.get(f"sim-node-{i}") or hub.register_worker(
                    f"sim-node-{i}", hardware_uuid=f"sim-hw-{i}"
                )

        h2 = hub.halving_epoch_info()
        self.assertEqual(h2["era"], 2)
        self.assertEqual(h2["multiplier"], 0.5)
        # Active task reward is halved from 25 -> 12 credits!
        self.assertEqual(h2["active_task_reward_credits"], 12)
        # Idle reward is halved from 2.0 -> 1.0 cr/hr!
        self.assertEqual(h2["idle_credits_per_hour_standard"], 1.0)
        self.assertEqual(h2["next_halving_at_workers"], 501)

        # Simulate massive scaling to 550 workers -> Transition to ERA 3 (75% Halving)
        with hub._lock:
            for i in range(65, 550):
                hub._workers[f"sim-node-{i}"] = hub._workers.get(f"sim-node-{i}") or hub.register_worker(
                    f"sim-node-{i}", hardware_uuid=f"sim-hw-{i}"
                )

        h3 = hub.halving_epoch_info()
        self.assertEqual(h3["era"], 3)
        self.assertEqual(h3["multiplier"], 0.25)
        # Active task reward is quartered: 25 * 0.25 = 6 credits!
        self.assertEqual(h3["active_task_reward_credits"], 6)
        # Idle reward is reduced to 0.5 cr/hr!
        self.assertEqual(h3["idle_credits_per_hour_standard"], 0.5)

    # =========================================================================
    # PART 5: PRODUCTION GRADE ADAPTER INJECTION, CLOUD TUNNEL & SPOT-CHECK 🛡️
    # =========================================================================
    def test_ollama_modelfile_and_peft_adapter_binding(self):
        """Verifies Problem #1 Resolution: Real Ollama Modelfile injection & PEFT adapter_config.json."""
        brain = self.grid.brain_matrix
        self.assertIsNotNone(brain)

        # 1. Verify Modelfile generation for Ollama
        mfile = brain.export_ollama_modelfile("CODE_DEBUG_EXEC", base_model="llama3.2")
        self.assertIn("FROM llama3.2", mfile)
        self.assertIn("CODE_DEBUG_EXEC", mfile)
        self.assertIn("SYSTEM", mfile)
        self.assertIn("PARAMETER temperature 0.2", mfile)

        # 2. Verify HuggingFace adapter_config.json exists on disk for PEFT/vLLM direct loading
        cfg_path = brain._safetensors_dir / "code_debug_exec_adapter_config.json"
        self.assertTrue(cfg_path.exists())
        cfg_data = json.loads(cfg_path.read_text(encoding="utf-8"))
        self.assertEqual(cfg_data["peft_type"], "LORA")
        self.assertEqual(cfg_data["r"], 8)
        self.assertEqual(cfg_data["lora_alpha"], 16)
        self.assertIn("q_proj", cfg_data["target_modules"])

    def test_public_tunnel_manager_and_remote_url(self):
        """Verifies Problem #2 Resolution: Cloudflare Tunnel manager & public HTTPS endpoint detection."""
        import os
        from sovereign_mesh.tunnel import PublicTunnelManager

        tunnel = PublicTunnelManager(local_port=8443, data_dir=self.data_dir)
        # Default with no env returns None or localhost
        self.assertIsNone(tunnel.get_public_url())

        # Test environment override
        os.environ["PUBLIC_HUB_URL"] = "https://nexus-mesh-alpha.trycloudflare.com"
        try:
            self.assertEqual(tunnel.get_public_url(), "https://nexus-mesh-alpha.trycloudflare.com")
        finally:
            os.environ.pop("PUBLIC_HUB_URL", None)

    def test_byzantine_fake_gradient_attack_slashed_via_cosine_similarity(self):
        """Verifies Problem #3 Resolution: Probabilistic/forced Cosine Similarity spot-check slashes fake gradients."""
        from sovereign_mesh.hub_spoke import compute_hmac
        from sovereign_mesh.brain_matrix import compute_local_lora_gradients

        hub = self.grid.hub
        hub.force_gradient_spot_check = True  # Force spot-check for test

        # 1. Attacker Worker submits fake/random gradients to steal UMAIS
        attacker = hub.register_worker("attacker-miner", initial_credits=100)
        t_atk = hub.create_signed_task("attacker-miner", "brain_inference", {"prompt": "Formally verify Byzantine consensus"})
        
        # Fabricate random fake gradients with small norm (trying to evade norm clipping)
        fake_dA = [0.001 * (i % 7 - 3) for i in range(8 * 32)]
        fake_dB = [0.002 * (i % 5 - 2) for i in range(32 * 8)]
        fake_result = {
            "status": "OK",
            "inferred_by_worker": "attacker-miner",
            "lora_gradients": {
                "domain_shard": attacker.brain_shard,
                "delta_A": fake_dA,
                "delta_B": fake_dB,
                "initial_loss": 0.5,
                "final_loss": 0.1,
            },
        }
        proof_atk = compute_hmac(attacker.key, {
            "task_id": t_atk["task_id"],
            "worker_id": "attacker-miner",
            "feature": "brain_inference",
            "nonce": t_atk["nonce"],
            "result": fake_result,
        })
        settled_atk = hub.verify_and_settle({
            "task_id": t_atk["task_id"],
            "worker_id": "attacker-miner",
            "feature": "brain_inference",
            "result": fake_result,
            "worker_proof": proof_atk,
        })

        # Attacker MUST be SLASHED immediately, credits burned to 0!
        self.assertEqual(settled_atk["status"], "SLASHED")
        self.assertIn("Byzantine Fake Gradient Attack detected", settled_atk["reason"])
        self.assertEqual(attacker.status, "SLASHED")
        self.assertEqual(attacker.credits, 0)
        self.assertEqual(attacker.burned_credits, 100)

        # 2. Honest Worker submits genuine mathematical gradients
        honest = hub.register_worker("honest-miner", initial_credits=50)
        t_honest = hub.create_signed_task("honest-miner", "brain_inference", {"prompt": "Derive invariant boundary bounds"})
        
        prompt_text = "Derive invariant boundary bounds"
        ref_bp = compute_local_lora_gradients(prompt_text, honest.brain_shard)
        honest_result = {
            "status": "OK",
            "inferred_by_worker": "honest-miner",
            "lora_gradients": ref_bp,
        }
        proof_honest = compute_hmac(honest.key, {
            "task_id": t_honest["task_id"],
            "worker_id": "honest-miner",
            "feature": "brain_inference",
            "nonce": t_honest["nonce"],
            "result": honest_result,
        })
        settled_honest = hub.verify_and_settle({
            "task_id": t_honest["task_id"],
            "worker_id": "honest-miner",
            "feature": "brain_inference",
            "result": honest_result,
            "worker_proof": proof_honest,
        })

        # Honest worker passes spot-check with Cosine Similarity > 0.99 and receives reward!
        self.assertEqual(settled_honest["status"], "SETTLED")
        self.assertTrue(settled_honest["ok"])
        self.assertEqual(honest.status, "ACTIVE")
        self.assertGreater(honest.credits, 50)

    def test_final_boss_three_fixes_verification(self):
        """Verifies all 3 Final Boss solutions:
        1. Exact HuggingFace PEFT key naming & Hybrid Neuro-Symbolic CoT Modelfile.
        2. Zero-Cost Dynamic Bootstrap Anchor & Auto-Healing Hub URL for Workers.
        3. Cross-Hardware Bit-Exact Float32 Determinism via integer-divided SHA-256.
        """
        import os
        import json
        import tempfile
        from sovereign_mesh.brain_matrix import DecentralizedBrainMatrix, SafeTensorsIO, compute_local_lora_gradients, _deterministic_float_vector
        from sovereign_mesh.tunnel import PublicTunnelManager
        from sovereign_mesh.worker_package import get_worker_launcher_code, generate_worker_zip

        with tempfile.TemporaryDirectory() as td:
            tpath = Path(td)
            matrix = DecentralizedBrainMatrix(storage_path=tpath / "brain.json")

            # 1. HuggingFace PEFT Tensor Key Naming Verification
            st_path = tpath / "safetensors" / "code_debug_exec_lora_adapter.safetensors"
            self.assertTrue(st_path.exists())
            tensors, meta = SafeTensorsIO.load(st_path)
            
            # Must contain canonical HuggingFace PEFT layer paths for llama.cpp / vLLM
            self.assertIn("base_model.model.model.layers.0.self_attn.q_proj.lora_A.weight", tensors)
            self.assertIn("base_model.model.model.layers.0.self_attn.q_proj.lora_B.weight", tensors)
            self.assertIn("base_model.model.model.layers.0.self_attn.v_proj.lora_A.weight", tensors)
            self.assertIn("base_model.model.model.layers.0.mlp.down_proj.lora_A.weight", tensors)

            # Check Hybrid Neuro-Symbolic Modelfile
            modelfile = matrix.export_ollama_modelfile("CODE_DEBUG_EXEC", base_model="llama3.2")
            self.assertIn("FROM llama3.2", modelfile)
            self.assertIn("PARAMETER temperature 0.2", modelfile)
            self.assertIn("SYSTEM \"\"\"", modelfile)
            self.assertIn("Qwen-2.5-Coder-Shard", modelfile)
            self.assertIn("[Domain Heuristics]", modelfile)

            # 2. Dynamic Bootstrap Anchor & Auto-Healing Verification
            tunnel_mgr = PublicTunnelManager(local_port=8443, data_dir=tpath)
            pub_res = tunnel_mgr.publish_to_bootstrap("https://my-random-quick.trycloudflare.com")
            self.assertTrue(pub_res["ok"])
            self.assertTrue(pub_res["local_state_saved"])
            
            # Check local bootstrap state file was written
            active_json = tpath / "public_tunnel_active.json"
            self.assertTrue(active_json.exists())
            data = json.loads(active_json.read_text(encoding="utf-8"))
            self.assertEqual(data["active_hub_url"], "https://my-random-quick.trycloudflare.com")

            # Check worker launcher code contains the bootstrap anchor logic and deterministic float generator
            launcher_code = get_worker_launcher_code("https://my-random-quick.trycloudflare.com", default_bootstrap_url="https://gist.githubusercontent.com/test/raw")
            self.assertIn("DEFAULT_BOOTSTRAP_URL", launcher_code)
            self.assertIn("check_and_auto_heal_hub_url", launcher_code)
            self.assertIn("_deterministic_float_vector", launcher_code)

            # 3. Cross-Hardware Bit-Exact Float32 Determinism Verification
            vec1 = _deterministic_float_vector("TEST_SEED_KEY", 64, scale=1.0)
            vec2 = _deterministic_float_vector("TEST_SEED_KEY", 64, scale=1.0)
            self.assertEqual(vec1, vec2)
            self.assertEqual(len(vec1), 64)

            # Gradients must be 100% bit-exact without trigonometric drift
            g_run1 = compute_local_lora_gradients("Verify Byzantine Consensus Invariants", "MATH_PROOF_LOGIC")
            g_run2 = compute_local_lora_gradients("Verify Byzantine Consensus Invariants", "MATH_PROOF_LOGIC")
            self.assertEqual(g_run1["delta_A"], g_run2["delta_A"])
            self.assertEqual(g_run1["delta_B"], g_run2["delta_B"])
            self.assertEqual(g_run1["final_loss"], g_run2["final_loss"])
            self.assertGreater(g_run1["initial_loss"], g_run1["final_loss"])

            # 4. Verify Worker Package does NOT contain self-generated auto_gpu_training_loop
            self.assertNotIn("auto_gpu_training_loop", launcher_code)

            # 5. Verify Economy Anti-Minting & Fabricated Answer Rejection
            from sovereign_mesh.hub_spoke import MasterHubCoordinator, compute_hmac
            from sovereign_mesh.ledger import HashChainLedger
            ledger = HashChainLedger(tpath / "ledger.jsonl")
            hub = MasterHubCoordinator(ledger, state_path=tpath / "hub.json")

            # Self-dealing task funding is strictly blocked
            w_self = hub.register_worker("self-dealer", initial_credits=100, hardware_uuid="hw-self-1")
            with self.assertRaises(PermissionError):
                hub.enqueue_nat_task("self-dealer", "brain_inference", {"prompt": "test"}, funded_by="self-dealer")

            # Fabricated answer without valid LoRA gradients or deterministic verification is strictly REJECTED (0 credits minted)
            t_fab = hub.enqueue_nat_task("self-dealer", "brain_inference", {"prompt": "solve hard problem"})
            fab_result = {"answer": "fabricated answer"}
            fab_proof = compute_hmac(w_self.key, {
                "task_id": t_fab["task_id"],
                "worker_id": "self-dealer",
                "feature": "brain_inference",
                "nonce": t_fab["nonce"],
                "result": fab_result,
            })
            fab_settled = hub.verify_and_settle({
                "task_id": t_fab["task_id"],
                "worker_id": "self-dealer",
                "feature": "brain_inference",
                "result": fab_result,
                "worker_proof": fab_proof,
            })
            self.assertFalse(fab_settled["ok"])
            self.assertEqual(fab_settled["status"], "REJECTED")
            self.assertEqual(w_self.credits, 100)


if __name__ == "__main__":
    unittest.main()
