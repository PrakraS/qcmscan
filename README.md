# QCMScan

Application locale de QCM papier à correction automatique par scan, façon
AMC mais pensée pour Windows : banque de questions LaTeX, copies nominatives
mélangées, lecture des scans par QR code et marqueurs de coin, notes
exportables (CSV, Pronote, copies annotées).

## Installation (Windows)

1. **Python 3.11+** : https://www.python.org/downloads/ (cocher « Add
   python.exe to PATH » à l'installation).
2. **MiKTeX** : https://miktex.org/download — `pdflatex` doit être dans le
   PATH (c'est le cas par défaut). Les paquets LaTeX manquants s'installent
   automatiquement à la première compilation (accepter l'invite MiKTeX ou
   activer l'installation automatique dans la console MiKTeX).
3. Dans le dossier de l'application :

   ```
   pip install -r requirements.txt
   python main.py
   ```

Si `pdflatex` n'est pas trouvé alors que MiKTeX est installé, redémarrer la
session Windows (mise à jour du PATH), ou renseigner son chemin complet :
l'application lit la clé `pdflatex` de la table `settings` de la base
(`%APPDATA%\QCMScan\qcmscan.db`).

## Utilisation

1. **Banque de questions** — énoncés et réponses en LaTeX (mode maths avec
   `$…$`, TikZ accepté dans les énoncés). Une seule bonne réponse par
   question. Le bouton « Aperçu PDF » compile la question seule.
2. **Classes** — saisie directe, import CSV (`Nom;Prénom`) ou collage
   depuis un tableur.
3. **Sujets** — choisir la classe, composer la liste de questions, fixer le
   barème (points identiques par défaut, ou coefficients par question).
   « Générer les copies » produit :
   - `main.pdf` : une copie nominative par élève, questions et réponses
     mélangées, cases à cocher dans le corps du sujet, QR code et marqueurs
     sur chaque page ;
   - `corrige.pdf` : le corrigé maître (lettres correctes de chaque copie).
4. **Impression et passation** — imprimer `main.pdf` (recto simple ou
   recto-verso, indifférent). Consigne élève : **noircir complètement** la
   case (une croix légère part en révision manuelle).
5. **Correction** — scanner les copies en PDF (200 dpi conseillé, niveaux
   de gris, ordre et sens des pages indifférents, plusieurs fichiers
   acceptés), lancer l'analyse, réviser les éventuelles cases douteuses,
   calculer, exporter.

## Exports

- CSV des notes (`Nom;Prénom;Note;Barème;Note/20`, décimales à virgule) ;
- CSV Pronote (note sur 20) ;
- un PDF de toutes les copies annotées (bonne réponse encadrée en vert,
  coche fautive en rouge, note tamponnée) ;
- statistiques de réussite par question (CSV).

## Notation

Une question rapporte ses points si exactement une case est cochée et que
c'est la bonne. Blanc, mauvaise réponse ou réponses multiples : zéro. Pas
de points négatifs.

## Données

Tout est stocké dans `%APPDATA%\QCMScan\` : base SQLite, sources LaTeX et
PDF générés (`sujets\`), pages scannées redressées (`scans\`). Sauvegarder
ce dossier suffit à tout conserver.

## Limites connues

- Une seule bonne réponse par question (pas de cases multiples).
- Les copies déjà imprimées ne doivent pas être régénérées : la
  régénération remélange les questions et invalide la géométrie.
- La détection exige les quatre marqueurs de coin et le QR : éviter de
  rogner les bords au scan.
