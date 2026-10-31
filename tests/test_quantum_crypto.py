"""Unit tests for NEXUS Hyper-Sovereign Multi-Vault Quantum Cryptography Engine (HSQK-4096).
Verifies post-quantum lattice ML-DSA, Ed448, Hardware PUF Silicon Seal, Ephemeral Ratchet,
Bech32m quantum addresses, and end-to-end Master Hub settlement.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import unittest
from pathlib import Path

from sovereign_mesh.ledger import HashChainLedger
from sovereign_mesh.hub_spoke import MasterHubCoordinator, WorkerNodeRecord
from sovereign_mesh.quantum_crypto import (
    HyperSovereignKeyVault,
    verify_hyper_proof,
    verify_quantum_address,
    encode_quantum_address,
    compute_hardware_puf_seal,
    lattice_keygen,
    lattice_sign,
    lattice_verify,
    VAULT_ENTROPY_BYTES,
    ADDRESS_HRP,
)


class TestHyperSovereignQuantumCrypto(unittest.TestCase):
    def setUp(self):
        self.tmp_ledger_path = Path("tests_tmp_quantum_ledger.jsonl")
        self.tmp_hub_state = Path("tests_tmp_quantum_hub.json")
        for p in (self.tmp_ledger_path, self.tmp_hub_state):
            if p.exists():
                try:
                    p.unlink()
                except OSError:
                    pass
        self.ledger = HashChainLedger(self.tmp_ledger_path)
        self.hub = MasterHubCoordinator(self.ledger, state_path=self.tmp_hub_state)

    def tearDown(self):
        for p in (
            self.tmp_ledger_path,
            self.tmp_hub_state,
            Path(f".{self.tmp_ledger_path.name}.lock"),
            Path(f".{self.tmp_hub_state.name}.lock"),
        ):
            if p.exists():
                try:
                    p.unlink()
                except OSError:
                    pass

    def test_01_4096_bit_vault_entropy_and_structure(self):
        """Proves key entropy is 4096 bits (512 bytes), mathematically equivalent to (2^256)^16 Bitcoin spaces."""
        vault = HyperSovereignKeyVault.generate()
        raw_entropy = bytes.fromhex(vault.entropy_hex)
        self.assertEqual(len(raw_entropy), VAULT_ENTROPY_BYTES)
        self.assertEqual(len(raw_entropy) * 8, 4096)
        
        # Verify all 4 chambers are initialized
        self.assertTrue(vault.lattice_pub["a_seed_hex"])
        self.assertEqual(len(vault.lattice_priv["s1"]), 32)
        self.assertTrue(vault.ed448_pub_hex)
        self.assertTrue(vault.cascade_root_hex)
        self.assertTrue(vault.puf_seal)
        self.assertTrue(vault.quantum_address.startswith("nxq1"))

    def test_02_bech32m_quantum_address_encoding_and_error_detection(self):
        """Verifies Bech32m polynomial error-detection checksum on nxq1 addresses."""
        commitment = hashlib.blake2b(b"NEXUS_TEST_COMMITMENT_2026", digest_size=32).digest()
        addr = encode_quantum_address(ADDRESS_HRP, commitment)
        self.assertTrue(addr.startswith("nxq1"))
        self.assertTrue(verify_quantum_address(addr))

        # Test single character corruption detection
        corrupted = addr[:-1] + ("a" if addr[-1] != "a" else "b")
        self.assertFalse(verify_quantum_address(corrupted))

    def test_03_nist_fips_204_lattice_module_lwe_signing(self):
        """Verifies pure-Python Module-LWE cyclotomic ring signature and verification."""
        seed = os.urandom(96)
        pub, priv = lattice_keygen(seed)
        msg = b"NEXUS Decentralized Neural Shard Gradient Proof"
        sig = lattice_sign(priv, pub, msg, nonce="nonce-42")
        
        # Valid signature must verify
        self.assertTrue(lattice_verify(pub, msg, sig))

    def test_04_hardware_puf_silicon_drift_anchor(self):
        """Verifies hardware silicon drift sampling and anti-clone tamper detection."""
        puf1 = compute_hardware_puf_seal()
        self.assertTrue(puf1["stable_hw_id"].startswith("hw-"))
        self.assertTrue(puf1["silicon_drift"])
        self.assertTrue(puf1["puf_seal"])

        vault = HyperSovereignKeyVault.generate()
        pub = vault.get_public_bundle()
        payload = {"task": "test", "data": 123}
        proof = vault.sign_hyper_proof(payload, nonce="n1")

        # Valid proof with matching PUF passes
        ok, reason = verify_hyper_proof(pub, payload, proof, nonce="n1")
        self.assertTrue(ok)
        self.assertEqual(reason, "OK_QUANTUM_VERIFIED")

        # Rogue clone on another machine with mismatched PUF seal is blocked!
        tampered_pub = dict(pub)
        tampered_pub["puf_seal"] = "bad_silicon_seal_" + "0" * 48
        bad_ok, bad_reason = verify_hyper_proof(tampered_pub, payload, proof, nonce="n1")
        self.assertFalse(bad_ok)
        self.assertIn("puf_silicon_seal_mismatch", bad_reason)

    def test_05_forward_secure_ephemeral_ratchet(self):
        """Verifies ratchet advances on every proof and detects stale/replayed ratchet steps."""
        vault = HyperSovereignKeyVault.generate()
        pub = vault.get_public_bundle()
        
        # First proof
        payload_1 = {"step": 1}
        proof_1 = vault.sign_hyper_proof(payload_1, nonce="n1")
        self.assertEqual(proof_1["ratchet_step"], 1)
        ok1, _ = verify_hyper_proof(pub, payload_1, proof_1, nonce="n1")
        self.assertTrue(ok1)
        pub["ratchet_step"] = proof_1["ratchet_step"]

        # Second proof
        payload_2 = {"step": 2}
        proof_2 = vault.sign_hyper_proof(payload_2, nonce="n2")
        self.assertEqual(proof_2["ratchet_step"], 2)
        ok2, _ = verify_hyper_proof(pub, payload_2, proof_2, nonce="n2")
        self.assertTrue(ok2)
        pub["ratchet_step"] = proof_2["ratchet_step"]

        # Replaying stale step 1 must be rejected by Master Hub!
        stale_ok, stale_reason = verify_hyper_proof(pub, payload_1, proof_1, nonce="n1")
        self.assertFalse(stale_ok)
        self.assertIn("stale_or_replayed_ratchet_step", stale_reason)

    def test_06_master_hub_end_to_end_hyper_proof_settlement(self):
        """End-to-End Master Hub worker registration and 4096-bit HyperProof task settlement."""
        vault = HyperSovereignKeyVault.generate()
        wid = "quantum-worker-01"

        # Register worker with Hub including full quantum credentials
        rec = self.hub.register_worker(
            wid,
            url="local",
            hardware_uuid=vault.hardware_uuid,
            quantum_address=vault.quantum_address,
            quantum_vault_pub=vault.get_public_bundle(),
            puf_seal=vault.puf_seal,
        )
        self.assertEqual(rec.quantum_address, vault.quantum_address)
        self.assertIn("4096-Bit", rec.crypto_security_level)

        # Enqueue and pull NAT task
        task_pkt = self.hub.enqueue_nat_task(wid, "data_analysis", {"series": [10, 20, 30]})
        pulled = self.hub.pull_pending_tasks(wid, max_tasks=1)
        self.assertEqual(len(pulled), 1)
        t = pulled[0]

        # Worker processes task and signs with 4096-bit HyperProof
        task_result = {"status": "OK", "mean": 20.0}
        proof_body = {
            "task_id": t["task_id"],
            "worker_id": wid,
            "feature": t["feature"],
            "nonce": t["nonce"],
            "result": task_result,
        }
        hyper_proof = vault.sign_hyper_proof(proof_body, nonce=t["nonce"])

        submission = {
            "task_id": t["task_id"],
            "worker_id": wid,
            "result": task_result,
            "worker_proof": hyper_proof,
        }

        # Master Hub settles task
        settled = self.hub.verify_and_settle(submission)
        self.assertTrue(settled.get("ok"))
        self.assertEqual(settled.get("status"), "SETTLED")
        self.assertTrue(settled.get("quantum_verified"))
        self.assertEqual(settled.get("quantum_address"), vault.quantum_address)
        self.assertEqual(rec.credits, 45)  # 20 welcome + 25 task reward
        self.assertEqual(rec.tasks_completed, 1)

    def test_07_backward_compatibility_with_legacy_hmac_proofs(self):
        """Ensures existing workers using classical HMAC continue to settle tasks seamlessly."""
        wid = "legacy-worker-99"
        rec = self.hub.register_worker(wid, url="local")
        self.assertTrue(rec.quantum_address.startswith("nxq1"))  # Automatically provisioned quantum address

        task_pkt = self.hub.enqueue_nat_task(wid, "trend_forecasting", {"data": [1, 2, 3]})
        pulled = self.hub.pull_pending_tasks(wid, max_tasks=1)
        t = pulled[0]

        result = {"trend": "UP"}
        proof_body = {
            "task_id": t["task_id"],
            "worker_id": wid,
            "feature": t["feature"],
            "nonce": t["nonce"],
            "result": result,
        }
        legacy_proof = hmac.new(rec.key.encode("utf-8"), json.dumps(proof_body, sort_keys=True, separators=(",", ":")).encode("utf-8"), hashlib.sha256).hexdigest()

        submission = {
            "task_id": t["task_id"],
            "worker_id": wid,
            "result": result,
            "worker_proof": legacy_proof,
        }
        settled = self.hub.verify_and_settle(submission)
        self.assertTrue(settled.get("ok"))
        self.assertEqual(settled.get("status"), "SETTLED")
        self.assertFalse(settled.get("quantum_verified"))  # legacy HMAC is not quantum, but valid


if __name__ == "__main__":
    unittest.main()
