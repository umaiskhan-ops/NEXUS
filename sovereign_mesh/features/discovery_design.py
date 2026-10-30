"""Block 2 — Discovery & Design (21 features)."""
from __future__ import annotations

import re

from ..sandbox import run_python
from ..state import cosine, tokenize
from .registry import Block, FeatureInputError, core, hardware, integration, llm, require_text

B = Block.DISCOVERY


def _novelty(grid, p):
    q = tokenize(require_text(p))
    corpus = [f"{k} {grid.memory.get(k)}" for k in grid.memory.keys()]
    corpus += [str(b["data"]["payload"]) for b in grid.ledger.tail(500)]
    best = max((cosine(q, tokenize(c)) for c in corpus), default=0.0)
    return {"status": "OK", "novelty_score": round(1.0 - best, 4), "max_similarity": round(best, 4),
            "compared_against": len(corpus)}


def _simulation(grid, p):
    res = run_python(require_text(p, "code"), enabled=grid.config.enable_code_execution,
                     timeout=float(p.get("timeout", 10)))
    return {"status": "OK" if res["ok"] else "FAILED", **res}


def _box_stl(name: str, w: float, d: float, h: float) -> str:
    v = [(0, 0, 0), (w, 0, 0), (w, d, 0), (0, d, 0), (0, 0, h), (w, 0, h), (w, d, h), (0, d, h)]
    faces = [((0, 0, -1), [(0, 2, 1), (0, 3, 2)]), ((0, 0, 1), [(4, 5, 6), (4, 6, 7)]),
             ((0, -1, 0), [(0, 1, 5), (0, 5, 4)]), ((0, 1, 0), [(3, 7, 6), (3, 6, 2)]),
             ((-1, 0, 0), [(0, 4, 7), (0, 7, 3)]), ((1, 0, 0), [(1, 2, 6), (1, 6, 5)])]
    out = [f"solid {name}"]
    for n, tris in faces:
        for tri in tris:
            out.append(f"  facet normal {n[0]} {n[1]} {n[2]}\n    outer loop")
            out.extend(f"      vertex {v[i][0]:.4f} {v[i][1]:.4f} {v[i][2]:.4f}" for i in tri)
            out.append("    endloop\n  endfacet")
    out.append(f"endsolid {name}")
    return "\n".join(out) + "\n"


def _cad(grid, p):
    try:
        w, d, h = (float(p.get(k, 10)) for k in ("width", "depth", "height"))
    except (TypeError, ValueError) as exc:
        raise FeatureInputError("width/depth/height must be numbers (mm)") from exc
    if not all(0 < x <= 10_000 for x in (w, d, h)):
        raise FeatureInputError("dimensions must be in (0, 10000] mm")
    name = re.sub(r"[^A-Za-z0-9_-]", "_", str(p.get("name", "part")))[:64] or "part"
    path = grid.data_dir / "cad" / f"{name}.stl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_box_stl(name, w, d, h), encoding="ascii")
    return {"status": "OK", "format": "ASCII STL", "path": str(path), "triangles": 12,
            "note": "Parametric box primitive. Complex geometry needs a CAD adapter (e.g. CadQuery)."}


def _feedback_guard(grid, p):
    series = p.get("series")
    if not isinstance(series, list) or len(series) < 3:
        raise FeatureInputError("payload 'series' must be a list of >= 3 numbers")
    try:
        xs = [float(x) for x in series]
        lo, hi = float(p.get("min", float("-inf"))), float(p.get("max", float("inf")))
    except (TypeError, ValueError) as exc:
        raise FeatureInputError("series and min/max bounds must be numeric") from exc
    if any(x < lo or x > hi for x in xs):
        return {"status": "TRIP", "action": "HALT_ACTUATION", "reason": "value out of safe bounds"}
    diffs = [b - a for a, b in zip(xs, xs[1:])]
    flips = sum(1 for a, b in zip(diffs, diffs[1:]) if a * b < 0)
    amplitudes = [abs(x) for x in diffs]
    growing = len(amplitudes) >= 4 and amplitudes[-1] > 1.5 * amplitudes[0]
    if len(diffs) > 2 and flips / (len(diffs) - 1) > 0.6 and growing:
        return {"status": "UNSTABLE", "action": "REDUCE_GAIN", "reason": "growing oscillation detected"}
    return {"status": "STABLE", "action": "CONTINUE"}


FEATURES = [
    llm("hypothesis_generation", "Hypothesis Generation", B,
        "Generate 3-5 falsifiable hypotheses for the problem. For each: statement, rationale, test to falsify it."),
    core("virtual_simulation_sandbox", "Virtual Simulation Sandbox", B, _simulation,
         "Runs a Python simulation script (requires ENABLE_CODE_EXECUTION)."),
    llm("probability_scoring", "Probability Scoring", B,
        "Estimate the probability of each listed outcome. Give a calibrated percentage, key drivers and uncertainty."),
    core("novelty_detection", "Novelty Detection", B, _novelty, "Lexical novelty vs. memory + ledger."),
    llm("cross_domain_transfer", "Cross-Domain Transfer Gateway", B,
        "Identify analogous solutions from other scientific/engineering domains and explain how to transfer them."),
    llm("research_paper_analyzer", "Research Paper Analyzer", B,
        "Analyze the paper text: contribution, method, evidence quality, limitations, reproducibility concerns."),
    integration("theorem_proving_engine", "Theorem Proving Engine", B, "a Lean 4 / Coq toolchain adapter"),
    integration("self_play_math_training", "Self-Play Math Training", B,
                "a training pipeline (GPU + fine-tuning stack); not feasible inside the request loop"),
    llm("olympiad_problem_solver", "Olympiad Problem Solver", B,
        "Solve the competition math problem step by step. State the final answer clearly and verify it."),
    llm("academic_paper_writer", "Academic Paper Writer", B,
        "Draft an academic paper section in a formal style. Mark every factual claim needing a citation as [CITE]."),
    llm("real_experiment_designer", "Real Experiment Designer", B,
        "Design a controlled experiment: variables, controls, sample size reasoning, protocol, safety considerations."),
    llm("blueprint_generation_core", "Blueprint Generation Core", B,
        "Produce a structured engineering blueprint: requirements, subsystems, interfaces, bill of materials."),
    llm("material_selection", "Material Selection", B,
        "Recommend materials for the application with trade-offs (strength, cost, weight, availability)."),
    llm("cost_optimization_engine", "Cost Optimization Engine", B,
        "Analyze the cost breakdown and propose prioritized optimizations with estimated savings."),
    core("cad_stl_output", "3D Model Output (CAD/STL)", B, _cad, "Writes parametric STL files."),
    llm("circuit_design_framework", "Circuit Design Framework", B,
        "Design the circuit: block diagram, component list with values, and a SPICE-style netlist."),
    hardware("printer_3d_control", "3D Printer Control", B, "an OctoPrint/Moonraker API adapter"),
    hardware("robotic_arm_ros2", "Robotic Arm Control (ROS 2 Bridge)", B, "a rclpy/ROS 2 bridge adapter"),
    hardware("cnc_machine_control", "CNC Machine Control", B, "a GRBL/LinuxCNC adapter"),
    integration("sensor_integration", "Sensor Integration", B, "an MQTT/serial sensor adapter"),
    core("feedback_loop_guard", "Feedback Loop Guard", B, _feedback_guard, "Bounds + oscillation trip detector."),
]
