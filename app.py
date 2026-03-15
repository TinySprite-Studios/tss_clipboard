import ctypes
import ctypes.wintypes
import json
import os
import sys
import threading
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk


APP_NAME = "TSS Clipboard"
MAX_ENTRIES = 100
ERROR_ALREADY_EXISTS = 183


def _get_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(__file__)


BASE_DIR = _get_base_dir()
DATA_FILE = os.path.join(BASE_DIR, "clipboard_entries.json")


def _resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(BASE_DIR, relative_path)


class ClipboardApp:
    MOD_ALT = 0x0001
    WM_HOTKEY = 0x0312
    HOTKEY_ID = 1
    VK_C = 0x43

    def __init__(self, mutex_handle):
        self.mutex_handle = mutex_handle
        self.root = tk.Tk()
        self.root.title("TSS Clipboard")
        self.root.geometry("520x560+220+140")
        self.root.overrideredirect(True)
        self.root.configure(bg="#020802")
        self.start_hidden = "--hidden" in sys.argv

        self._drag_x = 0
        self._drag_y = 0
        self._stop_hotkey = threading.Event()
        self._hotkey_thread_id = None
        self.entries = []
        self.logo_img = None
        self.title_logo_img = None
        self.settings_btn_img = None

        self._build_ui()
        self._load_entries()
        self._refresh_list()

        self._load_window_icon()
        if self.start_hidden:
            self.root.withdraw()

        self.root.bind("<Escape>", lambda _e: self.hide_window())
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)

        self.hotkey_thread = threading.Thread(target=self._hotkey_listener, daemon=True)
        self.hotkey_thread.start()

    def _build_ui(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "Terminal.Vertical.TScrollbar",
            troughcolor="#000000",
            background="#0f3b18",
            arrowcolor="#8dffaf",
            bordercolor="#00aa2b",
            lightcolor="#00aa2b",
            darkcolor="#0a2410",
            arrowsize=14,
        )
        style.map(
            "Terminal.Vertical.TScrollbar",
            background=[("active", "#00a32b"), ("pressed", "#00c133")],
            arrowcolor=[("active", "#c9ffd9")],
        )

        title_bar = tk.Frame(self.root, bg="#081808", highlightthickness=1, highlightbackground="#00ff41")
        title_bar.pack(fill="x")

        self._build_title_logo(title_bar)

        title_label = tk.Label(
            title_bar,
            text="TSS CLIPBOARD TERMINAL",
            fg="#00ff41",
            bg="#081808",
            font=("Consolas", 12, "bold"),
            padx=10,
            pady=8,
        )
        title_label.pack(side="left")

        settings_btn = tk.Button(
            title_bar,
            text="SET",
            command=self.open_settings,
            bg="#081808",
            fg="#8dffaf",
            activebackground="#103010",
            activeforeground="#c9ffd9",
            relief="flat",
            bd=0,
            width=5,
            cursor="hand2",
            font=("Consolas", 9, "bold"),
        )
        settings_btn.pack(side="right", padx=2, pady=2)
        self._apply_settings_button_icon(settings_btn)

        close_btn = tk.Button(
            title_bar,
            text="X",
            command=self.quit_app,
            bg="#081808",
            fg="#ff4d4d",
            activebackground="#301010",
            activeforeground="#ff7676",
            relief="flat",
            bd=0,
            width=3,
            cursor="hand2",
            font=("Consolas", 11, "bold"),
        )
        close_btn.pack(side="right", padx=2, pady=2)

        hide_btn = tk.Button(
            title_bar,
            text="_",
            command=self.hide_window,
            bg="#081808",
            fg="#ffd700",
            activebackground="#103010",
            activeforeground="#ffd700",
            relief="flat",
            bd=0,
            width=3,
            cursor="hand2",
            font=("Consolas", 11, "bold"),
        )
        hide_btn.pack(side="right", padx=2, pady=2)

        for widget in (title_bar, title_label, self.title_logo_label):
            widget.bind("<ButtonPress-1>", self._start_move)
            widget.bind("<B1-Motion>", self._do_move)

        body = tk.Frame(self.root, bg="#020802", padx=12, pady=12)
        body.pack(fill="both", expand=True)

        entry_frame = tk.Frame(body, bg="#020802")
        entry_frame.pack(fill="x", pady=(0, 10))

        self.input_var = tk.StringVar()
        self.input_box = tk.Entry(
            entry_frame,
            textvariable=self.input_var,
            bg="#000000",
            fg="#00ff41",
            insertbackground="#00ff41",
            highlightthickness=1,
            highlightbackground="#00aa2b",
            highlightcolor="#00ff41",
            relief="flat",
            font=("Consolas", 10),
        )
        self.input_box.pack(side="left", fill="x", expand=True, ipady=8)

        save_btn = tk.Button(
            entry_frame,
            text="SAVE",
            command=self.add_entry,
            bg="#00a32b",
            fg="#000000",
            activebackground="#00c133",
            activeforeground="#000000",
            relief="flat",
            cursor="hand2",
            font=("Consolas", 10, "bold"),
            padx=18,
            pady=8,
        )
        save_btn.pack(side="left", padx=(8, 0), fill="y")

        list_frame = tk.Frame(body, bg="#020802")
        list_frame.pack(fill="both", expand=True)

        self.listbox = tk.Listbox(
            list_frame,
            bg="#000000",
            fg="#8dffaf",
            selectbackground="#00ff41",
            selectforeground="#000000",
            highlightthickness=1,
            highlightbackground="#00aa2b",
            relief="flat",
            font=("Consolas", 10),
            activestyle="none",
        )
        self.listbox.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(
            list_frame,
            command=self.listbox.yview,
            orient="vertical",
            style="Terminal.Vertical.TScrollbar",
        )
        scrollbar.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=scrollbar.set)

        self.listbox.bind("<<ListboxSelect>>", self._copy_selected)
        self.listbox.bind("<Button-3>", self._show_context_menu)

        self.context_menu = tk.Menu(self.root, tearoff=0, bg="#061206", fg="#8dffaf", activebackground="#00aa2b")
        self.context_menu.add_command(label="Edit", command=self.edit_selected)
        self.context_menu.add_command(label="Delete", command=self.delete_selected)

        self.status_var = tk.StringVar(value="Hidden by default. Press Alt+C to toggle.")
        status = tk.Label(
            body,
            textvariable=self.status_var,
            bg="#020802",
            fg="#7ac78e",
            anchor="w",
            font=("Consolas", 9),
            pady=8,
        )
        status.pack(fill="x")

    def _load_window_icon(self):
        logo_path = _resource_path(os.path.join("assets", "images", "clipboard_logo.png"))
        if not os.path.exists(logo_path):
            return
        try:
            self.logo_img = tk.PhotoImage(file=logo_path)
            self.root.iconphoto(True, self.logo_img)
        except Exception:
            pass

    def _build_title_logo(self, parent):
        logo_path = _resource_path(os.path.join("assets", "images", "clipboard_logo.png"))
        self.title_logo_label = tk.Label(parent, bg="#081808")
        self.title_logo_label.pack(side="left", padx=(8, 4), pady=4)

        if not os.path.exists(logo_path):
            return

        try:
            raw = tk.PhotoImage(file=logo_path)
            factor = max(1, max(raw.width(), raw.height()) // 18)
            self.title_logo_img = raw.subsample(factor, factor) if factor > 1 else raw
            self.title_logo_label.configure(image=self.title_logo_img)
        except Exception:
            self.title_logo_label.configure(text="[]", fg="#00ff41", font=("Consolas", 9, "bold"))

    def _apply_settings_button_icon(self, settings_btn):
        settings_logo_path = _resource_path(os.path.join("assets", "images", "clipboard_settings_logo.png"))
        if not os.path.exists(settings_logo_path):
            return

        try:
            raw = tk.PhotoImage(file=settings_logo_path)
            factor = max(1, max(raw.width(), raw.height()) // 18)
            self.settings_btn_img = raw.subsample(factor, factor) if factor > 1 else raw
            settings_btn.configure(image=self.settings_btn_img, text="", width=24, height=24)
        except Exception:
            pass

    def _start_move(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _do_move(self, event):
        x = self.root.winfo_pointerx() - self._drag_x
        y = self.root.winfo_pointery() - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    def _load_entries(self):
        if not os.path.exists(DATA_FILE):
            self.entries = []
            return

        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self.entries = [str(item) for item in data[:MAX_ENTRIES]]
            else:
                self.entries = []
        except Exception:
            self.entries = []

    def _save_entries(self):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.entries[:MAX_ENTRIES], f, ensure_ascii=False, indent=2)

    def _preview(self, text):
        first_line = text.strip().splitlines()[0] if text.strip() else "(empty)"
        if len(first_line) > 58:
            return first_line[:58] + "..."
        return first_line

    def _refresh_list(self):
        self.listbox.delete(0, tk.END)
        for i, entry in enumerate(self.entries, start=1):
            self.listbox.insert(tk.END, f"{i:02d}. {self._preview(entry)}")
        self.status_var.set(f"{len(self.entries)}/{MAX_ENTRIES} saved entries")

    def add_entry(self):
        text = self.input_var.get().strip()
        if not text:
            self.status_var.set("Nothing to save.")
            return

        if len(self.entries) >= MAX_ENTRIES:
            messagebox.showwarning("Limit reached", f"Maximum of {MAX_ENTRIES} entries reached.")
            return

        self.entries.append(text)
        self._save_entries()
        self._refresh_list()
        self.input_var.set("")
        self.status_var.set("Entry saved.")

    def _copy_selected(self, _event=None):
        selected = self.listbox.curselection()
        if not selected:
            return

        idx = selected[0]
        text = self.entries[idx]
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()
        self.status_var.set(f"Copied entry {idx + 1} to clipboard.")

    def _show_context_menu(self, event):
        idx = self.listbox.nearest(event.y)
        if idx >= 0:
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(idx)
            self.listbox.activate(idx)
            self.context_menu.tk_popup(event.x_root, event.y_root)

    def _open_edit_dialog(self, idx):
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Entry")
        dialog.geometry("500x240")
        dialog.configure(bg="#020802")
        dialog.transient(self.root)
        dialog.grab_set()

        label = tk.Label(
            dialog,
            text=f"Edit entry {idx + 1}",
            bg="#020802",
            fg="#00ff41",
            font=("Consolas", 11, "bold"),
            pady=8,
        )
        label.pack()

        edit_box = tk.Text(
            dialog,
            bg="#000000",
            fg="#8dffaf",
            insertbackground="#00ff41",
            highlightthickness=1,
            highlightbackground="#00aa2b",
            relief="flat",
            font=("Consolas", 10),
            wrap="word",
            height=8,
        )
        edit_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        edit_box.insert("1.0", self.entries[idx])

        btn_row = tk.Frame(dialog, bg="#020802")
        btn_row.pack(fill="x", padx=10, pady=(0, 10))

        def save_edit():
            new_text = edit_box.get("1.0", tk.END).strip()
            if not new_text:
                messagebox.showwarning("Invalid entry", "Entry cannot be empty.")
                return
            self.entries[idx] = new_text
            self._save_entries()
            self._refresh_list()
            self.status_var.set(f"Edited entry {idx + 1}.")
            dialog.destroy()

        save_btn = tk.Button(
            btn_row,
            text="SAVE",
            command=save_edit,
            bg="#00a32b",
            fg="#000000",
            activebackground="#00c133",
            activeforeground="#000000",
            relief="flat",
            cursor="hand2",
            font=("Consolas", 10, "bold"),
            padx=14,
            pady=6,
        )
        save_btn.pack(side="right", padx=(6, 0))

        cancel_btn = tk.Button(
            btn_row,
            text="CANCEL",
            command=dialog.destroy,
            bg="#2a2a2a",
            fg="#8dffaf",
            activebackground="#404040",
            activeforeground="#8dffaf",
            relief="flat",
            cursor="hand2",
            font=("Consolas", 10),
            padx=14,
            pady=6,
        )
        cancel_btn.pack(side="right")

    def _startup_cmd_path(self):
        appdata = os.environ.get("APPDATA", "")
        startup_dir = os.path.join(
            appdata,
            "Microsoft",
            "Windows",
            "Start Menu",
            "Programs",
            "Startup",
        )
        return os.path.join(startup_dir, f"{APP_NAME}.cmd")

    def _startup_cmd_content(self):
        if getattr(sys, "frozen", False):
            exe_path = sys.executable
            return f'@echo off\nstart "" "{exe_path}" --hidden\n'

        bat_path = os.path.join(BASE_DIR, "start_clipboard.bat")
        if os.path.exists(bat_path):
            return f'@echo off\nstart "" "{bat_path}"\n'

        pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        app_path = os.path.join(BASE_DIR, "app.py")
        return f'@echo off\nstart "" "{pyw}" "{app_path}" --hidden\n'

    def is_startup_enabled(self):
        return os.path.exists(self._startup_cmd_path())

    def set_startup_enabled(self, enabled):
        startup_path = self._startup_cmd_path()
        if enabled:
            os.makedirs(os.path.dirname(startup_path), exist_ok=True)
            with open(startup_path, "w", encoding="utf-8") as f:
                f.write(self._startup_cmd_content())
        else:
            if os.path.exists(startup_path):
                os.remove(startup_path)

    def open_settings(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Settings")
        dialog.geometry("360x170")
        dialog.configure(bg="#020802")
        dialog.transient(self.root)
        dialog.grab_set()

        label = tk.Label(
            dialog,
            text="SETTINGS",
            bg="#020802",
            fg="#00ff41",
            font=("Consolas", 12, "bold"),
            pady=10,
        )
        label.pack()

        settings_wrap = tk.Frame(dialog, bg="#020802", padx=14, pady=6)
        settings_wrap.pack(fill="both", expand=True)

        startup_var = tk.BooleanVar(value=self.is_startup_enabled())
        startup_check = tk.Checkbutton(
            settings_wrap,
            text="Run on startup",
            variable=startup_var,
            bg="#020802",
            fg="#8dffaf",
            activebackground="#020802",
            activeforeground="#c9ffd9",
            selectcolor="#000000",
            font=("Consolas", 10),
            highlightthickness=0,
        )
        startup_check.pack(anchor="w")

        status = tk.Label(
            settings_wrap,
            text="Applies for current Windows user.",
            bg="#020802",
            fg="#7ac78e",
            font=("Consolas", 9),
            pady=8,
        )
        status.pack(anchor="w")

        btn_row = tk.Frame(settings_wrap, bg="#020802")
        btn_row.pack(fill="x", pady=(8, 0))

        def save_settings():
            try:
                self.set_startup_enabled(startup_var.get())
                self.status_var.set(
                    "Settings updated: startup enabled."
                    if startup_var.get()
                    else "Settings updated: startup disabled."
                )
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror("Settings error", str(exc))

        save_btn = tk.Button(
            btn_row,
            text="SAVE",
            command=save_settings,
            bg="#00a32b",
            fg="#000000",
            activebackground="#00c133",
            activeforeground="#000000",
            relief="flat",
            cursor="hand2",
            font=("Consolas", 10, "bold"),
            padx=14,
            pady=6,
        )
        save_btn.pack(side="right", padx=(6, 0))

        cancel_btn = tk.Button(
            btn_row,
            text="CANCEL",
            command=dialog.destroy,
            bg="#2a2a2a",
            fg="#8dffaf",
            activebackground="#404040",
            activeforeground="#8dffaf",
            relief="flat",
            cursor="hand2",
            font=("Consolas", 10),
            padx=14,
            pady=6,
        )
        cancel_btn.pack(side="right")

    def edit_selected(self):
        selected = self.listbox.curselection()
        if not selected:
            return
        self._open_edit_dialog(selected[0])

    def delete_selected(self):
        selected = self.listbox.curselection()
        if not selected:
            return

        idx = selected[0]
        del self.entries[idx]
        self._save_entries()
        self._refresh_list()
        self.status_var.set(f"Deleted entry {idx + 1}.")

    def toggle_window(self):
        if self.root.state() == "withdrawn":
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after(300, lambda: self.root.attributes("-topmost", False))
            self.status_var.set("Visible. Left-click copies. Right-click edits.")
            self.root.focus_force()
        else:
            self.hide_window()

    def hide_window(self):
        self.root.withdraw()

    def _hotkey_listener(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        if not user32.RegisterHotKey(None, self.HOTKEY_ID, self.MOD_ALT, self.VK_C):
            self.root.after(0, lambda: self.status_var.set("Alt+C hotkey unavailable."))
            return

        self._hotkey_thread_id = kernel32.GetCurrentThreadId()
        msg = ctypes.wintypes.MSG()
        while not self._stop_hotkey.is_set():
            result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result == 0:
                break
            if msg.message == self.WM_HOTKEY and msg.wParam == self.HOTKEY_ID:
                self.root.after(0, self.toggle_window)
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        user32.UnregisterHotKey(None, self.HOTKEY_ID)

    def quit_app(self):
        self._stop_hotkey.set()
        if self._hotkey_thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._hotkey_thread_id, 0x0012, 0, 0)
        if self.mutex_handle:
            ctypes.windll.kernel32.CloseHandle(self.mutex_handle)
            self.mutex_handle = None
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\TSSClipboardSingleton")
    if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        ctypes.windll.user32.MessageBoxW(
            None,
            "TSS Clipboard is already running.\nPress Alt+C to show or hide it.",
            APP_NAME,
            0x40,
        )
        if mutex_handle:
            ctypes.windll.kernel32.CloseHandle(mutex_handle)
        raise SystemExit(0)

    app = ClipboardApp(mutex_handle)
    app.run()
