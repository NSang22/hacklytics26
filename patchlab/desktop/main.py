"""
PatchLab Desktop Capture Agent — tkinter GUI for the Stage 1 data collection.

Provides a unified control panel for:
  • Screen capture (configurable FPS: 1, 2, 3, custom up to 30)
  • Webcam recording + MediaPipe live emotion detection
  • Apple Watch BLE connection (HR/HRV streaming)
  • Real-time data preview (emotions, HR, chunk upload status)
  • Auto-chunking and async upload to the PatchLab backend
"""

from __future__ import annotations

import os
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Dict, List, Optional
from PIL import Image, ImageTk

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from screen_capture import ScreenCapture
from webcam_capture import WebcamCapture, EmotionReading
from watch_ble import WatchBLE, WatchReading as WatchBLEReading
from chunk_uploader import ChunkUploader
from face_analyzer import FaceAnalyzer
from gaze_calibration import GazeCalibrationWindow
from face_calibration import FaceCalibrationWindow

import cv2


# ── Color palette (matches webapp) ──────────────────────────
BG = "#0f172a"
BG2 = "#1e293b"
SURFACE = "#334155"
TEXT = "#f1f5f9"
MUTED = "#94a3b8"
GREEN = "#22c55e"
RED = "#ef4444"
BLUE = "#3b82f6"
AMBER = "#f59e0b"
PURPLE = "#8b5cf6"


