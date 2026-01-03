import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import json
import os
import sys
import sv_ttk
import darkdetect

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

class ConfigApp(ttk.Frame):
    def __init__(self, root):
        super().__init__(root)
        self.root = root
        self.root.title("Monitor Profile Swapper")
        self.root.geometry("600x550")
        
        # Initial Theme Application
        self.current_theme = darkdetect.theme()
        sv_ttk.set_theme(self.current_theme.lower())
        
        # Start monitoring for theme changes
        self.check_theme_change()

        self.config = load_config()
        self.pack(fill="both", expand=True, padx=20, pady=20)

        # Header
        header_lbl = ttk.Label(self, text="Profile Settings", font=("Segoe UI Variable Display", 18, "bold"))
        header_lbl.pack(anchor="w", pady=(0, 20))

        # --- Game Processes Section ---
        proc_frame = ttk.LabelFrame(self, text="Watched Processes", padding=(15, 10))
        proc_frame.pack(fill="both", expand=True, pady=(0, 15))

        self.proc_listbox = tk.Listbox(proc_frame, height=6, font=("Segoe UI", 10), 
                                       borderwidth=0, highlightthickness=1, selectmode="single")
        self.proc_listbox.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        scrollbar = ttk.Scrollbar(proc_frame, orient="vertical", command=self.proc_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.proc_listbox.config(yscrollcommand=scrollbar.set)

        btn_row = ttk.Frame(proc_frame)
        btn_row.pack(fill="x", pady=(10, 0))
        
        ttk.Button(btn_row, text="Add Process", command=self.add_process).pack(side="left", padx=(0, 5))
        ttk.Button(btn_row, text="Remove Selected", command=self.remove_process).pack(side="left")

        # --- Settings Section ---
        settings_container = ttk.LabelFrame(self, text="Monitor Calibration (0-100)", padding=(15, 15))
        settings_container.pack(fill="x", pady=(0, 20))

        # Grid Layout for Settings
        settings_container.columnconfigure(1, weight=1)
        settings_container.columnconfigure(3, weight=1)

        # Game Mode Column
        ttk.Label(settings_container, text="🎮 Game Mode", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        
        ttk.Label(settings_container, text="Brightness").grid(row=1, column=0, sticky="w", pady=5)
        self.game_bri = ttk.Spinbox(settings_container, from_=0, to=100, width=8)
        self.game_bri.grid(row=1, column=1, sticky="w", padx=10)

        ttk.Label(settings_container, text="Contrast").grid(row=2, column=0, sticky="w", pady=5)
        self.game_con = ttk.Spinbox(settings_container, from_=0, to=100, width=8)
        self.game_con.grid(row=2, column=1, sticky="w", padx=10)

        # Divider
        ttk.Separator(settings_container, orient="vertical").grid(row=0, column=2, rowspan=3, sticky="ns", padx=20)

        # Desktop Mode Column
        ttk.Label(settings_container, text="🖥️ Desktop Mode", font=("Segoe UI", 11, "bold")).grid(row=0, column=3, columnspan=2, sticky="w", pady=(0, 10))

        ttk.Label(settings_container, text="Brightness").grid(row=1, column=3, sticky="w", pady=5)
        self.desk_bri = ttk.Spinbox(settings_container, from_=0, to=100, width=8)
        self.desk_bri.grid(row=1, column=4, sticky="w", padx=10)

        ttk.Label(settings_container, text="Contrast").grid(row=2, column=3, sticky="w", pady=5)
        self.desk_con = ttk.Spinbox(settings_container, from_=0, to=100, width=8)
        self.desk_con.grid(row=2, column=4, sticky="w", padx=10)

        # --- Footer ---
        footer_frame = ttk.Frame(self)
        footer_frame.pack(fill="x", pady=10)

        save_btn = ttk.Button(footer_frame, text="Save Configuration", command=self.save_settings, style="Accent.TButton")
        save_btn.pack(side="right")
        
        reload_btn = ttk.Button(footer_frame, text="Discard Changes", command=self.refresh_ui)
        reload_btn.pack(side="right", padx=10)

        self.refresh_ui()

    def check_theme_change(self):
        new_theme = darkdetect.theme()
        if new_theme != self.current_theme:
            self.current_theme = new_theme
            if new_theme:
                sv_ttk.set_theme(new_theme.lower())
        
        # Check again in 2 seconds
        self.root.after(2000, self.check_theme_change)

    def refresh_ui(self):
        self.config = load_config()
        
        # Processes
        self.proc_listbox.delete(0, tk.END)
        for p in self.config.get("game_processes", []):
            self.proc_listbox.insert(tk.END, p)
        
        # Settings
        self.game_bri.set(self.config["game_mode"]["brightness"])
        self.game_con.set(self.config["game_mode"]["contrast"])

        self.desk_bri.set(self.config["desktop_mode"]["brightness"])
        self.desk_con.set(self.config["desktop_mode"]["contrast"])

    def add_process(self):
        new_proc = simpledialog.askstring("Add Process", "Enter process name (e.g. game.exe):", parent=self.root)
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
        if messagebox.askyesno("Confirm", f"Remove '{proc}'?", parent=self.root):
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
            messagebox.showerror("Error", "Brightness and Contrast must be integers (0-100).", parent=self.root)

if __name__ == "__main__":
    root = tk.Tk()
    app = ConfigApp(root)
    root.mainloop()
