import asyncio
import binascii
import ctypes
import hashlib
import io
import os
import plistlib
import subprocess
import sys
from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageFont
import hid
import yaml
from strmdck.device import ButtonAction
from strmdck.devices.ulanzi_d200 import UlanziD200Device

ICON_DIR = os.path.join('.cache', 'icons', '_generated')
SIZE = UlanziD200Device.ICON_WIDTH  # 196x196
CONFIG_PATH = 'config.yaml'
APP_TITLE_SIZE = 28  # title under an app icon

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
    elif kind != 'text':
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


def render_button(number, button):
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
    elif kind != 'text':
        raise ValueError(f'key {number}: unknown type: {kind}')

    if button.get('icon'):
        img = Image.open(button['icon']).convert('RGB').resize((SIZE, SIZE))
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


class Manager:
    def __init__(self, deck, config_path):
        self.deck = deck
        self.config_path = config_path
        self.mtime = None
        self.device = {}
        self.buttons = {}
        self.knobs = {}

    def load(self):
        """Read the config and push it to the deck. On error the previous config stays active."""
        self.mtime = os.path.getmtime(self.config_path)
        try:
            config = load_config(self.config_path) or {}
            device = config.get('device') or {}
            defaults = config.get('button_defaults') or {}
            # Config keys are numbered from 1; the deck index is number - 1
            # (left-to-right, top-to-bottom, index = row * 5 + col).
            buttons = {int(n): {**defaults, **(b or {})} for n, b in (config.get('buttons') or {}).items()}
            knobs = {k['index']: parse_knob(name, k) for name, k in (config.get('knobs') or {}).items()}

            clear_icons()
            layout = {number - 1: {'icon': render_button(number, b)} for number, b in buttons.items()}
            # Slots 13 and 14 (cols 3-4 of the bottom row) are the clock window. Give them
            # a solid background so the deck's default image doesn't show behind the time.
            clock = render_solid(device.get('clock_background', '#000000'))
            for i in range(UlanziD200Device.BUTTON_COUNT, UlanziD200Device.BUTTON_ROWS * UlanziD200Device.BUTTON_COLS):
                layout[i] = {'icon': clock}
        except Exception as e:
            print(f'config error, keeping previous config: {e}')
            return False

        self.device, self.buttons, self.knobs = device, buttons, knobs
        # Media keys work without it, but normal key combos are dropped silently.
        combos = [c for b in buttons.values() for c in b.get('combos', [])]
        combos += [c for k in knobs.values() for cs in k.get('combos', {}).values() for c in cs]
        if any(kind == 'key' for kind, _, _ in combos) and not _AS.AXIsProcessTrusted():
            print('warning: type key needs Accessibility permission for this terminal app '
                  '(System Settings > Privacy & Security > Accessibility)')
        self.deck.set_brightness(device.get('brightness', 80))
        self.deck.set_buttons(layout)
        return True

    async def watch_config(self, interval=1.0):
        while True:
            await asyncio.sleep(interval)
            try:
                mtime = os.path.getmtime(self.config_path)
            except OSError:
                continue  # editors may briefly remove the file while saving
            if mtime != self.mtime and self.load():
                print('config reloaded')

    async def keep_alive(self):
        # Without regular host traffic the deck switches to its screensaver after
        # ~30s. Ulanzi Studio pushes the small-window clock every second; do the same.
        while True:
            self.deck.keep_alive()
            await asyncio.sleep(self.device.get('keep_alive_interval', 1.0))

    def handle(self, action):
        if isinstance(action, KnobAction):
            if action.value == KNOB_RELEASE:
                return
            knob = self.knobs.get(action.index)
            event = KNOB_EVENTS.get(action.value)
            if knob is None or event is None:
                print(f'knob 0x{action.index:02x} value 0x{action.value:02x}')
            elif knob.get('type') == 'key':
                send_keys(knob['combos'].get(event, []))
            elif knob.get(event):
                print(knob[event])
        elif action and action.pressed:
            button = self.buttons.get(action.index + 1)
            if not button:
                return
            if button.get('type') == 'app':
                subprocess.Popen(['open', button['app']])
            elif button.get('type') == 'key':
                send_keys(button['combos'])
            if button.get('output'):
                print(button['output'])


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
             asyncio.create_task(manager.watch_config())]

    print("Druk op een knop (Ctrl+C om te stoppen)")
    async for action in deck.read_packet():
        manager.handle(action)

asyncio.run(main())
