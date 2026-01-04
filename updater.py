import requests
import os
import sys
import subprocess
import zipfile
import shutil
import time
import stat
import re
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
        if os.path.commonpath([target_dir, member_path]) != target_dir:
            raise PathTraversalError(f"Attempted path traversal in zip file: {member.filename}")

        # Reject symbolic links to prevent symlink-based attacks
        # Note: This check relies on Unix file permissions in external_attr (bits 16-31).
        # It works for zip files created on Unix/Linux systems but may not detect
        # symlinks in zip files created on Windows or by non-standard tools.
        if (member.external_attr >> 16) & 0o170000 == stat.S_IFLNK:
            raise PathTraversalError(f"Zip file contains symbolic link: {member.filename}")

        # Extract each validated member individually to maintain full control
        zip_ref.extract(member, target_dir)

def check_for_updates():
    """
    Checks GitHub Releases for a version newer than CURRENT_VERSION.
    Returns the release data dict if an update is found, else None.
    """
    print(f"Checking for updates... (Current: {CURRENT_VERSION})")
    try:
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
        response = requests.get(url, timeout=5)
        
        # Handle rate limiting
        if response.status_code == 403:
            remaining = response.headers.get('X-RateLimit-Remaining', 'unknown')
            if remaining == '0':
                reset_time = response.headers.get('X-RateLimit-Reset', '')
                print(f"   Update check skipped: GitHub API rate limit exceeded.")
                return None
        
        if response.status_code != 200:
            print(f"   Update check failed: HTTP {response.status_code}")
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
    """
    print(f"Initializing update to {release_data['tag_name']}...")
    
    # 1. Find the correct asset (.zip) - prefer "Release.zip" or similar named packages
    asset_url = None
    asset_name = None
    fallback_url = None
    fallback_name = None
    
    for asset in release_data.get("assets", []):
        name = asset.get("name", "")
        if name.endswith(".zip"):
            # Prefer Release.zip or monitor-profile-swapper*.zip over generic zips
            if "release" in name.lower() or REPO_NAME.lower() in name.lower():
                asset_url = asset["browser_download_url"]
                asset_name = name
                break
            elif fallback_url is None:
                # Store first .zip as fallback
                fallback_url = asset["browser_download_url"]
                fallback_name = name
    
    # Use fallback if no preferred asset found
    if not asset_url and fallback_url:
        asset_url = fallback_url
        asset_name = fallback_name
    
    if not asset_url:
        print("   Error: No .zip asset found in release.")
        return False
    
    print(f"   Found update package: {asset_name}")

    # 2. Download the zip
    zip_path = os.path.join(BASE_DIR, "update_pkg.zip")
    try:
        print(f"   Downloading update package to {zip_path}...")
        r = requests.get(asset_url, stream=True, timeout=60)
        r.raise_for_status()  # Raise exception for HTTP errors
        
        with open(zip_path, 'wb') as f:
            shutil.copyfileobj(r.raw, f)
        
        # Verify the downloaded file is a valid ZIP
        if not zipfile.is_zipfile(zip_path):
            print("   Error: Downloaded file is not a valid ZIP archive.")
            if os.path.exists(zip_path):
                os.remove(zip_path)
            return False
            
    except requests.exceptions.HTTPError as e:
        print(f"   Download failed: HTTP {e.response.status_code}")
        return False
    except requests.exceptions.Timeout:
        print("   Download failed: Connection timed out.")
        return False
    except Exception as e:
        print(f"   Download failed: {e}")
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
    except zipfile.BadZipFile:
        print("   Extraction failed: Corrupt or invalid ZIP file.")
        return False
    except PathTraversalError as e:
        print(f"   Security error: {e}")
        return False
    except Exception as e:
        print(f"   Extraction failed: {e}")
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
