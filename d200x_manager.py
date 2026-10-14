import asyncio
import binascii
import ctypes
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from functools import partial
from PIL import Image, ImageColor, ImageDraw, ImageFont
import hid
import yaml
from strmdck.device import ButtonAction
from strmdck.devices.ulanzi_d200 import UlanziD200Device
import web_server
from appicon import app_icon as load_app_icon
import i18n
from i18n import t

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


def set_top_line(text, key, value):
    """Set (or with value None remove) a top-level `key: value` line, keeping the rest of the file."""
    lines = text.split('\n')
    index = next((i for i, line in enumerate(lines) if re.match(rf'{key}:', line)), None)
    if value is None:
        if index is not None:
            lines.pop(index)
    else:
        line = f'{key}: {json.dumps(value)}'
        if index is not None:
            lines[index] = line
        else:
            # After the leading comment block, so the file's header stays on top.
            at = next((i for i, l in enumerate(lines) if l.strip() and not l.startswith('#')), len(lines))
            lines.insert(at, line)
    return '\n'.join(lines)


def parse_keys(keys):
    """Parse "cmd+c", "volumeup" (or a list of those) into [(kind, code, flags), ...]."""
    combos = []
    for combo in [keys] if isinstance(keys, str) else keys:
        *mods, key = [part.strip().lower() for part in str(combo).split('+')]
        if key in MEDIA_KEYS and not mods:
            combos.append(('media', MEDIA_KEYS[key], 0))
            continue
        if key not in KEY_CODES or any(m not in MODIFIERS for m in mods):
            raise ValueError(t('config.unknown_combo', combo=combo))
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
            raise ValueError(t('config.knob', name=name, error=e))
    elif kind not in ('text', 'device_brightness'):
        raise ValueError(t('config.knob', name=name, error=t('config.unknown_type', type=kind)))
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


def cover_tiles(path, cols, rows):
    """Cover-fit an image over a cols x rows block of keys. Returns one image per key, row by row."""
    image = Image.open(path).convert('RGB')
    width, height = cols * SIZE, rows * SIZE
    scale = max(width / image.width, height / image.height)
    image = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    left, top = (image.width - width) // 2, (image.height - height) // 2
    image = image.crop((left, top, left + width, top + height))
    return [image.crop((c * SIZE, r * SIZE, (c + 1) * SIZE, (r + 1) * SIZE))
            for r in range(rows) for c in range(cols)]


def clock_window_tiles(wallpaper, key):
    """The two slots behind the clock, from key 14's settings: a color or picture, optionally transparent."""
    first = UlanziD200Device.BUTTON_COUNT
    base = Image.new('RGBA', (2 * SIZE, SIZE), (0, 0, 0, 255))
    for i in range(2):
        if wallpaper:
            base.paste(wallpaper[first + i], (i * SIZE, 0))
    opacity = 1 - float(key.get('transparency', 0)) / 100
    if key.get('background_image'):
        layer = cover_tiles(key['background_image'], 2, 1)
        joined = Image.new('RGBA', (2 * SIZE, SIZE))
        for i, tile in enumerate(layer):
            joined.paste(tile, (i * SIZE, 0))
    else:
        joined = Image.new('RGBA', (2 * SIZE, SIZE), ImageColor.getrgb(key['background'])[:3] + (255,))
    joined.putalpha(joined.getchannel('A').point(lambda a: round(a * opacity)))
    out = Image.alpha_composite(base, joined).convert('RGB')
    return [save_icon(out.crop((i * SIZE, 0, (i + 1) * SIZE, SIZE)), 'clock') for i in range(2)]


HEX_COLOR = re.compile(r'#[0-9a-fA-F]{6}')


def background_of(values):
    """The background a profile or page asks for: ('image', path), ('color', '#rrggbb') or None."""
    if (values or {}).get('background_image'):
        return 'image', values['background_image']
    if (values or {}).get('background_color'):
        return 'color', values['background_color']
    return None


def check_background(values):
    image, color = (values or {}).get('background_image'), (values or {}).get('background_color')
    if image and not os.path.isfile(image):
        raise ValueError(t('errors.background_missing', path=image))
    if color and not HEX_COLOR.fullmatch(str(color)):
        raise ValueError(t('errors.hex_color', field='background_color'))


