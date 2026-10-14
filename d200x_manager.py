import asyncio
import binascii
import ctypes
import hashlib
import io
import os
import plistlib
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from functools import partial
from PIL import Image, ImageDraw, ImageFont
import hid
import yaml
from strmdck.device import ButtonAction
from strmdck.devices.ulanzi_d200 import UlanziD200Device
import web_server

ICON_DIR = os.path.join('.cache', 'icons', '_generated')
SIZE = UlanziD200Device.ICON_WIDTH  # 196x196
CONFIG_PATH = 'config.yaml'
APP_TITLE_SIZE = 28  # title under an app icon
WEB_PORT = 8765
LONG_PRESS = 0.6  # seconds a key with a "hold" action must be held
# Keys 14, 16 and 17 send presses but have no screen (14 is the clock slot, 16 and 17 are next to the knobs).
INPUT_ONLY_KEYS = (14, 16, 17)
CLOCK_KEY = 14  # first clock slot; the clock window covers slots 13 and 14
SMALL_WINDOW_CLOCK = 1
SMALL_WINDOW_BACKGROUND = 2
KEY_NUMBERS = set(range(1, UlanziD200Device.BUTTON_COUNT + 1)) | set(INPUT_ONLY_KEYS)

IN_BUTTON = b'\x01\x01'
KIND_BUTTON = 0x01
KIND_KNOB = 0x02
# Value byte of a knob event -> config field. 0x00 (release) is ignored;
# anything else is printed raw.
KNOB_RELEASE = 0x00
KNOB_EVENTS = {0x01: 'press', 0x02: 'left', 0x03: 'right'}


# Keyboard events via CoreGraphics (no extra dependency). Sending them needs the
# Accessibility permission for the app running this script (Terminal, VS Code, ...).
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

_NS_WORKSPACE = _OBJC.objc_getClass(b'NSWorkspace')
_SEL_SHARED_WORKSPACE = _OBJC.sel_registerName(b'sharedWorkspace')
_SEL_FRONTMOST = _OBJC.sel_registerName(b'frontmostApplication')
_SEL_LOCALIZED_NAME = _OBJC.sel_registerName(b'localizedName')
_SEL_UTF8 = _OBJC.sel_registerName(b'UTF8String')
_ns_object = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(_MSG_SEND)
_ns_cstring = ctypes.CFUNCTYPE(ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p)(_MSG_SEND)


def frontmost_app_name():
    app = _ns_object(_ns_object(_NS_WORKSPACE, _SEL_SHARED_WORKSPACE), _SEL_FRONTMOST)
    if not app:
        return None
    return _ns_cstring(_ns_object(app, _SEL_LOCALIZED_NAME), _SEL_UTF8).decode()


def parse_keys(keys):
    """Parse "cmd+c", "volumeup" (or a list of those) into [(kind, code, flags), ...]."""
    combos = []
    for combo in [keys] if isinstance(keys, str) else keys:
        *mods, key = [part.strip().lower() for part in str(combo).split('+')]
        if key in MEDIA_KEYS and not mods:
            combos.append(('media', MEDIA_KEYS[key], 0))
            continue
        if key not in KEY_CODES or any(m not in MODIFIERS for m in mods):
            raise ValueError(f'unknown key combo: {combo}')
        flags = 0
        for m in mods:
            flags |= MODIFIERS[m]
        combos.append(('key', KEY_CODES[key], flags))
    return combos


def send_media_key(key):
    for state in (MEDIA_DOWN, MEDIA_UP):
        event = _ns_other_event(_NSEVENT, _SEL_OTHER_EVENT, NS_SYSTEM_DEFINED, _NSPoint(0, 0),
                                state << 8, 0.0, 0, None, NS_SUBTYPE_AUX_CONTROL,
                                (key << 16) | (state << 8), -1)
        _AS.CGEventPost(CG_HID_EVENT_TAP, _ns_cg_event(event, _SEL_CG_EVENT))


def send_keys(combos):
    for kind, code, flags in combos:
        if kind == 'media':
            send_media_key(code)
            continue
        for down in (True, False):
            event = _AS.CGEventCreateKeyboardEvent(None, code, down)
            _AS.CGEventSetFlags(event, flags)
            _AS.CGEventPost(CG_HID_EVENT_TAP, event)
            _AS.CFRelease(event)


