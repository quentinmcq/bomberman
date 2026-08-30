"""Règles du jeu : grille, joueurs, bombes, flammes et power-ups.

Ce module est du Python pur (aucune dépendance Qt) : il est testable
unitairement et pourrait être réutilisé avec un autre moteur d'affichage.
"""

from __future__ import annotations

import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum, IntEnum

Coord = tuple[int, int]

GRID_COLS = 21
GRID_ROWS = 19
BOMB_FUSE = 3.0
FLAME_DURATION = 0.45
CURSE_DURATION = 10.0
MAX_BOMBS = 8
MAX_RANGE = 8
BRICK_REMOVAL_CHANCE = 0.25
POWERUP_DROP_CHANCE = 0.20
BRICK_SCORE = 1
KILL_SCORE = 5

PLAYER_NAMES: Sequence[str] = ("Rouge", "Bleu", "Jaune", "Rose")


class Tile(IntEnum):
    FLOOR = 0
    BRICK = 1
    STONE = 2


class Direction(Enum):
    UP = (-1, 0)
    DOWN = (1, 0)
    LEFT = (0, -1)
    RIGHT = (0, 1)

    @property
    def dr(self) -> int:
        return self.value[0]

    @property
    def dc(self) -> int:
        return self.value[1]

    @property
    def opposite(self) -> Direction:
        return _OPPOSITE[self]

    @property
    def horizontal(self) -> bool:
        return self.dr == 0

    def step(self, pos: Coord, k: int = 1) -> Coord:
        return pos[0] + self.dr * k, pos[1] + self.dc * k


_OPPOSITE = {
    Direction.UP: Direction.DOWN,
    Direction.DOWN: Direction.UP,
    Direction.LEFT: Direction.RIGHT,
    Direction.RIGHT: Direction.LEFT,
}


class PowerUp(Enum):
    FIRE_UP = "fire_up"
    BOMB_UP = "bomb_up"
    PIERCE = "pierce"
    FIRE_DOWN = "fire_down"
    SKULL = "skull"
    BOMB_DOWN = "bomb_down"

    @property
    def is_bonus(self) -> bool:
        return self in (PowerUp.FIRE_UP, PowerUp.BOMB_UP, PowerUp.PIERCE)


POWERUP_ODDS: Sequence[tuple[PowerUp, float]] = (
    (PowerUp.FIRE_UP, 0.45),
    (PowerUp.BOMB_UP, 0.10),
    (PowerUp.FIRE_DOWN, 0.225),
    (PowerUp.BOMB_DOWN, 0.125),
    (PowerUp.SKULL, 0.05),
    (PowerUp.PIERCE, 0.05),
)


class FlameShape(Enum):
    CENTER = "center"
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


@dataclass(eq=False)
class Player:
    index: int
    name: str
    row: int
    col: int
    is_ai: bool = False
    alive: bool = True
    score: int = 0
    max_bombs: int = 1
    fire_range: int = 1
    pierce: bool = False
    curse_left: float = 0.0
    facing: Direction = Direction.DOWN
    frame: int = 0
    bombs_placed: int = 0
    last_move_at: float = 0.0

    @property
    def pos(self) -> Coord:
        return self.row, self.col

    @property
    def cursed(self) -> bool:
        return self.curse_left > 0.0


@dataclass(eq=False)
class Bomb:
    row: int
    col: int
    owner: int
    fire_range: int
    pierce: bool = False
    fuse: float = BOMB_FUSE

    @property
    def pos(self) -> Coord:
        return self.row, self.col


@dataclass(eq=False)
class Flame:
    row: int
    col: int
    shape: FlameShape
    owner: int
    ttl: float = FLAME_DURATION

    @property
    def pos(self) -> Coord:
        return self.row, self.col


@dataclass(frozen=True)
class GameEvent:
    """Fait marquant produit par le moteur (pour les sons / l'interface)."""

    kind: str
    player: int | None = None
    pos: Coord | None = None
    powerup: PowerUp | None = None


def generate_grid(
    rows: int,
    cols: int,
    rng: random.Random,
    removal_chance: float = BRICK_REMOVAL_CHANCE,
) -> list[list[Tile]]:
    """Terrain classique : bordure et piliers en pierre, briques ailleurs.

    Les quatre coins (case de départ + ses deux voisines) sont dégagés, puis une
    fraction des briques est retirée aléatoirement pour varier les parties.
    """
    if rows < 5 or cols < 5 or rows % 2 == 0 or cols % 2 == 0:
        raise ValueError("La grille doit avoir des dimensions impaires >= 5")
    grid: list[list[Tile]] = []
    for r in range(rows):
        row: list[Tile] = []
        for c in range(cols):
            if r in (0, rows - 1) or c in (0, cols - 1) or (r % 2 == 0 and c % 2 == 0):
                row.append(Tile.STONE)
            else:
                row.append(Tile.BRICK)
        grid.append(row)

    for r, c in spawn_points(rows, cols):
        grid[r][c] = Tile.FLOOR
        for direction in Direction:
            nr, nc = direction.step((r, c))
            if 0 < nr < rows - 1 and 0 < nc < cols - 1 and grid[nr][nc] is Tile.BRICK:
                grid[nr][nc] = Tile.FLOOR

    for r in range(1, rows - 1):
        for c in range(1, cols - 1):
            if grid[r][c] is Tile.BRICK and rng.random() < removal_chance:
                grid[r][c] = Tile.FLOOR
    return grid


