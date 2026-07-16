"""Vérification des mises à jour via les Releases GitHub.

Aucune donnée n'est envoyée : simple lecture publique de la dernière
release. Silencieux en cas d'absence de réseau ou d'erreur.
"""

import json
import urllib.request

from .version import DEPOT, __version__


def _tuple_version(v: str):
    try:
        return tuple(int(x) for x in v.strip().lstrip("v").split("."))
    except ValueError:
        return ()


def verifier(progress=None):
    """Retourne (version, url_de_téléchargement) si une version plus
    récente que la nôtre est publiée, sinon None."""
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{DEPOT}/releases/latest",
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": f"QCMScan/{__version__}"})
        with urllib.request.urlopen(req, timeout=6) as r:
            data = json.load(r)
    except Exception:                     # noqa: BLE001 — hors ligne, etc.
        return None
    distante = data.get("tag_name", "")
    if _tuple_version(distante) <= _tuple_version(__version__):
        return None
    url = next((a["browser_download_url"]
                for a in data.get("assets", [])
                if a.get("name", "").endswith(".exe")),
               data.get("html_url", f"https://github.com/{DEPOT}/releases"))
    return distante.lstrip("v"), url
