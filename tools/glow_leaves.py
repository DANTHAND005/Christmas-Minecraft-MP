#!/usr/bin/env python3
"""Christmas Critters spruce leaves: dark needles strung with glowing Christmas lights.

The old ornaments are painted out, the needles darkened a little, and a string-light pattern of dashes, dots
and plus-shaped bulbs (pink, yellow, blue, orange) is drawn on; each light twinkles on its own through the
flipbook, needles next to a light catch a faint glow, and an emissive (MER) map makes the lights truly glow
in Vibrant Visuals / RTX.

    python3 tools/glow_leaves.py              # reads the original textures from git (commit b89627e)
"""
import colorsys, io, json, math, os, subprocess, sys
from PIL import Image

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
BLOCKS = 'ChristmasCritters/ChristmasCritters_RP/textures/blocks'
ORIGINAL = 'b89627e'                         # untouched textures as received, so re-running never stacks the glow
NAMES = sys.argv[1:] or ['leaves_spruce', 'leaves_spruce_carried', 'leaves_spruce_opaque']


def original(name):
    data = subprocess.run(['git', 'show', '%s:%s/%s.png' % (ORIGINAL, BLOCKS, name)], cwd=ROOT, capture_output=True, check=True).stdout
    return Image.open(io.BytesIO(data)).convert('RGBA')


def kind(p):
    """'O' coloured ornament, 'W' white ornament, 'h' its soft halo, 'L' plain needle, '.' gap."""
    r, g, b, a = p
    if not a: return '.'
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    if s < 0.22 and v >= 0.55: return 'W'
    if s >= 0.5 and v >= 0.35 and not (0.22 < h < 0.45 and v < 0.55): return 'O'
    return 'L' if s < 0.5 else 'h'


def plain_needles(frame, dark=0.6):
    """The leaves with the old ornaments painted out (each takes a nearby needle colour), slightly darkened."""
    out = frame.copy()
    kinds = {(x, y): kind(frame.getpixel((x, y))) for x in range(16) for y in range(16)}
    for (x, y), k in kinds.items():
        if k in 'OWh':
            near = [frame.getpixel(((x + dx) % 16, (y + dy) % 16)) for dx in range(-2, 3) for dy in range(-2, 3)
                    if kinds[((x + dx) % 16, (y + dy) % 16)] == 'L']
            out.putpixel((x, y), min(near, key=lambda c: sum(c[:3])) if near else (25, 39, 25, 255))
    for x in range(16):
        for y in range(16):
            r, g, b, a = out.getpixel((x, y))
            out.putpixel((x, y), (round(r * dark), round(g * dark), round(b * dark), a))
    return out


# String-light pattern: little horizontal dashes, single dots and a couple of plus-shaped bulbs, spread so tiles
# sit next to each other without clumping. (x, y, shape, colour)
COLOURS = {'pink': (255, 92, 132), 'yellow': (255, 214, 58), 'blue': (104, 178, 246), 'orange': (255, 160, 36)}
LIGHTS = [(4, 4, 'plus', 'blue'), (11, 11, 'plus', 'orange'), (9, 2, 'dash', 'yellow'), (13, 6, 'dash', 'pink'),
          (1, 10, 'dash', 'pink'), (6, 13, 'dash', 'yellow'), (14, 14, 'dot', 'blue'), (7, 8, 'dot', 'pink'),
          (0, 1, 'dot', 'yellow'), (12, 1, 'dot', 'blue'), (3, 15, 'dot', 'orange'), (9, 6, 'dash', 'blue')]
SHAPES = {'plus': [(0, 0, 1.0), (1, 0, 0.88), (-1, 0, 0.88), (0, 1, 0.88), (0, -1, 0.88)],
          'dash': [(0, 0, 1.0), (1, 0, 0.92)], 'dot': [(0, 0, 1.0)]}


def lights(base, f, n):
    """Draw the string lights onto clean needles for twinkle frame f of n; returns (colour, MER)."""
    out, mer = base.copy(), Image.new('RGBA', (16, 16), (0, 0, 0, 255))
    lit = {}
    for i, (x, y, shape, name) in enumerate(LIGHTS):
        k = 1.0 if n == 1 else 0.88 + 0.12 * math.sin(2 * math.pi * f / n + i * 2.399)   # each light twinkles on its own
        c = COLOURS[name]
        for dx, dy, w in SHAPES[shape]:
            t = 0.35 if (dx, dy) == (0, 0) and shape == 'plus' else 0.0                 # plus bulbs have a pale centre
            col = tuple(min(255, round((v + (255 - v) * t) * w * k)) for v in c)
            lit[((x + dx) % 16, (y + dy) % 16)] = (col, w * k)
    for (x, y), (col, e) in lit.items():
        out.putpixel((x, y), col + (255,))
        mer.putpixel((x, y), (0, round(255 * min(1, e)), 210, 255))                   # R metalness, G emissive, B roughness
    for (x, y), (col, e) in lit.items():                                               # needles touching a light catch a faint glow
        for q in (((x + 1) % 16, y), ((x - 1) % 16, y), (x, (y + 1) % 16), (x, (y - 1) % 16)):
            if q in lit: continue
            r, g, b, a = out.getpixel(q)
            if a:
                out.putpixel(q, tuple(min(255, round(v + cv * 0.14 * e)) for v, cv in zip((r, g, b), col)) + (a,))
                mer.putpixel(q, (0, max(mer.getpixel(q)[1], round(255 * 0.18 * e)), 210, 255))
    return out, mer


def main():
    for name in NAMES:
        src = original(name)
        n = src.height // 16
        base = plain_needles(src.crop((0, 0, 16, 16)))
        col, mer = Image.new('RGBA', src.size), Image.new('RGBA', src.size)
        for i in range(n):
            c, m = lights(base, i, n)
            col.paste(c, (0, i * 16)); mer.paste(m, (0, i * 16))
        col.save(os.path.join(ROOT, BLOCKS, name + '.png'))
        mer.save(os.path.join(ROOT, BLOCKS, name + '_mer.png'))
        ts = {'format_version': '1.16.100', 'minecraft:texture_set': {'color': name, 'metalness_emissive_roughness': name + '_mer'}}
        json.dump(ts, open(os.path.join(ROOT, BLOCKS, name + '.texture_set.json'), 'w'))
        print('%-22s %2d frame(s)' % (name, n))


if __name__ == '__main__':
    main()
