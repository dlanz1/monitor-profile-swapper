import time
import psutil
import json
import os
import sys
import threading
import subprocess
import ctypes
import ctypes.wintypes
import winreg
import webbrowser
import logging
from logging.handlers import RotatingFileHandler
from monitorcontrol import get_monitors
import updater
import hdr_control
import pystray
from PIL import Image, ImageDraw

# Windows API constants for single-instance mutex
ERROR_ALREADY_EXISTS = 183

if getattr(sys, 'frozen', False):
    # Running as compiled exe
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Running as script
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
LOG_FILE = os.path.join(BASE_DIR, "monitor_swapper.log")

# Global flag to stop threads
stop_event = threading.Event()

# Thread safety locks (from v1.4.8)
update_lock = threading.Lock()
config_lock = threading.Lock()

# ===== LOGGING SETUP =====
def setup_logging():
    """Initialize file-based logging with rotation."""
    logger = logging.getLogger('MonitorSwapper')
    logger.setLevel(logging.DEBUG)
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # File handler with rotation (max 1MB, keep 3 backups)
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=1024*1024, backupCount=3, encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Console handler for development
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('[%(levelname)s] %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

# ===== SINGLE INSTANCE MUTEX =====
class SingleInstanceMutex:
    """
    Windows Mutex-based single instance enforcement.
    Prevents multiple copies of the application from running simultaneously.
    """
    def __init__(self, mutex_name="MonitorProfileSwapper_SingleInstance_Mutex"):
        self.mutex_name = mutex_name
        self.mutex_handle = None
        
    def acquire(self):
        """Attempt to acquire the mutex. Returns True if successful (first instance)."""
        kernel32 = ctypes.windll.kernel32
        self.mutex_handle = kernel32.CreateMutexW(None, True, self.mutex_name)
        last_error = kernel32.GetLastError()
        
        if last_error == ERROR_ALREADY_EXISTS:
            logger.warning("Another instance is already running!")
            return False
        
        if self.mutex_handle is None:
            logger.error(f"Failed to create mutex: error code {last_error}")
            return False
            
        logger.info("Single instance mutex acquired successfully.")
        return True
        
    def release(self):
        """Release the mutex when shutting down."""
        if self.mutex_handle:
            ctypes.windll.kernel32.ReleaseMutex(self.mutex_handle)
            ctypes.windll.kernel32.CloseHandle(self.mutex_handle)
            self.mutex_handle = None

# Global mutex instance
instance_mutex = SingleInstanceMutex()

# ===== CONFIG VALIDATION =====
class ConfigValidationError(Exception):
    """Raised when config validation fails."""
    pass

def validate_config(config):
    """
    Validate configuration values and sanitize/repair invalid entries.
    Returns a tuple of (validated_config, list_of_warnings).
    """
    warnings = []
    validated = {}
    
    # Validate game_processes
    game_processes = config.get("game_processes", [])
    if not isinstance(game_processes, list):
        warnings.append(f"game_processes should be a list, got {type(game_processes).__name__}. Using defaults.")
        game_processes = DEFAULT_CONFIG["game_processes"]
    else:
        # Filter and sanitize process names
        valid_processes = []
        for proc in game_processes:
            if isinstance(proc, str) and proc.strip():
                # Sanitize: remove path separators, keep only filename
                sanitized = os.path.basename(proc.strip())
                if sanitized:
                    valid_processes.append(sanitized)
                else:
                    warnings.append(f"Invalid process name skipped: '{proc}'")
            else:
                warnings.append(f"Invalid process entry skipped: {proc}")
        game_processes = valid_processes if valid_processes else DEFAULT_CONFIG["game_processes"]
    validated["game_processes"] = game_processes
    
    # Validate game_mode
    game_mode = config.get("game_mode", {})
    if not isinstance(game_mode, dict):
        warnings.append(f"game_mode should be an object, got {type(game_mode).__name__}. Using defaults.")
        game_mode = DEFAULT_CONFIG["game_mode"].copy()
    else:
        game_mode = game_mode.copy()
        
    validated["game_mode"] = validate_mode_settings(game_mode, "game_mode", warnings, include_hdr=True)
    
    # Validate desktop_mode
    desktop_mode = config.get("desktop_mode", {})
    if not isinstance(desktop_mode, dict):
        warnings.append(f"desktop_mode should be an object, got {type(desktop_mode).__name__}. Using defaults.")
        desktop_mode = DEFAULT_CONFIG["desktop_mode"].copy()
    else:
        desktop_mode = desktop_mode.copy()
        
    validated["desktop_mode"] = validate_mode_settings(desktop_mode, "desktop_mode", warnings, include_hdr=False)
    
    # Preserve other config keys (tray_enabled, startup_prompted, etc.)
    validated["tray_enabled"] = bool(config.get("tray_enabled", True))
    if "startup_prompted" in config:
        validated["startup_prompted"] = bool(config["startup_prompted"])
    
    return validated, warnings

def validate_mode_settings(mode, mode_name, warnings, include_hdr=False):
    """Validate brightness/contrast values for a mode (0-100 range)."""
    import math
    validated = {}
    
    # Validate brightness (0-100)
    brightness = mode.get("brightness", 50)
    try:
        # Handle infinity and NaN before conversion
        if isinstance(brightness, float) and (math.isinf(brightness) or math.isnan(brightness)):
            raise ValueError("infinity or NaN")
        brightness = int(brightness)
        if brightness < 0:
            warnings.append(f"{mode_name}.brightness was {brightness}, clamped to 0.")
            brightness = 0
        elif brightness > 100:
            warnings.append(f"{mode_name}.brightness was {brightness}, clamped to 100.")
            brightness = 100
    except (ValueError, TypeError, OverflowError):
        warnings.append(f"{mode_name}.brightness was invalid ({mode.get('brightness')}), using default 50.")
        brightness = 50
    validated["brightness"] = brightness
    
    # Validate contrast (0-100)
    contrast = mode.get("contrast", 50)
    try:
        # Handle infinity and NaN before conversion
        if isinstance(contrast, float) and (math.isinf(contrast) or math.isnan(contrast)):
            raise ValueError("infinity or NaN")
        contrast = int(contrast)
        if contrast < 0:
            warnings.append(f"{mode_name}.contrast was {contrast}, clamped to 0.")
            contrast = 0
        elif contrast > 100:
            warnings.append(f"{mode_name}.contrast was {contrast}, clamped to 100.")
            contrast = 100
    except (ValueError, TypeError, OverflowError):
        warnings.append(f"{mode_name}.contrast was invalid ({mode.get('contrast')}), using default 50.")
        contrast = 50
    validated["contrast"] = contrast
    
    # Validate HDR setting if applicable
    if include_hdr:
        validated["hdr_enabled"] = bool(mode.get("hdr_enabled", False))
    
    return validated

DEFAULT_CONFIG = {
    "game_processes": ["EscapeFromTarkov.exe", "EscapeFromTarkov_BE.exe", "TarkovArena.exe"],
    "game_mode": {"brightness": 80, "contrast": 80, "hdr_enabled": False},
    "desktop_mode": {"brightness": 50, "contrast": 50},
    "tray_enabled": True
}

def check_vcredist_installed():
    """
    Check if Visual C++ Redistributable 2015-2022 (x64) is installed.
    Returns True if found, False otherwise.
    """
    registry_paths = [
        # VC++ 2015-2022 x64 (various versions)
        r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64",
        r"SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64",
    ]
    
    for path in registry_paths:
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
            installed, _ = winreg.QueryValueEx(key, "Installed")
            winreg.CloseKey(key)
            if installed == 1:
                return True
        except (FileNotFoundError, OSError):
            continue
    
    # Alternative check: look for the DLL directly
    try:
        ctypes.WinDLL("vcruntime140.dll")
        return True
    except OSError:
        pass
    
    return False

def prompt_vcredist_install():
    """
    Show a message box prompting the user to install VC++ Redistributable.
    Returns True if user wants to continue anyway, False to exit.
    """
    MB_YESNO = 0x04
    MB_ICONWARNING = 0x30
    IDYES = 6
    
    message = (
        "Microsoft Visual C++ Redistributable is not detected on your system.\n\n"
        "This is required for Monitor Profile Swapper to work correctly.\n\n"
        "Would you like to open the download page?\n\n"
        "(Click 'Yes' to open the download page, 'No' to try running anyway)"
    )
    
    result = ctypes.windll.user32.MessageBoxW(
        0, message, "Missing Dependency", MB_YESNO | MB_ICONWARNING
    )
    
    if result == IDYES:
        # Open the official Microsoft download page
        webbrowser.open("https://aka.ms/vs/17/release/vc_redist.x64.exe")
        
        # Show follow-up message
        MB_OK = 0x00
        MB_ICONINFORMATION = 0x40
        ctypes.windll.user32.MessageBoxW(
            0,
            "After installing the Visual C++ Redistributable, please restart Monitor Profile Swapper.",
            "Installation Required",
            MB_OK | MB_ICONINFORMATION
        )
        return False  # Exit the app
    
    return True  # User chose to continue anyway

def get_startup_folder():
    """Get the Windows Startup folder path."""
    import winreg
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
    )
    startup_path, _ = winreg.QueryValueEx(key, "Startup")
    winreg.CloseKey(key)
    return startup_path

