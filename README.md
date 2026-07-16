# QCMScan

Application Windows de **QCM papier à correction automatique par scan**,
pensée pour les enseignants : banque de questions LaTeX, copies
nominatives mélangées, lecture des scans par QR code et marqueurs de
coin, notes exportables (CSV, Pronote, copies annotées). Tout fonctionne
**en local** — aucune donnée ne quitte votre ordinateur.

## Installation

1. Télécharger **`QCMScan-Setup.exe`** depuis la page
   [Releases](https://github.com/PrakraS/qcmscan/releases) et
   l'exécuter (aucun droit administrateur requis). Si Windows affiche
   « Windows a protégé votre ordinateur », cliquer *Informations
   complémentaires* puis *Exécuter quand même*.
2. Installer [MiKTeX](https://miktex.org/download) (gratuit) : QCMScan
   fabrique les copies avec LaTeX. L'application le rappelle au premier
   lancement si besoin, et MiKTeX installe ensuite tout seul les paquets
   manquants.

Les mises à jour sont signalées en bas de la fenêtre : un clic télécharge
le nouvel installateur, qui remplace l'application **sans toucher aux
données**.

## Le flux de travail

1. **Banque de questions** — énoncés et réponses en LaTeX (maths entre
   `$…$`, TikZ et tableaux de signes `tkz-tab` acceptés), une seule
   bonne réponse par question, aperçu compilé qui se met à jour pendant
   la frappe. Chaque question porte un **niveau** (Seconde, 1SPE… liste
   gérable via ⚙) et un **chapitre** ; un badge signale les questions
   déjà utilisées (détail au survol). Corbeille avec restauration.
2. **Classes** — saisie directe, import CSV (`Nom;Prénom`) ou collage
   depuis un tableur ; chaque classe porte un niveau.
3. **Sujets** — composer par glisser-déposer depuis la banque
   (« ⚠ déjà donnée à cette classe », « • à ce niveau » — informatif,
   jamais bloquant), fixer le barème (uniforme, coefficients par
   question, points négatifs optionnels), vérifier la mise en page avec
   la **copie témoin**, puis **générer** : une copie nominative par
   élève, questions et réponses mélangées, plus le corrigé maître.
   Un sujet se **duplique** en un clic pour une autre classe.
4. **Impression et passation** — consigne élève (imprimée en tête de
   copie) : *noircir complètement la case ; en cas d'erreur, entourer la
   case fautive et noircir la bonne*.
5. **Correction** — scanner en PDF (200 dpi, ordre et sens des pages
   indifférents), analyser, **réviser les cases signalées** (marquages
   légers, cases entourées — la question s'affiche en entier, case en
   cause encadrée), calculer, exporter. Synthèse : moyenne, médiane,
   histogramme, réussite par question.

L'enregistrement est automatique partout (sujets, questions) ; les notes
calculées sont archivées et réaffichées à l'ouverture, et la liste des
sujets montre le cycle de vie : *brouillon → généré le … → scanné →
corrigé (moyenne)*.

## Écrire des questions vite (IA, collègue…)

Le bouton « Coller… » de la banque importe des questions au format
texte : un bloc par question, une ligne vide entre les blocs,
`[Niveau | Chapitre]` facultatif en tête, `*` devant la bonne réponse,
`-` devant les autres, LaTeX autorisé :

```
[1SPE | Dérivation]
Soit $f(x)=x^2+3x$. Que vaut $f'(x)$ ?
* $2x+3$
- $x^2$
- $2x$
- $3$
```

Le bouton « Consigne pour l'IA » copie un prompt prêt à l'emploi à
donner à n'importe quel assistant ; il ne reste qu'à coller sa réponse.
Les boutons « Exporter… / Importer… » (menu ⋯) échangent la banque en
JSON pour le partage entre collègues.

## Notation

Une question rapporte ses points si exactement une case est cochée et
que c'est la bonne. Blanc, mauvaise réponse ou réponses multiples : zéro.

- **Points négatifs** (option par sujet) : une mauvaise réponse ou des
  réponses multiples retirent le malus ; un blanc reste à zéro ; la note
  d'une copie ne descend jamais sous 0.
- **Changement de réponse** : l'analyse mesure aussi l'encre *autour*
  des cases ; parmi plusieurs cases noircies, si une seule n'est pas
  entourée, c'est elle qui est retenue. Ces cases passent aussi en
  révision manuelle, où votre décision prime.

## Exports

Dans le dossier du sujet, datés : CSV des notes (décimales à virgule),
CSV Pronote (note sur 20), PDF des copies annotées (bonne réponse
encadrée, coche fautive en rouge, note tamponnée), statistiques par
question.

## Vos données restent chez vous

- **Banque de questions, classes, élèves, mesures, notes** : base SQLite
  locale `%APPDATA%\QCMScan\qcmscan.db` (les pages scannées redressées
  sont à côté).
- **Copies générées et exports** : `Documents\QCMScan\sujets\`, un
  dossier parlant par sujet (`0003 - Suites - 1G3\`), stable à travers
  les mises à jour. Bouton « Ouvrir le dossier » dans l'onglet Sujets.
- **Réseau** : l'application ne fait qu'une seule requête, la lecture
  publique de la dernière version disponible. Rien n'est envoyé — ni
  noms, ni notes, ni questions. Ce dépôt ne contient que le code du
  logiciel, jamais son contenu.

Sauvegarder `%APPDATA%\QCMScan` et `Documents\QCMScan` conserve tout.

## Limites connues

- Une seule bonne réponse par question (pas de cases multiples).
- Régénérer un sujet invalide les copies déjà imprimées ; l'analyse
  **rejette** alors leurs scans (numéro de génération dans le QR) au
  lieu de corriger de travers — mais il faut réimprimer.
- La détection exige les quatre marqueurs de coin et le QR : éviter de
  rogner les bords au scan.

## Lancer depuis les sources (développeurs)

```
pip install -r requirements.txt
python main.py          # ou double-clic sur QCMScan.pyw
```

Prérequis : Python 3.11+ et MiKTeX (`pdflatex` dans le PATH — sinon,
renseigner son chemin dans la clé `pdflatex` de la table `settings`).
Tests : `python tests/test_pipeline.py` (synthétique) et
`python tests/test_generation.py` (boucle réelle avec pdflatex).

## Publier une version (mainteneur)

1. Monter `__version__` dans `qcmscan/version.py`, committer ;
2. `git tag v1.2.0 && git push && git push --tags` ;
3. Le workflow GitHub Actions construit l'exécutable (PyInstaller), le
   teste, fabrique l'installateur (Inno Setup) et publie la Release.
   Les utilisateurs sont notifiés à leur prochain lancement.
