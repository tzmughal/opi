"""
llm_classifier.py
-----------------
Optional LLM-assisted question classification for the OPI system.

STRICT USAGE RULES:
  - This module ONLY classifies question polarity and assigns trait categories.
  - It NEVER computes scores or influences the final recommendation.
  - All results are cached to questions_meta.json.
  - If LLM is disabled or unavailable, a rule-based fallback is used.
"""

from __future__ import annotations

import json
import re
import os
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALL_TRAITS = [
    "emotional_stability",
    "conscientiousness",
    "integrity",
    "initiative",
    "sociability",
    "discipline",
]

TRAIT_KEYWORDS: dict[str, list[str]] = {
    "emotional_stability": [
        "calm", "pressure", "overwhelm", "anxious", "anxiety", "panic",
        "stress", "emotion", "recover", "setback", "upset", "anger", "temper",
        "worry", "nervous", "compose", "distress",
    ],
    "conscientiousness": [
        "deadline", "detail", "thorough", "commit", "organised", "organized",
        "plan", "schedule", "punctual", "appointment", "complete", "finish",
        "accurate", "careful", "precise", "systematic",
    ],
    "integrity": [
        "honest", "ethical", "truth", "trust", "fair", "accountable",
        "responsible", "transparent", "principle", "moral", "own mistake",
        "blame", "unethical", "cheat", "lie", "rule",
    ],
    "initiative": [
        "proactive", "initiative", "lead", "suggest", "idea", "improve",
        "opportun", "self-start", "volunteer", "identify problem", "anticipate",
        "innovative", "creative", "independent",
    ],
    "sociability": [
        "team", "colleague", "social", "people", "group", "interact",
        "communicate", "collaborat", "rapport", "network", "outgoing",
        "friendly", "partner", "share", "discuss",
    ],
    "discipline": [
        "routine", "habit", "consistent", "disciplin", "focus", "priorit",
        "responsib", "structured", "distraction", "impulse", "standard",
        "regulat", "self-control", "motivation",
    ],
}

NEGATIVE_KEYWORDS = [
    "avoid", "struggle", "fail", "never", "don't", "cannot", "can't",
    "lose", "lack", "rarely", "seldom", "difficul", "hard time",
    "leave unfinished", "forget", "miss", "bend", "acted unethically",
    "prefer not", "draining", "overwhelming", "panic", "anxious",
    "wait for", "prefer to be told", "abandon", "impulse",
]


# ---------------------------------------------------------------------------
# Rule-based fallback classifier (no LLM)
# ---------------------------------------------------------------------------

def _rule_based_classify(question_text: str) -> dict[str, Any]:
    """
    Classify a question using keyword heuristics.

    Returns
    -------
    {'trait': str, 'polarity': str, 'confidence': float}
    """
    text_lower = question_text.lower()

    # Polarity
    negative_hits = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text_lower)
    polarity = "negative" if negative_hits >= 1 else "positive"

    # Trait assignment — count keyword hits per trait
    trait_hits: dict[str, int] = {}
    for trait, keywords in TRAIT_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in text_lower)
        if hits > 0:
            trait_hits[trait] = hits

    if trait_hits:
        best_trait = max(trait_hits, key=lambda t: trait_hits[t])
        total_hits = sum(trait_hits.values())
        confidence = round(trait_hits[best_trait] / max(total_hits, 1), 2)
        confidence = min(0.90, max(0.50, confidence))
    else:
        best_trait = "conscientiousness"  # safe default
        confidence = 0.40

    return {"trait": best_trait, "polarity": polarity, "confidence": confidence}


# ---------------------------------------------------------------------------
# LLM classifier (OpenAI)
# ---------------------------------------------------------------------------