def page_wallpapers(pages, page_settings, background):
    """{page: per-slot background images or None}. A page's own background wins over the profile's
    (`background`, from background_of); without any the screen is black."""
    cache = {}
    result = {}
    for page in pages:
        spec = background_of(page_settings.get(page)) or background
        if spec and spec not in cache:
            kind, value = spec
            slots = UlanziD200Device.BUTTON_COLS * UlanziD200Device.BUTTON_ROWS
            cache[spec] = (cover_tiles(value, UlanziD200Device.BUTTON_COLS, UlanziD200Device.BUTTON_ROWS) if kind == 'image'
                           else [Image.new('RGB', (SIZE, SIZE), value)] * slots)
        result[page] = cache.get(spec) if spec else None
    return result


def render_tiles(path, cols, rows):
    return [save_icon(tile, 'bg') for tile in cover_tiles(path, cols, rows)]


def screensaver_mode(device):
    mode = device.get('screensaver', 'off')
    return 'firmware' if mode is True else 'off' if not mode else mode


def draw_title(img, button, center):
    draw = ImageDraw.Draw(img)
    draw.text(center, str(button.get('title', '')),
              font=load_font(button['font_size']), fill=button['color'], anchor='mm')


def button_problem(button):
    """What is wrong with a key definition, or None. Also parses "keys" into button['combos']."""
    kind = button.get('type', 'text')
    if kind == 'app':
        app = button.get('app')
        if not app or not os.path.isdir(app):
            return t('config.app_not_found', app=app)
    elif kind == 'key':
        try:
            button['combos'] = parse_keys(button.get('keys') or [])
        except ValueError as e:
            return str(e)
        if not button['combos']:
            return t('config.keys_needed')
    elif kind not in ('text', 'page', 'profile'):
        return t('config.unknown_type', type=kind)
    if button.get('background_image') and not os.path.isfile(button['background_image']):
        return t('config.background_image_missing', path=button['background_image'])
    if not 0 <= button.get('transparency', 0) <= 100:
        return t('config.transparency_range')
    return None


def check_button(number, button):
    problem = button_problem(button)
    if problem:
        raise ValueError(t('config.key', number=number, error=problem))


KEY_FIELDS = {'title', 'type', 'keys', 'app', 'profile', 'page', 'icon', 'background', 'color', 'font_size',
              'transparency', 'hold', 'output', 'background_image'}


def check_key_entry(entry, where, icons=()):
    """Check one key definition as written in a config, profile or library file.
    `icons` are extra icon file names that are available, e.g. from a library's zip."""
    def fail(message):
        raise ValueError(t('errors.at', where=where, error=message))

    if not isinstance(entry, dict):
        fail(t('library_check.not_a_key'))
    unknown = sorted(set(entry) - KEY_FIELDS)
    if unknown:
        fail(t('library_check.unknown_field', fields=', '.join(unknown)))
    kind = entry.get('type', 'text')
    if kind == 'page' and entry.get('page') is None:
        fail(t('library_check.page_needed'))
    if kind == 'profile' and not entry.get('profile'):
        fail(t('library_check.profile_needed'))
    for field in ('background', 'color'):
        if field in entry:
            try:
                ImageColor.getrgb(str(entry[field]))
            except ValueError:
                fail(t('library_check.not_a_color', field=field, value=entry[field]))
    if 'font_size' in entry and not (isinstance(entry['font_size'], int) and 8 <= entry['font_size'] <= 200):
        fail(t('library_check.font_size_range'))
    if 'transparency' in entry and not isinstance(entry['transparency'], (int, float)):
        fail(t('library_check.transparency_number'))
    if (entry.get('icon') and not os.path.isfile(os.path.join(os.path.dirname(os.path.abspath(__file__)), entry['icon']))
            and os.path.basename(entry['icon']) not in icons):
        fail(t('library_check.icon_missing', path=entry['icon']))
    problem = button_problem(dict(entry))
    if problem:
        fail(problem)
    if 'hold' in entry:
        if 'hold' in (entry['hold'] or {}):
            fail(t('library_check.hold_in_hold'))
        check_key_entry(entry['hold'], t('library_check.hold', where=where), icons)


