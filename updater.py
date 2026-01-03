import requests
import os
import sys
import subprocess
import zipfile
import shutil
import stat
from packaging import version

# Current version of the application
CURRENT_VERSION = "v1.4.2"

# GitHub Repository details
REPO_OWNER = "dlanz1"
REPO_NAME = "monitor-profile-swapper"

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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
        if response.status_code != 200:
            print(f"   Update check failed: HTTP {response.status_code}")
            return None
            
        data = response.json()
        latest_tag = data["tag_name"]
        
        # Clean versions for comparison (remove 'v')
        curr_ver_clean = CURRENT_VERSION.lstrip('v')
        latest_ver_clean = latest_tag.lstrip('v')

        if version.parse(latest_ver_clean) > version.parse(curr_ver_clean):
            print(f"   >>> Update Found: {latest_tag}")
            return data
        
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
    
    # 1. Find the correct asset (.zip)
    asset_url = None
    for asset in release_data.get("assets", []):
        if asset["name"].endswith(".zip"):
            asset_url = asset["browser_download_url"]
            break
    
    if not asset_url:
        print("   Error: No .zip asset found in release.")
        return False

    # 2. Download the zip
    zip_path = os.path.join(BASE_DIR, "update_pkg.zip")
    try:
        print(f"   Downloading update package to {zip_path}...")
        r = requests.get(asset_url, stream=True)
        with open(zip_path, 'wb') as f:
            shutil.copyfileobj(r.raw, f)
    except Exception as e:
        print(f"   Download failed: {e}")
        return False

    # 3. Extract to temporary folder
    extract_folder = os.path.join(BASE_DIR, "update_tmp")
    try:
        print("   Extracting files...")
        if os.path.exists(extract_folder):
            shutil.rmtree(extract_folder)
        os.makedirs(extract_folder)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            safe_extract(zip_ref, extract_folder)
    except Exception as e:
        print(f"   Extraction failed: {e}")
        return False

    # 4. Create Batch Script for atomic swap
    exe_name = os.path.basename(sys.executable)
    if not getattr(sys, 'frozen', False):
        print("   [DEV] Running from source: Auto-update simulation complete.")
        return True

    print("   Scheduling restart...")
    
    exe_path = sys.executable
    settings_path = os.path.join(BASE_DIR, "Settings.exe")
    log_path = os.path.join(BASE_DIR, "update_log.txt")
    
    # We move the batch script to TEMP so it's not in the path of robocopy
    temp_dir = os.environ.get("TEMP", os.environ.get("TMP", BASE_DIR))
    bat_path = os.path.join(temp_dir, "monitor_swapper_updater.bat")

    # CRITICAL: We clear all MEI related variables. 
    # Using 'start /i' or a fresh 'cmd /c' helps ensure environment isolation.
    batch_script = f"""
@echo off
echo [{time.ctime()}] Starting update... > "{log_path}"
echo Finalizing update...
taskkill /F /IM MonitorSwapper.exe /T > NUL 2>&1
taskkill /F /IM Settings.exe /T > NUL 2>&1
timeout /t 3 /nobreak > NUL

echo Updating files in {BASE_DIR}...
echo [{time.ctime()}] Running robocopy... >> "{log_path}"
cd /d "{BASE_DIR}"
robocopy "{extract_folder}" "{BASE_DIR}" /E /IS /IT /NP /R:3 /W:5 >> "{log_path}"

if %errorlevel% geq 8 (
    echo Update failed! Check update_log.txt
    echo [{time.ctime()}] Robocopy failed with exit code %errorlevel% >> "{log_path}"
    pause
    exit
)

echo Cleaning up...
rmdir /S /Q "{extract_folder}"
del "{zip_path}"

echo Restarting application...
echo [{time.ctime()}] Restarting MonitorSwapper... >> "{log_path}"
set _MEIPASS=
set _MEI=
start "" "{exe_path}"
start "" "{settings_path}"

echo [{time.ctime()}] Update process finished. >> "{log_path}"
del "%~f0"
"""
    
    with open(bat_path, "w") as f:
        f.write(batch_script)

    # 5. Launch Batch and Exit
    os.startfile(bat_path)
    sys.exit(0)
