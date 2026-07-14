"""Analyse des PDF scannés.

Pipeline par page : rasterisation -> lecture du QR (identité de la page)
-> détection des quatre marqueurs de coin -> homographie vers la géométrie
de référence -> mesure du taux de noircissement de chaque case attendue.

Le QR sert aussi à orienter la page : le marqueur le plus proche du QR est
nécessairement le coin haut-droit, ce qui rend l'analyse insensible aux
pages scannées à l'envers ou en travers.
"""

import cv2
import numpy as np
import zxingcpp

from . import config as C
from .paths import scans_dir

RECT_W = int(C.PAGE_W_MM * C.RECT_PX_PER_MM)
RECT_H = int(C.PAGE_H_MM * C.RECT_PX_PER_MM)


class PageIgnoree(Exception):
    """Page non exploitable (QR illisible, marqueurs absents…)."""


# ------------------------------------------------------------ rasterisation

def iter_pages_pdf(pdf_path):
    """Itère les pages d'un PDF en niveaux de gris (numpy uint8)."""
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        for i in range(len(pdf)):
            bmp = pdf[i].render(scale=C.SCAN_DPI / 72)
            img = np.array(bmp.to_pil().convert("L"))
            yield i, img
    finally:
        pdf.close()


# ------------------------------------------------------------------- QR

def lire_qr(gray):
    """Retourne (sujet, copie, page, generation, centre_xy) ou lève
    PageIgnoree. generation vaut None pour les copies imprimées avant
    l'introduction du marquage (QR à quatre champs)."""
    results = zxingcpp.read_barcodes(gray)
    for r in results:
        txt = r.text or ""
        if not txt.startswith(C.QR_PREFIX + "|"):
            continue
        try:
            champs = txt.split("|")
            s, c, p = champs[1:4]
            gen = int(champs[4]) if len(champs) > 4 else None
            pos = r.position
            pts = [(pt.x, pt.y) for pt in
                   (pos.top_left, pos.top_right,
                    pos.bottom_right, pos.bottom_left)]
            cx = sum(q[0] for q in pts) / 4
            cy = sum(q[1] for q in pts) / 4
            return int(s), int(c), int(p), gen, (cx, cy)
        except (ValueError, AttributeError, IndexError):
            continue
    raise PageIgnoree("QR code introuvable ou illisible")


# --------------------------------------------------------------- marqueurs

