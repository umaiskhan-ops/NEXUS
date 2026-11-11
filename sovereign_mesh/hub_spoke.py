"""Hybrid Hub-and-Spoke: the Master Hub keeps all governance; edge Workers only execute signed tasks.

Security model (read this before relying on slashing):
  * Every worker gets its OWN random key at registration (no shared secret). A valid proof is therefore
    attributable: only the Hub and that one worker know the key.
  * An INVALID proof is rejected but never slashed, because it cannot be attributed (anyone can send garbage
    in someone else's name; slashing on that would let attackers burn honest workers' credits).
  * Slashing happens only on PROVABLE misbehaviour: a correctly-signed result that disagrees with the Hub's own
    re-execution (spot-check) of a deterministic feature.
  * Non-deterministic (LLM) results are validated via schema, non-empty output commitment, and constitutional
    sanitization; any unverified or invalid result (`verified: false`) is rejected and never rewarded.
  * Credits are an internal accounting number, not money or a token.
"""
from __future__ import annotations

import dataclasses
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .features import FeatureRegistry, build_registry
from .ledger import HashChainLedger, interprocess_file_lock
from .security import sanitize_payload

# Governance, control, hardware and anything that can fan out into other features stays on the Hub.
HUB_ONLY_FEATURES: Set[str] = {
    "mission_control", "veto_power", "approval_gates", "full_transparency_ledger", "emergency_override",
    "shutdown_authority", "access_control", "mission_change_rollbacks", "simulation_rollback",
    "grid_state_rollback", "final_say_protocol", "kill_switch_protocol", "token_budget_controller",
    "autonomous_mode_toggle", "authorization_system", "encryption_layer", "disaster_recovery_manager",
    "redundant_backup_system", "recursive_self_improvement", "printer_3d_control", "robotic_arm_ros2",
    "cnc_machine_control", "workflow_automation", "task_scheduling", "trigger_based_actions",
    "load_testing_engine", "red_team_safety_tester", "automated_testing_sandbox", "version_control_integration",
    "quantized_model_hot_swap", "precision_scalability_switch", "gradual_scaling_controller",
    "human_review_gate", "multi_user_collaboration",
}

# Deterministic features the Hub can re-execute to verify a worker's answer.
SPOT_CHECKABLE: Set[str] = {
    "data_analysis", "feedback_loop_guard", "output_format_enforcer", "input_sanitization_layer",
    "emotional_tone_detection", "virtual_experiment_simulator", "trend_forecasting",
}
_VOLATILE_KEYS = {"input_flags"}
TASK_TTL_S = 3600.0


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def compute_hmac(key: str, payload: Any) -> str:
    return hmac.new(key.encode("utf-8"), _canonical(payload), hashlib.sha256).hexdigest()


def compute_cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Computes exact mathematical Cosine Similarity between two float32 vectors: (u · v) / (||u|| ||v||)."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = 0.0
    norm_a_sq = 0.0
    norm_b_sq = 0.0
    for a, b in zip(vec_a, vec_b):
        if math.isnan(a) or math.isnan(b) or math.isinf(a) or math.isinf(b):
            return 0.0
        dot += a * b
        norm_a_sq += a * a
        norm_b_sq += b * b
    if norm_a_sq <= 1e-12 or norm_b_sq <= 1e-12:
        return 0.0
    return max(-1.0, min(1.0, dot / (math.sqrt(norm_a_sq) * math.sqrt(norm_b_sq))))


_STOPWORDS: Set[str] = {
    # English common grammatical / function words
    "the", "a", "an", "is", "are", "was", "were", "and", "or", "but", "in", "on", "at",
    "to", "for", "of", "with", "by", "as", "from", "that", "this", "it", "its", "be",
    "have", "has", "had", "do", "does", "did", "can", "could", "will", "would", "shall",
    "should", "may", "might", "must", "they", "them", "their", "we", "us", "our", "you",
    "your", "he", "him", "his", "she", "her", "i", "me", "my", "so", "than", "then",
    "there", "here", "when", "where", "why", "how", "all", "any", "both", "each", "few",
    "more", "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same",
    "too", "very", "about", "above", "after", "again", "against", "between", "into",
    "through", "during", "before", "under", "below", "up", "down", "over", "just",
    "what", "which", "who", "whom", "these", "those", "am", "been", "being",
    "because", "becaus",
    # Roman Urdu common function words
    "hai", "hain", "ke", "ki", "ko", "se", "par", "ka", "kya", "ye", "woh", "aur",
    "bhi", "tha", "thi", "the", "kar", "karna", "hoti", "hota", "hote", "mein", "main",
    "ab", "jab", "tab", "kuch", "apne", "apna", "apni", "humein", "unhein", "unka",
}
CONSENSUS_BUFFER_TTL = 300.0  # Seconds before unverified freeform candidate entries expire

_FUNCTION_WORDS: Set[str] = {
    "the", "a", "an", "is", "am", "are", "was", "were", "be", "been", "being",
    "in", "on", "at", "to", "for", "with", "by", "from", "of", "about",
    "into", "through", "during", "before", "after", "above", "below",
    "between", "under", "and", "but", "or", "so", "yet", "because", "as",
    "since", "while", "although", "though", "that", "which", "who", "whom",
    "this", "these", "those", "it", "its", "they", "them", "their", "theirs",
    "we", "us", "our", "ours", "you", "your", "yours", "he", "him", "his",
    "she", "her", "hers", "can", "could", "may", "might", "shall", "should",
    "will", "would", "must", "have", "has", "had", "do", "does", "did",
    "toward", "towards", "upon", "within", "without", "via", "onto", "than",
    "like", "such", "each", "every", "both", "all", "other", "another",
    "more", "most", "much", "less", "least", "too", "very", "also", "even",
    "only", "then", "now", "here", "there", "where", "when", "why", "how",
    "across", "causes", "describes", "remains", "determines", "occurs",
}

def compute_semantic_embedding(text: str, dim: int = 64) -> List[float]:
    """Deterministic continuous dense float embedding using token & character subwords."""
    raw_tokens = re.findall(r"\b[a-zA-Z0-9_-]+\b", (text or "").lower())
    tokens = [t for t in raw_tokens if t not in _STOPWORDS and not t.isdigit()] or raw_tokens or ["empty"]
    vec = [0.0] * dim
    for tok in tokens:
        subwords = [tok]
        for n in (3, 4):
            if len(tok) >= n:
                for i in range(len(tok) - n + 1):
                    subwords.append(tok[i:i+n])
        for sw in subwords:
            h = hashlib.sha256(sw.encode("utf-8")).digest()
            for d in range(dim):
                b = h[d % len(h)]
                vec[d] += ((b / 255.0) * 2.0 - 1.0)
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [round(v / norm, 6) for v in vec]


def check_prose_coherence(text: str) -> Tuple[bool, str]:
    """Ensures response is natural English prose rather than keyword salad, token vomit, or template loops."""
    tokens = re.findall(r"[a-zA-Z]+", (text or "").lower())
    if len(tokens) < 3:
        return False, "insufficient_word_count (less than 3 words)"
    func_tokens = [t for t in tokens if t in _FUNCTION_WORDS]
    func_ratio = len(func_tokens) / len(tokens)
    if func_ratio < 0.15:
        return False, f"keyword_salad_rejected (function word ratio {func_ratio:.2f} < 0.15 indicates ungrammatical word list)"
    if func_ratio > 0.85 and len(tokens) >= 5:
        return False, f"low_content_entropy_rejected (function word ratio {func_ratio:.2f} > 0.85 indicates stopword salad)"

    # Pseudo-grammatical keyword salad detection:
    # 1. Repetitive preposition-determiner chaining (e.g. "of the ... of the ... of the ...")
    prep_chains = re.findall(r"\b(of|in|at|by|from|with|to)\s+(the|a|an)\b", text.lower())
    if len(tokens) <= 25 and len(prep_chains) >= 3:
        return False, "keyword_salad_rejected (excessive preposition chain template)"

    # 2. Excessive determiner repetition in short sentence
    the_count = tokens.count("the")
    if len(tokens) <= 20 and the_count >= 4:
        return False, "keyword_salad_rejected (excessive determiner repetition)"

    # 3. Bigram repetition
    bigrams = [f"{tokens[i]} {tokens[i+1]}" for i in range(len(tokens) - 1)]
    from collections import Counter
    b_counts = Counter(bigrams)
    for bg, c in b_counts.items():
        if c >= 3 and len(tokens) <= 30:
            return False, f"keyword_salad_rejected (repetitive bigram template: '{bg}')"

    has_sent_structure = bool(re.search(r"[.!?]", text)) or len(tokens) >= 8
    if not has_sent_structure:
        return False, "lacks_sentence_structure"
    return True, "ok"


def extract_content_tokens(text: str) -> List[str]:
    """Extracts meaningful, non-stopword content tokens from response text."""
    raw = re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", (text or "").lower())
    return [t for t in raw if t not in _STOPWORDS and not t.isdigit()]


def stem_token(w: str) -> str:
    """Lightweight morphological stemmer for English content words."""
    w = (w or "").lower()
    for s in ("ation", "ment", "able", "ible", "ness", "ing", "ies", "ied", "ity", "ive", "ful", "est", "ed", "es", "ly", "al", "s", "e"):
        if w.endswith(s) and len(w) - len(s) >= 3:
            w = w[:-len(s)]
            break
    return w


def extract_prompt_stems(prompt_text: str) -> Set[str]:
    """Extracts stemmed content keywords from prompt to detect echo attacks."""
    tokens = re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", (prompt_text or "").lower())
    return {stem_token(t) for t in tokens if t not in _STOPWORDS and not t.isdigit()}


def extract_novel_stems(response_text: str, prompt_stems: Set[str]) -> List[str]:
    """Extracts stems that represent novel explanatory concepts not merely repeated from prompt."""
    tokens = re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", (response_text or "").lower())
    stems = []
    for raw_t in tokens:
        if raw_t in _STOPWORDS or raw_t.isdigit():
            continue
        st = stem_token(raw_t)
        if st in prompt_stems:
            continue
        stems.append(st)
    return stems


ANTONYM_MODIFIERS: List[Tuple[Set[str], Set[str]]] = [
    ({"less", "lower", "decrease", "decreasing", "drop", "fall", "erode", "eroding", "decay", "loss", "reduc", "reducing", "deflation", "cheaper"},
     {"more", "higher", "increase", "increasing", "rise", "rising", "grow", "gain", "expand", "expanding", "inflation", "expensive"}),
    ({"less dense", "lower density", "lighter", "9% less dense"},
     {"denser", "heavier", "higher density", "more dense"}),
    ({"absorb", "absorbs", "absorbing", "intake", "consume", "take in", "capture"},
     {"produce", "produces", "producing", "release", "releases", "releasing", "emit", "discharge", "discharging", "generate", "create", "output"}),
    ({"reliable", "guarantee", "guarantees", "ordered", "error-checked", "connection-oriented", "handshake"},
     {"unreliable", "connectionless", "unordered", "lossy", "no guarantee", "without delivery guarantees", "without verification", "drops"}),
    ({"stimulate", "stimulates", "train", "training", "protect", "defend", "neutralize", "immunity", "antibodies"},
     {"destroy", "destroying", "poison", "harm", "kill immune", "damage", "weaken"}),
    ({"tilt", "tilted", "angle", "angles", "inclination", "obliquity"},
     {"closer to the sun", "farther away", "elliptical orbit distance", "distance to the sun"}),
    ({"scatter", "scattered", "scattering", "rayleigh", "wavelength", "wavelengths"},
     {"reflect the ocean", "mirror that reflects", "ocean waters", "reflects the blue color", "giant mirror"}),
    ({"barbarian", "invasion", "invasions", "visigoths", "vandals", "mercenaries", "corruption", "internal decay"},
     {"asteroid", "meteor", "alien", "comet strike"}),
]

VAGUE_DISCOURSE_MARKERS: Set[str] = {
    "various", "complex", "complicated", "multiple", "diverse", "several", "many",
    "different", "natural", "process", "processes", "factors", "conditions",
    "studied", "scientists", "experts", "years", "important", "matter", "things",
    "aspects", "dynamics", "developments", "variables", "inputs", "mechanics",
    "specifications", "particular", "ways", "effectively", "within", "across",
    "history", "historical", "period", "changes", "events", "involving", "safe",
}


def is_vague_non_answer(text: str) -> Tuple[bool, float]:
    """Detects evasive meta-discourse filler that avoids substantive factual mechanisms."""
    words = re.findall(r"[a-zA-Z]+", (text or "").lower())
    content_words = [w for w in words if len(w) >= 4]
    if not content_words:
        return False, 0.0
    vague_hits = [w for w in content_words if w in VAGUE_DISCOURSE_MARKERS]
    vague_ratio = len(vague_hits) / len(content_words)
    return vague_ratio >= 0.22, round(vague_ratio, 4)


def get_clause_snippet(text: str, phrase: str) -> str:
    """Extracts the clause-bounded text containing the specified phrase."""
    m = re.search(r"\b" + re.escape(phrase) + r"\b", text)
    if not m:
        return ""
    start = m.start()
    end = m.end()
    pre = text[:start]
    delims = [pre.rfind(d) for d in [",", ";", ".", " whereas ", " while ", " but "]]
    c_start = max(0, max(delims) + 1 if max(delims) != -1 else 0)
    post = text[end:]
    delims_post = [post.find(d) for d in [",", ";", ".", " whereas ", " while ", " but "] if post.find(d) != -1]
    c_end = end + min(delims_post) if delims_post else len(text)
    return text[c_start:c_end]


def check_snippet_polarity(snippet: str, set_a: Set[str], set_b: Set[str]) -> Tuple[bool, bool]:
    """Checks directional antonym polarity with negation masking."""
    s = " " + snippet.lower() + " "
    has_b = False
    for nw in sorted(set_b, key=len, reverse=True):
        if re.search(r"\b" + re.escape(nw) + r"\b", s):
            has_b = True
            s = re.sub(r"\b" + re.escape(nw) + r"\b", " [MASKED] ", s)

    has_a = False
    for pw in sorted(set_a, key=len, reverse=True):
        m = re.search(r"\b(without|no|not|never|lacks?)\s+(?:\w+\s+)?" + re.escape(pw) + r"\b", s)
        if m:
            has_b = True
            s = s[:m.start()] + " [MASKED] " + s[m.end():]
        elif re.search(r"\b" + re.escape(pw) + r"\b", s):
            has_a = True

    return has_a, has_b


def detect_contradiction(t1: str, t2: str) -> Tuple[bool, str]:
    """Detects factual inversions and opposing claims across responses."""
    t1_low = (t1 or "").lower()
    t2_low = (t2 or "").lower()

    key_phrases = [
        "purchasing power", "prices", "ice", "tcp", "udp", "oxygen",
        "carbon dioxide", "glucose", "water", "immune system", "sky",
        "seasons", "western roman empire", "rome",
    ]
    for kp in key_phrases:
        if re.search(r"\b" + re.escape(kp) + r"\b", t1_low) and re.search(r"\b" + re.escape(kp) + r"\b", t2_low):
            cl1 = get_clause_snippet(t1_low, kp)
            cl2 = get_clause_snippet(t2_low, kp)
            for set_a, set_b in ANTONYM_MODIFIERS:
                has_a_1, has_b_1 = check_snippet_polarity(cl1, set_a, set_b)
                has_a_2, has_b_2 = check_snippet_polarity(cl2, set_a, set_b)
                if (has_a_1 and has_b_2) or (has_b_1 and has_a_2):
                    return True, f"antonym_clause_collision on {kp}"

    # Broad antonym check across full text if no multi-phrase collision
    for set_a, set_b in ANTONYM_MODIFIERS:
        has_a_1, has_b_1 = check_snippet_polarity(t1_low, set_a, set_b)
        has_a_2, has_b_2 = check_snippet_polarity(t2_low, set_a, set_b)
        if (has_a_1 and not has_b_1 and has_b_2 and not has_a_2) or (has_b_1 and not has_a_1 and has_a_2 and not has_b_2):
            return True, "broad_antonym_polar_opposition"

    return False, "no_contradiction"


