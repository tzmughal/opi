"""
main.py
-------
Application entry point for the OPI Personality Assessment System.

Responsibilities:
  - Bootstrap the Qt application
  - Load configuration and data files
  - Wire signals between GUI screens and backend modules
  - Manage session persistence (responses.json)
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QApplication, QMessageBox

# ── Local modules
from ui import MainWindow
from llm_classifier import load_or_classify
from scoring_engine import run_full_scoring
from report_generator import generate_report, export_report_text

# ---------------------------------------------------------------------------
# Paths (relative to the project root)
# ---------------------------------------------------------------------------

PROJECT_DIR   = Path(__file__).parent
CONFIG_PATH   = PROJECT_DIR / "config.json"
QUESTIONS_PATH = PROJECT_DIR / "questions.txt"
META_PATH     = PROJECT_DIR / "questions_meta.json"
RESPONSES_PATH = PROJECT_DIR / "responses.json"


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    """Load system configuration from config.json."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[main] Warning: could not load config ({e}). Using defaults.")
        return {
            "thresholds": {"recommended": 0.72, "borderline_lower": 0.60},
            "hard_constraints": {"emotional_stability_min": 0.60},
            "penalties": {
                "extreme_answer_ratio_threshold": 0.60,
                "low_variance_threshold": 0.5,
                "extreme_answer_penalty": 0.05,
                "inconsistency_penalty_multiplier": 0.15,
            },
            "trait_weights": {
                "emotional_stability": 0.25,
                "conscientiousness": 0.20,
                "integrity": 0.20,
                "initiative": 0.15,
                "sociability": 0.10,
                "discipline": 0.10,
            },
            "llm": {"enabled": False},
            "session": {"allow_back_navigation": True, "auto_save": True},
        }


def load_questions(path: Path) -> list[str]:
    """Load questions from a .txt file (one per line, skip blanks)."""
    with open(path, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]
    if not lines:
        raise ValueError(f"No questions found in {path}")
    return lines


def load_responses(path: Path = RESPONSES_PATH) -> dict[int, int]:
    """Load a previously saved response session if it exists."""
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        # Keys in JSON are strings — convert back to int
        return {int(k): int(v) for k, v in raw.items()}
    except (json.JSONDecodeError, ValueError, OSError) as e:
        print(f"[main] Warning: could not load responses ({e}). Starting fresh.")
        return {}


