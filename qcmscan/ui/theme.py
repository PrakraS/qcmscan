"""Thèmes de l'application. Sobre, papier et encre, un seul accent.

Deux palettes (claire et sombre) alimentent la même feuille de style.
`palette` reflète toujours le thème actif, pour les couleurs posées en
code (hors feuille de style).
"""

CLAIR = {
    "papier": "#F5F4F0",         # fond général
    "surface": "#FFFFFF",        # champs, listes, cartes
    "bord": "#DDDAD2",
    "texte": "#23272C",
    "texte2": "#6E6A62",
    "accent": "#2E5A7D",         # encre bleue
    "accent_hover": "#386C93",
    "accent_clair": "#EAF0F5",
    "vert": "#1F7A45",
    "rouge": "#B03434",
    "rouge_fond": "#F9ECEC",
    "orange": "#B4700A",
    "nav_fond": "#23272C",
    "nav_texte": "#C8C4BC",
    "nav_texte_sel": "#FFFFFF",
    "nav_sel_fond": "#2E333A",
    "nav_hover": "#292E34",
    "nav_marque": "#7FA8C9",
    "desactive": "#B5B1A9",
    "desactive_fond": "#F0EFEA",
    "prim_off": "#9FB3C2",
    "prim_off_texte": "#EDEDED",
    "alterne": "#FAF9F6",
    "entete_table": "#EFEEE9",
    "grille": "#EDEBE5",
    "scroll": "#C9C5BD",
    "scroll_hover": "#B0ACA4",
}

SOMBRE = {
    "papier": "#1E2126",
    "surface": "#282C32",
    "bord": "#3C4148",
    "texte": "#E6E4DF",
    "texte2": "#9DA2A8",
    "accent": "#6E9CC0",
    "accent_hover": "#7FA8C9",
    "accent_clair": "#2C3A46",
    "vert": "#54B37E",
    "rouge": "#D07070",
    "rouge_fond": "#3A2A2A",
    "orange": "#D69A45",
    "nav_fond": "#15181C",
    "nav_texte": "#A9ADB3",
    "nav_texte_sel": "#FFFFFF",
    "nav_sel_fond": "#252A31",
    "nav_hover": "#1D2126",
    "nav_marque": "#7FA8C9",
    "desactive": "#5C6167",
    "desactive_fond": "#23262B",
    "prim_off": "#3D4C59",
    "prim_off_texte": "#8B949C",
    "alterne": "#22262B",
    "entete_table": "#2B3036",
    "grille": "#33383E",
    "scroll": "#454A51",
    "scroll_hover": "#565C64",
}

# Palette active, mise à jour par qss(). Copie pour que les références
# gardées par les pages restent valables après un changement de thème.
palette = dict(CLAIR)


