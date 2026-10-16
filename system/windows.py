"""Windows: keys through SendInput, the app in front through its window, icons from the .exe. All through ctypes.

Apps are .exe files or Start menu shortcuts (.lnk); the app picker lists the Start menu. "cmd" in a key combo is
Ctrl here, so a shared config's cmd+c copies on both systems; the Windows key is "win".
Screen brightness has no key on Windows; brightnessup/down set it through WMI (laptop screens).
"""
import ctypes
import os
import re
import subprocess
from ctypes import wintypes

from PIL import Image

APP_DIR = '%Start menu%'      # the picker's "folder": the Start menu of this user and of all users
APP_FOLDERS = [(APP_DIR, 'app_dialog.start_menu'), ('%ProgramFiles%', None), ('%ProgramFiles(x86)%', None),
               ('%LOCALAPPDATA%\\Programs', None)]
SETTINGS_HINT = ''
LINK = re.compile(r'[a-z][a-z0-9+.-]*://', re.I)
NO_WINDOW = 0x08000000        # CREATE_NO_WINDOW: no console flashing up for powershell
BROWSERS = {'chrome': 'chrome.exe', 'firefox': 'firefox.exe', 'edge': 'msedge.exe', 'brave': 'brave.exe'}

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)
shell32 = ctypes.WinDLL('shell32', use_last_error=True)

# --- keys
VK_SHIFT, VK_CONTROL, VK_MENU, VK_LWIN = 0x10, 0x11, 0x12, 0x5B
MODIFIERS = {
    'shift': VK_SHIFT,
    'ctrl': VK_CONTROL, 'control': VK_CONTROL, 'cmd': VK_CONTROL, 'command': VK_CONTROL,
    'alt': VK_MENU, 'option': VK_MENU, 'opt': VK_MENU,
    'win': VK_LWIN, 'windows': VK_LWIN,
}
KEY_CODES = {
    **{chr(c): c - 32 for c in range(ord('a'), ord('z') + 1)},     # 'a' -> 0x41
    **{str(d): 0x30 + d for d in range(10)},
    ';': 0xBA, '=': 0xBB, ',': 0xBC, '-': 0xBD, '.': 0xBE, '/': 0xBF, '`': 0xC0,
    '[': 0xDB, '\\': 0xDC, ']': 0xDD, "'": 0xDE,
    'enter': 0x0D, 'return': 0x0D, 'tab': 0x09, 'space': 0x20,
    'backspace': 0x08, 'delete': 0x08, 'forwarddelete': 0x2E, 'esc': 0x1B, 'escape': 0x1B,
    **{f'f{n}': 0x6F + n for n in range(1, 13)},
    'home': 0x24, 'end': 0x23, 'pageup': 0x21, 'pagedown': 0x22,
    'left': 0x25, 'up': 0x26, 'right': 0x27, 'down': 0x28,
    'insert': 0x2D, 'printscreen': 0x2C,
}
MEDIA_KEYS = {
    'volumeup': 0xAF, 'volumedown': 0xAE, 'mute': 0xAD,
    'play': 0xB3, 'next': 0xB0, 'previous': 0xB1,
    'brightnessup': 'brightness+', 'brightnessdown': 'brightness-',
}
# keys that are "extended" (they are on the separate key blocks); SendInput needs the flag for them
EXTENDED = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2C, 0x2D, 0x2E, 0x5B,
            0xAD, 0xAE, 0xAF, 0xB0, 0xB1, 0xB3}
KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP = 0x1, 0x2
INPUT_KEYBOARD = 1
ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD), ('dwFlags', wintypes.DWORD),
                ('time', wintypes.DWORD), ('dwExtraInfo', ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):   # only here so the union has the size Windows expects
    _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG), ('mouseData', wintypes.DWORD),
                ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD), ('dwExtraInfo', ULONG_PTR)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [('ki', KEYBDINPUT), ('mi', MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [('type', wintypes.DWORD), ('u', _INPUTUNION)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]


def flags(modifiers):
    return tuple(modifiers)


def can_send_keys():
    return True


def _key(vk, up):
    scan = user32.MapVirtualKeyW(vk, 0)
    dw = (KEYEVENTF_EXTENDEDKEY if vk in EXTENDED else 0) | (KEYEVENTF_KEYUP if up else 0)
    return INPUT(type=INPUT_KEYBOARD, u=_INPUTUNION(ki=KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=dw)))


def _send(events):
    array = (INPUT * len(events))(*events)
    user32.SendInput(len(events), array, ctypes.sizeof(INPUT))


def send_keys(combos):
    for kind, code, mods in combos:
        if kind == 'media':
            if isinstance(code, str):
                _brightness(10 if code.endswith('+') else -10)
            else:
                _send([_key(code, False), _key(code, True)])
            continue
        # modifiers down, the key down and up, modifiers up (in reverse)
        _send([_key(m, False) for m in mods] + [_key(code, False), _key(code, True)]
              + [_key(m, True) for m in reversed(mods)])


def _brightness(step):
    script = ('$b = (Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).CurrentBrightness; '
              f'$n = [Math]::Max(0, [Math]::Min(100, $b + ({step}))); '
              'Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods | '
              'Invoke-CimMethod -MethodName WmiSetBrightness -Arguments @{Timeout=0; Brightness=[byte]$n}')
    subprocess.Popen(['powershell', '-NoProfile', '-NonInteractive', '-Command', script], creationflags=NO_WINDOW)


# --- the app in front
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                ctypes.POINTER(wintypes.DWORD)]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