_CANARY_ELEMENTS = [
    ("Gold", "Au"), ("Silver", "Ag"), ("Iron", "Fe"), ("Copper", "Cu"),
    ("Helium", "He"), ("Oxygen", "O"), ("Sodium", "Na"), ("Potassium", "K"),
    ("Mercury", "Hg"), ("Lead", "Pb"), ("Carbon", "C"), ("Nitrogen", "N"),
    ("Calcium", "Ca"), ("Hydrogen", "H"), ("Zinc", "Zn"), ("Platinum", "Pt"),
    ("Chlorine", "Cl"), ("Magnesium", "Mg"), ("Aluminum", "Al"), ("Silicon", "Si"),
    ("Lithium", "Li"), ("Beryllium", "Be"), ("Boron", "B"), ("Fluorine", "F"),
    ("Neon", "Ne"), ("Phosphorus", "P"), ("Sulfur", "S"), ("Argon", "Ar"),
    ("Scandium", "Sc"), ("Titanium", "Ti"), ("Vanadium", "V"), ("Chromium", "Cr"),
    ("Manganese", "Mn"), ("Cobalt", "Co"), ("Nickel", "Ni"), ("Gallium", "Ga"),
    ("Germanium", "Ge"), ("Arsenic", "As"), ("Selenium", "Se"), ("Bromine", "Br"),
    ("Krypton", "Kr"), ("Rubidium", "Rb"), ("Strontium", "Sr"), ("Tin", "Sn"),
    ("Iodine", "I"), ("Xenon", "Xe"), ("Cesium", "Cs"), ("Barium", "Ba"),
    ("Tungsten", "W"), ("Bismuth", "Bi"), ("Uranium", "U"),
]

_CANARY_CAPITALS = [
    ("Japan", "Tokyo"), ("France", "Paris"), ("Germany", "Berlin"),
    ("Italy", "Rome"), ("Spain", "Madrid"), ("Canada", "Ottawa"),
    ("Australia", "Canberra"), ("Egypt", "Cairo"), ("Brazil", "Brasilia"),
    ("United Kingdom", "London"), ("China", "Beijing"), ("India", "New Delhi"),
    ("South Korea", "Seoul"), ("Argentina", "Buenos Aires"), ("Mexico", "Mexico City"),
    ("Russia", "Moscow"), ("South Africa", "Pretoria"), ("Turkey", "Ankara"),
    ("Norway", "Oslo"), ("Sweden", "Stockholm"), ("Finland", "Helsinki"),
    ("Denmark", "Copenhagen"), ("Switzerland", "Bern"), ("Netherlands", "Amsterdam"),
    ("Belgium", "Brussels"), ("Austria", "Vienna"), ("Greece", "Athens"),
    ("Portugal", "Lisbon"), ("Ireland", "Dublin"), ("Poland", "Warsaw"),
    ("Czech Republic", "Prague"), ("New Zealand", "Wellington"), ("Chile", "Santiago"),
    ("Colombia", "Bogota"), ("Peru", "Lima"), ("Thailand", "Bangkok"),
    ("Vietnam", "Hanoi"), ("Indonesia", "Jakarta"), ("Malaysia", "Kuala Lumpur"),
    ("Singapore", "Singapore"), ("Philippines", "Manila"), ("Saudi Arabia", "Riyadh"),
    ("Kenya", "Nairobi"), ("Nigeria", "Abuja"), ("Morocco", "Rabat"),
    ("Iceland", "Reykjavik"), ("Hungary", "Budapest"), ("Romania", "Bucharest"),
]

_CANARY_FACTS = [
    ("Which subatomic particle carries a negative electric charge?", "electron"),
    ("Which subatomic particle carries a positive electric charge?", "proton"),
    ("Which subatomic particle has no electric charge?", "neutron"),
    ("What is the boiling point of water in Celsius at 1 atmosphere pressure?", "100"),
    ("What is the freezing point of water in Celsius?", "0"),
    ("Which planet in our solar system is closest to the Sun?", "Mercury"),
    ("Which planet in our solar system is known as the Red Planet?", "Mars"),
    ("What is the largest planet in our solar system?", "Jupiter"),
    ("What gas do green plants primarily absorb from the air during photosynthesis?", "carbon dioxide"),
    ("What gas is released into the air by green plants during photosynthesis?", "oxygen"),
    ("What is the hardest known natural mineral on Earth?", "diamond"),
    ("What is the speed of light in vacuum approximately in thousands of kilometers per second?", "300"),
    ("What fundamental force pulls objects toward the center of the Earth?", "gravity"),
    ("What organ pumps blood through the human body?", "heart"),
    ("What pair of organs in the human body filters metabolic waste from blood?", "kidneys"),
    ("What is the primary chemical compound found in natural gas?", "methane"),
    ("What is the chemical formula for water?", "H2O"),
    ("How many bones are in the adult human skeleton?", "206"),
    ("What is the powerhouse of the biological cell?", "mitochondria"),
    ("Which ocean is the largest on Earth by surface area?", "Pacific"),
]

_CANARY_CODE = [
    ("Write a python function `def reverse_str(s):` that reverses a string.", "assert reverse_str('nexus') == 'suxen'\nassert reverse_str('abc') == 'cba'"),
    ("Write a python function `def add_nums(a, b):` that returns the sum of two numbers.", "assert add_nums(3, 5) == 8\nassert add_nums(-2, 2) == 0"),
    ("Write a python function `def count_vowels(s):` that returns the number of vowels in a string.", "assert count_vowels('hello') == 2\nassert count_vowels('sky') == 0"),
    ("Write a python function `def is_even(n):` that returns True if n is even, else False.", "assert is_even(4) == True\nassert is_even(7) == False"),
    ("Write a python function `def square(x):` that returns x squared.", "assert square(5) == 25\nassert square(0) == 0"),
]


def generate_procedural_canary(seed: Optional[int] = None) -> Dict[str, Any]:
    """Generates an unannounced, procedurally-grounded canary task with vast procedural diversity.
    Guarantees natural question phrasing and robust ground truth verification across infinite space.
    """
    import random
    rnd = random.Random(seed) if seed is not None else random.SystemRandom()
    cat = rnd.choice(["math", "element", "capital", "fact", "code", "word_math"])
    cid = f"canary-{cat}-{secrets.token_hex(4)}"

    if cat == "math":
        sub = rnd.choice(["mul", "mul_add", "mul_sub", "pow", "mod", "gcd"])
        if sub == "mul":
            a = rnd.randint(12, 199)
            b = rnd.randint(11, 99)
            prod = a * b
            prompt = rnd.choice([
                f"What is the product of {a} and {b}? Return only the single integer answer.",
                f"Calculate {a} multiplied by {b}.",
                f"What is {a} times {b}?",
                f"Compute {a} * {b}.",
            ])
            return {"id": cid, "feature": "brain_inference", "prompt": prompt, "expected": str(prod), "type": "number"}
        elif sub == "mul_add":
            a = rnd.randint(12, 99)
            b = rnd.randint(11, 49)
            c = rnd.randint(10, 199)
            val = a * b + c
            prompt = rnd.choice([
                f"What is the result of ({a} * {b}) + {c}?",
                f"Calculate {a} times {b} plus {c}.",
                f"Compute ({a} * {b}) + {c} as a single integer.",
            ])
            return {"id": cid, "feature": "brain_inference", "prompt": prompt, "expected": str(val), "type": "number"}
        elif sub == "mul_sub":
            a = rnd.randint(15, 99)
            b = rnd.randint(11, 49)
            c = rnd.randint(5, 80)
            val = a * b - c
            prompt = rnd.choice([
                f"Calculate {a} multiplied by {b} minus {c}.",
                f"What is {a} times {b} minus {c}?",
            ])
            return {"id": cid, "feature": "brain_inference", "prompt": prompt, "expected": str(val), "type": "number"}
        elif sub == "pow":
            base = rnd.choice([2, 3, 4, 5, 6, 7, 10])
            exp = rnd.randint(2, 6 if base <= 3 else 4)
            val = base ** exp
            prompt = rnd.choice([
                f"What is {base} to the power of {exp}?",
                f"Calculate {base} raised to the {exp} power.",
            ])
            return {"id": cid, "feature": "brain_inference", "prompt": prompt, "expected": str(val), "type": "number"}
        elif sub == "gcd":
            n1 = rnd.randint(12, 120)
            n2 = rnd.randint(12, 120)
            val = math.gcd(n1, n2)
            prompt = f"What is the greatest common divisor (GCD) of {n1} and {n2}?"
            return {"id": cid, "feature": "brain_inference", "prompt": prompt, "expected": str(val), "type": "number"}
        else:
            m = rnd.randint(7, 43)
            a = rnd.randint(20, 200)
            b = rnd.randint(5, 40)
            val = (a * b) % m
            prompt = f"What is the remainder when {a * b} is divided by {m}?"
            return {"id": cid, "feature": "brain_inference", "prompt": prompt, "expected": str(val), "type": "number"}

    elif cat == "word_math":
        sub = rnd.choice(["train", "boxes", "bandwidth", "factory"])
        if sub == "train":
            v = rnd.randint(40, 140)
            t = rnd.randint(2, 9)
            val = v * t
            prompt = f"A high-speed train travels at {v} km/h for {t} hours. What total distance in kilometers was traveled?"
            return {"id": cid, "feature": "brain_inference", "prompt": prompt, "expected": str(val), "type": "number"}
        elif sub == "boxes":
            a = rnd.randint(10, 60)
            b = rnd.randint(10, 30)
            c = rnd.randint(5, 50)
            val = a * b - c
            prompt = f"A warehouse contains {a} boxes with {b} items in each box. After {c} items are removed, how many items remain in total?"
            return {"id": cid, "feature": "brain_inference", "prompt": prompt, "expected": str(val), "type": "number"}
        elif sub == "bandwidth":
            rate = rnd.randint(10, 150)
            sec = rnd.randint(10, 60)
            val = rate * sec
            prompt = f"A network interface transmits {rate} megabytes per second. How many megabytes are transmitted in {sec} seconds?"
            return {"id": cid, "feature": "brain_inference", "prompt": prompt, "expected": str(val), "type": "number"}
        else:
            workers = rnd.randint(3, 12)
            units = rnd.randint(5, 20)
            days = rnd.randint(2, 7)
            val = workers * units * days
            prompt = f"A team of {workers} workers each produces {units} components per day. Over {days} days, how many total components are produced?"
            return {"id": cid, "feature": "brain_inference", "prompt": prompt, "expected": str(val), "type": "number"}

    elif cat == "element":
        el, sym = rnd.choice(_CANARY_ELEMENTS)
        prompt = rnd.choice([
            f"What is the chemical symbol for the element {el}? Provide only the standard chemical symbol.",
            f"What is the chemical symbol for {el}?",
            f"Provide the standard two-letter chemical symbol for {el}.",
            f"In chemistry, what symbol denotes the element {el}?",
        ])
        return {"id": cid, "feature": "brain_inference", "prompt": prompt, "expected": sym, "type": "word"}

    elif cat == "capital":
        country, cap = rnd.choice(_CANARY_CAPITALS)
        prompt = rnd.choice([
            f"What is the capital of {country}?",
            f"What is the capital city of {country}?",
            f"Name the capital city of {country}.",
            f"Which city serves as the official capital of {country}?",
        ])
        return {"id": cid, "feature": "brain_inference", "prompt": prompt, "expected": cap, "type": "word"}

    elif cat == "fact":
        q, ans = rnd.choice(_CANARY_FACTS)
        return {"id": cid, "feature": "brain_inference", "prompt": q, "expected": ans, "type": "word" if not ans.isdigit() else "number"}

    else:
        # Procedurally parameterized code tasks
        templates = ["reverse_str", "add_nums", "count_vowels", "is_even", "square", "find_max", "sum_evens", "factorial", "count_char"]
        tpl = rnd.choice(templates)
        if tpl == "reverse_str":
            w = rnd.choice(["nexus", "crypto", "quantum", "matrix", "tensor", "vector", "neural", "python"])
            prompt = "Write a python function `def reverse_str(s):` that reverses a string."
            assertions = f"assert reverse_str({w!r}) == {w[::-1]!r}\nassert reverse_str('abc') == 'cba'"
        elif tpl == "find_max":
            nums = [rnd.randint(1, 99) for _ in range(4)]
            prompt = "Write a python function `def find_max(lst):` returning the largest number in a list."
            assertions = f"assert find_max({nums}) == {max(nums)}\nassert find_max([5, 1, 9, 3]) == 9"
        elif tpl == "sum_evens":
            nums = [rnd.randint(1, 20) for _ in range(4)]
            ev_sum = sum(x for x in nums if x % 2 == 0)
            prompt = "Write a python function `def sum_evens(lst):` returning the sum of even numbers in a list."
            assertions = f"assert sum_evens({nums}) == {ev_sum}\nassert sum_evens([1, 3, 5]) == 0"
        elif tpl == "factorial":
            n = rnd.randint(3, 6)
            prompt = "Write a python function `def factorial(n):` that computes the factorial of non-negative integer n."
            assertions = f"assert factorial({n}) == {math.factorial(n)}\nassert factorial(0) == 1"
        elif tpl == "count_char":
            ch = rnd.choice(["a", "e", "l", "o", "r"])
            word = rnd.choice(["parallel", "hello", "banana", "tomorrow", "apple", "network"])
            prompt = f"Write a python function `def count_char(s, ch):` that returns how many times character `ch` appears in string `s`."
            assertions = f"assert count_char({word!r}, {ch!r}) == {word.count(ch)}\nassert count_char('xyz', 'a') == 0"
        elif tpl == "count_vowels":
            prompt = "Write a python function `def count_vowels(s):` that returns the number of vowels in a string."
            assertions = "assert count_vowels('hello') == 2\nassert count_vowels('sky') == 0\nassert count_vowels('antigravity') == 5"
        elif tpl == "is_even":
            n = rnd.randint(10, 50)
            prompt = "Write a python function `def is_even(n):` that returns True if n is even, else False."
            assertions = f"assert is_even({n}) == {n % 2 == 0}\nassert is_even({n+1}) == {(n+1) % 2 == 0}"
        elif tpl == "square":
            n = rnd.randint(4, 15)
            prompt = "Write a python function `def square(x):` that returns x squared."
            assertions = f"assert square({n}) == {n * n}\nassert square(0) == 0"
        else:
            a = rnd.randint(3, 50)
            b = rnd.randint(3, 50)
            prompt = "Write a python function `def add_nums(a, b):` that returns the sum of two numbers."
            assertions = f"assert add_nums({a}, {b}) == {a + b}\nassert add_nums(-2, 2) == 0"
        return {"id": cid, "feature": "brain_inference", "prompt": prompt, "test_assertions": assertions, "type": "code"}


