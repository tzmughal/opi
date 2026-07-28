"""
scoring_engine.py
-----------------
Deterministic personality scoring engine for the OPI Personality Assessment System.
All scoring logic is purely mathematical — no LLM involvement.
"""

from __future__ import annotations

import statistics
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LIKERT_MIN = 1
LIKERT_MAX = 7
LIKERT_MID = 4

ALL_TRAITS = [
    "emotional_stability",
    "conscientiousness",
    "integrity",
    "initiative",
    "sociability",
    "discipline",
    "planning_ability",
    "responsibility",
    "courage",
    "determination",
    "social_relations",
    "practical_ability",
    "influencing_ability",
    "general_awareness",
    "expression",
    "physical_endurance",
    "self_confidence"
]

# Pairs of question IDs that measure opposite poles of the same construct.
# If both are answered in contradictory directions, a contradiction is flagged.
# Format: (positive_keyed_id, negative_keyed_id)
CONTRADICTION_PAIRS = [
    (1, 2),   # calm vs overwhelmed
    (1, 4),   # calm vs anxious
    (3, 4),   # manage emotions vs anxious
    (5, 2),   # recover quickly vs overwhelmed
    (6, 7),   # complete before deadline vs leave unfinished
    (8, 9),   # attention to detail vs miss commitments
    (10, 9),  # follow through vs forget commitments
    (11, 12), # honest vs bend rules
    (13, 14), # own mistakes vs acted unethically
    (15, 12), # consistent standards vs bend rules
    (16, 17), # proactive vs wait for lead
    (18, 19), # look for improvements vs prefer told what to do
    (20, 17), # suggest ideas vs wait for lead
    (21, 24), # enjoy teamwork vs avoid groups
    (23, 22), # comfortable with new people vs draining to interact
    (25, 24), # build rapport vs avoid groups
    (26, 27),  # consistent habits vs struggle with routines
    (28, 29),  # prioritize responsibilities vs abandon plans
    (30, 27),  # high standards vs struggle with routines
    # New pairs for questions 31-48
    (31, 32),  # composed in stress vs emotions affect judgment
    (33, 32),  # bounce back from criticism vs emotions affect judgment
    (34, 35),  # set clear goals vs procrastinate
    (36, 35),  # verify work vs procrastinate
    (31,  2),  # composed in stress vs overwhelmed
    (33,  4),  # bounce back from criticism vs anxious under change
    # Phase 1 Expansion
    (49, 50),
    (51, 55),
    (53, 50),
    (31, 54),
    (3,  56),
    (1,  54),
    (57, 59),
    (61, 59),
    (6,  60),
    (67, 63),
    (67, 64),
    (11, 68),
    (71, 75),
    (72, 76),
    (77, 17),
    (71, 78),
    (21, 82),
    (79, 82),
    (90, 27),
    (90, 29),
    (97, 93),
    (99, 95),
    (94, 100),
]

# Items designed to detect "faking good" or social desirability bias.
# Claiming absolute perfection on these is unrealistic.
LIE_SCALE_ITEMS = {
    10: "positive",  # consistently follow through promises
    11: "positive",  # always honest
    15: "positive",  # maintain same standards whether observed or not
    66: "positive",  # keep confidential strictly to myself without exception
    91: "positive",  # rarely make exceptions to standards I set
}


# ---------------------------------------------------------------------------
# Core scoring helpers
# ---------------------------------------------------------------------------

def reverse_score(raw: int, polarity: str) -> int:
    """
    Apply reverse scoring for negative-keyed items.

    Parameters
    ----------
    raw      : Raw Likert response (1–7)
    polarity : 'positive' or 'negative'

    Returns
    -------
    Adjusted score (1–7)
    """
    if polarity == "negative":
        return 8 - raw
    return raw


def compute_trait_scores(
    responses: dict[int, int],
    meta: list[dict[str, Any]],
) -> dict[str, float]:
    """
    Compute normalised (0–1) trait scores.

    Formula:  trait_score = sum(adjusted_scores) / (7 * n_questions)

    Parameters
    ----------
    responses : {question_id: raw_likert_score}
    meta      : list of question metadata dicts

    Returns
    -------
    {trait_name: normalised_score}
    """
    trait_totals: dict[str, list[int]] = {t: [] for t in ALL_TRAITS}

    for item in meta:
        qid = item["id"]
        if qid not in responses:
            continue
        raw = responses[qid]
        adjusted = reverse_score(raw, item["polarity"])
        trait = item["trait"]
        if trait in trait_totals:
            trait_totals[trait].append(adjusted)

    trait_scores: dict[str, float | None] = {}
    for trait, scores in trait_totals.items():
        if scores:
            max_possible = LIKERT_MAX * len(scores)
            trait_scores[trait] = sum(scores) / max_possible
        else:
            trait_scores[trait] = None

    return trait_scores


