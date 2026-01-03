import time
import psutil
from monitorcontrol import get_monitors

# Settings
FPS_BRI = 79
FPS_CON = 80
DEF_BRI = 75
DEF_CON = 75

# Comprehensive list of process names to watch for
GAME_PROCESSES = [
    "EscapeFromTarkov.exe", 
    "EscapeFromTarkov_BE.exe", 
    "TarkovArena.exe",
    "EscapeFromTarkovArena.exe"
]

def set_monitor(brightness, contrast):
    try:
        monitors = get_monitors()
        if not monitors:
            return False
        with monitors[0] as m:
            m.vcp.set_vcp_feature(0x10, brightness)
            m.vcp.set_vcp_feature(0x12, contrast)
        return True
    except:
        return False

def check_process():
    for proc in psutil.process_iter(['name']):
        try:
            # Case-insensitive match against our list
            if proc.info['name'] in GAME_PROCESSES:
                return True
        except:
            pass
    return False

def main():
    in_game_mode = False
    saved_brightness = 75
    saved_contrast = 75

    while True:
        is_running = check_process()
        
        if is_running and not in_game_mode:
            # Save current settings before applying FPS mode
            # (In case you changed them manually since the last run)
            try:
                with get_monitors()[0] as m:
                    saved_brightness = m.vcp.get_vcp_feature(0x10)[0]
                    saved_contrast = m.vcp.get_vcp_feature(0x12)[0]
            except:
                pass # Keep defaults if read fails
                
            if set_monitor(FPS_BRI, FPS_CON):
                in_game_mode = True
        
        elif not is_running and in_game_mode:
            # Restore the settings we saved earlier
            if set_monitor(saved_brightness, saved_contrast):
                in_game_mode = False

        time.sleep(5)

if __name__ == "__main__":
    main()
