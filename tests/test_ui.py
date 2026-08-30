"""Tests de fumée de l'interface Qt (rendu hors écran)."""

from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

import bomberman.assets
from bomberman.assets import Textures
from bomberman.model import Direction, Flame, FlameShape
from bomberman.ui.game_widget import RESULT_DELAY, TICK_MS, GameWidget
from bomberman.ui.main_window import PAGE_GAME, PAGE_MENU, PAGE_OPTIONS, MainWindow


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


def test_textures_scale_and_cache(app):
    textures = Textures()
    textures.preload()
    assert textures.tile("bomb", 40).width() == 40
    frame = textures.player(0, Direction.UP, 1, 32)
    assert frame.width() == 32 and frame.height() == 32
    assert textures.tile("bomb", 40) is textures.tile("bomb", 40)


def test_scaled_texture_cache_is_bounded(app, monkeypatch):
    monkeypatch.setattr(bomberman.assets, "SCALED_CACHE_LIMIT", 16)
    textures = Textures()
    for size in range(8, 48):  # 40 tailles différentes, comme lors d'un redimensionnement
        textures.tile("bomb", size)
    assert textures.cached_scaled <= 16


def test_game_widget_keyboard_and_rendering(app):
    widget = GameWidget(Textures())
    widget.resize(900, 700)
    sounds: list[str] = []
    widget.sound.connect(sounds.append)
    widget.start_new_game(seed=1)
    game = widget.game
    assert game is not None

    QTest.keyClick(widget, Qt.Key.Key_D)
    assert game.players[0].pos == (1, 2)
    QTest.keyClick(widget, Qt.Key.Key_Space)
    assert len(game.bombs) == 1
    assert "bomb" in sounds

    # Le joueur Bleu est une IA jusqu'à ce qu'un humain touche à ses touches.
    assert game.players[1].is_ai
    QTest.keyClick(widget, Qt.Key.Key_L)
    assert not game.players[1].is_ai

    for _ in range(int(3.5 * 1000 / TICK_MS)):
        widget._on_tick()
    assert game.bomb_at(1, 2) is None  # la bombe du joueur a explosé (les IA posent les leurs)
    assert "explosion" in sounds

    image = widget.grab().toImage()
    assert not image.isNull()
    assert image.width() == 900


def test_game_over_is_announced_when_a_human_walks_into_a_flame(app):
    widget = GameWidget(Textures())
    widget.resize(800, 600)
    winners: list[object] = []
    widget.game_over.connect(winners.append)
    widget.start_new_game(seed=3)
    game = widget.game
    assert game is not None
    red, blue, yellow, pink = game.players
    yellow.alive = False
    pink.alive = False
    game.flames[(1, 2)] = Flame(1, 2, FlameShape.CENTER, owner=blue.index)

    QTest.keyClick(widget, Qt.Key.Key_D)
    assert not red.alive and game.over
    assert winners == [blue]
    widget._on_tick()
    assert winners == [blue]  # annoncé une seule fois


def test_pause_and_result_flow(app):
    widget = GameWidget(Textures())
    widget.resize(800, 600)
    states: list[bool] = []
    widget.pause_toggled.connect(states.append)
    widget.start_new_game(seed=2)
    assert widget.game is not None

    QTest.keyClick(widget, Qt.Key.Key_Escape)
    assert widget.paused and states == [True]
    pos_before = widget.game.players[0].pos
    QTest.keyClick(widget, Qt.Key.Key_D)  # ignoré en pause
    assert widget.game.players[0].pos == pos_before
    QTest.keyClick(widget, Qt.Key.Key_Escape)
    assert not widget.paused and states == [True, False]

    returned: list[bool] = []
    widget.return_to_menu.connect(lambda: returned.append(True))
    for player in widget.game.players[1:]:
        player.alive = False
    widget._on_tick()
    assert widget.game.over and widget.game.winner is widget.game.players[0]
    assert not widget.grab().toImage().isNull()
    for _ in range(int(RESULT_DELAY * 1000 / TICK_MS) + 2):
        widget._on_tick()
    assert returned == [True]


def test_main_window_navigation(app):
    window = MainWindow(seed=1, audio_enabled=False)
    window.resize(1000, 750)
    window.show()
    assert window.stack.currentIndex() == PAGE_MENU
    assert not window.grab().toImage().isNull()

    window.menu_page.options_button.click()
    assert window.stack.currentIndex() == PAGE_OPTIONS
    window.options_page.slider.setValue(30)
    assert window.audio.volume == 30
    window.options_page.mute_button.click()
    assert window.audio.muted
    assert window.pause_overlay.mute_button.isChecked()
    window.options_page.back_button.click()
    assert window.stack.currentIndex() == PAGE_MENU

    window.menu_page.play_button.click()
    assert window.stack.currentIndex() == PAGE_GAME
    assert window.game_widget.game is not None
    QTest.keyClick(window.game_widget, Qt.Key.Key_Escape)
    assert window.pause_overlay.isVisible()
    window.pause_overlay.mute_button.click()  # rétablit le son depuis la pause...
    assert not window.audio.muted
    assert not window.options_page.mute_button.isChecked()  # ...et la page Options suit
    window.pause_overlay.resume_button.click()
    assert not window.pause_overlay.isVisible()
    assert not window.grab().toImage().isNull()

    window.show_menu()
    assert window.stack.currentIndex() == PAGE_MENU
    assert window.game_widget.game is None
    window.close()
