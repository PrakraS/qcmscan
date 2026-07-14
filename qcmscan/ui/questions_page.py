"""Banque de questions : liste filtrable + éditeur avec aperçu LaTeX."""

import html
import json
import re
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QApplication, QButtonGroup, QComboBox,
                               QDialog, QFileDialog, QHBoxLayout,
                               QInputDialog, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMenu, QPlainTextEdit,
                               QRadioButton, QScrollArea, QSplitter,
                               QToolButton, QVBoxLayout, QWidget)

from .. import db
from ..latexgen import compiler_apercu
from . import theme
from .widgets import (ROLE_BADGE, ROLE_META, ListeDeuxLignes, Worker,
                      bouton, confirmer, entete, erreur, info,
                      ligne_boutons)


class LigneReponse(QWidget):
    def __init__(self, groupe, texte="", correcte=False, on_delete=None,
                 on_change=None):
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
        if on_change:
            self.champ.textChanged.connect(on_change)
            self.radio.toggled.connect(on_change)
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
            "Les énoncés et les réponses doivent être en LaTeX."))

        self._usages = {}
        barre = QHBoxLayout()
        self.filtre_niveau = QComboBox()
        self.filtre_niveau.setMinimumWidth(110)
        self.filtre_niveau.currentIndexChanged.connect(self._niveau_change)
        gerer = QToolButton()
        gerer.setText("⚙")
        gerer.setToolTip("Gérer les niveaux")
        gerer.clicked.connect(self.gerer_niveaux)
        self.filtre_chap = QComboBox()
        self.filtre_chap.setMinimumWidth(160)
        self.filtre_chap.currentIndexChanged.connect(self.recharger_liste)
        self.recherche = QLineEdit()
        self.recherche.setPlaceholderText("Rechercher dans les énoncés…")
        self.recherche.textChanged.connect(self.recharger_liste)
        barre.addWidget(QLabel("Niveau :"))
        barre.addWidget(self.filtre_niveau)
        barre.addWidget(gerer)
        barre.addWidget(QLabel("Chapitre :"))
        barre.addWidget(self.filtre_chap)
        barre.addWidget(self.recherche, 1)
        barre.addWidget(bouton("Nouvelle question", "primaire",
                               self.nouvelle))
        barre.addWidget(bouton("Coller…", on_click=self.coller))
        outils = QToolButton()
        outils.setText("⋯")
        outils.setToolTip("Exporter, importer, corbeille")
        menu = QMenu(outils)
        menu.addAction("Exporter la banque…", self.exporter)
        menu.addAction("Importer un fichier…", self.importer)
        menu.addSeparator()
        menu.addAction("Renommer un chapitre…", self.renommer_chapitre)
        menu.addAction("Corbeille…", self.corbeille)
        outils.setMenu(menu)
        outils.setPopupMode(QToolButton.InstantPopup)
        barre.addWidget(outils)
        racine.addLayout(barre)

        split = QSplitter()
        racine.addWidget(split, 1)

        self.liste = QListWidget()
        self.liste.setItemDelegate(ListeDeuxLignes(self.liste))
        self.liste.currentItemChanged.connect(self.charger_selection)
        split.addWidget(self.liste)

        editeur = QWidget()
        elay = QVBoxLayout(editeur)
        elay.setContentsMargins(8, 0, 0, 0)

        lig1 = QHBoxLayout()
        lig1.addWidget(QLabel("Niveau :"))
        self.niveau = QComboBox()
        self.niveau.currentIndexChanged.connect(self._maj_chapitres_editeur)
        lig1.addWidget(self.niveau, 1)
        lig1.addWidget(QLabel("Chapitre :"))
        self.chapitre = QComboBox()
        lig1.addWidget(self.chapitre, 2)
        plus = QToolButton()
        plus.setText("＋")
        plus.setToolTip("Nouveau chapitre")
        plus.clicked.connect(self.nouveau_chapitre)
        lig1.addWidget(plus)
        elay.addLayout(lig1)

        lbl = QLabel("ÉNONCÉ")
        lbl.setProperty("role", "section")
        elay.addWidget(lbl)
        self.enonce = QPlainTextEdit()
        self.enonce.setPlaceholderText(
            r"Exemple : Soit $f(x) = x^2 + 3x$. Que vaut $f'(x)$ ?")
        self.enonce.setMinimumHeight(90)
        self.enonce.textChanged.connect(self._programmer_apercu)
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
        scroll.setMinimumHeight(120)
        elay.addWidget(scroll, 2)
        lig_ajout = QHBoxLayout()
        lig_ajout.addWidget(bouton("Ajouter une réponse",
                                   on_click=lambda: self.ajouter_reponse()))
        lig_ajout.addStretch()
        elay.addLayout(lig_ajout)

        lbl = QLabel("APERÇU")
        lbl.setProperty("role", "section")
        elay.addWidget(lbl)
        self.apercu_img = QLabel()
        self.apercu_img.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.apercu_img.setTextFormat(Qt.RichText)
        self.apercu_scroll = QScrollArea()
        self.apercu_scroll.setWidgetResizable(True)
        self.apercu_scroll.setWidget(self.apercu_img)
        self.apercu_scroll.setMinimumHeight(150)
        elay.addWidget(self.apercu_scroll, 2)

        elay.addWidget(ligne_boutons(
            bouton("Enregistrer", "primaire", self.enregistrer),
            bouton("Supprimer", "danger", self.supprimer)))
        split.addWidget(editeur)
        split.setSizes([340, 560])

        # aperçu LaTeX en direct : compilation ~1 s après la dernière frappe
        self._apercu_dir = Path(tempfile.mkdtemp(prefix="qcmscan_apercu_"))
        self._apercu_timer = QTimer(self)
        self._apercu_timer.setSingleShot(True)
        self._apercu_timer.setInterval(900)
        self._apercu_timer.timeout.connect(self._lancer_apercu)
        self._apercu_cle = None
        self._apercu_encours = False
        self._apercu_refaire = False
        self._etat_charge = None

        self.refresh()

    # ------------------------------------------------------------ données
    def _filtre_niveau_valeur(self):
        n = self.filtre_niveau.currentText()
        return None if n in ("", "Tous") else n

    def _maj_filtre_chap(self):
        courant = self.filtre_chap.currentText()
        self.filtre_chap.blockSignals(True)
        self.filtre_chap.clear()
        self.filtre_chap.addItem("Tous")
        self.filtre_chap.addItems(
            db.liste_chapitres(self.con, self._filtre_niveau_valeur()))
        i = self.filtre_chap.findText(courant)
        self.filtre_chap.setCurrentIndex(max(i, 0))
        self.filtre_chap.blockSignals(False)

    def _niveau_change(self):
        self._maj_filtre_chap()
        self.recharger_liste()

    def refresh(self):
        niveaux = db.liste_niveaux(self.con)
        courant = self.filtre_niveau.currentText()
        self.filtre_niveau.blockSignals(True)
        self.filtre_niveau.clear()
        self.filtre_niveau.addItem("Tous")
        self.filtre_niveau.addItems(niveaux)
        i = self.filtre_niveau.findText(courant)
        self.filtre_niveau.setCurrentIndex(max(i, 0))
        self.filtre_niveau.blockSignals(False)
        self._maj_filtre_chap()

        courant = self.niveau.currentText()
        self.niveau.blockSignals(True)
        self.niveau.clear()
        self.niveau.addItem("")
        self.niveau.addItems(niveaux)
        self._choisir(self.niveau, courant)
        self.niveau.blockSignals(False)
        self._maj_chapitres_editeur()

        self._usages = db.usages_questions(self.con)
        self.recharger_liste()

    @staticmethod
    def _choisir(combo, texte):
        """Sélectionne `texte` dans un combo non éditable, en l'ajoutant
        au besoin (valeur héritée qui a quitté le catalogue)."""
        if texte and combo.findText(texte) < 0:
            combo.addItem(texte)
        combo.setCurrentText(texte)

    def _maj_chapitres_editeur(self):
        """Chapitres proposés dans l'éditeur : ceux du niveau choisi, ou
        tous si ce niveau n'en a pas encore."""
        courant = self.chapitre.currentText()
        niv = self.niveau.currentText() or None
        chapitres = db.liste_chapitres(self.con, niv)
        if niv and not chapitres:
            chapitres = db.liste_chapitres(self.con)
        self.chapitre.blockSignals(True)
        self.chapitre.clear()
        self.chapitre.addItem("")
        self.chapitre.addItems(chapitres)
        self._choisir(self.chapitre, courant)
        self.chapitre.blockSignals(False)

    def nouveau_chapitre(self):
        nom, ok = QInputDialog.getText(self, "Nouveau chapitre",
                                       "Nom du chapitre :")
        if ok and nom.strip():
            self._choisir(self.chapitre, nom.strip())

    def recharger_liste(self):
        self.liste.blockSignals(True)
        self.liste.clear()
        chap = self.filtre_chap.currentText()
        chap = None if chap in ("", "Tous") else chap
        for q in db.liste_questions(self.con, chap,
                                    self.recherche.text().strip() or None,
                                    self._filtre_niveau_valeur()):
            usages = self._usages.get(q["id"], [])
            it = QListWidgetItem(" ".join(q["enonce"].split())[:120])
            it.setData(Qt.UserRole, q["id"])
            meta = " · ".join(x for x in (q["niveau"], q["chapitre"]) if x)
            it.setData(ROLE_META, meta or "non classée")
            tip = q["enonce"]
            if usages:
                it.setData(ROLE_BADGE, f"⬩{len(usages)}")
                tip += "\n\nUtilisée dans :\n" + "\n".join(
                    f"– {u['titre']} — {u['classe']}"
                    + (f" ({u['niveau']})" if u["niveau"] else "")
                    + f", {u['date_creation']}" for u in usages)
            it.setToolTip(tip)
            self.liste.addItem(it)
            if q["id"] == self.qid:
                self.liste.setCurrentItem(it)
        self.liste.blockSignals(False)

    # ------------------------------------------------------------ niveaux
    def gerer_niveaux(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Niveaux")
        dlg.resize(380, 380)
        lay = QVBoxLayout(dlg)
        aide = QLabel("Niveaux proposés dans les listes déroulantes. "
                      "En retirer un ne modifie pas les questions "
                      "qui le portent.")
        aide.setWordWrap(True)
        aide.setObjectName("sousTitre")
        lay.addWidget(aide)
        liste = QListWidget()
        lay.addWidget(liste, 1)
        lig = QHBoxLayout()
        champ = QLineEdit()
        champ.setPlaceholderText("Nouveau niveau…")
        lig.addWidget(champ, 1)

        def recharger():
            liste.clear()
            for r in self.con.execute(
                    "SELECT nom FROM niveaux ORDER BY ordre, nom"):
                liste.addItem(r["nom"])

        def ajouter():
            if champ.text().strip():
                db.ajouter_niveau(self.con, champ.text())
                champ.clear()
                recharger()
                self.refresh()

        def retirer():
            it = liste.currentItem()
            if it is None:
                return
            if confirmer(dlg, "Retirer le niveau",
                         f"Retirer « {it.text()} » de la liste des "
                         "niveaux ?\nLes questions et classes de ce "
                         "niveau ne sont pas modifiées."):
                db.supprimer_niveau(self.con, it.text())
                recharger()
                self.refresh()

        champ.returnPressed.connect(ajouter)
        lig.addWidget(bouton("Ajouter", "primaire", ajouter))
        lay.addLayout(lig)
        lay.addWidget(ligne_boutons(
            bouton("Retirer la sélection", "danger", retirer),
            bouton("Fermer", on_click=dlg.accept)))
        recharger()
        dlg.exec()

    def charger_selection(self, item, _=None):
        if item is None:
            return
        qid = item.data(Qt.UserRole)
        if qid == self.qid:
            return          # re-sélection après un rafraîchissement
        self._sauver_si_modifiee()
        q = self.con.execute("SELECT * FROM questions WHERE id=?",
                             (qid,)).fetchone()
        self.qid = qid
        self._choisir(self.niveau, q["niveau"])
        self._choisir(self.chapitre, q["chapitre"])
        self.enonce.setPlainText(q["enonce"])
        self.vider_reponses()
        for r in db.reponses_de(self.con, qid):
            self.ajouter_reponse(r["texte"], bool(r["correcte"]))
        self._etat_charge = self._instantane()

    # ------------------------------------------------ enregistrement auto
    def _instantane(self):
        return (self.niveau.currentText().strip(),
                self.chapitre.currentText().strip(),
                self.enonce.toPlainText().strip(),
                tuple(self.lignes_reponses()))

    def _sauver_si_modifiee(self):
        """Enregistre la question en cours d'édition si elle a changé et
        qu'elle est valide ; appelé quand on la quitte (autre question,
        autre onglet, fermeture). Une question invalide n'est pas sauvée,
        sans message : on est en train de partir."""
        actuel = self._instantane()
        if actuel == self._etat_charge:
            return
        niveau, chapitre, enonce, reponses = actuel
        if (not enonce or len(reponses) < 2
                or sum(1 for _, c in reponses if c) != 1):
            return
        try:
            self.qid = db.sauver_question(self.con, self.qid, chapitre,
                                          enonce, list(reponses),
                                          niveau=niveau)
        except Exception:  # noqa: BLE001 — ex. nb de réponses verrouillé
            return
        self._etat_charge = self._instantane()
        QTimer.singleShot(0, self.refresh)

    def quitter(self):
        """Appelé au changement d'onglet et à la fermeture."""
        self._sauver_si_modifiee()

    # ----------------------------------------------------------- éditeur
    def vider_reponses(self):
        while self.zone_reponses.count():
            w = self.zone_reponses.takeAt(0).widget()
            if w:
                w.deleteLater()

    def ajouter_reponse(self, texte="", correcte=False):
        ligne = LigneReponse(self.groupe, texte, correcte,
                             on_delete=self.supprimer_reponse,
                             on_change=self._programmer_apercu)
        self.zone_reponses.addWidget(ligne)

    def supprimer_reponse(self, ligne):
        self.zone_reponses.removeWidget(ligne)
        ligne.deleteLater()
        self._programmer_apercu()

    def lignes_reponses(self):
        out = []
        for i in range(self.zone_reponses.count()):
            w = self.zone_reponses.itemAt(i).widget()
            if w and w.champ.text().strip():
                out.append((w.champ.text().strip(), w.radio.isChecked()))
        return out

    def nouvelle(self):
        self._sauver_si_modifiee()
        self.qid = None
        self.liste.clearSelection()
        if self._filtre_niveau_valeur():
            self._choisir(self.niveau, self._filtre_niveau_valeur())
        self.enonce.clear()
        self.vider_reponses()
        for _ in range(4):
            self.ajouter_reponse()
        self._etat_charge = self._instantane()
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
        try:
            self.qid = db.sauver_question(
                self.con, self.qid, self.chapitre.currentText().strip(),
                self.enonce.toPlainText().strip(), reponses,
                niveau=self.niveau.currentText())
        except Exception as e:  # noqa: BLE001 — remonté à l'utilisateur
            erreur(self, "Enregistrer", str(e))
            return
        self._etat_charge = self._instantane()
        self.refresh()

    def supprimer(self):
        """Envoi direct à la corbeille : récupérable, donc pas de
        confirmation."""
        if self.qid is None:
            return
        db.supprimer_question(self.con, self.qid)
        self._etat_charge = self._instantane()   # ne pas re-sauver en quittant
        self.qid = None
        self.nouvelle()
        self.refresh()

    def corbeille(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Corbeille")
        dlg.resize(620, 420)
        lay = QVBoxLayout(dlg)
        liste = QListWidget()
        liste.setSelectionMode(QListWidget.ExtendedSelection)
        lay.addWidget(liste, 1)

        def recharger():
            liste.clear()
            for q in db.questions_corbeille(self.con):
                apercu = " ".join(q["enonce"].split())[:70]
                it = QListWidgetItem(f"[{q['chapitre']}]  {apercu}")
                it.setData(Qt.UserRole, q["id"])
                liste.addItem(it)

        def restaurer():
            for it in liste.selectedItems():
                db.restaurer_question(self.con, it.data(Qt.UserRole))
            recharger()
            self.refresh()

        def detruire():
            sel = liste.selectedItems()
            if not sel or not confirmer(
                    dlg, "Supprimer définitivement",
                    f"Supprimer définitivement {len(sel)} question(s) ? "
                    "Cette action est irréversible."):
                return
            refus = []
            for it in sel:
                try:
                    db.detruire_question(self.con, it.data(Qt.UserRole))
                except ValueError as e:
                    refus.append(str(e))
            recharger()
            if refus:
                erreur(dlg, "Corbeille", refus[0])

        recharger()
        lay.addWidget(ligne_boutons(
            bouton("Restaurer", "primaire", restaurer),
            bouton("Supprimer définitivement", "danger", detruire),
            bouton("Fermer", on_click=dlg.accept)))
        dlg.exec()

    def renommer_chapitre(self):
        """Renomme un chapitre partout (fusion si le nom existe déjà)."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Renommer un chapitre")
        lay = QVBoxLayout(dlg)
        aide = QLabel("Toutes les questions du chapitre (corbeille "
                      "comprise) sont déplacées. Donner le nom d'un "
                      "chapitre existant fusionne les deux.")
        aide.setWordWrap(True)
        aide.setObjectName("sousTitre")
        lay.addWidget(aide)
        lig = QHBoxLayout()
        ancien = QComboBox()
        ancien.addItems(db.liste_chapitres(self.con))
        nouveau = QLineEdit()
        nouveau.setPlaceholderText("Nouveau nom…")
        lig.addWidget(ancien, 1)
        lig.addWidget(QLabel("→"))
        lig.addWidget(nouveau, 1)
        lay.addLayout(lig)

        def valider():
            a, n = ancien.currentText(), nouveau.text().strip()
            if not a or not n or a == n:
                return
            existants = db.liste_chapitres(self.con)
            if n in existants and not confirmer(
                    dlg, "Fusionner",
                    f"« {n} » existe déjà : fusionner « {a} » dedans ?"):
                return
            nb = db.renommer_chapitre(self.con, a, n)
            self.refresh()
            info(dlg, "Chapitre renommé",
                 f"{nb} question(s) déplacée(s) de « {a} » vers « {n} ».")
            dlg.accept()

        lay.addWidget(ligne_boutons(
            bouton("Renommer", "primaire", valider),
            bouton("Annuler", on_click=dlg.reject)))
        dlg.exec()

    # ---------------------------------------------------- export / import
    def coller(self):
        """Import rapide de questions au format texte (copier-coller)."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Coller des questions")
        lay = QVBoxLayout(dlg)
        aide = QLabel(
            "Un bloc par question, une ligne vide entre les blocs.\n"
            "Première ligne « [Niveau | Chapitre] » ou « [Chapitre] » "
            "facultative, puis l'énoncé, puis les réponses :\n« * » devant "
            "la bonne, « - » devant les autres. LaTeX autorisé.")
        aide.setObjectName("sousTitre")
        lay.addWidget(aide)
        zone = QPlainTextEdit()
        zone.setPlaceholderText(
            "[1SPE | Dérivation]\n"
            "Soit $f(x)=x^2+3x$. Que vaut $f'(x)$ ?\n"
            "* $2x+3$\n"
            "- $x^2$\n"
            "- $2x$\n"
            "- $3$")
        zone.setMinimumSize(560, 320)
        presse = QApplication.clipboard().text()
        if re.search(r"^\s*[-*]\s+\S", presse, re.MULTILINE):
            zone.setPlainText(presse)
        lay.addWidget(zone, 1)

        def valider():
            chap = self.filtre_chap.currentText()
            chap = "" if chap in ("", "Tous") else chap
            niv = self._filtre_niveau_valeur() or ""
            try:
                data = db.parser_questions_texte(zone.toPlainText(),
                                                 chap, niv)
                ajoutees, ignorees = db.importer_questions(self.con, data)
            except ValueError as e:
                erreur(dlg, "Coller", str(e))
                return
            self.refresh()
            msg = f"{ajoutees} question(s) ajoutée(s)."
            if ignorees:
                msg += f" {ignorees} doublon(s) ignoré(s)."
            info(dlg, "Coller", msg)
            dlg.accept()

        def consigne_ia():
            niv = self._filtre_niveau_valeur() or "[niveau]"
            chap = self.filtre_chap.currentText()
            chap = chap if chap not in ("", "Tous") else "[chapitre]"
            QApplication.clipboard().setText(
                "Rédige des questions de QCM de mathématiques. Réponds "
                "UNIQUEMENT avec les questions, au format exact suivant — "
                "une question par bloc, une ligne vide entre les blocs :\n"
                "\n"
                f"[{niv} | {chap}]\n"
                "Énoncé de la question.\n"
                "* bonne réponse\n"
                "- mauvaise réponse\n"
                "- mauvaise réponse\n"
                "- mauvaise réponse\n"
                "\n"
                "Règles impératives :\n"
                "- exactement UNE bonne réponse par question, marquée "
                "« * » ; les autres avec « - » ;\n"
                "- 4 propositions par question ;\n"
                "- notation mathématique en LaTeX entre $…$ (exemple : "
                "$f(x)=2x+3$) ; écrire \\& pour afficher « & » ;\n"
                f"- reprendre la ligne [{niv} | {chap}] en tête de "
                "chaque bloc ;\n"
                "- aucune numérotation, aucun texte hors des blocs ;\n"
                "- des distracteurs plausibles (erreurs typiques "
                "d'élèves).\n"
                "\n"
                f"Ma demande : [nombre] questions de niveau {niv} sur "
                f"« {chap} ».")
            info(dlg, "Consigne copiée",
                 "La consigne est dans le presse-papiers : collez-la "
                 "dans votre IA, complétez la dernière ligne (nombre, "
                 "niveau, chapitre), puis rapportez sa réponse ici.")

        lay.addWidget(ligne_boutons(
            bouton("Ajouter à la banque", "primaire", valider),
            bouton("Consigne pour l'IA", on_click=consigne_ia),
            bouton("Annuler", on_click=dlg.reject)))
        dlg.exec()

    def exporter(self):
        """Exporte la banque telle que filtrée (niveau + chapitre +
        recherche)."""
        chap = self.filtre_chap.currentText()
        chap = None if chap in ("", "Tous") else chap
        niv = self._filtre_niveau_valeur()
        data = db.exporter_questions(self.con, chap,
                                     self.recherche.text().strip() or None,
                                     niv)
        if not data:
            info(self, "Exporter", "Aucune question à exporter "
                 "(avec le filtre actuel).")
            return
        nom = "banque_" + "_".join(p for p in (niv, chap) if p) + ".json" \
            if (niv or chap) else "banque_qcm.json"
        chemin, _ = QFileDialog.getSaveFileName(
            self, "Exporter la banque", nom, "JSON (*.json)")
        if not chemin:
            return
        Path(chemin).write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8")
        info(self, "Exporter",
             f"{len(data)} question(s) exportée(s) vers\n{chemin}")

    def importer(self):
        chemin, _ = QFileDialog.getOpenFileName(
            self, "Importer des questions", "", "JSON (*.json)")
        if not chemin:
            return
        try:
            data = json.loads(Path(chemin).read_text(encoding="utf-8"))
            ajoutees, ignorees = db.importer_questions(self.con, data)
        except (OSError, ValueError) as e:
            erreur(self, "Importer", f"Import impossible : {e}")
            return
        self.refresh()
        msg = f"{ajoutees} question(s) importée(s)."
        if ignorees:
            msg += f"\n{ignorees} doublon(s) ignoré(s) (même chapitre " \
                   "et même énoncé qu'une question existante)."
        info(self, "Importer", msg)

    # ------------------------------------------------------ aperçu direct
    def _programmer_apercu(self, *_):
        if hasattr(self, "_apercu_timer"):
            self._apercu_timer.start()

    def _lancer_apercu(self):
        enonce = self.enonce.toPlainText().strip()
        reponses = self.lignes_reponses()
        if not enonce and not reponses:
            self.apercu_img.clear()
            self._apercu_cle = None
            return
        cle = (enonce, tuple(reponses))
        if cle == self._apercu_cle:
            return
        if self._apercu_encours:
            self._apercu_refaire = True
            return
        self._apercu_cle = cle
        self._apercu_encours = True
        self._apercu_worker = Worker(self._apercu_fn, enonce, reponses,
                                     self._apercu_dir)
        self._apercu_worker.done.connect(self._apercu_ok)
        self._apercu_worker.error.connect(self._apercu_err)
        self._apercu_worker.start()

    def _apercu_fn(self, enonce, reponses, workdir, progress=None):
        return compiler_apercu(self.con, enonce, reponses, workdir)

    def _apercu_fini(self):
        self._apercu_encours = False
        if self._apercu_refaire:
            self._apercu_refaire = False
            self._apercu_timer.start()

    def _apercu_ok(self, png_path):
        self._apercu_fini()
        pm = QPixmap(str(png_path))
        largeur = self.apercu_scroll.viewport().width() - 12
        if largeur > 120 and pm.width() > largeur:
            pm = pm.scaledToWidth(largeur, Qt.SmoothTransformation)
        self.apercu_img.setPixmap(pm)

    def _apercu_err(self, msg):
        self._apercu_fini()
        self.apercu_img.setText(
            f"<pre style='color:{theme.palette['rouge']};"
            f"white-space:pre-wrap'>{html.escape(msg)}</pre>")
