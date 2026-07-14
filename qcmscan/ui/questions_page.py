"""Banque de questions : liste filtrable + éditeur avec aperçu LaTeX."""

import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QDialog, QHBoxLayout,
                               QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QPlainTextEdit, QRadioButton,
                               QScrollArea, QSplitter, QToolButton,
                               QVBoxLayout, QWidget)

from .. import db
from ..latexgen import compiler_apercu
from .widgets import (Worker, bouton, confirmer, entete, erreur, info,
                      ligne_boutons)


class LigneReponse(QWidget):
    def __init__(self, groupe, texte="", correcte=False, on_delete=None):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.radio = QRadioButton()
        self.radio.setToolTip("Bonne réponse")
        self.radio.setChecked(correcte)
        groupe.addButton(self.radio)
        self.champ = QLineEdit(texte)
        self.champ.setPlaceholderText("Texte de la réponse (LaTeX autorisé)")
        sup = QToolButton()
        sup.setText("✕")
        sup.setProperty("role", "suppr")
        sup.setToolTip("Supprimer cette réponse")
        if on_delete:
            sup.clicked.connect(lambda: on_delete(self))
        lay.addWidget(self.radio)
        lay.addWidget(self.champ, 1)
        lay.addWidget(sup)


class QuestionsPage(QWidget):
    def __init__(self, con):
        super().__init__()
        self.con = con
        self.qid = None

        racine = QVBoxLayout(self)
        racine.addWidget(entete(
            "Banque de questions",
            "Énoncés et réponses en LaTeX. Une seule bonne réponse "
            "par question. Pour afficher « & », écrivez « \\& »."))

        barre = QHBoxLayout()
        self.filtre_chap = QComboBox()
        self.filtre_chap.setMinimumWidth(180)
        self.filtre_chap.currentIndexChanged.connect(self.recharger_liste)
        self.recherche = QLineEdit()
        self.recherche.setPlaceholderText("Rechercher dans les énoncés…")
        self.recherche.textChanged.connect(self.recharger_liste)
        barre.addWidget(QLabel("Chapitre :"))
        barre.addWidget(self.filtre_chap)
        barre.addWidget(self.recherche, 1)
        barre.addWidget(bouton("Nouvelle question", "primaire",
                               self.nouvelle))
        racine.addLayout(barre)

        split = QSplitter()
        racine.addWidget(split, 1)

        self.liste = QListWidget()
        self.liste.currentItemChanged.connect(self.charger_selection)
        split.addWidget(self.liste)

        editeur = QWidget()
        elay = QVBoxLayout(editeur)
        elay.setContentsMargins(8, 0, 0, 0)

        lig1 = QHBoxLayout()
        lig1.addWidget(QLabel("Chapitre :"))
        self.chapitre = QComboBox()
        self.chapitre.setEditable(True)
        lig1.addWidget(self.chapitre, 1)
        elay.addLayout(lig1)

        lbl = QLabel("ÉNONCÉ")
        lbl.setProperty("role", "section")
        elay.addWidget(lbl)
        self.enonce = QPlainTextEdit()
        self.enonce.setPlaceholderText(
            r"Exemple : Soit $f(x) = x^2 + 3x$. Que vaut $f'(x)$ ?")
        self.enonce.setMinimumHeight(90)
        elay.addWidget(self.enonce)

        lbl = QLabel("RÉPONSES  (cocher la bonne)")
        lbl.setProperty("role", "section")
        elay.addWidget(lbl)
        self.groupe = QButtonGroup(self)
        self.zone_reponses = QVBoxLayout()
        self.zone_reponses.setSpacing(4)
        conteneur = QWidget()
        conteneur.setLayout(self.zone_reponses)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(conteneur)
        scroll.setMinimumHeight(140)
        elay.addWidget(scroll, 1)
        elay.addWidget(bouton("Ajouter une réponse",
                              on_click=lambda: self.ajouter_reponse()))

        elay.addWidget(ligne_boutons(
            bouton("Enregistrer", "primaire", self.enregistrer),
            bouton("Aperçu PDF", on_click=self.apercu),
            bouton("Supprimer", "danger", self.supprimer)))
        split.addWidget(editeur)
        split.setSizes([340, 560])

        self.refresh()

    # ------------------------------------------------------------ données
    def refresh(self):
        courant = self.filtre_chap.currentText()
        self.filtre_chap.blockSignals(True)
        self.filtre_chap.clear()
        self.filtre_chap.addItem("Tous")
        chapitres = db.liste_chapitres(self.con)
        self.filtre_chap.addItems(chapitres)
        i = self.filtre_chap.findText(courant)
        self.filtre_chap.setCurrentIndex(max(i, 0))
        self.filtre_chap.blockSignals(False)

        courant = self.chapitre.currentText()
        self.chapitre.clear()
        self.chapitre.addItems(chapitres)
        self.chapitre.setCurrentText(courant)
        self.recharger_liste()

    def recharger_liste(self):
        self.liste.blockSignals(True)
        self.liste.clear()
        chap = self.filtre_chap.currentText()
        chap = None if chap in ("", "Tous") else chap
        for q in db.liste_questions(self.con, chap,
                                    self.recherche.text().strip() or None):
            apercu = " ".join(q["enonce"].split())[:70]
            it = QListWidgetItem(f"[{q['chapitre']}]  {apercu}")
            it.setData(Qt.UserRole, q["id"])
            self.liste.addItem(it)
        self.liste.blockSignals(False)

    def charger_selection(self, item, _=None):
        if item is None:
            return
        qid = item.data(Qt.UserRole)
        q = self.con.execute("SELECT * FROM questions WHERE id=?",
                             (qid,)).fetchone()
        self.qid = qid
        self.chapitre.setCurrentText(q["chapitre"])
        self.enonce.setPlainText(q["enonce"])
        self.vider_reponses()
        for r in db.reponses_de(self.con, qid):
            self.ajouter_reponse(r["texte"], bool(r["correcte"]))

    # ----------------------------------------------------------- éditeur
    def vider_reponses(self):
        while self.zone_reponses.count():
            w = self.zone_reponses.takeAt(0).widget()
            if w:
                w.deleteLater()

    def ajouter_reponse(self, texte="", correcte=False):
        ligne = LigneReponse(self.groupe, texte, correcte,
                             on_delete=self.supprimer_reponse)
        self.zone_reponses.addWidget(ligne)

    def supprimer_reponse(self, ligne):
        self.zone_reponses.removeWidget(ligne)
        ligne.deleteLater()

    def lignes_reponses(self):
        out = []
        for i in range(self.zone_reponses.count()):
            w = self.zone_reponses.itemAt(i).widget()
            if w and w.champ.text().strip():
                out.append((w.champ.text().strip(), w.radio.isChecked()))
        return out

    def nouvelle(self):
        self.qid = None
        self.liste.clearSelection()
        self.enonce.clear()
        self.vider_reponses()
        for _ in range(4):
            self.ajouter_reponse()
        self.enonce.setFocus()

    def valider(self):
        reponses = self.lignes_reponses()
        if not self.enonce.toPlainText().strip():
            erreur(self, "Question incomplète", "L'énoncé est vide.")
            return None
        if len(reponses) < 2:
            erreur(self, "Question incomplète",
                   "Il faut au moins deux réponses.")
            return None
        if sum(1 for _, c in reponses if c) != 1:
            erreur(self, "Question incomplète",
                   "Cochez exactement une bonne réponse.")
            return None
        return reponses

    def enregistrer(self):
        reponses = self.valider()
        if reponses is None:
            return
        self.qid = db.sauver_question(
            self.con, self.qid, self.chapitre.currentText().strip(),
            self.enonce.toPlainText().strip(), reponses)
        self.refresh()

    def supprimer(self):
        if self.qid is None:
            return
        if not confirmer(self, "Supprimer",
                         "Supprimer cette question de la banque ?"):
            return
        db.supprimer_question(self.con, self.qid)
        self.nouvelle()
        self.refresh()

    # ------------------------------------------------------------ aperçu
    def apercu(self):
        reponses = self.valider()
        if reponses is None:
            return
        workdir = Path(tempfile.mkdtemp(prefix="qcmscan_apercu_"))
        self._worker = Worker(self._apercu_fn,
                              self.enonce.toPlainText().strip(),
                              reponses, workdir)
        self._worker.done.connect(self._apercu_ok)
        self._worker.error.connect(
            lambda msg: erreur(self, "Aperçu", msg))
        self._worker.start()

    def _apercu_fn(self, enonce, reponses, workdir, progress=None):
        return compiler_apercu(self.con, enonce, reponses, workdir)

    def _apercu_ok(self, png_path):
        dlg = QDialog(self)
        dlg.setWindowTitle("Aperçu de la question")
        lay = QVBoxLayout(dlg)
        lbl = QLabel()
        pm = QPixmap(str(png_path))
        if pm.width() > 900:
            pm = pm.scaledToWidth(900, Qt.SmoothTransformation)
        lbl.setPixmap(pm)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(lbl)
        lay.addWidget(scroll)
        dlg.resize(min(pm.width() + 60, 980), min(pm.height() + 80, 700))
        dlg.exec()
