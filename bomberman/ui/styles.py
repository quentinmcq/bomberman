"""Feuilles de style Qt (QSS) : identité visuelle jaune/noir du jeu d'origine."""

ACCENT = "#e4c934"
ACCENT_LIGHT = "#f0d75a"
ACCENT_DARK = "#c9ad24"

TEXT_ON_ACCENT = "#1a1a1a"
TEAM_COLORS = ("#d62828", "#1d6fd6", "#f2c14e", "#c72c76")

ROOT_QSS = """
QWidget#root {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1b2735, stop:1 #090a0f);
}
QLabel {
    color: white;
}
"""

BUTTON_QSS = f"""
QPushButton {{
    background: {ACCENT};
    border-radius: 10px;
    color: {TEXT_ON_ACCENT};
    font-weight: bold;
    font-size: 26px;
    border: 1.5px solid black;
    min-height: 70px;
    min-width: 300px;
    margin: 8px;
    padding: 0 24px;
}}
QPushButton:hover {{ background: {ACCENT_LIGHT}; }}
QPushButton:pressed, QPushButton:checked {{ background: {ACCENT_DARK}; }}
QPushButton:focus {{ border: 3px solid white; }}
"""

TITLE_QSS = """
QLabel#title {
    color: #e4c934;
    font-weight: bold;
    font-size: 72px;
    letter-spacing: 6px;
}
QLabel#subtitle {
    color: #cfd6e4;
    font-size: 20px;
}
QLabel#hint {
    color: #cfd6e4;
    font-size: 15px;
    background: rgba(0, 0, 0, 110);
    border-radius: 8px;
    padding: 12px 18px;
}
"""

PANEL_LABEL_QSS = f"""
QLabel#panel {{
    background: {ACCENT};
    border-radius: 10px;
    color: {TEXT_ON_ACCENT};
    font-weight: bold;
    font-size: 28px;
    border: 1.5px solid black;
    min-height: 60px;
    min-width: 300px;
    margin: 8px;
    padding: 0 24px;
}}
"""

SLIDER_QSS = f"""
QSlider::groove:horizontal {{
    border: 2px solid #A0A5B2;
    border-radius: 2px;
    height: 4px;
    background: #E8E8E8;
}}
QSlider::handle:horizontal {{
    background: {ACCENT};
    width: 20px;
    border: 1px solid #000000;
    border-bottom: 2px solid #000000;
    border-radius: 2px;
    margin: -8px 0;
}}
"""

OVERLAY_QSS = """
QWidget#overlay {
    background: rgba(5, 8, 15, 190);
}
QLabel#overlayTitle {
    color: #e4c934;
    font-weight: bold;
    font-size: 56px;
}
"""
