"""Tests des règles du jeu (module pur Python)."""

from __future__ import annotations

import random

import pytest

from bomberman.model import (
    BOMB_FUSE,
    BRICK_SCORE,
    CURSE_DURATION,
    FLAME_DURATION,
    GRID_COLS,
    GRID_ROWS,
    KILL_SCORE,
    MAX_BOMBS,
    MAX_RANGE,
    Bomb,
    Direction,
    Flame,
    FlameShape,
    PowerUp,
    Tile,
    generate_grid,
    spawn_points,
)
from helpers import clear_bricks, make_game, tick


class ScriptedRandom:
    """Remplace ``Game.rng`` : ``random()`` renvoie une suite imposée, puis 0.99.

    Volontairement indépendant de ``random.Random`` : le moteur n'utilise que
    ``random()``, et sous-classer ``Random`` avec un ``__init__`` différent se
    comporte différemment selon la version de Python.
    """

    def __init__(self, values):
        self._values = list(values)

    def random(self):
        return self._values.pop(0) if self._values else 0.99


def test_grid_layout():
    game = make_game()
    grid = game.grid
    assert len(grid) == GRID_ROWS
    assert all(len(row) == GRID_COLS for row in grid)
    assert all(tile is Tile.STONE for tile in grid[0])
    assert all(tile is Tile.STONE for tile in grid[-1])
    assert all(row[0] is Tile.STONE and row[-1] is Tile.STONE for row in grid)
    for r in range(2, GRID_ROWS - 1, 2):
        for c in range(2, GRID_COLS - 1, 2):
            assert grid[r][c] is Tile.STONE
    for r in range(1, GRID_ROWS - 1):
        for c in range(1, GRID_COLS - 1):
            if r % 2 == 1 or c % 2 == 1:
                assert grid[r][c] is not Tile.STONE


def test_spawn_corners_are_clear():
    game = make_game()
    for r, c in spawn_points(GRID_ROWS, GRID_COLS):
        assert game.grid[r][c] is Tile.FLOOR
        for direction in Direction:
            nr, nc = direction.step((r, c))
            if 0 < nr < GRID_ROWS - 1 and 0 < nc < GRID_COLS - 1:
                assert game.grid[nr][nc] is Tile.FLOOR


def test_brick_removal_ratio():
    def count_bricks(chance: float) -> int:
        grid = generate_grid(GRID_ROWS, GRID_COLS, random.Random(7), chance)
        return sum(tile is Tile.BRICK for row in grid for tile in row)

    full = count_bricks(0.0)
    assert full > 100
    assert count_bricks(1.0) == 0
    partial = count_bricks(0.25)
    assert 0.6 * full < partial < 0.9 * full


def test_grid_dimensions_are_validated():
    with pytest.raises(ValueError):
        generate_grid(4, GRID_COLS, random.Random(0))
    with pytest.raises(ValueError):
        generate_grid(GRID_ROWS, 20, random.Random(0))


def test_players_start_in_corners():
    game = make_game()
    assert [player.pos for player in game.players] == spawn_points(GRID_ROWS, GRID_COLS)
    assert [player.is_ai for player in game.players] == [False, True, True, True]
    assert [player.name for player in game.players] == ["Rouge", "Bleu", "Jaune", "Rose"]


def test_move_into_free_cell():
    game = make_game()
    clear_bricks(game)
    player = game.players[0]
    assert game.move(player, Direction.RIGHT)
    assert player.pos == (1, 2)
    assert player.facing is Direction.RIGHT
    assert player.frame == 1


def test_move_blocked_by_stone_brick_bomb_and_player():
    game = make_game()
    clear_bricks(game)
    player = game.players[0]

    assert not game.move(player, Direction.UP)
    assert player.pos == (1, 1)
    assert player.facing is Direction.UP

    game.grid[1][2] = Tile.BRICK
    assert not game.move(player, Direction.RIGHT)
    game.grid[1][2] = Tile.FLOOR

    game.bombs.append(Bomb(1, 2, owner=1, fire_range=1))
    assert not game.move(player, Direction.RIGHT)
    game.bombs.clear()

    other = game.players[1]
    other.row, other.col = 1, 2
    assert not game.move(player, Direction.RIGHT)

    other.alive = False
    assert game.move(player, Direction.RIGHT)


def test_curse_inverts_controls_and_expires():
    game = make_game()
    clear_bricks(game)
    player = game.players[0]
    player.row, player.col = 1, 5
    player.curse_left = 1.0
    assert game.move(player, Direction.RIGHT)
    assert player.pos == (1, 4)
    assert player.facing is Direction.LEFT
    tick(game, 1.1)
    assert not player.cursed
    assert game.move(player, Direction.RIGHT)
    assert player.pos == (1, 5)


