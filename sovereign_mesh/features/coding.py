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
    candidates = [c for c in grid.router.fan_out(f"Implement in Python: {spec}",
                                                 system="Return only one python code block.") if "text" in c]
    if not candidates:
        return {"status": "NO_CANDIDATES"}
    listing = "\n\n".join(f"Candidate {i + 1}:\n```python\n{extract_code(c['text'])}\n```"
                          for i, c in enumerate(candidates))
    ballots = grid.router.fan_out(f"Spec: {spec}\n\n{listing}",
                                  system="Reply with ONLY the number of the best candidate, then one reason.")
    tally: Counter = Counter()
    for b in ballots:
        m = re.search(r"\d+", b.get("text", ""))
        if m and 1 <= int(m.group()) <= len(candidates):
            tally[int(m.group())] += 1
    winner = tally.most_common(1)[0][0] if tally else 1
    return {"status": "OK", "winner_node": candidates[winner - 1]["node"], "tally": dict(tally),
            "code": extract_code(candidates[winner - 1]["text"])}


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
