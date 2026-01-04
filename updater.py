import requests
import os
import sys
import subprocess
import zipfile
import shutil
import time
import stat
import re
import hashlib
import random
from packaging import version

# Current version of the application
CURRENT_VERSION = "v1.5.0"

# GitHub Repository details
REPO_OWNER = "dlanz1"
REPO_NAME = "monitor-profile-swapper"

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(os.path.realpath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.realpath(os.path.abspath(__file__)))

def _remove_readonly(func, path, excinfo):
    """Error handler for shutil.rmtree to handle read-only files on Windows."""
    os.chmod(path, stat.S_IWRITE)
    func(path)

def _escape_batch_path(path):
    """Escape special characters in paths for batch script safety."""
    # Replace problematic batch characters
    return path.replace('%', '%%')

def cleanup_update_artifacts():
    """
    Removes leftover update files from a previous update attempt.
    Call this at startup to ensure no stale files remain if the batch script failed.
    """
    zip_path = os.path.join(BASE_DIR, "update_pkg.zip")
    extract_folder = os.path.join(BASE_DIR, "update_tmp")
    
    zip_cleaned = False
    folder_cleaned = False
    
    # Clean up ZIP file
    if os.path.exists(zip_path):
        try:
            os.remove(zip_path)
            print(f"   Cleaned up leftover update archive: {zip_path}")
            zip_cleaned = True
        except Exception as e:
            print(f"   Warning: Failed to clean update archive: {e}")
    
    # Clean up extract folder
    if os.path.exists(extract_folder):
        try:
            shutil.rmtree(extract_folder, onerror=_remove_readonly)
            print(f"   Cleaned up leftover update folder: {extract_folder}")
            folder_cleaned = True
        except Exception as e:
            print(f"   Warning: Failed to clean update folder: {e}")
    
    return zip_cleaned or folder_cleaned

class PathTraversalError(Exception):
    """Exception raised when a zip file contains a path traversal attempt."""
    pass


def safe_extract(zip_ref, target_dir):
    """
    Extracts files from a zip archive to a target directory,
    ensuring that no files are extracted outside the target directory.
    Validates against path traversal attacks and symbolic link exploits.
    """
    target_dir = os.path.abspath(target_dir)
    for member in zip_ref.infolist():
        filename = member.filename

        # Validate filename is not empty and not just path separators
        if not filename:
            raise PathTraversalError("Invalid filename in zip file: empty filename")
        if not filename.strip("/\\"):
            raise PathTraversalError(f"Invalid filename in zip file (only path separators): {filename!r}")

        # Normalize and validate the path
        member_path = os.path.abspath(os.path.normpath(os.path.join(target_dir, filename)))

        # Prevent path traversal (e.g., ../../../etc/passwd)
        try:
            if os.path.commonpath([target_dir, member_path]) != target_dir:
                raise PathTraversalError(f"Attempted path traversal in zip file: {member.filename}")
        except ValueError:
            # On Windows, os.path.commonpath raises ValueError if paths are on different drives.
            # If they are on different drives, it's definitely a traversal attempt.
            raise PathTraversalError(f"Attempted path traversal (different drive) in zip file: {member.filename}")

        # Reject symbolic links to prevent symlink-based attacks
        # Note: This check relies on Unix file permissions in external_attr (bits 16-31).
        # It works for zip files created on Unix/Linux systems but may not detect
        # symlinks in zip files created on Windows or by non-standard tools.
        if (member.external_attr >> 16) & 0o170000 == stat.S_IFLNK:
            raise PathTraversalError(f"Zip file contains symbolic link: {member.filename}")

        # Extract each validated member individually to maintain full control
        zip_ref.extract(member, target_dir)


def _show_error(title, message):
    """
    Show error message to user.
    For frozen executables, displays a Windows MessageBox.
    For development/source runs, prints to console.
    """
    print(f"   Error: {message}")
    if getattr(sys, 'frozen', False):
        try:
            import ctypes
            MB_OK = 0x0
            MB_ICONERROR = 0x10
            MB_TOPMOST = 0x40000
            ctypes.windll.user32.MessageBoxW(0, message, title, MB_OK | MB_ICONERROR | MB_TOPMOST)
        except Exception:
            pass  # If MessageBox fails, we already printed to console


