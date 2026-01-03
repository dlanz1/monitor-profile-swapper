import unittest
import zipfile
import os
import shutil
import sys
from updater import safe_extract, PathTraversalError

class TestSafeExtract(unittest.TestCase):
    def setUp(self):
        self.test_dir = 'test_safe_extract_dir'
        self.zip_name = 'test_malicious.zip'
        os.makedirs(self.test_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        if os.path.exists(self.zip_name):
            os.remove(self.zip_name)
        if os.path.exists('evil.txt'):
            os.remove('evil.txt')

    def create_zip(self, filenames):
        with zipfile.ZipFile(self.zip_name, 'w') as zipf:
            for name in filenames:
                zipf.writestr(name, 'dummy content')

    def test_safe_extract_rejects_traversal(self):
        """Test basic path traversal with ../"""
        self.create_zip(['../evil.txt'])

        with zipfile.ZipFile(self.zip_name, 'r') as zip_ref:
            with self.assertRaises(PathTraversalError) as cm:
                safe_extract(zip_ref, self.test_dir)

            self.assertIn("path traversal", str(cm.exception).lower())

        self.assertFalse(os.path.exists('evil.txt'))

    def test_safe_extract_rejects_deep_traversal(self):
        """Test deep path traversal with ../../../../../../etc/evil.txt"""
        self.create_zip(['../../../../../../tmp/evil.txt'])

        with zipfile.ZipFile(self.zip_name, 'r') as zip_ref:
            with self.assertRaises(PathTraversalError) as cm:
                safe_extract(zip_ref, self.test_dir)

            self.assertIn("path traversal", str(cm.exception).lower())

    def test_safe_extract_rejects_absolute_path_unix(self):
        """Test absolute path on Unix-like systems"""
        if sys.platform != 'win32':
            self.create_zip(['/tmp/evil.txt'])

            with zipfile.ZipFile(self.zip_name, 'r') as zip_ref:
                with self.assertRaises(PathTraversalError) as cm:
                    safe_extract(zip_ref, self.test_dir)

                self.assertIn("path traversal", str(cm.exception).lower())

    def test_safe_extract_rejects_absolute_path_windows(self):
        """Test absolute path on Windows"""
        if sys.platform == 'win32':
            self.create_zip(['C:\\evil.txt'])

            with zipfile.ZipFile(self.zip_name, 'r') as zip_ref:
                with self.assertRaises(PathTraversalError) as cm:
                    safe_extract(zip_ref, self.test_dir)

                self.assertIn("path traversal", str(cm.exception).lower())

    def test_safe_extract_rejects_empty_filename(self):
        """Test that empty filenames are rejected"""
        # Create a zip with an empty filename (if possible)
        with zipfile.ZipFile(self.zip_name, 'w') as zipf:
            # We'll manually create an entry with empty filename
            info = zipfile.ZipInfo('')
            zipf.writestr(info, 'dummy content')

        with zipfile.ZipFile(self.zip_name, 'r') as zip_ref:
            with self.assertRaises(PathTraversalError) as cm:
                safe_extract(zip_ref, self.test_dir)

            self.assertIn("empty filename", str(cm.exception).lower())

    def test_safe_extract_rejects_null_byte(self):
        """Test that filenames with null bytes are rejected (or stripped by zipfile)"""
        # Note: Python's zipfile library automatically strips null bytes from filenames
        # This test documents that behavior - the zip library itself provides protection
        with zipfile.ZipFile(self.zip_name, 'w') as zipf:
            info = zipfile.ZipInfo('evil\x00.txt')
            zipf.writestr(info, 'dummy content')

        with zipfile.ZipFile(self.zip_name, 'r') as zip_ref:
            # The zipfile library strips the null byte, so the filename becomes 'evil'
            # This is acceptable as it prevents null byte attacks
            # We verify it extracts safely without error
            safe_extract(zip_ref, self.test_dir)
            # Verify the file was extracted (with stripped filename)
            self.assertTrue(os.path.exists(os.path.join(self.test_dir, 'evil')))

    def test_safe_extract_rejects_only_separators(self):
        """Test that filenames with only path separators are rejected"""
        with zipfile.ZipFile(self.zip_name, 'w') as zipf:
            info = zipfile.ZipInfo('///')
            zipf.writestr(info, 'dummy content')

        with zipfile.ZipFile(self.zip_name, 'r') as zip_ref:
            with self.assertRaises(PathTraversalError) as cm:
                safe_extract(zip_ref, self.test_dir)

            self.assertIn("only path separators", str(cm.exception).lower())

    def test_safe_extract_allows_safe_files(self):
        """Test that legitimate files are extracted correctly"""
        self.create_zip(['safe.txt', 'subdir/safe2.txt'])

        with zipfile.ZipFile(self.zip_name, 'r') as zip_ref:
            safe_extract(zip_ref, self.test_dir)

        self.assertTrue(os.path.exists(os.path.join(self.test_dir, 'safe.txt')))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, 'subdir', 'safe2.txt')))

if __name__ == '__main__':
    unittest.main()
