#!/usr/bin/env python3
"""
NEXUS Sovereign Mesh — Neural Consensus Models Downloader & Attestation
Downloads, pins, and verifies the CPU ONNX models required for neural semantic
embedding and cross-encoder contradiction detection in Sovereign Mesh consensus.

Models:
  1. Xenova/all-MiniLM-L6-v2      (ONNX Quantized ~21.9 MB)
  2. Xenova/nli-deberta-v3-xsmall (ONNX Quantized ~83.2 MB)

Usage:
  python scripts/download_models.py
  python scripts/download_models.py --verify-only
  python scripts/download_models.py --force
"""

import sys
import os
import argparse
import hashlib
from typing import Tuple, Dict, Any

MODELS: Dict[str, Dict[str, Any]] = {
    "embedding": {
        "name": "MiniLM-L6-v2",
        "repo_id": "Xenova/all-MiniLM-L6-v2",
        "revision": "751bff37182d3f1213fa05d7196b954e230abad9",
        "onnx_subpath": "onnx/model_quantized.onnx",
        "expected_sha256": "afdb6f1a0e45b715d0bb9b11772f032c399babd23bfc31fed1c170afc848bdb1",
        "expected_size": 22972370,
        "description": "384-dimensional dense sentence embeddings for semantic similarity & grounding",
    },
    "nli": {
        "name": "NLI-DeBERTa-v3-xsmall",
        "repo_id": "Xenova/nli-deberta-v3-xsmall",
        "revision": "2a4f614a701367a02d51389039afc998faeda637",
        "onnx_subpath": "onnx/model_quantized.onnx",
        "expected_sha256": "3fac2500c45c75af42c7711de0d1b93d59577456100208be0dc1f9e8811946b6",
        "expected_size": 87246587,
        "description": "Cross-encoder NLI classifier for factual contradiction & inversion detection",
    },
}


def compute_file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def verify_model(key: str) -> Tuple[bool, str]:
    spec = MODELS[key]
    try:
        from huggingface_hub import hf_hub_download
        from transformers import AutoTokenizer, AutoConfig
    except ImportError as exc:
        return False, f"Missing required libraries: {exc}"

    try:
        onnx_path = hf_hub_download(
            repo_id=spec["repo_id"],
            filename=spec["onnx_subpath"],
            revision=spec["revision"],
            local_files_only=True,
        )
    except Exception as exc:
        return False, f"ONNX file not found in local cache: {exc}"

    if not os.path.exists(onnx_path):
        return False, f"File does not exist: {onnx_path}"

    sha = compute_file_sha256(onnx_path)
    if sha != spec["expected_sha256"]:
        return False, f"SHA-256 mismatch: got {sha}, expected {spec['expected_sha256']}"

    try:
        AutoTokenizer.from_pretrained(spec["repo_id"], revision=spec["revision"], local_files_only=True)
    except Exception as exc:
        return False, f"Tokenizer verification failed: {exc}"

    if key == "nli":
        try:
            AutoConfig.from_pretrained(spec["repo_id"], revision=spec["revision"], local_files_only=True)
        except Exception as exc:
            return False, f"Config verification failed: {exc}"

    return True, onnx_path


def download_model(key: str, force: bool = False) -> bool:
    spec = MODELS[key]
    if not force:
        ok, path = verify_model(key)
        if ok:
            print(f"  [*] {spec['name']} already verified in cache: {path}")
            return True

    print(f"  [>] Downloading {spec['name']} from huggingface.co/{spec['repo_id']} (rev: {spec['revision'][:8]})...")
    try:
        from huggingface_hub import snapshot_download
        snapshot_download(
            repo_id=spec["repo_id"],
            revision=spec["revision"],
            allow_patterns=["*.json", "*.txt", spec["onnx_subpath"]],
        )
    except Exception as exc:
        print(f"  [!] Download failed for {spec['name']}: {exc}")
        return False

    ok, path = verify_model(key)
    if ok:
        print(f"  [+] {spec['name']} verified successfully: {path}")
        return True
    else:
        print(f"  [!] Post-download verification failed for {spec['name']}: {path}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Download & attest NEXUS neural consensus models")
    parser.add_argument("--verify-only", action="store_true", help="Only verify existing models without downloading")
    parser.add_argument("--force", action="store_true", help="Force re-download of models even if present")
    args = parser.parse_args()

    print("=" * 72)
    print("  NEXUS Sovereign Mesh — Neural Consensus Models Attestation")
    print("=" * 72)

    all_ok = True
    for key, spec in MODELS.items():
        print(f"\nChecking {spec['name']} ({spec['description']}):")
        if args.verify_only:
            ok, res = verify_model(key)
            if ok:
                print(f"  [+] STATUS: ACTIVE (SHA-256 attested: {spec['expected_sha256'][:16]}...)")
                print(f"      Path: {res}")
            else:
                print(f"  [-] STATUS: INACTIVE ({res})")
                all_ok = False
        else:
            success = download_model(key, force=args.force)
            if not success:
                all_ok = False

    print("\n" + "=" * 72)
    if all_ok:
        print("  [SUCCESS] All neural consensus models are ACTIVE and attested.")
        print("            Free-form semantic consensus & NLI guards are fully operational.")
        print("=" * 72)
        sys.exit(0)
    else:
        print("  [FAILURE] One or more neural models are missing or failed attestation.")
        print("            Free-form semantic consensus will operate in FAIL-CLOSED mode.")
        print("=" * 72)
        sys.exit(1)


if __name__ == "__main__":
    main()
