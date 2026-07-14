"""Éléments d'interface partagés."""

from PySide6.QtCore import QSize, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QStyle, QStyledItemDelegate,
                               QStyleOptionViewItem, QVBoxLayout, QWidget)

from . import theme

# Rôles de données pour les listes à deux lignes.
ROLE_META = Qt.UserRole + 1     # ligne secondaire, grisée
ROLE_BADGE = Qt.UserRole + 2    # marque courte alignée à droite


class ListeDeuxLignes(QStyledItemDelegate):
    """Élément de liste à deux lignes : texte principal, puis une ligne
    de métadonnées en petit et gris ; badge facultatif à droite."""

    MARGE_X, MARGE_Y = 10, 5

    def sizeHint(self, option, index):
        return QSize(220, 44)

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        style = opt.widget.style() if opt.widget else None
        if style:
            style.drawControl(QStyle.CE_ItemViewItem, opt, painter,
                              opt.widget)
        r = opt.rect.adjusted(self.MARGE_X, self.MARGE_Y,
                              -self.MARGE_X, -self.MARGE_Y)
        painter.save()

        badge = index.data(ROLE_BADGE) or ""
        largeur_badge = 0
        if badge:
            couleur = (theme.palette["orange"] if badge.startswith("⚠")
                       else theme.palette["texte2"])
            painter.setPen(QColor(couleur))
            largeur_badge = painter.fontMetrics().horizontalAdvance(badge)
            painter.drawText(r, Qt.AlignRight | Qt.AlignTop, badge)
            largeur_badge += 10

        principal = index.data(Qt.DisplayRole) or ""
        fm = painter.fontMetrics()
        painter.setPen(QColor(theme.palette["texte"]))
        painter.drawText(
            r, Qt.AlignLeft | Qt.AlignTop,
            fm.elidedText(principal, Qt.ElideRight,
                          r.width() - largeur_badge))

        meta = index.data(ROLE_META) or ""
        if meta:
            f = painter.font()
            f.setPointSizeF(max(f.pointSizeF() - 1.5, 6.5))
            painter.setFont(f)
            painter.setPen(QColor(theme.palette["texte2"]))
            painter.drawText(
                r, Qt.AlignLeft | Qt.AlignBottom,
                painter.fontMetrics().elidedText(meta, Qt.ElideRight,
                                                 r.width()))
        painter.restore()


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
