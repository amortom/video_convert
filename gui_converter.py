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


class ConverterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("780x620")
        self.minsize(720, 560)

        self.log_queue = queue.Queue()
        self.worker = None
        self.output_path = None

        self._build_vars()
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

    def _build_ui(self):
        outer = ttk.Frame(self, padding=14)
        outer.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(
            outer,
            text=f"BK7258 Terminal Video Converter v{APP_VERSION}",
            font=("Segoe UI", 16, "bold"),
        )
        title.pack(anchor=tk.W)

        subtitle = ttk.Label(
            outer,
            text="Output profile: MP4 / MJPEG / Baseline JPEG / YUV422 / 480x480 / no audio",
        )
        subtitle.pack(anchor=tk.W, pady=(2, 12))

        file_frame = ttk.LabelFrame(outer, text="Files", padding=10)
        file_frame.pack(fill=tk.X)
        file_frame.columnconfigure(1, weight=1)

        ttk.Label(file_frame, text="Input MP4").grid(row=0, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        ttk.Entry(file_frame, textvariable=self.input_var).grid(row=0, column=1, sticky=tk.EW, pady=4)
        ttk.Button(file_frame, text="Browse", command=self._browse_input).grid(row=0, column=2, padx=(8, 0), pady=4)

        ttk.Label(file_frame, text="Output MP4").grid(row=1, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        ttk.Entry(file_frame, textvariable=self.output_var).grid(row=1, column=1, sticky=tk.EW, pady=4)
        ttk.Button(file_frame, text="Save As", command=self._browse_output).grid(row=1, column=2, padx=(8, 0), pady=4)

        options = ttk.LabelFrame(outer, text="Terminal Profile", padding=10)
        options.pack(fill=tk.X, pady=(12, 0))

        for col in range(6):
            options.columnconfigure(col, weight=1)

        ttk.Label(options, text="Width").grid(row=0, column=0, sticky=tk.W)
        ttk.Spinbox(options, from_=2, to=4096, increment=2, textvariable=self.width_var, width=8).grid(row=1, column=0, sticky=tk.W)

        ttk.Label(options, text="Height").grid(row=0, column=1, sticky=tk.W)
        ttk.Spinbox(options, from_=2, to=4096, increment=2, textvariable=self.height_var, width=8).grid(row=1, column=1, sticky=tk.W)

        ttk.Label(options, text="FPS").grid(row=0, column=2, sticky=tk.W)
        ttk.Spinbox(options, from_=20, to=25, increment=1, textvariable=self.fps_var, width=8).grid(row=1, column=2, sticky=tk.W)

        ttk.Label(options, text="Quality").grid(row=0, column=3, sticky=tk.W)
        ttk.Spinbox(options, from_=1, to=95, increment=1, textvariable=self.quality_var, width=8).grid(row=1, column=3, sticky=tk.W)

        ttk.Label(options, text="Resize").grid(row=0, column=4, sticky=tk.W)
        ttk.Combobox(
            options,
            values=("fit", "crop", "stretch"),
            textvariable=self.resize_mode_var,
            width=10,
            state="readonly",
        ).grid(row=1, column=4, sticky=tk.W)

        ttk.Label(options, text="Max Frame KB").grid(row=0, column=5, sticky=tk.W)
        ttk.Spinbox(options, from_=1, to=512, increment=1, textvariable=self.max_frame_kb_var, width=10).grid(row=1, column=5, sticky=tk.W)

        limits = ttk.Frame(options)
        limits.grid(row=2, column=0, columnspan=6, sticky=tk.EW, pady=(12, 0))
        limits.columnconfigure(1, weight=1)
        limits.columnconfigure(3, weight=1)

        ttk.Label(limits, text="Max Duration (sec, optional)").grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        ttk.Entry(limits, textvariable=self.max_duration_var, width=14).grid(row=0, column=1, sticky=tk.W)
        ttk.Label(limits, text="Max File Size KB (optional)").grid(row=0, column=2, sticky=tk.W, padx=(24, 8))
        ttk.Entry(limits, textvariable=self.max_size_var, width=14).grid(row=0, column=3, sticky=tk.W)

        actions = ttk.Frame(outer)
        actions.pack(fill=tk.X, pady=(12, 0))
        self.convert_btn = ttk.Button(actions, text="Convert", command=self._start_convert)
        self.convert_btn.pack(side=tk.LEFT)
        self.open_folder_btn = ttk.Button(actions, text="Open Output Folder", command=self._open_output_folder, state=tk.DISABLED)
        self.open_folder_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.progress = ttk.Progressbar(actions, mode="determinate", maximum=100)
        self.progress.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(12, 0))

        log_frame = ttk.LabelFrame(outer, text="Log", padding=8)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log_text = tk.Text(log_frame, height=16, wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.grid(row=0, column=0, sticky=tk.NSEW)
        scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scroll.grid(row=0, column=1, sticky=tk.NS)
        self.log_text.configure(yscrollcommand=scroll.set)

        status = ttk.Label(outer, textvariable=self.status_var)
        status.pack(anchor=tk.W, pady=(8, 0))

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
            self.status_var.set("Done")
            self.open_folder_btn.configure(state=tk.NORMAL)
            messagebox.showinfo(APP_TITLE, "Conversion complete.")
        else:
            self.progress.configure(value=0)
            self.status_var.set("Failed")
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