def parse_knob(name, knob):
    """For a knob with type key, parse its left/right/press combos into knob['combos']."""
    kind = knob.get('type', 'text')
    if kind == 'key':
        try:
            knob['combos'] = {e: parse_keys(knob[e]) for e in KNOB_EVENTS.values() if knob.get(e)}
        except ValueError as e:
            raise ValueError(f'knob {name}: {e}')
    elif kind not in ('text', 'device_brightness'):
        raise ValueError(f'knob {name}: unknown type: {kind}')
    return knob


@dataclass
class KnobAction:
    index: int
    value: int


class Deck(UlanziD200Device):
    # strmdck's ButtonPressedStruct requires byte 2 to be 0x01, so knob events
    # (0x02) fail to parse. Parse the button/knob payload ourselves.
    def _parse_input(self, inp):
        raw = bytes(inp)
        if raw[2:4] != IN_BUTTON:
            return super()._parse_input(inp)
        state, index, kind, value = raw[8:12]
        if kind == KIND_BUTTON:
            return ButtonAction(index=index, pressed=value == 0x01, state=state)
        if kind == KIND_KNOB:
            return KnobAction(index=index, value=value)
        print('unknown event', binascii.hexlify(raw[:16]).decode())
        return None


def connect():
    # auto_connect() opens by VID/PID, which on macOS can hit the keyboard
    # interface (usage page 0x1, usage 0x6) that the OS won't let us open.
    for d in hid.enumerate(UlanziD200Device.USB_VENDOR_ID, UlanziD200Device.USB_PRODUCT_ID):
        if (d['usage_page'], d['usage']) == (0x1, 0x6):
            continue
        try:
            dev = hid.device()
            dev.open_path(d['path'])
            dev.set_nonblocking(True)
            return Deck(dev)
        except OSError:
            continue
    return None


def load_font(size):
    try:
        return ImageFont.load_default(size=size)  # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


def load_config(path):
    with open(path) as fp:
        return yaml.safe_load(fp)


def save_icon(img, prefix):
    # The deck caches icons by file name, so a changed image under the same name
    # keeps showing the old one. Put a hash of the content in the name.
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    data = buf.getvalue()
    name = f'{prefix}_{hashlib.sha1(data).hexdigest()[:10]}.png'
    with open(os.path.join(ICON_DIR, name), 'wb') as fp:
        fp.write(data)
    return name


def clear_icons():
    os.makedirs(ICON_DIR, exist_ok=True)
    for name in os.listdir(ICON_DIR):
        if name.endswith('.png'):
            os.remove(os.path.join(ICON_DIR, name))


def render_solid(color):
    return save_icon(Image.new('RGB', (SIZE, SIZE), color=color), 'solid')


def load_app_icon(app):
    """Return the .app bundle's icon as an RGBA image, or None if it has no .icns."""
    with open(os.path.join(app, 'Contents', 'Info.plist'), 'rb') as fp:
        icon = plistlib.load(fp).get('CFBundleIconFile')
    if not icon:
        return None
    if not icon.endswith('.icns'):
        icon += '.icns'
    path = os.path.join(app, 'Contents', 'Resources', icon)
    if not os.path.exists(path):
        return None
    return Image.open(path).convert('RGBA')  # Pillow loads the largest size in the .icns


def draw_title(img, button, center):
    draw = ImageDraw.Draw(img)
    draw.text(center, str(button.get('title', '')),
              font=load_font(button['font_size']), fill=button['color'], anchor='mm')


def check_button(number, button):
    kind = button.get('type', 'text')
    if kind == 'app':
        app = button.get('app')
        if not app or not os.path.isdir(app):
            raise ValueError(f'key {number}: app not found: {app}')
    elif kind == 'key':
        try:
            button['combos'] = parse_keys(button.get('keys') or [])
        except ValueError as e:
            raise ValueError(f'key {number}: {e}')
        if not button['combos']:
            raise ValueError(f'key {number}: type key needs "keys"')
    elif kind not in ('text', 'page', 'profile'):
        raise ValueError(f'key {number}: unknown type: {kind}')

