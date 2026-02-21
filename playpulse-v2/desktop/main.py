"""
AURA Desktop Capture Agent — tkinter GUI for the Stage 1 data collection.

Provides a unified control panel for:
  • Screen capture (configurable FPS: 1, 2, 3, custom up to 30)
  • Webcam recording + Presage SDK live emotion detection
  • Apple Watch BLE connection (HR/HRV streaming)
  • Real-time data preview (emotions, HR, chunk upload status)
  • Auto-chunking and async upload to the AURA backend
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


class AuraDesktopApp:
    """Main application window for the AURA Desktop Capture Agent."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("AURA — Desktop Capture Agent")
        self.root.geometry("900x750")
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

        # Live data
        self._latest_emotion: Optional[Dict] = None
        self._latest_hr: Optional[Dict] = None
        self._log_messages: List[str] = []
        self._chunks_sent = 0

        self._build_ui()
        self._update_loop()

    def run(self) -> None:
        """Start the tkinter main loop."""
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    # ═══════════════════════════════════════════════════════
    # UI CONSTRUCTION
    # ═══════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        # Apply custom style
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 11))
        style.configure("TButton", font=("Segoe UI", 11, "bold"), padding=8)
        style.configure("Header.TLabel", font=("Segoe UI", 20, "bold"), foreground=TEXT, background=BG)
        style.configure("Sub.TLabel", font=("Segoe UI", 10), foreground=MUTED, background=BG)
        style.configure("Card.TFrame", background=BG2)
        style.configure("Card.TLabel", background=BG2, foreground=TEXT)
        style.configure("CardMuted.TLabel", background=BG2, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Green.TLabel", background=BG2, foreground=GREEN, font=("Segoe UI", 11, "bold"))
        style.configure("Red.TLabel", background=BG2, foreground=RED, font=("Segoe UI", 11, "bold"))
        style.configure("Blue.TLabel", background=BG2, foreground=BLUE, font=("Segoe UI", 11, "bold"))
        style.configure("Amber.TLabel", background=BG2, foreground=AMBER, font=("Segoe UI", 11, "bold"))
        style.configure("Value.TLabel", background=BG2, foreground=TEXT, font=("Segoe UI", 16, "bold"))
        style.configure("Big.TButton", font=("Segoe UI", 14, "bold"), padding=12)

        # ── Header ──────────────────────────────────────────
        header = ttk.Frame(self.root)
        header.pack(fill="x", padx=20, pady=(16, 8))

        ttk.Label(header, text="🎯 AURA Desktop Agent", style="Header.TLabel").pack(side="left")
        self.status_label = ttk.Label(header, text="● Idle", style="Sub.TLabel")
        self.status_label.pack(side="right")

        # ── Scrollable content ──────────────────────────────
        canvas = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        self.scroll_frame = ttk.Frame(canvas)

        self.scroll_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=(20, 0))
        scrollbar.pack(side="right", fill="y")

        # ── Connection Card ─────────────────────────────────
        conn_card = self._make_card(self.scroll_frame, "🔌 Backend Connection")

        row1 = ttk.Frame(conn_card, style="Card.TFrame")
        row1.pack(fill="x", pady=4)
        ttk.Label(row1, text="Backend URL:", style="Card.TLabel").pack(side="left")
        self.url_var = tk.StringVar(value=self.backend_url)
        url_entry = ttk.Entry(row1, textvariable=self.url_var, width=35)
        url_entry.pack(side="left", padx=8)

        row2 = ttk.Frame(conn_card, style="Card.TFrame")
        row2.pack(fill="x", pady=4)
        ttk.Label(row2, text="Project ID:", style="Card.TLabel").pack(side="left")
        self.project_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.project_var, width=25).pack(side="left", padx=8)

        row3 = ttk.Frame(conn_card, style="Card.TFrame")
        row3.pack(fill="x", pady=4)
        ttk.Label(row3, text="Tester Name:", style="Card.TLabel").pack(side="left")
        self.tester_var = tk.StringVar(value="desktop_tester")
        ttk.Entry(row3, textvariable=self.tester_var, width=25).pack(side="left", padx=8)

        self.conn_status = ttk.Label(conn_card, text="Not connected", style="CardMuted.TLabel")
        self.conn_status.pack(anchor="w", pady=4)

        ttk.Button(conn_card, text="🔍 Test Connection", command=self._test_connection).pack(anchor="w", pady=4)

        # ── Screen Capture Card ─────────────────────────────
        screen_card = self._make_card(self.scroll_frame, "🖥️ Screen Capture")

        fps_row = ttk.Frame(screen_card, style="Card.TFrame")
        fps_row.pack(fill="x", pady=4)
        ttk.Label(fps_row, text="Capture FPS:", style="Card.TLabel").pack(side="left")

        self.fps_var = tk.IntVar(value=3)
        for fps_val in [1, 2, 3]:
            ttk.Radiobutton(fps_row, text=str(fps_val), variable=self.fps_var, value=fps_val).pack(side="left", padx=4)
        ttk.Label(fps_row, text="Custom:", style="Card.TLabel").pack(side="left", padx=(12, 4))
        self.custom_fps_var = tk.StringVar(value="")
        custom_entry = ttk.Entry(fps_row, textvariable=self.custom_fps_var, width=5)
        custom_entry.pack(side="left")
        custom_entry.bind("<FocusIn>", lambda e: self.fps_var.set(0))

        mon_row = ttk.Frame(screen_card, style="Card.TFrame")
        mon_row.pack(fill="x", pady=4)
        ttk.Label(mon_row, text="Monitor:", style="Card.TLabel").pack(side="left")
        self.monitor_var = tk.IntVar(value=1)
        self.monitor_combo = ttk.Combobox(mon_row, state="readonly", width=35)
        self.monitor_combo.pack(side="left", padx=8)
        self._refresh_monitors()
        self.monitor_combo.bind("<<ComboboxSelected>>", self._on_monitor_select)

        chunk_row = ttk.Frame(screen_card, style="Card.TFrame")
        chunk_row.pack(fill="x", pady=4)
        ttk.Label(chunk_row, text="Chunk Duration:", style="Card.TLabel").pack(side="left")
        self.chunk_dur_var = tk.IntVar(value=10)
        ttk.Scale(chunk_row, from_=5, to=30, variable=self.chunk_dur_var, orient="horizontal", length=150).pack(side="left", padx=8)
        self.chunk_dur_label = ttk.Label(chunk_row, text="10s", style="Card.TLabel")
        self.chunk_dur_label.pack(side="left")

        res_row = ttk.Frame(screen_card, style="Card.TFrame")
        res_row.pack(fill="x", pady=4)
        ttk.Label(res_row, text="Resolution:", style="Card.TLabel").pack(side="left")
        self.resolution_var = tk.StringVar(value="native")
        for label, val in [("Native", "native"), ("1280×720", "1280x720"), ("960×540", "960x540")]:
            ttk.Radiobutton(res_row, text=label, variable=self.resolution_var, value=val).pack(side="left", padx=4)

        # Screen capture preview thumbnail
        self.screen_preview_frame = ttk.Frame(screen_card, style="Card.TFrame")
        self.screen_preview_frame.pack(fill="x", pady=(8, 4))
        ttk.Label(self.screen_preview_frame, text="Latest Captured Frame:", style="CardMuted.TLabel").pack(anchor="w")
        self.screen_canvas = tk.Canvas(self.screen_preview_frame, width=320, height=180, bg="#0a0a0a", highlightthickness=1, highlightbackground=SURFACE)
        self.screen_canvas.pack(anchor="w", pady=4)
        self.screen_canvas.create_text(160, 90, text="No capture yet", fill=MUTED, font=("Segoe UI", 10))
        self._screen_photo = None  # Keep reference to prevent GC

        # ── Webcam / Presage Card ───────────────────────────
        webcam_card = self._make_card(self.scroll_frame, "📷 Webcam + Presage SDK")

        cam_row = ttk.Frame(webcam_card, style="Card.TFrame")
        cam_row.pack(fill="x", pady=4)
        ttk.Label(cam_row, text="Camera:", style="Card.TLabel").pack(side="left")
        self.camera_combo = ttk.Combobox(cam_row, state="readonly", width=30)
        self.camera_combo.pack(side="left", padx=8)
        ttk.Button(cam_row, text="🔄", command=self._refresh_cameras, width=3).pack(side="left")
        self._refresh_cameras()

        presage_row = ttk.Frame(webcam_card, style="Card.TFrame")
        presage_row.pack(fill="x", pady=4)
        ttk.Label(presage_row, text="Presage API Key:", style="Card.TLabel").pack(side="left")
        self.presage_key_var = tk.StringVar(value=os.getenv("PRESAGE_API_KEY", ""))
        ttk.Entry(presage_row, textvariable=self.presage_key_var, width=30, show="•").pack(side="left", padx=8)

        # Live camera preview
        cam_preview_frame = ttk.Frame(webcam_card, style="Card.TFrame")
        cam_preview_frame.pack(fill="x", pady=(8, 4))
        ttk.Label(cam_preview_frame, text="Live Camera Feed:", style="CardMuted.TLabel").pack(anchor="w")
        self.cam_canvas = tk.Canvas(cam_preview_frame, width=240, height=180, bg="#0a0a0a", highlightthickness=1, highlightbackground=SURFACE)
        self.cam_canvas.pack(anchor="w", pady=4)
        self.cam_canvas.create_text(120, 90, text="Camera off", fill=MUTED, font=("Segoe UI", 10))
        self._cam_photo = None  # Keep reference to prevent GC

        self.emotion_display = ttk.Frame(webcam_card, style="Card.TFrame")
        self.emotion_display.pack(fill="x", pady=8)
        self._emotion_labels = {}
        for em in ["frustration", "confusion", "delight", "boredom", "surprise", "engagement"]:
            row = ttk.Frame(self.emotion_display, style="Card.TFrame")
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=f"{em.capitalize()}:", style="Card.TLabel", width=14).pack(side="left")
            bar = tk.Canvas(row, width=200, height=14, bg=SURFACE, highlightthickness=0)
            bar.pack(side="left", padx=4)
            val_label = ttk.Label(row, text="—", style="Card.TLabel", width=6)
            val_label.pack(side="left")
            self._emotion_labels[em] = (bar, val_label)

        # ── Apple Watch Card ────────────────────────────────
        watch_card = self._make_card(self.scroll_frame, "⌚ Apple Watch BLE")

        watch_row = ttk.Frame(watch_card, style="Card.TFrame")
        watch_row.pack(fill="x", pady=4)
        ttk.Label(watch_row, text="Device:", style="Card.TLabel").pack(side="left")
        self.watch_combo = ttk.Combobox(watch_row, state="readonly", width=30)
        self.watch_combo.pack(side="left", padx=8)
        ttk.Button(watch_row, text="🔍 Scan", command=self._scan_ble).pack(side="left", padx=(4, 0))
        self.ble_connect_btn = ttk.Button(watch_row, text="▶ Connect", command=self._connect_ble)
        self.ble_connect_btn.pack(side="left", padx=(4, 0))
        self.ble_disconnect_btn = ttk.Button(watch_row, text="⏹ Disconnect", command=self._disconnect_ble, state="disabled")
        self.ble_disconnect_btn.pack(side="left", padx=(4, 0))

        hr_row = ttk.Frame(watch_card, style="Card.TFrame")
        hr_row.pack(fill="x", pady=8)
        self.hr_value = ttk.Label(hr_row, text="— BPM", style="Value.TLabel")
        self.hr_value.pack(side="left", padx=(0, 24))
        ttk.Label(hr_row, text="HR", style="CardMuted.TLabel").pack(side="left", padx=(0, 32))
        self.hrv_value = ttk.Label(hr_row, text="— ms", style="Value.TLabel")
        self.hrv_value.pack(side="left", padx=(0, 8))
        ttk.Label(hr_row, text="HRV (RMSSD)", style="CardMuted.TLabel").pack(side="left")

        self.watch_status = ttk.Label(watch_card, text="Not connected", style="CardMuted.TLabel")
        self.watch_status.pack(anchor="w")

        # ── Upload Stats Card ───────────────────────────────
        stats_card = self._make_card(self.scroll_frame, "📤 Upload Status")

        stats_grid = ttk.Frame(stats_card, style="Card.TFrame")
        stats_grid.pack(fill="x", pady=4)

        self.stat_chunks = ttk.Label(stats_grid, text="0", style="Value.TLabel")
        self.stat_chunks.grid(row=0, column=0, padx=16)
        ttk.Label(stats_grid, text="Chunks", style="CardMuted.TLabel").grid(row=1, column=0)

        self.stat_emotions = ttk.Label(stats_grid, text="0", style="Value.TLabel")
        self.stat_emotions.grid(row=0, column=1, padx=16)
        ttk.Label(stats_grid, text="Emotions", style="CardMuted.TLabel").grid(row=1, column=1)

        self.stat_watch = ttk.Label(stats_grid, text="0", style="Value.TLabel")
        self.stat_watch.grid(row=0, column=2, padx=16)
        ttk.Label(stats_grid, text="Watch", style="CardMuted.TLabel").grid(row=1, column=2)

        self.stat_session = ttk.Label(stats_card, text="Session: —", style="CardMuted.TLabel")
        self.stat_session.pack(anchor="w", pady=4)

        # ── Log Card ────────────────────────────────────────
        log_card = self._make_card(self.scroll_frame, "📝 Activity Log")
        self.log_text = tk.Text(
            log_card, height=6, bg=BG, fg=MUTED, font=("Courier", 10),
            wrap="word", state="disabled", borderwidth=0,
        )
        self.log_text.pack(fill="x", pady=4)

        # ── CONTROL BUTTONS ─────────────────────────────────
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill="x", padx=20, pady=16)

        self.start_btn = tk.Button(
            btn_frame, text="▶  START RECORDING", font=("Segoe UI", 14, "bold"),
            bg=GREEN, fg="white", activebackground="#16a34a", relief="flat",
            padx=24, pady=10, command=self._start_recording,
        )
        self.start_btn.pack(side="left", padx=4)

        self.stop_btn = tk.Button(
            btn_frame, text="⏹  STOP", font=("Segoe UI", 14, "bold"),
            bg=RED, fg="white", activebackground="#dc2626", relief="flat",
            padx=24, pady=10, command=self._stop_recording, state="disabled",
        )
        self.stop_btn.pack(side="left", padx=4)

    def _make_card(self, parent: ttk.Frame, title: str) -> ttk.Frame:
        """Create a styled card with title."""
        container = ttk.Frame(parent, style="Card.TFrame")
        container.pack(fill="x", pady=6, padx=4, ipady=8, ipadx=12)

        ttk.Label(container, text=title, font=("Segoe UI", 13, "bold"),
                  background=BG2, foreground=TEXT).pack(anchor="w", padx=4, pady=(4, 8))

        return container

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
        self.hr_value.configure(text="— BPM")
        self.hrv_value.configure(text="— ms")
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
                labels = ["Simulated Watch (auto)"]
                self._ble_devices = [{"address": None, "name": "Simulated Watch"}]

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
        """Start all data collection streams."""
        if self.recording:
            return

        self.backend_url = self.url_var.get().strip()
        self.project_id = self.project_var.get().strip()

        if not self.project_id:
            messagebox.showwarning("Missing Project", "Please enter a Project ID.")
            return

        self._log("Starting recording...")
        self.status_label.configure(text="● Starting...", foreground=AMBER)

        # Disable start, enable stop
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")

        # Start everything in a thread to avoid blocking UI
        threading.Thread(target=self._init_recording, daemon=True).start()

    def _init_recording(self) -> None:
        """Initialize all capture modules (runs in thread)."""
        try:
            fps = self._get_fps()
            resolution = self._get_resolution()
            chunk_dur = self.chunk_dur_var.get()

            # 1. Create uploader and session
            self.uploader = ChunkUploader(
                backend_url=self.backend_url,
                project_id=self.project_id,
            )
            session_id = self.uploader.create_session(tester_name=self.tester_var.get())
            if not session_id:
                self.root.after(0, lambda: self._recording_error("Failed to create session"))
                return

            self.session_id = session_id
            self.root.after(0, lambda: self.stat_session.configure(text=f"Session: {session_id}"))

            self.uploader.start(
                on_upload_complete=self._on_chunk_uploaded,
                on_status_change=self._on_upload_status,
            )

            # 2. Start screen capture
            self.screen_cap = ScreenCapture(
                fps=fps,
                chunk_duration_sec=float(chunk_dur),
                monitor_index=self.monitor_var.get(),
                resolution=resolution,
            )
            self.screen_cap.start(on_chunk_ready=self._on_screen_chunk)

            # 3. Start webcam + Presage
            cam_idx = self.camera_combo.current()
            if cam_idx < 0:
                cam_idx = 0
            self.webcam_cap = WebcamCapture(
                camera_index=cam_idx,
                presage_api_key=self.presage_key_var.get(),
            )
            self.webcam_cap.start(
                on_emotion=self._on_emotion_reading,
                record_video=True,
            )

            # 4. Apple Watch BLE — reuse if already connected, otherwise start
            if not (self.watch_ble and self.watch_ble.is_running):
                self.watch_ble = WatchBLE()
                device_addr = None
                if hasattr(self, "_ble_devices") and self._ble_devices:
                    idx = self.watch_combo.current()
                    if idx >= 0 and idx < len(self._ble_devices):
                        device_addr = self._ble_devices[idx].get("address")

                self.watch_ble.start(
                    on_reading=self._on_watch_reading,
                    device_address=device_addr,
                )
            else:
                self._log("Reusing existing BLE connection")

            self.recording = True
            self.root.after(0, lambda: self._update_recording_ui(True))
            self._log(f"Recording started — FPS={fps}, Chunk={chunk_dur}s, Session={session_id}")

        except Exception as e:
            self.root.after(0, lambda: self._recording_error(str(e)))

    def _stop_recording(self) -> None:
        """Stop all data collection and finalize the session."""
        if not self.recording:
            return

        self._log("Stopping recording...")
        self.status_label.configure(text="● Stopping...", foreground=AMBER)
        self.stop_btn.configure(state="disabled")

        threading.Thread(target=self._shutdown_recording, daemon=True).start()

    def _shutdown_recording(self) -> None:
        """Shutdown all modules and finalize (runs in thread)."""
        try:
            # Stop screen capture
            if self.screen_cap:
                self.screen_cap.stop()
                self._log("Screen capture stopped")

            # Stop webcam and get video
            face_video_path = None
            if self.webcam_cap:
                face_video_path, _ = self.webcam_cap.stop()
                self._log("Webcam stopped")

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
            # Fit to 240x180 maintaining aspect ratio
            scale = min(240 / w, 180 / h)
            new_w, new_h = int(w * scale), int(h * scale)
            rgb = cv2.resize(rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)
            img = Image.fromarray(rgb)
            self._cam_photo = ImageTk.PhotoImage(img)
            self.cam_canvas.delete("all")
            # Center in canvas
            x_off = (240 - new_w) // 2
            y_off = (180 - new_h) // 2
            self.cam_canvas.create_image(x_off, y_off, anchor="nw", image=self._cam_photo)
        except Exception:
            pass

    def _update_screen_preview(self) -> None:
        """Update the screen capture thumbnail canvas."""
        if not self.screen_cap or not self.screen_cap.is_running:
            return
        frame = self.screen_cap.get_latest_frame()
        if frame is None:
            return
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            # Fit to 320x180 maintaining aspect ratio
            scale = min(320 / w, 180 / h)
            new_w, new_h = int(w * scale), int(h * scale)
            rgb = cv2.resize(rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)
            img = Image.fromarray(rgb)
            self._screen_photo = ImageTk.PhotoImage(img)
            self.screen_canvas.delete("all")
            x_off = (320 - new_w) // 2
            y_off = (180 - new_h) // 2
            self.screen_canvas.create_image(x_off, y_off, anchor="nw", image=self._screen_photo)
        except Exception:
            pass

    def _update_emotion_bars(self) -> None:
        """Update emotion bar visualization."""
        if not self._latest_emotion:
            return
        for em, (bar, val_label) in self._emotion_labels.items():
            val = self._latest_emotion.get(em, 0.0)
            bar.delete("all")
            width = int(val * 200)
            color = self._emotion_color(em)
            bar.create_rectangle(0, 0, width, 14, fill=color, outline="")
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
        self.hr_value.configure(text=f"{hr:.0f} BPM")
        self.hrv_value.configure(text=f"{hrv:.1f} ms")

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
        """Handle window close."""
        if self.recording:
            if not messagebox.askyesno("Recording Active", "Recording is active. Stop and exit?"):
                return
            self._shutdown_recording()
        self.root.destroy()


# ── Entry point ─────────────────────────────────────────────
if __name__ == "__main__":
    app = AuraDesktopApp()
    app.run()
