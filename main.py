"""QCMScan — point d'entrée."""

import sys

from PySide6.QtWidgets import QApplication

from qcmscan import db
from qcmscan.paths import db_path
from qcmscan.ui import theme
from qcmscan.ui.mainwindow import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("QCMScan")
    app.setStyle("Fusion")
    con = db.connect(db_path())
    sombre = db.get_setting(con, "theme", "clair") == "sombre"
    app.setStyleSheet(theme.qss(sombre))
    fenetre = MainWindow(con)
    fenetre.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
