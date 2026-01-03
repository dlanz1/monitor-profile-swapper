from monitorcontrol import get_monitors

print("Reading Picture Settings...")
try:
    with get_monitors()[0] as m:
        # 0x10=Brightness, 0x12=Contrast
        # 0x16=Red Gain, 0x18=Green Gain, 0x1A=Blue Gain
        
        bri = m.vcp.get_vcp_feature(0x10)[0]
        con = m.vcp.get_vcp_feature(0x12)[0]
        
        print(f"Brightness: {bri}")
        print(f"Contrast:   {con}")
        
        try:
            r = m.vcp.get_vcp_feature(0x16)[0]
            g = m.vcp.get_vcp_feature(0x18)[0]
            b = m.vcp.get_vcp_feature(0x1A)[0]
            print(f"RGB:        {r}, {g}, {b}")
        except:
            print("RGB:        Not readable")

except Exception as e:
    print(f"Error: {e}")
