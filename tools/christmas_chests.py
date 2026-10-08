#!/usr/bin/env python3
"""Gift-wrapped chests for the Christmas Textures pack.

Chest = red with a gold ribbon (a double chest is one big present), trapped chest = green with a red ribbon,
ender chest = purple with a white ribbon. Ribbons line up across the lid, sides and bottom so they wrap the
whole box, the lid gets a bow, the latch becomes the ribbon knot and the insides stay dark. Inventory icons
match. (Placed chests use one fixed texture per chest type, so every chest of a type looks the same.)

    python3 tools/christmas_chests.py
"""
import os
from PIL import Image

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
RP = os.path.join(ROOT, 'ChristmasTextures/ChristmasTextures_RP/textures')
GIFTS = {   # name: (wrap colour, ribbon colour)
    'normal': ((178, 30, 36), (240, 194, 52)),
    'trapped': ((48, 120, 40), (204, 32, 38)),
    'ender': ((116, 52, 158), (240, 240, 236)),
}


def shade(c, k):
    return tuple(max(0, min(255, round(v * k))) for v in c)


def faces(w):
    """(x, y, width, height, kind) of every face of a chest texture whose box is w px wide (14 single, 30 double)."""
    d, L = 14, w + 14
    out = [(0, 0, 6, 5, 'latch'), (d, 0, w, d, 'top'), (d + w, 0, w, d, 'inside'),
           (d, 19, w, d, 'inside'), (d + w, 19, w, d, 'bottom')]
    for y, h in ((14, 5), (33, 10)):            # lid sides, base sides: west, front, east, back
        out += [(0, y, d, h, 'side'), (d, y, w, h, 'long'), (d + w, y, d, h, 'side'), (L + d, y, w, h, 'long')]
    return out


def paint(w, wrap, ribbon):
    img = Image.new('RGBA', (64 if w == 14 else 128, 64), (0, 0, 0, 0))
    for fx, fy, fw, fh, kind in faces(w):
        for x in range(fw):
            for y in range(fh):
                edge = x in (0, fw - 1) or y in (0, fh - 1)
                if kind == 'inside':
                    c = shade(wrap, 0.3 if not edge else 0.45)
                elif kind == 'latch':
                    c = shade(ribbon, 0.8 if edge else 1.05)
                else:
                    c = shade(wrap, 1.12 if (x + 2 * y) % 5 == 0 else 0.9 if (x - y) % 4 == 0 else 1.0)   # knitted paper
                    band_x = abs(x - (fw - 1) / 2) < 1                                                       # ribbon down the middle
                    band_y = kind in ('top', 'bottom') and abs(y - (fh - 1) / 2) < 1                         # and across the top / bottom
                    if band_x or band_y:
                        c = shade(ribbon, 0.85 if (x + y) % 3 == 0 else 1.0)
                    if edge:
                        c = shade(c, 0.6)
                img.putpixel((fx + x, fy + y), c + (255,))
        if kind == 'top':                          # bow on the lid
            cx, cy = fx + fw // 2, fy + fh // 2
            for dx, dy in ((-3, -1), (-2, -2), (-2, -1), (-2, 0), (-3, 0), (2, -1), (1, -2), (1, -1), (1, 0), (2, 0),
                           (-1, -1), (0, -1), (-1, 0), (0, 0), (-2, 1), (1, 1)):
                img.putpixel((cx + dx, cy + dy), shade(ribbon, 1.1 if dx in (-1, 0) else 1.0) + (255,))
    return img


def icon(wrap, ribbon, part):
    """16x16 inventory icon faces."""
    img = Image.new('RGBA', (16, 16))
    for x in range(16):
        for y in range(16):
            c = shade(wrap, 1.12 if (x + 2 * y) % 5 == 0 else 0.9 if (x - y) % 4 == 0 else 1.0)
            if 7 <= x <= 8 or (part == 'top' and 7 <= y <= 8):
                c = ribbon
            if part != 'top' and y == 5:
                c = shade(wrap, 0.55)                  # lid seam
            if x in (0, 15) or y in (0, 15):
                c = shade(c, 0.6)
            img.putpixel((x, y), c + (255,))
    if part == 'front':
        for x, y in ((6, 4), (7, 4), (8, 4), (9, 4), (6, 5), (9, 5), (7, 6), (8, 6)):   # ribbon knot where the latch is
            img.putpixel((x, y), shade(ribbon, 1.1) + (255,))
    if part == 'top':
        for x, y in ((5, 6), (6, 5), (6, 6), (9, 5), (9, 6), (10, 6)):
            img.putpixel((x, y), shade(ribbon, 1.1) + (255,))
    return img


def main():
    os.makedirs(os.path.join(RP, 'entity/chest'), exist_ok=True)
    os.makedirs(os.path.join(RP, 'blocks'), exist_ok=True)
    out = lambda img, rel: img.save(os.path.join(RP, rel + '.png'))
    for name, (wrap, ribbon) in GIFTS.items():
        out(paint(14, wrap, ribbon), 'entity/chest/' + name)
        if name != 'ender':
            out(paint(30, wrap, ribbon), 'entity/chest/' + ('double_normal' if name == 'normal' else 'trapped_double'))
    wrap, ribbon = GIFTS['normal']
    for part in ('top', 'side', 'front'):
        out(icon(wrap, ribbon, part), 'blocks/chest_' + part)
    out(icon(wrap, GIFTS['trapped'][0], 'front'), 'blocks/trapped_chest_front')   # same red gift, green ribbon on the front
    wrap, ribbon = GIFTS['ender']
    for part in ('top', 'side', 'front'):
        out(icon(wrap, ribbon, part), 'blocks/ender_chest_' + part)
    print('wrote gift chest textures')


if __name__ == '__main__':
    main()
