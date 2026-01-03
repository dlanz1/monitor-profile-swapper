import requests
import os
import sys
import subprocess
import zipfile
import shutil
from packaging import version

# Current version of the application
CURRENT_VERSION = "v1.3.7"

# GitHub Repository details
REPO_OWNER = "dlanz1"
REPO_NAME = "monitor-profile-swapper"

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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
            zip_ref.extractall(extract_folder)
    except Exception as e:
        print(f"   Extraction failed: {e}")
        return False

    # 4. Create Batch Script for atomic swap
    exe_name = os.path.basename(sys.executable)
    if not getattr(sys, 'frozen', False):
        print("   [DEV] Running from source: Auto-update simulation complete.")
        return True

    print("   Scheduling restart...")
    # Use /D to ensure we stay in the right drive, and use absolute paths
    # CRITICAL: We MUST clear _MEIPASS environment variable so the new EXE 
    # creates its own temp folder instead of looking for the old deleted one.
    batch_script = f"""
@echo off
echo Waiting for application to close...
timeout /t 5 /nobreak > NUL
echo Updating files in {BASE_DIR}...
cd /d "{BASE_DIR}"
xcopy /Y /E "{extract_folder}\\*" "{BASE_DIR}"
if %errorlevel% neq 0 (
    echo Update failed! Check if the application is still running.
    pause
    exit
)
echo Cleaning up...
rmdir /S /Q "{extract_folder}"
del "{zip_path}"
echo Restarting application...
set _MEIPASS=
start "" "{exe_name}"
start "" "Settings.exe"
del "%~f0"
"""
    
    bat_path = os.path.join(BASE_DIR, "update_runner.bat")
    with open(bat_path, "w") as f:
        f.write(batch_script)

    # 5. Launch Batch and Exit
    os.startfile(bat_path)
    sys.exit(0)
