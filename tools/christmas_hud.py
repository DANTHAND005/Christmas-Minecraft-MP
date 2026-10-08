#!/usr/bin/env python3
"""Christmas HUD for Christmas Critters: peppermint hearts, candy-cane hunger, candy-cane hotbar.

Writes textures/ui/*.png into the Christmas Critters resource pack. The hotbar slot textures are built on
top of the vanilla ones, fetched from Mojang's bedrock-samples, so the slot backgrounds stay the same.

    python3 tools/christmas_hud.py
"""
import io, os, urllib.request
from PIL import Image

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUT = os.path.join(ROOT, 'ChristmasCritters/ChristmasCritters_RP/textures/ui')
VANILLA = 'https://raw.githubusercontent.com/Mojang/bedrock-samples/main/resource_pack/textures/ui/%s.png'

RED, WHITE, DARK_RED = (214, 28, 40), (248, 248, 244), (150, 14, 24)
GREEN, DARK_GREEN = (40, 178, 74), (18, 110, 44)
OUTLINE, HOLLOW = (22, 10, 12), (52, 40, 42)

HEART = ['.........',
         '..##.##..',
         '.#######.',
         '.#######.',
         '.#######.',
         '..#####..',
         '...###...',
         '....#....',
         '.........']
CANE = ['.........',            # hook top-left, shaft down the right; drawn 2 px thick
        '...###...',
        '..#####..',
        '..##.##..',
        '..#..##..',
        '.....##..',
        '.....##..',
        '.....##..',
        '.....##..']


def vanilla(name):
    with urllib.request.urlopen(VANILLA % name, timeout=60) as r:
        return Image.open(io.BytesIO(r.read())).convert('RGBA')


def mask(rows, keep=lambda x, y: True):
    return {(x, y) for y, row in enumerate(rows) for x, ch in enumerate(row) if ch == '#' and keep(x, y)}


def stripes(pix, a, b, light=0.0, size=9, width=2):
    """Diagonal two-colour candy stripes over the given pixels; light > 0 brightens (flash frames)."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    for x, y in pix:
        c = a if ((x + y) // width) % 2 == 0 else b
        img.putpixel((x, y), tuple(round(v + (255 - v) * light) for v in c) + (255,))
    return img


def outline(pix, size=9):
    """Empty slot: dark outline around a hollow shape (like the vanilla empty heart / drumstick)."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    grown = {(x + dx, y + dy) for x, y in pix for dx in (-1, 0, 1) for dy in (-1, 0, 1)
             if 0 <= x + dx < size and 0 <= y + dy < size and (dx == 0 or dy == 0)}
    for p in grown:
        img.putpixel(p, (HOLLOW if p in pix else OUTLINE) + (255,))
    return img


def shine(img, p):
    img.putpixel(p, (255, 255, 255, 255))
    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    save = lambda img, name: img.save(os.path.join(OUT, name + '.png'))

    # hearts: peppermint stripes, white glint top-left; half hearts keep the left side like vanilla
    heart, half = mask(HEART), mask(HEART, lambda x, y: x <= 4)
    save(shine(stripes(heart, RED, WHITE), (2, 2)), 'heart')
    save(shine(stripes(half, RED, WHITE), (2, 2)), 'heart_half')
    save(stripes(heart, RED, WHITE, light=0.55), 'heart_flash')
    save(stripes(half, RED, WHITE, light=0.55), 'heart_flash_half')
    save(outline(heart), 'heart_background')

    # hunger: candy canes; a half shank keeps the shaft (right side); the Hunger effect turns them mint green
    cane, cane_half = mask(CANE), mask(CANE, lambda x, y: x >= 5)
    for prefix, (a, b) in (('hunger', (RED, WHITE)), ('hunger_effect', (GREEN, WHITE))):
        save(stripes(cane, a, b), prefix + '_full')
        save(stripes(cane_half, a, b), prefix + '_half')
        save(stripes(cane, a, b, light=0.55), prefix + '_flash_full')
        save(stripes(cane_half, a, b, light=0.55), prefix + '_flash_half')
        save(outline(cane), prefix + '_background')

    # hotbar: the grey frame of every slot becomes candy stripes, continuous across all nine slots
    for i in range(9):
        slot = vanilla('hotbar_%d' % i)
        for y in range(1, 21):
            for x in range(20):
                if y in (1, 2, 19, 20) or x in (0, 1, 18, 19):
                    gx = i * 20 + x
                    c = RED if ((gx + y) // 2) % 2 == 0 else WHITE
                    if y in (2, 19) or x in (1, 18):           # inner edge a shade darker for depth
                        c = DARK_RED if c == RED else (214, 210, 206)
                    slot.putpixel((x, y), c + (255,))
        save(slot, 'hotbar_%d' % i)
    # selected slot: thick mint-green and white candy frame so it stands out from the red ones
    sel = vanilla('selected_hotbar_slot')
    for y in range(24):
        for x in range(24):
            r, g, b, a = sel.getpixel((x, y))
            if a and not (x in (0, 23) or y in (0, 23)):
                c = GREEN if ((x + y) // 2) % 2 == 0 else WHITE
                sel.putpixel((x, y), (c if not (x in (3, 20) or y in (3, 20)) else (DARK_GREEN if c == GREEN else (220, 226, 220))) + (255,))
    save(sel, 'selected_hotbar_slot')
    print('wrote Christmas HUD textures to', os.path.relpath(OUT, ROOT))


if __name__ == '__main__':
    main()