def get_startup_shortcut_path():
    """Get the path where our startup shortcut would be."""
    return os.path.join(get_startup_folder(), "MonitorSwapper.lnk")

def is_in_startup():
    """Check if the program is already in startup."""
    return os.path.exists(get_startup_shortcut_path())

def add_to_startup():
    """Add the program to Windows startup by creating a shortcut."""
    try:
        import win32com.client
        
        startup_path = get_startup_shortcut_path()
        
        if getattr(sys, 'frozen', False):
            target = sys.executable
        else:
            # When running as script, don't add to startup
            return False
        
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(startup_path)
        shortcut.Targetpath = target
        shortcut.WorkingDirectory = os.path.dirname(target)
        shortcut.IconLocation = target
        shortcut.Description = "Monitor Profile Swapper - Auto-switch monitor settings"
        shortcut.save()
        
        return True
    except Exception as e:
        logger.error(f"Failed to add to startup: {e}")
        return False

def remove_from_startup():
    """Remove the program from Windows startup."""
    try:
        shortcut_path = get_startup_shortcut_path()
        if os.path.exists(shortcut_path):
            os.remove(shortcut_path)
            return True
    except Exception as e:
        logger.error(f"Failed to remove from startup: {e}")
    return False

def prompt_startup_option():
    """
    Prompt the user to add the program to startup if not already added.
    Only prompts once - stores preference in config.
    """
    # Only prompt when running as exe
    if not getattr(sys, 'frozen', False):
        return
    
    # Check if already in startup
    if is_in_startup():
        return
    
    # Check if user has already been prompted (stored in config)
    config = load_config()
    if config.get("startup_prompted", False):
        return
    
    MB_YESNO = 0x04
    MB_ICONQUESTION = 0x20
    IDYES = 6
    
    message = (
        "For the best experience, Monitor Profile Swapper should run automatically when Windows starts.\n\n"
        "Would you like to add it to your startup programs?\n\n"
        "(You can change this later in Windows Settings > Apps > Startup)"
    )
    
    result = ctypes.windll.user32.MessageBoxW(
        0, message, "Run on Startup?", MB_YESNO | MB_ICONQUESTION
    )
    
    if result == IDYES:
        if add_to_startup():
            MB_OK = 0x00
            MB_ICONINFORMATION = 0x40
            ctypes.windll.user32.MessageBoxW(
                0,
                "Monitor Profile Swapper will now start automatically with Windows.",
                "Added to Startup",
                MB_OK | MB_ICONINFORMATION
            )
    
    # Mark as prompted so we don't ask again
    config["startup_prompted"] = True
    try:
        with config_lock:
            tmp_file = CONFIG_FILE + ".tmp"
            with open(tmp_file, 'w') as f:
                json.dump(config, f, indent=4)
            os.replace(tmp_file, CONFIG_FILE)
    except Exception:
        pass

