"""Draw the app icon of D200X Manager.app: the deck seen from above, a grid of keys on a dark tile.
Writes an .iconset folder for iconutil: python make_icon.py <out.iconset>"""
import os
import sys

from PIL import Image, ImageDraw

S = 1024
KEYS = [  # (column, row) -> color; the others are dark keys
    ((0, 0), (108, 140, 255)), ((2, 0), (255, 99, 99)), ((4, 1), (80, 200, 140)), ((1, 2), (255, 180, 60)),
]


def draw():
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    # the macOS icon grid: an 824 px rounded square in a 1024 canvas, with a soft shadow
    shadow = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([100, 118, 924, 942], radius=185, fill=(0, 0, 0, 90))
    from PIL import ImageFilter
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)))
    tile = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    grad = Image.new('RGBA', (1, 824))
    for y in range(824):
        f = y / 823
        grad.putpixel((0, y), (round(46 - 22 * f), round(46 - 22 * f), round(60 - 26 * f), 255))
    mask = Image.new('L', (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([100, 100, 924, 924], radius=185, fill=255)
    tile.paste(grad.resize((824, 824)), (100, 100))
    img.paste(tile, (0, 0), mask)
    d = ImageDraw.Draw(img)
    # 5 x 3 keys, as on the D200X
    cols, rows, key, gap = 5, 3, 118, 28
    x0 = (S - (cols * key + (cols - 1) * gap)) // 2
    y0 = 300
    colors = dict(KEYS)
    for r in range(rows):
        for c in range(cols):
            x, y = x0 + c * (key + gap), y0 + r * (key + gap)
            color = colors.get((c, r))
            d.rounded_rectangle([x, y, x + key, y + key], radius=26,
                                fill=color + (255,) if color else (66, 66, 84, 255))
            if color:   # a light top edge on the lit keys
                d.rounded_rectangle([x + 10, y + 8, x + key - 10, y + 22], radius=7, fill=(255, 255, 255, 70))
    # the bar above the keys
    d.rounded_rectangle([x0, 196, S - x0, 238], radius=21, fill=(90, 90, 110, 255))
    return img


if __name__ == '__main__':
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    big = draw()
    for size in (16, 32, 128, 256, 512):
        big.resize((size, size), Image.LANCZOS).save(os.path.join(out, f'icon_{size}x{size}.png'))
        big.resize((size * 2, size * 2), Image.LANCZOS).save(os.path.join(out, f'icon_{size}x{size}@2x.png'))