def check_library(text, icons=()):
    """Validate the text of a library file. Returns its key definitions or raises ValueError.
    `icons` are the icon file names in the zip that comes with the library."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ValueError(t('library_check.invalid_yaml', error=e))
    if not isinstance(data, dict) or 'buttons' not in data:
        raise ValueError(t('library_check.needs_buttons'))
    extra = sorted(set(data) - {'buttons'})
    if extra:
        raise ValueError(t('library_check.top_field', fields=', '.join(extra)))
    buttons = data['buttons'] or []
    if not isinstance(buttons, list):
        raise ValueError(t('library_check.buttons_list'))
    for i, entry in enumerate(buttons, 1):
        title = entry.get('title') if isinstance(entry, dict) else None
        where = t('library_check.entry_titled', number=i, title=title) if title else t('library_check.entry', number=i)
        check_key_entry(entry, where, icons)
    return buttons


def render_button(number, button, wallpaper=None):
    """Render a key. `wallpaper` is the list of per-slot background images that shows through
    the key's background when it has a transparency above 0."""
    check_button(number, button)
    kind = button.get('type', 'text')
    opacity = 1 - float(button.get('transparency', 0)) / 100
    fill = ImageColor.getrgb(button['background'])[:3] + (round(255 * opacity),)
    if button.get('icon'):
        # Like the other keys: the background color (with its transparency) first, the icon on top of it.
        icon = Image.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), button['icon'])).convert('RGBA')
        img = Image.new('RGBA', (SIZE, SIZE), color=fill)
        img.alpha_composite(icon.resize((SIZE, SIZE), Image.LANCZOS))
    elif kind == 'app' and (app_icon := load_app_icon(button['app'])):
        img = Image.new('RGBA', (SIZE, SIZE), color=fill)
        # Leave room at the bottom for an optional title.
        icon_size = SIZE - 50 if button.get('title') else SIZE - 20
        app_icon = app_icon.resize((icon_size, icon_size), Image.LANCZOS)
        img.paste(app_icon, ((SIZE - icon_size) // 2, 10), app_icon)
        if button.get('title'):
            draw_title(img, {**button, 'font_size': APP_TITLE_SIZE}, (SIZE / 2, SIZE - 20))
    else:
        img = Image.new('RGBA', (SIZE, SIZE), color=fill)
        draw_title(img, button, (SIZE / 2, SIZE / 2))
    base = wallpaper[number - 1].convert('RGBA') if wallpaper and number - 1 < len(wallpaper) else Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 255))
    return save_icon(Image.alpha_composite(base, img).convert('RGB'), f'button_{number}')


def check_pages(pages):
    for page, keys in pages.items():
        for number, button in keys.items():
            if number not in KEY_NUMBERS:
                raise ValueError(t('config.key_out_of_range', page=page, number=number))
            check_button(number, button)
            if button.get('hold'):
                check_button(number, button['hold'])
            if button.get('type') == 'page':
                target = button.get('page')
                if target not in ('home', 'next', 'previous') and not (str(target).isdigit() and int(target) in pages):
                    raise ValueError(t('config.unknown_page', page=page, number=number, target=target))


PROFILE_TEMPLATE = """pages:
  1:
    11: {type: page, page: previous, title: "<"}
    12: {type: page, page: home, title: "Home"}
    13: {type: page, page: next, title: ">"}
    14: {type: profile, profile: default}
    16: {type: page, page: previous, hold: {type: profile, profile: default}}
    17: {type: page, page: next}
"""


PAGE_NAME_MAX = 30


def page_settings_of(config):
    """{page number: {'name': ..., 'background_image': ...}} from a config or profile file, checked."""
    settings = {}
    for page, values in (config.get('page_settings') or {}).items():
        values = values or {}
        name = values.get('name')
        if name is not None and (not isinstance(name, str) or len(name) > PAGE_NAME_MAX):
            raise ValueError(t('errors.page_name_long', max=PAGE_NAME_MAX))
        check_background(values)
        settings[int(page)] = values
    return settings


def check_text(text):
    """Validate config text without touching the deck or rendering icons."""
    config = yaml.safe_load(text) or {}
    page_settings_of(config)
    defaults = config.get('button_defaults') or {}
    pages = {int(p): {int(n): {**defaults, **(b or {})} for n, b in (keys or {}).items()}
             for p, keys in (config.get('pages') or {}).items()}
    pages.setdefault(1, {})
    check_pages(pages)
    for name, k in (config.get('knobs') or {}).items():
        parse_knob(name, {**k, 'name': name})