def load_config():
    """Load and validate configuration from file."""
    if not os.path.exists(CONFIG_FILE):
        logger.info("Config file not found, using defaults.")
        return DEFAULT_CONFIG.copy()
    
    try:
        with config_lock:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                raw_config = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Malformed JSON in config file: {e}")
        logger.info("Using default configuration due to JSON parse error.")
        return DEFAULT_CONFIG.copy()
    except Exception as e:
        logger.error(f"Error reading config file: {e}")
        return DEFAULT_CONFIG.copy()
    
    # Validate and sanitize the loaded config
    validated_config, warnings = validate_config(raw_config)
    
    # Log any validation warnings
    for warning in warnings:
        logger.warning(f"Config validation: {warning}")
    
    # If there were warnings, auto-save the corrected config
    if warnings:
        logger.info("Auto-saving corrected configuration...")
        try:
            with config_lock:
                tmp_file = CONFIG_FILE + ".tmp"
                with open(tmp_file, 'w', encoding='utf-8') as f:
                    json.dump(validated_config, f, indent=4)
                os.replace(tmp_file, CONFIG_FILE)
            logger.info("Corrected configuration saved successfully.")
        except Exception as e:
            logger.error(f"Failed to auto-save corrected config: {e}")
    
    return validated_config

def set_monitor(brightness, contrast):
    """Apply brightness and contrast settings to all connected monitors."""
    logger.info(f"Setting monitor to Brightness:{brightness}, Contrast:{contrast}")
    try:
        monitors = get_monitors()
        if not monitors:
            logger.error("No DDC/CI compatible monitors found!")
            return False
        
        applied_count = 0
        for i, m in enumerate(monitors):
            try:
                with m:
                    m.vcp.set_vcp_feature(0x10, brightness)
                    m.vcp.set_vcp_feature(0x12, contrast)
                    applied_count += 1
                    logger.debug(f"Monitor {i+1}: Settings applied successfully.")
            except Exception as monitor_err:
                logger.error(f"Monitor {i+1}: Failed to apply settings - {monitor_err}")
        
        if applied_count > 0:
            logger.info(f"Settings applied to {applied_count}/{len(monitors)} monitor(s).")
            return True
        else:
            logger.error("Failed to apply settings to any monitor.")
            return False
            
    except Exception as e:
        logger.exception(f"Critical error in set_monitor: {e}")
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
    """Main monitoring loop that watches for game processes and switches profiles."""
    logger.info("=" * 50)
    logger.info("MONITOR PROFILE SWAPPER - Monitoring Started")
    logger.info("=" * 50)
    
    config = load_config()
    game_processes = config.get("game_processes", [])
    game_mode = config.get("game_mode", {})
    desktop_mode = config.get("desktop_mode", {})
    
    hdr_in_game = game_mode.get("hdr_enabled", False)
    
    logger.info(f"Watching for processes: {game_processes}")
    logger.info(f"Game Mode: B={game_mode.get('brightness')}, C={game_mode.get('contrast')}, HDR={hdr_in_game}")
    logger.info(f"Desktop Mode: B={desktop_mode.get('brightness')}, C={desktop_mode.get('contrast')}")
    
    in_game_mode = False
    
    # Apply Desktop Mode on startup
    logger.info("Applying Desktop settings on startup...")
    set_monitor(desktop_mode.get("brightness", 50), desktop_mode.get("contrast", 50))
    if hdr_in_game:
        hdr_control.set_hdr_mode(False)

    # Track previous HDR config to detect runtime changes
    prev_hdr_in_game = hdr_in_game

    while not stop_event.is_set():
        # Reload config periodically (every 2 seconds along with process check)
        try:
            # Re-read config to pick up changes dynamically
            new_config = load_config()
            game_processes = new_config.get("game_processes", [])
            game_mode = new_config.get("game_mode", {})
            desktop_mode = new_config.get("desktop_mode", {})
            hdr_in_game = game_mode.get("hdr_enabled", False)
        except Exception:
            pass # Keep old config on error

        is_running = check_process(game_processes)
        
        if is_running and not in_game_mode:
            logger.info("Game process detected! Switching to Game settings...")
            if set_monitor(game_mode.get("brightness", 80), game_mode.get("contrast", 80)):
                if hdr_in_game:
                    hdr_control.set_hdr_mode(True)
                in_game_mode = True
        
        elif not is_running and in_game_mode:
            logger.info("Game process closed. Restoring Desktop settings...")
            if set_monitor(desktop_mode.get("brightness", 50), desktop_mode.get("contrast", 50)):
                # If we were in game mode, and HDR was enabled there, we disable it now.
                # Even if user just disabled it in config, we want to ensure it's OFF for desktop.
                if prev_hdr_in_game or hdr_in_game:
                    hdr_control.set_hdr_mode(False)
                in_game_mode = False

        # Handle HDR config change while in game mode
        if in_game_mode and hdr_in_game != prev_hdr_in_game:
            logger.info(f"HDR config changed (Enabled={hdr_in_game}). Applying...")
            hdr_control.set_hdr_mode(hdr_in_game)

        prev_hdr_in_game = hdr_in_game
        
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
    
    logger.info(f"Launching settings: {settings_path}")
    
    # CRITICAL: Clear _MEIPASS so Settings.exe doesn't inherit the parent's temp folder
    clean_env = os.environ.copy()
    clean_env.pop("_MEIPASS", None)

    if settings_path.endswith(".py"):
        subprocess.Popen(["python", settings_path], env=clean_env)
    else:
        subprocess.Popen([settings_path], env=clean_env)