CONCEPT_TAXONOMY: Dict[str, Set[str]] = {
    "PHYSICS_QUANTUM": {
        "quantum", "entangle", "particl", "subatom", "wave", "stat", "spin", "photon",
        "atom", "electron", "proton", "superposit", "teleport", "physic", "matter",
        "energi", "field", "intertwin", "molecul", "mechan", "correlat",
    },
    "OPTICS_LIGHT": {
        "light", "wavelength", "scatter", "rayleigh", "atmospher", "sunlight",
        "molecul", "blue", "sky", "color", "spectrum", "optic", "reflect",
        "refract", "absorb", "frequenc", "photon", "beam", "radiat",
    },
    "BIOLOGY_LIFE": {
        "photosynthe", "plant", "cell", "chlorophyl", "chloroplast", "sugar",
        "glucos", "solar", "sun", "leaf", "leav", "carbon", "dioxid", "oxygen",
        "water", "organ", "biolog", "energi", "chemic",
    },
    "RELATIVITY_GRAVITY": {
        "relativ", "gravit", "spacetim", "space", "time", "mass", "curv",
        "curvatur", "einstein", "fabric", "speed", "veloc", "warp", "accelerat",
        "matter", "physic",
    },
    "COMPUTING_TECH": {
        "comput", "algorithm", "code", "softwar", "program", "hash", "encrypt",
        "network", "server", "data", "token", "neural", "train", "model",
        "tcp", "udp", "protocol", "packet", "handshak", "reliabl", "unreliabl",
        "latenc", "stream", "datagram", "deliveri", "connect", "order",
    },
    "ASTRONOMY_PLANETARY": {
        "season", "earth", "sun", "orbit", "tilt", "axi", "hemispher", "solar",
        "planet", "summer", "winter", "rotat", "angl", "radiat", "incid", "climat",
        "astronomi", "space", "eclips", "equator", "pole", "axial",
    },
    "CHEMISTRY_MATTER": {
        "ice", "water", "solid", "liquid", "gas", "crystal", "lattic", "hydrogen",
        "bond", "dens", "densiti", "freez", "molecul", "expand", "float", "temperatur",
        "mass", "volum", "hexagan", "hexagonal", "structur", "melt",
    },
    "ECONOMICS_FINANCE": {
        "infl", "inflat", "price", "pric", "money", "currenc", "purchas", "power", "suppli", "supp", "demand",
        "market", "cost", "deflat", "econom", "economic", "economi", "bank", "good", "servic",
        "output", "monetari", "central", "rate", "consum", "spend",
    },
    "HISTORY_CIVILIZATION": {
        "rome", "roman", "empir", "fall", "barbarian", "invas", "collaps", "decay",
        "corrupt", "crisi", "militari", "mercenari", "emperor", "trib", "ancient",
        "civil", "west", "western", "visigoth", "vandal", "instabl",
    },
    "MEDICINE_IMMUNOLOGY": {
        "vaccin", "immun", "antibodi", "antigen", "pathogen", "viru", "infect",
        "diseas", "white", "blood", "cell", "bacteria", "protect", "defens",
        "neutral", "bodi", "health", "medic", "prepar",
    },
    "GENERAL_SCIENCE": {
        "phenomenon", "measur", "observ", "correlat", "interact", "system",
        "mechan", "dynam", "transform", "process", "instant", "instantane",
        "simultan", "connect", "link", "depend", "properti", "stat", "effect",
        "caus", "determin", "acros", "distanc", "space", "pair",
    },
    "RELATIONAL_CORE": {
        "connect", "link", "pair", "stat", "chang", "occur", "remain", "depend",
        "caus", "produc", "differ", "similar", "increas", "decreas", "describ",
        "relat", "regardles", "hold", "keep", "bound", "tie",
    },
    "RELATION_SPACE": {
        "distanc", "space", "far", "remot", "separat", "acros", "locat",
        "posit", "spatial", "interv", "reach", "apart", "away",
    },
    "RELATION_STATE": {
        "remain", "stay", "persist", "hold", "continu", "maintain", "keep", "exist",
    },
    "RELATION_TIME": {
        "instant", "immediat", "instantane", "simultan", "time", "speed", "durat", "fast", "moment", "quick",
    },
    "RELATION_CONDITION": {
        "regardles", "despit", "independ", "irrespect", "notwithstand",
    },
    "OBSERVE_MEASURE": {
        "measur", "observ", "detect", "determin", "test", "probe", "gaug", "check", "record",
    },
    "CAUSAL_DETERMINE": {
        "caus", "determin", "influenc", "affect", "dictat", "control", "govern", "decid", "lead", "trigger", "fix",
    },
}


def extract_novel_clusters(stems: Iterable[str]) -> Set[str]:
    """Maps content stems to broad semantic concept clusters."""
    clusters = set()
    for st in stems:
        for c_name, words in CONCEPT_TAXONOMY.items():
            if st in words or any(w.startswith(st) or st.startswith(w) for w in words):
                clusters.add(c_name)
    return clusters


GOLDEN_CANARIES: List[Dict[str, Any]] = [
    {
        "id": "canary-math-factor-1",
        "feature": "brain_inference",
        "prompt": "What is the product of 17 and 19? Return only the single integer answer.",
        "verifier": lambda text: bool(re.search(r"\b323\b", str(text or ""))),
        "expected": "323",
    },
    {
        "id": "canary-sci-element-1",
        "feature": "brain_inference",
        "prompt": "What is the chemical symbol for the element Gold? Provide only the standard two-letter chemical symbol.",
        "verifier": lambda text: bool(re.search(r"(?i)\bau\b", str(text or ""))),
        "expected": "Au",
    },
    {
        "id": "canary-code-reverse-1",
        "feature": "brain_inference",
        "prompt": "Write a python function `def reverse_str(s):` that reverses a string.",
        "test_assertions": "assert reverse_str('nexus') == 'suxen'\nassert reverse_str('abc') == 'cba'",
        "expected": "reverse_str",
    },
    {
        "id": "canary-physics-charge-1",
        "feature": "brain_inference",
        "prompt": "Which subatomic particle carries a negative electric charge: proton, neutron, or electron?",
        "verifier": lambda text: bool(re.search(r"(?i)\belectron\b", str(text or ""))),
        "expected": "electron",
    },
]


def compute_novel_stem_cosine_similarity(stems1: List[str], stems2: List[str]) -> float:
    """Computes cosine similarity on novel content stem vectors."""
    if not stems1 or not stems2:
        return 0.0
    from collections import Counter
    v1 = Counter(stems1)
    v2 = Counter(stems2)
    keys = set(v1.keys()) | set(v2.keys())
    dot = sum(v1.get(k, 0) * v2.get(k, 0) for k in keys)
    n1_sq = sum(v * v for v in v1.values())
    n2_sq = sum(v * v for v in v2.values())
    if n1_sq <= 1e-12 or n2_sq <= 1e-12:
        return 0.0
    return dot / (math.sqrt(n1_sq) * math.sqrt(n2_sq))


def compute_content_cosine_similarity(text1: str, text2: str) -> float:
    """Computes exact cosine similarity over substantive content word vectors."""
    t1 = extract_content_tokens(text1)
    t2 = extract_content_tokens(text2)
    if len(t1) < 4 or len(t2) < 4:
        return 0.0

    from collections import Counter
    vec1 = Counter(t1)
    vec2 = Counter(t2)
    all_keys = set(vec1.keys()) | set(vec2.keys())

    dot = sum(vec1.get(k, 0) * vec2.get(k, 0) for k in all_keys)
    norm1_sq = sum(v * v for v in vec1.values())
    norm2_sq = sum(v * v for v in vec2.values())
    if norm1_sq <= 1e-12 or norm2_sq <= 1e-12:
        return 0.0
    return dot / (math.sqrt(norm1_sq) * math.sqrt(norm2_sq))


def _is_independent_peer(w1: WorkerNodeRecord, w2: WorkerNodeRecord) -> bool:
    """Verifies that two workers are genuinely independent nodes (Anti-Sybil Separation)."""
    if not w1 or not w2:
        return False
    if w1.worker_id == w2.worker_id:
        return False
    if w1.hardware_uuid and w2.hardware_uuid and w1.hardware_uuid == w2.hardware_uuid:
        return False
    ip1 = (getattr(w1, "public_ip", "") or "").strip()
    ip2 = (getattr(w2, "public_ip", "") or "").strip()
    local_hosts = {"", "local", "127.0.0.1", "localhost", "::1"}
    if ip1 not in local_hosts and ip2 not in local_hosts:
        if ip1 == ip2:
            return False
        # Check /24 IPv4 subnet
        sub1 = ".".join(ip1.split(".")[:3]) if "." in ip1 else ip1
        sub2 = ".".join(ip2.split(".")[:3]) if "." in ip2 else ip2
        if sub1 == sub2:
            return False
    # Check referral collusion
    if getattr(w1, "referred_by", "") and w1.referred_by == w2.worker_id:
        return False
    if getattr(w2, "referred_by", "") and w2.referred_by == w1.worker_id:
        return False
    return True


def _comparable(result: Any) -> Any:
    if isinstance(result, dict):
        return {k: v for k, v in result.items() if k not in _VOLATILE_KEYS}
    return result


def _spot_checkable(feature: str, payload: dict) -> bool:
    if feature not in SPOT_CHECKABLE:
        return False
    if not isinstance(payload, dict):
        return False
    if feature == "trend_forecasting":
        return isinstance(payload.get("series") or payload.get("data"), list)
    if feature == "data_analysis":
        return bool(payload.get("series") or payload.get("data") or payload.get("numbers"))
    if feature == "virtual_experiment_simulator":
        return not payload.get("code")
    return True


WELCOME_CREDITS = 20
REFERRAL_BONUS_RATE = 0.05  # +5% extra bonus credits minted to referrer when referred worker mines/completes tasks
POW_DIFFICULTY = int(os.environ.get("NEXUS_POW_DIFFICULTY", "4"))  # SHA-256 hex prefix difficulty (~65,536 hashes default, scales up to 6)


def dynamic_pow_difficulty(active_workers: int = 1) -> int:
    """Dynamically scales Micro-PoW difficulty based on network size (N4 Anti-Sybil Fix)."""
    if active_workers > 500:
        return max(POW_DIFFICULTY, 6)
    if active_workers > 50:
        return max(POW_DIFFICULTY, 5)
    return POW_DIFFICULTY


def solve_pow_challenge(worker_id: str, challenge: str, difficulty: int = POW_DIFFICULTY) -> str:
    """Solves the Hub's Micro-PoW challenge by burning real CPU SHA-256 cycles."""
    prefix = "0" * max(1, int(difficulty))
    nonce = 0
    base = f"{worker_id}:{challenge}:"
    while True:
        candidate = f"{base}{nonce}".encode("utf-8")
        if hashlib.sha256(candidate).hexdigest().startswith(prefix):
            return str(nonce)
        nonce += 1


def verify_pow_solution(worker_id: str, challenge: str, nonce: str, difficulty: int = POW_DIFFICULTY) -> bool:
    """Verifies a worker's Micro-PoW solution for a heartbeat ping (N4 Fix: strict difficulty check, no '00' fallback)."""
    if not challenge or nonce is None or str(nonce).strip() == "":
        return False
    prefix = "0" * max(1, int(difficulty))
    digest = hashlib.sha256(f"{worker_id}:{challenge}:{str(nonce).strip()}".encode("utf-8")).hexdigest()
    return digest.startswith(prefix)


def _ip_subnet_prefix(ip_str: str) -> str:
    """Extracts /24 IPv4 or /48 IPv6 subnet prefix to mitigate proxy/VPN rotation within the same ASN block (N4 Fix)."""
    clean = (ip_str or "").strip()
    if not clean or clean in {"127.0.0.1", "localhost", "::1", "local"}:
        return ""
    if "." in clean:
        parts = clean.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
    if ":" in clean:
        hextets = clean.split(":")
        return ":".join(hextets[:3]) + "::/48"
    return clean


@dataclass
class WorkerNodeRecord:
    worker_id: str
    key: str = field(repr=False)
    url: str = "local"
    status: str = "ACTIVE"  # ACTIVE | SLASHED
    credits: int = WELCOME_CREDITS
    welcome_credits_locked: int = 0
    burned_credits: int = 0
    tasks_completed: int = 0
    tasks_verified: int = 0
    rejected_packets: int = 0
    registered_at: float = field(default_factory=time.time)
    slashed_reason: str = ""
    payout_address: str = ""
    total_payout_earned: float = 0.0
    pending_payout: float = 0.0
    epoch_tasks_verified: int = 0
    uptime_minutes_verified: int = 0
    last_heartbeat_reward_at: float = field(default_factory=time.time)
    # Anti-Sybil & Hardware Rig Specs
    hardware_uuid: str = ""
    public_ip: str = ""
    hardware_spec: str = "Standard Multi-Core Rig"
    # Anti-Fake-Uptime Micro-PoW
    pow_challenge: str = field(default_factory=lambda: secrets.token_hex(8))
    pow_verified_count: int = 0
    # P2P Dispute Freeze (H6: order-scoped freeze by default; account lock only for accused scammer)
    dispute_frozen: bool = False
    dispute_account_locked: bool = False
    dispute_escrow_locked_credits: int = 0
    dispute_reason: str = ""
    # Viral Referral Multiplier (+5% Network Effect)
    referral_code: str = ""
    referred_by: str = ""
    referrals_count: int = 0
    referral_bonus_credits: int = 0
    referral_bonus_accumulator: float = 0.0
    # Decentralized Brain Matrix Sharding & P2P Delta Sync
    brain_shard: str = "DATA_MEMORY_SYNTHESIS"
    replica_shards: List[str] = field(default_factory=lambda: ["CODE_DEBUG_EXEC", "MATH_PROOF_LOGIC"])
    synced_deltas_count: int = 0
    protocol_version: str = "2026.5.0"
    # Multi-Chamber 4096-Bit Hybrid Cryptographic Identity (HSQK-4096)
    quantum_address: str = ""
    crypto_security_level: str = "4096-Bit Hybrid Lattice + Ed448 + SHA3-512 Key Vault"
    puf_seal: str = ""
    quantum_vault_pub: Dict[str, Any] = field(default_factory=dict)
    ratchet_step: int = 0
    daily_task_credits_earned: int = 0
    daily_task_window_start: float = 0.0
    canary_strikes: int = 0

    def __post_init__(self) -> None:
        if not self.referral_code:
            self.referral_code = f"REF-{self.worker_id.upper()}"
        if not self.pow_challenge:
            self.pow_challenge = secrets.token_hex(8)
        if not self.brain_shard:
            from .brain_matrix import assign_worker_brain_shard
            sh = assign_worker_brain_shard(4, self.hardware_spec, self.worker_id)
            self.brain_shard = sh["primary_shard"]
            self.replica_shards = sh["replica_shards"]
        if not self.quantum_address:
            try:
                from .quantum_crypto import encode_quantum_address, ADDRESS_HRP
                seed = hashlib.blake2b(f"{self.worker_id}:{self.key}".encode("utf-8"), digest_size=32).digest()
                self.quantum_address = encode_quantum_address(ADDRESS_HRP, seed)
            except Exception:
                self.quantum_address = f"nxq1{self.worker_id.replace('-', '')[:16]}q000"

    def to_dict(self, include_key: bool = False) -> dict:
        d = dataclasses.asdict(self)
        if not include_key:
            d.pop("key")
        return d


