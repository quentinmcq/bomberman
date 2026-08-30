"""Widget de jeu : clavier, horloge et relais des événements (le dessin est délégué)."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QPainter, QPaintEvent
from PyQt6.QtWidgets import QWidget

from .. import ai
from ..assets import Textures
from ..model import Direction, Game, Player
from .renderer import BACKGROUND, BoardRenderer

TICK_MS = 50
MOVE_REPEAT = 0.16  # secondes entre deux pas lorsqu'une touche reste enfoncée
RESULT_DELAY = 6.0  # secondes d'affichage du résultat avant retour au menu


@dataclass(frozen=True)
class Binding:
    player: int
    direction: Direction | None  # None = poser une bombe


# Touches du jeu d'origine (ZQSD, KOLM, flèches, pavé numérique) + alias WASD.
KEY_BINDINGS: dict[Qt.Key, Binding] = {
    Qt.Key.Key_Z: Binding(0, Direction.UP),
    Qt.Key.Key_W: Binding(0, Direction.UP),
    Qt.Key.Key_S: Binding(0, Direction.DOWN),
    Qt.Key.Key_Q: Binding(0, Direction.LEFT),
    Qt.Key.Key_A: Binding(0, Direction.LEFT),
    Qt.Key.Key_D: Binding(0, Direction.RIGHT),
    Qt.Key.Key_Space: Binding(0, None),
    Qt.Key.Key_O: Binding(1, Direction.UP),
    Qt.Key.Key_L: Binding(1, Direction.DOWN),
    Qt.Key.Key_K: Binding(1, Direction.LEFT),
    Qt.Key.Key_M: Binding(1, Direction.RIGHT),
    Qt.Key.Key_Shift: Binding(1, None),
    Qt.Key.Key_Up: Binding(2, Direction.UP),
    Qt.Key.Key_Down: Binding(2, Direction.DOWN),
    Qt.Key.Key_Left: Binding(2, Direction.LEFT),
    Qt.Key.Key_Right: Binding(2, Direction.RIGHT),
    Qt.Key.Key_Control: Binding(2, None),
    Qt.Key.Key_0: Binding(2, None),
    Qt.Key.Key_8: Binding(3, Direction.UP),
    Qt.Key.Key_5: Binding(3, Direction.DOWN),
    Qt.Key.Key_4: Binding(3, Direction.LEFT),
    Qt.Key.Key_6: Binding(3, Direction.RIGHT),
    Qt.Key.Key_Plus: Binding(3, None),
}

EVENT_SOUNDS = {
    "explosion": "explosion",
    "pickup": "pickup",
    "bomb_placed": "bomb",
    "death": "death",
}


class GameWidget(QWidget):
    game_over = pyqtSignal(object)  # Player gagnant, ou None en cas d'égalité
    phase_changed = pyqtSignal(str)  # "battle" (3-4 joueurs en vie) ou "boss" (duel)
    sound = pyqtSignal(str)  # nom d'un effet sonore à jouer
    pause_toggled = pyqtSignal(bool)
    return_to_menu = pyqtSignal()

    def __init__(self, textures: Textures, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.renderer = BoardRenderer(textures)
        self.game: Game | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._on_tick)
        self._held: dict[int, list[Direction]] = {}  # directions maintenues, par joueur
        self._cooldown: dict[int, float] = {}
        self._ai_accumulator = 0.0
        self._paused = False
        self._phase = ""
        self._result_timer = 0.0
        self._game_over_announced = False
        self._menu_requested = False
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(640, 480)

    # ------------------------------------------------------------------ cycle de vie

    def start_new_game(self, seed: int | None = None) -> None:
        self.game = Game(random.Random(seed))
        self._held.clear()
        self._cooldown = {player.index: 0.0 for player in self.game.players}
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
    def paused(self) -> bool:
        return self._paused

    def set_paused(self, paused: bool) -> None:
        if self.game is None or self.game.over or paused == self._paused:
            return
        self._paused = paused
        self._held.clear()
        self.pause_toggled.emit(paused)
        self.update()

    # ------------------------------------------------------------------ clavier

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (API Qt)
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
        if self._paused:
            return

        binding = KEY_BINDINGS.get(key)
        if binding is None:
            super().keyPressEvent(event)
            return
        player = self.game.players[binding.player]
        if player.is_ai:
            self.game.take_control(player)
        if binding.direction is None:
            self.game.place_bomb(player)
        else:
            held = self._held.setdefault(binding.player, [])
            if binding.direction in held:
                held.remove(binding.direction)
            held.append(binding.direction)
            self._step(player, binding.direction)
        self._sync()
        self.update()

    def keyReleaseEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (API Qt)
        if event.isAutoRepeat():
            return
        try:
            key = Qt.Key(event.key())
        except ValueError:
            return
        binding = KEY_BINDINGS.get(key)
        if binding is not None and binding.direction is not None:
            held = self._held.get(binding.player)
            if held and binding.direction in held:
                held.remove(binding.direction)

    def _step(self, player: Player, direction: Direction) -> None:
        assert self.game is not None
        self.game.move(player, direction)
        self._cooldown[player.index] = MOVE_REPEAT

    # ------------------------------------------------------------------ horloge

    def _on_tick(self) -> None:
        game = self.game
        if game is None or self._paused:
            return
        dt = TICK_MS / 1000.0
        if not game.over:
            self._move_held(game, dt)
            self._run_ai(game, dt)
        game.tick(dt)  # après la fin, laisse les dernières bombes et flammes se résoudre
        self._sync()
        if game.over:
            self._result_timer += dt
            if self._result_timer >= RESULT_DELAY and not self._menu_requested:
                self._menu_requested = True
                self._timer.stop()
                self.return_to_menu.emit()
        self.update()

    def _move_held(self, game: Game, dt: float) -> None:
        for index, held in self._held.items():
            if not held:
                continue
            self._cooldown[index] -= dt
            if self._cooldown[index] <= 0.0:
                self._step(game.players[index], held[-1])

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

    # ------------------------------------------------------------------ rendu

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 (API Qt)
        painter = QPainter(self)
        if self.game is None:
            painter.fillRect(self.rect(), BACKGROUND)
        else:
            self.renderer.paint(painter, self.game, self.rect())
            if self.game.over:
                remaining = max(0, math.ceil(RESULT_DELAY - self._result_timer))
                self.renderer.paint_result(painter, self.game, self.rect(), remaining)
            elif self._paused:
                # Le titre et les boutons viennent de PauseOverlay : on assombrit seulement.
                self.renderer.paint_dim(painter, self.rect(), "")
        painter.end()
