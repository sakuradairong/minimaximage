"""Build standalone executables for minimaximage.

Run from the project root:

    python scripts/build.py                 # build both CLI and GUI
    python scripts/build.py --gui-only      # only the GUI exe
    python scripts/build.py --cli-only      # only the CLI exe
    python scripts/build.py --no-onefile    # produce a folder instead of one file
    python scripts/build.py --icon path/to/icon.ico

Outputs:
    dist/minimaximage[-gui].exe  (Windows)
    dist/minimaximage[-gui]      (Linux / macOS)
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Sequence

import PyInstaller.__main__


# PyInstaller doesn't always pick up these dynamic imports — list them
# explicitly so the resulting binary is self-contained.
COMMON_HIDDEN_IMPORTS = [
    "PIL._tkinter_finder",
    "httpx",
    "httpx._sync",
    "httpx._exceptions",
    "httpx._transports",
    "httpx._transports.default",
    "httpx._urlparse",
    "dotenv",
    "minimaximage",
    "minimaximage.cli",
    "minimaximage.gui",
    "minimaximage.models",
    "minimaximage.client",
    "minimaximage.config",
    "minimaximage.download",
    "minimaximage.generate",
]

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
SPEC_DIR = ROOT

TARGETS = {
    "minimaximage-gui": {
        "script": "src/minimaximage/gui.py",
        "windowed": True,
    },
    "minimaximage": {
        "script": "src/minimaximage/cli.py",
        "windowed": False,
    },
}


def _run_pyinstaller(args: Sequence[str]) -> None:
    """Invoke PyInstaller's CLI with the given args (without the binary name)."""
    print("→ pyinstaller " + " ".join(args), flush=True)
    PyInstaller.__main__.run(list(args))


def build_target(
    name: str,
    *,
    onefile: bool = True,
    icon: Path | None = None,
    clean: bool = True,
) -> Path:
    """Build a single target. Returns the path of the produced binary."""
    spec = TARGETS[name]
    script = ROOT / spec["script"]
    if not script.exists():
        raise FileNotFoundError(f"Entry script not found: {script}")

    workpath = BUILD / name
    if clean and workpath.exists():
        shutil.rmtree(workpath)

    args: list[str] = [
        str(script),
        f"--name={name}",
        f"--distpath={DIST}",
        f"--workpath={workpath}",
        f"--specpath={SPEC_DIR}",
        "--noconfirm",
        "--noupx",  # avoid UPX — better AV compatibility
    ]
    if clean:
        args.append("--clean")
    if onefile:
        args.append("--onefile")
    else:
        args.append("--onedir")
    if spec["windowed"]:
        args.append("--windowed")
    if icon is not None:
        args.append(f"--icon={icon}")

    for hidden in COMMON_HIDDEN_IMPORTS:
        args.append(f"--hidden-import={hidden}")

    # Include the .env.example next to the binary so users have a template.
    import os

    env_example = ROOT / ".env.example"
    if env_example.exists():
        args.append(f"--add-data={env_example}{os.pathsep}.")

    _run_pyinstaller(args)

    suffix = ".exe" if sys.platform == "win32" else ""
    if onefile:
        return DIST / f"{name}{suffix}"
    return DIST / name / f"{name}{suffix}"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--gui-only", action="store_true", help="Build only the GUI binary")
    p.add_argument("--cli-only", action="store_true", help="Build only the CLI binary")
    p.add_argument(
        "--no-onefile",
        action="store_true",
        help="Build a folder distribution instead of a single file (faster startup).",
    )
    p.add_argument("--icon", type=Path, help="Path to a .ico file (Windows) for the GUI binary")
    p.add_argument("--no-clean", action="store_true", help="Skip removing previous build artefacts")
    args = p.parse_args(argv)

    if args.gui_only and args.cli_only:
        p.error("--gui-only and --cli-only are mutually exclusive")

    DIST.mkdir(exist_ok=True)
    onefile = not args.no_onefile
    clean = not args.no_clean

    built: list[Path] = []
    if not args.cli_only:
        built.append(build_target("minimaximage-gui", onefile=onefile, icon=args.icon, clean=clean))
    if not args.gui_only:
        built.append(build_target("minimaximage", onefile=onefile, clean=clean))

    print()
    print("✓ Build complete. Artefacts:")
    for path in built:
        size = path.stat().st_size if path.exists() else 0
        print(f"  {path}  ({size / (1024 * 1024):.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
