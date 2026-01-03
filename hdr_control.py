import ctypes
from ctypes import wintypes, Structure
import pyautogui
import time

# --- Windows API Definitions for HDR Reading ---

class LUID(Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]

DISPLAYCONFIG_DEVICE_INFO_GET_TARGET_NAME = 2
DISPLAYCONFIG_DEVICE_INFO_GET_ADVANCED_COLOR_INFO = 8

class DISPLAYCONFIG_DEVICE_INFO_HEADER(Structure):
    _fields_ = [
        ("type", wintypes.UINT),
        ("size", wintypes.UINT),
        ("adapterId", LUID),
        ("id", wintypes.UINT)
    ]

class DISPLAYCONFIG_GET_ADVANCED_COLOR_INFO(Structure):
    _fields_ = [
        ("header", DISPLAYCONFIG_DEVICE_INFO_HEADER),
        ("value", wintypes.UINT),
        ("advancedColorSupported", wintypes.BOOL),
        ("advancedColorEnabled", wintypes.BOOL),
        ("wideColorGamutSupported", wintypes.BOOL),
        ("wideColorGamutEnabled", wintypes.BOOL)
    ]

class DISPLAYCONFIG_PATH_INFO(Structure):
    _fields_ = [("sourceInfo", wintypes.UINT * 4), ("targetInfo", wintypes.UINT * 4)]

class DISPLAYCONFIG_MODE_INFO(Structure):
    _fields_ = [("infoType", wintypes.UINT), ("id", wintypes.UINT), ("adapterId", LUID), ("targetMode", wintypes.UINT * 4)]

QDC_ONLY_ACTIVE_PATHS = 0x00000002
user32 = ctypes.WinDLL('user32')

def get_hdr_status():
    """
    Returns True if ANY connected monitor has HDR (Advanced Color) enabled.
    """
    path_count = wintypes.UINT(0)
    mode_count = wintypes.UINT(0)

    if user32.GetDisplayConfigBufferSizes(QDC_ONLY_ACTIVE_PATHS, ctypes.byref(path_count), ctypes.byref(mode_count)) != 0:
        return False

    paths = (DISPLAYCONFIG_PATH_INFO * path_count.value)()
    modes = (DISPLAYCONFIG_MODE_INFO * mode_count.value)()

    if user32.QueryDisplayConfig(QDC_ONLY_ACTIVE_PATHS, ctypes.byref(path_count), paths, ctypes.byref(mode_count), modes, None) != 0:
        return False

    for i in range(path_count.value):
        path_info = paths[i]
        
        # We need to manually pack the adapterId into LUID structure manually for the header
        # The path_info.targetInfo array contains: [adapterId Low, adapterId High, id, statusFlags]
        
        header = DISPLAYCONFIG_DEVICE_INFO_HEADER()
        header.type = DISPLAYCONFIG_DEVICE_INFO_GET_ADVANCED_COLOR_INFO
        header.size = ctypes.sizeof(DISPLAYCONFIG_GET_ADVANCED_COLOR_INFO)
        header.adapterId = LUID(path_info.targetInfo[0], path_info.targetInfo[1])
        header.id = path_info.targetInfo[2]

        info = DISPLAYCONFIG_GET_ADVANCED_COLOR_INFO()
        info.header = header

        if user32.DisplayConfigGetDeviceInfo(ctypes.byref(info)) == 0:
            if info.advancedColorEnabled:
                return True
                
    return False

def set_hdr_mode(enable=True):
    """
    Toggles HDR if the current state does not match the desired state.
    Uses Win+Alt+B shortcut.
    """
    current_state = get_hdr_status()
    print(f"   >>> HDR Check: Current={current_state}, Target={enable}")
    
    if current_state != enable:
        print("   >>> Toggling HDR via Win+Alt+B...")
        pyautogui.hotkey('win', 'alt', 'b')
        
        # Wait a moment for transition
        time.sleep(3)
        
        # Verify
        new_state = get_hdr_status()
        if new_state == enable:
            print("   >>> HDR Toggle Successful.")
        else:
            print("   >>> Warning: HDR Toggle may have failed or monitor takes long to switch.")
            
    else:
        print("   >>> HDR already in target state.")
