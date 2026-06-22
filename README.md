# minimaximage

Generate images with the **Minimax `image_generation` API** (`image-01` /
`image-01-live`). Ships as a Python SDK, a terminal CLI, **and a cross-platform
desktop GUIs** — pick whichever fits your workflow.

API reference: <https://platform.minimaxi.com/docs/api-reference/image-generation-t2i>

## Features

- **T2I** (text-to-image) with prompt, aspect ratio, and custom width/height
- **I2I** (image-to-image) with one or more subject-reference URLs
- Choose between `url` (24 h expiry) and `base64` responses
- Reproducible runs via `seed`
- `prompt_optimizer` and AIGC watermark toggles
- 🖥️ **Modern desktop UI** powered by FastAPI + React/Vite + pywebview,
  inspired by the MiniMax image debug console
- 🧰 **Legacy Tk desktop GUI** with live preview, multi-image navigation, and
  "Open in viewer" — works on Windows, macOS, and Linux

## Install (Windows)

```powershell
py -3 -m venv .venv
.venv\Scripts\activate
pip install -e .
copy .env.example .env
# edit .env and set MINIMAX_API_KEY
```

`tkinter` is bundled with the standard Python installer on Windows — no extra
step needed. Pillow (used for the preview) is pulled in automatically.

## Where the API key comes from

The API key is resolved in this order (first match wins):

1. **Typed in the GUI's API key field** — overrides everything for that run.
   Click **Save** next to the field to persist it to the user config file.
2. **User config file** — `%APPDATA%\minimaximage\config.json` (Windows),
   `~/.config/minimaximage/config.json` (Linux / macOS). Created by the
   GUI's **Save** button or by running:

   ```python
   from minimaximage import save_config
   save_config({"api_key": "eyJhbGciOi..."})
   ```

3. **`MINIMAX_API_KEY` environment variable** (or `.env` file via
   python-dotenv).
4. **`--api-key KEY`** CLI flag overrides all of the above for that single
   invocation (not persisted).

This means you can launch the GUI without any environment setup, paste the
key into the field, click **Save**, and never set an env var again.

## Modern Web Desktop GUI

The recommended desktop UI is a local FastAPI backend plus a React/Vite
frontend hosted inside a pywebview window. It mirrors the MiniMax image debug
console layout: prompt templates, prompt editor, reference image URLs, basic
settings, advanced settings, generation results, history, and curl preview.

Development mode:

```powershell
# terminal 1: backend
uvicorn minimaximage.server:app --host 127.0.0.1 --port 8765

# terminal 2: frontend
cd frontend
npm install
npm run dev
```

Desktop mode:

```powershell
minimaximage-desktop
# or
python -m minimaximage desktop
```

Production frontend build:

```powershell
python scripts\build_frontend.py
```

## Legacy Tk GUI

Launch the legacy Tk desktop app with any of:

```powershell
minimaximage-gui
# or
python -m minimaximage gui
```

```text
┌──────────────────────────────────────────────────────────┐
│ minimaximage — image generator                           │
├──────────────────────────────────────────────────────────┤
│ API key: [••••••••••••••••••••••••••] [Save] [☐ Show]     │
│                                                          │
│ Model: [image-01 ▼]   Aspect: [1:1 ▼]   n: [1]  Seed: [ ]│
│ Format: [url ▼]   ☐ Prompt optimizer   ☐ AIGC watermark   │
│                                                          │
│ Prompt (≤1500 characters)                                │
│ ┌──────────────────────────────────────────────────────┐ │
│ │ A fluffy cat wearing a top hat, studio portrait...   │ │
│ └──────────────────────────────────────────────────────┘ │
│                                                          │
│ Reference image URLs (one per line, for I2I)             │
│ ┌──────────────────────────────────────────────────────┐ │
│ └──────────────────────────────────────────────────────┘ │
│                                                          │
│ Output folder: [./output    ] [Browse…]  [ Generate ]    │
│                                                          │
│ ◀ Prev   Next ▶   1/4     /output/task-id.png  [Open] [Copy path] │
│ ┌──────────────────────────────────────────────────────┐ │
│ │                                                      │ │
│ │                (image preview)                       │ │
│ │                                                      │ │
│ └──────────────────────────────────────────────────────┘ │
│ Status: Done — 4 image(s) saved to ./output              │
└──────────────────────────────────────────────────────────┘
```

