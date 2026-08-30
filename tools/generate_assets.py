#!/usr/bin/env python3
"""Génère les assets originaux du jeu (pixel-art PNG et sons WAV).

Aucune dépendance externe : les PNG sont encodés à la main (zlib/struct) et les
sons sont synthétisés en pur Python (module ``wave``). Tout ce qui sort de ce
script est une création originale, libre de droits, reproductible à l'identique.

Usage :  python tools/generate_assets.py [--images] [--sounds]
"""

from __future__ import annotations

import argparse
import math
import struct
import sys
import wave
import zlib
from array import array
from collections.abc import Iterable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGES_DIR = ROOT / "bomberman" / "assets" / "images"
SOUNDS_DIR = ROOT / "bomberman" / "assets" / "sounds"

RGBA = tuple[int, int, int, int]
Image = list[list[RGBA]]  # image[y][x]

SPRITE = 16  # taille native d'un sprite (pixels)
SCALE = 4  # facteur d'agrandissement à l'export (16 -> 64 px)

# ---------------------------------------------------------------------------
# Encodage PNG
# ---------------------------------------------------------------------------


def _chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def write_png(path: Path, image: Image) -> None:
    height = len(image)
    width = len(image[0])
    raw = bytearray()
    for row in image:
        raw.append(0)  # filtre "None"
        for r, g, b, a in row:
            raw += bytes((r, g, b, a))
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )
    path.write_bytes(png)


# ---------------------------------------------------------------------------
# Outils image
# ---------------------------------------------------------------------------

TRANSPARENT: RGBA = (0, 0, 0, 0)


def blank(width: int, height: int, color: RGBA = TRANSPARENT) -> Image:
    return [[color for _ in range(width)] for _ in range(height)]


def scale(image: Image, factor: int) -> Image:
    return [[px for px in row for _ in range(factor)] for row in image for _ in range(factor)]


def blit(dest: Image, src: Image, x: int, y: int) -> None:
    for sy, row in enumerate(src):
        for sx, px in enumerate(row):
            if px[3]:
                dest[y + sy][x + sx] = px


def mirror(rows: Sequence[str]) -> list[str]:
    return [row[::-1] for row in rows]


def shade(color: RGBA, factor: float) -> RGBA:
    r, g, b, a = color
    return (
        max(0, min(255, int(r * factor))),
        max(0, min(255, int(g * factor))),
        max(0, min(255, int(b * factor))),
        a,
    )


def from_ascii(rows: Sequence[str], palette: dict[str, RGBA]) -> Image:
    width = len(rows[0])
    for row in rows:
        if len(row) != width:
            raise ValueError(f"Ligne de largeur incohérente : {row!r} ({len(row)} != {width})")
    return [[palette[ch] for ch in row] for row in rows]


class Lcg:
    """Petit générateur pseudo-aléatoire déterministe (textures reproductibles)."""

    def __init__(self, seed: int) -> None:
        self.state = seed & 0xFFFFFFFF

    def next(self) -> float:
        self.state = (1103515245 * self.state + 12345) & 0x7FFFFFFF
        return self.state / 0x7FFFFFFF


# ---------------------------------------------------------------------------
# Palettes
# ---------------------------------------------------------------------------

BASE_PALETTE: dict[str, RGBA] = {
    ".": TRANSPARENT,
    "K": (24, 24, 32, 255),  # contour
    "W": (245, 245, 245, 255),  # blanc
    "G": (122, 126, 142, 255),  # combinaison grise
    "g": (82, 86, 100, 255),  # ombre grise
    "D": (47, 50, 71, 255),  # corps de bombe / visière
    "E": (120, 230, 255, 255),  # yeux lumineux
    "Y": (255, 224, 64, 255),  # étincelle jaune
    "O": (255, 140, 0, 255),  # orange
    "R": (143, 29, 44, 255),  # rouge sombre (bombe perforante)
    "M": (205, 208, 220, 255),  # métal
    "P": (120, 60, 160, 255),  # violet (malus)
    "V": (60, 200, 80, 255),  # vert (signe +)
    "X": (225, 50, 50, 255),  # rouge vif (signe -)
}

