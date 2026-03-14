#!/usr/bin/env python3
"""
Tests for hardware_profile.py — hardware auto-detection and performance profiles.

Run:
    cd vitrine_interactive
    python -m pytest test_hardware_profile.py -v
    # or simply:
    python test_hardware_profile.py
"""

import os
import unittest
from unittest.mock import patch

# Import the module under test
import hardware_profile
from hardware_profile import (
    _detect_board,
    _total_ram_mb,
    _select_profile,
    PROFILES,
    HardwareProfile,
)


class TestDetectBoard(unittest.TestCase):
    """Test board detection from /proc/device-tree/model."""

    @patch("hardware_profile._read_file", return_value="Raspberry Pi Zero 2 W Rev 1.0\x00")
    def test_pi_zero_2w(self, _):
        self.assertEqual(_detect_board(), "pi_zero2w")

    @patch("hardware_profile._read_file", return_value="Raspberry Pi Zero W Rev 1.1\x00")
    def test_pi_zero_w(self, _):
        self.assertEqual(_detect_board(), "pi_zero")

    @patch("hardware_profile._read_file", return_value="Raspberry Pi 3 Model B Plus Rev 1.3\x00")
    def test_pi3(self, _):
        self.assertEqual(_detect_board(), "pi3")

    @patch("hardware_profile._read_file", return_value="Raspberry Pi 4 Model B Rev 1.4\x00")
    def test_pi4(self, _):
        self.assertEqual(_detect_board(), "pi4")

    @patch("hardware_profile._read_file", return_value="Raspberry Pi 5 Model B Rev 1.0\x00")
    def test_pi5(self, _):
        self.assertEqual(_detect_board(), "pi5")

    @patch("hardware_profile._read_file", return_value="")
    def test_pc_no_file(self, _):
        self.assertEqual(_detect_board(), "pc")

    @patch("hardware_profile._read_file", return_value="Some Unknown Raspberry Pi Board\x00")
    def test_unknown_pi(self, _):
        self.assertEqual(_detect_board(), "pi_unknown")


class TestSelectProfile(unittest.TestCase):
    """Test profile selection logic based on board and RAM."""

    def test_pi_zero2w_gets_minimal(self):
        self.assertEqual(_select_profile("pi_zero2w", 512, 4), "minimal")

    def test_pi_zero_gets_minimal(self):
        self.assertEqual(_select_profile("pi_zero", 512, 1), "minimal")

    def test_pi3_gets_low(self):
        self.assertEqual(_select_profile("pi3", 1024, 4), "low")

    def test_pi4_1gb_gets_low(self):
        """Pi 4 with only 1 GB RAM should get low profile."""
        self.assertEqual(_select_profile("pi4", 1024, 4), "low")

    def test_pi4_2gb_gets_medium(self):
        self.assertEqual(_select_profile("pi4", 2048, 4), "medium")

    def test_pi4_4gb_gets_high(self):
        self.assertEqual(_select_profile("pi4", 4096, 4), "high")

    def test_pi5_4gb_gets_high(self):
        self.assertEqual(_select_profile("pi5", 4096, 4), "high")

    def test_pi5_2gb_gets_medium(self):
        self.assertEqual(_select_profile("pi5", 2048, 4), "medium")

    def test_pc_8gb_gets_high(self):
        self.assertEqual(_select_profile("pc", 8192, 8), "high")

    def test_pc_512mb_gets_minimal(self):
        self.assertEqual(_select_profile("pc", 512, 2), "minimal")

    def test_pc_16gb_gets_high(self):
        self.assertEqual(_select_profile("pc", 16384, 16), "high")


class TestProfiles(unittest.TestCase):
    """Validate profile definitions — prevent regressions in expected keys."""

    REQUIRED_KEYS = {
        "label", "frame_width", "frame_height", "camera_fps",
        "capture_loop_sleep", "stream_fps_sleep", "ws_emitter_sleep",
        "jpeg_quality", "face_detection_interval", "face_scale",
        "face_min_size", "face_recognition", "nostr_limit",
        "nostr_refresh", "frontend_poll_ms",
    }

    def test_all_profiles_have_required_keys(self):
        for name, profile in PROFILES.items():
            for key in self.REQUIRED_KEYS:
                self.assertIn(key, profile, f"Profile '{name}' missing key '{key}'")

    def test_profile_names(self):
        self.assertEqual(set(PROFILES.keys()), {"minimal", "low", "medium", "high"})

    def test_frame_dimensions_are_positive(self):
        for name, p in PROFILES.items():
            self.assertGreater(p["frame_width"], 0, f"{name}: frame_width")
            self.assertGreater(p["frame_height"], 0, f"{name}: frame_height")

    def test_jpeg_quality_in_range(self):
        for name, p in PROFILES.items():
            self.assertGreaterEqual(p["jpeg_quality"], 1, f"{name}")
            self.assertLessEqual(p["jpeg_quality"], 100, f"{name}")

    def test_minimal_disables_face_recognition(self):
        self.assertFalse(PROFILES["minimal"]["face_recognition"])
        self.assertFalse(PROFILES["low"]["face_recognition"])

    def test_high_enables_face_recognition(self):
        self.assertTrue(PROFILES["high"]["face_recognition"])
        self.assertTrue(PROFILES["medium"]["face_recognition"])

    def test_profiles_scale_up(self):
        """Higher profiles should have >= resolution and quality."""
        order = ["minimal", "low", "medium", "high"]
        for i in range(len(order) - 1):
            lo = PROFILES[order[i]]
            hi = PROFILES[order[i + 1]]
            self.assertLessEqual(lo["frame_width"], hi["frame_width"],
                                 f"{order[i]} -> {order[i+1]}: frame_width")
            self.assertLessEqual(lo["jpeg_quality"], hi["jpeg_quality"],
                                 f"{order[i]} -> {order[i+1]}: jpeg_quality")


