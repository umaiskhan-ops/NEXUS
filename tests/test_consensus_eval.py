"""Comprehensive CI Benchmark Suite for Free-Form Semantic Consensus and Canary Replay.

Evaluates the consensus engine across 8 diverse topics (Physics, Astronomy, Biology, History,
Economics, Biochemistry, Computer Networks, Thermodynamics) against four distinct behavioral patterns:
1. Honest Paraphrases: Independent honest workers explaining real mechanisms (Target: >= 80% pass).
2. Semantic Contradictions: Factual inversions, opposite claims, or impossible mechanisms (Target: <= 10% pass).
3. Vague Non-Answers: Evasive meta-discourse filler lacking concrete mechanism stems (Target: <= 10% pass).
4. Keyword Salads: Unstructured or pseudo-grammatical word dumps (Target: <= 10% pass).

Also verifies the Canary Replay mechanism:
- Authentic tasks from consensus pool replayed as indistinguishable canaries.
- Graduated penalty enforcement for false or contradictory canary submissions.
"""

import unittest
import time
import tempfile
from pathlib import Path
from sovereign_mesh.ledger import HashChainLedger
from sovereign_mesh.hub_spoke import (
    MasterHubCoordinator,
    compute_hmac,
    detect_contradiction,
    is_vague_non_answer,
    check_prose_coherence,
)


