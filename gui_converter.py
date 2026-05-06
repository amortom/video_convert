#!/usr/bin/env python3
"""Tkinter GUI for the BK7258 MP4 -> MJPEG YUV422 converter."""

import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    import sv_ttk
    HAS_SV_TTK = True
except ImportError:
    HAS_SV_TTK = False


APP_VERSION = "1.0.0"
APP_TITLE = f"BK7258 MP4(MJPEG) Converter v{APP_VERSION}"
OUTPUT_SUFFIX = "_bk7258_mjpeg_yuv422.mp4"
TERMINAL_DEFAULT_WIDTH = 480
TERMINAL_DEFAULT_HEIGHT = 480
TERMINAL_DEFAULT_FPS = 25
TERMINAL_DEFAULT_QUALITY = 85
TERMINAL_DEFAULT_MAX_FRAME_KB = 96
TERMINAL_DEFAULT_MIN_QUALITY = 50
PROGRESS_RE = re.compile(r"\((\d+)%\)")


# ─── Color palette ────────────────────────────────────────────────────────────
COLOR_BG         = "#f5f6fa"
COLOR_CARD_BG    = "#ffffff"
COLOR_ACCENT     = "#0078d4"
COLOR_ACCENT_HOV = "#106ebe"
COLOR_SUCCESS    = "#107c10"
COLOR_DANGER     = "#d13438"
COLOR_TEXT       = "#1a1a1a"
COLOR_TEXT_SEC   = "#5f6368"
COLOR_LOG_BG     = "#1e1e2e"
COLOR_LOG_FG     = "#cdd6f4"
COLOR_BORDER     = "#e0e0e0"


class ConverterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("850x700")
        self.minsize(780, 640)
        self.configure(bg=COLOR_BG)

        if HAS_SV_TTK:
            sv_ttk.set_theme("light")

        self.log_queue = queue.Queue()
        self.worker = None
        self.output_path = None

        self._build_vars()
        self._apply_styles()
        self._build_ui()
        self.after(100, self._drain_log_queue)

    def _build_vars(self):
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.width_var = tk.IntVar(value=TERMINAL_DEFAULT_WIDTH)
        self.height_var = tk.IntVar(value=TERMINAL_DEFAULT_HEIGHT)
        self.fps_var = tk.IntVar(value=TERMINAL_DEFAULT_FPS)
        self.quality_var = tk.IntVar(value=TERMINAL_DEFAULT_QUALITY)
        self.resize_mode_var = tk.StringVar(value="fit")
        self.max_frame_kb_var = tk.IntVar(value=TERMINAL_DEFAULT_MAX_FRAME_KB)
        self.min_quality_var = tk.IntVar(value=TERMINAL_DEFAULT_MIN_QUALITY)
        self.max_duration_var = tk.StringVar()
        self.max_size_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready")

    def _apply_styles(self):
        style = ttk.Style(self)
        style.configure("Card.TFrame", background=COLOR_CARD_BG)
        style.configure("CardInner.TFrame", background=COLOR_CARD_BG)
        style.configure("Header.TLabel", font=("Segoe UI", 18, "bold"),
                        foreground=COLOR_TEXT)
        style.configure("Subtitle.TLabel", font=("Segoe UI", 9),
                        foreground=COLOR_TEXT_SEC)
        style.configure("Section.TLabel", font=("Segoe UI", 10, "bold"),
                        foreground=COLOR_ACCENT)
        style.configure("FieldLabel.TLabel", font=("Segoe UI", 9),
                        foreground=COLOR_TEXT_SEC)
        style.configure("Status.TLabel", font=("Segoe UI", 9),
                        foreground=COLOR_TEXT_SEC)
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

    def _make_card(self, parent, **pack_kw):
        card = ttk.Frame(parent, style="Card.TFrame", padding=16)
        card.pack(fill=tk.X, padx=2, pady=(0, 12), **pack_kw)
        return card

    def _section_header(self, parent, text, row=None):
        lbl = ttk.Label(parent, text=text, style="Section.TLabel")
        if row is not None:
            lbl.grid(row=row, column=0, columnspan=6, sticky=tk.W, pady=(0, 8))
        else:
            lbl.pack(anchor=tk.W, pady=(0, 8))
        return lbl

    def _build_ui(self):
        # ── Scrollable outer container ────────────────────────────────────────
        outer = ttk.Frame(self, padding=(20, 16, 20, 12))
        outer.pack(fill=tk.BOTH, expand=True)

        # ── Header ────────────────────────────────────────────────────────────
        header = ttk.Frame(outer)
        header.pack(fill=tk.X, pady=(0, 16))

        ttk.Label(
            header,
            text="BK7258 Terminal Video Converter",
            style="Header.TLabel",
        ).pack(side=tk.LEFT)

        ver_label = ttk.Label(header, text=f"v{APP_VERSION}",
                              font=("Segoe UI", 10), foreground=COLOR_TEXT_SEC)
        ver_label.pack(side=tk.LEFT, padx=(8, 0), pady=(6, 0))

        ttk.Label(
            outer,
            text="MP4 ► MJPEG / Baseline JPEG / YUV422 / no audio",
            style="Subtitle.TLabel",
        ).pack(anchor=tk.W, pady=(0, 14))

        ttk.Separator(outer, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 14))

        # ── Files card ────────────────────────────────────────────────────────
        file_card = self._make_card(outer)
        self._section_header(file_card, "📂  Files")

        file_grid = ttk.Frame(file_card, style="CardInner.TFrame")
        file_grid.pack(fill=tk.X)
        file_grid.columnconfigure(1, weight=1)

        ttk.Label(file_grid, text="Input MP4", style="FieldLabel.TLabel").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 12), pady=6)
        ttk.Entry(file_grid, textvariable=self.input_var, font=("Segoe UI", 9)).grid(
            row=0, column=1, sticky=tk.EW, pady=6, ipady=3)
        ttk.Button(file_grid, text="Browse…", command=self._browse_input,
                   width=10).grid(row=0, column=2, padx=(10, 0), pady=6)

        ttk.Label(file_grid, text="Output MP4", style="FieldLabel.TLabel").grid(
            row=1, column=0, sticky=tk.W, padx=(0, 12), pady=6)
        ttk.Entry(file_grid, textvariable=self.output_var, font=("Segoe UI", 9)).grid(
            row=1, column=1, sticky=tk.EW, pady=6, ipady=3)
        ttk.Button(file_grid, text="Save As…", command=self._browse_output,
                   width=10).grid(row=1, column=2, padx=(10, 0), pady=6)

        # ── Terminal Profile card ─────────────────────────────────────────────
        profile_card = self._make_card(outer)
        self._section_header(profile_card, "⚙  Terminal Profile")

        options = ttk.Frame(profile_card, style="CardInner.TFrame")
        options.pack(fill=tk.X)
        for col in range(6):
            options.columnconfigure(col, weight=1, uniform="opt")

        fields = [
            ("Width",          self.width_var,      2, 4096, 2,   8),
            ("Height",         self.height_var,     2, 4096, 2,   8),
            ("FPS",            self.fps_var,       20,   25, 1,   8),
            ("Quality",        self.quality_var,    1,   95, 1,   8),
        ]
        for i, (label, var, lo, hi, step, w) in enumerate(fields):
            ttk.Label(options, text=label, style="FieldLabel.TLabel").grid(
                row=0, column=i, sticky=tk.W, padx=(0, 8), pady=(0, 4))
            ttk.Spinbox(options, from_=lo, to=hi, increment=step,
                        textvariable=var, width=w, font=("Segoe UI", 9)).grid(
                row=1, column=i, sticky=tk.W, padx=(0, 8), pady=(0, 8))

        ttk.Label(options, text="Resize", style="FieldLabel.TLabel").grid(
            row=0, column=4, sticky=tk.W, padx=(0, 8), pady=(0, 4))
        ttk.Combobox(
            options, values=("fit", "crop", "stretch"),
            textvariable=self.resize_mode_var, width=10, state="readonly",
            font=("Segoe UI", 9),
        ).grid(row=1, column=4, sticky=tk.W, padx=(0, 8), pady=(0, 8))

        ttk.Label(options, text="Max Frame KB", style="FieldLabel.TLabel").grid(
            row=0, column=5, sticky=tk.W, pady=(0, 4))
        ttk.Spinbox(options, from_=1, to=512, increment=1,
                    textvariable=self.max_frame_kb_var, width=10,
                    font=("Segoe UI", 9)).grid(
            row=1, column=5, sticky=tk.W, pady=(0, 8))

        # ── Limits row ────────────────────────────────────────────────────────
        ttk.Separator(profile_card, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(4, 10))

        limits = ttk.Frame(profile_card, style="CardInner.TFrame")
        limits.pack(fill=tk.X)
        limits.columnconfigure(1, weight=1)
        limits.columnconfigure(3, weight=1)

        ttk.Label(limits, text="Max Duration (sec)", style="FieldLabel.TLabel").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 8))
        ttk.Entry(limits, textvariable=self.max_duration_var, width=14,
                  font=("Segoe UI", 9)).grid(row=0, column=1, sticky=tk.W, ipady=2)
        ttk.Label(limits, text="Max File Size (KB)", style="FieldLabel.TLabel").grid(
            row=0, column=2, sticky=tk.W, padx=(28, 8))
        ttk.Entry(limits, textvariable=self.max_size_var, width=14,
                  font=("Segoe UI", 9)).grid(row=0, column=3, sticky=tk.W, ipady=2)

        # ── Action bar ────────────────────────────────────────────────────────
        actions = ttk.Frame(outer)
        actions.pack(fill=tk.X, pady=(0, 12))

        self.convert_btn = ttk.Button(
            actions, text="▶  Convert", command=self._start_convert,
            style="Accent.TButton", width=14)
        self.convert_btn.pack(side=tk.LEFT)

        self.open_folder_btn = ttk.Button(
            actions, text="📁  Open Folder", command=self._open_output_folder,
            state=tk.DISABLED, width=14)
        self.open_folder_btn.pack(side=tk.LEFT, padx=(10, 0))

        self.progress = ttk.Progressbar(actions, mode="determinate", maximum=100,
                                        length=200)
        self.progress.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(20, 0))

        # ── Log card ──────────────────────────────────────────────────────────
        log_card = ttk.Frame(outer, style="Card.TFrame", padding=12)
        log_card.pack(fill=tk.BOTH, expand=True)
        log_card.rowconfigure(1, weight=1)
        log_card.columnconfigure(0, weight=1)

        self._section_header(log_card, "📋  Log", row=0)

        self.log_text = tk.Text(
            log_card, height=12, wrap=tk.WORD, state=tk.DISABLED,
            bg=COLOR_LOG_BG, fg=COLOR_LOG_FG,
            font=("Cascadia Code", 9), insertbackground=COLOR_LOG_FG,
            selectbackground=COLOR_ACCENT, selectforeground="#ffffff",
            relief=tk.FLAT, padx=10, pady=8,
            borderwidth=0,
        )
        self.log_text.grid(row=1, column=0, sticky=tk.NSEW)

        scroll = ttk.Scrollbar(log_card, orient=tk.VERTICAL,
                               command=self.log_text.yview)
        scroll.grid(row=1, column=1, sticky=tk.NS)
        self.log_text.configure(yscrollcommand=scroll.set)

        # ── Status bar ────────────────────────────────────────────────────────
        status_bar = ttk.Frame(outer)
        status_bar.pack(fill=tk.X, pady=(8, 0))

        self.status_dot = tk.Canvas(status_bar, width=10, height=10,
                                    highlightthickness=0, bg=COLOR_BG)
        self.status_dot.pack(side=tk.LEFT, padx=(0, 6))
        self._draw_status_dot(COLOR_SUCCESS)

        ttk.Label(status_bar, textvariable=self.status_var,
                  style="Status.TLabel").pack(side=tk.LEFT)

    def _draw_status_dot(self, color):
        self.status_dot.delete("all")
        self.status_dot.create_oval(1, 1, 9, 9, fill=color, outline=color)

    def _browse_input(self):
        path = filedialog.askopenfilename(
            title="Select input MP4",
            filetypes=(("MP4 files", "*.mp4"), ("Video files", "*.mp4 *.mov *.avi"), ("All files", "*.*")),
        )
        if not path:
            return

        self.input_var.set(path)
        base, _ = os.path.splitext(path)
        self.output_var.set(base + OUTPUT_SUFFIX)

    def _browse_output(self):
        initial = self.output_var.get() or "output_bk7258_mjpeg_yuv422.mp4"
        path = filedialog.asksaveasfilename(
            title="Save output MP4",
            defaultextension=".mp4",
            initialfile=os.path.basename(initial),
            initialdir=os.path.dirname(initial) or os.getcwd(),
            filetypes=(("MP4 files", "*.mp4"), ("All files", "*.*")),
        )
        if path:
            self.output_var.set(path)

    def _parse_optional_float(self, value, label):
        value = value.strip()
        if not value:
            return None
        try:
            parsed = float(value)
        except ValueError as exc:
            raise ValueError(f"{label} must be a number") from exc
        if parsed <= 0:
            raise ValueError(f"{label} must be greater than 0")
        return parsed

    def _parse_optional_int(self, value, label):
        value = value.strip()
        if not value:
            return None
        try:
            parsed = int(value)
        except ValueError as exc:
            raise ValueError(f"{label} must be an integer") from exc
        if parsed <= 0:
            raise ValueError(f"{label} must be greater than 0")
        return parsed

    def _validate_inputs(self):
        input_path = self.input_var.get().strip()
        output_path = self.output_var.get().strip()
        if not input_path:
            raise ValueError("Please select an input MP4 file")
        if not os.path.isfile(input_path):
            raise ValueError("Input file does not exist")
        if not output_path:
            raise ValueError("Please select an output MP4 path")
        if os.path.abspath(input_path) == os.path.abspath(output_path):
            raise ValueError("Output path must be different from input path")

        width = int(self.width_var.get())
        height = int(self.height_var.get())
        fps = int(self.fps_var.get())
        quality = int(self.quality_var.get())
        max_frame_kb = int(self.max_frame_kb_var.get())
        min_quality = int(self.min_quality_var.get())

        if width <= 0 or height <= 0 or width % 2 or height % 2:
            raise ValueError("Width and height must be positive even numbers")
        if fps < 20 or fps > 25:
            raise ValueError("FPS must be in range 20-25")
        if quality < 1 or quality > 95:
            raise ValueError("Quality must be in range 1-95")
        if min_quality < 1 or min_quality > quality:
            raise ValueError("Minimum quality must be in range 1..quality")
        if max_frame_kb <= 0:
            raise ValueError("Max Frame KB must be greater than 0")

        max_duration = self._parse_optional_float(self.max_duration_var.get(), "Max Duration")
        max_size = self._parse_optional_int(self.max_size_var.get(), "Max File Size")

        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        return {
            "input_path": input_path,
            "output_path": output_path,
            "target_w": width,
            "target_h": height,
            "fps": fps,
            "quality": quality,
            "resize_mode": self.resize_mode_var.get(),
            "max_size_kb": max_size,
            "max_duration": max_duration,
            "max_frame_kb": max_frame_kb,
            "min_quality": min_quality,
        }

    def _start_convert(self):
        if self.worker and self.worker.is_alive():
            return

        try:
            params = self._validate_inputs()
        except ValueError as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return

        self.output_path = params["output_path"]
        self._clear_log()
        self.open_folder_btn.configure(state=tk.DISABLED)
        self.convert_btn.configure(state=tk.DISABLED)
        self.status_var.set("Converting...")
        self._draw_status_dot(COLOR_ACCENT)
        self.progress.configure(value=0)

        self.worker = threading.Thread(target=self._run_convert, args=(params,), daemon=True)
        self.worker.start()

    def _worker_command(self, params):
        if getattr(sys, "frozen", False):
            worker = os.path.join(os.path.dirname(sys.executable), "BK7258ConverterWorker.exe")
            cmd = [worker]
        else:
            script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mp4_converter.py")
            cmd = [sys.executable, "-u", script]

        cmd.extend([
            params["input_path"],
            "-o", params["output_path"],
            "-W", str(params["target_w"]),
            "-H", str(params["target_h"]),
            "-f", str(params["fps"]),
            "-q", str(params["quality"]),
            "-m", params["resize_mode"],
            "--max-frame-kb", str(params["max_frame_kb"]),
            "--min-quality", str(params["min_quality"]),
        ])

        if params["max_size_kb"] is not None:
            cmd.extend(["--max-size", str(params["max_size_kb"])])
        if params["max_duration"] is not None:
            cmd.extend(["--max-duration", str(params["max_duration"])])

        return cmd

    def _run_convert(self, params):
        cmd = self._worker_command(params)
        if getattr(sys, "frozen", False) and not os.path.isfile(cmd[0]):
            self.log_queue.put(("log", f"Error: worker executable not found: {cmd[0]}\n"))
            self.log_queue.put(("done", False))
            return

        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
            )
            assert process.stdout is not None
            for line in process.stdout:
                self.log_queue.put(("log", line))
            ok = process.wait() == 0
        except Exception as exc:
            self.log_queue.put(("log", f"\nError: {exc}\n"))
            ok = False

        self.log_queue.put(("done", ok))

    def _drain_log_queue(self):
        try:
            while True:
                kind, payload = self.log_queue.get_nowait()
                if kind == "log":
                    self._append_log(payload)
                elif kind == "done":
                    self._on_done(bool(payload))
        except queue.Empty:
            pass

        self.after(100, self._drain_log_queue)

    def _append_log(self, text):
        match = PROGRESS_RE.search(text)
        if match:
            pct = int(match.group(1))
            self.progress.configure(value=max(0, min(100, pct)))
            self.status_var.set(f"Converting... {pct}%")

        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _clear_log(self):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _on_done(self, ok):
        self.convert_btn.configure(state=tk.NORMAL)
        if ok:
            self.progress.configure(value=100)
            self.status_var.set("Done — conversion complete")
            self._draw_status_dot(COLOR_SUCCESS)
            self.open_folder_btn.configure(state=tk.NORMAL)
            messagebox.showinfo(APP_TITLE, "Conversion complete.")
        else:
            self.progress.configure(value=0)
            self.status_var.set("Failed — check the log for details")
            self._draw_status_dot(COLOR_DANGER)
            messagebox.showerror(APP_TITLE, "Conversion failed. Check the log for details.")

    def _open_output_folder(self):
        path = self.output_path or self.output_var.get().strip()
        folder = os.path.dirname(path)
        if folder and os.path.isdir(folder):
            subprocess.Popen(["explorer", folder])


def main():
    app = ConverterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
