"""Query Intelligence Engine (rule-based, fully explainable).

For every question it answers:
  * category   - factual | conceptual | analytical | comparative | mathematical | multi_step
  * complexity - a 0-100 score and a level: simple (<35) | medium (35-64) | complex (>=65)
  * whether retrieval and multi-step reasoning are needed
  * the list of signals that produced the decision (shown in the UI)

It is deliberately simple and transparent. The `analyze()` signature is the
extension point for an ML classifier later (same inputs, same outputs).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

CATEGORIES = ("factual", "conceptual", "analytical", "comparative", "mathematical", "multi_step")

_PATTERNS: dict[str, list[str]] = {
    "comparative": [r"\bcompare\b", r"\bcomparison\b", r"\bversus\b", r"\bvs\.?\b", r"\bdifference(s)? between\b",
                    r"\bdiffer(s)?\b", r"\bbetter than\b", r"\bworse than\b", r"\bcontrast\b", r"\bsimilarit(y|ies)\b",
                    r"\bpros and cons\b", r"\bwhich is (better|cheaper|faster)\b"],
    "mathematical": [r"\d+(\.\d+)?\s*[-+*/x^%]\s*\d+", r"\bcalculate\b", r"\bcompute\b", r"\d+(\.\d+)?\s*%",
                     r"\bpercent(age)? of\b", r"\baverage of\b", r"\bsum of\b", r"\bratio of\b",
                     r"\bhow (much|many)\b.*\d"],
    "analytical": [r"^why\b", r"\bwhy (do|does|is|are|did|would)\b", r"\banaly[sz]e\b", r"\bevaluate\b", r"\bassess\b",
                   r"\bimpact\b", r"\bimplications?\b", r"\btrade-?offs?\b", r"\brisks?\b", r"\bjustify\b",
                   r"\broot cause\b", r"\bwhat would happen\b", r"\bcritically\b"],
    "multi_step": [r"\bstep[- ]by[- ]step\b", r"\bfirst\b.*\bthen\b", r"\band then\b", r"\bafter that\b",
                   r"\bwalk me through\b", r"\bsequence of steps\b", r"\bthen (explain|list|compare|calculate)\b"],
    "conceptual": [r"\bexplain\b", r"\bhow does\b", r"\bhow do\b", r"\bconcept\b", r"\bmeaning of\b", r"\bdescribe\b",
                   r"\bwhat is the (purpose|idea|principle)\b", r"\bunderstand\b", r"\boverview\b"],
    "factual": [r"^(who|when|where|which)\b", r"^what (is|are|was|were)\b", r"\blist\b", r"\bname\b", r"\bdefine\b",
                r"\bdate\b", r"\bdeadline\b", r"\bhow long\b", r"\bhow (much|many)\b"],
}
_COMPILED = {k: [re.compile(p, re.IGNORECASE) for p in v] for k, v in _PATTERNS.items()}
_PRIORITY = ("multi_step", "mathematical", "comparative", "analytical", "conceptual", "factual")
_BASE = {"factual": 10, "conceptual": 30, "comparative": 45, "mathematical": 40, "analytical": 50, "multi_step": 60}
_PURE_MATH = re.compile(r"^[\d\s.+\-*/()%^=?]+$|^(what is|calculate|compute)\s+[\d\s.+\-*/()%^]+\??$", re.IGNORECASE)


@dataclass
class QueryAnalysis:
    category: str
    complexity_score: float
    complexity_level: str
    retrieval_required: bool
    reasoning_required: bool
    multi_step: bool
    word_count: int
    signals: list[str] = field(default_factory=list)
    matched_categories: list[str] = field(default_factory=list)
    processing_path: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def analyze(query: str, has_documents: bool = True) -> QueryAnalysis:
    q = " ".join(query.strip().split())
    words = re.findall(r"\w+", q)
    signals: list[str] = []

    matched = [c for c in _PRIORITY if any(p.search(q) for p in _COMPILED[c])]
    # several questions in one message also means multi-step reasoning
    question_marks = q.count("?")
    interrogatives = len(re.findall(r"\b(what|why|how|which|who|when|where)\b", q, re.IGNORECASE))
    if question_marks >= 2 or interrogatives >= 3:
        if "multi_step" not in matched:
            matched.insert(0, "multi_step")
        signals.append(f"{max(question_marks, interrogatives)} questions in one message")

    category = matched[0] if matched else ("factual" if len(words) <= 8 else "conceptual")
    signals.append(f"category '{category}' " + (f"matched keywords ({', '.join(matched)})" if matched
                                                 else "chosen by default (no keyword matched)"))

    score = float(_BASE[category])
    length_pts = min(20.0, max(0.0, (len(words) - 8) * 0.8))
    if length_pts:
        signals.append(f"+{length_pts:.0f} for length ({len(words)} words)")
    score += length_pts
    extra = max(0, len(set(matched)) - 1) * 6
    if extra:
        signals.append(f"+{extra} for mixing {len(set(matched))} kinds of reasoning")
    score += extra
    clauses = len(re.findall(r"\b(and|but|while|whereas|because|if|unless|considering)\b", q, re.IGNORECASE))
    if clauses >= 2:
        signals.append(f"+{min(clauses, 4) * 3} for {clauses} linked clauses")
        score += min(clauses, 4) * 3
    score = round(min(100.0, score), 1)
    level = "simple" if score < 35 else "medium" if score < 65 else "complex"

    reasoning = category in ("analytical", "comparative", "mathematical", "multi_step") or level == "complex"
    pure_math = bool(_PURE_MATH.match(q))
    retrieval = not pure_math          # everything except bare arithmetic must be grounded in documents
    if pure_math:
        signals.append("pure arithmetic - no document retrieval needed")
    elif not has_documents:
        signals.append("no indexed documents in scope - the answer cannot be grounded")

    path = ("semantic cache -> " + ("document retrieval -> " if retrieval and has_documents else "") +
            f"{'small' if level == 'simple' else 'medium' if level == 'medium' else 'large'}-tier model")
    return QueryAnalysis(category, score, level, retrieval, reasoning, category == "multi_step", len(words),
                         signals, matched, path)
