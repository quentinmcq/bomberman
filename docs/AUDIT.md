# Audit et modernisation — 30 août 2026

Audit du projet scolaire *Bomberman* (avril–juin 2019, Python 3 + PyQt5) puis reconstruction
complète : package `bomberman/` en PyQt6, Python ≥ 3.10 (développé sur 3.14), moteur de jeu
testable sans Qt, IA réécrite, assets originaux, outillage moderne (uv, ruff, pytest, CI, Renovate).

Les références de lignes « avant » renvoient au commit `a4fa049` (dernier état d'origine).

## 1. État des lieux

### 1.1 Métriques

| Indicateur | Avant | Après |
| --- | --- | --- |
| Lignes de code applicatif | 3 206 (8 fichiers, dont `Map2.py` = 748 lignes dupliquées) | 1 765 (`bomberman/`, docstrings comprises) |
| Tests | 0 | 54 (pytest, 0,6 s ; 838 lignes) — moteur, IA, générateur d'assets, UI hors écran ; exécutés sous Python 3.10 et 3.14 |
| Appels à `findJoueur()` (balayage complet de la grille) | 678 dans `IA.py`, 11 dans `Map.py` | 0 (positions en O(1)) |
| Lignes > 200 caractères | 51 (record : 847) | 0 (limite 100, vérifiée par ruff) |
| Bloc d'animation `movementJx == 0 … = 1` copié | 44 fois | 1 ligne (`frame = (frame + 1) % 4`) |
| Tirage de power-up copié | 8 fois (`bombe.py`) | 1 table pondérée |
| `from … import *` | 23 | 0 |
| `quit()` (builtin de `site`) | 7 | 0 |
| Dépendances déclarées | aucune | `pyproject.toml` + `uv.lock` |
| Assets | 61 images + 4 WAV = 18 Mo, sous droits tiers | 19 PNG + 9 WAV = 1,8 Mo, originaux |
| Musiques manquantes | `Battle.wav`, `Boss.wav` référencées mais absentes | toutes présentes |

### 1.2 Architecture

- **Tout hérite de `QWidget`** (`var`, `sprite`, `mouvement`, `bombe`, `ia`) sans raison : widgets
  fantômes, logique de jeu impossible à tester sans `QApplication`.
- **État du jeu = matrice de nombres magiques** (`0, 1, 2, 3, 4, 6.1 … 6.6, 7, 8, 9, 34, 74, 84,
  94`), avec des *floats* comparés par `==` pour identifier des tuiles.
- **`Map1` est un attribut de classe**, randomisé au moment de l'import du module : une seule
  partie possible par processus, état partagé entre instances.
- **`paintEvent` contient la logique de jeu** (`Map.py:176-419`) : démarrage des timers IA,
  décompte des survivants (4 à 6 balayages de grille par repaint), changement de musique,
  `QLabel` de victoire et `QTimer → quit()` recréés à chaque rafraîchissement.
- **IA triplée** : `moveIA2/3/4` sont identiques au numéro de joueur près ; chaque condition
  appelle `findJoueur()` jusqu'à 20 fois sur une seule ligne.
- **`bombe.py`** : 2 fonctions × 4 directions copiées-collées (8 blocs de 40 lignes), closures
  capturant l'état, et une pile `QMediaPlayer + QMediaPlaylist` créée à chaque explosion.
- **`Main.py`** : attributs qui écrasent les méthodes homonymes (`self.playlist`, `self.level`,
  `self.stackedLayout`), `self.widget` / `self.layout` réutilisés pour tous les menus → le menu
  pause pose un layout sur un widget qui en a déjà un (avertissement Qt, menu inopérant).
- Chemins relatifs au répertoire courant (`"Images/..."`, `os.getcwd()`), `.idea/` versionné,
  noms de classes en minuscules / modules en majuscules, aucun docstring ni typage.

### 1.3 Bugs fonctionnels relevés

1. `variable.py:255` — `setSkull` teste `n == 8` au lieu de `7` : le joueur Bleu ne peut jamais
   être maudit, le Jaune est testé deux fois.
2. `mouvement.py:22-27` — `6.1` testé deux fois (FireUp puis `allowLessRange`) au lieu de `6.4` :
   en quittant sa bombe vers le haut, un FireUp est annulé et un FireDown ignoré.
3. `bombe.py:132` et `:334` — `Map1[i1 + 1]` au lieu de `Map1[i1 + k]` : la chance de power-up
   vers le bas est calculée sur la mauvaise case.
4. `bombe.py:177` et `:378` — `powerup = random()` re-tiré sans condition : des power-ups
   apparaissent sur des cases vides vers le haut.
5. `bombe.py:198` — `Map1[i1][j1] = 1` inconditionnel à l'explosion : un joueur ou un power-up
   arrivé sur la case d'une bombe déjà détruite par une autre explosion est effacé sans mort ni score.
6. `bombe.py:36` — un joueur debout sur sa bombe (`34/74/84/94`) tué ne rapporte aucun point
   (seuls `3/7/8/9` sont comptés).
7. `posePikeBombe` ne reconnaît que `6.1`/`6.2` comme power-ups et oublie les bombes vers le haut
   (copier-coller incomplet) : comportement différent selon la direction.
8. `IA.py:38`, `:153`, `:360` — l'IA teste `bombeJ1` (type de bombe du **joueur 1**) au lieu du sien.
9. `IA.py:18` et suivantes — conditions terminées par `or Map1[…][…]` (valeur brute, presque
   toujours vraie) : la garde de sécurité est inopérante.
10. `IA.py:68`, `:230`, `:435` — `findJoueur(2)[2 - 1]` indexe le tuple au lieu de décaler la colonne.
11. `IA.py:61` — branche aléatoire « droite » de l'IA 2 sans `else` : cette IA ne va jamais à
    droite au hasard, sauf maudite.
12. `IA.py:86` — `posJ2 = 1` après `moveTop` : sprite orienté à l'envers.
13. `Map.py:383` — `findJoueur(3)` au lieu de `findJoueur(2)` : la victoire du joueur Bleu n'est
    jamais annoncée.
14. `Map.py:369-419` — `quit` branché sur des `QTimer` recréés à chaque repaint : la fin de partie
    est un arrêt brutal du processus ; pas de retour au menu.
15. `Main.py:37-38` — `Battle.wav` et `Boss.wav` absents du dépôt : aucune musique en jeu.
16. `Map.py:438` — la touche **A** ressuscite le joueur 1 (cheat de développement oublié).
17. `resetSkullJx` n'est jamais appelé : malédiction permanente, contrairement à l'intention.
18. `Main.py:95` — `optionsMenu()` démarre la musique par effet de bord lors de la construction ;
    curseur à 50 mais volume réel à 100.
19. `Main.py:18-21` — `QDesktopWidget` déprécié (supprimé dans Qt 6) ; fenêtre sans bordure figée
    à la taille de l'écran ; plateau 1050 × 950 px à position fixe → dernière ligne hors écran sur
    un 1440 × 900.
20. `Map.py:31-34` — floats passés à des API entières (`setMinimumWidth(self.width() / 2)`) :
    tolérance dépendante de la version de Python/sip (Python ≥ 3.10 a retiré la conversion
    implicite via `__int__` dans `PyLong_AsLong`).
21. `sprite.py` — `.copy(0, 138, 52, 65)` sur toutes les images : rectangle hors image, Qt
    l'intersecte et recopie l'image entière → 60 appels inutiles (cargo-cult).
22. Tuile `5` « Flamme » déclarée mais jamais dessinée : les explosions sont invisibles.

### 1.4 Performance

- `findJoueur` balaie 399 cases ; 678 appels dans les conditions de l'IA ⇒ plusieurs dizaines de
  milliers de lectures par décision, pour 3 IA toutes les 500 ms. Pas de ralentissement perçu sur
  une machine moderne, mais O(n) là où O(1) suffit — et une IA impossible à faire évoluer.
- `paintEvent` : 399 `QBrush` texturés recréés à chaque repaint, `drawRect` avec brosse au lieu de
  `drawPixmap` (l'alignement des textures ne tenait qu'aux offsets 400/50 multiples de 50).
- Une pile multimédia complète par explosion (~100 ms de latence, jamais libérée avant la fin du widget).

## 2. Ce qui a été fait

### 2.1 Nouvelle architecture

```
bomberman/
├── model.py        règles pures : Game, Player, Bomb, Flame, PowerUp, Tile, Direction, événements
│                   (Game.blast_ray/blast_cells : unique source de vérité de la propagation du souffle)
├── ai.py           IA déterministe : survie → attaque → exploration (BFS bornés)
├── assets.py       chargement des images, cache borné par taille
├── audio.py        musique (QMediaPlayer) + effets préchargés (QSoundEffect), désactivable
├── ui/game_widget  clavier (touche maintenue), horloge 50 ms, relais des événements (sons, fin)
├── ui/renderer     dessin du plateau à l'échelle, bandeau de scores, superpositions
├── ui/menus        accueil, options, surcouche de pause (bouton « Son » partagé)
├── ui/main_window  navigation, musique par phase, plein écran
└── assets/         19 PNG + 9 WAV générés par tools/generate_assets.py
```

Le moteur (`model.py`, `ai.py`) n'importe pas Qt : il est couvert par des tests unitaires
rapides ; l'interface est testée hors écran (`QT_QPA_PLATFORM=offscreen`). Les aides communes
aux tests (`clear_bricks`, `open_arena`, `tick`) vivent dans `tests/helpers.py`.

### 2.2 Corrections et changements de comportement

| Sujet | Avant | Après |
| --- | --- | --- |
| Explosions | invisibles, instantanées | flammes visibles 0,45 s et létales ; réactions en chaîne immédiates |
| Bombe touchée par un souffle | explose 3 s plus tard depuis son ancienne case (bug 5) | explose en chaîne |
| Crâne | inversion permanente | inversion pendant 10 s, icône au-dessus du joueur |
| Fin de partie | `quit()` du processus | écran de résultat, musique victoire/égalité, retour au menu |
| Score | +1 pour tout objet touché (bombes et joueurs compris), +5 par kill | +1 par brique, +5 par kill, 0 pour un suicide |
| Déplacement | un pas par événement clavier (répétition OS) | touche maintenue = un pas toutes les 160 ms |
| Fenêtre | sans bordure, taille écran figée, plateau à position fixe | fenêtre normale redimensionnable, plateau mis à l'échelle, F11 |
| Pause | cassée | Continuer / Son / Menu principal / Quitter |
| Musique | menu seulement (fichiers manquants) | menu, combat, duel (2 survivants), victoire, égalité |
| IA | conditions copiées, aucune notion de danger, teste le mauvais joueur | carte des souffles, fuite par BFS, ne pose une bombe que si une issue est atteignable en ≤ 5 pas |
| Cheat touche A | présent | retiré ; alias W A S D ajoutés |
| Prise de contrôle d'une IA | par n'importe quelle touche du joueur | idem (conservé) |

Les probabilités de power-ups, la grille 21 × 19, les 25 % de briques retirées, la mèche de 3 s,
les plafonds (8 bombes / portée 8) et les touches d'origine sont conservés à l'identique.

### 2.3 Assets

Les images d'origine (fond Konami, sprites Eren / Donkey Kong / Bomberman / Trump, `snk.jpg`
inutilisé) et les musiques (dont `Bomberman.wav`, 74 s / 14 Mo) ont été retirées du dépôt. Elles
sont remplacées par des créations originales générées procéduralement, sans dépendance :

