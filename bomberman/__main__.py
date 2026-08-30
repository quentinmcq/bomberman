"""Point d'entrée : ``python -m bomberman`` (ou la commande ``bomberman``)."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bomberman", description="Bomberman-like à 1-4 joueurs (PyQt6)."
    )
    parser.add_argument(
        "--seed", type=int, default=None, help="graine aléatoire (terrain reproductible)"
    )
    parser.add_argument(
        "--no-audio", action="store_true", help="désactive la musique et les effets sonores"
    )
    parser.add_argument(
        "--fullscreen", action="store_true", help="démarre en plein écran (F11 pour basculer)"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="journalisation détaillée")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    from PyQt6.QtCore import QLoggingCategory
    from PyQt6.QtWidgets import QApplication

    from .ui.main_window import MainWindow

    if not args.verbose:
        # Le backend FFmpeg de QtMultimedia décrit chaque fichier ouvert sur stderr.
        QLoggingCategory.setFilterRules("qt.multimedia.ffmpeg*=false")

    app = QApplication(sys.argv[:1])
    app.setApplicationName("Bomberman")
    window = MainWindow(
        seed=args.seed,
        audio_enabled=False if args.no_audio else None,
        fullscreen=args.fullscreen,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
