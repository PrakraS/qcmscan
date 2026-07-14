"""Constantes partagées entre la génération LaTeX et l'analyse des scans.

Toutes les coordonnées "référence" sont en millimètres, origine en HAUT à
gauche de la page (convention image, y vers le bas). Les positions issues de
pdflatex (\\pdfsavepos) ont l'origine en BAS à gauche : la conversion est
faite au moment du parsing du .aux.
"""

# ---------------------------------------------------------------- page A4
PAGE_W_MM = 210.0
PAGE_H_MM = 297.0

# ------------------------------------------------- marqueurs d'alignement
# Carrés pleins de MARK_MM de côté. Positions du coin inférieur gauche en
# coordonnées PDF (origine bas-gauche), telles qu'écrites dans le .tex.
MARK_MM = 6.0
_MARKS_PDF_LL = [(10.0, 281.0), (194.0, 281.0), (10.0, 10.0), (194.0, 10.0)]

# Centres des marqueurs en coordonnées image (origine haut-gauche), dans
# l'ordre : haut-gauche, haut-droit, bas-gauche, bas-droit.
MARK_CENTERS_TOP = [
    (13.0, 13.0),    # haut-gauche
    (197.0, 13.0),   # haut-droit
    (13.0, 284.0),   # bas-gauche
    (197.0, 284.0),  # bas-droit
]

# --------------------------------------------------------------- QR code
QR_SIZE_MM = 16.0
# Coin inférieur gauche du QR en coordonnées PDF (proche du coin haut-droit,
# sans chevaucher le marqueur).
QR_POS_PDF = (176.0, 273.0)
# Centre du QR en coordonnées image (origine haut-gauche).
QR_CENTER_TOP = (QR_POS_PDF[0] + QR_SIZE_MM / 2,
                 PAGE_H_MM - QR_POS_PDF[1] - QR_SIZE_MM / 2)
QR_PREFIX = "QS"          # contenu : "QS|<sujet>|<copie>|<page>"
QR_MAX_PAGES = 12         # QR pré-générés par copie (marge large)

# ------------------------------------------------------- cases à cocher
CASE_MM = 4.5             # côté des cases imprimées

# ------------------------------------------------------------- analyse
RECT_PX_PER_MM = 6        # résolution de l'image redressée (px / mm)
SCAN_DPI = 200            # rasterisation des PDF scannés
CASE_SHRINK = 0.24        # rétrécissement du ROI (élimine le trait imprimé)

# Seuils de décision sur le taux de noircissement intérieur.
SEUIL_VIDE = 0.08         # en dessous : case vide
SEUIL_COCHEE = 0.30       # au-dessus : case cochée
SEUIL_AUTO = 0.17         # coupure unique en mode automatique

# Détection des cases annulées (« entourez la case fautive ») : anneau
# mesuré autour de la case. Sert uniquement à départager les réponses
# multiples : parmi les cases cochées, si une seule n'est pas entourée,
# c'est elle la réponse retenue.
ANNEAU_RETRAIT_MM = 0.5   # écart entre le bord de la case et l'anneau
ANNEAU_LARGEUR_MM = 1.5   # largeur de l'anneau mesuré
SEUIL_ANNULEE = 0.20      # noircissement d'anneau à partir duquel la
                          # case est considérée comme entourée (mesuré :
                          # cercle réel ≈ 0.4, débordement de feutre
                          # d'une case noircie ≤ 0.12)

# --------------------------------------------------------------- divers
APP_NAME = "QCMScan"
DB_FILENAME = "qcmscan.db"
