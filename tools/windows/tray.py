"""D200X Manager for Windows: an icon in the system tray that runs the manager (d200x_manager.py).

Started with pythonw.exe (no console window) by the Start menu shortcut that install.ps1 makes. Runs the manager
from this project folder with its .venv; the manager's output goes to %LOCALAPPDATA%\\D200X Manager\\manager.log.
When the manager stops (no deck connected, a config error), it is started again after a few seconds.
The menu is the same as the menu bar app on macOS (tools/macos-app); its texts are in lang/*.yaml under app_menu.
"""
import ctypes
import os
import subprocess
import sys
import threading
import time
import webbrowser
import winreg

import pystray
import yaml

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT, 'tools'))
from app_icon import draw  # noqa: E402

WEB_URL = 'http://127.0.0.1:8765'
PYTHON = os.path.join(PROJECT, '.venv', 'Scripts', 'python.exe')
LOG_DIR = os.path.join(os.environ.get('LOCALAPPDATA', PROJECT), 'D200X Manager')
LOG = os.path.join(LOG_DIR, 'manager.log')
RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
RUN_NAME = 'D200X Manager'
RESTART_DELAY = 10
NO_WINDOW = 0x08000000


def texts():
    """The menu texts in the manager's language ("ui: language:" in config.yaml)."""
    def section(code):
        try:
            with open(os.path.join(PROJECT, 'lang', f'{code}.yaml'), encoding='utf-8') as fp:
                return (yaml.safe_load(fp) or {}).get('app_menu') or {}
        except OSError:
            return {}
    try:
        with open(os.path.join(PROJECT, 'config.yaml'), encoding='utf-8') as fp:
            language = ((yaml.safe_load(fp) or {}).get('ui') or {}).get('language') or 'en'
    except (OSError, yaml.YAMLError):
        language = 'en'
    return {**section('en'), **section(language)}


def log(text):
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(LOG, 'a', encoding='utf-8') as fp:
        fp.write(text)


class Tray:
    def __init__(self):
        self.t = texts()
        self.process = None
        self.quitting = False
        self.lock = threading.Lock()
        self.icon = pystray.Icon('D200X Manager', draw().resize((64, 64)), 'D200X Manager', menu=pystray.Menu(
            pystray.MenuItem(lambda item: self.t['running' if self.running() else 'stopped'], None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self.t['open'], self.open_web, default=True),     # also a click on the icon
            pystray.MenuItem(self.t['restart'], self.restart),
            pystray.MenuItem(self.t['log'], lambda: os.startfile(LOG) if os.path.exists(LOG) else None),
            pystray.MenuItem(self.t['folder'], lambda: os.startfile(PROJECT)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self.t['login'], self.toggle_login, checked=lambda item: self.starts_at_login()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self.t['quit'], self.quit),
        ))

    # --- the manager process
    def running(self):
        return self.process is not None and self.process.poll() is None

    def supervise(self):
        while not self.quitting:
            with self.lock:
                if not self.running():
                    self.start()
            process = self.process
            if process:
                code = process.wait()
                log(f'=== {time.strftime("%Y-%m-%d %H:%M:%S")} stopped (exit {code}) ===\n')
            for _ in range(RESTART_DELAY * 10):
                if self.quitting or self.running():
                    break
                time.sleep(0.1)

    def start(self):
        if not os.path.exists(PYTHON):
            log(f'D200X Manager: no Python at {PYTHON}; run tools\\windows\\install.ps1 first.\n')
            self.process = None
            return
        log(f'\n=== {time.strftime("%Y-%m-%d %H:%M:%S")} start ===\n')
        output = open(LOG, 'a', encoding='utf-8')
        env = {**os.environ, 'PYTHONUNBUFFERED': '1', 'PYTHONUTF8': '1'}
        self.process = subprocess.Popen([PYTHON, '-X', 'utf8', 'd200x_manager.py'], cwd=PROJECT, env=env,
                                        stdout=output, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
        output.close()

    def stop(self):
        with self.lock:
            process, self.process = self.process, None
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(5)
                except subprocess.TimeoutExpired:
                    process.kill()

    # --- menu actions
    def open_web(self):
        webbrowser.open(WEB_URL)

    def restart(self):
        self.stop()          # supervise() starts it again
        with self.lock:
            self.start()

    def starts_at_login(self):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                winreg.QueryValueEx(key, RUN_NAME)
                return True
        except OSError:
            return False

    def toggle_login(self):
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if self.starts_at_login():
                winreg.DeleteValue(key, RUN_NAME)
            else:
                pythonw = os.path.join(os.path.dirname(PYTHON), 'pythonw.exe')
                winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, subprocess.list2cmdline([pythonw, os.path.abspath(__file__)]))

    def quit(self):
        self.quitting = True
        self.stop()
        self.icon.stop()

    def run(self):
        threading.Thread(target=self.supervise, daemon=True).start()
        self.icon.run()


def main():
    # one tray icon: a second start opens the web interface instead
    ctypes.windll.kernel32.CreateMutexW(None, False, 'D200X-Manager-tray')
    if ctypes.windll.kernel32.GetLastError() == 183:      # ERROR_ALREADY_EXISTS
        webbrowser.open(WEB_URL)
        return
    Tray().run()


if __name__ == '__main__':
    main()
