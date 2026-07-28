"""
ui.py
-----
PySide6 GUI for the OPI Personality Assessment System.

Four-screen application using QStackedWidget:
  Screen 0 — StartScreen
  Screen 1 — TestScreen
  Screen 2 — AnalysisScreen
  Screen 3 — ReportScreen
"""

from __future__ import annotations

import json
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QTimer,
    Signal,
    QRect,
    QSize,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QBrush,
    QPixmap,
    QIcon,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QMessageBox,
    QTextEdit,
    QGridLayout,
)

# ---------------------------------------------------------------------------
# Design System — Tokens
# ---------------------------------------------------------------------------

COLORS = {
    "bg":           "#0a0e1a",
    "surface":      "#111827",
    "surface2":     "#1a2235",
    "border":       "#1e2d45",
    "border_light": "#2d3f5a",
    "accent":       "#7C3AED",
    "accent_light": "#9D5CF0",
    "accent_dim":   "#3b1f7a",
    "text_primary": "#f0f4ff",
    "text_secondary": "#8899bb",
    "text_muted":   "#4a5a7a",
    "success":      "#22c55e",
    "warning":      "#f59e0b",
    "danger":       "#ef4444",
    "info":         "#38bdf8",
    "white":        "#ffffff",
}

LIKERT_COLORS = [
    "#ef4444",  # 1 — Strongly Disagree
    "#f97316",  # 2 — Slightly Disagree
    "#f59e0b",  # 3 — Disagree
    "#94a3b8",  # 4 — Neutral
    "#4ade80",  # 5 — Agree
    "#22c55e",  # 6 — Slightly Agree
    "#16a34a",  # 7 — Strongly Agree
]

LIKERT_LABELS = [
    "Strongly\nDisagree",
    "Slightly\nDisagree",
    "Disagree",
    "Neutral",
    "Agree",
    "Slightly\nAgree",
    "Strongly\nAgree",
]

TRAIT_COLORS = {
    "emotional_stability": "#7C3AED",
    "conscientiousness":   "#2563EB",
    "integrity":           "#059669",
    "initiative":          "#D97706",
    "sociability":         "#DB2777",
    "discipline":          "#0891B2",
}

GLOBAL_STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {COLORS['bg']};
    color: {COLORS['text_primary']};
    font-family: 'Segoe UI', sans-serif;
}}
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: {COLORS['surface']};
    width: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {COLORS['accent_dim']};
    border-radius: 3px;
    min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar:horizontal {{
    height: 0px;
}}
"""


# ---------------------------------------------------------------------------
# Reusable Widget Components
# ---------------------------------------------------------------------------

class GlassCard(QFrame):
    """Semi-transparent card with rounded corners and subtle border."""

    def __init__(
        self,
        parent: QWidget | None = None,
        padding: int = 24,
        radius: int = 16,
    ) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: {radius}px;
                padding: {padding}px;
            }}
        """)


class GradientButton(QPushButton):
    """Purple gradient primary action button."""

    def __init__(
        self,
        text: str,
        parent: QWidget | None = None,
        height: int = 48,
        font_size: int = 14,
    ) -> None:
        super().__init__(text, parent)
        self.setFixedHeight(height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['accent']},
                    stop:1 {COLORS['accent_light']}
                );
                color: {COLORS['white']};
                border: none;
                border-radius: 12px;
                font-size: {font_size}px;
                font-weight: 700;
                letter-spacing: 0.5px;
                padding: 0 28px;
            }}
            QPushButton:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['accent_light']},
                    stop:1 #b880ff
                );
            }}
            QPushButton:pressed {{
                background: {COLORS['accent_dim']};
            }}
            QPushButton:disabled {{
                background: {COLORS['surface2']};
                color: {COLORS['text_muted']};
            }}
        """)


class OutlineButton(QPushButton):
    """Secondary outline button."""

    def __init__(
        self,
        text: str,
        parent: QWidget | None = None,
        height: int = 40,
        font_size: int = 13,
    ) -> None:
        super().__init__(text, parent)
        self.setFixedHeight(height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 10px;
                font-size: {font_size}px;
                padding: 0 20px;
            }}
            QPushButton:hover {{
                background: {COLORS['surface2']};
                color: {COLORS['text_primary']};
                border-color: {COLORS['accent']};
            }}
            QPushButton:pressed {{
                background: {COLORS['accent_dim']};
            }}
        """)


