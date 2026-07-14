"""Test de bout en bout : scans synthétiques -> analyse -> notation -> exports.

Simule des copies imprimées (marqueurs + QR + cases), leur applique des
déformations réalistes (perspective, rotation 180°), les emballe en PDF et
vérifie que l'analyse retrouve les bonnes réponses.
"""

import io
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
import segno
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qcmscan import config as C
from qcmscan import db, grading, exports
from qcmscan.omr import analyser_pdfs

PXMM = C.SCAN_DPI / 25.4
W, H = int(210 * PXMM), int(297 * PXMM)


def mm(v):
    return int(round(v * PXMM))


def page_vierge(sujet, copie, page):
    img = np.full((H, W), 255, np.uint8)
    for cx, cy in C.MARK_CENTERS_TOP:
        s = C.MARK_MM / 2
        cv2.rectangle(img, (mm(cx - s), mm(cy - s)),
                      (mm(cx + s), mm(cy + s)), 0, -1)
    buf = io.BytesIO()
    segno.make(f"{C.QR_PREFIX}|{sujet}|{copie}|{page}",
               error="m").save(buf, kind="png", scale=10, border=2)
    qr = np.array(Image.open(buf).convert("L"))
    qx, qy = C.QR_POS_PDF
    x0, y0 = mm(qx), mm(297 - qy - C.QR_SIZE_MM)
    side = mm(C.QR_SIZE_MM)
    qr = cv2.resize(qr, (side, side), interpolation=cv2.INTER_AREA)
    img[y0:y0 + side, x0:x0 + side] = qr
    return img


def dessiner_case(img, x_mm, y_mm, remplir=None):
    """remplir: None (vide), 'plein', 'croix'."""
    s = C.CASE_MM
    p0, p1 = (mm(x_mm), mm(y_mm)), (mm(x_mm + s), mm(y_mm + s))
    cv2.rectangle(img, p0, p1, 0, 2)
    if remplir == "plein":
        cv2.rectangle(img, p0, p1, 0, -1)
    elif remplir == "croix":
        cv2.line(img, p0, p1, 0, 4)
        cv2.line(img, (p0[0], p1[1]), (p1[0], p0[1]), 0, 4)


def deformer(img, rot180=False):
    """Légère perspective + option rotation 180°."""
    h, w = img.shape
    src = np.float32([(0, 0), (w, 0), (0, h), (w, h)])
    dst = np.float32([(6, 9), (w - 4, 3), (2, h - 7), (w - 9, h - 3)])
    M = cv2.getPerspectiveTransform(src, dst)
    out = cv2.warpPerspective(img, M, (w, h), borderValue=255)
    if rot180:
        out = cv2.rotate(out, cv2.ROTATE_180)
    return out