TEAM_COLORS: dict[str, RGBA] = {
    "red": (214, 40, 40, 255),
    "blue": (29, 111, 214, 255),
    "yellow": (242, 193, 78, 255),
    "pink": (224, 82, 153, 255),
}


def team_palette(color: RGBA) -> dict[str, RGBA]:
    palette = dict(BASE_PALETTE)
    palette["B"] = color
    palette["b"] = shade(color, 0.65)
    palette["H"] = shade(color, 1.35)
    return palette


# ---------------------------------------------------------------------------
# Sprites des joueurs (16x16, 4 directions x 3 images)
# ---------------------------------------------------------------------------

_FRONT_BODY = [
    "......KKKK......",
    "....KKBBBBKK....",
    "...KBBHHBBBBK...",
    "..KBBHBBBBBBBK..",
    "..KBKKKKKKKKBK..",
    "..KBKDDEDDEDBK..",
    "..KBKDDDDDDDBK..",
    "..KBBKKKKKKBBK..",
    "...KBBBBBBBBK...",
    "....KKGGGGKK....",
    "...KBGGBBGGBK...",
    "..KBBGGBBGGBBK..",
    "..KbKGGGGGGKbK..",
]

_BACK_BODY = [
    "......KKKK......",
    "....KKBBBBKK....",
    "...KBBHHBBBBK...",
    "..KBBHBBBBBBBK..",
    "..KBBBBBBBBBBK..",
    "..KBBBBBBBBBBK..",
    "..KBBBBBBBBBBK..",
    "..KBbBBBBBBbBK..",
    "...KBbbbbbbBK...",
    "....KKGGGGKK....",
    "...KBGGGGGGBK...",
    "..KBBGGGGGGBBK..",
    "..KbKGGGGGGKbK..",
]

_FRONT_LEGS = [
    [
        "...K.KGGGGK.K...",
        ".....KKKKKK.....",
        "....KKK..KKK....",
    ],
    [
        "...K.KGGGGK.K...",
        "....KKKK.KKK....",
        "...KKK....KKK...",
    ],
    [
        "...K.KGGGGK.K...",
        "....KKK.KKKK....",
        "...KKK....KKK...",
    ],
]

_SIDE_BODY = [
    "......KKKK......",
    "....KKBBBBKK....",
    "...KBBHBBBBBK...",
    "..KBBBBBBBBBBK..",
    "..KBBBBBKKKKKK..",
    "..KBBBBBKDDEDK..",
    "..KBBBBBKDDDDK..",
    "..KBBBBBBKKKK...",
    "...KBBBBBBBBK...",
    "....KKGGGGKK....",
    "....KGGGGGBK....",
    "....KGGGGGBK....",
    "....KGGGGGKK....",
]

_SIDE_LEGS = [
    [
        "....KGGGGGK.....",
        ".....KKKKK......",
        "....KKKKKK......",
    ],
    [
        "....KGGGGGK.....",
        "...KKKK.KKK.....",
        "..KKK....KKK....",
    ],
    [
        "....KGGGGGK.....",
        ".....KKKKKK.....",
        "......KKK.KK....",
    ],
]


def player_frames() -> dict[str, list[list[str]]]:
    """Retourne, par direction, les 3 images ASCII du personnage."""
    down = [_FRONT_BODY + legs for legs in _FRONT_LEGS]
    up = [_BACK_BODY + legs for legs in _FRONT_LEGS]
    right = [_SIDE_BODY + legs for legs in _SIDE_LEGS]
    left = [mirror(frame) for frame in right]
    return {"up": up, "down": down, "left": left, "right": right}


def build_player_sheet(color: RGBA) -> Image:
    """Feuille de sprites : 4 lignes (haut, bas, gauche, droite) x 3 colonnes."""
    palette = team_palette(color)
    frames = player_frames()
    sheet = blank(SPRITE * 3, SPRITE * 4)
    for row_index, direction in enumerate(("up", "down", "left", "right")):
        for col_index, frame in enumerate(frames[direction]):
            blit(sheet, from_ascii(frame, palette), col_index * SPRITE, row_index * SPRITE)
    return sheet


# ---------------------------------------------------------------------------
# Bombes
# ---------------------------------------------------------------------------

