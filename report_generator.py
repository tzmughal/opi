"""
report_generator.py
--------------------
Generates structured, human-readable personality assessment reports
for the OPI Personality Assessment System.

This module ONLY formats data — it performs no scoring computations.
"""

from __future__ import annotations

import textwrap
from datetime import datetime
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TRAIT_LABELS = {
    "emotional_stability": "Emotional Stability",
    "conscientiousness":   "Conscientiousness",
    "integrity":           "Integrity",
    "initiative":          "Initiative",
    "sociability":         "Sociability",
    "discipline":          "Discipline",
    "planning_ability":    "Planning Ability",
    "responsibility":      "Responsibility",
    "courage":             "Courage",
    "determination":       "Determination",
    "social_relations":    "Social Relations",
    "practical_ability":   "Practical Ability",
    "influencing_ability": "Influencing Ability",
    "general_awareness":   "General Awareness",
    "expression":          "Expression",
    "physical_endurance":  "Physical Endurance",
    "self_confidence":     "Self-Confidence",
}

VERDICT_DESCRIPTIONS = {
    "Recommended": (
        "The candidate demonstrates a well-rounded personality profile with strengths "
        "across key professional competencies. Results suggest readiness for the role."
    ),
    "Borderline": (
        "The candidate shows a mixed profile with notable strengths in some areas and "
        "development opportunities in others. Further evaluation is recommended before "
        "a final decision."
    ),
    "Not Recommended": (
        "The candidate's profile indicates significant gaps in one or more critical "
        "competency areas. Results suggest the candidate may not yet meet the "
        "requirements for this role."
    ),
}

VERDICT_COLORS = {
    "Recommended":     "#22c55e",
    "Borderline":      "#f59e0b",
    "Not Recommended": "#ef4444",
}

SCORE_BANDS = [
    (0.85, "Exceptional"),
    (0.72, "Strong"),
    (0.60, "Moderate"),
    (0.45, "Developing"),
    (0.00, "Limited"),
]

MERIT_THRESHOLD = 0.72
DEMERIT_THRESHOLD = 0.55


def _score_band(score: float) -> str:
    for threshold, label in SCORE_BANDS:
        if score >= threshold:
            return label
    return "Limited"


def _bar(score: float, width: int = 30) -> str:
    """ASCII progress bar for plain-text output."""
    filled = round(score * width)
    return "#" * filled + "-" * (width - filled)


# ---------------------------------------------------------------------------
# Strength / weakness analysis
# ---------------------------------------------------------------------------

def _analyse_strengths_weaknesses(
    trait_scores: dict[str, float],
    responses: dict[int, int],
    meta: list[dict[str, Any]],
    threshold_strong: float = 0.72,
    threshold_weak: float = 0.55,
) -> tuple[list[dict], list[dict]]:
    """
    Identify strong and weak traits with supporting evidence.

    Returns
    -------
    (strengths, weaknesses)
    Each item: {'trait': str, 'score': float, 'questions': list[dict]}
    """
    meta_by_id = {item["id"]: item for item in meta}

    strengths: list[dict] = []
    weaknesses: list[dict] = []

    for trait, score in trait_scores.items():
        if score is None:
            continue

        trait_questions = [
            item for item in meta
            if item["trait"] == trait and item["id"] in responses
        ]

        evidence = []
        for item in trait_questions:
            raw = responses[item["id"]]
            polarity = item["polarity"]
            adjusted = (8 - raw) if polarity == "negative" else raw
            evidence.append(
                {
                    "id": item["id"],
                    "text": item["text"],
                    "raw": raw,
                    "adjusted": adjusted,
                    "polarity": polarity,
                }
            )

        if score >= threshold_strong:
            strengths.append(
                {
                    "trait":      trait,
                    "label":      TRAIT_LABELS.get(trait, trait),
                    "score":      score,
                    "percentage": f"{score:.1%}",
                    "band":       _score_band(score),
                    "questions":  evidence,
                }
            )
        elif score < threshold_weak:
            weaknesses.append(
                {
                    "trait":      trait,
                    "label":      TRAIT_LABELS.get(trait, trait),
                    "score":      score,
                    "percentage": f"{score:.1%}",
                    "band":       _score_band(score),
                    "questions":  evidence,
                    "reasoning":  _weakness_reasoning(trait, score, evidence),
                }
            )

    strengths.sort(key=lambda x: x["score"], reverse=True)
    weaknesses.sort(key=lambda x: x["score"])
    return strengths, weaknesses


