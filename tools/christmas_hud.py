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
XP_W, XP_FRAMES = 91, 20                          # one rainbow frame (stretched over the bar), frames laid side by side
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
    # experience bar: a smooth rainbow, stacked as XP_FRAMES frames that each shift the hues a little further;
    # ui/hud_screen.json scrolls through them (flip_book) and fades the level number through the same colours
    import colorsys
    bar = Image.new('RGBA', (XP_W * XP_FRAMES, 5))                   # flip_book steps sideways, like vanilla auto_save
    for f in range(XP_FRAMES):
        for x in range(XP_W):
            r, g, b = colorsys.hsv_to_rgb((x / XP_W - f / XP_FRAMES) % 1.0, 0.85, 1.0)
            for y, k in enumerate((1.25, 1.1, 1.0, 0.88, 0.7)):        # glossy: light top edge, darker bottom
                bar.putpixel((f * XP_W + x, y), tuple(min(255, round(c * 255 * k)) for c in (r, g, b)) + (255,))
    save(bar, 'experiencebarfull')
    with open(os.path.join(OUT, 'experiencebarfull.json'), 'w') as fh:   # no nine-slicing: one frame spans the bar
        fh.write('{ "nineslice_size": 0, "base_size": [ %d, 5 ] }\n' % XP_W)
    print('wrote Christmas HUD textures to', os.path.relpath(OUT, ROOT))


if __name__ == '__main__':
    main()
