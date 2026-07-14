"""Génération des sujets : LaTeX, QR codes, compilation, lecture du .aux.

Principe : un unique document contient toutes les copies (une copie = une
séquence de pages). Chaque case à cocher enregistre sa position exacte via
\\pdfsavepos (paquet zref), ce qui rend la correction insensible aux ratures
et aux cases entièrement noircies. Chaque page porte un QR code identifiant
(sujet, copie, page) et quatre marqueurs de coin pour le redressement.
"""

import os
import random
import re
import shutil
import subprocess
from pathlib import Path

import segno

from . import config as C
from . import db

SP_TO_MM = 25.4 / (65536 * 72.27)

# Sans ce drapeau, chaque pdflatex ouvre une fenêtre de console quand
# l'application tourne sans terminal (lancement par QCMScan.pyw).
_SANS_CONSOLE = (subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)


class LatexError(RuntimeError):
    pass


def verifier_texte_question(texte: str, emplacement: str) -> None:
    """Signale les esperluettes littérales avant de lancer pdflatex.

    Les énoncés sont volontairement du LaTeX brut. Une esperluette isolée y
    est toutefois presque toujours une faute de saisie : LaTeX la réserve aux
    tableaux et alignements, et exige ``\\&`` pour l'afficher.
    """
    if re.search(r"(?<!\\)(?:\\\\)*&", texte):
        raise LatexError(
            f"{emplacement} contient un « & » non échappé. "
            "Pour afficher une esperluette, écrivez « \\& ».")


def trouver_pdflatex(con=None) -> str:
    if con is not None:
        p = db.get_setting(con, "pdflatex")
        if p and Path(p).exists():
            return p
    p = shutil.which("pdflatex")
    if not p:
        raise LatexError(
            "pdflatex introuvable. Installez une distribution TeX (MiKTeX) "
            "ou indiquez son chemin dans les réglages.")
    return p


def escape_tex(s: str) -> str:
    """Échappe un texte brut (noms, titres) pour LaTeX."""
    rep = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
           "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
           "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(rep.get(ch, ch) for ch in s)


def fmt_points(p: float) -> str:
    s = f"{p:g}".replace(".", ",")
    return f"{s} pt" if p <= 1 else f"{s} pts"


# ------------------------------------------------------------------ tex

# Paquets LaTeX disponibles dans les énoncés et les réponses. Pour en
# ajouter un, une ligne ici suffit : il sera chargé à la fois pour les
# copies et pour l'aperçu de l'éditeur (MiKTeX installe automatiquement
# les paquets manquants à la première compilation).
PAQUETS_QUESTIONS = r"""\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[french]{babel}
\usepackage{amsmath,amssymb}
\usepackage{tikz}
\usepackage{graphicx}"""


def _preambule() -> str:
    m = C.MARK_MM
    marks = "".join(
        f"  \\AtPageLowerLeft{{\\put(\\LenToUnit{{{x:g}mm}},"
        f"\\LenToUnit{{{y:g}mm}}){{\\rule{{{m:g}mm}}{{{m:g}mm}}}}}}%\n"
        for x, y in [(10, 281), (194, 281), (10, 10), (194, 10)])
    qx, qy = C.QR_POS_PDF
    case = f"{C.CASE_MM:g}"
    return rf"""\documentclass[11pt,a4paper]{{article}}
{PAQUETS_QUESTIONS}
\usepackage[a4paper,left=20mm,right=20mm,top=26mm,bottom=24mm]{{geometry}}
\usepackage{{eso-pic}}
\usepackage{{zref-savepos,zref-abspage,zref-user}}
\pagestyle{{empty}}
\setlength{{\parindent}}{{0pt}}

\newcounter{{copiepage}}
\def\copieid{{0}}

% Marqueurs, QR et pied de page sur chaque page.
\AddToShipoutPictureBG{{%
  \stepcounter{{copiepage}}%
{marks}  \AtPageLowerLeft{{\put(\LenToUnit{{{qx:g}mm}},\LenToUnit{{{qy:g}mm}}){{%
    \edef\qrfile{{qr/c\copieid-p\arabic{{copiepage}}.png}}%
    \IfFileExists{{\qrfile}}{{\includegraphics[width={C.QR_SIZE_MM:g}mm]{{\qrfile}}}}{{}}}}}}%
  \AtPageLowerLeft{{\put(\LenToUnit{{105mm}},\LenToUnit{{12.5mm}}){{%
    \makebox(0,0){{\footnotesize Copie \copieid{{}} --
      page \arabic{{copiepage}}}}}}}}%
}}

% Case à cocher : la position exacte du coin inférieur gauche est
% enregistrée dans le .aux (posx/posy + page absolue).
\newcommand{{\qcase}}[1]{{\raisebox{{-0.9mm}}{{\zsavepos{{P-#1}}\zlabel{{A-#1}}%
  \setlength\unitlength{{1mm}}\linethickness{{0.5pt}}%
  \begin{{picture}}({case},{case})\put(0,0){{\framebox({case},{case}){{}}}}\end{{picture}}}}}}
"""


