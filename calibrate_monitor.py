from monitorcontrol import get_monitors

print("Scanning monitors for VCP features...")

try:
    monitors = get_monitors()
    if not monitors:
        print("No monitors found. Make sure DDC/CI is enabled in your monitor's OSD menu.")
    
    for i, monitor in enumerate(monitors):
        print(f"\n--- Monitor {i + 1} ---")
        with monitor:
            # Try reading VCP 0x14 (Select Color Preset)
            try:
                val_14, _ = monitor.vcp.get_vcp_feature(0x14)
                print(f"VCP 0x14 (Color Preset): {val_14}")
            except Exception as e:
                print(f"VCP 0x14 (Color Preset): Not supported or Error ({e})")

            # Try reading VCP 0xDC (Display Mode)
            try:
                val_DC, _ = monitor.vcp.get_vcp_feature(0xDC)
                print(f"VCP 0xDC (Display Mode): {val_DC}")
            except Exception as e:
                print(f"VCP 0xDC (Display Mode): Not supported or Error ({e})")

except Exception as e:
    print(f"An error occurred: {e}")
    print("Ensure you have installed the library: pip install monitorcontrol")
