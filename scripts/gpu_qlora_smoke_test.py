"""End-to-End 24GB GPU Smoke Test for NEXUS Marhala 2 Real QLoRA & Paired Pass@1 Gate.

Executes the complete real-world verification requested by the Auditor on a GPU node:
1. Verifies CUDA GPU availability and `requirements-gpu.txt` stack (`torch>=2.4`, `transformers`, `peft`, `trl`, `bitsandbytes`).
2. Loads the 140 held-out NEXUS code benchmark tasks and runs `DataContaminationChecker` against the verified training dataset.
3. Runs real 4-bit NF4 QLoRA training (`RealQLoRAEngine.train_hf_qlora`) on a Llama/Mistral-family base model, saves via `peft_model.save_pretrained`, and converts to GGUF v3 (`PeftToGGUFConverter.convert_peft_to_gguf`).
4. Runs `AdapterModelCompatibilityValidator.validate` and registers the candidate tag in Ollama (`OllamaBackend.create_model` / `ollama create`).
5. Evaluates baseline vs. candidate on all 140 held-out code tasks (`K=5` samples/task, 1,000 paired bootstrap resamples) via `AdapterBenchmarkSuite.evaluate_paired_pass_at_1` and writes `data/gpu_smoke_test_report.json`.

Usage on a 24GB GPU machine:
    pip install -r requirements-gpu.txt
    python scripts/gpu_qlora_smoke_test.py \\
        --hf-model meta-llama/Llama-3.1-8B-Instruct \\
        --ollama-base-tag llama3.1:8b \\
        --tasks 140 \\
        --samples-per-task 5 \\
        --epochs 3
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sovereign_mesh.continuous_learning import (
    AdapterBenchmarkSuite,
    ContinuousSelfImprovementManager,
    DataContaminationChecker,
)
from sovereign_mesh.models import OllamaBackend
from sovereign_mesh.qlora_engine import (
    AdapterModelCompatibilityValidator,
    RealQLoRAEngine,
    is_hf_qlora_stack_ready,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="NEXUS 24GB GPU QLoRA + Ollama + 140-Task Paired Pass@1 Smoke Test")
    parser.add_argument(
        "--hf-model",
        default="meta-llama/Llama-3.1-8B-Instruct",
        help="HuggingFace model ID or local path for QLoRA fine-tuning (default: meta-llama/Llama-3.1-8B-Instruct)",
    )
    parser.add_argument(
        "--ollama-base-tag",
        default="llama3.1:8b",
        help="Ollama base model tag matching --hf-model (default: llama3.1:8b)",
    )
    parser.add_argument(
        "--ollama-url",
        default="http://127.0.0.1:11434",
        help="Ollama HTTP API base URL (default: http://127.0.0.1:11434)",
    )
    parser.add_argument(
        "--data-dir",
        default=str(ROOT_DIR / "data"),
        help="Data directory for verified dataset, checkpoints, and smoke test report",
    )
    parser.add_argument("--tasks", type=int, default=140, help="Number of held-out code tasks to evaluate (default: 140)")
    parser.add_argument("--samples-per-task", type=int, default=5, help="Samples per task K for paired pass@1 (default: 5)")
    parser.add_argument("--epochs", type=int, default=3, help="QLoRA training epochs (default: 3)")
    parser.add_argument("--lr", type=float, default=2e-4, help="Learning rate (default: 2e-4)")
    parser.add_argument("--rank", type=int, default=16, help="LoRA rank r (default: 16)")
    parser.add_argument("--alpha", type=float, default=32.0, help="LoRA alpha (default: 32.0)")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print(" NEXUS MARHALA 2 - REAL GPU QLORA & 140-TASK PAIRED PASS@1 SMOKE TEST")
    print("=" * 72)

    if not is_hf_qlora_stack_ready():
        print("[ERROR] HuggingFace + PEFT QLoRA stack is not installed.")
        print("        Run: pip install -r requirements-gpu.txt")
        return 1

    import torch
    cuda_ok = torch.cuda.is_available()
    gpu_name = torch.cuda.get_device_name(0) if cuda_ok else "CPU (No CUDA GPU detected)"
    vram_gb = (torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)) if cuda_ok else 0.0
    print(f"[1/5] Hardware & Stack Check: device={gpu_name} | VRAM={vram_gb:.1f} GB")

    mgr = ContinuousSelfImprovementManager(
        data_dir=data_dir,
        base_model_tag=args.ollama_base_tag,
        hf_model_name_or_path=args.hf_model,
    )
    if mgr.dataset_store.count() < 4:
        mgr.populate_seed_verified_dataset()
    verified_samples = mgr.dataset_store.list_verified(limit=500)

    all_tasks = mgr.benchmark_suite.get_benchmark_tasks(limit=160)
    code_tasks = [t for t in all_tasks if t.get("type") == "code"][: args.tasks]
    if not code_tasks:
        code_tasks = all_tasks[: args.tasks]

    contamination = DataContaminationChecker.detect_contamination(verified_samples, code_tasks)
    print(
        f"[2/5] Dataset & Contamination Check: verified_samples={len(verified_samples)} | "
        f"eval_code_tasks={len(code_tasks)} | contaminated={contamination['contaminated']}"
    )
    if contamination["contaminated"]:
        print(f"[ERROR] Data contamination detected: {contamination['violations_count']} overlap(s)!")
        return 1

    print(f"[3/5] Running Real QLoRA Training on '{args.hf_model}' (epochs={args.epochs}, r={args.rank}, alpha={args.alpha})...")
    engine = RealQLoRAEngine(
        adapter_dir=data_dir / "gpu_smoke_qlora",
        rank=args.rank,
        alpha=args.alpha,
        base_model_name_or_path=args.hf_model,
        base_model_tag=args.ollama_base_tag,
    )
    gguf_path = data_dir / "gpu_smoke_candidate.gguf"
    qlora_res = engine.train_hf_qlora(
        dataset=[{"prompt": s["prompt"], "response": s["solution"]} for s in verified_samples],
        hf_model_name_or_path=args.hf_model,
        base_model_tag=args.ollama_base_tag,
        epochs=args.epochs,
        learning_rate=args.lr,
        gguf_out_path=gguf_path,
    )
    print(
        f"      Training complete: initial_ce_loss={qlora_res['initial_ce_loss']:.4f} -> "
        f"final_ce_loss={qlora_res['final_ce_loss']:.4f} | GGUF={gguf_path.name}"
    )

    compat = AdapterModelCompatibilityValidator.validate(gguf_path, args.ollama_base_tag)
    print(f"[4/5] Pre-`ollama create` Compatibility Check: compatible={compat['compatible']}")
    if not compat["compatible"]:
        print(f"[ERROR] {compat['reason']}")
        return 1

    cand_tag = f"{args.ollama_base_tag}-cand-{qlora_res['gguf_conversion']['sha256'][:10]}"
    modelfile_path = data_dir / "Modelfile.gpu_smoke_candidate"
    modelfile_content = (
        f"FROM {args.ollama_base_tag}\n"
        f"ADAPTER {gguf_path.resolve().as_posix()}\n"
        f"PARAMETER temperature 0.2\n"
    )
    modelfile_path.write_text(modelfile_content, encoding="utf-8")

    ollama = OllamaBackend(args.ollama_url)
    create_res = ollama.create_model(
        model_tag=cand_tag,
        modelfile_content=modelfile_content,
        modelfile_path=modelfile_path,
        timeout=60.0,
    )
    print(f"      Ollama candidate registration ({cand_tag}): ok={create_res.get('ok')} | method={create_res.get('method')}")
    if not create_res.get("ok"):
        print(f"[ERROR] Failed to register candidate model tag in Ollama: {create_res}")
        return 1

    print(
        f"[5/5] Running Paired Pass@1 Evaluation ({len(code_tasks)} code tasks, "
        f"K={args.samples_per_task} samples/task, 1,000 bootstrap resamples)..."
    )
    sys_prompt = (
        "You are an expert software engineer in the NEXUS mesh. "
        "Write only valid, robust, executable Python code with no conversational commentary."
    )

    def base_gen(prompt: str, sample_idx: int = 0, **kwargs: object) -> str:
        return ollama.chat(args.ollama_base_tag, sys_prompt, prompt, temperature=0.2, timeout=45.0)

    def cand_gen(prompt: str, sample_idx: int = 0, **kwargs: object) -> str:
        return ollama.chat(cand_tag, sys_prompt, prompt, temperature=0.2, timeout=45.0)

    base_gen.model_tag = args.ollama_base_tag  # type: ignore[attr-defined]
    cand_gen.model_tag = cand_tag  # type: ignore[attr-defined]

    suite = AdapterBenchmarkSuite(held_out_tasks=code_tasks)
    paired_report = suite.evaluate_paired_pass_at_1(
        base_generator_fn=base_gen,
        cand_generator_fn=cand_gen,
        tasks=code_tasks,
        base_model_tag=args.ollama_base_tag,
        cand_model_tag=cand_tag,
        samples_per_task=max(5, args.samples_per_task),
        bootstrap_resamples=1000,
    )

    report_path = data_dir / "gpu_smoke_test_report.json"
    full_report = {
        "timestamp": time.time(),
        "gpu_name": gpu_name,
        "vram_gb": round(vram_gb, 2),
        "hf_model": args.hf_model,
        "base_model_tag": args.ollama_base_tag,
        "candidate_model_tag": cand_tag,
        "qlora_training": {
            "initial_ce_loss": qlora_res["initial_ce_loss"],
            "final_ce_loss": qlora_res["final_ce_loss"],
            "epoch_losses": qlora_res["epoch_losses"],
            "trainable_lora_params": qlora_res["trainable_lora_params"],
            "gguf_conversion": qlora_res["gguf_conversion"],
        },
        "compatibility_check": compat,
        "ollama_create": create_res,
        "paired_pass_at_1_gate": {
            "gate_passed": paired_report["gate_passed"],
            "tasks_evaluated": len(code_tasks),
            "samples_per_task": paired_report["samples_per_task"],
            "baseline_pass_at_1": paired_report["baseline_pass_at_1"],
            "candidate_pass_at_1": paired_report["candidate_pass_at_1"],
            "mean_delta": paired_report["mean_delta"],
            "ci_lower_95": paired_report["ci_lower_95"],
            "ci_upper_95": paired_report["ci_upper_95"],
            "prob_improvement": paired_report["prob_improvement"],
        },
    }
    report_path.write_text(json.dumps(full_report, indent=2), encoding="utf-8")

    print("-" * 72)
    print(f" Baseline pass@1  ({args.ollama_base_tag}): {paired_report['baseline_pass_at_1']:.4f}")
    print(f" Candidate pass@1 ({cand_tag}): {paired_report['candidate_pass_at_1']:.4f}")
    print(f" Mean Delta       : {paired_report['mean_delta']:+.4f}")
    print(f" 95% Bootstrap CI : [{paired_report['ci_lower_95']:+.4f}, {paired_report['ci_upper_95']:+.4f}]")
    print(f" Gate Passed      : {paired_report['gate_passed']}")
    print(f" Report Saved     : {report_path}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