@pytest.mark.parametrize(
    ("powerup", "attribute", "expected"),
    [
        (PowerUp.FIRE_UP, "fire_range", 2),
        (PowerUp.BOMB_UP, "max_bombs", 2),
        (PowerUp.PIERCE, "pierce", True),
        (PowerUp.FIRE_DOWN, "fire_range", 1),
        (PowerUp.BOMB_DOWN, "max_bombs", 1),
        (PowerUp.SKULL, "curse_left", CURSE_DURATION),
    ],
)
def test_powerup_pickup_effects(powerup, attribute, expected):
    game = make_game()
    clear_bricks(game)
    player = game.players[0]
    game.powerups[(1, 2)] = powerup
    assert game.move(player, Direction.RIGHT)
    assert getattr(player, attribute) == expected
    assert (1, 2) not in game.powerups
    kinds = [event.kind for event in game.drain_events()]
    assert kinds == ["pickup"]


def test_powerups_are_capped():
    game = make_game()
    player = game.players[0]
    for _ in range(20):
        game._apply_powerup(player, PowerUp.FIRE_UP)
        game._apply_powerup(player, PowerUp.BOMB_UP)
    assert player.fire_range == MAX_RANGE
    assert player.max_bombs == MAX_BOMBS
    for _ in range(20):
        game._apply_powerup(player, PowerUp.FIRE_DOWN)
        game._apply_powerup(player, PowerUp.BOMB_DOWN)
    assert player.fire_range == 1
    assert player.max_bombs == 1


def test_place_bomb_respects_limit_and_occupied_cell():
    game = make_game()
    clear_bricks(game)
    player = game.players[0]
    assert game.place_bomb(player)
    assert player.bombs_placed == 1
    assert not game.place_bomb(player)
    assert game.move(player, Direction.RIGHT)
    assert not game.place_bomb(player)
    player.max_bombs = 2
    assert game.place_bomb(player)
    assert len(game.bombs) == 2
    assert [event.kind for event in game.drain_events()] == ["bomb_placed", "bomb_placed"]


def test_bomb_explodes_after_fuse_and_frees_slot():
    game = make_game()
    clear_bricks(game)
    player = game.players[0]
    assert game.place_bomb(player)
    assert game.move(player, Direction.DOWN)
    assert game.move(player, Direction.DOWN)
    tick(game, BOMB_FUSE - 0.2)
    assert len(game.bombs) == 1
    tick(game, 0.4)
    assert game.bombs == []
    assert player.bombs_placed == 0
    assert player.alive
    assert (1, 1) in game.flames and game.flames[(1, 1)].shape is FlameShape.CENTER
    assert (1, 2) in game.flames and game.flames[(1, 2)].shape is FlameShape.HORIZONTAL
    assert (2, 1) in game.flames and game.flames[(2, 1)].shape is FlameShape.VERTICAL
    assert (0, 1) not in game.flames
    kinds = [event.kind for event in game.drain_events()]
    assert kinds.count("explosion") == 1


def test_flames_expire():
    game = make_game()
    clear_bricks(game)
    game.bombs.append(Bomb(5, 5, owner=0, fire_range=2, fuse=0.01))
    tick(game, 0.1)
    assert game.flames
    tick(game, FLAME_DURATION + 0.1)
    assert game.flames == {}


def test_explosion_destroys_first_brick_and_stops():
    game = make_game()
    clear_bricks(game)
    game.grid[5][7] = Tile.BRICK
    game.grid[5][8] = Tile.BRICK
    game.rng = ScriptedRandom([0.9])
    game.bombs.append(Bomb(5, 5, owner=0, fire_range=4, fuse=0.01))
    tick(game, 0.1)
    assert game.grid[5][7] is Tile.FLOOR
    assert game.grid[5][8] is Tile.BRICK
    assert (5, 7) in game.flames
    assert (5, 8) not in game.flames
    assert game.players[0].score == BRICK_SCORE


def test_pierce_bomb_goes_through_bricks():
    game = make_game()
    clear_bricks(game)
    game.grid[5][7] = Tile.BRICK
    game.grid[5][8] = Tile.BRICK
    game.rng = ScriptedRandom([0.9, 0.9])
    game.bombs.append(Bomb(5, 5, owner=0, fire_range=4, pierce=True, fuse=0.01))
    tick(game, 0.1)
    assert game.grid[5][7] is Tile.FLOOR
    assert game.grid[5][8] is Tile.FLOOR
    assert (5, 9) in game.flames
    assert game.players[0].score == 2 * BRICK_SCORE


def test_powerup_drop_follows_odds_table():
    game = make_game()
    clear_bricks(game)
    game.grid[5][6] = Tile.BRICK
    game.rng = ScriptedRandom([0.1, 0.5])
    game.bombs.append(Bomb(5, 5, owner=0, fire_range=1, fuse=0.01))
    tick(game, 0.1)
    assert game.powerups == {(5, 6): PowerUp.BOMB_UP}


