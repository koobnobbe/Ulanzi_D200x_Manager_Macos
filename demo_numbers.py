import asyncio
import binascii
import os
from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageFont
import hid
from strmdck.device import ButtonAction
from strmdck.devices.ulanzi_d200 import UlanziD200Device

ICON_DIR = os.path.join('.cache', 'icons', '_generated')
SIZE = UlanziD200Device.ICON_WIDTH  # 196x196

IN_BUTTON = b'\x01\x01'
KIND_BUTTON = 0x01
KIND_KNOB = 0x02
# Value byte of a knob event: 0x01/0x00 press/release, 0x02 counter-clockwise,
# 0x03 clockwise. Anything else is printed raw.
KNOB_PRESS = 0x01
KNOB_RELEASE = 0x00
KNOB_DIRECTION = {0x02: '<-', 0x03: '->'}
# Index byte of a knob event -> knob name. Only 0x11 (left knob) has been seen;
# the other two are assumed to follow it. Unknown indices are printed raw.
KNOB_NAMES = {0x11: 'K1', 0x12: 'K2', 0x13: 'K3'}


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


def render_black():
    name = 'black.png'
    Image.new('RGB', (SIZE, SIZE), color='black').save(os.path.join(ICON_DIR, name))
    return name


def render_number(number):
    img = Image.new('RGB', (SIZE, SIZE), color='#1a1a2e')
    draw = ImageDraw.Draw(img)
    draw.text((SIZE / 2, SIZE / 2), str(number), font=load_font(110), fill='white', anchor='mm')
    name = f'num_{number}.png'
    img.save(os.path.join(ICON_DIR, name))
    return name


async def keep_alive(deck, interval=1.0):
    # Without regular host traffic the deck switches to its screensaver after
    # ~30s. Ulanzi Studio pushes the small-window clock every second; do the same.
    while True:
        deck.keep_alive()
        await asyncio.sleep(interval)


async def main():
    deck = connect()
    if deck is None:
        raise SystemExit("No Ulanzi D200 found")

    os.makedirs(ICON_DIR, exist_ok=True)

    # Button index runs left-to-right, top-to-bottom (index = row * 5 + col),
    # so the number shown is simply index + 1.
    buttons = {i: {'icon': render_number(i + 1)} for i in range(UlanziD200Device.BUTTON_COUNT)}
    # Slots 13 and 14 (cols 3-4 of the bottom row) are the clock window. Give them
    # a black background so the deck's default image doesn't show behind the time.
    black = render_black()
    for i in range(UlanziD200Device.BUTTON_COUNT, UlanziD200Device.BUTTON_ROWS * UlanziD200Device.BUTTON_COLS):
        buttons[i] = {'icon': black}

    deck.set_brightness(80)
    deck.set_buttons(buttons)
    keep_alive_task = asyncio.create_task(keep_alive(deck))  # keep a reference so it isn't GC'd

    print("Druk op een knop (Ctrl+C om te stoppen)")
    async for action in deck.read_packet():
        if isinstance(action, KnobAction):
            name = KNOB_NAMES.get(action.index, f'knob 0x{action.index:02x}')
            if action.value == KNOB_PRESS:
                print(f'{name} press')
            elif action.value != KNOB_RELEASE:
                direction = KNOB_DIRECTION.get(action.value, f'value 0x{action.value:02x}')
                print(f'{name} {direction}')
        elif action and action.pressed:
            print(action.index + 1)

asyncio.run(main())
