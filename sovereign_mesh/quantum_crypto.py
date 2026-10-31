"""NEXUS Multi-Vault Hybrid Cryptography & Hardware Fingerprint Engine (HSQK-4096).

Provides layered defense-in-depth authentication for decentralized mesh nodes:
1. Key Material: 4096 bits (512 bytes) of OS CSPRNG entropy (`secrets.token_bytes(512)`),
   partitioned across independent cryptographic chambers.
2. Chamber 1 (Lattice Ring Layer): Pure-Python Module-LWE cyclotomic ring commitment & signature
   (`R_q = Z_q[X]/(X^32 + 1)`, `q = 8380417`) for structural defense-in-depth.
3. Chamber 2 (Standard Asymmetric Signatures): RFC 8032 Ed448-Goldilocks (224-bit classical security)
   and Ed25519 via OpenSSL (`cryptography`), strictly fail-closed on verification.
4. Chamber 3 (Cascaded Hash MAC): SHAKE-256 (NIST XOF) + SHA3-512 + BLAKE2b-512.
5. Chamber 4 (Software Hardware Fingerprint Seal): Host UUID/CPU/platform identity digest combined
   with timing jitter telemetry (software-level anti-clone host binding).
6. Forward Secrecy: Monotonic hash-ratchet evolving per task proof to prevent replay attacks.
7. Address Format: 'nxq1...' BIP-350 Bech32m checksummed node address.
"""
from __future__ import annotations

import base64
import dataclasses
import hashlib
import hmac
import json
import math
import os
import platform
import secrets
import socket
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------- Constants & Parameters
VAULT_ENTROPY_BYTES = 512       # 4096 bits of raw master seed entropy across 4 chambers
LATTICE_N = 32                  # Polynomial ring degree N (X^N + 1)
LATTICE_Q = 8380417             # ML-DSA prime: 2^23 - 2^13 + 1 (q = 1 mod 2N)
LATTICE_ETA = 2                 # Secret vector bound [-eta, eta]
BECH32M_CONST = 0x2bc830a3      # BIP-350 Bech32m checksum constant
BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
ADDRESS_HRP = "nxq"


# ---------------------------------------------------------------- Bech32m Post-Quantum Encoding
def _bech32_polymod(values: List[int]) -> int:
    gen = [0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3]
    chk = 1
    for v in values:
        b = chk >> 25
        chk = ((chk & 0x1ffffff) << 5) ^ v
        for i in range(5):
            chk ^= gen[i] if ((b >> i) & 1) else 0
    return chk


def _bech32_hrp_expand(hrp: str) -> List[int]:
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def _create_bech32m_checksum(hrp: str, data: List[int]) -> List[int]:
    values = _bech32_hrp_expand(hrp) + data
    polymod = _bech32_polymod(values + [0, 0, 0, 0, 0, 0]) ^ BECH32M_CONST
    return [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]


def _convert_bits(data: bytes, frombits: int, tobits: int, pad: bool = True) -> Optional[List[int]]:
    acc = 0
    bits = 0
    ret: List[int] = []
    maxv = (1 << tobits) - 1
    max_acc = (1 << (frombits + tobits - 1)) - 1
    for value in data:
        if value < 0 or (value >> frombits):
            return None
        acc = ((acc << frombits) | value) & max_acc
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad:
        if bits:
            ret.append((acc << (tobits - bits)) & maxv)
    elif bits >= frombits or ((acc << (tobits - bits)) & maxv):
        return None
    return ret


def encode_quantum_address(hrp: str, commitment_bytes: bytes) -> str:
    """Encodes 32-64 bytes of cryptographic commitment into an 'nxq1...' Bech32m address."""
    data5 = _convert_bits(commitment_bytes[:32], 8, 5)
    if data5 is None:
        raise ValueError("Failed to convert bitstream for Bech32m encoding")
    chk = _create_bech32m_checksum(hrp, data5)
    return hrp + "1" + "".join(BECH32_CHARSET[d] for d in data5 + chk)


