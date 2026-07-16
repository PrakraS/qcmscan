"""Version de l'application et dépôt de distribution.

Avant de publier une version : monter __version__ ici, committer, puis
poser le tag correspondant (git tag v1.0.0 && git push --tags). Le
robot GitHub Actions vérifie la cohérence tag/version et publie.
"""

__version__ = "1.0.1"

# Dépôt GitHub « proprietaire/nom », utilisé par le vérificateur de
# mise à jour et affiché dans l'aide. À ajuster si le dépôt change.
DEPOT = "PrakraS/qcmscan"
