import tkinter as tk

from PIL import Image
from screeninfo import get_monitors
from pystray import Icon, Menu, MenuItem
import sys
import threading
import ctypes
import os

def get_icon_path():
    # When packaged with PyInstaller, use the temporary resource directory
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, "icon.ico")

class MonitorBlocker:
    def __init__(self, monitor):
        self.monitor = monitor
        self.root = None
        self.is_active = False
        self.left_pressed = False
        self.right_pressed = False
        self.timer = None

    def show(self, root):
        if self.is_active:
            return
        self.root = tk.Toplevel(root)
        self.root.attributes('-topmost', True)
        self.root.overrideredirect(True)
        self.root.geometry(f"{self.monitor.width}x{self.monitor.height}+{self.monitor.x}+{self.monitor.y}")
        self.root.configure(bg='black')
        self.root.attributes("-alpha", 0.25)

        # Prevent window from appearing in taskbar
        hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
        style |= 0x80  # WS_EX_TOOLWINDOW
        ctypes.windll.user32.SetWindowLongW(hwnd, -20, style)

        canvas = tk.Canvas(self.root, bg='black', highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        width, height = self.monitor.width, self.monitor.height
        for i in range(-height, width + height, 100):
            canvas.create_line(i, 0, i + height, height, fill="#666", width=4)

        # Bind mouse events for hold-to-unlock
        canvas.bind("<Button-1>", self.on_left_press)
        canvas.bind("<Button-3>", self.on_right_press)
        canvas.bind("<ButtonRelease-1>", self.on_left_release)
        canvas.bind("<ButtonRelease-3>", self.on_right_release)
        self.canvas = canvas

        self.is_active = True
        self.root.update()

    def hide(self):
        if self.root:
            self.root.destroy()
            self.root = None
            self.is_active = False
            if self.timer:
                self.timer.cancel()
                self.timer = None
            self.left_pressed = False
            self.right_pressed = False

    def toggle(self, root):
        if self.is_active:
            self.hide()
        else:
            self.show(root)

    def on_left_press(self, event):
        self.left_pressed = True
        self.check_both_pressed()

    def on_right_press(self, event):
        self.right_pressed = True
        self.check_both_pressed()

    def on_left_release(self, event):
        self.left_pressed = False
        self.cancel_timer()

    def on_right_release(self, event):
        self.right_pressed = False
        self.cancel_timer()

    def check_both_pressed(self):
        if self.left_pressed and self.right_pressed and self.is_active:
            self.canvas.configure(bg="#000066")
            self.timer = threading.Timer(3.0, self.unlock_if_held)
            self.timer.start()

    def cancel_timer(self):
        if self.timer:
            self.timer.cancel()
            self.timer = None
        if self.is_active:
            self.canvas.configure(bg="black")

    def unlock_if_held(self):
        if self.left_pressed and self.right_pressed and self.is_active:
            self.hide()

class ScreenBlockApp:
    def __init__(self):
        # Check for existing instance using a mutex
        mutex_name = "ScreenBlockAppMutex"
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
        last_error = ctypes.windll.kernel32.GetLastError()
        if last_error == 183:  # ERROR_ALREADY_EXISTS
            sys.exit(0)

        self.monitors = get_monitors()
        self.blockers = [MonitorBlocker(m) for m in self.monitors]
        self.tk_root = tk.Tk()
        self.tk_root.withdraw()

        try:
            self.icon = Icon("ScreenBlock", icon=Image.open(get_icon_path()))
        except FileNotFoundError:
            self.icon = Icon("ScreenBlock")  # Fallback to no icon
        self.icon.menu = self.create_menu()

    def create_menu(self):
        lock_screen_menu = Menu(*[
            MenuItem(
                f"Toggle {(self.monitors[i].name or f'Monitor {i+1}').replace('\\.\\', '')} ({self.monitors[i].width}x{self.monitors[i].height})",
                self.make_toggle_callback(i)
            ) for i in range(len(self.monitors))
        ])

        return Menu(
            MenuItem("Lock Screen", lock_screen_menu),
            MenuItem("Lock All", self.lock_all),
            MenuItem("Unlock All", self.unlock_all),
            MenuItem("Quit", self.quit)
        )

    def make_toggle_callback(self, index):
        def callback(icon, item):
            self.blockers[index].toggle(self.tk_root)
        return callback

    def lock_all(self, icon=None, item=None):
        for blocker in self.blockers:
            blocker.show(self.tk_root)

    def unlock_all(self, icon=None, item=None):
        for blocker in self.blockers:
            blocker.hide()

    def quit(self, icon=None, item=None):
        for blocker in self.blockers:
            blocker.hide()
        self.icon.stop()
        self.tk_root.destroy()
        sys.exit(0)
        os._exit(0)  # Force process termination as a fallback

    def run(self):
        # Run pystray in a separate thread to avoid blocking Tkinter's mainloop
        threading.Thread(target=self.icon.run, daemon=True).start()
        self.tk_root.mainloop()

if __name__ == "__main__":
    app = ScreenBlockApp()
    app.run()