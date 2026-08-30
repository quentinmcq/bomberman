"""Musique et effets sonores.

Le module se désactive proprement si QtMultimedia n'est pas disponible (CI,
machine sans sortie audio) ou si la variable d'environnement
``BOMBERMAN_NO_AUDIO`` vaut 1.
"""

from __future__ import annotations

import logging
import os

from PyQt6.QtCore import QObject, QUrl

from .assets import sound_path

try:
    from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer, QSoundEffect
except ImportError:
    QAudioOutput = QMediaPlayer = QSoundEffect = None

log = logging.getLogger(__name__)

MUSIC_TRACKS = ("menu", "battle", "boss", "victory", "draw")
LOOPING_TRACKS = frozenset({"menu", "battle", "boss"})
SOUND_EFFECTS = ("explosion", "pickup", "bomb", "death")


def audio_disabled_by_env() -> bool:
    return os.environ.get("BOMBERMAN_NO_AUDIO", "").lower() in ("1", "true", "yes")


class AudioManager(QObject):
    """Un lecteur pour la musique, un ``QSoundEffect`` préchargé par effet."""

    def __init__(self, parent: QObject | None = None, enabled: bool | None = None) -> None:
        super().__init__(parent)
        self._volume = 0.5
        self._muted = False
        self.current_track: str | None = None
        self._player: QMediaPlayer | None = None
        self._output: QAudioOutput | None = None
        self._effects: dict[str, QSoundEffect] = {}
        if enabled is None:
            enabled = not audio_disabled_by_env()
        if enabled:
            self._setup()

    @property
    def enabled(self) -> bool:
        return self._player is not None

    def _setup(self) -> None:
        if QMediaPlayer is None:
            log.warning("QtMultimedia indisponible, jeu silencieux")
            return
        try:
            self._output = QAudioOutput(self)
            self._player = QMediaPlayer(self)
            self._player.setAudioOutput(self._output)
            for name in SOUND_EFFECTS:
                path = sound_path(name)
                if not path.exists():
                    log.warning("Effet sonore manquant : %s", path)
                    continue
                effect = QSoundEffect(self)
                effect.setSource(QUrl.fromLocalFile(str(path)))
                self._effects[name] = effect
            self._apply_volume()
        except Exception as exc:
            log.warning("Initialisation audio impossible, jeu silencieux : %s", exc)
            self._player = None
            self._output = None
            self._effects.clear()

    def play_music(self, track: str) -> None:
        """Lance ``track`` (en boucle pour les ambiances) ; sans effet si elle joue déjà."""
        if track not in MUSIC_TRACKS:
            raise ValueError(f"Musique inconnue : {track!r}")
        if track == self.current_track:
            return
        self.current_track = track
        if self._player is None:
            return
        self._player.stop()
        path = sound_path(track)
        if not path.exists():
            log.warning("Musique manquante : %s", path)
            return
        loops = QMediaPlayer.Loops.Infinite if track in LOOPING_TRACKS else QMediaPlayer.Loops.Once
        self._player.setLoops(loops)
        self._player.setSource(QUrl.fromLocalFile(str(path)))
        self._player.play()

    def stop_music(self) -> None:
        self.current_track = None
        if self._player is not None:
            self._player.stop()

    def play_sfx(self, name: str) -> None:
        effect = self._effects.get(name)
        if effect is not None:
            effect.play()

    @property
    def volume(self) -> int:
        """Volume en pourcentage (0-100)."""
        return round(self._volume * 100)

    def set_volume(self, percent: int) -> None:
        self._volume = max(0, min(100, percent)) / 100.0
        self._apply_volume()

    @property
    def muted(self) -> bool:
        return self._muted

    def set_muted(self, muted: bool) -> None:
        self._muted = bool(muted)
        self._apply_volume()

    def _apply_volume(self) -> None:
        if self._output is not None:
            self._output.setVolume(self._volume)
            self._output.setMuted(self._muted)
        for effect in self._effects.values():
            effect.setVolume(self._volume)
            effect.setMuted(self._muted)