def _classify_via_openai(
    questions: list[str],
    model: str,
    api_key: str,
    timeout: int,
) -> list[dict[str, Any]] | None:
    """
    Classify questions using OpenAI Chat Completions API.

    Returns list of classification dicts, or None on failure.
    """
    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=api_key, timeout=timeout)

        prompt_lines = "\n".join(
            f"{i+1}. {q}" for i, q in enumerate(questions)
        )

        system_msg = (
            "You are a psychometric classification assistant. "
            "For each question, output ONLY a JSON array where each element has: "
            "'trait' (one of: emotional_stability, conscientiousness, integrity, "
            "initiative, sociability, discipline), "
            "'polarity' ('positive' or 'negative'), "
            "'confidence' (0.0–1.0). "
            "Do NOT include any explanation. Output raw JSON only."
        )

        user_msg = (
            f"Classify each of the following {len(questions)} personality "
            f"assessment questions:\n\n{prompt_lines}"
        )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.0,
        )

        raw = response.choices[0].message.content.strip()
        # Strip markdown fences if present
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        result = json.loads(raw)

        if isinstance(result, list) and len(result) == len(questions):
            return result
        return None

    except Exception as exc:
        print(f"[LLM] OpenAI classification failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# LLM classifier (Ollama — local)
# ---------------------------------------------------------------------------

def _classify_via_ollama(
    questions: list[str],
    model: str,
    timeout: int,
) -> list[dict[str, Any]] | None:
    """
    Classify questions using a locally running Ollama instance.

    Returns list of classification dicts, or None on failure.
    """
    try:
        import httpx  # type: ignore

        prompt_lines = "\n".join(
            f"{i+1}. {q}" for i, q in enumerate(questions)
        )

        payload = {
            "model": model,
            "prompt": (
                "You are a psychometric classification assistant. "
                f"Classify each of the following {len(questions)} personality "
                "assessment questions. For each, output a JSON array element with: "
                "'trait' (one of: emotional_stability, conscientiousness, integrity, "
                "initiative, sociability, discipline), "
                "'polarity' ('positive' or 'negative'), "
                "'confidence' (0.0–1.0). "
                "Output ONLY the JSON array, no explanation.\n\n"
                f"{prompt_lines}"
            ),
            "stream": False,
        }

        resp = httpx.post(
            "http://localhost:11434/api/generate",
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "").strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        result = json.loads(raw)

        if isinstance(result, list) and len(result) == len(questions):
            return result
        return None

    except Exception as exc:
        print(f"[LLM] Ollama classification failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_questions(
    questions: list[str],
    config: dict[str, Any],
    meta_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """
    Classify a list of question strings into trait/polarity metadata.

    Strategy:
    1. If config.llm.enabled is True, attempt LLM classification.
    2. Fall back to rule-based classifier on any failure.
    3. Cache results to meta_path (questions_meta.json) if provided.

    Parameters
    ----------
    questions  : List of question text strings (ordered, 1-indexed)
    config     : Full system config dict
    meta_path  : Optional path to write/cache results

    Returns
    -------
    List of metadata dicts:
    [{'id': int, 'text': str, 'trait': str, 'polarity': str, 'confidence': float}, ...]
    """
    llm_cfg = config.get("llm", {})
    llm_enabled = llm_cfg.get("enabled", False)
    provider = llm_cfg.get("provider", "ollama").lower()
    timeout = int(llm_cfg.get("timeout_seconds", 30))

    classifications: list[dict[str, Any]] | None = None

    if llm_enabled:
        if provider == "openai":
            api_key = os.environ.get("OPENAI_API_KEY", "")
            model = llm_cfg.get("openai_model", "gpt-4o-mini")
            if api_key:
                classifications = _classify_via_openai(
                    questions, model, api_key, timeout
                )
            else:
                print("[LLM] OPENAI_API_KEY not set — falling back to rules.")
        elif provider == "ollama":
            model = llm_cfg.get("model", "llama3")
            classifications = _classify_via_ollama(questions, model, timeout)

    # Build final metadata list
    meta: list[dict[str, Any]] = []
    for idx, text in enumerate(questions):
        qid = idx + 1
        if classifications and idx < len(classifications):
            raw = classifications[idx]
            trait = raw.get("trait", "conscientiousness")
            # Validate trait is allowed
            if trait not in ALL_TRAITS:
                trait = "conscientiousness"
            polarity = raw.get("polarity", "positive")
            if polarity not in ("positive", "negative"):
                polarity = "positive"
            confidence = float(raw.get("confidence", 0.7))
        else:
            fallback = _rule_based_classify(text)
            trait = fallback["trait"]
            polarity = fallback["polarity"]
            confidence = fallback["confidence"]

        meta.append(
            {
                "id": qid,
                "text": text,
                "trait": trait,
                "polarity": polarity,
                "confidence": round(confidence, 2),
            }
        )

    # Cache to file if path provided
    if meta_path:
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)
            print(f"[LLM] Metadata cached to {meta_path}")
        except OSError as e:
            print(f"[LLM] Warning: could not write metadata cache: {e}")

    return meta


def load_or_classify(
    questions: list[str],
    config: dict[str, Any],
    meta_path: str | Path,
) -> list[dict[str, Any]]:
    """
    Load cached metadata if available and question count matches,
    otherwise classify and cache.

    Parameters
    ----------
    questions : List of question texts
    config    : Full system config dict
    meta_path : Path to questions_meta.json

    Returns
    -------
    List of metadata dicts
    """
    meta_path = Path(meta_path)

    if meta_path.exists():
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if isinstance(cached, list) and len(cached) == len(questions):
                print(f"[LLM] Loaded {len(cached)} metadata entries from cache.")
                return cached
            else:
                print("[LLM] Cache mismatch — reclassifying.")
        except (json.JSONDecodeError, OSError) as e:
            print(f"[LLM] Cache read error: {e} — reclassifying.")

    return classify_questions(questions, config, meta_path=meta_path)
