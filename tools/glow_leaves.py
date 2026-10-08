#!/usr/bin/env python3
"""Christmas Critters spruce leaves: dark needles strung with glowing Christmas lights.

The old ornaments are painted out, the needles darkened a little, and a string-light pattern of dashes, dots
and plus-shaped bulbs (pink, yellow, blue, orange) is drawn on; each light twinkles on its own through the
flipbook, needles next to a light catch a faint glow, and an emissive (MER) map makes the lights truly glow
in Vibrant Visuals / RTX.

    python3 tools/glow_leaves.py              # reads the original textures from git (commit b89627e)
"""
import colorsys, io, json, math, os, random, subprocess, sys
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
    def needle(p):                                 # true needle green; anything else is an old ornament or its halo
        if not p[3]: return False
        h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in p[:3]))
        return 0.28 <= h <= 0.45 and s <= 0.45
    kinds = {(x, y): ('L' if needle(frame.getpixel((x, y))) else 'O' if frame.getpixel((x, y))[3] else '.')
             for x in range(16) for y in range(16)}
    for (x, y), k in kinds.items():
        if k == 'O':
            near = [frame.getpixel(((x + dx) % 16, (y + dy) % 16)) for dx in range(-2, 3) for dy in range(-2, 3)
                    if kinds[((x + dx) % 16, (y + dy) % 16)] == 'L']
            out.putpixel((x, y), min(near, key=lambda c: sum(c[:3])) if near else (25, 39, 25, 255))
    for x in range(16):
        for y in range(16):
            r, g, b, a = out.getpixel((x, y))
            out.putpixel((x, y), (round(r * dark), round(g * dark), round(b * dark), a))
    return out


COLOURS = {'pink': (255, 92, 132), 'yellow': (255, 214, 58), 'blue': (104, 178, 246), 'orange': (255, 160, 36)}
SHAPES = {'plus': [(0, 0, 1.0), (1, 0, 0.88), (-1, 0, 0.88), (0, 1, 0.88), (0, -1, 0.88)],
          'dash': [(0, 0, 1.0), (1, 0, 0.92)], 'dot': [(0, 0, 1.0)]}
VARIANTS = 6                                   # Minecraft picks one of these at random for every spruce leaf block


def pattern(seed):
    """Random string-light layout for one variant: 1-2 plus bulbs, 3-5 dashes, 2-4 dots, never touching
    (the tile wraps, so spacing is checked across the edges too)."""
    rnd = random.Random(seed)
    want = ['plus'] * rnd.randint(1, 2) + ['dash'] * rnd.randint(3, 5) + ['dot'] * rnd.randint(2, 4)
    taken, out = set(), []
    for shape in want:
        for _ in range(200):
            x, y = rnd.randrange(16), rnd.randrange(16)
            pix = {((x + dx) % 16, (y + dy) % 16) for dx, dy, _ in SHAPES[shape]}
            if all((((px + ax) % 16, (py + ay) % 16) not in taken) for px, py in pix for ax in (-1, 0, 1) for ay in (-1, 0, 1)):
                taken |= pix
                out.append((x, y, shape, rnd.choice(list(COLOURS)), rnd.uniform(0, 2 * math.pi)))
                break
    return out


