"""macOS: keys through CoreGraphics, media keys through NSEvent, the app in front through launch services.

No pyobjc: the frameworks are called through ctypes. Sending keys needs the Accessibility permission for the app
that runs the manager (Terminal, VS Code, D200X Manager.app).
"""
import ctypes
import os
import re
import subprocess

APP_DIR = '/Applications'
# the folders of the app picker: (folder, text key of its label or None for the folder itself)
APP_FOLDERS = [('/Applications', None), ('/System/Applications', None), ('/System/Applications/Utilities', None),
               ('~/Applications', None), ('/System/Library/CoreServices', 'app_dialog.finder_folder')]
SETTINGS_HINT = ('warning: type key needs Accessibility permission for this app '
                 '(System Settings > Privacy & Security > Accessibility)')
BROWSERS = {'safari': 'Safari', 'chrome': 'Google Chrome', 'firefox': 'Firefox', 'arc': 'Arc',
            'edge': 'Microsoft Edge', 'brave': 'Brave Browser'}
LINK = re.compile(r'[a-z][a-z0-9+.-]*://', re.I)

_AS = ctypes.cdll.LoadLibrary('/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices')
_AS.AXIsProcessTrusted.restype = ctypes.c_bool
_AS.CGEventCreateKeyboardEvent.restype = ctypes.c_void_p
_AS.CGEventCreateKeyboardEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool]
_AS.CGEventSetFlags.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
_AS.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
_AS.CFRelease.argtypes = [ctypes.c_void_p]
CG_HID_EVENT_TAP = 0

MODIFIERS = {
    'shift': 0x20000,
    'ctrl': 0x40000, 'control': 0x40000,
    'alt': 0x80000, 'option': 0x80000, 'opt': 0x80000,
    'cmd': 0x100000, 'command': 0x100000,
    'fn': 0x800000,
}
# macOS virtual key codes (ANSI layout positions).
KEY_CODES = {
    'a': 0, 's': 1, 'd': 2, 'f': 3, 'h': 4, 'g': 5, 'z': 6, 'x': 7, 'c': 8, 'v': 9,
    'b': 11, 'q': 12, 'w': 13, 'e': 14, 'r': 15, 'y': 16, 't': 17,
    '1': 18, '2': 19, '3': 20, '4': 21, '6': 22, '5': 23, '=': 24, '9': 25, '7': 26,
    '-': 27, '8': 28, '0': 29, ']': 30, 'o': 31, 'u': 32, '[': 33, 'i': 34, 'p': 35,
    'enter': 36, 'return': 36, 'l': 37, 'j': 38, "'": 39, 'k': 40, ';': 41, '\\': 42,
    ',': 43, '/': 44, 'n': 45, 'm': 46, '.': 47, 'tab': 48, 'space': 49, '`': 50,
    'backspace': 51, 'delete': 51, 'esc': 53, 'escape': 53,
    'f1': 122, 'f2': 120, 'f3': 99, 'f4': 118, 'f5': 96, 'f6': 97, 'f7': 98, 'f8': 100,
    'f9': 101, 'f10': 109, 'f11': 103, 'f12': 111,
    'home': 115, 'pageup': 116, 'forwarddelete': 117, 'end': 119, 'pagedown': 121,
    'left': 123, 'right': 124, 'down': 125, 'up': 126,
}
# Media keys (NX_KEYTYPE_*). These aren't key codes but system-defined events,
# the same ones the volume/media keys on a Mac keyboard send.
MEDIA_KEYS = {
    'volumeup': 0, 'volumedown': 1, 'mute': 7,
    'brightnessup': 2, 'brightnessdown': 3,
    'play': 16, 'next': 17, 'previous': 18,
}

# NSEvent is needed to build a system-defined event; call it through the
# Objective-C runtime so no pyobjc dependency is needed.
_OBJC = ctypes.cdll.LoadLibrary('/usr/lib/libobjc.A.dylib')
ctypes.cdll.LoadLibrary('/System/Library/Frameworks/AppKit.framework/AppKit')
_OBJC.objc_getClass.restype = ctypes.c_void_p
_OBJC.objc_getClass.argtypes = [ctypes.c_char_p]
_OBJC.sel_registerName.restype = ctypes.c_void_p
_OBJC.sel_registerName.argtypes = [ctypes.c_char_p]


class _NSPoint(ctypes.Structure):
    _fields_ = [('x', ctypes.c_double), ('y', ctypes.c_double)]