def trouver_marqueurs(gray):
    """Retourne les 4 centroïdes des marqueurs de coin (px image)."""
    h, w = gray.shape
    px_mm = min(w / C.PAGE_W_MM, h / C.PAGE_H_MM)
    a_est = (C.MARK_MM * px_mm) ** 2
    _, bw = cv2.threshold(gray, 0, 255,
                          cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, _, stats, cents = cv2.connectedComponentsWithStats(bw)
    cand = []
    for i in range(1, n):
        x, y, ww, hh, area = stats[i]
        if not (0.35 * a_est < area < 4.0 * a_est):
            continue
        if not (0.55 < ww / max(hh, 1) < 1.8):
            continue
        if area / (ww * hh) < 0.6:          # doit être un carré plein
            continue
        cand.append(tuple(cents[i]))
    if len(cand) < 4:
        raise PageIgnoree("marqueurs de coin non détectés")

    coins = [(0, 0), (w, 0), (0, h), (w, h)]
    choisis, pris = [], set()
    for cx, cy in coins:
        ordre = sorted(cand, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)
        pt = next((p for p in ordre if p not in pris), None)
        d = ((pt[0] - cx) ** 2 + (pt[1] - cy) ** 2) ** 0.5 if pt else 1e9
        if pt is None or d > 0.35 * min(w, h):
            raise PageIgnoree("marqueurs de coin incomplets")
        pris.add(pt)
        choisis.append(pt)
    return choisis


def ordonner_marqueurs(marqueurs, qr_center):
    """Ordonne [haut-gauche, haut-droit, bas-gauche, bas-droit] du point de
    vue de la page imprimée, quel que soit le sens du scan."""
    qx, qy = qr_center
    tr = min(marqueurs, key=lambda p: (p[0] - qx) ** 2 + (p[1] - qy) ** 2)
    bl = max(marqueurs, key=lambda p: (p[0] - tr[0]) ** 2 + (p[1] - tr[1]) ** 2)
    reste = [p for p in marqueurs if p is not tr and p is not bl]
    v = (bl[0] - tr[0], bl[1] - tr[1])
    a, b = reste
    cross_a = v[0] * (a[1] - tr[1]) - v[1] * (a[0] - tr[0])
    tl, br = (a, b) if cross_a > 0 else (b, a)
    return [tl, tr, bl, br]


def redresser(gray, marqueurs_ordonnes):
    """Homographie vers l'image de référence (RECT_PX_PER_MM px/mm)."""
    src = np.float32(marqueurs_ordonnes)
    dst = np.float32([(x * C.RECT_PX_PER_MM, y * C.RECT_PX_PER_MM)
                      for x, y in C.MARK_CENTERS_TOP])
    H = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(gray, H, (RECT_W, RECT_H),
                               flags=cv2.INTER_LINEAR,
                               borderValue=255)


# ------------------------------------------------------------------ mesure

def _ratio_anneau(sombre, x0, y0, s, k):
    """Taux d'encre dans l'anneau autour de la case (case entourée)."""
    g = C.ANNEAU_RETRAIT_MM * k
    w = C.ANNEAU_LARGEUR_MM * k
    h_img, w_img = sombre.shape

    def zone(ax, ay, bx, by):
        ax, ay = max(int(round(ax)), 0), max(int(round(ay)), 0)
        bx = min(int(round(bx)), w_img)
        by = min(int(round(by)), h_img)
        if bx <= ax or by <= ay:
            return 0, 0
        r = sombre[ay:by, ax:bx]
        return int(r.sum()), r.size

    s_ext, n_ext = zone(x0 - g - w, y0 - g - w, x0 + s + g + w,
                        y0 + s + g + w)
    s_int, n_int = zone(x0 - g, y0 - g, x0 + s + g, y0 + s + g)
    aire = n_ext - n_int
    return (s_ext - s_int) / aire if aire > 0 else 0.0


def mesurer_cases(rect, cases_rows):
    """Mesure chaque case : {case_id: (ratio, ratio_ext, crop_png_bytes)}."""
    th, _ = cv2.threshold(rect, 0, 255,
                          cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    sombre = rect < th
    out = {}
    k = C.RECT_PX_PER_MM
    for row in cases_rows:
        s = row["taille_mm"] * k
        x0, y0 = row["x_mm"] * k, row["y_mm"] * k
        inset = s * C.CASE_SHRINK
        ax, ay = int(round(x0 + inset)), int(round(y0 + inset))
        bx, by = int(round(x0 + s - inset)), int(round(y0 + s - inset))
        ax, ay = max(ax, 0), max(ay, 0)
        bx = min(bx, rect.shape[1] - 1)
        by = min(by, rect.shape[0] - 1)
        roi = sombre[ay:by, ax:bx]
        ratio = float(roi.mean()) if roi.size else 0.0
        ratio_ext = _ratio_anneau(sombre, x0, y0, s, k)

        m = int(round(s * 0.55))
        cx0, cy0 = max(int(x0) - m, 0), max(int(y0) - m, 0)
        cx1 = min(int(x0 + s) + m, rect.shape[1])
        cy1 = min(int(y0 + s) + m, rect.shape[0])
        crop = rect[cy0:cy1, cx0:cx1]
        crop = cv2.resize(crop, None, fx=3, fy=3,
                          interpolation=cv2.INTER_CUBIC)
        ok, png = cv2.imencode(".png", crop)
        out[row["id"]] = (ratio, ratio_ext, png.tobytes() if ok else None)
    return out


def etat_depuis_ratio(ratio):
    if ratio <= C.SEUIL_VIDE:
        return "vide"
    if ratio >= C.SEUIL_COCHEE:
        return "cochee"
    return "douteuse"


# ------------------------------------------------------------ orchestration

def analyser_pdfs(con, sujet_id, pdf_paths, progress=None):
    """Analyse une liste de PDF scannés pour un sujet donné.

    Efface les mesures précédentes du sujet, puis stocke pour chaque case
    reconnue son ratio, son état et une vignette. Retourne un rapport.
    """
    def say(msg):
        if progress:
            progress(msg)

    copies = {r["numero"]: r["id"] for r in con.execute(
        "SELECT id, numero FROM copies WHERE sujet_id=?", (sujet_id,))}

    con.execute(
        "DELETE FROM mesures WHERE case_id IN "
        "(SELECT ca.id FROM cases ca JOIN copies co ON co.id=ca.copie_id "
        " WHERE co.sujet_id=?)", (sujet_id,))
    con.execute(
        "DELETE FROM pages_scannees WHERE copie_id IN "
        "(SELECT id FROM copies WHERE sujet_id=?)", (sujet_id,))
    con.commit()

    gen_courante = con.execute(
        "SELECT generation FROM sujets WHERE id=?",
        (sujet_id,)).fetchone()["generation"]
    rapport = {"pages_ok": 0, "pages_ignorees": [], "autre_sujet": 0,
               "autre_generation": 0}
    outdir = scans_dir(sujet_id)

    for pdf_path in pdf_paths:
        say(f"Lecture de {pdf_path}…")
        for idx, gray in iter_pages_pdf(pdf_path):
            ref = f"{pdf_path} p.{idx + 1}"
            try:
                s, num, page, gen, qr_center = lire_qr(gray)
                if s != sujet_id:
                    rapport["autre_sujet"] += 1
                    continue
                if gen is not None and gen != gen_courante:
                    rapport["autre_generation"] += 1
                    continue
                if num not in copies:
                    raise PageIgnoree(f"copie n°{num} inconnue")
                marqueurs = trouver_marqueurs(gray)
                ordres = ordonner_marqueurs(marqueurs, qr_center)
                rect = redresser(gray, ordres)
            except PageIgnoree as e:
                rapport["pages_ignorees"].append((ref, str(e)))
                continue

            copie_id = copies[num]
            img_path = outdir / f"copie_{num:03d}_p{page}.png"
            cv2.imwrite(str(img_path), rect)
            con.execute(
                "INSERT OR REPLACE INTO pages_scannees VALUES(?,?,?)",
                (copie_id, page, str(img_path)))

            cases_rows = con.execute(
                "SELECT * FROM cases WHERE copie_id=? AND page=?",
                (copie_id, page)).fetchall()
            mesures = mesurer_cases(rect, cases_rows)
            for case_id, (ratio, ratio_ext, crop) in mesures.items():
                con.execute(
                    "INSERT OR REPLACE INTO mesures"
                    "(case_id, ratio, ratio_ext, etat, decision, crop) "
                    "VALUES(?,?,?,?,NULL,?)",
                    (case_id, ratio, ratio_ext,
                     etat_depuis_ratio(ratio), crop))
            rapport["pages_ok"] += 1
            say(f"{ref} : copie {num}, page {page} analysée")
        con.commit()
    if rapport["pages_ok"]:
        con.execute("UPDATE sujets SET date_scan=date('now','localtime') "
                    "WHERE id=?", (sujet_id,))
        con.commit()
    return rapport