def frontmost_app():
    """(name, path of the .exe) of the app whose window is in front, or (None, None)."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None, None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return None, None
    try:
        size = wintypes.DWORD(1024)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return None, None
        path = buffer.value
    finally:
        kernel32.CloseHandle(handle)
    return os.path.splitext(os.path.basename(path))[0], os.path.normpath(path)


# --- clipboard
CF_UNICODETEXT, GMEM_MOVEABLE = 13, 0x0002
user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.GetClipboardData.restype = wintypes.HANDLE
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.SetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]


def _open_clipboard():
    # another app may hold it for a moment
    import time
    for _ in range(20):
        if user32.OpenClipboard(None):
            return
        time.sleep(0.02)
    raise OSError('clipboard is in use')


def clipboard(text=None):
    """The clipboard's text, or set it to text."""
    _open_clipboard()
    try:
        if text is None:
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return ''
            pointer = kernel32.GlobalLock(handle)
            try:
                return ctypes.wstring_at(pointer)
            finally:
                kernel32.GlobalUnlock(handle)
        data = ctypes.create_unicode_buffer(text)
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, ctypes.sizeof(data))
        pointer = kernel32.GlobalLock(handle)
        ctypes.memmove(pointer, data, ctypes.sizeof(data))
        kernel32.GlobalUnlock(handle)
        user32.EmptyClipboard()
        user32.SetClipboardData(CF_UNICODETEXT, handle)    # the clipboard owns the memory now
    finally:
        user32.CloseClipboard()


# --- apps
_targets = {}


def _shortcut_target(path):
    """The program a Start menu shortcut (.lnk) starts, through Windows Script Host. Cached."""
    if path not in _targets:
        script = f"(New-Object -ComObject WScript.Shell).CreateShortcut('{path.replace(chr(39), chr(39) * 2)}').TargetPath"
        try:
            result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script],
                                    capture_output=True, text=True, timeout=10, creationflags=NO_WINDOW)
            _targets[path] = result.stdout.strip() or None
        except (OSError, subprocess.TimeoutExpired):
            _targets[path] = None
    return _targets[path]


def is_app(path):
    """An app this PC can open: an .exe or .lnk file, or a link such as spotify://..."""
    if not path:
        return False
    if LINK.match(path) and not re.match(r'[a-z]:[\\/]', path, re.I):
        return True
    return path.lower().endswith(('.exe', '.lnk')) and os.path.isfile(path)


def app_key(path):
    """How an app path is compared with the app in front: the .exe it starts, in one spelling."""
    if not path:
        return None
    if path.lower().endswith('.lnk'):
        path = _shortcut_target(path) or path
    return os.path.normcase(os.path.normpath(path))


def open_app(path):
    os.startfile(path)


def open_url(url, browser=None):
    exe = BROWSERS.get(browser or '')
    if exe:
        # "start" finds browsers through App Paths in the registry, also when they are not on PATH
        subprocess.Popen(['cmd', '/c', 'start', '', exe, url], creationflags=NO_WINDOW)
    else:
        os.startfile(url)


def _start_menus():
    return [os.path.join(os.environ.get(root, ''), 'Microsoft', 'Windows', 'Start Menu', 'Programs')
            for root in ('APPDATA', 'PROGRAMDATA') if os.environ.get(root)]


def list_apps(directory):
    """The apps for the app picker: the Start menu's shortcuts (APP_DIR), or the .exe and .lnk files in a folder."""
    found = {}
    if directory in ('', APP_DIR):
        for root in _start_menus():
            for folder, _, files in os.walk(root):
                for name in files:
                    stem, ext = os.path.splitext(name)
                    if ext.lower() == '.lnk' and not re.search(r'uninstall|verwijder|deinstall|readme|help', stem, re.I):
                        found.setdefault(stem.lower(), {'name': stem, 'path': os.path.join(folder, name)})
    else:
        folder = os.path.expandvars(os.path.expanduser(directory))
        # programs live one or two folders down: Program Files\Vendor\App\app.exe
        for root, dirs, files in os.walk(folder):
            if root[len(folder):].count(os.sep) >= 2:
                dirs.clear()
            for name in files:
                stem, ext = os.path.splitext(name)
                if ext.lower() == '.exe' and not re.search(r'unins|setup|update|crash|helper|install', stem, re.I):
                    found.setdefault(stem.lower(), {'name': stem, 'path': os.path.join(root, name)})
    apps = sorted(found.values(), key=lambda a: a['name'].lower())
    return {'dir': directory or APP_DIR, 'apps': apps}


