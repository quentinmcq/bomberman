"""Widget de jeu : clavier, horloge et relais des événements (le dessin est délégué).

Un seul humain joue, avec le personnage choisi avant la partie ; les trois autres
sont toujours des IA. Les touches sont fixes : Z Q S D (ou W A S D) et les flèches
pour se déplacer, Espace pour poser une bombe.
"""

from __future__ import annotations

import math
import random

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QPainter, QPaintEvent
from PyQt6.QtWidgets import QWidget

from .. import ai
from ..assets import Textures
from ..model import Direction, Game, Player
from .renderer import BACKGROUND, BoardRenderer

TICK_MS = 50
MOVE_REPEAT = 0.16
RESULT_DELAY = 6.0

KEY_BINDINGS: dict[Qt.Key, Direction | None] = {
    Qt.Key.Key_Z: Direction.UP,
    Qt.Key.Key_W: Direction.UP,
    Qt.Key.Key_Up: Direction.UP,
    Qt.Key.Key_S: Direction.DOWN,
    Qt.Key.Key_Down: Direction.DOWN,
    Qt.Key.Key_Q: Direction.LEFT,
    Qt.Key.Key_A: Direction.LEFT,
    Qt.Key.Key_Left: Direction.LEFT,
    Qt.Key.Key_D: Direction.RIGHT,
    Qt.Key.Key_Right: Direction.RIGHT,
    Qt.Key.Key_Space: None,
}

EVENT_SOUNDS = {
    "explosion": "explosion",
    "pickup": "pickup",
    "bomb_placed": "bomb",
    "death": "death",
}


class GameWidget(QWidget):
    game_over = pyqtSignal(object)
    phase_changed = pyqtSignal(str)
    sound = pyqtSignal(str)
    pause_toggled = pyqtSignal(bool)
    return_to_menu = pyqtSignal()

    def __init__(self, textures: Textures, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.renderer = BoardRenderer(textures)
        self.game: Game | None = None
        self.human_index = 0
        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._on_tick)
        self._held: list[Direction] = []
        self._cooldown = 0.0
        self._ai_accumulator = 0.0
        self._paused = False
        self._phase = ""
        self._result_timer = 0.0
        self._game_over_announced = False
        self._menu_requested = False
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(640, 480)

    def start_new_game(self, seed: int | None = None, human: int = 0) -> None:
        """Lance une partie où l'humain joue le personnage ``human`` (0-3)."""
        rng = random.Random(seed)
        self.game = Game(rng, ai_players=[i for i in range(4) if i != human])
        self.human_index = human
        self._held.clear()
        self._cooldown = 0.0
        self._ai_accumulator = 0.0
        self._paused = False
        self._phase = ""
        self._result_timer = 0.0
        self._game_over_announced = False
        self._menu_requested = False
        self._sync()
        self._timer.start()
        self.setFocus()
        self.update()

    def stop(self) -> None:
        self._timer.stop()
        self.game = None
        self._held.clear()
        self.update()

    @property
    def human(self) -> Player | None:
        return None if self.game is None else self.game.players[self.human_index]

    @property
    def paused(self) -> bool:
        return self._paused

    def set_paused(self, paused: bool) -> None:
        if self.game is None or self.game.over or paused == self._paused:
            return
        self._paused = paused
        self._held.clear()
        self.pause_toggled.emit(paused)
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.isAutoRepeat():
            return
        try:
            key = Qt.Key(event.key())
        except ValueError:
            super().keyPressEvent(event)
            return

        if key == Qt.Key.Key_Escape:
            if self.game is not None and not self.game.over:
                self.set_paused(not self._paused)
            return
        if self.game is None:
            super().keyPressEvent(event)
            return
        if self.game.over:
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
                self.return_to_menu.emit()
            return
        if self._paused or key not in KEY_BINDINGS:
            super().keyPressEvent(event)
            return

        direction = KEY_BINDINGS[key]
        player = self.game.players[self.human_index]
        if direction is None:
            self.game.place_bomb(player)
        else:
            if direction in self._held:
                self._held.remove(direction)
            self._held.append(direction)
            self._step(player, direction)
        self._sync()
        self.update()

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.isAutoRepeat():
            return
        try:
            key = Qt.Key(event.key())
        except ValueError:
            return
        direction = KEY_BINDINGS.get(key)
        if direction is not None and direction in self._held:
            self._held.remove(direction)

    def _step(self, player: Player, direction: Direction) -> None:
        assert self.game is not None
        self.game.move(player, direction)
        self._cooldown = MOVE_REPEAT

    def _on_tick(self) -> None:
        game = self.game
        if game is None or self._paused:
            return
        dt = TICK_MS / 1000.0
        if not game.over:
            self._move_held(game, dt)
            self._run_ai(game, dt)
        game.tick(dt)
        self._sync()
        if game.over:
            self._result_timer += dt
            if self._result_timer >= RESULT_DELAY and not self._menu_requested:
                self._menu_requested = True
                self._timer.stop()
                self.return_to_menu.emit()
        self.update()

    def _move_held(self, game: Game, dt: float) -> None:
        if not self._held:
            return
        self._cooldown -= dt
        if self._cooldown <= 0.0:
            self._step(game.players[self.human_index], self._held[-1])

    def _run_ai(self, game: Game, dt: float) -> None:
        self._ai_accumulator += dt
        if self._ai_accumulator < ai.AI_PERIOD:
            return
        self._ai_accumulator -= ai.AI_PERIOD
        for player in game.players:
            if not (player.alive and player.is_ai):
                continue
            action = ai.decide(game, player, game.rng)
            if action.kind == "move" and action.direction is not None:
                game.move(player, action.direction)
            elif action.kind == "bomb":
                game.place_bomb(player)

    def _sync(self) -> None:
        """Relaie l'état du moteur : sons, fin de partie, phase musicale."""
        game = self.game
        assert game is not None
        sounds = {EVENT_SOUNDS[e.kind] for e in game.drain_events() if e.kind in EVENT_SOUNDS}
        for name in sorted(sounds):
            self.sound.emit(name)
        if game.over:
            if not self._game_over_announced:
                self._game_over_announced = True
                self.game_over.emit(game.winner)
            return
        phase = "boss" if len(game.alive_players()) <= 2 else "battle"
        if phase != self._phase:
            self._phase = phase
            self.phase_changed.emit(phase)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        if self.game is None:
            painter.fillRect(self.rect(), BACKGROUND)
        else:
            self.renderer.paint(painter, self.game, self.rect())
            if self.game.over:
                remaining = max(0, math.ceil(RESULT_DELAY - self._result_timer))
                self.renderer.paint_result(painter, self.game, self.rect(), remaining)
            elif self._paused:
                self.renderer.paint_dim(painter, self.rect(), "")
        painter.end()
