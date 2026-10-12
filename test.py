import asyncio
import os
from PIL import Image, ImageDraw
import hid
from strmdck.devices.ulanzi_d200 import UlanziD200Device

ICON_DIR = os.path.join('.cache', 'icons', '_generated')


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
            return UlanziD200Device(dev)
        except OSError:
            continue
    return None


async def main():
    deck = connect()
    if deck is None:
        raise SystemExit("No Ulanzi D200 found")

    # Render an icon where strmdck expects it (196x196)
    os.makedirs(ICON_DIR, exist_ok=True)
    img = Image.new('RGB', (196, 196), color='#1a1a2e')
    ImageDraw.Draw(img).text((60, 90), "Hello!", fill='white')
    img.save(os.path.join(ICON_DIR, 'hello.png'))

    deck.set_brightness(80)
    deck.set_buttons({0: {'name': 'Hello', 'icon': 'hello.png'}})

    # Listen for key events
    async for action in deck.read_packet():
        if action:
            print(f"Key {action.index}: {'down' if action.pressed else 'up'}")

asyncio.run(main())
