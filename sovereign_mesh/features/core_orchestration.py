"""Block 1 — Core Orchestration (10 features)."""
from __future__ import annotations

import re
from collections import Counter

from .registry import Block, FeatureInputError, clamp, core, integration, llm, require_text

B = Block.CORE


def _orchestrate(grid, p):
    return {"status": "OK", "responses": grid.router.fan_out(require_text(p), system=p.get("system", ""))}


def _debate(grid, p):
    return {"status": "OK", **grid.router.debate(require_text(p), clamp(p.get("rounds"), 1, 4, 2))}


def _consensus(grid, p):
    res = grid.router.vote(require_text(p), partial_failure_tolerant=grid.partial_failure_tolerant,
                           simulate_offline=grid.config.simulate_offline_consensus)
    return {"status": "CONSENSUS" if res["passed"] else "NO_CONSENSUS", **res}


def _memory(grid, p):
    op = p.get("op", "list")
    if op == "set":
        grid.memory.set(require_text(p, "key"), p.get("value", p.get("text", "")), p.get("session", "default"))
        return {"status": "OK", "stored": p["key"]}
    if op == "get":
        return {"status": "OK", "value": grid.memory.get(require_text(p, "key"))}
    if op == "delete":
        return {"status": "OK", "deleted": grid.memory.delete(require_text(p, "key"))}
    if op == "search":
        return {"status": "OK", "results": grid.memory.search(require_text(p), clamp(p.get("k"), 1, 50, 5))}
    return {"status": "OK", "keys": grid.memory.keys(), "sessions": grid.memory.sessions()}


def _explain(grid, p):
    if p.get("text"):
        block = grid.ledger.append("reasoning", {"rationale": p["text"], "decision": p.get("decision")})
        return {"status": "RECORDED", "block": block["hash"][:16]}
    entries = [b for b in grid.ledger.tail(500) if b["data"]["task"] == "reasoning"][-10:]
    return {"status": "OK", "entries": [{"hash": b["hash"][:16], **b["data"]["payload"]} for b in entries]}


def _conflict(grid, p):
    options = p.get("options")
    if not isinstance(options, list) or len(options) < 2:
        raise FeatureInputError("payload 'options' must be a list with >= 2 entries")
    listing = "\n".join(f"{i + 1}. {o}" for i, o in enumerate(options))
    results = grid.router.fan_out(f"{p.get('text', 'Choose the best option.')}\n\nOptions:\n{listing}",
                                  system="Reply with ONLY the number of the best option, then a short reason.")
    tally: Counter = Counter()
    for r in results:
        m = re.search(r"\d+", r.get("text", ""))
        if m and 1 <= int(m.group()) <= len(options):
            tally[int(m.group())] += 1
    ranked = tally.most_common()
    if ranked and (len(ranked) == 1 or ranked[0][1] > ranked[1][1]):
        return {"status": "RESOLVED", "winner": options[ranked[0][0] - 1], "tally": dict(tally)}
    return {"status": "ESCALATE_TO_HUMAN", "tally": dict(tally),
            "message": "No majority; owner decision required (human review gate)."}


def _energy(grid, p):
    if "eco_mode" in p:
        grid.router.eco_mode = bool(p["eco_mode"])
    nodes = sorted((n.to_dict() for n in grid.router.nodes), key=lambda d: d["avg_latency_s"] or 1e9)
    return {"status": "OK", "eco_mode": grid.router.eco_mode, "nodes_by_latency": nodes,
            "note": "eco_mode limits fan-out to the 2 fastest nodes"}


FEATURES = [
    core("multi_ai_orchestration", "Multi-AI Orchestration", B, _orchestrate, "Fan a prompt out to all mesh nodes."),
    core("roundtable_debate", "Roundtable Debate", B, _debate, "Multi-round critique + moderator synthesis.",
         depends_on=("multi_ai_orchestration",)),
    core("consensus_engine", "Consensus Engine", B, _consensus, ">= 2/3 supermajority vote across nodes.",
         depends_on=("multi_ai_orchestration",)),
    llm("knowledge_synthesis", "Knowledge Synthesis", B,
        "Synthesize the provided material into a structured summary: key facts, relationships, open questions."),
    llm("gap_analysis", "Gap Analysis", B,
        "Perform a gap analysis: compare current state vs. desired state, list gaps, impact and remediation steps."),
    integration("realtime_learning_streams", "Real-time Learning Web Streams", B,
                "a web/RSS ingestion adapter that writes into grid.memory"),
    core("local_memory_management", "Local Memory Management", B, _memory, "ops: set/get/delete/search/list"),
    core("explainable_reasoning_ledger", "Explainable Reasoning Ledger", B, _explain,
         "Record or list rationale entries on the hash-chained ledger.", depends_on=("full_transparency_ledger",)),
    core("conflict_resolution_protocol", "Conflict Resolution Protocol", B, _conflict,
         "Majority pick between options; ties escalate to the owner.", depends_on=("human_review_gate",)),
    core("energy_efficiency_optimization", "Energy Efficiency Optimization", B, _energy, "Latency/eco-mode control."),
]