BOMB = [
    "..........YO....",
    ".........OY.....",
    "........KK......",
    ".......KK.......",
    ".....KKKKKK.....",
    "....KDDDDDDK....",
    "...KDWDDDDDDK...",
    "..KDWWDDDDDDDK..",
    "..KDWDDDDDDDDK..",
    "..KDDDDDDDDDDK..",
    "..KDDDDDDDDDDK..",
    "..KDDDDDDDDDDK..",
    "...KDDDDDDDDK...",
    "....KDDDDDDK....",
    ".....KKKKKK.....",
    "................",
]

BOMB_PIERCE = [
    "..........YO....",
    ".........OY.....",
    "........KK......",
    ".......KK.......",
    ".M...KKKKKK...M.",
    "..M.KRRRRRRK.M..",
    "...KRWRRRRRRK...",
    "..KRWWRRRRRRRK..",
    "..KRWRRRRRRRRK..",
    "..KRRRRRRRRRRK..",
    "..KRRRRRRRRRRK..",
    "..KRRRRRRRRRRK..",
    "...KRRRRRRRRK...",
    "..M.KRRRRRRK.M..",
    ".M...KKKKKK...M.",
    "................",
]

# ---------------------------------------------------------------------------
# Tuiles de terrain (générées algorithmiquement)
# ---------------------------------------------------------------------------


def floor_tile() -> Image:
    base: RGBA = (92, 160, 72, 255)
    dark: RGBA = (74, 136, 58, 255)
    light: RGBA = (112, 182, 88, 255)
    rng = Lcg(2019)
    img = blank(SPRITE, SPRITE, base)
    for y in range(SPRITE):
        for x in range(SPRITE):
            roll = rng.next()
            if roll < 0.10:
                img[y][x] = dark
            elif roll > 0.93:
                img[y][x] = light
    return img


def stone_tile() -> Image:
    fill: RGBA = (128, 132, 146, 255)
    light: RGBA = (178, 182, 194, 255)
    dark: RGBA = (72, 74, 88, 255)
    outline: RGBA = (48, 50, 62, 255)
    rng = Lcg(42)
    img = blank(SPRITE, SPRITE, fill)
    for y in range(SPRITE):
        for x in range(SPRITE):
            if x == 0 or y == 0 or x == SPRITE - 1 or y == SPRITE - 1:
                img[y][x] = outline
            elif x <= 2 or y <= 2:
                img[y][x] = light
            elif x >= SPRITE - 3 or y >= SPRITE - 3:
                img[y][x] = dark
            elif rng.next() < 0.12:
                img[y][x] = shade(fill, 0.9)
    return img


