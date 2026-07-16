# QCMScan — guide pour les sessions Claude

Application Windows (PySide6) de QCM papier corrigés par scan, pour
enseignants. Tout en français : interface, commentaires, commits.

## Architecture

- `qcmscan/db.py` — persistance SQLite (schéma + `_migrer()` pour les
  bases existantes : toute nouvelle colonne passe par une migration).
- `qcmscan/latexgen.py` — génération LaTeX des copies (pdflatex, QR par
  copie/page, positions des cases lues dans le `.aux`).
- `qcmscan/omr.py` — analyse des scans : QR (identité + génération),
  marqueurs de coin, homographie, taux d'encre intérieur (`ratio`) et
  autour (`ratio_ext`, cases entourées = annulées).
- `qcmscan/grading.py` — notation (une bonne réponse ; malus optionnel ;
  départage des multiples par `ratio_ext` ; décision manuelle prime).
- `qcmscan/ui/` — pages Qt ; `theme.py` (deux palettes + QSS généré),
  `widgets.py` (délégué deux lignes `ListeDeuxLignes`, `Worker` threads).
- `qcmscan/version.py` — version unique + dépôt ; `maj.py` — mise à
  jour en un clic (release GitHub → installation silencieuse).

## Commandes

- Lancer : `python main.py` (ou `QCMScan.pyw` sans console).
- Tests : `python tests/test_pipeline.py` (synthétique, rapide) et
  `python tests/test_generation.py` (boucle réelle, exige pdflatex).
  `tests/test_latexgen.py` demande pytest.
- Publier : monter `__version__` dans `qcmscan/version.py`, committer,
  `git tag vX.Y.Z && git push && git push --tags` — le workflow
  `release.yml` construit, teste (`--autotest`) et publie.

## Conventions et pièges

- **Jamais de données dans le dépôt** : base en `%APPDATA%\QCMScan`,
  PDF générés dans `Documents\QCMScan` (gitignorés ; attention, sur le
  poste de dev `Documents\qcmscan` == `Documents\QCMScan`, casse
  ignorée par Windows).
- Les copies imprimées référencent les ids de `reponses` : ne jamais
  supprimer/recréer des réponses d'une question générée (modification
  en place dans `sauver_question`).
- Régénérer un sujet incrémente `sujets.generation` (portée par le QR) ;
  les scans d'une génération périmée sont rejetés à l'analyse.
- L'auto-enregistrement (sujets, questions) a des garde-fous : sujet
  généré = composition verrouillée sans clic explicite ; sujet supprimé
  = ne rien re-sauver. Y penser à chaque nouveau flux.
- UI : boutons secondaires discrets, un seul « primaire » par zone ;
  pas d'icônes ; couleurs uniquement via `theme.palette` (deux thèmes).
- pdflatex : toujours `creationflags=_SANS_CONSOLE` (sinon fenêtres de
  console en cascade sous .pyw) ; paquets des questions dans
  `PAQUETS_QUESTIONS` (chargés pour les copies ET l'aperçu).
- Vérifier les changements sur une **copie** de la base réelle
  (`%APPDATA%\QCMScan\qcmscan.db`), jamais dessus directement ; pour
  l'OMR, monkeypatcher `omr.scans_dir` et `paths.sujets_root`.
