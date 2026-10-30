"""Unit tests for The Token Sink: Deflationary Lottery Pool & Staking Vault."""
import tempfile
import unittest
from pathlib import Path

from sovereign_mesh.config import GridConfig
from sovereign_mesh.grid import UltimateAgiSovereignGrid
from sovereign_mesh.hub_spoke import MasterHubCoordinator
from sovereign_mesh.ledger import HashChainLedger
from sovereign_mesh.token_sink import TokenSinkManager


class TestTokenSink(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name)
        self.ledger = HashChainLedger(self.data_dir / "ledger.jsonl")
        self.hub = MasterHubCoordinator(self.ledger, state_path=self.data_dir / "hub.json")
        self.sink = TokenSinkManager(
            self.hub,
            self.ledger,
            storage_path=self.data_dir / "sink.json",
            ticket_price=5,
            target_pool_tickets=10,
        )

        # Register workers
        self.w1 = self.hub.register_worker("worker-alice", url="local", initial_credits=100)
        self.w2 = self.hub.register_worker("worker-bob", url="local", initial_credits=100)
        self.w3 = self.hub.register_worker("worker-charlie", url="local", initial_credits=20)

    def tearDown(self):
        self.tmp.cleanup()

    def test_lottery_ticket_purchase_and_balance_deduction(self):
        # Alice buys 2 tickets (10 credits)
        res = self.sink.buy_lottery_ticket("worker-alice", count=2)
        self.assertTrue(res["ok"])
        self.assertEqual(res["tickets_bought"], 2)
        self.assertEqual(res["cost_credits"], 10)
        self.assertEqual(res["remaining_credits"], 90)
        self.assertEqual(self.w1.credits, 90)

        status = self.sink.get_lottery_status()
        self.assertEqual(status["tickets_sold_in_round"], 2)
        self.assertEqual(status["current_pool_credits"], 10)
        self.assertEqual(status["tickets_needed_for_draw"], 8)

    def test_insufficient_credits_for_lottery(self):
        # Charlie has 20 credits, tries to buy 5 tickets (25 credits)
        res = self.sink.buy_lottery_ticket("worker-charlie", count=5)
        self.assertFalse(res["ok"])
        self.assertTrue(res.get("insufficient_credits"))
        self.assertEqual(self.w3.credits, 20)

    def test_slashed_or_frozen_worker_cannot_buy(self):
        self.w1.status = "SLASHED"
        res = self.sink.buy_lottery_ticket("worker-alice", count=1)
        self.assertFalse(res["ok"])
        self.assertIn("SLASHED", res["error"])

        self.w2.dispute_frozen = True
        res2 = self.sink.buy_lottery_ticket("worker-bob", count=1)
        self.assertFalse(res2["ok"])
        self.assertIn("FROZEN", res2["error"])

    def test_lottery_draw_jackpot_and_deflationary_burn(self):
        # Alice buys 5 tickets (25 cr), Bob buys 5 tickets (25 cr) -> target pool 10 tickets (50 cr) reached!
        res_a = self.sink.buy_lottery_ticket("worker-alice", count=5)
        self.assertTrue(res_a["ok"])
        self.assertFalse(res_a["auto_drawn"])

        res_b = self.sink.buy_lottery_ticket("worker-bob", count=5)
        self.assertTrue(res_b["ok"])
        # Target pool reached -> auto-draw triggered!
        self.assertTrue(res_b["auto_drawn"])
        draw = res_b["draw_result"]
        self.assertTrue(draw["ok"])

        # 50 credits total: 90% (45 cr) to winner, 10% (5 cr) burned permanently!
        self.assertEqual(draw["total_pot_credits"], 50)
        self.assertEqual(draw["jackpot_credits"], 45)
        self.assertEqual(draw["burned_credits"], 5)
        self.assertIn(draw["winner_worker_id"], ["worker-alice", "worker-bob"])
        self.assertTrue(len(draw["beacon_hash"]) >= 16)

        # Deflationary burn recorded
        status = self.sink.get_lottery_status()
        self.assertEqual(status["total_deflationary_burned_credits"], 5)
        self.assertEqual(status["total_jackpot_credits_awarded"], 45)
        self.assertEqual(status["current_round"], 2)
        self.assertEqual(status["tickets_sold_in_round"], 0)

    def test_force_lottery_draw(self):
        # Alice buys 2 tickets (10 cr), Bob buys 1 ticket (5 cr)
        self.sink.buy_lottery_ticket("worker-alice", count=2)
        self.sink.buy_lottery_ticket("worker-bob", count=1)

        # Force draw with 15 credits
        draw = self.sink.draw_lottery_winner(force=True)
        self.assertTrue(draw["ok"])
        self.assertEqual(draw["total_pot_credits"], 15)
        self.assertEqual(draw["jackpot_credits"], 14)  # 90% of 15 ~ 14
        self.assertEqual(draw["burned_credits"], 1)    # 10% of 15 ~ 1

    def test_staking_vault_tiers_and_perks(self):
        # Initial: Alice has 100 credits
        # Stake 20 -> BRONZE
        res1 = self.sink.stake_credits("worker-alice", 20)
        self.assertTrue(res1["ok"])
        self.assertEqual(res1["tier"], "BRONZE")
        self.assertEqual(res1["total_staked"], 20)
        self.assertEqual(res1["remaining_credits"], 80)
        self.assertEqual(self.w1.credits, 80)

        # Stake another 30 (total 50) -> SILVER
        res2 = self.sink.stake_credits("worker-alice", 30)
        self.assertTrue(res2["ok"])
        self.assertEqual(res2["tier"], "SILVER")
        self.assertEqual(res2["total_staked"], 50)
        self.assertEqual(res2["remaining_credits"], 50)

        # Bob has 100 credits, grants him 60 more so 160 credits
        self.hub.grant_credits("worker-bob", 60)
        res3 = self.sink.stake_credits("worker-bob", 150)
        self.assertTrue(res3["ok"])
        self.assertEqual(res3["tier"], "GOLD")
        self.assertIn("2x Lottery Luck Odds", res3["perks"])

        # Check staking status
        st_info = self.sink.get_staking_status("worker-bob")
        self.assertEqual(st_info["user_staked"], 150)
        self.assertEqual(st_info["user_tier"], "GOLD")
        self.assertEqual(st_info["total_staked_in_vault"], 200)

    def test_unstaking_vault_refunds_balance(self):
        self.sink.stake_credits("worker-alice", 50)
        self.assertEqual(self.w1.credits, 50)

        # Unstake 20 credits
        res = self.sink.unstake_credits("worker-alice", 20)
        self.assertTrue(res["ok"])
        self.assertEqual(res["remaining_staked"], 30)
        self.assertEqual(res["active_credits"], 70)
        self.assertEqual(self.w1.credits, 70)

        # Cannot unstake more than staked
        fail_res = self.sink.unstake_credits("worker-alice", 40)
        self.assertFalse(fail_res["ok"])
        self.assertIn("Insufficient staked balance", fail_res["error"])

    def test_grid_feature_dispatch(self):
        cfg = GridConfig(
            owner_telegram_id=999888,
            master_passphrase_hash="test_hash_1234",
            data_dir=self.data_dir / "grid_data",
        )
        grid = UltimateAgiSovereignGrid(cfg)
        try:
            # Verify TokenSinkManager is initialized on Grid
            self.assertTrue(hasattr(grid, "token_sink"))
            self.assertIsNotNone(grid.token_sink)

            # Register a worker on grid hub
            w = grid.hub.register_worker("grid-miner-1", url="local", initial_credits=100)

            # Run lottery status via grid.run_feature
            res_lot = grid.run_feature(999888, "credit_lottery_pool", {"account_key": w.worker_id, "action": "status"})
            self.assertTrue(res_lot.get("ok"))
            self.assertIn("current_round", res_lot)

            # Buy ticket via grid.run_feature
            res_buy = grid.run_feature(999888, "credit_lottery_pool", {"account_key": w.worker_id, "count": 2})
            self.assertTrue(res_buy.get("ok"))
            self.assertEqual(res_buy.get("tickets_bought"), 2)

            # Run staking feature via grid.run_feature
            res_stk = grid.run_feature(999888, "staking_rewards_vault", {"account_key": w.worker_id, "action": "stake", "amount": 50})
            self.assertTrue(res_stk.get("ok"))
            self.assertEqual(res_stk.get("tier"), "SILVER")
        finally:
            grid.stop()

    def test_http_lottery_and_staking_endpoints_and_webui(self):
        import json
        import threading
        import urllib.request
        from http.server import ThreadingHTTPServer
        from sovereign_mesh.server import make_handler

        cfg = GridConfig(
            owner_telegram_id=999888,
            master_passphrase_hash="test_hash_1234",
            data_dir=self.data_dir / "http_grid_data",
        )
        grid = UltimateAgiSovereignGrid(cfg)
        grid.hub.register_worker("http-miner-1", url="local", initial_credits=100)
        grid.hub.register_worker("http-miner-2", url="local", initial_credits=100)

        srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(grid, None))
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        base = f"http://127.0.0.1:{port}"
        try:
            # 1. Verify Web UI renders cleanly with Tab 6 (Lottery & Staking Sink)
            with urllib.request.urlopen(f"{base}/", timeout=5) as resp:
                html = resp.read().decode("utf-8")
                self.assertIn("tab-lottery", html)
                self.assertIn("Credit Lottery &amp; Staking Sink", html)
                self.assertIn("loadLotteryAndStaking", html)

            # 2. Buy tickets via HTTP POST
            req_buy = urllib.request.Request(
                f"{base}/api/lottery/buy_ticket",
                data=json.dumps({"account_key": "http-miner-1", "count": 3}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req_buy, timeout=5) as resp:
                buy_data = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(buy_data["ok"])
                self.assertEqual(buy_data["tickets_bought"], 3)
                self.assertEqual(buy_data["current_pool_credits"], 15)

            # 3. Draw winner via HTTP POST
            req_draw = urllib.request.Request(
                f"{base}/api/lottery/draw",
                data=json.dumps({"force": True}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req_draw, timeout=5) as resp:
                draw_data = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(draw_data["ok"])
                self.assertEqual(draw_data["winner_worker_id"], "http-miner-1")
                self.assertEqual(draw_data["jackpot_credits"], 14)
                self.assertEqual(draw_data["burned_credits"], 1)

            # 4. Stake & Unstake via HTTP POST
            req_stake = urllib.request.Request(
                f"{base}/api/staking/stake",
                data=json.dumps({"account_key": "http-miner-2", "amount": 50}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req_stake, timeout=5) as resp:
                stk_data = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(stk_data["ok"])
                self.assertEqual(stk_data["tier"], "SILVER")
                self.assertEqual(stk_data["total_staked"], 50)

            with urllib.request.urlopen(f"{base}/api/staking/status?account_key=http-miner-2", timeout=5) as resp:
                st_status = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(st_status["ok"])
                self.assertEqual(st_status["user_staked"], 50)
                self.assertEqual(st_status["user_tier"], "SILVER")
        finally:
            srv.shutdown()
            srv.server_close()
            grid.stop()


if __name__ == "__main__":
    unittest.main()
