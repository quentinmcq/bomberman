"""Pages de menu (accueil, options) et surcouche de pause."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

CONTROLS_HELP = (
    "<b>Joueur Rouge</b> : Z Q S D (ou W A S D) + Espace &nbsp;·&nbsp; "
    "<b>Bleu</b> : O K L M + Maj<br>"
    "<b>Jaune</b> : flèches + Ctrl ou 0 &nbsp;·&nbsp; "
    "<b>Rose</b> : pavé 8 4 5 6 + « + »<br>"
    "Les joueurs Bleu, Jaune et Rose sont pilotés par l'IA jusqu'à ce qu'un humain "
    "appuie sur l'une de leurs touches. &nbsp;Échap : pause &nbsp;·&nbsp; F11 : plein écran"
)


def _button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


class MuteButton(QPushButton):
    """Bouton à bascule « Son : activé / coupé » ; son signal ``toggled`` porte l'état."""

    def __init__(self, muted: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggled.connect(self._refresh_text)
        self.setChecked(muted)
        self._refresh_text(muted)

    def set_muted(self, muted: bool) -> None:
        """Aligne le bouton sur un état venu d'ailleurs (autre page)."""
        if self.isChecked() != muted:
            self.setChecked(muted)

    def _refresh_text(self, muted: bool) -> None:
        self.setText("Son : coupé" if muted else "Son : activé")


class MenuPage(QWidget):
    play = pyqtSignal()
    options = pyqtSignal()
    quit = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(6)

        title = QLabel("BOMBERMAN")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel("1 à 4 joueurs — projet PyQt")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.play_button = _button("Jouer")
        self.options_button = _button("Options")
        self.quit_button = _button("Quitter")
        self.play_button.clicked.connect(self.play)
        self.options_button.clicked.connect(self.options)
        self.quit_button.clicked.connect(self.quit)

        hint = QLabel(CONTROLS_HELP)
        hint.setObjectName("hint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setTextFormat(Qt.TextFormat.RichText)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(24)
        for button in (self.play_button, self.options_button, self.quit_button):
            layout.addWidget(button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(24)
        layout.addWidget(hint, 0, Qt.AlignmentFlag.AlignHCenter)


class OptionsPage(QWidget):
    volume_changed = pyqtSignal(int)
    mute_toggled = pyqtSignal(bool)
    back = pyqtSignal()

    def __init__(self, volume: int, muted: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label = QLabel("Volume")
        label.setObjectName("panel")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(volume)
        self.slider.setFixedWidth(320)
        self.slider.valueChanged.connect(self.volume_changed)

        self.mute_button = MuteButton(muted)
        self.mute_button.toggled.connect(self.mute_toggled)

        self.back_button = _button("Retour")
        self.back_button.clicked.connect(self.back)

        for widget in (label, self.slider, self.mute_button, self.back_button):
            layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignHCenter)

    def set_muted(self, muted: bool) -> None:
        self.mute_button.set_muted(muted)


class PauseOverlay(QWidget):
    resume = pyqtSignal()
    menu = pyqtSignal()
    quit = pyqtSignal()
    mute_toggled = pyqtSignal(bool)

    def __init__(self, muted: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("overlay")
        self.setAutoFillBackground(True)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("PAUSE")
        title.setObjectName("overlayTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.resume_button = _button("Continuer")
        self.mute_button = MuteButton(muted)
        self.menu_button = _button("Menu principal")
        self.quit_button = _button("Quitter")

        self.resume_button.clicked.connect(self.resume)
        self.mute_button.toggled.connect(self.mute_toggled)
        self.menu_button.clicked.connect(self.menu)
        self.quit_button.clicked.connect(self.quit)

        layout.addWidget(title)
        layout.addSpacing(16)
        for button in (self.resume_button, self.mute_button, self.menu_button, self.quit_button):
            layout.addWidget(button, 0, Qt.AlignmentFlag.AlignHCenter)

    def set_muted(self, muted: bool) -> None:
        self.mute_button.set_muted(muted)