class TestHardwareProfileInstance(unittest.TestCase):
    """Test the HardwareProfile class instantiation."""

    @patch.dict(os.environ, {"VITRINE_PROFILE": "minimal"}, clear=False)
    def test_env_override(self):
        hp = HardwareProfile()
        self.assertEqual(hp.profile_name, "minimal")
        self.assertEqual(hp.frame_width, 320)

    @patch.dict(os.environ, {"VITRINE_PROFILE": "high"}, clear=False)
    def test_env_override_high(self):
        hp = HardwareProfile()
        self.assertEqual(hp.profile_name, "high")
        self.assertEqual(hp.frame_width, 1280)

    @patch.dict(os.environ, {"VITRINE_PROFILE": "invalid_name"}, clear=False)
    def test_env_override_invalid_ignored(self):
        hp = HardwareProfile()
        # Should not crash, falls back to auto-detected profile
        self.assertIn(hp.profile_name, PROFILES)

    def test_summary_is_string(self):
        hp = HardwareProfile()
        s = hp.summary()
        self.assertIsInstance(s, str)
        self.assertIn("Profile:", s)
        self.assertIn("RAM:", s)

    def test_all_attributes_present(self):
        hp = HardwareProfile()
        for key in TestProfiles.REQUIRED_KEYS:
            self.assertTrue(hasattr(hp, key), f"Missing attribute: {key}")


class TestFaceRecognitionByProfile(unittest.TestCase):
    """Test that face recognition is enabled/disabled based on machine profile.

    On constrained hardware (Pi Zero 2W, Pi 3), face recognition via dlib
    is too heavy — the profile must disable it. On capable machines (Pi 4 2GB+,
    PC), it should be allowed.
    """

    @patch.dict(os.environ, {"VITRINE_PROFILE": "minimal"}, clear=False)
    def test_minimal_disables_face_recognition(self):
        """Pi Zero 2W (512 MB) — face_recognition must be disabled."""
        hp = HardwareProfile()
        self.assertFalse(hp.face_recognition,
                         "minimal profile should disable face recognition (dlib too heavy for 512 MB)")

    @patch.dict(os.environ, {"VITRINE_PROFILE": "low"}, clear=False)
    def test_low_disables_face_recognition(self):
        """Pi 3 / 1 GB — face_recognition must be disabled."""
        hp = HardwareProfile()
        self.assertFalse(hp.face_recognition,
                         "low profile should disable face recognition")

    @patch.dict(os.environ, {"VITRINE_PROFILE": "medium"}, clear=False)
    def test_medium_enables_face_recognition(self):
        """Pi 4 2-4 GB — face_recognition should be available."""
        hp = HardwareProfile()
        self.assertTrue(hp.face_recognition,
                        "medium profile should enable face recognition")

    @patch.dict(os.environ, {"VITRINE_PROFILE": "high"}, clear=False)
    def test_high_enables_face_recognition(self):
        """PC / Pi 5 4 GB+ — face_recognition should be available."""
        hp = HardwareProfile()
        self.assertTrue(hp.face_recognition,
                        "high profile should enable face recognition")

    def test_face_detection_interval_scales_with_profile(self):
        """Lower-end profiles should detect faces less often to save CPU."""
        intervals = {}
        for profile_name in PROFILES:
            intervals[profile_name] = PROFILES[profile_name]["face_detection_interval"]

        # Minimal should have the largest interval (least frequent)
        self.assertGreater(intervals["minimal"], intervals["medium"])
        self.assertGreater(intervals["low"], intervals["medium"])
        # High should be the most frequent
        self.assertLessEqual(intervals["high"], intervals["medium"])

    def test_face_scale_smaller_on_constrained_hw(self):
        """Constrained hardware should use smaller face detection scale."""
        self.assertLess(PROFILES["minimal"]["face_scale"],
                        PROFILES["high"]["face_scale"])
        self.assertLess(PROFILES["low"]["face_scale"],
                        PROFILES["high"]["face_scale"])

    @patch.dict(os.environ, {"VITRINE_PROFILE": "minimal"}, clear=False)
    def test_minimal_camera_resolution(self):
        """Pi Zero 2W should use 320x240 to keep CPU/memory manageable."""
        hp = HardwareProfile()
        self.assertEqual(hp.frame_width, 320)
        self.assertEqual(hp.frame_height, 240)
        self.assertLessEqual(hp.camera_fps, 15)

    @patch.dict(os.environ, {"VITRINE_PROFILE": "high"}, clear=False)
    def test_high_camera_resolution(self):
        """PC should use 1280x720 for best face detection accuracy."""
        hp = HardwareProfile()
        self.assertEqual(hp.frame_width, 1280)
        self.assertEqual(hp.frame_height, 720)


class TestSingleton(unittest.TestCase):
    """The module exports a HW singleton."""

    def test_hw_exists(self):
        from hardware_profile import HW
        self.assertIsInstance(HW, HardwareProfile)
        self.assertIn(HW.profile_name, PROFILES)


if __name__ == "__main__":
    unittest.main()
