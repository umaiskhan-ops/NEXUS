"""Unit tests for P2P Credits Marketplace & Escrow Engine."""
import tempfile
import unittest
from pathlib import Path

from sovereign_mesh.hub_spoke import MasterHubCoordinator
from sovereign_mesh.ledger import HashChainLedger
from sovereign_mesh.p2p_market import P2PMarketplace


class TestP2PMarketplace(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name)
        self.ledger = HashChainLedger(self.data_dir / "ledger.jsonl")
        self.hub = MasterHubCoordinator(self.ledger, state_path=self.data_dir / "hub.json")
        self.market = P2PMarketplace(self.hub, self.ledger, storage_path=self.data_dir / "p2p.json")

        # Register seller and buyer nodes (400 credits so 20% daily cap allows up to 80 credits)
        self.seller = self.hub.register_worker("seller-node-1", url="local", initial_credits=400)
        self.buyer = self.hub.register_worker("buyer-node-1", url="local", initial_credits=10)

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_sell_order_escrow_locking(self):
        # Seller sells 50 credits for 250 PKR
        res = self.market.create_sell_order(
            seller_id="seller-node-1",
            amount_credits=50,
            price_fiat=250.0,
            payment_method="EasyPaisa: 0300-1234567 (Ali)",
            currency="PKR"
        )
        self.assertTrue(res["ok"])
        order_id = res["order_id"]

        # Seller balance should now be 400 - 50 = 350 (held in escrow)
        self.assertEqual(self.seller.credits, 350)

        # Check order in market listing
        orders = self.market.list_orders(status="OPEN")
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["order_id"], order_id)
        self.assertEqual(orders[0]["amount_credits"], 50)
        self.assertEqual(orders[0]["price_fiat"], 250.0)

    def test_insufficient_credits_rejection(self):
        # Seller tries to sell more than they have
        res = self.market.create_sell_order(
            seller_id="seller-node-1",
            amount_credits=500,
            price_fiat=2000.0,
            payment_method="JazzCash: 0312-0000000"
        )
        self.assertFalse(res["ok"])
        self.assertIn("Insufficient credits", res["error"])
        # Balance untouched
        self.assertEqual(self.seller.credits, 400)

    def test_full_p2p_trade_lifecycle(self):
        # 1. Create sell offer (50 credits for 250 PKR)
        res_sell = self.market.create_sell_order(
            seller_id="seller-node-1",
            amount_credits=50,
            price_fiat=250.0,
            payment_method="EasyPaisa: 0300-1234567",
            currency="PKR"
        )
        order_id = res_sell["order_id"]

        # 2. Buyer initiates buy
        res_buy = self.market.initiate_buy(order_id, "buyer-node-1")
        self.assertTrue(res_buy["ok"])
        self.assertEqual(res_buy["status"], "IN_ESCROW")

        # 3. Buyer submits payment proof
        res_pay = self.market.submit_payment(order_id, "buyer-node-1", "TID-9876543210")
        self.assertTrue(res_pay["ok"])
        self.assertEqual(res_pay["status"], "PAYMENT_SUBMITTED")

        # 4. Seller verifies payment and releases escrow
        res_release = self.market.confirm_and_release(order_id, "seller-node-1")
        self.assertTrue(res_release["ok"])
        self.assertEqual(res_release["status"], "COMPLETED")
        self.assertEqual(res_release["credits_released"], 50)

        # 5. Verify balances:
        # Buyer started with 10, should now have 10 + 50 = 60
        self.assertEqual(self.buyer.credits, 60)
        # Seller started with 400, sold 50, should remain at 350
        self.assertEqual(self.seller.credits, 350)

        # 6. Verify tamper-proof ledger records trade
        valid, bad_idx = self.ledger.verify()
        self.assertTrue(valid)
        self.assertIsNone(bad_idx)

    def test_cancel_order_refunds_escrow(self):
        # Seller lists 80 credits (20% of 400)
        res_sell = self.market.create_sell_order(
            seller_id="seller-node-1",
            amount_credits=80,
            price_fiat=400.0,
            payment_method="Bank Raast"
        )
        order_id = res_sell["order_id"]
        self.assertEqual(self.seller.credits, 320)

        # Seller changes their mind and cancels
        res_cancel = self.market.cancel_order(order_id, "seller-node-1")
        self.assertTrue(res_cancel["ok"])
        self.assertEqual(res_cancel["refunded_credits"], 80)

        # Credits refunded back to 400
        self.assertEqual(self.seller.credits, 400)

    def test_unauthorized_release_rejected(self):
        res_sell = self.market.create_sell_order(
            seller_id="seller-node-1",
            amount_credits=40,
            price_fiat=200.0,
            payment_method="JazzCash"
        )
        order_id = res_sell["order_id"]
        self.market.initiate_buy(order_id, "buyer-node-1")

        # Rogue outsider tries to release escrow
        with self.assertRaises(PermissionError):
            self.market.confirm_and_release(order_id, "rogue-intruder")

    def test_post_payment_cancel_blocked_for_seller(self):
        res_sell = self.market.create_sell_order(
            seller_id="seller-node-1",
            amount_credits=50,
            price_fiat=250.0,
            payment_method="EasyPaisa"
        )
        order_id = res_sell["order_id"]
        self.market.initiate_buy(order_id, "buyer-node-1")
        self.market.submit_payment(order_id, "buyer-node-1", "TID-111222333")

        # Seller cannot unilaterally cancel after buyer submitted payment
        res_cancel = self.market.cancel_order(order_id, "seller-node-1", is_owner=False)
        self.assertFalse(res_cancel["ok"])
        self.assertIn("Sovereign Owner arbitration required", res_cancel["error"])

        # Sovereign Owner CAN arbitrate and cancel if needed
        res_owner_cancel = self.market.cancel_order(order_id, "owner", is_owner=True)
        self.assertTrue(res_owner_cancel["ok"])
        self.assertEqual(res_owner_cancel["status"], "CANCELLED")

    def test_welcome_credits_cannot_be_sold_below_threshold(self):
        # Register new worker with default 20 welcome credits
        new_worker = self.hub.register_worker("new-welcome-worker", url="local")
        self.assertEqual(new_worker.credits, 20)

        # Attempt to sell 10 welcome credits -> blocked by 150-credit minimum threshold
        res_locked = self.market.create_sell_order(
            seller_id="new-welcome-worker",
            amount_credits=10,
            price_fiat=50.0,
            payment_method="EasyPaisa: 0300-0000000"
        )
        self.assertFalse(res_locked["ok"])
        self.assertTrue(res_locked.get("min_threshold_locked"))
        self.assertIn("Minimum 150 credits", res_locked["error"])
        self.assertEqual(new_worker.credits, 20)

    def test_rule2_daily_vesting_and_single_open_order_limit(self):
        # Seller has 400 credits -> max 20% daily sell limit is 80 credits.
        # 1. Trying to dump 150 credits (> 80) is rejected by Anti-Dump Vesting
        res_dump = self.market.create_sell_order(
            seller_id="seller-node-1",
            amount_credits=150,
            price_fiat=750.0,
            payment_method="EasyPaisa: 0300-1234567"
        )
        self.assertFalse(res_dump["ok"])
        self.assertTrue(res_dump.get("daily_vesting_locked"))
        self.assertEqual(res_dump.get("max_sellable_today"), 80)

        # 2. Selling 40 credits (<= 80) succeeds
        res_ok = self.market.create_sell_order(
            seller_id="seller-node-1",
            amount_credits=40,
            price_fiat=200.0,
            payment_method="EasyPaisa: 0300-1234567"
        )
        self.assertTrue(res_ok["ok"])

        # 3. Trying to create a 2nd concurrent open order while 1st is OPEN is rejected
        res_second = self.market.create_sell_order(
            seller_id="seller-node-1",
            amount_credits=20,
            price_fiat=100.0,
            payment_method="EasyPaisa: 0300-1234567"
        )
        self.assertFalse(res_second["ok"])
        self.assertTrue(res_second.get("open_order_limit_reached"))

    def test_buyer_buy_order_full_lifecycle_and_cancel(self):
        # 1. Buyer (only 10 credits) posts a Want-to-Buy order for 60 credits at 180 PKR
        res_bo = self.market.create_buy_order(
            buyer_id="buyer-node-1",
            amount_credits=60,
            price_fiat=180.0,
            payment_method="EasyPaisa / JazzCash",
            currency="PKR"
        )
        self.assertTrue(res_bo["ok"])
        self.assertEqual(res_bo["order_type"], "BUY")
        order_id = res_bo["order_id"]

        # Verify it shows up in BUY orders
        buy_orders = self.market.list_orders(status="OPEN", order_type="BUY")
        self.assertEqual(len(buy_orders), 1)
        self.assertEqual(buy_orders[0]["order_id"], order_id)

        # 2. Seller (400 credits) accepts Buyer's Buy Order -> locks 60 credits in Escrow
        res_acc = self.market.accept_buy_order(
            order_id=order_id,
            seller_id="seller-node-1",
            seller_payment_method="EasyPaisa: 0300-9998887 (Seller Ali)"
        )
        self.assertTrue(res_acc["ok"])
        self.assertEqual(res_acc["status"], "IN_ESCROW")
        self.assertEqual(self.seller.credits, 340)

        # 3. Buyer submits payment TID
        res_pay = self.market.submit_payment(order_id, "buyer-node-1", "TID-BUYORDER-555")
        self.assertTrue(res_pay["ok"])
        self.assertEqual(res_pay["status"], "PAYMENT_SUBMITTED")

        # 4. Seller confirms and releases 60 escrowed credits to Buyer
        res_rel = self.market.confirm_and_release(order_id, "seller-node-1")
        self.assertTrue(res_rel["ok"])
        self.assertEqual(self.buyer.credits, 70)  # 10 + 60

        # 5. Buyer can also create and cancel an OPEN Buy Order before a seller accepts
        res_bo2 = self.market.create_buy_order("buyer-node-1", 50, 150.0, "JazzCash")
        res_can = self.market.cancel_order(res_bo2["order_id"], "buyer-node-1")
        self.assertTrue(res_can["ok"])
        self.assertEqual(res_can["status"], "CANCELLED")

    def test_p2p_dispute_dual_account_freeze_telegram_escalation_and_owner_resolution(self):
        notifications = []
        market = P2PMarketplace(
            self.hub,
            self.ledger,
            storage_path=self.data_dir / "p2p_dispute.json",
            notifier=lambda msg: notifications.append(msg),
        )
        res_sell = market.create_sell_order(
            seller_id="seller-node-1",
            amount_credits=50,
            price_fiat=250.0,
            payment_method="EasyPaisa: 0300-1234567",
        )
        order_id = res_sell["order_id"]
        market.initiate_buy(order_id, "buyer-node-1")
        market.submit_payment(order_id, "buyer-node-1", "TID-DISPUTE-999")

        # Buyer raises dispute
        res_disp = market.raise_dispute(
            order_id=order_id,
            caller_id="buyer-node-1",
            reason="Paid 250 PKR via EasyPaisa TID-DISPUTE-999, seller not releasing",
        )
        self.assertTrue(res_disp["ok"])
        self.assertEqual(res_disp["status"], "DISPUTED")
        self.assertTrue(res_disp["owner_notified"])
        self.assertEqual(len(notifications), 1)
        self.assertIn("P2P ESCROW DISPUTE ESCALATION", notifications[0])

        # H6: Dispute locks only the order's escrowed credits for the seller (anti-DoS:
        # seller's un-escrowed balance remains usable), while blocking P2P griefing.
        self.assertTrue(self.seller.dispute_frozen)
        self.assertFalse(getattr(self.seller, "dispute_account_locked", False))
        self.assertEqual(getattr(self.seller, "dispute_escrow_locked_credits", 0), 50)
        self.assertTrue(self.buyer.dispute_frozen)

        # Seller can still use non-disputed credits (H6 anti-DoS), and refunding Seller's 5 credits keeps balance clean
        self.assertTrue(self.hub.spend_credits("seller-node-1", 5, "test_spend"))
        self.seller.credits += 5

        # Seller cannot unilaterally release while DISPUTED (only Sovereign Owner can arbitrate)
        res_seller_rel = market.confirm_and_release(order_id, "seller-node-1", is_owner=False)
        self.assertFalse(res_seller_rel["ok"])

        # Sovereign Owner resolves dispute by force-releasing credits to Buyer
        res_owner_rel = market.confirm_and_release(order_id, "owner", is_owner=True)
        self.assertTrue(res_owner_rel["ok"])
        self.assertEqual(res_owner_rel["status"], "COMPLETED")
        self.assertEqual(self.buyer.credits, 60)  # 10 + 50

        # Both accounts are automatically unfrozen after resolution
        self.assertFalse(self.seller.dispute_frozen)
        self.assertFalse(self.buyer.dispute_frozen)

    def test_anti_sybil_hardware_uuid_and_micro_pow_heartbeat(self):
        from sovereign_mesh.hub_spoke import solve_pow_challenge

        w1 = self.hub.register_worker(
            "real-pc-worker",
            url="local",
            hardware_uuid="hw-unique-rig-abc123",
            public_ip="203.0.113.10",
            hardware_spec="RTX 4090 (16 Cores)",
        )
        self.assertEqual(w1.hardware_uuid, "hw-unique-rig-abc123")
        self.assertTrue(bool(w1.pow_challenge))

        # Spinning up a 2nd VM worker with the same hardware_uuid is blocked by Anti-Sybil guard
        with self.assertRaises(PermissionError):
            self.hub.register_worker(
                "sybil-vm-clone-2",
                url="local",
                hardware_uuid="hw-unique-rig-abc123",
                public_ip="203.0.113.10",
            )

        # Fake heartbeat script sending invalid PoW nonce is rejected
        with self.assertRaises(PermissionError):
            self.hub.record_heartbeat("real-pc-worker", cores=8, pow_nonce="invalid_fake_nonce")

        # Genuine worker solving the SHA-256 micro-PoW challenge succeeds
        old_challenge = w1.pow_challenge
        valid_nonce = solve_pow_challenge("real-pc-worker", old_challenge)
        hb_res = self.hub.record_heartbeat("real-pc-worker", cores=8, pow_nonce=valid_nonce)
        self.assertEqual(hb_res.pow_verified_count, 1)
        self.assertNotEqual(hb_res.pow_challenge, old_challenge)

    def test_viral_referral_multiplier_5_percent_bonus_and_hardware_flex(self):
        ref_a = self.hub.register_worker(
            "miner-leader-a",
            url="local",
            initial_credits=20,
            hardware_spec="AMD Ryzen 9 7950X + RTX 4080",
        )
        ref_b = self.hub.register_worker(
            "miner-friend-b",
            url="local",
            initial_credits=20,
            referred_by=ref_a.referral_code,
        )
        self.assertEqual(ref_b.referred_by, "miner-leader-a")
        self.assertEqual(ref_a.referrals_count, 1)

        # Friend B earns 100 credits from verified compute tasks -> Leader A gets +5% (+5 credits) minted!
        ref_b.credits += 100
        minted = self.hub._award_referral_bonus(ref_b, 100, source="verified_task_completion")
        self.assertEqual(minted, 5)
        self.assertEqual(ref_b.credits, 120)
        self.assertEqual(ref_a.referral_bonus_credits, 5)
        self.assertEqual(ref_a.credits, 25)

        # Leaderboard exposes hardware_spec and social flex share text
        lb = self.hub.get_top_miners_leaderboard(limit=5)
        leader_entry = next(m for m in lb["leaderboard"] if m["worker_id"] == "miner-leader-a")
        self.assertEqual(leader_entry["hardware_spec"], "AMD Ryzen 9 7950X + RTX 4080")
        self.assertIn("AMD Ryzen 9 7950X + RTX 4080", leader_entry["flex_share_text"])

    def test_cot_knowledge_distillation_and_20_credit_frontier_vs_1_credit_cached(self):
        from sovereign_mesh.models import (
            FRONTIER_TASK_CREDIT_COST,
            STANDARD_TASK_CREDIT_COST,
            DistillationCache,
            ModelNode,
            ModelRouter,
            TokenBudget,
            compute_task_credit_cost,
        )

        class _MockBackend:
            def chat(self, model: str, system: str, prompt: str, timeout: float) -> str:
                return f"<thinking>Step 1: Analyze distributed consensus. Step 2: Prove safety.</thinking>\nSolution for: {prompt[:40]}"

        cot_cache = DistillationCache(storage_path=self.data_dir / "distill.json", ledger=self.ledger)
        nodes = [ModelNode(name="Alpha-Node", model="nex-alpha", role="general")]
        router = ModelRouter(
            nodes=nodes,
            backend=_MockBackend(),
            budget=TokenBudget(100_000),
            distillation_cache=cot_cache,
        )

        # 1. Simple prompt costs 1 credit
        simple_cost = compute_task_credit_cost("Write a hello world function in Python", "fast", cached_locally=False)
        self.assertEqual(simple_cost, STANDARD_TASK_CREDIT_COST)

        # 2. Complex Frontier prompt costs 20 credits on first run (uncached)
        complex_prompt = (
            "Design a distributed consensus proof and formal verification architecture "
            "using GPT-6 Astra with step-by-step reasoning."
        )
        first_cost = compute_task_credit_cost(complex_prompt, "frontier", cached_locally=False)
        self.assertEqual(first_cost, FRONTIER_TASK_CREDIT_COST)

        # Execute on router -> distills CoT + solution into local cache & ledger
        ask_res_1 = router.ask(complex_prompt, frontier_mode=True)
        self.assertTrue(ask_res_1["newly_distilled"])
        self.assertFalse(ask_res_1["distilled_from_cache"])
        self.assertEqual(ask_res_1["cost_credits"], 20)

        # 3. Subsequent similar/identical complex prompt is served from Local Distilled CoT Cache for 1 credit!
        cached_hit = cot_cache.find_similar(complex_prompt)
        self.assertIsNotNone(cached_hit)
        second_cost = compute_task_credit_cost(complex_prompt, "frontier", cached_locally=bool(cached_hit))
        self.assertEqual(second_cost, STANDARD_TASK_CREDIT_COST)

        ask_res_2 = router.ask(complex_prompt, frontier_mode=True)
        self.assertTrue(ask_res_2["distilled_from_cache"])
        self.assertEqual(ask_res_2["cost_credits"], 1)
        self.assertEqual(cot_cache.stats()["external_api_calls_saved"], 1)

    def test_decentralized_brain_matrix_splitting_self_play_and_p2p_survivability(self):
        from sovereign_mesh.brain_matrix import DecentralizedBrainMatrix
        from sovereign_mesh.models import DistillationCache, ModelNode, ModelRouter, TokenBudget

        cot_cache = DistillationCache(storage_path=self.data_dir / "brain_distill.json", ledger=self.ledger)
        brain = DecentralizedBrainMatrix(
            storage_path=self.data_dir / "brain_matrix.json",
            ledger=self.ledger,
            distillation_cache=cot_cache,
            hub=self.hub,
        )

        # Step 1: Register heterogeneous workers -> verify automatic Brain Shard & Replica assignment
        gamer_node = self.hub.register_worker(
            "gamer-rtx-node",
            url="local",
            hardware_spec="Intel i9 + RTX 4090 (16 Cores)",
        )
        office_node = self.hub.register_worker(
            "office-laptop-node",
            url="local",
            hardware_spec="Intel Core i5 Laptop (4 Cores)",
        )
        self.assertIn(gamer_node.brain_shard, {"CODE_DEBUG_EXEC", "MATH_PROOF_LOGIC", "SECURITY_AUDIT_REDTEAM"})
        self.assertEqual(office_node.brain_shard, "DATA_MEMORY_SYNTHESIS")
        self.assertEqual(len(gamer_node.replica_shards), 2)

        # Verify Attention Routing Matrix routes math/proof and coding prompts to specialized shards
        math_route = brain.route_attention("Prove formal verification theorem for Byzantine consensus matrix")
        self.assertEqual(math_route["primary_shard"], "MATH_PROOF_LOGIC")
        self.assertIn("gamer-rtx-node", math_route["routed_worker_nodes"])

        code_route = brain.route_attention("Debug and refactor this Python FastAPI async microservice")
        self.assertEqual(code_route["primary_shard"], "CODE_DEBUG_EXEC")

        # Step 2: Run Self-Play Freedom Loop -> generates synthetic variations & P2P weight delta
        sp_res = brain.run_self_play_freedom_loop(
            seed_prompt="Design a lock-free distributed consensus algorithm",
            seed_solution="Use Raft/PBFT quorum state transitions with monotonic term counters.",
            source_tier="Frontier-GPT6-Astra",
            num_variations=4,
        )
        self.assertTrue(sp_res["ok"])
        self.assertEqual(sp_res["synthetic_variations_generated"], 4)
        self.assertGreaterEqual(cot_cache.stats()["total_distilled_samples"], 4)

        # Step 3: Verify P2P Shared Weights Delta Ledger & 100% Brain Survivability even if a node leaves
        gamer_node.status = "OFFLINE"
        surv = brain.verify_brain_survivability()
        self.assertTrue(surv["all_shards_survivable"])
        self.assertEqual(surv["survivability_pct"], 100.0)

        era_info = brain.autonomy_era_status()
        self.assertIn("Era 1", era_info["era"])
        self.assertGreater(era_info["p2p_weight_deltas_synced"], 0)
        self.assertEqual(len(era_info["era_timeline"]), 3)

    def test_safetensors_lora_backprop_fedavg_and_nat_swarm(self):
        """Tests binary HuggingFace .safetensors IO, LoRA Backpropagation, FedAvg, NAT Pull Queue, and 4-Shard Swarm."""
        from sovereign_mesh.brain_matrix import DecentralizedBrainMatrix, SafeTensorsIO

        brain_path = self.data_dir / "brain_matrix_prod.json"
        brain = DecentralizedBrainMatrix(storage_path=brain_path, hub=self.hub)

        # 1. Verify binary .safetensors checkpoints exist for all 4 shards and unpack to IEEE-754 float32
        checkpoints = brain.get_safetensors_checkpoints()
        self.assertEqual(len(checkpoints), 4)
        for ckpt in checkpoints:
            self.assertTrue(ckpt["exists"])
            self.assertGreater(ckpt["size_bytes"], 2000)
            st_file = brain._safetensors_path(ckpt["shard"])
            tensors, metadata = SafeTensorsIO.load(st_file)
            self.assertIn("layers.0.self_attn.q_proj.lora_A.weight", tensors)
            self.assertIn("layers.0.self_attn.q_proj.lora_B.weight", tensors)
            self.assertEqual(len(tensors["layers.0.self_attn.q_proj.lora_A.weight"][1]), 8 * 32)
            self.assertEqual(len(tensors["layers.0.self_attn.q_proj.lora_B.weight"][1]), 32 * 8)
            self.assertEqual(metadata.get("aggregation"), "FedAvg")

        # 2. Verify real LoRA Backpropagation reduces MSE loss and produces analytical gradients
        st_code_path = brain._safetensors_path("CODE_DEBUG_EXEC")
        init_tensors, _ = SafeTensorsIO.load(st_code_path)
        init_sha = brain._shard_safetensors_meta["CODE_DEBUG_EXEC"]["sha256"]
        bp = brain.compute_lora_backprop_step(
            domain_shard="CODE_DEBUG_EXEC",
            prompt_text="Optimize lock-free ring buffer in Python",
            target_text="Use memoryview and atomic indices for zero-copy throughput.",
            base_A=init_tensors["layers.0.self_attn.q_proj.lora_A.weight"][1],
            base_B=init_tensors["layers.0.self_attn.q_proj.lora_B.weight"][1],
            epochs=5,
        )
        self.assertLess(bp["final_loss"], bp["initial_loss"])
        self.assertGreater(bp["loss_reduction_pct"], 0.0)
        self.assertGreater(bp["gradient_l2_norm"], 0.0)

        # 3. Verify Federated Averaging (FedAvg) merges valid worker deltas & clips/filters poisoned ones
        fed_res = brain.federated_average_lora_deltas(
            domain_shard="CODE_DEBUG_EXEC",
            worker_packets=[
                {
                    "worker_id": "worker-honest-1",
                    "delta_A": bp["delta_A"],
                    "delta_B": bp["delta_B"],
                    "samples_count": 4,
                    "initial_loss": bp["initial_loss"],
                    "final_loss": bp["final_loss"],
                    "gradient_l2_norm": bp["gradient_l2_norm"],
                },
                {
                    "worker_id": "worker-byzantine-bad",
                    "delta_A": [float("nan")] * (8 * 32),
                    "delta_B": [0.0] * (32 * 8),
                    "samples_count": 4,
                },
            ],
        )
        self.assertTrue(fed_res["ok"])
        self.assertEqual(fed_res["accepted_worker_packets"], 1)
        self.assertEqual(fed_res["rejected_byzantine_packets"], 1)
        self.assertNotEqual(fed_res["safetensors_sha256"], init_sha)

        # 4. Verify NAT / Firewall Outbound Pull Task Queue & Proof Settlement with LoRA gradients
        class _DummyGrid:
            pass
        dummy_grid = _DummyGrid()
        dummy_grid.brain_matrix = brain
        self.hub._grid = dummy_grid
        nat_worker = self.hub.register_worker("worker-behind-nat", url="nat://outbound", initial_credits=50)
        queued_pkt = self.hub.enqueue_nat_task(
            "worker-behind-nat",
            "brain_inference",
            {"prompt": "Implement distributed Byzantine-fault-tolerant FedAvg consensus"},
        )
        pulled = self.hub.pull_pending_tasks("worker-behind-nat", max_tasks=5)
        self.assertEqual(len(pulled), 1)
        self.assertEqual(pulled[0]["task_id"], queued_pkt["task_id"])

        from sovereign_mesh.hub_spoke import compute_hmac
        nat_result = {
            "status": "OK",
            "inferred_by_worker": "worker-behind-nat",
            "lora_gradients": {
                "domain_shard": "CODE_DEBUG_EXEC",
                "delta_A": bp["delta_A"],
                "delta_B": bp["delta_B"],
                "initial_loss": bp["initial_loss"],
                "final_loss": bp["final_loss"],
                "gradient_l2_norm": bp["gradient_l2_norm"],
                "samples_count": 4,
            },
        }
        proof = compute_hmac(nat_worker.key, {
            "task_id": queued_pkt["task_id"],
            "worker_id": "worker-behind-nat",
            "feature": "brain_inference",
            "nonce": queued_pkt["nonce"],
            "result": nat_result,
        })
        settled = self.hub.verify_and_settle({
            "task_id": queued_pkt["task_id"],
            "worker_id": "worker-behind-nat",
            "feature": "brain_inference",
            "result": nat_result,
            "worker_proof": proof,
        })
        self.assertTrue(settled["ok"])
        self.assertIsNotNone(settled["fedavg_safetensors_merge"])
        self.assertTrue(settled["fedavg_safetensors_merge"]["ok"])

        # 5. Verify Parallel 4-Shard Swarm Map-Reduce Reasoning
        swarm = brain.execute_parallel_swarm_reasoning("Design and audit a formal cryptographic microservice")
        self.assertTrue(swarm["ok"])
        self.assertEqual(swarm["shards_activated"], 4)
        self.assertEqual(len(swarm["shard_results"]), 4)


if __name__ == "__main__":
    unittest.main()



