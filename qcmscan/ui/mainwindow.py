"""Fenêtre principale : navigation latérale + pages empilées."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel,
                               QListWidget, QMainWindow, QStackedWidget,
                               QToolButton, QVBoxLayout, QWidget)

from .. import db
from . import theme
from .classes_page import ClassesPage
from .correction_page import CorrectionPage
from .questions_page import QuestionsPage
from .subjects_page import SubjectsPage


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
        lay.addWidget(cote)

        self.pages = QStackedWidget()
        conteneur = QWidget()
        plage = QVBoxLayout(conteneur)
        plage.setContentsMargins(18, 14, 18, 10)
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
        self.statusBar().showMessage(
            "Les données sont enregistrées automatiquement dans votre "
            "dossier utilisateur.")

    def _changer_page(self, row):
        self.pages.setCurrentIndex(row)
        page = self.pages.currentWidget()
        if hasattr(page, "refresh"):
            page.refresh()

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
