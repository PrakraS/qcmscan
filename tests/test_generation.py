"""Boucle complète réelle : LaTeX -> PDF -> remplissage simulé -> correction.

Compile un vrai sujet avec pdflatex, rasterise les copies, noircit des
cases selon un plan connu, ré-emballe en PDF « scanné » (avec déformation)
et vérifie que les notes calculées correspondent au plan.
"""

import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pypdfium2 as pdfium
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import qcmscan.paths as paths

TMP = Path(tempfile.mkdtemp())
paths.data_dir = lambda: TMP
paths.sujets_root = lambda: TMP / "sujets"

from qcmscan import config as C
from qcmscan import db, grading
from qcmscan.latexgen import generer_sujet
from qcmscan.omr import analyser_pdfs

PXMM = C.SCAN_DPI / 25.4


def deformer(img, rot180=False):
    h, w = img.shape
    src = np.float32([(0, 0), (w, 0), (0, h), (w, h)])
    dst = np.float32([(5, 8), (w - 3, 4), (3, h - 6), (w - 8, h - 2)])
    out = cv2.warpPerspective(img, cv2.getPerspectiveTransform(src, dst),
                              (w, h), borderValue=255)
    return cv2.rotate(out, cv2.ROTATE_180) if rot180 else out


def main():
    con = db.connect(TMP / "test.db")
    con.execute("INSERT INTO classes(id, nom) VALUES(1, '1G2')")
    eleves = [("DUPONT", "Alice"), ("MARTIN", "Bob"), ("N'GUYEN", "Chloé")]
    for i, (n, p) in enumerate(eleves, start=1):
        con.execute("INSERT INTO eleves(id, classe_id, nom, prenom) "
                    "VALUES(?,1,?,?)", (i, n, p))
    enonces = [
        r"Soit $f(x) = x^2 + 3x$. Que vaut $f'(x)$ ?",
        r"Résoudre $x^2 = 25$ dans $\mathbb{R}$.",
        r"La fonction $x \mapsto \mathrm{e}^x$ est :",
        r"Que vaut $\displaystyle\lim_{x\to+\infty} \frac{1}{x}$ ?",
        r"Si $u_n = 3n - 2$, la suite $(u_n)$ est :",
    ]
    reps = [
        [(r"$2x + 3$", 1), (r"$2x$", 0), (r"$x^2 + 3$", 0), (r"$2x^2$", 0)],
        [(r"$x=5$ ou $x=-5$", 1), (r"$x=5$", 0), (r"$x=-5$", 0),
         (r"$x=12{,}5$", 0)],
        [("croissante sur $\\mathbb{R}$", 1), ("décroissante", 0),
         ("constante", 0), ("non monotone", 0)],
        [(r"$0$", 1), (r"$+\infty$", 0), (r"$1$", 0), (r"$-\infty$", 0)],
        [("arithmétique de raison $3$", 1), ("géométrique de raison $3$", 0),
         ("arithmétique de raison $-2$", 0), ("ni l'un ni l'autre", 0)],
    ]
    for qid, (en, rr) in enumerate(zip(enonces, reps), start=1):
        db.sauver_question(con, None, "Chapitre test", en, rr)
        assert qid == con.execute(
            "SELECT MAX(id) m FROM questions").fetchone()["m"]
    con.execute("INSERT INTO sujets(id, titre, classe_id, points_defaut,"
                " coef_actifs) VALUES(1,'QCM Dérivation — test',1,2.0,0)")
    for i in range(5):
        con.execute("INSERT INTO sujet_questions(sujet_id, question_id,"
                    " ordre, points) VALUES(1,?,?,2.0)", (i + 1, i))
    con.commit()

    pdf_copies, pdf_corrige = generer_sujet(con, 1, progress=print)
    assert pdf_copies.exists() and pdf_corrige.exists()

    nb_cases = con.execute(
        "SELECT COUNT(*) n FROM cases ca JOIN copies co ON "
        "co.id=ca.copie_id WHERE co.sujet_id=1").fetchone()["n"]
    assert nb_cases == 3 * 5 * 4, nb_cases
    print(f"{nb_cases} cases positionnées, OK")

    # Plan de remplissage : copie 1 tout juste ; copie 2 tout faux ;
    # copie 3 : justes sur q impaires, blanc sur q paires.
    def mode_pour(numero, qid):
        if numero == 1:
            return "correct"
        if numero == 2:
            return "faux"
        return "correct" if qid % 2 == 1 else None

    copies = db.copies_du_sujet(con, 1)
    offset = {}
    cum = 0
    for c in copies:
        offset[c["id"]] = cum
        cum += c["nb_pages"]

    doc = pdfium.PdfDocument(str(pdf_copies))
    pages_px = [np.array(doc[i].render(scale=C.SCAN_DPI / 72)
                         .to_pil().convert("L")) for i in range(len(doc))]
    doc.close()
    assert len(pages_px) == cum, (len(pages_px), cum)

    attendu = {}
    for c in copies:
        note = 0.0
        for qid in range(1, 6):
            m = mode_pour(c["numero"], qid)
            if m == "correct":
                note += 2.0
            if m is None:
                continue
            row = con.execute(
                "SELECT ca.* FROM cases ca JOIN reponses r ON "
                "r.id=ca.reponse_id WHERE ca.copie_id=? AND "
                "ca.question_id=? AND r.correcte=? "
                "ORDER BY ca.reponse_id LIMIT 1",
                (c["id"], qid, 1 if m == "correct" else 0)).fetchone()
            img = pages_px[offset[c["id"]] + row["page"] - 1]
            x0, y0 = row["x_mm"] * PXMM, row["y_mm"] * PXMM
            s = row["taille_mm"] * PXMM
            cv2.rectangle(img, (int(x0 + 2), int(y0 + 2)),
                          (int(x0 + s - 2), int(y0 + s - 2)), 0, -1)
        attendu[c["numero"]] = note

    # « Scan » : pages dans le désordre, déformées, certaines à l'envers.
    ordre = list(range(len(pages_px)))
    ordre.reverse()
    imgs = [Image.fromarray(deformer(pages_px[i], rot180=(i % 2 == 0)))
            for i in ordre]
    scan = TMP / "scan.pdf"
    imgs[0].save(scan, save_all=True, append_images=imgs[1:],
                 resolution=C.SCAN_DPI)

    rapport = analyser_pdfs(con, 1, [scan], progress=lambda m: None)
    print("Rapport scan :", rapport["pages_ok"], "pages OK,",
          len(rapport["pages_ignorees"]), "ignorées")
    assert rapport["pages_ok"] == cum
    assert not rapport["pages_ignorees"], rapport["pages_ignorees"]

    res = grading.corriger_sujet(con, 1, mode="auto")
    for r in sorted(res, key=lambda r: r["numero"]):
        print(f"Copie {r['numero']} ({r['eleve']}) : {r['note']} / "
              f"{r['total']}  statuts="
              f"{[q['statut'] for q in r['questions']]}")
        assert r["note"] == attendu[r["numero"]], (r["note"], attendu)
        assert r["total"] == 10.0
        assert not r["pages_manquantes"]

    print("\nGÉNÉRATION + CORRECTION RÉELLES : OK")


if __name__ == "__main__":
    main()
