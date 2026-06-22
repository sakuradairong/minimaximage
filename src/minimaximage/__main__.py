"""Entry point for `python -m minimaximage`.

Defaults to the CLI; pass `gui` for the legacy Tk app or `desktop` for the React app.
"""

from __future__ import annotations

import importlib
import sys


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "gui":
        from minimaximage.gui import main as gui_main

        return gui_main()
    if len(sys.argv) > 1 and sys.argv[1] == "desktop":
        desktop_main = importlib.import_module("minimaximage.desktop").main
        return desktop_main(sys.argv[2:])
    from minimaximage.cli import main as cli_main

    return cli_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
