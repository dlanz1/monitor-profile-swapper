"""
Unit tests for single-instance mutex functionality.
Tests for Bug #1: Multiple instance prevention.
"""

import unittest
import ctypes
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monitor_swapper import SingleInstanceMutex, ERROR_ALREADY_EXISTS


@unittest.skipUnless(sys.platform == 'win32', "Requires Windows")
class TestSingleInstanceMutex(unittest.TestCase):
    """Tests for the SingleInstanceMutex class."""

    def setUp(self):
        """Use a unique mutex name for each test to avoid conflicts."""
        self.test_mutex_name = f"TestMutex_{os.getpid()}_{id(self)}"
        self.mutex = None
        self.second_mutex = None

    def tearDown(self):
        """Clean up any mutexes created during tests."""
        if self.mutex:
            self.mutex.release()
        if self.second_mutex:
            self.second_mutex.release()

    def test_first_instance_acquires_mutex(self):
        """Test that the first instance can acquire the mutex."""
        self.mutex = SingleInstanceMutex(self.test_mutex_name)
        
        result = self.mutex.acquire()
        
        self.assertTrue(result)
        self.assertIsNotNone(self.mutex.mutex_handle)

    def test_second_instance_fails_to_acquire(self):
        """Test that a second instance cannot acquire the same mutex."""
        self.mutex = SingleInstanceMutex(self.test_mutex_name)
        self.second_mutex = SingleInstanceMutex(self.test_mutex_name)
        
        # First instance acquires
        first_result = self.mutex.acquire()
        self.assertTrue(first_result)
        
        # Second instance should fail
        second_result = self.second_mutex.acquire()
        self.assertFalse(second_result)

    def test_release_allows_new_acquisition(self):
        """Test that releasing a mutex allows another instance to acquire it."""
        self.mutex = SingleInstanceMutex(self.test_mutex_name)
        self.second_mutex = SingleInstanceMutex(self.test_mutex_name)
        
        # First instance acquires and releases
        first_result = self.mutex.acquire()
        self.assertTrue(first_result)
        self.mutex.release()
        
        # Second instance should now succeed
        second_result = self.second_mutex.acquire()
        self.assertTrue(second_result)

    def test_multiple_releases_safe(self):
        """Test that calling release multiple times doesn't crash."""
        self.mutex = SingleInstanceMutex(self.test_mutex_name)
        self.mutex.acquire()
        
        # Multiple releases should be safe
        self.mutex.release()
        self.mutex.release()
        self.mutex.release()
        
        self.assertIsNone(self.mutex.mutex_handle)

    def test_release_without_acquire(self):
        """Test that releasing without acquiring doesn't crash."""
        self.mutex = SingleInstanceMutex(self.test_mutex_name)
        
        # Should not raise an exception
        self.mutex.release()
        
        self.assertIsNone(self.mutex.mutex_handle)

    def test_different_mutex_names_independent(self):
        """Test that different mutex names don't interfere."""
        self.mutex = SingleInstanceMutex(f"{self.test_mutex_name}_A")
        self.second_mutex = SingleInstanceMutex(f"{self.test_mutex_name}_B")
        
        # Both should succeed because they have different names
        first_result = self.mutex.acquire()
        second_result = self.second_mutex.acquire()
        
        self.assertTrue(first_result)
        self.assertTrue(second_result)


@unittest.skipUnless(sys.platform == 'win32', "Requires Windows")
class TestErrorAlreadyExistsConstant(unittest.TestCase):
    """Test that the ERROR_ALREADY_EXISTS constant is correct."""

    def test_error_constant_value(self):
        """Test that ERROR_ALREADY_EXISTS has the correct Windows API value."""
        # Windows API ERROR_ALREADY_EXISTS is 183
        self.assertEqual(ERROR_ALREADY_EXISTS, 183)


if __name__ == '__main__':
    unittest.main()