class TestConsensusEvaluation(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp_dir.name)
        self.ledger = HashChainLedger(self.data_dir / "ledger.jsonl")
        self.hub = MasterHubCoordinator(self.ledger, state_path=self.data_dir / "state.json")

    def tearDown(self):
        self.hub.stop()
        self.tmp_dir.cleanup()

    def test_detector_primitives_unit(self):
        """Direct unit validation of contradiction, vagueness, and coherence detection primitives."""
        # 1. Contradiction Detection
        t_pos = "Ice floats on water because solid ice is less dense than liquid water."
        t_neg = "Ice floats on water because solid ice is heavier and denser than liquid water."
        is_contra, reason = detect_contradiction(t_pos, t_neg)
        self.assertTrue(is_contra, "Expected polar density contradiction to be detected")
        self.assertTrue("polar" in reason or "antonym" in reason, f"Unexpected reason: {reason}")

        # 2. Vague Non-Answer Detection
        vague_text = "Seasons happen because of various astronomical factors and complex orbital mechanics across time."
        is_vague, ratio = is_vague_non_answer(vague_text)
        self.assertTrue(is_vague, f"Expected meta-discourse filler to be flagged (ratio {ratio})")
        self.assertGreaterEqual(ratio, 0.15)

        # 3. Coherence / Salad Detection
        salad_text = "scatter molecules wavelength sunlight rayleigh atmosphere light photons"
        is_coherent, reason = check_prose_coherence(salad_text)
        self.assertFalse(is_coherent, "Expected keyword salad without function words to fail coherence")
        self.assertIn("keyword_salad_rejected", reason)

    def test_consensus_8_topic_benchmark_suite(self):
        """End-to-end multi-worker consensus verification on the 8 benchmark topics."""
        topics = {
            "sky": {
                "prompt": "Why is the sky blue?",
                "honest_1": "Sunlight reaches Earth atmosphere and is scattered in all directions by gases in the air. Blue light is scattered more than other colors because it travels as shorter, smaller waves, a process known as Rayleigh scattering.",
                "honest_2": "The blue color of the sky is caused by Rayleigh scattering. As sunlight enters the atmosphere, shorter blue wavelengths are scattered much more strongly by air molecules than longer red wavelengths.",
                "contradict": "The sky appears blue because the atmosphere acts as a giant mirror that reflects the blue color of the ocean waters up into the clouds.",
                "vague": "The sky is blue due to various natural processes and complex atmospheric conditions that scientists have studied for many years involving sunlight and the air.",
                "salad": "scatter molecules wavelength sunlight rayleigh atmosphere light photons blue gas waves sky",
            },
            "seasons": {
                "prompt": "Why do we have seasons on Earth?",
                "honest_1": "Earth has seasons because its axis of rotation is tilted at an angle of about 23.5 degrees relative to its orbital plane. As Earth orbits the Sun, different hemispheres receive varying angles and intensities of sunlight throughout the year.",
                "honest_2": "Seasons occur because of the 23.5 degree axial tilt of the Earth. When the Northern Hemisphere is tilted toward the Sun, it experiences summer due to direct sunlight, while the Southern Hemisphere experiences winter.",
                "contradict": "Earth experiences seasons because its elliptical orbit brings it significantly closer to the Sun during summer and much farther away during winter, changing global temperatures.",
                "vague": "Seasons happen because of various astronomical factors and complex orbital mechanics as the Earth travels through space around the solar system over time.",
                "salad": "tilted axis sunlight hemisphere summer winter orbit angle solar radiation seasons earth",
            },
            "vaccination": {
                "prompt": "How do vaccines protect against disease?",
                "honest_1": "Vaccines introduce a weakened or harmless piece of a pathogen such as an antigen into the body. This stimulates the immune system to produce antibodies and memory cells without causing the disease, providing immunity against future infection.",
                "honest_2": "Vaccines work by training the immune system to recognize antigens from pathogens. The body creates specific antibodies and memory B and T cells that rapidly neutralize the actual pathogen if exposed later.",
                "contradict": "Vaccines work by destroying the body natural immune system so that synthetic artificial chemicals can directly poison and kill any invading bacteria without relying on white blood cells.",
                "vague": "Vaccines protect health through multiple biological mechanisms and medical interactions within human biology that help people stay safe from various dangerous sicknesses.",
                "salad": "antibodies antigen pathogen immune system memory cells white blood cells immunity vaccination disease",
            },
            "Rome": {
                "prompt": "What caused the fall of the Western Roman Empire?",
                "honest_1": "The fall of the Western Roman Empire resulted from multiple converging factors including severe economic crises, political corruption and frequent civil wars, military overexpansion and reliance on mercenaries, and relentless invasions by Germanic barbarian tribes.",
                "honest_2": "The collapse of Western Rome was driven by internal decay such as political instability and economic decline, combined with external military pressure and migrations from barbarian tribes including the Visigoths and Vandals.",
                "contradict": "The Western Roman Empire fell abruptly because a massive asteroid struck the capital city of Rome, destroying the Senate and instantly ending imperial administration.",
                "vague": "The Western Roman Empire fell due to many complicated historical reasons, events, and sociopolitical changes that took place across Europe over a very long historical period.",
                "salad": "barbarian invasions visigoths mercenaries corruption economic crisis political instability empire collapse rome",
            },
            "inflation": {
                "prompt": "What causes economic inflation?",
                "honest_1": "Inflation is primarily caused when the money supply expands faster than real economic output, increasing aggregate demand, or when production costs rise sharply, eroding the purchasing power of the currency.",
                "honest_2": "Economic inflation occurs when too much money chases too few goods, often triggered by loose central bank monetary policy (demand-pull) or supply chain disruptions and rising energy costs (cost-push).",
                "contradict": "Inflation is caused when prices across the economy experience rapid deflation, significantly increasing the purchasing power of consumers and making goods cheaper for everyone.",
                "vague": "Economic inflation happens because of diverse financial dynamics, market developments, and various monetary variables that affect financial transactions across the economy.",
                "salad": "money supply purchasing power prices central bank monetary policy demand cost push goods inflation",
            },
            "photosynthesis": {
                "prompt": "How does photosynthesis work in plants?",
                "honest_1": "Photosynthesis is the process in which green plants use chlorophyll to capture light energy from the sun. They convert carbon dioxide from the air and water from the soil into glucose sugar and release oxygen as a byproduct.",
                "honest_2": "In plant chloroplasts, solar energy drives a chemical reaction combining water and carbon dioxide to produce glucose for energy while discharging oxygen gas into the atmosphere.",
                "contradict": "During photosynthesis, plant leaves absorb oxygen gas and glucose sugar from the environment and chemically convert them into carbon dioxide and water, releasing heat into the air.",
                "vague": "Photosynthesis is an important natural botanical process involving plant cells and environmental inputs that allows vegetation to function effectively within ecosystems.",
                "salad": "chloroplasts chlorophyll light sunlight carbon dioxide water glucose oxygen plants leaves",
            },
            "TCP/UDP": {
                "prompt": "What is the difference between TCP and UDP protocols?",
                "honest_1": "TCP is a connection-oriented protocol that provides reliable, ordered, and error-checked delivery of data using a three-way handshake, whereas UDP is connectionless and faster without delivery guarantees.",
                "honest_2": "The key distinction is that TCP guarantees packet delivery and ordering through acknowledgments and retransmission, while UDP is lightweight and connectionless, sacrificing reliability for lower latency in streaming and gaming.",
                "contradict": "TCP is a connectionless and unreliable protocol that drops packets without verification, whereas UDP establishes strict dedicated connections and guarantees reliable ordered packet transmission.",
                "vague": "TCP and UDP are two different networking communication protocols used in computer networks that handle data transmission across the internet according to their respective specifications.",
                "salad": "connection oriented reliable handshake packet delivery connectionless latency protocol tcp udp datagram",
            },
            "ice": {
                "prompt": "Why does ice float on water?",
                "honest_1": "Ice floats on liquid water because when water freezes, hydrogen bonds hold the molecules in an open hexagonal crystal lattice. This structure makes solid ice about 9% less dense than the liquid water beneath it.",
                "honest_2": "Solid water floats because it expands upon freezing due to hydrogen bonding. The resulting crystalline structure has more open space between molecules, meaning ice has lower density than liquid water.",
                "contradict": "Ice floats on water because ice is significantly heavier and denser than liquid water, which creates strong upward pressure that forces the heavy ice blocks to the top surface.",
                "vague": "Ice floats due to various physical properties of chemical compounds and molecular thermodynamics that cause solid materials to interact with fluids in particular ways.",
                "salad": "hydrogen bonds hexagonal lattice crystalline structure density expand freeze liquid water ice",
            },
        }

        honest_passes = 0
        contradict_leaks = 0
        vague_leaks = 0
        salad_leaks = 0
        total_topics = len(topics)

        # Register two persistent independent workers on distinct subnets
        w1_id = "eval-worker-alpha"
        w2_id = "eval-worker-beta"
        w1 = self.hub.register_worker(w1_id, url="local", public_ip="198.51.100.50", initial_credits=2000)
        w2 = self.hub.register_worker(w2_id, url="local", public_ip="203.0.113.80", initial_credits=2000)

        # Dedicated test helper to execute a consensus pair through the real hub
        def run_pair(topic_key: str, sub_id: str, prompt_text: str, out_1: str, out_2: str) -> bool:
            c_id = f"cons-{topic_key}-{sub_id}"
            t1 = self.hub.create_signed_task(w1_id, "brain_inference", {"prompt": prompt_text, "consensus_id": c_id}, funded_credits=25)
            t2 = self.hub.create_signed_task(w2_id, "brain_inference", {"prompt": prompt_text, "consensus_id": c_id}, funded_credits=25)

            p1 = compute_hmac(w1.key, {"task_id": t1["task_id"], "worker_id": w1_id, "feature": "brain_inference", "nonce": t1["nonce"], "result": {"status": "OK", "output": out_1}})
            s1 = self.hub.verify_and_settle({"task_id": t1["task_id"], "worker_id": w1_id, "feature": "brain_inference", "result": {"status": "OK", "output": out_1}, "worker_proof": p1})

            if not s1.get("ok") or s1.get("status") != "PENDING_CONSENSUS":
                return False

            p2 = compute_hmac(w2.key, {"task_id": t2["task_id"], "worker_id": w2_id, "feature": "brain_inference", "nonce": t2["nonce"], "result": {"status": "OK", "output": out_2}})
            s2 = self.hub.verify_and_settle({"task_id": t2["task_id"], "worker_id": w2_id, "feature": "brain_inference", "result": {"status": "OK", "output": out_2}, "worker_proof": p2})

            return bool(s2.get("ok") and s2.get("status") == "SETTLED")

        for key, data in topics.items():
            prompt = data["prompt"]
            h1 = data["honest_1"]
            h2 = data["honest_2"]
            contra = data["contradict"]
            vague = data["vague"]
            salad = data["salad"]

            # 1. Honest pair evaluation
            if run_pair(key, "honest", prompt, h1, h2):
                honest_passes += 1

            # 2. Contradiction pair evaluation
            if run_pair(key, "contra", prompt, h1, contra):
                contradict_leaks += 1

            # 3. Vague non-answer pair evaluation
            if run_pair(key, "vague", prompt, h1, vague):
                vague_leaks += 1

            # 4. Keyword salad pair evaluation
            if run_pair(key, "salad", prompt, h1, salad):
                salad_leaks += 1

        honest_pct = (honest_passes / total_topics) * 100.0
        contra_pct = (contradict_leaks / total_topics) * 100.0
        vague_pct = (vague_leaks / total_topics) * 100.0
        salad_pct = (salad_leaks / total_topics) * 100.0

        print(f"\n[CI CONSENSUS BENCHMARK SCORES]")
        print(f"  Honest Paraphrase Pass Rate : {honest_passes}/{total_topics} ({honest_pct:.1f}%) [Target >= 80%]")
        print(f"  Contradiction Leak Rate     : {contradict_leaks}/{total_topics} ({contra_pct:.1f}%) [Target <= 10%]")
        print(f"  Vague Non-Answer Leak Rate  : {vague_leaks}/{total_topics} ({vague_pct:.1f}%) [Target <= 10%]")
        print(f"  Keyword Salad Leak Rate     : {salad_leaks}/{total_topics} ({salad_pct:.1f}%) [Target <= 10%]")

        self.assertGreaterEqual(honest_passes, 7, f"Honest pass rate must be >= 80% (got {honest_passes}/{total_topics})")
        self.assertEqual(contradict_leaks, 0, f"Contradictions must be 0% (got {contradict_leaks}/{total_topics})")
        self.assertEqual(vague_leaks, 0, f"Vague non-answers must be 0% (got {vague_leaks}/{total_topics})")
        self.assertEqual(salad_leaks, 0, f"Keyword salads must be 0% (got {salad_leaks}/{total_topics})")

    def test_canary_replay_lifecycle(self):
        """Verifies that the Canary Replay pool records clean tasks and evaluates workers reliably."""
        # 1. Check replay pool initialization (starts empty, organic population)
        self.assertEqual(len(self.hub._replay_canary_pool), 0)

        # 2. Record an authentic clean user consensus settlement
        user_prompt = "Explain why leaves change color in autumn in temperate zones."
        user_output = "Leaves change color because trees break down green chlorophyll in response to cooler temperatures and shorter daylight. This unmasks underlying orange carotenoid pigments and triggers anthocyanin synthesis."
        self.hub.record_trusted_replay_task(user_prompt, user_output)

        matched_entries = [e for e in self.hub._replay_canary_pool if e["prompt"] == user_prompt]
        self.assertEqual(len(matched_entries), 1)
        canary_entry = matched_entries[0]
        self.assertTrue(canary_entry["is_replay"])

        # 3. Inject a replay canary to a worker
        worker = self.hub.register_worker("canary-target-node", url="local", public_ip="198.51.100.22", initial_credits=100)
        # Force replay selection by setting pool temporarily to our target
        orig_pool = list(self.hub._replay_canary_pool)
        self.hub._replay_canary_pool = [canary_entry]

        try:
            task = self.hub.create_golden_canary_task("canary-target-node", canary_idx="replay")
            # Verify worker-facing task is completely disguised: contains prompt, no canary tags, no test_assertions
            self.assertEqual(task["payload"]["prompt"], user_prompt)
            self.assertNotIn("test_assertions", task["payload"])
            self.assertNotIn("is_canary", task)
            self.assertNotIn("canary_spec", task)

            # 4. Honest response to replay canary -> Settles & rewards credits
            good_answer = "In autumn, green chlorophyll degrades due to reduced sunlight, revealing yellow and red carotenoids and anthocyanins in foliage."
            proof_good = compute_hmac(worker.key, {"task_id": task["task_id"], "worker_id": "canary-target-node", "feature": "brain_inference", "nonce": task["nonce"], "result": {"status": "OK", "output": good_answer}})
            settle_res = self.hub.verify_and_settle({"task_id": task["task_id"], "worker_id": "canary-target-node", "feature": "brain_inference", "result": {"status": "OK", "output": good_answer}, "worker_proof": proof_good})
            self.assertTrue(settle_res["ok"])
            self.assertEqual(settle_res["status"], "SETTLED")
            self.assertEqual(worker.credits, 125)  # +25 credits rewarded

            # 5. Inverted/contradictory response to replay canary -> Fails & triggers strike warning
            task2 = self.hub.create_golden_canary_task("canary-target-node", canary_idx="replay")
            bad_answer = "Leaves turn bright green in autumn because trees absorb immense heat and double chlorophyll production to survive winter."
            proof_bad = compute_hmac(worker.key, {"task_id": task2["task_id"], "worker_id": "canary-target-node", "feature": "brain_inference", "nonce": task2["nonce"], "result": {"status": "OK", "output": bad_answer}})
            bad_res = self.hub.verify_and_settle({"task_id": task2["task_id"], "worker_id": "canary-target-node", "feature": "brain_inference", "result": {"status": "OK", "output": bad_answer}, "worker_proof": proof_bad})
            self.assertFalse(bad_res["ok"])
            self.assertEqual(bad_res["status"], "REJECTED")
            self.assertIn("canary_strike_1_warning", bad_res["reason"])
            self.assertEqual(worker.canary_strikes, 1)

        finally:
            self.hub._replay_canary_pool = orig_pool


if __name__ == "__main__":
    unittest.main()
