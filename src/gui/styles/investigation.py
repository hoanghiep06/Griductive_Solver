"""Shared visual vocabulary for the investigation desk and guided first case."""

INK = "#203247"
MUTED_INK = "#586576"
PAPER = "#FBF6EB"
PAPER_EDGE = "#CDBB98"
DESK = "#172432"
BRASS = "#B38C49"
CURSOR_RADIUS = 42.0  # Logical viewport pixels: independent of the board zoom.
CURSOR_OPACITY = 0.42

PANEL_STYLE = f"""
QFrame#ClueReader {{ background: {PAPER}; border: 1px solid {PAPER_EDGE}; border-radius: 10px; }}
QFrame#ClueReader QLabel {{ background: transparent; border: none; color: {INK}; }}
QFrame#ClueReader QLabel#ClueReaderSource {{ font-size: 11px; font-weight: 700; color: #755A2E; }}
QFrame#ClueReader QLabel#ClueReaderType {{ font-size: 11px; font-weight: 700; color: #2D637A; }}
QFrame#ClueReader QLabel#ClueReaderText {{ font-size: 14px; color: {INK}; }}
QFrame#ClueReader QLabel#ClueReaderReferences {{ font-size: 11px; color: {MUTED_INK}; }}
QFrame#ClueReader QScrollArea, QFrame#ClueReader QWidget#ClueReaderCopy {{ border: none; background: transparent; }}
"""

TABS_STYLE = f"""
QTabWidget#InvestigationTabs::pane {{ border: none; background: transparent; }}
QTabBar::tab {{ background: #DFD5C0; color: {INK}; padding: 8px 15px;
                border: 1px solid {PAPER_EDGE}; border-bottom: none;
                border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 4px;
                font-size: 12px; font-weight: 600; }}
QTabBar::tab:selected {{ background: {PAPER}; color: {INK}; border-top: 2px solid {BRASS}; }}
QTabBar::tab:hover {{ background: #F3E8CF; }}
"""