def brick_tile() -> Image:
    mortar: RGBA = (214, 186, 150, 255)
    brick: RGBA = (196, 86, 46, 255)
    brick_shade: RGBA = (160, 64, 36, 255)
    img = blank(SPRITE, SPRITE, mortar)
    course_height = 4  # 3 px de brique + 1 px de mortier
    brick_width = 8  # 7 px de brique + 1 px de mortier
    for y in range(SPRITE):
        if y % course_height == course_height - 1:
            continue  # ligne de mortier
        offset = 0 if (y // course_height) % 2 == 0 else brick_width // 2
        for x in range(SPRITE):
            if (x + offset) % brick_width == brick_width - 1:
                continue  # joint vertical
            bottom = y % course_height == course_height - 2
            right = (x + offset) % brick_width == brick_width - 2
            img[y][x] = brick_shade if (bottom or right) else brick
    return img


# ---------------------------------------------------------------------------
# Flammes
# ---------------------------------------------------------------------------

FLAME_BANDS: Sequence[tuple[float, RGBA]] = (
    (2.2, (255, 250, 205, 255)),
    (4.2, (255, 220, 60, 255)),
    (6.2, (255, 140, 30, 255)),
    (7.6, (220, 60, 30, 255)),
)


def _flame_color(distance: float) -> RGBA:
    for limit, color in FLAME_BANDS:
        if distance < limit:
            return color
    return TRANSPARENT


def flame_center() -> Image:
    img = blank(SPRITE, SPRITE)
    for y in range(SPRITE):
        for x in range(SPRITE):
            d = math.hypot(x - 7.5, y - 7.5)
            img[y][x] = _flame_color(d)
    return img


def flame_horizontal() -> Image:
    img = blank(SPRITE, SPRITE)
    for y in range(SPRITE):
        color = _flame_color(abs(y - 7.5))
        for x in range(SPRITE):
            img[y][x] = color
    return img


def flame_vertical() -> Image:
    horizontal = flame_horizontal()
    return [[horizontal[x][y] for x in range(SPRITE)] for y in range(SPRITE)]


# ---------------------------------------------------------------------------
# Power-ups
# ---------------------------------------------------------------------------

GLYPH_FIRE = [
    "....Y.....",
    "...YO.....",
    "...OO.Y...",
    "..OOOYO...",
    "..OYYOO...",
    ".OYYYYOO..",
    ".OYWWYYO..",
    ".OYWWYYO..",
    "..OYYYO...",
    "...OOO....",
]

GLYPH_BOMB = [
    "......YO..",
    ".....KK...",
    "...KKKK...",
    "..KDDDDK..",
    ".KDWDDDDK.",
    ".KDDDDDDK.",
    ".KDDDDDDK.",
    "..KDDDDK..",
    "...KKKK...",
    "..........",
]

GLYPH_PIERCE = [
    "......YO..",
    ".....KK...",
    "M..KKKK..M",
    ".MKRRRRKM.",
    ".KRWRRRRK.",
    ".KRRRRRRK.",
    ".KRRRRRRK.",
    ".MKRRRRKM.",
    "M..KKKK..M",
    "..........",
]

GLYPH_SKULL = [
    "...WWWW...",
    "..WWWWWW..",
    ".WWWWWWWW.",
    ".WKKWWKKW.",
    ".WKKWWKKW.",
    ".WWWWWWWW.",
    "..WWKKWW..",
    "...WWWW...",
    "...WKWK...",
    "...WWWW...",
]

SIGN_PLUS = [
    ".V.",
    "VVV",
    ".V.",
]

SIGN_MINUS = [
    "...",
    "XXX",
    "...",
]


def powerup_tile(glyph: Sequence[str], sign: Sequence[str] | None, fill: RGBA) -> Image:
    outline = BASE_PALETTE["K"]
    inner_shadow = shade(fill, 0.8)
    img = blank(SPRITE, SPRITE)
    for y in range(1, SPRITE - 1):
        for x in range(1, SPRITE - 1):
            corner = (x in (1, SPRITE - 2)) and (y in (1, SPRITE - 2))
            if corner:
                continue
            edge = x in (1, SPRITE - 2) or y in (1, SPRITE - 2)
            if edge:
                img[y][x] = outline
            elif x == SPRITE - 3 or y == SPRITE - 3:
                img[y][x] = inner_shadow
            else:
                img[y][x] = fill
    blit(img, from_ascii(glyph, BASE_PALETTE), 3, 3)
    if sign is not None:
        blit(img, from_ascii(sign, BASE_PALETTE), 10, 10)
    return img


PANEL_BONUS: RGBA = (226, 232, 244, 255)
PANEL_MALUS: RGBA = (244, 214, 214, 255)
PANEL_SKULL: RGBA = (120, 60, 160, 255)


def powerup_tiles() -> dict[str, Image]:
    return {
        "powerup_fire_up": powerup_tile(GLYPH_FIRE, SIGN_PLUS, PANEL_BONUS),
        "powerup_fire_down": powerup_tile(GLYPH_FIRE, SIGN_MINUS, PANEL_MALUS),
        "powerup_bomb_up": powerup_tile(GLYPH_BOMB, SIGN_PLUS, PANEL_BONUS),
        "powerup_bomb_down": powerup_tile(GLYPH_BOMB, SIGN_MINUS, PANEL_MALUS),
        "powerup_pierce": powerup_tile(GLYPH_PIERCE, None, PANEL_BONUS),
        "powerup_skull": powerup_tile(GLYPH_SKULL, None, PANEL_SKULL),
    }


# ---------------------------------------------------------------------------
# Génération des images
# ---------------------------------------------------------------------------


def generate_images(out_dir: Path = IMAGES_DIR) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    tiles: dict[str, Image] = {
        "floor": floor_tile(),
        "stone": stone_tile(),
        "brick": brick_tile(),
        "bomb": from_ascii(BOMB, BASE_PALETTE),
        "bomb_pierce": from_ascii(BOMB_PIERCE, BASE_PALETTE),
        "flame_center": flame_center(),
        "flame_h": flame_horizontal(),
        "flame_v": flame_vertical(),
    }
    tiles.update(powerup_tiles())
    for name, color in TEAM_COLORS.items():
        tiles[f"player_{name}"] = build_player_sheet(color)
    tiles["icon"] = from_ascii(BOMB, BASE_PALETTE)

    written: list[Path] = []
    for name, image in tiles.items():
        path = out_dir / f"{name}.png"
        write_png(path, scale(image, SCALE))
        written.append(path)
    return written


# ---------------------------------------------------------------------------
# Synthèse sonore (chiptune)
# ---------------------------------------------------------------------------

SAMPLE_RATE = 22050

NOTE_INDEX = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def note_to_freq(name: str) -> float:
    """Convertit un nom de note ("A4" -> 440.0) ; accepte dièses ("F#3") et bémols ("Bb4")."""
    letter = name[0].upper()
    rest = name[1:]
    semitone = NOTE_INDEX[letter]
    if rest.startswith("#"):
        semitone += 1
        rest = rest[1:]
    elif rest.startswith("b"):
        semitone -= 1
        rest = rest[1:]
    octave = int(rest)
    midi = 12 * (octave + 1) + semitone
    return 440.0 * 2 ** ((midi - 69) / 12)


class Event:
    __slots__ = ("duration", "freq", "start", "volume", "wave")

    def __init__(self, start: float, duration: float, freq: float, wave: str, volume: float):
        self.start = start
        self.duration = duration
        self.freq = freq
        self.wave = wave
        self.volume = volume


def render(events: Iterable[Event], length: float, peak: float = 0.85) -> array:
    """Mixe les événements en un buffer mono normalisé."""
    total = int(length * SAMPLE_RATE)
    mix = [0.0] * total
    rng = Lcg(7)
    sr = SAMPLE_RATE
    attack = max(1, int(0.004 * sr))
    release = max(1, int(0.03 * sr))
    for ev in events:
        start = int(ev.start * sr)
        count = int(ev.duration * sr)
        if count <= 0:
            continue
        wave = ev.wave
        freq = ev.freq
        vol = ev.volume
        for i in range(count):
            idx = start + i
            if idx >= total:
                break
            t = i / sr
            if wave == "square":
                sample = 1.0 if (t * freq) % 1.0 < 0.5 else -1.0
            elif wave == "pulse":
                sample = 1.0 if (t * freq) % 1.0 < 0.25 else -1.0
            elif wave == "tri":
                phase = (t * freq) % 1.0
                sample = 4.0 * abs(phase - 0.5) - 1.0
            elif wave == "saw":
                sample = 2.0 * ((t * freq) % 1.0) - 1.0
            elif wave == "sine":
                sample = math.sin(2 * math.pi * freq * t)
            elif wave == "noise":
                sample = (rng.next() * 2.0 - 1.0) * math.exp(-6.0 * i / count)
            elif wave == "kick":
                sweep = freq * math.exp(-8.0 * t) + 45.0
                sample = math.sin(2 * math.pi * sweep * t) * math.exp(-7.0 * i / count)
            else:
                raise ValueError(f"Onde inconnue : {wave}")
            env = 1.0
            if i < attack:
                env = i / attack
            remaining = count - i
            if remaining < release:
                env *= remaining / release
            mix[idx] += sample * vol * env
    top = max(1e-9, max(abs(v) for v in mix))
    gain = peak / top if top > peak else 1.0
    out = array("h", (int(max(-1.0, min(1.0, v * gain)) * 32767) for v in mix))
    return out


def write_wav(path: Path, samples: array) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(samples.tobytes())


class Sequencer:
    """Transforme des motifs texte en événements. Un token = une double-croche.

    Tokens : "C5" note, "-" prolonge la note précédente, "." silence.
    """

    def __init__(self, bpm: float) -> None:
        self.step = 60.0 / bpm / 4.0
        self.events: list[Event] = []
        self.length = 0.0

    def track(self, pattern: str, wave: str, volume: float, repeat: int = 1) -> None:
        """Ajoute une voix mélodique ; ``repeat`` enchaîne le motif plusieurs fois."""
        current: Event | None = None
        time = 0.0
        for token in pattern.split() * repeat:
            if token == "-":
                if current is not None:
                    current.duration += self.step
            elif token == ".":
                current = None
            else:
                current = Event(time, self.step * 0.92, note_to_freq(token), wave, volume)
                self.events.append(current)
            time += self.step
        self.length = max(self.length, time)

    def drums(self, pattern: str, volume: float, repeat: int = 1) -> None:
        """'k' kick, 'h' charley (bruit court), 's' snare (bruit long), '.' rien."""
        time = 0.0
        for token in pattern.split() * repeat:
            if token == "k":
                self.events.append(Event(time, self.step * 1.6, 160.0, "kick", volume))
            elif token == "h":
                self.events.append(Event(time, self.step * 0.35, 0.0, "noise", volume * 0.45))
            elif token == "s":
                self.events.append(Event(time, self.step * 1.2, 0.0, "noise", volume * 0.8))
            time += self.step
        self.length = max(self.length, time)


def music_menu() -> array:
    seq = Sequencer(bpm=126)
    lead = (
        "E5 - G5 - A5 - G5 - E5 - D5 - C5 - - - . . "
        "D5 - E5 - G5 - E5 - D5 - C5 - A4 - - - . . "
        "E5 - G5 - A5 - G5 - E5 - D5 - C5 - - - . . "
        "C5 - D5 - E5 - D5 - C5 - A4 - G4 - - - - - "
    )
    bass = (
        "C3 - - - C3 - - - G2 - - - G2 - - - "
        "A2 - - - A2 - - - F2 - - - F2 - - - "
        "C3 - - - C3 - - - G2 - - - G2 - - - "
        "F2 - - - G2 - - - C3 - - - C3 - - - "
    )
    drums = "k . h . s . h . k . h . s . h h " * 4
    seq.track(lead, "square", 0.32)
    seq.track(bass, "tri", 0.40)
    seq.drums(drums, 0.5)
    return render(seq.events, seq.length)


def music_battle() -> array:
    seq = Sequencer(bpm=156)
    riff = (
        "A4 A4 . A4 C5 . A4 . G4 A4 . C5 . D5 . . "
        "A4 A4 . A4 C5 . A4 . E5 . D5 . C5 . B4 . "
        "A4 A4 . A4 C5 . A4 . G4 A4 . C5 . D5 . . "
        "F5 . E5 . D5 . C5 . B4 . A4 . - - . . "
    )
    harmony = (
        "E4 - - - . . . . E4 - - - . . . . "
        "E4 - - - . . . . G4 - - - F4 - - - "
        "E4 - - - . . . . E4 - - - . . . . "
        "A4 - - - G4 - - - F4 - - - E4 - - - "
    )
    bass = (
        "A2 . A2 . A2 . A2 . G2 . G2 . G2 . G2 . "
        "A2 . A2 . A2 . A2 . E2 . E2 . E2 . E2 . "
        "A2 . A2 . A2 . A2 . G2 . G2 . G2 . G2 . "
        "F2 . F2 . G2 . G2 . A2 . A2 . A2 . A2 . "
    )
    drums = "k . h h s . h . k . h h s . h h " * 4
    seq.track(riff, "square", 0.30, repeat=2)
    seq.track(harmony, "pulse", 0.16, repeat=2)
    seq.track(bass, "saw", 0.28, repeat=2)
    seq.drums(drums, 0.55, repeat=2)
    return render(seq.events, seq.length)


def music_boss() -> array:
    seq = Sequencer(bpm=172)
    lead = (
        "D5 . D5 . F5 . D5 . G#4 . - . A4 . - . "
        "D5 . D5 . F5 . D5 . C5 . Bb4 . A4 . G4 . "
        "D5 . D5 . F5 . D5 . G#4 . - . A4 . - . "
        "Bb4 . A4 . G4 . F4 . E4 . D4 . - - - - "
    )
    counter = (
        "A3 - - - Bb3 - - - A3 - - - G#3 - - - "
        "A3 - - - Bb3 - - - A3 - - - G3 - - - "
        "A3 - - - Bb3 - - - A3 - - - G#3 - - - "
        "F3 - - - E3 - - - D3 - - - - - - - "
    )
    bass = "D2 D2 . D2 . D2 D2 . D2 D2 . D2 . D2 D2 . " * 4
    drums = "k . h . k . h . k . h . s s h h " * 4
    seq.track(lead, "square", 0.30, repeat=2)
    seq.track(counter, "pulse", 0.18, repeat=2)
    seq.track(bass, "saw", 0.30, repeat=2)
    seq.drums(drums, 0.6, repeat=2)
    return render(seq.events, seq.length)


def music_victory() -> array:
    seq = Sequencer(bpm=140)
    lead = "C5 . C5 . C5 . C5 - - E5 - - G5 - - - C6 - - - - - - - "
    harmony = "E4 . E4 . E4 . E4 - - G4 - - C5 - - - E5 - - - - - - - "
    bass = "C3 - - - C3 - - - G2 - - - C3 - - - C3 - - - - - - - "
    seq.track(lead, "square", 0.32)
    seq.track(harmony, "pulse", 0.20)
    seq.track(bass, "tri", 0.38)
    seq.drums("k . . . k . . . k . . . k . . . s . . . . . . . ", 0.5)
    return render(seq.events, seq.length + 0.4)


def music_draw() -> array:
    seq = Sequencer(bpm=96)
    lead = "E5 - - - D5 - - - C5 - - - B4 - - - Bb4 - - - - - - - "
    bass = "A2 - - - - - - - F2 - - - - - - - E2 - - - - - - - "
    seq.track(lead, "tri", 0.34)
    seq.track(bass, "square", 0.22)
    return render(seq.events, seq.length + 0.4)


def sfx_explosion() -> array:
    events = [
        Event(0.0, 0.7, 0.0, "noise", 0.9),
        Event(0.0, 0.5, 190.0, "kick", 0.9),
        Event(0.02, 0.25, 55.0, "saw", 0.35),
    ]
    return render(events, 0.75, peak=0.95)


def sfx_pickup() -> array:
    events = [
        Event(0.0, 0.07, note_to_freq("E5"), "square", 0.4),
        Event(0.07, 0.07, note_to_freq("G5"), "square", 0.4),
        Event(0.14, 0.12, note_to_freq("C6"), "square", 0.4),
    ]
    return render(events, 0.3)


def sfx_bomb() -> array:
    events = [
        Event(0.0, 0.05, 900.0, "tri", 0.5),
        Event(0.03, 0.08, 300.0, "square", 0.3),
    ]
    return render(events, 0.14)


def sfx_death() -> array:
    events = [
        Event(0.00, 0.10, note_to_freq("G4"), "square", 0.35),
        Event(0.10, 0.10, note_to_freq("E4"), "square", 0.35),
        Event(0.20, 0.25, note_to_freq("C4"), "square", 0.35),
    ]
    return render(events, 0.5)


def generate_sounds(out_dir: Path = SOUNDS_DIR, names: Sequence[str] | None = None) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    tracks = {
        "menu": music_menu,
        "battle": music_battle,
        "boss": music_boss,
        "victory": music_victory,
        "draw": music_draw,
        "explosion": sfx_explosion,
        "pickup": sfx_pickup,
        "bomb": sfx_bomb,
        "death": sfx_death,
    }
    written: list[Path] = []
    for name, builder in tracks.items():
        if names is not None and name not in names:
            continue
        path = out_dir / f"{name}.wav"
        write_wav(path, builder())
        written.append(path)
    return written


# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", action="store_true", help="ne générer que les images")
    parser.add_argument("--sounds", action="store_true", help="ne générer que les sons")
    args = parser.parse_args(argv)
    do_images = args.images or not args.sounds
    do_sounds = args.sounds or not args.images
    if do_images:
        for path in generate_images():
            print(f"image  {path.relative_to(ROOT)}")
    if do_sounds:
        for path in generate_sounds():
            print(f"son    {path.relative_to(ROOT)}  ({path.stat().st_size / 1024:.0f} Kio)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
