import time
import psutil
import json
import os
import sys
import threading
import subprocess
from monitorcontrol import get_monitors
import updater
import hdr_control
import pystray
from PIL import Image, ImageDraw

if getattr(sys, 'frozen', False):
    # Running as compiled exe
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Running as script
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

DEFAULT_CONFIG = {
    "game_processes": ["EscapeFromTarkov.exe", "EscapeFromTarkov_BE.exe", "TarkovArena.exe"],
    "game_mode": {"brightness": 80, "contrast": 80, "hdr_enabled": False},
    "desktop_mode": {"brightness": 50, "contrast": 50},
    "tray_enabled": True
}

# Global flag to stop threads
stop_event = threading.Event()

def load_config():
    if not os.path.exists(CONFIG_FILE):
        print("Config file not found, using defaults.")
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}. Using defaults.")
        return DEFAULT_CONFIG

def set_monitor(brightness, contrast):
    print(f"   >>> ACTION: Setting Monitor to B:{brightness} / C:{contrast}")
    try:
        monitors = get_monitors()
        if not monitors:
            print("   ERROR: No monitors found!")
            return False
        for m in monitors:
            with m:
                m.vcp.set_vcp_feature(0x10, brightness)
                m.vcp.set_vcp_feature(0x12, contrast)
        print("   >>> SUCCESS: Settings applied.")
        return True
    except Exception as e:
        print(f"   ERROR: Failed to set monitor: {e}")
        return False

def check_process(process_list):
    # Check if any of the processes in the list are running
    for proc in psutil.process_iter(['name']):
        try:
            name = proc.info['name']
            if name in process_list:
                return True
        except:
            pass
    return False

def monitoring_loop():
    print("--- MONITOR PROFILE SWAPPER ---")
    
    config = load_config()
    game_processes = config.get("game_processes", [])
    game_mode = config.get("game_mode", {})
    desktop_mode = config.get("desktop_mode", {})
    
    hdr_in_game = game_mode.get("hdr_enabled", False)
    
    print(f"Monitoring for: {game_processes}")
    
    in_game_mode = False
    
    # Apply Desktop Mode on startup
    print("Applying Desktop settings on startup...")
    set_monitor(desktop_mode.get("brightness", 50), desktop_mode.get("contrast", 50))
    if hdr_in_game:
        hdr_control.set_hdr_mode(False)

    while not stop_event.is_set():
        # Reload config periodically? For now, we assume restart on config change
        # But we can reload basic flags if needed.
        
        is_running = check_process(game_processes)
        
        if is_running and not in_game_mode:
            print("DETECTED LAUNCH! Switching to Game settings...")
            set_monitor(game_mode.get("brightness", 80), game_mode.get("contrast", 80))
            if hdr_in_game:
                hdr_control.set_hdr_mode(True)
            in_game_mode = True
        
        elif not is_running and in_game_mode:
            print("DETECTED CLOSE. Restoring Desktop settings...")
            set_monitor(desktop_mode.get("brightness", 50), desktop_mode.get("contrast", 50))
            if hdr_in_game:
                hdr_control.set_hdr_mode(False)
            in_game_mode = False
        
        time.sleep(2)

def create_icon():
    # Create a simple icon
    width = 64
    height = 64
    image = Image.new('RGB', (width, height), (0, 0, 0))
    dc = ImageDraw.Draw(image)
    # Draw a blue 'M'
    dc.rectangle((0, 0, width, height), fill=(30, 30, 30))
    dc.rectangle((16, 16, 48, 48), fill=(0, 120, 215))
    return image

def open_settings(icon, item):
    # Launch Settings.exe
    if getattr(sys, 'frozen', False):
        # Running as exe
        base_path = os.path.dirname(sys.executable)
        settings_path = os.path.join(base_path, "Settings.exe")
    else:
        # Running as script
        settings_path = "swapper_config.py"
    
    print(f"Launching settings: {settings_path}")
    if settings_path.endswith(".py"):
        subprocess.Popen(["python", settings_path])
    else:
        subprocess.Popen([settings_path])

def quit_app(icon, item):
    icon.stop()
    stop_event.set()
    sys.exit(0)

def manual_update_check(icon, item):
    # Use standard Windows MessageBox for feedback
    MB_OK = 0x0
    MB_YESNO = 0x4
    MB_ICONINFO = 0x40
    MB_ICONQUESTION = 0x20
    IDYES = 6

    update_data = updater.check_for_updates()
    if update_data:
        new_ver = update_data.get("tag_name", "Unknown")
        msg = f"A new update ({new_ver}) is available. Would you like to install it now?\n\nThe application will restart automatically."
        res = ctypes.windll.user32.MessageBoxW(0, msg, "Update Available", MB_YESNO | MB_ICONQUESTION)
        
        if res == IDYES:
            updater.perform_update(update_data)
    else:
        ctypes.windll.user32.MessageBoxW(0, "You are already running the latest version.", "No Updates Found", MB_OK | MB_ICONINFO)

def main():
    # --- Auto-Update Check ---
    update_data = updater.check_for_updates()
    if update_data:
        updater.perform_update(update_data)
    # -------------------------

    config = load_config()
    
    # Start monitoring in a separate thread
    monitor_thread = threading.Thread(target=monitoring_loop)
    monitor_thread.daemon = True
    monitor_thread.start()

    if config.get("tray_enabled", True):
        print("Starting System Tray Icon...")
        menu = pystray.Menu(
            pystray.MenuItem("Monitor Swapper", None, enabled=False),
            pystray.MenuItem("Settings", open_settings, default=True),
            pystray.MenuItem("Check for updates", manual_update_check),
            pystray.Menu.Separator(),
            pystray.MenuItem("Exit", quit_app)
        )
        icon = pystray.Icon("MonitorSwapper", create_icon(), "Monitor Swapper", menu, action=open_settings)
        icon.run()
    else:
        print("Tray icon disabled. Running in console mode.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            stop_event.set()

if __name__ == "__main__":
    main()

