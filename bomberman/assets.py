"""Localisation et chargement des ressources (images, sons)."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

from .model import Direction, FlameShape, PowerUp

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
IMAGES_DIR = ASSETS_DIR / "images"
SOUNDS_DIR = ASSETS_DIR / "sounds"

FRAME_SIZE = 64
PLAYER_SHEETS = ("player_red", "player_blue", "player_yellow", "player_pink")
SHEET_ROWS = {Direction.UP: 0, Direction.DOWN: 1, Direction.LEFT: 2, Direction.RIGHT: 3}
WALK_CYCLE = (0, 1, 0, 2)

TILE_TEXTURES = ("floor", "stone", "brick", "bomb", "bomb_pierce")

POWERUP_TEXTURES = {
    PowerUp.FIRE_UP: "powerup_fire_up",
    PowerUp.FIRE_DOWN: "powerup_fire_down",
    PowerUp.BOMB_UP: "powerup_bomb_up",
    PowerUp.BOMB_DOWN: "powerup_bomb_down",
    PowerUp.PIERCE: "powerup_pierce",
    PowerUp.SKULL: "powerup_skull",
}

FLAME_TEXTURES = {
    FlameShape.CENTER: "flame_center",
    FlameShape.HORIZONTAL: "flame_h",
    FlameShape.VERTICAL: "flame_v",
}

SCALED_CACHE_LIMIT = 512


def image_path(name: str) -> Path:
    return IMAGES_DIR / f"{name}.png"


def sound_path(name: str) -> Path:
    return SOUNDS_DIR / f"{name}.wav"


class Textures:
    """Charge les images une seule fois et met en cache leurs versions redimensionnées."""

    def __init__(self) -> None:
        self._raw: dict[str, QPixmap] = {}
        self._scaled: dict[tuple, QPixmap] = {}

    @property
    def cached_scaled(self) -> int:
        return len(self._scaled)

    def raw(self, name: str) -> QPixmap:
        pixmap = self._raw.get(name)
        if pixmap is None:
            path = image_path(name)
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                raise FileNotFoundError(
                    f"Image introuvable : {path} (lancer tools/generate_assets.py)"
                )
            self._raw[name] = pixmap
        return pixmap

    def tile(self, name: str, size: int) -> QPixmap:
        """Texture carrée ``name`` redimensionnée à ``size`` pixels."""
        key = (name, size)
        pixmap = self._scaled.get(key)
        if pixmap is None:
            pixmap = self._store(key, self.raw(name), size)
        return pixmap

    def player(self, index: int, facing: Direction, frame: int, size: int) -> QPixmap:
        """Image du joueur ``index`` regardant vers ``facing`` à l'étape ``frame`` du cycle."""
        column = WALK_CYCLE[frame % len(WALK_CYCLE)]
        key = ("player", index, facing, column, size)
        pixmap = self._scaled.get(key)
        if pixmap is None:
            sheet = self.raw(PLAYER_SHEETS[index % len(PLAYER_SHEETS)])
            cell = sheet.copy(
                column * FRAME_SIZE, SHEET_ROWS[facing] * FRAME_SIZE, FRAME_SIZE, FRAME_SIZE
            )
            pixmap = self._store(key, cell, size)
        return pixmap

    def _store(self, key: tuple, source: QPixmap, size: int) -> QPixmap:
        if len(self._scaled) >= SCALED_CACHE_LIMIT:
            self._scaled.clear()
        pixmap = source.scaled(
            size,
            size,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        self._scaled[key] = pixmap
        return pixmap

    def preload(self) -> None:
        """Charge toutes les images au démarrage pour éviter les à-coups en jeu."""
        for name in (
            *TILE_TEXTURES,
            *FLAME_TEXTURES.values(),
            *POWERUP_TEXTURES.values(),
            *PLAYER_SHEETS,
        ):
            self.raw(name)
