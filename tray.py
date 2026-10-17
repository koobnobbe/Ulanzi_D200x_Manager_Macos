"""The icon in the menu bar (macOS) or system tray (Windows). It runs the manager as a second process of the same
program (main.py --manager), writes its output to the log and starts it again when it stops.

A manager that exits with RESTART (after the config folder changed) is started again at once; after anything
else (no deck connected, a config error) after RESTART_DELAY seconds. The menu texts are in lang/*.yaml under
app_menu, in the language of config.yaml.
"""
import os
import plistlib
import subprocess
import sys
import threading
import time
import webbrowser

import pystray
import yaml

import paths
from app_logo import draw

WEB_URL = 'http://127.0.0.1:8765'
RESTART = 3             # exit code of the manager: start me again now
RESTART_DELAY = 10
NO_WINDOW = 0x08000000  # Windows: no console window for the manager
LAUNCH_AGENT = os.path.expanduser('~/Library/LaunchAgents/com.koobnobbe.d200x-manager.plist')
RUN_KEY, RUN_NAME = r'Software\Microsoft\Windows\CurrentVersion\Run', paths.NAME


def manager_command():
    if paths.FROZEN:
        return [sys.executable, '--manager']
    return [sys.executable, os.path.join(paths.SOURCE, 'main.py'), '--manager']


def own_command():
    """How to start this program, for "Open at login"."""
    if paths.FROZEN:
        return [sys.executable]
    return [sys.executable, os.path.join(paths.SOURCE, 'main.py')]


def texts():
    """The menu texts in the manager's language ("ui: language:" in config.yaml)."""
    def section(code):
        for folder in (paths.config('lang'), os.path.join(paths.DEFAULTS, 'lang')):
            try:
                with open(os.path.join(folder, f'{code}.yaml'), encoding='utf-8') as fp:
                    return (yaml.safe_load(fp) or {}).get('app_menu') or {}
            except OSError:
                continue
        return {}
    try:
        with open(paths.config('config.yaml'), encoding='utf-8') as fp:
            language = ((yaml.safe_load(fp) or {}).get('ui') or {}).get('language') or 'en'
    except (OSError, yaml.YAMLError):
        language = 'en'
    return {**section('en'), **section(language)}


def log(text):
    os.makedirs(os.path.dirname(paths.LOG_FILE), exist_ok=True)
    with open(paths.LOG_FILE, 'a', encoding='utf-8') as fp:
        fp.write(text)


def open_file(path):
    if sys.platform == 'win32':
        os.startfile(path)
    else:
        subprocess.Popen(['open', path])


# --- open at login: a LaunchAgent on macOS, the Run key on Windows
def starts_at_login():
    if sys.platform == 'darwin':
        return os.path.exists(LAUNCH_AGENT)
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, RUN_NAME)
            return True
    except OSError:
        return False


def set_start_at_login(on):
    if sys.platform == 'darwin':
        if on:
            os.makedirs(os.path.dirname(LAUNCH_AGENT), exist_ok=True)
            with open(LAUNCH_AGENT, 'wb') as fp:
                plistlib.dump({'Label': 'com.koobnobbe.d200x-manager', 'ProgramArguments': own_command(),
                               'RunAtLoad': True}, fp)
        elif os.path.exists(LAUNCH_AGENT):
            os.remove(LAUNCH_AGENT)
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if on:
            winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, subprocess.list2cmdline(own_command()))
        else:
            try:
                winreg.DeleteValue(key, RUN_NAME)
            except OSError:
                pass


class Tray:
    def __init__(self):
        self.t = texts()
        self.process = None
        self.quitting = False
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.icon = pystray.Icon(paths.NAME, draw().resize((64, 64)), paths.NAME, menu=pystray.Menu(
            pystray.MenuItem(lambda item: self.t['running' if self.running() else 'stopped'], None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self.t['open'], self.open_web, default=True),     # Windows: also a click on the icon
            pystray.MenuItem(self.t['restart'], self.restart),
            pystray.MenuItem(self.t['log'], lambda: open_file(paths.LOG_FILE) if os.path.exists(paths.LOG_FILE) else None),
            pystray.MenuItem(self.t['folder'], lambda: open_file(paths.CONFIG_DIR)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self.t['login'], lambda: set_start_at_login(not starts_at_login()),
                             checked=lambda item: starts_at_login()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self.t['quit'], self.quit),
        ))

    # --- the manager process
    def running(self):
        return self.process is not None and self.process.poll() is None

    def start(self):
        log(f'\n=== {time.strftime("%Y-%m-%d %H:%M:%S")} start ({paths.CONFIG_DIR}) ===\n')
        output = open(paths.LOG_FILE, 'a', encoding='utf-8')
        env = {**os.environ, 'PYTHONUNBUFFERED': '1', 'PYTHONUTF8': '1'}
        self.process = subprocess.Popen(manager_command(), env=env, stdout=output, stderr=subprocess.STDOUT,
                                        creationflags=NO_WINDOW if sys.platform == 'win32' else 0)
        output.close()

    def supervise(self):
        while not self.quitting:
            with self.lock:
                if not self.running():
                    self.start()
                process = self.process
            code = process.wait()
            log(f'=== {time.strftime("%Y-%m-%d %H:%M:%S")} stopped (exit {code}) ===\n')
            if code == RESTART or self.quitting:
                continue
            self.wake.wait(RESTART_DELAY)
            self.wake.clear()

    def stop(self):
        with self.lock:
            process = self.process
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
        self.stop()
        self.wake.set()      # don't wait RESTART_DELAY

    def quit(self):
        self.quitting = True
        self.stop()
        self.wake.set()
        self.icon.stop()

    def run(self):
        threading.Thread(target=self.supervise, daemon=True).start()
        self.icon.run()


def already_running():
    """Is another tray of this program running? Then this start opens the web interface instead."""
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.kernel32.CreateMutexW(None, False, 'D200X-Manager-tray')
        return ctypes.windll.kernel32.GetLastError() == 183      # ERROR_ALREADY_EXISTS
    import fcntl
    global _lock_file
    os.makedirs(paths.WORK_DIR, exist_ok=True)
    _lock_file = open(os.path.join(paths.WORK_DIR, 'tray.lock'), 'w')
    try:
        fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return False
    except OSError:
        return True


def main():
    if already_running():
        webbrowser.open(WEB_URL)
        return
    paths.seed()     # a new config folder is filled before the menu reads its texts
    Tray().run()
