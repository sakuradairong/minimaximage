"""Build the React/Vite frontend for the pywebview desktop app."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"


def main() -> int:
    npm = shutil.which("npm")
    if npm is None:
        print("error: npm was not found. Install Node.js first.", file=sys.stderr)
        return 1
    if not (FRONTEND / "node_modules").exists():
        subprocess.check_call([npm, "install"], cwd=FRONTEND)
    subprocess.check_call([npm, "run", "build"], cwd=FRONTEND)
    print(f"Frontend built: {FRONTEND / 'dist'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