def render_button(number, button):
    check_button(number, button)
    kind = button.get('type', 'text')
    if button.get('icon'):
        img = Image.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), button['icon'])).convert('RGB').resize((SIZE, SIZE))
    elif kind == 'app' and (app_icon := load_app_icon(button['app'])):
        img = Image.new('RGB', (SIZE, SIZE), color=button['background'])
        # Leave room at the bottom for an optional title.
        icon_size = SIZE - 50 if button.get('title') else SIZE - 20
        app_icon = app_icon.resize((icon_size, icon_size), Image.LANCZOS)
        img.paste(app_icon, ((SIZE - icon_size) // 2, 10), app_icon)
        if button.get('title'):
            draw_title(img, {**button, 'font_size': APP_TITLE_SIZE}, (SIZE / 2, SIZE - 20))
    else:
        img = Image.new('RGB', (SIZE, SIZE), color=button['background'])
        draw_title(img, button, (SIZE / 2, SIZE / 2))
    return save_icon(img, f'button_{number}')


def check_pages(pages):
    for page, keys in pages.items():
        for number, button in keys.items():
            if number not in KEY_NUMBERS:
                raise ValueError(f'page {page}: key {number} is out of range')
            check_button(number, button)
            if button.get('hold'):
                check_button(number, button['hold'])
            if button.get('type') == 'page':
                target = button.get('page')
                if target not in ('home', 'next', 'previous') and not (str(target).isdigit() and int(target) in pages):
                    raise ValueError(f'page {page} key {number}: unknown page: {target}')


PROFILE_TEMPLATE = """pages:
  1:
    11: {type: page, page: previous, title: "<"}
    12: {type: page, page: home, title: "Home"}
    13: {type: page, page: next, title: ">"}
    14: {type: profile, profile: default}
    16: {type: page, page: previous, hold: {type: profile, profile: default}}
    17: {type: page, page: next}
"""


def check_text(text):
    """Validate config text without touching the deck or rendering icons."""
    config = yaml.safe_load(text) or {}
    defaults = config.get('button_defaults') or {}
    pages = {int(p): {int(n): {**defaults, **(b or {})} for n, b in (keys or {}).items()}
             for p, keys in (config.get('pages') or {}).items()}
    pages.setdefault(1, {})
    check_pages(pages)
    for name, k in (config.get('knobs') or {}).items():
        parse_knob(name, {**k, 'name': name})


def replace_key_line(text, page, number, data):
    lines = text.split('\n')
    if 'pages:' not in lines:
        raise ValueError('no pages section in this file')
    start = lines.index('pages:')
    header = next((i for i in range(start + 1, len(lines)) if lines[i].rstrip() == f'  {page}:'), None)
    if header is None:
        raise ValueError(f'page {page} not found in this file')
    end = next((i for i in range(header + 1, len(lines))
                if lines[i].strip() and not lines[i].startswith('#') and len(lines[i]) - len(lines[i].lstrip()) <= 2),
               len(lines))
    flow = yaml.safe_dump(data, default_flow_style=True, sort_keys=False, allow_unicode=True, width=10 ** 6).strip()
    new_line = f'    {number}: {flow}'
    for i in range(header + 1, end):
        if re.match(rf'    {number}:', lines[i]):
            lines[i] = new_line
            return '\n'.join(lines)
    last = next((i for i in range(header + 1, end) if lines[i].startswith('    ') and lines[i].strip()), header)
    lines.insert(last + 1, new_line)
    return '\n'.join(lines)


def remove_key_line(text, page, number):
    lines = text.split('\n')
    header = next((i for i in range(len(lines)) if lines[i].rstrip() == f'  {page}:'), None)
    if header is None:
        raise ValueError(f'page {page} not found in this file')
    end = next((i for i in range(header + 1, len(lines))
                if lines[i].strip() and not lines[i].startswith('#') and len(lines[i]) - len(lines[i].lstrip()) <= 2),
               len(lines))
    for i in range(header + 1, end):
        if re.match(rf'    {number}:', lines[i]):
            del lines[i]
            break
    return '\n'.join(lines)


def replace_device_lines(text, data):
    lines = text.split('\n')
    if 'device:' not in lines:
        lines.insert(0, 'device:')
    start = lines.index('device:')

    def block_end():
        return next((i for i in range(start + 1, len(lines))
                     if lines[i].strip() and not lines[i].startswith('#') and not lines[i].startswith(' ')),
                    len(lines))

    for key, value in data.items():
        rendered = 'true' if value is True else 'false' if value is False else json.dumps(value)
        end = block_end()
        for i in range(start + 1, end):
            if re.match(rf'  {key}:', lines[i]):
                lines[i] = f'  {key}: {rendered}'
                break
        else:
            lines.insert(start + 1, f'  {key}: {rendered}')
    return '\n'.join(lines)


def replace_knob_line(text, name, data):
    lines = text.split('\n')
    if 'knobs:' not in lines:
        lines.append('knobs:')
    start = lines.index('knobs:')
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].strip() and not lines[i].startswith('#') and not lines[i].startswith(' ')),
               len(lines))
    flow = yaml.safe_dump(data, default_flow_style=True, sort_keys=False, allow_unicode=True, width=10 ** 6).strip()
    new_line = f'  {name}: {flow}'
    for i in range(start + 1, end):
        if re.match(rf'  {name}:', lines[i]):
            lines[i] = new_line
            return '\n'.join(lines)
    last = next((i for i in range(end - 1, start, -1) if lines[i].startswith('  ') and lines[i].strip()), start)
    lines.insert(last + 1, new_line)
    return '\n'.join(lines)


