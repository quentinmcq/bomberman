# Bomberman

Jeu de type *Bomberman* — un joueur contre trois IA — en **Python / PyQt6**. Éliminez vos
adversaires à coups de bombes ; les briques détruites libèrent des power-ups (portée, nombre de
bombes, bombe perforante) mais aussi des malus (crâne : contrôles inversés pendant 10 s).

Projet scolaire réalisé en groupe de trois personnes d'avril à juin 2019 (Python 3 + PyQt5),
modernisé en 2026.

| Menu | Partie |
| --- | --- |
| ![Menu](docs/screenshots/menu.png) | ![Partie](docs/screenshots/game.png) |

## Installation

Le projet se gère avec [uv](https://docs.astral.sh/uv/), qui installe lui-même le bon
Python (3.14.7, d'après `.python-version`) :

```bash
uv sync            # crée .venv, installe PyQt6 + outils de dev d'après uv.lock
uv run bomberman   # lance le jeu
```

Options : `--seed 42` (terrain reproductible), `--no-audio`, `--fullscreen`, `-v`.

## Commandes

Avant la partie, choisissez votre personnage (Rouge, Bleu, Jaune ou Rose — le choix est
mémorisé) ; les trois autres sont pilotés par l'IA.

| Action | Touches |
| --- | --- |
| Se déplacer | Z Q S D (ou W A S D) — ou les flèches |
| Poser une bombe | Espace |
| Pause | Échap |
| Plein écran | F11 |

## Règles

- Grille 21 × 19 : bordure et piliers indestructibles, briques destructibles (25 % retirées
  aléatoirement à chaque partie), quatre coins de départ dégagés.
- Une bombe explose 3s après avoir été posée ; le souffle s'arrête sur la première brique (qu'il
  détruit) ou bombe (qu'il fait exploser en chaîne) ; une **bombe perforante** traverse tout sauf
  la pierre.
- Une brique détruite a 20% de chances de laisser un power-up : portée + (45 %), bombe + (10 %),
  portée − (22,5 %), bombe − (12,5 %), crâne (5 %), bombe perforante (5 %).
- Score : +1 par brique détruite, +5 par adversaire éliminé. Le dernier survivant gagne ; à deux
  joueurs la musique passe en mode « duel ».

## Développement

```bash
uv run pytest                               # 54 tests (moteur, IA, générateur, UI hors écran)
uv run ruff check . && uv run ruff format . # lint + formatage
uv run python tools/generate_assets.py      # régénère images et sons (créations originales)
```

## Assets et licence

Toutes les images et musiques sont des créations originales générées procéduralement par
`tools/generate_assets.py` (aucun contenu tiers). Le projet est sous licence
[MIT](LICENSE). PyQt6, utilisé comme dépendance, est distribué sous GPL v3.
