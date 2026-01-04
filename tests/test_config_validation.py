"""
Unit tests for configuration validation and sanitization.
Tests for Bug #2: Input sanitization and config validation.
"""

import unittest
import json
import os
import sys
import tempfile
import shutil

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monitor_swapper import (
    validate_config, 
    validate_mode_settings, 
    ConfigValidationError,
    DEFAULT_CONFIG
)


class TestConfigValidation(unittest.TestCase):
    """Tests for the validate_config function."""

    def test_valid_config_passes(self):
        """Test that a completely valid config passes without warnings."""
        config = {
            "game_processes": ["game1.exe", "game2.exe"],
            "game_mode": {"brightness": 80, "contrast": 75, "hdr_enabled": True},
            "desktop_mode": {"brightness": 50, "contrast": 50},
            "tray_enabled": True
        }
        
        validated, warnings = validate_config(config)
        
        self.assertEqual(len(warnings), 0)
        self.assertEqual(validated["game_mode"]["brightness"], 80)
        self.assertEqual(validated["game_mode"]["contrast"], 75)
        self.assertEqual(validated["desktop_mode"]["brightness"], 50)
        self.assertEqual(validated["game_processes"], ["game1.exe", "game2.exe"])

    def test_empty_config_uses_defaults(self):
        """Test that an empty config falls back to defaults."""
        config = {}
        
        validated, warnings = validate_config(config)
        
        # Should use default processes
        self.assertEqual(validated["game_processes"], DEFAULT_CONFIG["game_processes"])

    def test_brightness_out_of_bounds_high(self):
        """Test that brightness > 100 is clamped to 100."""
        config = {
            "game_processes": ["test.exe"],
            "game_mode": {"brightness": 200, "contrast": 50},
            "desktop_mode": {"brightness": 150, "contrast": 50}
        }
        
        validated, warnings = validate_config(config)
        
        self.assertEqual(validated["game_mode"]["brightness"], 100)
        self.assertEqual(validated["desktop_mode"]["brightness"], 100)
        self.assertTrue(any("clamped to 100" in w for w in warnings))

    def test_brightness_out_of_bounds_low(self):
        """Test that brightness < 0 is clamped to 0."""
        config = {
            "game_processes": ["test.exe"],
            "game_mode": {"brightness": -50, "contrast": 50},
            "desktop_mode": {"brightness": -10, "contrast": 50}
        }
        
        validated, warnings = validate_config(config)
        
        self.assertEqual(validated["game_mode"]["brightness"], 0)
        self.assertEqual(validated["desktop_mode"]["brightness"], 0)
        self.assertTrue(any("clamped to 0" in w for w in warnings))

    def test_contrast_out_of_bounds(self):
        """Test that contrast values are clamped to 0-100 range."""
        config = {
            "game_processes": ["test.exe"],
            "game_mode": {"brightness": 50, "contrast": 250},
            "desktop_mode": {"brightness": 50, "contrast": -100}
        }
        
        validated, warnings = validate_config(config)
        
        self.assertEqual(validated["game_mode"]["contrast"], 100)
        self.assertEqual(validated["desktop_mode"]["contrast"], 0)

    def test_non_integer_brightness_uses_default(self):
        """Test that non-integer brightness values fall back to default."""
        config = {
            "game_processes": ["test.exe"],
            "game_mode": {"brightness": "high", "contrast": 50},
            "desktop_mode": {"brightness": None, "contrast": 50}
        }
        
        validated, warnings = validate_config(config)
        
        # Should fall back to default of 50
        self.assertEqual(validated["game_mode"]["brightness"], 50)
        self.assertEqual(validated["desktop_mode"]["brightness"], 50)
        self.assertTrue(any("invalid" in w.lower() for w in warnings))

    def test_non_list_game_processes_uses_default(self):
        """Test that non-list game_processes falls back to default."""
        config = {
            "game_processes": "not_a_list",
            "game_mode": {"brightness": 50, "contrast": 50},
            "desktop_mode": {"brightness": 50, "contrast": 50}
        }
        
        validated, warnings = validate_config(config)
        
        self.assertEqual(validated["game_processes"], DEFAULT_CONFIG["game_processes"])
        self.assertTrue(any("should be a list" in w for w in warnings))

    def test_invalid_process_names_filtered(self):
        """Test that invalid process entries are filtered out."""
        config = {
            "game_processes": ["valid.exe", 123, "", None, "  ", "also_valid.exe"],
            "game_mode": {"brightness": 50, "contrast": 50},
            "desktop_mode": {"brightness": 50, "contrast": 50}
        }
        
        validated, warnings = validate_config(config)
        
        self.assertEqual(validated["game_processes"], ["valid.exe", "also_valid.exe"])
        self.assertTrue(any("Invalid process" in w or "skipped" in w for w in warnings))

    def test_path_in_process_name_sanitized(self):
        """Test that full paths in process names are sanitized to filenames."""
        config = {
            "game_processes": [
                "C:\\Games\\MyGame\\game.exe",
                "/usr/games/linux_game.exe",
                "..\\..\\sneaky.exe"
            ],
            "game_mode": {"brightness": 50, "contrast": 50},
            "desktop_mode": {"brightness": 50, "contrast": 50}
        }
        
        validated, warnings = validate_config(config)
        
        # Should extract just the filename
        self.assertIn("game.exe", validated["game_processes"])
        self.assertIn("linux_game.exe", validated["game_processes"])
        self.assertIn("sneaky.exe", validated["game_processes"])
        # Should NOT contain full paths
        self.assertNotIn("C:\\Games\\MyGame\\game.exe", validated["game_processes"])

    def test_non_dict_game_mode_uses_default(self):
        """Test that non-dict game_mode falls back to default."""
        config = {
            "game_processes": ["test.exe"],
            "game_mode": "not_a_dict",
            "desktop_mode": {"brightness": 50, "contrast": 50}
        }
        
        validated, warnings = validate_config(config)
        
        self.assertEqual(validated["game_mode"]["brightness"], DEFAULT_CONFIG["game_mode"]["brightness"])
        self.assertTrue(any("should be an object" in w for w in warnings))

    def test_hdr_enabled_boolean_coercion(self):
        """Test that hdr_enabled is properly coerced to boolean."""
        config = {
            "game_processes": ["test.exe"],
            "game_mode": {"brightness": 50, "contrast": 50, "hdr_enabled": 1},
            "desktop_mode": {"brightness": 50, "contrast": 50}
        }
        
        validated, warnings = validate_config(config)
        
        self.assertTrue(validated["game_mode"]["hdr_enabled"])

    def test_tray_enabled_boolean_coercion(self):
        """Test that tray_enabled is properly coerced to boolean."""
        config = {
            "game_processes": ["test.exe"],
            "game_mode": {"brightness": 50, "contrast": 50},
            "desktop_mode": {"brightness": 50, "contrast": 50},
            "tray_enabled": 0
        }
        
        validated, warnings = validate_config(config)
        
        self.assertFalse(validated["tray_enabled"])

    def test_startup_prompted_preserved(self):
        """Test that startup_prompted flag is preserved when present."""
        config = {
            "game_processes": ["test.exe"],
            "game_mode": {"brightness": 50, "contrast": 50},
            "desktop_mode": {"brightness": 50, "contrast": 50},
            "startup_prompted": True
        }
        
        validated, warnings = validate_config(config)
        
        self.assertTrue(validated.get("startup_prompted"))

    def test_float_brightness_truncated(self):
        """Test that float brightness values are truncated to int."""
        config = {
            "game_processes": ["test.exe"],
            "game_mode": {"brightness": 75.9, "contrast": 50},
            "desktop_mode": {"brightness": 25.1, "contrast": 50}
        }
        
        validated, warnings = validate_config(config)
        
        # Should be truncated to int
        self.assertEqual(validated["game_mode"]["brightness"], 75)
        self.assertEqual(validated["desktop_mode"]["brightness"], 25)

    def test_missing_brightness_uses_default(self):
        """Test that missing brightness uses default value."""
        config = {
            "game_processes": ["test.exe"],
            "game_mode": {"contrast": 80},  # No brightness
            "desktop_mode": {"brightness": 50}  # No contrast
        }
        
        validated, warnings = validate_config(config)
        
        # Should use default 50
        self.assertEqual(validated["game_mode"]["brightness"], 50)
        self.assertEqual(validated["desktop_mode"]["contrast"], 50)