# ---------------------------------------------------------------------------
# Consistency detection
# ---------------------------------------------------------------------------

def compute_consistency(
    responses: dict[int, int],
    meta: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Detect contradictions between semantically opposite question pairs.

    A contradiction is flagged when:
      - Both questions are answered
      - The adjusted scores differ by >= 3 points

    Returns
    -------
    {
        'consistency_score': float (0–1),
        'contradiction_rate': float,
        'contradictions': list of contradiction dicts,
    }
    """
    # Build a fast lookup: id -> (adjusted_score, text)
    meta_by_id = {item["id"]: item for item in meta}
    adjusted: dict[int, int] = {}
    for item in meta:
        qid = item["id"]
        if qid in responses:
            adjusted[qid] = reverse_score(responses[qid], item["polarity"])

    contradictions = []
    checked = 0

    for pos_id, neg_id in CONTRADICTION_PAIRS:
        if pos_id not in adjusted or neg_id not in adjusted:
            continue
        checked += 1
        score_pos = adjusted[pos_id]   # higher = more positive trait
        score_neg = adjusted[neg_id]   # already reversed — higher = more positive
        diff = abs(score_pos - score_neg)
        if diff >= 3:
            contradictions.append(
                {
                    "q1_id": pos_id,
                    "q1_text": meta_by_id[pos_id]["text"],
                    "q1_raw": responses[pos_id],
                    "q1_adjusted": score_pos,
                    "q2_id": neg_id,
                    "q2_text": meta_by_id[neg_id]["text"],
                    "q2_raw": responses[neg_id],
                    "q2_adjusted": score_neg,
                    "divergence": diff,
                }
            )

    if checked == 0:
        return {"consistency_score": 1.0, "contradiction_rate": 0.0, "contradictions": []}

    contradiction_rate = len(contradictions) / checked
    consistency_score = 1.0 - contradiction_rate

    return {
        "consistency_score": round(consistency_score, 4),
        "contradiction_rate": round(contradiction_rate, 4),
        "contradictions": contradictions,
    }


# ---------------------------------------------------------------------------
# Bias / impression management detection
# ---------------------------------------------------------------------------

def detect_bias(responses: dict[int, int]) -> dict[str, Any]:
    """
    Detect faking / social desirability bias.

    Flags:
      - extreme_bias  : ratio of extreme answers (1 or 7) exceeds threshold
      - low_variance  : stdev of all answers is below threshold
      - acquiescence  : mean > 5.5 (all-agree pattern)

    Returns
    -------
    {
        'extreme_ratio': float,
        'variance': float,
        'mean': float,
        'flags': list[str],
        'penalty': float,
    }
    """
    if not responses:
        return {"extreme_ratio": 0.0, "variance": 0.0, "mean": 4.0, "flags": [], "penalty": 0.0}

    scores = list(responses.values())
    n = len(scores)

    extreme_count = sum(1 for s in scores if s in (1, 7))
    extreme_ratio = extreme_count / n

    try:
        variance = statistics.variance(scores) if n > 1 else 0.0
        stdev = statistics.stdev(scores) if n > 1 else 0.0
    except statistics.StatisticsError:
        variance = 0.0
        stdev = 0.0

    mean_score = sum(scores) / n

    flags = []
    penalty = 0.0

    if extreme_ratio >= 0.60:
        flags.append("extreme_answer_bias")
        penalty += 0.05

    if stdev < 0.5:
        flags.append("low_variance")
        penalty += 0.03

    if mean_score > 5.8:
        flags.append("acquiescence_bias")
        penalty += 0.03

    if mean_score < 2.2:
        flags.append("negativity_bias")
        penalty += 0.03

    # Lie Scale Check
    lie_score = 0
    lie_max = 0
    for qid, polarity in LIE_SCALE_ITEMS.items():
        if qid in responses:
            lie_max += 1
            raw = responses[qid]
            adjusted = reverse_score(raw, polarity)
            if adjusted >= 6:  # Agree or Strongly Agree to perfection
                lie_score += 1
                
    if lie_max > 0:
        lie_ratio = lie_score / lie_max
        if lie_ratio >= 0.5:
            flags.append("social_desirability_bias")
            penalty += 0.15

    return {
        "extreme_ratio": round(extreme_ratio, 4),
        "variance": round(variance, 4),
        "stdev": round(stdev, 4),
        "mean": round(mean_score, 4),
        "flags": flags,
        "penalty": round(min(penalty, 0.25), 4),  # cap penalty at 0.25
    }


# ---------------------------------------------------------------------------
# Final score + verdict
# ---------------------------------------------------------------------------

def compute_final_score(
    trait_scores: dict[str, float | None],
    config: dict[str, Any],
) -> float:
    """
    Compute the weighted composite trait score, ignoring unanswered traits.

    Returns
    -------
    Weighted score in [0, 1]
    """
    weights: dict[str, float] = config.get("trait_weights", {})
    
    answered_weights = 0.0
    weighted_sum = 0.0
    
    for trait, weight in weights.items():
        score = trait_scores.get(trait)
        if score is not None:
            weighted_sum += score * weight
            answered_weights += weight
            
    if answered_weights == 0.0:
        return 0.0

    return round(weighted_sum / answered_weights, 4)


def apply_penalties(
    base_score: float,
    bias_info: dict[str, Any],
    consistency_info: dict[str, Any],
    config: dict[str, Any],
) -> float:
    """
    Deduct penalties for bias and inconsistency.

    Formula:
        final = base_score
                - bias_penalty
                - (inconsistency_penalty_multiplier * contradiction_rate)

    Returns
    -------
    Penalised final score in [0, 1]
    """
    penalties_cfg = config.get("penalties", {})
    multiplier = penalties_cfg.get("inconsistency_penalty_multiplier", 0.15)

    bias_penalty = bias_info.get("penalty", 0.0)
    inconsistency_penalty = multiplier * consistency_info.get("contradiction_rate", 0.0)

    final = base_score - bias_penalty - inconsistency_penalty
    return round(max(0.0, min(1.0, final)), 4)


def get_verdict(
    final_score: float,
    trait_scores: dict[str, float],
    config: dict[str, Any],
) -> dict[str, Any]:
    """
    Determine the final recommendation verdict.

    Rules:
      - final_score >= recommended_threshold           → Recommended
      - borderline_lower <= final_score < recommended  → Borderline
      - final_score < borderline_lower                 → Not Recommended

    Hard constraint:
      - emotional_stability must be >= hard_constraint min
        for a 'Recommended' verdict; otherwise demoted to 'Borderline'

    Returns
    -------
    {
        'verdict': str,
        'final_score': float,
        'hard_constraint_triggered': bool,
        'reason': str,
    }
    """
    thresholds = config.get("thresholds", {})
    hard = config.get("hard_constraints", {})

    recommended_thr = thresholds.get("recommended", 0.72)
    borderline_thr = thresholds.get("borderline_lower", 0.60)
    es_min = hard.get("emotional_stability_min", 0.60)

    hard_constraint_triggered = False
    reason = ""

    if final_score >= recommended_thr:
        verdict = "Recommended"
        reason = f"Score {final_score:.2f} meets or exceeds threshold {recommended_thr:.2f}."
        # Apply hard constraint check
        es_score = trait_scores.get("emotional_stability")
        if es_score is not None and es_score < es_min:
            verdict = "Borderline"
            hard_constraint_triggered = True
            reason = (
                f"Score {final_score:.2f} qualified for Recommended, but "
                f"emotional_stability ({es_score:.2f}) is below minimum {es_min:.2f}."
            )
    elif final_score >= borderline_thr:
        verdict = "Borderline"
        reason = (
            f"Score {final_score:.2f} is between "
            f"{borderline_thr:.2f} and {recommended_thr:.2f}."
        )
    else:
        verdict = "Not Recommended"
        reason = f"Score {final_score:.2f} is below threshold {borderline_thr:.2f}."

    return {
        "verdict": verdict,
        "final_score": final_score,
        "hard_constraint_triggered": hard_constraint_triggered,
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# Full pipeline entry point
# ---------------------------------------------------------------------------

def run_full_scoring(
    responses: dict[int, int],
    meta: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    """
    Execute the complete scoring pipeline.

    Returns
    -------
    Full scoring result dict including trait_scores, consistency,
    bias, final_score, and verdict.
    """
    trait_scores = compute_trait_scores(responses, meta)
    consistency_info = compute_consistency(responses, meta)
    bias_info = detect_bias(responses)
    base_score = compute_final_score(trait_scores, config)
    final_score = apply_penalties(base_score, bias_info, consistency_info, config)
    verdict_info = get_verdict(final_score, trait_scores, config)

    return {
        "trait_scores": trait_scores,
        "consistency": consistency_info,
        "bias": bias_info,
        "base_score": base_score,
        "final_score": final_score,
        "verdict": verdict_info,
    }
