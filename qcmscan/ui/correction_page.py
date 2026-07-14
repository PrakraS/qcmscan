"""Correction : analyse des PDF scannés, révision, résultats, exports."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog,
                               QHBoxLayout, QLabel, QListWidget,
                               QRadioButton, QScrollArea, QTableWidget,
                               QTableWidgetItem, QTabWidget, QVBoxLayout,
                               QWidget)

from .. import db, exports, grading
from ..omr import analyser_pdfs
from .widgets import (Worker, bouton, entete, erreur, info, ligne_boutons,
                      ouvrir_fichier)


class DialogRevision(QDialog):
    """Passe en revue les cases douteuses, une par une."""

    def __init__(self, con, sujet_id, parent=None):
        super().__init__(parent)
        self.con = con
        self.sujet_id = sujet_id
        self.setWindowTitle("Révision des cases douteuses")
        self.resize(460, 420)

        lay = QVBoxLayout(self)
        self.contexte = QLabel("")
        self.contexte.setWordWrap(True)
        lay.addWidget(self.contexte)
        self.image = QLabel()
        self.image.setAlignment(Qt.AlignCenter)
        self.image.setMinimumHeight(220)
        lay.addWidget(self.image, 1)
        self.ratio = QLabel("")
        self.ratio.setObjectName("sousTitre")
        lay.addWidget(self.ratio)

        b_cochee = bouton("Cochée  (C)", "primaire",
                          lambda: self.trancher("cochee"))
        b_vide = bouton("Vide  (V)", None, lambda: self.trancher("vide"))
        b_stop = bouton("Terminer plus tard", None, self.accept)
        lay.addWidget(ligne_boutons(b_cochee, b_vide, b_stop))
        b_cochee.setShortcut("C")
        b_vide.setShortcut("V")

        self.suivante()

    def suivante(self):
        rows = grading.cases_a_reviser(self.con, self.sujet_id)
        if not rows:
            self.accept()
            return
        self.case = rows[0]
        reste = len(rows)
        lettre = chr(65 + self.case["r_ordre"])
        self.contexte.setText(
            f"<b>{self.case['nom']} {self.case['prenom']}</b> "
            f"(copie {self.case['numero']}) — "
            f"question {self.case['q_ordre'] + 1}, réponse {lettre}."
            f"<br>{reste} case(s) à trancher.")
        pm = QPixmap()
        if self.case["crop"]:
            pm.loadFromData(self.case["crop"])
        self.image.setPixmap(pm)
        self.ratio.setText(
            f"Taux de noircissement mesuré : {self.case['ratio']:.0%}")

    def trancher(self, decision):
        grading.trancher(self.con, self.case["case_id"], decision)
        self.suivante()


class CorrectionPage(QWidget):
    def __init__(self, con):
        super().__init__()
        self.con = con
        self.resultats = None

        racine = QVBoxLayout(self)
        racine.addWidget(entete(
            "Correction",
            "Scannez les copies (recto, ordre indifférent, plusieurs PDF "
            "acceptés), puis lancez l'analyse."))

        lig = QHBoxLayout()
        lig.addWidget(QLabel("Sujet :"))
        self.sujet = QComboBox()
        self.sujet.setMinimumWidth(320)
        self.sujet.currentIndexChanged.connect(self._sujet_change)
        lig.addWidget(self.sujet)
        lig.addStretch()
        self.mode_auto = QRadioButton("Correction automatique")
        self.mode_manuel = QRadioButton("Avec révision manuelle des "
                                        "cases douteuses")
        self.mode_auto.setChecked(True)
        lig.addWidget(self.mode_auto)
        lig.addWidget(self.mode_manuel)
        racine.addLayout(lig)

        lig = QHBoxLayout()
        self.fichiers = QListWidget()
        self.fichiers.setMaximumHeight(84)
        lig.addWidget(self.fichiers, 1)
        col = QVBoxLayout()
        col.addWidget(bouton("Ajouter des PDF…", None, self.ajouter_pdf))
        col.addWidget(bouton("Vider la liste", None, self.fichiers.clear))
        col.addStretch()
        lig.addLayout(col)
        racine.addLayout(lig)

        self.b_analyser = bouton("Lancer l'analyse", "primaire",
                                 self.analyser)
        self.b_reviser = bouton("Réviser les cases douteuses", None,
                                self.reviser)
        self.b_calculer = bouton("Calculer les résultats", None,
                                 self.calculer)
        self.b_exporter = bouton("Exporter…", None, self.exporter)
        racine.addWidget(ligne_boutons(self.b_analyser, self.b_reviser,
                                       self.b_calculer, self.b_exporter))
        self.statut = QLabel("")
        self.statut.setObjectName("sousTitre")
        self.statut.setWordWrap(True)
        racine.addWidget(self.statut)

        onglets = QTabWidget()
        self.t_notes = QTableWidget(0, 5)
        self.t_notes.setHorizontalHeaderLabels(
            ["Élève", "Note", "Note /20", "Anomalies", "Détail"])
        self.t_notes.setColumnWidth(0, 200)
        self.t_notes.setColumnWidth(3, 150)
        self.t_notes.horizontalHeader().setStretchLastSection(True)
        self.t_notes.setEditTriggers(QTableWidget.NoEditTriggers)
        onglets.addTab(self.t_notes, "Notes")
        self.t_stats = QTableWidget(0, 6)
        self.t_stats.setHorizontalHeaderLabels(
            ["N°", "Chapitre", "Réussite", "Faux", "Blancs", "Énoncé"])
        self.t_stats.horizontalHeader().setStretchLastSection(True)
        self.t_stats.setEditTriggers(QTableWidget.NoEditTriggers)
        onglets.addTab(self.t_stats, "Statistiques par question")
        racine.addWidget(onglets, 1)

        self.refresh()

    # ------------------------------------------------------------- état
    def refresh(self):
        sid = self.sujet.currentData()
        self.sujet.blockSignals(True)
        self.sujet.clear()
        for s in self.con.execute(
                "SELECT s.id, s.titre, c.nom FROM sujets s "
                "JOIN classes c ON c.id=s.classe_id "
                "WHERE s.etat='genere' ORDER BY s.id DESC"):
            self.sujet.addItem(f"{s['titre']} — {s['nom']}", s["id"])
        if sid is not None:
            i = self.sujet.findData(sid)
            if i >= 0:
                self.sujet.setCurrentIndex(i)
        self.sujet.blockSignals(False)
        self._sujet_change()

    def _sujet_change(self, *_):
        self._maj_boutons()

    def _maj_boutons(self):
        sid = self.sujet.currentData()
        a_mesures = douteuses = 0
        if sid is not None:
            a_mesures = self.con.execute(
                "SELECT COUNT(*) n FROM mesures m JOIN cases ca ON "
                "ca.id=m.case_id JOIN copies co ON co.id=ca.copie_id "
                "WHERE co.sujet_id=?", (sid,)).fetchone()["n"]
            douteuses = len(grading.cases_a_reviser(self.con, sid))
        self.b_analyser.setEnabled(sid is not None)
        self.b_reviser.setEnabled(douteuses > 0)
        self.b_reviser.setText(
            f"Réviser les cases douteuses ({douteuses})" if douteuses
            else "Réviser les cases douteuses")
        self.b_calculer.setEnabled(a_mesures > 0)
        self.b_exporter.setEnabled(self.resultats is not None)

    # ----------------------------------------------------------- analyse
    def ajouter_pdf(self):
        chemins, _ = QFileDialog.getOpenFileNames(
            self, "PDF scannés", "", "PDF (*.pdf)")
        for c in chemins:
            self.fichiers.addItem(c)

    def analyser(self):
        sid = self.sujet.currentData()
        pdfs = [self.fichiers.item(i).text()
                for i in range(self.fichiers.count())]
        if not pdfs:
            erreur(self, "Analyse", "Ajoutez au moins un PDF scanné.")
            return
        self.b_analyser.setEnabled(False)
        self.resultats = None
        self._worker = Worker(self._analyser_fn, sid, pdfs)
        self._worker.progress.connect(self.statut.setText)
        self._worker.done.connect(self._analyse_ok)
        self._worker.error.connect(self._analyse_err)
        self._worker.start()

    def _analyser_fn(self, sid, pdfs, progress=None):
        return analyser_pdfs(self.con, sid, pdfs, progress=progress)

    def _analyse_ok(self, rapport):
        self.b_analyser.setEnabled(True)
        msg = [f"{rapport['pages_ok']} page(s) analysée(s)."]
        if rapport["autre_sujet"]:
            msg.append(f"{rapport['autre_sujet']} page(s) d'un autre sujet "
                       "ignorée(s).")
        if rapport["pages_ignorees"]:
            details = " ; ".join(f"{ref} ({raison})" for ref, raison
                                 in rapport["pages_ignorees"][:8])
            msg.append(f"{len(rapport['pages_ignorees'])} page(s) non "
                       f"exploitables : {details}")
        self.statut.setText(" ".join(msg))
        self._maj_boutons()
        if self.mode_manuel.isChecked() and self.b_reviser.isEnabled():
            self.reviser()

    def _analyse_err(self, msg):
        self.b_analyser.setEnabled(True)
        erreur(self, "Analyse", msg)

    def reviser(self):
        sid = self.sujet.currentData()
        DialogRevision(self.con, sid, self).exec()
        self._maj_boutons()

    # --------------------------------------------------------- résultats
    def calculer(self):
        sid = self.sujet.currentData()
        mode = "auto" if self.mode_auto.isChecked() else "manuel"
        self.resultats = grading.corriger_sujet(self.con, sid, mode)
        self.stats = grading.stats_questions(self.con, sid, self.resultats)

        self.t_notes.setRowCount(0)
        for res in sorted(self.resultats,
                          key=lambda r: (r["nom"], r["prenom"])):
            r = self.t_notes.rowCount()
            self.t_notes.insertRow(r)
            anomalies = []
            if res["pages_manquantes"]:
                anomalies.append("pages manquantes : " + ",".join(
                    map(str, res["pages_manquantes"])))
            nb_rev = sum(1 for q in res["questions"]
                         if q["statut"] == "a_reviser")
            if nb_rev:
                anomalies.append(f"{nb_rev} à réviser")
            detail = "  ".join(
                f"{q['ordre']}:{self._sym(q)}" for q in res["questions"])
            vals = [res["eleve"],
                    f"{res['note']:g} / {res['total']:g}",
                    f"{res['note20']:g}",
                    ", ".join(anomalies), detail]
            for c, v in enumerate(vals):
                self.t_notes.setItem(r, c, QTableWidgetItem(v))

        self.t_stats.setRowCount(0)
        for s in self.stats:
            r = self.t_stats.rowCount()
            self.t_stats.insertRow(r)
            vals = [str(s["num"]), s["chapitre"],
                    f"{s['reussite']:.0%}", str(s["faux"]),
                    str(s["blanc"]),
                    " ".join(s["enonce"].split())[:80]]
            for c, v in enumerate(vals):
                self.t_stats.setItem(r, c, QTableWidgetItem(v))
        self.statut.setText("Résultats calculés.")
        self._maj_boutons()

    @staticmethod
    def _sym(q):
        return {"juste": "J", "faux": "F", "blanc": "B", "multiple": "M",
                "incomplet": "?", "a_reviser": "R"}.get(q["statut"], "?")

    # ----------------------------------------------------------- exports
    def exporter(self):
        if not self.resultats:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Exporter les résultats")
        lay = QVBoxLayout(dlg)
        cases = {
            "csv": QCheckBox("Notes en CSV (Nom;Prénom;Note;Note/20)"),
            "pronote": QCheckBox("CSV pour Pronote (note sur 20)"),
            "pdf": QCheckBox("Copies annotées (un PDF, cases surlignées)"),
            "stats": QCheckBox("Statistiques par question (CSV)"),
        }
        for c in cases.values():
            c.setChecked(True)
            lay.addWidget(c)
        lay.addWidget(ligne_boutons(
            bouton("Exporter", "primaire", dlg.accept),
            bouton("Annuler", None, dlg.reject)))
        if dlg.exec() != QDialog.Accepted:
            return
        dossier = QFileDialog.getExistingDirectory(
            self, "Dossier de destination")
        if not dossier:
            return
        sid = self.sujet.currentData()
        base = Path(dossier)
        self.b_exporter.setEnabled(False)
        self._worker = Worker(self._exporter_fn, sid, base,
                              {k: c.isChecked() for k, c in cases.items()})
        self._worker.progress.connect(self.statut.setText)
        self._worker.done.connect(self._export_ok)
        self._worker.error.connect(self._export_err)
        self._worker.start()

    def _exporter_fn(self, sid, base, choix, progress=None):
        s = self.con.execute("SELECT titre FROM sujets WHERE id=?",
                             (sid,)).fetchone()
        slug = "".join(ch if ch.isalnum() else "_"
                       for ch in s["titre"]).strip("_") or f"sujet_{sid}"
        faits = []
        if choix["csv"]:
            progress("Export CSV…")
            faits.append(exports.export_csv_notes(
                self.resultats, base / f"notes_{slug}.csv"))
        if choix["pronote"]:
            progress("Export Pronote…")
            faits.append(exports.export_pronote(
                self.resultats, base / f"pronote_{slug}.csv"))
        if choix["stats"]:
            progress("Export statistiques…")
            faits.append(exports.export_stats(
                self.stats, base / f"stats_{slug}.csv"))
        if choix["pdf"]:
            progress("Copies annotées…")
            faits.append(exports.export_pdf_annotes(
                self.con, self.resultats, base / f"copies_{slug}.pdf"))
        return base, faits

    def _export_ok(self, res):
        base, faits = res
        self.b_exporter.setEnabled(True)
        self.statut.setText(f"{len(faits)} fichier(s) exporté(s) "
                            f"dans {base}.")
        ouvrir_fichier(base)

    def _export_err(self, msg):
        self.b_exporter.setEnabled(True)
        erreur(self, "Export", msg)
