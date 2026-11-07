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

from sovereign_mesh.benchmark_corpus import synthesize_verified_completion_for_task
from sovereign_mesh.config import GridConfig
from sovereign_mesh.continuous_learning import (
    AdapterBenchmarkSuite,
    ContinuousLoRAEngine,
    ContinuousSelfImprovementManager,
    DataContaminationChecker,
    HELD_OUT_BENCHMARK_TASKS,
    ObjectiveGroundTruthVerifier,
    TORCH_AVAILABLE,
    VerifiedDatasetStore,
    generate_held_out_benchmark_corpus,
)
from sovereign_mesh.grid import UltimateAgiSovereignGrid
from sovereign_mesh.ledger import HashChainLedger
from sovereign_mesh.models import OllamaBackend
from sovereign_mesh.qlora_engine import (
    AdapterModelCompatibilityValidator,
    GGUFLoRAExporter,
    PeftToGGUFConverter,
    RealQLoRAEngine,
    is_hf_qlora_stack_ready,
)
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

    @unittest.skipUnless(TORCH_AVAILABLE, "PyTorch required for neural autograd")
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
        self.assertGreaterEqual(res["total_count"], 5)
        self.assertIn("elapsed_seconds", res)

    @unittest.skipUnless(TORCH_AVAILABLE, "PyTorch required for neural autograd cycle")
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
        self.assertIn(f"FROM {self.mgr.base_model_tag}", modelfile_text)

        # Check ledger recorded event
        tail_events = [b["data"]["task"] for b in self.ledger.tail(10)]
        self.assertIn("lora_adapter_deployed", tail_events)

    @unittest.skipUnless(TORCH_AVAILABLE, "PyTorch required for neural autograd")
    def test_07_self_improvement_manager_automated_rollback(self):
        """When candidate adapter regresses on benchmark, candidate is rejected and rollback is recorded."""
        self.mgr.populate_seed_verified_dataset()

        # Simulate regression in benchmark suite
        def mock_regression_eval(adapter_weights=None, **kwargs):
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

    @unittest.skipUnless(TORCH_AVAILABLE, "PyTorch required for real benchmark evaluation")
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

    @unittest.skipUnless(TORCH_AVAILABLE, "PyTorch required for neural autograd")
    def test_07c_no_op_and_tiny_adapters_rejected(self):
        """Marhala 1 Task 3: Identity/No-Op adapters (B=0) and tiny non-improving adapters are strictly rejected."""
        self.mgr.populate_seed_verified_dataset()

        # Case 1: Identity / No-Op adapter (B == 0)
        orig_train = self.mgr.engine.train_on_verified_dataset
        def mock_noop_training(dataset, epochs=5, lr=0.015):
            rep = orig_train(dataset, epochs=epochs, lr=lr)
            # Force B to all zeros (no-op update)
            rep["tensors"]["layers.0.self_attn.q_proj.lora_B.weight"] = ([64, 8], [0.0] * 512)
            return rep

        self.mgr.engine.train_on_verified_dataset = mock_noop_training
        res_noop = self.mgr.run_training_and_deploy_cycle(epochs=2)
        self.assertFalse(res_noop["ok"])
        self.assertEqual(res_noop["action"], "ROLLED_BACK")
        self.assertIn("no-op", res_noop["reason"].lower())
        self.assertFalse(self.mgr.active_adapter_path.exists(), "No-op adapter must never be deployed")

        # Case 2: Tiny random adapter (B norm < 1e-4)
        def mock_tiny_training(dataset, epochs=5, lr=0.015):
            rep = orig_train(dataset, epochs=epochs, lr=lr)
            rep["tensors"]["layers.0.self_attn.q_proj.lora_B.weight"] = ([64, 8], [1e-6] * 512)
            return rep

        self.mgr.engine.train_on_verified_dataset = mock_tiny_training
        res_tiny = self.mgr.run_training_and_deploy_cycle(epochs=2)
        self.assertFalse(res_tiny["ok"])
        self.assertEqual(res_tiny["action"], "ROLLED_BACK")
        self.assertIn("no-op", res_tiny["reason"].lower())

    def test_07d_data_contamination_checker(self):
        """Marhala 1 Task 4: Data contamination checker detects overlap between training data and benchmark tasks."""
        bench_sample = self.mgr.benchmark_suite.get_benchmark_tasks(limit=5)
        # Clean training data
        clean_train = [
            {"prompt": "Write custom bubble sort", "solution": "def bubble_sort(): pass"},
            {"prompt": "Calculate factorial of 5", "solution": "120"},
        ]
        res_clean = DataContaminationChecker.detect_contamination(clean_train, bench_sample)
        self.assertFalse(res_clean["contaminated"])
        self.assertEqual(res_clean["violations_count"], 0)

        # Contaminated training data (exact prompt match)
        leaked_train = [
            {"prompt": bench_sample[0]["prompt"], "solution": "cheated solution"},
        ]
        res_leaked = DataContaminationChecker.detect_contamination(leaked_train, bench_sample)
        self.assertTrue(res_leaked["contaminated"])
        self.assertEqual(res_leaked["violations_count"], 1)

        # Contaminated training data via mgr cycle
        self.mgr.dataset_store.record_verified(
            bench_sample[0]["prompt"],
            "def leak(): pass",
            "CODE",
            {"verified": True},
        )
        res_cycle = self.mgr.run_training_and_deploy_cycle(epochs=1, eval_limit=5)
        self.assertFalse(res_cycle["ok"])
        self.assertEqual(res_cycle["status"], "REJECTED_DATA_CONTAMINATION")
        self.assertIn("contamination", res_cycle["reason"].lower())

    def test_07e_held_out_benchmark_corpus_and_pass_at_1(self):
        """Marhala 1 Task 1 & 2: 160 diverse held-out benchmark tasks with hidden tests and strict mandatory pass@1 generator."""
        corpus = generate_held_out_benchmark_corpus(160)
        self.assertEqual(len(corpus), 160)
        domains = set(t.get("domain") for t in corpus)
        self.assertEqual(len(domains), 8)

        # Ensure all tasks have hidden unit tests and DO NOT leak reference_solution in task dicts
        for t in corpus:
            self.assertIn("hidden_tests", t)
            self.assertTrue(len(t["hidden_tests"]) > 0)
            self.assertNotIn("reference_solution", t)

        suite = AdapterBenchmarkSuite(held_out_tasks=corpus)

        # 1. Missing generator_fn must strictly raise ValueError (cannot cheat with reference solutions)
        with self.assertRaises(ValueError) as ctx:
            suite.evaluate_pass_at_1(generator_fn=None, tasks=corpus[:5])
        self.assertIn("strictly mandatory", str(ctx.exception).lower())

        # 2. Real pass@1 evaluation with golden generator closure
        prompt_to_sol = {t["prompt"]: synthesize_verified_completion_for_task(t) for t in corpus[:10]}
        def golden_generator(prompt, **kwargs):
            return prompt_to_sol.get(prompt, "")

        res_pass1_golden = suite.evaluate_pass_at_1(generator_fn=golden_generator, tasks=corpus[:10])
        self.assertEqual(res_pass1_golden["pass_at_1"], 1.0)
        self.assertEqual(res_pass1_golden["passed_count"], 10)

        # 3. Real pass@1 evaluation with broken generator
        def broken_generator(prompt, **kwargs):
            return "def broken(): raise RuntimeError('syntax/logic fail')\n"

        res_pass1_broken = suite.evaluate_pass_at_1(generator_fn=broken_generator, tasks=corpus[:5])
        self.assertEqual(res_pass1_broken["pass_at_1"], 0.0)
        self.assertEqual(res_pass1_broken["passed_count"], 0)

    def test_07f_model_tag_collision_strictly_rejected(self):
        """Auditor Recheck Step 1: Baseline and Candidate must have strictly distinct model tags; collision raises MODEL_TAG_COLLISION."""
        corpus = generate_held_out_benchmark_corpus(10)
        suite = AdapterBenchmarkSuite(held_out_tasks=corpus)

        def gen_a(prompt, **kwargs):
            return "def f(): pass"

        def gen_b(prompt, **kwargs):
            return "def f(): pass"

        # Same model_tag -> raises MODEL_TAG_COLLISION
        with self.assertRaises(ValueError) as ctx1:
            suite.evaluate_paired_pass_at_1(
                base_generator_fn=gen_a,
                cand_generator_fn=gen_b,
                tasks=corpus[:5],
                base_model_tag="llama3.1:8b",
                cand_model_tag="llama3.1:8b",
                samples_per_task=5,
            )
        self.assertIn("MODEL_TAG_COLLISION", str(ctx1.exception))

        # Identical generator callable -> raises MODEL_TAG_COLLISION
        with self.assertRaises(ValueError) as ctx2:
            suite.evaluate_paired_pass_at_1(
                base_generator_fn=gen_a,
                cand_generator_fn=gen_a,
                tasks=corpus[:5],
                base_model_tag="llama3.1:8b",
                cand_model_tag="llama3.1:8b-cand-1",
                samples_per_task=5,
            )
        self.assertIn("MODEL_TAG_COLLISION", str(ctx2.exception))

        # Insufficient samples_per_task (< 5) -> raises INSUFFICIENT_SAMPLES_PER_TASK
        with self.assertRaises(ValueError) as ctx3:
            suite.evaluate_paired_pass_at_1(
                base_generator_fn=gen_a,
                cand_generator_fn=gen_b,
                tasks=corpus[:5],
                base_model_tag="llama3.1:8b",
                cand_model_tag="llama3.1:8b-cand-1",
                samples_per_task=2,
            )
        self.assertIn("INSUFFICIENT_SAMPLES_PER_TASK", str(ctx3.exception))

    def test_07g_shrinkage_adapter_rejected_by_paired_pass_at_1_gate(self):
        """Auditor Recheck Step 2: Rank-8 'shrink' adapter (Delta_W = -c*I) without task knowledge worsens cross-subspace loss and is strictly rejected by the pass@1 gate."""
        # Construct rank-8 shrinkage matrix: A reads first 8 coords, B scales them by -0.15
        # so (alpha/r) * B @ A = -0.15 * I_8 on the first 8 coords and 0 elsewhere
        a_mat = [[1.0 if i == j else 0.0 for j in range(64)] for i in range(8)]
        b_mat = [[-0.075 if i == j else 0.0 for j in range(8)] for i in range(64)]
        a_flat = [x for row in a_mat for x in row]
        b_flat = [x for row in b_mat for x in row]
        shrink_rep = {
            "ok": True,
            "epochs": 3,
            "initial_loss": 0.015625,
            "final_loss": 0.015977,
            "loss_reduction": -0.000352,
            "loss_history": [0.015625, 0.015977],
            "tensors": {
                "layers.0.self_attn.q_proj.lora_A.weight": ([8, 64], a_flat),
                "layers.0.self_attn.q_proj.lora_B.weight": ([64, 8], b_flat),
            },
        }

        # 1. Verify diagnostic cross-subspace loss is WORSENED (not improved) by shrinkage (works with or without PyTorch)
        base_diag = self.mgr.benchmark_suite.evaluate(adapter_weights=None)
        shrink_diag = self.mgr.benchmark_suite.evaluate(adapter_weights=shrink_rep)
        self.assertGreaterEqual(
            shrink_diag["avg_loss"],
            base_diag["avg_loss"],
            "Shrinkage adapter must NEVER reduce orthogonal cross-subspace loss",
        )

        # 2. Verify paired pass@1 with local tag generators rejects shrinkage adapter
        base_gen = self.mgr.create_model_generator(use_adapter=False, model_tag="llama3.1:8b")
        cand_gen = self.mgr.create_model_generator(use_adapter=True, adapter_weights=shrink_rep, model_tag="llama3.1:8b-cand-shrink")
        paired = self.mgr.benchmark_suite.evaluate_paired_pass_at_1(
            base_generator_fn=base_gen,
            cand_generator_fn=cand_gen,
            tasks=self.mgr.benchmark_suite.get_benchmark_tasks(limit=8),
            base_model_tag="llama3.1:8b",
            cand_model_tag="llama3.1:8b-cand-shrink",
            adapter_weights=shrink_rep,
            samples_per_task=5,
        )
        self.assertFalse(paired["gate_passed"], "Shrinkage adapter must NEVER pass the paired pass@1 bootstrap gate")
        self.assertLessEqual(paired["ci_lower_95"], 0.0)

        # 3. Verify full deploy cycle strictly rejects and rolls back the shrinkage adapter when PyTorch is available
        if TORCH_AVAILABLE:
            self.mgr.populate_seed_verified_dataset()
            self.mgr.engine.train_on_verified_dataset = lambda dataset, epochs=5, lr=0.035: shrink_rep
            res = self.mgr.run_training_and_deploy_cycle(epochs=3, eval_limit=8, samples_per_task=5)
            self.assertFalse(res["ok"])
            self.assertEqual(res["action"], "ROLLED_BACK")
            self.assertEqual(res["status"], "REJECTED_REGRESSION")
            self.assertFalse(self.mgr.active_adapter_path.exists())

    def test_07h_noisy_generator_rejected_by_paired_bootstrap_ci(self):
        """Auditor Recheck Step 2: Candidate that only beats baseline by tiny 1-sample sampling noise fails the 95% bootstrap CI gate."""
        corpus = generate_held_out_benchmark_corpus(8)
        suite = AdapterBenchmarkSuite(held_out_tasks=corpus)
        sol_0 = synthesize_verified_completion_for_task(corpus[0])

        def base_noisy(prompt, sample_idx=0, **kwargs):
            return "def fail(): return None"

        def cand_noisy(prompt, sample_idx=0, **kwargs):
            # Only passes 1 out of 5 samples on 1 out of 8 tasks by random luck (mean_delta = 0.025, but CI includes 0)
            if prompt == corpus[0]["prompt"] and sample_idx == 4:
                return sol_0
            return "def fail(): return None"

        paired = suite.evaluate_paired_pass_at_1(
            base_generator_fn=base_noisy,
            cand_generator_fn=cand_noisy,
            tasks=corpus,
            base_model_tag="llama3.1:8b",
            cand_model_tag="llama3.1:8b-cand-noisy",
            samples_per_task=5,
            bootstrap_resamples=1000,
        )
        self.assertGreater(paired["mean_delta"], 0.0)
        self.assertLessEqual(paired["ci_lower_95"], 0.0)
        self.assertFalse(paired["gate_passed"], "Sampling noise with ci_lower_95 <= 0 must be rejected")

    def test_07i_gguf_v3_lora_export_and_private_benchmark_isolation(self):
        """Auditor Recheck Step 1, 3, 4: Verifies spec-compliant GGUF v3 binary LoRA export and zero reference_solution/LeetCode leakage in benchmark_corpus.py."""
        gguf_test_path = self.data_dir / "test_adapter.gguf"
        GGUFLoRAExporter.save(
            file_path=gguf_test_path,
            tensors={
                "blk.0.attn_q.weight.lora_a": ([8, 64], [0.05] * 512),
                "blk.0.attn_q.weight.lora_b": ([64, 8], [0.02] * 512),
            },
            alpha=16.0,
            rank=8,
            arch="llama",
        )
        gguf_info = GGUFLoRAExporter.verify_gguf_header(gguf_test_path)
        self.assertTrue(gguf_info["valid"])
        self.assertEqual(gguf_info["magic"], "GGUF")
        self.assertEqual(gguf_info["version"], 3)
        self.assertEqual(gguf_info["metadata"]["general.type"], "adapter")
        self.assertEqual(gguf_info["metadata"]["adapter.type"], "lora")
        self.assertEqual(gguf_info["n_tensors"], 2)

        # Verify benchmark_corpus.py contains zero reference_solution dicts or standard LeetCode tasks
        corpus_src = Path("sovereign_mesh/benchmark_corpus.py").read_text(encoding="utf-8")
        self.assertNotIn('"reference_solution":', corpus_src)
        for leetcode_name in ("def two_sum", "def coin_change", "def roman_to_int", "def fizz_buzz"):
            self.assertNotIn(leetcode_name, corpus_src)

        if TORCH_AVAILABLE:
            res = self.mgr.run_training_and_deploy_cycle(epochs=3, eval_limit=6, samples_per_task=5)
            self.assertTrue(res["ok"])
            self.assertTrue(self.mgr.active_gguf_path.exists())
            self.assertNotEqual(res["base_model_tag"], res["deployed_model_tag"])

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
                data=json.dumps({"epochs": 3, "min_samples": 2}).encode("utf-8"),
                headers=auth_hdrs,
            )
            if TORCH_AVAILABLE:
                with urllib.request.urlopen(req_train, timeout=10) as resp_t:
                    t_data = json.loads(resp_t.read().decode("utf-8"))
                    self.assertTrue(t_data["ok"])
                    self.assertEqual(t_data["action"], "DEPLOYED")
                    self.assertIn("training_report", t_data)
            else:
                with self.assertRaises(urllib.error.HTTPError) as ctx_t:
                    urllib.request.urlopen(req_train, timeout=10)
                self.assertEqual(ctx_t.exception.code, 503)

        finally:
            srv.shutdown()
            srv.server_close()
            grid.stop()

    @unittest.skipUnless(TORCH_AVAILABLE, "PyTorch required for recursive_self_improvement cycle")
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
            res_rsi = grid.run_feature(888, "recursive_self_improvement", {"action": "cycle", "epochs": 4}, approved=True)
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

    def test_10_hf_peft_qlora_tiny_model_plumbing(self):
        """Marhala 2: Verifies HF PEFT save_pretrained -> GGUF conversion, pre-`ollama create` compatibility check, and tiny HF model QLoRA plumbing."""
        from sovereign_mesh.brain_matrix import SafeTensorsIO

        # 1. Verify toy NexusCausalTransformerLM is completely removed from production code
        qlora_src = Path("sovereign_mesh/qlora_engine.py").read_text(encoding="utf-8")
        self.assertNotIn("class NexusCausalTransformerLM", qlora_src)
        self.assertIn("AutoModelForCausalLM.from_pretrained", qlora_src)
        self.assertIn("get_peft_model", qlora_src)
        self.assertIn("BitsAndBytesConfig", qlora_src)
        self.assertIn("save_pretrained", qlora_src)

        # 2. Test PEFT save_pretrained directory -> GGUF conversion & compatibility validator (works even without GPU/torch)
        peft_dir = self.data_dir / "tiny_peft_dir"
        peft_dir.mkdir(parents=True, exist_ok=True)
        adapter_cfg = {
            "peft_type": "LORA",
            "task_type": "CAUSAL_LM",
            "base_model_name_or_path": "tiny-llama:64d-2l",
            "r": 8,
            "lora_alpha": 16.0,
            "target_modules": ["q_proj", "v_proj"],
            "hidden_size": 64,
            "num_hidden_layers": 2,
        }
        (peft_dir / "adapter_config.json").write_text(json.dumps(adapter_cfg, indent=2), encoding="utf-8")

        peft_tensors = {
            "base_model.model.model.layers.0.self_attn.q_proj.lora_A.weight": ([8, 64], [0.02] * 512),
            "base_model.model.model.layers.0.self_attn.q_proj.lora_B.weight": ([64, 8], [0.01] * 512),
            "base_model.model.model.layers.0.self_attn.v_proj.lora_A.weight": ([8, 64], [0.02] * 512),
            "base_model.model.model.layers.0.self_attn.v_proj.lora_B.weight": ([64, 8], [0.01] * 512),
            "base_model.model.model.layers.1.self_attn.q_proj.lora_A.weight": ([8, 64], [0.03] * 512),
            "base_model.model.model.layers.1.self_attn.q_proj.lora_B.weight": ([64, 8], [0.015] * 512),
            "base_model.model.model.layers.1.self_attn.v_proj.lora_A.weight": ([8, 64], [0.03] * 512),
            "base_model.model.model.layers.1.self_attn.v_proj.lora_B.weight": ([64, 8], [0.015] * 512),
        }
        SafeTensorsIO.save(
            peft_dir / "adapter_model.safetensors",
            peft_tensors,
            metadata={"format": "pt", "base_model": "tiny-llama:64d-2l"},
        )

        gguf_out = self.data_dir / "tiny_llama_lora.gguf"
        conv_res = PeftToGGUFConverter.convert_peft_to_gguf(
            peft_dir=peft_dir,
            gguf_out_path=gguf_out,
            base_model_tag="tiny-llama:64d-2l",
            hidden_size=64,
            num_hidden_layers=2,
        )
        self.assertTrue(conv_res["ok"])
        self.assertTrue(gguf_out.exists())
        self.assertEqual(conv_res["hidden_size"], 64)
        self.assertEqual(conv_res["num_hidden_layers"], 2)

        # 3. Pre-`ollama create` compatibility check:
        # 3a. Matching base model (`tiny-llama:64d-2l`: hidden_size=64, layers=2) -> PASSES
        compat_ok = AdapterModelCompatibilityValidator.validate(gguf_out, "tiny-llama:64d-2l")
        self.assertTrue(compat_ok["compatible"], f"Expected compatible=True, got {compat_ok}")

        # 3b. Mismatched base model (`llama3.1:8b`: hidden_size=4096, layers=32) -> IMMEDIATELY REJECTED
        compat_bad = AdapterModelCompatibilityValidator.validate(gguf_out, "llama3.1:8b")
        self.assertFalse(compat_bad["compatible"])
        self.assertIn("ADAPTER_MODEL_MISMATCH", compat_bad["reason"])

        # 3c. OllamaBackend.create_model immediately rejects incompatible Modelfile before network call
        bad_modelfile = (
            f"FROM llama3.1:8b\n"
            f"ADAPTER {gguf_out.as_posix()}\n"
        )
        ollama_reject = OllamaBackend("http://127.0.0.1:11434").create_model(
            model_tag="llama3.1:8b-bad-cand",
            modelfile_content=bad_modelfile,
        )
        self.assertFalse(ollama_reject["ok"])
        self.assertEqual(ollama_reject["status"], "REJECTED_INCOMPATIBLE_ADAPTER")
        self.assertIn("ADAPTER_MODEL_MISMATCH", ollama_reject["error"])

        # 3d. ContinuousSelfImprovementManager with base_model_tag="llama3.1:8b" rejects 64-dim adapter before `ollama create`
        if TORCH_AVAILABLE:
            mismatch_mgr = ContinuousSelfImprovementManager(
                self.data_dir / "mismatch_mgr",
                base_model_tag="llama3.1:8b",
            )
            mismatch_res = mismatch_mgr.run_training_and_deploy_cycle(epochs=2, min_samples=2, eval_limit=4)
            self.assertFalse(mismatch_res["ok"])
            self.assertEqual(mismatch_res["action"], "ROLLED_BACK")
            self.assertEqual(mismatch_res["status"], "REJECTED_INCOMPATIBLE_ADAPTER")
            self.assertIn("ADAPTER_MODEL_MISMATCH", mismatch_res["reason"])

        # 4. Full End-to-End HuggingFace AutoModelForCausalLM + PEFT LoraConfig + save_pretrained + GGUF test
        if is_hf_qlora_stack_ready():
            from transformers import LlamaConfig, LlamaForCausalLM

            hf_base_dir = self.data_dir / "hf_tiny_llama_base"
            hf_base_dir.mkdir(parents=True, exist_ok=True)
            tiny_cfg = LlamaConfig(
                vocab_size=256,
                hidden_size=64,
                intermediate_size=128,
                num_hidden_layers=2,
                num_attention_heads=4,
                num_key_value_heads=4,
                max_position_embeddings=128,
                pad_token_id=0,
                bos_token_id=1,
                eos_token_id=2,
            )
            tiny_model = LlamaForCausalLM(tiny_cfg)
            tiny_model.save_pretrained(str(hf_base_dir))

            engine = RealQLoRAEngine(
                model_dir=self.data_dir / "hf_qlora_out",
                rank=8,
                alpha=16.0,
                base_model_name_or_path=str(hf_base_dir),
                base_model_tag="tiny-llama:64d-2l",
            )
            hf_train_res = engine.train_hf_qlora(
                dataset=[
                    {"prompt": "def add(a, b):", "response": "    return a + b\n"},
                    {"prompt": "def mul(a, b):", "response": "    return a * b\n"},
                ],
                base_model_name_or_path=str(hf_base_dir),
                base_model_tag="tiny-llama:64d-2l",
                epochs=2,
                lr=1e-3,
                max_seq_len=64,
                peft_out_dir=self.data_dir / "hf_peft_saved",
                gguf_out_path=self.data_dir / "hf_peft_converted.gguf",
            )
            self.assertTrue(hf_train_res["ok"])
            self.assertTrue((self.data_dir / "hf_peft_saved" / "adapter_config.json").exists())
            self.assertTrue((self.data_dir / "hf_peft_saved" / "adapter_model.safetensors").exists())
            self.assertTrue((self.data_dir / "hf_peft_converted.gguf").exists())
            self.assertTrue(hf_train_res["compatibility_verification"]["compatible"])
            self.assertGreater(hf_train_res["trainable_lora_params"], 0)
            self.assertGreater(len(hf_train_res["tensors"]), 0)


if __name__ == "__main__":
    unittest.main()
