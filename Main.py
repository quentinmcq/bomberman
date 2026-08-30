"""Lanceur de compatibilité : ``python Main.py`` équivaut à ``python -m bomberman``."""

from bomberman.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