class LikertButton(QPushButton):
    """Single Likert-scale response button (1–7)."""

    def __init__(
        self,
        value: int,
        label: str,
        color: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.value = value
        self._color = color
        self._selected = False
        self.setText(f"{value}\n{label}")
        self.setFixedSize(88, 80)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_style()

    def _refresh_style(self) -> None:
        if self._selected:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self._color};
                    color: white;
                    border: 2px solid {self._color};
                    border-radius: 12px;
                    font-size: 11px;
                    font-weight: 700;
                    outline: none;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['surface2']};
                    color: {COLORS['text_secondary']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 12px;
                    font-size: 11px;
                    font-weight: 500;
                    outline: none;
                }}
                QPushButton:hover {{
                    background-color: {self._color}33;
                    color: white;
                    border: 1px solid {self._color};
                }}
            """)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self._refresh_style()


class TraitBar(QWidget):
    """Animated horizontal progress bar for a single trait score."""

    def __init__(
        self,
        label: str,
        score: float,
        color: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.label = label
        self.target_score = score
        self.color = color
        self._current_score = 0.0
        self.setFixedHeight(52)
        self.setMinimumWidth(300)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Label
        painter.setPen(QColor(COLORS["text_secondary"]))
        font = painter.font()
        font.setPointSize(9)
        font.setWeight(QFont.Weight.Medium)
        painter.setFont(font)
        painter.drawText(QRect(0, 0, 180, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.label)

        # Percentage
        painter.setPen(QColor(COLORS["text_primary"]))
        font2 = painter.font()
        font2.setPointSize(10)
        font2.setWeight(QFont.Weight.Bold)
        painter.setFont(font2)
        painter.drawText(
            QRect(w - 60, 0, 60, 20),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"{self._current_score:.0%}",
        )

        # Background track
        track_rect = QRect(0, 26, w, 16)
        path_bg = QPainterPath()
        path_bg.addRoundedRect(track_rect, 8, 8)
        painter.fillPath(path_bg, QColor(COLORS["surface2"]))

        # Filled bar
        fill_w = int(self._current_score * w)
        if fill_w > 0:
            fill_rect = QRect(0, 26, fill_w, 16)
            path_fill = QPainterPath()
            path_fill.addRoundedRect(fill_rect, 8, 8)

            grad = QLinearGradient(0, 0, fill_w, 0)
            grad.setColorAt(0, QColor(self.color).darker(110))
            grad.setColorAt(1, QColor(self.color))
            painter.fillPath(path_fill, QBrush(grad))

        painter.end()

    def animate_to(self, score: float) -> None:
        """Animate the bar from 0 to target score."""
        self.target_score = score
        steps = 40
        delta = score / steps

        def tick(step: list) -> None:
            step[0] += 1
            self._current_score = min(delta * step[0], score)
            self.update()
            if step[0] < steps:
                QTimer.singleShot(16, lambda: tick(step))

        tick([0])


class VerdictBadge(QLabel):
    """Large colored badge for the final verdict."""

    STYLE_MAP = {
        "Recommended":     (COLORS["success"],   "#052e16"),
        "Borderline":      (COLORS["warning"],   "#431407"),
        "Not Recommended": (COLORS["danger"],    "#450a0a"),
    }

    def __init__(self, verdict: str, parent: QWidget | None = None) -> None:
        super().__init__(verdict, parent)
        fg, bg = self.STYLE_MAP.get(verdict, ("#888", "#111"))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(56)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                color: {fg};
                border: 2px solid {fg};
                border-radius: 12px;
                font-size: 20px;
                font-weight: 800;
                letter-spacing: 1px;
                padding: 0 32px;
            }}
        """)


# ---------------------------------------------------------------------------
# Screen 0 — Start Screen
# ---------------------------------------------------------------------------

