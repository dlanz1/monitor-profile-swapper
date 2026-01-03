import tkinter as tk
from tkinter import messagebox, simpledialog
import json
import os
import sys

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "game_processes": ["EscapeFromTarkov.exe", "EscapeFromTarkov_BE.exe", "TarkovArena.exe"],
    "game_mode": {"brightness": 80, "contrast": 80},
    "desktop_mode": {"brightness": 50, "contrast": 50}
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load config: {e}\nUsing defaults.")
        return DEFAULT_CONFIG

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        messagebox.showinfo("Success", "Configuration saved successfully!")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save config: {e}")

class ConfigApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Monitor Profile Swapper Settings")
        self.config = load_config()

        # Frames
        self.proc_frame = tk.LabelFrame(root, text="Game Processes (Watch List)")
        self.proc_frame.pack(fill="both", expand="yes", padx=10, pady=5)

        self.settings_frame = tk.LabelFrame(root, text="Monitor Settings (0-100)")
        self.settings_frame.pack(fill="both", expand="yes", padx=10, pady=5)

        self.btn_frame = tk.Frame(root)
        self.btn_frame.pack(fill="x", padx=10, pady=10)

        # Process List
        self.proc_listbox = tk.Listbox(self.proc_frame, height=6)
        self.proc_listbox.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        self.scrollbar = tk.Scrollbar(self.proc_frame)
        self.scrollbar.pack(side="right", fill="y")
        self.proc_listbox.config(yscrollcommand=self.scrollbar.set)
        self.scrollbar.config(command=self.proc_listbox.yview)

        self.proc_btn_frame = tk.Frame(self.proc_frame)
        self.proc_btn_frame.pack(side="bottom", fill="x", padx=5, pady=5)
        
        tk.Button(self.proc_btn_frame, text="Add Process", command=self.add_process).pack(side="left", padx=5)
        tk.Button(self.proc_btn_frame, text="Remove Selected", command=self.remove_process).pack(side="left", padx=5)

        # Settings Inputs
        # Game Mode
        tk.Label(self.settings_frame, text="Game Mode", font=("Arial", 10, "bold")).grid(row=0, column=0, columnspan=2, pady=5)
        tk.Label(self.settings_frame, text="Brightness:").grid(row=1, column=0, sticky="e")
        self.game_bri = tk.Entry(self.settings_frame, width=10)
        self.game_bri.grid(row=1, column=1)
        tk.Label(self.settings_frame, text="Contrast:").grid(row=2, column=0, sticky="e")
        self.game_con = tk.Entry(self.settings_frame, width=10)
        self.game_con.grid(row=2, column=1)

        # Desktop Mode
        tk.Label(self.settings_frame, text="Desktop Mode", font=("Arial", 10, "bold")).grid(row=0, column=2, columnspan=2, pady=5)
        tk.Label(self.settings_frame, text="Brightness:").grid(row=1, column=2, sticky="e")
        self.desk_bri = tk.Entry(self.settings_frame, width=10)
        self.desk_bri.grid(row=1, column=3)
        tk.Label(self.settings_frame, text="Contrast:").grid(row=2, column=2, sticky="e")
        self.desk_con = tk.Entry(self.settings_frame, width=10)
        self.desk_con.grid(row=2, column=3)

        # Action Buttons
        tk.Button(self.btn_frame, text="Save Settings", command=self.save_settings, bg="#dddddd").pack(side="right", padx=10)
        tk.Button(self.btn_frame, text="Reload from File", command=self.refresh_ui).pack(side="right", padx=10)

        self.refresh_ui()

    def refresh_ui(self):
        self.config = load_config()
        
        # Processes
        self.proc_listbox.delete(0, tk.END)
        for p in self.config.get("game_processes", []):
            self.proc_listbox.insert(tk.END, p)
        
        # Settings
        self.game_bri.delete(0, tk.END)
        self.game_bri.insert(0, str(self.config["game_mode"]["brightness"]))
        self.game_con.delete(0, tk.END)
        self.game_con.insert(0, str(self.config["game_mode"]["contrast"]))

        self.desk_bri.delete(0, tk.END)
        self.desk_bri.insert(0, str(self.config["desktop_mode"]["brightness"]))
        self.desk_con.delete(0, tk.END)
        self.desk_con.insert(0, str(self.config["desktop_mode"]["contrast"]))

    def add_process(self):
        new_proc = simpledialog.askstring("Add Process", "Enter process name (e.g. game.exe):")
        if new_proc:
            if new_proc not in self.config["game_processes"]:
                self.config["game_processes"].append(new_proc)
                self.refresh_ui()

    def remove_process(self):
        sel = self.proc_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        proc = self.proc_listbox.get(idx)
        if messagebox.askyesno("Confirm", f"Remove '{proc}'?"):
            self.config["game_processes"].remove(proc)
            self.refresh_ui()

    def save_settings(self):
        try:
            self.config["game_mode"]["brightness"] = int(self.game_bri.get())
            self.config["game_mode"]["contrast"] = int(self.game_con.get())
            self.config["desktop_mode"]["brightness"] = int(self.desk_bri.get())
            self.config["desktop_mode"]["contrast"] = int(self.desk_con.get())
            self.config["game_processes"] = list(self.proc_listbox.get(0, tk.END))
            
            save_config(self.config)
        except ValueError:
            messagebox.showerror("Error", "Brightness and Contrast must be integers (0-100).")

if __name__ == "__main__":
    root = tk.Tk()
    app = ConfigApp(root)
    root.mainloop()
