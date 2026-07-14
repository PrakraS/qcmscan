"""Sujets : composition des questions, barème, génération des copies."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMenu, QSplitter,
                               QTableWidget, QTableWidgetItem,
                               QTableWidgetSelectionRange, QToolButton,
                               QVBoxLayout, QWidget)

from .. import db
from ..latexgen import generer_sujet
from ..paths import subject_dir
from . import theme
from .widgets import (ROLE_BADGE, ROLE_META, ListeDeuxLignes, Worker,
                      bouton, confirmer, entete, erreur, info,
                      ligne_boutons, ouvrir_fichier)


class TableQuestions(QTableWidget):
    """Questions du sujet : réordonnables à la souris, et la banque peut
    y déposer des questions par glisser-déposer."""

    def __init__(self, page):
        super().__init__(0, 3)
        self.page = page
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QTableWidget.DragDrop)

    def _ligne_cible(self, event):
        pos = event.position().toPoint()
        idx = self.indexAt(pos)
        if not idx.isValid():
            return self.rowCount()
        r = idx.row()
        if pos.y() > self.visualRect(idx).center().y():
            r += 1
        return r

    def dragEnterEvent(self, event):
        if event.source() in (self, self.page.banque):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.source() in (self, self.page.banque):
            super().dragMoveEvent(event)   # dessine l'indicateur de dépôt
            event.acceptProposedAction()

    def dropEvent(self, event):
        cible = self._ligne_cible(event)
        if event.source() is self:
            lignes = sorted({i.row() for i in self.selectedIndexes()})
            if lignes:
                self.page.deplacer_vers(lignes, cible)
        else:
            self.page.deposer_banque(cible)
        # CopyAction : la vue source ne doit pas supprimer ses lignes,
        # la page a déjà tout reconstruit.
        event.setDropAction(Qt.CopyAction)
        event.accept()


class SubjectsPage(QWidget):
    def __init__(self, con):
        super().__init__()
        self.con = con
        self.sujet_id = None
        self._chargement = False

        racine = QVBoxLayout(self)
        racine.addWidget(entete(
            "Sujets",
            "Composer un sujet, fixer le barème, générer une copie "
            "nominative par élève."))

        split = QSplitter()
        racine.addWidget(split, 1)

        gauche = QWidget()
        glay = QVBoxLayout(gauche)
        glay.setContentsMargins(0, 0, 8, 0)
        self.liste = QListWidget()
        self.liste.setItemDelegate(ListeDeuxLignes(self.liste))
        self.liste.currentItemChanged.connect(self.charger_selection)
        glay.addWidget(self.liste, 1)
        glay.addWidget(ligne_boutons(
            bouton("Nouveau sujet", "primaire", self.nouveau),
            bouton("Supprimer", "danger", self.supprimer)))
        split.addWidget(gauche)

        droite = QWidget()
        dlay = QVBoxLayout(droite)
        dlay.setContentsMargins(8, 0, 0, 0)

        lig = QHBoxLayout()
        lig.addWidget(QLabel("Titre :"))
        self.titre = QLineEdit()
        lig.addWidget(self.titre, 2)
        lig.addWidget(QLabel("Classe :"))
        self.classe = QComboBox()
        self.classe.currentIndexChanged.connect(self._recharger_banque)
        lig.addWidget(self.classe, 1)
        dlay.addLayout(lig)

        lig = QHBoxLayout()
        lig.addWidget(QLabel("Points par question :"))
        self.points = QDoubleSpinBox()
        self.points.setRange(0.25, 20)
        self.points.setSingleStep(0.25)
        self.points.setValue(1.0)
        lig.addWidget(self.points)
        self.coefs = QCheckBox("Coefficients par question")
        self.coefs.toggled.connect(self._toggle_coefs)
        lig.addWidget(self.coefs)
        self.malus_actif = QCheckBox("Points négatifs :")
        self.malus_actif.setToolTip(
            "Une mauvaise réponse ou plusieurs cases cochées retirent le "
            "malus. Blanc : zéro. La note d'une copie ne descend pas "
            "sous 0.")
        lig.addWidget(self.malus_actif)
        self.malus = QDoubleSpinBox()
        self.malus.setRange(0.25, 10)
        self.malus.setSingleStep(0.25)
        self.malus.setValue(0.5)
        self.malus.setPrefix("− ")
        self.malus.setEnabled(False)
        self.malus_actif.toggled.connect(self.malus.setEnabled)
        lig.addWidget(self.malus)
        lig.addStretch()
        dlay.addLayout(lig)

        picker = QHBoxLayout()
        colg = QVBoxLayout()
        lbl = QLabel("BANQUE")
        lbl.setProperty("role", "section")
        colg.addWidget(lbl)
        self.filtre_niveau = QComboBox()
        self.filtre_niveau.currentIndexChanged.connect(self._niveau_change)
        colg.addWidget(self.filtre_niveau)
        self.filtre_chap = QComboBox()
        self.filtre_chap.currentIndexChanged.connect(self._recharger_banque)
        colg.addWidget(self.filtre_chap)
        self.banque = QListWidget()
        self.banque.setItemDelegate(ListeDeuxLignes(self.banque))
        self.banque.setSelectionMode(QListWidget.ExtendedSelection)
        self.banque.setDragEnabled(True)
        colg.addWidget(self.banque, 1)
        colg.addWidget(bouton("Ajouter au sujet →",
                              on_click=self.ajouter_questions))
        picker.addLayout(colg, 1)

        cold = QVBoxLayout()
        lbl = QLabel("QUESTIONS DU SUJET")
        lbl.setProperty("role", "section")
        cold.addWidget(lbl)
        self.table = TableQuestions(self)
        self.table.setHorizontalHeaderLabels(["Chapitre", "Énoncé", "Points"])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setColumnWidth(0, 130)
        self.table.setColumnWidth(1, 320)
        self.table.setColumnWidth(2, 60)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        cold.addWidget(self.table, 1)
        cold.addWidget(ligne_boutons(
            bouton("Retirer", on_click=self.retirer_questions),
            bouton("Monter", on_click=lambda: self.deplacer(-1)),
            bouton("Descendre", on_click=lambda: self.deplacer(1))))
        picker.addLayout(cold, 2)
        dlay.addLayout(picker, 1)

        self.etat = QLabel("")
        self.etat.setObjectName("sousTitre")
        dlay.addWidget(self.etat)
        self.b_generer = bouton("Générer les copies", "primaire",
                                self.generer)
        self.b_ouvrir = QToolButton()
        self.b_ouvrir.setText("Ouvrir…")
        self.b_ouvrir.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self.b_ouvrir)
        self.a_copies = menu.addAction(
            "Les copies (main.pdf)", lambda: self._ouvrir("main.pdf"))
        self.a_corrige = menu.addAction(
            "Le corrigé", lambda: self._ouvrir("corrige.pdf"))
        menu.addSeparator()
        self.a_dossier = menu.addAction(
            "Le dossier du sujet", lambda: self._ouvrir(""))
        self.b_ouvrir.setMenu(menu)
        dlay.addWidget(ligne_boutons(
            bouton("Enregistrer le sujet", on_click=self.enregistrer),
            self.b_generer, self.b_ouvrir))
        split.addWidget(droite)
        split.setSizes([260, 720])

        # enregistrement automatique, différé après la dernière modification
        self._autosave = QTimer(self)
        self._autosave.setSingleShot(True)
        self._autosave.setInterval(900)
        self._autosave.timeout.connect(self.auto_enregistrer)
        self.titre.textChanged.connect(self._modifie)
        self.classe.currentIndexChanged.connect(self._modifie)
        self.points.valueChanged.connect(self._modifie)
        self.coefs.toggled.connect(self._modifie)
        self.malus_actif.toggled.connect(self._modifie)
        self.malus.valueChanged.connect(self._modifie)
        self.table.itemChanged.connect(self._modifie)

        self.refresh()

    # ------------------------------------------------ enregistrement auto
    def _modifie(self, *_):
        if not self._chargement:
            self._autosave.start()

    def auto_enregistrer(self):
        """Enregistre sans rien demander ; s'abstient si le sujet est
        incomplet, ou si un sujet déjà généré change de composition
        (là, le bouton « Enregistrer le sujet » reste le geste explicite)."""
        if self._chargement:
            return
        if not self.titre.text().strip() or self.classe.currentData() is None:
            return
        if self.sujet_id is not None:
            s = self.con.execute(
                "SELECT etat, classe_id FROM sujets WHERE id=?",
                (self.sujet_id,)).fetchone()
            if s is None:
                return               # sujet supprimé : rien à sauver
            if s["etat"] == "genere":
                en_base = {r["question_id"] for r in self.con.execute(
                    "SELECT question_id FROM sujet_questions "
                    "WHERE sujet_id=?", (self.sujet_id,))}
                if (set(self._question_ids()) != en_base
                        or self.classe.currentData() != s["classe_id"]):
                    self.etat.setText(
                        "Sujet déjà généré : cliquez « Enregistrer le "
                        "sujet » pour confirmer le changement de "
                        "composition (les copies imprimées ne suivront "
                        "pas).")
                    return
        nouveau = self.sujet_id is None
        if self.enregistrer(silencieux=True) is None:
            return
        if nouveau:
            self.refresh()
        self.etat.setText("Modifications enregistrées.")

    def quitter(self):
        """Appelé au changement d'onglet et à la fermeture."""
        self._autosave.stop()
        self.auto_enregistrer()

    # ------------------------------------------------------------ listes
    def refresh(self):
        sid = self.sujet_id
        self.liste.blockSignals(True)
        self.liste.clear()
        for s in self.con.execute(
                "SELECT s.*, c.nom AS classe_nom FROM sujets s "
                "JOIN classes c ON c.id = s.classe_id ORDER BY s.id DESC"):
            it = QListWidgetItem(s["titre"])
            it.setData(Qt.UserRole, s["id"])
            meta = f"{s['classe_nom']} · {self._cycle(s)}"
            it.setData(ROLE_META, meta)
            it.setToolTip(f"{s['titre']}\n{meta}")
            self.liste.addItem(it)
            if s["id"] == sid:
                self.liste.setCurrentItem(it)
        self.liste.blockSignals(False)

        self.classe.blockSignals(True)
        classe_courante = self.classe.currentData()
        self.classe.clear()
        for c in db.liste_classes(self.con):
            self.classe.addItem(c["nom"], c["id"])
        i = self.classe.findData(classe_courante)
        if i >= 0:
            self.classe.setCurrentIndex(i)
        self.classe.blockSignals(False)

        courant = self.filtre_niveau.currentText()
        self.filtre_niveau.blockSignals(True)
        self.filtre_niveau.clear()
        self.filtre_niveau.addItem("Tous niveaux")
        self.filtre_niveau.addItems(db.liste_niveaux(self.con))
        i = self.filtre_niveau.findText(courant)
        self.filtre_niveau.setCurrentIndex(max(i, 0))
        self.filtre_niveau.blockSignals(False)
        self._niveau_change()
        self._maj_boutons()

    @staticmethod
    def _fmt_date(d):
        return f" {d[8:10]}/{d[5:7]}" if d and len(d) >= 10 else ""

    def _cycle(self, s):
        """Étapes du cycle de vie pour la liste des sujets."""
        if s["etat"] != "genere":
            return "brouillon"
        etapes = ["généré" + self._fmt_date(s["date_generation"])]
        if s["date_scan"]:
            etapes.append("scanné" + self._fmt_date(s["date_scan"]))
        if s["date_correction"]:
            txt = "corrigé" + self._fmt_date(s["date_correction"])
            moy = self.con.execute(
                "SELECT AVG(r.note20) m FROM resultats r "
                "JOIN copies c ON c.id = r.copie_id "
                "WHERE c.sujet_id=?", (s["id"],)).fetchone()["m"]
            if moy is not None:
                txt += " · moy. " + f"{moy:.1f}".replace(".", ",") + "/20"
            etapes.append(txt)
        return " · ".join(etapes)

    def _niveau_valeur(self):
        n = self.filtre_niveau.currentText()
        return None if n in ("", "Tous niveaux") else n

    def _niveau_change(self):
        courant = self.filtre_chap.currentText()
        self.filtre_chap.blockSignals(True)
        self.filtre_chap.clear()
        self.filtre_chap.addItem("Tous")
        self.filtre_chap.addItems(
            db.liste_chapitres(self.con, self._niveau_valeur()))
        i = self.filtre_chap.findText(courant)
        self.filtre_chap.setCurrentIndex(max(i, 0))
        self.filtre_chap.blockSignals(False)
        self._recharger_banque()

    @staticmethod
    def _detail_usages(usages):
        return "\n".join(
            f"– {u['titre']} — {u['classe']}"
            + (f" ({u['niveau']})" if u["niveau"] else "")
            + f", {u['date_creation']}" for u in usages)

    def _recharger_banque(self):
        self.banque.clear()
        chap = self.filtre_chap.currentText()
        chap = None if chap in ("", "Tous") else chap
        deja = set(self._question_ids())
        usages = db.usages_questions(self.con)
        classe_id = self.classe.currentData()
        niveau_classe = ""
        if classe_id is not None:
            r = self.con.execute("SELECT niveau FROM classes WHERE id=?",
                                 (classe_id,)).fetchone()
            niveau_classe = r["niveau"] if r else ""
        for q in db.liste_questions(self.con, chap, None,
                                    self._niveau_valeur()):
            if q["id"] in deja:
                continue
            u = usages.get(q["id"], [])
            u_classe = [x for x in u if x["classe_id"] == classe_id]
            u_niveau = [x for x in u
                        if niveau_classe and x["niveau"] == niveau_classe]
            badge, tip = "", ""
            if u_classe:
                badge = "⚠ classe"
                tip = "Déjà donnée à cette classe :\n" \
                    + self._detail_usages(u_classe)
            elif u_niveau:
                badge = "• niveau"
                tip = f"Déjà donnée en {niveau_classe} :\n" \
                    + self._detail_usages(u_niveau)
            elif u:
                badge = f"⬩{len(u)}"
                tip = "Utilisée dans :\n" + self._detail_usages(u)
            it = QListWidgetItem(" ".join(q["enonce"].split())[:120])
            it.setData(Qt.UserRole, q["id"])
            meta = " · ".join(x for x in (q["niveau"], q["chapitre"]) if x)
            it.setData(ROLE_META, meta or "non classée")
            if badge:
                it.setData(ROLE_BADGE, badge)
            it.setToolTip(q["enonce"] + (f"\n\n{tip}" if tip else ""))
            self.banque.addItem(it)

    def _question_ids(self):
        return [self.table.item(r, 0).data(Qt.UserRole)
                for r in range(self.table.rowCount())]

    def _toggle_coefs(self, actif):
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 2)
            if it:
                it.setFlags(it.flags() | Qt.ItemIsEditable if actif
                            else it.flags() & ~Qt.ItemIsEditable)
                self._style_points(it, actif)
        self.points.setEnabled(not actif)

    def _style_points(self, it, actif):
        """Grise la colonne Points quand le barème uniforme s'applique :
        les coefficients saisis sont conservés mais ignorés."""
        couleur = theme.palette["texte" if actif else "desactive"]
        it.setForeground(QBrush(QColor(couleur)))
        it.setToolTip("" if actif else
                      "Coefficient conservé mais ignoré : le barème "
                      "uniforme « Points par question » s'applique.")

    # ------------------------------------------------------------ sujet
    def nouveau(self):
        self._autosave.stop()
        self.auto_enregistrer()          # modifications en attente
        self.sujet_id = None
        self._chargement = True
        self.liste.clearSelection()
        self.titre.setText("")
        self.points.setValue(1.0)
        self.coefs.setChecked(False)
        self.malus_actif.setChecked(False)
        self.malus.setValue(0.5)
        self.table.setRowCount(0)
        self._chargement = False
        self._recharger_banque()
        self._maj_boutons()
        self.titre.setFocus()

    def charger_selection(self, item, _=None):
        if item is None:
            return
        sid = item.data(Qt.UserRole)
        self._autosave.stop()
        self.auto_enregistrer()          # modifications en attente
        s = self.con.execute("SELECT * FROM sujets WHERE id=?",
                             (sid,)).fetchone()
        self.sujet_id = sid
        self._chargement = True
        self.titre.setText(s["titre"])
        self.points.setValue(s["points_defaut"])
        self.coefs.setChecked(bool(s["coef_actifs"]))
        self.malus_actif.setChecked(bool(s["malus_actif"]))
        self.malus.setValue(s["malus"])
        i = self.classe.findData(s["classe_id"])
        self.classe.setCurrentIndex(max(i, 0))
        self.table.setRowCount(0)
        for q in db.questions_du_sujet(self.con, sid):
            self._ligne_question(q["id"], q["chapitre"], q["enonce"],
                                 q["points"])
        self._chargement = False
        self._recharger_banque()
        self._maj_boutons()

    def _ligne_question(self, qid, chapitre, enonce, points):
        r = self.table.rowCount()
        self.table.insertRow(r)
        it = QTableWidgetItem(chapitre)
        it.setData(Qt.UserRole, qid)
        it.setFlags(it.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(r, 0, it)
        it = QTableWidgetItem(" ".join(enonce.split())[:80])
        it.setFlags(it.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(r, 1, it)
        it = QTableWidgetItem(f"{points:g}")
        if not self.coefs.isChecked():
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
        self._style_points(it, self.coefs.isChecked())
        self.table.setItem(r, 2, it)

    def _donnees_table(self):
        """(qid, chapitre, enonce, points) pour chaque ligne affichée."""
        out = []
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            try:
                pts = float(self.table.item(r, 2).text().replace(",", "."))
            except (ValueError, AttributeError):
                pts = 1.0
            out.append((it.data(Qt.UserRole), it.text(),
                        self.table.item(r, 1).text(), pts))
        return out

    def _remplir_table(self, donnees):
        self._chargement = True
        self.table.setRowCount(0)
        for qid, chap, enonce, pts in donnees:
            self._ligne_question(qid, chap, enonce, pts)
        self._chargement = False
        self._modifie()

    def deplacer_vers(self, lignes, cible):
        """Déplace les lignes sélectionnées avant la ligne `cible`."""
        donnees = self._donnees_table()
        prises = [donnees[r] for r in lignes]
        cible -= sum(1 for r in lignes if r < cible)
        reste = [d for i, d in enumerate(donnees) if i not in set(lignes)]
        for i, d in enumerate(prises):
            reste.insert(cible + i, d)
        self._remplir_table(reste)
        self.table.clearSelection()
        self.table.setRangeSelected(
            QTableWidgetSelectionRange(cible, 0,
                                       cible + len(prises) - 1, 2), True)

    def deposer_banque(self, cible):
        """Insère les questions sélectionnées de la banque à la position
        `cible` (fin de table pour le bouton « Ajouter au sujet »)."""
        donnees = self._donnees_table()
        deja = {d[0] for d in donnees}
        for i, it in enumerate(s for s in self.banque.selectedItems()
                               if s.data(Qt.UserRole) not in deja):
            qid = it.data(Qt.UserRole)
            q = self.con.execute("SELECT * FROM questions WHERE id=?",
                                 (qid,)).fetchone()
            donnees.insert(cible + i, (qid, q["chapitre"], q["enonce"], 1.0))
        self._remplir_table(donnees)
        self._recharger_banque()

    def ajouter_questions(self):
        self.deposer_banque(self.table.rowCount())

    def retirer_questions(self):
        lignes = sorted({i.row() for i in self.table.selectedIndexes()},
                        reverse=True)
        for r in lignes:
            self.table.removeRow(r)
        self._recharger_banque()
        self._modifie()

    def deplacer(self, delta):
        r = self.table.currentRow()
        cible = r + delta
        if r < 0 or not (0 <= cible < self.table.rowCount()):
            return
        for c in range(self.table.columnCount()):
            a, b = (self.table.takeItem(r, c), self.table.takeItem(cible, c))
            self.table.setItem(r, c, b)
            self.table.setItem(cible, c, a)
        self.table.setCurrentCell(cible, self.table.currentColumn() or 0)

    def enregistrer(self, silencieux=False):
        titre = self.titre.text().strip()
        if not titre:
            erreur(self, "Sujet", "Le titre est vide.")
            return None
        classe_id = self.classe.currentData()
        if classe_id is None:
            erreur(self, "Sujet", "Créez d'abord une classe.")
            return None
        if self.sujet_id is None:
            cur = self.con.execute(
                "INSERT INTO sujets(titre, classe_id, points_defaut,"
                " coef_actifs, malus_actif, malus) VALUES(?,?,?,?,?,?)",
                (titre, classe_id, self.points.value(),
                 int(self.coefs.isChecked()),
                 int(self.malus_actif.isChecked()), self.malus.value()))
            self.sujet_id = cur.lastrowid
        else:
            self.con.execute(
                "UPDATE sujets SET titre=?, classe_id=?, points_defaut=?,"
                " coef_actifs=?, malus_actif=?, malus=? WHERE id=?",
                (titre, classe_id, self.points.value(),
                 int(self.coefs.isChecked()),
                 int(self.malus_actif.isChecked()), self.malus.value(),
                 self.sujet_id))
        self.con.execute("DELETE FROM sujet_questions WHERE sujet_id=?",
                         (self.sujet_id,))
        for r in range(self.table.rowCount()):
            qid = self.table.item(r, 0).data(Qt.UserRole)
            try:
                pts = float(self.table.item(r, 2).text().replace(",", "."))
            except (ValueError, AttributeError):
                pts = 1.0
            self.con.execute(
                "INSERT INTO sujet_questions(sujet_id, question_id, ordre,"
                " points) VALUES(?,?,?,?)", (self.sujet_id, qid, r, pts))
        self.con.commit()
        if not silencieux:
            self.refresh()
        return self.sujet_id

    def supprimer(self):
        if self.sujet_id is None:
            return
        if confirmer(self, "Supprimer",
                     "Supprimer ce sujet, ses copies et ses corrections ?"):
            self._autosave.stop()
            self.con.execute("DELETE FROM sujets WHERE id=?",
                             (self.sujet_id,))
            self.con.commit()
            self.nouveau()
            self.refresh()

    # -------------------------------------------------------- génération
    def _maj_boutons(self):
        genere = False
        if self.sujet_id is not None:
            s = self.con.execute("SELECT etat FROM sujets WHERE id=?",
                                 (self.sujet_id,)).fetchone()
            genere = bool(s and s["etat"] == "genere")
        self.a_copies.setEnabled(genere)
        self.a_corrige.setEnabled(genere)
        self.a_dossier.setEnabled(self.sujet_id is not None)
        self.b_ouvrir.setEnabled(self.sujet_id is not None)

    def _ouvrir(self, nom):
        if self.sujet_id is not None:
            ouvrir_fichier(subject_dir(self.con, self.sujet_id) / nom)

    def generer(self):
        self._autosave.stop()
        sid = self.enregistrer(silencieux=True)
        if sid is None:
            return
        deja = self.con.execute(
            "SELECT 1 FROM copies WHERE sujet_id=? LIMIT 1",
            (sid,)).fetchone()
        if deja and not confirmer(
                self, "Régénérer",
                "Des copies existent déjà pour ce sujet. Régénérer "
                "efface la géométrie et les corrections associées. "
                "Continuer ?"):
            return
        self.b_generer.setEnabled(False)
        self.etat.setText("Génération en cours…")
        self._worker = Worker(self._generer_fn, sid)
        self._worker.progress.connect(self.etat.setText)
        self._worker.done.connect(self._genere_ok)
        self._worker.error.connect(self._genere_err)
        self._worker.start()

    def _generer_fn(self, sid, progress=None):
        return generer_sujet(self.con, sid, progress=progress)

    def _genere_ok(self, chemins):
        self.b_generer.setEnabled(True)
        nb = self.con.execute(
            "SELECT COUNT(*) n, COALESCE(SUM(nb_pages),0) p FROM copies "
            "WHERE sujet_id=?", (self.sujet_id,)).fetchone()
        self.etat.setText(
            f"Généré : {nb['n']} copies, {nb['p']} pages. "
            "Imprimez, faites composer, puis passez à l'onglet Correction.")
        self.refresh()

    def _genere_err(self, msg):
        self.b_generer.setEnabled(True)
        self.etat.setText("Échec de la génération.")
        erreur(self, "Génération", msg)