class StartScreen(QWidget):
    """Welcome/setup screen. Emits start_requested when user is ready."""

    start_requested = Signal(str, str)  # (questions_path, meta_path)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._questions_path: str = ""
        self._meta_path: str = ""
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Gradient header
        header = QWidget()
        header.setFixedHeight(200)
        header.setStyleSheet(f"""
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:1,
                stop:0 #1a0533,
                stop:0.5 #0a0e1a,
                stop:1 #001528
            );
        """)
        h_lay = QVBoxLayout(header)
        h_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("OPI")
        title.setStyleSheet(f"""
            color: {COLORS['accent_light']};
            font-size: 56px;
            font-weight: 900;
            letter-spacing: 12px;
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("Personality Assessment System")
        subtitle.setStyleSheet(f"""
            color: {COLORS['text_secondary']};
            font-size: 16px;
            font-weight: 400;
            letter-spacing: 3px;
        """)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        h_lay.addWidget(title)
        h_lay.addWidget(subtitle)
        root.addWidget(header)

        # Body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        body = QWidget()
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(60, 40, 60, 40)
        body_lay.setSpacing(20)
        body_lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Info card
        info_card = GlassCard(radius=14)
        info_layout = QVBoxLayout(info_card)
        info_layout.setSpacing(12)

        info_title = QLabel("About This Assessment")
        info_title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 15px; font-weight: 700;")
        info_layout.addWidget(info_title)

        info_text = QLabel(
            "This is a structured psychometric-style questionnaire designed to evaluate "
            "personality traits across six professional competency domains. "
            "Please respond honestly — all questions use a 7-point scale from "
            "Strongly Disagree to Strongly Agree. There are no right or wrong answers."
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px; line-height: 1.6;")
        info_layout.addWidget(info_text)

        # Trait pills
        traits_row = QHBoxLayout()
        traits_row.setSpacing(8)
        trait_names = [
            ("😌", "Emotional Stability"),
            ("📋", "Conscientiousness"),
            ("⚖️",  "Integrity"),
            ("🚀", "Initiative"),
            ("🤝", "Sociability"),
            ("🎯", "Discipline"),
        ]
        for icon, name in trait_names:
            pill = QLabel(f"{icon}  {name}")
            pill.setStyleSheet(f"""
                background-color: {COLORS['surface2']};
                color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border']};
                border-radius: 20px;
                padding: 4px 12px;
                font-size: 11px;
            """)
            traits_row.addWidget(pill)
        traits_row.addStretch()
        info_layout.addLayout(traits_row)
        body_lay.addWidget(info_card)

        # File selection card
        file_card = GlassCard(radius=14)
        file_layout = QVBoxLayout(file_card)
        file_layout.setSpacing(16)

        file_title = QLabel("Load Assessment Files")
        file_title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 15px; font-weight: 700;")
        file_layout.addWidget(file_title)

        # Questions file row
        q_row = QHBoxLayout()
        self._q_label = QLabel("No file selected")
        self._q_label.setStyleSheet(f"""
            color: {COLORS['text_muted']};
            font-size: 12px;
            background: {COLORS['surface2']};
            border: 1px solid {COLORS['border']};
            border-radius: 8px;
            padding: 8px 14px;
        """)
        self._q_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        q_btn = OutlineButton("Browse questions.txt", height=36)
        q_btn.setObjectName("btn_browse_questions")
        q_btn.clicked.connect(self._browse_questions)
        q_row.addWidget(self._q_label)
        q_row.addWidget(q_btn)
        file_layout.addLayout(q_row)

        # Meta file row
        m_row = QHBoxLayout()
        self._m_label = QLabel("No file selected (optional — will auto-classify)")
        self._m_label.setStyleSheet(f"""
            color: {COLORS['text_muted']};
            font-size: 12px;
            background: {COLORS['surface2']};
            border: 1px solid {COLORS['border']};
            border-radius: 8px;
            padding: 8px 14px;
        """)
        self._m_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        m_btn = OutlineButton("Browse metadata", height=36)
        m_btn.setObjectName("btn_browse_meta")
        m_btn.clicked.connect(self._browse_meta)
        m_row.addWidget(self._m_label)
        m_row.addWidget(m_btn)
        file_layout.addLayout(m_row)

        body_lay.addWidget(file_card)

        # Status bar
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body_lay.addWidget(self._status_label)

        # Start button
        self._start_btn = GradientButton("Begin Assessment  →", height=56, font_size=15)
        self._start_btn.setObjectName("btn_start")
        self._start_btn.setEnabled(False)
        self._start_btn.clicked.connect(self._on_start)
        body_lay.addWidget(self._start_btn)

        body_lay.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll)

    def _browse_questions(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Questions File", str(Path.cwd()), "Text Files (*.txt)"
        )
        if path:
            self._questions_path = path
            fname = Path(path).name
            self._q_label.setText(f"✓  {fname}")
            self._q_label.setStyleSheet(f"""
                color: {COLORS['success']};
                font-size: 12px;
                background: {COLORS['surface2']};
                border: 1px solid {COLORS['success']}55;
                border-radius: 8px;
                padding: 8px 14px;
            """)
            self._check_ready()

    def _browse_meta(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Metadata File", str(Path.cwd()), "JSON Files (*.json)"
        )
        if path:
            self._meta_path = path
            fname = Path(path).name
            self._m_label.setText(f"✓  {fname}")
            self._m_label.setStyleSheet(f"""
                color: {COLORS['info']};
                font-size: 12px;
                background: {COLORS['surface2']};
                border: 1px solid {COLORS['info']}55;
                border-radius: 8px;
                padding: 8px 14px;
            """)

    def _check_ready(self) -> None:
        if self._questions_path:
            self._start_btn.setEnabled(True)
            self._status_label.setText("✓ Ready to begin")
            self._status_label.setStyleSheet(f"color: {COLORS['success']}; font-size: 12px;")

    def _on_start(self) -> None:
        self.start_requested.emit(self._questions_path, self._meta_path)

    def prefill_paths(self, q_path: str, m_path: str) -> None:
        """Pre-fill paths (called from main.py on startup if defaults exist)."""
        if q_path and Path(q_path).exists():
            self._questions_path = q_path
            self._q_label.setText(f"✓  {Path(q_path).name}")
            self._q_label.setStyleSheet(f"""
                color: {COLORS['success']};
                font-size: 12px;
                background: {COLORS['surface2']};
                border: 1px solid {COLORS['success']}55;
                border-radius: 8px;
                padding: 8px 14px;
            """)
        if m_path and Path(m_path).exists():
            self._meta_path = m_path
            self._m_label.setText(f"✓  {Path(m_path).name}")
            self._m_label.setStyleSheet(f"""
                color: {COLORS['info']};
                font-size: 12px;
                background: {COLORS['surface2']};
                border: 1px solid {COLORS['info']}55;
                border-radius: 8px;
                padding: 8px 14px;
            """)
        self._check_ready()


# ---------------------------------------------------------------------------
# Screen 1 — Test Screen
# ---------------------------------------------------------------------------

class TestScreen(QWidget):
    """Presents questions one at a time with a 7-button Likert scale."""

    response_saved = Signal(int, int)       # (question_id, raw_score)
    test_completed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._questions: list[dict] = []     # [{id, text, trait, polarity}]
        self._responses: dict[int, int] = {}
        self._current_index: int = 0
        self._selected_value: int | None = None
        self._allow_back: bool = True
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top bar
        topbar = QWidget()
        topbar.setFixedHeight(64)
        topbar.setStyleSheet(f"background: {COLORS['surface']}; border-bottom: 1px solid {COLORS['border']};")
        tb_lay = QHBoxLayout(topbar)
        tb_lay.setContentsMargins(24, 0, 24, 0)

        opi_label = QLabel("OPI Assessment")
        opi_label.setStyleSheet(f"color: {COLORS['accent_light']}; font-size: 14px; font-weight: 700; letter-spacing: 2px;")

        self._progress_label = QLabel("Question 1 of 30")
        self._progress_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._trait_label = QLabel("")
        self._trait_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        self._trait_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        tb_lay.addWidget(opi_label)
        tb_lay.addStretch()
        tb_lay.addWidget(self._progress_label)
        tb_lay.addStretch()
        tb_lay.addWidget(self._trait_label)
        root.addWidget(topbar)

        # ── Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(4)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {COLORS['surface2']};
                border: none;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {COLORS['accent']}, stop:1 {COLORS['accent_light']});
            }}
        """)
        root.addWidget(self._progress_bar)

        # ── Stacked area
        self._test_stack = QStackedWidget()
        self._test_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # ── Question Page
        self._question_page = QWidget()
        content_lay = QVBoxLayout(self._question_page)
        content_lay.setContentsMargins(60, 40, 60, 40)
        content_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_lay.setSpacing(32)

        # Question card
        q_card = GlassCard(radius=20, padding=40)
        q_card.setMinimumHeight(160)
        q_card_lay = QVBoxLayout(q_card)
        q_card_lay.setSpacing(16)

        q_num_row = QHBoxLayout()
        self._q_number = QLabel("Q1")
        self._q_number.setStyleSheet(f"""
            color: {COLORS['accent']};
            font-size: 13px;
            font-weight: 700;
            background: {COLORS['accent_dim']};
            border-radius: 6px;
            padding: 2px 10px;
        """)
        q_num_row.addWidget(self._q_number)
        q_num_row.addStretch()
        q_card_lay.addLayout(q_num_row)

        self._question_text = QLabel("Loading question...")
        self._question_text.setWordWrap(True)
        self._question_text.setStyleSheet(f"""
            color: {COLORS['text_primary']};
            font-size: 20px;
            font-weight: 500;
            line-height: 1.7;
        """)
        self._question_text.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        q_card_lay.addWidget(self._question_text)

        content_lay.addWidget(q_card)

        # Scale label row
        scale_header = QHBoxLayout()
        left_label = QLabel("← Disagree")
        left_label.setStyleSheet(f"color: {COLORS['danger']}; font-size: 12px;")
        right_label = QLabel("Agree →")
        right_label.setStyleSheet(f"color: {COLORS['success']}; font-size: 12px;")
        scale_header.addWidget(left_label)
        scale_header.addStretch()
        scale_header.addWidget(right_label)
        content_lay.addLayout(scale_header)

        # Likert buttons row
        self._likert_buttons: list[LikertButton] = []
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        for i in range(7):
            btn = LikertButton(i + 1, LIKERT_LABELS[i], LIKERT_COLORS[i])
            btn.setObjectName(f"btn_likert_{i+1}")
            btn.clicked.connect(lambda checked, v=i + 1: self._on_likert_select(v))
            btn_row.addWidget(btn)
            self._likert_buttons.append(btn)

        content_lay.addLayout(btn_row)

        # Nav buttons
        nav_row = QHBoxLayout()
        nav_row.setSpacing(12)

        self._finish_early_btn = OutlineButton("Finish & See Results", height=44)
        self._finish_early_btn.setObjectName("btn_finish_early")
        self._finish_early_btn.clicked.connect(self.test_completed.emit)

        self._back_btn = OutlineButton("← Back", height=44)
        self._back_btn.setObjectName("btn_back")
        self._back_btn.setEnabled(False)
        self._back_btn.clicked.connect(self._go_back)

        self._next_btn = GradientButton("Next →", height=44, font_size=13)
        self._next_btn.setObjectName("btn_next")
        self._next_btn.setEnabled(False)
        self._next_btn.clicked.connect(self._go_next)

        nav_row.addWidget(self._finish_early_btn)
        nav_row.addStretch()
        nav_row.addWidget(self._back_btn)
        nav_row.addWidget(self._next_btn)
        content_lay.addLayout(nav_row)

        self._test_stack.addWidget(self._question_page)

        # ── Phase Break Page
        self._phase_break_page = QWidget()
        pb_lay = QVBoxLayout(self._phase_break_page)
        pb_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pb_lay.setSpacing(24)

        pb_title = QLabel("Phase Complete! 🎉")
        pb_title.setStyleSheet(f"color: {COLORS['success']}; font-size: 28px; font-weight: 800;")
        pb_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self._pb_stats = QLabel("Loading stats...")
        self._pb_stats.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 16px;")
        self._pb_stats.setAlignment(Qt.AlignmentFlag.AlignCenter)

        pb_btn_row = QHBoxLayout()
        pb_btn_row.setSpacing(16)
        pb_btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        view_res_btn = OutlineButton("View Results Now", height=48)
        view_res_btn.clicked.connect(self.test_completed.emit)

        self._cont_btn = GradientButton("Continue  →", height=48)
        self._cont_btn.clicked.connect(self._continue_phase)

        pb_btn_row.addWidget(view_res_btn)
        pb_btn_row.addWidget(self._cont_btn)

        pb_lay.addStretch()
        pb_lay.addWidget(pb_title)
        pb_lay.addWidget(self._pb_stats)
        pb_lay.addLayout(pb_btn_row)
        pb_lay.addStretch()

        self._test_stack.addWidget(self._phase_break_page)

        root.addWidget(self._test_stack)

    # ── Public API

    def load_session(
        self,
        questions: list[dict],
        existing_responses: dict[int, int],
        allow_back: bool = True,
    ) -> None:
        import random
        phases = {}
        for q in questions:
            p = q.get("phase", 1)
            phases.setdefault(p, []).append(q)
            
        shuffled_questions = []
        for p in sorted(phases.keys()):
            q_list = phases[p]
            random.shuffle(q_list)
            shuffled_questions.extend(q_list)
            
        self._questions = shuffled_questions
        self._responses = dict(existing_responses)
        self._allow_back = allow_back
        self._current_index = 0
        self._progress_bar.setMaximum(len(questions))
        self._render_current()

    def get_responses(self) -> dict[int, int]:
        return dict(self._responses)

    # ── Internal

    def _render_current(self) -> None:
        if not self._questions:
            return

        self._test_stack.setCurrentWidget(self._question_page)

        q = self._questions[self._current_index]
        total = len(self._questions)
        idx = self._current_index
        qid = q["id"]
        phase = q.get("phase", 1)

        self._progress_label.setText(f"Phase {phase} of 3 · Question {idx + 1} of {total}")
        self._progress_bar.setValue(idx + 1)
        self._q_number.setText(f"Q{qid}")
        self._question_text.setText(q["text"])

        trait = q.get("trait", "")
        self._trait_label.setText(trait.replace("_", " ").title() if trait else "")

        # Restore selection if already answered
        saved = self._responses.get(qid)
        self._selected_value = saved
        for btn in self._likert_buttons:
            btn.set_selected(btn.value == saved)

        self._back_btn.setEnabled(self._allow_back and idx > 0)
        self._next_btn.setEnabled(saved is not None)

        is_last = idx == total - 1
        if is_last:
            self._next_btn.setText(f"Complete Phase {phase}  ✓")
        else:
            self._next_btn.setText("Next  →")

    def _on_likert_select(self, value: int) -> None:
        self._selected_value = value
        for btn in self._likert_buttons:
            btn.set_selected(btn.value == value)
            btn.clearFocus()

        qid = self._questions[self._current_index]["id"]
        is_first_time = qid not in self._responses
        
        self._responses[qid] = value
        self.response_saved.emit(qid, value)
        self._next_btn.setEnabled(True)
        
        if is_first_time:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(250, self._go_next)

    def _go_back(self) -> None:
        if self._current_index > 0:
            self._current_index -= 1
            self._render_current()

    def _continue_phase(self) -> None:
        self._current_index += 1
        self._render_current()

    def _go_next(self) -> None:
        total = len(self._questions)
        current_q = self._questions[self._current_index]
        
        if self._current_index < total - 1:
            next_q = self._questions[self._current_index + 1]
            if current_q.get("phase", 1) != next_q.get("phase", 1):
                # Phase transition!
                next_phase = next_q.get("phase", 2)
                self._pb_stats.setText(f"You answered {len(self._responses)} questions so far.")
                self._cont_btn.setText(f"Continue to Phase {next_phase} →")
                self._cont_btn.show()
                self._test_stack.setCurrentWidget(self._phase_break_page)
            else:
                self._current_index += 1
                self._render_current()
        else:
            # End of test reached
            answered = len(self._responses)
            self._pb_stats.setText(f"You completed the test! ({answered}/{total} answered)")
            self._cont_btn.hide()
            self._test_stack.setCurrentWidget(self._phase_break_page)