- Click **Generate** to start; the button disables while the request is in
  flight so you can't double-fire.
- Generated images are written to the **Output folder** immediately. The
  preview shows the first one; use **◀ Prev / Next ▶** to browse.
- **Open** opens the current image in the system viewer
  (`os.startfile` on Windows).
- **Copy path** puts the absolute path on the clipboard.
- **API key** field is masked by default — toggle **Show** to reveal.
  Click **Save** to persist it to the user config file
  (`%APPDATA%\minimaximage\config.json` on Windows). The status bar shows
  which source the current key came from (env / saved config / typed).

The GUI uses the same `generate_image()` SDK as the CLI, so all the
parameters work identically (model, aspect ratio, n, seed, response_format,
prompt_optimizer, AIGC watermark, subject references).

## CLI

```bash
# text-to-image, default 1:1
minimaximage "a fluffy cat wearing a top hat" --aspect-ratio 1:1 --n 1

# wide cinematic still
minimaximage "Tokyo street at night, neon reflections, 35mm film" \
    --aspect-ratio 16:9 --seed 42 --output-dir ./shots

# image-to-image with a subject reference
minimaximage "the same character on a beach" \
    --reference https://example.com/portrait.jpg --aspect-ratio 3:2

# custom resolution (image-01 only, must be multiple of 8 in [512, 2048])
minimaximage "studio portrait" --width 1024 --height 1024

# ask the API to auto-rewrite the prompt
minimaximage "a cat" --prompt-optimizer

# pass the API key inline (overrides saved config + env for this run)
minimaximage "a cat" --api-key eyJhbGciOi...
```

Generated URLs are valid for **24 hours**; the CLI downloads them to the
`--output-dir` immediately. Use `--print-json` to dump the full response
instead of writing files.

## SDK

```python
from minimaximage import generate_image

resp = generate_image(
    "a fox in a snowy forest, illustration style",
    model="image-01",
    aspect_ratio="16:9",
    n=2,
    seed=7,
)
for img in resp.images:
    img.save(f"out/{resp.id}.png")
```

Switch to image-to-image by passing `reference_images=[url1, url2, ...]`.

## Supported parameters

| Parameter | Notes |
| --- | --- |
| `model` | `image-01` or `image-01-live` |
| `prompt` | ≤ 1500 characters |
| `aspect_ratio` | `1:1`, `16:9`, `4:3`, `3:2`, `2:3`, `3:4`, `9:16`, `21:9` (`21:9` only on `image-01`) |
| `width` / `height` | `image-01` only; [512, 2048], multiple of 8, set together |
| `n` | 1–9 |
| `response_format` | `url` (default, 24 h expiry) or `base64` |
| `seed` | `int64` for reproducibility |
| `prompt_optimizer` | let the API rewrite the prompt |
| `aigc_watermark` | add an AIGC watermark |
| `subject_reference` | list of `{type: "character", image_file: <url>}` for I2I |

## Development

```bash
.venv/bin/pytest          # 59 tests
.venv/bin/ruff check src tests
.venv/bin/ruff format src tests
```

## Building standalone executables

To produce a Windows `.exe` that runs without Python installed:

```powershell
py -3 -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
python scripts\build_frontend.py
python scripts\build.py
```

Three files land in `dist\`:

- `dist\minimaximage.exe` — command-line interface
- `dist\minimaximage-desktop.exe` — modern FastAPI + React + pywebview GUI
- `dist\minimaximage-gui.exe` — legacy Tk desktop GUI (no console window)

See [BUILDING.md](BUILDING.md) for distribution tips, signing, antivirus
workarounds, and a sample GitHub Actions workflow.

## Project layout

```text
src/minimaximage/
├── __init__.py    # public API re-exports
├── __main__.py    # python -m minimaximage [gui]
├── cli.py         # `minimaximage` console script
├── gui.py         # `minimaximage-gui` console script
├── client.py      # httpx wrapper for POST /v1/image_generation
├── config.py      # env / .env loading
├── download.py    # URL → file (with 24 h reminder)
├── generate.py    # high-level `generate_image()`
└── models.py      # request/response dataclasses + validation
```

## License

MIT