def test_flame_destroys_powerup_and_stops():
    game = make_game()
    clear_bricks(game)
    game.powerups[(5, 6)] = PowerUp.FIRE_UP
    game.bombs.append(Bomb(5, 5, owner=0, fire_range=3, fuse=0.01))
    tick(game, 0.1)
    assert (5, 6) not in game.powerups
    assert (5, 6) in game.flames
    assert (5, 7) not in game.flames


def test_chain_reaction():
    game = make_game()
    clear_bricks(game)
    game.players[1].bombs_placed = 1
    game.bombs.append(Bomb(5, 5, owner=0, fire_range=1, fuse=0.01))
    game.bombs.append(Bomb(5, 6, owner=1, fire_range=1, fuse=BOMB_FUSE))
    tick(game, 0.1)
    assert game.bombs == []
    assert (5, 7) in game.flames
    assert game.players[1].bombs_placed == 0
    kinds = [event.kind for event in game.drain_events()]
    assert kinds.count("explosion") == 2


def test_kill_awards_points_and_ends_the_duel():
    game = make_game()
    clear_bricks(game)
    red, blue, yellow, pink = game.players
    yellow.alive = False
    pink.alive = False
    blue.row, blue.col = 1, 2
    assert game.place_bomb(red)
    assert game.move(red, Direction.DOWN)
    assert game.move(red, Direction.DOWN)
    tick(game, BOMB_FUSE + 0.1)
    assert not blue.alive
    assert red.alive
    assert red.score == KILL_SCORE
    assert game.over
    assert game.winner is red
    kinds = [event.kind for event in game.drain_events()]
    assert "death" in kinds and kinds[-1] == "game_over"


def test_suicide_gives_no_points():
    game = make_game()
    clear_bricks(game)
    red = game.players[0]
    assert game.place_bomb(red)
    tick(game, BOMB_FUSE + 0.1)
    assert not red.alive
    assert red.score == 0


def test_walking_into_a_flame_is_lethal():
    game = make_game()
    clear_bricks(game)
    red, blue = game.players[0], game.players[1]
    game.flames[(1, 2)] = Flame(1, 2, FlameShape.CENTER, owner=blue.index)
    assert game.move(red, Direction.RIGHT)
    assert not red.alive
    assert blue.score == KILL_SCORE


def test_dead_players_cannot_act():
    game = make_game()
    clear_bricks(game)
    red = game.players[0]
    red.alive = False
    assert not game.move(red, Direction.RIGHT)
    assert not game.place_bomb(red)


def test_draw_when_nobody_survives():
    game = make_game()
    for player in game.players:
        player.alive = False
    game.tick(0.05)
    assert game.over
    assert game.winner is None
    assert not game.move(game.players[0], Direction.RIGHT)


def test_take_control_switches_ai_off():
    game = make_game()
    blue = game.players[1]
    assert blue.is_ai
    game.take_control(blue)
    assert not blue.is_ai


def test_drain_events_empties_queue():
    game = make_game()
    game.place_bomb(game.players[0])
    assert len(game.drain_events()) == 1
    assert game.drain_events() == []


def test_walking_into_a_flame_ends_the_duel_immediately():
    game = make_game()
    clear_bricks(game)
    red, blue, yellow, pink = game.players
    yellow.alive = False
    pink.alive = False
    game.flames[(1, 2)] = Flame(1, 2, FlameShape.CENTER, owner=blue.index)
    assert game.move(red, Direction.RIGHT)
    assert not red.alive
    assert game.over and game.winner is blue
    assert [event.kind for event in game.drain_events()] == ["death", "game_over"]


def test_blast_cells_follow_propagation_rules():
    game = make_game()
    clear_bricks(game)
    game.grid[5][7] = Tile.BRICK
    cells = game.blast_cells(Bomb(5, 5, owner=0, fire_range=4))
    assert (5, 5) in cells
    assert (5, 6) in cells and (5, 7) in cells
    assert (5, 8) not in cells
    assert (1, 5) in cells and (9, 5) in cells
    assert (0, 5) not in game.blast_cells(Bomb(3, 5, owner=0, fire_range=4))

    pierce = game.blast_cells(Bomb(5, 5, owner=0, fire_range=4, pierce=True))
    assert (5, 8) in pierce and (5, 9) in pierce

    game.bombs.append(Bomb(5, 3, owner=1, fire_range=1))
    game.powerups[(7, 5)] = PowerUp.FIRE_UP
    cells = game.blast_cells(Bomb(5, 5, owner=0, fire_range=4))
    assert (5, 3) in cells and (5, 2) not in cells
    assert (7, 5) in cells and (8, 5) not in cells
