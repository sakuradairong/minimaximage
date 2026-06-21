"""Cross-platform Tk GUI for minimaximage.

Run with:
    minimaximage-gui
    python -m minimaximage gui
    python -m minimaximage_gui

Requires Pillow (installed by default) and tkinter (bundled with the
standard Python installer on Windows and macOS; on Linux install the
`python3-tk` package).
"""

from __future__ import annotations

import base64
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from PIL import Image, ImageTk

from minimaximage.client import MinimaxClient
from minimaximage.config import (
    Settings,
    load_config,
    save_config,
)
from minimaximage.download import default_filename, download_to_path
from minimaximage.generate import generate_image
from minimaximage.models import AspectRatio, ImageModel, ResponseFormat

DEFAULT_OUTPUT_DIR = Path("./output")
POLL_MS = 100


# --------------------------------------------------------------------------- #
# Pure helpers (UI-free, easy to unit-test)
# --------------------------------------------------------------------------- #


def parse_references(text: str) -> list[str]:
    """Parse a newline-separated list of reference image URLs."""
    return [line.strip() for line in text.splitlines() if line.strip()]


def build_request_params(
    *,
    prompt: str,
    model: str,
    aspect_ratio: str,
    n: int,
    seed: str,
    response_format: str,
    prompt_optimizer: bool,
    watermark: bool,
    reference_text: str,
) -> dict[str, Any]:
    """Translate form values into kwargs for generate_image()."""
    return {
        "prompt": prompt.strip(),
        "model": ImageModel.parse(model),
        "aspect_ratio": aspect_ratio or None,
        "n": n,
        "seed": int(seed) if seed.strip() else None,
        "response_format": response_format,
        "prompt_optimizer": prompt_optimizer,
        "aigc_watermark": watermark,
        "reference_images": parse_references(reference_text) or None,
    }


