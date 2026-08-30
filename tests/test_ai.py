"""Tests de l'IA : survie, attaque, exploration, déterminisme."""

from __future__ import annotations

import random

from bomberman import ai
from bomberman.model import Direction, Game, PowerUp, Tile
from helpers import open_arena


def test_ai_escapes_from_its_own_bomb():
    game = open_arena()
    blue = game.players[1]
    assert game.place_bomb(blue)
    danger = ai.danger_cells(game)
    assert blue.pos in danger
    for _ in range(2):
        action = ai.decide(game, blue, random.Random(0))
        assert action.kind == "move"
        assert game.move(blue, action.direction)
    assert blue.pos not in danger
    assert blue.alive


def test_ai_bombs_a_brick_when_it_can_escape():
    game = open_arena()
    blue = game.players[1]
    game.grid[1][18] = Tile.BRICK
    action = ai.decide(game, blue, random.Random(0))
    assert action == ai.PLACE_BOMB


def test_ai_refuses_to_bomb_without_escape():
    game = open_arena()
    blue = game.players[1]
    game.grid[1][18] = Tile.BRICK
    game.grid[2][19] = Tile.BRICK
    action = ai.decide(game, blue, random.Random(0))
    assert action == ai.WAIT


def test_ai_refuses_to_bomb_when_the_escape_is_too_long():
    game = open_arena()
    blue = game.players[1]
    game.grid[1][18] = Tile.BRICK
    for r in range(3, 10, 2):
        game.grid[r][18] = Tile.BRICK
    blue.fire_range = 8
    assert ai.decide(game, blue, random.Random(0)) != ai.PLACE_BOMB
    blue.fire_range = 1
    assert ai.decide(game, blue, random.Random(0)) == ai.PLACE_BOMB


def test_ai_bombs_an_adjacent_enemy():
    game = open_arena()
    blue, red = game.players[1], game.players[0]
    red.row, red.col = 1, 18
    action = ai.decide(game, blue, random.Random(0))
    assert action == ai.PLACE_BOMB


def test_ai_heads_for_a_bonus():
    game = open_arena()
    blue = game.players[1]
    game.powerups[(1, 17)] = PowerUp.FIRE_UP
    action = ai.decide(game, blue, random.Random(0))
    assert action == ai.move(Direction.LEFT)


def test_ai_avoids_malus():
    game = open_arena()
    blue = game.players[1]
    game.powerups[(1, 18)] = PowerUp.SKULL
    for seed in range(10):
        action = ai.decide(game, blue, random.Random(seed))
        if action.kind == "move":
            assert action.direction is not Direction.LEFT


def test_cursed_ai_compensates_inverted_controls():
    game = open_arena()
    blue = game.players[1]
    blue.curse_left = 5.0
    game.powerups[(1, 17)] = PowerUp.FIRE_UP
    action = ai.decide(game, blue, random.Random(0))
    assert action.direction is Direction.RIGHT
    assert game.move(blue, action.direction)
    assert blue.pos == (1, 18)


def simulate(game: Game, seconds: float, rng: random.Random, check=None) -> None:
    steps = int(seconds / ai.AI_PERIOD)
    for _ in range(steps):
        for player in game.players:
            if not (player.alive and player.is_ai):
                continue
            danger_before = ai.danger_cells(game)
            was_safe = player.pos not in danger_before
            action = ai.decide(game, player, rng)
            if action.kind == "move":
                moved = game.move(player, action.direction)
                if check is not None and was_safe and moved:
                    check(player, danger_before)
            elif action.kind == "bomb":
                game.place_bomb(player)
        game.tick(ai.AI_PERIOD)


def test_ai_never_walks_from_safety_into_danger():
    def check(player, danger_before):
        assert player.pos not in danger_before, f"{player.name} est entré dans une zone dangereuse"

    for seed in range(12):
        game = Game(random.Random(seed), ai_players=(0, 1, 2, 3))
        simulate(game, 60.0, random.Random(seed), check)


def test_full_ai_game_progresses_and_terminates():
    finished = 0
    for seed in range(6):
        game = Game(random.Random(seed), ai_players=(0, 1, 2, 3))
        bricks_before = sum(tile is Tile.BRICK for row in game.grid for tile in row)
        simulate(game, 240.0, random.Random(seed))
        bricks_after = sum(tile is Tile.BRICK for row in game.grid for tile in row)
        assert bricks_after < bricks_before, "l'IA doit casser des briques"
        finished += game.over
    assert finished >= 1, "au moins une partie entièrement automatique doit se terminer en 4 min"


def test_ai_is_deterministic_for_a_given_seed():
    def snapshot(seed: int):
        game = Game(random.Random(seed), ai_players=(0, 1, 2, 3))
        simulate(game, 90.0, random.Random(seed))
        return (
            [(p.pos, p.alive, p.score) for p in game.players],
            [row[:] for row in game.grid],
            sorted(game.powerups.items(), key=lambda item: item[0]),
        )

    assert snapshot(3) == snapshot(3)
