"""Block 3 — Coding & Compilation JIT (10 features)."""
from __future__ import annotations

import re
from collections import Counter

from ..sandbox import compile_check, run_python
from .registry import Block, clamp, core, extract_code, integration, llm, require_text

B = Block.CODING
CODER_ROLE = "JIT Compiler"


def _debug_fix(grid, p):
    task = p.get("text", "")
    code = p.get("code") or extract_code(grid.router.ask(
        f"Write a complete Python script for: {require_text(p)}", system="Return only one python code block.",
        role=CODER_ROLE)["text"])
    history = []
    for attempt in range(1, clamp(p.get("max_iterations"), 1, 5, 3) + 1):
        check = compile_check(code)
        res = check if not check["ok"] else run_python(code, enabled=grid.config.enable_code_execution)
        history.append({"attempt": attempt, "ok": res["ok"], "error": res.get("error") or res.get("stderr", "")[-500:]})
        if res["ok"] or res.get("disabled"):
            return {"status": "FIXED" if res["ok"] else "COMPILED_ONLY", "code": code, "history": history}
        code = extract_code(grid.router.ask(
            f"Task: {task}\n\nCode:\n```python\n{code}\n```\n\nError:\n{history[-1]['error']}\n\nFix the code.",
            system="Return only the corrected python code block.", role=CODER_ROLE)["text"])
    return {"status": "UNRESOLVED", "code": code, "history": history}


def _code_voting(grid, p):
    spec = require_text(p)
    test_assertions = str(p.get("test_assertions") or "").strip()
    candidates = [c for c in grid.router.fan_out(f"Implement in Python: {spec}",
                                                 system="Return only one python code block.") if "text" in c]
    if not candidates:
        if p.get("candidates") and isinstance(p["candidates"], list):
            candidates = [
                {"node": f"candidate-{i+1}", "text": str(c)}
                for i, c in enumerate(p["candidates"])
            ]
        elif getattr(getattr(grid, "config", None), "simulate_offline_consensus", False):
            candidates = [
                {"node": "node-coder-1", "text": "```python\ndef square(x):\n    return x * x\n```"},
                {"node": "node-coder-2", "text": "```python\ndef square(x):\n    return x ** 2\n```"},
            ]
        else:
            return {"status": "NO_CANDIDATES"}

    from ..continuous_learning import ObjectiveGroundTruthVerifier

    # 1. Objective execution verification on every candidate (Sach Ki Jaanch)
    verified_candidates = []
    for idx, c in enumerate(candidates):
        raw_c = extract_code(c.get("text", ""))
        vr = ObjectiveGroundTruthVerifier.verify_code(raw_c, test_assertions=test_assertions)
        verified_candidates.append({
            "candidate_idx": idx + 1,
            "node": c.get("node", "unknown"),
            "code": raw_c,
            "verification": vr,
            "is_verified": bool(vr.get("verified")),
        })

    # Only include candidates that compile and execute cleanly if any exist
    clean_pool = [c for c in verified_candidates if c["is_verified"]]
    target_pool = clean_pool if clean_pool else verified_candidates

    listing = "\n\n".join(f"Candidate {c['candidate_idx']}:\n```python\n{c['code']}\n```"
                          for c in target_pool)
    ballots = grid.router.fan_out(f"Spec: {spec}\n\n{listing}",
                                  system="Reply with ONLY the number of the best candidate, then one reason.")
    tally: Counter = Counter()
    for b in ballots:
        m = re.search(r"\d+", b.get("text", ""))
        if m:
            val = int(m.group())
            if any(c["candidate_idx"] == val for c in target_pool):
                tally[val] += 1

    winner_idx = tally.most_common(1)[0][0] if tally else target_pool[0]["candidate_idx"]
    winner_obj = next(c for c in target_pool if c["candidate_idx"] == winner_idx)

    # 2. Feed verified winner into the continuous learning verified training dataset!
    saved_sample = None
    if winner_obj["is_verified"] and getattr(grid, "continuous_learning", None):
        saved_sample = grid.continuous_learning.dataset_store.record_verified(
            prompt=spec,
            solution=winner_obj["code"],
            domain="CODE_DEBUG_EXEC",
            proof=winner_obj["verification"],
        )

    return {
        "status": "OK",
        "winner_node": winner_obj["node"],
        "tally": dict(tally),
        "code": winner_obj["code"],
        "verified": winner_obj["is_verified"],
        "verification_proof": winner_obj["verification"],
        "saved_to_continuous_training_dataset": bool(saved_sample),
    }


def _jit(grid, p):
    code = require_text(p, "code")
    out = {"compile": compile_check(code)}
    if out["compile"]["ok"] and p.get("execute"):
        out["run"] = run_python(code, enabled=grid.config.enable_code_execution)
    return {"status": "OK" if out["compile"]["ok"] else "SYNTAX_ERROR", **out}


FEATURES = [
    llm("code_generation_core", "Code Generation Core", B,
        "Write clean, production-quality code for the request. Include brief usage notes.", role=CODER_ROLE),
    llm("automated_code_review", "Automated Code Review", B,
        "Review the code: bugs, security issues, performance, readability. Give severity-ranked findings."),
    llm("documentation_writer", "Documentation Writer", B,
        "Write clear developer documentation (overview, API reference, examples) for the given code."),
    llm("test_generation_sandbox", "Test Generation Sandbox", B,
        "Write a thorough unittest test module for the given code, covering edge cases.", role=CODER_ROLE),
    integration("api_integration_layer", "API Integration Layer", B, "per-API client adapters with credentials"),
    llm("competitive_programming_trainer", "Competitive Programming Trainer", B,
        "Act as a competitive programming coach: explain the optimal approach, complexity, and a reference solution."),
    core("code_debug_fix_loop", "Code Debug & Fix Loop", B, _debug_fix,
         "Compile/run -> feed errors to the model -> retry.", depends_on=("execution_jit_compilation",)),
    core("multi_ai_code_voting", "Multi-AI Code Voting", B, _code_voting, "Every node implements; nodes vote.",
         depends_on=("multi_ai_orchestration",)),
    llm("performance_optimization_engine", "Performance Optimization Engine", B,
        "Profile-by-reasoning: identify hot spots in the code and propose optimized versions with complexity notes."),
    core("execution_jit_compilation", "Execution JIT Compilation", B, _jit,
         "Bytecode compile + syntax validation; optional sandboxed run."),
]
