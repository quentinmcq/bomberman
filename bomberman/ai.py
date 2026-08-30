"""Intelligence artificielle des joueurs non contrôlés.

L'IA raisonne en trois temps, à chaque tick (toutes les ``AI_PERIOD`` secondes) :

1. **Survie** : si sa case est menacée (flamme ou souffle prévu d'une bombe), elle
   rejoint la case sûre la plus proche (parcours en largeur).
2. **Attaque** : si poser une bombe ici toucherait une brique ou un adversaire et
   qu'une issue sûre est atteignable avant l'explosion, elle pose la bombe.
3. **Exploration** : sinon elle se dirige vers la cible la plus proche (bonus,
   brique à casser, adversaire) en évitant les zones dangereuses et les malus ;
   à défaut elle se déplace au hasard.

Tout est déterministe pour un ``random.Random`` donné.
"""

from __future__ import annotations

import random
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from .model import BOMB_FUSE, Bomb, Coord, Direction, Game, Player, Tile

AI_PERIOD = 0.5  # secondes entre deux décisions
ESCAPE_DEPTH = 8  # longueur max. d'un chemin de fuite quand on est déjà en danger
# Avant de poser une bombe, l'issue doit être atteignable avant l'explosion :
# une case par décision, en gardant une décision de marge.
BOMB_ESCAPE_STEPS = int(BOMB_FUSE / AI_PERIOD) - 1
SEARCH_DEPTH = 40
RANDOM_MOVE_CHANCE = 0.75

_DIRECTION_BY_DELTA = {direction.value: direction for direction in Direction}


@dataclass(frozen=True)
class Action:
    kind: str  # "move" | "bomb" | "wait"
    direction: Direction | None = None


WAIT = Action("wait")
PLACE_BOMB = Action("bomb")


def move(direction: Direction) -> Action:
    return Action("move", direction)


def danger_cells(game: Game, extra: Bomb | None = None) -> set[Coord]:
    """Toutes les cases actuellement ou prochainement mortelles."""
    danger: set[Coord] = set(game.flames)
    for bomb in game.bombs:
        danger |= game.blast_cells(bomb)
    if extra is not None:
        danger |= game.blast_cells(extra)
    return danger


def find_path(
    game: Game,
    start: Coord,
    is_goal: Callable[[Coord], bool],
    avoid: set[Coord],
    max_depth: int,
) -> list[Coord] | None:
    """Plus court chemin (hors case de départ) vers une case satisfaisant ``is_goal``."""
    previous: dict[Coord, Coord | None] = {start: None}
    queue = deque([(start, 0)])
    while queue:
        pos, depth = queue.popleft()
        if pos != start and is_goal(pos):
            path: list[Coord] = []
            cursor: Coord | None = pos
            while cursor is not None and cursor != start:
                path.append(cursor)
                cursor = previous[cursor]
            path.reverse()
            return path
        if depth >= max_depth:
            continue
        for direction in Direction:
            nxt = direction.step(pos)
            if nxt in previous or nxt in avoid or not game.is_walkable(*nxt):
                continue
            previous[nxt] = pos
            queue.append((nxt, depth + 1))
    return None


def direction_to(origin: Coord, target: Coord) -> Direction:
    """Direction menant d'une case à une case adjacente."""
    delta = (target[0] - origin[0], target[1] - origin[1])
    try:
        return _DIRECTION_BY_DELTA[delta]
    except KeyError:
        raise ValueError(f"{target} n'est pas adjacent à {origin}") from None


def decide(game: Game, player: Player, rng: random.Random) -> Action:
    """Choisit l'action du joueur ``player`` pour ce tick."""
    if game.over or not player.alive:
        return WAIT

    pos = player.pos
    danger = danger_cells(game)
    flames = set(game.flames)

    def as_move(direction: Direction) -> Action:
        # Les contrôles d'un joueur maudit sont inversés : on compense.
        return move(direction.opposite if player.cursed else direction)

    # 1. Survie
    if pos in danger:
        escape = find_path(game, pos, lambda p: p not in danger, flames, ESCAPE_DEPTH)
        if escape:
            return as_move(direction_to(pos, escape[0]))
        return WAIT

    enemies = [p for p in game.players if p.alive and p is not player]

    # 2. Attaque
    if player.bombs_placed < player.max_bombs and game.bomb_at(*pos) is None:
        hypothetical = Bomb(pos[0], pos[1], player.index, player.fire_range, player.pierce)
        blast = game.blast_cells(hypothetical)
        hits_brick = any(game.tile(r, c) is Tile.BRICK for r, c in blast)
        hits_enemy = any(enemy.pos in blast for enemy in enemies)
        if hits_brick or hits_enemy:
            new_danger = danger | blast
            escape = find_path(game, pos, lambda p: p not in new_danger, flames, BOMB_ESCAPE_STEPS)
            if escape:
                return PLACE_BOMB

    # 3. Exploration
    malus = {p for p, powerup in game.powerups.items() if not powerup.is_bonus}

    def is_target(cell: Coord) -> bool:
        powerup = game.powerups.get(cell)
        if powerup is not None and powerup.is_bonus:
            return True
        for direction in Direction:
            r, c = direction.step(cell)
            if game.in_bounds(r, c) and game.tile(r, c) is Tile.BRICK:
                return True
        return any(abs(e.row - cell[0]) + abs(e.col - cell[1]) == 1 for e in enemies)

    path = find_path(game, pos, is_target, danger | malus, SEARCH_DEPTH)
    if path:
        return as_move(direction_to(pos, path[0]))

    options = [
        direction
        for direction in Direction
        if game.is_walkable(*direction.step(pos))
        and direction.step(pos) not in danger
        and direction.step(pos) not in malus
    ]
    if options and rng.random() < RANDOM_MOVE_CHANCE:
        return as_move(rng.choice(options))
    return WAIT