class TestModeSettingsValidation(unittest.TestCase):
    """Tests for the validate_mode_settings helper function."""

    def test_valid_mode_no_warnings(self):
        """Test that valid mode settings produce no warnings."""
        mode = {"brightness": 75, "contrast": 60}
        warnings = []
        
        validated = validate_mode_settings(mode, "test_mode", warnings)
        
        self.assertEqual(len(warnings), 0)
        self.assertEqual(validated["brightness"], 75)
        self.assertEqual(validated["contrast"], 60)

    def test_boundary_values_accepted(self):
        """Test that boundary values (0 and 100) are accepted."""
        mode = {"brightness": 0, "contrast": 100}
        warnings = []
        
        validated = validate_mode_settings(mode, "test_mode", warnings)
        
        self.assertEqual(len(warnings), 0)
        self.assertEqual(validated["brightness"], 0)
        self.assertEqual(validated["contrast"], 100)

    def test_hdr_included_when_requested(self):
        """Test that HDR setting is included when include_hdr=True."""
        mode = {"brightness": 50, "contrast": 50, "hdr_enabled": True}
        warnings = []
        
        validated = validate_mode_settings(mode, "game_mode", warnings, include_hdr=True)
        
        self.assertIn("hdr_enabled", validated)
        self.assertTrue(validated["hdr_enabled"])

    def test_hdr_excluded_when_not_requested(self):
        """Test that HDR setting is excluded when include_hdr=False."""
        mode = {"brightness": 50, "contrast": 50, "hdr_enabled": True}
        warnings = []
        
        validated = validate_mode_settings(mode, "desktop_mode", warnings, include_hdr=False)
        
        self.assertNotIn("hdr_enabled", validated)


