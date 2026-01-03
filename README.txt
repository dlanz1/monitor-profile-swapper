Monitor Profile Swapper
=======================

This tool automatically changes your monitor's Brightness and Contrast when specific games/programs are running.

Usage:
1. Run "Settings.exe" to configure:
   - Which programs to watch (e.g., EscapeFromTarkov.exe)
   - The Brightness/Contrast levels for "Game Mode"
   - The Brightness/Contrast levels for "Desktop Mode"

2. Run "MonitorSwapper.exe" to start monitoring.
   - Keep this window open (or minimize it).
   - It will automatically switch profiles when it detects the game.

Requirements:
- DDC/CI must be enabled in your monitor's OSD settings.
- Run as Administrator if required by your system policy (usually not needed).

Troubleshooting:
- If settings don't apply, ensure your monitor supports DDC/CI.
- Check "config.json" manually if needed.
