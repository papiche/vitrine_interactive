#!/usr/bin/env python3
"""
Hardware auto-detection and performance profile selection for Vitrine Interactive.

Detects machine type (Pi Zero 2W, Pi 3, Pi 4, Pi 5, generic PC) and available
resources (RAM, CPU cores) to automatically select optimal performance settings.

Usage:
    from hardware_profile import HW
    # Then use HW.frame_width, HW.jpeg_quality, etc.
"""

import os
import platform
import re


def _read_file(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except (OSError, IOError):
        return ""


def _detect_board():
    """Detect Raspberry Pi model or return 'pc'."""
    model = _read_file("/proc/device-tree/model")
    if not model:
        model = _read_file("/sys/firmware/devicetree/base/model")
    model = model.rstrip('\x00')

    if not model:
        return "pc"

    ml = model.lower()
    if "zero 2" in ml:
        return "pi_zero2w"
    if "zero" in ml:
        return "pi_zero"
    if "pi 3" in ml or "model b plus" in ml:
        return "pi3"
    if "pi 4" in ml:
        return "pi4"
    if "pi 5" in ml:
        return "pi5"
    if "raspberry" in ml:
        return "pi_unknown"
    return "pc"


def _total_ram_mb():
    """Return total physical RAM in MB."""
    meminfo = _read_file("/proc/meminfo")
    m = re.search(r"MemTotal:\s+(\d+)\s+kB", meminfo)
    if m:
        return int(m.group(1)) // 1024
    # Fallback for non-Linux
    try:
        import psutil
        return psutil.virtual_memory().total // (1024 * 1024)
    except ImportError:
        return 4096  # assume decent PC


def _cpu_count():
    return os.cpu_count() or 1


# ---------------------------------------------------------------------------
# Performance profiles
# ---------------------------------------------------------------------------
# Each profile is a dict of tunable parameters.
# Profiles are ordered from most constrained to most capable.

PROFILES = {
    # Pi Zero / Zero 2W — 512 MB RAM, 1 GHz quad-core (Zero 2W)
    "minimal": {
        "label":                   "Minimal (Pi Zero 2W / <=512 MB)",
        "frame_width":             320,
        "frame_height":            240,
        "camera_fps":              15,
        "capture_loop_sleep":      0.05,   # ~20 fps max
        "stream_fps_sleep":        0.066,  # ~15 fps
        "ws_emitter_sleep":        0.066,
        "jpeg_quality":            40,
        "face_detection_interval": 60,     # every 60 frames
        "face_scale":              0.25,   # downscale to 25%
        "face_min_size":           15,
        "face_recognition":        False,  # disable dlib/face_recognition
        "nostr_limit":             20,
        "nostr_refresh":           60,     # every 60s
        "frontend_poll_ms":        100,    # slower JS polling
    },
    # Pi 3 / low-RAM Pi 4 — 1 GB RAM
    "low": {
        "label":                   "Low (Pi 3 / 1 GB)",
        "frame_width":             480,
        "frame_height":            360,
        "camera_fps":              20,
        "capture_loop_sleep":      0.04,
        "stream_fps_sleep":        0.05,
        "ws_emitter_sleep":        0.05,
        "jpeg_quality":            50,
        "face_detection_interval": 45,
        "face_scale":              0.30,
        "face_min_size":           18,
        "face_recognition":        False,
        "nostr_limit":             30,
        "nostr_refresh":           45,
        "frontend_poll_ms":        80,
    },
    # Pi 4 (2-4 GB) / Pi 5 (low config)
    "medium": {
        "label":                   "Medium (Pi 4 / Pi 5 2 GB)",
        "frame_width":             640,
        "frame_height":            480,
        "camera_fps":              30,
        "capture_loop_sleep":      0.02,
        "stream_fps_sleep":        0.033,
        "ws_emitter_sleep":        0.033,
        "jpeg_quality":            60,
        "face_detection_interval": 30,
        "face_scale":              0.33,
        "face_min_size":           20,
        "face_recognition":        True,
        "nostr_limit":             50,
        "nostr_refresh":           30,
        "frontend_poll_ms":        50,
    },
    # PC / Pi 5 (4-8 GB)
    "high": {
        "label":                   "High (PC / Pi 5 4 GB+)",
        "frame_width":             1280,
        "frame_height":            720,
        "camera_fps":              30,
        "capture_loop_sleep":      0.015,
        "stream_fps_sleep":        0.033,
        "ws_emitter_sleep":        0.033,
        "jpeg_quality":            75,
        "face_detection_interval": 15,
        "face_scale":              0.50,
        "face_min_size":           30,
        "face_recognition":        True,
        "nostr_limit":             100,
        "nostr_refresh":           30,
        "frontend_poll_ms":        50,
    },
}


def _select_profile(board, ram_mb, cpus):
    """Pick the best profile for detected hardware."""
    # Explicit board-based selection
    if board in ("pi_zero", "pi_zero2w"):
        return "minimal"
    if board == "pi3":
        return "low"

    # RAM-based fallback (works for any board including PC)
    if ram_mb <= 600:
        return "minimal"
    if ram_mb <= 1200:
        return "low"
    if ram_mb <= 3000:
        return "medium"
    return "high"


class HardwareProfile:
    """Detected hardware profile — all tunables as attributes."""

    def __init__(self):
        self.board = _detect_board()
        self.ram_mb = _total_ram_mb()
        self.cpus = _cpu_count()
        self.profile_name = _select_profile(self.board, self.ram_mb, self.cpus)

        # Allow manual override via env var: VITRINE_PROFILE=minimal|low|medium|high
        override = os.getenv("VITRINE_PROFILE", "").strip().lower()
        if override in PROFILES:
            self.profile_name = override

        profile = PROFILES[self.profile_name]

        # Set every key as an attribute
        for k, v in profile.items():
            setattr(self, k, v)

    def summary(self):
        return (
            f"Board: {self.board} | RAM: {self.ram_mb} MB | CPUs: {self.cpus} | "
            f"Profile: {self.profile_name} ({self.label})"
        )


# Singleton — import and use directly
HW = HardwareProfile()
