"""
Comprehensive tests for the updater module.

Tests cover:
- Network request retry logic
- Checksum verification
- Version comparison
- Folder flattening for GitHub releases
- Error handling scenarios
- API response parsing
"""

import unittest
import os
import sys
import shutil
import tempfile
import hashlib
import json
from unittest.mock import Mock, patch, MagicMock
import zipfile

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import updater
from updater import (
    _calculate_sha256,
    _verify_checksum,
    _flatten_nested_folder,
    _remove_readonly,
    check_for_updates,
    perform_update,
    cleanup_update_artifacts,
    PathTraversalError,
    safe_extract,
    CURRENT_VERSION,
)


class TestChecksumVerification(unittest.TestCase):
    """Tests for checksum calculation and verification."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.test_dir, 'test_file.bin')
        # Create a test file with known content
        with open(self.test_file, 'wb') as f:
            f.write(b'Hello, World!')

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, onerror=_remove_readonly)

    def test_calculate_sha256_correct_hash(self):
        """Test that SHA256 calculation produces correct hash."""
        # Known SHA256 of "Hello, World!"
        expected_hash = "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"
        actual_hash = _calculate_sha256(self.test_file)
        self.assertEqual(actual_hash, expected_hash)

    def test_verify_checksum_valid(self):
        """Test checksum verification with valid hash."""
        valid_hash = "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"
        self.assertTrue(_verify_checksum(self.test_file, valid_hash))

    def test_verify_checksum_case_insensitive(self):
        """Test checksum verification is case-insensitive."""
        uppercase_hash = "DFFD6021BB2BD5B0AF676290809EC3A53191DD81C7F70A4B28688A362182986F"
        self.assertTrue(_verify_checksum(self.test_file, uppercase_hash))

    def test_verify_checksum_invalid(self):
        """Test checksum verification with invalid hash."""
        invalid_hash = "0000000000000000000000000000000000000000000000000000000000000000"
        self.assertFalse(_verify_checksum(self.test_file, invalid_hash))

    def test_calculate_sha256_empty_file(self):
        """Test SHA256 of empty file."""
        empty_file = os.path.join(self.test_dir, 'empty.bin')
        with open(empty_file, 'wb') as f:
            pass
        # Known SHA256 of empty string
        expected_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        actual_hash = _calculate_sha256(empty_file)
        self.assertEqual(actual_hash, expected_hash)


class TestFlattenNestedFolder(unittest.TestCase):
    """Tests for GitHub release folder flattening."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, onerror=_remove_readonly)

    def test_flatten_single_nested_folder(self):
        """Test flattening a single nested folder structure."""
        # Create nested structure: test_dir/repo-v1.0.0/file.txt
        nested_folder = os.path.join(self.test_dir, 'repo-v1.0.0')
        os.makedirs(nested_folder)
        test_file = os.path.join(nested_folder, 'file.txt')
        with open(test_file, 'w') as f:
            f.write('test content')

        # Flatten
        result = _flatten_nested_folder(self.test_dir)

        # Verify
        self.assertTrue(result)
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, 'file.txt')))
        self.assertFalse(os.path.exists(nested_folder))

    def test_flatten_nested_folder_with_subdirs(self):
        """Test flattening nested folder containing subdirectories."""
        # Create: test_dir/repo-v1.0.0/src/main.py and test_dir/repo-v1.0.0/README.md
        nested_folder = os.path.join(self.test_dir, 'repo-v1.0.0')
        src_folder = os.path.join(nested_folder, 'src')
        os.makedirs(src_folder)

        with open(os.path.join(nested_folder, 'README.md'), 'w') as f:
            f.write('# Readme')
        with open(os.path.join(src_folder, 'main.py'), 'w') as f:
            f.write('print("hello")')

        # Flatten
        result = _flatten_nested_folder(self.test_dir)

        # Verify
        self.assertTrue(result)
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, 'README.md')))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, 'src', 'main.py')))
        self.assertFalse(os.path.exists(nested_folder))

    def test_no_flatten_multiple_items(self):
        """Test no flattening when multiple items at root level."""
        # Create: test_dir/file1.txt and test_dir/file2.txt
        with open(os.path.join(self.test_dir, 'file1.txt'), 'w') as f:
            f.write('file 1')
        with open(os.path.join(self.test_dir, 'file2.txt'), 'w') as f:
            f.write('file 2')

        # Should not flatten
        result = _flatten_nested_folder(self.test_dir)

        # Verify
        self.assertFalse(result)
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, 'file1.txt')))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, 'file2.txt')))

    def test_no_flatten_single_file(self):
        """Test no flattening when single item is a file, not folder."""
        # Create: test_dir/file.txt (single file, not folder)
        with open(os.path.join(self.test_dir, 'file.txt'), 'w') as f:
            f.write('content')

        # Should not flatten
        result = _flatten_nested_folder(self.test_dir)

        # Verify
        self.assertFalse(result)
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, 'file.txt')))

    def test_flatten_empty_folder(self):
        """Test flattening with empty nested folder."""
        empty_folder = os.path.join(self.test_dir, 'empty-folder')
        os.makedirs(empty_folder)

        # Should flatten (remove empty folder)
        result = _flatten_nested_folder(self.test_dir)

        self.assertTrue(result)
        self.assertFalse(os.path.exists(empty_folder))


