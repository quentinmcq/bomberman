"""Dessin du plateau, du bandeau de scores et des superpositions (pause, résultat)."""

from __future__ import annotations

import math

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen

from ..assets import FLAME_TEXTURES, POWERUP_TEXTURES, Textures
from ..model import BOMB_FUSE, FLAME_DURATION, Game, Player, Tile
from .styles import ACCENT, TEAM_COLORS

HUD_HEIGHT = 64
MARGIN = 8
IDLE_DELAY = 0.25  # secondes sans bouger avant de revenir à la pose statique
BACKGROUND = QColor("#0f1620")
DIM = QColor(5, 8, 15, 170)
TERRAIN_TEXTURES = {Tile.FLOOR: "floor", Tile.BRICK: "brick", Tile.STONE: "stone"}

_CENTER = Qt.AlignmentFlag.AlignCenter
_LEFT = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
_RIGHT = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight


class BoardRenderer:
    """Sait dessiner une partie dans un rectangle ; ne conserve aucun état de jeu."""

    def __init__(self, textures: Textures) -> None:
        self.textures = textures

    @staticmethod
    def board_geometry(game: Game, rect: QRect) -> tuple[int, int, int]:
        """(taille d'une case, x0, y0) : plateau centré sous le bandeau, à l'échelle."""
        avail_w = rect.width() - 2 * MARGIN
        avail_h = rect.height() - HUD_HEIGHT - 2 * MARGIN
        tile = max(8, min(avail_w // game.cols, avail_h // game.rows))
        x0 = rect.x() + (rect.width() - tile * game.cols) // 2
        y0 = rect.y() + HUD_HEIGHT + MARGIN + (avail_h - tile * game.rows) // 2
        return tile, x0, y0

    def paint(self, painter: QPainter, game: Game, rect: QRect) -> None:
        painter.fillRect(rect, BACKGROUND)
        tile, x0, y0 = self.board_geometry(game, rect)
        self._paint_terrain(painter, game, tile, x0, y0)
        self._paint_bombs(painter, game, tile, x0, y0)
        self._paint_players(painter, game, tile, x0, y0)
        self._paint_flames(painter, game, tile, x0, y0)
        self._paint_hud(painter, game, rect)

    def paint_dim(
        self, painter: QPainter, rect: QRect, title: str, subtitle: str = "", color: str = ACCENT
    ) -> None:
        """Assombrit la zone et affiche un titre (et un sous-titre) centrés."""
        painter.fillRect(rect, DIM)
        font = QFont(painter.font())
        font.setBold(True)
        font.setPixelSize(max(24, min(72, rect.width() // 16)))
        painter.setFont(font)
        painter.setPen(QColor(color))
        painter.drawText(rect.adjusted(0, 0, 0, -rect.height() // 6), _CENTER, title)
        if subtitle:
            font.setPixelSize(max(14, min(26, rect.width() // 44)))
            font.setBold(False)
            painter.setFont(font)
            painter.setPen(QColor("white"))
            painter.drawText(rect.adjusted(0, rect.height() // 8, 0, 0), _CENTER, subtitle)

    def paint_result(self, painter: QPainter, game: Game, rect: QRect, remaining: int) -> None:
        subtitle = f"Retour au menu dans {remaining} s  —  Entrée pour revenir tout de suite"
        if game.winner is None:
            self.paint_dim(painter, rect, "ÉGALITÉ !", subtitle, "white")
        else:
            title = f"VICTOIRE DU JOUEUR {game.winner.name.upper()} !"
            self.paint_dim(painter, rect, title, subtitle, TEAM_COLORS[game.winner.index])

    # ------------------------------------------------------------------ interne

    def _paint_terrain(self, painter: QPainter, game: Game, tile: int, x0: int, y0: int) -> None:
        pixmaps = {kind: self.textures.tile(name, tile) for kind, name in TERRAIN_TEXTURES.items()}
        for r, row in enumerate(game.grid):
            y = y0 + r * tile
            for c, cell in enumerate(row):
                painter.drawPixmap(x0 + c * tile, y, pixmaps[cell])
        for (r, c), powerup in game.powerups.items():
            pixmap = self.textures.tile(POWERUP_TEXTURES[powerup], tile)
            painter.drawPixmap(x0 + c * tile, y0 + r * tile, pixmap)

    def _paint_bombs(self, painter: QPainter, game: Game, tile: int, x0: int, y0: int) -> None:
        for bomb in game.bombs:
            # Pulsation qui s'accélère à l'approche de l'explosion.
            speed = 6.0 + max(0.0, BOMB_FUSE - bomb.fuse) * 4.0
            size = max(4, int(tile * (1.0 + 0.08 * math.sin(game.elapsed * speed))))
            offset = (tile - size) // 2
            pixmap = self.textures.tile("bomb_pierce" if bomb.pierce else "bomb", size)
            painter.drawPixmap(x0 + bomb.col * tile + offset, y0 + bomb.row * tile + offset, pixmap)

    def _paint_players(self, painter: QPainter, game: Game, tile: int, x0: int, y0: int) -> None:
        skull = max(4, tile // 2)
        for player in game.players:
            if not player.alive:
                continue
            idle = game.elapsed - player.last_move_at > IDLE_DELAY
            frame = 0 if idle else player.frame
            x, y = x0 + player.col * tile, y0 + player.row * tile
            painter.drawPixmap(x, y, self.textures.player(player.index, player.facing, frame, tile))
            if player.cursed:
                painter.drawPixmap(x + tile - skull, y, self.textures.tile("powerup_skull", skull))

    def _paint_flames(self, painter: QPainter, game: Game, tile: int, x0: int, y0: int) -> None:
        for (r, c), flame in game.flames.items():
            fade = max(0.0, min(1.0, flame.ttl / FLAME_DURATION))
            painter.setOpacity(0.35 + 0.65 * fade)
            pixmap = self.textures.tile(FLAME_TEXTURES[flame.shape], tile)
            painter.drawPixmap(x0 + c * tile, y0 + r * tile, pixmap)
        painter.setOpacity(1.0)

    def _paint_hud(self, painter: QPainter, game: Game, rect: QRect) -> None:
        box_w = (rect.width() - MARGIN * 5) // 4
        box_h = HUD_HEIGHT - MARGIN * 2
        font = QFont(painter.font())
        font.setBold(True)
        font.setPixelSize(max(11, min(24, box_h // 2, box_w // 11)))
        painter.setFont(font)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for player in game.players:
            box = QRect(
                rect.x() + MARGIN + player.index * (box_w + MARGIN), rect.y() + MARGIN, box_w, box_h
            )
            color = QColor(TEAM_COLORS[player.index])
            if not player.alive:
                color = color.darker(260)
            painter.setPen(QPen(QColor("black"), 1.5))
            painter.setBrush(color)
            painter.drawRoundedRect(box, 10, 10)
            painter.setPen(QColor("white"))
            inner = box.adjusted(12, 0, -12, 0)
            painter.drawText(inner, _LEFT, f"{player.name} : {player.score}")
            painter.drawText(inner, _RIGHT, self._status(player))

    @staticmethod
    def _status(player: Player) -> str:
        if not player.alive:
            return "éliminé"
        who = "IA" if player.is_ai else "Joueur"
        return f"{who}  B{player.max_bombs} P{player.fire_range}"
