from monitorcontrol import get_monitors

print("--- Deep Scan for Monitor Modes ---")
print("Scanning manufacturer-specific VCP codes (0xE0 - 0xFF)...")

try:
    monitors = get_monitors()
    if not monitors:
        print("No monitors found.")
        exit()

    with monitors[0] as m:
        print(f"Monitor: {m.get_vcp_capabilities().get('model', 'Unknown')}")
        
        # Scan standard possibilities again
        print("\nStandard Codes:")
        for code in [0x14, 0xDC]:
            try:
                val, _ = m.vcp.get_vcp_feature(code)
                print(f"VCP {hex(code)}: {val}")
            except:
                pass

        # Scan Manufacturer Specific (0xE0 - 0xFF)
        print("\nManufacturer Specific Codes:")
        for code in range(0xE0, 0x100):
            try:
                val, _ = m.vcp.get_vcp_feature(code)
                # Only print if we get a valid integer back
                print(f"VCP {hex(code)}: {val}")
            except:
                # Most will fail, that's expected
                pass

except Exception as e:
    print(f"Error: {e}")