class TestRetryLogic(unittest.TestCase):
    """Tests for network request retry functionality."""

    @patch('updater.requests.get')
    @patch('updater.time.sleep')
    def test_retry_succeeds_on_second_attempt(self, mock_sleep, mock_get):
        """Test that retry logic succeeds after first failure."""
        import requests.exceptions
        
        # First call fails, second succeeds
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        mock_get.side_effect = [
            requests.exceptions.ConnectionError("Network error"),
            mock_response
        ]

        from updater import _request_with_retry
        result = _request_with_retry("http://example.com", max_retries=3)

        self.assertEqual(result, mock_response)
        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(mock_sleep.call_count, 1)

    @patch('updater.requests.get')
    @patch('updater.time.sleep')
    def test_retry_exhausts_all_attempts(self, mock_sleep, mock_get):
        """Test that all retry attempts are exhausted before raising."""
        import requests.exceptions

        mock_get.side_effect = requests.exceptions.ConnectionError("Failed")

        from updater import _request_with_retry
        with self.assertRaises(requests.exceptions.ConnectionError):
            _request_with_retry("http://example.com", max_retries=3)

        self.assertEqual(mock_get.call_count, 3)

    @patch('updater.requests.get')
    def test_no_retry_on_success(self, mock_get):
        """Test that no retry occurs when request succeeds immediately."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        from updater import _request_with_retry
        result = _request_with_retry("http://example.com", max_retries=3)

        self.assertEqual(result, mock_response)
        self.assertEqual(mock_get.call_count, 1)


class TestCheckForUpdates(unittest.TestCase):
    """Tests for the check_for_updates function."""

    @patch('updater._request_with_retry')
    def test_update_available(self, mock_request):
        """Test detection of available update."""
        mock_response = Mock()
        mock_response.json.return_value = {"tag_name": "v999.0.0"}
        mock_request.return_value = mock_response

        result = check_for_updates()

        self.assertIsNotNone(result)
        self.assertEqual(result["tag_name"], "v999.0.0")

    @patch('updater._request_with_retry')
    def test_no_update_current_is_latest(self, mock_request):
        """Test when current version is latest."""
        mock_response = Mock()
        mock_response.json.return_value = {"tag_name": CURRENT_VERSION}
        mock_request.return_value = mock_response

        result = check_for_updates()

        self.assertIsNone(result)

    @patch('updater._request_with_retry')
    def test_no_update_older_release(self, mock_request):
        """Test when release is older than current version."""
        mock_response = Mock()
        mock_response.json.return_value = {"tag_name": "v0.0.1"}
        mock_request.return_value = mock_response

        result = check_for_updates()

        self.assertIsNone(result)

    @patch('updater._request_with_retry')
    def test_handles_missing_tag_name(self, mock_request):
        """Test handling of release without tag_name."""
        mock_response = Mock()
        mock_response.json.return_value = {"name": "No tag release"}  # Missing tag_name
        mock_request.return_value = mock_response

        result = check_for_updates()

        self.assertIsNone(result)

    @patch('updater._request_with_retry')
    def test_handles_network_error(self, mock_request):
        """Test handling of network errors."""
        import requests.exceptions
        mock_request.side_effect = requests.exceptions.ConnectionError("No internet")

        result = check_for_updates()

        self.assertIsNone(result)

    @patch('updater._request_with_retry')
    def test_handles_invalid_version_format(self, mock_request):
        """Test handling of unparseable version strings."""
        mock_response = Mock()
        mock_response.json.return_value = {"tag_name": "not-a-version"}
        mock_request.return_value = mock_response

        result = check_for_updates()

        self.assertIsNone(result)

    @patch('updater._request_with_retry')
    def test_handles_rate_limit(self, mock_request):
        """Test handling of GitHub API rate limiting."""
        import requests.exceptions
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.headers = {'X-RateLimit-Remaining': '0'}

        error = requests.exceptions.HTTPError()
        error.response = mock_response
        mock_request.side_effect = error

        result = check_for_updates()

        self.assertIsNone(result)


class TestPerformUpdate(unittest.TestCase):
    """Tests for the perform_update function."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        # Patch BASE_DIR for testing
        self.base_dir_patch = patch('updater.BASE_DIR', self.test_dir)
        self.base_dir_patch.start()

    def tearDown(self):
        self.base_dir_patch.stop()
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, onerror=_remove_readonly)

    def test_no_zip_asset_returns_false(self):
        """Test that missing zip asset returns False."""
        release_data = {
            "tag_name": "v2.0.0",
            "assets": [
                {"name": "readme.txt", "browser_download_url": "http://example.com/readme.txt"}
            ]
        }

        result = perform_update(release_data)

        self.assertFalse(result)

    def test_empty_assets_returns_false(self):
        """Test that empty assets list returns False."""
        release_data = {
            "tag_name": "v2.0.0",
            "assets": []
        }

        result = perform_update(release_data)

        self.assertFalse(result)

    @patch('updater._show_error')
    @patch('updater._download_with_progress')
    def test_prefers_release_zip(self, mock_download, mock_show_error):
        """Test that Release.zip is preferred over other zips."""
        release_data = {
            "tag_name": "v2.0.0",
            "assets": [
                {"name": "source.zip", "browser_download_url": "http://example.com/source.zip"},
                {"name": "Release.zip", "browser_download_url": "http://example.com/release.zip"},
            ]
        }

        # Make download fail to abort early but check which URL was used
        mock_download.side_effect = Exception("Test abort")

        perform_update(release_data)

        # Verify the correct URL was used
        call_args = mock_download.call_args
        self.assertIn("release.zip", call_args[0][0])

    @patch('updater._show_error')
    @patch('updater._download_with_progress')
    @patch('updater._request_with_retry')
    def test_fetches_checksum_file(self, mock_request, mock_download, mock_show_error):
        """Test that checksum file is fetched when available."""
        release_data = {
            "tag_name": "v2.0.0",
            "assets": [
                {"name": "sha256.txt", "browser_download_url": "http://example.com/sha256.txt"},
                {"name": "Release.zip", "browser_download_url": "http://example.com/release.zip"},
            ]
        }

        # Mock checksum response
        mock_checksum_response = Mock()
        mock_checksum_response.text = "abcd1234  Release.zip"
        mock_request.return_value = mock_checksum_response

        # Make download fail to abort early
        mock_download.side_effect = Exception("Test abort")

        perform_update(release_data)

        # Verify checksum was fetched
        mock_request.assert_called()


