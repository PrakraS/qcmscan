"""Lanceur sans console : double-cliquer ce fichier ouvre QCMScan.

L'extension .pyw est associée à pythonw.exe (installé avec Python),
qui exécute le programme sans fenêtre de terminal.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from main import main

main()