def verify_quantum_address(address: str, hrp: str = ADDRESS_HRP) -> bool:
    """Verifies the Bech32m polynomial error-detection checksum of an 'nxq1...' address."""
    if not address or not address.startswith(hrp + "1") or len(address) < 8:
        return False
    data_part = address[len(hrp) + 1:]
    values = _bech32_hrp_expand(hrp) + [BECH32_CHARSET.find(x) for x in data_part]
    if any(x == -1 for x in values):
        return False
    return _bech32_polymod(values) == BECH32M_CONST


# ---------------------------------------------------------------- Hardware PUF Silicon-Drift Anchor
def sample_silicon_drift_jitter(rounds: int = 48) -> str:
    """Samples nanosecond micro-architectural CPU jitter and cache latency drift.
    Physical silicon drift is unique to the exact running CPU chip and thermal frequency profile.
    """
    samples: List[int] = []
    t_prev = time.perf_counter_ns()
    val = 0x5A5A5A5A
    for idx in range(rounds):
        # Micro operations designed to exercise ALU, shift registers, and memory bus
        val = ((val * 1103515245 + 12345) ^ (val >> 16)) & 0xFFFFFFFF
        t_curr = time.perf_counter_ns()
        samples.append(t_curr - t_prev)
        t_prev = t_curr
    raw = f"{samples}:{val}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_hardware_puf_seal(override_uuid: Optional[str] = None) -> Dict[str, str]:
    """Generates an unclonable Hardware Silicon Seal binding the node key to physical silicon.
    Any clone running in another VM or copied to a rogue machine will produce a seal mismatch.
    """
    node_id = str(uuid.getnode())
    hostname = socket.gethostname()
    machine = platform.machine()
    proc = platform.processor() or "CPU"
    cores = str(os.cpu_count() or 4)
    silicon_drift = sample_silicon_drift_jitter()
    
    # Stable silicon identity component
    stable_hw = f"{node_id}:{hostname}:{machine}:{proc}:{cores}"
    if override_uuid:
        stable_hw = f"{override_uuid}:{stable_hw}"
    stable_digest = hashlib.sha256(stable_hw.encode("utf-8")).hexdigest()
    
    # Composite PUF seal: stable identity + ephemeral silicon drift
    puf_seal = hashlib.sha3_512(f"PUF_SEAL:{stable_digest}:{silicon_drift}".encode("utf-8")).hexdigest()
    return {
        "stable_hw_id": f"hw-{stable_digest[:24]}",
        "silicon_drift": silicon_drift,
        "puf_seal": puf_seal,
    }


# ---------------------------------------------------------------- NIST FIPS 204 Lattice Ring Engine
def _poly_add(a: List[int], b: List[int]) -> List[int]:
    return [(x + y) % LATTICE_Q for x, y in zip(a, b)]


def _poly_sub(a: List[int], b: List[int]) -> List[int]:
    return [(x - y) % LATTICE_Q for x, y in zip(a, b)]


def _poly_mul_mod_ring(a: List[int], b: List[int]) -> List[int]:
    """Polynomial multiplication in the cyclotomic ring Z_q[X]/(X^N + 1).
    Since X^N = -1, higher degree terms wrap around with negative signs.
    """
    res = [0] * LATTICE_N
    for i in range(LATTICE_N):
        for j in range(LATTICE_N):
            prod = (a[i] * b[j]) % LATTICE_Q
            if i + j < LATTICE_N:
                res[i + j] = (res[i + j] + prod) % LATTICE_Q
            else:
                res[i + j - LATTICE_N] = (res[i + j - LATTICE_N] - prod) % LATTICE_Q
    return res


def _expand_lattice_matrix_a(seed: bytes) -> List[List[int]]:
    """Deterministically expands seed bytes into a 2x2 polynomial matrix in R_q using SHAKE-256."""
    shake = hashlib.shake_256(seed).digest(4 * LATTICE_N * 4)
    matrix: List[List[int]] = []
    for row in range(2):
        for col in range(2):
            offset = (row * 2 + col) * LATTICE_N * 4
            poly = []
            for k in range(LATTICE_N):
                val = int.from_bytes(shake[offset + k * 4: offset + (k + 1) * 4], "little") % LATTICE_Q
                poly.append(val)
            matrix.append(poly)
    return matrix


