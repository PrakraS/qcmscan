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


def subject_dir(sujet_id: int) -> Path:
    d = data_dir() / "sujets" / f"sujet_{sujet_id:04d}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def scans_dir(sujet_id: int) -> Path:
    d = data_dir() / "scans" / f"sujet_{sujet_id:04d}"
    d.mkdir(parents=True, exist_ok=True)
    return d
