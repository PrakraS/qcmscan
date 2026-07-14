"""QCMScan — point d'entrée."""

import sys

from PySide6.QtWidgets import QApplication

from qcmscan import db
from qcmscan.paths import db_path
from qcmscan.ui.mainwindow import MainWindow
from qcmscan.ui.theme import QSS


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("QCMScan")
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)
    con = db.connect(db_path())
    fenetre = MainWindow(con)
    fenetre.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
