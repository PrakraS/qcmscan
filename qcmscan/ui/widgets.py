"""Éléments d'interface partagés."""

from PySide6.QtCore import QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QVBoxLayout, QWidget)


class Worker(QThread):
    """Exécute une fonction en arrière-plan avec remontée de progression."""
    progress = Signal(str)
    done = Signal(object)
    error = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn, self._args, self._kwargs = fn, args, kwargs

    def run(self):
        try:
            res = self._fn(*self._args, progress=self.progress.emit,
                           **self._kwargs)
            self.done.emit(res)
        except Exception as e:            # noqa: BLE001 — remonté à l'UI
            self.error.emit(str(e))


def entete(titre, sous_titre=""):
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 8)
    lay.setSpacing(2)
    t = QLabel(titre)
    t.setObjectName("titrePage")
    lay.addWidget(t)
    if sous_titre:
        s = QLabel(sous_titre)
        s.setObjectName("sousTitre")
        lay.addWidget(s)
    return w


def bouton(texte, type_=None, on_click=None):
    b = QPushButton(texte)
    if type_:
        b.setProperty("type", type_)
    if on_click:
        b.clicked.connect(on_click)
    return b


def ligne_boutons(*boutons):
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    for b in boutons:
        lay.addWidget(b)
    lay.addStretch()
    return w


def info(parent, titre, texte):
    QMessageBox.information(parent, titre, texte)


def erreur(parent, titre, texte):
    QMessageBox.critical(parent, titre, texte)


def confirmer(parent, titre, texte) -> bool:
    return QMessageBox.question(
        parent, titre, texte,
        QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes


def ouvrir_fichier(path):
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
