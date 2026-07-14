"""Correction : analyse des PDF scannés, révision, résultats, exports."""

import statistics
from datetime import date
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog,
                               QHBoxLayout, QLabel, QListWidget,
                               QRadioButton, QScrollArea, QTableWidget,
                               QTableWidgetItem, QTabWidget, QVBoxLayout,
                               QWidget)

from .. import config as C
from .. import db, exports, grading
from ..omr import analyser_pdfs
from ..paths import subject_dir
from . import theme
from .widgets import (Worker, bouton, entete, erreur, info, ligne_boutons,
                      ouvrir_fichier)


class HistogrammeNotes(QWidget):
    """Répartition des notes sur 20, par tranches de 2 points."""

    def __init__(self):
        super().__init__()
        self.notes = []
        self.setMinimumHeight(240)

    def set_notes(self, notes):
        self.notes = list(notes)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = theme.palette
        p.fillRect(self.rect(), QColor(pal["surface"]))
        if not self.notes:
            p.end()
            return
        bins = [0] * 10
        for n in self.notes:
            bins[min(int(n // 2), 9)] += 1
        haut = max(bins)
        m_g, m_b, m_h = 16, 26, 22
        w = (self.width() - 2 * m_g) / 10
        zone_h = self.height() - m_b - m_h
        p.setPen(QColor(pal["bord"]))
        p.drawLine(m_g, self.height() - m_b,
                   self.width() - m_g, self.height() - m_b)
        for i, n in enumerate(bins):
            x = m_g + i * w
            h = zone_h * n / haut if haut else 0
            y = self.height() - m_b - h
            if n:
                p.fillRect(int(x + w * 0.15), int(y),
                           int(w * 0.7), int(h), QColor(pal["accent"]))
                p.setPen(QColor(pal["texte"]))
                p.drawText(int(x), int(y - 18), int(w), 16,
                           Qt.AlignCenter, str(n))
            p.setPen(QColor(pal["texte2"]))
            p.drawText(int(x), self.height() - m_b + 4, int(w), 18,
                       Qt.AlignCenter, f"{2 * i}–{2 * i + 2}")
        p.end()


class DialogRevision(QDialog):
    """Passe en revue les cases à vérifier : douteuses (marquage léger)
    et noircies-mais-entourées (réponse annulée par l'élève)."""

    def __init__(self, con, sujet_id, parent=None):
        super().__init__(parent)
        self.con = con
        self.sujet_id = sujet_id
        self.setWindowTitle("Révision des cases signalées")
        self.resize(760, 520)

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
        b_vide = bouton("Vide / annulée  (V)", None,
                        lambda: self.trancher("vide"))
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
        if self.case["etat"] == "cochee":
            nature = ("Case noircie mais <b>entourée</b> : l'élève semble "
                      "l'avoir annulée. Comptée seulement si vous "
                      "choisissez « Cochée ».")
        else:
            nature = "Marquage léger ou ambigu."
        self.contexte.setText(
            f"<b>{self.case['nom']} {self.case['prenom']}</b> "
            f"(copie {self.case['numero']}) — "
            f"question {self.case['q_ordre'] + 1}, réponse "
            f"<b>{lettre}</b> (encadrée en rouge)."
            f"<br>{nature}{self._autres_cases()}"
            f"<br>{reste} case(s) à vérifier.")
        pm = self._image_question()
        if pm is None:
            pm = QPixmap()
            if self.case["crop"]:
                pm.loadFromData(self.case["crop"])
        self.image.setPixmap(pm)
        self.ratio.setText(
            f"Noircissement intérieur : {self.case['ratio']:.0%} — "
            f"encre autour : {self.case['ratio_ext']:.0%}")

    def _autres_cases(self):
        """Avertit si d'autres cases de la même question sont noircies :
        trancher « cochée » donnerait alors une réponse multiple."""
        autres = self.con.execute(
            "SELECT cr.ordre, m.ratio, m.etat, m.decision FROM cases ca "
            "JOIN mesures m ON m.case_id = ca.id "
            "JOIN copie_reponses cr ON cr.copie_id = ca.copie_id "
            "  AND cr.question_id = ca.question_id "
            "  AND cr.reponse_id = ca.reponse_id "
            "WHERE ca.copie_id=? AND ca.question_id=? AND ca.id<>? "
            "ORDER BY cr.ordre",
            (self.case["copie_id"], self.case["question_id"],
             self.case["case_id"])).fetchall()
        noircies = [f"{chr(65 + a['ordre'])} ({a['ratio']:.0%})"
                    for a in autres
                    if (a["decision"] == "cochee"
                        or (a["decision"] is None and a["etat"] == "cochee"))]
        if not noircies:
            return "<br>Aucune autre case de la question n'est noircie."
        return ("<br>⚠ Autre(s) case(s) déjà noircie(s) sur cette "
                "question : <b>" + ", ".join(noircies) + "</b> — "
                "« Cochée » ici donnerait une réponse multiple.")

    def _image_question(self):
        """Découpe la question entière dans la page redressée et encadre
        la case à trancher. None si la page n'est plus disponible."""
        row = self.con.execute(
            "SELECT image_path FROM pages_scannees WHERE copie_id=? "
            "AND page=?", (self.case["copie_id"],
                           self.case["page"])).fetchone()
        if row is None or not Path(row["image_path"]).exists():
            return None
        cases = self.con.execute(
            "SELECT * FROM cases WHERE copie_id=? AND question_id=? "
            "AND page=?", (self.case["copie_id"], self.case["question_id"],
                           self.case["page"])).fetchall()
        if not cases:
            return None
        k = C.RECT_PX_PER_MM
        y0 = min(c["y_mm"] for c in cases) - 6
        y1 = max(c["y_mm"] + c["taille_mm"] for c in cases) + 5
        x0 = min(c["x_mm"] for c in cases) - 6
        x1 = C.PAGE_W_MM - 14
        page = QPixmap(row["image_path"])
        pm = page.copy(QRect(int(x0 * k), int(y0 * k),
                             int((x1 - x0) * k), int((y1 - y0) * k)))
        moi = next(c for c in cases if c["id"] == self.case["case_id"])
        p = QPainter(pm)
        p.setPen(QPen(QColor(theme.palette["rouge"]), 2))
        m = 3
        p.drawRect(int((moi["x_mm"] - x0) * k) - m,
                   int((moi["y_mm"] - y0) * k) - m,
                   int(moi["taille_mm"] * k) + 2 * m,
                   int(moi["taille_mm"] * k) + 2 * m)
        p.end()
        largeur = max(self.width() - 60, 400)
        if pm.width() > largeur:
            pm = pm.scaledToWidth(largeur, Qt.SmoothTransformation)
        elif pm.width() < largeur * 0.7:
            pm = pm.scaledToWidth(int(largeur * 0.85),
                                  Qt.SmoothTransformation)
        return pm

    def trancher(self, decision):
        grading.trancher(self.con, self.case["case_id"], decision)
        self.suivante()


class CorrectionPage(QWidget):
    def __init__(self, con):
        super().__init__()
        self.con = con
        self.resultats = None
        self._sid_calcule = None

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
                                        "cases signalées")
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
        self.b_reviser = bouton("Réviser les cases signalées", None,
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
        synthese = QWidget()
        slay = QVBoxLayout(synthese)
        self.resume = QLabel("Calculez les résultats pour voir la synthèse.")
        self.resume.setWordWrap(True)
        slay.addWidget(self.resume)
        self.histogramme = HistogrammeNotes()
        slay.addWidget(self.histogramme, 1)
        onglets.addTab(synthese, "Synthèse")
        stats_tab = QWidget()
        stlay = QVBoxLayout(stats_tab)
        note = QLabel(
            "Les questions sont mélangées différemment sur chaque copie : "
            "le N° renvoie à l'ordre du sujet (onglet Sujets), pas à la "
            "numérotation d'une copie. Fiez-vous à l'énoncé.")
        note.setObjectName("sousTitre")
        note.setWordWrap(True)
        stlay.addWidget(note)
        self.t_stats = QTableWidget(0, 6)
        self.t_stats.setHorizontalHeaderLabels(
            ["N° sujet", "Chapitre", "Réussite", "Faux", "Blancs",
             "Énoncé"])
        self.t_stats.horizontalHeader().setStretchLastSection(True)
        self.t_stats.setEditTriggers(QTableWidget.NoEditTriggers)
        stlay.addWidget(self.t_stats, 1)
        onglets.addTab(stats_tab, "Statistiques par question")
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
        sid = self.sujet.currentData()
        if sid is None or sid == self._sid_calcule:
            return
        # ré-affiche automatiquement les derniers résultats calculés
        s = self.con.execute(
            "SELECT date_correction, mode_correction FROM sujets "
            "WHERE id=?", (sid,)).fetchone()
        if s and s["date_correction"] and self.b_calculer.isEnabled():
            (self.mode_manuel if s["mode_correction"] == "manuel"
             else self.mode_auto).setChecked(True)
            self.calculer()

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
            f"Réviser les cases signalées ({douteuses})" if douteuses
            else "Réviser les cases signalées")
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
        self._sid_calcule = sid

        # archive les notes : ré-affichées à la prochaine ouverture,
        # et moyenne visible dans la liste des sujets
        self.con.execute(
            "DELETE FROM resultats WHERE copie_id IN "
            "(SELECT id FROM copies WHERE sujet_id=?)", (sid,))
        for r in self.resultats:
            self.con.execute(
                "INSERT INTO resultats(copie_id, note, total, note20) "
                "VALUES(?,?,?,?)",
                (r["copie_id"], r["note"], r["total"], r["note20"]))
        self.con.execute(
            "UPDATE sujets SET date_correction=date('now','localtime'),"
            " mode_correction=? WHERE id=?", (mode, sid))
        self.con.commit()

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
            nb_mult = sum(1 for q in res["questions"]
                          if q["statut"] == "multiple")
            if nb_mult:
                anomalies.append(f"{nb_mult} réponse(s) multiple(s)")
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
                    " ".join(s["enonce"].split())]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if c == 2:
                    t = s["reussite"]
                    couleur = ("vert" if t >= 2 / 3
                               else "orange" if t >= 1 / 3 else "rouge")
                    it.setForeground(QColor(theme.palette[couleur]))
                if c == 5:
                    it.setToolTip(s["enonce"])
                self.t_stats.setItem(r, c, it)

        notes20 = [res["note20"] for res in self.resultats]
        self.histogramme.set_notes(notes20)
        if notes20:
            def fr(x):
                return f"{x:.1f}".rstrip("0").rstrip(".").replace(".", ",")
            self.resume.setText(
                f"<b>{len(notes20)} copie(s)</b> — "
                f"moyenne <b>{fr(statistics.mean(notes20))}/20</b>, "
                f"médiane {fr(statistics.median(notes20))}, "
                f"min {fr(min(notes20))}, max {fr(max(notes20))}.")
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
        sid = self.sujet.currentData()
        base = subject_dir(self.con, sid) / "exports"
        base.mkdir(exist_ok=True)
        self.b_exporter.setEnabled(False)
        self._worker = Worker(self._exporter_fn, sid, base,
                              {k: c.isChecked() for k, c in cases.items()})
        self._worker.progress.connect(self.statut.setText)
        self._worker.done.connect(self._export_ok)
        self._worker.error.connect(self._export_err)
        self._worker.start()

    def _exporter_fn(self, sid, base, choix, progress=None):
        jour = date.today().isoformat()
        faits = []
        if choix["csv"]:
            progress("Export CSV…")
            faits.append(exports.export_csv_notes(
                self.resultats, base / f"notes_{jour}.csv"))
        if choix["pronote"]:
            progress("Export Pronote…")
            faits.append(exports.export_pronote(
                self.resultats, base / f"pronote_{jour}.csv"))
        if choix["stats"]:
            progress("Export statistiques…")
            faits.append(exports.export_stats(
                self.stats, base / f"stats_{jour}.csv"))
        if choix["pdf"]:
            progress("Copies annotées…")
            faits.append(exports.export_pdf_annotes(
                self.con, self.resultats, base / f"copies_{jour}.pdf"))
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
