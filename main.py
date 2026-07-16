"""QCMScan — point d'entrée."""

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from qcmscan import db
from qcmscan.paths import db_path
from qcmscan.ui import theme
from qcmscan.ui.mainwindow import MainWindow


def _verifier_pdflatex(con, fenetre):
    """Accueille gentiment les nouveaux venus sans distribution LaTeX."""
    from qcmscan.latexgen import LatexError, trouver_pdflatex
    try:
        trouver_pdflatex(con)
    except LatexError:
        boite = QMessageBox(fenetre)
        boite.setWindowTitle("Installer MiKTeX")
        boite.setTextFormat(Qt.RichText)
        boite.setText(
            "QCMScan fabrique les copies avec <b>LaTeX</b>, qui n'est "
            "pas encore installé sur cet ordinateur.<br><br>"
            "Installez gratuitement <b>MiKTeX</b> (quelques minutes, "
            "assistant classique) puis relancez QCMScan :<br>"
            "<a href='https://miktex.org/download'>"
            "miktex.org/download</a><br><br>"
            "Vous pouvez déjà préparer vos questions et vos classes "
            "en attendant.")
        boite.exec()


def main():
    autotest = "--autotest" in sys.argv
    app = QApplication(sys.argv)
    app.setApplicationName("QCMScan")
    app.setStyle("Fusion")
    con = db.connect(db_path())
    sombre = db.get_setting(con, "theme", "clair") == "sombre"
    app.setStyleSheet(theme.qss(sombre))
    fenetre = MainWindow(con)
    if autotest:
        # démarrage complet sans affichage : vérifie l'empaquetage
        from qcmscan.version import __version__
        fenetre.setAttribute(Qt.WA_DontShowOnScreen, True)
        fenetre.show()
        app.processEvents()
        import tempfile
        from pathlib import Path
        Path(tempfile.gettempdir(),
             "qcmscan_autotest.txt").write_text(f"OK {__version__}")
        return
    fenetre.show()
    _verifier_pdflatex(con, fenetre)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
