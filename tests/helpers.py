"""Aides partagées par les tests."""

from __future__ import annotations

import random

from bomberman.model import Game, Tile


def make_game(seed: int = 1, **kwargs) -> Game:
    return Game(random.Random(seed), **kwargs)


def clear_bricks(game: Game) -> None:
    """Retire toutes les briques : les déplacements deviennent prévisibles."""
    for row in game.grid:
        for c, tile in enumerate(row):
            if tile is Tile.BRICK:
                row[c] = Tile.FLOOR


def open_arena(seed: int = 1) -> Game:
    game = make_game(seed)
    clear_bricks(game)
    return game


def tick(game: Game, seconds: float, step: float = 0.05) -> None:
    """Fait avancer la partie de ``seconds`` par pas de ``step``."""
    elapsed = 0.0
    while elapsed < seconds - 1e-9:
        game.tick(step)
        elapsed += step
