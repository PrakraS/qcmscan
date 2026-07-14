"""Thème de l'application. Sobre, papier et encre, un seul accent."""

ENCRE = "#23272C"
PAPIER = "#F5F4F0"
SURFACE = "#FFFFFF"
BORD = "#DDDAD2"
TEXTE = "#23272C"
TEXTE_2 = "#6E6A62"
ACCENT = "#2E5A7D"        # encre bleue
ACCENT_CLAIR = "#EAF0F5"
VERT = "#1F7A45"
ROUGE = "#B03434"
ORANGE = "#B4700A"

QSS = f"""
* {{
    font-family: "Segoe UI", "Noto Sans", sans-serif;
    font-size: 10pt;
    color: {TEXTE};
}}
QMainWindow, QDialog {{ background: {PAPIER}; }}

/* ------------------------------------------------ navigation latérale */
#nav {{
    background: {ENCRE};
    border: none;
    outline: none;
    padding-top: 4px;
}}
#nav::item {{
    color: #C8C4BC;
    padding: 10px 18px;
    border-left: 3px solid transparent;
}}
#nav::item:selected {{
    color: #FFFFFF;
    background: #2E333A;
    border-left: 3px solid #7FA8C9;
}}
#nav::item:hover:!selected {{ background: #292E34; }}
#logo {{
    color: #FFFFFF;
    background: {ENCRE};
    font-size: 13pt;
    font-weight: 600;
    letter-spacing: 2px;
    padding: 18px 18px 12px 18px;
}}
#logosub {{
    color: #8A867E;
    background: {ENCRE};
    font-size: 8pt;
    padding: 0 18px 14px 18px;
}}

/* ------------------------------------------------------------- titres */
#titrePage {{
    font-size: 15pt;
    font-weight: 600;
    color: {TEXTE};
}}
#sousTitre {{ color: {TEXTE_2}; }}
QLabel[role="section"] {{
    font-weight: 600;
    color: {TEXTE_2};
    letter-spacing: 1px;
    font-size: 8.5pt;
}}

/* ------------------------------------------------------------ champs */
QLineEdit, QPlainTextEdit, QComboBox, QDoubleSpinBox, QSpinBox,
QDateEdit {{
    background: {SURFACE};
    border: 1px solid {BORD};
    border-radius: 3px;
    padding: 5px 7px;
    selection-background-color: {ACCENT};
    selection-color: white;
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
QDoubleSpinBox:focus {{ border: 1px solid {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE};
    border: 1px solid {BORD};
    selection-background-color: {ACCENT_CLAIR};
    selection-color: {TEXTE};
}}
QPlainTextEdit {{ font-family: "Consolas", "DejaVu Sans Mono", monospace; }}

/* ------------------------------------------------------------ boutons */
QPushButton {{
    background: {SURFACE};
    border: 1px solid {BORD};
    border-radius: 3px;
    padding: 6px 14px;
}}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:pressed {{ background: {ACCENT_CLAIR}; }}
QPushButton:disabled {{ color: #B5B1A9; background: #F0EFEA; }}
QPushButton[type="primaire"] {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: white;
    font-weight: 600;
}}
QPushButton[type="primaire"]:hover {{ background: #386C93; }}
QPushButton[type="primaire"]:disabled {{
    background: #9FB3C2; border-color: #9FB3C2; color: #EDEDED;
}}
QPushButton[type="danger"] {{ color: {ROUGE}; }}
QToolButton {{
    border: 1px solid transparent;
    border-radius: 3px;
    padding: 3px;
}}
QToolButton:hover {{ border-color: {BORD}; background: {SURFACE}; }}
QToolButton[role="suppr"] {{
    color: {ROUGE};
    font-weight: 600;
    padding: 3px 8px;
}}
QToolButton[role="suppr"]:hover {{
    border-color: {ROUGE};
    background: #F9ECEC;
}}

/* ------------------------------------------------------ listes/tables */
QListWidget, QTableWidget, QTableView, QTreeWidget {{
    background: {SURFACE};
    border: 1px solid {BORD};
    border-radius: 3px;
    outline: none;
    alternate-background-color: #FAF9F6;
}}
QListWidget::item {{ padding: 6px 8px; }}
QListWidget::item:selected, QTableWidget::item:selected {{
    background: {ACCENT_CLAIR};
    color: {TEXTE};
}}
QHeaderView::section {{
    background: #EFEEE9;
    border: none;
    border-bottom: 1px solid {BORD};
    border-right: 1px solid {BORD};
    padding: 5px 8px;
    font-weight: 600;
    color: {TEXTE_2};
}}
QTableWidget {{ gridline-color: #EDEBE5; }}

/* ------------------------------------------------------------- divers */
QSplitter::handle {{ background: {PAPIER}; width: 8px; }}
QRadioButton, QCheckBox {{ spacing: 6px; }}
QProgressBar {{
    background: {SURFACE};
    border: 1px solid {BORD};
    border-radius: 3px;
    text-align: center;
    height: 16px;
}}
QProgressBar::chunk {{ background: {ACCENT}; }}
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #C9C5BD; border-radius: 5px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: #B0ACA4; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{
    background: #C9C5BD; border-radius: 5px; min-width: 30px;
}}
QStatusBar {{ background: {PAPIER}; color: {TEXTE_2}; }}
QFrame[role="carte"] {{
    background: {SURFACE};
    border: 1px solid {BORD};
    border-radius: 3px;
}}
"""
