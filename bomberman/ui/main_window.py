"""Fenêtre principale : navigation entre les pages, musique, pause."""

from __future__ import annotations

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QIcon, QKeyEvent, QResizeEvent
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..assets import Textures, image_path
from ..audio import AudioManager
from ..model import Player
from .game_widget import GameWidget
from .menus import MenuPage, OptionsPage, PauseOverlay, SetupPage
from .styles import (
    BUTTON_QSS,
    OVERLAY_QSS,
    PANEL_LABEL_QSS,
    ROOT_QSS,
    SLIDER_QSS,
    TITLE_QSS,
)

PAGE_MENU = 0
PAGE_SETUP = 1
PAGE_OPTIONS = 2
PAGE_GAME = 3


class GamePage(QWidget):
    """Conteneur du plateau qui garde la surcouche de pause plein cadre."""

    def __init__(self, game_widget: GameWidget, overlay: PauseOverlay) -> None:
        super().__init__()
        self.overlay = overlay
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(game_widget)
        overlay.setParent(self)
        overlay.hide()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.overlay.setGeometry(self.rect())


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        seed: int | None = None,
        audio_enabled: bool | None = None,
        fullscreen: bool = False,
        settings: QSettings | None = None,
    ) -> None:
        super().__init__()
        self.seed = seed
        self.settings = settings if settings is not None else QSettings("quentinmcq", "Bomberman")
        self.textures = Textures()
        self.textures.preload()
        self.audio = AudioManager(self, enabled=audio_enabled)

        self.setWindowTitle("Bomberman")
        self.setWindowIcon(QIcon(str(image_path("icon"))))
        self.setStyleSheet(
            ROOT_QSS + BUTTON_QSS + TITLE_QSS + PANEL_LABEL_QSS + SLIDER_QSS + OVERLAY_QSS
        )

        self.menu_page = MenuPage()
        self.setup_page = SetupPage(self.textures, self.settings)
        self.options_page = OptionsPage(self.audio.volume, self.audio.muted)
        self.game_widget = GameWidget(self.textures)
        self.pause_overlay = PauseOverlay(self.audio.muted)
        self.game_page = GamePage(self.game_widget, self.pause_overlay)

        self.stack = QStackedWidget()
        for page in (self.menu_page, self.setup_page, self.options_page, self.game_page):
            self.stack.addWidget(page)

        root = QWidget()
        root.setObjectName("root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stack)
        self.setCentralWidget(root)

        self._connect_signals()
        self._place_window(fullscreen)
        self.show_menu()

    def _connect_signals(self) -> None:
        self.menu_page.play.connect(self.show_setup)
        self.menu_page.options.connect(lambda: self.stack.setCurrentIndex(PAGE_OPTIONS))
        self.menu_page.quit.connect(self.confirm_quit)

        self.setup_page.start.connect(self.start_game)
        self.setup_page.back.connect(self.show_menu)

        self.options_page.volume_changed.connect(self.audio.set_volume)
        self.options_page.mute_toggled.connect(self._set_muted)
        self.options_page.back.connect(self.show_menu)

        self.game_widget.phase_changed.connect(self.audio.play_music)
        self.game_widget.sound.connect(self.audio.play_sfx)
        self.game_widget.game_over.connect(self._on_game_over)
        self.game_widget.pause_toggled.connect(self._on_pause_toggled)
        self.game_widget.return_to_menu.connect(self.show_menu)

        self.pause_overlay.resume.connect(lambda: self.game_widget.set_paused(False))
        self.pause_overlay.mute_toggled.connect(self._set_muted)
        self.pause_overlay.menu.connect(self._confirm_menu)
        self.pause_overlay.quit.connect(self.confirm_quit)

    def _place_window(self, fullscreen: bool) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            self.resize(1100, 760)
            return
        available = screen.availableGeometry()
        width = int(available.width() * 0.82)
        height = int(available.height() * 0.86)
        self.resize(min(width, 1400), min(height, 980))
        frame = self.frameGeometry()
        frame.moveCenter(available.center())
        self.move(frame.topLeft())
        if fullscreen:
            self.showFullScreen()

    def show_menu(self) -> None:
        self.game_widget.stop()
        self.pause_overlay.hide()
        self.stack.setCurrentIndex(PAGE_MENU)
        self.audio.play_music("menu")
        self.menu_page.play_button.setFocus()

    def show_setup(self) -> None:
        self.stack.setCurrentIndex(PAGE_SETUP)
        self.setup_page.play_button.setFocus()

    def start_game(self, human: int = 0) -> None:
        self.pause_overlay.hide()
        self.stack.setCurrentIndex(PAGE_GAME)
        self.game_widget.start_new_game(self.seed, human=human)

    def _on_game_over(self, winner: Player | None) -> None:
        self.audio.play_music("victory" if winner is not None else "draw")

    def _on_pause_toggled(self, paused: bool) -> None:
        self.pause_overlay.setVisible(paused)
        if paused:
            self.pause_overlay.setGeometry(self.game_page.rect())
            self.pause_overlay.raise_()
            self.pause_overlay.resume_button.setFocus()
        else:
            self.game_widget.setFocus()

    def _set_muted(self, muted: bool) -> None:
        self.audio.set_muted(muted)
        self.options_page.set_muted(muted)
        self.pause_overlay.set_muted(muted)

    def _confirm_menu(self) -> None:
        answer = QMessageBox.question(
            self,
            "Menu",
            "<b>Voulez-vous retourner au menu ?</b> La partie en cours sera perdue.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.show_menu()

    def confirm_quit(self) -> None:
        answer = QMessageBox.question(
            self,
            "Quitter",
            "<b>Voulez-vous quitter le jeu ?</b>",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            QApplication.quit()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
            return
        super().keyPressEvent(event)
