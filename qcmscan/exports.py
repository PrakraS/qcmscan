"""Exports des résultats : CSV, Pronote, copies annotées, statistiques."""

import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import config as C

_FR = dict(delimiter=";", lineterminator="\n")


def _fr_num(x):
    return f"{x:g}".replace(".", ",")


def export_csv_notes(resultats, out_path: Path):
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, **_FR)
        w.writerow(["Nom", "Prénom", "Note", "Barème", "Note/20"])
        for r in sorted(resultats, key=lambda r: (r["nom"], r["prenom"])):
            w.writerow([r["nom"], r["prenom"], _fr_num(r["note"]),
                        _fr_num(r["total"]), _fr_num(r["note20"])])
    return out_path


def export_pronote(resultats, out_path: Path):
    """CSV minimal Nom;Prénom;Note sur 20, décimales à virgule, prêt à
    coller/importer dans Pronote."""
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, **_FR)
        for r in sorted(resultats, key=lambda r: (r["nom"], r["prenom"])):
            w.writerow([r["nom"], r["prenom"], _fr_num(r["note20"])])
    return out_path


def export_stats(stats, out_path: Path):
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, **_FR)
        w.writerow(["N°", "Chapitre", "Réussite %", "Justes", "Faux",
                    "Blancs", "Multiples", "Énoncé"])
        for s in stats:
            w.writerow([s["num"], s["chapitre"],
                        _fr_num(round(100 * s["reussite"], 1)),
                        s["juste"], s["faux"], s["blanc"], s["multiple"],
                        s["enonce"][:120].replace("\n", " ")])
    return out_path


# ------------------------------------------------------------ PDF annotés

def _police(taille):
    for nom in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(nom, taille)
        except OSError:
            continue
    return ImageFont.load_default()


VERT = (0, 150, 60)
ROUGE = (205, 40, 40)
ORANGE = (225, 130, 0)


def export_pdf_annotes(con, resultats, out_path: Path):
    """Un PDF unique : toutes les copies redressées, cases surlignées,
    note tamponnée en tête de première page."""
    k = C.RECT_PX_PER_MM
    police = _police(int(5.5 * k))
    images = []
    for res in sorted(resultats, key=lambda r: r["numero"]):
        pages = {r["page"]: r["image_path"] for r in con.execute(
            "SELECT page, image_path FROM pages_scannees WHERE copie_id=?",
            (res["copie_id"],))}
        annots = {}   # page -> [(x, y, s, couleur, epaisseur)]
        for q in res["questions"]:
            for row in con.execute(
                    "SELECT * FROM cases WHERE copie_id=? AND question_id=?",
                    (res["copie_id"], q["question_id"])):
                rid = row["reponse_id"]
                couleur = None
                if rid == q["correcte_id"]:
                    couleur, ep = VERT, 3
                    if q["statut"] in ("faux", "blanc", "multiple"):
                        ep = 4
                if rid in q["cochees"] and rid != q["correcte_id"]:
                    couleur, ep = ROUGE, 4
                if couleur:
                    annots.setdefault(row["page"], []).append(
                        (row["x_mm"] * k, row["y_mm"] * k,
                         row["taille_mm"] * k, couleur, ep))
        for page in sorted(pages):
            img = Image.open(pages[page]).convert("RGB")
            d = ImageDraw.Draw(img)
            marge = 1.2 * k
            for x, y, s, couleur, ep in annots.get(page, []):
                d.rectangle([x - marge, y - marge, x + s + marge,
                             y + s + marge], outline=couleur, width=ep)
            if page == 1:
                txt = (f"Note : {_fr_num(res['note'])} / "
                       f"{_fr_num(res['total'])}"
                       f"   ({_fr_num(res['note20'])}/20)")
                if res["pages_manquantes"]:
                    txt += "   [pages manquantes : " + ", ".join(
                        map(str, res["pages_manquantes"])) + "]"
                d.text((22 * k, 3 * k), txt, fill=ROUGE, font=police)
            images.append(img)
    if not images:
        raise RuntimeError("Aucune page scannée à annoter.")
    dpi = 25.4 * k
    images[0].save(out_path, save_all=True, append_images=images[1:],
                   resolution=dpi)
    return out_path