PAGE_HEADER = re.compile(r'  (\d+):\s*(#.*)?$')
KEY_LINE = re.compile(r'(    \d+:\s*)(.*)$')


def top_block(lines, name):
    """(start, end) line indexes of a top-level "name:" block; end is the first line after it. None if absent."""
    if f'{name}:' not in lines:
        return None
    start = lines.index(f'{name}:')
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].strip() and not lines[i].startswith('#') and not lines[i].startswith(' ')), len(lines))
    return start, end


def retarget_pages(line, mapping):
    """A key line with its page references (also in "hold") changed by `mapping`; the line itself if none change."""
    match = KEY_LINE.match(line)
    if not match:
        return line
    try:
        data = yaml.safe_load(match.group(2))
    except yaml.YAMLError:
        return line
    if not isinstance(data, dict):
        return line
    changed = False
    for target in (data, data.get('hold')):
        if isinstance(target, dict) and target.get('type') == 'page' and target.get('page') in mapping:
            target['page'] = mapping[target['page']]
            changed = True
    if not changed:
        return line
    flow = yaml.safe_dump(data, default_flow_style=True, sort_keys=False, allow_unicode=True, width=10 ** 6).strip()
    return match.group(1) + flow


def swap_page_numbers(text, a, b):
    """Swap pages a and b: their headers under "pages:" and "page_settings:", and keys that go to them."""
    lines = text.split('\n')
    for block in ('pages', 'page_settings'):
        found = top_block(lines, block)
        if not found:
            continue
        for i in range(found[0] + 1, found[1]):
            header = PAGE_HEADER.match(lines[i]) or (re.match(r'  (\d+):', lines[i]) if block == 'page_settings' else None)
            if header and int(header.group(1)) in (a, b):
                number = b if int(header.group(1)) == a else a
                lines[i] = f'  {number}:' + lines[i][len(f'  {header.group(1)}:'):]
            elif block == 'pages':
                lines[i] = retarget_pages(lines[i], {a: b, b: a})
    return '\n'.join(lines)


def remove_page(text, page):
    """Remove a page with its keys and settings; keys that went to it go to the home page."""
    lines = text.split('\n')
    found = top_block(lines, 'pages')
    if found:
        start, end = found
        header = next((i for i in range(start + 1, end) if (m := PAGE_HEADER.match(lines[i])) and int(m.group(1)) == page), None)
        if header is not None:
            stop = next((i for i in range(header + 1, end) if PAGE_HEADER.match(lines[i])), end)
            del lines[header:stop]
        found = top_block(lines, 'pages')
        for i in range(found[0] + 1, found[1]):
            lines[i] = retarget_pages(lines[i], {page: 'home'})
    return set_page_settings_line('\n'.join(lines), page, None)


def set_page_settings_line(text, page, values):
    """Set (or with empty values remove) the "  page: {...}" line under "page_settings:"."""
    lines = text.split('\n')
    found = top_block(lines, 'page_settings')
    if found:
        start, end = found
        lines[start + 1:end] = [line for line in lines[start + 1:end] if not re.match(rf'  {page}:', line)]
    if values:
        if not found:
            while lines and not lines[-1].strip():
                lines.pop()
            lines += ['', 'page_settings:', '']
        start, end = top_block(lines, 'page_settings')   # again: the lines above may have changed
        last = max([i for i in range(start + 1, end) if lines[i].strip()], default=start)
        flow = yaml.safe_dump(values, default_flow_style=True, sort_keys=False, allow_unicode=True, width=10 ** 6).strip()
        lines.insert(last + 1, f'  {page}: {flow}')
    elif found:
        start, end = top_block(lines, 'page_settings')
        if not any(line.strip() and not line.lstrip().startswith('#') for line in lines[start + 1:end]):
            del lines[start:end]   # no page has settings any more
            while len(lines) > 1 and not lines[-1].strip() and not lines[-2].strip():
                lines.pop()
    return '\n'.join(lines)


