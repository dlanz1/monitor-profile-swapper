import subprocess
import os
import shutil

def run_command(command):
    print(f"Running: {command}")
    subprocess.check_call(command, shell=True)

def main():
    if not shutil.which("pyinstaller"):
        print("Error: PyInstaller not found. Please install it with 'pip install pyinstaller'")
        return

    # Clean previous builds
    if os.path.exists("build"):
        shutil.rmtree("build")
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    if os.path.exists("Release"):
        shutil.rmtree("Release")

    print("Building MonitorSwapper...")
    run_command("pyinstaller --noconfirm --onefile --console --name MonitorSwapper --hidden-import=pyautogui monitor_swapper.py")

    print("Building Settings GUI...")
    run_command("pyinstaller --noconfirm --onefile --windowed --name Settings --hidden-import=sv_ttk --hidden-import=darkdetect swapper_config.py")

    # Organize into a Release folder
    os.makedirs("Release", exist_ok=True)
    
    shutil.move("dist/MonitorSwapper.exe", "Release/MonitorSwapper.exe")
    shutil.move("dist/Settings.exe", "Release/Settings.exe")
    
    if os.path.exists("config.json"):
        shutil.copy("config.json", "Release/config.json")
    
    if os.path.exists("README.txt"):
        shutil.copy("README.txt", "Release/README.txt")

    print("\nBuild Complete! Check the 'Release' folder.")

if __name__ == "__main__":
    main()