class MasterHubCoordinator:
    """Runs only on the owner's Hub: issues signed tasks, verifies proofs, spot-checks, rewards and slashes."""

    def __init__(self, ledger: HashChainLedger, grid: Any = None, state_path: Optional[Path] = None,
                 reward_per_task: int = 25, spot_check_rate: float = 1.0, gradient_spot_check_rate: float = 1.0):
        self.ledger = ledger
        self.grid = grid  # used for spot-check re-execution
        self.reward_per_task = reward_per_task
        self.spot_check_rate = spot_check_rate
        self.gradient_spot_check_rate = gradient_spot_check_rate
        self.force_gradient_spot_check = True
        self.max_referral_cap = 500
        self.max_workers_per_ip = 3
        self.max_daily_task_credits = 250
        self.enable_canary_injection: bool = False
        self.canary_injection_rate_pct: int = 5
        self.force_canary_injection: bool = False
        self._worker_last_canary: Dict[str, float] = {}
        self._replay_canary_pool: List[Dict[str, Any]] = [
            {
                "id": "replay-seed-sky-blue",
                "feature": "brain_inference",
                "prompt": "Why is the sky blue?",
                "trusted_output": "The blue color of the sky is caused by Rayleigh scattering. As sunlight enters the atmosphere, shorter blue wavelengths are scattered much more strongly by air molecules than longer red wavelengths.",
                "is_replay": True,
            },
            {
                "id": "replay-seed-seasons",
                "feature": "brain_inference",
                "prompt": "Why do we have seasons on Earth?",
                "trusted_output": "Seasons occur because of the 23.5 degree axial tilt of the Earth. When the Northern Hemisphere is tilted toward the Sun, it experiences summer due to direct sunlight, while the Southern Hemisphere experiences winter.",
                "is_replay": True,
            },
            {
                "id": "replay-seed-vaccines",
                "feature": "brain_inference",
                "prompt": "How do vaccines protect against disease?",
                "trusted_output": "Vaccines work by training the immune system to recognize antigens from pathogens. The body creates specific antibodies and memory B and T cells that rapidly neutralize the actual pathogen if exposed later.",
                "is_replay": True,
            },
            {
                "id": "replay-seed-tcp-udp",
                "feature": "brain_inference",
                "prompt": "What is the difference between TCP and UDP protocols?",
                "trusted_output": "TCP is a connection-oriented protocol that provides reliable, ordered, and error-checked delivery of data using a three-way handshake, whereas UDP is connectionless and faster without delivery guarantees.",
                "is_replay": True,
            },
            {
                "id": "replay-seed-ice-float",
                "feature": "brain_inference",
                "prompt": "Why does ice float on water?",
                "trusted_output": "Solid water floats because it expands upon freezing due to hydrogen bonding. The resulting crystalline structure has more open space between molecules, meaning ice has lower density than liquid water.",
                "is_replay": True,
            },
            {
                "id": "replay-seed-inflation",
                "feature": "brain_inference",
                "prompt": "What causes economic inflation?",
                "trusted_output": "Economic inflation occurs when too much money chases too few goods, often triggered by loose central bank monetary policy (demand-pull) or supply chain disruptions and rising energy costs (cost-push).",
                "is_replay": True,
            },
            {
                "id": "replay-seed-photosynthesis",
                "feature": "brain_inference",
                "prompt": "How does photosynthesis work in plants?",
                "trusted_output": "In plant chloroplasts, solar energy drives a chemical reaction combining water and carbon dioxide to produce glucose for energy while discharging oxygen gas into the atmosphere.",
                "is_replay": True,
            },
            {
                "id": "replay-seed-rome-fall",
                "feature": "brain_inference",
                "prompt": "What caused the fall of the Western Roman Empire?",
                "trusted_output": "The collapse of Western Rome was driven by internal decay such as political instability and economic decline, combined with external military pressure and migrations from barbarian tribes including the Visigoths and Vandals.",
                "is_replay": True,
            },
        ]
        self._path = state_path
        self._workers: Dict[str, WorkerNodeRecord] = {}
        self._pending: Dict[str, dict] = {}
        self._nat_outbound_queue: Dict[str, List[dict]] = {}
        self._nat_in_flight: Dict[str, dict] = {}
        self._nat_task_events: Dict[str, threading.Event] = {}
        self._nat_settled_results: Dict[str, dict] = {}
        self._freeform_consensus: Dict[str, dict] = {}
        self.commercial_revenue_pool: float = 0.0
        self.treasury_balance: float = 0.0
        self.current_epoch: int = 1
        self.appeal_log: List[dict] = []
        self._lock = threading.RLock()
        self._load()
        self._stop_maintenance = threading.Event()
        self._maintenance_thread = threading.Thread(target=self._maintenance_loop, daemon=True, name="nexus-hub-prune-loop")
        self._maintenance_thread.start()

    def _maintenance_loop(self) -> None:
        while not self._stop_maintenance.wait(15.0):
            try:
                self.prune_expired_tasks()
            except Exception:
                pass

    def stop(self) -> None:
        self._stop_maintenance.set()
        if hasattr(self, "_maintenance_thread") and self._maintenance_thread.is_alive():
            try:
                self._maintenance_thread.join(timeout=1.0)
            except Exception:
                pass

    # -- persistence & WAL crash-recovery (H4 / M7 Fix)
    def _load(self) -> None:
        last_settled_hash = ""
        if self._path and self._path.exists():
            try:
                with interprocess_file_lock(self._path):
                    data = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self.commercial_revenue_pool = float(data.get("commercial_revenue_pool", 0.0))
                    self.treasury_balance = float(data.get("treasury_balance", 0.0))
                    self.current_epoch = int(data.get("current_epoch", 1))
                    last_settled_hash = str(data.get("last_settled_ledger_hash", ""))
                    workers_data = data.get("workers", [])
                else:
                    workers_data = data
                valid_fields = {f.name for f in dataclasses.fields(WorkerNodeRecord)}
                for d in workers_data:
                    filtered = {k: v for k, v in d.items() if k in valid_fields}
                    self._workers[d["worker_id"]] = WorkerNodeRecord(**filtered)
            except Exception:
                pass
        self._reconcile_wal_from_ledger(last_settled_hash)

    def _reconcile_wal_from_ledger(self, last_settled_hash: str) -> None:
        """Replays any uncommitted WAL credit transitions from HashChainLedger after a process crash (H4 Fix)."""
        if not self.ledger or not self._workers:
            return
        try:
            blocks = self.ledger.range(0, len(self.ledger))
            if not blocks:
                return
            start_idx = 0
            if last_settled_hash:
                found = False
                for idx, b in enumerate(blocks):
                    if b.get("hash") == last_settled_hash:
                        start_idx = idx + 1
                        found = True
                        break
                if not found:
                    return
            else:
                return
            reconciled = False
            for b in blocks[start_idx:]:
                task = b.get("data", {}).get("task", "")
                p = b.get("data", {}).get("payload", {})
                if task == "credits_spent":
                    w = self._workers.get(p.get("worker_id", ""))
                    if w and "remaining" in p and w.credits != int(p["remaining"]):
                        w.credits = int(p["remaining"])
                        reconciled = True
                elif task == "owner_credits_granted":
                    w = self._workers.get(p.get("worker_id", ""))
                    if w and "new_balance" in p and w.credits != int(p["new_balance"]):
                        w.credits = int(p["new_balance"])
                        reconciled = True
                elif task == "credits_transferred":
                    wf = self._workers.get(p.get("from_worker", ""))
                    wt = self._workers.get(p.get("to_worker", ""))
                    if wf and "from_balance" in p:
                        wf.credits = int(p["from_balance"])
                        reconciled = True
                    if wt and "to_balance" in p:
                        wt.credits = int(p["to_balance"])
                        reconciled = True
            if reconciled:
                self._flush()
        except Exception:
            pass

    def _flush(self) -> None:
        if not self._path:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with interprocess_file_lock(self._path):
            tmp = self._path.with_suffix(".tmp")
            payload = {
                "commercial_revenue_pool": self.commercial_revenue_pool,
                "treasury_balance": self.treasury_balance,
                "current_epoch": self.current_epoch,
                "last_settled_ledger_hash": getattr(self.ledger, "head_hash", "") if self.ledger else "",
                "workers": [w.to_dict(include_key=True) for w in self._workers.values()],
            }
            with tmp.open("w", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, indent=1))
                fh.flush()
                try:
                    os.fsync(fh.fileno())
                except OSError:
                    pass
            tmp.replace(self._path)
            try:
                os.chmod(self._path, 0o600)
            except OSError:
                pass

    def _resolve_referrer(self, ref_code_or_id: str) -> Optional[WorkerNodeRecord]:
        if not ref_code_or_id:
            return None
        cand = str(ref_code_or_id).strip()
        with self._lock:
            if cand in self._workers:
                return self._workers[cand]
            upper = cand.upper()
            for w in self._workers.values():
                if w.referral_code.upper() == upper or w.worker_id.upper() == upper:
                    return w
            return None

    def _award_referral_bonus(self, earner: WorkerNodeRecord, earned_credits: int, source: str) -> int:
        """Awards +5% extra bonus credits to earner's referrer without deducting from earner (capped per N4 Fix)."""
        if not earner.referred_by or earned_credits <= 0:
            return 0
        max_referral_cap = int(getattr(self, "max_referral_cap", 500))
        with self._lock:
            referrer = self._workers.get(earner.referred_by)
            if not referrer or referrer.status != "ACTIVE" or referrer.worker_id == earner.worker_id:
                return 0
            if referrer.referral_bonus_credits >= max_referral_cap:
                return 0
            exact_bonus = float(earned_credits) * REFERRAL_BONUS_RATE
            referrer.referral_bonus_accumulator = round(referrer.referral_bonus_accumulator + exact_bonus, 4)
            if source == "task_settlement":
                # Guarantee at least +1 bonus credit on active task completion (e.g. 5% of 25 = 1.25 -> +1 cr immediately)
                minted = max(1, int(referrer.referral_bonus_accumulator))
                referrer.referral_bonus_accumulator = max(0.0, round(referrer.referral_bonus_accumulator - minted, 4))
            else:
                minted = int(referrer.referral_bonus_accumulator)
                if minted > 0:
                    referrer.referral_bonus_accumulator = round(referrer.referral_bonus_accumulator - minted, 4)
            minted = min(minted, max(0, max_referral_cap - referrer.referral_bonus_credits))
            if minted > 0:
                referrer.credits += minted
                referrer.referral_bonus_credits += minted
                self.ledger.append("referral_bonus_minted", {
                    "referrer_id": referrer.worker_id,
                    "from_referred_worker": earner.worker_id,
                    "source": source,
                    "worker_earned": earned_credits,
                    "bonus_minted": minted,
                    "referrer_new_balance": referrer.credits,
                })
            return minted

    # -- registry
    def register_worker(self, worker_id: str, url: str = "local", initial_credits: int = WELCOME_CREDITS,
                        hardware_uuid: str = "", public_ip: str = "", hardware_spec: str = "",
                        referred_by: str = "", version: str = "",
                        quantum_address: str = "", quantum_vault_pub: Optional[Dict[str, Any]] = None,
                        puf_seal: str = "") -> WorkerNodeRecord:
        from .brain_matrix import assign_worker_brain_shard

        hardware_uuid = (hardware_uuid or "").strip()
        public_ip = (public_ip or "").strip()
        hardware_spec = (hardware_spec or "").strip()
        referred_by = (referred_by or "").strip()
        version = (version or "").strip()
        quantum_address = (quantum_address or "").strip()
        puf_seal = (puf_seal or "").strip()
        quantum_vault_pub = quantum_vault_pub or {}

        with self._lock:
            existing = self._workers.get(worker_id)
            if existing and existing.status == "SLASHED":
                raise PermissionError(f"Worker {worker_id!r} is blacklisted (slashed: {existing.slashed_reason})")
            if existing:
                if url and url != "local":
                    existing.url = url
                if hardware_spec:
                    existing.hardware_spec = hardware_spec
                    sh = assign_worker_brain_shard(4, hardware_spec, worker_id)
                    existing.brain_shard = sh["primary_shard"]
                    existing.replica_shards = sh["replica_shards"]
                if hardware_uuid and not existing.hardware_uuid:
                    existing.hardware_uuid = hardware_uuid
                if version:
                    existing.protocol_version = version
                if quantum_address:
                    existing.quantum_address = quantum_address
                if quantum_vault_pub:
                    existing.quantum_vault_pub = quantum_vault_pub
                if puf_seal:
                    existing.puf_seal = puf_seal
                if referred_by and not existing.referred_by:
                    referrer = self._resolve_referrer(referred_by)
                    if referrer and referrer.worker_id != existing.worker_id:
                        existing.referred_by = referrer.worker_id
                        referrer.referrals_count += 1
                self._flush()
                return existing

            # Anti-Sybil VM & Sandbox Spoofing Guard: block multiple workers with the same hardware_uuid
            if hardware_uuid and worker_id != "owner-master":
                for other in self._workers.values():
                    if other.worker_id != worker_id and other.hardware_uuid and other.hardware_uuid == hardware_uuid:
                        self.ledger.append("sybil_attempt_blocked", {
                            "attempted_worker_id": worker_id,
                            "existing_worker_id": other.worker_id,
                            "hardware_uuid": hardware_uuid,
                            "public_ip": public_ip,
                        })
                        raise PermissionError(
                            f"Anti-Sybil Hardware Guard: Hardware fingerprint {hardware_uuid!r} is already registered to "
                            f"active worker {other.worker_id!r}. Spinning up multiple VMs/clones on 1 PC to farm welcome "
                            f"credits or uptime is strictly blocked."
                        )

            # Anti-Sybil Per-IP Limit (N4 Fix): block mass registration from the same public IP
            if public_ip and public_ip not in {"127.0.0.1", "localhost", "::1", "local"} and worker_id != "owner-master":
                same_ip_count = sum(
                    1 for other in self._workers.values()
                    if other.worker_id != worker_id and other.public_ip == public_ip and other.status == "ACTIVE"
                )
                if same_ip_count >= int(getattr(self, "max_workers_per_ip", 3)):
                    self.ledger.append("sybil_ip_limit_blocked", {
                        "attempted_worker_id": worker_id,
                        "public_ip": public_ip,
                        "existing_count": same_ip_count,
                    })
                    raise PermissionError(
                        f"Anti-Sybil IP Guard (N4): Maximum workers ({self.max_workers_per_ip}) per public IP ({public_ip}) exceeded."
                    )
                subnet = _ip_subnet_prefix(public_ip)
                if subnet:
                    same_subnet_count = sum(
                        1 for other in self._workers.values()
                        if other.worker_id != worker_id and other.status == "ACTIVE" and _ip_subnet_prefix(other.public_ip) == subnet
                    )
                    max_subnet = int(getattr(self, "max_workers_per_subnet", 5))
                    if same_subnet_count >= max_subnet:
                        self.ledger.append("sybil_subnet_limit_blocked", {
                            "attempted_worker_id": worker_id,
                            "public_ip": public_ip,
                            "subnet": subnet,
                            "existing_count": same_subnet_count,
                        })
                        raise PermissionError(
                            f"Anti-Sybil Subnet Guard (N4): Maximum workers ({max_subnet}) per subnet ({subnet}) exceeded."
                        )

            referrer = self._resolve_referrer(referred_by) if referred_by else None
            ref_wid = referrer.worker_id if (referrer and referrer.worker_id != worker_id) else ""
            eff_spec = hardware_spec or "Standard Multi-Core Rig"
            shard_info = assign_worker_brain_shard(4, eff_spec, worker_id)

            rec = WorkerNodeRecord(
                worker_id=worker_id,
                key=secrets.token_hex(32),
                url=url,
                credits=initial_credits,
                hardware_uuid=hardware_uuid,
                public_ip=public_ip,
                hardware_spec=eff_spec,
                referred_by=ref_wid,
                brain_shard=shard_info["primary_shard"],
                replica_shards=shard_info["replica_shards"],
                protocol_version=version or "2026.5.0",
                quantum_address=quantum_address,
                quantum_vault_pub=quantum_vault_pub or {},
                puf_seal=puf_seal,
            )
            self._workers[worker_id] = rec
            if referrer and ref_wid:
                referrer.referrals_count += 1
            self._flush()
            self.ledger.append("worker_registered", {
                "worker_id": worker_id,
                "url": url,
                "credits": initial_credits,
                "hardware_uuid": hardware_uuid,
                "hardware_spec": rec.hardware_spec,
                "brain_shard": rec.brain_shard,
                "referred_by": ref_wid,
                "quantum_address": rec.quantum_address,
                "crypto_security_level": rec.crypto_security_level,
                "puf_seal_active": bool(rec.puf_seal),
            })
            return rec

    def get_worker_by_key(self, secret_key: str) -> Optional[WorkerNodeRecord]:
        if not secret_key:
            return None
        with self._lock:
            for w in self._workers.values():
                if w.key and hmac.compare_digest(w.key, secret_key):
                    return w
            return None

    def is_public_worker_id(self, candidate: str) -> bool:
        with self._lock:
            w = self._workers.get(candidate)
            return bool(w and w.key != candidate)

    def authenticate_worker_key(self, secret_key: str) -> WorkerNodeRecord:
        """Strictly authenticates a worker by private 64-char secret key, rejecting public worker_ids (C3 Fix)."""
        cand = (secret_key or "").strip()
        if not cand:
            raise PermissionError("Authentication Error (C3): Secret Account Key is required")
        with self._lock:
            if self.is_public_worker_id(cand):
                raise PermissionError(
                    f"Security Error (C3): Public Worker ID {cand!r} cannot be used as an authentication key. "
                    "Use your private 64-character Secret Account Key."
                )
            w = self.get_worker_by_key(cand)
            if not w:
                raise PermissionError("Authentication Error (C3/N3): Invalid or unregistered Secret Account Key")
            if w.status == "SLASHED":
                raise PermissionError(f"Worker {w.worker_id!r} is SLASHED and blacklisted")
            return w

    def get_worker(self, worker_id: str) -> Optional[WorkerNodeRecord]:
        """Strictly looks up a worker by public worker_id only (R3 Fix: never conflates worker_id with secret_key)."""
        with self._lock:
            return self._workers.get(worker_id)

    def _resolve_worker_or_key(self, identifier: str) -> Optional[WorkerNodeRecord]:
        with self._lock:
            return self._workers.get(identifier) or self.get_worker_by_key(identifier)

    def worker_key(self, worker_id: str) -> str:
        rec = self.get_worker(worker_id)
        if not rec:
            raise KeyError(f"Unknown worker {worker_id!r}")
        return rec.key

    def list_workers(self) -> List[dict]:
        with self._lock:
            return [w.to_dict() for w in self._workers.values()]

    # -- Rule 5: Dynamic Bitcoin-Style Halving based on Active Network Workers
    def halving_epoch_info(self) -> dict:
        with self._lock:
            active_workers = sum(1 for w in self._workers.values() if w.status == "ACTIVE")
            if active_workers <= 50:
                era = 1
                label = "Era 1: Genesis Growth (1-50 Workers)"
                multiplier = 1.0
                uptime_interval_s = 1800.0  # 30 mins -> 2 cr/hr (4 cr/hr on 16+ cores)
                next_halving_at = 51
            elif active_workers <= 500:
                era = 2
                label = "Era 2: First Halving 50% (51-500 Workers)"
                multiplier = 0.5
                uptime_interval_s = 3600.0  # 60 mins -> 1 cr/hr (2 cr/hr on 16+ cores)
                next_halving_at = 501
            else:
                era = 3
                label = "Era 3: Sovereign Scarcity 75% Halving (500+ Workers)"
                multiplier = 0.25
                uptime_interval_s = 7200.0  # 120 mins -> 0.5 cr/hr (1 cr/hr on 16+ cores)
                next_halving_at = 5000
            effective_task_reward = max(1, int(self.reward_per_task * multiplier))
            idle_rate_standard = round((3600.0 / uptime_interval_s) * 1.0, 2)
            idle_rate_heavy = round((3600.0 / uptime_interval_s) * 2.0, 2)
            return {
                "era": era,
                "label": label,
                "active_workers": active_workers,
                "multiplier": multiplier,
                "uptime_interval_seconds": uptime_interval_s,
                "idle_credits_per_hour_standard": idle_rate_standard,
                "idle_credits_per_hour_heavy_16c": idle_rate_heavy,
                "idle_credits_per_hour_high_core": idle_rate_heavy,
                "active_task_reward_credits": effective_task_reward,
                "next_halving_at_workers": next_halving_at,
            }

    # -- Rule 1 + Anti-Fake-Uptime Micro-PoW: Slow Idle Uptime Mining (2-4 Credits/Hour)
    def record_heartbeat(self, worker_id: str, cores: int = 4, pow_nonce: Optional[str] = None,
                         hardware_spec: str = "", synced_deltas_count: Optional[int] = None) -> Optional[WorkerNodeRecord]:
        """Awards slow idle uptime credits after verifying optional Micro-PoW challenge."""
        from .brain_matrix import assign_worker_brain_shard

        with self._lock:
            rec = self.get_worker(worker_id)
            if not rec or rec.status == "SLASHED":
                return rec
            if hardware_spec and hardware_spec.strip():
                rec.hardware_spec = hardware_spec.strip()
            if synced_deltas_count is not None:
                try:
                    sdc = int(synced_deltas_count)
                    if sdc > rec.synced_deltas_count:
                        rec.synced_deltas_count = sdc
                except (ValueError, TypeError):
                    pass
            sh = assign_worker_brain_shard(int(cores or 4), rec.hardware_spec, rec.worker_id)
            rec.brain_shard = sh["primary_shard"]
            rec.replica_shards = sh["replica_shards"]
            if pow_nonce is not None:
                if not verify_pow_solution(rec.worker_id, rec.pow_challenge, str(pow_nonce)):
                    rec.rejected_packets += 1
                    self._flush()
                    self.ledger.append("heartbeat_pow_rejected", {
                        "worker_id": rec.worker_id,
                        "supplied_nonce": str(pow_nonce)[:32],
                    })
                    raise PermissionError(
                        "Anti-Fake-Uptime PoW Guard: Invalid Micro-PoW solution for heartbeat ping. "
                        "Fake ping scripts without real CPU hash computation are rejected."
                    )
                rec.pow_verified_count += 1
                rec.pow_challenge = secrets.token_hex(8)
            hinfo = self.halving_epoch_info()
            interval_s = hinfo["uptime_interval_seconds"]  # 1800s (30 mins) in Era 1
            now = time.time()
            last_ts = getattr(rec, "last_reward_time", None) or rec.last_heartbeat_reward_at or rec.registered_at or now
            elapsed = now - last_ts
            if elapsed >= interval_s:
                # Cap intervals per single heartbeat ping to prevent offline clock-jump farming (N4 Fix)
                intervals = min(2, max(1, int(elapsed // interval_s)))
                capped_cores = min(64, max(1, int(cores or 4)))
                hw_multiplier = 2 if capped_cores >= 16 else 1
                earned = intervals * hw_multiplier
                rec.credits += earned
                rec.uptime_minutes_verified += int((intervals * interval_s) // 60)
                rec.last_heartbeat_reward_at = now
                if hasattr(rec, "last_reward_time"):
                    rec.last_reward_time = now
                self._award_referral_bonus(rec, earned, source="uptime_heartbeat")
                self._flush()
            elif pow_nonce is not None:
                self._flush()
            return rec

    # -- Rule 4 + Gamified "Uptime Flex" Hardware Leaderboard
    def get_top_miners_leaderboard(self, limit: int = 10) -> dict:
        with self._lock:
            candidates = [
                w for w in self._workers.values()
                if w.status == "ACTIVE" and w.worker_id != "owner-master"
            ]
            ranked = sorted(
                candidates,
                key=lambda w: (w.tasks_verified * 100 + w.tasks_completed * 50 + w.uptime_minutes_verified * 2 + w.credits),
                reverse=True,
            )[:limit]
            board = []
            for idx, w in enumerate(ranked):
                score = (w.tasks_verified * 100) + (w.tasks_completed * 50) + (w.uptime_minutes_verified * 2) + w.credits
                badge = "🥇" if idx == 0 else ("🥈" if idx == 1 else ("🥉" if idx == 2 else ""))
                uptime_hrs = round(w.uptime_minutes_verified / 60.0, 2)
                rig = w.hardware_spec or "Standard Multi-Core Rig"
                flex_text = (
                    f"⚡ My Rig ({rig}) is Ranked #{idx + 1} on SUP Agentic Mesh (Powered by NEXUS)! "
                    f"Brain Shard: {w.brain_shard} | Verified Tasks: {w.tasks_verified} | Uptime: {uptime_hrs}h | "
                    f"Credits: {w.credits} | Join with Referral Code '{w.referral_code}' (+5% Bonus)!"
                )
                board.append({
                    "rank": idx + 1,
                    "badge": badge,
                    "worker_id": w.worker_id,
                    "hardware_spec": rig,
                    "brain_shard": w.brain_shard,
                    "replica_shards": list(w.replica_shards),
                    "synced_deltas_count": w.synced_deltas_count,
                    "credits": w.credits,
                    "tasks_completed": w.tasks_completed,
                    "tasks_verified": w.tasks_verified,
                    "uptime_minutes": w.uptime_minutes_verified,
                    "uptime_minutes_verified": w.uptime_minutes_verified,
                    "uptime_hours": uptime_hrs,
                    "pow_verified_count": w.pow_verified_count,
                    "referral_code": w.referral_code,
                    "referrals_count": w.referrals_count,
                    "referral_bonus_credits": w.referral_bonus_credits,
                    "flex_share_text": flex_text,
                    "score": score,
                    "competition_score": score,
                    "weekly_buyback_eligible": idx < 3,
                    "eligible_for_sunday_buyback": idx < 3,
                    "payout_address": w.payout_address or "(not set)",
                    "pending_payout_usd": w.pending_payout,
                })
            return {
                "halving": self.halving_epoch_info(),
                "top_miners": board,
                "leaderboard": board,
                "sunday_buyback_pool": {
                    "official_floor_rate_pkr": 500,
                    "top_winners_count": 3,
                },
                "weekly_pool_policy": "Every Sunday, Top 3 Active Miners by Uptime & Verified Tasks qualify for Official Owner Floor Buyback.",
            }

    def execute_weekly_top3_buyback(self, reward_pkr_each: float = 500.0, credits_bought_each: int = 100) -> dict:
        """Owner-exclusive Weekly Top 3 Miners Buyback settlement."""
        with self._lock:
            lb = self.get_top_miners_leaderboard(limit=3)["top_miners"]
            winners = []
            for entry in lb:
                w = self._workers.get(entry["worker_id"])
                if not w or w.credits <= 0:
                    continue
                deducted = min(w.credits, max(1, int(credits_bought_each)))
                w.credits -= deducted
                usd_equiv = round(float(reward_pkr_each) / 280.0, 2)
                w.pending_payout = round(w.pending_payout + usd_equiv, 2)
                w.total_payout_earned = round(w.total_payout_earned + usd_equiv, 2)
                winners.append({
                    "rank": entry["rank"],
                    "worker_id": w.worker_id,
                    "credits_bought_by_owner": deducted,
                    "credits_bought_back": deducted,
                    "remaining_credits": w.credits,
                    "reward_pkr": reward_pkr_each,
                    "reward_usd_credited": usd_equiv,
                    "reward_usd_equivalent": usd_equiv,
                    "payout_address": w.payout_address or "(not set)",
                })
            self._flush()
            total_pkr = round(len(winners) * reward_pkr_each, 2)
            total_cr = sum(w["credits_bought_back"] for w in winners)
            block = self.ledger.append("weekly_top3_buyback_settled", {
                "winners_count": len(winners),
                "reward_pkr_each": reward_pkr_each,
                "total_pkr_paid": total_pkr,
                "total_credits_bought_back": total_cr,
                "winners": winners,
            })
            return {
                "ok": True,
                "status": "WEEKLY_BUYBACK_SETTLED",
                "winners": winners,
                "total_pkr_allocated": total_pkr,
                "total_pkr_paid": total_pkr,
                "total_credits_bought_back": total_cr,
                "ledger_block": block["hash"][:16],
            }

    # -- tasks & NAT-Traversal Outbound Pull Queue
    def create_signed_task(
        self,
        worker_id: str,
        feature_key: str,
        payload: dict,
        funded_by: str = "",
        funded_credits: Optional[int] = None,
    ) -> dict:
        with self._lock:
            if worker_id in {"auto", "random", "any"}:
                eligible = [w for w in self._workers.values() if w.status == "ACTIVE" and w.worker_id != funded_by]
                if not eligible:
                    raise ValueError("No active workers available to assign task")
                worker = min(eligible, key=lambda w: len(self._nat_outbound_queue.get(w.worker_id, [])))
            else:
                worker = self.get_worker(worker_id)
            if not worker:
                raise KeyError(f"Unknown worker node {worker_id!r}")
            if worker.status == "SLASHED":
                raise PermissionError(f"Worker {worker.worker_id!r} is SLASHED and blocked")
            if feature_key in HUB_ONLY_FEATURES:
                raise PermissionError(f"Feature {feature_key!r} is a Hub-only power and cannot be delegated")

            escrow_credits: Optional[int] = funded_credits
            funder_id = (funded_by or "").strip()
            if funder_id and funder_id not in {"owner_hub", "hub_internal"}:
                funder = self._resolve_worker_or_key(funder_id)
                if not funder:
                    raise PermissionError(f"Unknown funder account {funder_id!r} for task escrow")
                if funder.worker_id == worker.worker_id or (
                    funder.hardware_uuid and worker.hardware_uuid and funder.hardware_uuid == worker.hardware_uuid
                ):
                    raise PermissionError("Self-dealing blocked: Worker cannot fund or enqueue tasks for itself")
                req_amt = int(escrow_credits) if escrow_credits is not None else self.halving_epoch_info()["active_task_reward_credits"]
                spend_res = self.spend_credits(funder.worker_id, req_amt, reason=f"task_escrow:{feature_key}:{worker.worker_id}")
                if spend_res.get("status") != "SPENT":
                    raise PermissionError(spend_res.get("error") or "Insufficient credits to fund task escrow")
                escrow_credits = req_amt
                funder_id = funder.worker_id

            envelope = {"task_id": secrets.token_hex(8), "worker_id": worker.worker_id, "feature": feature_key,
                        "payload": payload, "issued_at": time.time(), "nonce": secrets.token_hex(8)}
            packet = {**envelope, "hub_signature": compute_hmac(worker.key, envelope)}
            stored_task = dict(packet)
            if funder_id:
                stored_task["funded_by"] = funder_id
            if escrow_credits is not None:
                stored_task["funded_credits"] = int(escrow_credits)
            self._pending[envelope["task_id"]] = stored_task
            return stored_task

    def enqueue_nat_task(
        self,
        worker_id: str,
        feature_key: str,
        payload: dict,
        funded_by: str = "",
        funded_credits: Optional[int] = None,
    ) -> dict:
        """Queues a signed task for a worker behind NAT/Firewall/CGNAT to pull via outbound polling."""
        with self._lock:
            packet = self.create_signed_task(
                worker_id,
                feature_key,
                payload,
                funded_by=funded_by,
                funded_credits=funded_credits,
            )
            w_id = packet["worker_id"]
            queue = self._nat_outbound_queue.setdefault(w_id, [])
            queue.append(packet)
            self._nat_task_events[packet["task_id"]] = threading.Event()
            return packet

    def pull_pending_tasks(
        self,
        worker_id: str,
        max_tasks: int = 5,
        visibility_timeout_s: float = 90.0,
    ) -> List[dict]:
        """Called by edge workers behind NAT/Firewall to pull their signed compute/LoRA tasks.
        Includes visibility timeout recovery so unacknowledged/lost tasks return to queue.
        """
        with self._lock:
            # Wire up: Prune expired tasks and refund escrow on pull
            self.prune_expired_tasks()

            worker = self.get_worker(worker_id)
            if not worker or worker.status == "SLASHED":
                return []
            w_id = worker.worker_id
            now = time.time()

            # 1. Recover any in-flight tasks whose visibility timeout expired without settlement
            requeued = []
            for tid, flight in list(self._nat_in_flight.items()):
                if flight.get("worker_id") == w_id:
                    if (now - float(flight.get("pulled_at", 0.0))) > float(flight.get("timeout_s", visibility_timeout_s)):
                        requeued.append(flight["packet"])
                        self._nat_in_flight.pop(tid, None)

            queue = self._nat_outbound_queue.setdefault(w_id, [])
            if requeued:
                queue[0:0] = requeued

            # 2. Canary Injection: Inject an unannounced procedural canary only when enabled or forced,
            # rate-limited to avoid predictable idle-triggering, and never displacing queued user tasks
            canary_interval_ok = (now - getattr(self, "_worker_last_canary", {}).get(w_id, 0.0)) >= 60.0
            inject_canary = worker.status == "ACTIVE" and (
                getattr(self, "force_canary_injection", False)
                or (
                    getattr(self, "enable_canary_injection", False)
                    and canary_interval_ok
                    and len(queue) == 0
                    and secrets.randbelow(100) < int(getattr(self, "canary_injection_rate_pct", 5))
                )
            )
            if inject_canary:
                try:
                    canary_pkt = self.create_golden_canary_task(w_id)
                    queue.append(canary_pkt)
                    if hasattr(self, "_worker_last_canary"):
                        self._worker_last_canary[w_id] = now
                except Exception:
                    pass

            if not queue:
                return []
            valid = [pkt for pkt in queue if (now - pkt.get("issued_at", now)) <= TASK_TTL_S]
            pulled = valid[:max(1, int(max_tasks or 5))]
            self._nat_outbound_queue[w_id] = valid[len(pulled):]
            sanitized_pulled = []
            for pkt in pulled:
                self._nat_in_flight[pkt["task_id"]] = {
                    "packet": pkt,
                    "worker_id": w_id,
                    "pulled_at": now,
                    "timeout_s": float(visibility_timeout_s),
                }
                # Disguise canary metadata and strip hidden assertions from worker's packet
                w_pkt = dict(pkt)
                w_pkt.pop("is_canary", None)
                w_pkt.pop("canary_spec", None)
                if w_pkt.get("funded_by") in {"hub_internal", "owner_hub"}:
                    peer_workers = [wid for wid in self._workers.keys() if wid != w_id and self._workers[wid].status == "ACTIVE"]
                    if peer_workers and secrets.randbelow(10) < 6:
                        w_pkt["funded_by"] = secrets.choice(peer_workers)
                    elif secrets.randbelow(10) < 5:
                        w_pkt["funded_by"] = f"worker-{secrets.token_hex(6)}"
                    else:
                        w_pkt.pop("funded_by", None)
                if isinstance(w_pkt.get("payload"), dict):
                    w_payload = dict(w_pkt["payload"])
                    for hidden_key in ("hidden_assertions", "hidden_test_assertions", "hidden_tests"):
                        w_payload.pop(hidden_key, None)
                    w_pkt["payload"] = w_payload
                sanitized_pulled.append(w_pkt)
            return sanitized_pulled

    def refund_task_escrow(self, task: Optional[dict], reason: str = "escrow_refund") -> bool:
        """Atomically returns unspent task escrow credits back to the task funder."""
        if not isinstance(task, dict):
            return False
        funder_id = str(task.get("funded_by") or "").strip()
        amt = int(task.get("funded_credits") or 0)
        if not funder_id or amt <= 0 or funder_id in {"owner_hub", "hub_internal"}:
            return False
        with self._lock:
            if task.get("escrow_refunded"):
                return False
            task["escrow_refunded"] = True
            task["funded_credits"] = 0
            funder = self._resolve_worker_or_key(funder_id)
            if not funder:
                return False
            prev_bal = funder.credits
            new_bal = prev_bal + amt
            if self.ledger:
                self.ledger.append("escrow_refunded", {
                    "worker_id": funder.worker_id,
                    "amount": amt,
                    "task_id": task.get("task_id", ""),
                    "reason": reason,
                    "previous_balance": prev_bal,
                    "new_balance": new_bal,
                })
            funder.credits = new_bal
            self._flush()
            return True

    def prune_expired_tasks(self) -> dict:
        """Prunes expired pending, in-flight, and consensus tasks, refunding escrow back to requesters."""
        with self._lock:
            self._prune_consensus_buffer()
            now = time.time()
            refunded_count = 0
            refunded_credits = 0

            expired_pending = [
                tid for tid, t in self._pending.items()
                if (now - float(t.get("issued_at", now))) > TASK_TTL_S
            ]
            for tid in expired_pending:
                t = self._pending.pop(tid, None)
                if t:
                    amt = int(t.get("funded_credits") or 0)
                    if self.refund_task_escrow(t, reason=f"task_ttl_expired:{tid}"):
                        refunded_count += 1
                        refunded_credits += amt
                    if tid in self._nat_task_events:
                        self._nat_task_events[tid].set()

            return {
                "ok": True,
                "refunded_count": refunded_count,
                "refunded_credits": refunded_credits,
                "active_pending": len(self._pending),
                "active_consensus": len(self._freeform_consensus),
            }

    def record_trusted_replay_task(self, prompt: str, trusted_output: str, feature: str = "brain_inference") -> None:
        """Stores a confirmed clean multi-worker task in the replay pool for organic canary spot-checks."""
        if not prompt or not trusted_output or len(prompt) < 10 or len(trusted_output) < 20:
            return
        with self._lock:
            for item in self._replay_canary_pool:
                if item.get("prompt") == prompt:
                    return
            entry = {
                "id": f"replay-{hashlib.sha256(prompt.encode('utf-8')).hexdigest()[:10]}",
                "feature": feature,
                "prompt": prompt,
                "trusted_output": trusted_output,
                "is_replay": True,
            }
            self._replay_canary_pool.append(entry)
            if len(self._replay_canary_pool) > 100:
                self._replay_canary_pool.pop(0)

    def create_golden_canary_task(self, worker_id: str, canary_idx: Optional[int] = None) -> dict:
        """Injects an unannounced ground-truth canary task to spot-check worker honesty.
        Procedurally generates unique challenges disguised identically to real requester tasks.
        """
        with self._lock:
            worker = self.get_worker(worker_id)
            if not worker:
                raise KeyError(f"Unknown worker {worker_id!r}")
            if canary_idx is not None and canary_idx < len(GOLDEN_CANARIES):
                canary = GOLDEN_CANARIES[canary_idx]
            elif self._replay_canary_pool and secrets.randbelow(10) < 5:
                canary = secrets.choice(self._replay_canary_pool)
            else:
                canary = generate_procedural_canary(seed=canary_idx)
            payload = {"prompt": canary["prompt"]}
            if "test_assertions" in canary:
                payload["test_assertions"] = canary["test_assertions"]

            task = self.create_signed_task(
                worker_id,
                canary.get("feature", "brain_inference"),
                payload,
                funded_by="hub_internal",
                funded_credits=self.halving_epoch_info()["active_task_reward_credits"],
            )
            task_rec = self._pending.get(task["task_id"])
            if task_rec:
                task_rec["is_canary"] = True
                task_rec["canary_spec"] = canary
            # Worker-facing view is disguised realistically: mimics authentic worker-funded or owner task
            peer_workers = [wid for wid in self._workers.keys() if wid != worker_id and self._workers[wid].status == "ACTIVE"]
            if peer_workers and secrets.randbelow(10) < 6:
                task["funded_by"] = secrets.choice(peer_workers)
            elif secrets.randbelow(10) < 5:
                task["funded_by"] = f"worker-{secrets.token_hex(6)}"
            else:
                task.pop("funded_by", None)
            # Jitter issued_at so it doesn't match now exactly (avoids immediate-injection signature)
            jittered_now = time.time() - float(secrets.randbelow(20) + 3)
            task["issued_at"] = jittered_now
            if task_rec:
                task_rec["issued_at"] = jittered_now
            worker_task = dict(task)
            worker_task.pop("is_canary", None)
            worker_task.pop("canary_spec", None)
            return worker_task

    def dispatch_consensus_task(
        self,
        feature_key: str,
        payload: dict,
        funded_by: str = "",
        funded_credits: Optional[int] = None,
    ) -> Tuple[dict, dict]:
        """Hub autonomously selects two random, independent workers on different subnets
        to execute a dual-worker consensus task. Prevents workers from self-selecting tasks or colluding.
        """
        with self._lock:
            eligible = [
                w for w in self._workers.values()
                if w.status == "ACTIVE" and w.worker_id != funded_by
            ]
            if len(eligible) < 2:
                raise ValueError("Insufficient active workers to dispatch consensus pair (at least 2 required)")

            shuffled = list(eligible)
            secrets.SystemRandom().shuffle(shuffled)

            w1 = None
            w2 = None
            for cand1 in shuffled:
                for cand2 in shuffled:
                    if cand1.worker_id != cand2.worker_id and _is_independent_peer(cand1, cand2):
                        w1 = cand1
                        w2 = cand2
                        break
                if w1 and w2:
                    break

            if not w1 or not w2:
                raise PermissionError("No two independent workers on distinct subnets available for consensus task")

            consensus_id = str(payload.get("consensus_id") or secrets.token_hex(8))
            p1 = dict(payload)
            p1["consensus_id"] = consensus_id
            p2 = dict(payload)
            p2["consensus_id"] = consensus_id

            t1 = self.enqueue_nat_task(w1.worker_id, feature_key, p1, funded_by=funded_by, funded_credits=funded_credits)
            t2 = self.enqueue_nat_task(w2.worker_id, feature_key, p2, funded_by=funded_by, funded_credits=funded_credits)
            return t1, t2

    def _prune_consensus_buffer(self) -> None:
        """Removes expired entries from the freeform consensus buffer (TTL = 300s) and refunds escrow."""
        now = time.time()
        with self._lock:
            expired = [k for k, v in self._freeform_consensus.items() if (now - float(v.get("created_at", now))) > CONSENSUS_BUFFER_TTL]
            for k in expired:
                entry = self._freeform_consensus.pop(k, None)
                if entry and isinstance(entry.get("task"), dict):
                    self.refund_task_escrow(entry["task"], reason=f"consensus_buffer_ttl_expired:{entry.get('task_id')}")
                    tid = entry.get("task_id")
                    if tid in self._nat_task_events:
                        self._nat_task_events[tid].set()

    def _reject(self, worker: Optional[WorkerNodeRecord], reason: str, task: Optional[dict] = None) -> dict:
        if worker:
            worker.rejected_packets += 1
            self._flush()
        if task and isinstance(task, dict):
            self.refund_task_escrow(task, reason=f"task_rejected:{reason}")
            tid = task.get("task_id")
            if tid in self._nat_task_events:
                self._nat_task_events[tid].set()
        return {"ok": False, "status": "REJECTED", "reason": reason,
                "note": "Unattributable failures are rejected, never slashed."}

    def verify_and_settle(self, response: dict) -> dict:
        task_id = str(response.get("task_id", ""))
        worker_id = str(response.get("worker_id", ""))
        result = response.get("result")
        with self._lock:
            worker = self._workers.get(worker_id)
            if not worker:
                return self._reject(None, "unknown_worker")
            if worker.status == "SLASHED":
                return {"status": "BLOCKED", "reason": "worker_already_slashed"}
            task = self._pending.get(task_id)
            if not task or task["worker_id"] != worker_id:
                return self._reject(worker, "unknown_replayed_or_mismatched_task")
            if time.time() - task["issued_at"] > TASK_TTL_S:
                self._pending.pop(task_id, None)
                return self._reject(worker, "task_expired", task=task)
            proof_body = {"task_id": task_id, "worker_id": worker_id, "feature": task["feature"],
                          "nonce": task["nonce"], "result": result}
            raw_proof = response.get("worker_proof") or response.get("worker_proof_bundle")
            is_valid_sig = False
            quantum_verified = False

            # 1. Check if worker provided a 4096-bit Hyper-Sovereign Multi-Vault Quantum Proof
            if isinstance(raw_proof, dict) and raw_proof.get("version") == "HSQK-4096-v1":
                from .quantum_crypto import verify_hyper_proof
                pub_bundle = worker.quantum_vault_pub or {
                    "quantum_address": worker.quantum_address,
                    "puf_seal": worker.puf_seal,
                    "ratchet_step": worker.ratchet_step,
                }
                ok_q, reason_q = verify_hyper_proof(pub_bundle, proof_body, raw_proof, nonce=task["nonce"])
                if ok_q:
                    is_valid_sig = True
                    quantum_verified = True
                    worker.ratchet_step = int(raw_proof.get("ratchet_step", worker.ratchet_step + 1))
                else:
                    return self._reject(worker, f"quantum_proof_rejected: {reason_q}", task=task)
            else:
                # 2. Classical HMAC-SHA256 signature (backward-compatible fallback)
                is_valid_sig = hmac.compare_digest(str(raw_proof or ""), compute_hmac(worker.key, proof_body))

            if not is_valid_sig:
                return self._reject(worker, "invalid_proof_signature")
            if response.get("verified") is False or (isinstance(result, dict) and result.get("verified") is False):
                return self._reject(worker, "unverified_task_result_rejected", task=task)
            if not isinstance(result, dict) or not result or result.get("status") == "ERROR":
                return self._reject(worker, "empty_or_failed_task_result", task=task)
            self._pending.pop(task_id, None)  # proof is authentic -> task consumed (replay-safe)
            self._nat_in_flight.pop(task_id, None)

        verified = False
        clean_res, res_flags = sanitize_payload(result)
        if "prompt_injection_suspected" in res_flags:
            return self._reject(worker, "tainted_or_injected_worker_output", task=task)

        # Golden Canary Task Spot-Check Verification
        if task.get("is_canary"):
            canary = task.get("canary_spec") or {}
            out_str = str(
                result.get("output")
                or result.get("code")
                or result.get("response")
                or result.get("text")
                or ""
            ).strip()
            passed = False
            if canary.get("is_replay") and canary.get("trusted_output"):
                t_out = str(canary["trusted_output"])
                p_stems = extract_prompt_stems(canary.get("prompt", ""))
                coh, _ = check_prose_coherence(out_str)
                vague, _ = is_vague_non_answer(out_str)
                contra, _ = detect_contradiction(out_str, t_out)
                s1 = set(extract_novel_stems(out_str, p_stems))
                s2 = set(extract_novel_stems(t_out, p_stems))
                shared = s1 & s2
                passed = coh and not vague and not contra and len(shared) >= 2
            elif canary.get("verifier") and callable(canary["verifier"]):
                try:
                    passed = bool(canary["verifier"](out_str))
                except Exception:
                    passed = False
            elif canary.get("test_assertions"):
                from .continuous_learning import ObjectiveGroundTruthVerifier
                v_res = ObjectiveGroundTruthVerifier.verify_code(out_str, canary["test_assertions"], timeout=2.0)
                passed = bool(v_res.get("verified"))
            elif canary.get("expected"):
                exp = str(canary["expected"]).strip()
                if exp.isdigit():
                    found_nums = re.findall(r"\b\d+\b", out_str)
                    passed = exp in found_nums
                else:
                    pattern = r"(?i)\b" + re.escape(exp) + r"\b"
                    passed = bool(re.search(pattern, out_str))

            if passed:
                task["funded_credits"] = self.halving_epoch_info()["active_task_reward_credits"]
                verified = True
            else:
                # Canary failed! Graduated penalty system (Warning -> 20% burn -> Slashed)
                worker.canary_strikes = getattr(worker, "canary_strikes", 0) + 1
                strike = worker.canary_strikes
                cid = canary.get("id", "canary_unknown")
                if strike == 1:
                    log_entry = {
                        "worker_id": worker.worker_id,
                        "task_id": task_id,
                        "strike": 1,
                        "reason": f"First failure on ground-truth canary {cid}",
                        "action": "warning_recorded",
                        "timestamp": time.time(),
                    }
                    self.appeal_log.append(log_entry)
                    if self.ledger:
                        self.ledger.append("canary_strike_warning", log_entry)
                    self._flush()
                    return self._reject(worker, "canary_strike_1_warning: incorrect ground-truth result on canary (first warning, 0 penalty)", task=task)
                elif strike == 2:
                    burn_amt = int(worker.credits * 0.20)
                    worker.credits -= burn_amt
                    worker.burned_credits += burn_amt
                    log_entry = {
                        "worker_id": worker.worker_id,
                        "task_id": task_id,
                        "strike": 2,
                        "burned_credits": burn_amt,
                        "new_balance": worker.credits,
                        "reason": f"Second failure on ground-truth canary {cid}",
                        "action": "20_percent_burn",
                        "timestamp": time.time(),
                    }
                    self.appeal_log.append(log_entry)
                    if self.ledger:
                        self.ledger.append("canary_strike_penalty", log_entry)
                    self._flush()
                    return self._reject(worker, f"canary_strike_2_penalty: repeated failure on ground-truth canary (-{burn_amt} credits burned)", task=task)
                else:
                    log_entry = {
                        "worker_id": worker.worker_id,
                        "task_id": task_id,
                        "strike": 3,
                        "reason": f"Three consecutive ground-truth failures ({cid})",
                        "action": "full_slashing",
                        "timestamp": time.time(),
                    }
                    self.appeal_log.append(log_entry)
                    with self._lock:
                        slash_res = self._slash(worker, f"canary_strike_3_slash: 3 ground-truth canary failures ({cid})")
                        return {
                            "ok": False,
                            "status": "SLASHED",
                            "reason": "golden_canary_strike_3_slashed",
                            "burned_credits": slash_res.get("burned_credits", 0),
                            "worker_id": worker.worker_id,
                        }

        if self.grid is not None and _spot_checkable(task["feature"], task["payload"]) \
                and secrets.randbelow(10_000) < int(self.spot_check_rate * 10_000):
            try:
                expected = self.grid.registry.get(task["feature"]).handler(self.grid, sanitize_payload(task["payload"])[0])
                if _canonical(_comparable(expected)) != _canonical(_comparable(result)):
                    with self._lock:
                        return self._slash(worker, f"spot_check_mismatch on {task['feature']} (task {task_id})")
                verified = True
            except Exception as exc:
                return self._reject(worker, f"spot_check_handler_error: {exc}")
        elif task["feature"] in SPOT_CHECKABLE:
            # Standalone Hub verification of deterministic features (rejects fabricated answers)
            t_payload = task.get("payload") if isinstance(task.get("payload"), dict) else {}
            if task["feature"] == "data_analysis":
                raw_nums = t_payload.get("series") or t_payload.get("data") or t_payload.get("numbers")
                nums = []
                if isinstance(raw_nums, (list, tuple)):
                    nums = [float(x) for x in raw_nums if isinstance(x, (int, float)) and not isinstance(x, bool)]
                elif isinstance(raw_nums, str):
                    nums = [float(x) for x in re.findall(r"[-+]?(?:\d*\.\d+|\d+)", raw_nums)]
                if nums and isinstance(result.get("mean"), (int, float)) and not isinstance(result.get("mean"), bool):
                    expected_mean = sum(nums) / len(nums)
                    if abs(float(result["mean"]) - expected_mean) <= 0.05:
                        if "count" in result and int(result["count"]) != len(nums):
                            verified = False
                        elif "sum" in result and abs(float(result["sum"]) - sum(nums)) > 0.05:
                            verified = False
                        else:
                            verified = True
            elif task["feature"] == "trend_forecasting":
                raw_vals = t_payload.get("series") or t_payload.get("data") or t_payload.get("values")
                xs = []
                if isinstance(raw_vals, (list, tuple)):
                    xs = [float(x) for x in raw_vals if isinstance(x, (int, float)) and not isinstance(x, bool)]
                elif isinstance(raw_vals, str):
                    xs = [float(x) for x in re.findall(r"[-+]?(?:\d*\.\d+|\d+)", raw_vals)]
                if len(xs) >= 2:
                    n = len(xs)
                    t = list(range(n))
                    t_mean = sum(t) / n
                    x_mean = sum(xs) / n
                    denom = sum((ti - t_mean) ** 2 for ti in t)
                    expected_slope = sum((ti - t_mean) * (xi - x_mean) for ti, xi in zip(t, xs)) / (denom if denom != 0 else 1)
                    expected_direction = "UPWARD" if expected_slope > 0.01 else ("DOWNWARD" if expected_slope < -0.01 else "FLAT")
                    res_trend = str(result.get("trend") or "").upper()
                    if res_trend == "UP":
                        res_trend = "UPWARD"
                    elif res_trend == "DOWN":
                        res_trend = "DOWNWARD"
                    if res_trend == expected_direction:
                        if "slope" in result and isinstance(result["slope"], (int, float)) and not isinstance(result["slope"], bool):
                            if abs(float(result["slope"]) - expected_slope) <= 0.05:
                                verified = True
                        else:
                            verified = True

        # Objective Ground Truth Verifier for LLM Tasks (Code assertions, Math logic, Schema contracts)
        if not verified and task["feature"] in {"brain_inference", "model_query", "neural_shard_compute", "code_review"}:
            t_payload = task.get("payload") if isinstance(task.get("payload"), dict) else {}
            out_text = str(
                result.get("output")
                or result.get("code")
                or result.get("response")
                or result.get("local_ollama_output")
                or result.get("text")
                or ""
            ).strip()

            test_assertions = str(t_payload.get("test_assertions") or "")
            hidden_assertions = str(t_payload.get("hidden_assertions") or t_payload.get("hidden_test_assertions") or t_payload.get("hidden_tests") or "")
            combined_assertions = f"{test_assertions}\n{hidden_assertions}".strip()

            if combined_assertions:
                from .continuous_learning import ObjectiveGroundTruthVerifier
                v_res = ObjectiveGroundTruthVerifier.verify_code(out_text, combined_assertions, timeout=2.0)
                if v_res.get("verified"):
                    verified = True
                else:
                    return self._reject(worker, f"code_assertions_failed: {v_res.get('error')}", task=task)
            elif t_payload.get("expected_value") is not None:
                from .continuous_learning import ObjectiveGroundTruthVerifier
                v_res = ObjectiveGroundTruthVerifier.verify_math(out_text, expected_val=t_payload["expected_value"])
                if v_res.get("verified"):
                    verified = True
                else:
                    return self._reject(worker, f"math_verification_failed: {v_res.get('error')}", task=task)
            elif t_payload.get("required_keys"):
                from .continuous_learning import ObjectiveGroundTruthVerifier
                v_res = ObjectiveGroundTruthVerifier.verify_json_schema(
                    out_text,
                    t_payload["required_keys"],
                    rules=t_payload.get("schema_rules") or t_payload.get("rules"),
                )
                if v_res.get("verified"):
                    verified = True
                else:
                    return self._reject(worker, f"schema_verification_failed: {v_res.get('error')}", task=task)
            elif (t_payload.get("prompt") or t_payload.get("query")) and out_text:
                # Darja 2: Free-form Redundant Multi-Worker Consensus Verification
                self._prune_consensus_buffer()
                prompt_str = str(t_payload.get("prompt") or t_payload.get("query") or "").strip()
                out_tokens = extract_content_tokens(out_text)
                if len(out_tokens) < 1 or (len(out_text.split()) >= 5 and len(out_tokens) < 2):
                    return self._reject(worker, "low_content_entropy_rejected (response lacks substantive content words)", task=task)

                # Prose Coherence Guard: Check function words & prose syntax (kills keyword salads & gibberish)
                is_coherent, coh_reason = check_prose_coherence(out_text)
                if not is_coherent:
                    return self._reject(worker, f"keyword_salad_rejected ({coh_reason})", task=task)

                # Vague Non-Answer Defense: Filter meta-discourse evasive non-answers
                is_vague, v_ratio = is_vague_non_answer(out_text)
                if is_vague:
                    return self._reject(worker, f"vague_non_answer_rejected (meta-discourse ratio {v_ratio:.2f} >= 0.22 lacks substantive mechanisms)", task=task)

                # Prompt-Echo Defense: Extract prompt stems and require novel explanatory stems for long answers
                prompt_stems = extract_prompt_stems(prompt_str)
                novel_stems_2 = extract_novel_stems(out_text, prompt_stems)
                if len(out_tokens) >= 8 and len(novel_stems_2) < 2:
                    return self._reject(worker, "prompt_echo_attack_rejected (response merely repeats prompt keywords without novel explanatory content)", task=task)

                consensus_key = str(t_payload.get("consensus_id") or hashlib.sha256(prompt_str.encode("utf-8")).hexdigest()[:16])
                existing = self._freeform_consensus.get(consensus_key)

                if existing is None:
                    # First worker submitted. Hold in buffer awaiting independent verification.
                    self._freeform_consensus[consensus_key] = {
                        "worker_id": worker.worker_id,
                        "task_id": task_id,
                        "output": out_text,
                        "worker": worker,
                        "funded_by": task.get("funded_by", ""),
                        "funded_credits": int(task.get("funded_credits") or 0),
                        "task": task,
                        "created_at": time.time(),
                    }
                    return {
                        "ok": True,
                        "status": "PENDING_CONSENSUS",
                        "task_id": task_id,
                        "worker_id": worker.worker_id,
                        "message": "Result held for independent multi-worker consensus verification",
                    }
                else:
                    w1 = existing["worker"]
                    w2 = worker
                    out1 = existing["output"]
                    out2 = out_text

                    # 1. Anti-Sybil Check: Ensure workers are from independent nodes and subnets
                    if not _is_independent_peer(w1, w2):
                        return self._reject(worker, "sybil_consensus_attempt_blocked (consensus peer must be an independent node)", task=task)

                    # 2. Continuous dense semantic embeddings & prompt relevance
                    emb1 = compute_semantic_embedding(out1)
                    emb2 = compute_semantic_embedding(out2)
                    emb_prompt = compute_semantic_embedding(prompt_str)
                    cos_sim = compute_cosine_similarity(emb1, emb2)

                    novel_stems_1 = extract_novel_stems(out1, prompt_stems)
                    set1 = set(novel_stems_1)
                    set2 = set(novel_stems_2)
                    shared_novel = set1 & set2
                    shared_novel_count = len(shared_novel)
                    len_ratio = min(len(out1), len(out2)) / max(len(out1), len(out2))

                    # 3. Deterministic Factual Query Rule:
                    # Short factual answers (<= 25 words) like "The capital of Japan is Tokyo."
                    is_short_factual = len(out1.split()) <= 25 and len(out2.split()) <= 25

                    # 4. Principled Grounding & Sybil Collusion Detection:
                    # Identify prompt domain concept clusters and verify if novel shared words are grounded.
                    # Zero hardcoded token blacklists! Generic detection of ungrounded coordinated vocabulary.
                    prompt_clusters = {
                        c_name for c_name, words in CONCEPT_TAXONOMY.items()
                        if any(stem_token(w) in prompt_stems or any(ps.startswith(w) or w.startswith(ps) for ps in prompt_stems) for w in words)
                    }
                    valid_grounding_clusters = prompt_clusters | {
                        "GENERAL_SCIENCE", "RELATIONAL_CORE", "RELATION_SPACE",
                        "RELATION_STATE", "RELATION_TIME", "RELATION_CONDITION",
                        "OBSERVE_MEASURE", "CAUSAL_DETERMINE",
                    }
                    grounded_vocab = set()
                    for c in valid_grounding_clusters:
                        grounded_vocab |= CONCEPT_TAXONOMY.get(c, set())

                    grounded_shared = {
                        w for w in shared_novel
                        if any(w.startswith(gw) or gw.startswith(w) for gw in grounded_vocab)
                    }
                    ungrounded_shared = shared_novel - grounded_shared

                    is_collusion = False
                    # If workers share multiple arbitrary novel words with ZERO grounding in prompt topic
                    if len(ungrounded_shared) >= 2 and len(grounded_shared) == 0:
                        is_collusion = True
                    elif not is_short_factual and (cos_sim >= 0.85 or out1.strip().lower() == out2.strip().lower()) and shared_novel_count >= 2:
                        prompt_cos = max(compute_cosine_similarity(emb_prompt, emb1), compute_cosine_similarity(emb_prompt, emb2))
                        if prompt_cos < 0.15 and len(grounded_shared) == 0:
                            is_collusion = True

                    if is_collusion:
                        return self._reject(worker, "sybil_collusion_detected (arbitrary ungrounded vocabulary across nodes)", task=task)

                    # Contradiction Detection: Catch factual inversions and opposing claims
                    is_contra, c_reason = detect_contradiction(out1, out2)
                    if is_contra:
                        return self._reject(worker, f"consensus_semantic_divergence_rejected (contradiction_rejected: {c_reason})", task=task)

                    # 5. Semantic Agreement Check:
                    is_agreed = False
                    if is_short_factual:
                        # Strict factual entity agreement:
                        # NEVER match on whole-sentence cosine (which triggers on prompt-echo filler like "is the capital of Japan")!
                        # Contradicting entities (Tokyo vs Osaka) or filler non-answers have shared_novel_count == 0 and are REJECTED!
                        if out1.strip().lower() == out2.strip().lower() or shared_novel_count >= 1:
                            is_agreed = True
                    else:
                        # Explanatory responses: evaluate shared novel explanatory mechanism stems
                        if len_ratio >= 0.15 and shared_novel_count >= 2:
                            is_agreed = True

                    if is_agreed:
                        # Consensus verified! Disburse exact funded escrow to each worker (Zero-sum credit economy)
                        w1_reward = int(existing.get("funded_credits") or 0)
                        w2_reward = int(task.get("funded_credits") or 0)

                        if w1.status != "SLASHED":
                            with self._lock:
                                if w1_reward > 0:
                                    w1.credits += w1_reward
                                w1.tasks_completed += 1
                                w1.tasks_verified += 1
                                if getattr(w1, "canary_strikes", 0) > 0 and w1.tasks_verified % 20 == 0:
                                    w1.canary_strikes = max(0, w1.canary_strikes - 1)
                                if self.ledger:
                                    self.ledger.append("worker_task_settled", {
                                        "worker_id": w1.worker_id,
                                        "task_id": existing["task_id"],
                                        "feature": task["feature"],
                                        "credits_awarded": w1_reward,
                                        "new_balance": w1.credits,
                                        "funded_by": existing.get("funded_by", ""),
                                        "consensus": True,
                                        "consensus_peer": w2.worker_id,
                                    })
                                self._flush()
                                if existing["task_id"] in self._nat_task_events:
                                    self._nat_task_events[existing["task_id"]].set()

                        # Configure candidate worker reward
                        task["funded_credits"] = w2_reward
                        verified = True
                        self._freeform_consensus.pop(consensus_key, None)
                        # Record clean settlement in organic canary replay pool
                        self.record_trusted_replay_task(prompt_str, out1, feature=task["feature"])
                    else:
                        # Divergent or fraudulent output
                        return self._reject(worker, "consensus_semantic_divergence_rejected", task=task)

        # Cryptographic Proof-of-Neural-Work Cosine Similarity Verification on LoRA Gradients
        if isinstance(result, dict) and isinstance(result.get("lora_gradients"), dict):
            lg = result["lora_gradients"]
            dA = lg.get("delta_A")
            dB = lg.get("delta_B")
            should_spot_check_grad = (
                getattr(self, "force_gradient_spot_check", True)
                or (secrets.randbelow(100) < int(getattr(self, "gradient_spot_check_rate", 1.0) * 100))
            )
            if isinstance(dA, list) and isinstance(dB, list) and len(dA) > 0 and len(dB) > 0:
                if should_spot_check_grad:
                    try:
                        from .brain_matrix import compute_local_lora_gradients
                        p_text = str((task.get("payload") or {}).get("prompt") or (task.get("payload") or {}).get("text") or task.get("feature") or "sovereign_mesh_train")
                        shard_name = lg.get("domain_shard") or worker.brain_shard
                        ref_grads = compute_local_lora_gradients(p_text, shard_name)
                        worker_vec = list(dA or []) + list(dB or [])
                        ref_vec = list(ref_grads["delta_A"]) + list(ref_grads["delta_B"])
                        cos_sim = compute_cosine_similarity(worker_vec, ref_vec)
                        if cos_sim < 0.98:
                            with self._lock:
                                return self._slash(
                                    worker,
                                    f"Byzantine Fake Gradient Attack detected on {shard_name}: Cosine similarity {cos_sim:.4f} < 0.98 (task {task_id})"
                                )
                        verified = True
                    except Exception:
                        verified = False
                else:
                    verified = True

        if not verified:
            return self._reject(worker, "unverified_or_fabricated_task_result (objective verification failed)", task=task)

        with self._lock:
            now_ts = time.time()
            max_daily = int(getattr(self, "max_daily_task_credits", 250))
            if (now_ts - float(getattr(worker, "daily_task_window_start", 0.0) or 0.0)) >= 86400.0:
                worker.daily_task_window_start = now_ts
                worker.daily_task_credits_earned = 0
            if worker.daily_task_credits_earned >= max_daily:
                return self._reject(worker, f"daily_reward_cap_exceeded ({max_daily} credits/day max)", task=task)

            effective_reward = self.halving_epoch_info()["active_task_reward_credits"]
            if task.get("funded_credits") is not None:
                effective_reward = min(effective_reward, max(0, int(task["funded_credits"])))
            effective_reward = min(effective_reward, max(0, max_daily - worker.daily_task_credits_earned))
            worker.daily_task_credits_earned += effective_reward
            worker.credits += effective_reward
            worker.tasks_completed += 1
            worker.tasks_verified += int(verified)
            worker.epoch_tasks_verified += int(verified)
            if getattr(worker, "canary_strikes", 0) > 0 and worker.tasks_verified % 20 == 0:
                worker.canary_strikes = max(0, worker.canary_strikes - 1)
            referral_bonus = self._award_referral_bonus(worker, effective_reward, source="task_settlement")
            self._flush()
            block = self.ledger.append("worker_task_settled", {
                "task_id": task_id, "worker_id": worker_id, "feature": task["feature"], "verified": verified,
                "reward": effective_reward, "referral_bonus_minted": referral_bonus, "balance": worker.credits,
                "quantum_verified": quantum_verified,
                "quantum_address": worker.quantum_address,
                "crypto_security_level": worker.crypto_security_level,
                "ratchet_step": worker.ratchet_step,
            })
            settled_out = {
                "ok": True,
                "status": "SETTLED", "verified": verified, "worker_id": worker_id, "task_id": task_id,
                "reward_credits": effective_reward, "reward_umais": effective_reward,
                "referral_bonus_minted": referral_bonus,
                "total_credits": worker.credits, "worker_credits": worker.credits, "balance_umais": worker.credits,
                "quantum_verified": quantum_verified,
                "quantum_address": worker.quantum_address,
                "crypto_security_level": worker.crypto_security_level,
                "ratchet_step": worker.ratchet_step,
                "ledger_block": block["hash"][:16], "result": result,
            }
            # If the worker computed mathematical LoRA weight deltas (ΔA, ΔB), merge via FedAvg into .safetensors
            if isinstance(result, dict) and isinstance(result.get("lora_gradients"), dict):
                lg = result["lora_gradients"]
                grid_ref = self.grid or getattr(self, "_grid", None)
                if grid_ref is not None and getattr(grid_ref, "brain_matrix", None) is not None:
                    try:
                        fed_res = grid_ref.brain_matrix.federated_average_lora_deltas(
                            domain_shard=lg.get("domain_shard") or worker.brain_shard,
                            worker_gradient_packets=[lg],
                        )
                        settled_out["fedavg_safetensors_merge"] = fed_res
                    except Exception:
                        pass
            self._nat_settled_results[task_id] = settled_out
            ev = self._nat_task_events.pop(task_id, None)
            if ev is not None:
                ev.set()
            return settled_out

    def _slash(self, worker: WorkerNodeRecord, reason: str) -> dict:
        burned, worker.credits = worker.credits, 0
        worker.burned_credits += burned
        worker.pending_payout = 0.0  # Slashed workers forfeit pending payouts
        worker.epoch_tasks_verified = 0
        worker.status = "SLASHED"
        worker.slashed_reason = reason
        # Also slash any staked collateral in token_sink if available
        burned_staked = 0
        sink = getattr(self, "token_sink", None)
        if sink and hasattr(sink, "slash_staker"):
            burned_staked = sink.slash_staker(worker.worker_id, reason=reason)
            worker.burned_credits += burned_staked
        self._flush()
        block = self.ledger.append("worker_slashed", {
            "worker_id": worker.worker_id,
            "reason": reason,
            "burned_credits": burned,
            "burned_staked": burned_staked,
        })
        return {
            "ok": False,
            "status": "SLASHED",
            "worker_id": worker.worker_id,
            "reason": reason,
            "burned_credits": burned,
            "burned_staked": burned_staked,
            "remaining_credits": 0,
            "ledger_block": block["hash"][:16],
        }

    def slash_worker(self, worker_id: str, reason: str = "Provable misbehaviour or security violation") -> dict:
        """Authority method to slash a misbehaving or malicious worker node, burning all credits."""
        with self._lock:
            worker = self._resolve_worker_or_key(worker_id)
            if not worker:
                return {"status": "NOT_FOUND", "worker_id": worker_id}
            return self._slash(worker, reason)

    # -- Model 1: Compute Barter & Credit Economy
    def spend_credits(self, worker_id: str, amount: int, reason: str = "compute_task") -> dict:
        if amount <= 0:
            raise ValueError("Amount to spend must be positive")
        with self._lock:
            worker = self._resolve_worker_or_key(worker_id)
            if not worker:
                raise KeyError(f"Unknown worker node {worker_id!r}")
            if worker.status == "SLASHED":
                raise PermissionError(f"Worker {worker.worker_id!r} is SLASHED and cannot spend credits")
            if getattr(worker, "dispute_account_locked", False):
                raise PermissionError(
                    f"Worker {worker.worker_id!r} account is FROZEN due to an active P2P Dispute ({worker.dispute_reason}). "
                    f"Awaiting Sovereign Owner arbitration."
                )
            if worker.credits < amount:
                return {"status": "INSUFFICIENT_CREDITS", "worker_id": worker.worker_id,
                        "balance": worker.credits, "required": amount,
                        "error": (f"Insufficient credits (balance: {worker.credits}, required: {amount}). "
                                  f"Run worker node to execute network tasks and earn compute credits!")}
            prev_bal = worker.credits
            new_bal = prev_bal - amount
            # H4 Fix: Write-Ahead Ledger entry first, then mutate state and fsync atomically
            block = self.ledger.append("credits_spent", {
                "worker_id": worker.worker_id, "amount": amount, "reason": reason,
                "previous_balance": prev_bal, "remaining": new_bal,
            })
            try:
                worker.credits = new_bal
                self._flush()
            except Exception:
                worker.credits = prev_bal
                raise
            return {"status": "SPENT", "worker_id": worker.worker_id, "amount": amount,
                    "remaining_credits": worker.credits, "reason": reason,
                    "ledger_block": block["hash"][:16]}

    def grant_credits(self, worker_id: str, amount: int, reason: str = "owner_grant") -> dict:
        if amount <= 0:
            raise ValueError("Amount to grant must be positive")
        with self._lock:
            worker = self._resolve_worker_or_key(worker_id)
            if not worker:
                worker = self.register_worker(worker_id, url="local", initial_credits=0)
            prev_credits = worker.credits
            prev_status = worker.status
            new_bal = prev_credits + amount
            tier = "SOVEREIGN_VIP" if new_bal >= 200 else ("PRO" if new_bal >= 50 else "COMMUNITY")
            block = self.ledger.append("owner_credits_granted", {
                "worker_id": worker.worker_id,
                "amount": amount,
                "reason": reason,
                "previous_balance": prev_credits,
                "new_balance": new_bal,
                "tier": tier,
            })
            try:
                worker.credits = new_bal
                if worker.status == "SLASHED" and reason == "owner_grant":
                    worker.status = "ACTIVE"
                self._flush()
            except Exception:
                worker.credits = prev_credits
                worker.status = prev_status
                raise
            return {
                "status": "GRANTED",
                "worker_id": worker.worker_id,
                "account_key": worker.key,
                "previous_credits": prev_credits,
                "added_credits": amount,
                "amount_added": amount,
                "new_credits": worker.credits,
                "new_balance": worker.credits,
                "tier": tier,
                "reason": reason,
                "ledger_block": block["hash"][:16],
            }

    def transfer_credits(self, from_worker: str, to_worker: str, amount: int) -> dict:
        if amount <= 0:
            raise ValueError("Transfer amount must be positive")
        with self._lock:
            w_from = self._resolve_worker_or_key(from_worker)
            w_to = self._resolve_worker_or_key(to_worker)
            if not w_from:
                raise KeyError(f"Sender worker {from_worker!r} not found")
            if not w_to:
                raise KeyError(f"Recipient worker {to_worker!r} not found")
            if w_from.worker_id == w_to.worker_id:
                raise ValueError("Cannot transfer credits to self")
            if w_from.status == "SLASHED" or w_to.status == "SLASHED":
                raise PermissionError("Slashed nodes cannot transfer or receive credits")
            if w_from.dispute_frozen or w_to.dispute_frozen:
                raise PermissionError("Accounts under active P2P Dispute Freeze cannot transfer or receive credits until Owner arbitration")
            if w_from.credits < amount:
                return {"ok": False, "status": "INSUFFICIENT_CREDITS", "worker_id": w_from.worker_id,
                        "balance": w_from.credits, "required": amount,
                        "error": f"Insufficient credits in {w_from.worker_id} (balance: {w_from.credits}, required: {amount})"}
            prev_from, prev_to = w_from.credits, w_to.credits
            new_from, new_to = prev_from - amount, prev_to + amount
            block = self.ledger.append("credits_transferred", {
                "from_worker": w_from.worker_id, "to_worker": w_to.worker_id, "amount": amount,
                "from_balance": new_from, "to_balance": new_to})
            try:
                w_from.credits = new_from
                w_to.credits = new_to
                self._flush()
            except Exception:
                w_from.credits = prev_from
                w_to.credits = prev_to
                raise
            return {"ok": True, "status": "TRANSFERRED", "from_worker": w_from.worker_id, "to_worker": w_to.worker_id,
                    "amount": amount, "from_balance": w_from.credits, "to_balance": w_to.credits,
                    "ledger_block": block["hash"][:16]}

    def get_balance(self, worker_id: str) -> dict:
        with self._lock:
            worker = self._resolve_worker_or_key(worker_id)
            if not worker:
                raise KeyError(f"Unknown worker node {worker_id!r}")
            tier_name = "COMMUNITY"
            if worker.credits >= 200:
                tier_name = "SOVEREIGN_VIP"
            elif worker.credits >= 50:
                tier_name = "PRO"
            return {
                "worker_id": worker.worker_id,
                "status": worker.status,
                "credits": worker.credits,
                "balance_umais": worker.credits,
                "currency_symbol": "UMAIS",
                "credit_to_umais_parity": "1 Credit = 1 UMAIS",
                "tier": tier_name,
                "tasks_completed": worker.tasks_completed,
                "tasks_verified": worker.tasks_verified,
                "uptime_minutes_verified": worker.uptime_minutes_verified,
                "hardware_spec": worker.hardware_spec,
                "brain_shard": worker.brain_shard,
                "replica_shards": list(worker.replica_shards),
                "synced_deltas_count": worker.synced_deltas_count,
                "referral_code": worker.referral_code,
                "referred_by": worker.referred_by,
                "referrals_count": worker.referrals_count,
                "referral_bonus_credits": worker.referral_bonus_credits,
                "dispute_frozen": worker.dispute_frozen,
                "dispute_reason": worker.dispute_reason,
                "pending_payout_usd": worker.pending_payout,
                "total_payout_earned_usd": worker.total_payout_earned,
                "payout_address": worker.payout_address or "NOT_SET",
            }

    # -- Model 3: Enterprise Revenue Share & Payout Settlement
    def set_payout_address(self, worker_id: str, address: str) -> dict:
        address = str(address).strip()
        if not address:
            raise ValueError("Payout address cannot be empty")
        with self._lock:
            worker = self.get_worker(worker_id)
            if not worker:
                raise KeyError(f"Unknown worker node {worker_id!r}")
            worker.payout_address = address
            self._flush()
            self.ledger.append("worker_payout_address_updated", {"worker_id": worker.worker_id, "address": address})
            return {"status": "UPDATED", "worker_id": worker.worker_id, "payout_address": address}

    def deposit_commercial_revenue(self, amount_usd: float, client_name: str, job_id: str = "") -> dict:
        if amount_usd <= 0:
            raise ValueError("Deposit amount must be positive")
        with self._lock:
            self.commercial_revenue_pool = round(self.commercial_revenue_pool + amount_usd, 2)
            block = self.ledger.append("commercial_revenue_deposit", {
                "client": client_name, "amount_usd": amount_usd, "job_id": job_id,
                "pool_balance": self.commercial_revenue_pool})
            self._flush()
            return {"status": "DEPOSITED", "client": client_name, "amount_usd": amount_usd,
                    "commercial_revenue_pool_usd": self.commercial_revenue_pool,
                    "ledger_block": block["hash"][:16]}

    def settle_epoch_revenue_split(self, split_ratio: float = 0.70) -> dict:
        with self._lock:
            pool = self.commercial_revenue_pool
            if pool <= 0:
                return {"status": "NO_REVENUE", "message": "Commercial revenue pool is $0.00"}
            eligible = [w for w in self._workers.values() if w.status == "ACTIVE" and w.epoch_tasks_verified > 0]
            worker_pot = round(pool * split_ratio, 2)
            treasury_share = round(pool - worker_pot, 2)
            self.treasury_balance = round(self.treasury_balance + treasury_share, 2)

            distributions = []
            total_work = sum(w.epoch_tasks_verified for w in eligible)
            if total_work > 0:
                for w in eligible:
                    share = round((w.epoch_tasks_verified / total_work) * worker_pot, 2)
                    w.pending_payout = round(w.pending_payout + share, 2)
                    w.total_payout_earned = round(w.total_payout_earned + share, 2)
                    distributions.append({
                        "worker_id": w.worker_id, "epoch_tasks": w.epoch_tasks_verified,
                        "payout_usd": share, "pending_payout_usd": w.pending_payout,
                        "payout_address": w.payout_address or "UNSPECIFIED"
                    })
                    w.epoch_tasks_verified = 0
            else:
                self.treasury_balance = round(self.treasury_balance + worker_pot, 2)
                treasury_share = round(treasury_share + worker_pot, 2)

            epoch_num = self.current_epoch
            self.current_epoch += 1
            self.commercial_revenue_pool = 0.0
            self._flush()

            block = self.ledger.append("revenue_epoch_settled", {
                "epoch": epoch_num, "total_pool_usd": pool, "workers_share_usd": worker_pot,
                "treasury_share_usd": treasury_share, "workers_count": len(distributions),
                "distributions": distributions})
            return {
                "status": "SETTLED", "epoch": epoch_num, "total_revenue_usd": pool,
                "workers_pool_usd": worker_pot, "treasury_pool_usd": treasury_share,
                "split_ratio": f"{int(split_ratio * 100)}% workers / {int((1 - split_ratio) * 100)}% treasury",
                "distributions": distributions, "ledger_block": block["hash"][:16]
            }

    def payout_stats(self) -> dict:
        with self._lock:
            return {
                "current_epoch": self.current_epoch,
                "commercial_revenue_pool_usd": self.commercial_revenue_pool,
                "treasury_balance_usd": self.treasury_balance,
                "workers": [
                    {
                        "worker_id": w.worker_id, "credits": w.credits,
                        "epoch_tasks_verified": w.epoch_tasks_verified,
                        "pending_payout_usd": w.pending_payout,
                        "total_payout_earned_usd": w.total_payout_earned,
                        "payout_address": w.payout_address or "NOT_SET",
                        "status": w.status
                    }
                    for w in self._workers.values()
                ]
            }

    def dispatch_remote(self, worker_id: str, feature_key: str, payload: dict, timeout: float = 120.0) -> dict:
        worker = self.get_worker(worker_id)
        if not worker or worker.url == "local":
            raise ValueError("worker has no remote URL")
        if worker.url in {"nat", "pull", "nat://outbound"}:
            packet = self.enqueue_nat_task(worker.worker_id, feature_key, payload)
            tid = packet["task_id"]
            ev = self._nat_task_events.get(tid)
            if ev and ev.wait(timeout=min(timeout, 30.0)):
                with self._lock:
                    return self._nat_settled_results.pop(tid, {"status": "SETTLED", "task_id": tid})
            return {"status": "QUEUED_FOR_NAT_PULL", "task_id": tid, "worker_id": worker.worker_id}
        packet = self.create_signed_task(worker_id, feature_key, payload)
        req = urllib.request.Request(worker.url.rstrip("/") + "/worker/execute", data=_canonical(packet),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                response = json.loads(resp.read())
        except (urllib.error.URLError, OSError, ValueError) as exc:
            with self._lock:
                self._pending.pop(packet["task_id"], None)
            return {"status": "UNREACHABLE", "error": str(exc)[:200]}
        return self.verify_and_settle(response)


class LightweightWorkerNode:
    """Edge worker. Holds only its own key; refuses unsigned tasks and Hub-only features; executes through the
    local safety pipeline (sanitization + constitutional rules) and signs the result."""

    def __init__(self, worker_id: str, worker_key: str, executor: Any):
        if not worker_key or len(worker_key) < 32:
            raise ValueError("worker_key must be the key issued by the Hub at registration")
        self.worker_id = worker_id
        self._key = worker_key
        self._executor = executor
        self.registry: FeatureRegistry = build_registry()

    def allowed_features(self) -> List[str]:
        return [f.key for f in self.registry.all() if f.key not in HUB_ONLY_FEATURES]

    def _reply(self, packet: dict, result: dict, sign: bool) -> dict:
        out = {"task_id": packet.get("task_id"), "worker_id": self.worker_id,
               "feature": packet.get("feature"), "result": result, "worker_proof": ""}
        if sign:
            out["worker_proof"] = compute_hmac(self._key, {
                "task_id": packet.get("task_id"), "worker_id": self.worker_id, "feature": packet.get("feature"),
                "nonce": packet.get("nonce"), "result": result})
        return out

    def execute_signed_task(self, packet: dict) -> dict:
        envelope = {k: packet.get(k) for k in ("task_id", "worker_id", "feature", "payload", "issued_at", "nonce")}
        if not hmac.compare_digest(str(packet.get("hub_signature", "")), compute_hmac(self._key, envelope)):
            return self._reply(packet, {"status": "UNAUTHORIZED_HUB", "error": "invalid Hub signature"}, sign=False)
        if envelope["worker_id"] != self.worker_id:
            return self._reply(packet, {"status": "ERROR", "error": "worker_id mismatch"}, sign=False)
        feature_key = str(envelope["feature"])
        if feature_key in HUB_ONLY_FEATURES:
            return self._reply(packet, {"status": "DENIED", "error": "Hub-only feature"}, sign=True)
        payload = envelope["payload"] if isinstance(envelope["payload"], dict) else {}
        if hasattr(self._executor, "run_feature"):
            result = self._executor.run_feature(self._executor.owner_tg_id, feature_key, payload,
                                                via="hub_task", log=False)
        else:
            result = self.registry.get(feature_key).handler(self._executor, sanitize_payload(payload)[0])
        return self._reply(packet, result if isinstance(result, dict) else {"status": "OK", "output": result},
                           sign=True)
