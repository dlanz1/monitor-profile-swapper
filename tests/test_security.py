import unittest
import zipfile
import os
import shutil
from updater import safe_extract

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
        self.create_zip(['../evil.txt'])

        with zipfile.ZipFile(self.zip_name, 'r') as zip_ref:
            with self.assertRaises(Exception) as cm:
                safe_extract(zip_ref, self.test_dir)

            self.assertIn("path traversal", str(cm.exception).lower())

        self.assertFalse(os.path.exists('evil.txt'))

    def test_safe_extract_allows_safe_files(self):
        self.create_zip(['safe.txt', 'subdir/safe2.txt'])

        with zipfile.ZipFile(self.zip_name, 'r') as zip_ref:
            safe_extract(zip_ref, self.test_dir)

        self.assertTrue(os.path.exists(os.path.join(self.test_dir, 'safe.txt')))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, 'subdir', 'safe2.txt')))

if __name__ == '__main__':
    unittest.main()
