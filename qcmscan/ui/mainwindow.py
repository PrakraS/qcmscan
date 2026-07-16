"""Fenêtre principale : navigation latérale + pages empilées."""

import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel,
                               QListWidget, QMainWindow, QStackedWidget,
                               QToolButton, QVBoxLayout, QWidget)

from .. import db, maj
from ..version import __version__
from . import theme
from .classes_page import ClassesPage
from .correction_page import CorrectionPage
from .questions_page import QuestionsPage
from .subjects_page import SubjectsPage
from .widgets import Worker


class MainWindow(QMainWindow):
    def __init__(self, con):
        super().__init__()
        self.con = con
        self.sombre = db.get_setting(con, "theme", "clair") == "sombre"
        self.setWindowTitle("QCMScan")
        self.resize(1180, 760)

        central = QWidget()
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        cote = QWidget()
        clay = QVBoxLayout(cote)
        clay.setContentsMargins(0, 0, 0, 0)
        clay.setSpacing(0)
        logo = QLabel("QCMSCAN")
        logo.setObjectName("logo")
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.addItems(["Banque de questions", "Classes", "Sujets",
                           "Correction"])
        self.nav.setFixedWidth(210)
        logo.setFixedWidth(210)
        clay.addWidget(logo)
        clay.addWidget(self.nav, 1)
        self.b_theme = QToolButton()
        self.b_theme.setObjectName("themeToggle")
        self.b_theme.setFixedWidth(210)
        self.b_theme.setCursor(Qt.PointingHandCursor)
        self.b_theme.clicked.connect(self._basculer_theme)
        clay.addWidget(self.b_theme)
        self.b_version = QToolButton()
        self.b_version.setObjectName("versionInfo")
        self.b_version.setFixedWidth(210)
        self.b_version.setText(f"version {__version__}")
        clay.addWidget(self.b_version)
        lay.addWidget(cote)

        self.pages = QStackedWidget()
        conteneur = QWidget()
        plage = QVBoxLayout(conteneur)
        plage.setContentsMargins(22, 16, 22, 14)
        plage.addWidget(self.pages)
        lay.addWidget(conteneur, 1)

        self.p_questions = QuestionsPage(con)
        self.p_classes = ClassesPage(con)
        self.p_sujets = SubjectsPage(con)
        self.p_correction = CorrectionPage(con)
        for p in (self.p_questions, self.p_classes, self.p_sujets,
                  self.p_correction):
            self.pages.addWidget(p)

        self.nav.currentRowChanged.connect(self._changer_page)
        self.nav.setCurrentRow(0)
        self.setCentralWidget(central)
        self._maj_bouton_theme()

        # vérification de mise à jour, en arrière-plan et sans bruit
        self._maj_worker = Worker(lambda progress=None: maj.verifier())
        self._maj_worker.done.connect(self._maj_disponible)
        self._maj_worker.start()

    def _maj_disponible(self, resultat):
        if resultat is None:
            return
        version, url = resultat
        self.b_version.setText(f"Version {version} disponible  ↗")
        self.b_version.setToolTip(
            "Une nouvelle version est disponible : cliquer pour "
            "télécharger l'installateur, puis l'exécuter. Vos données "
            "sont conservées.")
        self.b_version.setCursor(Qt.PointingHandCursor)
        self.b_version.setProperty("maj", True)
        self.b_version.style().unpolish(self.b_version)
        self.b_version.style().polish(self.b_version)
        self.b_version.clicked.connect(lambda: webbrowser.open(url))

    def _changer_page(self, row):
        ancien = self.pages.currentWidget()
        if ancien is not None and hasattr(ancien, "quitter"):
            ancien.quitter()             # enregistrement automatique
        self.pages.setCurrentIndex(row)
        page = self.pages.currentWidget()
        if hasattr(page, "refresh"):
            page.refresh()

    def closeEvent(self, event):
        page = self.pages.currentWidget()
        if page is not None and hasattr(page, "quitter"):
            page.quitter()
        super().closeEvent(event)

    # -------------------------------------------------------------- thème
    def _basculer_theme(self):
        self.sombre = not self.sombre
        db.set_setting(self.con, "theme",
                       "sombre" if self.sombre else "clair")
        QApplication.instance().setStyleSheet(theme.qss(self.sombre))
        self._maj_bouton_theme()
        # les couleurs posées hors feuille de style (colonne Points)
        self.p_sujets._toggle_coefs(self.p_sujets.coefs.isChecked())

    def _maj_bouton_theme(self):
        self.b_theme.setText("☀   Mode clair" if self.sombre
                             else "☾   Mode sombre")