def qss(sombre: bool = False) -> str:
    """Feuille de style de l'application ; met à jour `palette`."""
    palette.clear()
    palette.update(SOMBRE if sombre else CLAIR)
    p = palette
    return f"""
* {{
    font-family: "Segoe UI", "Noto Sans", sans-serif;
    font-size: 10pt;
    color: {p['texte']};
}}
QMainWindow, QDialog {{ background: {p['papier']}; }}

/* ------------------------------------------------ navigation latérale */
#nav {{
    background: {p['nav_fond']};
    border: none;
    outline: none;
    padding-top: 4px;
}}
#nav::item {{
    color: {p['nav_texte']};
    padding: 10px 18px;
    border-left: 3px solid transparent;
}}
#nav::item:selected {{
    color: {p['nav_texte_sel']};
    background: {p['nav_sel_fond']};
    border-left: 3px solid {p['nav_marque']};
}}
#nav::item:hover:!selected {{ background: {p['nav_hover']}; }}
#logo {{
    color: {p['nav_texte_sel']};
    background: {p['nav_fond']};
    font-size: 13pt;
    font-weight: 600;
    letter-spacing: 2px;
    padding: 18px 18px 14px 18px;
}}
#themeToggle {{
    color: {p['nav_texte']};
    background: {p['nav_fond']};
    border: none;
    padding: 12px 18px;
    font-size: 9pt;
}}
#themeToggle:hover {{
    color: {p['nav_texte_sel']};
    background: {p['nav_hover']};
}}

/* ------------------------------------------------------------- titres */
#titrePage {{
    font-size: 15pt;
    font-weight: 600;
    color: {p['texte']};
}}
#sousTitre {{ color: {p['texte2']}; }}
QLabel[role="section"] {{
    font-weight: 600;
    color: {p['texte2']};
    letter-spacing: 1px;
    font-size: 8.5pt;
}}

/* ------------------------------------------------------------ champs */
QLineEdit, QPlainTextEdit, QComboBox, QDoubleSpinBox, QSpinBox,
QDateEdit {{
    background: {p['surface']};
    border: 1px solid {p['bord']};
    border-radius: 3px;
    padding: 5px 7px;
    selection-background-color: {p['accent']};
    selection-color: white;
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
QDoubleSpinBox:focus {{ border: 1px solid {p['accent']}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {p['surface']};
    border: 1px solid {p['bord']};
    selection-background-color: {p['accent_clair']};
    selection-color: {p['texte']};
}}
QPlainTextEdit {{ font-family: "Consolas", "DejaVu Sans Mono", monospace; }}

/* ------------------------------------------------------------ boutons */
QPushButton {{
    background: {p['surface']};
    border: 1px solid {p['bord']};
    border-radius: 3px;
    padding: 6px 14px;
}}
QPushButton:hover {{ border-color: {p['accent']}; }}
QPushButton:pressed {{ background: {p['accent_clair']}; }}
QPushButton:disabled {{
    color: {p['desactive']}; background: {p['desactive_fond']};
}}
QPushButton[type="primaire"] {{
    background: {p['accent']};
    border: 1px solid {p['accent']};
    color: white;
    font-weight: 600;
}}
QPushButton[type="primaire"]:hover {{ background: {p['accent_hover']}; }}
QPushButton[type="primaire"]:disabled {{
    background: {p['prim_off']};
    border-color: {p['prim_off']};
    color: {p['prim_off_texte']};
}}
QPushButton[type="danger"] {{ color: {p['rouge']}; }}
QToolButton {{
    border: 1px solid transparent;
    border-radius: 3px;
    padding: 3px;
}}
QToolButton:hover {{ border-color: {p['bord']}; background: {p['surface']}; }}
QToolButton[role="suppr"] {{
    color: {p['rouge']};
    font-weight: 600;
    padding: 3px 8px;
}}
QToolButton[role="suppr"]:hover {{
    border-color: {p['rouge']};
    background: {p['rouge_fond']};
}}

/* ------------------------------------------------------ listes/tables */
QListWidget, QTableWidget, QTableView, QTreeWidget {{
    background: {p['surface']};
    border: 1px solid {p['bord']};
    border-radius: 3px;
    outline: none;
    alternate-background-color: {p['alterne']};
}}
QListWidget::item {{ padding: 6px 8px; }}
QListWidget::item:selected, QTableWidget::item:selected {{
    background: {p['accent_clair']};
    color: {p['texte']};
}}
QHeaderView {{ background: {p['surface']}; border: none; }}
QTableCornerButton::section {{
    background: {p['entete_table']};
    border: none;
}}
QHeaderView::section {{
    background: {p['entete_table']};
    border: none;
    border-bottom: 1px solid {p['bord']};
    border-right: 1px solid {p['bord']};
    padding: 5px 8px;
    font-weight: 600;
    color: {p['texte2']};
}}
QTableWidget {{ gridline-color: {p['grille']}; }}

/* ------------------------------------------------- cases et puces */
QRadioButton::indicator, QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {p['bord']};
    background: {p['surface']};
}}
QRadioButton::indicator {{ border-radius: 8px; }}
QCheckBox::indicator {{ border-radius: 3px; }}
QRadioButton::indicator:hover, QCheckBox::indicator:hover {{
    border-color: {p['accent']};
}}
QRadioButton::indicator:checked {{
    width: 8px;
    height: 8px;
    border: 4px solid {p['accent']};
    background: {p['surface']};
}}
QCheckBox::indicator:checked {{
    background: {p['accent']};
    border-color: {p['accent']};
}}
QRadioButton::indicator:disabled, QCheckBox::indicator:disabled {{
    background: {p['desactive_fond']};
    border-color: {p['bord']};
}}

/* ------------------------------------------------------------- divers */
QScrollArea {{
    background: {p['surface']};
    border: 1px solid {p['bord']};
    border-radius: 3px;
}}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QSplitter::handle {{ background: {p['papier']}; width: 8px; }}
QRadioButton, QCheckBox {{ spacing: 6px; }}
QProgressBar {{
    background: {p['surface']};
    border: 1px solid {p['bord']};
    border-radius: 3px;
    text-align: center;
    height: 16px;
}}
QProgressBar::chunk {{ background: {p['accent']}; }}
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {p['scroll']}; border-radius: 5px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {p['scroll_hover']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{
    background: {p['scroll']}; border-radius: 5px; min-width: 30px;
}}
QStatusBar {{ background: {p['papier']}; color: {p['texte2']}; }}
QFrame[role="carte"] {{
    background: {p['surface']};
    border: 1px solid {p['bord']};
    border-radius: 3px;
}}
"""
