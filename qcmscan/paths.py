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


def subject_dir(sujet_id: int) -> Path:
    d = sujets_root() / f"sujet_{sujet_id:04d}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def scans_dir(sujet_id: int) -> Path:
    d = data_dir() / "scans" / f"sujet_{sujet_id:04d}"
    d.mkdir(parents=True, exist_ok=True)
    return d