- pixel-art 16 × 16 défini en ASCII (personnages 4 directions × 3 poses en 4 couleurs, bombes,
  flammes, tuiles, power-ups), exporté en PNG ×4 par un encodeur maison (`zlib` + `struct`) ;
- chiptunes composés pour l'occasion (séquenceur à motifs, ondes carrées/triangles/bruit) :
  menu 8,6 s, combat 12,3 s, duel 11,2 s, victoire, égalité, et 4 effets.

`python tools/generate_assets.py` régénère tout en moins d'une seconde.

### 2.4 Outillage

- `pyproject.toml` (PEP 621, `[dependency-groups]`), `uv.lock`, `.python-version` = 3.14,
  `requires-python >= 3.10` ; commande `bomberman` installée ; `python Main.py` conservé.
- `ruff` (lint + format, `target-version = py310`), `pytest` (54 tests, vérifiés localement
  sous Python 3.14.7 et, via `uv run --python 3.10 --isolated`, sous Python 3.10).
- GitHub Actions : matrice Python 3.10 / 3.12 / 3.14, Qt en rendu hors écran.
- `renovate.json` : PyQt6 groupé, outils de dev et actions GitHub fusionnés automatiquement quand
  la CI passe, maintenance mensuelle de `uv.lock`, mises à jour de `.python-version`.
- `.gitignore` complété ; `.idea/` retiré de l'index (fichiers locaux conservés).

## 3. Reste à faire

- **Commiter** : toutes les modifications sont dans l'arbre de travail, rien n'a été commité.
- **Activer Renovate** : installer l'application GitHub sur le dépôt (<https://github.com/apps/renovate>).
- **Choisir une licence** pour le code (aucune n'est déclarée). PyQt6 est sous GPL v3 ; si c'est
  un frein, PySide6 (LGPL) offre une API quasi identique.
- Idées : niveaux/densités de briques multiples (le menu « Niveau 1/2/3 » d'origine était vide),
  manette, exécutable autonome (PyInstaller).
