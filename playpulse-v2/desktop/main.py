"""
PatchLab Desktop Agent - tkinter GUI for Stage 1 data collection.

Provides a unified control panel for:
  - Screen capture (configurable FPS: 1, 2, 3, custom up to 30)
  - Webcam recording + MediaPipe live emotion detection
  - Apple Watch BLE connection (HR/HRV streaming)
  - Real-time data preview (emotions, HR, chunk upload status)
  - Auto-chunking and async upload to the backend

Visual: Frutiger Aero / Apple Liquid Glass - bright, colorful, optimistic.
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

import cv2


# -- Frutiger Aero Color Palette --
BG          = "#e8f4fc"
CARD_BG     = "#ffffff"
CARD_BORDER = "#d0e8f5"
TEXT        = "#1a2b3c"
TEXT_LIGHT  = "#5a7a8f"
TEXT_MUTED  = "#8fa8b8"

BLUE   = "#2196F3"
GREEN  = "#4CAF50"
RED    = "#F44336"
YELLOW = "#FFC107"
CYAN   = "#00BCD4"
ORANGE = "#FF9800"

ACCENT_BLUE   = "#2196F3"
ACCENT_GREEN  = "#4CAF50"
ACCENT_YELLOW = "#FFC107"
ACCENT_RED    = "#F44336"
ACCENT_CYAN   = "#00BCD4"

EMOTION_COLORS = {
    "engagement": BLUE,
    "delight":    YELLOW,
    "surprise":   CYAN,
    "frustration": RED,
    "confusion":  GREEN,
    "boredom":    ORANGE,
}

FONT      = "Bahnschrift"
FONT_MONO = "Cascadia Mono"


class PatchLabApp:
    """Main application window for PatchLab Desktop Agent."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("PatchLab Desktop Agent")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)
        self.root.minsize(1100, 700)

        # Maximize on Windows
        try:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            self.root.geometry(f"{sw}x{sh}+0+0")
            self.root.update_idletasks()
            self.root.state("zoomed")
        except Exception:
            self.root.geometry("1400x900")

        # -- State --
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
        self._last_screen_seq: int = -1

        self._build_background()
        self._build_ui()
        self._start_previews()
        self._update_loop()

    def run(self) -> None:
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    # ============================================================
    # BACKGROUND (Frutiger Aero floating shapes)
    # ============================================================

    def _build_background(self) -> None:
        self._bg_canvas = tk.Canvas(self.root, highlightthickness=0, bg=BG)
        self._bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        shapes = [
            (0.08, 0.15, 220, "#90CAF9"),
            (0.85, 0.10, 180, "#A5D6A7"),
            (0.50, 0.80, 260, "#FFF9C4"),
            (0.15, 0.75, 200, "#FFCCBC"),
            (0.75, 0.55, 190, "#B2EBF2"),
            (0.35, 0.35, 150, "#C8E6C9"),
            (0.90, 0.85, 170, "#FFE0B2"),
            (0.05, 0.50, 140, "#BBDEFB"),
        ]
        def _draw_bg(event=None):
            self._bg_canvas.delete("bg_shape")
            cw = self._bg_canvas.winfo_width()
            ch = self._bg_canvas.winfo_height()
            for (xp, yp, r, color) in shapes:
                cx = int(xp * cw)
                cy = int(yp * ch)
                self._bg_canvas.create_oval(
                    cx - r, cy - r, cx + r, cy + r,
                    fill=color, outline="", stipple="gray50",
                    tags="bg_shape",
                )
        self._bg_canvas.bind("<Configure>", _draw_bg)

    # ============================================================
    # UI CONSTRUCTION
    # ============================================================

    def _build_ui(self) -> None:
        main_frame = tk.Frame(self.root, bg=BG)
        main_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        # -- Top Bar (rounded) --
        topbar_canvas = tk.Canvas(main_frame, bg=BG, highlightthickness=0, bd=0, height=72)
        topbar_canvas.pack(fill="x", padx=12, pady=(12, 4))
        topbar = tk.Frame(topbar_canvas, bg=CARD_BG, height=56, bd=0, highlightthickness=0)
        topbar.pack(fill="x", padx=14, pady=8)
        topbar.pack_propagate(False)
        def _redraw_topbar(event=None):
            w = topbar_canvas.winfo_width()
            h = topbar_canvas.winfo_height()
            if w < 2:
                return
            topbar_canvas.delete("topbg")
            self._draw_rounded_rect(topbar_canvas, 1, 1, w - 1, h - 1,
                                    radius=18, fill=CARD_BG,
                                    outline=CARD_BORDER, width=1.2,
                                    tags="topbg")
            topbar_canvas.tag_lower("topbg")
        topbar_canvas.bind("<Configure>", _redraw_topbar)

        tk.Label(
            topbar, text="PatchLab Desktop Agent",
            font=(FONT, 20, "bold"), fg=TEXT, bg=CARD_BG,
        ).pack(side="left", padx=24)

        self.status_label = tk.Label(
            topbar, text="Idle", font=(FONT, 12), fg=TEXT_LIGHT, bg=CARD_BG,
        )
        self.status_label.pack(side="left", padx=16)

        btn_frame = tk.Frame(topbar, bg=CARD_BG)
        btn_frame.pack(side="right", padx=16)

        self.stop_btn = tk.Button(
            btn_frame, text="Stop Recording",
            font=(FONT, 12, "bold"), fg="white", bg=RED,
            activebackground="#D32F2F", activeforeground="white",
            relief="flat", padx=24, pady=8, cursor="hand2",
            command=self._stop_recording, state="disabled",
            bd=0, highlightthickness=0,
        )
        self.stop_btn.pack(side="right", padx=(8, 0))

        self.start_btn = tk.Button(
            btn_frame, text="Start Recording",
            font=(FONT, 12, "bold"), fg="white", bg=BLUE,
            activebackground="#1976D2", activeforeground="white",
            relief="flat", padx=24, pady=8, cursor="hand2",
            command=self._start_recording,
            bd=0, highlightthickness=0,
        )
        self.start_btn.pack(side="right", padx=(0, 8))

        # -- Scrollable Body --
        body_outer = tk.Frame(main_frame, bg=BG)
        body_outer.pack(fill="both", expand=True, padx=0, pady=0)

        self._main_canvas = tk.Canvas(body_outer, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(body_outer, orient="vertical", command=self._main_canvas.yview)
        self._main_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._main_canvas.pack(side="left", fill="both", expand=True)

        self.scroll_frame = tk.Frame(self._main_canvas, bg=BG)
        self._canvas_win = self._main_canvas.create_window(
            (0, 0), window=self.scroll_frame, anchor="nw",
        )

        def _on_canvas_resize(event):
            self._main_canvas.itemconfig(self._canvas_win, width=event.width)
        self._main_canvas.bind("<Configure>", _on_canvas_resize)
        self.scroll_frame.bind(
            "<Configure>",
            lambda e: self._main_canvas.configure(scrollregion=self._main_canvas.bbox("all")),
        )
        def _on_mousewheel(event):
            self._main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self._main_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # -- Two-Column Layout (40/60) --
        self.scroll_frame.columnconfigure(0, weight=2, minsize=420)
        self.scroll_frame.columnconfigure(1, weight=3, minsize=500)
        self.scroll_frame.rowconfigure(0, weight=1)

        left_col = tk.Frame(self.scroll_frame, bg=BG)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)
        right_col = tk.Frame(self.scroll_frame, bg=BG)
        right_col.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=12)

        # ================================================================
        # LEFT COLUMN
        # ================================================================

        # 1. Backend Connection
        conn_card = self._make_card(left_col, "Backend Connection", ACCENT_BLUE)
        self._card_field(conn_card, "Backend URL:")
        self.url_var = tk.StringVar(value=self.backend_url)
        self._card_entry(conn_card, self.url_var)
        self._card_field(conn_card, "Project ID:")
        self.project_var = tk.StringVar()
        self._card_entry(conn_card, self.project_var)
        self._card_field(conn_card, "Tester Name:")
        self.tester_var = tk.StringVar(value="desktop_tester")
        self._card_entry(conn_card, self.tester_var)

        conn_btns = tk.Frame(conn_card, bg=CARD_BG)
        conn_btns.pack(fill="x", padx=16, pady=(4, 8))
        test_btn = tk.Button(
            conn_btns, text="Test Connection",
            font=(FONT, 10, "bold"), fg="white", bg=BLUE,
            activebackground="#1976D2", relief="flat",
            padx=16, pady=4, cursor="hand2", bd=0,
            command=self._test_connection,
        )
        test_btn.pack(side="left")
        self.conn_status = tk.Label(
            conn_btns, text="Not connected",
            font=(FONT, 10), fg=TEXT_MUTED, bg=CARD_BG,
        )
        self.conn_status.pack(side="left", padx=12)

        # 2. Screen Capture
        screen_card = self._make_card(left_col, "Screen Capture", ACCENT_GREEN)
        fps_row = tk.Frame(screen_card, bg=CARD_BG)
        fps_row.pack(fill="x", padx=16, pady=4)
        tk.Label(fps_row, text="FPS:", font=(FONT, 10, "bold"), fg=TEXT, bg=CARD_BG, width=12, anchor="w").pack(side="left")
        self.fps_var = tk.IntVar(value=3)
        for fps_val in [1, 2, 3]:
            rb = tk.Radiobutton(
                fps_row, text=str(fps_val), variable=self.fps_var, value=fps_val,
                font=(FONT, 10), fg=TEXT, bg=CARD_BG, selectcolor=CARD_BG,
                activebackground=CARD_BG, command=self._on_fps_change,
                indicatoron=True, highlightthickness=0,
            )
            rb.pack(side="left", padx=4)
        tk.Label(fps_row, text="Custom:", font=(FONT, 10), fg=TEXT_LIGHT, bg=CARD_BG).pack(side="left", padx=(10, 4))
        self.custom_fps_var = tk.StringVar(value="")
        ce = tk.Entry(fps_row, textvariable=self.custom_fps_var, width=5,
                      font=(FONT, 10), bg="#f0f7ff", fg=TEXT, relief="flat",
                      highlightbackground=CARD_BORDER, highlightthickness=1)
        ce.pack(side="left")
        ce.bind("<FocusIn>", lambda e: self.fps_var.set(0))
        ce.bind("<Return>", lambda e: self._on_fps_change())

        mon_row = tk.Frame(screen_card, bg=CARD_BG)
        mon_row.pack(fill="x", padx=16, pady=4)
        tk.Label(mon_row, text="Monitor:", font=(FONT, 10, "bold"), fg=TEXT, bg=CARD_BG, width=12, anchor="w").pack(side="left")
        self.monitor_var = tk.IntVar(value=1)
        self.monitor_combo = ttk.Combobox(mon_row, state="readonly", width=25)
        self.monitor_combo.pack(side="left", padx=8)
        self._refresh_monitors()
        self.monitor_combo.bind("<<ComboboxSelected>>", self._on_monitor_select)

        chunk_row = tk.Frame(screen_card, bg=CARD_BG)
        chunk_row.pack(fill="x", padx=16, pady=4)
        tk.Label(chunk_row, text="Chunk:", font=(FONT, 10, "bold"), fg=TEXT, bg=CARD_BG, width=12, anchor="w").pack(side="left")
        self.chunk_dur_var = tk.IntVar(value=10)
        ttk.Scale(chunk_row, from_=5, to=30, variable=self.chunk_dur_var,
                  orient="horizontal", length=160).pack(side="left", padx=8)
        self.chunk_dur_label = tk.Label(chunk_row, text="10s", font=(FONT, 10), fg=TEXT, bg=CARD_BG)
        self.chunk_dur_label.pack(side="left")

        res_row = tk.Frame(screen_card, bg=CARD_BG)
        res_row.pack(fill="x", padx=16, pady=(4, 8))
        tk.Label(res_row, text="Resolution:", font=(FONT, 10, "bold"), fg=TEXT, bg=CARD_BG, width=12, anchor="w").pack(side="left")
        self.resolution_var = tk.StringVar(value="native")
        for lbl, val in [("Native", "native"), ("720p", "1280x720"), ("540p", "960x540")]:
            rb = tk.Radiobutton(
                res_row, text=lbl, variable=self.resolution_var, value=val,
                font=(FONT, 10), fg=TEXT, bg=CARD_BG, selectcolor=CARD_BG,
                activebackground=CARD_BG, command=self._on_resolution_change,
                indicatoron=True, highlightthickness=0,
            )
            rb.pack(side="left", padx=4)

        # 3. Camera Settings
        cam_card = self._make_card(left_col, "Camera Settings", ACCENT_YELLOW)
        cam_row = tk.Frame(cam_card, bg=CARD_BG)
        cam_row.pack(fill="x", padx=16, pady=4)
        tk.Label(cam_row, text="Camera:", font=(FONT, 10, "bold"), fg=TEXT, bg=CARD_BG, width=12, anchor="w").pack(side="left")
        self.camera_combo = ttk.Combobox(cam_row, state="readonly", width=22)
        self.camera_combo.pack(side="left", padx=8)
        self.camera_combo.bind("<<ComboboxSelected>>", self._on_camera_change)
        refresh_btn = tk.Button(
            cam_row, text="Refresh", font=(FONT, 9), fg=BLUE, bg=CARD_BG,
            relief="flat", cursor="hand2", bd=0, command=self._refresh_cameras,
        )
        refresh_btn.pack(side="left", padx=4)
        self._refresh_cameras()

        gaze_row = tk.Frame(cam_card, bg=CARD_BG)
        gaze_row.pack(fill="x", padx=16, pady=6)
        cal_btn = tk.Button(
            gaze_row, text="Calibrate Gaze",
            font=(FONT, 10, "bold"), fg="white", bg=ACCENT_YELLOW,
            activebackground="#FFB300", relief="flat",
            padx=16, pady=4, cursor="hand2", bd=0,
            command=self._calibrate_gaze,
        )
        cal_btn.pack(side="left")
        self.gaze_status = tk.Label(
            gaze_row, text="Not calibrated",
            font=(FONT, 10), fg=TEXT_MUTED, bg=CARD_BG,
        )
        self.gaze_status.pack(side="left", padx=12)

        pose_row = tk.Frame(cam_card, bg=CARD_BG)
        pose_row.pack(fill="x", padx=16, pady=(2, 8))
        tk.Label(pose_row, text="Head Pose:", font=(FONT, 10, "bold"), fg=TEXT, bg=CARD_BG, width=12, anchor="w").pack(side="left")
        self.head_pose_label = tk.Label(
            pose_row, text="P:--  Y:--  R:--",
            font=(FONT, 10), fg=TEXT_MUTED, bg=CARD_BG,
        )
        self.head_pose_label.pack(side="left", padx=8)

        # 4. Apple Watch BLE
        watch_card = self._make_card(left_col, "Apple Watch BLE", ACCENT_RED)
        watch_row = tk.Frame(watch_card, bg=CARD_BG)
        watch_row.pack(fill="x", padx=16, pady=4)
        tk.Label(watch_row, text="Device:", font=(FONT, 10, "bold"), fg=TEXT, bg=CARD_BG, width=12, anchor="w").pack(side="left")
        self.watch_combo = ttk.Combobox(watch_row, state="readonly", width=20)
        self.watch_combo.pack(side="left", padx=8)
        scan_btn = tk.Button(
            watch_row, text="Scan", font=(FONT, 9, "bold"), fg="white", bg=CYAN,
            relief="flat", padx=10, pady=2, cursor="hand2", bd=0,
            command=self._scan_ble,
        )
        scan_btn.pack(side="left", padx=4)
        self.ble_connect_btn = tk.Button(
            watch_row, text="Connect", font=(FONT, 9, "bold"), fg="white", bg=GREEN,
            relief="flat", padx=10, pady=2, cursor="hand2", bd=0,
            command=self._connect_ble,
        )
        self.ble_connect_btn.pack(side="left", padx=4)
        self.ble_disconnect_btn = tk.Button(
            watch_row, text="Disconnect", font=(FONT, 9, "bold"), fg="white", bg=RED,
            relief="flat", padx=10, pady=2, cursor="hand2", bd=0, state="disabled",
            command=self._disconnect_ble,
        )
        self.ble_disconnect_btn.pack(side="left", padx=4)

        hr_row = tk.Frame(watch_card, bg=CARD_BG)
        hr_row.pack(fill="x", padx=16, pady=10)
        hr_block = tk.Frame(hr_row, bg=CARD_BG)
        hr_block.pack(side="left", padx=(0, 30))
        self.hr_value = tk.Label(hr_block, text="--", font=(FONT, 24, "bold"), fg=RED, bg=CARD_BG)
        self.hr_value.pack()
        tk.Label(hr_block, text="BPM - Heart Rate", font=(FONT, 9), fg=TEXT_MUTED, bg=CARD_BG).pack()
        hrv_block = tk.Frame(hr_row, bg=CARD_BG)
        hrv_block.pack(side="left")
        self.hrv_value = tk.Label(hrv_block, text="--", font=(FONT, 24, "bold"), fg=BLUE, bg=CARD_BG)
        self.hrv_value.pack()
        tk.Label(hrv_block, text="ms - HRV (RMSSD)", font=(FONT, 9), fg=TEXT_MUTED, bg=CARD_BG).pack()

        self.watch_status = tk.Label(
            watch_card, text="Not connected",
            font=(FONT, 10), fg=TEXT_MUTED, bg=CARD_BG,
        )
        self.watch_status.pack(anchor="w", padx=16, pady=(4, 8))

        # 5. Upload Status
        stats_card = self._make_card(left_col, "Upload Status", ACCENT_CYAN)
        stats_grid = tk.Frame(stats_card, bg=CARD_BG)
        stats_grid.pack(fill="x", padx=16, pady=6)
        stats_grid.columnconfigure((0, 1, 2), weight=1)
        for col, (attr, label, color) in enumerate([
            ("stat_chunks", "Chunks", BLUE),
            ("stat_emotions", "Emotions", GREEN),
            ("stat_watch", "Watch", ORANGE),
        ]):
            val_lbl = tk.Label(stats_grid, text="0", font=(FONT, 22, "bold"), fg=color, bg=CARD_BG)
            val_lbl.grid(row=0, column=col, pady=(0, 2))
            setattr(self, attr, val_lbl)
            tk.Label(stats_grid, text=label, font=(FONT, 9), fg=TEXT_MUTED, bg=CARD_BG).grid(row=1, column=col)
        self.stat_session = tk.Label(
            stats_card, text="Session: --",
            font=(FONT, 10), fg=TEXT_MUTED, bg=CARD_BG,
        )
        self.stat_session.pack(anchor="w", padx=16, pady=(6, 8))

        # ================================================================
        # RIGHT COLUMN
        # ================================================================

        # 1. Live Camera Feed
        livecam_card = self._make_card(right_col, "Live Camera Feed", ACCENT_BLUE)
        self.cam_canvas = tk.Canvas(
            livecam_card, width=480, height=340,
            bg="#f0f4f8", highlightthickness=0, bd=0,
        )
        self.cam_canvas.pack(padx=16, pady=(0, 12), fill="both", expand=True)
        self.cam_canvas.create_text(240, 170, text="Camera off", fill=TEXT_MUTED, font=(FONT, 12))
        self._cam_photo = None

        # 2. Face Analysis - Emotions
        emo_card = self._make_card(right_col, "Face Analysis - Emotions", ACCENT_GREEN)
        self._emotion_labels = {}
        for em in ["engagement", "delight", "surprise", "frustration", "confusion", "boredom"]:
            em_row = tk.Frame(emo_card, bg=CARD_BG)
            em_row.pack(fill="x", padx=16, pady=3)
            tk.Label(
                em_row, text=f"{em.capitalize()}:",
                font=(FONT, 10, "bold"), fg=TEXT, bg=CARD_BG, width=12, anchor="w",
            ).pack(side="left")
            bar = tk.Canvas(em_row, height=20, bg="#e8eef3", highlightthickness=0)
            bar.pack(side="left", padx=6, fill="x", expand=True)
            val_label = tk.Label(em_row, text="--", font=(FONT, 10), fg=TEXT_LIGHT, bg=CARD_BG, width=6)
            val_label.pack(side="right")
            self._emotion_labels[em] = (bar, val_label)
        tk.Frame(emo_card, bg=CARD_BG, height=8).pack()

        # 3. Gaze Tracking
        gaze_card = self._make_card(right_col, "Gaze Tracking", ACCENT_YELLOW)
        gaze_inner = tk.Frame(gaze_card, bg=CARD_BG)
        gaze_inner.pack(fill="x", padx=16, pady=(0, 12))
        self.gaze_canvas = tk.Canvas(
            gaze_inner, width=240, height=160, bg="#1a1a1a",
            highlightthickness=0, bd=0,
        )
        self.gaze_canvas.pack(side="left", padx=(0, 16), pady=4)
        self.gaze_canvas.create_text(120, 80, text="--", fill="#888", font=(FONT, 9))
        self._gaze_photo = None

        screen_right = tk.Frame(gaze_inner, bg=CARD_BG)
        screen_right.pack(side="left", fill="both", expand=True)
        tk.Label(screen_right, text="Screen Preview:", font=(FONT, 10, "bold"), fg=TEXT, bg=CARD_BG).pack(anchor="w")
        self.screen_canvas = tk.Canvas(
            screen_right, width=380, height=160,
            bg="#f0f4f8", highlightthickness=0, bd=0,
        )
        self.screen_canvas.pack(fill="both", expand=True, pady=(4, 0))
        self.screen_canvas.create_text(190, 80, text="No capture yet", fill=TEXT_MUTED, font=(FONT, 10))
        self._screen_photo = None

        # 4. Activity Log
        log_card = self._make_card(right_col, "Activity Log", ACCENT_CYAN)
        self.log_text = tk.Text(
            log_card, height=12, bg="#f8fafc", fg=TEXT_LIGHT,
            font=(FONT_MONO, 9), wrap="word", state="disabled",
            borderwidth=0, insertbackground=TEXT, relief="flat",
            padx=12, pady=8,
        )
        self.log_text.pack(fill="both", expand=True, padx=16, pady=(0, 12))

    # -- Card Helpers --

    def _make_card(self, parent, title, accent_color=BLUE):
        R = 14
        outer = tk.Frame(parent, bg=BG)
        outer.pack(fill="x", pady=6, padx=4)
        wrapper = tk.Canvas(outer, bg=BG, highlightthickness=0, bd=0)
        wrapper.pack(fill="x")
        card = tk.Frame(wrapper, bg=CARD_BG, bd=0, highlightthickness=0)
        card.pack(fill="x", padx=R, pady=R)
        tk.Label(card, text=title,
                 font=(FONT, 13, "bold"), fg=TEXT, bg=CARD_BG,
                 ).pack(anchor="w", padx=8, pady=(4, 4))
        def _redraw_card(event=None):
            w = wrapper.winfo_width()
            h = wrapper.winfo_height()
            if w < 2 or h < 2:
                return
            wrapper.delete("cardbg")
            self._draw_rounded_rect(wrapper, 1, 1, w - 1, h - 1,
                                    radius=R, fill=CARD_BG,
                                    outline=CARD_BORDER, width=1.5,
                                    tags="cardbg")
            wrapper.tag_lower("cardbg")
        wrapper.bind("<Configure>", _redraw_card)
        wrapper.after(100, _redraw_card)
        return card

    @staticmethod
    def _draw_rounded_rect(canvas, x1, y1, x2, y2, radius=14, **kwargs):
        """Draw a smooth rounded rectangle on a canvas."""
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]
        return canvas.create_polygon(points, smooth=True, **kwargs)

    def _card_field(self, card, label):
        tk.Label(card, text=label,
                 font=(FONT, 10, "bold"), fg=TEXT, bg=CARD_BG,
                 ).pack(anchor="w", padx=16, pady=(4, 0))

    def _card_entry(self, card, var):
        e = tk.Entry(card, textvariable=var, font=(FONT, 10),
                     bg="#f0f7ff", fg=TEXT, relief="flat",
                     highlightbackground=CARD_BORDER, highlightthickness=1,
                     insertbackground=TEXT)
        e.pack(fill="x", padx=16, pady=(2, 4))
        return e

    # ============================================================
    # PREVIEW
    # ============================================================

    def _start_previews(self) -> None:
        fps = self._get_fps()
        res = self._get_resolution()
        mon = self.monitor_var.get()
        self.screen_cap = ScreenCapture(fps=fps, monitor_index=mon, resolution=res)
        self.screen_cap.start_preview()
        self._log(f"Screen preview started (FPS={fps}, monitor={mon})")

    # ============================================================
    # ACTIONS
    # ============================================================

    def _test_connection(self) -> None:
        self.backend_url = self.url_var.get().strip()
        uploader = ChunkUploader(backend_url=self.backend_url)
        if uploader.check_backend():
            self.conn_status.configure(text="Connected", fg=GREEN)
            self._log("Backend connected: " + self.backend_url)
        else:
            self.conn_status.configure(text="Cannot reach backend", fg=RED)
            self._log("Backend connection failed")

    def _refresh_monitors(self) -> None:
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
        fps = self._get_fps()
        if self.screen_cap and self.screen_cap.is_running:
            self.screen_cap.update_settings(fps=fps)
            self._log(f"FPS changed to {fps}")

    def _on_resolution_change(self) -> None:
        res = self._get_resolution()
        if self.screen_cap and self.screen_cap.is_running:
            self.screen_cap.update_settings(resolution=res)
            self._log(f"Resolution changed to {res or 'native'}")

    def _on_camera_change(self, event=None) -> None:
        cam_idx = self.camera_combo.current()
        if cam_idx < 0:
            return
        if self.webcam_cap and self.webcam_cap.is_running:
            self.webcam_cap.stop()
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

    def _apply_cameras(self, labels) -> None:
        self.camera_combo["values"] = labels or ["No cameras found"]
        if labels:
            self.camera_combo.current(0)
            self._on_camera_change()
        else:
            self.camera_combo.set("No cameras found")

    def _connect_ble(self) -> None:
        if self.watch_ble and self.watch_ble.is_running:
            self._log("BLE already connected")
            return
        device_addr = None
        if hasattr(self, "_ble_devices") and self._ble_devices:
            idx = self.watch_combo.current()
            if idx >= 0 and idx < len(self._ble_devices):
                device_addr = self._ble_devices[idx].get("address")
        if device_addr is None:
            self._log("No BLE device selected -- will scan automatically")
        self.watch_ble = WatchBLE()
        self.watch_ble.start(
            on_reading=self._on_watch_reading,
            device_address=device_addr,
        )
        self.watch_status.configure(text="Connecting...", fg=YELLOW)
        self.ble_connect_btn.configure(state="disabled")
        self.ble_disconnect_btn.configure(state="normal")
        self._log(f"BLE connecting to {device_addr or 'auto-scan'}...")
        def _check_connected():
            if self.watch_ble and self.watch_ble.connected:
                name = self.watch_ble.device_name or "HR Device"
                self.watch_status.configure(text=f"Connected: {name}", fg=GREEN)
                self._log(f"BLE connected to {name}")
            elif self.watch_ble and self.watch_ble.is_running:
                self.root.after(500, _check_connected)
            else:
                self.watch_status.configure(text="Connection failed", fg=RED)
                self.ble_connect_btn.configure(state="normal")
                self.ble_disconnect_btn.configure(state="disabled")
        self.root.after(1000, _check_connected)

    def _disconnect_ble(self) -> None:
        if self.watch_ble:
            self.watch_ble.stop()
            self.watch_ble = None
        self.watch_status.configure(text="Disconnected", fg=TEXT_MUTED)
        self.hr_value.configure(text="--")
        self.hrv_value.configure(text="--")
        self.ble_connect_btn.configure(state="normal")
        self.ble_disconnect_btn.configure(state="disabled")
        self._latest_hr = None
        self._log("BLE disconnected")

    def _scan_ble(self) -> None:
        self.watch_status.configure(text="Scanning...", fg=YELLOW)
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
                    prefix = "HR" if d.get("has_hr_service") else "BLE"
                    rssi = d.get("rssi", "?")
                    labels.append(f"[{prefix}] {d['name']} ({d['address']}) [{rssi}dB]")
                self._ble_devices = devices
            else:
                labels = ["No watch found - Connect your Apple Watch"]
                self._ble_devices = []
            self.root.after(0, lambda: self._update_ble_list(labels))
        threading.Thread(target=_do_scan, daemon=True).start()

    def _update_ble_list(self, labels) -> None:
        self.watch_combo["values"] = labels
        if labels:
            self.watch_combo.current(0)
        self.watch_status.configure(text=f"Found {len(labels)} device(s)", fg=TEXT)
        self._log(f"BLE scan: found {len(labels)} device(s)")

    def _get_fps(self) -> int:
        fps_val = self.fps_var.get()
        if fps_val == 0:
            try:
                return max(1, min(30, int(self.custom_fps_var.get())))
            except ValueError:
                return 3
        return fps_val

    def _get_resolution(self):
        val = self.resolution_var.get()
        if val == "native":
            return None
        try:
            w, h = val.split("x")
            return (int(w), int(h))
        except Exception:
            return None

    # -- Recording Control --

    def _start_recording(self) -> None:
        if self.recording:
            return
        self.backend_url = self.url_var.get().strip()
        self.project_id = self.project_var.get().strip()
        if not self.project_id:
            messagebox.showwarning("Missing Project", "Please enter a Project ID.")
            return
        self._log("Starting recording...")
        self.status_label.configure(text="Starting...", fg=YELLOW)
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        chunk_dur = self.chunk_dur_var.get()
        tester_name = self.tester_var.get()
        threading.Thread(
            target=self._init_recording,
            args=(chunk_dur, tester_name),
            daemon=True,
        ).start()

    def _init_recording(self, chunk_dur, tester_name) -> None:
        try:
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
            if self.screen_cap and self.screen_cap.is_running:
                self.screen_cap.chunk_duration_sec = float(chunk_dur)
                self.screen_cap.start(on_chunk_ready=self._on_screen_chunk)
            else:
                self._log("WARNING: Screen capture not running")
            if self.webcam_cap and self.webcam_cap.is_running:
                self.webcam_cap.start_recording()
            else:
                self._log("WARNING: Webcam not running")
            if not (self.watch_ble and self.watch_ble.is_running):
                device_addr = None
                if hasattr(self, "_ble_devices") and self._ble_devices:
                    idx = self.watch_combo.current()
                    if idx >= 0 and idx < len(self._ble_devices):
                        device_addr = self._ble_devices[idx].get("address")
                if device_addr:
                    self.watch_ble = WatchBLE()
                    self.watch_ble.start(
                        on_reading=self._on_watch_reading,
                        device_address=device_addr,
                    )
                else:
                    self._log("WARNING: No Apple Watch selected - HRV data will not be collected")
            else:
                self._log("Reusing existing BLE connection")
            self.recording = True
            self.root.after(0, lambda: self._update_recording_ui(True))
            fps = self.screen_cap.fps if self.screen_cap else "?"
            self._log(f"Recording started -- FPS={fps}, Chunk={chunk_dur}s, Session={session_id}")
        except Exception as e:
            self.root.after(0, lambda: self._recording_error(str(e)))

    def _stop_recording(self) -> None:
        if not self.recording:
            return
        self._log("Stopping recording...")
        self.status_label.configure(text="Stopping...", fg=YELLOW)
        self.stop_btn.configure(state="disabled")
        threading.Thread(target=self._shutdown_recording, daemon=True).start()

    def _shutdown_recording(self) -> None:
        try:
            if self.screen_cap:
                self.screen_cap.stop_recording()
                self._log("Screen recording stopped (preview continues)")
            face_video_path = None
            if self.webcam_cap:
                face_video_path = self.webcam_cap.stop_recording()
                self._log("Webcam recording stopped (preview continues)")
            watch_data = []
            if self.watch_ble:
                watch_data = self.watch_ble.get_all_readings()
                self._log(f"Watch data collected -- {len(watch_data)} readings (BLE stays connected)")
            if face_video_path and self.uploader:
                self._log("Uploading face video...")
                self.uploader.upload_face_video(face_video_path)
            if self.uploader:
                stats = self.uploader.stop()
                self._log(f"Uploader stopped -- {stats}")
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

    # -- Data Callbacks --

    def _on_screen_chunk(self, video_bytes, chunk_index) -> None:
        if self.uploader:
            self.uploader.enqueue_chunk(video_bytes, chunk_index)
            self._chunks_sent = chunk_index + 1

    def _on_emotion_reading(self, reading) -> None:
        data = reading.to_dict()
        self._latest_emotion = data
        if self.uploader:
            self.uploader.enqueue_emotion(data)

    def _on_watch_reading(self, reading) -> None:
        data = reading.to_dict()
        self._latest_hr = data
        if self.uploader:
            self.uploader.enqueue_watch(data)

    def _on_chunk_uploaded(self, chunk_index, success) -> None:
        pass

    def _on_upload_status(self, msg) -> None:
        self._log(msg)

    # ============================================================
    # UI UPDATES
    # ============================================================

    def _update_loop(self) -> None:
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
        if not self.webcam_cap or not self.webcam_cap.is_running:
            return
        frame = self.webcam_cap.get_current_frame()
        if frame is None:
            return
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            canvas_w = max(self.cam_canvas.winfo_width(), 480)
            canvas_h = max(self.cam_canvas.winfo_height(), 340)
            scale = min(canvas_w / w, canvas_h / h)
            new_w, new_h = int(w * scale), int(h * scale)
            rgb = cv2.resize(rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)
            img = Image.fromarray(rgb)
            self._cam_photo = ImageTk.PhotoImage(img)
            self.cam_canvas.delete("all")
            x_off = (canvas_w - new_w) // 2
            y_off = (canvas_h - new_h) // 2
            self.cam_canvas.create_image(x_off, y_off, anchor="nw", image=self._cam_photo)
        except Exception:
            pass

    def _update_screen_preview(self) -> None:
        if not self.screen_cap or not self.screen_cap.is_running:
            return
        seq = self.screen_cap.frame_seq
        if seq == self._last_screen_seq:
            return
        self._last_screen_seq = seq
        frame = self.screen_cap.get_latest_frame()
        if frame is None:
            return
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            canvas_w = max(self.screen_canvas.winfo_width(), 380)
            canvas_h = max(self.screen_canvas.winfo_height(), 160)
            scale = min(canvas_w / w, canvas_h / h)
            new_w, new_h = int(w * scale), int(h * scale)
            rgb = cv2.resize(rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)
            img = Image.fromarray(rgb)
            self._screen_photo = ImageTk.PhotoImage(img)
            self.screen_canvas.delete("all")
            x_off = (canvas_w - new_w) // 2
            y_off = (canvas_h - new_h) // 2
            self.screen_canvas.create_image(x_off, y_off, anchor="nw", image=self._screen_photo)
            actual = self.screen_cap._actual_fps
            target = self.screen_cap.fps
            self.screen_canvas.create_text(
                canvas_w - 4, 4, anchor="ne",
                text=f"{actual:.1f}/{target} FPS",
                fill=BLUE, font=(FONT, 9, "bold"),
            )
        except Exception:
            pass

    def _update_emotion_bars(self) -> None:
        if not self._latest_emotion:
            return
        for em, (bar, val_label) in self._emotion_labels.items():
            val = self._latest_emotion.get(em, 0.0)
            bar_w = bar.winfo_width() or 240
            bar.delete("all")
            filled = int(val * bar_w)
            color = EMOTION_COLORS.get(em, BLUE)
            if filled > 0:
                bar.create_rectangle(0, 0, filled, 20, fill=color, outline="")
            val_label.configure(text=f"{val:.2f}")

    def _update_hr_display(self) -> None:
        if not self._latest_hr:
            return
        hr = self._latest_hr.get("heart_rate", 0)
        hrv = self._latest_hr.get("hrv_rmssd", 0)
        self.hr_value.configure(text=f"{hr:.0f}")
        self.hrv_value.configure(text=f"{hrv:.1f}")

    def _update_gaze_display(self) -> None:
        if not self._latest_emotion:
            return
        p = self._latest_emotion.get("head_pitch", 0)
        y = self._latest_emotion.get("head_yaw", 0)
        r = self._latest_emotion.get("head_roll", 0)
        self.head_pose_label.configure(text=f"P:{p:+.0f}  Y:{y:+.0f}  R:{r:+.0f}")
        gx = self._latest_emotion.get("gaze_x", 0.5)
        gy = self._latest_emotion.get("gaze_y", 0.5)
        conf = self._latest_emotion.get("gaze_confidence", 0)
        cal = self.face_analyzer.gaze_calibrator
        self.gaze_canvas.delete("all")
        cw = self.gaze_canvas.winfo_width() or 240
        ch = self.gaze_canvas.winfo_height() or 160
        self.gaze_canvas.create_rectangle(2, 2, cw - 2, ch - 2, outline="#333", width=1)
        if conf > 0.5 and cal.calibrated:
            dot_x = (gx / cal.screen_w) * (cw - 4) + 2
            dot_y = (gy / cal.screen_h) * (ch - 4) + 2
        else:
            dot_x = gx * (cw - 4) + 2
            dot_y = gy * (ch - 4) + 2
        dot_x = max(4, min(cw - 4, dot_x))
        dot_y = max(4, min(ch - 4, dot_y))
        color = ORANGE if conf <= 0.5 else YELLOW
        self.gaze_canvas.create_oval(
            dot_x - 7, dot_y - 7, dot_x + 7, dot_y + 7,
            fill=color, outline="#fff", width=1,
        )
        status = "calibrated" if cal.calibrated else "raw iris ratio"
        self.gaze_canvas.create_text(
            cw // 2, ch - 8, text=status, fill="#888", font=(FONT, 8),
        )

    def _calibrate_gaze(self) -> None:
        cam_idx = self.camera_combo.current()
        if cam_idx < 0:
            cam_idx = 0
        def _on_done(error_px):
            if error_px >= 0:
                self.gaze_status.configure(text=f"Calibrated ({error_px:.0f}px error)", fg=GREEN)
                self._log(f"Gaze calibrated -- mean error: {error_px:.1f}px")
            else:
                self.gaze_status.configure(text="Calibration failed", fg=RED)
                self._log("Gaze calibration failed")
        GazeCalibrationWindow(
            master=self.root,
            face_analyzer=self.face_analyzer,
            camera_index=cam_idx,
            on_complete=_on_done,
        )
        self._log("Gaze calibration started")

    def _update_stats(self) -> None:
        if self.uploader:
            self.stat_chunks.configure(text=str(self.uploader.chunks_uploaded))
            self.stat_emotions.configure(text=str(self.uploader.emotion_frames_sent))
            self.stat_watch.configure(text=str(self.uploader.watch_readings_sent))

    def _update_recording_ui(self, is_recording) -> None:
        if is_recording:
            self.status_label.configure(text="RECORDING", fg=RED)
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
        else:
            self.status_label.configure(text="Idle", fg=TEXT_LIGHT)
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")

    def _recording_error(self, msg) -> None:
        self._log(f"ERROR: {msg}")
        self.status_label.configure(text="Error", fg=RED)
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        messagebox.showerror("Recording Error", msg)

    def _log(self, msg) -> None:
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        self._log_messages.append(line)
        if len(self._log_messages) > 100:
            self._log_messages = self._log_messages[-100:]
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
        if self.recording:
            if not messagebox.askyesno("Recording Active", "Recording is active. Stop and exit?"):
                return
            self._shutdown_recording()
        if self.screen_cap:
            self.screen_cap.stop()
        if self.webcam_cap:
            self.webcam_cap.stop()
        if self.face_analyzer:
            self.face_analyzer.close()
        self.root.destroy()


# -- Entry point --
if __name__ == "__main__":
    app = PatchLabApp()
    app.run()