def main():
    tmp = Path(tempfile.mkdtemp())
    import qcmscan.paths as paths
    paths.data_dir = lambda: tmp  # isole les données du test

    con = db.connect(tmp / "test.db")
    con.execute("INSERT INTO classes(id, nom) VALUES(1, 'Test 1G1')")
    con.execute("INSERT INTO eleves(id, classe_id, nom, prenom) "
                "VALUES(1, 1, 'DUPONT', 'Alice'), (2, 1, 'MARTIN', 'Bob')")
    for qid in (1, 2):
        con.execute("INSERT INTO questions(id, chapitre, enonce) "
                    "VALUES(?, 'Dérivation', ?)", (qid, f"Question {qid}"))
        for j in range(4):
            con.execute(
                "INSERT INTO reponses(id, question_id, texte, correcte,"
                " ordre) VALUES(?,?,?,?,?)",
                (qid * 10 + j, qid, f"rep{j}", int(j == 1), j))
    con.execute("INSERT INTO sujets(id, titre, classe_id, points_defaut,"
                " coef_actifs) VALUES(1, 'Interro test', 1, 2.0, 0)")
    for i, qid in enumerate((1, 2)):
        con.execute("INSERT INTO sujet_questions(sujet_id, question_id,"
                    " ordre, points) VALUES(1, ?, ?, 1.0)", (qid, i))

    # Copies : ordre des réponses = ordre de la banque (pas de mélange ici,
    # le mélange est testé par la génération LaTeX, pas par l'OMR).
    layout = {}
    for num, eleve in ((1, 1), (2, 2)):
        cur = con.execute(
            "INSERT INTO copies(sujet_id, eleve_id, numero, nb_pages) "
            "VALUES(1, ?, ?, 1)", (eleve, num))
        cid = cur.lastrowid
        y = 60.0
        for i, qid in enumerate((1, 2)):
            con.execute("INSERT INTO copie_questions VALUES(?,?,?)",
                        (cid, qid, i))
            for j in range(4):
                rid = qid * 10 + j
                con.execute("INSERT INTO copie_reponses VALUES(?,?,?,?)",
                            (cid, qid, rid, j))
                x_mm, y_mm = 25.0, y
                con.execute(
                    "INSERT INTO cases(copie_id, question_id, reponse_id,"
                    " page, x_mm, y_mm, taille_mm) VALUES(?,?,?,1,?,?,?)",
                    (cid, qid, rid, x_mm, y_mm, C.CASE_MM))
                layout[(num, qid, j)] = (x_mm, y_mm)
                y += 9.0
            y += 6.0
    con.commit()

    # Copie 1 : Q1 bonne réponse noircie (j=1) -> juste ;
    #           Q2 mauvaise réponse noircie (j=2) -> faux.
    p1 = page_vierge(1, 1, 1)
    for (num, qid, j), (x, y) in layout.items():
        if num != 1:
            continue
        rempli = ("plein" if (qid, j) in ((1, 1), (2, 2)) else None)
        dessiner_case(p1, x, y, rempli)
    p1 = deformer(p1)

    # Copie 2 (scannée à l'envers) : Q1 croix sur la bonne réponse
    # -> douteuse puis tranchée 'cochee' ; Q2 blanc.
    p2 = page_vierge(1, 2, 1)
    for (num, qid, j), (x, y) in layout.items():
        if num != 2:
            continue
        dessiner_case(p2, x, y, "croix" if (qid, j) == (1, 1) else None)
    p2 = deformer(p2, rot180=True)

    scan = tmp / "scan.pdf"
    pages = [Image.fromarray(p) for p in (p1, p2)]
    pages[0].save(scan, save_all=True, append_images=pages[1:],
                  resolution=C.SCAN_DPI)

    rapport = analyser_pdfs(con, 1, [scan])
    assert rapport["pages_ok"] == 2, rapport
    assert not rapport["pages_ignorees"], rapport

    ratios = {}
    for r in con.execute(
            "SELECT ca.copie_id, ca.question_id, ca.reponse_id, m.ratio,"
            " m.etat, co.numero FROM mesures m JOIN cases ca ON"
            " ca.id=m.case_id JOIN copies co ON co.id=ca.copie_id"):
        ratios[(r["numero"], r["question_id"], r["reponse_id"])] = \
            (r["ratio"], r["etat"])
    print("Mesures :")
    for k in sorted(ratios):
        print(f"  copie {k[0]} q{k[1]} r{k[2]} : ratio={ratios[k][0]:.3f} "
              f"etat={ratios[k][1]}")

    assert ratios[(1, 1, 11)][1] == "cochee"
    assert ratios[(1, 2, 22)][1] == "cochee"
    assert ratios[(1, 1, 10)][1] == "vide"
    croix = ratios[(2, 1, 11)]
    assert croix[1] in ("douteuse", "cochee"), croix

    # Mode manuel : la croix est douteuse -> on tranche.
    res = grading.corriger_sujet(con, 1, mode="manuel")
    r2 = next(r for r in res if r["numero"] == 2)
    if croix[1] == "douteuse":
        assert r2["questions"][0]["statut"] == "a_reviser"
        aq = grading.cases_a_reviser(con, 1)
        assert len(aq) >= 1
        grading.trancher(con, aq[0]["case_id"], "cochee")

    res = grading.corriger_sujet(con, 1, mode="manuel")
    r1 = next(r for r in res if r["numero"] == 1)
    r2 = next(r for r in res if r["numero"] == 2)
    s1 = [q["statut"] for q in r1["questions"]]
    s2 = [q["statut"] for q in r2["questions"]]
    print("Copie 1 :", s1, "note", r1["note"], "/", r1["total"])
    print("Copie 2 :", s2, "note", r2["note"], "/", r2["total"])
    assert s1 == ["juste", "faux"] and r1["note"] == 2.0
    assert s2 == ["juste", "blanc"] and r2["note"] == 2.0
    assert r1["total"] == 4.0

    stats = grading.stats_questions(con, 1, res)
    exports.export_csv_notes(res, tmp / "notes.csv")
    exports.export_pronote(res, tmp / "pronote.csv")
    exports.export_stats(stats, tmp / "stats.csv")
    exports.export_pdf_annotes(con, res, tmp / "annotees.pdf")
    print("Exports OK :", (tmp / "annotees.pdf").stat().st_size, "octets")
    print("\nPIPELINE COMPLET : OK")


if __name__ == "__main__":
    main()
