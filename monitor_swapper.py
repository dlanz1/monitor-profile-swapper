import time
import psutil
import json
import os
import sys
from monitorcontrol import get_monitors

CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {
    "game_processes": ["EscapeFromTarkov.exe", "EscapeFromTarkov_BE.exe", "TarkovArena.exe"],
    "game_mode": {"brightness": 80, "contrast": 80},
    "desktop_mode": {"brightness": 50, "contrast": 50}
}

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
                # print(f"   >>> FOUND GAME PROCESS: {name}") # too verbose for loop
                return True
        except:
            pass
    return False

def main():
    print("--- MONITOR PROFILE SWAPPER ---")
    config = load_config()
    game_processes = config.get("game_processes", [])
    game_mode = config.get("game_mode", {})
    desktop_mode = config.get("desktop_mode", {})
    
    print(f"Monitoring for: {game_processes}")
    print(f"Game Mode: {game_mode}")
    print(f"Desktop Mode: {desktop_mode}")
    
    in_game_mode = False
    
    # Apply Desktop Mode on startup ensuring consistent state
    print("Applying Desktop settings on startup...")
    set_monitor(desktop_mode.get("brightness", 50), desktop_mode.get("contrast", 50))

    while True:
        is_running = check_process(game_processes)
        
        # Determine target state
        if is_running and not in_game_mode:
            print("DETECTED LAUNCH! Switching to Game settings...")
            if set_monitor(game_mode.get("brightness", 80), game_mode.get("contrast", 80)):
                in_game_mode = True
        
        elif not is_running and in_game_mode:
            print("DETECTED CLOSE. Restoring Desktop settings...")
            if set_monitor(desktop_mode.get("brightness", 50), desktop_mode.get("contrast", 50)):
                in_game_mode = False
        
        # Optional: Periodic config reload check could go here
        
        time.sleep(2)

if __name__ == "__main__":
    main()
