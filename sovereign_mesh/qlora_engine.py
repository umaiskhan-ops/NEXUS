"""NEXUS Sovereign Mesh — Marhala 2 Real HuggingFace QLoRA Engine, PEFT-to-GGUF Converter & Compatibility Gate.

Implements the complete production QLoRA / LoRA pipeline:
  1. `RealQLoRAEngine`:
     - Loads a real pretrained Causal LM via `transformers.AutoModelForCausalLM.from_pretrained`
       and `AutoTokenizer.from_pretrained`.
     - Configures 4-bit NF4 quantization via `transformers.BitsAndBytesConfig` (`bitsandbytes`)
       when running on CUDA GPU.
     - Injects low-rank adapters via `peft.LoraConfig` and `peft.get_peft_model`.
     - Fine-tunes on objectively verified `(prompt, solution)` pairs using `trl.SFTTrainer`
       (`SFTConfig`) or HuggingFace token-level CausalLM cross-entropy backpropagation
       with `-100` prompt-token masking.
     - Saves the trained adapter via `peft_model.save_pretrained(peft_dir)` (`adapter_config.json`
       + `adapter_model.safetensors`).
  2. `PeftToGGUFConverter`:
     - Converts a `save_pretrained` PEFT adapter directory into a spec-compliant GGUF v3
       LoRA adapter binary (`.gguf`) for that exact base model architecture (invoking
       `llama.cpp`'s `convert_lora_to_gguf.py` when configured, or mapping PEFT `.safetensors`
       weights directly to `blk.{i}.attn_{q,k,v,output}.weight.lora_{a,b}`).
  3. `AdapterModelCompatibilityValidator`:
     - Strictly verifies BEFORE `ollama create` that the GGUF adapter's `base_model`,
       `hidden_size` (both header metadata and `lora_a` tensor shape), and `num_hidden_layers`
       (both header metadata and `blk.<layer_idx>` count) match `base_model_tag`.
     - Any mismatch (e.g., pairing a 64-dim 1-layer adapter with `llama3.1:8b` which requires
       `hidden_size=4096, num_hidden_layers=32`) immediately fails closed with
       `ADAPTER_MODEL_MISMATCH`.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .brain_matrix import SafeTensorsIO

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    torch = None  # type: ignore[assignment]
    nn = None  # type: ignore[assignment]
    F = None  # type: ignore[assignment]
    TORCH_AVAILABLE = False

try:
    import transformers  # type: ignore[import-untyped]
    from transformers import (  # type: ignore[import-untyped]
        AutoConfig,
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        Trainer,
        TrainingArguments,
    )
    TRANSFORMERS_AVAILABLE = AutoModelForCausalLM is not None
except Exception:
    transformers = None  # type: ignore[assignment]
    AutoConfig = None  # type: ignore[assignment]
    AutoModelForCausalLM = None  # type: ignore[assignment]
    AutoTokenizer = None  # type: ignore[assignment]
    BitsAndBytesConfig = None  # type: ignore[assignment]
    Trainer = None  # type: ignore[assignment]
    TrainingArguments = None  # type: ignore[assignment]
    TRANSFORMERS_AVAILABLE = False

try:
    import peft  # type: ignore[import-untyped]
    from peft import (  # type: ignore[import-untyped]
        LoraConfig,
        PeftModel,
        TaskType,
        get_peft_model,
        prepare_model_for_kbit_training,
    )
    PEFT_AVAILABLE = True
except Exception:
    peft = None  # type: ignore[assignment]
    LoraConfig = None  # type: ignore[assignment]
    PeftModel = None  # type: ignore[assignment]
    TaskType = None  # type: ignore[assignment]
    get_peft_model = None  # type: ignore[assignment]
    prepare_model_for_kbit_training = None  # type: ignore[assignment]
    PEFT_AVAILABLE = False

try:
    import trl  # type: ignore[import-untyped]
    from trl import SFTConfig, SFTTrainer  # type: ignore[import-untyped]
    TRL_AVAILABLE = True
except Exception:
    trl = None  # type: ignore[assignment]
    SFTConfig = None  # type: ignore[assignment]
    SFTTrainer = None  # type: ignore[assignment]
    TRL_AVAILABLE = False

try:
    import bitsandbytes as bnb  # type: ignore[import-untyped]
    BITSANDBYTES_AVAILABLE = True
except Exception:
    bnb = None  # type: ignore[assignment]
    BITSANDBYTES_AVAILABLE = False


def is_hf_qlora_stack_ready() -> bool:
    """Returns True only when PyTorch, HuggingFace `AutoModelForCausalLM`, and `peft` are all functional."""
    if not (TORCH_AVAILABLE and TRANSFORMERS_AVAILABLE and PEFT_AVAILABLE):
        return False
    try:
        # transformers >= 5.0 disables AutoModelForCausalLM if torch < 2.4
        _ = getattr(AutoModelForCausalLM, "from_pretrained")
        if hasattr(transformers, "is_torch_available") and not transformers.is_torch_available():
            return False
        return True
    except Exception:
        return False


# =====================================================================
# 1. SPEC-COMPLIANT GGUF v3 LORA BINARY EXPORTER & PARSER
# =====================================================================

GGUF_MAGIC = b"GGUF"
GGUF_VERSION = 3
GGUF_DEFAULT_ALIGNMENT = 32

GGUF_TYPE_UINT32 = 4
GGUF_TYPE_INT32 = 5
GGUF_TYPE_FLOAT32 = 6
GGUF_TYPE_BOOL = 7
GGUF_TYPE_STRING = 8

GGML_TYPE_F32 = 0


class GGUFLoRAExporter:
    """Writes and verifies spec-compliant GGUF v3 LoRA adapter files for Ollama / llama.cpp."""

    @staticmethod
    def _pack_string(s: str) -> bytes:
        raw = s.encode("utf-8")
        return struct.pack("<Q", len(raw)) + raw

    @classmethod
    def _pack_kv(cls, key: str, val_type: int, value: Any) -> bytes:
        buf = cls._pack_string(key) + struct.pack("<I", val_type)
        if val_type == GGUF_TYPE_STRING:
            buf += cls._pack_string(str(value))
        elif val_type == GGUF_TYPE_FLOAT32:
            buf += cls._pack_pack_f32(float(value)) if hasattr(cls, "_pack_pack_f32") else struct.pack("<f", float(value))
        elif val_type == GGUF_TYPE_UINT32:
            buf += struct.pack("<I", int(value))
        elif val_type == GGUF_TYPE_INT32:
            buf += struct.pack("<i", int(value))
        elif val_type == GGUF_TYPE_BOOL:
            buf += struct.pack("<?", bool(value))
        else:
            raise ValueError(f"Unsupported GGUF KV type: {val_type}")
        return buf

    @classmethod
    def save(
        cls,
        file_path: Path,
        tensors: Dict[str, Tuple[List[int], List[float]]],
        alpha: float = 16.0,
        rank: int = 8,
        arch: str = "llama",
        base_model: str = "",
        hidden_size: Optional[int] = None,
        num_hidden_layers: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Serializes LoRA A/B tensors into a GGUF v3 binary adapter file with architectural metadata."""
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Infer hidden_size and num_hidden_layers from tensor table if not explicitly provided
        inferred_hidden = hidden_size
        layer_indices: Set[int] = set()
        for tname, (shape, _) in tensors.items():
            m = re.match(r"^blk\.(\d+)\.", tname)
            if m:
                layer_indices.add(int(m.group(1)))
            if inferred_hidden is None and tname.endswith(".lora_a") and len(shape) == 2:
                inferred_hidden = int(shape[1])

        eff_hidden = int(inferred_hidden) if inferred_hidden is not None else 64
        eff_layers = int(num_hidden_layers) if num_hidden_layers is not None else max(1, len(layer_indices))

        kv_entries: List[Tuple[str, int, Any]] = [
            ("general.architecture", GGUF_TYPE_STRING, arch),
            ("general.type", GGUF_TYPE_STRING, "adapter"),
            ("adapter.type", GGUF_TYPE_STRING, "lora"),
            ("adapter.lora.alpha", GGUF_TYPE_FLOAT32, float(alpha)),
            ("adapter.lora.rank", GGUF_TYPE_UINT32, int(rank)),
            (f"{arch}.embedding_length", GGUF_TYPE_UINT32, eff_hidden),
            (f"{arch}.block_count", GGUF_TYPE_UINT32, eff_layers),
            ("adapter.base.hidden_size", GGUF_TYPE_UINT32, eff_hidden),
            ("adapter.base.num_hidden_layers", GGUF_TYPE_UINT32, eff_layers),
        ]
        if base_model:
            kv_entries.append(("general.base_model.0.name", GGUF_TYPE_STRING, str(base_model)))

        header = bytearray()
        header += GGUF_MAGIC
        header += struct.pack("<I", GGUF_VERSION)
        header += struct.pack("<Q", len(tensors))
        header += struct.pack("<Q", len(kv_entries))

        for k, vtype, val in kv_entries:
            header += cls._pack_kv(k, vtype, val)

        tensor_infos = bytearray()
        data_blobs: List[bytes] = []
        current_offset = 0

        for name, (shape, flat_vals) in tensors.items():
            expected_numel = 1
            for d in shape:
                expected_numel *= int(d)
            if len(flat_vals) != expected_numel:
                raise ValueError(
                    f"GGUF tensor '{name}' shape {shape} expects {expected_numel} floats, got {len(flat_vals)}"
                )

            tensor_infos += cls._pack_string(name)
            tensor_infos += struct.pack("<I", len(shape))
            for dim in reversed(shape):
                tensor_infos += struct.pack("<Q", int(dim))
            tensor_infos += struct.pack("<I", GGML_TYPE_F32)
            tensor_infos += struct.pack("<Q", current_offset)

            raw_bytes = struct.pack(f"<{len(flat_vals)}f", *flat_vals)
            pad_len = (GGUF_DEFAULT_ALIGNMENT - (len(raw_bytes) % GGUF_DEFAULT_ALIGNMENT)) % GGUF_DEFAULT_ALIGNMENT
            aligned_bytes = raw_bytes + (b"\x00" * pad_len)
            data_blobs.append(aligned_bytes)
            current_offset += len(aligned_bytes)

        pre_data = bytes(header) + bytes(tensor_infos)
        header_pad = (GGUF_DEFAULT_ALIGNMENT - (len(pre_data) % GGUF_DEFAULT_ALIGNMENT)) % GGUF_DEFAULT_ALIGNMENT
        full_binary = pre_data + (b"\x00" * header_pad) + b"".join(data_blobs)

        file_path.write_bytes(full_binary)
        sha256_hex = hashlib.sha256(full_binary).hexdigest()
        return {
            "path": str(file_path),
            "size_bytes": len(full_binary),
            "sha256": sha256_hex,
            "version": GGUF_VERSION,
            "tensor_count": len(tensors),
            "alpha": alpha,
            "rank": rank,
            "arch": arch,
            "base_model": base_model,
            "hidden_size": eff_hidden,
            "num_hidden_layers": eff_layers,
        }

    @classmethod
    def verify_gguf_header(cls, file_path: Path) -> Dict[str, Any]:
        """Parses and verifies a GGUF v3 binary LoRA file header, KV metadata, and tensor table."""
        if not file_path.exists():
            raise FileNotFoundError(f"GGUF file not found: {file_path}")
        data = file_path.read_bytes()
        if len(data) < 24:
            raise ValueError("File too small to be a valid GGUF v3 binary.")
        magic = data[:4]
        if magic != GGUF_MAGIC:
            raise ValueError(f"Invalid GGUF magic bytes: {magic!r}")
        version, n_tensors, n_kv = struct.unpack("<IQQ", data[4:24])
        if version != GGUF_VERSION:
            raise ValueError(f"Unsupported GGUF version: {version}")

        pos = 24

        def _read_str(p: int) -> Tuple[str, int]:
            (slen,) = struct.unpack("<Q", data[p : p + 8])
            p += 8
            s = data[p : p + slen].decode("utf-8")
            return s, p + slen

        metadata: Dict[str, Any] = {}
        for _ in range(n_kv):
            key, pos = _read_str(pos)
            (vtype,) = struct.unpack("<I", data[pos : pos + 4])
            pos += 4
            if vtype == GGUF_TYPE_STRING:
                val, pos = _read_str(pos)
            elif vtype == GGUF_TYPE_FLOAT32:
                (val,) = struct.unpack("<f", data[pos : pos + 4])
                pos += 4
            elif vtype == GGUF_TYPE_UINT32:
                (val,) = struct.unpack("<I", data[pos : pos + 4])
                pos += 4
            elif vtype == GGUF_TYPE_INT32:
                (val,) = struct.unpack("<i", data[pos : pos + 4])
                pos += 4
            elif vtype == GGUF_TYPE_BOOL:
                (val,) = struct.unpack("<?", data[pos : pos + 1])
                pos += 1
            else:
                raise ValueError(f"Unknown GGUF KV type {vtype} for key {key}")
            metadata[key] = val

        tensors: List[Dict[str, Any]] = []
        for _ in range(n_tensors):
            tname, pos = _read_str(pos)
            (n_dims,) = struct.unpack("<I", data[pos : pos + 4])
            pos += 4
            dims_rev = []
            for _ in range(n_dims):
                (d,) = struct.unpack("<Q", data[pos : pos + 8])
                pos += 8
                dims_rev.append(d)
            shape = list(reversed(dims_rev))
            ggml_type, offset = struct.unpack("<IQ", data[pos : pos + 12])
            pos += 12
            tensors.append({
                "name": tname,
                "shape": shape,
                "ggml_type": ggml_type,
                "offset": offset,
            })

        return {
            "valid": True,
            "magic": "GGUF",
            "version": version,
            "n_tensors": n_tensors,
            "n_kv": n_kv,
            "metadata": metadata,
            "tensors": tensors,
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }


