"""Couche de persistance SQLite. Un seul fichier de base, schéma simple."""

import re
import sqlite3
from pathlib import Path

_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY,
    chapitre TEXT NOT NULL DEFAULT '',
    niveau TEXT NOT NULL DEFAULT '',
    enonce TEXT NOT NULL,
    actif INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS reponses (
    id INTEGER PRIMARY KEY,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    texte TEXT NOT NULL,
    correcte INTEGER NOT NULL DEFAULT 0,
    ordre INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS classes (
    id INTEGER PRIMARY KEY,
    nom TEXT NOT NULL,
    niveau TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS eleves (
    id INTEGER PRIMARY KEY,
    classe_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    nom TEXT NOT NULL,
    prenom TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS sujets (
    id INTEGER PRIMARY KEY,
    titre TEXT NOT NULL,
    classe_id INTEGER NOT NULL REFERENCES classes(id),
    date_creation TEXT NOT NULL DEFAULT (date('now')),
    points_defaut REAL NOT NULL DEFAULT 1.0,
    coef_actifs INTEGER NOT NULL DEFAULT 0,
    malus_actif INTEGER NOT NULL DEFAULT 0,  -- points négatifs si faux
    malus REAL NOT NULL DEFAULT 0.5,
    etat TEXT NOT NULL DEFAULT 'brouillon'   -- brouillon | genere
);

CREATE TABLE IF NOT EXISTS sujet_questions (
    sujet_id INTEGER NOT NULL REFERENCES sujets(id) ON DELETE CASCADE,
    question_id INTEGER NOT NULL REFERENCES questions(id),
    ordre INTEGER NOT NULL,
    points REAL NOT NULL DEFAULT 1.0,
    PRIMARY KEY (sujet_id, question_id)
);

CREATE TABLE IF NOT EXISTS copies (
    id INTEGER PRIMARY KEY,
    sujet_id INTEGER NOT NULL REFERENCES sujets(id) ON DELETE CASCADE,
    eleve_id INTEGER NOT NULL REFERENCES eleves(id) ON DELETE CASCADE,
    numero INTEGER NOT NULL,
    nb_pages INTEGER NOT NULL DEFAULT 0
);

-- Ordre des questions imprimé sur chaque copie.
CREATE TABLE IF NOT EXISTS copie_questions (
    copie_id INTEGER NOT NULL REFERENCES copies(id) ON DELETE CASCADE,
    question_id INTEGER NOT NULL REFERENCES questions(id),
    ordre INTEGER NOT NULL,
    PRIMARY KEY (copie_id, question_id)
);

-- Ordre des réponses imprimé pour chaque question de chaque copie.
CREATE TABLE IF NOT EXISTS copie_reponses (
    copie_id INTEGER NOT NULL REFERENCES copies(id) ON DELETE CASCADE,
    question_id INTEGER NOT NULL REFERENCES questions(id),
    reponse_id INTEGER NOT NULL REFERENCES reponses(id),
    ordre INTEGER NOT NULL,
    PRIMARY KEY (copie_id, question_id, reponse_id)
);

-- Géométrie des cases (issue du .aux), coordonnées mm origine haut-gauche.
CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY,
    copie_id INTEGER NOT NULL REFERENCES copies(id) ON DELETE CASCADE,
    question_id INTEGER NOT NULL REFERENCES questions(id),
    reponse_id INTEGER NOT NULL REFERENCES reponses(id),
    page INTEGER NOT NULL,           -- page locale de la copie (1..n)
    x_mm REAL NOT NULL,
    y_mm REAL NOT NULL,              -- bord supérieur de la case
    taille_mm REAL NOT NULL
);

-- Résultat de mesure d'une case après analyse d'un scan.
CREATE TABLE IF NOT EXISTS mesures (
    case_id INTEGER PRIMARY KEY REFERENCES cases(id) ON DELETE CASCADE,
    ratio REAL NOT NULL,
    ratio_ext REAL NOT NULL DEFAULT 0,  -- encre autour (case entourée)
    etat TEXT NOT NULL,              -- vide | cochee | douteuse
    decision TEXT,                   -- vide | cochee (tranché manuellement)
    crop BLOB                        -- PNG de la case pour la révision
);

CREATE TABLE IF NOT EXISTS pages_scannees (
    copie_id INTEGER NOT NULL REFERENCES copies(id) ON DELETE CASCADE,
    page INTEGER NOT NULL,
    image_path TEXT NOT NULL,
    PRIMARY KEY (copie_id, page)
);

CREATE TABLE IF NOT EXISTS settings (
    cle TEXT PRIMARY KEY,
    valeur TEXT NOT NULL
);
"""


def connect(path: Path) -> sqlite3.Connection:
    # check_same_thread=False : la connexion est partagée avec les threads
    # de travail (génération, analyse) ; l'UI sérialise les accès en
    # désactivant les actions pendant les traitements.
    con = sqlite3.connect(str(path), check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(_SCHEMA)
    _migrer(con)
    return con


NIVEAUX_DEFAUT = ("Seconde", "1SPE", "1NonSPE", "1TECHNO", "TCOMP", "TSPE")


def _migrer(con):
    """Ajoute aux bases existantes les colonnes et tables apparues depuis
    leur création (CREATE TABLE IF NOT EXISTS ne modifie pas les tables
    déjà en place)."""
    cols = {r[1] for r in con.execute("PRAGMA table_info(sujets)")}
    if "malus_actif" not in cols:
        con.execute("ALTER TABLE sujets ADD COLUMN malus_actif INTEGER "
                    "NOT NULL DEFAULT 0")
        con.execute("ALTER TABLE sujets ADD COLUMN malus REAL "
                    "NOT NULL DEFAULT 0.5")
        con.commit()
    cols = {r[1] for r in con.execute("PRAGMA table_info(questions)")}
    if "niveau" not in cols:
        con.execute("ALTER TABLE questions ADD COLUMN niveau TEXT "
                    "NOT NULL DEFAULT ''")
        con.execute("ALTER TABLE classes ADD COLUMN niveau TEXT "
                    "NOT NULL DEFAULT ''")
        con.commit()
    cols = {r[1] for r in con.execute("PRAGMA table_info(mesures)")}
    if "ratio_ext" not in cols:
        con.execute("ALTER TABLE mesures ADD COLUMN ratio_ext REAL "
                    "NOT NULL DEFAULT 0")
        con.commit()
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                       "AND name='niveaux'").fetchone():
        # catalogue des niveaux proposés dans les listes déroulantes ;
        # une question garde son niveau même s'il quitte le catalogue
        con.execute("CREATE TABLE niveaux ("
                    "nom TEXT PRIMARY KEY, ordre INTEGER NOT NULL)")
        for i, nom in enumerate(NIVEAUX_DEFAUT):
            con.execute("INSERT INTO niveaux VALUES(?,?)", (nom, i))
        con.commit()


# ----------------------------------------------------------------- niveaux

def liste_niveaux(con):
    """Catalogue ordonné, complété des niveaux encore portés par des
    questions actives (un niveau retiré du catalogue reste visible tant
    que des questions le portent)."""
    cat = [r["nom"] for r in con.execute(
        "SELECT nom FROM niveaux ORDER BY ordre, nom")]
    portes = [r["niveau"] for r in con.execute(
        "SELECT DISTINCT niveau FROM questions WHERE actif=1 "
        "AND niveau<>'' ORDER BY niveau")]
    return cat + [n for n in portes if n not in cat]


def ajouter_niveau(con, nom):
    nom = (nom or "").strip()
    if not nom:
        return
    con.execute(
        "INSERT OR IGNORE INTO niveaux(nom, ordre) "
        "VALUES(?, (SELECT COALESCE(MAX(ordre), -1) + 1 FROM niveaux))",
        (nom,))
    con.commit()


def supprimer_niveau(con, nom):
    """Retire le niveau du catalogue ; les questions qui le portent ne
    sont pas modifiées."""
    con.execute("DELETE FROM niveaux WHERE nom=?", (nom,))
    con.commit()


# --------------------------------------------------------------- questions

def liste_chapitres(con, niveau=None):
    q = "SELECT DISTINCT chapitre FROM questions WHERE actif=1"
    args = []
    if niveau:
        q += " AND niveau=?"
        args.append(niveau)
    rows = con.execute(q + " ORDER BY chapitre", args).fetchall()
    return [r["chapitre"] for r in rows if r["chapitre"]]


def liste_questions(con, chapitre=None, recherche=None, niveau=None):
    q = "SELECT * FROM questions WHERE actif=1"
    args = []
    if niveau:
        q += " AND niveau=?"
        args.append(niveau)
    if chapitre:
        q += " AND chapitre=?"
        args.append(chapitre)
    if recherche:
        q += " AND enonce LIKE ?"
        args.append(f"%{recherche}%")
    q += " ORDER BY niveau, chapitre, id"
    return con.execute(q, args).fetchall()


def usages_questions(con):
    """question_id -> liste des sujets où elle figure (titre, classe,
    niveau de la classe, date), pour les indicateurs « déjà utilisée »."""
    out = {}
    for r in con.execute(
            "SELECT sq.question_id AS qid, s.titre, s.date_creation,"
            "       s.classe_id, c.nom AS classe, c.niveau "
            "FROM sujet_questions sq "
            "JOIN sujets s ON s.id = sq.sujet_id "
            "JOIN classes c ON c.id = s.classe_id ORDER BY s.id"):
        out.setdefault(r["qid"], []).append(r)
    return out


def reponses_de(con, question_id):
    return con.execute(
        "SELECT * FROM reponses WHERE question_id=? ORDER BY ordre, id",
        (question_id,)).fetchall()


def sauver_question(con, qid, chapitre, enonce, reponses, niveau=""):
    """reponses : liste de (texte, correcte). Retourne l'id.

    Les réponses existantes sont modifiées en place quand leur nombre ne
    change pas : les copies déjà générées référencent leurs ids
    (copie_reponses, cases), qu'un DELETE violerait.
    """
    niveau = (niveau or "").strip()
    if niveau:
        ajouter_niveau(con, niveau)   # un niveau tapé rejoint le catalogue
    if qid is None:
        cur = con.execute(
            "INSERT INTO questions(chapitre, niveau, enonce) VALUES(?,?,?)",
            (chapitre, niveau, enonce))
        qid = cur.lastrowid
        anciennes = []
    else:
        con.execute(
            "UPDATE questions SET chapitre=?, niveau=?, enonce=? WHERE id=?",
            (chapitre, niveau, enonce, qid))
        anciennes = reponses_de(con, qid)
    if len(anciennes) == len(reponses):
        for old, (i, (texte, correcte)) in zip(anciennes,
                                               enumerate(reponses)):
            con.execute(
                "UPDATE reponses SET texte=?, correcte=?, ordre=? WHERE id=?",
                (texte, int(correcte), i, old["id"]))
    else:
        try:
            con.execute("DELETE FROM reponses WHERE question_id=?", (qid,))
            for i, (texte, correcte) in enumerate(reponses):
                con.execute(
                    "INSERT INTO reponses(question_id, texte, correcte,"
                    " ordre) VALUES(?,?,?,?)", (qid, texte, int(correcte), i))
        except sqlite3.IntegrityError:
            con.rollback()
            raise ValueError(
                "Cette question figure sur des copies déjà générées : "
                "impossible d'ajouter ou de retirer des réponses (les "
                "copies imprimées y font référence). Vous pouvez modifier "
                "les textes et déplacer la bonne réponse, ou créer une "
                "nouvelle question.") from None
    con.commit()
    return qid


def supprimer_question(con, qid):
    """Envoie la question à la corbeille (suppression douce)."""
    con.execute("UPDATE questions SET actif=0 WHERE id=?", (qid,))
    con.commit()


def questions_corbeille(con):
    return con.execute(
        "SELECT * FROM questions WHERE actif=0 ORDER BY chapitre, id"
    ).fetchall()


def restaurer_question(con, qid):
    con.execute("UPDATE questions SET actif=1 WHERE id=?", (qid,))
    con.commit()


def detruire_question(con, qid):
    """Suppression définitive ; refusée si un sujet ou des copies y font
    référence (la question reste alors dans la corbeille)."""
    try:
        con.execute("DELETE FROM questions WHERE id=?", (qid,))
    except sqlite3.IntegrityError:
        con.rollback()
        raise ValueError(
            "Cette question est utilisée par un sujet ou des copies "
            "générées : elle ne peut pas être supprimée définitivement."
        ) from None
    con.commit()


def exporter_questions(con, chapitre=None, recherche=None, niveau=None):
    """Banque (filtrée) sous forme de liste de dicts sérialisables JSON."""
    out = []
    for q in liste_questions(con, chapitre, recherche, niveau):
        out.append({
            "niveau": q["niveau"],
            "chapitre": q["chapitre"],
            "enonce": q["enonce"],
            "reponses": [{"texte": r["texte"],
                          "correcte": bool(r["correcte"])}
                         for r in reponses_de(con, q["id"])],
        })
    return out


def parser_questions_texte(texte, chapitre_defaut="", niveau_defaut=""):
    """Convertit le format texte « collable » en liste pour importer_questions.

    Un bloc par question, blocs séparés par une ligne vide :

        [Niveau | Chapitre]               (facultatif ; « [Chapitre] » seul
        Énoncé, éventuellement sur         fonctionne aussi)
        plusieurs lignes. LaTeX autorisé.
        * bonne réponse
        - autre réponse
        - autre réponse

    Une ligne de réponse qui ne tient pas sur une ligne peut continuer
    sur la suivante (sans « - » ni « * » en tête).
    """
    questions = []
    blocs = [b for b in re.split(r"\n\s*\n", texte.strip()) if b.strip()]
    for i, bloc in enumerate(blocs, start=1):
        lignes = bloc.strip().splitlines()
        chapitre, niveau = chapitre_defaut, niveau_defaut
        if lignes and re.fullmatch(r"\[.+\]", lignes[0].strip()):
            entete = lignes[0].strip()[1:-1]
            if "|" in entete:
                niveau, chapitre = (s.strip() for s in entete.split("|", 1))
            else:
                chapitre = entete.strip()
            lignes = lignes[1:]
        enonce, reponses = [], []
        for ligne in lignes:
            m = re.match(r"^\s*([-*])\s+(.*)$", ligne)
            if m:
                reponses.append({"texte": m.group(2).strip(),
                                 "correcte": m.group(1) == "*"})
            elif reponses:
                reponses[-1]["texte"] += " " + ligne.strip()
            else:
                enonce.append(ligne)
        if not enonce or not reponses:
            raise ValueError(
                f"Bloc {i} : il faut un énoncé puis les réponses, "
                "« * » ou « - » suivi d'une espace en début de ligne.")
        questions.append({"niveau": niveau, "chapitre": chapitre,
                          "enonce": "\n".join(enonce).strip(),
                          "reponses": reponses})
    if not questions:
        raise ValueError("Aucune question trouvée dans le texte.")
    return questions


def importer_questions(con, data):
    """Importe une liste au format d'exporter_questions.

    Les doublons exacts (même chapitre et même énoncé qu'une question
    active) sont ignorés. Retourne (ajoutées, ignorées).
    """
    if not isinstance(data, list):
        raise ValueError("Format inattendu : le fichier doit contenir "
                         "une liste de questions.")
    ajoutees = ignorees = 0
    for i, q in enumerate(data, start=1):
        try:
            chapitre = str(q.get("chapitre", "")).strip()
            niveau = str(q.get("niveau", "")).strip()
            enonce = str(q["enonce"]).strip()
            reponses = [(str(r["texte"]), bool(r.get("correcte")))
                        for r in q["reponses"]]
        except (TypeError, KeyError):
            raise ValueError(f"Question {i} : champs manquants "
                             "(enonce, reponses[].texte attendus).") from None
        if not enonce or len(reponses) < 2:
            raise ValueError(f"Question {i} : énoncé vide ou moins de "
                             "deux réponses.")
        if sum(1 for _, c in reponses if c) != 1:
            raise ValueError(f"Question {i} : il faut exactement une "
                             "bonne réponse.")
        existe = con.execute(
            "SELECT 1 FROM questions WHERE actif=1 AND chapitre=? "
            "AND niveau=? AND enonce=? LIMIT 1",
            (chapitre, niveau, enonce)).fetchone()
        if existe:
            ignorees += 1
            continue
        if niveau:
            ajouter_niveau(con, niveau)
        cur = con.execute(
            "INSERT INTO questions(chapitre, niveau, enonce) VALUES(?,?,?)",
            (chapitre, niveau, enonce))
        for j, (texte, correcte) in enumerate(reponses):
            con.execute(
                "INSERT INTO reponses(question_id, texte, correcte, ordre) "
                "VALUES(?,?,?,?)", (cur.lastrowid, texte, int(correcte), j))
        ajoutees += 1
    con.commit()
    return ajoutees, ignorees


# ----------------------------------------------------------------- classes

def liste_classes(con):
    return con.execute("SELECT * FROM classes ORDER BY nom").fetchall()


def eleves_de(con, classe_id):
    return con.execute(
        "SELECT * FROM eleves WHERE classe_id=? ORDER BY nom, prenom",
        (classe_id,)).fetchall()


# ----------------------------------------------------------------- sujets

def questions_du_sujet(con, sujet_id):
    return con.execute(
        "SELECT q.*, sq.points, sq.ordre AS sq_ordre FROM sujet_questions sq "
        "JOIN questions q ON q.id = sq.question_id "
        "WHERE sq.sujet_id=? ORDER BY sq.ordre", (sujet_id,)).fetchall()


def copies_du_sujet(con, sujet_id):
    return con.execute(
        "SELECT c.*, e.nom, e.prenom FROM copies c "
        "JOIN eleves e ON e.id = c.eleve_id "
        "WHERE c.sujet_id=? ORDER BY c.numero", (sujet_id,)).fetchall()


def purger_generation(con, sujet_id):
    """Efface copies, géométrie et mesures avant une régénération."""
    con.execute("DELETE FROM copies WHERE sujet_id=?", (sujet_id,))
    con.commit()


# ---------------------------------------------------------------- settings

def get_setting(con, cle, defaut=None):
    r = con.execute("SELECT valeur FROM settings WHERE cle=?",
                    (cle,)).fetchone()
    return r["valeur"] if r else defaut


def set_setting(con, cle, valeur):
    con.execute(
        "INSERT INTO settings(cle, valeur) VALUES(?,?) "
        "ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur",
        (cle, str(valeur)))
    con.commit()