class TestMalformedJsonHandling(unittest.TestCase):
    """Tests for malformed JSON file handling."""

    def setUp(self):
        """Create a temporary directory for test config files."""
        self.test_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.test_dir, "config.json")

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir)

    def test_truncated_json(self):
        """Test handling of truncated JSON (incomplete structure)."""
        with open(self.config_path, 'w') as f:
            f.write('{"game_processes": ["test.exe", ')  # Incomplete
        
        # This should be caught by load_config's json.JSONDecodeError handler
        # We're testing the validation layer here, so we simulate what load_config does
        try:
            with open(self.config_path, 'r') as f:
                json.load(f)
            self.fail("Should have raised JSONDecodeError")
        except json.JSONDecodeError:
            pass  # Expected

    def test_unicode_process_names(self):
        """Test handling of unicode characters in process names."""
        config = {
            "game_processes": ["游戏.exe", "ゲーム.exe", "spëcial.exe"],
            "game_mode": {"brightness": 50, "contrast": 50},
            "desktop_mode": {"brightness": 50, "contrast": 50}
        }
        
        validated, warnings = validate_config(config)
        
        # Unicode names should be preserved
        self.assertEqual(len(validated["game_processes"]), 3)


class TestEdgeCases(unittest.TestCase):
    """Tests for edge cases and boundary conditions."""

    def test_very_long_process_name(self):
        """Test handling of very long process names."""
        long_name = "a" * 500 + ".exe"
        config = {
            "game_processes": [long_name],
            "game_mode": {"brightness": 50, "contrast": 50},
            "desktop_mode": {"brightness": 50, "contrast": 50}
        }
        
        validated, warnings = validate_config(config)
        
        # Should still be accepted (let OS handle filename limits)
        self.assertEqual(validated["game_processes"], [long_name])

    def test_empty_process_list_uses_default(self):
        """Test that empty process list falls back to default."""
        config = {
            "game_processes": [],
            "game_mode": {"brightness": 50, "contrast": 50},
            "desktop_mode": {"brightness": 50, "contrast": 50}
        }
        
        validated, warnings = validate_config(config)
        
        # Empty list should trigger default
        self.assertEqual(validated["game_processes"], DEFAULT_CONFIG["game_processes"])

    def test_extreme_values(self):
        """Test handling of extreme numeric values."""
        config = {
            "game_processes": ["test.exe"],
            "game_mode": {"brightness": 999999999, "contrast": -999999999},
            "desktop_mode": {"brightness": float('inf'), "contrast": 50}
        }
        
        validated, warnings = validate_config(config)
        
        # Should be clamped
        self.assertEqual(validated["game_mode"]["brightness"], 100)
        self.assertEqual(validated["game_mode"]["contrast"], 0)
        # infinity should trigger validation error and use default
        self.assertEqual(validated["desktop_mode"]["brightness"], 50)


if __name__ == '__main__':
    unittest.main()
