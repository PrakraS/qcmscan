"""Classes et listes d'élèves : saisie directe, import CSV, collage."""

import csv

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog,
                               QHBoxLayout, QInputDialog, QLabel,
                               QListWidget, QListWidgetItem, QSplitter,
                               QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from .. import db
from .widgets import bouton, confirmer, entete, erreur, info, ligne_boutons


class ClassesPage(QWidget):
    def __init__(self, con):
        super().__init__()
        self.con = con
        racine = QVBoxLayout(self)
        racine.addWidget(entete(
            "Classes",
            "Listes d'élèves : saisie directe, import CSV ou collage "
            "depuis un tableur."))

        split = QSplitter()
        racine.addWidget(split, 1)

        gauche = QWidget()
        glay = QVBoxLayout(gauche)
        glay.setContentsMargins(0, 0, 8, 0)
        self.liste = QListWidget()
        self.liste.currentItemChanged.connect(self.charger_classe)
        glay.addWidget(self.liste, 1)
        glay.addWidget(ligne_boutons(
            bouton("Nouvelle classe", "primaire", self.nouvelle_classe),
            bouton("Renommer", on_click=self.renommer),
            bouton("Supprimer", "danger", self.supprimer_classe)))
        split.addWidget(gauche)

        droite = QWidget()
        dlay = QVBoxLayout(droite)
        dlay.setContentsMargins(8, 0, 0, 0)
        self._chargement = False
        lig = QHBoxLayout()
        lig.addWidget(QLabel("Niveau de la classe :"))
        self.niveau = QComboBox()
        self.niveau.setEditable(True)
        self.niveau.setMinimumWidth(150)
        self.niveau.setToolTip(
            "Sert aux indicateurs « déjà donnée à ce niveau » lors de "
            "la composition des sujets.")
        self.niveau.activated.connect(self._sauver_niveau)
        self.niveau.lineEdit().editingFinished.connect(self._sauver_niveau)
        lig.addWidget(self.niveau)
        lig.addStretch()
        dlay.addLayout(lig)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Nom", "Prénom"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 220)
        dlay.addWidget(self.table, 1)
        dlay.addWidget(ligne_boutons(
            bouton("Ajouter un élève", on_click=self.ajouter_eleve),
            bouton("Supprimer la sélection", on_click=self.supprimer_eleves),
            bouton("Importer un CSV…", on_click=self.importer_csv),
            bouton("Coller une liste", on_click=self.coller),
            bouton("Enregistrer la liste", "primaire", self.enregistrer)))
        self.compteur = QLabel("")
        self.compteur.setObjectName("sousTitre")
        dlay.addWidget(self.compteur)
        split.addWidget(droite)
        split.setSizes([260, 640])

        self.refresh()

    # ------------------------------------------------------------ classes
    def classe_id(self):
        it = self.liste.currentItem()
        return it.data(Qt.UserRole) if it else None

    def refresh(self):
        self._chargement = True
        self.niveau.clear()
        self.niveau.addItem("")
        self.niveau.addItems(db.liste_niveaux(self.con))
        self._chargement = False

        cid = self.classe_id()
        self.liste.blockSignals(True)
        self.liste.clear()
        for c in db.liste_classes(self.con):
            n = self.con.execute(
                "SELECT COUNT(*) n FROM eleves WHERE classe_id=?",
                (c["id"],)).fetchone()["n"]
            niv = f" — {c['niveau']}" if c["niveau"] else ""
            it = QListWidgetItem(f"{c['nom']}{niv}   ({n} élèves)")
            it.setData(Qt.UserRole, c["id"])
            self.liste.addItem(it)
            if c["id"] == cid:
                self.liste.setCurrentItem(it)
        self.liste.blockSignals(False)
        if self.liste.currentItem() is None and self.liste.count():
            self.liste.setCurrentRow(0)
        else:
            self.charger_classe(self.liste.currentItem())

    def nouvelle_classe(self):
        nom, ok = QInputDialog.getText(self, "Nouvelle classe",
                                       "Nom de la classe :")
        if ok and nom.strip():
            self.con.execute("INSERT INTO classes(nom) VALUES(?)",
                             (nom.strip(),))
            self.con.commit()
            self.refresh()

    def renommer(self):
        cid = self.classe_id()
        if cid is None:
            return
        actuel = self.con.execute("SELECT nom FROM classes WHERE id=?",
                                  (cid,)).fetchone()["nom"]
        nom, ok = QInputDialog.getText(self, "Renommer", "Nom :",
                                       text=actuel)
        if ok and nom.strip():
            self.con.execute("UPDATE classes SET nom=? WHERE id=?",
                             (nom.strip(), cid))
            self.con.commit()
            self.refresh()

    def supprimer_classe(self):
        cid = self.classe_id()
        if cid is None:
            return
        utilise = self.con.execute(
            "SELECT 1 FROM sujets WHERE classe_id=? LIMIT 1",
            (cid,)).fetchone()
        if utilise:
            erreur(self, "Impossible",
                   "Cette classe est utilisée par au moins un sujet.")
            return
        if confirmer(self, "Supprimer",
                     "Supprimer la classe et sa liste d'élèves ?"):
            self.con.execute("DELETE FROM classes WHERE id=?", (cid,))
            self.con.commit()
            self.refresh()

    # ------------------------------------------------------------- élèves
    def charger_classe(self, item, _=None):
        self.table.setRowCount(0)
        cid = item.data(Qt.UserRole) if item else None
        self._chargement = True
        if cid is None:
            self.niveau.setCurrentText("")
            self._chargement = False
            self.compteur.setText("")
            return
        c = self.con.execute("SELECT niveau FROM classes WHERE id=?",
                             (cid,)).fetchone()
        self.niveau.setCurrentText(c["niveau"] if c else "")
        self._chargement = False
        for e in db.eleves_de(self.con, cid):
            self._ligne(e["nom"], e["prenom"])
        self.compteur.setText(f"{self.table.rowCount()} élèves")

    def _sauver_niveau(self, *_):
        if self._chargement:
            return
        cid = self.classe_id()
        if cid is None:
            return
        niv = self.niveau.currentText().strip()
        actuel = self.con.execute(
            "SELECT niveau FROM classes WHERE id=?", (cid,)).fetchone()
        if actuel is None or actuel["niveau"] == niv:
            return
        self.con.execute("UPDATE classes SET niveau=? WHERE id=?",
                         (niv, cid))
        self.con.commit()
        if niv:
            db.ajouter_niveau(self.con, niv)
        self.refresh()

    def _ligne(self, nom="", prenom=""):
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem(nom))
        self.table.setItem(r, 1, QTableWidgetItem(prenom))

    def ajouter_eleve(self):
        self._ligne()
        self.table.setCurrentCell(self.table.rowCount() - 1, 0)
        self.table.editItem(self.table.currentItem())

    def supprimer_eleves(self):
        lignes = sorted({i.row() for i in self.table.selectedIndexes()},
                        reverse=True)
        for r in lignes:
            self.table.removeRow(r)

    def importer_csv(self):
        chemin, _ = QFileDialog.getOpenFileName(
            self, "Importer une liste", "", "CSV (*.csv *.txt)")
        if not chemin:
            return
        try:
            with open(chemin, encoding="utf-8-sig", newline="") as f:
                extrait = f.read(2048)
                f.seek(0)
                sep = ";" if extrait.count(";") >= extrait.count(",") else ","
                lignes = list(csv.reader(f, delimiter=sep))
        except OSError as e:
            erreur(self, "Import", str(e))
            return
        n = self._inserer_lignes(lignes)
        info(self, "Import", f"{n} élèves ajoutés au tableau. "
             "Pensez à enregistrer la liste.")

    def coller(self):
        texte = QApplication.clipboard().text()
        if not texte.strip():
            info(self, "Collage", "Le presse-papiers est vide.")
            return
        lignes = []
        for l in texte.splitlines():
            if "\t" in l:
                lignes.append(l.split("\t"))
            elif ";" in l:
                lignes.append(l.split(";"))
            else:
                lignes.append(l.split(None, 1))
        n = self._inserer_lignes(lignes)
        info(self, "Collage", f"{n} élèves ajoutés au tableau. "
             "Pensez à enregistrer la liste.")

    def _inserer_lignes(self, lignes):
        n = 0
        for l in lignes:
            l = [c.strip() for c in l if c is not None]
            if not l or not l[0]:
                continue
            if l[0].lower() in ("nom", "name"):
                continue
            self._ligne(l[0], l[1] if len(l) > 1 else "")
            n += 1
        return n

    def enregistrer(self):
        cid = self.classe_id()
        if cid is None:
            erreur(self, "Classes", "Créez d'abord une classe.")
            return
        genere = self.con.execute(
            "SELECT 1 FROM sujets WHERE classe_id=? AND etat='genere' "
            "LIMIT 1", (cid,)).fetchone()
        if genere and not confirmer(
                self, "Attention",
                "Des sujets ont déjà été générés pour cette classe.\n"
                "Modifier la liste ne change pas les copies déjà "
                "imprimées. Continuer ?"):
            return
        self.con.execute("DELETE FROM eleves WHERE classe_id=?", (cid,))
        for r in range(self.table.rowCount()):
            nom = (self.table.item(r, 0) or QTableWidgetItem()).text().strip()
            prenom = (self.table.item(r, 1)
                      or QTableWidgetItem()).text().strip()
            if nom:
                self.con.execute(
                    "INSERT INTO eleves(classe_id, nom, prenom) "
                    "VALUES(?,?,?)", (cid, nom, prenom))
        self.con.commit()
        self.refresh()