_MSG_SEND = ctypes.cast(_OBJC.objc_msgSend, ctypes.c_void_p).value
# +[NSEvent otherEventWithType:location:modifierFlags:timestamp:windowNumber:context:subtype:data1:data2:]
_ns_other_event = ctypes.CFUNCTYPE(
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, _NSPoint, ctypes.c_ulong,
    ctypes.c_double, ctypes.c_long, ctypes.c_void_p, ctypes.c_short, ctypes.c_long, ctypes.c_long)(_MSG_SEND)
_ns_cg_event = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(_MSG_SEND)
_NSEVENT = _OBJC.objc_getClass(b'NSEvent')
_SEL_OTHER_EVENT = _OBJC.sel_registerName(
    b'otherEventWithType:location:modifierFlags:timestamp:windowNumber:context:subtype:data1:data2:')
_SEL_CG_EVENT = _OBJC.sel_registerName(b'CGEvent')
NS_SYSTEM_DEFINED = 14
NS_SUBTYPE_AUX_CONTROL = 8
MEDIA_DOWN, MEDIA_UP = 0xa, 0xb


def flags(modifiers):
    result = 0
    for m in modifiers:
        result |= m
    return result


def can_send_keys():
    return _AS.AXIsProcessTrusted()


def _send_media_key(key):
    for state in (MEDIA_DOWN, MEDIA_UP):
        event = _ns_other_event(_NSEVENT, _SEL_OTHER_EVENT, NS_SYSTEM_DEFINED, _NSPoint(0, 0),
                                state << 8, 0.0, 0, None, NS_SUBTYPE_AUX_CONTROL,
                                (key << 16) | (state << 8), -1)
        _AS.CGEventPost(CG_HID_EVENT_TAP, _ns_cg_event(event, _SEL_CG_EVENT))


def send_keys(combos):
    for kind, code, mods in combos:
        if kind == 'media':
            _send_media_key(code)
            continue
        for down in (True, False):
            event = _AS.CGEventCreateKeyboardEvent(None, code, down)
            _AS.CGEventSetFlags(event, mods)
            _AS.CGEventPost(CG_HID_EVENT_TAP, event)
            _AS.CFRelease(event)


def frontmost_app():
    """(name, bundle path) of the frontmost app, or (None, None).

    NSWorkspace.frontmostApplication goes stale in a process without a Cocoa run loop,
    so ask launch services instead."""
    front = subprocess.run(['lsappinfo', 'front'], capture_output=True, text=True, timeout=2).stdout.strip()
    if not front:
        return None, None
    info = subprocess.run(['lsappinfo', 'info', front], capture_output=True, text=True, timeout=2).stdout
    name = re.match(r'\s*"(.*?)" ASN', info)
    path = re.search(r'bundle path="(.*?)"', info)
    return (name.group(1) if name else None), (os.path.normpath(path.group(1)) if path else None)


def clipboard(text=None):
    """The clipboard's text, or set it to text. pbcopy/pbpaste need a UTF-8 locale for anything beyond ASCII."""
    env = {**os.environ, 'LANG': 'en_US.UTF-8'}
    if text is None:
        return subprocess.run(['pbpaste'], capture_output=True, env=env, timeout=2).stdout.decode('utf-8', 'replace')
    subprocess.run(['pbcopy'], input=text.encode('utf-8'), env=env, timeout=2)


def is_app(path):
    """An app this Mac can open: an .app folder, or a link such as raycast://..."""
    return bool(path) and ((path.endswith('.app') and os.path.isdir(path)) or bool(LINK.match(path)))


def app_key(path):
    """How an app path is compared with the app in front (to find its profile)."""
    return os.path.normpath(path) if path else None


def open_app(path):
    subprocess.Popen(['open', path])


def open_url(url, browser=None):
    """Open a web page, in the default browser or a named one (a key of BROWSERS)."""
    app = BROWSERS.get(browser or '')
    subprocess.Popen(['open', '-a', app, url] if app else ['open', url])


def app_icon(path):
    """The app's icon as RGBA, or None."""
    from system.mac_icon import app_icon as icon
    return icon(path)


def list_apps(directory):
    """The apps in a folder for the app picker: [{'name', 'path'}]."""
    directory = os.path.expanduser(directory or APP_DIR)
    entries = [e for e in os.scandir(directory) if e.name.endswith('.app') and e.is_dir()]
    entries.sort(key=lambda e: e.name.lower())
    return {'dir': directory, 'apps': [{'name': e.name[:-4], 'path': e.path} for e in entries]}
