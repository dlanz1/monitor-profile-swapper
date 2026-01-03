import time
import psutil
from monitorcontrol import get_monitors

# Settings
FPS_BRI = 79
FPS_CON = 80
DEF_BRI = 75
DEF_CON = 75

# List of process names to watch for
GAME_PROCESSES = [
    "EscapeFromTarkov.exe", 
    "EscapeFromTarkov_BE.exe", 
    "TarkovArena.exe"
]

def set_monitor(brightness, contrast):
    print(f"   >>> ACTION: Setting Monitor to B:{brightness} / C:{contrast}")
    try:
        monitors = get_monitors()
        if not monitors:
            print("   ERROR: No monitors found!")
            return False
        with monitors[0] as m:
            m.vcp.set_vcp_feature(0x10, brightness)
            m.vcp.set_vcp_feature(0x12, contrast)
        print("   >>> SUCCESS: Settings applied.")
        return True
    except Exception as e:
        print(f"   ERROR: Failed to set monitor: {e}")
        return False

def check_process():
    for proc in psutil.process_iter(['name']):
        try:
            name = proc.info['name']
            if name in GAME_PROCESSES:
                print(f"   >>> FOUND GAME PROCESS: {name}")
                return True
        except:
            pass
    return False

def main():
    print(f"--- DEBUG MODE: ARENA SUPPORT ---")
    print(f"Monitoring for: {GAME_PROCESSES}")
    
    in_game_mode = False
    
    while True:
        is_running = check_process()
        
        status = "GAME RUNNING" if is_running else "Game Closed"
        mode = "FPS Mode" if in_game_mode else "Standard Mode"
        print(f"Status: {status} | Current State: {mode}")

        if is_running and not in_game_mode:
            print("DETECTED LAUNCH! Switching to FPS settings...")
            if set_monitor(FPS_BRI, FPS_CON):
                in_game_mode = True
        
        elif not is_running and in_game_mode:
            print("DETECTED CLOSE. Restoring Standard settings...")
            if set_monitor(DEF_BRI, DEF_CON):
                in_game_mode = False

        time.sleep(2)

if __name__ == "__main__":
    main()