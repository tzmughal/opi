# OPI Personality Assessment System

A desktop application that administers a structured 7-point Likert personality questionnaire, scores results using a deterministic psychometric engine, and generates a full personality report.

---

## Requirements

- Python 3.10 or higher
- Windows / macOS / Linux

---

## Setup

```powershell
# 1. Clone / copy the project into a folder, e.g. D:\OPI

# 2. Create and activate the virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Running the Application

```powershell
# Make sure the venv is active
.venv\Scripts\activate

python main.py
```

The application will launch a GUI window. The default `questions.txt` and `questions_meta.json` files bundled with the project are pre-loaded automatically.

---

## Project Structure

| File | Purpose |
|---|---|
| `main.py` | Entry point & controller — wires screens to backend |
| `ui.py` | PySide6 GUI (4-screen application) |
| `scoring_engine.py` | Deterministic scoring, consistency, bias detection |
| `llm_classifier.py` | Optional LLM classification (OpenAI / Ollama) |
| `report_generator.py` | Structured report generation & plain-text export |
| `questions.txt` | One question per line (editable) |
| `questions_meta.json` | Cached trait/polarity metadata |
| `responses.json` | Auto-saved session responses |
| `config.json` | Thresholds, weights, LLM settings |

---

## Configuration (`config.json`)

| Setting | Default | Description |
|---|---|---|
| `thresholds.recommended` | `0.72` | Minimum score for "Recommended" |
| `thresholds.borderline_lower` | `0.60` | Minimum score for "Borderline" |
| `hard_constraints.emotional_stability_min` | `0.60` | Hard floor for ES trait |
| `trait_weights.*` | See file | Relative weighting per trait |
| `penalties.extreme_answer_penalty` | `0.05` | Penalty for extreme-answer bias |
| `penalties.inconsistency_penalty_multiplier` | `0.15` | Penalty multiplier for contradictions |
| `llm.enabled` | `false` | Enable LLM classification |
| `llm.provider` | `"ollama"` | `"ollama"` or `"openai"` |
| `llm.model` | `"llama3"` | Ollama model name |
| `llm.openai_model` | `"gpt-4o-mini"` | OpenAI model name |

---

## Optional: LLM Classification

To use OpenAI for question classification:

```json
// config.json
"llm": {
  "enabled": true,
  "provider": "openai",
  "openai_model": "gpt-4o-mini"
}
```

```powershell
$env:OPENAI_API_KEY = "sk-..."
python main.py
```

To use Ollama (local):
```json
"llm": {
  "enabled": true,
  "provider": "ollama",
  "model": "llama3"
}
```

> ⚠️ LLM is used **only** for classifying question polarity and trait assignment. It **never** influences scoring or the final verdict.

---

## Multi-Phase Test Structure

The OPI Assessment is divided into multiple phases:
- **Phase 1**: 100 questions covering core traits, ISSB leadership qualities, and personal demerits.
- **Phase 2 / Phase 3**: Currently reserved for future expansions.

**Finish Early:** You can choose to skip the remainder of a phase and view your results at any time by clicking the **"Finish & See Results"** button during the test. The scoring engine automatically handles partial assessments.

---

## Adding Your Own Questions

Edit `questions.txt` — one question per line:

```
I remain calm under pressure.
I avoid responsibility when tasks are difficult.
I enjoy teamwork.
```

Then delete `questions_meta.json` to force reclassification, or update it manually following the JSON schema.

---

## Verdict Logic

| Score Range | Verdict |
|---|---|
| ≥ 0.72 | ✅ Recommended |
| 0.60 – 0.71 | ⚠️ Borderline |
| < 0.60 | ❌ Not Recommended |

**Hard constraint:** Emotional Stability must be ≥ 0.60 for a "Recommended" verdict (otherwise demoted to "Borderline").

---

## Scoring Formula

```
adjusted_score = raw_score                  (positive items)
adjusted_score = 8 - raw_score             (negative items)

trait_score = sum(adjusted) / (7 × n_questions)

base_score  = weighted_average(trait_scores)
final_score = base_score - bias_penalty - (inconsistency_multiplier × contradiction_rate)
```