class TestCleanupArtifacts(unittest.TestCase):
    """Tests for cleanup_update_artifacts function."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.base_dir_patch = patch('updater.BASE_DIR', self.test_dir)
        self.base_dir_patch.start()

    def tearDown(self):
        self.base_dir_patch.stop()
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, onerror=_remove_readonly)

    def test_cleans_zip_file(self):
        """Test cleanup removes leftover zip file."""
        zip_path = os.path.join(self.test_dir, "update_pkg.zip")
        with open(zip_path, 'w') as f:
            f.write('fake zip')

        result = cleanup_update_artifacts()

        self.assertTrue(result)
        self.assertFalse(os.path.exists(zip_path))

    def test_cleans_temp_folder(self):
        """Test cleanup removes leftover temp folder."""
        temp_folder = os.path.join(self.test_dir, "update_tmp")
        os.makedirs(temp_folder)
        with open(os.path.join(temp_folder, 'file.txt'), 'w') as f:
            f.write('temp file')

        result = cleanup_update_artifacts()

        self.assertTrue(result)
        self.assertFalse(os.path.exists(temp_folder))

    def test_no_cleanup_needed(self):
        """Test cleanup returns False when nothing to clean."""
        result = cleanup_update_artifacts()

        self.assertFalse(result)


class TestVersionParsing(unittest.TestCase):
    """Tests for version comparison edge cases."""

    @patch('updater._request_with_retry')
    def test_handles_prerelease_versions(self, mock_request):
        """Test handling of pre-release version tags."""
        mock_response = Mock()
        mock_response.json.return_value = {"tag_name": "v999.0.0-beta.1"}
        mock_request.return_value = mock_response

        # Should still detect as newer
        result = check_for_updates()

        # Pre-release versions are typically considered newer in packaging
        self.assertIsNotNone(result)

    @patch('updater._request_with_retry')
    def test_handles_version_without_v_prefix(self, mock_request):
        """Test handling of versions without 'v' prefix."""
        mock_response = Mock()
        mock_response.json.return_value = {"tag_name": "999.0.0"}  # No 'v' prefix
        mock_request.return_value = mock_response

        result = check_for_updates()

        self.assertIsNotNone(result)


class TestDownloadWithProgress(unittest.TestCase):
    """Tests for download with progress functionality."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, onerror=_remove_readonly)

    @patch('updater._request_with_retry')
    def test_download_success(self, mock_request):
        """Test successful download."""
        # Create mock response with content
        mock_response = Mock()
        mock_response.headers = {'content-length': '13'}
        mock_response.iter_content.return_value = [b'Hello, World!']
        mock_request.return_value = mock_response

        dest_path = os.path.join(self.test_dir, 'downloaded.bin')

        from updater import _download_with_progress
        result = _download_with_progress("http://example.com/file", dest_path)

        self.assertTrue(result)
        self.assertTrue(os.path.exists(dest_path))
        with open(dest_path, 'rb') as f:
            self.assertEqual(f.read(), b'Hello, World!')

    @patch('updater._request_with_retry')
    def test_download_incomplete_raises(self, mock_request):
        """Test that incomplete download raises IOError."""
        mock_response = Mock()
        mock_response.headers = {'content-length': '1000'}  # Claims 1000 bytes
        mock_response.iter_content.return_value = [b'Short']  # Only 5 bytes
        mock_request.return_value = mock_response

        dest_path = os.path.join(self.test_dir, 'downloaded.bin')

        from updater import _download_with_progress
        with self.assertRaises(IOError) as cm:
            _download_with_progress("http://example.com/file", dest_path)

        self.assertIn("Incomplete download", str(cm.exception))

    @patch('updater._request_with_retry')
    def test_progress_callback_called(self, mock_request):
        """Test that progress callback is invoked."""
        mock_response = Mock()
        mock_response.headers = {'content-length': '100'}
        mock_response.iter_content.return_value = [b'x' * 25, b'x' * 25, b'x' * 25, b'x' * 25]
        mock_request.return_value = mock_response

        dest_path = os.path.join(self.test_dir, 'downloaded.bin')
        progress_calls = []

        def progress_cb(downloaded, total):
            progress_calls.append((downloaded, total))

        from updater import _download_with_progress
        _download_with_progress("http://example.com/file", dest_path, progress_cb)

        # Should have been called multiple times
        self.assertGreater(len(progress_calls), 0)
        # Last call should have full size
        self.assertEqual(progress_calls[-1][0], 100)


if __name__ == '__main__':
    unittest.main()