def _entete_copie(copie_num, eleve, classe_nom, titre, date_str,
                  malus=0.0) -> str:
    nom = escape_tex(f"{eleve['nom']} {eleve['prenom']}".strip())
    consigne_malus = (
        rf" Attention : une réponse fausse enlève {fmt_points(malus)} "
        "(une question sans réponse ne retire rien)." if malus else "")
    return rf"""\setcounter{{copiepage}}{{0}}\def\copieid{{{copie_num}}}%
\zlabel{{A-debut-{copie_num}}}%
{{\Large\bfseries {nom}}} \hfill {escape_tex(classe_nom)}\\[0.5mm]
{escape_tex(titre)} \hfill {escape_tex(date_str)}\\[-2mm]
\rule{{\linewidth}}{{0.4pt}}\\[0.5mm]
{{\small\itshape Noircissez complètement la case de votre réponse.
Une seule réponse par question. En cas d'erreur, entourez la case fautive
et noircissez la bonne.{consigne_malus}}}\\[2mm]
"""


def construire_tex(con, sujet_id) -> tuple[str, list[dict]]:
    """Construit le .tex complet et le plan des copies.

    Retourne (source, copies) où copies est une liste de dicts
    {numero, eleve_id, questions:[(qid, points, [reponse_rows])]}.
    """
    sujet = con.execute("SELECT * FROM sujets WHERE id=?",
                        (sujet_id,)).fetchone()
    classe = con.execute("SELECT * FROM classes WHERE id=?",
                         (sujet["classe_id"],)).fetchone()
    eleves = db.eleves_de(con, sujet["classe_id"])
    if not eleves:
        raise LatexError("La classe ne contient aucun élève.")
    sq = db.questions_du_sujet(con, sujet_id)
    if not sq:
        raise LatexError("Le sujet ne contient aucune question.")

    for q in sq:
        verifier_texte_question(q["enonce"], f"L'énoncé de la question {q['id']}")
        for r in db.reponses_de(con, q["id"]):
            verifier_texte_question(
                r["texte"], f"La réponse de la question {q['id']}")

    parts = [_preambule(), r"\begin{document}"]
    plan = []
    for i, eleve in enumerate(eleves):
        num = i + 1
        rng = random.Random(f"{sujet_id}:{num}:{eleve['id']}")
        questions = list(sq)
        rng.shuffle(questions)
        if i > 0:
            parts.append(r"\clearpage")
        parts.append(_entete_copie(
            num, eleve, classe["nom"], sujet["titre"],
            sujet["date_creation"],
            malus=sujet["malus"] if sujet["malus_actif"] else 0.0))
        qplan = []
        for pos, q in enumerate(questions, start=1):
            reps = list(db.reponses_de(con, q["id"]))
            rng.shuffle(reps)
            pts = q["points"] if sujet["coef_actifs"] else sujet["points_defaut"]
            lignes = [r"\noindent\begin{minipage}{\linewidth}",
                      rf"{{\bfseries Question {pos}}}\hfill"
                      rf"{{\small ({fmt_points(pts)})}}\par\vspace{{1mm}}",
                      q["enonce"], r"\par\vspace{1.5mm}"]
            for j, r in enumerate(reps):
                lettre = chr(65 + j)
                lignes.append(
                    rf"\qcase{{c{num}-q{q['id']}-r{r['id']}}}"
                    rf"~~\textbf{{{lettre}.}}~{r['texte']}"
                    r"\par\vspace{1.2mm}")
            lignes.append(r"\end{minipage}\par\vspace{4mm}")
            parts.append("\n".join(lignes))
            qplan.append((q["id"], pts, reps))
        plan.append({"numero": num, "eleve_id": eleve["id"],
                     "questions": qplan})
    parts.append(r"\end{document}")
    return "\n".join(parts), plan


# ------------------------------------------------------------- compilation

def _run_pdflatex(pdflatex, workdir: Path, texname: str):
    for _ in range(2):  # deux passes pour zref
        r = subprocess.run(
            [pdflatex, "-interaction=nonstopmode", "-halt-on-error",
             "-file-line-error", texname],
            cwd=str(workdir), capture_output=True, text=True,
            errors="replace", creationflags=_SANS_CONSOLE)
        if r.returncode != 0:
            log = (workdir / texname.replace(".tex", ".log"))
            tail = ""
            if log.exists():
                tail = log.read_text(errors="replace")[-3000:]
            raise LatexError("Échec de compilation LaTeX.\n" + tail)


