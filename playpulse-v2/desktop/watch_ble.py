"""
Apple Watch BLE Module — connects to an Apple Watch (or any BLE heart-rate
device) and streams HR + HRV data at ~1 Hz.

Uses the ``bleak`` library for cross-platform BLE support.

Standard BLE UUIDs:
  Heart Rate Service:       0x180D
  Heart Rate Measurement:   0x2A37
  (HRV is derived from RR-intervals in the HR Measurement characteristic)

The Apple Watch exposes HR via standard Bluetooth Heart Rate Profile when
running a workout or a compatible app.
"""

from __future__ import annotations

import asyncio
import math
import struct
import threading
import time
from collections import deque
from typing import Callable, Dict, List, Optional

# Optional: bleak import
try:
    from bleak import BleakClient, BleakScanner
    HAS_BLEAK = True
except ImportError:
    HAS_BLEAK = False


# ── Standard BLE Heart Rate UUIDs ───────────────────────────
HR_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HR_MEASUREMENT_UUID = "00002a37-0000-1000-8000-00805f9b34fb"


class WatchReading:
    """Single HR/HRV reading from the watch."""

    __slots__ = ("timestamp_sec", "heart_rate", "hrv_rmssd", "hrv_sdnn", "rr_intervals", "movement_variance")

    def __init__(
        self,
        timestamp_sec: float,
        heart_rate: float = 0.0,
        hrv_rmssd: float = 0.0,
        hrv_sdnn: float = 0.0,
        rr_intervals: Optional[List[float]] = None,
        movement_variance: float = 0.0,
    ):
        self.timestamp_sec = timestamp_sec
        self.heart_rate = heart_rate
        self.hrv_rmssd = hrv_rmssd
        self.hrv_sdnn = hrv_sdnn
        self.rr_intervals = rr_intervals or []
        self.movement_variance = movement_variance

    def to_dict(self) -> Dict:
        return {
            "timestamp_sec": self.timestamp_sec,
            "heart_rate": self.heart_rate,
            "hrv_rmssd": self.hrv_rmssd,
            "hrv_sdnn": self.hrv_sdnn,
            "rr_intervals": self.rr_intervals,
            "movement_variance": self.movement_variance,
        }