# =====================================================================
# 2. ADAPTER <-> BASE MODEL COMPATIBILITY VALIDATOR (PRE-OLLAMA CREATE)
# =====================================================================

KNOWN_BASE_MODEL_SPECS: Dict[str, Dict[str, Any]] = {
    "llama3.1:8b": {
        "arch": "llama",
        "hidden_size": 4096,
        "num_hidden_layers": 32,
        "hf_base_models": [
            "llama3.1:8b",
            "meta-llama/Llama-3.1-8B",
            "meta-llama/Llama-3.1-8B-Instruct",
            "meta-llama/Meta-Llama-3.1-8B",
            "meta-llama/Meta-Llama-3.1-8B-Instruct",
        ],
    },
    "llama3.1:70b": {
        "arch": "llama",
        "hidden_size": 8192,
        "num_hidden_layers": 80,
        "hf_base_models": [
            "llama3.1:70b",
            "meta-llama/Llama-3.1-70B",
            "meta-llama/Llama-3.1-70B-Instruct",
        ],
    },
    "llama3.2:1b": {
        "arch": "llama",
        "hidden_size": 2048,
        "num_hidden_layers": 16,
        "hf_base_models": [
            "llama3.2:1b",
            "meta-llama/Llama-3.2-1B",
            "meta-llama/Llama-3.2-1B-Instruct",
        ],
    },
    "llama3.2:3b": {
        "arch": "llama",
        "hidden_size": 3072,
        "num_hidden_layers": 28,
        "hf_base_models": [
            "llama3.2:3b",
            "meta-llama/Llama-3.2-3B",
            "meta-llama/Llama-3.2-3B-Instruct",
        ],
    },
    "mistral:7b": {
        "arch": "llama",
        "hidden_size": 4096,
        "num_hidden_layers": 32,
        "hf_base_models": [
            "mistral:7b",
            "mistralai/Mistral-7B-v0.1",
            "mistralai/Mistral-7B-v0.3",
            "mistralai/Mistral-7B-Instruct-v0.3",
        ],
    },
    "gpt-oss:20b": {
        "arch": "llama",
        "hidden_size": 5120,
        "num_hidden_layers": 40,
        "hf_base_models": [
            "gpt-oss:20b",
            "openai/gpt-oss-20b",
        ],
    },
    "qwen2.5:7b": {
        "arch": "qwen2",
        "hidden_size": 3584,
        "num_hidden_layers": 28,
        "hf_base_models": [
            "qwen2.5:7b",
            "Qwen/Qwen2.5-7B",
            "Qwen/Qwen2.5-7B-Instruct",
        ],
    },
    "nexus-proto:64d-1l": {
        "arch": "llama",
        "hidden_size": 64,
        "num_hidden_layers": 1,
        "hf_base_models": [
            "nexus-proto:64d-1l",
            "nexus-local/proto-64d-1l",
        ],
    },
    "tiny-llama:64d-2l": {
        "arch": "llama",
        "hidden_size": 64,
        "num_hidden_layers": 2,
        "hf_base_models": [
            "tiny-llama:64d-2l",
            "hf_tiny_llama_base",
        ],
    },
}


