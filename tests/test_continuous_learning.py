"""Comprehensive Test Suite for Continuous Verifiable LoRA Learning Loop.

Verifies:
1. Objective Ground-Truth Verification (Code, Math, JSON schema).
2. Verified Dataset Storage & Filtering.
3. Real PyTorch LoRA autograd gradient descent & loss reduction.
4. Standardized Benchmark Battery execution.
5. Deployment & Automated Rollback Guard logic.
6. Server API endpoints (/api/learning/status, /verify, /train with Auth lock).
7. Feature integration (recursive_self_improvement, multi_ai_code_voting).
"""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from sovereign_mesh.config import GridConfig
from sovereign_mesh.continuous_learning import (
    AdapterBenchmarkSuite,
    ContinuousLoRAEngine,
    ContinuousSelfImprovementManager,
    ObjectiveGroundTruthVerifier,
    VerifiedDatasetStore,
)
from sovereign_mesh.grid import UltimateAgiSovereignGrid
from sovereign_mesh.ledger import HashChainLedger
from sovereign_mesh.server import make_handler


class TestContinuousLearning(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="learning_test_")
        self.data_dir = Path(self.tmp_dir)
        self.ledger = HashChainLedger(self.data_dir / "ledger.jsonl")
        self.mgr = ContinuousSelfImprovementManager(self.data_dir, ledger=self.ledger)

    def test_01_objective_ground_truth_code_verification(self):
        """Code verification passes for valid executing code with assertions, fails on syntax/runtime errors."""
        verifier = ObjectiveGroundTruthVerifier()

        # Valid code with passing assertions
        valid_code = "def add(a, b):\n    return a + b\n"
        valid_res = verifier.verify_code(valid_code, test_assertions="assert add(2, 3) == 5\nassert add(-1, 1) == 0")
        self.assertTrue(valid_res["verified"])
        self.assertEqual(valid_res["exit_code"], 0)
        self.assertIn("proof_hash", valid_res)

        # Code with syntax error
        bad_syntax = "def broken(:\n    pass"
        syntax_res = verifier.verify_code(bad_syntax)
        self.assertFalse(syntax_res["verified"])
        self.assertEqual(syntax_res["verification_type"], "CODE_SYNTAX_FAILED")

        # Code with failing assertion
        fail_code = "def sub(a, b):\n    return a + b\n"
        fail_res = verifier.verify_code(fail_code, test_assertions="assert sub(5, 2) == 3")
        self.assertFalse(fail_res["verified"])
        self.assertEqual(fail_res["verification_type"], "CODE_EXECUTION_FAILED")

    def test_02_objective_ground_truth_math_and_schema_verification(self):
        """Math evaluator deterministically verifies arithmetic; Schema verifier validates JSON contracts."""
        verifier = ObjectiveGroundTruthVerifier()

        # Math verification
        math_res = verifier.verify_math("(12 * 8) + (100 // 4)", expected_val=121)
        self.assertTrue(math_res["verified"])
        self.assertEqual(math_res["result_value"], 121)

        # Math mismatch
        math_fail = verifier.verify_math("2 + 2", expected_val=5)
        self.assertFalse(math_fail["verified"])

        # Math injection block (forbids imports / function calls)
        math_inj = verifier.verify_math("__import__('os').system('echo hi')")
        self.assertFalse(math_inj["verified"])

        # JSON schema verification
        valid_json = '{"worker_id": "w-1", "status": "ACTIVE", "credits": 100}'
        s_res = verifier.verify_json_schema(valid_json, ["worker_id", "status"])
        self.assertTrue(s_res["verified"])

        # Missing key
        s_fail = verifier.verify_json_schema(valid_json, ["worker_id", "missing_token"])
        self.assertFalse(s_fail["verified"])
        self.assertIn("missing_token", s_fail["error"])

    def test_03_verified_dataset_store_and_persistence(self):
        """Verified dataset store records valid truth pairs and survives reloading."""
        store = VerifiedDatasetStore(self.data_dir / "test_dataset.jsonl", ledger=self.ledger)
        entry1 = store.record_verified("Task 1", "Solution 1", "CODE", {"verified": True, "exit_code": 0})
        entry2 = store.record_verified("Task 2", "Solution 2", "MATH", {"verified": True, "result_value": 42})

        self.assertEqual(store.count(), 2)
        code_items = store.list_verified(domain="CODE")
        self.assertEqual(len(code_items), 1)
        self.assertEqual(code_items[0]["id"], entry1["id"])

        # Reload from disk
        reloaded = VerifiedDatasetStore(self.data_dir / "test_dataset.jsonl")
        self.assertEqual(reloaded.count(), 2)

    def test_04_continuous_lora_engine_autograd_loss_reduction(self):
        """Continuous LoRA engine executes real backprop with measurable loss reduction across epochs."""
        engine = ContinuousLoRAEngine(dim=64, rank=8, alpha=16.0)
        dataset = [
            {"prompt": "Write bubble sort", "solution": "def bubble_sort(arr): pass"},
            {"prompt": "Calculate prime sum", "solution": "2 + 3 + 5 + 7 + 11 = 28"},
            {"prompt": "Format worker status", "solution": '{"status": "ACTIVE"}'},
        ]

        report = engine.train_on_verified_dataset(dataset, epochs=6, lr=0.02)
        self.assertTrue(report["ok"])
        self.assertEqual(report["trained_samples"], 3)
        self.assertGreater(report["initial_loss"], report["final_loss"])
        self.assertGreater(report["loss_reduction"], 0.0)
        self.assertIn("layers.0.self_attn.q_proj.lora_A.weight", report["tensors"])
        self.assertIn("layers.0.self_attn.q_proj.lora_B.weight", report["tensors"])

    def test_04b_torch_unavailable_raises_clean_error(self):
        """Marhala 0 Task 2: If PyTorch is unavailable, engine strictly raises TRAINING_UNAVAILABLE (never fake report)."""
        import sovereign_mesh.continuous_learning as cl
        orig = cl.TORCH_AVAILABLE
        try:
            cl.TORCH_AVAILABLE = False
            engine = ContinuousLoRAEngine(dim=64, rank=8)
            with self.assertRaises(RuntimeError) as ctx:
                engine.train_on_verified_dataset([{"prompt": "task", "solution": "sol"}])
            self.assertIn("TRAINING_UNAVAILABLE", str(ctx.exception))
        finally:
            cl.TORCH_AVAILABLE = orig

    def test_05_adapter_benchmark_suite(self):
        """Adapter benchmark suite runs standard algorithmic, math, and schema tasks and computes pass rate."""
        suite = AdapterBenchmarkSuite()
        res = suite.evaluate(adapter_weights=None)
        self.assertGreaterEqual(res["pass_rate"], 0.8)
        self.assertEqual(res["total_count"], 5)
        self.assertIn("elapsed_seconds", res)

    def test_06_self_improvement_manager_deploy_cycle(self):
        """Manager runs complete cycle, detects benchmark pass, and deploys active adapter + Modelfile."""
        self.assertEqual(self.mgr.dataset_store.count(), 0)
        res = self.mgr.run_training_and_deploy_cycle(epochs=4, min_samples=2)

        self.assertTrue(res["ok"])
        self.assertEqual(res["action"], "DEPLOYED")
        self.assertEqual(res["status"], "ACTIVE")
        self.assertTrue(self.mgr.active_adapter_path.exists())
        self.assertTrue(self.mgr.modelfile_path.exists())

        # Verify Modelfile contains ADAPTER directive pointing to active adapter
        modelfile_text = self.mgr.modelfile_path.read_text(encoding="utf-8")
        self.assertIn("ADAPTER", modelfile_text)
        self.assertIn("FROM llama3.1:8b", modelfile_text)

        # Check ledger recorded event
        tail_events = [b["data"]["task"] for b in self.ledger.tail(10)]
        self.assertIn("lora_adapter_deployed", tail_events)

    def test_07_self_improvement_manager_automated_rollback(self):
        """When candidate adapter regresses on benchmark, candidate is rejected and rollback is recorded."""
        self.mgr.populate_seed_verified_dataset()

        # Simulate regression in benchmark suite
        def mock_regression_eval(adapter_weights=None):
            if adapter_weights is not None:
                return {"passed_count": 1, "total_count": 5, "pass_rate": 0.2, "avg_loss": 3.0, "results": []}
            return {"passed_count": 5, "total_count": 5, "pass_rate": 1.0, "avg_loss": 0.1, "results": []}

        self.mgr.benchmark_suite.evaluate = mock_regression_eval
        res = self.mgr.run_training_and_deploy_cycle(epochs=2)

        self.assertFalse(res["ok"])
        self.assertEqual(res["action"], "ROLLED_BACK")
        self.assertEqual(res["status"], "REJECTED_REGRESSION")
        self.assertIn("regressed", res["reason"])
        self.assertFalse(self.mgr.candidate_adapter_path.exists())

        tail_events = [b["data"]["task"] for b in self.ledger.tail(10)]
        self.assertIn("lora_adapter_rollback", tail_events)

    def test_07b_kachra_adapter_rejected_and_rolled_back_by_real_benchmark(self):
        """Marhala 0 Task 3: Deliberately corrupted/kachra adapter weights cause real loss to explode and are rejected by benchmark gate."""
        self.mgr.populate_seed_verified_dataset()

        # Simulate a bad/corrupted training output (kachra adapter with blown-up weights)
        orig_train = self.mgr.engine.train_on_verified_dataset
        def mock_kachra_training(dataset, epochs=6, lr=0.015):
            rep = orig_train(dataset, epochs=epochs, lr=lr)
            # Corrupt the weights with massive adversarial values
            rep["tensors"]["layers.0.self_attn.q_proj.lora_A.weight"] = ([8, 64], [50.0] * 512)
            rep["tensors"]["layers.0.self_attn.q_proj.lora_B.weight"] = ([64, 8], [50.0] * 512)
            return rep

        self.mgr.engine.train_on_verified_dataset = mock_kachra_training

        # Run cycle with REAL un-mocked benchmark evaluation
        res = self.mgr.run_training_and_deploy_cycle(epochs=2)

        self.assertFalse(res["ok"])
        self.assertEqual(res["action"], "ROLLED_BACK")
        self.assertEqual(res["status"], "REJECTED_REGRESSION")
        self.assertIn("regressed", res["reason"])
        self.assertFalse(self.mgr.candidate_adapter_path.exists())
        self.assertFalse(self.mgr.active_adapter_path.exists(), "Kachra adapter must NEVER be deployed to active adapter")

        tail_events = [b["data"]["task"] for b in self.ledger.tail(10)]
        self.assertIn("lora_adapter_rollback", tail_events)

    def test_08_server_api_learning_endpoints_and_auth(self):
        """Server exposes /api/learning/status, /verify, /train with strict authentication."""
        cfg = GridConfig(
            owner_telegram_id=999,
            master_passphrase_hash="test_pass_hash",
            data_dir=self.data_dir / "grid_srv",
            dashboard_token="sec-token-learning",
        )
        grid = UltimateAgiSovereignGrid(cfg)
        grid.start()
        srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(grid, None))
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            base = f"http://127.0.0.1:{port}"
            auth_hdrs = {"X-Dashboard-Token": "sec-token-learning", "Content-Type": "application/json"}
            unauth_hdrs = {"Content-Type": "application/json"}

            # GET /api/learning/status
            with urllib.request.urlopen(f"{base}/api/learning/status", timeout=5) as resp:
                status_data = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(status_data["ok"])
                self.assertIn("verified_samples_count", status_data)

            # POST /api/learning/verify (unauth rejected with 401)
            req_unauth = urllib.request.Request(
                f"{base}/api/learning/verify",
                data=json.dumps({"type": "math", "expression": "10 * 10"}).encode("utf-8"),
                headers=unauth_hdrs,
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(req_unauth, timeout=5)
            self.assertEqual(ctx.exception.code, 401)

            # POST /api/learning/verify (auth succeeds with proof and saves to dataset)
            req_verify = urllib.request.Request(
                f"{base}/api/learning/verify",
                data=json.dumps({
                    "type": "code",
                    "code": "def double(x):\n    return x * 2\n",
                    "test_assertions": "assert double(4) == 8",
                    "save_to_dataset": True,
                    "prompt": "Write double(x)",
                    "domain": "CODE_DEBUG_EXEC",
                }).encode("utf-8"),
                headers=auth_hdrs,
            )
            with urllib.request.urlopen(req_verify, timeout=5) as resp_v:
                v_data = json.loads(resp_v.read().decode("utf-8"))
                self.assertTrue(v_data["ok"])
                self.assertTrue(v_data["verified"])
                self.assertIn("saved_sample_id", v_data)

            # POST /api/learning/train (auth triggers self-improvement cycle)
            req_train = urllib.request.Request(
                f"{base}/api/learning/train",
                data=json.dumps({"epochs": 3, "min_samples": 1}).encode("utf-8"),
                headers=auth_hdrs,
            )
            with urllib.request.urlopen(req_train, timeout=10) as resp_t:
                t_data = json.loads(resp_t.read().decode("utf-8"))
                self.assertTrue(t_data["ok"])
                self.assertEqual(t_data["action"], "DEPLOYED")
                self.assertIn("training_report", t_data)

        finally:
            srv.shutdown()
            srv.server_close()
            grid.stop()

    def test_09_feature_integration_code_voting_and_recursive_improvement(self):
        """recursive_self_improvement and multi_ai_code_voting connect to continuous learning loop."""
        cfg = GridConfig(
            owner_telegram_id=888,
            master_passphrase_hash="pass_hash_888",
            data_dir=self.data_dir / "grid_feats",
            dashboard_token="token-feats",
        )
        grid = UltimateAgiSovereignGrid(cfg)
        grid.start()
        try:
            # 1. recursive_self_improvement feature executes real training cycle (approval gated)
            res_rsi = grid.run_feature(888, "recursive_self_improvement", {"action": "cycle", "epochs": 2}, approved=True)
            self.assertEqual(res_rsi["status"], "ACTIVE")
            self.assertEqual(res_rsi["action"], "DEPLOYED")

            # 2. multi_ai_code_voting objectively verifies code candidates and saves to continuous learning store
            res_vote = grid.run_feature(888, "multi_ai_code_voting", {
                "text": "Write a function square(x: int) -> int that returns x * x",
                "test_assertions": "assert square(5) == 25",
                "candidates": [
                    "def square(x):\n    return x * x\n",
                    "def square(x):\n    return x + x\n",
                ],
            })
            self.assertEqual(res_vote["status"], "OK")
            self.assertIn("verified", res_vote)
            self.assertIn("verification_proof", res_vote)

        finally:
            grid.stop()


if __name__ == "__main__":
    unittest.main()