def _parse_aux(aux_path: Path):
    """Retourne (positions, pages) : label -> (x_sp, y_sp) et label -> abspage."""
    txt = aux_path.read_text(errors="replace")
    positions, pages = {}, {}
    for m in re.finditer(r"\\zref@newlabel\{([^}]*)\}\{(.*)\}", txt):
        label, props = m.group(1), m.group(2)
        px = re.search(r"\\posx\{(-?\d+)\}", props)
        py = re.search(r"\\posy\{(-?\d+)\}", props)
        ap = re.search(r"\\abspage\{(\d+)\}", props)
        if px and py:
            positions[label] = (int(px.group(1)), int(py.group(1)))
        if ap:
            pages[label] = int(ap.group(1))
    return positions, pages


def generer_sujet(con, sujet_id, progress=None):
    """Génère copies.pdf + corrige.pdf et remplit la géométrie en base.

    progress : callable(str) facultatif pour l'UI.
    """
    from .paths import subject_dir
    import pypdfium2 as pdfium

    def say(msg):
        if progress:
            progress(msg)

    pdflatex = trouver_pdflatex(con)
    workdir = subject_dir(con, sujet_id)
    say("Préparation des copies…")
    source, plan = construire_tex(con, sujet_id)
    (workdir / "main.tex").write_text(source, encoding="utf-8")

    say("Génération des QR codes…")
    qrdir = workdir / "qr"
    qrdir.mkdir(exist_ok=True)
    for copie in plan:
        n = copie["numero"]
        for p in range(1, C.QR_MAX_PAGES + 1):
            f = qrdir / f"c{n}-p{p}.png"
            if not f.exists():
                segno.make(f"{C.QR_PREFIX}|{sujet_id}|{n}|{p}",
                           error="m").save(str(f), scale=10, border=2)

    say("Compilation pdflatex (2 passes)…")
    _run_pdflatex(pdflatex, workdir, "main.tex")

    say("Lecture des positions des cases…")
    positions, pages = _parse_aux(workdir / "main.aux")
    pdf = pdfium.PdfDocument(str(workdir / "main.pdf"))
    total_pages = len(pdf)
    pdf.close()

    debuts = {c["numero"]: pages.get(f"A-debut-{c['numero']}")
              for c in plan}
    if any(v is None for v in debuts.values()):
        raise LatexError("Positions incomplètes dans le .aux "
                         "(labels de début de copie manquants).")

    db.purger_generation(con, sujet_id)
    numeros = sorted(debuts)
    for idx, copie in enumerate(plan):
        n = copie["numero"]
        fin = (debuts[numeros[idx + 1]] - 1 if idx + 1 < len(numeros)
               else total_pages)
        nb_pages = fin - debuts[n] + 1
        cur = con.execute(
            "INSERT INTO copies(sujet_id, eleve_id, numero, nb_pages) "
            "VALUES(?,?,?,?)", (sujet_id, copie["eleve_id"], n, nb_pages))
        cid = cur.lastrowid
        for ordre_q, (qid, _pts, reps) in enumerate(copie["questions"]):
            con.execute(
                "INSERT INTO copie_questions VALUES(?,?,?)",
                (cid, qid, ordre_q))
            for ordre_r, r in enumerate(reps):
                con.execute(
                    "INSERT INTO copie_reponses VALUES(?,?,?,?)",
                    (cid, qid, r["id"], ordre_r))
                label = f"c{n}-q{qid}-r{r['id']}"
                if f"P-{label}" not in positions or f"A-{label}" not in pages:
                    raise LatexError(f"Case absente du .aux : {label}")
                x_sp, y_sp = positions[f"P-{label}"]
                page_loc = pages[f"A-{label}"] - debuts[n] + 1
                x_mm = x_sp * SP_TO_MM
                y_top = C.PAGE_H_MM - (y_sp * SP_TO_MM + C.CASE_MM)
                con.execute(
                    "INSERT INTO cases(copie_id, question_id, reponse_id,"
                    " page, x_mm, y_mm, taille_mm) VALUES(?,?,?,?,?,?,?)",
                    (cid, qid, r["id"], page_loc, x_mm, y_top, C.CASE_MM))
    con.execute("UPDATE sujets SET etat='genere', "
                "date_generation=date('now','localtime'), "
                "date_scan=NULL, date_correction=NULL WHERE id=?",
                (sujet_id,))
    con.commit()

    say("Corrigé maître…")
    generer_corrige(con, sujet_id, workdir, pdflatex)
    _nettoyer_auxiliaires(workdir)
    say("Terminé.")
    return workdir / "main.pdf", workdir / "corrige.pdf"