def spawn_points(rows: int, cols: int) -> list[Coord]:
    """Coins de départ, ordre des joueurs : haut-gauche, haut-droite, bas-gauche, bas-droite."""
    return [(1, 1), (1, cols - 2), (rows - 2, 1), (rows - 2, cols - 2)]


class Game:
    """État complet d'une partie et application des règles."""

    def __init__(
        self,
        rng: random.Random | None = None,
        *,
        rows: int = GRID_ROWS,
        cols: int = GRID_COLS,
        ai_players: Iterable[int] = (1, 2, 3),
    ) -> None:
        self.rng = rng if rng is not None else random.Random()
        self.rows = rows
        self.cols = cols
        self.grid = generate_grid(rows, cols, self.rng)
        ai = set(ai_players)
        self.players: list[Player] = [
            Player(index, PLAYER_NAMES[index], r, c, is_ai=index in ai)
            for index, (r, c) in enumerate(spawn_points(rows, cols))
        ]
        self.bombs: list[Bomb] = []
        self.flames: dict[Coord, Flame] = {}
        self.powerups: dict[Coord, PowerUp] = {}
        self.events: list[GameEvent] = []
        self.elapsed = 0.0
        self.over = False
        self.winner: Player | None = None

    def in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < self.rows and 0 <= c < self.cols

    def tile(self, r: int, c: int) -> Tile:
        return self.grid[r][c]

    def bomb_at(self, r: int, c: int) -> Bomb | None:
        for bomb in self.bombs:
            if bomb.row == r and bomb.col == c:
                return bomb
        return None

    def player_at(self, r: int, c: int) -> Player | None:
        for player in self.players:
            if player.alive and player.row == r and player.col == c:
                return player
        return None

    def is_walkable(self, r: int, c: int) -> bool:
        """Case traversable : sol libre, sans bombe ni joueur vivant."""
        return (
            self.in_bounds(r, c)
            and self.grid[r][c] is Tile.FLOOR
            and self.bomb_at(r, c) is None
            and self.player_at(r, c) is None
        )

    def blast_ray(self, bomb: Bomb, direction: Direction) -> list[Coord]:
        """Cases atteintes par le souffle de ``bomb`` dans une direction, dans l'ordre.

        Le souffle s'arrête devant la pierre et, sauf bombe perforante, juste après
        la première brique, bombe ou power-up rencontré. Seule source de vérité de
        cette règle : l'explosion et l'IA s'appuient toutes deux dessus.
        """
        cells: list[Coord] = []
        for k in range(1, bomb.fire_range + 1):
            r, c = direction.step(bomb.pos, k)
            if not self.in_bounds(r, c) or self.grid[r][c] is Tile.STONE:
                break
            cells.append((r, c))
            if bomb.pierce:
                continue
            if (
                self.grid[r][c] is Tile.BRICK
                or self.bomb_at(r, c) is not None
                or (r, c) in self.powerups
            ):
                break
        return cells

    def blast_cells(self, bomb: Bomb) -> set[Coord]:
        """Toutes les cases que couvrirait l'explosion de ``bomb`` maintenant."""
        cells = {bomb.pos}
        for direction in Direction:
            cells.update(self.blast_ray(bomb, direction))
        return cells

    def alive_players(self) -> list[Player]:
        return [player for player in self.players if player.alive]

    def drain_events(self) -> list[GameEvent]:
        events, self.events = self.events, []
        return events

    def take_control(self, player: Player) -> None:
        """Un humain prend la main sur un joueur contrôlé par l'IA."""
        player.is_ai = False

    def move(self, player: Player, direction: Direction) -> bool:
        """Déplace le joueur d'une case (contrôles inversés s'il est maudit)."""
        if self.over or not player.alive:
            return False
        if player.cursed:
            direction = direction.opposite
        player.facing = direction
        r, c = direction.step(player.pos)
        if not self.is_walkable(r, c):
            return False
        player.row, player.col = r, c
        player.frame = (player.frame + 1) % 4
        player.last_move_at = self.elapsed
        self._enter_cell(player)
        return True

    def place_bomb(self, player: Player) -> bool:
        """Pose une bombe sous le joueur, dans la limite de son stock."""
        if self.over or not player.alive:
            return False
        if player.bombs_placed >= player.max_bombs or self.bomb_at(player.row, player.col):
            return False
        self.bombs.append(
            Bomb(player.row, player.col, player.index, player.fire_range, player.pierce)
        )
        player.bombs_placed += 1
        self.events.append(GameEvent("bomb_placed", player.index, player.pos))
        return True

    def tick(self, dt: float) -> None:
        """Fait avancer le temps de ``dt`` secondes."""
        self.elapsed += dt
        for player in self.players:
            if player.curse_left > 0.0:
                player.curse_left = max(0.0, player.curse_left - dt)

        expired = []
        for pos, flame in self.flames.items():
            flame.ttl -= dt
            if flame.ttl <= 0.0:
                expired.append(pos)
        for pos in expired:
            del self.flames[pos]

        for bomb in self.bombs:
            bomb.fuse -= dt
        for bomb in [b for b in self.bombs if b.fuse <= 0.0]:
            if bomb in self.bombs:
                self._explode(bomb)

        self._check_game_over()

    def _enter_cell(self, player: Player) -> None:
        powerup = self.powerups.pop(player.pos, None)
        if powerup is not None:
            self._apply_powerup(player, powerup)
            self.events.append(GameEvent("pickup", player.index, player.pos, powerup))
        flame = self.flames.get(player.pos)
        if flame is not None:
            self._kill(player, flame.owner)

    def _apply_powerup(self, player: Player, powerup: PowerUp) -> None:
        if powerup is PowerUp.FIRE_UP:
            player.fire_range = min(MAX_RANGE, player.fire_range + 1)
        elif powerup is PowerUp.FIRE_DOWN:
            player.fire_range = max(1, player.fire_range - 1)
        elif powerup is PowerUp.BOMB_UP:
            player.max_bombs = min(MAX_BOMBS, player.max_bombs + 1)
        elif powerup is PowerUp.BOMB_DOWN:
            player.max_bombs = max(1, player.max_bombs - 1)
        elif powerup is PowerUp.PIERCE:
            player.pierce = True
        elif powerup is PowerUp.SKULL:
            player.curse_left = CURSE_DURATION

    def _explode(self, first: Bomb) -> None:
        """Fait exploser une bombe, et en chaîne toutes celles qu'elle touche."""
        queue = [first]
        while queue:
            bomb = queue.pop()
            if bomb not in self.bombs:
                continue
            self.bombs.remove(bomb)
            owner = self.players[bomb.owner]
            owner.bombs_placed = max(0, owner.bombs_placed - 1)
            self.events.append(GameEvent("explosion", bomb.owner, bomb.pos))
            self._burn(bomb.pos, FlameShape.CENTER, bomb.owner)

            for direction in Direction:
                shape = FlameShape.HORIZONTAL if direction.horizontal else FlameShape.VERTICAL
                for r, c in self.blast_ray(bomb, direction):
                    if self.grid[r][c] is Tile.BRICK:
                        self._destroy_brick(r, c, owner)
                    else:
                        other = self.bomb_at(r, c)
                        if other is not None:
                            queue.append(other)
                        self.powerups.pop((r, c), None)
                    self._burn((r, c), shape, bomb.owner)

    def _destroy_brick(self, r: int, c: int, owner: Player) -> None:
        self.grid[r][c] = Tile.FLOOR
        owner.score += BRICK_SCORE
        if self.rng.random() < POWERUP_DROP_CHANCE:
            self.powerups[(r, c)] = self._roll_powerup()

    def _roll_powerup(self) -> PowerUp:
        roll = self.rng.random()
        cumulative = 0.0
        for powerup, odds in POWERUP_ODDS:
            cumulative += odds
            if roll < cumulative:
                return powerup
        return POWERUP_ODDS[-1][0]

    def _burn(self, pos: Coord, shape: FlameShape, owner: int) -> None:
        existing = self.flames.get(pos)
        if existing is not None and existing.shape is not shape:
            shape = FlameShape.CENTER
        self.flames[pos] = Flame(pos[0], pos[1], shape, owner)
        victim = self.player_at(*pos)
        if victim is not None:
            self._kill(victim, owner)

    def _kill(self, victim: Player, killer: int) -> None:
        if not victim.alive:
            return
        victim.alive = False
        if killer != victim.index:
            self.players[killer].score += KILL_SCORE
        self.events.append(GameEvent("death", victim.index, victim.pos))
        self._check_game_over()

    def _check_game_over(self) -> None:
        if self.over:
            return
        alive = self.alive_players()
        if len(alive) <= 1:
            self.over = True
            self.winner = alive[0] if alive else None
            self.events.append(GameEvent("game_over", self.winner.index if self.winner else None))
