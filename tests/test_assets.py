"""Tests du générateur d'assets et de la présence des ressources livrées."""

from __future__ import annotations

import struct
import wave

import pytest

from bomberman.assets import (
    FLAME_TEXTURES,
    PLAYER_SHEETS,
    POWERUP_TEXTURES,
    image_path,
    sound_path,
)
from bomberman.audio import MUSIC_TRACKS, SOUND_EFFECTS
from tools import generate_assets as gen


def png_size(data: bytes) -> tuple[int, int]:
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def test_pixel_maps_are_consistent():
    for frames in gen.player_frames().values():
        assert len(frames) == 3
        for frame in frames:
            assert len(frame) == gen.SPRITE
            assert all(len(row) == gen.SPRITE for row in frame)
    for sprite in (gen.BOMB, gen.BOMB_PIERCE):
        assert len(sprite) == gen.SPRITE and all(len(row) == gen.SPRITE for row in sprite)
    for glyph in (gen.GLYPH_FIRE, gen.GLYPH_BOMB, gen.GLYPH_PIERCE, gen.GLYPH_SKULL):
        assert all(len(row) == 10 for row in glyph)


def test_generate_images_into_directory(tmp_path):
    paths = gen.generate_images(tmp_path)
    names = {path.stem for path in paths}
    assert {"floor", "brick", "stone", "bomb", "bomb_pierce", "icon"} <= names
    assert set(FLAME_TEXTURES.values()) <= names
    assert set(POWERUP_TEXTURES.values()) <= names
    assert set(PLAYER_SHEETS) <= names
    assert png_size((tmp_path / "bomb.png").read_bytes()) == (64, 64)
    assert png_size((tmp_path / "player_red.png").read_bytes()) == (192, 256)


def test_generate_short_sounds_into_directory(tmp_path):
    paths = gen.generate_sounds(tmp_path, names=("bomb", "pickup"))
    assert {path.name for path in paths} == {"bomb.wav", "pickup.wav"}
    with wave.open(str(tmp_path / "pickup.wav")) as wav:
        assert wav.getframerate() == gen.SAMPLE_RATE
        assert wav.getnchannels() == 1
        assert wav.getnframes() > 1000


def test_note_to_freq():
    assert gen.note_to_freq("A4") == pytest.approx(440.0)
    assert gen.note_to_freq("C5") == pytest.approx(523.25, abs=0.01)
    assert gen.note_to_freq("F#3") == pytest.approx(185.0, abs=0.01)
    assert gen.note_to_freq("Bb4") == pytest.approx(gen.note_to_freq("A#4"))


def test_shipped_assets_are_present():
    for name in (
        "floor",
        "brick",
        "stone",
        "bomb",
        "bomb_pierce",
        "icon",
        *FLAME_TEXTURES.values(),
        *POWERUP_TEXTURES.values(),
        *PLAYER_SHEETS,
    ):
        assert image_path(name).is_file(), name
    for name in (*MUSIC_TRACKS, *SOUND_EFFECTS):
        assert sound_path(name).is_file(), name
