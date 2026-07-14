"""Couche de persistance SQLite. Un seul fichier de base, schéma simple."""

import sqlite3
from pathlib import Path

_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY,
    chapitre TEXT NOT NULL DEFAULT '',
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
    nom TEXT NOT NULL
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


def _migrer(con):
    """Ajoute aux bases existantes les colonnes apparues depuis leur création
    (CREATE TABLE IF NOT EXISTS ne modifie pas les tables déjà en place)."""
    cols = {r[1] for r in con.execute("PRAGMA table_info(sujets)")}
    if "malus_actif" not in cols:
        con.execute("ALTER TABLE sujets ADD COLUMN malus_actif INTEGER "
                    "NOT NULL DEFAULT 0")
        con.execute("ALTER TABLE sujets ADD COLUMN malus REAL "
                    "NOT NULL DEFAULT 0.5")
        con.commit()


# --------------------------------------------------------------- questions

def liste_chapitres(con):
    rows = con.execute(
        "SELECT DISTINCT chapitre FROM questions WHERE actif=1 "
        "ORDER BY chapitre").fetchall()
    return [r["chapitre"] for r in rows if r["chapitre"]]


def liste_questions(con, chapitre=None, recherche=None):
    q = "SELECT * FROM questions WHERE actif=1"
    args = []
    if chapitre:
        q += " AND chapitre=?"
        args.append(chapitre)
    if recherche:
        q += " AND enonce LIKE ?"
        args.append(f"%{recherche}%")
    q += " ORDER BY chapitre, id"
    return con.execute(q, args).fetchall()


def reponses_de(con, question_id):
    return con.execute(
        "SELECT * FROM reponses WHERE question_id=? ORDER BY ordre, id",
        (question_id,)).fetchall()


def sauver_question(con, qid, chapitre, enonce, reponses):
    """reponses : liste de (texte, correcte). Retourne l'id.

    Les réponses existantes sont modifiées en place quand leur nombre ne
    change pas : les copies déjà générées référencent leurs ids
    (copie_reponses, cases), qu'un DELETE violerait.
    """
    if qid is None:
        cur = con.execute(
            "INSERT INTO questions(chapitre, enonce) VALUES(?,?)",
            (chapitre, enonce))
        qid = cur.lastrowid
        anciennes = []
    else:
        con.execute("UPDATE questions SET chapitre=?, enonce=? WHERE id=?",
                    (chapitre, enonce, qid))
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
    """Suppression douce si la question est utilisée dans un sujet."""
    utilisee = con.execute(
        "SELECT 1 FROM sujet_questions WHERE question_id=? LIMIT 1",
        (qid,)).fetchone()
    if utilisee:
        con.execute("UPDATE questions SET actif=0 WHERE id=?", (qid,))
    else:
        con.execute("DELETE FROM questions WHERE id=?", (qid,))
    con.commit()


def exporter_questions(con, chapitre=None, recherche=None):
    """Banque (filtrée) sous forme de liste de dicts sérialisables JSON."""
    out = []
    for q in liste_questions(con, chapitre, recherche):
        out.append({
            "chapitre": q["chapitre"],
            "enonce": q["enonce"],
            "reponses": [{"texte": r["texte"],
                          "correcte": bool(r["correcte"])}
                         for r in reponses_de(con, q["id"])],
        })
    return out


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
            "AND enonce=? LIMIT 1", (chapitre, enonce)).fetchone()
        if existe:
            ignorees += 1
            continue
        cur = con.execute(
            "INSERT INTO questions(chapitre, enonce) VALUES(?,?)",
            (chapitre, enonce))
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
