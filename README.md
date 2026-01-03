# Monitor Profile Swapper

![Python](https://img.shields.io/badge/Python-3.x-blue?style=for-the-badge&logo=python)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey?style=for-the-badge&logo=windows)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**Automate your monitor's brightness and contrast settings based on the game you're playing.**

Monitor Profile Swapper is a lightweight utility that automatically switches your monitor's display settings (Brightness & Contrast) when specific applications (like games) are launched. When you close the game, it instantly reverts to your desktop preferences.

Perfect for games like *Escape from Tarkov* where higher visibility is crucial, without blinding yourself on your desktop.

---

## 📸 Preview

**Configuration GUI**
![Settings Preview](docs/gui_preview.png)

---

## ✨ Features

*   **Automatic Detection**: Watches for specific process names (e.g., `EscapeFromTarkov.exe`).
*   **Dual Profiles**:
    *   **Game Mode**: Boost brightness/contrast for competitive advantage.
    *   **Desktop Mode**: Comfortable settings for browsing and work.
*   **User Friendly GUI**: Easily add/remove games and tweak settings without editing code.
*   **DDC/CI Support**: Communicates directly with your monitor hardware.
*   **Portable**: Runs as a standalone executable (no installation required).

---

## 🚀 Installation & Usage

### Option 1: Download the Release
1.  Download the latest `.zip` from the [Releases](../../releases) page.
2.  Extract the folder to a location of your choice.
3.  Open the folder.

### Option 2: Build from Source
If you prefer to run from source or build it yourself:
```bash
git clone https://github.com/dlanz1/monitor-profile-swapper.git
cd monitor-profile-swapper
pip install -r requirements.txt
python build.py
```

---

## 🎮 How to Use

1.  **Configure Settings**:
    Run `Settings.exe`.
    *   **Game Processes**: Add the executable names of the games you want to detect (e.g., `game.exe`).
    *   **Monitor Settings**: Enter values (0-100) for Brightness and Contrast for both modes.
    *   Click **Save Settings**.

2.  **Start Monitoring**:
    Run `MonitorSwapper.exe`.
    *   Keep this window open (or minimize it).
    *   The tool will scan for your games every few seconds.
    *   When a game is found, your monitor will visibly update.

---

## ⚠️ Requirements

*   **DDC/CI Enabled Monitor**: Ensure "DDC/CI" is turned **ON** in your physical monitor's OSD menu.
*   **Windows OS**: Currently supports Windows due to DDC/CI library dependencies.

---

## 🛠️ Configuration

Your settings are stored in `config.json`. You can edit this file manually if you prefer:

```json
{
    "game_processes": [
        "EscapeFromTarkov.exe",
        "TarkovArena.exe"
    ],
    "game_mode": {
        "brightness": 100,
        "contrast": 80
    },
    "desktop_mode": {
        "brightness": 40,
        "contrast": 50
    }
}
```

---

## 🤝 Contributing

1.  Fork the repository.
2.  Create your feature branch (`git checkout -b feature/AmazingFeature`).
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4.  Push to the branch (`git push origin feature/AmazingFeature`).
5.  Open a Pull Request.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
