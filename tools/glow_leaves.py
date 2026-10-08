#!/usr/bin/env python3
"""Make the ornaments on the Christmas Critters spruce leaves glow much more.

Brightens each ornament to a vivid colour with a hot centre, spreads a soft halo of that colour into the
leaves (pulsing through the flipbook), adds sparkles at the brightest frames, and writes an emissive (MER)
map so the ornaments really light up in Vibrant Visuals / RTX.

    python3 tools/glow_leaves.py              # reads the original textures from git (commit b89627e)
"""
import colorsys, io, json, math, os, subprocess, sys
from PIL import Image

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
BLOCKS = 'ChristmasCritters/ChristmasCritters_RP/textures/blocks'
ORIGINAL = 'b89627e'                         # untouched textures as received, so re-running never stacks the glow
NAMES = sys.argv[1:] or ['leaves_spruce', 'leaves_spruce_carried', 'leaves_spruce_opaque']
HALO = [(0.0, 1.0), (1.0, 0.62), (1.5, 0.44), (2.25, 0.24), (3.0, 0.1)]   # distance -> glow strength


def original(name):
    data = subprocess.run(['git', 'show', '%s:%s/%s.png' % (ORIGINAL, BLOCKS, name)], cwd=ROOT, capture_output=True, check=True).stdout
    return Image.open(io.BytesIO(data)).convert('RGBA')


def is_core(p):
    r, g, b, a = p
    return a > 0 and max(r, g, b) >= 140 and (max(r, g, b) - min(r, g, b) >= 90 or min(r, g, b) >= 150)


def ornaments(frames):
    """Connected groups of ornament pixels (looked for across every frame) with their vivid colour."""
    core = {(x, y) for x in range(16) for y in range(16)                    # ornament in most frames, not just a halo flash
            if sum(is_core(f.getpixel((x, y))) for f in frames) * 2 >= len(frames)}
    hue = {}
    for p in core:
        c = max((f.getpixel(p) for f in frames), key=lambda c: max(c[:3]))
        h, s, v = colorsys.rgb_to_hsv(*(v / 255 for v in c[:3]))
        hue[p] = -1 if s < 0.3 else h                                       # -1 = white ornament
    groups, seen = [], set()
    for start in core:
        if start in seen: continue
        stack, pix = [start], []
        seen.add(start)
        while stack:
            x, y = stack.pop()
            pix.append((x, y))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (x + dx, y + dy)
                    if q in core and q not in seen and (hue[q] == hue[(x, y)] == -1 or
                            hue[q] >= 0 <= hue[(x, y)] and min(abs(hue[q] - hue[(x, y)]), 1 - abs(hue[q] - hue[(x, y)])) < 0.06):
                        seen.add(q); stack.append(q)
        best = max((f.getpixel(p) for f in frames for p in pix), key=lambda c: max(c[:3]) + (max(c[:3]) - min(c[:3])))
        h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in best[:3]))
        white = s < 0.3
        vivid = tuple(round(c * 255) for c in colorsys.hsv_to_rgb(h, 0.15 if white else max(s, 0.9), 1.0))
        hot = max(pix, key=lambda p: max(f.getpixel(p)[:3] for f in frames))
        groups.append(dict(pix=pix, colour=vivid, hot=hot, phase=(sum(hot) * 2.399) % (2 * math.pi)))
    return groups


def glow(frame, groups, f, n):
    out, mer = frame.copy(), Image.new('RGBA', (16, 16), (0, 0, 0, 255))
    for x in range(16):
        for y in range(16):
            r, g, b, a = frame.getpixel((x, y))
            col, em = [r, g, b], 0.0
            for o in groups:
                k = 1.0 if n == 1 else 0.78 + 0.22 * math.sin(2 * math.pi * f / n + o['phase'])
                d = min(math.dist((x, y), p) for p in o['pix'])
                w = next((s for dd, s in HALO if d <= dd), 0.0) * k
                if not w: continue
                c = o['colour']
                if d == 0:                       # ornament itself: vivid, hottest pixel nearly white
                    t = 0.55 * k if (x, y) == o['hot'] else 0.15 * k
                    col = [c[i] + (255 - c[i]) * t for i in range(3)]
                elif a == 0 and d <= 1.0:        # glow spills into the gaps right next to it
                    col, a = [c[i] * w + 20 * (1 - w) for i in range(3)], 255
                else:                            # additive halo over the needles
                    col = [min(255, col[i] + c[i] * w * 0.85) for i in range(3)]
                if n > 1 and k > 0.97 and d == math.sqrt(2) and a:   # sparkle on the brightest frames
                    col = [255, 255, 240]
                em = max(em, w)
            out.putpixel((x, y), tuple(round(v) for v in col) + (a,))
            mer.putpixel((x, y), (0, round(255 * em), 210, 255))   # R metalness, G emissive, B roughness
    return out, mer


def main():
    for name in NAMES:
        src = original(name)
        n = src.height // 16
        frames = [src.crop((0, i * 16, 16, i * 16 + 16)) for i in range(n)]
        groups = ornaments(frames)
        col, mer = Image.new('RGBA', src.size), Image.new('RGBA', src.size)
        for i, fr in enumerate(frames):
            c, m = glow(fr, groups, i, n)
            col.paste(c, (0, i * 16)); mer.paste(m, (0, i * 16))
        col.save(os.path.join(ROOT, BLOCKS, name + '.png'))
        mer.save(os.path.join(ROOT, BLOCKS, name + '_mer.png'))
        ts = {'format_version': '1.16.100', 'minecraft:texture_set': {'color': name, 'metalness_emissive_roughness': name + '_mer'}}
        json.dump(ts, open(os.path.join(ROOT, BLOCKS, name + '.texture_set.json'), 'w'))
        print('%-22s %2d frame(s), %d ornaments' % (name, n, len(groups)))


if __name__ == '__main__':
    main()
