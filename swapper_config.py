import tkinter as tk
from tkinter import messagebox, simpledialog, ttk, filedialog
import json
import os
import sys
import threading
import sv_ttk
import darkdetect
from monitorcontrol import get_monitors

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

DEFAULT_CONFIG = {
    "game_processes": ["EscapeFromTarkov.exe", "EscapeFromTarkov_BE.exe", "TarkovArena.exe"],
    "game_mode": {"brightness": 80, "contrast": 80, "hdr_enabled": False},
    "desktop_mode": {"brightness": 50, "contrast": 50},
    "tray_enabled": True
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
        self.root.geometry("600x600")
        
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
        
        ttk.Button(btn_row, text="Add Manually", command=self.add_process).pack(side="left", padx=(0, 5))
        ttk.Button(btn_row, text="Browse...", command=self.browse_process).pack(side="left", padx=(0, 5))
        ttk.Button(btn_row, text="Remove Selected", command=self.remove_process).pack(side="left")

        # --- Settings Section ---
        settings_container = ttk.LabelFrame(self, text="Monitor Calibration (0-100)", padding=(15, 15))
        settings_container.pack(fill="x", pady=(0, 20))

        # Grid Layout for Settings
        settings_container.columnconfigure(1, weight=1)
        settings_container.columnconfigure(3, weight=1)

        # Game Mode Column
        game_header_frame = ttk.Frame(settings_container)
        game_header_frame.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        
        ttk.Label(game_header_frame, text="🎮 Game Mode", font=("Segoe UI", 11, "bold")).pack(side="left", padx=(0, 10))
        ttk.Button(game_header_frame, text="Test", width=5, command=lambda: self.test_settings("game")).pack(side="left")

        ttk.Label(settings_container, text="Brightness").grid(row=1, column=0, sticky="w", pady=5)
        self.game_bri = ttk.Spinbox(settings_container, from_=0, to=100, width=8)
        self.game_bri.grid(row=1, column=1, sticky="w", padx=10)

        ttk.Label(settings_container, text="Contrast").grid(row=2, column=0, sticky="w", pady=5)
        self.game_con = ttk.Spinbox(settings_container, from_=0, to=100, width=8)
        self.game_con.grid(row=2, column=1, sticky="w", padx=10)

        # HDR Checkbox
        self.hdr_var = tk.BooleanVar()
        self.hdr_chk = ttk.Checkbutton(settings_container, text="Enable HDR", variable=self.hdr_var)
        self.hdr_chk.grid(row=3, column=0, columnspan=2, sticky="w", pady=(10, 0))

        # Divider
        ttk.Separator(settings_container, orient="vertical").grid(row=0, column=2, rowspan=4, sticky="ns", padx=20)

        # Desktop Mode Column
        desk_header_frame = ttk.Frame(settings_container)
        desk_header_frame.grid(row=0, column=3, columnspan=2, sticky="w", pady=(0, 10))

        ttk.Label(desk_header_frame, text="🖥️ Desktop Mode", font=("Segoe UI", 11, "bold")).pack(side="left", padx=(0, 10))
        ttk.Button(desk_header_frame, text="Test", width=5, command=lambda: self.test_settings("desktop")).pack(side="left")

        ttk.Label(settings_container, text="Brightness").grid(row=1, column=3, sticky="w", pady=5)
        self.desk_bri = ttk.Spinbox(settings_container, from_=0, to=100, width=8)
        self.desk_bri.grid(row=1, column=4, sticky="w", padx=10)

        ttk.Label(settings_container, text="Contrast").grid(row=2, column=3, sticky="w", pady=5)
        self.desk_con = ttk.Spinbox(settings_container, from_=0, to=100, width=8)
        self.desk_con.grid(row=2, column=4, sticky="w", padx=10)

        # --- Footer ---
        footer_frame = ttk.Frame(self)
        footer_frame.pack(fill="x", pady=10)

        # Tray Option
        self.tray_var = tk.BooleanVar()
        ttk.Checkbutton(footer_frame, text="Show System Tray Icon", variable=self.tray_var).pack(side="left")

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
        self.hdr_var.set(self.config["game_mode"].get("hdr_enabled", False))

        self.desk_bri.set(self.config["desktop_mode"]["brightness"])
        self.desk_con.set(self.config["desktop_mode"]["contrast"])
        
        self.tray_var.set(self.config.get("tray_enabled", True))

    def test_settings(self, mode):
        try:
            if mode == "game":
                bri = int(self.game_bri.get())
                con = int(self.game_con.get())
                lbl = "Game Mode"
            else:
                bri = int(self.desk_bri.get())
                con = int(self.desk_con.get())
                lbl = "Desktop Mode"
        except ValueError:
            messagebox.showerror("Invalid Input", "Brightness and Contrast must be integers (0-100).", parent=self.root)
            return

        def run_test():
            try:
                monitors = get_monitors()
                if not monitors:
                    self.root.after(0, lambda: messagebox.showerror("Error", "No compatible monitors found!", parent=self.root))
                    return

                applied_count = 0
                for m in monitors:
                    with m:
                        # Apply Brightness (0x10) and Contrast (0x12)
                        m.vcp.set_vcp_feature(0x10, bri)
                        m.vcp.set_vcp_feature(0x12, con)
                        applied_count += 1

                msg = f"Applied {lbl} settings to {applied_count} monitor(s).\n(B: {bri}, C: {con})"
                self.root.after(0, lambda: messagebox.showinfo("Test Complete", msg, parent=self.root))

            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to apply settings: {e}", parent=self.root))
            finally:
                self.root.after(0, lambda: self.root.config(cursor=""))

        # Show busy cursor
        self.root.config(cursor="wait")
        self.root.update()

        # Run in background
        threading.Thread(target=run_test, daemon=True).start()

    def add_process(self):
        new_proc = simpledialog.askstring("Add Process", "Enter process name (e.g. game.exe):", parent=self.root)
        if new_proc:
            if new_proc not in self.config["game_processes"]:
                self.config["game_processes"].append(new_proc)
                self.refresh_ui()

    def browse_process(self):
        file_path = filedialog.askopenfilename(
            title="Select Game Executable",
            filetypes=[("Executable Files", "*.exe"), ("All Files", "*.*")],
            parent=self.root
        )
        if file_path:
            filename = os.path.basename(file_path)
            if filename not in self.config["game_processes"]:
                self.config["game_processes"].append(filename)
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
            self.config["game_mode"]["hdr_enabled"] = self.hdr_var.get()
            self.config["desktop_mode"]["brightness"] = int(self.desk_bri.get())
            self.config["desktop_mode"]["contrast"] = int(self.desk_con.get())
            self.config["game_processes"] = list(self.proc_listbox.get(0, tk.END))
            self.config["tray_enabled"] = self.tray_var.get()
            
            save_config(self.config)
        except ValueError:
            messagebox.showerror("Error", "Brightness and Contrast must be integers (0-100).", parent=self.root)

if __name__ == "__main__":
    root = tk.Tk()
    app = ConfigApp(root)
    root.mainloop()