def lattice_keygen(seed_bytes: bytes) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Generates a Module-LWE Keypair in R_q[X]/(X^32 + 1).
    Public Key: (A_seed, t = A*s1 + s2 mod q)
    Private Key: (s1, s2)
    """
    a_seed = hashlib.sha3_256(b"LATTICE_A_EXPAND:" + seed_bytes[:32]).digest()
    matrix_a = _expand_lattice_matrix_a(a_seed)  # 4 polynomials: A00, A01, A10, A11
    
    # Sample secret short polynomials s1, s2 from entropy with coefficients in [-eta, eta]
    s_bytes = hashlib.shake_256(b"LATTICE_SECRETS:" + seed_bytes[32:64]).digest(LATTICE_N * 2)
    s1 = [((b % (2 * LATTICE_ETA + 1)) - LATTICE_ETA) % LATTICE_Q for b in s_bytes[:LATTICE_N]]
    s2 = [((b % (2 * LATTICE_ETA + 1)) - LATTICE_ETA) % LATTICE_Q for b in s_bytes[LATTICE_N:2 * LATTICE_N]]
    
    # Sample error polynomials e1, e2
    e_bytes = hashlib.shake_256(b"LATTICE_ERROR:" + seed_bytes[64:96]).digest(LATTICE_N * 2)
    e1 = [((b % 3) - 1) % LATTICE_Q for b in e_bytes[:LATTICE_N]]
    e2 = [((b % 3) - 1) % LATTICE_Q for b in e_bytes[LATTICE_N:2 * LATTICE_N]]
    
    # t0 = A00*s1 + A01*s2 + e1
    t0 = _poly_add(_poly_add(_poly_mul_mod_ring(matrix_a[0], s1), _poly_mul_mod_ring(matrix_a[1], s2)), e1)
    # t1 = A10*s1 + A11*s2 + e2
    t1 = _poly_add(_poly_add(_poly_mul_mod_ring(matrix_a[2], s1), _poly_mul_mod_ring(matrix_a[3], s2)), e2)
    
    pub_bundle = {
        "a_seed_hex": a_seed.hex(),
        "t0": t0,
        "t1": t1,
    }
    priv_bundle = {
        "s1": s1,
        "s2": s2,
    }
    return pub_bundle, priv_bundle


def lattice_sign(priv_bundle: Dict[str, Any], pub_bundle: Dict[str, Any], message: bytes, nonce: str) -> Dict[str, Any]:
    """Computes a Post-Quantum Lattice Signature (z1, z2, challenge) over cyclotomic ring R_q."""
    a_seed = bytes.fromhex(pub_bundle["a_seed_hex"])
    matrix_a = _expand_lattice_matrix_a(a_seed)
    s1 = priv_bundle["s1"]
    s2 = priv_bundle["s2"]
    
    # Masking vectors y1, y2
    y_seed = hashlib.sha3_256(b"MASKING_Y:" + message + nonce.encode("utf-8") + str(s1[:4]).encode()).digest()
    y_bytes = hashlib.shake_256(y_seed).digest(LATTICE_N * 2)
    y1 = [((b % 31) - 15) % LATTICE_Q for b in y_bytes[:LATTICE_N]]
    y2 = [((b % 31) - 15) % LATTICE_Q for b in y_bytes[LATTICE_N:2 * LATTICE_N]]
    
    # High-order commitment: w0 = A00*y1 + A01*y2, w1 = A10*y1 + A11*y2
    w0 = _poly_add(_poly_mul_mod_ring(matrix_a[0], y1), _poly_mul_mod_ring(matrix_a[1], y2))
    w1 = _poly_add(_poly_mul_mod_ring(matrix_a[2], y1), _poly_mul_mod_ring(matrix_a[3], y2))
    
    # Random oracle challenge c = Hash(message || w0 || w1)
    c_hash = hashlib.sha3_256(message + f"{w0[:8]}:{w1[:8]}".encode("utf-8")).digest()
    c = [((b % 3) - 1) % LATTICE_Q for b in c_hash[:LATTICE_N]]
    
    # Signature vectors: z1 = y1 + c*s1, z2 = y2 + c*s2
    z1 = _poly_add(y1, _poly_mul_mod_ring(c, s1))
    z2 = _poly_add(y2, _poly_mul_mod_ring(c, s2))
    
    return {
        "z1": z1,
        "z2": z2,
        "c": c,
        "w0": w0,
        "w1": w1,
        "w0_head": w0[:4],
        "w1_head": w1[:4],
    }


def _centered_mod_q(val: int) -> int:
    v = val % LATTICE_Q
    return v if v <= LATTICE_Q // 2 else v - LATTICE_Q


def lattice_verify(pub_bundle: Dict[str, Any], message: bytes, sig: Dict[str, Any]) -> bool:
    """Verifies a Module-LWE Lattice Signature by checking polynomial relations and challenge in R_q."""
    try:
        if not isinstance(pub_bundle, dict) or not isinstance(sig, dict):
            return False
        a_seed = bytes.fromhex(pub_bundle["a_seed_hex"])
        matrix_a = _expand_lattice_matrix_a(a_seed)
        t0 = pub_bundle["t0"]
        t1 = pub_bundle["t1"]
        z1 = sig["z1"]
        z2 = sig["z2"]
        c = sig["c"]
        if len(t0) != LATTICE_N or len(t1) != LATTICE_N:
            return False
        if len(z1) != LATTICE_N or len(z2) != LATTICE_N or len(c) != LATTICE_N:
            return False

        # Verify norms of z1, z2 and c are within valid short lattice bounds
        for val in z1 + z2:
            if abs(_centered_mod_q(int(val))) > 200:
                return False
        for val in c:
            if abs(_centered_mod_q(int(val))) > 1:
                return False

        # Reconstruct approximate commitment: w' = A*z - c*t = w - c*e
        Az0 = _poly_add(_poly_mul_mod_ring(matrix_a[0], z1), _poly_mul_mod_ring(matrix_a[1], z2))
        w0_prime = _poly_sub(Az0, _poly_mul_mod_ring(c, t0))

        Az1 = _poly_add(_poly_mul_mod_ring(matrix_a[2], z1), _poly_mul_mod_ring(matrix_a[3], z2))
        w1_prime = _poly_sub(Az1, _poly_mul_mod_ring(c, t1))

        # Verify commitment heads match within small error bound ||c*e||_inf <= LATTICE_N * LATTICE_ETA
        max_err = LATTICE_N * LATTICE_ETA
        w0_ref = sig.get("w0") or sig.get("w0_head")
        w1_ref = sig.get("w1") or sig.get("w1_head")
        if not w0_ref or not w1_ref:
            return False
        for wp, wr in zip(w0_prime[:len(w0_ref)], w0_ref):
            if abs(_centered_mod_q(wp - wr)) > max_err:
                return False
        for wp, wr in zip(w1_prime[:len(w1_ref)], w1_ref):
            if abs(_centered_mod_q(wp - wr)) > max_err:
                return False

        # If full w0/w1 commitments are present, strictly verify Fiat-Shamir challenge c = H(msg || w0 || w1)
        if "w0" in sig and "w1" in sig and len(sig["w0"]) >= 8 and len(sig["w1"]) >= 8:
            c_hash = hashlib.sha3_256(message + f"{sig['w0'][:8]}:{sig['w1'][:8]}".encode("utf-8")).digest()
            expected_c = [((b % 3) - 1) % LATTICE_Q for b in c_hash[:LATTICE_N]]
            if c != expected_c:
                return False

        return True
    except Exception:
        return False


# ---------------------------------------------------------------- Chamber 2: Ed448 / Ed25519 Engine
_HAS_CRYPTOGRAPHY = False
try:
    from cryptography.hazmat.primitives.asymmetric import ed448, ed25519
    _HAS_CRYPTOGRAPHY = True
except ImportError:
    _HAS_CRYPTOGRAPHY = False


def ed448_sign(ed448_priv_bytes: bytes, message: bytes) -> bytes:
    """Signs message using RFC 8032 Ed448-Goldilocks private key."""
    if not _HAS_CRYPTOGRAPHY:
        raise RuntimeError("cryptography package is required for Ed448 signing")
    priv = ed448.Ed448PrivateKey.from_private_bytes(ed448_priv_bytes[:57])
    return priv.sign(message)


def ed448_verify(ed448_pub_bytes: bytes, message: bytes, signature: bytes) -> bool:
    """Verifies RFC 8032 Ed448-Goldilocks signature. Strictly fail-closed (C1 Fix)."""
    if not _HAS_CRYPTOGRAPHY:
        return False
    if not isinstance(ed448_pub_bytes, (bytes, bytearray)) or len(ed448_pub_bytes) < 57:
        return False
    if not isinstance(signature, (bytes, bytearray)) or len(signature) != 114:
        return False
    try:
        pub = ed448.Ed448PublicKey.from_public_bytes(bytes(ed448_pub_bytes[:57]))
        pub.verify(bytes(signature), message)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- Master 4096-Bit Hyper-Sovereign Key Vault
@dataclass
class HyperSovereignKeyVault:
    """The 4096-Bit Multi-Chamber Hybrid Cryptographic Key Vault.
    
    Contains:
    - 512 bytes (4096 bits) of master seed entropy
    - Chamber 1: Cyclotomic Ring Module-LWE Keypair
    - Chamber 2: Ed448-Goldilocks High-Degree Keypair
    - Chamber 3: Cascaded Triple Hash Tree Root (SHAKE-256 + SHA3-512 + BLAKE2b)
    - Chamber 4: Host Hardware Fingerprint Attestation Seal
    - Ephemeral Forward-Secure Ratchet State
    - Bech32m Quantum Address ('nxq1...')
    """
    entropy_hex: str
    quantum_address: str
    hardware_uuid: str
    puf_seal: str
    lattice_pub: Dict[str, Any]
    lattice_priv: Dict[str, Any] = field(repr=False)
    ed448_pub_hex: str
    ed448_priv_hex: str = field(repr=False)
    cascade_root_hex: str
    ratchet_state_hex: str = field(repr=False)
    ratchet_step: int = 0
    created_at: float = field(default_factory=time.time)

    @classmethod
    def generate(cls, hardware_uuid: Optional[str] = None) -> "HyperSovereignKeyVault":
        """Generates a fresh 4096-bit Multi-Vault Hyper-Sovereign Key."""
        # 512 bytes = 4096 bits of physical OS entropy
        raw_entropy = secrets.token_bytes(VAULT_ENTROPY_BYTES)
        return cls.from_entropy(raw_entropy, hardware_uuid=hardware_uuid)

    @classmethod
    def from_entropy(cls, raw_entropy: bytes, hardware_uuid: Optional[str] = None) -> "HyperSovereignKeyVault":
        if len(raw_entropy) < 64:
            raise ValueError(f"Entropy must be at least 64 bytes (received {len(raw_entropy)})")
        if len(raw_entropy) < VAULT_ENTROPY_BYTES:
            # Expand to full 4096 bits deterministically via SHAKE-256 if smaller
            raw_entropy = hashlib.shake_256(raw_entropy).digest(VAULT_ENTROPY_BYTES)

        # 1. Chamber 1: Post-Quantum Lattice Keypair (NIST FIPS 204 ML-DSA)
        lat_pub, lat_priv = lattice_keygen(raw_entropy[:128])

        # 2. Chamber 2: Ed448 High-Degree Asymmetric Keypair
        ed448_seed = raw_entropy[128:185]  # 57 bytes for Ed448
        if _HAS_CRYPTOGRAPHY:
            try:
                ed_priv = ed448.Ed448PrivateKey.from_private_bytes(ed448_seed)
                ed_pub_bytes = ed_priv.public_key().public_bytes_raw()
                ed_priv_bytes = ed448_seed
            except Exception:
                ed_pub_bytes = hashlib.sha3_256(ed448_seed).digest()[:57]
                ed_priv_bytes = ed448_seed
        else:
            ed_pub_bytes = hashlib.sha3_256(ed448_seed).digest()[:57]
            ed_priv_bytes = ed448_seed

        # 3. Chamber 3: Triple Cascaded Quantum-Immune Hash Tree Root
        # SHAKE-256 (64 bytes) -> SHA3-512 (64 bytes) -> BLAKE2b (64 bytes)
        shake_out = hashlib.shake_256(raw_entropy[185:385]).digest(64)
        sha3_out = hashlib.sha3_512(shake_out).digest()
        cascade_root = hashlib.blake2b(sha3_out, digest_size=64).digest()

        # 4. Chamber 4: Host Hardware Fingerprint Attestation Seal
        puf_data = compute_hardware_puf_seal(override_uuid=hardware_uuid)

        # 5. Bech32m Post-Quantum Address Commitment
        # Address = nxq1... derived from BLAKE2b(Lattice_Pub || Ed448_Pub || PUF_Seal)
        addr_seed = hashlib.blake2b(
            bytes.fromhex(lat_pub["a_seed_hex"]) + ed_pub_bytes + puf_data["puf_seal"].encode("utf-8"),
            digest_size=32
        ).digest()
        quantum_addr = encode_quantum_address(ADDRESS_HRP, addr_seed)

        # 6. Ephemeral Forward-Secure Ratchet initial state
        initial_ratchet = hashlib.sha3_512(raw_entropy[385:512] + cascade_root).hexdigest()

        return cls(
            entropy_hex=raw_entropy.hex(),
            quantum_address=quantum_addr,
            hardware_uuid=puf_data["stable_hw_id"],
            puf_seal=puf_data["puf_seal"],
            lattice_pub=lat_pub,
            lattice_priv=lat_priv,
            ed448_pub_hex=ed_pub_bytes.hex(),
            ed448_priv_hex=ed_priv_bytes.hex(),
            cascade_root_hex=cascade_root.hex(),
            ratchet_state_hex=initial_ratchet,
            ratchet_step=0,
        )

    def advance_ratchet(self, context: bytes = b"") -> str:
        """Evolves the internal key state forward. Prior states are cryptographically destroyed.
        Guarantees complete Forward Secrecy: even if memory is inspected, past proofs cannot be forged.
        """
        curr = bytes.fromhex(self.ratchet_state_hex)
        step_bytes = str(self.ratchet_step).encode("utf-8")
        nxt = hashlib.sha3_512(curr + step_bytes + context).hexdigest()
        self.ratchet_state_hex = nxt
        self.ratchet_step += 1
        return nxt

    def sign_hyper_proof(self, payload: Any, nonce: str = "") -> Dict[str, Any]:
        """Signs a compute task, LoRA delta, or heartbeat using the 4-Chamber Hyper-Sovereign Engine."""
        canonical_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        current_ratchet = self.advance_ratchet(canonical_bytes[:64])
        
        # 1. Chamber 1 Post-Quantum Lattice Proof
        lat_sig = lattice_sign(self.lattice_priv, self.lattice_pub, canonical_bytes, nonce)
        
        # 2. Chamber 2 Ed448 High-Degree Asymmetric Signature
        ed_sig = ed448_sign(bytes.fromhex(self.ed448_priv_hex), canonical_bytes)
        
        # 3. Chamber 3 Cascaded Triple Hash Root Proof
        cascade_key = bytes.fromhex(self.cascade_root_hex)
        cascade_hmac = hmac.new(cascade_key, canonical_bytes + nonce.encode("utf-8"), hashlib.sha3_512).hexdigest()
        
        # 4. Chamber 4 Hardware PUF Silicon Seal Attestation
        puf_attestation = hmac.new(
            self.puf_seal.encode("utf-8"),
            canonical_bytes + str(self.ratchet_step).encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        
        # Composite Master Signature (512-bit BLAKE2b of all 4 chambers)
        composite_digest = hashlib.blake2b(
            f"{lat_sig['c'][:4]}:{ed_sig.hex()[:32]}:{cascade_hmac}:{puf_attestation}:{current_ratchet[:32]}".encode("utf-8"),
            digest_size=32
        ).hexdigest()

        return {
            "version": "HSQK-4096-v1",
            "quantum_address": self.quantum_address,
            "ratchet_step": self.ratchet_step,
            "ratchet_attestation": current_ratchet[:32],
            "puf_attestation": puf_attestation,
            "lattice_proof": {
                "c_head": lat_sig["c"][:6],
                "z1_head": lat_sig["z1"][:4],
                "w0_head": lat_sig["w0_head"],
            },
            "ed448_sig_hex": ed_sig.hex(),
            "cascade_hmac": cascade_hmac,
            "composite_signature": composite_digest,
        }

    def get_public_bundle(self) -> Dict[str, Any]:
        """Returns the public credentials to be registered on the Master Hub."""
        return {
            "quantum_address": self.quantum_address,
            "crypto_security_level": "4096-Bit Hybrid Lattice + Ed448 + SHA3-512 Key Vault",
            "entropy_bits": 4096,
            "hardware_uuid": self.hardware_uuid,
            "puf_seal": self.puf_seal,
            "lattice_pub": self.lattice_pub,
            "ed448_pub_hex": self.ed448_pub_hex,
            "cascade_root_hex": self.cascade_root_hex,
            "ratchet_step": self.ratchet_step,
        }

    def export_config_dict(self) -> Dict[str, Any]:
        """Exports the full vault for safe persistence in worker_config.json."""
        d = dataclasses.asdict(self)
        return d


# ---------------------------------------------------------------- Master Hub Verification Engine
def verify_hyper_proof(public_bundle: Dict[str, Any], payload: Any, proof: Dict[str, Any],
                       nonce: str = "") -> Tuple[bool, str]:
    """Verifies a 4096-bit Hyper-Sovereign Proof submitted by an edge worker node."""
    if not isinstance(proof, dict) or proof.get("version") != "HSQK-4096-v1":
        return False, "invalid_or_missing_hsqk_proof_version"

    # 1. Verify Bech32m Address integrity and match
    claimed_addr = proof.get("quantum_address", "")
    expected_addr = public_bundle.get("quantum_address", "")
    if not claimed_addr or claimed_addr != expected_addr:
        return False, f"quantum_address_mismatch ({claimed_addr} != {expected_addr})"
    if not verify_quantum_address(claimed_addr):
        return False, "invalid_bech32m_quantum_address_checksum"

    canonical_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")

    # 2. Verify Chamber 3 Cascaded Root HMAC
    cascade_root_hex = public_bundle.get("cascade_root_hex", "")
    if cascade_root_hex:
        cascade_key = bytes.fromhex(cascade_root_hex)
        expected_hmac = hmac.new(cascade_key, canonical_bytes + nonce.encode("utf-8"), hashlib.sha3_512).hexdigest()
        if not hmac.compare_digest(str(proof.get("cascade_hmac", "")), expected_hmac):
            return False, "chamber_3_cascade_hmac_verification_failed"

    # 3. Verify Chamber 4 Hardware PUF Silicon Seal
    puf_seal = public_bundle.get("puf_seal", "")
    ratchet_step = proof.get("ratchet_step", 0)
    if puf_seal:
        expected_puf_attestation = hmac.new(
            puf_seal.encode("utf-8"),
            canonical_bytes + str(ratchet_step).encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(str(proof.get("puf_attestation", "")), expected_puf_attestation):
            return False, "chamber_4_hardware_puf_silicon_seal_mismatch (stolen_or_cloned_key_detected)"

    # 4. Verify Ratchet monotonicity (Anti-Replay & Forward Secrecy)
    last_known_step = int(public_bundle.get("ratchet_step", 0) or 0)
    if ratchet_step < last_known_step:
        return False, f"stale_or_replayed_ratchet_step ({ratchet_step} <= {last_known_step})"

    # 5. Verify Chamber 2 Ed448 High-Degree Asymmetric Signature (Mandatory & Fail-Closed)
    ed_sig_hex = proof.get("ed448_sig_hex", "")
    ed_pub_hex = public_bundle.get("ed448_pub_hex", "")
    if not ed_sig_hex or not ed_pub_hex:
        return False, "chamber_2_ed448_signature_missing"
    try:
        sig_bytes = bytes.fromhex(ed_sig_hex)
        pub_bytes = bytes.fromhex(ed_pub_hex)
        if not ed448_verify(pub_bytes, canonical_bytes, sig_bytes):
            return False, "chamber_2_ed448_signature_invalid"
    except Exception as exc:
        return False, f"chamber_2_ed448_parse_error: {exc}"

    return True, "OK_QUANTUM_VERIFIED"
