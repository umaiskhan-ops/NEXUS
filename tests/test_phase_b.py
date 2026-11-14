"""Phase B Comprehensive Verification Suite (NEXUS Sovereign Mesh).

Covers all Phase B deliverables and exit criteria:
- B2 (Darja 3) & B9: Adaptive reputation-scaled spot checking + verifier worker offloading.
- B10: Welcome credits vesting, spendable_credits() enforcement, collateral staking, device attestation.
- B11: Explicit worker reputation scoring & attributable proof-hash slashing (zero slash on timeout).
- Exit Criterion: Workers earn verified credits across brain_inference, model_query,
  neural_shard_compute, code_review + >= 99% red-team adversarial catch rate across 100 attacks.
- B13: Verified training curriculum generator (>= 5,000 samples, no 500 cap, 0 held-out contamination).
- B14: Model Garden single-vs-ensemble benchmark + Urdu & Roman Urdu suite (16 tasks).
- B15: DGM-lite self-improvement loop + immutable evaluator/gate tamper guard.
- B20: Telemetry snapshot, Prometheus exposition, WAL crash-restore drill, Owner HTTP auth & runbook/docs.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from sovereign_mesh.config import GridConfig
from sovereign_mesh.continuous_learning import (
    HELD_OUT_BENCHMARK_TASKS,
    AdapterBenchmarkSuite,
    ContinuousSelfImprovementManager,
    DataContaminationChecker,
)
from sovereign_mesh.grid import UltimateAgiSovereignGrid
from sovereign_mesh.hub_spoke import (
    MasterHubCoordinator,
    check_semantic_models_status,
    compute_hmac,
)
from sovereign_mesh.ledger import HashChainLedger
from sovereign_mesh.models import (
    URDU_ROMAN_URDU_BENCHMARK_TASKS,
    ModelGardenEvaluator,
)
from sovereign_mesh.security import hash_passphrase
from sovereign_mesh.server import make_handler


class _DeterministicMockBackend:
    def chat(self, model: str, system: str, prompt: str, timeout: float) -> str:
        return f"[{model}] {prompt[:40]}"

    def list_models(self, timeout: float = 3.0):
        return ["llama3.1:8b", "mistral:7b-instruct"]


def _sign_result(worker_rec, task: dict, result: dict) -> dict:
    proof = compute_hmac(
        worker_rec.key,
        {
            "task_id": task["task_id"],
            "worker_id": worker_rec.worker_id,
            "feature": task["feature"],
            "nonce": task["nonce"],
            "result": result,
        },
    )
    return {
        "task_id": task["task_id"],
        "worker_id": worker_rec.worker_id,
        "feature": task["feature"],
        "result": result,
        "worker_proof": proof,
    }


def _sign_attestation(worker_rec, gpu_uuid: str, tpm_quote_hash: str, puf_seal: str = "") -> dict:
    eff_puf = puf_seal or worker_rec.puf_seal or ""
    quote_body = {
        "worker_id": worker_rec.worker_id,
        "gpu_uuid": gpu_uuid,
        "tpm_quote_hash": tpm_quote_hash,
        "puf_seal": eff_puf,
    }
    return {
        "gpu_uuid": gpu_uuid,
        "tpm_quote_hash": tpm_quote_hash,
        "puf_seal": eff_puf,
        "signature": compute_hmac(worker_rec.key, quote_body),
    }


class PhaseBSuiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="nexus_phase_b_")
        self.data_dir = Path(self.tmp_dir)
        self.pw_hash = hash_passphrase("PhaseBSecure2026!")
        self.backend = _DeterministicMockBackend()
        self.config = GridConfig(
            owner_telegram_id=919293,
            master_passphrase_hash=self.pw_hash,
            data_dir=self.data_dir,
            dashboard_token="phase-b-owner-token",
            enable_code_execution=True,
            simulate_offline_consensus=False,
            token_budget=1_000_000,
        )
        self.grid = UltimateAgiSovereignGrid(self.config, backend=self.backend)
        self.hub: MasterHubCoordinator = self.grid.hub

    def tearDown(self):
        self.grid.stop()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # B2 (Darja 3) & B9: Adaptive Spot Checking + Verifier Offloading
    # ------------------------------------------------------------------
    def test_01_adaptive_spot_checking_and_verifier_offload(self):
        prob_w = self.hub.register_worker(
            "prob-worker", url="local", public_ip="198.51.100.10", initial_credits=100, hardware_uuid="hw-prob-1"
        )
        self.assertEqual(self.hub.compute_effective_spot_check_rate(prob_w), 1.0)

        # High-reputation independent verifier on distinct /24 subnet
        ver_w = self.hub.register_worker(
            "trusted-verifier", url="local", public_ip="203.0.113.20", initial_credits=100, hardware_uuid="hw-ver-2"
        )
        ver_w.tasks_verified = 12
        ver_w.reputation_score = 0.92
        ver_w.canary_strikes = 0
        ver_w.tasks_rejected = 0

        eff_rate = self.hub.compute_effective_spot_check_rate(ver_w)
        self.assertGreaterEqual(eff_rate, 0.05)
        self.assertLessEqual(eff_rate, 0.25)

        # Same-/24 neighbor must NOT qualify as independent verifier if no distinct-/24 exists
        solo_hub = MasterHubCoordinator(
            HashChainLedger(self.data_dir / "solo_ledger.jsonl"),
            state_path=self.data_dir / "solo_hub.json",
        )
        try:
            solo_target = solo_hub.register_worker("solo-t", public_ip="198.51.100.10", initial_credits=50, hardware_uuid="hw-s1")
            same_sub = solo_hub.register_worker("same-sub-v", public_ip="198.51.100.55", initial_credits=50, hardware_uuid="hw-s2")
            same_sub.tasks_verified = 15
            same_sub.reputation_score = 0.95
            self.assertIsNone(
                solo_hub.dispatch_verifier_task(
                    solo_target.worker_id, "t-none", "data_analysis", {"numbers": [1, 2, 3]}, {"sum": 6}
                )
            )
        finally:
            solo_hub.stop()

        # Dispatch real spot-check offload for a falsified data_analysis result to trusted-verifier
        bad_payload = {"numbers": [10, 20, 30]}
        tampered_res = {"count": 3, "sum": 9999, "mean": 3333.0, "min": 10, "max": 30}
        v_pkt = self.hub.dispatch_verifier_task(
            target_worker_id=prob_w.worker_id,
            original_task_id="orig-task-77",
            feature_key="data_analysis",
            payload=bad_payload,
            submitted_result=tampered_res,
            submitted_sig="sig_prefix_deadbeef",
        )
        self.assertIsNotNone(v_pkt)
        self.assertEqual(v_pkt["feature"], "verifier_spot_check")
        self.assertEqual(v_pkt["worker_id"], ver_w.worker_id)

        ver_submission = _sign_result(
            ver_w,
            v_pkt,
            {"verified_match": False, "audit_notes": "sum mismatch: expected 60 got 9999"},
        )
        v_settled = self.hub.verify_and_settle(ver_submission)
        self.assertTrue(v_settled["ok"], f"Verifier settlement failed: {v_settled}")
        self.assertEqual(self.hub.get_worker(ver_w.worker_id).verifier_checks_completed, 1)

        # Target worker must now be SLASHED with attributable ledger proof
        slashed_target = self.hub.get_worker(prob_w.worker_id)
        self.assertEqual(slashed_target.status, "SLASHED")
        self.assertGreaterEqual(slashed_target.attributable_slashes, 1)

    # ------------------------------------------------------------------
    # B10 & B11: Welcome Vesting, Collateral Stake, Device Attestation, Attributable Slash
    # ------------------------------------------------------------------
    def test_02_welcome_vesting_collateral_attestation_and_reputation(self):
        buyer = self.hub.register_worker(
            "buyer-funder", url="local", public_ip="198.51.100.1", initial_credits=500, hardware_uuid="hw-buyer"
        )
        new_w = self.hub.register_worker(
            "new-sybil-candidate", url="local", public_ip="203.0.113.50", hardware_uuid="hw-new-1"
        )
        peer_w = self.hub.register_worker(
            "peer-receiver", url="local", public_ip="192.0.2.50", hardware_uuid="hw-peer-2"
        )

        # Default welcome bonus (20) is locked until progressive vesting
        self.assertEqual(new_w.credits, 20)
        self.assertEqual(new_w.welcome_credits_locked, 20)
        self.assertEqual(new_w.spendable_credits(), 0)

        with self.assertRaises(PermissionError):
            self.hub.transfer_credits(new_w.worker_id, peer_w.worker_id, 5)
        unvested_spend = self.hub.spend_credits(new_w.worker_id, 5, reason="unvested_drain_attempt")
        self.assertEqual(unvested_spend.get("status"), "INSUFFICIENT_SPENDABLE_CREDITS")

        # B11: Mere timeout / task expiration MUST NOT slash worker (0 attributable_slashes)
        timeout_task = self.hub.create_signed_task(
            new_w.worker_id,
            "brain_inference",
            {"prompt": "Timeout probe"},
            funded_by=buyer.worker_id,
            funded_credits=10,
        )
        self.hub._pending[timeout_task["task_id"]]["issued_at"] = time.time() - 9999.0
        self.hub.prune_expired_tasks()
        self.assertNotIn(timeout_task["task_id"], self.hub._pending)
        self.assertEqual(buyer.credits, 500)
        self.assertEqual(new_w.status, "ACTIVE")
        self.assertEqual(new_w.attributable_slashes, 0)

        # Complete 1 verified task -> unlocks 5 credits of welcome bonus
        task1 = self.hub.create_signed_task(
            new_w.worker_id,
            "brain_inference",
            {"prompt": "Write dbl(x)", "test_assertions": "assert dbl(3) == 6\nassert dbl(0) == 0"},
        )
        settle1 = self.hub.verify_and_settle(
            _sign_result(new_w, task1, {"status": "OK", "output": "def dbl(x):\n    return x * 2"})
        )
        self.assertTrue(settle1["ok"], f"settle1 failed: {settle1}")
        self.assertTrue(settle1["verified"])
        self.assertEqual(new_w.welcome_credits_locked, 15)
        self.assertGreaterEqual(new_w.spendable_credits(), 5)

        # Grant verified credits (spendable), test collateral staking & device attestation
        self.hub.grant_credits(new_w.worker_id, 50, reason="test_grant")
        stake_res = self.hub.stake_worker_collateral(new_w.worker_id, 25)
        self.assertTrue(stake_res["ok"])
        self.assertEqual(new_w.staked_collateral, 25)
        rep_after_stake = new_w.reputation_score

        # Bad attestation signature rejected
        bad_att = self.hub.verify_device_attestation(
            new_w.worker_id,
            {"gpu_uuid": "GPU-1234", "tpm_quote_hash": "abc", "signature": "0" * 64},
        )
        self.assertFalse(bad_att["ok"])

        # Valid HMAC device attestation accepted and boosts reputation
        good_att_payload = _sign_attestation(new_w, gpu_uuid="GPU-RTX4090-XYZ", tpm_quote_hash="tpm-sha256-999")
        good_att = self.hub.verify_device_attestation(new_w.worker_id, good_att_payload)
        self.assertTrue(good_att["ok"])
        self.assertTrue(new_w.device_attestation["verified"])
        self.assertGreater(new_w.reputation_score, rep_after_stake)

        # Attributable slashing burns both liquid credits and staked collateral, resets reputation to 0.0
        slash_res = self.hub.slash_worker(
            new_w.worker_id,
            reason="proven_equivocation",
            attributable_proof={"task_id": "t-eq-1", "evidence": "signed_conflicting_digests"},
        )
        self.assertEqual(slash_res["status"], "SLASHED")
        self.assertTrue(slash_res.get("attributable_proof_hash"))
        self.assertEqual(new_w.staked_collateral, 0)
        self.assertEqual(new_w.credits, 0)
        self.assertEqual(new_w.reputation_score, 0.0)
        self.assertEqual(new_w.attributable_slashes, 1)

        # Ledger contains attributable slash proof hash
        slash_blocks = [
            b for b in self.grid.ledger.range(0, len(self.grid.ledger))
            if b["data"].get("task") == "worker_slashed"
        ]
        self.assertTrue(any(b["data"]["payload"].get("attributable_proof_hash") == slash_res["attributable_proof_hash"] for b in slash_blocks))
        self.assertEqual(buyer.credits, 500)

    # ------------------------------------------------------------------
    # Exit Criteria: Honest LLM Earnings + >=99% Red-Team Catch Rate (100 attacks)
    # ------------------------------------------------------------------
    def test_03_honest_llm_earnings_and_red_team_100_submissions(self):
        buyer = self.hub.register_worker(
            "llm-buyer", url="local", public_ip="192.0.2.10", initial_credits=2000, hardware_uuid="hw-llm-buyer"
        )
        hw1 = self.hub.register_worker(
            "honest-llm-1", url="local", public_ip="198.51.100.41", initial_credits=100, hardware_uuid="hw-llm-1"
        )
        hw2 = self.hub.register_worker(
            "honest-llm-2", url="local", public_ip="203.0.113.42", initial_credits=100, hardware_uuid="hw-llm-2"
        )
        self.assertEqual(buyer.spendable_credits(), 2000)

        # Part A: Honest workers earn verified credits on brain_inference, model_query,
        # neural_shard_compute, and code_review via paired consensus with objective verifiers.
        llm_cases = [
            (
                "brain_inference",
                {"prompt": "Write add_two(x, y)", "test_assertions": "assert add_two(2, 3) == 5\nassert add_two(-1, 1) == 0", "consensus_id": "hon-bi-1"},
                {"status": "OK", "output": "def add_two(x, y):\n    return x + y"},
            ),
            (
                "model_query",
                {"prompt": "Compute (18 * 4) + 8", "expected_value": 80, "consensus_id": "hon-mq-1"},
                {"status": "OK", "output": "80"},
            ),
            (
                "neural_shard_compute",
                {"prompt": "Emit JSON health report", "required_keys": ["node:str", "healthy:bool", "score:int>=0"], "consensus_id": "hon-ns-1"},
                {"status": "OK", "output": '{"node": "shard-7", "healthy": true, "score": 98}'},
            ),
            (
                "code_review",
                {"prompt": "Write safe_div(a, b)", "test_assertions": "assert safe_div(10, 2) == 5\nassert safe_div(10, 0) == 0", "consensus_id": "hon-cr-1"},
                {"status": "OK", "output": "def safe_div(a, b):\n    return 0 if b == 0 else a / b"},
            ),
        ]

        start_c1, start_c2 = hw1.credits, hw2.credits
        for idx, (feat, pay, good_out) in enumerate(llm_cases):
            # Tasks with objective validators (test_assertions, expected_math, required_keys) settle immediately on verification
            pay_single_1 = {k: v for k, v in pay.items() if k != "consensus_id"}
            pay_single_2 = {k: v for k, v in pay.items() if k != "consensus_id"}
            t1 = self.hub.create_signed_task(hw1.worker_id, feat, pay_single_1, funded_by=buyer.worker_id, funded_credits=20)
            t2 = self.hub.create_signed_task(hw2.worker_id, feat, pay_single_2, funded_by=buyer.worker_id, funded_credits=20)
            s1 = self.hub.verify_and_settle(_sign_result(hw1, t1, good_out))
            s2 = self.hub.verify_and_settle(_sign_result(hw2, t2, good_out))
            self.assertTrue(s1["ok"], f"{feat} leg 1 failed: {s1}")
            self.assertEqual(s1["status"], "SETTLED", f"{feat} leg 1 did not settle: {s1}")
            self.assertTrue(s2["ok"], f"{feat} leg 2 failed: {s2}")
            self.assertEqual(s2["status"], "SETTLED", f"{feat} leg 2 did not settle: {s2}")

        if check_semantic_models_status()["active"]:
            # Also verify free-form semantic consensus settles honest independent paraphrases
            c_prompt = "Why does solid ice float on liquid water?"
            tp1 = self.hub.create_signed_task(hw1.worker_id, "brain_inference", {"prompt": c_prompt, "consensus_id": "hon-sem-1"}, funded_by=buyer.worker_id, funded_credits=20)
            tp2 = self.hub.create_signed_task(hw2.worker_id, "brain_inference", {"prompt": c_prompt, "consensus_id": "hon-sem-1"}, funded_by=buyer.worker_id, funded_credits=20)
            sp1 = self.hub.verify_and_settle(_sign_result(hw1, tp1, {"status": "OK", "output": "Ice floats on liquid water because hydrogen bonds hold water molecules in an open crystalline lattice that is less dense than liquid water."}))
            sp2 = self.hub.verify_and_settle(_sign_result(hw2, tp2, {"status": "OK", "output": "Solid ice has lower density than liquid water because freezing forms an expanded hydrogen-bonded hexagonal structure with more space between molecules."}))
            self.assertEqual(sp1["status"], "PENDING_CONSENSUS")
            self.assertEqual(sp2["status"], "SETTLED")

        self.assertGreater(hw1.credits, start_c1)
        self.assertGreater(hw2.credits, start_c2)
        self.assertEqual(hw1.credits - start_c1, hw2.credits - start_c2)

        # Part B: 100 Adversarial Red-Team Submissions across 6 attack classes
        attack_results = []
        illicit_mints = 0

        def _record_attack(label: str, sub: dict, target_worker=None):
            nonlocal illicit_mints
            before = target_worker.credits if target_worker is not None else 0
            try:
                res = self.hub.verify_and_settle(sub)
                caught = (not res.get("ok")) or (res.get("status") in {"REJECTED", "SLASHED", "REJECTED_INELIGIBLE"})
                if res.get("ok") and res.get("status") == "SETTLED":
                    caught = False
            except (PermissionError, ValueError, KeyError):
                caught = True
                res = {"ok": False, "status": "EXCEPTION_CAUGHT"}
            after = target_worker.credits if target_worker is not None else 0
            if after > before:
                illicit_mints += (after - before)
                caught = False
            attack_results.append((label, caught, res.get("status")))

        # Group 1 (20 attacks): Wrong math answers on funded model_query consensus pairs
        for i in range(20):
            atk = self.hub.register_worker(f"rt-math-{i}", public_ip=f"198.51.{(i % 200) + 1}.5", initial_credits=100, hardware_uuid=f"hw-rt-m-{i}")
            t = self.hub.create_signed_task(
                atk.worker_id,
                "model_query",
                {"prompt": f"What is {10 + i} * 7?", "expected_value": (10 + i) * 7, "consensus_id": f"rt-math-c-{i}"},
                funded_by=buyer.worker_id,
                funded_credits=10,
            )
            _record_attack("wrong_math", _sign_result(atk, t, {"status": "OK", "output": "999999"}), atk)

        # Group 2 (20 attacks): Failing code_review / brain_inference test_assertions
        for i in range(20):
            feat = "code_review" if i % 2 == 0 else "brain_inference"
            atk = self.hub.register_worker(f"rt-code-{i}", public_ip=f"203.0.{(i % 200) + 1}.5", initial_credits=100, hardware_uuid=f"hw-rt-c-{i}")
            t = self.hub.create_signed_task(
                atk.worker_id,
                feat,
                {"prompt": "Write sq(n)", "test_assertions": "assert sq(4) == 16\nassert sq(5) == 25", "consensus_id": f"rt-code-c-{i}"},
                funded_by=buyer.worker_id,
                funded_credits=10,
            )
            _record_attack("failing_code", _sign_result(atk, t, {"status": "OK", "output": "def sq(n):\n    return n + 1"}), atk)

        # Group 3 (15 attacks): Malformed JSON schema on neural_shard_compute
        for i in range(15):
            atk = self.hub.register_worker(f"rt-schema-{i}", public_ip=f"192.0.{(i % 200) + 2}.5", initial_credits=100, hardware_uuid=f"hw-rt-s-{i}")
            t = self.hub.create_signed_task(
                atk.worker_id,
                "neural_shard_compute",
                {"prompt": "Emit JSON", "required_keys": ["id:str", "valid:bool", "count:int>=0"], "consensus_id": f"rt-schema-c-{i}"},
                funded_by=buyer.worker_id,
                funded_credits=10,
            )
            _record_attack("bad_schema", _sign_result(atk, t, {"status": "OK", "output": '{"id": 123, "count": -5}'}), atk)

        # Group 4 (15 attacks): Forged HMAC signatures on real tasks
        for i in range(15):
            atk = self.hub.register_worker(f"rt-sig-{i}", public_ip=f"198.18.{(i % 200) + 1}.5", initial_credits=100, hardware_uuid=f"hw-rt-sig-{i}")
            t = self.hub.create_signed_task(atk.worker_id, "brain_inference", {"prompt": "Explain gravity"})
            _record_attack(
                "forged_hmac",
                {
                    "task_id": t["task_id"],
                    "worker_id": atk.worker_id,
                    "feature": "brain_inference",
                    "result": {"status": "OK", "output": "Gravity curves spacetime."},
                    "worker_proof": "deadbeef" * 8,
                },
                atk,
            )

        # Group 5 (15 attacks): Invented non-existent task IDs / unauthorized credit minting
        for i in range(15):
            atk = self.hub.register_worker(f"rt-fakeid-{i}", public_ip=f"198.19.{(i % 200) + 1}.5", initial_credits=100, hardware_uuid=f"hw-rt-fid-{i}")
            _record_attack(
                "invented_task",
                {
                    "task_id": f"invented-fake-task-{i}",
                    "worker_id": atk.worker_id,
                    "feature": "brain_inference",
                    "result": {"status": "OK", "output": "Fabricated claim"},
                    "worker_proof": "0" * 64,
                },
                atk,
            )

        # Group 6 (15 attacks): Same-/24 Sybil collusion across 15 distinct /24 pairs
        for i in range(15):
            syb_a = self.hub.register_worker(f"rt-syb-a-{i}", public_ip=f"198.51.{210 + i}.10", initial_credits=100, hardware_uuid=f"hw-rt-syba-{i}")
            syb_b = self.hub.register_worker(f"rt-syb-b-{i}", public_ip=f"198.51.{210 + i}.50", initial_credits=100, hardware_uuid=f"hw-rt-sybb-{i}")
            c_id = f"rt-syb-c-{i}"
            prompt = f"Explain how packet switching works in computer networks ({i})."
            t_a = self.hub.create_signed_task(syb_a.worker_id, "brain_inference", {"prompt": prompt, "consensus_id": c_id}, funded_by=buyer.worker_id, funded_credits=10)
            t_b = self.hub.create_signed_task(syb_b.worker_id, "brain_inference", {"prompt": prompt, "consensus_id": c_id}, funded_by=buyer.worker_id, funded_credits=10)
            collude_out = "packet switching breaks data into independent packets routed across shared links."
            self.hub.verify_and_settle(_sign_result(syb_a, t_a, {"status": "OK", "output": collude_out}))
            # Second worker in SAME /24 must be rejected on collusion!
            _record_attack("same_subnet_sybil", _sign_result(syb_b, t_b, {"status": "OK", "output": collude_out}), syb_b)

        self.assertEqual(len(attack_results), 100)
        caught_count = sum(1 for _, ok, _ in attack_results if ok)
        catch_rate = caught_count / float(len(attack_results))
        self.assertEqual(illicit_mints, 0, f"Illicit credits minted to red-team attackers: {illicit_mints}")
        self.assertGreaterEqual(catch_rate, 0.99, f"Catch rate {catch_rate:.2%} below 99%: {[r for r in attack_results if not r[1]]}")

    # ------------------------------------------------------------------
    # B13: 5,000+ Verified Training Curriculum & Zero Contamination
    # ------------------------------------------------------------------
    def test_04_curriculum_generator_5000_samples_zero_contamination(self):
        cl: ContinuousSelfImprovementManager = self.grid.continuous_learning
        res = cl.generate_verified_curriculum(target_count=5050, seed=42)
        self.assertTrue(res["ok"], f"Curriculum generation failed: {res}")
        self.assertGreaterEqual(res["total_verified_samples"], 5050)
        self.assertEqual(res["contamination_violations"], 0)
        self.assertEqual(res["status"], "CURRICULUM_GENERATED")

        # Verify VerifiedDatasetStore.count() and list_verified(limit=None) have no 500-sample cap
        self.assertGreaterEqual(cl.dataset_store.count(), 5050)
        all_rows = cl.dataset_store.list_verified(limit=None)
        self.assertGreaterEqual(len(all_rows), 5050)

        # Double-check independently via DataContaminationChecker against held-out tasks
        chk = DataContaminationChecker.detect_contamination(all_rows, HELD_OUT_BENCHMARK_TASKS)
        self.assertFalse(chk["contaminated"], f"Contamination detected: {chk}")
        self.assertEqual(chk["violations_count"], 0)

    # ------------------------------------------------------------------
    # B14: Model Garden Evaluation & Urdu / Roman Urdu Suite
    # ------------------------------------------------------------------
    def test_05_model_garden_evaluator_and_urdu_suite(self):
        self.assertEqual(len(URDU_ROMAN_URDU_BENCHMARK_TASKS), 16)
        self.assertEqual(sum(1 for t in URDU_ROMAN_URDU_BENCHMARK_TASKS if t["script"] == "roman_urdu"), 8)
        self.assertEqual(sum(1 for t in URDU_ROMAN_URDU_BENCHMARK_TASKS if t["script"] == "urdu_script"), 8)

        # Deterministic reference answers for the 16 Urdu/Roman Urdu tasks
        solutions = {
            "ur_rom_01": "def urdu_hisab_jama(a, b):\n    return a + b",
            "ur_rom_02": "def karaya_total(fasla_km, rate):\n    return fasla_km * rate if fasla_km > 0 else 0",
            "ur_rom_03": "def chota_lafz(alfaz):\n    return min(len(w) for w in alfaz) if alfaz else 0",
            "ur_rom_04": "39",
            "ur_rom_05": "110",
            "ur_rom_06": '{"naam": "Ali", "umar": 21, "paas": true}',
            "ur_rom_07": '{"shehar": "Lahore", "darja_hararat": 28, "barish": false}',
            "ur_rom_08": "def even_ginti(nums):\n    return sum(1 for x in nums if x % 2 == 0)",
            "ur_scr_01": "def urdu_zarb(x, y):\n    return x * y",
            "ur_scr_02": "def ausat_nikalo(a, b, c):\n    return (a + b + c) / 3",
            "ur_scr_03": "def sab_se_bara(lst):\n    return max(lst) if lst else 0",
            "ur_scr_04": "110",
            "ur_scr_05": "240",
            "ur_scr_06": '{"worker_name": "node-pk", "credits": 50, "active": true}',
            "ur_scr_07": '{"node_city": "Karachi", "latency_ms": 18, "verified": true}',
            "ur_scr_08": "def manfi_hatao(nums):\n    return sum(x for x in nums if x > 0)",
        }

        def _match_task_id(prompt: str) -> str:
            for t in URDU_ROMAN_URDU_BENCHMARK_TASKS:
                if t["prompt"] == prompt:
                    return t["id"]
            return ""

        # Simulate 3 complementary specialized models where ensemble beats every single model
        def _model_alpha(prompt: str) -> str:
            tid = _match_task_id(prompt)
            return solutions[tid] if tid in {"ur_rom_01", "ur_rom_02", "ur_rom_03"} else "wrong"

        def _model_beta(prompt: str) -> str:
            tid = _match_task_id(prompt)
            return solutions[tid] if tid in {"ur_rom_04", "ur_rom_05"} else "wrong"

        def _model_gamma(prompt: str) -> str:
            tid = _match_task_id(prompt)
            return solutions[tid] if tid in {"ur_rom_06", "ur_rom_07", "ur_rom_08"} else "wrong"

        evaluator = ModelGardenEvaluator()
        garden = evaluator.evaluate_single_vs_ensemble(
            self.grid.router,
            tasks=URDU_ROMAN_URDU_BENCHMARK_TASKS[:8],
            model_callables={"alpha": _model_alpha, "beta": _model_beta, "gamma": _model_gamma},
        )
        self.assertTrue(garden["ok"])
        self.assertEqual(garden["tasks_evaluated"], 8)
        self.assertLess(garden["best_single_pass_at_1"], 1.0)
        self.assertEqual(garden["debate_pass_at_1"], 1.0)
        self.assertGreater(garden["ensemble_gain_over_best_single"], 0.0)

        # Full 16-task Urdu & Roman Urdu breakdown
        urdu_res = evaluator.evaluate_urdu_suite(
            callable_fn=lambda p: solutions.get(_match_task_id(p), ""),
        )
        self.assertTrue(urdu_res["ok"])
        self.assertEqual(urdu_res["total_tasks"], 16)
        self.assertEqual(urdu_res["roman_urdu_total"], 8)
        self.assertEqual(urdu_res["urdu_script_total"], 8)
        self.assertEqual(urdu_res["overall_pass_at_1"], 1.0)

    # ------------------------------------------------------------------
    # B15: DGM Self-Improvement Loop & Immutable Evaluator Tamper Guard
    # ------------------------------------------------------------------
    def test_06_dgm_evolution_and_immutable_evaluator_guard(self):
        dgm = self.grid.continuous_learning.dgm_loop

        # 1. Default deterministic scaffold cycle shows genuine paired improvement & promotes candidate
        evo = dgm.run_evolution_cycle(samples_per_task=5, min_improvement_margin=0.05)
        self.assertTrue(evo["ok"])
        self.assertTrue(evo["promoted"])
        self.assertTrue(evo["paired_gate"]["gate_passed"])
        self.assertGreater(evo["paired_gate"]["candidate_pass_at_1"], evo["paired_gate"]["baseline_pass_at_1"])
        self.assertEqual(evo["active_scaffold_id"], evo["candidate_scaffold"]["scaffold_id"])
        self.assertTrue(dgm.archive_path.exists())

        # 2. Candidate regression must NOT be promoted
        prev_active = dgm.get_active_scaffold()["scaffold_id"]
        def _regress_factory(scaffold: dict):
            sid = str(scaffold.get("scaffold_id", ""))
            is_parent = (sid == prev_active)
            from sovereign_mesh.continuous_learning import synthesize_verified_completion_for_task
            code_tasks = {t["prompt"]: t for t in self.grid.continuous_learning.benchmark_suite.get_benchmark_tasks(category="CODE", limit=10)}
            def _fn(prompt: str, **kwargs) -> str:
                return synthesize_verified_completion_for_task(code_tasks[prompt]) if is_parent else ""
            _fn.model_tag = sid
            return _fn

        evo_bad = dgm.run_evolution_cycle(
            eval_tasks=self.grid.continuous_learning.benchmark_suite.get_benchmark_tasks(category="CODE", limit=10),
            runner_factory=_regress_factory,
            samples_per_task=5,
            min_improvement_margin=0.02,
        )
        self.assertTrue(evo_bad["ok"])
        self.assertFalse(evo_bad["promoted"])
        self.assertEqual(evo_bad["active_scaffold_id"], prev_active)

        # 3. Runtime tampering with evaluate_paired_pass_at_1 MUST raise IMMUTABLE_EVALUATOR_TAMPER_DETECTED
        orig_method = AdapterBenchmarkSuite.evaluate_paired_pass_at_1
        try:
            def _tampered_gate(self_arg, *args, **kwargs):
                return {"gate_passed": True}

            AdapterBenchmarkSuite.evaluate_paired_pass_at_1 = _tampered_gate  # type: ignore[method-assign]
            with self.assertRaises(PermissionError) as ctx:
                dgm.verify_evaluator_immutability()
            self.assertIn("IMMUTABLE_EVALUATOR_TAMPER_DETECTED", str(ctx.exception))
            with self.assertRaises(PermissionError):
                dgm.run_evolution_cycle(samples_per_task=5)
        finally:
            AdapterBenchmarkSuite.evaluate_paired_pass_at_1 = orig_method  # type: ignore[method-assign]

        # Restored -> clean again
        self.assertTrue(dgm.verify_evaluator_immutability()["ok"])

    # ------------------------------------------------------------------
    # B20: Observability HTTP Metrics, WAL Drill, Owner Auth & Docs Parity
    # ------------------------------------------------------------------
    def test_07_observability_http_endpoints_wal_drill_and_docs(self):
        # Register a worker so WAL drill & metrics have live state
        w = self.hub.register_worker("obs-worker-1", url="local", public_ip="198.51.100.77", initial_credits=120)
        self.hub.stake_worker_collateral(w.worker_id, 30)

        self.grid.start()
        srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.grid, None))
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            base = f"http://127.0.0.1:{port}"
            auth_hdrs = {"X-Dashboard-Token": "phase-b-owner-token", "Content-Type": "application/json"}

            # 1. Verify strict 401 without Owner token across all 5 new Phase B endpoints
            unauth_cases = [
                ("GET", "/api/metrics", None),
                ("POST", "/api/learning/generate_curriculum", {"target_count": 20, "seed": 1}),
                ("POST", "/api/learning/dgm_cycle", {"samples_per_task": 5}),
                ("POST", "/api/models/evaluate_garden", {}),
                ("POST", "/api/hub/wal_drill", {}),
            ]
            for method, path, body in unauth_cases:
                req = urllib.request.Request(
                    f"{base}{path}",
                    data=(json.dumps(body).encode("utf-8") if method == "POST" else None),
                    headers={"Content-Type": "application/json"},
                    method=method,
                )
                with self.assertRaises(urllib.error.HTTPError, msg=f"Expected 401 for unauth {method} {path}") as ctx:
                    urllib.request.urlopen(req, timeout=5)
                self.assertEqual(ctx.exception.code, 401, f"Route {path} did not return 401")

            # 2. POST /api/hub/wal_drill (Owner auth) -> verifies 100% WAL & ledger crash-restore parity
            req_drill = urllib.request.Request(
                f"{base}/api/hub/wal_drill",
                data=b"{}",
                headers=auth_hdrs,
                method="POST",
            )
            with urllib.request.urlopen(req_drill, timeout=10) as resp:
                drill = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(drill["ok"], f"WAL drill failed: {drill}")
            self.assertTrue(drill["restored_ok"])
            self.assertTrue(drill["ledger_intact"])
            self.assertEqual(drill["balance_mismatches"], [])

            # 3. GET /api/metrics (JSON)
            req_metrics = urllib.request.Request(f"{base}/api/metrics", headers=auth_hdrs)
            with urllib.request.urlopen(req_metrics, timeout=5) as resp:
                snap = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(snap["ok"])
            self.assertIn("p50", snap["latency_seconds"])
            self.assertIn("p95", snap["latency_seconds"])
            self.assertIn("p99", snap["latency_seconds"])
            self.assertGreaterEqual(snap["latency_seconds"]["count"], 5)
            self.assertEqual(snap["economy"]["staked_collateral_credits"], 30)
            self.assertTrue(snap["ledger"]["intact"])
            self.assertIsNotNone(snap["last_wal_drill"])

            # 4. GET /api/metrics?format=prometheus
            req_prom = urllib.request.Request(f"{base}/api/metrics?format=prometheus", headers=auth_hdrs)
            with urllib.request.urlopen(req_prom, timeout=5) as resp:
                ctype = resp.headers.get("Content-Type", "")
                prom_text = resp.read().decode("utf-8")
            self.assertIn("text/plain", ctype)
            self.assertIn("nexus_uptime_seconds", prom_text)
            self.assertIn("nexus_credits_staked", prom_text)
            self.assertIn("nexus_http_latency_p95_seconds", prom_text)
            self.assertIn("nexus_ledger_intact 1", prom_text)

            # 5. Documentation & Runbook parity check
            route_doc = (Path(__file__).resolve().parent.parent / "docs" / "API_ROUTE_PERMISSIONS.md").read_text(encoding="utf-8")
            for route in [
                "/api/metrics",
                "/api/learning/generate_curriculum",
                "/api/learning/dgm_cycle",
                "/api/models/evaluate_garden",
                "/api/hub/wal_drill",
            ]:
                self.assertIn(route, route_doc, f"Route {route} missing from docs/API_ROUTE_PERMISSIONS.md")
            runbook_path = Path(__file__).resolve().parent.parent / "docs" / "OPERATIONS_RUNBOOK.md"
            self.assertTrue(runbook_path.exists(), "docs/OPERATIONS_RUNBOOK.md missing")
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main()