class AdapterModelCompatibilityValidator:
    """Verifies before `ollama create` that a GGUF LoRA adapter matches `base_model_tag`'s base, hidden_size, and layers."""

    @classmethod
    def register_base_model_spec(
        cls,
        base_model_tag: str,
        hidden_size: int,
        num_hidden_layers: int,
        arch: str = "llama",
        hf_base_models: Optional[List[str]] = None,
    ) -> None:
        tag = base_model_tag.strip()
        models = list(hf_base_models or [])
        if tag not in models:
            models.append(tag)
        KNOWN_BASE_MODEL_SPECS[tag] = {
            "arch": arch,
            "hidden_size": int(hidden_size),
            "num_hidden_layers": int(num_hidden_layers),
            "hf_base_models": models,
        }

    @classmethod
    def resolve_expected_spec(cls, base_model_tag: str) -> Optional[Dict[str, Any]]:
        tag = (base_model_tag or "").strip()
        if not tag:
            return None
        if tag in KNOWN_BASE_MODEL_SPECS:
            return dict(KNOWN_BASE_MODEL_SPECS[tag])

        # Check if `base_model_tag` is a path to a local HuggingFace directory with `config.json`
        cfg_path = Path(tag) / "config.json"
        if cfg_path.exists():
            try:
                cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                h_size = int(cfg.get("hidden_size") or cfg.get("n_embd") or 0)
                n_layers = int(cfg.get("num_hidden_layers") or cfg.get("n_layer") or 0)
                arch = str(cfg.get("model_type") or "llama")
                if h_size > 0 and n_layers > 0:
                    return {
                        "arch": arch,
                        "hidden_size": h_size,
                        "num_hidden_layers": n_layers,
                        "hf_base_models": [tag, str(Path(tag).resolve())],
                    }
            except Exception:
                pass
        return None

    @classmethod
    def validate(
        cls,
        gguf_path: Path,
        base_model_tag: str,
        expected_spec: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Checks that the GGUF adapter at `gguf_path` matches `base_model_tag` in base model, hidden_size, and layer count."""
        tag = (base_model_tag or "").strip()
        spec = expected_spec or cls.resolve_expected_spec(tag)
        if spec is None:
            return {
                "compatible": False,
                "base_model_tag": tag,
                "reason": (
                    f"ADAPTER_MODEL_MISMATCH: Unknown or unregistered base_model_tag '{tag}'. "
                    f"Cannot verify hidden_size and num_hidden_layers compatibility."
                ),
            }

        try:
            gguf_info = GGUFLoRAExporter.verify_gguf_header(gguf_path)
        except Exception as exc:
            return {
                "compatible": False,
                "base_model_tag": tag,
                "reason": f"ADAPTER_MODEL_MISMATCH: Invalid GGUF file ({exc}).",
            }

        meta = gguf_info.get("metadata", {})
        tensors = gguf_info.get("tensors", [])

        if meta.get("general.type") != "adapter" or meta.get("adapter.type") != "lora":
            return {
                "compatible": False,
                "base_model_tag": tag,
                "reason": "ADAPTER_MODEL_MISMATCH: GGUF binary is not a valid LoRA adapter (general.type != 'adapter').",
            }

        exp_hidden = int(spec["hidden_size"])
        exp_layers = int(spec["num_hidden_layers"])
        allowed_bases = {str(b).strip().lower() for b in spec.get("hf_base_models", [tag])}
        allowed_bases.add(tag.lower())

        # 1. Base model name check
        adapter_base = str(meta.get("general.base_model.0.name", "") or "").strip()
        if not adapter_base:
            return {
                "compatible": False,
                "base_model_tag": tag,
                "reason": (
                    f"ADAPTER_MODEL_MISMATCH: GGUF adapter is missing 'general.base_model.0.name' metadata "
                    f"required to verify compatibility with '{tag}'."
                ),
            }
        if adapter_base.lower() not in allowed_bases and Path(adapter_base).name.lower() not in allowed_bases:
            return {
                "compatible": False,
                "base_model_tag": tag,
                "adapter_base_model": adapter_base,
                "expected_base_models": sorted(allowed_bases),
                "reason": (
                    f"ADAPTER_MODEL_MISMATCH: Adapter base_model '{adapter_base}' does not match "
                    f"target base_model_tag '{tag}' (allowed: {sorted(allowed_bases)})."
                ),
            }

        # 2. Hidden size check (both metadata AND actual tensor dimensions)
        arch = str(meta.get("general.architecture", "llama"))
        meta_hidden = int(
            meta.get(f"{arch}.embedding_length")
            or meta.get("llama.embedding_length")
            or meta.get("adapter.base.hidden_size")
            or 0
        )
        if meta_hidden != exp_hidden:
            return {
                "compatible": False,
                "base_model_tag": tag,
                "adapter_hidden_size": meta_hidden,
                "expected_hidden_size": exp_hidden,
                "reason": (
                    f"ADAPTER_MODEL_MISMATCH: Adapter metadata hidden_size={meta_hidden} does not match "
                    f"base_model_tag '{tag}' hidden_size={exp_hidden}."
                ),
            }

        # Inspect actual tensor shapes in GGUF table
        lora_a_tensors = [
            t for t in tensors
            if t["name"].endswith(".lora_a") and any(p in t["name"] for p in ("attn_q", "attn_k", "attn_v", "attn_output"))
        ]
        if not lora_a_tensors:
            return {
                "compatible": False,
                "base_model_tag": tag,
                "reason": "ADAPTER_MODEL_MISMATCH: GGUF adapter contains no attention lora_a tensors.",
            }

        for t in lora_a_tensors:
            shape = t.get("shape", [])
            if len(shape) != 2 or int(shape[1]) != exp_hidden:
                return {
                    "compatible": False,
                    "base_model_tag": tag,
                    "tensor_name": t["name"],
                    "tensor_shape": shape,
                    "expected_hidden_size": exp_hidden,
                    "reason": (
                        f"ADAPTER_MODEL_MISMATCH: Tensor '{t['name']}' has shape {shape} (in_features={shape[1] if len(shape)>1 else 'N/A'}), "
                        f"but base_model_tag '{tag}' requires hidden_size={exp_hidden}."
                    ),
                }

        # 3. Layer count check (both metadata AND actual blk.<idx> tensors)
        meta_layers = int(
            meta.get(f"{arch}.block_count")
            or meta.get("llama.block_count")
            or meta.get("adapter.base.num_hidden_layers")
            or 0
        )
        layer_indices: Set[int] = set()
        for t in tensors:
            m = re.match(r"^blk\.(\d+)\.", t["name"])
            if m:
                layer_indices.add(int(m.group(1)))

        actual_layers = len(layer_indices)
        if meta_layers != exp_layers or actual_layers != exp_layers:
            return {
                "compatible": False,
                "base_model_tag": tag,
                "adapter_meta_layers": meta_layers,
                "adapter_tensor_layers": actual_layers,
                "expected_num_layers": exp_layers,
                "reason": (
                    f"ADAPTER_MODEL_MISMATCH: Adapter has {actual_layers} tensor layer(s) (meta={meta_layers}), "
                    f"but base_model_tag '{tag}' requires num_hidden_layers={exp_layers}."
                ),
            }

        return {
            "compatible": True,
            "base_model_tag": tag,
            "adapter_base_model": adapter_base,
            "hidden_size": exp_hidden,
            "num_hidden_layers": exp_layers,
            "n_tensors": len(tensors),
            "gguf_sha256": gguf_info["sha256"],
        }


# =====================================================================
# 3. PEFT `save_pretrained` -> GGUF v3 CONVERTER (`llama.cpp` / Native)
# =====================================================================

class PeftToGGUFConverter:
    """Converts a HuggingFace PEFT `save_pretrained` directory (`adapter_config.json` + `adapter_model.safetensors`) to GGUF v3."""

    _HF_TO_GGUF_MODULE_MAP: Dict[str, str] = {
        "self_attn.q_proj": "attn_q",
        "self_attn.k_proj": "attn_k",
        "self_attn.v_proj": "attn_v",
        "self_attn.o_proj": "attn_output",
        "attn.c_attn": "attn_qkv",
        "attn.c_proj": "attn_output",
        "mlp.gate_proj": "ffn_gate",
        "mlp.up_proj": "ffn_up",
        "mlp.down_proj": "ffn_down",
    }

    @classmethod
    def map_peft_tensor_name_to_gguf(cls, hf_name: str) -> Optional[str]:
        """Maps a PEFT parameter name like `base_model.model.model.layers.0.self_attn.q_proj.lora_A.weight` to `blk.0.attn_q.weight.lora_a`."""
        m_ab = re.search(r"\.lora_([AB])(?:\.default)?\.weight$", hf_name)
        if not m_ab:
            return None
        ab_suffix = f"lora_{m_ab.group(1).lower()}"

        m_layer = re.search(r"(?:layers|h|blocks)\.(\d+)\.(.+?)\.lora_[AB]", hf_name)
        if m_layer:
            layer_idx = int(m_layer.group(1))
            mod_part = m_layer.group(2)
            gguf_mod = cls._HF_TO_GGUF_MODULE_MAP.get(mod_part)
            if gguf_mod is None:
                # Fallback: match last segment
                short = mod_part.split(".")[-1]
                fallback_map = {
                    "q_proj": "attn_q",
                    "k_proj": "attn_k",
                    "v_proj": "attn_v",
                    "o_proj": "attn_output",
                    "gate_proj": "ffn_gate",
                    "up_proj": "ffn_up",
                    "down_proj": "ffn_down",
                }
                gguf_mod = fallback_map.get(short, short)
            return f"blk.{layer_idx}.{gguf_mod}.weight.{ab_suffix}"

        if "lm_head" in hf_name or "embed_out" in hf_name:
            return f"output.weight.{ab_suffix}"
        return None

    @classmethod
    def convert_peft_to_gguf(
        cls,
        peft_dir: Path,
        gguf_out_path: Path,
        base_model_tag: str,
        base_model_config: Optional[Any] = None,
        base_model_path: Optional[Path] = None,
        hidden_size: Optional[int] = None,
        num_hidden_layers: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Converts a `save_pretrained` PEFT adapter folder into a base-model-matched GGUF v3 binary."""
        adapter_cfg_path = peft_dir / "adapter_config.json"
        safetensors_path = peft_dir / "adapter_model.safetensors"

        if not adapter_cfg_path.exists():
            raise FileNotFoundError(f"PEFT adapter_config.json not found in {peft_dir}")
        if not safetensors_path.exists():
            raise FileNotFoundError(f"PEFT adapter_model.safetensors not found in {peft_dir}")

        adapter_cfg = json.loads(adapter_cfg_path.read_text(encoding="utf-8"))
        rank = int(adapter_cfg.get("r", 8))
        alpha = float(adapter_cfg.get("lora_alpha", 16.0))
        base_name = str(adapter_cfg.get("base_model_name_or_path") or base_model_tag)

        # 1. Try external `llama.cpp` `convert_lora_to_gguf.py` if configured and base_model_path exists
        converter_script = os.environ.get("NEXUS_LLAMA_CPP_CONVERTER", "").strip() or shutil.which("convert_lora_to_gguf.py")
        if converter_script and base_model_path is not None and Path(base_model_path).exists():
            try:
                proc = subprocess.run(
                    [
                        sys.executable,
                        str(converter_script),
                        "--base",
                        str(base_model_path),
                        "--outfile",
                        str(gguf_out_path),
                        str(peft_dir),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60.0,
                    check=False,
                )
                if proc.returncode == 0 and gguf_out_path.exists():
                    info = GGUFLoRAExporter.verify_gguf_header(gguf_out_path)
                    return {
                        "ok": True,
                        "converter": "llama_cpp_convert_lora_to_gguf",
                        "gguf_path": str(gguf_out_path),
                        "sha256": info["sha256"],
                        "n_tensors": info["n_tensors"],
                        "rank": rank,
                        "alpha": alpha,
                    }
            except Exception:
                pass

        # 2. Native PEFT `.safetensors` -> GGUF v3 conversion
        loaded_st = SafeTensorsIO.load(safetensors_path)
        raw_tensors = loaded_st[0] if isinstance(loaded_st, tuple) else loaded_st
        gguf_tensors: Dict[str, Tuple[List[int], List[float]]] = {}
        layer_indices: Set[int] = set()
        inferred_hidden: Optional[int] = None

        for hf_key, (shape, flat_vals) in raw_tensors.items():
            gguf_name = cls.map_peft_tensor_name_to_gguf(hf_key)
            if gguf_name is None:
                continue
            gguf_tensors[gguf_name] = (list(shape), list(flat_vals))
            m = re.match(r"^blk\.(\d+)\.", gguf_name)
            if m:
                layer_indices.add(int(m.group(1)))
            if inferred_hidden is None and gguf_name.endswith(".lora_a") and len(shape) == 2:
                inferred_hidden = int(shape[1])

        if not gguf_tensors:
            raise ValueError(f"No valid LoRA A/B tensors found in {safetensors_path}")

        # Resolve architectural dimensions from explicit args, adapter_cfg, base_model_config, or config.json
        arch = "llama"
        eff_hidden_size = int(hidden_size or adapter_cfg.get("hidden_size") or inferred_hidden or 64)
        eff_num_layers = int(num_hidden_layers or adapter_cfg.get("num_hidden_layers") or len(layer_indices) or 1)

        if base_model_config is not None:
            if isinstance(base_model_config, dict):
                arch = str(base_model_config.get("model_type") or "llama")
                eff_hidden_size = int(base_model_config.get("hidden_size") or base_model_config.get("n_embd") or eff_hidden_size)
                eff_num_layers = int(base_model_config.get("num_hidden_layers") or base_model_config.get("n_layer") or eff_num_layers)
            else:
                arch = str(getattr(base_model_config, "model_type", "llama") or "llama")
                eff_hidden_size = int(getattr(base_model_config, "hidden_size", getattr(base_model_config, "n_embd", eff_hidden_size)) or eff_hidden_size)
                eff_num_layers = int(getattr(base_model_config, "num_hidden_layers", getattr(base_model_config, "n_layer", eff_num_layers)) or eff_num_layers)
        elif base_model_path is not None and (Path(base_model_path) / "config.json").exists():
            cfg_data = json.loads((Path(base_model_path) / "config.json").read_text(encoding="utf-8"))
            arch = str(cfg_data.get("model_type") or "llama")
            eff_hidden_size = int(cfg_data.get("hidden_size") or cfg_data.get("n_embd") or eff_hidden_size)
            eff_num_layers = int(cfg_data.get("num_hidden_layers") or cfg_data.get("n_layer") or eff_num_layers)

        save_meta = GGUFLoRAExporter.save(
            file_path=gguf_out_path,
            tensors=gguf_tensors,
            alpha=alpha,
            rank=rank,
            arch=arch,
            base_model=base_model_tag or base_name,
            hidden_size=eff_hidden_size,
            num_hidden_layers=eff_num_layers,
        )
        return {
            "ok": True,
            "converter": "native_peft_safetensors_to_gguf_v3",
            "peft_dir": str(peft_dir),
            "gguf_path": str(gguf_out_path),
            "sha256": save_meta["sha256"],
            "n_tensors": save_meta["tensor_count"],
            "hidden_size": eff_hidden_size,
            "num_hidden_layers": eff_num_layers,
            "base_model": base_model_tag or base_name,
            "rank": rank,
            "alpha": alpha,
        }


# =====================================================================
# 4. REAL HUGGINGFACE + PEFT + TRL + BITSANDBYTES QLORA ENGINE
# =====================================================================

class RealQLoRAEngine:
    """Production HuggingFace CausalLM QLoRA / LoRA Engine.

    Loads a real pretrained model (`AutoModelForCausalLM.from_pretrained`), applies
    4-bit NF4 quantization on GPU (`BitsAndBytesConfig`), wraps with `peft.LoraConfig`
    and `get_peft_model`, trains via `trl.SFTTrainer` or HF token-level CausalLM
    cross-entropy loss, saves via `peft_model.save_pretrained`, and converts to
    GGUF v3 via `PeftToGGUFConverter`.

    Note: Contains ZERO toy transformer fallbacks. If the HuggingFace + PEFT stack
    is unavailable, strictly raises `RuntimeError("TRAINING_UNAVAILABLE")`.
    """

    def __init__(
        self,
        adapter_dir: Optional[Path] = None,
        rank: int = 8,
        alpha: float = 16.0,
        lora_dropout: float = 0.05,
        target_modules: Optional[List[str]] = None,
        base_model_name_or_path: Optional[str] = None,
        base_model_tag: str = "nexus-proto:64d-1l",
        model_dir: Optional[Path] = None,
    ):
        eff_dir = adapter_dir or model_dir or Path("data/qlora_checkpoints")
        self.adapter_dir = Path(eff_dir)
        self.adapter_dir.mkdir(parents=True, exist_ok=True)
        self.rank = int(rank)
        self.alpha = float(alpha)
        self.lora_dropout = float(lora_dropout)
        self.target_modules = target_modules or ["q_proj", "k_proj", "v_proj", "o_proj"]
        self.base_model_name_or_path = base_model_name_or_path
        self.base_model_tag = base_model_tag

    def train_hf_qlora(
        self,
        dataset: List[Dict[str, Any]],
        hf_model_name_or_path: Optional[str] = None,
        base_model_name_or_path: Optional[str] = None,
        base_model_tag: Optional[str] = None,
        epochs: int = 3,
        learning_rate: float = 2e-4,
        lr: Optional[float] = None,
        max_seq_length: int = 256,
        max_seq_len: Optional[int] = None,
        use_4bit: Optional[bool] = None,
        use_trl_sft: bool = True,
        peft_out_dir: Optional[Path] = None,
        gguf_out_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Loads `hf_model_name_or_path` via `AutoModelForCausalLM.from_pretrained`, attaches `peft.LoraConfig`, trains, calls `save_pretrained`, and converts to GGUF v3."""
        if not is_hf_qlora_stack_ready():
            raise RuntimeError(
                "TRAINING_UNAVAILABLE: Real HuggingFace QLoRA training requires torch>=2.4, "
                "transformers>=4.44, and peft>=0.12 (see requirements-gpu.txt)."
            )
        if not dataset:
            raise ValueError("Dataset cannot be empty for HuggingFace QLoRA training.")

        eff_model_path = str(
            hf_model_name_or_path
            or base_model_name_or_path
            or self.base_model_name_or_path
            or ""
        ).strip()
        if not eff_model_path:
            raise ValueError("hf_model_name_or_path / base_model_name_or_path is required for train_hf_qlora.")

        eff_tag = str(base_model_tag or self.base_model_tag or "llama3.1:8b").strip()
        eff_lr = float(lr if lr is not None else learning_rate)
        eff_seq_len = int(max_seq_len if max_seq_len is not None else max_seq_length)

        t0 = time.monotonic()
        enable_4bit = (
            bool(use_4bit)
            if use_4bit is not None
            else bool(torch.cuda.is_available() and BITSANDBYTES_AVAILABLE)
        )

        bnb_config = None
        if enable_4bit and BitsAndBytesConfig is not None:
            compute_dtype = (
                torch.bfloat16
                if (torch.cuda.is_available() and hasattr(torch.cuda, "is_bf16_supported") and torch.cuda.is_bf16_supported())
                else torch.float16
            )
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=compute_dtype,
                bnb_4bit_use_double_quant=True,
            )

        # 1. Load Base CausalLM via `AutoModelForCausalLM.from_pretrained`
        model_kwargs: Dict[str, Any] = {}
        if bnb_config is not None:
            model_kwargs["quantization_config"] = bnb_config
            model_kwargs["device_map"] = "auto"

        base_model = AutoModelForCausalLM.from_pretrained(eff_model_path, **model_kwargs)
        base_config = base_model.config
        vocab_size = int(getattr(base_config, "vocab_size", 256))

        tokenizer = None
        try:
            tokenizer = AutoTokenizer.from_pretrained(eff_model_path)
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
        except Exception:
            tokenizer = None

        if bnb_config is not None and prepare_model_for_kbit_training is not None:
            base_model = prepare_model_for_kbit_training(base_model)

        # 2. Apply `peft.LoraConfig` via `get_peft_model`
        lora_cfg = LoraConfig(
            r=self.rank,
            lora_alpha=self.alpha,
            lora_dropout=self.lora_dropout,
            bias="none",
            task_type=TaskType.CAUSAL_LM,
            target_modules=list(self.target_modules),
        )
        peft_model = get_peft_model(base_model, lora_cfg)
        peft_model.train()

        trainable_params = sum(p.numel() for p in peft_model.parameters() if p.requires_grad)
        total_params = sum(p.numel() for p in peft_model.parameters())

        # 3. Tokenize verified `(prompt, response)` pairs with `-100` prompt masking
        encoded_batches: List[Dict[str, torch.Tensor]] = []
        sft_texts: List[Dict[str, str]] = []
        device = next(peft_model.parameters()).device

        for item in dataset:
            prompt_str = str(item.get("prompt", "")).strip()
            resp_str = str(item.get("response") or item.get("solution") or "").strip()
            full_text = f"### Instruction:\n{prompt_str}\n\n### Response:\n{resp_str}"
            prompt_prefix = f"### Instruction:\n{prompt_str}\n\n### Response:\n"
            sft_texts.append({"text": full_text})

            if tokenizer is not None:
                full_enc = tokenizer(
                    full_text,
                    truncation=True,
                    max_length=eff_seq_len,
                    return_tensors="pt",
                )
                prefix_enc = tokenizer(
                    prompt_prefix,
                    truncation=True,
                    max_length=eff_seq_len,
                    return_tensors="pt",
                )
                input_ids = full_enc["input_ids"].to(device)
                attention_mask = full_enc["attention_mask"].to(device)
                prefix_len = min(int(prefix_enc["input_ids"].shape[1]), int(input_ids.shape[1]) - 1)
            else:
                full_bytes = [1] + [max(3, b % vocab_size) for b in full_text.encode("utf-8")[: max(2, eff_seq_len - 2)]] + [2]
                prefix_bytes = [1] + [max(3, b % vocab_size) for b in prompt_prefix.encode("utf-8")[: max(1, eff_seq_len - 3)]]
                input_ids = torch.tensor([full_bytes], dtype=torch.long, device=device)
                attention_mask = torch.ones_like(input_ids)
                prefix_len = min(len(prefix_bytes), int(input_ids.shape[1]) - 1)

            labels = input_ids.clone()
            if prefix_len > 0:
                labels[:, :prefix_len] = -100
            encoded_batches.append({
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "labels": labels,
            })

        # Measure initial token-level cross-entropy loss on the PEFT model
        with torch.no_grad():
            init_losses = [
                float(peft_model(**batch).loss.item())
                for batch in encoded_batches
            ]
        initial_ce_loss = sum(init_losses) / max(1, len(init_losses))

        # 4. Train via `trl.SFTTrainer` (if enabled and tokenizer + datasets present) or direct HF PeftModel loop
        epoch_losses: List[float] = []
        used_trainer = "hf_peft_causal_lm_adamw"

        if use_trl_sft and tokenizer is not None and TRL_AVAILABLE and SFTTrainer is not None and SFTConfig is not None:
            try:
                from datasets import Dataset as HFDataset  # type: ignore[import-untyped]
                hf_ds = HFDataset.from_list(sft_texts)
                sft_out_dir = self.adapter_dir / "trl_sft_checkpoints"
                sft_args = SFTConfig(
                    output_dir=str(sft_out_dir),
                    num_train_epochs=float(max(1, epochs)),
                    per_device_train_batch_size=1,
                    learning_rate=eff_lr,
                    logging_steps=1,
                    save_strategy="no",
                    report_to="none",
                    use_cpu=not torch.cuda.is_available(),
                )
                trainer = SFTTrainer(
                    model=peft_model,
                    train_dataset=hf_ds,
                    args=sft_args,
                    processing_class=tokenizer,
                )
                train_out = trainer.train()
                epoch_losses.append(float(getattr(train_out, "training_loss", initial_ce_loss)))
                used_trainer = "trl_sft_trainer"
            except Exception:
                used_trainer = "hf_peft_causal_lm_adamw"

        if used_trainer == "hf_peft_causal_lm_adamw":
            optimizer = torch.optim.AdamW(
                [p for p in peft_model.parameters() if p.requires_grad],
                lr=eff_lr,
                weight_decay=1e-4,
            )
            for _ in range(max(1, epochs)):
                step_losses: List[float] = []
                for batch in encoded_batches:
                    optimizer.zero_grad()
                    outputs = peft_model(**batch)
                    loss = outputs.loss
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(
                        [p for p in peft_model.parameters() if p.requires_grad],
                        max_norm=1.0,
                    )
                    optimizer.step()
                    step_losses.append(float(loss.item()))
                epoch_losses.append(sum(step_losses) / max(1, len(step_losses)))

        with torch.no_grad():
            end_losses = [
                float(peft_model(**batch).loss.item())
                for batch in encoded_batches
            ]
        final_ce_loss = sum(end_losses) / max(1, len(end_losses))

        # 5. Save adapter via `peft_model.save_pretrained`
        peft_save_dir = Path(peft_out_dir) if peft_out_dir is not None else (self.adapter_dir / "peft_saved_adapter")
        peft_save_dir.mkdir(parents=True, exist_ok=True)
        peft_model.save_pretrained(str(peft_save_dir), safe_serialization=True)
        if tokenizer is not None:
            try:
                tokenizer.save_pretrained(str(peft_save_dir))
            except Exception:
                pass

        # 6. Convert `save_pretrained` PEFT adapter to GGUF v3 for `eff_tag`
        gguf_dest = gguf_out_path or (self.adapter_dir / "candidate_lora_adapter.gguf")
        base_path_obj = Path(eff_model_path) if Path(eff_model_path).exists() else None
        gguf_conv = PeftToGGUFConverter.convert_peft_to_gguf(
            peft_dir=peft_save_dir,
            gguf_out_path=gguf_dest,
            base_model_tag=eff_tag,
            base_model_config=base_config,
            base_model_path=base_path_obj,
        )

        # Register the base model spec if loaded from a local HF model path
        h_size = int(getattr(base_config, "hidden_size", getattr(base_config, "n_embd", 64)))
        n_layers = int(getattr(base_config, "num_hidden_layers", getattr(base_config, "n_layer", 1)))
        arch_type = str(getattr(base_config, "model_type", "llama"))
        if eff_tag not in KNOWN_BASE_MODEL_SPECS:
            AdapterModelCompatibilityValidator.register_base_model_spec(
                base_model_tag=eff_tag,
                hidden_size=h_size,
                num_hidden_layers=n_layers,
                arch=arch_type,
                hf_base_models=[eff_tag, str(eff_model_path)],
            )

        compat = AdapterModelCompatibilityValidator.validate(
            gguf_path=gguf_dest,
            base_model_tag=eff_tag,
        )
        loaded_saved = SafeTensorsIO.load(peft_save_dir / "adapter_model.safetensors")
        saved_tensors = loaded_saved[0] if isinstance(loaded_saved, tuple) else loaded_saved

        elapsed_s = round(time.monotonic() - t0, 4)
        return {
            "ok": True,
            "engine": used_trainer,
            "hf_model_name_or_path": str(eff_model_path),
            "base_model_tag": eff_tag,
            "quantized_4bit_nf4": enable_4bit,
            "trainable_lora_params": trainable_params,
            "total_params": total_params,
            "initial_ce_loss": round(initial_ce_loss, 6),
            "final_ce_loss": round(final_ce_loss, 6),
            "initial_perplexity": round(math.exp(min(15.0, initial_ce_loss)), 4),
            "final_perplexity": round(math.exp(min(15.0, final_ce_loss)), 4),
            "epoch_losses": [round(x, 6) for x in epoch_losses],
            "peft_save_pretrained_dir": str(peft_save_dir),
            "gguf_conversion": gguf_conv,
            "gguf_adapter": gguf_conv,
            "compatibility_check": compat,
            "compatibility_verification": compat,
            "tensors": saved_tensors,
            "elapsed_s": elapsed_s,
        }
