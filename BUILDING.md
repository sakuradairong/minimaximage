# Building standalone executables

This project ships as a Python package. To distribute it to users who don't
have Python installed, build a single-file executable with PyInstaller.

## Quick start (Windows)

```powershell
py -3 -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
python scripts\build.py
```

The result is two files in `dist\`:

- `dist\minimaximage.exe` — command-line interface
- `dist\minimaximage-gui.exe` — desktop GUI (no console window)

Copy the `.exe`(s) to any folder. Users run them from that folder (or add it
to `PATH`). They do **not** need Python installed.

## Output sizes

Both binaries are around 40 MB. PyInstaller embeds the Python runtime and
every dependency (Pillow, httpx, dotenv, tkinter, the `minimaximage` package).
Most of that footprint is the Python runtime + Pillow image codecs.

## Distribution checklist

1. Copy `dist\minimaximage-gui.exe` (and optionally `dist\minimaximage.exe`)
   to the target machine.
2. Drop a `.env` file next to the exe(s) with at minimum:
   ```
   MINIMAX_API_KEY=eyJhbGciOi...
   ```
3. The GUI/CLI looks for `.env` in the **current working directory** (CWD).
   - When the user **double-clicks** the GUI exe, CWD is usually the exe's
     folder, so a sibling `.env` works.
   - When the user runs the CLI from a terminal, the CWD is wherever they
     are — point them to `cd` into the exe's folder or use absolute paths.

## Build options

```
python scripts\build.py --help
```

Common flags:

| Flag | Effect |
| --- | --- |
| `--gui-only` | Build only the GUI binary |
| `--cli-only` | Build only the CLI binary |
| `--no-onefile` | Produce a folder instead of a single exe (faster startup, easier to debug) |
| `--icon path\to\icon.ico` | Embed a Windows icon in the GUI binary |
| `--no-clean` | Skip removing previous `build/` artefacts (faster re-builds) |

## Cross-platform note

PyInstaller produces a binary for the platform it runs on:

- Build on **Windows** → Windows `.exe`
- Build on **macOS** → macOS app
- Build on **Linux** → Linux ELF

You cannot cross-compile. To produce a Windows exe, run the build on a
Windows machine (or a Windows VM).

## CI: building on every release

A minimal GitHub Actions workflow that builds and attaches the binaries:

```yaml
# .github/workflows/build.yml
name: build
on:
  push:
    tags: ["v*"]
jobs:
  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev]"
      - run: python scripts\build.py
      - uses: actions/upload-artifact@v4
        with:
          name: minimaximage-windows
          path: dist\*.exe
```

## Troubleshooting

### "Failed to execute script" on first run

The PyInstaller bootloader extracts your app to a temp folder at startup. On
Windows this can trip aggressive antivirus software. If Windows Defender
quarantines the exe:

1. Right-click the exe → Properties → check "Unblock".
2. Add the folder to your AV exclusion list.
3. If it still fails, build with `--no-onefile` (the folder form is harder
   for AV to false-positive because the bootloader isn't carrying a
   compressed archive).

### ModuleNotFoundError at runtime

If a runtime `ModuleNotFoundError` mentions a module not in
`COMMON_HIDDEN_IMPORTS` in `scripts/build.py`, add it there and rebuild.

### The GUI shows a console window

That means it was built with the wrong target. `minimaximage-gui` must use
`--windowed`. The build script does this automatically; if you hand-roll
PyInstaller commands, double-check.

### Slow first launch

One-file mode extracts the archive to `%TEMP%` on every run. Use
`--no-onefile` for faster startups (you'll distribute a folder instead of
a single exe).
