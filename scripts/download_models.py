#!/usr/bin/env python3
"""
NEXUS Sovereign Mesh — Neural Consensus Models Downloader & Attestation
Downloads, pins, and verifies the CPU ONNX models required for neural semantic
embedding and cross-encoder contradiction detection in Sovereign Mesh consensus.

Verifies exact SHA-256 cryptographic signatures for:
  - ONNX quantized model weights
  - Model configuration (config.json)
  - Tokenizer vocabulary and state (tokenizer.json, tokenizer_config.json, special_tokens_map.json)

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
        "description": "384-dimensional dense sentence embeddings for semantic similarity & grounding",
        "files": {
            "onnx/model_quantized.onnx": {
                "sha256": "afdb6f1a0e45b715d0bb9b11772f032c399babd23bfc31fed1c170afc848bdb1",
                "size": 22972370,
            },
            "config.json": {
                "sha256": "7135149f7cffa1a573466c6e4d8423ed73b62fd2332c575bf738a0d033f70df7",
                "size": 650,
            },
            "tokenizer.json": {
                "sha256": "da0e79933b9ed51798a3ae27893d3c5fa4a201126cef75586296df9b4d2c62a0",
                "size": 711661,
            },
            "tokenizer_config.json": {
                "sha256": "9261e7d79b44c8195c1cada2b453e55b00aeb81e907a6664974b4d7776172ab3",
                "size": 366,
            },
            "special_tokens_map.json": {
                "sha256": "b6d346be366a7d1d48332dbc9fdf3bf8960b5d879522b7799ddba59e76237ee3",
                "size": 125,
            },
        },
    },
    "nli": {
        "name": "NLI-DeBERTa-v3-xsmall",
        "repo_id": "Xenova/nli-deberta-v3-xsmall",
        "revision": "2a4f614a701367a02d51389039afc998faeda637",
        "description": "Cross-encoder NLI classifier for factual contradiction & inversion detection",
        "files": {
            "onnx/model_quantized.onnx": {
                "sha256": "3fac2500c45c75af42c7711de0d1b93d59577456100208be0dc1f9e8811946b6",
                "size": 87246587,
            },
            "config.json": {
                "sha256": "ec0bd14cc28640326474399cd61d38ccd52b64900228799d0f81debda8c4bc53",
                "size": 1038,
            },
            "tokenizer.json": {
                "sha256": "a86f883318afa11c8c10466f1bf4efaeb6ded28a52cbe57217a8fa0d0a2a87df",
                "size": 8656551,
            },
            "tokenizer_config.json": {
                "sha256": "d8d3bb123b99317634d5ee3d1d2d8b2ddb01510a0654687fc2639a5347a7291f",
                "size": 384,
            },
            "special_tokens_map.json": {
                "sha256": "311de3f4eed9d76a43bf0d71f10e62e086ca65ccce9f15d5da0d2098bf519ecc",
                "size": 173,
            },
        },
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

    verified_paths = []
    for rel_path, meta in spec["files"].items():
        try:
            local_path = hf_hub_download(
                repo_id=spec["repo_id"],
                filename=rel_path,
                revision=spec["revision"],
                local_files_only=True,
            )
        except Exception as exc:
            return False, f"File '{rel_path}' not found in local cache: {exc}"

        if not os.path.exists(local_path):
            return False, f"File does not exist: {local_path}"

        actual_sha = compute_file_sha256(local_path)
        if actual_sha != meta["sha256"]:
            return False, f"SHA-256 mismatch for {rel_path}: got {actual_sha}, expected {meta['sha256']}"

        verified_paths.append(local_path)

    # Sanity check: Ensure tokenizer and config can initialize from verified cache
    try:
        AutoTokenizer.from_pretrained(spec["repo_id"], revision=spec["revision"], local_files_only=True)
    except Exception as exc:
        return False, f"Tokenizer verification failed: {exc}"

    if key == "nli":
        try:
            AutoConfig.from_pretrained(spec["repo_id"], revision=spec["revision"], local_files_only=True)
        except Exception as exc:
            return False, f"Config verification failed: {exc}"

    return True, verified_paths[0]


def download_model(key: str, force: bool = False) -> bool:
    spec = MODELS[key]
    if not force:
        ok, path = verify_model(key)
        if ok:
            print(f"  [*] {spec['name']} already verified in cache (all 5 files attested): {path}")
            return True

    print(f"  [>] Downloading {spec['name']} from huggingface.co/{spec['repo_id']} (rev: {spec['revision'][:8]})...")
    try:
        from huggingface_hub import snapshot_download
        snapshot_download(
            repo_id=spec["repo_id"],
            revision=spec["revision"],
            allow_patterns=["*.json", "*.txt", "onnx/model_quantized.onnx"],
        )
    except Exception as exc:
        print(f"  [!] Download failed for {spec['name']}: {exc}")
        return False

    ok, path = verify_model(key)
    if ok:
        print(f"  [+] {spec['name']} verified successfully (all files attested): {path}")
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
                print(f"  [+] STATUS: ACTIVE (All files verified & attested)")
                for fpath, fmeta in spec["files"].items():
                    print(f"      - {fpath:25}: sha256={fmeta['sha256'][:16]}...")
            else:
                print(f"  [-] STATUS: INACTIVE ({res})")
                all_ok = False
        else:
            success = download_model(key, force=args.force)
            if not success:
                all_ok = False

    print("\n" + "=" * 72)
    if all_ok:
        print("  [SUCCESS] All neural consensus models & tokenizers are ACTIVE and attested.")
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
