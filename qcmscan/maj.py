"""Vérification et installation des mises à jour via les Releases GitHub.

Aucune donnée n'est envoyée : simple lecture publique de la dernière
release. Silencieux en cas d'absence de réseau ou d'erreur.
"""

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

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


def telecharger(url, destination, progress=None):
    """Télécharge `url` vers `destination` avec progression affichable."""
    req = urllib.request.Request(
        url, headers={"User-Agent": f"QCMScan/{__version__}"})
    with urllib.request.urlopen(req, timeout=30) as r, \
            open(destination, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        lu = 0
        while True:
            bloc = r.read(1 << 16)
            if not bloc:
                break
            f.write(bloc)
            lu += len(bloc)
            if progress and total:
                progress("Téléchargement de la mise à jour… "
                         f"{lu * 100 // total} %")
    return destination


def installer_et_relancer(setup: Path):
    """Lance l'installation silencieuse puis la relance de l'application.

    À appeler depuis l'application empaquetée, juste avant de quitter :
    un processus détaché attend la fin de l'installation (qui remplace
    nos fichiers une fois l'application fermée) puis redémarre l'exe.
    """
    exe = Path(sys.executable)
    commande = (
        f"Start-Process -FilePath '{setup}' -ArgumentList "
        "'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',"
        "'/FORCECLOSEAPPLICATIONS' -Wait; "
        f"Start-Process -FilePath '{exe}'")
    subprocess.Popen(
        ["powershell", "-NoProfile", "-WindowStyle", "Hidden",
         "-Command", commande],
        creationflags=(subprocess.CREATE_NO_WINDOW
                       | subprocess.DETACHED_PROCESS))
