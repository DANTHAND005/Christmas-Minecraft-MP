#!/usr/bin/env python3
"""Make the ornaments on the Christmas Critters spruce leaves glow much more.

Ornaments keep their exact original pixels and twinkle; they are pushed to vivid, much brighter colours
(white-hot glints on the brightest pixels), their halos are lifted, and an emissive (MER) map makes them
truly light up in Vibrant Visuals / RTX.

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


def glow(frame):
    """Every ornament keeps its exact pixels in every frame; it just gets much brighter and lights its halo."""
    out, mer = frame.copy(), Image.new('RGBA', (16, 16), (0, 0, 0, 255))
    kinds = {(x, y): kind(frame.getpixel((x, y))) for x in range(16) for y in range(16)}
    for (x, y), k in kinds.items():
        r, g, b, a = frame.getpixel((x, y))
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        em = 0.0
        if k in 'OW':
            core = v >= 0.7                                    # dimmer ornament-coloured pixels are its halo: keep them softer
            s = s if k == 'W' else (max(s, 0.88) if core else min(1, s * 1.1))
            v2 = min(1.0, v * 1.4)                             # proportional boost keeps the original shapes
            col = [c * 255 for c in colorsys.hsv_to_rgb(h, s, v2)]
            if v >= 0.85:                                      # the brightest pixels get a white-hot glint
                col = [c + (255 - c) * 0.12 for c in col]
            em = v2
        elif k == 'h':
            col = [c * 255 for c in colorsys.hsv_to_rgb(h, min(1, s * 1.25), min(1, v * 1.35))]
            em = 0.45
        else:
            col = [r, g, b]
            near = [kinds.get((x + dx, y + dy)) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
            if k == 'L' and ('O' in near or 'W' in near):     # needles touching an ornament catch a faint glow
                col = [min(255, c * 1.25 + 12) for c in col]
                em = 0.2
        out.putpixel((x, y), tuple(round(c) for c in col) + (a,))
        mer.putpixel((x, y), (0, round(255 * em), 210, 255))   # R metalness, G emissive, B roughness
    return out, mer


def main():
    for name in NAMES:
        src = original(name)
        n = src.height // 16
        col, mer = Image.new('RGBA', src.size), Image.new('RGBA', src.size)
        for i in range(n):
            c, m = glow(src.crop((0, i * 16, 16, i * 16 + 16)))
            col.paste(c, (0, i * 16)); mer.paste(m, (0, i * 16))
        col.save(os.path.join(ROOT, BLOCKS, name + '.png'))
        mer.save(os.path.join(ROOT, BLOCKS, name + '_mer.png'))
        ts = {'format_version': '1.16.100', 'minecraft:texture_set': {'color': name, 'metalness_emissive_roughness': name + '_mer'}}
        json.dump(ts, open(os.path.join(ROOT, BLOCKS, name + '.texture_set.json'), 'w'))
        print('%-22s %2d frame(s)' % (name, n))


if __name__ == '__main__':
    main()