def quit_app(icon, item):
    icon.stop()
    stop_event.set()
    # Use os._exit to kill all threads immediately and avoid pystray callback noise
    os._exit(0)

def manual_update_check(icon, item):
    def run_check():
        # Prevent concurrent update checks
        if not update_lock.acquire(blocking=False):
            return
        
        # Use standard Windows MessageBox for feedback
        MB_OK = 0x0
        MB_YESNO = 0x4
        MB_ICONINFO = 0x40
        MB_ICONQUESTION = 0x20
        MB_TOPMOST = 0x40000
        MB_SETFOREGROUND = 0x10000
        IDYES = 6

        try:
            update_data = updater.check_for_updates()
            if update_data:
                new_ver = update_data.get("tag_name", "Unknown")
                msg = f"A new update ({new_ver}) is available. Would you like to install it now?\\n\\nThe application will restart automatically."
                res = ctypes.windll.user32.MessageBoxW(0, msg, "Update Available", 
                                                       MB_YESNO | MB_ICONQUESTION | MB_TOPMOST | MB_SETFOREGROUND)
                
                if res == IDYES:
                    updater.perform_update(update_data)
            else:
                ctypes.windll.user32.MessageBoxW(0, "You are already running the latest version.", "No Updates Found", 
                                                 MB_OK | MB_ICONINFO | MB_TOPMOST | MB_SETFOREGROUND)
        except Exception as e:
            ctypes.windll.user32.MessageBoxW(0, f"Update check failed: {e}", "Error", 
                                             MB_OK | 0x10 | MB_TOPMOST | MB_SETFOREGROUND)
        finally:
            update_lock.release()

    # Run check in a background thread so the tray menu doesn't hang
    threading.Thread(target=run_check, daemon=True).start()