class Manager:
    def __init__(self, deck, config_path):
        self.deck = deck
        self.config_path = config_path
        self.profile = None
        self.last_app = None
        self.sticky = False
        self.mtimes = None
        self.device = {}
        self.pages = {}
        self.layouts = {}
        self.page = 1
        self.knobs = {}
        self.icons = {}
        self.last_error = None

    def profile_path(self, name):
        return os.path.join(os.path.dirname(os.path.abspath(self.config_path)), 'profiles', f'{name}.yaml')

    def active_path(self):
        return self.profile_path(self.profile) if self.profile else self.config_path

    def file_mtimes(self):
        paths = [self.config_path] + ([self.active_path()] if self.profile else [])
        return tuple(os.path.getmtime(p) if os.path.exists(p) else None for p in paths)

    def load(self):
        """Read the config and push it to the deck. On error the previous config stays active."""
        self.mtimes = self.file_mtimes()
        try:
            config = load_config(self.config_path) or {}
            if self.profile:
                profile = load_config(self.active_path()) or {}
                config = {**config, **{k: profile[k] for k in ('pages', 'knobs') if k in profile}}
            device = config.get('device') or {}
            defaults = config.get('button_defaults') or {}
            # Config keys are numbered from 1; the deck index is number - 1
            # (left-to-right, top-to-bottom, index = row * 5 + col).
            if config.get('buttons'):
                raise ValueError('"buttons" moved: put the keys under "pages: 1:"')
            pages = {int(p): {int(n): {**defaults, **(b or {})} for n, b in (keys or {}).items()}
                     for p, keys in (config.get('pages') or {}).items()}
            pages.setdefault(1, {})
            check_pages(pages)
            knobs = {k['index']: parse_knob(name, {**k, 'name': name}) for name, k in (config.get('knobs') or {}).items()}

            clear_icons()
            # Key 14 has no screen of its own, but it shows an icon over the clock when it has a title or icon.
            icons = {p: {n: render_button(n, b) for n, b in keys.items()
                         if n not in INPUT_ONLY_KEYS or (n == CLOCK_KEY and (b.get('title') or b.get('icon')))}
                     for p, keys in pages.items()}
            blank = render_solid(defaults.get('background', '#1a1a2e'))
            # Slots 13 and 14 (cols 3-4 of the bottom row) are the clock window. Give them
            # a solid background so the deck's default image doesn't show behind the time.
            clock = render_solid(device.get('clock_background', '#000000'))
            layouts = {}
            for p in pages:
                layout = {i: {'icon': blank} for i in range(UlanziD200Device.BUTTON_COUNT)}
                layout.update({n - 1: {'icon': name} for n, name in icons[p].items()})
                for i in range(UlanziD200Device.BUTTON_COUNT, UlanziD200Device.BUTTON_ROWS * UlanziD200Device.BUTTON_COLS):
                    layout.setdefault(i, {'icon': clock})
                layouts[p] = layout
        except Exception as e:
            self.last_error = str(e)
            print(f'config error, keeping previous config: {e}')
            return False

        self.last_error = None
        self.device, self.pages, self.knobs, self.icons, self.layouts = device, pages, knobs, icons, layouts
        if self.page not in pages:
            self.page = 1
        # Media keys work without it, but normal key combos are dropped silently.
        combos = [c for keys in pages.values() for b in keys.values() for c in b.get('combos', [])]
        combos += [c for k in knobs.values() for cs in k.get('combos', {}).values() for c in cs]
        if any(kind == 'key' for kind, _, _ in combos) and not _AS.AXIsProcessTrusted():
            print('warning: type key needs Accessibility permission for this terminal app '
                  '(System Settings > Privacy & Security > Accessibility)')
        self.deck.set_brightness(device.get('brightness', 80))
        self.deck.set_buttons(self.layouts[self.page])
        self.apply_small_window()
        return True

    def apply_small_window(self):
        # The small window draws the clock over the slots next to key 13. Hide it when key 14 has an icon there.
        shows_key = CLOCK_KEY in self.icons.get(self.page, {})
        self.deck.set_small_window_mode(SMALL_WINDOW_BACKGROUND if shows_key else SMALL_WINDOW_CLOCK)

    async def watch_config(self, interval=1.0):
        while True:
            await asyncio.sleep(interval)
            # Editors may briefly remove a file while saving; a missing file just reads as None.
            if self.file_mtimes() != self.mtimes and self.load():
                print('config reloaded')

    def open_app_profile(self, app_name, profile):
        # The app activating would otherwise switch to its own profile, so mark it as already seen.
        self.last_app = app_name
        self.open_profile(profile)
        self.sticky = profile is not None

    def open_profile(self, name):
        self.sticky = False
        self.profile = name
        self.page = 1
        self.load()
        print(f'profile: {name or "default"}')

    def set_profile(self, name):
        if name != self.profile:
            self.open_profile(name)

    async def watch_app(self, interval=1.0):
        # Only switch when the frontmost app changes, so a profile chosen with a key stays until then.
        while True:
            try:
                name = frontmost_app_name()
                if name != self.last_app:
                    self.last_app = name
                    print(f'app: {name}')
                    if not self.sticky:
                        wanted = name if name and '/' not in name and os.path.exists(self.profile_path(name)) else None
                        self.set_profile(wanted)
            except Exception as e:
                print(f'app watch error: {e}')
            await asyncio.sleep(interval)

    async def keep_alive(self):
        # Without regular host traffic the deck switches to its screensaver after
        # ~30s. Ulanzi Studio pushes the small-window clock every second; do the same.
        while True:
            if not self.device.get('screensaver', False):
                self.deck.keep_alive()
            await asyncio.sleep(self.device.get('keep_alive_interval', 1.0))

    def page_number(self, target):
        numbers = sorted(self.pages)
        if target == 'home':
            return 1
        if target == 'next':
            return numbers[(numbers.index(self.page) + 1) % len(numbers)]
        if target == 'previous':
            return numbers[(numbers.index(self.page) - 1) % len(numbers)]
        return int(target)

    def goto(self, page):
        self.page = page
        self.deck.set_buttons(self.layouts[page])
        self.apply_small_window()

    def add_page(self, name=None):
        name = name or (self.profile or 'default')
        lines = self.read_file(name).split('\n')
        if 'pages:' not in lines:
            lines.append('pages:')
        start = lines.index('pages:')
        last = start
        for i in range(start + 1, len(lines)):
            line = lines[i]
            if line and not line[0].isspace() and not line.startswith('#'):
                break
            if line.startswith(' '):
                last = i
        pages = (load_config(self.file_for(name)) or {}).get('pages') or {}
        number = max(pages, default=0) + 1
        lines[last + 1:last + 1] = [
            f'  {number}:',
            '    11: {type: page, page: previous, title: "<-"}',
            '    12: {type: page, page: home, title: "Home"}',
            '    13: {type: page, page: next, title: "->"}',
            '    14: {type: profile, profile: default}',
            '    16: {type: page, page: home}',
            '    17: {type: page, page: next}',
        ]
        error = self.save_file(name, '\n'.join(lines))
        if error:
            raise ValueError(error)
        if name == (self.profile or 'default'):
            self.goto(number)
        return number

    def has_hold(self, number):
        return bool(self.pages.get(self.page, {}).get(number, {}).get('hold'))

    def plan_button(self, number, hold=False):
        """What pressing a key does, as (description, function) steps. Nothing runs until called."""
        button = self.pages.get(self.page, {}).get(number)
        if not button:
            text = f'key {number} pressed (not configured on page {self.page})'
            return [(text, partial(print, text))]
        if hold:
            button = button.get('hold') or {}
        steps = []
        if button.get('type') == 'page':
            target = self.page_number(str(button['page']))
            steps.append((f'page {target}', partial(self.goto, target)))
        elif button.get('type') == 'profile':
            name = None if button['profile'] == 'default' else button['profile']
            if name and not os.path.exists(self.profile_path(name)):
                text = f'profile {name} not found'
                return [(text, partial(print, text))]
            steps.append((f"profile {button['profile']}", partial(self.open_profile, name)))
        elif button.get('type') == 'app':
            steps.append((f"open {button['app']}", partial(subprocess.Popen, ['open', button['app']])))
            app_name = os.path.splitext(os.path.basename(button['app']))[0]
            wanted = button.get('profile') or app_name
            if wanted != 'none':
                target = None if wanted == 'default' else wanted
                if target is None or os.path.exists(self.profile_path(target)):
                    steps.append((f'profile {wanted}', partial(self.open_app_profile, app_name, target)))
        elif button.get('type') == 'key':
            steps.append((f"send {button['keys']}", partial(send_keys, button['combos'])))
        if button.get('output'):
            steps.append((f"print {button['output']}", partial(print, button['output'])))
        return steps

    def plan_knob(self, index, event):
        knob = self.knobs.get(index)
        if knob is None or event not in KNOB_EVENTS.values():
            text = f'unknown knob 0x{index:02x} event {event}'
            return [(text, partial(print, text))]
        if knob.get('type') == 'device_brightness':
            if event == 'press':
                return []
            current = self.device.get('brightness', 80)
            step = knob.get('step', 10) * (1 if event == 'right' else -1)
            value = min(100, max(0, current + step))
            return [(f'deck brightness {value}', partial(self.set_brightness, value))]
        if not knob.get(event):
            return []
        if knob.get('type') == 'key':
            return [(f"send {knob[event]}", partial(send_keys, knob['combos'][event]))]
        return [(f"print {knob[event]}", partial(print, knob[event]))]

    @staticmethod
    def run(steps):
        for _, action in steps:
            action()

    def set_brightness(self, value):
        self.device['brightness'] = value
        self.deck.set_brightness(value)

    def save_config(self, text):
        """Write the config only if it loads, otherwise restore the old file. Returns the error or None."""
        yaml.safe_load(text)
        path = self.active_path()
        with open(path) as fp:
            old = fp.read()
        with open(path, 'w') as fp:
            fp.write(text)
        if self.load():
            return None
        error = self.last_error
        with open(path, 'w') as fp:
            fp.write(old)
        self.load()
        return error

    def create_profile(self, name):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _-]{0,40}', name or ''):
            raise ValueError('ongeldige naam: gebruik letters, cijfers, spatie, - of _')
        if name in self.profile_names():
            raise ValueError(f'profiel {name} bestaat al')
        os.makedirs(os.path.dirname(self.profile_path(name)), exist_ok=True)
        with open(self.profile_path(name), 'x') as fp:
            fp.write(PROFILE_TEMPLATE)
        return name

    def key_data(self, name, page, number):
        pages = (load_config(self.file_for(name)) or {}).get('pages') or {}
        return dict((pages.get(page) or {}).get(number) or {})

    def device_settings(self):
        return {'clock_background': self.device.get('clock_background', '#000000'),
                'screensaver': bool(self.device.get('screensaver', False)),
                'keep_alive_interval': self.device.get('keep_alive_interval', 1.0)}

    def set_device(self, data):
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', str(data['clock_background'])):
            return 'achtergrond moet een hex-kleur zijn, bijv. #1a1a2e'
        interval = float(data['keep_alive_interval'])
        if not 0.2 <= interval <= 10:
            return 'keep-alive interval moet tussen 0.2 en 10 seconden zijn'
        values = {'clock_background': data['clock_background'], 'screensaver': bool(data['screensaver']),
                  'keep_alive_interval': interval}
        with open(self.config_path) as fp:
            old = fp.read()
        with open(self.config_path, 'w') as fp:
            fp.write(replace_device_lines(old, values))
        if self.load():
            return None
        error = self.last_error
        with open(self.config_path, 'w') as fp:
            fp.write(old)
        self.load()
        return error

    def knob_data(self, profile, name):
        knobs = (load_config(self.file_for(profile)) or {}).get('knobs') or {}
        return dict(knobs.get(name) or {})

    def set_knob(self, profile, name, data):
        text = replace_knob_line(self.read_file(profile), name, data)
        return self.save_file(profile, text)

    def clear_key(self, name, page, number):
        return self.save_file(name, remove_key_line(self.read_file(name), page, number))

    def set_key(self, name, page, number, data):
        text = replace_key_line(self.read_file(name), page, number, data)
        return self.save_file(name, text)

    def save_file(self, name, text):
        """Save the active config through the deck. Other files are only checked and written."""
        if name == (self.profile or 'default'):
            return self.save_config(text)
        try:
            check_text(text)
        except Exception as e:
            return str(e)
        with open(self.file_for(name), 'w') as fp:
            fp.write(text)
        return None

    def profile_names(self):
        folder = os.path.join(os.path.dirname(os.path.abspath(self.config_path)), 'profiles')
        names = sorted(os.path.splitext(f)[0] for f in os.listdir(folder) if f.endswith('.yaml')) if os.path.isdir(folder) else []
        return ['default'] + names

    def file_for(self, name):
        if name not in self.profile_names():
            raise ValueError(f'unknown profile: {name}')
        return self.config_path if name == 'default' else self.profile_path(name)

    def read_file(self, name):
        with open(self.file_for(name)) as fp:
            return fp.read()

    def tree(self):
        result = []
        for name in self.profile_names():
            error = None
            try:
                pages = (load_config(self.file_for(name)) or {}).get('pages') or {}
            except Exception as e:
                pages, error = {}, str(e)
            buttons = [{'page': int(p), 'number': int(n), 'type': (b or {}).get('type', 'text'), 'title': (b or {}).get('title')}
                       for p, keys in sorted(pages.items()) for n, b in sorted((keys or {}).items())]
            result.append({'name': name, 'buttons': buttons, 'error': error,
                           'active': name == (self.profile or 'default')})
        return result

    def state(self):
        return {
            'profiles': self.tree(),
            'error': self.last_error,
            'brightness': self.device.get('brightness', 80),
            'profile': self.profile or 'default',
            'page': self.page,
            'pages': sorted(self.pages),
            'keys': {n: {'icon': self.icons.get(self.page, {}).get(n),
                         **{k: self.pages.get(self.page, {}).get(n, {}).get(k)
                            for k in ('type', 'title', 'app', 'keys', 'output', 'page')}}
                     for n in sorted(KEY_NUMBERS)},
            'knobs': [{k: knob.get(k) for k in ('name', 'index', 'type', 'left', 'right', 'press')}
                      for knob in self.knobs.values()],
        }