def lights(base, layout, f, n):
    """Draw one layout onto clean needles for twinkle frame f of n; returns (colour, MER)."""
    out, mer = base.copy(), Image.new('RGBA', (16, 16), (0, 0, 0, 255))
    lit = {}
    for x, y, shape, name, phase in layout:
        k = 1.0 if n == 1 else 0.86 + 0.14 * math.sin(2 * math.pi * f / n + phase)   # each light twinkles on its own
        c = COLOURS[name]
        for dx, dy, w in SHAPES[shape]:
            centre = (dx, dy) == (0, 0)
            t = (0.4 if shape == 'plus' else 0.18 * max(0.0, (k - 0.93) / 0.07)) if centre else 0.0   # white shine
            col = tuple(min(255, round((v + (255 - v) * t) * w * k)) for v in c)
            lit[((x + dx) % 16, (y + dy) % 16)] = (col, w * k)
    for (x, y), (col, e) in lit.items():
        out.putpixel((x, y), col + (255,))
        mer.putpixel((x, y), (0, round(255 * min(1, e)), 210, 255))                   # R metalness, G emissive, B roughness
    glow = {}
    for (x, y), (col, e) in lit.items():                                               # light spills onto the needles around it
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                q = ((x + dx) % 16, (y + dy) % 16)
                if q in lit: continue
                w = (0.2 if dx == 0 or dy == 0 else 0.07) * e
                g = glow.setdefault(q, [0.0, 0.0, 0.0, 0.0])
                for i in range(3): g[i] += col[i] * w
                g[3] = max(g[3], w)
    for q, (gr, gg, gb, w) in glow.items():
        r, g, b, a = out.getpixel(q)
        if a:                                                                          # never fills gaps, so outlines stay the same
            out.putpixel(q, (min(255, round(r + gr)), min(255, round(g + gg)), min(255, round(b + gb)), a))
            mer.putpixel(q, (0, round(255 * min(1, w * 1.2)), 210, 255))
    return out, mer


def save(img, mer, name):
    img.save(os.path.join(ROOT, BLOCKS, name + '.png'))
    mer.save(os.path.join(ROOT, BLOCKS, name + '_mer.png'))
    ts = {'format_version': '1.16.100', 'minecraft:texture_set': {'color': name, 'metalness_emissive_roughness': name + '_mer'}}
    json.dump(ts, open(os.path.join(ROOT, BLOCKS, name + '.texture_set.json'), 'w'))


def main():
    layouts = [pattern(1000 + v) for v in range(VARIANTS)]
    for name in NAMES:
        src = original(name)
        n = src.height // 16
        base = plain_needles(src.crop((0, 0, 16, 16)))
        for v, layout in enumerate(layouts):
            col, mer = Image.new('RGBA', src.size), Image.new('RGBA', src.size)
            for i in range(n):
                c, m = lights(base, layout, i, n)
                col.paste(c, (0, i * 16)); mer.paste(m, (0, i * 16))
            if v == 0:
                save(col, mer, name)                           # plain name = variant 0 (inventory icon, fallbacks)
            if name != 'leaves_spruce_carried':
                save(col, mer, '%s_v%d' % (name, v))
        print('%-22s %2d frame(s) x %d variants' % (name, n, VARIANTS))
    # random variant per block: index 0 = fancy (see-through) leaves, index 1 = fast-graphics leaves
    rp = os.path.join(ROOT, 'ChristmasCritters/ChristmasCritters_RP/textures')
    variations = lambda stem: {'variations': [{'path': 'textures/blocks/%s_v%d' % (stem, v), 'weight': 1} for v in range(VARIANTS)]}
    terrain = {'resource_pack_name': 'christmas_critters', 'texture_name': 'atlas.terrain', 'padding': 8, 'num_mip_levels': 4,
               'texture_data': {'spruce_leaves': {'textures': [variations('leaves_spruce'), variations('leaves_spruce_opaque')]}}}
    json.dump(terrain, open(os.path.join(rp, 'terrain_texture.json'), 'w'), indent=2)
    fp = os.path.join(rp, 'flipbook_textures.json')
    fb = [e for e in json.load(open(fp)) if e.get('atlas_tile') != 'spruce_leaves']
    fb += [{'flipbook_texture': 'textures/blocks/leaves_spruce_v%d' % v, 'atlas_tile': 'spruce_leaves', 'atlas_index': 0,
            'atlas_tile_variant': v, 'ticks_per_frame': 6, 'blend_frames': True} for v in range(VARIANTS)]
    json.dump(fb, open(fp, 'w'), indent=2)


if __name__ == '__main__':
    main()