# --- app icons
class ICONINFO(ctypes.Structure):
    _fields_ = [('fIcon', wintypes.BOOL), ('xHotspot', wintypes.DWORD), ('yHotspot', wintypes.DWORD),
                ('hbmMask', wintypes.HBITMAP), ('hbmColor', wintypes.HBITMAP)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG), ('biHeight', wintypes.LONG),
                ('biPlanes', wintypes.WORD), ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', wintypes.LONG),
                ('biYPelsPerMeter', wintypes.LONG), ('biClrUsed', wintypes.DWORD), ('biClrImportant', wintypes.DWORD)]


class BITMAP(ctypes.Structure):
    _fields_ = [('bmType', wintypes.LONG), ('bmWidth', wintypes.LONG), ('bmHeight', wintypes.LONG),
                ('bmWidthBytes', wintypes.LONG), ('bmPlanes', wintypes.WORD), ('bmBitsPixel', wintypes.WORD),
                ('bmBits', ctypes.c_void_p)]


user32.PrivateExtractIconsW.argtypes = [wintypes.LPCWSTR, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                        ctypes.POINTER(wintypes.HICON), ctypes.POINTER(wintypes.UINT),
                                        wintypes.UINT, wintypes.UINT]
user32.GetIconInfo.argtypes = [wintypes.HICON, ctypes.POINTER(ICONINFO)]
user32.DestroyIcon.argtypes = [wintypes.HICON]
user32.GetDC.restype = wintypes.HDC
user32.GetDC.argtypes = [wintypes.HWND]
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
gdi32.GetObjectW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p]
gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT, ctypes.c_void_p,
                            ctypes.c_void_p, wintypes.UINT]
gdi32.DeleteObject.argtypes = [wintypes.HANDLE]


def _bitmap_pixels(hdc, hbitmap, width, height):
    header = BITMAPINFOHEADER(biSize=ctypes.sizeof(BITMAPINFOHEADER), biWidth=width, biHeight=-height,  # top-down
                              biPlanes=1, biBitCount=32, biCompression=0)
    buffer = ctypes.create_string_buffer(width * height * 4)
    if not gdi32.GetDIBits(hdc, hbitmap, 0, height, buffer, ctypes.byref(header), 0):
        return None
    return buffer.raw


def app_icon(path, size=256):
    """The icon of an .exe or .lnk (of the program it starts) as RGBA, or None."""
    if not path or not os.path.isfile(path):
        return None
    source = _shortcut_target(path) if path.lower().endswith('.lnk') else path
    if not source or not os.path.isfile(source):
        source = path        # a shortcut to something else: its own icon
    hicon = wintypes.HICON()
    count = user32.PrivateExtractIconsW(source, 0, size, size, ctypes.byref(hicon), None, 1, 0)
    if count < 1 or not hicon:
        return None
    info = ICONINFO()
    hdc = user32.GetDC(None)
    try:
        if not user32.GetIconInfo(hicon, ctypes.byref(info)) or not info.hbmColor:
            return None
        bm = BITMAP()
        gdi32.GetObjectW(info.hbmColor, ctypes.sizeof(BITMAP), ctypes.byref(bm))
        width, height = bm.bmWidth, bm.bmHeight
        color = _bitmap_pixels(hdc, info.hbmColor, width, height)
        if color is None:
            return None
        image = Image.frombuffer('RGBA', (width, height), color, 'raw', 'BGRA', 0, 1)
        if not any(color[3::4]):
            # an old-style icon without alpha: take the transparency from its mask
            mask = _bitmap_pixels(hdc, info.hbmMask, width, height)
            if mask is not None:
                alpha = Image.frombuffer('RGBA', (width, height), mask, 'raw', 'BGRA', 0, 1).convert('L')
                image.putalpha(alpha.point(lambda v: 0 if v else 255))
        return image.copy()
    finally:
        if info.hbmColor:
            gdi32.DeleteObject(info.hbmColor)
        if info.hbmMask:
            gdi32.DeleteObject(info.hbmMask)
        user32.ReleaseDC(None, hdc)
        user32.DestroyIcon(hicon)