class PatchLabDesktopApp:
    """Main application window for the PatchLab Desktop Capture Agent."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("PatchLab — Desktop Capture Agent")
        self.root.geometry("1320x860")
        self.root.minsize(1100, 700)
        self.root.configure(bg=BG)
        self.root.resizable(True, True)

        # ── State ───────────────────────────────────────────
        self.recording = False
        self.session_id = ""
        self.project_id = ""
        self.backend_url = "http://localhost:8000"

        # Modules
        self.screen_cap: Optional[ScreenCapture] = None
        self.webcam_cap: Optional[WebcamCapture] = None
        self.watch_ble: Optional[WatchBLE] = None
        self.uploader: Optional[ChunkUploader] = None
        self.face_analyzer: FaceAnalyzer = FaceAnalyzer()

        # Live data
        self._latest_emotion: Optional[Dict] = None
        self._latest_hr: Optional[Dict] = None
        self._log_messages: List[str] = []
        self._chunks_sent = 0
        self._last_screen_seq: int = -1  # track last displayed screen frame

        self._build_ui()
        self._start_previews()
        self._update_loop()

    def run(self) -> None:
        """Start the tkinter main loop."""
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    # ═══════════════════════════════════════════════════════
    # UI CONSTRUCTION
    # ═══════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        # ── Styles ──────────────────────────────────────────
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 11))
        style.configure("TButton", font=("Segoe UI", 11, "bold"), padding=8)
        style.configure("Header.TLabel", font=("Segoe UI", 22, "bold"), foreground=TEXT, background=BG)
        style.configure("Sub.TLabel", font=("Segoe UI", 11), foreground=MUTED, background=BG)
        style.configure("Card.TFrame", background=BG2)
        style.configure("Card.TLabel", background=BG2, foreground=TEXT, font=("Segoe UI", 11))
        style.configure("CardMuted.TLabel", background=BG2, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("SectionTitle.TLabel", background=BG2, foreground=TEXT, font=("Segoe UI", 13, "bold"))
        style.configure("Green.TLabel", background=BG2, foreground=GREEN, font=("Segoe UI", 11, "bold"))
        style.configure("Red.TLabel", background=BG2, foreground=RED, font=("Segoe UI", 11, "bold"))
        style.configure("Blue.TLabel", background=BG2, foreground=BLUE, font=("Segoe UI", 11, "bold"))
        style.configure("Amber.TLabel", background=BG2, foreground=AMBER, font=("Segoe UI", 11, "bold"))
        style.configure("Value.TLabel", background=BG2, foreground=TEXT, font=("Segoe UI", 18, "bold"))
        style.configure("Big.TButton", font=("Segoe UI", 14, "bold"), padding=12)

        # ── Top bar: title + status + record buttons ────────
        topbar = ttk.Frame(self.root, style="TFrame")
        topbar.pack(fill="x", padx=20, pady=(14, 6))

        ttk.Label(topbar, text="🎯  PatchLab Desktop Agent", style="Header.TLabel").pack(side="left")

        # Record buttons on the right of the header bar
        btn_right = ttk.Frame(topbar, style="TFrame")
        btn_right.pack(side="right")

        self.stop_btn = tk.Button(
            btn_right, text="⏹  STOP", font=("Segoe UI", 13, "bold"),
            bg=RED, fg="white", activebackground="#dc2626", relief="flat",
            padx=20, pady=8, command=self._stop_recording, state="disabled",
        )
        self.stop_btn.pack(side="right", padx=(6, 0))

        self.start_btn = tk.Button(
            btn_right, text="▶  START RECORDING", font=("Segoe UI", 13, "bold"),
            bg=GREEN, fg="white", activebackground="#16a34a", relief="flat",
            padx=20, pady=8, command=self._start_recording,
        )
        self.start_btn.pack(side="right", padx=(0, 6))

        self.status_label = ttk.Label(topbar, text="● Idle", style="Sub.TLabel")
        self.status_label.pack(side="right", padx=16)

        # ── Divider ─────────────────────────────────────────
        div = tk.Frame(self.root, bg=SURFACE, height=1)
        div.pack(fill="x", padx=0, pady=(0, 0))

        # ── Scrollable body ──────────────────────────────────
        body_outer = ttk.Frame(self.root, style="TFrame")
        body_outer.pack(fill="both", expand=True)

        self._main_canvas = tk.Canvas(body_outer, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(body_outer, orient="vertical", command=self._main_canvas.yview)
        self._main_canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self._main_canvas.pack(side="left", fill="both", expand=True)

        self.scroll_frame = ttk.Frame(self._main_canvas, style="TFrame")
        self._canvas_win = self._main_canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")

        # Keep scroll_frame width in sync with canvas width
        def _on_canvas_resize(event):
            self._main_canvas.itemconfig(self._canvas_win, width=event.width)
        self._main_canvas.bind("<Configure>", _on_canvas_resize)

        self.scroll_frame.bind(
            "<Configure>",
            lambda e: self._main_canvas.configure(scrollregion=self._main_canvas.bbox("all")),
        )

        # Mousewheel scrolling
        def _on_mousewheel(event):
            self._main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self._main_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # ── Two-column layout ────────────────────────────────
        # Left column (~440px) = controls; Right column (flex) = live data
        self.scroll_frame.columnconfigure(0, weight=0, minsize=440)
        self.scroll_frame.columnconfigure(1, weight=1, minsize=460)
        self.scroll_frame.rowconfigure(0, weight=1)

        left_col = ttk.Frame(self.scroll_frame, style="TFrame")
        left_col.grid(row=0, column=0, sticky="nsew", padx=(16, 8), pady=12)

        right_col = ttk.Frame(self.scroll_frame, style="TFrame")
        right_col.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=12)

        # ════════════════════════════════════════════════════
        # LEFT COLUMN
        # ════════════════════════════════════════════════════

        # ── Connection Card ──────────────────────────────────
        conn_card = self._make_card(left_col, "🔌 Backend Connection")

        row1 = ttk.Frame(conn_card, style="Card.TFrame")
        row1.pack(fill="x", pady=4)
        ttk.Label(row1, text="Backend URL:", style="Card.TLabel", width=14).pack(side="left")
        self.url_var = tk.StringVar(value=self.backend_url)
        ttk.Entry(row1, textvariable=self.url_var, width=28).pack(side="left", padx=8, fill="x", expand=True)

        row2 = ttk.Frame(conn_card, style="Card.TFrame")
        row2.pack(fill="x", pady=4)
        ttk.Label(row2, text="Project ID:", style="Card.TLabel", width=14).pack(side="left")
        self.project_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.project_var, width=28).pack(side="left", padx=8, fill="x", expand=True)

        row3 = ttk.Frame(conn_card, style="Card.TFrame")
        row3.pack(fill="x", pady=4)
        ttk.Label(row3, text="Tester Name:", style="Card.TLabel", width=14).pack(side="left")
        self.tester_var = tk.StringVar(value="desktop_tester")
        ttk.Entry(row3, textvariable=self.tester_var, width=28).pack(side="left", padx=8, fill="x", expand=True)

        conn_btns = ttk.Frame(conn_card, style="Card.TFrame")
        conn_btns.pack(fill="x", pady=(6, 2))
        ttk.Button(conn_btns, text="🔍 Test Connection", command=self._test_connection).pack(side="left")
        self.conn_status = ttk.Label(conn_btns, text="Not connected", style="CardMuted.TLabel")
        self.conn_status.pack(side="left", padx=12)

        # ── Screen Capture Card ──────────────────────────────
        screen_card = self._make_card(left_col, "🖥️ Screen Capture")

        fps_row = ttk.Frame(screen_card, style="Card.TFrame")
        fps_row.pack(fill="x", pady=4)
        ttk.Label(fps_row, text="FPS:", style="Card.TLabel", width=14).pack(side="left")
        self.fps_var = tk.IntVar(value=3)
        for fps_val in [1, 2, 3]:
            ttk.Radiobutton(fps_row, text=str(fps_val), variable=self.fps_var, value=fps_val,
                            command=self._on_fps_change).pack(side="left", padx=4)
        ttk.Label(fps_row, text="Custom:", style="Card.TLabel").pack(side="left", padx=(10, 4))
        self.custom_fps_var = tk.StringVar(value="")
        ce = ttk.Entry(fps_row, textvariable=self.custom_fps_var, width=5)
        ce.pack(side="left")
        ce.bind("<FocusIn>", lambda e: self.fps_var.set(0))
        ce.bind("<Return>", lambda e: self._on_fps_change())

        mon_row = ttk.Frame(screen_card, style="Card.TFrame")
        mon_row.pack(fill="x", pady=4)
        ttk.Label(mon_row, text="Monitor:", style="Card.TLabel", width=14).pack(side="left")
        self.monitor_var = tk.IntVar(value=1)
        self.monitor_combo = ttk.Combobox(mon_row, state="readonly", width=25)
        self.monitor_combo.pack(side="left", padx=8)
        self._refresh_monitors()
        self.monitor_combo.bind("<<ComboboxSelected>>", self._on_monitor_select)

        chunk_row = ttk.Frame(screen_card, style="Card.TFrame")
        chunk_row.pack(fill="x", pady=4)
        ttk.Label(chunk_row, text="Chunk:", style="Card.TLabel", width=14).pack(side="left")
        self.chunk_dur_var = tk.IntVar(value=10)
        ttk.Scale(chunk_row, from_=5, to=30, variable=self.chunk_dur_var,
                  orient="horizontal", length=160).pack(side="left", padx=8)
        self.chunk_dur_label = ttk.Label(chunk_row, text="10s", style="Card.TLabel")
        self.chunk_dur_label.pack(side="left")

        res_row = ttk.Frame(screen_card, style="Card.TFrame")
        res_row.pack(fill="x", pady=4)
        ttk.Label(res_row, text="Resolution:", style="Card.TLabel", width=14).pack(side="left")
        self.resolution_var = tk.StringVar(value="native")
        for lbl, val in [("Native", "native"), ("720p", "1280x720"), ("540p", "960x540")]:
            ttk.Radiobutton(res_row, text=lbl, variable=self.resolution_var, value=val,
                            command=self._on_resolution_change).pack(side="left", padx=4)

        # ── Camera Settings Card ─────────────────────────────
        cam_card = self._make_card(left_col, "📷 Camera Settings")

        cam_row = ttk.Frame(cam_card, style="Card.TFrame")
        cam_row.pack(fill="x", pady=4)
        ttk.Label(cam_row, text="Camera:", style="Card.TLabel", width=14).pack(side="left")
        self.camera_combo = ttk.Combobox(cam_row, state="readonly", width=22)
        self.camera_combo.pack(side="left", padx=8)
        self.camera_combo.bind("<<ComboboxSelected>>", self._on_camera_change)
        ttk.Button(cam_row, text="🔄", command=self._refresh_cameras, width=3).pack(side="left")
        self._refresh_cameras()

        # Gaze calibration row
        gaze_row = ttk.Frame(cam_card, style="Card.TFrame")
        gaze_row.pack(fill="x", pady=6)
        ttk.Button(gaze_row, text="🎯 Calibrate Gaze", command=self._calibrate_gaze).pack(side="left")
        self.gaze_status = ttk.Label(gaze_row, text="Not calibrated", style="CardMuted.TLabel")
        self.gaze_status.pack(side="left", padx=12)

        # Face calibration row
        face_cal_row = ttk.Frame(cam_card, style="Card.TFrame")
        face_cal_row.pack(fill="x", pady=6)
        ttk.Button(face_cal_row, text="😊 Calibrate Face", command=self._calibrate_face).pack(side="left")
        self.face_cal_status = ttk.Label(face_cal_row, text="Not calibrated", style="CardMuted.TLabel")
        self.face_cal_status.pack(side="left", padx=12)

        # Head pose row
        pose_row = ttk.Frame(cam_card, style="Card.TFrame")
        pose_row.pack(fill="x", pady=2)
        ttk.Label(pose_row, text="Head Pose:", style="Card.TLabel", width=14).pack(side="left")
        self.head_pose_label = ttk.Label(pose_row, text="P:—  Y:—  R:—", style="CardMuted.TLabel")
        self.head_pose_label.pack(side="left", padx=8)

        # ── Apple Watch Card ─────────────────────────────────
        watch_card = self._make_card(left_col, "⌚ Apple Watch BLE")

        watch_row = ttk.Frame(watch_card, style="Card.TFrame")
        watch_row.pack(fill="x", pady=4)
        ttk.Label(watch_row, text="Device:", style="Card.TLabel", width=14).pack(side="left")
        self.watch_combo = ttk.Combobox(watch_row, state="readonly", width=20)
        self.watch_combo.pack(side="left", padx=8)
        ttk.Button(watch_row, text="🔍", command=self._scan_ble, width=3).pack(side="left", padx=2)
        self.ble_connect_btn = ttk.Button(watch_row, text="▶ Connect", command=self._connect_ble)
        self.ble_connect_btn.pack(side="left", padx=4)
        self.ble_disconnect_btn = ttk.Button(watch_row, text="⏹ Disc.", command=self._disconnect_ble, state="disabled")
        self.ble_disconnect_btn.pack(side="left", padx=2)

        hr_row = ttk.Frame(watch_card, style="Card.TFrame")
        hr_row.pack(fill="x", pady=10)

        # HR block
        hr_block = ttk.Frame(hr_row, style="Card.TFrame")
        hr_block.pack(side="left", padx=(0, 24))
        self.hr_value = ttk.Label(hr_block, text="—", style="Value.TLabel")
        self.hr_value.pack()
        ttk.Label(hr_block, text="BPM  ·  Heart Rate", style="CardMuted.TLabel").pack()

        # HRV block
        hrv_block = ttk.Frame(hr_row, style="Card.TFrame")
        hrv_block.pack(side="left")
        self.hrv_value = ttk.Label(hrv_block, text="—", style="Value.TLabel")
        self.hrv_value.pack()
        ttk.Label(hrv_block, text="ms  ·  HRV (RMSSD)", style="CardMuted.TLabel").pack()

        self.watch_status = ttk.Label(watch_card, text="Not connected", style="CardMuted.TLabel")
        self.watch_status.pack(anchor="w", pady=(4, 0))

        # ── Upload Stats Card ────────────────────────────────
        stats_card = self._make_card(left_col, "📤 Upload Status")

        stats_grid = ttk.Frame(stats_card, style="Card.TFrame")
        stats_grid.pack(fill="x", pady=6)
        stats_grid.columnconfigure((0, 1, 2), weight=1)

        for col, (attr, label) in enumerate([
            ("stat_chunks", "Chunks"), ("stat_emotions", "Emotions"), ("stat_watch", "Watch"),
        ]):
            val_lbl = ttk.Label(stats_grid, text="0", style="Value.TLabel")
            val_lbl.grid(row=0, column=col, pady=(0, 2))
            setattr(self, attr, val_lbl)
            ttk.Label(stats_grid, text=label, style="CardMuted.TLabel").grid(row=1, column=col)

        self.stat_session = ttk.Label(stats_card, text="Session: —", style="CardMuted.TLabel")
        self.stat_session.pack(anchor="w", pady=(6, 0))

        # ════════════════════════════════════════════════════
        # RIGHT COLUMN
        # ════════════════════════════════════════════════════

        # ── Live Camera Preview ──────────────────────────────
        livecam_card = self._make_card(right_col, "📷 Live Camera Feed")

        self.cam_canvas = tk.Canvas(
            livecam_card, width=320, height=240,
            bg="#0a0a0a", highlightthickness=1, highlightbackground=SURFACE,
        )
        self.cam_canvas.pack(pady=(0, 6))
        self.cam_canvas.create_text(160, 120, text="Camera off", fill=MUTED, font=("Segoe UI", 11))
        self._cam_photo = None

        # ── Emotion Bars ─────────────────────────────────────
        emo_card = self._make_card(right_col, "😶 Face Analysis — Emotions")

        self._emotion_labels = {}
        for em in ["engagement", "delight", "surprise", "frustration", "confusion", "boredom"]:
            em_row = ttk.Frame(emo_card, style="Card.TFrame")
            em_row.pack(fill="x", pady=3)
            ttk.Label(em_row, text=f"{em.capitalize()}:", style="Card.TLabel", width=14).pack(side="left")
            bar = tk.Canvas(em_row, height=16, bg=SURFACE, highlightthickness=0)
            bar.pack(side="left", padx=6, fill="x", expand=True)
            val_label = ttk.Label(em_row, text="—", style="Card.TLabel", width=6)
            val_label.pack(side="right")
            self._emotion_labels[em] = (bar, val_label)

        # ── Gaze Visualizer ──────────────────────────────────
        gaze_card = self._make_card(right_col, "👁️ Gaze Tracking")

        gaze_inner = ttk.Frame(gaze_card, style="Card.TFrame")
        gaze_inner.pack(fill="x")

        self.gaze_canvas = tk.Canvas(
            gaze_inner, width=200, height=130, bg="#0a0a0a",
            highlightthickness=1, highlightbackground=SURFACE,
        )
        self.gaze_canvas.pack(side="left", padx=(0, 16), pady=4)
        self.gaze_canvas.create_text(100, 65, text="—", fill=MUTED, font=("Segoe UI", 9))
        self._gaze_photo = None

        # Screen preview in gaze card (side by side with gaze)
        screen_right = ttk.Frame(gaze_inner, style="Card.TFrame")
        screen_right.pack(side="left", fill="both", expand=True)
        ttk.Label(screen_right, text="Screen Preview:", style="CardMuted.TLabel").pack(anchor="w")
        self.screen_canvas = tk.Canvas(
            screen_right, width=320, height=130,
            bg="#0a0a0a", highlightthickness=1, highlightbackground=SURFACE,
        )
        self.screen_canvas.pack(anchor="w", pady=(4, 0))
        self.screen_canvas.create_text(160, 65, text="No capture yet", fill=MUTED, font=("Segoe UI", 10))
        self._screen_photo = None

        # ── Activity Log ─────────────────────────────────────
        log_card = self._make_card(right_col, "📝 Activity Log")
        self.log_text = tk.Text(
            log_card, height=9, bg=BG, fg=MUTED, font=("Courier New", 10),
            wrap="word", state="disabled", borderwidth=0, insertbackground=TEXT,
        )
        self.log_text.pack(fill="both", expand=True, pady=4)

    def _make_card(self, parent: ttk.Frame, title: str) -> ttk.Frame:
        """Create a styled card with title."""
        container = ttk.Frame(parent, style="Card.TFrame")
        container.pack(fill="x", pady=6, padx=4, ipady=8, ipadx=12)

        ttk.Label(container, text=title, font=("Segoe UI", 13, "bold"),
                  background=BG2, foreground=TEXT).pack(anchor="w", padx=4, pady=(4, 8))

        return container

    # ═══════════════════════════════════════════════════════
    # PREVIEW (runs on app launch, independent of recording)
    # ═══════════════════════════════════════════════════════

    def _start_previews(self) -> None:
        """Start screen + webcam previews immediately on launch."""
        # Screen preview
        fps = self._get_fps()
        res = self._get_resolution()
        mon = self.monitor_var.get()
        self.screen_cap = ScreenCapture(
            fps=fps, monitor_index=mon, resolution=res,
        )
        self.screen_cap.start_preview()
        self._log(f"Screen preview started (FPS={fps}, monitor={mon})")

        # Webcam preview starts once camera scan finishes (in _apply_cameras)

    # ═══════════════════════════════════════════════════════
    # ACTIONS
    # ═══════════════════════════════════════════════════════

    def _test_connection(self) -> None:
        """Test backend connection."""
        self.backend_url = self.url_var.get().strip()
        uploader = ChunkUploader(backend_url=self.backend_url)
        if uploader.check_backend():
            self.conn_status.configure(text="✅ Connected to backend", style="Green.TLabel")
            self._log("Backend connected: " + self.backend_url)
        else:
            self.conn_status.configure(text="❌ Cannot reach backend", style="Red.TLabel")
            self._log("Backend connection failed")

    def _refresh_monitors(self) -> None:
        """Refresh available monitor list."""
        try:
            cap = ScreenCapture()
            monitors = cap.get_monitors()
            labels = [m["label"] for m in monitors]
            self.monitor_combo["values"] = labels
            if labels:
                self.monitor_combo.current(min(1, len(labels) - 1))
                self.monitor_var.set(min(1, len(monitors) - 1))
        except Exception as e:
            self._log(f"Monitor scan error: {e}")

    def _on_monitor_select(self, event) -> None:
        idx = self.monitor_combo.current()
        self.monitor_var.set(idx)
        if self.screen_cap and self.screen_cap.is_running:
            self.screen_cap.update_settings(monitor_index=idx)
            self._log(f"Monitor changed to {idx}")

    def _on_fps_change(self) -> None:
        """Called when FPS radio button or custom entry changes."""
        fps = self._get_fps()
        if self.screen_cap and self.screen_cap.is_running:
            self.screen_cap.update_settings(fps=fps)
            self._log(f"FPS changed to {fps}")

    def _on_resolution_change(self) -> None:
        """Called when resolution radio button changes."""
        res = self._get_resolution()
        if self.screen_cap and self.screen_cap.is_running:
            self.screen_cap.update_settings(resolution=res)
            self._log(f"Resolution changed to {res or 'native'}")

    def _on_camera_change(self, event=None) -> None:
        """Called when camera combobox selection changes. Restarts webcam preview."""
        cam_idx = self.camera_combo.current()
        if cam_idx < 0:
            return
        # Stop existing webcam if running
        if self.webcam_cap and self.webcam_cap.is_running:
            self.webcam_cap.stop()
        # Start new webcam preview
        self.webcam_cap = WebcamCapture(
            camera_index=cam_idx,
            face_analyzer=self.face_analyzer,
        )
        self.webcam_cap.start(
            on_emotion=self._on_emotion_reading,
            record_video=False,
        )
        self._log(f"Camera switched to index {cam_idx}")

    def _refresh_cameras(self) -> None:
        """Refresh available camera list in background thread."""
        self.camera_combo["values"] = ["Scanning..."]
        self.camera_combo.current(0)

        def _do_scan():
            try:
                cameras = WebcamCapture.list_cameras()
                labels = [c["label"] for c in cameras]
            except Exception as e:
                self._log(f"Camera scan error: {e}")
                labels = []
            self.root.after(0, lambda: self._apply_cameras(labels))

        threading.Thread(target=_do_scan, daemon=True).start()

    def _apply_cameras(self, labels: list) -> None:
        self.camera_combo["values"] = labels or ["No cameras found"]
        if labels:
            self.camera_combo.current(0)
            # Auto-start webcam preview when cameras found
            self._on_camera_change()
        else:
            self.camera_combo.set("No cameras found")

    def _connect_ble(self) -> None:
        """Connect to the selected BLE device (independent of recording)."""
        if self.watch_ble and self.watch_ble.is_running:
            self._log("BLE already connected")
            return

        device_addr = None
        if hasattr(self, "_ble_devices") and self._ble_devices:
            idx = self.watch_combo.current()
            if idx >= 0 and idx < len(self._ble_devices):
                device_addr = self._ble_devices[idx].get("address")

        if device_addr is None:
            self._log("No BLE device selected — will scan automatically")

        self.watch_ble = WatchBLE()
        self.watch_ble.start(
            on_reading=self._on_watch_reading,
            device_address=device_addr,
        )
        self.watch_status.configure(text="Connecting...")
        self.ble_connect_btn.configure(state="disabled")
        self.ble_disconnect_btn.configure(state="normal")
        self._log(f"BLE connecting to {device_addr or 'auto-scan'}...")

        # Poll connection status
        def _check_connected():
            if self.watch_ble and self.watch_ble.connected:
                name = self.watch_ble.device_name or "HR Device"
                self.watch_status.configure(text=f"Connected: {name}")
                self._log(f"BLE connected to {name}")
            elif self.watch_ble and self.watch_ble.is_running:
                self.root.after(500, _check_connected)
            else:
                self.watch_status.configure(text="Connection failed")
                self.ble_connect_btn.configure(state="normal")
                self.ble_disconnect_btn.configure(state="disabled")
        self.root.after(1000, _check_connected)

    def _disconnect_ble(self) -> None:
        """Disconnect from BLE device."""
        if self.watch_ble:
            self.watch_ble.stop()
            self.watch_ble = None
        self.watch_status.configure(text="Disconnected")
        self.hr_value.configure(text="—")
        self.hrv_value.configure(text="—")
        self.ble_connect_btn.configure(state="normal")
        self.ble_disconnect_btn.configure(state="disabled")
        self._latest_hr = None
        self._log("BLE disconnected")

    def _scan_ble(self) -> None:
        """Scan for BLE devices."""
        self.watch_status.configure(text="Scanning...")
        self._log("Scanning for BLE devices...")

        def _do_scan():
            import asyncio
            loop = asyncio.new_event_loop()
            ble = WatchBLE()
            try:
                devices = loop.run_until_complete(ble.scan_devices(timeout=8.0))
            except Exception:
                devices = []
            finally:
                loop.close()

            if devices:
                labels = []
                for d in devices:
                    prefix = "❤️" if d.get("has_hr_service") else "📡"
                    rssi = d.get("rssi", "?")
                    labels.append(f"{prefix} {d['name']} ({d['address']}) [{rssi}dB]")
                self._ble_devices = devices
            else:
                labels = ["No watch found - Connect your Apple Watch"]
                self._ble_devices = []

            self.root.after(0, lambda: self._update_ble_list(labels))

        threading.Thread(target=_do_scan, daemon=True).start()

    def _update_ble_list(self, labels: List[str]) -> None:
        self.watch_combo["values"] = labels
        if labels:
            self.watch_combo.current(0)
        self.watch_status.configure(text=f"Found {len(labels)} device(s)")
        self._log(f"BLE scan: found {len(labels)} device(s)")

    def _get_fps(self) -> int:
        """Get the selected FPS value."""
        fps_val = self.fps_var.get()
        if fps_val == 0:
            # Custom value
            try:
                return max(1, min(30, int(self.custom_fps_var.get())))
            except ValueError:
                return 3
        return fps_val

    def _get_resolution(self):
        """Parse resolution setting."""
        val = self.resolution_var.get()
        if val == "native":
            return None
        try:
            w, h = val.split("x")
            return (int(w), int(h))
        except Exception:
            return None

    # ── Recording Control ───────────────────────────────────

    def _start_recording(self) -> None:
        """Upgrade live previews to recording mode + create backend session."""
        if self.recording:
            return

        self.backend_url = self.url_var.get().strip()
        self.project_id = self.project_var.get().strip()

        if not self.project_id:
            messagebox.showwarning("Missing Project", "Please enter a Project ID.")
            return

        self._log("Starting recording...")
        self.status_label.configure(text="● Starting...", foreground=AMBER)
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")

        # Read UI values on main thread
        chunk_dur = self.chunk_dur_var.get()
        tester_name = self.tester_var.get()

        threading.Thread(
            target=self._init_recording,
            args=(chunk_dur, tester_name),
            daemon=True,
        ).start()

    def _init_recording(self, chunk_dur: int, tester_name: str) -> None:
        """Create session and upgrade previews to recording (runs in thread)."""
        try:
            # 1. Create uploader and session
            self.uploader = ChunkUploader(
                backend_url=self.backend_url,
                project_id=self.project_id,
            )
            session_id = self.uploader.create_session(tester_name=tester_name)
            if not session_id:
                self.root.after(0, lambda: self._recording_error("Failed to create session"))
                return

            self.session_id = session_id
            self.root.after(0, lambda: self.stat_session.configure(text=f"Session: {session_id}"))

            self.uploader.start(
                on_upload_complete=self._on_chunk_uploaded,
                on_status_change=self._on_upload_status,
            )

            # 2. Upgrade screen preview → recording
            if self.screen_cap and self.screen_cap.is_running:
                self.screen_cap.chunk_duration_sec = float(chunk_dur)
                self.screen_cap.start(on_chunk_ready=self._on_screen_chunk)
            else:
                self._log("WARNING: Screen capture not running")

            # 3. Upgrade webcam preview → recording
            if self.webcam_cap and self.webcam_cap.is_running:
                self.webcam_cap.start_recording()
            else:
                self._log("WARNING: Webcam not running")

            # 4. BLE — reuse if already connected, otherwise start
            if not (self.watch_ble and self.watch_ble.is_running):
                device_addr = None
                if hasattr(self, "_ble_devices") and self._ble_devices:
                    idx = self.watch_combo.current()
                    if idx >= 0 and idx < len(self._ble_devices):
                        device_addr = self._ble_devices[idx].get("address")
                
                if device_addr:  # Only start if we have a real device address
                    self.watch_ble = WatchBLE()
                    self.watch_ble.start(
                        on_reading=self._on_watch_reading,
                        device_address=device_addr,
                    )
                else:
                    self._log("WARNING: No Apple Watch selected - HRV data will not be collected")
                    self._log("         To collect HRV data, scan for and select your Apple Watch")
            else:
                self._log("Reusing existing BLE connection")

            self.recording = True
            self.root.after(0, lambda: self._update_recording_ui(True))
            fps = self.screen_cap.fps if self.screen_cap else "?"
            self._log(f"Recording started — FPS={fps}, Chunk={chunk_dur}s, Session={session_id}")

        except Exception as e:
            self.root.after(0, lambda: self._recording_error(str(e)))

    def _stop_recording(self) -> None:
        """Stop recording but keep previews alive."""
        if not self.recording:
            return

        self._log("Stopping recording...")
        self.status_label.configure(text="● Stopping...", foreground=AMBER)
        self.stop_btn.configure(state="disabled")

        threading.Thread(target=self._shutdown_recording, daemon=True).start()

    def _shutdown_recording(self) -> None:
        """Stop recording on captures (keep previews) and finalize session."""
        try:
            # Downgrade screen capture: recording → preview
            if self.screen_cap:
                self.screen_cap.stop_recording()
                self._log("Screen recording stopped (preview continues)")

            # Stop webcam recording (keep camera + face analysis running)
            face_video_path = None
            if self.webcam_cap:
                face_video_path = self.webcam_cap.stop_recording()
                self._log("Webcam recording stopped (preview continues)")

            # Collect watch data but keep BLE connected
            watch_data = []
            if self.watch_ble:
                watch_data = self.watch_ble.get_all_readings()
                self._log(f"Watch data collected — {len(watch_data)} readings (BLE stays connected)")

            # Upload face video
            if face_video_path and self.uploader:
                self._log("Uploading face video...")
                self.uploader.upload_face_video(face_video_path)

            # Wait for chunk uploads to complete
            if self.uploader:
                stats = self.uploader.stop()
                self._log(f"Uploader stopped — {stats}")

                # Finalize session
                self._log("Finalizing session...")
                result = self.uploader.finalize_session()
                if result:
                    health = result.get("health_score", "?")
                    self._log(f"Session finalized! Health score: {health}")
                else:
                    self._log("Session finalization sent")

            self.recording = False
            self.root.after(0, lambda: self._update_recording_ui(False))

        except Exception as e:
            self._log(f"Stop error: {e}")
            self.recording = False
            self.root.after(0, lambda: self._update_recording_ui(False))

    # ── Data Callbacks ──────────────────────────────────────

    def _on_screen_chunk(self, video_bytes: bytes, chunk_index: int) -> None:
        """Called when a screen capture chunk is ready."""
        if self.uploader:
            self.uploader.enqueue_chunk(video_bytes, chunk_index)
            self._chunks_sent = chunk_index + 1

    def _on_emotion_reading(self, reading: EmotionReading) -> None:
        """Called at ~10 Hz with Presage emotion data."""
        data = reading.to_dict()
        self._latest_emotion = data
        if self.uploader:
            self.uploader.enqueue_emotion(data)

    def _on_watch_reading(self, reading: WatchBLEReading) -> None:
        """Called at ~1 Hz with Apple Watch HR/HRV data."""
        data = reading.to_dict()
        self._latest_hr = data
        if self.uploader:
            self.uploader.enqueue_watch(data)

    def _on_chunk_uploaded(self, chunk_index: int, success: bool) -> None:
        """Called after each chunk upload attempt."""
        pass  # Stats updated via uploader

    def _on_upload_status(self, msg: str) -> None:
        """Called with upload status messages."""
        self._log(msg)

    # ═══════════════════════════════════════════════════════
    # UI UPDATES
    # ═══════════════════════════════════════════════════════

    def _update_loop(self) -> None:
        """Periodic UI update (every 200ms)."""
        try:
            self._update_emotion_bars()
            self._update_hr_display()
            self._update_stats()
            self._update_camera_preview()
            self._update_screen_preview()
            self._update_gaze_display()
            self.chunk_dur_label.configure(text=f"{self.chunk_dur_var.get()}s")
        except Exception:
            pass
        self.root.after(200, self._update_loop)

    def _update_camera_preview(self) -> None:
        """Update the live camera feed canvas."""
        if not self.webcam_cap or not self.webcam_cap.is_running:
            return
        frame = self.webcam_cap.get_current_frame()
        if frame is None:
            return
        try:
            # Convert BGR -> RGB, resize to fit canvas
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            # Fit to 320x240 maintaining aspect ratio
            scale = min(320 / w, 240 / h)
            new_w, new_h = int(w * scale), int(h * scale)
            rgb = cv2.resize(rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)
            img = Image.fromarray(rgb)
            self._cam_photo = ImageTk.PhotoImage(img)
            self.cam_canvas.delete("all")
            # Center in canvas
            x_off = (320 - new_w) // 2
            y_off = (240 - new_h) // 2
            self.cam_canvas.create_image(x_off, y_off, anchor="nw", image=self._cam_photo)
        except Exception:
            pass

    def _update_screen_preview(self) -> None:
        """Update the screen capture thumbnail canvas only when a new frame arrives."""
        if not self.screen_cap or not self.screen_cap.is_running:
            return
        seq = self.screen_cap.frame_seq
        if seq == self._last_screen_seq:
            return  # no new frame since last redraw
        self._last_screen_seq = seq
        frame = self.screen_cap.get_latest_frame()
        if frame is None:
            return
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            # Fit to 320x130 maintaining aspect ratio
            scale = min(320 / w, 130 / h)
            new_w, new_h = int(w * scale), int(h * scale)
            rgb = cv2.resize(rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)
            img = Image.fromarray(rgb)
            self._screen_photo = ImageTk.PhotoImage(img)
            self.screen_canvas.delete("all")
            x_off = (320 - new_w) // 2
            y_off = (130 - new_h) // 2
            self.screen_canvas.create_image(x_off, y_off, anchor="nw", image=self._screen_photo)
            # Overlay actual FPS readout
            actual = self.screen_cap._actual_fps
            target = self.screen_cap.fps
            self.screen_canvas.create_text(
                318, 4, anchor="ne",
                text=f"{actual:.1f}/{target} FPS",
                fill="#00ff88", font=("Menlo", 9, "bold"),
            )
        except Exception:
            pass

    def _update_emotion_bars(self) -> None:
        """Update emotion bar visualization."""
        if not self._latest_emotion:
            return
        for em, (bar, val_label) in self._emotion_labels.items():
            val = self._latest_emotion.get(em, 0.0)
            bar_w = bar.winfo_width() or 240
            bar.delete("all")
            filled = int(val * bar_w)
            color = self._emotion_color(em)
            bar.create_rectangle(0, 0, filled, 16, fill=color, outline="")
            val_label.configure(text=f"{val:.2f}")

    def _emotion_color(self, emotion: str) -> str:
        colors = {
            "frustration": RED, "confusion": AMBER, "delight": GREEN,
            "boredom": MUTED, "surprise": BLUE, "engagement": PURPLE,
        }
        return colors.get(emotion, TEXT)

    def _update_hr_display(self) -> None:
        """Update heart rate display."""
        if not self._latest_hr:
            return
        hr = self._latest_hr.get("heart_rate", 0)
        hrv = self._latest_hr.get("hrv_rmssd", 0)
        self.hr_value.configure(text=f"{hr:.0f}")
        self.hrv_value.configure(text=f"{hrv:.1f}")

    def _update_gaze_display(self) -> None:
        """Update gaze indicator and head-pose labels."""
        if not self._latest_emotion:
            return
        # Head pose
        p = self._latest_emotion.get("head_pitch", 0)
        y = self._latest_emotion.get("head_yaw", 0)
        r = self._latest_emotion.get("head_roll", 0)
        self.head_pose_label.configure(text=f"P:{p:+.0f}°  Y:{y:+.0f}°  R:{r:+.0f}°")

        # Gaze dot on 160x100 mini-screen
        gx = self._latest_emotion.get("gaze_x", 0.5)
        gy = self._latest_emotion.get("gaze_y", 0.5)
        conf = self._latest_emotion.get("gaze_confidence", 0)
        cal = self.face_analyzer.gaze_calibrator

        self.gaze_canvas.delete("all")
        # Draw screen border
        self.gaze_canvas.create_rectangle(2, 2, 198, 128, outline=SURFACE, width=1)

        if conf > 0.5 and cal.calibrated:
            # Calibrated: gaze_x/y are screen px
            dot_x = (gx / cal.screen_w) * 196 + 2
            dot_y = (gy / cal.screen_h) * 126 + 2
        else:
            # Uncalibrated: gaze_x/y are iris ratios (0-1)
            dot_x = gx * 196 + 2
            dot_y = gy * 126 + 2

        dot_x = max(4, min(196, dot_x))
        dot_y = max(4, min(126, dot_y))
        color = GREEN if conf > 0.5 else AMBER
        self.gaze_canvas.create_oval(
            dot_x - 6, dot_y - 6, dot_x + 6, dot_y + 6,
            fill=color, outline="",
        )
        # Label
        status = "calibrated" if cal.calibrated else "raw iris ratio"
        self.gaze_canvas.create_text(
            100, 122, text=status, fill=MUTED, font=("Segoe UI", 7),
        )

    def _calibrate_gaze(self) -> None:
        """Open the 9-point gaze calibration window."""
        cam_idx = self.camera_combo.current()
        if cam_idx < 0:
            cam_idx = 0

        def _on_done(error_px: float):
            if error_px >= 0:
                self.gaze_status.configure(text=f"Calibrated ({error_px:.0f}px error)")
                self._log(f"Gaze calibrated — mean error: {error_px:.1f}px")
            else:
                self.gaze_status.configure(text="Calibration failed")
                self._log("Gaze calibration failed")

        GazeCalibrationWindow(
            master=self.root,
            face_analyzer=self.face_analyzer,
            camera_index=cam_idx,
            on_complete=_on_done,
        )
        self._log("Gaze calibration started")

    def _calibrate_face(self) -> None:
        """Open the 3-step face expression calibration window."""
        cam_idx = self.camera_combo.current()
        if cam_idx < 0:
            cam_idx = 0

        def _on_done(success: bool):
            if success:
                self.face_cal_status.configure(text="Calibrated ✓")
                self._log("Face calibration complete — per-person scaling active")
            else:
                self.face_cal_status.configure(text="Calibration failed")
                self._log("Face calibration failed")

        FaceCalibrationWindow(
            master=self.root,
            face_analyzer=self.face_analyzer,
            camera_index=cam_idx,
            on_complete=_on_done,
        )
        self._log("Face calibration started")

    def _update_stats(self) -> None:
        """Update upload stats."""
        if self.uploader:
            self.stat_chunks.configure(text=str(self.uploader.chunks_uploaded))
            self.stat_emotions.configure(text=str(self.uploader.emotion_frames_sent))
            self.stat_watch.configure(text=str(self.uploader.watch_readings_sent))

    def _update_recording_ui(self, is_recording: bool) -> None:
        """Toggle UI elements based on recording state."""
        if is_recording:
            self.status_label.configure(text="● RECORDING", foreground=RED)
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
        else:
            self.status_label.configure(text="● Idle", foreground=MUTED)
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")

    def _recording_error(self, msg: str) -> None:
        """Handle recording initialization error."""
        self._log(f"ERROR: {msg}")
        self.status_label.configure(text="● Error", foreground=RED)
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        messagebox.showerror("Recording Error", msg)

    def _log(self, msg: str) -> None:
        """Append a message to the activity log."""
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        self._log_messages.append(line)
        # Keep last 100 messages
        if len(self._log_messages) > 100:
            self._log_messages = self._log_messages[-100:]

        # Thread-safe UI update
        def _update():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", line + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

        try:
            self.root.after(0, _update)
        except Exception:
            pass

    def _on_close(self) -> None:
        """Handle window close — stop everything."""
        if self.recording:
            if not messagebox.askyesno("Recording Active", "Recording is active. Stop and exit?"):
                return
            self._shutdown_recording()
        # Stop previews
        if self.screen_cap:
            self.screen_cap.stop()
        if self.webcam_cap:
            self.webcam_cap.stop()
        if self.face_analyzer:
            self.face_analyzer.close()
        self.root.destroy()


# ── Entry point ─────────────────────────────────────────────
if __name__ == "__main__":
    app = PatchLabDesktopApp()
    app.run()
