"""Entry point for `python -m minimaximage`.

Defaults to the CLI; pass `gui` to launch the desktop app.
"""

from __future__ import annotations

import sys


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "gui":
        from minimaximage.gui import main as gui_main

        return gui_main()
    from minimaximage.cli import main as cli_main

    return cli_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