class WatchBLE:
    """Connects to an Apple Watch / BLE HR device and streams HR + HRV data."""

    def __init__(self, target_name: str = "Apple Watch"):
        self.target_name = target_name
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._client: Optional[object] = None  # BleakClient
        self._start_time: float = 0.0

        # Data buffers
        self._readings: List[WatchReading] = []
        self._lock = threading.Lock()

        # RR interval buffer for HRV calculation (rolling 60s window)
        self._rr_buffer: deque = deque(maxlen=120)

        # Callbacks
        self._on_reading: Optional[Callable[[WatchReading], None]] = None

        # Device address (discovered during scan)
        self._device_address: Optional[str] = None

        # Connection status
        self.connected = False
        self.device_name: Optional[str] = None

    async def scan_devices(self, timeout: float = 10.0) -> List[Dict]:
        """Scan for nearby BLE heart rate devices.

        Returns list of {address, name, rssi, has_hr_service} dicts.
        Uses bleak 2.x API with return_adv=True.
        """
        if not HAS_BLEAK:
            print("[WatchBLE] bleak not installed — returning empty scan")
            return []

        devices = []
        seen_addresses = set()

        # Single broad scan with advertisement data
        try:
            print("[WatchBLE] Scanning for BLE devices...")
            discovered = await BleakScanner.discover(timeout=timeout, return_adv=True)

            for addr, (dev, adv) in discovered.items():
                name = dev.name or (adv.local_name if adv else None) or ""
                rssi = adv.rssi if adv else -100
                service_uuids = [s.lower() for s in (adv.service_uuids if adv else [])]
                has_hr = any("180d" in s for s in service_uuids)

                if has_hr:
                    seen_addresses.add(addr)
                    devices.append({
                        "address": addr,
                        "name": name or "HR Device",
                        "rssi": rssi,
                        "has_hr_service": True,
                    })
                    print(f"[WatchBLE] ❤️  HR device: {name} ({addr}) RSSI={rssi}")

            # Also check by name keywords for devices not advertising HR service
            hr_keywords = ["watch", "heart", "polar", "garmin", "hr", "apple",
                           "heartcast", "wahoo", "fitbit", "coros", "suunto",
                           "chest", "strap", "band", "pulse", "iphone"]
            for addr, (dev, adv) in discovered.items():
                if addr in seen_addresses:
                    continue
                name = dev.name or (adv.local_name if adv else None) or ""
                rssi = adv.rssi if adv else -100
                if name and any(kw in name.lower() for kw in hr_keywords):
                    seen_addresses.add(addr)
                    devices.append({
                        "address": addr,
                        "name": name,
                        "rssi": rssi,
                        "has_hr_service": False,
                    })
                    print(f"[WatchBLE] 📡 By name: {name} ({addr}) RSSI={rssi}")

        except Exception as e:
            print(f"[WatchBLE] Scan error: {e}")
            import traceback
            traceback.print_exc()

        # Sort: HR service devices first, then by signal strength
        devices.sort(key=lambda x: (not x.get("has_hr_service", False), -(x.get("rssi") or -100)))

        if not devices:
            print("[WatchBLE] No HR devices found.")

        print(f"[WatchBLE] Scan complete: {len(devices)} device(s) found")
        return devices

    def start(
        self,
        on_reading: Optional[Callable[[WatchReading], None]] = None,
        device_address: Optional[str] = None,
    ) -> None:
        """Start BLE connection in a background thread.

        Args:
            on_reading: Callback fired at ~1 Hz with HR/HRV data.
            device_address: Specific BLE address to connect to.
                If None, will scan for target_name.
        """
        if self._running:
            return

        self._on_reading = on_reading
        self._device_address = device_address
        self._start_time = time.monotonic()
        self._readings.clear()
        self._rr_buffer.clear()
        self._running = True

        self._thread = threading.Thread(target=self._run_ble_loop, daemon=True)
        self._thread.start()

    def stop(self) -> List[Dict]:
        """Stop BLE connection and return collected readings."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10.0)
        self._thread = None
        self.connected = False

        with self._lock:
            return [r.to_dict() for r in self._readings]

    @property
    def is_running(self) -> bool:
        return self._running

    def get_latest_reading(self) -> Optional[WatchReading]:
        """Get the most recent reading."""
        with self._lock:
            return self._readings[-1] if self._readings else None

    def get_all_readings(self) -> List[Dict]:
        """Get all collected readings."""
        with self._lock:
            return [r.to_dict() for r in self._readings]

    # ── Internal ────────────────────────────────────────────

    def _run_ble_loop(self) -> None:
        """Run the async BLE event loop in this thread."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            if HAS_BLEAK:
                loop.run_until_complete(self._ble_connect_and_listen())
            else:
                # Fallback: generate simulated data
                loop.run_until_complete(self._simulate_data())
        except Exception as e:
            print(f"[WatchBLE] BLE loop error: {e}")
        finally:
            loop.close()

    async def _ble_connect_and_listen(self) -> None:
        """Scan, connect, and subscribe to HR notifications."""
        address = self._device_address

        if not address:
            # Scan with advertisement data (bleak 2.x API)
            print("[WatchBLE] Scanning for HR service devices...")
            try:
                discovered = await BleakScanner.discover(
                    timeout=15.0,
                    return_adv=True,
                )
                # Find devices advertising HR service
                for addr, (dev, adv) in discovered.items():
                    service_uuids = [s.lower() for s in (adv.service_uuids if adv else [])]
                    if any("180d" in s for s in service_uuids):
                        address = addr
                        self.device_name = dev.name or (adv.local_name if adv else None) or "HR Device"
                        print(f"[WatchBLE] Found HR device: {self.device_name} ({addr})")
                        break
            except Exception as e:
                print(f"[WatchBLE] Service-based scan error: {e}")

        if not address:
            # Fallback: scan by name
            print("[WatchBLE] No HR service found, scanning by name...")
            try:
                discovered = await BleakScanner.discover(timeout=10.0, return_adv=True)
                hr_keywords = ["watch", "heart", "polar", "garmin", "hr", "apple",
                               "heartcast", "wahoo", "fitbit", "coros", "band", "pulse", "iphone"]
                for addr, (dev, adv) in discovered.items():
                    name = dev.name or (adv.local_name if adv else None) or ""
                    if name and any(kw in name.lower() for kw in hr_keywords):
                        address = addr
                        self.device_name = name
                        print(f"[WatchBLE] Found by name: {name} ({addr})")
                        break
            except Exception as e:
                print(f"[WatchBLE] Name-scan error: {e}")

        if not address:
            print(f"[WatchBLE] No HR device found, starting simulation")
            await self._simulate_data()
            return

        # Connect and subscribe
        print(f"[WatchBLE] Connecting to {self.device_name} ({address})...")
        try:
            async with BleakClient(address, timeout=20.0) as client:
                self._client = client
                self.connected = True
                print(f"[WatchBLE] Connected to {address}")

                # Discover services and check for HR
                services = client.services
                hr_char = None
                for service in services:
                    print(f"[WatchBLE]   Service: {service.uuid}")
                    for char in service.characteristics:
                        print(f"[WatchBLE]     Char: {char.uuid} props={char.properties}")
                        if char.uuid.lower().startswith("00002a37"):
                            hr_char = char.uuid

                target_uuid = hr_char or HR_MEASUREMENT_UUID
                print(f"[WatchBLE] Subscribing to HR characteristic: {target_uuid}")

                # Subscribe to heart rate measurement
                await client.start_notify(target_uuid, self._hr_notification_handler)

                # Stay connected while running
                while self._running and client.is_connected:
                    await asyncio.sleep(0.5)

                await client.stop_notify(target_uuid)
        except Exception as e:
            print(f"[WatchBLE] Connection error: {e}")
            print(f"[WatchBLE] Falling back to simulation")
            await self._simulate_data()

        self.connected = False

    def _hr_notification_handler(self, sender: int, data: bytearray) -> None:
        """Parse BLE Heart Rate Measurement characteristic.

        Byte 0: Flags
          Bit 0: HR format (0 = uint8, 1 = uint16)
          Bit 4: RR-interval present
        Byte 1(+2): Heart Rate value
        Remaining: RR-intervals (uint16, in 1/1024 sec units)
        """
        flags = data[0]
        hr_format_16bit = bool(flags & 0x01)
        rr_present = bool(flags & 0x10)

        offset = 1
        if hr_format_16bit:
            heart_rate = struct.unpack_from("<H", data, offset)[0]
            offset += 2
        else:
            heart_rate = data[offset]
            offset += 1

        # Skip Energy Expended if present (bit 3)
        if flags & 0x08:
            offset += 2

        # Parse RR intervals
        rr_intervals = []
        if rr_present:
            while offset + 1 < len(data):
                rr_raw = struct.unpack_from("<H", data, offset)[0]
                rr_ms = rr_raw / 1024.0 * 1000.0  # Convert to milliseconds
                rr_intervals.append(round(rr_ms, 1))
                offset += 2

        # Add to RR buffer for HRV calc
        for rr in rr_intervals:
            self._rr_buffer.append(rr)

        # Compute HRV metrics
        hrv_rmssd, hrv_sdnn = self._compute_hrv()

        timestamp = round(time.monotonic() - self._start_time, 3)
        reading = WatchReading(
            timestamp_sec=timestamp,
            heart_rate=float(heart_rate),
            hrv_rmssd=hrv_rmssd,
            hrv_sdnn=hrv_sdnn,
            rr_intervals=rr_intervals,
        )

        with self._lock:
            self._readings.append(reading)

        if self._on_reading:
            try:
                self._on_reading(reading)
            except Exception:
                pass

    def _compute_hrv(self) -> tuple:
        """Compute RMSSD and SDNN from the RR interval buffer."""
        rr_list = list(self._rr_buffer)
        if len(rr_list) < 2:
            return 0.0, 0.0

        # RMSSD: Root Mean Square of Successive Differences
        diffs = [rr_list[i + 1] - rr_list[i] for i in range(len(rr_list) - 1)]
        rmssd = math.sqrt(sum(d ** 2 for d in diffs) / len(diffs)) if diffs else 0.0

        # SDNN: Standard Deviation of NN intervals
        mean_rr = sum(rr_list) / len(rr_list)
        sdnn = math.sqrt(sum((r - mean_rr) ** 2 for r in rr_list) / len(rr_list))

        return round(rmssd, 2), round(sdnn, 2)

    async def _simulate_data(self) -> None:
        """Generate simulated HR/HRV data when no device is available.

        Provides realistic-looking data for development/demo.
        """
        import random

        print("[WatchBLE] Running simulated HR data")
        self.connected = True
        self.device_name = "Simulated Watch"

        base_hr = 72.0
        base_hrv_rmssd = 42.0
        base_hrv_sdnn = 35.0

        while self._running:
            t = time.monotonic() - self._start_time
            timestamp = round(t, 3)

            # Simulate HR with some variability
            hr = base_hr + 10 * math.sin(t * 0.1) + random.gauss(0, 2)
            hr = max(50, min(180, hr))

            # Simulate HRV
            hrv_rmssd = base_hrv_rmssd + 8 * math.sin(t * 0.05 + 1) + random.gauss(0, 3)
            hrv_sdnn = base_hrv_sdnn + 5 * math.sin(t * 0.07 + 2) + random.gauss(0, 2)
            hrv_rmssd = max(10, min(100, hrv_rmssd))
            hrv_sdnn = max(10, min(80, hrv_sdnn))

            # Simulate RR intervals from HR
            rr_mean = 60000.0 / hr  # ms
            rr_intervals = [round(rr_mean + random.gauss(0, 20), 1) for _ in range(1)]

            reading = WatchReading(
                timestamp_sec=timestamp,
                heart_rate=round(hr, 1),
                hrv_rmssd=round(hrv_rmssd, 2),
                hrv_sdnn=round(hrv_sdnn, 2),
                rr_intervals=rr_intervals,
                movement_variance=round(random.uniform(0, 0.5), 3),
            )

            with self._lock:
                self._readings.append(reading)

            if self._on_reading:
                try:
                    self._on_reading(reading)
                except Exception:
                    pass

            await asyncio.sleep(1.0)  # 1 Hz

        self.connected = False