def _show_info(title, message):
    """
    Show informational message to user.
    For frozen executables, displays a Windows MessageBox.
    """
    print(f"   Info: {message}")
    if getattr(sys, 'frozen', False):
        try:
            import ctypes
            MB_OK = 0x0
            MB_ICONINFO = 0x40
            MB_TOPMOST = 0x40000
            ctypes.windll.user32.MessageBoxW(0, message, title, MB_OK | MB_ICONINFO | MB_TOPMOST)
        except Exception:
            pass


def _request_with_retry(url, max_retries=3, timeout=10, stream=False):
    """
    Make HTTP GET request with exponential backoff retry.
    
    Args:
        url: URL to request
        max_retries: Maximum number of retry attempts
        timeout: Request timeout in seconds
        stream: Whether to stream the response
        
    Returns:
        Response object on success
        
    Raises:
        requests.exceptions.RequestException on failure after all retries
    """
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=timeout, stream=stream)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            last_exception = e
            if attempt < max_retries - 1:
                # Exponential backoff with jitter
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                print(f"   Network error (attempt {attempt + 1}/{max_retries}): {e}")
                print(f"   Retrying in {wait_time:.1f} seconds...")
                time.sleep(wait_time)
            else:
                print(f"   Network error (attempt {attempt + 1}/{max_retries}): {e}")
    
    raise last_exception


def _calculate_sha256(file_path):
    """
    Calculate SHA256 hash of a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Lowercase hex string of the SHA256 hash
    """
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest().lower()


def _verify_checksum(file_path, expected_hash):
    """
    Verify SHA256 checksum of a file.
    
    Args:
        file_path: Path to file to verify
        expected_hash: Expected SHA256 hash (hex string)
        
    Returns:
        True if checksum matches, False otherwise
    """
    actual_hash = _calculate_sha256(file_path)
    return actual_hash == expected_hash.lower()