# ---------------------------------------------------------------------------
# Screen 2 — Analysis Screen
# ---------------------------------------------------------------------------

class AnalysisScreen(QWidget):
    """Displays trait scores, consistency, and final verdict with animations."""

    view_report_requested = Signal()
    restart_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._trait_bars: list[TraitBar] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        body = QWidget()
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(60, 40, 60, 40)
        body_lay.setSpacing(24)

        # Title
        title = QLabel("Assessment Results")
        title.setStyleSheet(f"""
            color: {COLORS['text_primary']};
            font-size: 28px;
            font-weight: 800;
            letter-spacing: 1px;
        """)
        body_lay.addWidget(title)

        subtitle = QLabel("Deterministic scoring based on your responses")
        subtitle.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 13px;")
        body_lay.addWidget(subtitle)

        # Verdict badge (populated in load_results)
        self._verdict_badge = VerdictBadge("Analyzing...")
        body_lay.addWidget(self._verdict_badge)

        # Score row
        score_row = QHBoxLayout()
        score_row.setSpacing(16)

        self._final_score_card = self._make_score_card("Final Score", "—", COLORS["accent"])
        self._base_score_card  = self._make_score_card("Base Score",  "—", COLORS["info"])
        self._consistency_card = self._make_score_card("Consistency", "—", COLORS["success"])
        self._bias_card        = self._make_score_card("Bias Penalty","—", COLORS["warning"])

        score_row.addWidget(self._final_score_card[0])
        score_row.addWidget(self._base_score_card[0])
        score_row.addWidget(self._consistency_card[0])
        score_row.addWidget(self._bias_card[0])
        body_lay.addLayout(score_row)

        # Trait scores card
        trait_card = GlassCard(radius=16)
        trait_layout = QVBoxLayout(trait_card)
        trait_layout.setSpacing(20)

        trait_title = QLabel("Trait Breakdown")
        trait_title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 16px; font-weight: 700;")
        trait_layout.addWidget(trait_title)

        self._trait_bars_container = QVBoxLayout()
        self._trait_bars_container.setSpacing(16)
        trait_layout.addLayout(self._trait_bars_container)
        body_lay.addWidget(trait_card)

        # Flags card
        self._flags_card = GlassCard(radius=14)
        self._flags_layout = QVBoxLayout(self._flags_card)
        self._flags_title = QLabel("Response Quality Flags")
        self._flags_title.setStyleSheet(f"color: {COLORS['warning']}; font-size: 14px; font-weight: 700;")
        self._flags_layout.addWidget(self._flags_title)
        self._flags_label = QLabel("None detected.")
        self._flags_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        self._flags_layout.addWidget(self._flags_label)
        body_lay.addWidget(self._flags_card)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        restart_btn = OutlineButton("↩  Start Over", height=48)
        restart_btn.setObjectName("btn_restart")
        restart_btn.clicked.connect(self.restart_requested.emit)

        report_btn = GradientButton("View Full Report  →", height=48, font_size=13)
        report_btn.setObjectName("btn_view_report")
        report_btn.clicked.connect(self.view_report_requested.emit)

        btn_row.addWidget(restart_btn)
        btn_row.addStretch()
        btn_row.addWidget(report_btn)
        body_lay.addLayout(btn_row)

        body_lay.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll)

    def _make_score_card(
        self, label: str, value: str, accent: str
    ) -> tuple[QFrame, QLabel]:
        card = GlassCard(radius=12, padding=16)
        lay = QVBoxLayout(card)
        lay.setSpacing(8)
        lay.setContentsMargins(16, 16, 16, 16)

        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; font-weight: 600; letter-spacing: 1px;")
        val_lbl = QLabel(value)
        val_lbl.setStyleSheet(f"color: {accent}; font-size: 22px; font-weight: 800;")

        lay.addWidget(lbl)
        lay.addWidget(val_lbl)
        return card, val_lbl

    def load_results(self, scoring_result: dict[str, Any], report: dict[str, Any]) -> None:
        """Populate the screen with scoring results and animate trait bars."""
        verdict_info = scoring_result["verdict"]
        verdict_label = verdict_info["verdict"]

        self._verdict_badge.setText(verdict_label)
        # Re-apply style
        fg_map = {"Recommended": COLORS["success"], "Borderline": COLORS["warning"], "Not Recommended": COLORS["danger"]}
        bg_map = {"Recommended": "#052e16", "Borderline": "#431407", "Not Recommended": "#450a0a"}
        fg = fg_map.get(verdict_label, "#888")
        bg = bg_map.get(verdict_label, "#111")
        self._verdict_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                color: {fg};
                border: 2px solid {fg};
                border-radius: 12px;
                font-size: 20px;
                font-weight: 800;
                letter-spacing: 1px;
                padding: 0 32px;
            }}
        """)

        _, fs_lbl = self._final_score_card
        _, bs_lbl = self._base_score_card
        _, cs_lbl = self._consistency_card
        _, bp_lbl = self._bias_card

        fs_lbl.setText(f"{scoring_result['final_score']:.3f}")
        bs_lbl.setText(f"{scoring_result['base_score']:.3f}")
        cs_lbl.setText(f"{scoring_result['consistency']['consistency_score']:.1%}")
        bp_lbl.setText(f"-{scoring_result['bias']['penalty']:.3f}")

        # Clear old trait bars
        while self._trait_bars_container.count():
            item = self._trait_bars_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._trait_bars.clear()

        trait_scores = scoring_result["trait_scores"]
        trait_labels = {
            "emotional_stability": "Emotional Stability",
            "conscientiousness":   "Conscientiousness",
            "integrity":           "Integrity",
            "initiative":          "Initiative",
            "sociability":         "Sociability",
            "discipline":          "Discipline",
        }

        for trait, label in trait_labels.items():
            score = trait_scores.get(trait)
            if score is None:
                continue
                
            color = TRAIT_COLORS.get(trait, COLORS["accent"])
            bar = TraitBar(label, score, color)
            self._trait_bars_container.addWidget(bar)
            self._trait_bars.append(bar)

        # Animate after 200ms
        QTimer.singleShot(200, self._animate_bars)

        # Flags
        flags = scoring_result["bias"].get("flags", [])
        if flags:
            self._flags_card.show()
            flags_text = "  •  ".join(f.replace("_", " ").title() for f in flags)
            self._flags_label.setText(flags_text)
        else:
            self._flags_card.hide()

    def _animate_bars(self) -> None:
        for bar in self._trait_bars:
            bar.animate_to(bar.target_score)


# ---------------------------------------------------------------------------
# Screen 3 — Report Screen
# ---------------------------------------------------------------------------

class ReportScreen(QWidget):
    """Full report display with export functionality."""

    back_to_analysis = Signal()
    restart_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._report_text: str = ""
        self._setup_ui()

    @staticmethod
    def _clear_layout(layout: "QVBoxLayout") -> None:
        """Remove all widgets from a layout."""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top bar
        topbar = QWidget()
        topbar.setFixedHeight(64)
        topbar.setStyleSheet(f"background: {COLORS['surface']}; border-bottom: 1px solid {COLORS['border']};")
        tb_lay = QHBoxLayout(topbar)
        tb_lay.setContentsMargins(24, 0, 24, 0)

        title_lbl = QLabel("Full Personality Report")
        title_lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 16px; font-weight: 700;")

        back_btn = OutlineButton("← Analysis", height=36, font_size=12)
        back_btn.setObjectName("btn_back_to_analysis")
        back_btn.clicked.connect(self.back_to_analysis.emit)

        export_btn = GradientButton("Export .txt", height=36, font_size=12)
        export_btn.setObjectName("btn_export")
        export_btn.clicked.connect(self._export)

        restart_btn = OutlineButton("↩ Start Over", height=36, font_size=12)
        restart_btn.setObjectName("btn_report_restart")
        restart_btn.clicked.connect(self.restart_requested.emit)

        tb_lay.addWidget(back_btn)
        tb_lay.addSpacing(12)
        tb_lay.addWidget(title_lbl)
        tb_lay.addStretch()
        tb_lay.addWidget(export_btn)
        tb_lay.addSpacing(8)
        tb_lay.addWidget(restart_btn)
        root.addWidget(topbar)

        # Report content
        body = QWidget()
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(60, 32, 60, 32)
        body_lay.setSpacing(20)

        # Verdict summary card
        self._verdict_card = GlassCard(radius=16)
        vc_lay = QVBoxLayout(self._verdict_card)
        self._verdict_lbl = QLabel("VERDICT")
        self._verdict_lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 22px; font-weight: 800;")
        self._verdict_desc = QLabel("")
        self._verdict_desc.setWordWrap(True)
        self._verdict_desc.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 14px;")
        self._verdict_reason = QLabel("")
        self._verdict_reason.setWordWrap(True)
        self._verdict_reason.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        vc_lay.addWidget(self._verdict_lbl)
        vc_lay.addWidget(self._verdict_desc)
        vc_lay.addWidget(self._verdict_reason)
        body_lay.addWidget(self._verdict_card)

        # Summary card
        self._summary_card = GlassCard(radius=14)
        sc_lay = QVBoxLayout(self._summary_card)
        sc_title = QLabel("Summary")
        sc_title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 15px; font-weight: 700;")
        self._summary_lbl = QLabel("")
        self._summary_lbl.setWordWrap(True)
        self._summary_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px; line-height: 1.6;")
        sc_lay.addWidget(sc_title)
        sc_lay.addWidget(self._summary_lbl)
        body_lay.addWidget(self._summary_card)

        # Strengths card
        self._strengths_card = GlassCard(radius=14)
        self._strengths_layout = QVBoxLayout(self._strengths_card)
        str_title = QLabel("✔  Strengths")
        str_title.setStyleSheet(f"color: {COLORS['success']}; font-size: 15px; font-weight: 700;")
        self._strengths_layout.addWidget(str_title)
        self._strengths_content = QLabel("")
        self._strengths_content.setWordWrap(True)
        self._strengths_content.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        self._strengths_layout.addWidget(self._strengths_content)
        body_lay.addWidget(self._strengths_card)

        # Weaknesses card
        self._weaknesses_card = GlassCard(radius=14)
        self._weaknesses_layout = QVBoxLayout(self._weaknesses_card)
        wk_title = QLabel("✘  Development Areas")
        wk_title.setStyleSheet(f"color: {COLORS['danger']}; font-size: 15px; font-weight: 700;")
        self._weaknesses_layout.addWidget(wk_title)
        self._weaknesses_content = QLabel("")
        self._weaknesses_content.setWordWrap(True)
        self._weaknesses_content.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        self._weaknesses_layout.addWidget(self._weaknesses_content)
        body_lay.addWidget(self._weaknesses_card)

        # Merits card
        self._merits_card = GlassCard(radius=14)
        self._merits_layout = QVBoxLayout(self._merits_card)
        merits_header = QHBoxLayout()
        merits_icon = QLabel("🏆")
        merits_icon.setStyleSheet("font-size: 20px;")
        merits_title_lbl = QLabel("Your Merits")
        merits_title_lbl.setStyleSheet(
            f"color: {COLORS['success']}; font-size: 16px; font-weight: 800; letter-spacing: 0.5px;"
        )
        merits_header.addWidget(merits_icon)
        merits_header.addSpacing(8)
        merits_header.addWidget(merits_title_lbl)
        merits_header.addStretch()
        self._merits_layout.addLayout(merits_header)
        self._merits_container = QVBoxLayout()
        self._merits_container.setSpacing(10)
        self._merits_layout.addLayout(self._merits_container)
        body_lay.addWidget(self._merits_card)

        # Demerits card
        self._demerits_card = GlassCard(radius=14)
        self._demerits_layout = QVBoxLayout(self._demerits_card)
        demerits_header = QHBoxLayout()
        demerits_icon = QLabel("⚠️")
        demerits_icon.setStyleSheet("font-size: 20px;")
        demerits_title_lbl = QLabel("Your Demerits")
        demerits_title_lbl.setStyleSheet(
            f"color: {COLORS['danger']}; font-size: 16px; font-weight: 800; letter-spacing: 0.5px;"
        )
        demerits_header.addWidget(demerits_icon)
        demerits_header.addSpacing(8)
        demerits_header.addWidget(demerits_title_lbl)
        demerits_header.addStretch()
        self._demerits_layout.addLayout(demerits_header)
        self._demerits_container = QVBoxLayout()
        self._demerits_container.setSpacing(10)
        self._demerits_layout.addLayout(self._demerits_container)
        body_lay.addWidget(self._demerits_card)

        # Consistency card
        self._consistency_card_widget = GlassCard(radius=14)
        cl = QVBoxLayout(self._consistency_card_widget)
        c_title = QLabel("⟳  Consistency Analysis")
        c_title.setStyleSheet(f"color: {COLORS['info']}; font-size: 15px; font-weight: 700;")
        self._consistency_content = QLabel("")
        self._consistency_content.setWordWrap(True)
        self._consistency_content.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        cl.addWidget(c_title)
        cl.addWidget(self._consistency_content)
        body_lay.addWidget(self._consistency_card_widget)

        # Raw text view (monospaced)
        raw_card = GlassCard(radius=14)
        raw_lay = QVBoxLayout(raw_card)
        raw_title = QLabel("Raw Report Text")
        raw_title.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 13px; font-weight: 600;")
        self._raw_text = QTextEdit()
        self._raw_text.setReadOnly(True)
        self._raw_text.setFont(QFont("Consolas", 10))
        self._raw_text.setStyleSheet(f"""
            QTextEdit {{
                background: {COLORS['bg']};
                color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        self._raw_text.setFixedHeight(300)
        raw_lay.addWidget(raw_title)
        raw_lay.addWidget(self._raw_text)
        body_lay.addWidget(raw_card)

        body_lay.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(body)
        root.addWidget(scroll)

    def load_report(self, report: dict[str, Any], report_text: str) -> None:
        """Populate the screen with report data."""
        self._report_text = report_text

        # Verdict
        v = report["verdict"]
        verdict_label = v["label"]
        fg_map = {"Recommended": COLORS["success"], "Borderline": COLORS["warning"], "Not Recommended": COLORS["danger"]}
        fg = fg_map.get(verdict_label, "#888")
        self._verdict_lbl.setText(f"► {verdict_label.upper()}")
        self._verdict_lbl.setStyleSheet(f"color: {fg}; font-size: 22px; font-weight: 800;")
        self._verdict_desc.setText(v["description"])
        self._verdict_reason.setText(f"Reason: {v['reason']}")

        # Summary
        self._summary_lbl.setText(report.get("summary", ""))

        # Strengths
        strengths = report.get("strengths", [])
        if strengths:
            lines = []
            for s in strengths:
                lines.append(f"<b>{s['label']}</b> — {s['percentage']} ({s['band']})")
                for q in s["questions"][:1]:
                    lines.append(f"&nbsp;&nbsp;• Q{q['id']}: {q['text'][:80]}… (response: {q['raw']})")
            self._strengths_content.setText("<br>".join(lines))
            self._strengths_content.setTextFormat(Qt.TextFormat.RichText)
        else:
            self._strengths_content.setText("No traits scored above the strong threshold in this session.")

        # Weaknesses
        weaknesses = report.get("weaknesses", [])
        if weaknesses:
            lines = []
            for w in weaknesses:
                lines.append(f"<b>{w['label']}</b> — {w['percentage']} ({w['band']})")
                lines.append(f"&nbsp;&nbsp;{w['reasoning']}")
                for q in w["questions"][:1]:
                    lines.append(f"&nbsp;&nbsp;• Q{q['id']}: {q['text'][:80]}… (response: {q['raw']})")
            self._weaknesses_content.setText("<br>".join(lines))
            self._weaknesses_content.setTextFormat(Qt.TextFormat.RichText)
        else:
            self._weaknesses_content.setText("No traits scored below the weakness threshold in this session.")

        # Merits
        self._clear_layout(self._merits_container)
        merits = report.get("merits", [])
        if merits:
            for m in merits:
                row = QFrame()
                row.setStyleSheet(f"""
                    QFrame {{
                        background: #052e1688;
                        border: 1px solid {COLORS['success']}44;
                        border-radius: 10px;
                        padding: 2px;
                    }}
                """)
                rl = QVBoxLayout(row)
                rl.setContentsMargins(14, 10, 14, 10)
                rl.setSpacing(4)
                top = QLabel(f"<b style='color:{COLORS['success']};'>✓ {m['label']}</b> &nbsp; <span style='color:{COLORS['text_muted']};'>{m['percentage']} — {m['band']}</span>")
                top.setTextFormat(Qt.TextFormat.RichText)
                rl.addWidget(top)
                for q in m["questions"][:2]:
                    ql = QLabel(f"&nbsp;&nbsp;• Q{q['id']}: {q['text'][:90]}… <i style='color:{COLORS['text_muted']};'>(response: {q['raw']}/7)</i>")
                    ql.setTextFormat(Qt.TextFormat.RichText)
                    ql.setWordWrap(True)
                    ql.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
                    rl.addWidget(ql)
                self._merits_container.addWidget(row)
        else:
            lbl = QLabel("No traits scored above the merit threshold (≥72%) in this session.")
            lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 13px;")
            self._merits_container.addWidget(lbl)

        # Demerits
        self._clear_layout(self._demerits_container)
        demerits = report.get("demerits", [])
        if demerits:
            for d in demerits:
                row = QFrame()
                row.setStyleSheet(f"""
                    QFrame {{
                        background: #450a0a88;
                        border: 1px solid {COLORS['danger']}44;
                        border-radius: 10px;
                        padding: 2px;
                    }}
                """)
                rl = QVBoxLayout(row)
                rl.setContentsMargins(14, 10, 14, 10)
                rl.setSpacing(4)
                top = QLabel(f"<b style='color:{COLORS['danger']};'>✗ {d['label']}</b> &nbsp; <span style='color:{COLORS['text_muted']};'>{d['percentage']} — {d['band']}</span>")
                top.setTextFormat(Qt.TextFormat.RichText)
                rl.addWidget(top)
                reason_lbl = QLabel(f"&nbsp;&nbsp;→ {d['reasoning']}")
                reason_lbl.setWordWrap(True)
                reason_lbl.setStyleSheet(f"color: {COLORS['warning']}; font-size: 12px;")
                reason_lbl.setTextFormat(Qt.TextFormat.RichText)
                rl.addWidget(reason_lbl)
                for q in d["questions"][:2]:
                    ql = QLabel(f"&nbsp;&nbsp;• Q{q['id']}: {q['text'][:90]}… <i style='color:{COLORS['text_muted']};'>(response: {q['raw']}/7)</i>")
                    ql.setTextFormat(Qt.TextFormat.RichText)
                    ql.setWordWrap(True)
                    ql.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
                    rl.addWidget(ql)
                self._demerits_container.addWidget(row)
        else:
            lbl = QLabel("No traits scored below the demerit threshold (<55%). Excellent!")
            lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 13px;")
            self._demerits_container.addWidget(lbl)

        # Consistency
        c = report.get("consistency", {})
        contradictions = c.get("contradictions", [])
        lines = [
            f"Consistency Score: {c.get('score', 0):.1%}",
            f"Contradiction Rate: {c.get('contradiction_rate', 0):.1%}",
        ]
        if contradictions:
            lines.append(f"<b>{len(contradictions)} contradiction(s) found:</b>")
            for contra in contradictions[:3]:
                lines.append(
                    f"&nbsp;&nbsp;• Q{contra['q1_id']} vs Q{contra['q2_id']}: "
                    f"divergence = {contra['divergence']} pts"
                )
        else:
            lines.append("No significant contradictions detected.")
        self._consistency_content.setText("<br>".join(lines))
        self._consistency_content.setTextFormat(Qt.TextFormat.RichText)

        # Raw text
        self._raw_text.setPlainText(report_text)

    def _export(self) -> None:
        if not self._report_text:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Report",
            f"opi_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt)",
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self._report_text)
                QMessageBox.information(self, "Saved", f"Report saved to:\n{path}")
            except OSError as e:
                QMessageBox.critical(self, "Error", f"Could not save: {e}")


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    """Root application window — owns the QStackedWidget."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("OPI — Personality Assessment System")
        self.resize(1100, 780)
        self.setMinimumSize(900, 640)
        self.setStyleSheet(GLOBAL_STYLESHEET)
        self._setup_central()

    def _setup_central(self) -> None:
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        self._start_screen    = StartScreen()
        self._test_screen     = TestScreen()
        self._analysis_screen = AnalysisScreen()
        self._report_screen   = ReportScreen()

        self._stack.addWidget(self._start_screen)     # index 0
        self._stack.addWidget(self._test_screen)      # index 1
        self._stack.addWidget(self._analysis_screen)  # index 2
        self._stack.addWidget(self._report_screen)    # index 3

    # ── Screen accessors (used by main.py)
    @property
    def start_screen(self) -> StartScreen:
        return self._start_screen

    @property
    def test_screen(self) -> TestScreen:
        return self._test_screen

    @property
    def analysis_screen(self) -> AnalysisScreen:
        return self._analysis_screen

    @property
    def report_screen(self) -> ReportScreen:
        return self._report_screen

    def show_screen(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