def save_response_images(response: Any, out_dir: Path) -> list[Path]:
    """Persist every image in the response to `out_dir` and return the paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for idx, img in enumerate(response.images):
        path = out_dir / default_filename(response.id, idx)
        if img.is_base64:
            path.write_bytes(base64.b64decode(img.value))
        else:
            download_to_path(img.value, str(path))
        paths.append(path)
    return paths


# --------------------------------------------------------------------------- #
# Main app
# --------------------------------------------------------------------------- #


class App(tk.Tk):
    """The main Tk window."""

    def __init__(self) -> None:
        super().__init__()
        self.title("minimaximage — image generator")
        self.geometry("980x720")
        self.minsize(820, 640)

        self._result_queue: queue.Queue = queue.Queue()
        self._current_paths: list[Path] = []
        self._current_index: int = 0
        self._preview_image: ImageTk.PhotoImage | None = None
        self._is_generating = False
        self._settings: Settings | None = None

        self._build_styles()
        self._build_widgets()

        # Try to load settings from env / config file and pre-fill the API key
        # field so the user can see what's being used. The field is editable:
        # if the user types a new key and clicks Generate, that value wins for
        # this run; clicking "Save" persists it to the config file.
        try:
            config = load_config()
        except OSError:
            config = {}
        saved_key = config.get("api_key") or os.environ.get("MINIMAX_API_KEY", "")
        self.api_key_var.set(saved_key)

        try:
            self._settings = Settings.load()
        except OSError as e:
            self._set_status(f"⚠ {e}", error=True)
        else:
            source = "env" if os.environ.get("MINIMAX_API_KEY", "").strip() else "saved config"
            self._set_status(f"Ready — API key from {source}")

    # -- layout -------------------------------------------------------------- #

    def _build_styles(self) -> None:
        style = ttk.Style(self)
        # "vista" is the modern Windows theme; fall back gracefully elsewhere.
        for theme in ("vista", "clam", "default"):
            if theme in style.theme_names():
                try:
                    style.theme_use(theme)
                    break
                except tk.TclError:
                    continue

    def _build_widgets(self) -> None:
        root = ttk.Frame(self, padding=10)
        root.pack(fill="both", expand=True)

        self._build_settings_frame(root)
        self._build_prompt_frame(root)
        self._build_references_frame(root)
        self._build_output_row(root)
        self._build_preview_frame(root)
        self._build_status_bar(root)

    def _build_settings_frame(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="Settings", padding=8)
        box.pack(fill="x", pady=(0, 8))

        self.model_var = tk.StringVar(value=ImageModel.IMAGE_01.value)
        self.aspect_var = tk.StringVar(value="")
        self.n_var = tk.IntVar(value=1)
        self.seed_var = tk.StringVar(value="")
        self.format_var = tk.StringVar(value=ResponseFormat.URL.value)
        self.optimizer_var = tk.BooleanVar(value=False)
        self.watermark_var = tk.BooleanVar(value=False)
        self.api_key_var = tk.StringVar()
        self.show_key_var = tk.BooleanVar(value=False)

        # --- API key row (sticky to top so it's always visible) ---
        ttk.Label(box, text="API key:").grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.api_key_entry = ttk.Entry(box, textvariable=self.api_key_var, show="•")
        self.api_key_entry.grid(row=0, column=1, columnspan=5, sticky="we", padx=(0, 4))
        box.columnconfigure(1, weight=1)
        ttk.Button(box, text="Save", command=self._on_save_api_key, width=8).grid(
            row=0, column=6, padx=(0, 4)
        )
        ttk.Checkbutton(
            box, text="Show", variable=self.show_key_var, command=self._on_toggle_key_visibility
        ).grid(row=0, column=7, sticky="w")

        # The Model/Aspect/etc. rows now start at row=1 to leave room for the
        # API key row above.
        ttk.Label(box, text="Model:").grid(row=1, column=0, sticky="w", padx=(0, 4), pady=(6, 0))
        ttk.Combobox(
            box,
            textvariable=self.model_var,
            width=14,
            state="readonly",
            values=[m.value for m in ImageModel],
        ).grid(row=1, column=1, sticky="w", padx=(0, 12), pady=(6, 0))

        ttk.Label(box, text="Aspect:").grid(row=1, column=2, sticky="w", padx=(0, 4), pady=(6, 0))
        ttk.Combobox(
            box,
            textvariable=self.aspect_var,
            width=10,
            values=["", *(a.value for a in AspectRatio)],
        ).grid(row=1, column=3, sticky="w", padx=(0, 12), pady=(6, 0))

        ttk.Label(box, text="n:").grid(row=1, column=4, sticky="w", padx=(0, 4), pady=(6, 0))
        ttk.Spinbox(box, from_=1, to=9, textvariable=self.n_var, width=4).grid(
            row=1, column=5, sticky="w", padx=(0, 12), pady=(6, 0)
        )

        ttk.Label(box, text="Seed:").grid(row=1, column=6, sticky="w", padx=(0, 4), pady=(6, 0))
        ttk.Entry(box, textvariable=self.seed_var, width=10).grid(
            row=1, column=7, sticky="w", pady=(6, 0)
        )

        ttk.Label(box, text="Format:").grid(row=2, column=0, sticky="w", padx=(0, 4), pady=(6, 0))
        ttk.Combobox(
            box,
            textvariable=self.format_var,
            width=10,
            state="readonly",
            values=[f.value for f in ResponseFormat],
        ).grid(row=2, column=1, sticky="w", pady=(6, 0))
        ttk.Checkbutton(box, text="Prompt optimizer", variable=self.optimizer_var).grid(
            row=2, column=2, columnspan=2, sticky="w", pady=(6, 0)
        )
        ttk.Checkbutton(box, text="AIGC watermark", variable=self.watermark_var).grid(
            row=2, column=4, columnspan=2, sticky="w", pady=(6, 0)
        )

    def _build_prompt_frame(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="Prompt (≤1500 characters)", padding=8)
        box.pack(fill="both", expand=False, pady=(0, 8))
        self.prompt_text = tk.Text(box, height=5, wrap="word")
        self.prompt_text.pack(fill="both", expand=True)

    def _build_references_frame(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="Reference image URLs — one per line, for I2I", padding=8)
        box.pack(fill="both", expand=False, pady=(0, 8))
        self.ref_text = tk.Text(box, height=3, wrap="word")
        self.ref_text.pack(fill="both", expand=True)

    def _build_output_row(self, parent: ttk.Frame) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(0, 8))

        ttk.Label(row, text="Output folder:").pack(side="left", padx=(0, 4))
        self.outdir_var = tk.StringVar(value=str(DEFAULT_OUTPUT_DIR))
        ttk.Entry(row, textvariable=self.outdir_var).pack(
            side="left", fill="x", expand=True, padx=(0, 4)
        )
        ttk.Button(row, text="Browse…", command=self._on_browse).pack(side="left", padx=(0, 8))
        self.generate_btn = ttk.Button(row, text="Generate", command=self._on_generate)
        self.generate_btn.pack(side="right")

    def _build_preview_frame(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="Preview", padding=8)
        box.pack(fill="both", expand=True)

        nav = ttk.Frame(box)
        nav.pack(fill="x", pady=(0, 6))
        self.prev_btn = ttk.Button(
            nav, text="◀ Prev", command=lambda: self._show_index(-1), state="disabled"
        )
        self.prev_btn.pack(side="left")
        self.next_btn = ttk.Button(
            nav, text="Next ▶", command=lambda: self._show_index(+1), state="disabled"
        )
        self.next_btn.pack(side="left", padx=(4, 0))
        self.index_label = ttk.Label(nav, text="—")
        self.index_label.pack(side="left", padx=8)
        self.path_label = ttk.Label(nav, text="")
        self.path_label.pack(side="left", padx=(0, 8))
        ttk.Button(nav, text="Open", command=self._on_open).pack(side="right")
        ttk.Button(nav, text="Copy path", command=self._on_copy_path).pack(
            side="right", padx=(0, 4)
        )

        self.canvas = tk.Canvas(box, bg="#222", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _e: self._refresh_preview())

    def _build_status_bar(self, parent: ttk.Frame) -> None:
        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(8, 0))
        self.status_var = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.status_var).pack(side="left")
        self.progress = ttk.Progressbar(bar, mode="indeterminate", length=160)

    # -- event handlers ------------------------------------------------------ #

    def _on_browse(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.outdir_var.get() or ".")
        if chosen:
            self.outdir_var.set(chosen)

    def _on_save_api_key(self) -> None:
        key = self.api_key_var.get().strip()
        if not key:
            messagebox.showwarning("API key required", "Please enter an API key to save.")
            return
        existing = load_config()
        existing["api_key"] = key
        path = save_config(existing)
        # Validate that the new key actually resolves.
        try:
            self._settings = Settings.load(api_key=key)
        except OSError as e:
            messagebox.showerror("Save failed", str(e))
            return
        self._set_status(f"Saved API key to {path}")
        messagebox.showinfo("Saved", f"API key persisted to:\n{path}")

    def _on_toggle_key_visibility(self) -> None:
        self.api_key_entry.configure(show="" if self.show_key_var.get() else "•")

    def _on_generate(self) -> None:
        if self._is_generating:
            return
        prompt = self.prompt_text.get("1.0", "end").strip()
        if not prompt:
            messagebox.showwarning("Prompt required", "Please enter a prompt.")
            return
        if len(prompt) > 1500:
            messagebox.showwarning("Prompt too long", "Prompt must be ≤1500 characters.")
            return

        # Resolve the API key for this run. The field value (if non-empty)
        # wins over the saved config and env vars so the user can test a new
        # key without restarting the app.
        typed_key = self.api_key_var.get().strip()
        try:
            self._settings = Settings.load(api_key=typed_key or None)
        except OSError as e:
            messagebox.showerror(
                "Missing API key",
                f"{e}\n\nEnter one above and click Generate, or click Save to persist it.",
            )
            return

        try:
            params = build_request_params(
                prompt=prompt,
                model=self.model_var.get(),
                aspect_ratio=self.aspect_var.get(),
                n=self.n_var.get(),
                seed=self.seed_var.get(),
                response_format=self.format_var.get(),
                prompt_optimizer=self.optimizer_var.get(),
                watermark=self.watermark_var.get(),
                reference_text=self.ref_text.get("1.0", "end"),
            )
        except (OSError, ValueError) as e:
            messagebox.showerror("Invalid input", str(e))
            return

        self._set_busy(True, f"Generating {params['n']} image(s)…")
        out_dir = Path(self.outdir_var.get())  # capture on main thread
        worker = threading.Thread(target=self._worker, args=(params, out_dir), daemon=True)
        worker.start()
        self.after(POLL_MS, self._poll_queue)

    def _worker(self, params: dict[str, Any], out_dir: Path) -> None:
        """Runs in a background thread; posts results via the queue.

        `out_dir` is a plain `pathlib.Path` captured on the main thread, so the
        worker never touches a `tk.Variable` (which would require the Tcl
        event loop).
        """
        assert self._settings is not None
        try:
            client = MinimaxClient(api_key=self._settings.api_key, base_url=self._settings.base_url)
            try:
                response = generate_image(client=client, **params)
                paths = save_response_images(response, out_dir)
            finally:
                client.close()
            self._result_queue.put(("ok", paths))
        except Exception as e:  # noqa: BLE001 — surface any failure to the UI
            self._result_queue.put(("err", e))

    def _poll_queue(self) -> None:
        try:
            kind, payload = self._result_queue.get_nowait()
        except queue.Empty:
            if self._is_generating:
                self.after(POLL_MS, self._poll_queue)
            return

        self._set_busy(False)
        if kind == "err":
            self._set_status(f"Error: {payload}", error=True)
            messagebox.showerror("Generation failed", str(payload))
            return
        self._current_paths = payload
        self._current_index = 0
        self._show_index(0)
        self._set_status(
            f"Done — {len(self._current_paths)} image(s) saved to {self.outdir_var.get()}"
        )

    # -- preview + nav ------------------------------------------------------- #

    def _show_index(self, delta: int) -> None:
        if not self._current_paths:
            return
        if delta:
            self._current_index = (self._current_index + delta) % len(self._current_paths)
        else:
            self._current_index = 0
        self._load_preview(self._current_paths[self._current_index])
        self._update_nav()

    def _load_preview(self, path: Path) -> None:
        try:
            with Image.open(path) as img:
                img.load()
                self._fit_to_canvas(img)
                self._preview_image = ImageTk.PhotoImage(img)
        except Exception as e:  # noqa: BLE001
            self._set_status(f"Preview failed: {e}", error=True)
            return
        self.canvas.delete("all")
        x = self.canvas.winfo_width() // 2
        y = self.canvas.winfo_height() // 2
        self.canvas.create_image(x, y, image=self._preview_image, anchor="center")
        self.path_label.configure(text=str(path))

    def _refresh_preview(self) -> None:
        """Re-render the preview when the canvas is resized."""
        if self._current_paths and self._preview_image is not None:
            self._load_preview(self._current_paths[self._current_index])

    def _fit_to_canvas(self, img: Image.Image) -> None:
        cw = max(self.canvas.winfo_width() - 12, 320)
        ch = max(self.canvas.winfo_height() - 12, 240)
        img.thumbnail((cw, ch), Image.Resampling.LANCZOS)

    def _update_nav(self) -> None:
        total = len(self._current_paths)
        if total <= 1:
            self.prev_btn.configure(state="disabled")
            self.next_btn.configure(state="disabled")
        else:
            self.prev_btn.configure(state="normal")
            self.next_btn.configure(state="normal")
        self.index_label.configure(text=f"{self._current_index + 1}/{total}" if total else "—")

    # -- misc ---------------------------------------------------------------- #

    def _on_open(self) -> None:
        if not self._current_paths:
            return
        path = self._current_paths[self._current_index]
        try:
            if sys.platform == "win32":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Open failed", str(e))

    def _on_copy_path(self) -> None:
        if not self._current_paths:
            return
        path = self._current_paths[self._current_index]
        self.clipboard_clear()
        self.clipboard_append(str(path))
        self._set_status(f"Copied path: {path}")

    def _set_status(self, text: str, *, error: bool = False) -> None:  # noqa: ARG002
        self.status_var.set(text)

    def _set_busy(self, busy: bool, text: str = "") -> None:
        self._is_generating = busy
        self.generate_btn.configure(state="disabled" if busy else "normal")
        if busy:
            self._set_status(text or "Working…")
            self.progress.pack(side="right", padx=(8, 0))
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.pack_forget()


def main() -> int:
    try:
        App().mainloop()
    except tk.TclError as e:
        print(f"Cannot start GUI: {e}", file=sys.stderr)
        return 1
    return 0


__all__ = ["App", "build_request_params", "main", "parse_references", "save_response_images"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