def _download_with_progress(url, dest_path, progress_callback=None):
    """
    Download a file with optional progress callback.
    Uses retry logic for network resilience.
    
    Args:
        url: URL to download from
        dest_path: Destination file path
        progress_callback: Optional function(downloaded_bytes, total_bytes)
        
    Returns:
        True on success
        
    Raises:
        Exception on failure
    """
    response = _request_with_retry(url, timeout=60, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    downloaded = 0
    
    with open(dest_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback and total_size > 0:
                    progress_callback(downloaded, total_size)
    
    # Verify we downloaded the expected amount
    if total_size > 0 and downloaded != total_size:
        raise IOError(f"Incomplete download: got {downloaded} bytes, expected {total_size}")
    
    return True


def _flatten_nested_folder(extract_folder):
    """
    GitHub release zips often contain a single top-level folder like
    'repo-name-v1.2.3/'. This function detects that pattern and flattens
    the structure so files are directly in extract_folder.
    
    Args:
        extract_folder: Path to the extraction directory
        
    Returns:
        True if flattening was performed, False otherwise
    """
    try:
        contents = os.listdir(extract_folder)
        
        # Check if there's exactly one item and it's a directory
        if len(contents) == 1:
            nested_folder = os.path.join(extract_folder, contents[0])
            if os.path.isdir(nested_folder):
                print(f"   Detected nested folder structure: {contents[0]}/")
                print(f"   Flattening to root level...")
                
                # Move all contents from nested folder up one level
                for item in os.listdir(nested_folder):
                    src = os.path.join(nested_folder, item)
                    dst = os.path.join(extract_folder, item)
                    
                    # Handle existing files/folders
                    if os.path.exists(dst):
                        if os.path.isdir(dst):
                            shutil.rmtree(dst, onerror=_remove_readonly)
                        else:
                            os.remove(dst)
                    
                    shutil.move(src, dst)
                
                # Remove the now-empty nested folder
                shutil.rmtree(nested_folder, onerror=_remove_readonly)
                print(f"   Folder structure flattened successfully.")
                return True
    except Exception as e:
        print(f"   Warning: Could not flatten folder structure: {e}")
    
    return False

def check_for_updates():
    """
    Checks GitHub Releases for a version newer than CURRENT_VERSION.
    Returns the release data dict if an update is found, else None.
    Uses retry logic for network resilience.
    """
    print(f"Checking for updates... (Current: {CURRENT_VERSION})")
    try:
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
        
        try:
            response = _request_with_retry(url, max_retries=3, timeout=10)
        except requests.exceptions.HTTPError as e:
            # Handle rate limiting specifically
            if e.response is not None and e.response.status_code == 403:
                remaining = e.response.headers.get('X-RateLimit-Remaining', 'unknown')
                if remaining == '0':
                    print(f"   Update check skipped: GitHub API rate limit exceeded.")
                    return None
            print(f"   Update check failed: {e}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"   Update check failed after retries: {e}")
            return None
            
        data = response.json()
        latest_tag = data.get("tag_name", "")
        
        if not latest_tag:
            print("   Update check failed: No tag_name in release data.")
            return None
        
        # Clean versions for comparison (remove 'v')
        curr_ver_clean = CURRENT_VERSION.lstrip('v')
        latest_ver_clean = latest_tag.lstrip('v')

        try:
            if version.parse(latest_ver_clean) > version.parse(curr_ver_clean):
                print(f"   >>> Update Found: {latest_tag}")
                return data
        except Exception as ve:
            print(f"   Warning: Could not parse version '{latest_tag}': {ve}")
            return None
        
        print("   Up to date.")
        return None
    except Exception as e:
        print(f"   Update check error: {e}")
        return None


def perform_update(release_data):
    """
    Downloads the zip from the release data, extracts it, and runs a batch script
    to overwrite the current files and restart the application.
    
    Includes:
    - Network retry with exponential backoff
    - SHA256 checksum verification (if available)
    - Nested folder structure flattening for GitHub releases
    - User-visible error messages for frozen executables
    """
    tag_name = release_data.get('tag_name', 'Unknown')
    print(f"Initializing update to {tag_name}...")
    
    # 1. Find the correct asset (.zip) and optional checksum
    # Prefer "Release.zip" or similar named packages
    asset_url = None
    asset_name = None
    fallback_url = None
    fallback_name = None
    checksum_url = None
    expected_checksum = None
    
    for asset in release_data.get("assets", []):
        name = asset.get("name", "")
        
        # Look for checksum file (common patterns: sha256.txt, CHECKSUMS.txt, *.sha256)
        if name.lower() in ('sha256.txt', 'checksums.txt', 'sha256sums.txt') or name.endswith('.sha256'):
            checksum_url = asset.get("browser_download_url")
            continue
            
        if name.endswith(".zip"):
            # Prefer Release.zip or monitor-profile-swapper*.zip over generic zips
            if "release" in name.lower() or REPO_NAME.lower() in name.lower():
                asset_url = asset["browser_download_url"]
                asset_name = name
                # Don't break - keep looking for checksum file
            elif fallback_url is None:
                # Store first .zip as fallback
                fallback_url = asset["browser_download_url"]
                fallback_name = name
    
    # Use fallback if no preferred asset found
    if not asset_url and fallback_url:
        asset_url = fallback_url
        asset_name = fallback_name
    
    if not asset_url:
        error_msg = "No .zip asset found in release. Please update manually."
        print(f"   Error: {error_msg}")
        _show_error("Update Failed", error_msg)
        return False
    
    print(f"   Found update package: {asset_name}")
    
    # 1b. Try to fetch checksum if available
    if checksum_url:
        try:
            print("   Fetching checksum file...")
            checksum_response = _request_with_retry(checksum_url, max_retries=2, timeout=10)
            checksum_content = checksum_response.text.strip()
            # Parse checksum file - typically format: "hash  filename" or just "hash"
            for line in checksum_content.split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split()
                if len(parts) >= 1:
                    # Check if this line is for our asset
                    if len(parts) == 1 or (len(parts) >= 2 and asset_name in parts[-1]):
                        expected_checksum = parts[0]
                        print(f"   Found checksum: {expected_checksum[:16]}...")
                        break
        except Exception as e:
            print(f"   Warning: Could not fetch checksum ({e}). Proceeding without verification.")
            expected_checksum = None

    # 2. Download the zip with retry and progress
    zip_path = os.path.join(BASE_DIR, "update_pkg.zip")
    try:
        print(f"   Downloading update package...")
        
        def progress_callback(downloaded, total):
            percent = (downloaded / total) * 100
            # Print progress every 25%
            if percent >= 25 and not hasattr(progress_callback, '_25'):
                print(f"   Download: 25%")
                progress_callback._25 = True
            elif percent >= 50 and not hasattr(progress_callback, '_50'):
                print(f"   Download: 50%")
                progress_callback._50 = True
            elif percent >= 75 and not hasattr(progress_callback, '_75'):
                print(f"   Download: 75%")
                progress_callback._75 = True
        
        _download_with_progress(asset_url, zip_path, progress_callback)
        print(f"   Download: 100%")
        
        # Verify the downloaded file is a valid ZIP
        if not zipfile.is_zipfile(zip_path):
            error_msg = "Downloaded file is corrupted (not a valid ZIP)."
            print(f"   Error: {error_msg}")
            _show_error("Update Failed", error_msg)
            if os.path.exists(zip_path):
                os.remove(zip_path)
            return False
        
        # Verify checksum if available
        if expected_checksum:
            print("   Verifying checksum...")
            if not _verify_checksum(zip_path, expected_checksum):
                actual_hash = _calculate_sha256(zip_path)
                error_msg = f"Checksum verification failed!\nExpected: {expected_checksum[:32]}...\nActual: {actual_hash[:32]}..."
                print(f"   Error: {error_msg}")
                _show_error("Update Failed - Security Check", 
                           "The downloaded file failed integrity verification.\n\n"
                           "This could indicate a corrupted download or tampering.\n"
                           "Please try again or download manually from GitHub.")
                if os.path.exists(zip_path):
                    os.remove(zip_path)
                return False
            print("   Checksum verified successfully.")
            
    except requests.exceptions.RequestException as e:
        error_msg = f"Download failed: {e}"
        print(f"   {error_msg}")
        _show_error("Update Failed", f"Could not download update package.\n\n{e}\n\nPlease check your internet connection and try again.")
        return False
    except IOError as e:
        error_msg = f"Download incomplete: {e}"
        print(f"   {error_msg}")
        _show_error("Update Failed", f"Download was incomplete.\n\n{e}\n\nPlease try again.")
        if os.path.exists(zip_path):
            os.remove(zip_path)
        return False
    except Exception as e:
        error_msg = f"Download failed: {e}"
        print(f"   {error_msg}")
        _show_error("Update Failed", f"An error occurred during download.\n\n{e}")
        return False

    # 3. Extract to temporary folder
    extract_folder = os.path.join(BASE_DIR, "update_tmp")
    try:
        print("   Extracting files...")
        if os.path.exists(extract_folder):
            shutil.rmtree(extract_folder, onerror=_remove_readonly)
        os.makedirs(extract_folder)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            safe_extract(zip_ref, extract_folder)
        
        # Flatten nested folder structure if present (common in GitHub releases)
        _flatten_nested_folder(extract_folder)
        
    except zipfile.BadZipFile:
        error_msg = "Extraction failed: Corrupt or invalid ZIP file."
        print(f"   {error_msg}")
        _show_error("Update Failed", error_msg)
        return False
    except PathTraversalError as e:
        error_msg = f"Security error: {e}"
        print(f"   {error_msg}")
        _show_error("Update Failed - Security", f"The update package contains suspicious paths.\n\n{e}")
        return False
    except Exception as e:
        error_msg = f"Extraction failed: {e}"
        print(f"   {error_msg}")
        _show_error("Update Failed", f"Could not extract update package.\n\n{e}")
        return False


    # 4. Create Batch Script for atomic swap
    exe_name = os.path.basename(sys.executable)
    if not getattr(sys, 'frozen', False):
        print("   [DEV] Running from source: Auto-update simulation complete.")
        # Clean up downloaded archive and temp folder in dev mode
        try:
            if os.path.exists(zip_path):
                os.remove(zip_path)
            if os.path.exists(extract_folder):
                shutil.rmtree(extract_folder, onerror=_remove_readonly)
        except Exception as e:
            print(f"   [DEV] Cleanup warning: {e}")
        return True

    print("   Scheduling restart...")
    
    exe_path = sys.executable
    settings_path = os.path.join(BASE_DIR, "Settings.exe")
    settings_exists = os.path.exists(settings_path)
    log_path = os.path.join(BASE_DIR, "update_log.txt")
    
    # Escape paths for batch script safety
    exe_path_safe = _escape_batch_path(exe_path)
    settings_path_safe = _escape_batch_path(settings_path)
    log_path_safe = _escape_batch_path(log_path)
    base_dir_safe = _escape_batch_path(BASE_DIR)
    extract_folder_safe = _escape_batch_path(extract_folder)
    zip_path_safe = _escape_batch_path(zip_path)
    
    # Get current timestamp for logging
    timestamp = time.ctime()
    
    # We move the batch script to TEMP so it's not in the path of robocopy
    temp_dir = os.environ.get("TEMP", os.environ.get("TMP", BASE_DIR))
    bat_path = os.path.join(temp_dir, "monitor_swapper_updater.bat")

    # Build Settings.exe launch command conditionally
    settings_launch = f'start "" "{settings_path_safe}"' if settings_exists else 'REM Settings.exe not found, skipping'

    # CRITICAL: We clear all MEI related variables. 
    # Using 'start /i' or a fresh 'cmd /c' helps ensure environment isolation.
    batch_script = f"""@echo off
echo [{timestamp}] Starting update... > "{log_path_safe}"
echo Finalizing update...
taskkill /F /IM "{exe_name}" /T > NUL 2>&1
taskkill /F /IM Settings.exe /T > NUL 2>&1
timeout /t 3 /nobreak > NUL

echo Updating files in {base_dir_safe}...
echo [{timestamp}] Running robocopy... >> "{log_path_safe}"
cd /d "{base_dir_safe}"
robocopy "{extract_folder_safe}" "{base_dir_safe}" /E /IS /IT /NP /R:3 /W:5 >> "{log_path_safe}"

set ROBO_EXIT=%%errorlevel%%
echo [{timestamp}] Robocopy exit code: %%ROBO_EXIT%% >> "{log_path_safe}"

if %%ROBO_EXIT%% geq 8 (
    echo Update failed! Check update_log.txt
    echo [{timestamp}] Robocopy failed with exit code %%ROBO_EXIT%% >> "{log_path_safe}"
    pause
    exit /b 1
)

echo Cleaning up...
rmdir /S /Q "{extract_folder_safe}" 2>NUL
del "{zip_path_safe}" 2>NUL

echo Restarting application...
echo [{timestamp}] Restarting MonitorSwapper... >> "{log_path_safe}"
set _MEIPASS=
set _MEI=
start "" "{exe_path_safe}"
{settings_launch}

echo [{timestamp}] Update process finished. >> "{log_path_safe}"
(goto) 2>nul & del "%%~f0"
"""
    
    try:
        with open(bat_path, "w") as f:
            f.write(batch_script)
    except Exception as e:
        print(f"   Error: Failed to create update script: {e}")
        return False

    # 5. Launch Batch and Exit
    try:
        os.startfile(bat_path)
    except Exception as e:
        print(f"   Error: Failed to launch update script: {e}")
        return False
    
    sys.exit(0)