def main():
    logger.info("Monitor Profile Swapper starting...")
    logger.info(f"Version: {updater.CURRENT_VERSION}")
    logger.info(f"Base directory: {BASE_DIR}")
    
    # --- Single Instance Check ---
    if not instance_mutex.acquire():
        MB_OK = 0x00
        MB_ICONWARNING = 0x30
        ctypes.windll.user32.MessageBoxW(
            0,
            "Monitor Profile Swapper is already running!\n\n"
            "Check your system tray for the existing instance.",
            "Already Running",
            MB_OK | MB_ICONWARNING
        )
        logger.error("Exiting - another instance is already running.")
        sys.exit(1)
    # -----------------------------
    
    # --- VC++ Redistributable Check ---
    if not check_vcredist_installed():
        logger.warning("VC++ Redistributable not detected!")
        if not prompt_vcredist_install():
            logger.info("Exiting - user chose to install VC++ Redistributable first.")
            instance_mutex.release()
            sys.exit(0)
        logger.info("User chose to continue without VC++ Redistributable.")
    # ----------------------------------

    # --- Startup Prompt (first run only) ---
    prompt_startup_option()
    # ---------------------------------------

    # --- Clean up any leftover update artifacts ---
    updater.cleanup_update_artifacts()
    # ----------------------------------------------

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
        logger.info("Starting System Tray Icon...")
        menu = pystray.Menu(
            pystray.MenuItem("Monitor Swapper", None, enabled=False),
            pystray.MenuItem("Settings", open_settings, default=True),
            pystray.MenuItem(f"Check for updates ({updater.CURRENT_VERSION})", manual_update_check),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", quit_app)
        )
        icon = pystray.Icon("MonitorSwapper", create_icon(), "Monitor Swapper", menu, action=open_settings)
        icon.run()
    else:
        logger.info("Tray icon disabled. Running in console mode.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            stop_event.set()

if __name__ == "__main__":
    main()

