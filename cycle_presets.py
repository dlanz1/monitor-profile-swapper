import time
from monitorcontrol import get_monitors, VCPError

print("--- Monitor Preset Cycler ---")
print("Press Ctrl+C immediately when you see FPS mode!")
print("Starting in 3 seconds...")
time.sleep(3)

try:
    monitors = get_monitors()
    with monitors[0] as m:
        # Loop through likely values
        for i in range(0, 26):
            print(f"Testing Value: {i}")
            try:
                m.vcp.set_vcp_feature(0x14, i)
            except VCPError:
                pass
            
            time.sleep(3) # Wait 3 seconds between swaps

except KeyboardInterrupt:
    print(f"\nStopped! The last value sent was likely the correct one.")
except Exception as e:
    print(f"Error: {e}")