def replace_key_line(text, page, number, data):
    lines = text.split('\n')
    if 'pages:' not in lines:
        raise ValueError(t('config.no_pages'))
    start = lines.index('pages:')
    header = next((i for i in range(start + 1, len(lines)) if lines[i].rstrip() == f'  {page}:'), None)
    if header is None:
        raise ValueError(t('config.page_missing', page=page))
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
        raise ValueError(t('config.page_missing', page=page))
    end = next((i for i in range(header + 1, len(lines))
                if lines[i].strip() and not lines[i].startswith('#') and len(lines[i]) - len(lines[i].lstrip()) <= 2),
               len(lines))
    for i in range(header + 1, end):
        if re.match(rf'    {number}:', lines[i]):
            del lines[i]
            break
    return '\n'.join(lines)


def replace_block_lines(text, block, data):
    """Set `key: value` lines inside a top-level block such as "device:", keeping the rest of the file."""
    lines = text.split('\n')
    if f'{block}:' not in lines:
        while lines and not lines[-1].strip():
            lines.pop()
        lines += ['', f'{block}:', '']
    start = lines.index(f'{block}:')

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
    check_library = staticmethod(check_library)

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
        self.saver_layout = None
        self.saver_active = False
        self.last_input = time.monotonic()

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
            i18n.set_language((config.get('ui') or {}).get('language'))
            # Each profile has its own background picture; without one the screen is black.
            check_background(config)
            background = background_of(config)
            page_settings = page_settings_of(config)
            if self.profile:
                profile = load_config(self.active_path()) or {}
                config = {**config, **{k: profile[k] for k in ('pages', 'knobs') if k in profile}}
                check_background(profile)
                background = background_of(profile)
                page_settings = page_settings_of(profile)
            device = config.get('device') or {}
            defaults = config.get('button_defaults') or {}
            # Config keys are numbered from 1; the deck index is number - 1
            # (left-to-right, top-to-bottom, index = row * 5 + col).
            if config.get('buttons'):
                raise ValueError(t('config.buttons_moved'))
            pages = {int(p): {int(n): {**defaults, **(b or {})} for n, b in (keys or {}).items()}
                     for p, keys in (config.get('pages') or {}).items()}
            pages.setdefault(1, {})
            check_pages(pages)
            knobs = {k['index']: parse_knob(name, {**k, 'name': name}) for name, k in (config.get('knobs') or {}).items()}

            clear_icons()
            # A page can have its own background; otherwise the profile's is used.
            wallpapers = page_wallpapers(pages, page_settings, background)
            # Key 14 has no screen of its own, but it shows an icon over the clock when it has a title or icon.
            icons = {p: {n: render_button(n, b, wallpapers[p]) for n, b in keys.items()
                         if n not in INPUT_ONLY_KEYS or (n == CLOCK_KEY and (b.get('title') or b.get('icon')))}
                     for p, keys in pages.items()}
            blank = render_solid('#000000')
            # Slots 13 and 14 (cols 3-4 of the bottom row) are the clock window. Give them
            # a solid background so the deck's default image doesn't show behind the time.
            clock_first = UlanziD200Device.BUTTON_COUNT
            raw_pages = config.get('pages') or {}
            mode = screensaver_mode(device)
            saver_layout = None
            if mode == 'color':
                solid = render_solid(device.get('screensaver_color', '#000000'))
                saver_layout = {i: {'icon': solid} for i in range(UlanziD200Device.BUTTON_ROWS * UlanziD200Device.BUTTON_COLS)}
            elif mode == 'image':
                tiles = render_tiles(device['screensaver_image'], UlanziD200Device.BUTTON_COLS, UlanziD200Device.BUTTON_ROWS)
                saver_layout = {i: {'icon': name} for i, name in enumerate(tiles)}
            layouts = {}
            for p in pages:
                wallpaper = wallpapers[p]
                wallpaper_names = [save_icon(t, 'bg') for t in wallpaper] if wallpaper else []
                raw_clock = (raw_pages.get(int(p)) or {}).get(CLOCK_KEY) or {}
                clock_tiles = clock_window_tiles(wallpaper, {
                    'background': raw_clock.get('background', device.get('clock_background', '#000000')),
                    'transparency': raw_clock.get('transparency', 0),
                    'background_image': raw_clock.get('background_image')})
                layout = {i: {'icon': wallpaper_names[i] if wallpaper else blank} for i in range(UlanziD200Device.BUTTON_COUNT)}
                layout.update({n - 1: {'icon': name} for n, name in icons[p].items()})
                for i in range(UlanziD200Device.BUTTON_COUNT, UlanziD200Device.BUTTON_ROWS * UlanziD200Device.BUTTON_COLS):
                    layout.setdefault(i, {'icon': clock_tiles[i - clock_first]})
                layouts[p] = layout
        except Exception as e:
            self.last_error = str(e)
            print(f'config error, keeping previous config: {e}')
            return False

        self.last_error = None
        self.device, self.pages, self.knobs, self.icons, self.layouts = device, pages, knobs, icons, layouts
        self.saver_layout, self.saver_active, self.last_input = saver_layout, False, time.monotonic()
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

    def open_app_profile(self, app, profile):
        # The app activating would otherwise switch to its own profile, so mark it as already seen.
        self.last_app = os.path.normpath(app)
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
                name, path = await asyncio.to_thread(frontmost_app)
                if path != self.last_app:
                    self.last_app = path
                    wanted = self.profile_for_app(path)
                    print(f'active app: {name} (profile: {wanted or "default"}{", sticky" if self.sticky else ""})')
                    if not self.sticky:
                        self.set_profile(wanted)
            except Exception as e:
                print(f'app watch error: {e}')
            await asyncio.sleep(interval)

    async def keep_alive(self):
        # Without regular host traffic the deck switches to its screensaver after
        # ~30s. Ulanzi Studio pushes the small-window clock every second; do the same.
        while True:
            if screensaver_mode(self.device) != 'firmware':
                self.deck.keep_alive()
            await asyncio.sleep(self.device.get('keep_alive_interval', 1.0))

    async def watch_idle(self):
        # Software screensaver: after the timeout, dim the deck and/or show a color or picture.
        while True:
            await asyncio.sleep(1.0)
            if (screensaver_mode(self.device) in ('dim', 'color', 'image') and not self.saver_active
                    and time.monotonic() - self.last_input >= self.device.get('screensaver_timeout', 60)):
                self.saver_active = True
                if self.saver_layout:
                    self.deck.set_buttons(self.saver_layout)
                self.deck.set_brightness(self.device.get('screensaver_brightness', 10))
                print('screensaver on')

    def wake(self, redraw=False):
        """Leave the screensaver. Returns True if it was active."""
        self.last_input = time.monotonic()
        if not self.saver_active:
            return False
        self.saver_active = False
        self.deck.set_brightness(self.device.get('brightness', 80))
        if redraw:
            self.deck.set_buttons(self.layouts[self.page])
            self.apply_small_window()
        print('screensaver off')
        return True

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
        self.wake()
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
            wanted = button.get('profile') or self.profile_for_app(button['app'])
            if wanted and wanted != 'none':
                target = None if wanted == 'default' else wanted
                if target is None or os.path.exists(self.profile_path(target)):
                    steps.append((f'profile {wanted}', partial(self.open_app_profile, button['app'], target)))
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
        self.wake(redraw=True)
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
            raise ValueError(t('errors.invalid_name'))
        if name in self.profile_names():
            raise ValueError(t('errors.profile_exists', name=name))
        os.makedirs(os.path.dirname(self.profile_path(name)), exist_ok=True)
        with open(self.profile_path(name), 'x') as fp:
            fp.write(PROFILE_TEMPLATE)
        return name

    def preview(self, name, page):
        """Key and clock images for one page of any profile, rendered as on the deck but not sent to it."""
        config = load_config(self.config_path) or {}
        own = config
        if name != 'default':
            own = load_config(self.file_for(name)) or {}
            config = {**config, **{k: own[k] for k in ('pages', 'knobs') if k in own}}
        background = background_of(own)
        device = config.get('device') or {}
        defaults = config.get('button_defaults') or {}
        raw = (config.get('pages') or {}).get(page) or {}
        wallpaper = page_wallpapers([page], page_settings_of(own), background)[page]
        icons = {}
        for n, b in raw.items():
            button = {**defaults, **(b or {})}
            if int(n) in INPUT_ONLY_KEYS and not (int(n) == CLOCK_KEY and (button.get('title') or button.get('icon'))):
                continue
            try:
                icons[int(n)] = render_button(int(n), button, wallpaper)
            except Exception:
                pass  # a broken key shows as text; the error is reported when the profile loads
        raw_clock = raw.get(CLOCK_KEY) or {}
        clock = clock_window_tiles(wallpaper, {
            'background': raw_clock.get('background', device.get('clock_background', '#000000')),
            'transparency': raw_clock.get('transparency', 0),
            'background_image': raw_clock.get('background_image')})
        if CLOCK_KEY in icons:
            clock[0] = icons[CLOCK_KEY]
        return {'keys': icons, 'clock': clock}

    def file_pages(self, name):
        """Page numbers of a profile file; page 1 always exists."""
        return sorted({int(p) for p in ((load_config(self.file_for(name)) or {}).get('pages') or {})} | {1})

    def set_page_settings(self, name, page, data):
        """Save a page's name and background under "page_settings:" in the profile's file."""
        if page not in self.file_pages(name):
            return t('errors.unknown_page_number', page=page)
        title = (data.get('name') or '').strip()
        if len(title) > PAGE_NAME_MAX:
            return t('errors.page_name_long', max=PAGE_NAME_MAX)
        image, color = data.get('background_image') or '', data.get('background_color') or ''
        try:
            check_background({'background_image': image, 'background_color': color})
        except ValueError as e:
            return str(e)
        values = {k: v for k, v in (('name', title), ('background_image', image), ('background_color', color)) if v}
        return self.save_file(name, set_page_settings_line(self.read_file(name), page, values))

    def move_page(self, name, page, direction):
        """Swap a page with its neighbour to the left (-1) or right (+1). Returns (new number, error)."""
        pages = self.file_pages(name)
        if page not in pages:
            return None, t('errors.unknown_page_number', page=page)
        index = pages.index(page) + direction
        if not 0 <= index < len(pages):
            return None, t('errors.page_edge')
        other = pages[index]
        error = self.save_file(name, swap_page_numbers(self.read_file(name), page, other))
        if error:
            return None, error
        if name == (self.profile or 'default') and self.page in (page, other):
            self.goto(other if self.page == page else page)   # the deck keeps showing the same page
        return other, None

    def delete_page(self, name, page):
        if page == 1:
            return t('errors.first_page')
        if page not in self.file_pages(name):
            return t('errors.unknown_page_number', page=page)
        error = self.save_file(name, remove_page(self.read_file(name), page))
        if not error and name == (self.profile or 'default') and self.page not in self.pages:
            self.goto(1)
        return error

    def profile_apps(self):
        """{profile name: app path} for every profile that names the app that activates it."""
        apps = {}
        for name in self.profile_names()[1:]:
            try:
                app = (load_config(self.profile_path(name)) or {}).get('app')
            except Exception:
                continue
            if app:
                apps[name] = os.path.normpath(app)
        return apps

    def profile_for_app(self, path):
        if not path:
            return None
        path = os.path.normpath(path)
        return next((name for name, app in self.profile_apps().items() if app == path), None)

    def set_profile_settings(self, name, data):
        """Change the app that activates a profile and/or its background (picture or color). Only given fields change."""
        path = self.file_for(name)
        with open(path) as fp:
            text = fp.read()
        if 'app' in data:
            app = data['app'] or None
            if app and name == 'default':
                return t('errors.default_no_app')
            if app:
                if not (app.endswith('.app') and os.path.isdir(app)):
                    return t('errors.not_an_app', app=app)
                other = self.profile_for_app(app)
                if other and other != name:
                    return t('errors.app_taken', app=os.path.basename(app), profile=other)
            text = set_top_line(text, 'app', app)
        for field in ('background_image', 'background_color'):
            if field in data:
                try:
                    check_background({field: data[field]})
                except ValueError as e:
                    return str(e)
                text = set_top_line(text, field, data[field] or None)
        yaml.safe_load(text)
        with open(path, 'w') as fp:
            fp.write(text)
        self.last_app = None  # re-check the frontmost app against a changed link
        if name == (self.profile or 'default'):
            self.load()
        return None

    def key_data(self, name, page, number):
        pages = (load_config(self.file_for(name)) or {}).get('pages') or {}
        return dict((pages.get(page) or {}).get(number) or {})

    def device_settings(self):
        d = self.device
        return {'screensaver': screensaver_mode(d),
                'screensaver_timeout': d.get('screensaver_timeout', 60),
                'screensaver_brightness': d.get('screensaver_brightness', 10),
                'screensaver_color': d.get('screensaver_color', '#000000'),
                'screensaver_image': d.get('screensaver_image') or '',
                'keep_alive_interval': d.get('keep_alive_interval', 1.0)}

    def ui_settings(self):
        return {'language': i18n.language(), 'languages': i18n.languages()}

    def set_ui(self, data):
        """Save the web interface settings under "ui:" in config.yaml."""
        code = data.get('language')
        if code not in [lang['code'] for lang in i18n.languages()]:
            return t('errors.unknown_language', language=code)
        with open(self.config_path) as fp:
            old = fp.read()
        with open(self.config_path, 'w') as fp:
            fp.write(replace_block_lines(old, 'ui', {'language': code}))
        if self.load():
            return None
        error = self.last_error
        with open(self.config_path, 'w') as fp:
            fp.write(old)
        self.load()
        return error

    def set_device(self, data):
        hexcolor = r'#[0-9a-fA-F]{6}'
        for field in ('screensaver_color',):
            if not re.fullmatch(hexcolor, str(data[field])):
                return t('errors.hex_color', field=field)
        if data['screensaver'] not in ('off', 'firmware', 'dim', 'color', 'image'):
            return t('errors.saver_mode')
        interval = float(data['keep_alive_interval'])
        if not 0.2 <= interval <= 10:
            return t('errors.keep_alive_range')
        timeout = int(data['screensaver_timeout'])
        if not 5 <= timeout <= 3600:
            return t('errors.saver_timeout_range')
        saver_brightness = int(data['screensaver_brightness'])
        if not 0 <= saver_brightness <= 100:
            return t('errors.saver_brightness_range')
        if data['screensaver'] == 'image' and not data['screensaver_image']:
            return t('errors.saver_image_needed')
        for field in ('screensaver_image',):
            if data[field] and not os.path.isfile(data[field]):
                return t('errors.file_missing', field=field)
        values = {'screensaver': data['screensaver'], 'screensaver_timeout': timeout,
                  'screensaver_brightness': saver_brightness, 'screensaver_color': data['screensaver_color'],
                  'screensaver_image': data['screensaver_image'], 'keep_alive_interval': interval}
        with open(self.config_path) as fp:
            old = fp.read()
        with open(self.config_path, 'w') as fp:
            fp.write(replace_block_lines(old, 'device', values))
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
            raise ValueError(t('errors.unknown_profile', name=name))
        return self.config_path if name == 'default' else self.profile_path(name)

    def read_file(self, name):
        with open(self.file_for(name)) as fp:
            return fp.read()

    def tree(self):
        result = []
        for name in self.profile_names():
            error = None
            try:
                config = load_config(self.file_for(name)) or {}
            except Exception as e:
                config, error = {}, str(e)
            pages = config.get('pages') or {}
            try:
                page_settings = page_settings_of(config)
            except ValueError as e:
                page_settings, error = {}, error or str(e)
            buttons = [{'page': int(p), 'number': int(n), 'type': (b or {}).get('type', 'text'), 'title': (b or {}).get('title')}
                       for p, keys in sorted(pages.items()) for n, b in sorted((keys or {}).items())]
            result.append({'name': name, 'buttons': buttons, 'error': error,
                           'app': config.get('app') if name != 'default' else None,
                           'background_image': config.get('background_image'),
                           'background_color': config.get('background_color'),
                           'pages': sorted({int(p) for p in pages} | {1}),
                           'page_settings': {p: {k: v for k, v in values.items() if k in ('name', 'background_image', 'background_color')}
                                             for p, values in page_settings.items()},
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
            'clock': [self.layouts[self.page][i]['icon'] for i in (13, 14)],
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
             asyncio.create_task(manager.watch_idle()),
             asyncio.create_task(manager.watch_config()),
             asyncio.create_task(manager.watch_app())]
    web_server.start(manager, asyncio.get_running_loop(), ICON_DIR, WEB_PORT)

    print("Druk op een knop (Ctrl+C om te stoppen)")
    pressed_at = {}
    async for action in deck.read_packet():
        if action and manager.wake(redraw=True):
            continue  # the press that wakes the deck does nothing else
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
