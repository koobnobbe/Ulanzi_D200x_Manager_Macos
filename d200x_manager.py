import asyncio
import binascii
import os
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

IN_BUTTON = b'\x01\x01'
KIND_BUTTON = 0x01
KIND_KNOB = 0x02
# Value byte of a knob event -> config field. 0x00 (release) is ignored;
# anything else is printed raw.
KNOB_RELEASE = 0x00
KNOB_EVENTS = {0x01: 'press', 0x02: 'left', 0x03: 'right'}


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


def render_solid(color):
    name = f'solid_{color.lstrip("#")}.png'
    Image.new('RGB', (SIZE, SIZE), color=color).save(os.path.join(ICON_DIR, name))
    return name


def render_button(number, button):
    name = f'button_{number}.png'
    if button.get('icon'):
        img = Image.open(button['icon']).convert('RGB').resize((SIZE, SIZE))
    else:
        img = Image.new('RGB', (SIZE, SIZE), color=button['background'])
        draw = ImageDraw.Draw(img)
        draw.text((SIZE / 2, SIZE / 2), str(button.get('text', '')),
                  font=load_font(button['font_size']), fill=button['color'], anchor='mm')
    img.save(os.path.join(ICON_DIR, name))
    return name


async def keep_alive(deck, interval=1.0):
    # Without regular host traffic the deck switches to its screensaver after
    # ~30s. Ulanzi Studio pushes the small-window clock every second; do the same.
    while True:
        deck.keep_alive()
        await asyncio.sleep(interval)


async def main():
    config = load_config(sys.argv[1] if len(sys.argv) > 1 else CONFIG_PATH)
    device = config.get('device', {})
    defaults = config.get('button_defaults', {})
    # Config keys are numbered from 1; the deck index is number - 1
    # (left-to-right, top-to-bottom, index = row * 5 + col).
    buttons = {int(n): {**defaults, **(b or {})} for n, b in config.get('buttons', {}).items()}
    knobs = {k['index']: k for k in config.get('knobs', {}).values()}

    deck = connect()
    if deck is None:
        raise SystemExit("No Ulanzi D200 found")

    os.makedirs(ICON_DIR, exist_ok=True)

    layout = {number - 1: {'icon': render_button(number, b)} for number, b in buttons.items()}
    # Slots 13 and 14 (cols 3-4 of the bottom row) are the clock window. Give them
    # a solid background so the deck's default image doesn't show behind the time.
    clock = render_solid(device.get('clock_background', '#000000'))
    for i in range(UlanziD200Device.BUTTON_COUNT, UlanziD200Device.BUTTON_ROWS * UlanziD200Device.BUTTON_COLS):
        layout[i] = {'icon': clock}

    deck.set_brightness(device.get('brightness', 80))
    deck.set_buttons(layout)
    keep_alive_task = asyncio.create_task(  # keep a reference so it isn't GC'd
        keep_alive(deck, device.get('keep_alive_interval', 1.0)))

    print("Druk op een knop (Ctrl+C om te stoppen)")
    async for action in deck.read_packet():
        if isinstance(action, KnobAction):
            if action.value == KNOB_RELEASE:
                continue
            knob = knobs.get(action.index)
            event = KNOB_EVENTS.get(action.value)
            if knob is None or event is None:
                print(f'knob 0x{action.index:02x} value 0x{action.value:02x}')
            elif knob.get(event):
                print(knob[event])
        elif action and action.pressed:
            button = buttons.get(action.index + 1)
            if button and button.get('output'):
                print(button['output'])

asyncio.run(main())
