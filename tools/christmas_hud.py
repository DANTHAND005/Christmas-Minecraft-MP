#!/usr/bin/env python3
"""Christmas HUD for the Christmas Textures pack: peppermint hearts, candy-cane hunger, candy-cane hotbar.

Writes textures/ui/*.png into the Christmas Textures resource pack. The hotbar slot textures are built on
top of the vanilla ones, fetched from Mojang's bedrock-samples, so the slot backgrounds stay the same.

    python3 tools/christmas_hud.py
"""
import io, os, urllib.request
from PIL import Image

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUT = os.path.join(ROOT, 'ChristmasTextures/ChristmasTextures_RP/textures/ui')
VANILLA = 'https://raw.githubusercontent.com/Mojang/bedrock-samples/main/resource_pack/textures/ui/%s.png'

RED, WHITE, DARK_RED = (214, 28, 40), (248, 248, 244), (150, 14, 24)
GREEN, DARK_GREEN = (40, 178, 74), (18, 110, 44)
OUTLINE, HOLLOW = (26, 14, 16), (128, 118, 122)   # empty icons: pale grey 'used up' shape, dark outline

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


def shade(c, k):
    return tuple(max(0, min(255, round(v * k))) for v in c)


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

    # armour: a green Christmas sweater strung with rainbow lights (full), half lit / half grey, and grey when empty
    SWEATER = ['.##...##.',
               '#cc#.#cc#',
               '#ggg#ggg#',
               '#LgLgLgL#',
               '.#ggggg#.',
               '.#LgLgL#.',
               '.#ggggg#.',
               '.#wwwww#.',
               '..#####..']
    rainbow = [(255, 52, 52), (255, 150, 30), (255, 230, 40), (60, 230, 80), (60, 150, 255), (190, 90, 255), (255, 120, 200)]
    def sweater(lit_cols):
        img, k = Image.new('RGBA', (9, 9), (0, 0, 0, 0)), 0
        for y, row in enumerate(SWEATER):
            for x, ch in enumerate(row):
                if ch == '.': continue
                lit = x in lit_cols
                if ch == '#': c = OUTLINE
                elif ch == 'L':
                    c = rainbow[k % len(rainbow)] if lit else (70, 70, 74); k += 1
                elif ch in 'cw': c = WHITE if lit else (150, 150, 154)
                else: c = ((34, 140, 62) if (x + y) % 2 else (28, 120, 52)) if lit else (104, 104, 108)
                img.putpixel((x, y), c + (255,))
        if lit_cols == range(0, 4):                                    # half: dark seam down the middle like vanilla
            for y in range(2, 8): img.putpixel((4, y), OUTLINE + (255,))
        return img
    save(sweater(range(9)), 'armor_full')
    save(sweater(range(0, 4)), 'armor_half')
    save(sweater(()), 'armor_empty')
    # experience bar: icy blue with snow along the top (vanilla sizes; vanilla nine-slicing stretches the middle)
    ICE = [(250, 252, 255), (214, 236, 255), (140, 200, 248), (104, 172, 236), (70, 132, 206)]   # top row = snow
    full = Image.new('RGBA', (13, 5))
    for x in range(13):
        for y in range(5):
            c = ICE[y]
            if x in (0, 12): c = shade(c, 0.8)
            full.putpixel((x, y), c + (255,))
    save(full, 'experiencebarfull')
    empty = Image.new('RGBA', (13, 5))
    for x in range(13):
        for y in range(5):
            c = [(150, 166, 190), (40, 52, 82), (30, 40, 66), (26, 34, 58), (20, 26, 46)][y]   # dusted with snow on top
            if x in (0, 12): c = (16, 20, 36)
            empty.putpixel((x, y), c + (255,))
    save(empty, 'experiencebarempty')
    # a little strip of snow that sits on top of the level number (tiled across the digits, see ui/hud_screen.json)
    cap = Image.new('RGBA', (6, 3), (0, 0, 0, 0))
    for x, y, c in ((0, 1, 'w'), (1, 0, 'w'), (2, 0, 'w'), (3, 1, 'w'), (4, 0, 'w'), (5, 1, 'w'),
                    (0, 2, 'b'), (1, 1, 'w'), (2, 1, 'w'), (3, 2, 'b'), (4, 1, 'w'), (5, 2, 'b'), (1, 2, 'b'), (4, 2, 'b')):
        cap.putpixel((x, y), ((255, 255, 255) if c == 'w' else (196, 226, 255)) + (255,))
    save(cap, 'xp_snow_cap')
    print('wrote Christmas HUD textures to', os.path.relpath(OUT, ROOT))


if __name__ == '__main__':
    main()