def _nettoyer_auxiliaires(workdir: Path):
    """Après compilation, ne garde que l'essentiel dans le dossier du
    sujet : les PDF et les sources .tex. Le .aux a déjà été lu (positions
    des cases) et les QR sont regénérés à chaque compilation."""
    for f in ("main.aux", "main.log", "corrige.aux", "corrige.log"):
        (workdir / f).unlink(missing_ok=True)
    shutil.rmtree(workdir / "qr", ignore_errors=True)


def generer_corrige(con, sujet_id, workdir: Path, pdflatex):
    """Corrigé maître : pour chaque copie, la lettre correcte par question."""
    sujet = con.execute("SELECT * FROM sujets WHERE id=?",
                        (sujet_id,)).fetchone()
    lignes = [r"""\documentclass[11pt,a4paper]{article}
\usepackage[T1]{fontenc}\usepackage[utf8]{inputenc}\usepackage[french]{babel}
\usepackage[a4paper,margin=18mm]{geometry}\usepackage{longtable}
\pagestyle{plain}\setlength{\parindent}{0pt}
\begin{document}""",
              rf"{{\Large\bfseries Corrigé maître --- "
              rf"{escape_tex(sujet['titre'])}}}\\[3mm]"]
    for copie in db.copies_du_sujet(con, sujet_id):
        qrows = con.execute(
            "SELECT question_id FROM copie_questions WHERE copie_id=? "
            "ORDER BY ordre", (copie["id"],)).fetchall()
        reps_txt = []
        for i, qr in enumerate(qrows, start=1):
            rows = con.execute(
                "SELECT cr.ordre, r.correcte FROM copie_reponses cr "
                "JOIN reponses r ON r.id = cr.reponse_id "
                "WHERE cr.copie_id=? AND cr.question_id=? ORDER BY cr.ordre",
                (copie["id"], qr["question_id"])).fetchall()
            lettre = next((chr(65 + r["ordre"]) for r in rows
                           if r["correcte"]), "?")
            reps_txt.append(f"{i}-{lettre}")
        nom = escape_tex(f"{copie['nom']} {copie['prenom']}".strip())
        lignes.append(rf"\textbf{{Copie {copie['numero']}}} --- {nom} : "
                      + ", ".join(reps_txt) + r"\\[1.5mm]")
    lignes.append(r"\end{document}")
    (workdir / "corrige.tex").write_text("\n".join(lignes), encoding="utf-8")
    _run_pdflatex(pdflatex, workdir, "corrige.tex")


# ------------------------------------------------------------- aperçu

def compiler_apercu(con, enonce, reponses, workdir: Path) -> Path:
    """Compile un aperçu PNG d'une question (éditeur de la banque)."""
    import pypdfium2 as pdfium

    verifier_texte_question(enonce, "L'énoncé")
    for i, (texte, _correcte) in enumerate(reponses, start=1):
        verifier_texte_question(texte, f"La réponse {i}")

    pdflatex = trouver_pdflatex(con)
    workdir.mkdir(parents=True, exist_ok=True)
    corps = [enonce, r"\par\vspace{2mm}"]
    for j, (texte, correcte) in enumerate(reponses):
        lettre = chr(65 + j)
        coche = r"$\boxtimes$" if correcte else r"$\square$"
        corps.append(rf"{coche}~\textbf{{{lettre}.}}~{texte}\par\vspace{{1mm}}")
    src = (r"\documentclass[preview,border=8pt,varwidth=160mm]{standalone}"
           "\n" + PAQUETS_QUESTIONS + "\n\\begin{document}\n"
           + "\n".join(corps) + "\n\\end{document}\n")
    (workdir / "apercu.tex").write_text(src, encoding="utf-8")
    r = subprocess.run(
        [pdflatex, "-interaction=nonstopmode", "-halt-on-error", "apercu.tex"],
        cwd=str(workdir), capture_output=True, text=True, errors="replace",
        creationflags=_SANS_CONSOLE)
    if r.returncode != 0:
        log = workdir / "apercu.log"
        tail = log.read_text(errors="replace")[-1500:] if log.exists() else ""
        raise LatexError("Erreur LaTeX dans la question.\n" + tail)
    pdf = pdfium.PdfDocument(str(workdir / "apercu.pdf"))
    page = pdf[0]
    bmp = page.render(scale=2.2)
    img = bmp.to_pil()
    out = workdir / "apercu.png"
    img.save(out)
    pdf.close()
    return out