def _weakness_reasoning(
    trait: str,
    score: float,
    evidence: list[dict],
) -> str:
    """Generate a brief text explanation for a weakness."""
    label = TRAIT_LABELS.get(trait, trait)
    low_items = [e for e in evidence if e["adjusted"] <= 3]
    if low_items:
        ids = ", ".join(f"Q{e['id']}" for e in low_items[:3])
        return (
            f"Low {label} score ({score:.0%}) driven by below-average responses "
            f"on items {ids}, indicating potential difficulties in this area."
        )
    return (
        f"{label} scored at {score:.0%}, which falls below the expected threshold. "
        "Responses suggest inconsistent engagement with related behaviours."
    )


# ---------------------------------------------------------------------------
# Summary paragraph
# ---------------------------------------------------------------------------

def _build_summary(
    trait_scores: dict[str, float],
    verdict_info: dict[str, Any],
    bias_info: dict[str, Any],
    consistency_info: dict[str, Any],
) -> str:
    """Build a 3-sentence personality summary."""
    verdict = verdict_info.get("verdict", "Borderline")
    final_score = verdict_info.get("final_score", 0.0)

    top_traits = sorted(
        [(t, s) for t, s in trait_scores.items() if s is not None and s >= 0.65],
        key=lambda x: x[1], reverse=True,
    )
    weak_traits = sorted(
        [(t, s) for t, s in trait_scores.items() if s is not None and s < 0.55],
        key=lambda x: x[1],
    )

    top_str = (
        ", ".join(TRAIT_LABELS.get(t, t) for t, _ in top_traits[:2])
        if top_traits else "no clearly dominant traits"
    )
    weak_str = (
        " and ".join(TRAIT_LABELS.get(t, t) for t, _ in weak_traits[:2])
        if weak_traits else None
    )

    flags = bias_info.get("flags", [])
    bias_note = ""
    if flags:
        bias_note = (
            " Note: response patterns suggest possible impression management "
            f"({', '.join(flags).replace('_', ' ')}), which has been factored into the score."
        )

    consistency_score = consistency_info.get("consistency_score", 1.0)
    consistency_note = ""
    if consistency_score < 0.75:
        consistency_note = (
            " Response consistency was below expected levels, indicating some "
            "contradictory self-perceptions that may warrant follow-up."
        )

    summary_parts = [
        f"This assessment yielded a composite score of {final_score:.2f} ({_score_band(final_score)}), "
        f"resulting in a verdict of '{verdict}'.",
        f"The candidate demonstrates notable strengths in {top_str}." if top_traits else
        "No trait scored strongly above baseline.",
    ]
    if weak_str:
        summary_parts.append(
            f"Development opportunities are identified in {weak_str}."
        )
    summary_parts.append(bias_note + consistency_note)

    return " ".join(p for p in summary_parts if p.strip())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_report(
    responses: dict[int, int],
    meta: list[dict[str, Any]],
    scoring_result: dict[str, Any],
    session_id: str | None = None,
) -> dict[str, Any]:
    """
    Build a complete structured report dict.

    Parameters
    ----------
    responses      : {question_id: raw_likert_score}
    meta           : List of question metadata dicts
    scoring_result : Output from scoring_engine.run_full_scoring()
    session_id     : Optional identifier for this assessment session

    Returns
    -------
    Full report dict (JSON-serialisable)
    """
    trait_scores    = scoring_result["trait_scores"]
    consistency     = scoring_result["consistency"]
    bias            = scoring_result["bias"]
    verdict_info    = scoring_result["verdict"]

    strengths, weaknesses = _analyse_strengths_weaknesses(
        trait_scores, responses, meta
    )

    summary = _build_summary(trait_scores, verdict_info, bias, consistency)

    # Trait breakdown table
    trait_breakdown = []
    for trait in TRAIT_LABELS:
        score = trait_scores.get(trait)
        if score is None:
            trait_breakdown.append(
                {
                    "trait":      trait,
                    "label":      TRAIT_LABELS[trait],
                    "score":      0.0,
                    "percentage": "N/A",
                    "band":       "Not Assessed",
                }
            )
        else:
            trait_breakdown.append(
                {
                    "trait":      trait,
                    "label":      TRAIT_LABELS[trait],
                    "score":      round(score, 4),
                    "percentage": f"{score:.1%}",
                    "band":       _score_band(score),
                }
            )

    return {
        "meta": {
            "generated_at":    datetime.now().isoformat(timespec="seconds"),
            "session_id":      session_id,
            "total_questions": len(meta),
            "answered":        len(responses),
        },
        "summary":         summary,
        "trait_breakdown": trait_breakdown,
        "strengths":       strengths,
        "weaknesses":      weaknesses,
        "merits":          strengths,
        "demerits":        weaknesses,
        "consistency": {
            "score":             consistency["consistency_score"],
            "contradiction_rate": consistency["contradiction_rate"],
            "contradictions":    consistency["contradictions"],
        },
        "bias": {
            "flags":         bias["flags"],
            "extreme_ratio": bias["extreme_ratio"],
            "variance":      bias["variance"],
            "penalty":       bias["penalty"],
        },
        "scoring": {
            "base_score":  scoring_result["base_score"],
            "final_score": scoring_result["final_score"],
        },
        "verdict": {
            "label":                     verdict_info["verdict"],
            "description":               VERDICT_DESCRIPTIONS.get(verdict_info["verdict"], ""),
            "color":                     VERDICT_COLORS.get(verdict_info["verdict"], "#888"),
            "reason":                    verdict_info["reason"],
            "hard_constraint_triggered": verdict_info["hard_constraint_triggered"],
        },
    }


