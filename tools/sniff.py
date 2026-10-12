# Print raw HID input packets from the deck, to discover unknown events (e.g. knob rotation).
import sys, time, binascii
import hid
from strmdck.devices.ulanzi_d200 import UlanziD200Device


def open_deck():
    for d in hid.enumerate(UlanziD200Device.USB_VENDOR_ID, UlanziD200Device.USB_PRODUCT_ID):
        if (d['usage_page'], d['usage']) == (0x1, 0x6):
            continue
        try:
            dev = hid.device()
            dev.open_path(d['path'])
            dev.set_nonblocking(True)
            return dev
        except OSError:
            continue
    return None


duration = float(sys.argv[1]) if len(sys.argv) > 1 else 60
end = time.time() + duration
dev = None
while time.time() < end:
    if dev is None:
        dev = open_deck()
        if dev is None:
            time.sleep(0.5)
            continue
        print("listening", flush=True)
    try:
        inp = dev.read(1024)
    except OSError:
        print("read error, reconnecting", flush=True)
        dev = None
        continue
    if inp:
        print(f"{time.time():.2f}", binascii.hexlify(bytes(inp[:24])).decode(), flush=True)
    else:
        time.sleep(0.01)
