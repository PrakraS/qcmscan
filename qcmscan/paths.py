"""Emplacements des données de l'application."""

import os
from pathlib import Path

from .config import APP_NAME, DB_FILENAME


def data_dir() -> Path:
    """Dossier de données utilisateur (%APPDATA%\\QCMScan sous Windows)."""
    base = os.environ.get("APPDATA")
    root = Path(base) if base else Path.home() / ".local" / "share"
    d = root / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def db_path() -> Path:
    return data_dir() / DB_FILENAME


def app_dir() -> Path:
    """Dossier de l'application (celui qui contient main.py)."""
    return Path(__file__).resolve().parents[1]


def sujets_root() -> Path:
    """Les PDF générés vont à côté de l'application, faciles à retrouver."""
    return app_dir() / "sujets"


def _slug(texte: str) -> str:
    """Nettoie un texte pour un nom de dossier Windows."""
    ok = "".join(ch if ch.isalnum() or ch in " -_'" else "_"
                 for ch in texte).strip(" _")
    return ok or "sans nom"


def subject_dir(con, sujet_id: int) -> Path:
    """Dossier du sujet, nommé « 0003 - Titre - Classe ». Les anciens
    dossiers (autre titre, ou format sujet_0003) sont renommés."""
    s = con.execute(
        "SELECT s.titre, c.nom FROM sujets s "
        "JOIN classes c ON c.id = s.classe_id WHERE s.id=?",
        (sujet_id,)).fetchone()
    racine = sujets_root()
    racine.mkdir(parents=True, exist_ok=True)
    nom = (f"{sujet_id:04d} - {_slug(s['titre'])} - {_slug(s['nom'])}"
           if s else f"sujet_{sujet_id:04d}")
    cible = racine / nom
    if not cible.exists():
        anciens = [racine / f"sujet_{sujet_id:04d}"]
        anciens += [d for d in racine.glob(f"{sujet_id:04d} - *")
                    if d.is_dir()]
        for ancien in anciens:
            if ancien.exists() and ancien != cible:
                try:
                    ancien.rename(cible)
                except OSError:      # fichier ouvert ailleurs : on garde
                    return ancien
                break
    cible.mkdir(parents=True, exist_ok=True)
    return cible


def scans_dir(sujet_id: int) -> Path:
    d = data_dir() / "scans" / f"sujet_{sujet_id:04d}"
    d.mkdir(parents=True, exist_ok=True)
    return d