def export_report_text(report: dict[str, Any]) -> str:
    """
    Render the report dict as a formatted plain-text string.

    Parameters
    ----------
    report : Output from generate_report()

    Returns
    -------
    Multi-line human-readable report string
    """
    lines: list[str] = []
    sep = "=" * 70
    thin_sep = "-" * 70

    def h1(text: str) -> None:
        lines.append("")
        lines.append(sep)
        lines.append(f"  {text.upper()}")
        lines.append(sep)


    def h2(text: str) -> None:
        lines.append("")
        lines.append(f"  >> {text}")
        lines.append("  " + thin_sep)

    # Header
    h1("OPI Personality Assessment — Full Report")
    meta = report["meta"]
    lines.append(f"  Generated : {meta['generated_at']}")
    if meta.get("session_id"):
        lines.append(f"  Session   : {meta['session_id']}")
    lines.append(f"  Questions : {meta['answered']} / {meta['total_questions']} answered")

    # 1. Summary
    h2("1. Summary")
    for sentence in textwrap.wrap(report["summary"], width=66):
        lines.append(f"  {sentence}")

    # 2. Trait Scores
    h2("2. Trait Scores")
    for t in report["trait_breakdown"]:
        bar = _bar(t["score"], width=25)
        lines.append(
            f"  {t['label']:<24} {bar}  {t['percentage']:>6}  [{t['band']}]"
        )

    # 3. Strengths
    h2("3. Strengths")
    if report["strengths"]:
        for s in report["strengths"]:
            lines.append(f"  [+] {s['label']} ({s['percentage']}  - {s['band']})")
            for q in s["questions"][:2]:
                lines.append(f"      Q{q['id']}: \"{q['text'][:60]}...\"")
                lines.append(f"             Response: {q['raw']} (adjusted: {q['adjusted']})")
    else:
        lines.append("  No traits scored above the strong threshold.")

    # 4. Weaknesses
    h2("4. Weaknesses")
    if report["weaknesses"]:
        for w in report["weaknesses"]:
            lines.append(f"  [-] {w['label']} ({w['percentage']}  - {w['band']})")
            lines.append(f"    Reasoning: {w['reasoning']}")
            for q in w["questions"][:2]:
                lines.append(f"      Q{q['id']}: \"{q['text'][:60]}...\"")
                lines.append(f"             Response: {q['raw']} (adjusted: {q['adjusted']})")
    else:
        lines.append("  No traits scored below the weakness threshold.")

    # 5. Consistency Analysis
    h2("5. Consistency Analysis")
    c = report["consistency"]
    lines.append(f"  Consistency Score   : {c['score']:.2%}")
    lines.append(f"  Contradiction Rate  : {c['contradiction_rate']:.2%}")
    if c["contradictions"]:
        lines.append(f"  Contradictions Found: {len(c['contradictions'])}")
        for contra in c["contradictions"][:3]:
            lines.append(
                f"    - Q{contra['q1_id']} vs Q{contra['q2_id']} "
                f"(divergence: {contra['divergence']} pts)"
            )
            lines.append(f"      \"{contra['q1_text'][:55]}...\"")
            lines.append(f"      \"{contra['q2_text'][:55]}...\"")
    else:
        lines.append("  No significant contradictions detected.")

    # 6. Response Quality
    h2("6. Response Quality / Bias Check")
    b = report["bias"]
    lines.append(f"  Extreme Answer Ratio : {b['extreme_ratio']:.1%}")
    lines.append(f"  Response Variance    : {b['variance']:.2f}")
    lines.append(f"  Bias Penalty Applied : {b['penalty']:.2f}")
    if b["flags"]:
        lines.append(f"  Flags                : {', '.join(b['flags'])}")
    else:
        lines.append("  Flags                : None")

    # 7. Final Verdict
    h1("FINAL VERDICT")
    v = report["verdict"]
    sc = report["scoring"]
    lines.append(f"  Base Score  : {sc['base_score']:.4f}")
    lines.append(f"  Final Score : {sc['final_score']:.4f}")
    lines.append("")
    lines.append(f"  >>> VERDICT  : {v['label'].upper()}")
    lines.append("")
    for sentence in textwrap.wrap(v["description"], width=66):
        lines.append(f"  {sentence}")
    lines.append("")
    lines.append(f"  Reason: {v['reason']}")
    if v["hard_constraint_triggered"]:
        lines.append(
            "  [!] Hard constraint triggered: Emotional Stability below minimum threshold."
        )
    lines.append("")

    # 8. Merits (Your Strengths)
    h1("YOUR MERITS (STRENGTHS)")
    merits = report.get("merits", [])
    if merits:
        for m in merits:
            lines.append(f"  ✓  {m['label']}  —  {m['percentage']}  [{m['band']}]")
            for q in m["questions"][:2]:
                lines.append(f"       Q{q['id']}: \"{q['text'][:65]}\"")
                lines.append(f"              Response: {q['raw']} / 7  (adjusted: {q['adjusted']})")
    else:
        lines.append("  No traits scored above the merit threshold (≥72%).")

    # 9. Demerits (Areas for Development)
    h1("YOUR DEMERITS (AREAS FOR DEVELOPMENT)")
    demerits = report.get("demerits", [])
    if demerits:
        for d in demerits:
            lines.append(f"  ✗  {d['label']}  —  {d['percentage']}  [{d['band']}]")
            lines.append(f"     → {d['reasoning']}")
            for q in d["questions"][:2]:
                lines.append(f"       Q{q['id']}: \"{q['text'][:65]}\"")
                lines.append(f"              Response: {q['raw']} / 7  (adjusted: {q['adjusted']})")
    else:
        lines.append("  No traits scored below the demerit threshold (<55%). Well done!")

    lines.append("")
    lines.append(sep)
    lines.append("  End of Report — OPI Personality Assessment System")
    lines.append(sep)

    return "\n".join(lines)