def save_responses(responses: dict[int, int], path: Path = RESPONSES_PATH) -> None:
    """Persist current responses to disk."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(responses, f, indent=2)
    except OSError as e:
        print(f"[main] Warning: could not save responses ({e}).")


# ---------------------------------------------------------------------------
# Application Controller
# ---------------------------------------------------------------------------

class OPIApp:
    """
    Central controller that owns data state and wires GUI screens
    to backend logic.
    """

    def __init__(self) -> None:
        self._config: dict[str, Any] = load_config()
        self._questions: list[str] = []
        self._meta: list[dict[str, Any]] = []
        self._responses: dict[int, int] = {}
        self._scoring_result: dict[str, Any] = {}
        self._report: dict[str, Any] = {}
        self._report_text: str = ""
        self._session_id: str = str(uuid.uuid4())[:8]

        self._app = QApplication(sys.argv)
        self._app.setApplicationName("OPI Personality Assessment System")
        self._app.setOrganizationName("OPI")

        self._window = MainWindow()
        self._wire_signals()
        self._prefill_defaults()

    def _wire_signals(self) -> None:
        """Connect all signals between screens."""
        ss = self._window.start_screen
        ts = self._window.test_screen
        an = self._window.analysis_screen
        rp = self._window.report_screen

        # Start → Test
        ss.start_requested.connect(self._on_start_requested)

        # Test → auto-save on each response
        ts.response_saved.connect(self._on_response_saved)

        # Test → Analysis
        ts.test_completed.connect(self._on_test_completed)

        # Analysis → Report
        an.view_report_requested.connect(self._on_view_report)

        # Analysis → restart
        an.restart_requested.connect(self._on_restart)

        # Report → Analysis (back)
        rp.back_to_analysis.connect(lambda: self._window.show_screen(2))

        # Report → restart
        rp.restart_requested.connect(self._on_restart)

    def _prefill_defaults(self) -> None:
        """Auto-fill default file paths if they exist beside main.py."""
        q_path = str(QUESTIONS_PATH) if QUESTIONS_PATH.exists() else ""
        m_path = str(META_PATH) if META_PATH.exists() else ""
        self._window.start_screen.prefill_paths(q_path, m_path)

    # ── Signal handlers

    def _on_start_requested(self, questions_path: str, meta_path: str) -> None:
        """Load questions and metadata, then show the test screen."""
        try:
            self._questions = load_questions(Path(questions_path))
        except (OSError, ValueError) as e:
            QMessageBox.critical(
                self._window,
                "File Error",
                f"Could not load questions:\n{e}",
            )
            return

        # Resolve metadata
        effective_meta_path = Path(meta_path) if meta_path else META_PATH
        try:
            self._meta = load_or_classify(
                self._questions,
                self._config,
                effective_meta_path,
            )
        except Exception as e:
            QMessageBox.warning(
                self._window,
                "Metadata Warning",
                f"Metadata could not be loaded or classified ({e}).\n"
                "Using rule-based classification.",
            )
            from llm_classifier import classify_questions
            self._meta = classify_questions(self._questions, self._config)

        # Start fresh for every new assessment
        self._responses = {}

        # Build question list for the test screen
        questions_for_ui = [
            {
                "id":      item["id"],
                "text":    item["text"],
                "trait":   item.get("trait", ""),
                "polarity": item.get("polarity", "positive"),
                "phase":   item.get("phase", 1),
            }
            for item in self._meta
        ]

        allow_back = self._config.get("session", {}).get("allow_back_navigation", True)
        self._window.test_screen.load_session(questions_for_ui, self._responses, allow_back)
        self._window.show_screen(1)

    def _on_response_saved(self, question_id: int, raw_score: int) -> None:
        """Auto-save each response to disk."""
        self._responses[question_id] = raw_score
        auto_save = self._config.get("session", {}).get("auto_save", True)
        if auto_save:
            save_responses(self._responses)

    def _on_test_completed(self) -> None:
        """All questions answered — run scoring and show analysis screen."""
        # Retrieve final responses from the test screen
        self._responses = self._window.test_screen.get_responses()
        save_responses(self._responses)

        # Run full scoring pipeline
        try:
            self._scoring_result = run_full_scoring(
                self._responses,
                self._meta,
                self._config,
            )
        except Exception as e:
            QMessageBox.critical(
                self._window,
                "Scoring Error",
                f"An error occurred during scoring:\n{e}",
            )
            return

        # Generate report
        try:
            self._report = generate_report(
                self._responses,
                self._meta,
                self._scoring_result,
                session_id=self._session_id,
            )
            self._report_text = export_report_text(self._report)
        except Exception as e:
            QMessageBox.warning(
                self._window,
                "Report Warning",
                f"Report generation encountered an issue:\n{e}",
            )
            self._report = {}
            self._report_text = f"Report generation failed: {e}"

        self._window.analysis_screen.load_results(self._scoring_result, self._report)
        self._window.show_screen(2)

    def _on_view_report(self) -> None:
        """Navigate from Analysis → Report screen."""
        if self._report:
            self._window.report_screen.load_report(self._report, self._report_text)
        self._window.show_screen(3)

    def _on_restart(self) -> None:
        """Clear session and return to Start screen."""
        self._questions = []
        self._meta = []
        self._responses = {}
        self._scoring_result = {}
        self._report = {}
        self._report_text = ""
        self._session_id = str(uuid.uuid4())[:8]
        # Clear saved responses
        if RESPONSES_PATH.exists():
            RESPONSES_PATH.unlink(missing_ok=True)
        self._window.show_screen(0)

    # ── Run

    def run(self) -> int:
        self._window.show()
        return self._app.exec()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    controller = OPIApp()
    sys.exit(controller.run())


if __name__ == "__main__":
    main()
