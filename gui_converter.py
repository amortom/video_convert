import os
import sys
import threading
import queue
import subprocess
import re
import customtkinter as ctk
from tkinter import filedialog, messagebox

# Set environment variables for single-executable compatibility BEFORE importing TkinterDnD
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
    os.environ["TKDND_LIBRARY"] = os.path.join(base_path, "tkinterdnd2", "tkdnd")
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

from tkinterdnd2 import TkinterDnD, DND_FILES

APP_VERSION = "1.1.0"
APP_TITLE = f"BK7258 Video Converter"
OUTPUT_SUFFIX = "_bk7258_mjpeg_yuv422.mp4"

# Default parameters
TERMINAL_DEFAULT_WIDTH = 480
TERMINAL_DEFAULT_HEIGHT = 480
TERMINAL_DEFAULT_FPS = 25
TERMINAL_DEFAULT_QUALITY = 85
TERMINAL_DEFAULT_MAX_FRAME_KB = 96
TERMINAL_DEFAULT_MIN_QUALITY = 50

PROGRESS_RE = re.compile(r"\((\d+)%\)")

# Wrapper to support both CustomTkinter and TkinterDnD2
class CTk(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TkdndVersion = TkinterDnD._require(self)

class ConverterApp(CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("900x650")
        self.minsize(800, 600)
        
        # Modern appearance setup
        ctk.set_appearance_mode("Light")
        ctk.set_default_color_theme("blue")
        
        self.log_queue = queue.Queue()
        self.worker = None
        self.input_file = None
        self.output_file = None
        
        self._build_vars()
        self._build_ui()
        self.after(100, self._drain_log_queue)

    def _build_vars(self):
        self.width_var = ctk.StringVar(value=str(TERMINAL_DEFAULT_WIDTH))
        self.height_var = ctk.StringVar(value=str(TERMINAL_DEFAULT_HEIGHT))
        self.fps_var = ctk.StringVar(value=str(TERMINAL_DEFAULT_FPS))
        self.quality_var = ctk.StringVar(value=str(TERMINAL_DEFAULT_QUALITY))
        self.resize_mode_var = ctk.StringVar(value="fit")
        self.max_frame_kb_var = ctk.StringVar(value=str(TERMINAL_DEFAULT_MAX_FRAME_KB))
        self.min_quality_var = ctk.StringVar(value=str(TERMINAL_DEFAULT_MIN_QUALITY))
        self.max_duration_var = ctk.StringVar(value="")
        self.max_size_var = ctk.StringVar(value="")

    def _build_ui(self):
        # Configure grid layout (1 row, 2 columns)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # --- 1. Sidebar ---
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color="#F8F9FA")
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        # App Logo / Title
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="BK7258\nConverter", font=ctk.CTkFont(size=22, weight="bold"), text_color="#1E1E1E")
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 40))

        # Nav Buttons
        self.btn_nav_convert = ctk.CTkButton(self.sidebar_frame, text=" 🎬   Convert Video", fg_color="transparent", text_color="#333333", hover_color="#E9ECEF", anchor="w", font=ctk.CTkFont(size=14, weight="bold"), command=lambda: self.select_frame("convert"))
        self.btn_nav_convert.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        self.btn_nav_settings = ctk.CTkButton(self.sidebar_frame, text=" ⚙️   Terminal Settings", fg_color="transparent", text_color="#333333", hover_color="#E9ECEF", anchor="w", font=ctk.CTkFont(size=14), command=lambda: self.select_frame("settings"))
        self.btn_nav_settings.grid(row=2, column=0, padx=10, pady=5, sticky="ew")

        self.btn_nav_log = ctk.CTkButton(self.sidebar_frame, text=" 📋   Console Log", fg_color="transparent", text_color="#333333", hover_color="#E9ECEF", anchor="w", font=ctk.CTkFont(size=14), command=lambda: self.select_frame("log"))
        self.btn_nav_log.grid(row=3, column=0, padx=10, pady=5, sticky="ew")

        # Version label at the bottom
        self.version_label = ctk.CTkLabel(self.sidebar_frame, text=f"Version {APP_VERSION}", text_color="#999999")
        self.version_label.grid(row=5, column=0, padx=20, pady=20, sticky="sw")

        # --- Main Frames Container ---
        self.frames = {}
        
        # --- 2. Convert Frame ---
        self.frame_convert = ctk.CTkFrame(self, corner_radius=0, fg_color="white")
        self.frame_convert.grid_rowconfigure(1, weight=1)
        self.frame_convert.grid_columnconfigure(0, weight=1)
        
        # Toolbar (Top) - Just for spacing now
        self.toolbar = ctk.CTkFrame(self.frame_convert, fg_color="white", corner_radius=0, height=20)
        self.toolbar.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        
        # Big Drag and Drop Area
        self.drop_area = ctk.CTkFrame(self.frame_convert, corner_radius=20, fg_color="#F8F9FA", border_width=2)
        # Using a solid border color to simulate dashed line since solid is natively supported
        self.drop_area.configure(border_color="#E2E5E9") 
        self.drop_area.grid(row=1, column=0, sticky="nsew", padx=50, pady=(0, 50))
        self.drop_area.grid_rowconfigure(0, weight=1)
        self.drop_area.grid_rowconfigure(1, weight=1)
        self.drop_area.grid_rowconfigure(2, weight=1)
        self.drop_area.grid_columnconfigure(0, weight=1)
        
        # Register Drag and Drop
        self.drop_area.drop_target_register(DND_FILES)
        self.drop_area.dnd_bind('<<Drop>>', self._on_drop)
        
        # Center UI container for drop area
        self.drop_center_ui = ctk.CTkFrame(self.drop_area, fg_color="transparent")
        self.drop_center_ui.grid(row=1, column=0)
        
        self.lbl_drop_icon = ctk.CTkLabel(self.drop_center_ui, text="🎬", font=ctk.CTkFont(size=48), text_color="#CED4DA")
        self.lbl_drop_icon.pack(pady=(0, 15))
        
        self.lbl_drop_text = ctk.CTkLabel(self.drop_center_ui, text="Drag files here to start conversion", font=ctk.CTkFont(size=16), text_color="#868E96")
        self.lbl_drop_text.pack(pady=(0, 25))
        
        # Prominent Red Add Button
        self.btn_center_add = ctk.CTkButton(self.drop_center_ui, text="➕ Add File", font=ctk.CTkFont(size=15, weight="bold"), fg_color="#FF4D4F", hover_color="#E03131", text_color="white", width=160, height=45, corner_radius=25, command=self._browse_input)
        self.btn_center_add.pack()
        
        # Item view (hidden by default, shown when file selected)
        self.item_frame = ctk.CTkFrame(self.drop_area, fg_color="white", corner_radius=10, border_width=1, border_color="#DEE2E6")
        self.item_frame.grid_columnconfigure(1, weight=1)
        
        # Item Icon and Text
        self.lbl_filename = ctk.CTkLabel(self.item_frame, text="", font=ctk.CTkFont(size=16, weight="bold"), text_color="#1E1E1E")
        self.lbl_filename.grid(row=0, column=0, columnspan=2, padx=20, pady=(20, 5), sticky="w")
        self.lbl_format = ctk.CTkLabel(self.item_frame, text="Target: MJPEG / 480x480 / YUV422", text_color="#6C757D", font=ctk.CTkFont(size=12))
        self.lbl_format.grid(row=1, column=0, columnspan=2, padx=20, pady=(0, 20), sticky="w")
        
        # Big Red Action Button
        self.btn_start_convert = ctk.CTkButton(self.item_frame, text="Convert", font=ctk.CTkFont(size=14, weight="bold"), fg_color="#FF4D4F", hover_color="#E03131", text_color="white", width=120, height=40, command=self._start_convert)
        self.btn_start_convert.grid(row=0, column=2, rowspan=2, padx=20)
        
        # Progress UI
        self.progress = ctk.CTkProgressBar(self.item_frame, mode="determinate", progress_color="#FF4D4F")
        self.progress.set(0)
        
        self.lbl_status = ctk.CTkLabel(self.item_frame, text="Ready", text_color="#6C757D", font=ctk.CTkFont(size=12))

        # --- 3. Settings Frame ---
        self.frame_settings = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="white")
        self.frame_settings.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(self.frame_settings, text="Terminal Profile Settings", font=ctk.CTkFont(size=22, weight="bold"), text_color="#1E1E1E").grid(row=0, column=0, columnspan=2, sticky="w", padx=40, pady=(40, 20))
        
        settings_fields = [
            ("Width", self.width_var),
            ("Height", self.height_var),
            ("FPS", self.fps_var),
            ("Quality (1-95)", self.quality_var),
            ("Max Frame KB", self.max_frame_kb_var),
            ("Min Quality", self.min_quality_var),
            ("Max Duration (sec)", self.max_duration_var),
            ("Max File Size (KB)", self.max_size_var)
        ]
        
        for i, (lbl, var) in enumerate(settings_fields):
            ctk.CTkLabel(self.frame_settings, text=lbl, text_color="#333333", font=ctk.CTkFont(size=14)).grid(row=i+1, column=0, sticky="w", padx=40, pady=12)
            entry = ctk.CTkEntry(self.frame_settings, textvariable=var, width=300, fg_color="#F8F9FA", border_color="#DEE2E6")
            entry.grid(row=i+1, column=1, sticky="w", padx=20, pady=12)
            
        ctk.CTkLabel(self.frame_settings, text="Resize Mode", text_color="#333333", font=ctk.CTkFont(size=14)).grid(row=len(settings_fields)+1, column=0, sticky="w", padx=40, pady=12)
        ctk.CTkOptionMenu(self.frame_settings, values=["fit", "crop", "stretch"], variable=self.resize_mode_var, width=300, fg_color="#F8F9FA", button_color="#E9ECEF", text_color="#333333").grid(row=len(settings_fields)+1, column=1, sticky="w", padx=20, pady=12)

        # --- 4. Log Frame ---
        self.frame_log = ctk.CTkFrame(self, corner_radius=0, fg_color="white")
        self.frame_log.grid_rowconfigure(1, weight=1)
        self.frame_log.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(self.frame_log, text="Console Log", font=ctk.CTkFont(size=22, weight="bold"), text_color="#1E1E1E").grid(row=0, column=0, sticky="w", padx=40, pady=(40, 20))
        
        self.log_text = ctk.CTkTextbox(self.frame_log, font=("Cascadia Code", 13), fg_color="#1E1E2E", text_color="#CDD6F4", corner_radius=10)
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=40, pady=(0, 40))

        # Register Frames
        self.frames["convert"] = self.frame_convert
        self.frames["settings"] = self.frame_settings
        self.frames["log"] = self.frame_log
        
        # Show default frame
        self.select_frame("convert")

    def select_frame(self, name):
        # Update button highlights (Active styling: Red text + light red bg)
        active_fg = "#FFF0F0"
        active_tc = "#FF4D4F"
        inactive_fg = "transparent"
        inactive_tc = "#333333"

        self.btn_nav_convert.configure(fg_color=active_fg if name == "convert" else inactive_fg, text_color=active_tc if name == "convert" else inactive_tc)
        self.btn_nav_settings.configure(fg_color=active_fg if name == "settings" else inactive_fg, text_color=active_tc if name == "settings" else inactive_tc)
        self.btn_nav_log.configure(fg_color=active_fg if name == "log" else inactive_fg, text_color=active_tc if name == "log" else inactive_tc)
        
        # Toggle frame visibility
        for f_name, frame in self.frames.items():
            if f_name == name:
                frame.grid(row=0, column=1, sticky="nsew")
            else:
                frame.grid_forget()

    def _on_drop(self, event):
        files = self.drop_area.tk.splitlist(event.data)
        if files:
            self._set_input_file(files[0])

    def _browse_input(self):
        path = filedialog.askopenfilename(
            title="Select input MP4",
            filetypes=(("MP4 files", "*.mp4"), ("Video files", "*.mp4 *.mov *.avi"), ("All files", "*.*")),
        )
        if path:
            self._set_input_file(path)

    def _set_input_file(self, path):
        self.input_file = path
        base, _ = os.path.splitext(path)
        self.output_file = base + OUTPUT_SUFFIX
        
        # Hide the big central prompt container and show the item card
        self.drop_center_ui.grid_forget()
        self.item_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=20)
        self.lbl_filename.configure(text=f"🎥 {os.path.basename(path)}")
        
        # Reset progress UI
        self.progress.grid_forget()
        self.lbl_status.grid_forget()
        self.progress.set(0)
        self.lbl_status.configure(text="Ready", text_color="#6C757D")
        self.btn_start_convert.configure(state="normal", text="Convert", fg_color="#FF4D4F", hover_color="#E03131", command=self._start_convert)

    def _validate_inputs(self):
        if not self.input_file or not os.path.isfile(self.input_file):
            raise ValueError("Input file does not exist.")
            
        try:
            w = int(self.width_var.get())
            h = int(self.height_var.get())
            fps = int(self.fps_var.get())
            q = int(self.quality_var.get())
            mf = int(self.max_frame_kb_var.get())
            mq = int(self.min_quality_var.get())
        except ValueError:
            raise ValueError("All settings fields must contain valid numbers.")
            
        md = self.max_duration_var.get().strip()
        ms = self.max_size_var.get().strip()
        
        md = float(md) if md else None
        ms = int(ms) if ms else None

        return {
            "input_path": self.input_file,
            "output_path": self.output_file,
            "target_w": w, "target_h": h, "fps": fps, "quality": q,
            "resize_mode": self.resize_mode_var.get(),
            "max_frame_kb": mf, "min_quality": mq,
            "max_duration": md, "max_size_kb": ms
        }

    def _start_convert(self):
        if self.worker and self.worker.is_alive():
            return
            
        try:
            params = self._validate_inputs()
        except ValueError as e:
            messagebox.showerror(APP_TITLE, str(e))
            return
            
        # Update UI state for converting
        self.log_text.delete("1.0", "end")
        self.btn_start_convert.configure(state="disabled", text="Converting...", fg_color="#ADB5BD", hover_color="#ADB5BD")
        
        self.progress.grid(row=2, column=0, columnspan=3, sticky="ew", padx=20, pady=(10, 5))
        self.lbl_status.grid(row=3, column=0, columnspan=3, sticky="w", padx=20, pady=(0, 20))
        self.lbl_status.configure(text="Converting... 0%", text_color="#107C10")
        self.progress.set(0)
        
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
            params["input_path"], "-o", params["output_path"],
            "-W", str(params["target_w"]), "-H", str(params["target_h"]),
            "-f", str(params["fps"]), "-q", str(params["quality"]),
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

        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

        try:
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                errors="replace", creationflags=creationflags,
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
                    match = PROGRESS_RE.search(payload)
                    if match:
                        pct = int(match.group(1))
                        self.progress.set(pct / 100.0)
                        self.lbl_status.configure(text=f"Converting... {pct}%")
                    self.log_text.insert("end", payload)
                    self.log_text.see("end")
                elif kind == "done":
                    if payload:
                        self.progress.set(1.0)
                        self.lbl_status.configure(text="Conversion Completed!", text_color="#107C10")
                        self.btn_start_convert.configure(state="normal", text="Open Folder", fg_color="#107C10", hover_color="#0B5A0B", command=self._open_folder)
                    else:
                        self.lbl_status.configure(text="Failed! Check Log.", text_color="#D13438")
                        self.btn_start_convert.configure(state="normal", text="Retry", fg_color="#FF4D4F", hover_color="#E03131", command=self._start_convert)
        except queue.Empty:
            pass
        self.after(100, self._drain_log_queue)
        
    def _open_folder(self):
        if self.output_file:
            folder = os.path.dirname(self.output_file)
            if folder and os.path.isdir(folder):
                subprocess.Popen(["explorer", folder])
        self.btn_start_convert.configure(text="Convert", fg_color="#FF4D4F", hover_color="#E03131", command=self._start_convert)

if __name__ == "__main__":
    app = ConverterApp()
    app.mainloop()
