import time
from monitorcontrol import get_monitors

print("--- Monitor Flash Test ---")
print("This will toggle Brightness between 10 and 100 every 3 seconds.")
print("Press Ctrl+C to stop.")

try:
    monitors = get_monitors()
    if not monitors:
        print("No monitors found.")
        exit()

    with monitors[0] as m:
        while True:
            print("Setting Brightness to 10 (Dark)...")
            m.vcp.set_vcp_feature(0x10, 10)
            time.sleep(3)

            print("Setting Brightness to 100 (Bright)...")
            m.vcp.set_vcp_feature(0x10, 100)
            time.sleep(3)

except KeyboardInterrupt:
    print("\nTest stopped.")
except Exception as e:
    print(f"Error: {e}")
