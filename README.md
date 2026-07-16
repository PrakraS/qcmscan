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
   question. L'aperçu compilé se met à jour tout seul pendant la frappe.
   Chaque question porte un **niveau** (Seconde, 1SPE… liste gérable via
   « ⚙ ») et un **chapitre** ; le badge « ⬩n » signale une question déjà
   utilisée (détail au survol). Les questions supprimées vont dans une
   corbeille (menu « ⋯ »), restaurables ou supprimables définitivement.
2. **Classes** — saisie directe, import CSV (`Nom;Prénom`) ou collage
   depuis un tableur. Chaque classe porte un niveau, utilisé par les
   indicateurs « déjà donnée » lors de la composition des sujets.
3. **Sujets** — choisir la classe, composer la liste de questions
   (glisser-déposer depuis la banque, réordonnancement à la souris ;
   « ⚠ » = déjà donnée à cette classe, « • » = déjà donnée à ce niveau —
   information seulement, jamais bloquant), fixer le barème (points
   identiques par défaut, coefficients par question, points négatifs
   optionnels).
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

## Écrire des questions vite (IA, collègue…)

Le bouton « Coller… » de la banque importe des questions au format texte,
pratique pour récupérer ce qu'une IA rédige. Un bloc par question, une
ligne vide entre les blocs, `[Niveau | Chapitre]` (ou `[Chapitre]` seul)
facultatif en tête de bloc, `*` devant la bonne réponse, `-` devant les
autres, LaTeX autorisé :

```
[1SPE | Dérivation]
Soit $f(x)=x^2+3x$. Que vaut $f'(x)$ ?
* $2x+3$
- $x^2$
- $2x$
- $3$
```

Consigne à donner à l'IA : « Rédige N questions de QCM sur <thème> à ce
format exact, une seule bonne réponse marquée `*`, maths en LaTeX `$…$`. »

Les boutons « Exporter… » / « Importer… » échangent la banque complète en
JSON (partage entre collègues, sauvegarde).

## Exports

- CSV des notes (`Nom;Prénom;Note;Barème;Note/20`, décimales à virgule) ;
- CSV Pronote (note sur 20) ;
- un PDF de toutes les copies annotées (bonne réponse encadrée en vert,
  coche fautive en rouge, note tamponnée) ;
- statistiques de réussite par question (CSV).

## Notation

Une question rapporte ses points si exactement une case est cochée et que
c'est la bonne. Blanc, mauvaise réponse ou réponses multiples : zéro.

Option « Points négatifs » (onglet Sujets) : une mauvaise réponse ou des
réponses multiples retirent le malus choisi (un blanc reste à zéro) ; la
note d'une copie ne descend jamais sous 0. La règle est rappelée dans la
consigne imprimée en tête de chaque copie.

Changement de réponse : l'élève **entoure la case fautive et noircit la
bonne** (consigne imprimée). L'analyse mesure aussi l'encre *autour* de
chaque case : quand plusieurs cases d'une question sont noircies, si une
seule n'est pas entourée, c'est elle qui est retenue. Dans tous les
autres cas (deux cases nettes, tout entouré…), la question reste
« réponses multiples ».

## Installation (utilisateurs)

1. Télécharger `QCMScan-Setup.exe` depuis la page
   [Releases](https://github.com/PrakraS/qcmscan/releases) et
   l'exécuter (aucun droit administrateur requis). Si Windows affiche
   « Windows a protégé votre ordinateur », cliquer *Informations
   complémentaires* puis *Exécuter quand même*.
2. Installer [MiKTeX](https://miktex.org/download) (gratuit) : QCMScan
   fabrique les copies avec LaTeX. L'application le rappelle au premier
   lancement si besoin.

Les mises à jour sont signalées en bas de la fenêtre : un clic
télécharge le nouvel installateur, qui remplace l'application sans
toucher aux données.

## Publier une version (mainteneur)

1. Monter `__version__` dans `qcmscan/version.py`, committer ;
2. `git tag v1.2.0 && git push && git push --tags` ;
3. Le workflow GitHub Actions construit l'exécutable (PyInstaller), le
   teste, fabrique l'installateur (Inno Setup) et publie la Release.
   Les utilisateurs sont notifiés à leur prochain lancement.

## Données

- Chaque sujet a son dossier parlant dans **`Documents\QCMScan\sujets\`**
  (stable à travers les mises à jour) : `0003 - Suites - 1G3\` contient
  `main.pdf`, `corrige.pdf` et un sous-dossier `exports\` où partent
  automatiquement les exports datés (notes, Pronote, copies annotées,
  statistiques). Bouton « Ouvrir le dossier » dans l'onglet Sujets.
- La liste des sujets affiche le cycle de vie : brouillon → généré le …
  → scanné le … → corrigé (avec la moyenne). Les notes calculées sont
  archivées en base : l'onglet Correction les réaffiche à l'ouverture.
- La base SQLite et les pages scannées redressées restent dans
  `%APPDATA%\QCMScan\`.

Sauvegarder ces deux dossiers conserve tout.

## Limites connues

- Une seule bonne réponse par question (pas de cases multiples).
- Les copies déjà imprimées ne doivent pas être régénérées : la
  régénération remélange les questions et invalide la géométrie.
- La détection exige les quatre marqueurs de coin et le QR : éviter de
  rogner les bords au scan.