async def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else CONFIG_PATH

    deck = connect()
    if deck is None:
        raise SystemExit("No Ulanzi D200 found")

    manager = Manager(deck, config_path)
    if not manager.load():
        raise SystemExit(1)
    # Keep references so the tasks aren't GC'd
    tasks = [asyncio.create_task(manager.keep_alive()),
             asyncio.create_task(manager.watch_config()),
             asyncio.create_task(manager.watch_app())]
    web_server.start(manager, asyncio.get_running_loop(), ICON_DIR, WEB_PORT)

    print("Druk op een knop (Ctrl+C om te stoppen)")
    pressed_at = {}
    async for action in deck.read_packet():
        if isinstance(action, KnobAction):
            if action.value != KNOB_RELEASE:
                manager.run(manager.plan_knob(action.index, KNOB_EVENTS.get(action.value)))
        elif action and action.pressed:
            number = action.index + 1
            if manager.has_hold(number):
                pressed_at[number] = time.monotonic()
            else:
                manager.run(manager.plan_button(number))
        elif action:
            number = action.index + 1
            started = pressed_at.pop(number, None)
            if started is not None:
                manager.run(manager.plan_button(number, hold=time.monotonic() - started >= LONG_PRESS))


if __name__ == '__main__':
    asyncio.run(main())
