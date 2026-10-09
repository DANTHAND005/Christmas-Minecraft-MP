#!/usr/bin/env python3
"""Builds the Christmas Market add-on: 20 villager market stalls you can trade with (gold coins), the gold coin
and the Coin Press that turns gold nuggets into coins.

Each stall is one entity: the hut, its goods and the villager are a single model, and trading uses an
economy trade table. Models are made with the same helpers as the Santa's Workbench decorations
(tools/make_decor.py); glowing colours use the alpha channel of the entity texture (entity_emissive_alpha).

    python3 tools/make_market.py             # build into ChristmasMarket/
    python3 tools/make_market.py --preview   # also render previews/market_*.png
"""
import json, math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_decor as D
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


def zrender(model, size=900, yaw=28, pitch=18, ss=2, icon=False):
    """Orthographic z-buffer render (supersampled) with a soft glow pass for the lit colours."""
    yw, pt = math.radians(yaw), math.radians(pitch)
    cam = np.array((math.sin(yw) * math.cos(pt), math.sin(pt), -math.cos(yw) * math.cos(pt)))
    sun = np.array((-0.45, 0.8, -0.4)); sun /= np.linalg.norm(sun)
    def proj(p):
        x, y, z = p[..., 0], p[..., 1], p[..., 2]
        dep = z * math.cos(yw) - x * math.sin(yw)
        return np.stack((x * math.cos(yw) + z * math.sin(yw), y * math.cos(pt) + dep * math.sin(pt), dep * math.cos(pt) - y * math.sin(pt)), -1)
    N = {(0, 0, -1): lambda a, b: [(a[0], a[1], a[2]), (b[0], a[1], a[2]), (a[0], b[1], a[2])],
         (0, 0, 1): lambda a, b: [(a[0], a[1], b[2]), (b[0], a[1], b[2]), (a[0], b[1], b[2])],
         (-1, 0, 0): lambda a, b: [(a[0], a[1], a[2]), (a[0], a[1], b[2]), (a[0], b[1], a[2])],
         (1, 0, 0): lambda a, b: [(b[0], a[1], a[2]), (b[0], a[1], b[2]), (b[0], b[1], a[2])],
         (0, 1, 0): lambda a, b: [(a[0], b[1], a[2]), (b[0], b[1], a[2]), (a[0], b[1], b[2])],
         (0, -1, 0): lambda a, b: [(a[0], a[1], a[2]), (b[0], a[1], a[2]), (a[0], a[1], b[2])]}
    faces = []
    for x0, y0, z0, x1, y1, z1, c, b in model.cubes:
        glow = c in D.GLOW
        if c in ('clear', 'glass'): continue                          # no see-through parts on entities
        col = np.array(D.GLOW[c][0] if glow else D.BASE[c], float)
        for n, f in N.items():
            if np.dot(n, cam) <= 0: continue
            k = 1.0 if glow else 0.55 + 0.45 * max(0.0, float(np.dot(n, sun))) + 0.12 * (n[1] == 1)
            faces.append((proj(np.array(f((x0, y0, z0), (x1, y1, z1)), float)), np.clip(col * k, 0, 255), glow, c == 'glass'))
    allp = np.concatenate([f[0] for f in faces])
    lo, hi = allp.min(0), allp.max(0)
    S = size * ss
    sc = (S - (2 if icon else 60) * ss) / max(hi[0] - lo[0], hi[1] - lo[1])
    ox, oy = (S - (hi[0] - lo[0]) * sc) / 2 - lo[0] * sc, (S - (hi[1] - lo[1]) * sc) / 2 + hi[1] * sc
    yy, xx = np.mgrid[0:S, 0:S]
    top, bot = np.array((14, 18, 40.)), np.array((44, 52, 82.))         # night sky gradient
    img = top + (bot - top) * (yy[..., None] / S)
    zb = np.full((S, S), np.inf)
    glowmask = np.zeros((S, S, 3))
    for pts, col, glow, glass in faces:
        sp = np.stack((ox + pts[:, 0] * sc, oy - pts[:, 1] * sc), -1)
        o, u, v = sp[0], sp[1] - sp[0], sp[2] - sp[0]
        corners = np.array([o, o + u, o + v, o + u + v])
        xa, ya = np.floor(corners.min(0)).astype(int); xb, yb = np.ceil(corners.max(0)).astype(int)
        xa, ya, xb, yb = max(xa, 0), max(ya, 0), min(xb, S - 1), min(yb, S - 1)
        if xa > xb or ya > yb: continue
        det = u[0] * v[1] - u[1] * v[0]
        if abs(det) < 1e-9: continue
        px, py = xx[ya:yb + 1, xa:xb + 1] + 0.5 - o[0], yy[ya:yb + 1, xa:xb + 1] + 0.5 - o[1]
        a = (px * v[1] - py * v[0]) / det; b = (u[0] * py - u[1] * px) / det
        inside = (a >= -1e-3) & (a <= 1 + 1e-3) & (b >= -1e-3) & (b <= 1 + 1e-3)
        d = pts[0, 2] + a * (pts[1, 2] - pts[0, 2]) + b * (pts[2, 2] - pts[0, 2]) - 0.01 * glow
        zs = zb[ya:yb + 1, xa:xb + 1]
        w = inside & (d < zs)
        if not w.any(): continue
        if glass:
            img[ya:yb + 1, xa:xb + 1][w] = img[ya:yb + 1, xa:xb + 1][w] * 0.7 + np.array((200, 225, 245.)) * 0.3
            continue
        zs[w] = d[w]
        img[ya:yb + 1, xa:xb + 1][w] = col
        glowmask[ya:yb + 1, xa:xb + 1][w] = col if glow else 0
    if icon:                                                          # transparent background, no glow haze or snow
        rgba = np.dstack((np.clip(img, 0, 255), np.where(np.isfinite(zb), 255, 0))).astype(np.uint8)
        return Image.fromarray(rgba, 'RGBA').resize((size, size), Image.LANCZOS)
    gm = Image.fromarray(glowmask.astype(np.uint8)).filter(ImageFilter.GaussianBlur(9 * ss))
    out = np.clip(img + np.asarray(gm, float) * 0.8, 0, 255).astype(np.uint8)
    rnd = random.Random(3)
    im = Image.fromarray(out).resize((size, size), Image.LANCZOS)
    dr = ImageDraw.Draw(im)
    for _ in range(140):                                              # falling snow
        x, y, r = rnd.uniform(0, size), rnd.uniform(0, size), rnd.choice((1, 1, 1.5, 2))
        dr.ellipse((x - r, y - r, x + r, y + r), fill=(240, 244, 255))
    return im.convert('RGBA')


F = {'A': '010101111101101', 'B': '110101110101110', 'C': '011100100100011', 'D': '110101101101110', 'E': '111100110100111',
     'G': '011100101101011', 'H': '101101111101101', 'I': '111010010010111', 'K': '101101110101101', 'L': '100100100100111',
     'M': '101111111101101', 'N': '110101101101101', 'O': '010101101101010', 'R': '110101110101101', 'S': '011100010001110',
     'T': '111010010010010', 'U': '101101101101111', 'W': '101101111111101', 'Y': '101101010010010', 'P': '110101110100100',
     'F': '111100110100100', ' ': '000000000000000', '&': '010101010101011', 'Z': '111001010100111', 'V': '101101101101010',
     'X': '101101010101101', 'J': '001001001101010', 'Q': '010101101110011'}


def words(m, s, cx, ytop, z, ps, col):
    wide = {'W': ['10001', '10001', '10101', '10101', '01010'], 'M': ['10001', '11011', '10101', '10001', '10001']}
    glyph = lambda ch, r: wide[ch][r] if ch in wide else F[ch][r * 3:r * 3 + 3]
    rows = ['0'.join(glyph(ch, r) for ch in s).replace('0', '.') for r in range(5)]
    m.pixels(rows, cx - len(rows[0]) * ps / 2, ytop, z, ps, {'1': col}, 0.15)


def bulbs_along(m, pts, cols, every=2.2, drop=0.6, s=0.45):
    """Green wire with glowing bulbs hanging off it every `every` px."""
    m.tube(pts, 0.3, ['dark_green'], step=0.5)
    k = 0
    for a, b in zip(pts, pts[1:]):
        L = math.dist(a, b)
        for i in range(max(1, int(L / every))):
            p = [a[q] + (b[q] - a[q]) * i * every / L for q in range(3)]
            m.box(p[0] - s, p[1] - drop - 2 * s, p[2] - s, p[0] + s, p[1] - drop, p[2] + s, cols[k % len(cols)])
            k += 1


def villager(m, x, y, z, robe, trim, hat):
    """Minecraft-style villager standing behind the counter, arms folded, facing -z."""
    m.box(x - 4, y, z - 3, x + 4, y + 24, z + 3, robe)
    m.box(x - 4.05, y, z - 3.05, x + 4.05, y + 1.2, z + 3.05, trim)            # robe hem
    m.box(x - 1, y + 4, z - 3.1, x + 1, y + 23, z - 3, trim)                     # front band
    m.box(x - 5, y + 15, z - 6, x + 5, y + 19, z - 3, robe)                       # folded arms
    m.box(x - 2, y + 15.3, z - 6.1, x + 2, y + 18.7, z - 5.9, 'skin')            # hands
    m.box(x - 4, y + 24, z - 4, x + 4, y + 34, z + 4, 'skin')                     # head
    m.box(x - 1, y + 25, z - 6, x + 1, y + 30, z - 4, 'cheek')                    # big nose
    for sx in (-1, 1):
        m.box(x + sx * 2.5 - 1, y + 29, z - 4.1, x + sx * 2.5 + 1, y + 30, z - 4, 'white')
        m.box(x + sx * 2.5 - (sx < 0) * 1, y + 29, z - 4.15, x + sx * 2.5 + (sx > 0) * 1, y + 30, z - 4.1, 'green')
    m.box(x - 4, y + 30.5, z - 4.12, x + 4, y + 31.3, z - 4, 'dark_brown')        # unibrow
    m.box(x - 4.2, y + 22.5, z - 3.4, x + 4.2, y + 24.5, z + 3.4, 'red')         # Christmas scarf
    m.box(x + 1.5, y + 17, z - 3.5, x + 3.5, y + 22.5, z - 3.3, 'red')
    hat(m, x, y + 34, z)


def straw_hat(m, x, y, z):
    m.box(x - 7, y - 0.5, z - 7, x + 7, y + 0.5, z + 7, 'tan'); m.box(x - 4.2, y, z - 4.2, x + 4.2, y + 3, z + 4.2, 'tan')
    m.box(x - 4.3, y + 0.5, z - 4.3, x + 4.3, y + 1.3, z + 4.3, 'red')


def santa_cap(m, x, y, z):
    m.box(x - 4.4, y - 1, z - 4.4, x + 4.4, y + 0.6, z + 4.4, 'white')
    m.box(x - 4, y + 0.6, z - 4, x + 4, y + 3, z + 4, 'red'); m.box(x - 2.5, y + 3, z - 2.5, x + 2.5, y + 5, z + 2.5, 'red')
    m.box(x + 1, y + 4, z - 1.2, x + 5, y + 5.5, z + 1.2, 'red'); m.ell(x + 5.5, y + 4.6, z, 1.3, 1.3, 1.3, 'white')


def headband(m, x, y, z):
    m.box(x - 4.2, y - 3, z - 4.2, x + 4.2, y - 1.8, z + 4.2, 'red'); m.box(x - 4, y, z - 4, x + 4, y + 1.5, z + 4, 'dark_brown')


def cleric_hood(m, x, y, z):
    m.box(x - 4.4, y - 4, z - 4.4, x + 4.4, y + 0.8, z + 4.4, 'purple'); m.box(x - 4.5, y - 3.5, z - 4.5, x + 4.5, y - 2.5, z + 4.5, 'gold')


def wool_hat(m, x, y, z):
    m.box(x - 4.4, y - 1, z - 4.4, x + 4.4, y + 2.5, z + 4.4, 'cream'); m.box(x - 4.5, y - 1, z - 4.5, x + 4.5, y, z + 4.5, 'green')
    m.ell(x, y + 3.6, z, 1.6, 1.4, 1.6, 'red')


def librarian_cap(m, x, y, z):
    m.box(x - 4.4, y - 0.5, z - 4.4, x + 4.4, y + 1.5, z + 4.4, 'dark_red'); m.box(x - 2.5, y + 1.5, z - 2.5, x + 2.5, y + 4.5, z + 2.5, 'dark_red')
    m.box(x - 2.6, y + 2, z - 2.6, x + 2.6, y + 2.8, z + 2.6, 'gold')


def monocle_cap(m, x, y, z):
    santa_cap(m, x, y, z)
    m.box(x + 1.4, y - 6.2, z - 4.3, x + 3.6, y - 3.8, z - 4.15, 'gold')


def stall(m, sign, roof, aw1, aw2, sign_bg, sign_fg, posts, crest, vill, goods, extras, seed):
    rnd = random.Random(seed)
    W, Dp = 24, 16                                                   # half width / half depth (px)
    m.box(-W - 3, 0, -Dp - 4, W + 3, 1.5, Dp + 2, 'dark_brown')     # wooden deck
    for i in range(-W - 3, W + 3, 4):
        m.box(i, 1.5, -Dp - 4, i + 0.2, 1.55, Dp + 2, 'brown')
    for _ in range(9):                                               # snow drifts on the deck edge
        x, w = rnd.uniform(-W, W), rnd.uniform(1.5, 4)
        m.box(x - w, 1.5, -Dp - 4.1, x + w, 2 + rnd.uniform(0, 0.8), -Dp - 4 + rnd.uniform(1, 2.5), 'snow')
    m.box(-W + 1, 1.5, Dp - 2, W - 1, 46, Dp, 'wood')               # back wall
    for i in range(-W + 3, W, 4):
        m.box(i, 1.5, Dp - 2.1, i + 0.4, 46, Dp - 2, 'brown')
    m.box(-W + 3, 18, Dp - 2.2, W - 3, 44, Dp - 2.1, 'g_window')    # warm glow inside
    for y in (24, 31):                                                # shelves
        m.box(-W + 3, y, Dp - 6, W - 3, y + 1, Dp - 2, 'light_wood')
    for s in (-1, 1):                                                 # side half walls with lattice
        m.box(s * W - 1, 1.5, -Dp + 2, s * W + 1, 16, Dp, 'wood')
        for k in range(4):
            zz = -Dp + 4 + k * 7
            m.tube([(s * (W + 1.1), 4, zz), (s * (W + 1.1), 14, zz + 5)], 0.5, ['light_wood'])
            m.tube([(s * (W + 1.1), 14, zz), (s * (W + 1.1), 4, zz + 5)], 0.5, ['light_wood'])
    for sx in (-1, 1):                                                # posts
        for z0 in (-Dp - 1, Dp - 1):
            x0 = sx * W - 1.5
            if posts == 'cane':
                for k, y in enumerate(range(2, 47, 2)):
                    m.box(x0, y - 0.5, z0 - 1.5, x0 + 3, y + 1.5, z0 + 1.5, 'red' if k % 2 else 'white')
            elif posts == 'garland':                                  # wood wrapped in a lit garland
                m.box(x0, 1.5, z0 - 1.5, x0 + 3, 47, z0 + 1.5, 'light_wood')
                for k, y in enumerate(range(3, 46, 3)):
                    m.box(x0 - 0.5, y, z0 - 2, x0 + 3.5, y + 1.2, z0 + 2, 'dark_green')
                    a = (k % 4) * 0.8
                    m.box(x0 - 0.8 + a, y + 0.2, z0 - 2.3, x0 + a, y + 1, z0 - 1.9, ['g_red', 'g_yellow', 'g_blue', 'g_green'][k % 4])
            else:
                m.box(x0, 1.5, z0 - 1.5, x0 + 3, 47, z0 + 1.5, 'light_wood')
                for y in (6, 22, 40):
                    m.box(x0 - 0.3, y, z0 - 1.8, x0 + 3.3, y + 1, z0 + 1.8, posts)
    # counter with the stall's name on a painted board
    m.box(-W + 1, 1.5, -Dp, W - 1, 15, -Dp + 4, 'wood')
    m.box(-W, 15, -Dp - 1.2, W, 16.5, -Dp + 5, 'light_wood')
    m.box(-W + 3.6, 3.6, -Dp - 0.1, W - 3.6, 13.4, -Dp, 'gold')
    m.box(-W + 4, 4, -Dp - 0.25, W - 4, 13, -Dp - 0.1, sign_bg)
    words(m, sign, 0, 11, -Dp - 0.25, min(1.4, 38 / (len(sign) * 4 + 2 * sign.count('W'))), sign_fg)
    for x in (-W + 2, W - 2):                                         # snow on the counter ends
        m.box(x - 2, 16.5, -Dp - 1, x + 2, 17, -Dp + 2, 'snow')
    villager(m, 0, 1.5, Dp - 9, *vill)
    # striped awning sloping out over the counter, scalloped edge
    for i in range(-W - 2, W + 2, 4):
        c = aw1 if (i // 4) % 2 else aw2
        for k in range(4):
            m.box(i, 44 - k * 1.2, -Dp - 1 - k * 1.8, i + 4, 45.2 - k * 1.2, -Dp + 1 - k * 1.8, c)
        m.box(i + 0.5, 39.2, -Dp - 7.4, i + 3.5, 40.5, -Dp - 6.6, c)
    bulbs_along(m, [(-W - 2, 39.5, -Dp - 7.6), (W + 2, 39.5, -Dp - 7.6)], ['g_red', 'g_yellow', 'g_green', 'g_blue'])
    # gable roof (ridge front-to-back) with snow, icicles and an A-frame cross at the front
    top = D.snowroof(m, -Dp - 3, Dp + 2, 0, 46, W + 5, 2.2, 2.3, roof, axis='z')
    for k in range(10):                                               # plaster gable with a sign
        h = W - k * 2.3
        if h < 1: break
        m.box(-h, 46 + k * 2.2, -Dp - 3.4, h, 48.2 + k * 2.2, -Dp - 3.1, 'plaster')
    for s in (-1, 1):
        m.tube([(s * (W + 6), 45, -Dp - 3.6), (s * (-3 if crest == 'cross' else 0), top + (4 if crest == 'cross' else 0), -Dp - 3.6)],
               1.3, ['light_wood'], step=0.7)
    if crest == 'star':                                               # glowing star on the ridge
        m.pixels(['..s..', '..s..', 'sssss', '.sss.', '.s.s.', 's...s'], -3, top + 7, -Dp - 3.4, 1.2, {'s': 'g_star'}, 1.2)
    elif crest == 'bell':                                             # golden bell with a bow
        m.ell(0, top + 2.6, -Dp - 3.6, 2.2, 2.6, 2.2, 'gold', ymin=top + 0.8)
        m.box(-2.6, top + 0.4, -Dp - 6, 2.6, top + 1.1, -Dp - 1.2, 'gold'); m.ell(0, top + 0.3, -Dp - 3.6, 0.7, 0.7, 0.7, 'dark_gold')
        D.bow(m, 0, top + 5.2, -Dp - 3.6, 'red', 1.2)
    m.box(-15, 49, -Dp - 3.7, 15, 58, -Dp - 3.4, 'gold')
    m.box(-14.5, 49.5, -Dp - 3.9, 14.5, 57.5, -Dp - 3.7, sign_bg)
    words(m, sign, 0, 56, -Dp - 3.9, min(1.1, 27 / (len(sign) * 4 + 2 * sign.count('W'))), 'gold')
    D.bow(m, 0, 59, -Dp - 3.9, 'red', 1.4)
    m.tube([(-W - 5, 46.6, -Dp - 3.8), (0, top - 0.5, -Dp - 3.8), (W + 5, 46.6, -Dp - 3.8)], 1.0, ['dark_green'], step=0.8)
    bulbs_along(m, [(-W - 5, 46.4, -Dp - 4.4), (0, top - 0.7, -Dp - 4.4), (W + 5, 46.4, -Dp - 4.4)],
                ['g_yellow2', 'g_red2', 'g_green2', 'g_blue2'], every=2.6, drop=0.2)
    for s in (-1, 1):                                                 # hanging lanterns
        x = s * (W + 1)
        m.box(x - 0.15, 39, -Dp - 8, x + 0.15, 43, -Dp - 7.7, 'black')
        m.box(x - 1.2, 35, -Dp - 9, x + 1.2, 39, -Dp - 6.6, 'black')
        m.box(x - 0.9, 35.4, -Dp - 9.1, x + 0.9, 38.6, -Dp - 6.5, 'g_flame')
    goods(m, W, Dp, rnd)
    extras(m, W, Dp, rnd)


# ---------------------------------------------------------------- what each villager sells
def heart(m, x, y, z, col='ginger', icing='white', ps=0.55):
    m.pixels(['.ii.ii.', 'iccicci', 'icccccі'.replace('і', 'i'), '.icccі.'.replace('і', 'i'), '..ici..', '...i...'], x, y + 3.3, z, ps, {'i': icing, 'c': col})


def ginger_man(m, x, y, z, s=1.0):
    m.pixels(['.ggg.', '.gwg.', 'ggggg', 'g.w.g', '.ggg.', '.g.g.', 'gg.gg'], x, y, z, 0.6 * s, {'g': 'ginger', 'w': 'white'}, 0.6)


def farmer_goods(m, W, Dp, rnd):
    for x in range(-W + 4, W - 4, 5):                                 # gingerbread men on the shelves
        ginger_man(m, x, 29.2, Dp - 4)
        m.box(x - 0.2, 32, Dp - 5.5, x + 3.5, 35, Dp - 2.5, rnd.choice(['tan', 'ginger', 'cream']))   # cookie tins
        m.box(x - 0.3, 35, Dp - 5.6, x + 3.6, 35.6, Dp - 2.4, rnd.choice(['red', 'green', 'gold']))
    for i, x in enumerate((-19, -12, -5)):                            # cookie trays and pies on the counter
        m.box(x - 3, 16.5, -Dp - 0.5, x + 3, 17, -Dp + 4, 'silver')
        for k in range(6):
            m.disc(x - 2 + (k % 3) * 2, -Dp + 0.5 + (k // 3) * 2, 17, 17.5, 0.8, 0.8, ['ginger', 'tan', 'cream'][(k + i) % 3])
    for x in (6, 15):
        m.disc(x, -Dp + 1.5, 16.5, 18, 3.2, 3.2, 'tan'); m.disc(x, -Dp + 1.5, 18, 18.4, 2.5, 2.5, 'dark_red')
    m.box(19, 16.5, -Dp, 22, 21, -Dp + 3, 'glass')
    for k in range(4):
        D.cane(m, 19.6 + k * 0.6, -Dp + 1.5, 17, 23.5, 0.7, 0.45)
    for i, x in enumerate(range(-W, W, 6)):                           # Lebkuchen hearts hanging from the awning
        m.box(x + 1.8, 34.5, -Dp - 7.3, x + 2, 39.2, -Dp - 7.1, 'red')
        heart(m, x, 34.8, -Dp - 7.2, ['ginger', 'dark_ginger'][i % 2], ['white', 'pink', 'mint'][i % 3])


def farmer_extras(m, W, Dp, rnd):
    D.pine(m, -W - 8, 0, -4, 26, 5, lights=['g_red', 'g_yellow', 'g_blue', 'g_green'])
    for k, (c, r) in enumerate((('red', 'gold'), ('green', 'red'), ('gold', 'red'))):
        m.present(W + 4 + k * 2, 1.5 + (k == 2) * 4, -Dp - 2 + k * 3, W + 8 + k * 2, 5.5 + (k == 2) * 4, -Dp + 2 + k * 3, c, r, w=0.6)
    m.box(W + 4, 1.5, Dp - 8, W + 9, 9, Dp - 2, 'wood')               # flour sack crate
    m.ell(W + 6.5, 11, Dp - 5, 2.5, 2.5, 2.5, 'cream')


def butcher_goods(m, W, Dp, rnd):
    m.box(-20, 16.5, -Dp - 0.5, -4, 18.5, -Dp + 4.5, 'black')         # grill with glowing coals and sausages
    m.box(-19.5, 18.5, -Dp, -4.5, 18.7, -Dp + 4, 'g_flame')
    for k in range(7):
        m.cyl('z', -18.5 + k * 2, 19.3, -Dp + 0.2, -Dp + 3.8, 0.6, 0.6, ['brown', 'dark_red'][k % 2])
    m.cyl('x', 10, 21, 2, 18, 3.5, 3.5, 'dark_gray', n=3)            # chestnut roasting drum
    m.box(1, 16.5, -Dp + 1, 3, 21, -Dp + 3, 'black'); m.box(17, 16.5, -Dp + 1, 19, 21, -Dp + 3, 'black')
    m.box(5, 16.5, -Dp + 0.5, 15, 17.5, -Dp + 3.5, 'g_flame')
    for i in range(5):                                                # smoke curling up
        r = 1 + i * 0.35
        m.ell(10 + math.sin(i) * 1.5, 26 + i * 3.2, -Dp + 2, r, r * 0.8, r, 'silver' if i % 2 else 'white')
    for x in range(-W + 5, W - 4, 6):                                  # hams and sausage strings on the back wall
        m.ell(x, 29, Dp - 4, 1.8, 2.6, 1.6, 'carrot')
        m.box(x - 0.15, 31.5, Dp - 4.1, x + 0.15, 32, Dp - 3.9, 'white')
        m.tube([(x + 2, 37, Dp - 3), (x + 3, 34, Dp - 3), (x + 4, 37, Dp - 3)], 0.9, ['dark_red', 'brown'], stripe=1.0)
    for x in range(-W + 4, W - 4, 4):                                  # paper cones of chestnuts on the shelf
        m.box(x, 24.9, Dp - 5, x + 2, 27.5, Dp - 3, 'paper'); m.box(x + 0.3, 27.5, Dp - 4.7, x + 1.7, 28.3, Dp - 3.3, 'dark_brown')


def butcher_extras(m, W, Dp, rnd):
    for k in range(3):
        m.cyl('y', -W - 6 + (k == 2) * 3, -Dp + 2 + k * 6 - (k == 2) * 3, 1.5 + (k == 2) * 8, 9.5 + (k == 2) * 8, 3, 3, 'wood', n=3)
        m.disc(-W - 6 + (k == 2) * 3, -Dp + 2 + k * 6 - (k == 2) * 3, 4.5 + (k == 2) * 8, 5.2 + (k == 2) * 8, 3.15, 3.15, 'dark_gray')
    m.disc(-W - 3, -Dp + 5, 17.5, 18.2, 2.8, 2.8, 'snow')
    lantern_post(m, W + 7, -Dp - 2)


def cleric_goods(m, W, Dp, rnd):
    m.ell(-12, 21, -Dp + 2, 5, 4.5, 4.5, 'orange', n=3)               # big copper kettle on a burner
    m.box(-15, 16.5, -Dp - 1, -9, 17.5, -Dp + 5, 'black')
    m.box(-14.5, 16.6, -Dp - 1.1, -9.5, 17.3, -Dp + 5.1, 'g_flame')
    m.disc(-12, -Dp + 2, 25, 26.5, 2.4, 2.4, 'gold')
    m.tube([(-7.5, 22, -Dp + 2), (-4, 24, -Dp + 2), (-3, 26, -Dp + 2)], 1.1, ['orange'])
    for i in range(5):
        r = 1.2 + i * 0.4
        m.ell(-12 + i * 0.8, 29 + i * 3, -Dp + 2, r, r * 0.7, r, 'white')
    for k in range(6):                                                # mugs with cocoa + marshmallows
        x, c = 0 + k * 3.5, ['red', 'white', 'green'][k % 3]
        m.cyl('y', x, -Dp + 1.5 + (k % 2) * 2, 16.5, 19.5, 1.2, 1.2, c)
        m.disc(x, -Dp + 1.5 + (k % 2) * 2, 19.4, 19.6, 0.9, 0.9, 'dark_brown')
        m.box(x - 0.4, 19.6, -Dp + 1.2 + (k % 2) * 2, x + 0.3, 20.2, -Dp + 1.9 + (k % 2) * 2, 'white')
        m.box(x + 1.2, 17.2, -Dp + 1.3 + (k % 2) * 2, x + 1.8, 18.8, -Dp + 1.7 + (k % 2) * 2, c)
    for y in (25, 32):
        for x in range(-W + 4, W - 3, 3):
            m.cyl('y', x, Dp - 4, y, y + 2.6, 1, 1, rnd.choice(['red', 'white', 'green', 'gold']))
    for i, x in enumerate(range(-W + 2, W, 8)):                       # star lanterns from the awning
        m.box(x - 0.1, 35.5, -Dp - 7.3, x + 0.1, 39.2, -Dp - 7.1, 'gold')
        m.pixels(['..y..', '.yyy.', 'yyyyy', '.yyy.', '.y.y.'], x - 1.5, 35.6, -Dp - 6.8, 0.6, {'y': ['g_star', 'g_purple'][i % 2]}, 0.6)


def cleric_extras(m, W, Dp, rnd):
    D.pine(m, W + 8, 0, -4, 24, 4.5, lights=['g_purple', 'g_yellow', 'g_white'])
    for k in range(3):
        m.box(-W - 8 + k * 0.5, 1.5 + k * 4, -Dp + 2, -W - 3 - k * 0.5, 5.5 + k * 4, -Dp + 8, ['wood', 'light_wood', 'wood'][k])
    m.cyl('y', -W - 5.5, -Dp + 5, 13.5, 16, 1.4, 1.4, 'purple')


def sweater(m, x, y, z, c, pat):
    m.pixels(['bb.bb', 'bbbbb', 'bpbpb', 'bbbbb', '.bbb.', '.bbb.'], x, y, z, 0.9, {'b': c, 'p': pat}, 0.4)
    m.pixels(['b...b'], x - 1.4, y - 0.4, z, 0.9, {'b': c}, 0.4)


def shepherd_goods(m, W, Dp, rnd):
    m.box(-W, 38.9, -Dp - 7.4, W, 39.1, -Dp - 7.2, 'dark_brown')        # sweaters on a line under the awning
    for i, x in enumerate(range(-W + 1, W - 3, 6)):
        c, p = [('red', 'white'), ('green', 'white'), ('navy', 'white'), ('white', 'red'), ('dark_red', 'gold'), ('teal', 'white'), ('green', 'red'), ('red', 'green')][i % 8]
        sweater(m, x, 38.8, -Dp - 7.0, c, p)
    for k, (a, b) in enumerate((('red', 'white'), ('green', 'white'), ('blue', 'white'), ('gold', 'red'))):  # scarves over the side wall
        z = -Dp + 3 + k * 6
        for j in range(6):
            m.box(W + 1.1, 16 - j * 1.8, z, W + 1.4, 17.8 - j * 1.8, z + 2.5, a if j % 2 else b)
        m.box(W - 1.2, 16, z, W + 1.4, 16.5, z + 2.5, a)
    for k in range(5):                                                 # mittens on the counter
        x = -18 + k * 4
        m.box(x, 16.5, -Dp, x + 2.2, 17.3, -Dp + 3, ['red', 'green', 'white', 'navy', 'red'][k])
        m.box(x + 2.2, 16.5, -Dp + 0.5, x + 3, 17.3, -Dp + 1.5, ['red', 'green', 'white', 'navy', 'red'][k])
    for y in (25, 32):                                                 # folded jumpers on the shelves
        for x in range(-W + 4, W - 4, 5):
            for j in range(3):
                m.box(x, y + j * 1.1, Dp - 5.5, x + 4, y + (j + 1) * 1.1, Dp - 2.5, rnd.choice(['red', 'white', 'green', 'navy', 'cream']))


def shepherd_extras(m, W, Dp, rnd):
    for k, (x, y, z, c) in enumerate(((-W - 9, 1.5, -6, 'white'), (-W - 9, 1.5, 1, 'red'), (-W - 9, 7.5, -2.5, 'green'))):
        m.box(x, y, z, x + 6, y + 6, z + 6, c)                         # wool bales
        m.box(x - 0.1, y + 2.5, z - 0.1, x + 6.1, y + 3.5, z + 6.1, 'tan')
    m.box(W + 4, 1.5, -Dp, W + 12, 7, -Dp + 6, 'white')                # a fluffy sheep
    m.box(W + 3, 4.5, -Dp + 1, W + 5, 8, -Dp + 5, 'cream')
    for x in (W + 5, W + 10):
        m.box(x, 0, -Dp + 0.5, x + 1.2, 1.5, -Dp + 1.7, 'dark_gray'); m.box(x, 0, -Dp + 4.3, x + 1.2, 1.5, -Dp + 5.5, 'dark_gray')
    m.box(W + 2.8, 6.4, -Dp + 1.2, W + 3, 7.2, -Dp + 2, 'black')
    santa_cap(m, W + 4, 8, -Dp + 3)


def librarian_goods(m, W, Dp, rnd):
    for y in (25, 32):                                                 # rows of book spines
        x = -W + 3.5
        while x < W - 4:
            w, h = rnd.uniform(0.8, 1.5), rnd.uniform(4.2, 5.8)
            m.box(x, y, Dp - 5.5, x + w, y + h, Dp - 2.5, rnd.choice(['dark_red', 'navy', 'green', 'brown', 'purple', 'teal']))
            m.box(x, y + h * 0.7, Dp - 5.55, x + w, y + h * 0.75, Dp - 2.5, 'gold')
            x += w + 0.1
    for k, x in enumerate((-19, -13)):                                 # stacks of books on the counter
        for j in range(4):
            m.box(x - 2.2 + (j % 2) * 0.4, 16.5 + j * 1.2, -Dp, x + 2.2 + (j % 2) * 0.4, 17.7 + j * 1.2, -Dp + 3.5,
                  ['dark_red', 'navy', 'green', 'gold'][(j + k) % 4])
    for k in range(4):                                                 # Christmas cards on a little stand
        x = -6 + k * 4
        m.box(x, 16.5, -Dp + 1, x + 3, 20.5, -Dp + 1.3, ['red', 'green', 'navy', 'white'][k])
        m.pixels(['.y.', 'yyy', '.y.'], x + 0.6, 19.6, -Dp + 0.95, 0.6, {'y': ['gold', 'white', 'white', 'red'][k]}, 0.1)
    m.cyl('y', 12, -Dp + 2, 16.5, 17, 2.2, 2.2, 'gold'); m.cyl('y', 12, -Dp + 2, 17, 22, 1, 1, 'cream')   # candle
    m.box(11.7, 22, -Dp + 1.7, 12.3, 23.4, -Dp + 2.3, 'g_flame')
    for x in (17, 21):                                                 # toy nutcrackers
        m.box(x - 1, 16.5, -Dp + 1, x + 1, 20, -Dp + 3, 'red'); m.box(x - 0.9, 20, -Dp + 1.1, x + 0.9, 22, -Dp + 2.9, 'skin')
        m.box(x - 1, 22, -Dp + 1, x + 1, 24.5, -Dp + 3, 'black')
    for i, x in enumerate(range(-W, W, 7)):                           # paper snowflakes on the awning edge
        m.box(x + 2.4, 36.5, -Dp - 7.3, x + 2.6, 39.2, -Dp - 7.1, 'white')
        m.pixels(['w.w.w', '.www.', 'wwwww', '.www.', 'w.w.w'], x + 1, 36.6, -Dp - 7.0, 0.6, {'w': 'white'}, 0.2)


def librarian_extras(m, W, Dp, rnd):
    m.box(-W - 9, 1.5, -6, -W - 3, 18, 4, 'wood')                      # outdoor book cart
    for x in (-W - 8.5, -W - 6):
        m.cyl('z', x + 1.2, 1.8, -7, 5, 1.8, 1.8, 'black')
    for y in (6, 12):
        z = -5.5
        while z < 3.5:
            w = rnd.uniform(0.8, 1.4)
            m.box(-W - 9.2, y, z, -W - 6, y + rnd.uniform(4, 5.5), z + w, rnd.choice(['dark_red', 'navy', 'green', 'brown']))
            z += w + 0.1
    D.pine(m, W + 8, 0, -4, 22, 4, lights=['g_white', 'g_yellow', 'g_white'])


def lantern_post(m, x, z):
    m.cyl('y', x, z, 0, 1.5, 2, 2, 'black'); m.cyl('y', x, z, 1.5, 30, 0.7, 0.7, 'black')
    m.box(x - 2, 30, z - 2, x + 2, 35, z + 2, 'black'); m.box(x - 1.6, 30.3, z - 2.1, x + 1.6, 34.7, z + 2.1, 'g_flame')
    m.box(x - 2.1, 30.3, z - 1.6, x + 2.1, 34.7, z + 1.6, 'g_flame')
    m.box(x - 2.6, 35, z - 2.6, x + 2.6, 35.8, z + 2.6, 'black'); m.box(x - 2.4, 35.8, z - 2.4, x + 2.4, 36.5, z + 2.4, 'snow')
    D.bow(m, x, 27, z - 1, 'red', 1.0)
    m.tube([(x, 26, z - 0.8), (x, 6, z - 0.8)], 0.8, ['red', 'white'], stripe=1.2)


def bauble(m, x, y, z, c, r=1.3):
    m.ell(x, y, z, r, r, r, c)
    m.box(x - 0.4, y + r - 0.1, z - 0.4, x + 0.4, y + r + 0.5, z + 0.4, 'gold')


def cartographer_goods(m, W, Dp, rnd):
    cols = ['g_red', 'g_blue', 'g_green', 'g_yellow', 'g_purple', 'g_cool', 'g_white']
    for i, x in enumerate(range(-W + 1, W, 3)):                       # glowing baubles hanging at different heights
        L = [1.5, 3, 2, 4, 2.5][i % 5]
        m.box(x - 0.05, 39 - L, -Dp - 7.25, x + 0.05, 39.2, -Dp - 7.15, 'gold')
        bauble(m, x, 39 - L - 1.6, -Dp - 7.2, cols[i % len(cols)], 1.1 + (i % 3) * 0.2)
    for x in range(-W + 4, W - 3, 4):                                  # bauble boxes on the shelves
        for y in (25, 32):
            m.box(x, y, Dp - 5.5, x + 3.4, y + 2, Dp - 2.5, 'cream')
            for j in range(2):
                bauble(m, x + 0.9 + j * 1.6, y + 2.6, Dp - 4, rnd.choice(['red', 'gold', 'silver', 'green', 'blue']), 0.7)
    for k, x in enumerate((-19, -12, -5)):                             # glass display domes with ornaments
        m.box(x - 3, 16.5, -Dp, x + 3, 17.3, -Dp + 4.5, 'dark_brown')
        bauble(m, x, 19.2, -Dp + 2.2, ['g_red', 'g_blue', 'g_green'][k], 1.6)
        m.box(x - 2.6, 17.3, -Dp + 0.2, x + 2.6, 23, -Dp + 4.3, 'glass')
    D.pine(m, 12, 16.5, -Dp + 2.5, 14, 3.2, snow=False, lights=['g_red', 'g_yellow', 'g_blue', 'g_green'])
    m.pixels(['.y.', 'yyy', '.y.'], 11.1, 31.6, -Dp + 2.5, 0.6, {'y': 'g_star'}, 0.6)


def cartographer_extras(m, W, Dp, rnd):
    for k, (c, r, h) in enumerate((('red', 'gold', 6), ('blue', 'white', 4), ('green', 'red', 5), ('gold', 'red', 3))):
        x = -W - 10 + (k % 2) * 6
        y = 1.5 + (k // 2) * 6
        m.present(x, y, -Dp + (k % 2), x + 5.5, y + h - (k // 2), -Dp + 5 + (k % 2), c, r, w=0.6)
    lantern_post(m, W + 7, -Dp - 2)
    D.pine(m, W + 9, 0, 6, 26, 5, lights=['g_purple', 'g_cool', 'g_white'])




# ---------------------------------------------------------------- more hats
def elf_hat(m, x, y, z):
    m.box(x - 4.4, y - 1, z - 4.4, x + 4.4, y + 0.4, z + 4.4, 'red')
    for k in range(4):
        r = 4 - k * 0.9
        m.box(x - r, y + 0.4 + k * 1.6, z - r, x + r, y + 2 + k * 1.6, z + r, 'green')
    m.box(x - 0.5, y + 6.8, z - 0.5, x + 3, y + 7.6, z + 0.5, 'green'); m.ell(x + 3.4, y + 7.2, z, 0.9, 0.9, 0.9, 'gold')


def chef_hat(m, x, y, z):
    m.box(x - 4.3, y - 1, z - 4.3, x + 4.3, y + 2, z + 4.3, 'white'); m.ell(x, y + 4.2, z, 5, 2.6, 5, 'white')


def beanie(col, bob='white'):
    def hat(m, x, y, z):
        m.box(x - 4.4, y - 2, z - 4.4, x + 4.4, y + 2.2, z + 4.4, col); m.box(x - 4.5, y - 2, z - 4.5, x + 4.5, y - 0.8, z + 4.5, bob)
        m.ell(x, y + 3.4, z, 1.7, 1.5, 1.7, bob)
    return hat


def fisher_hat(m, x, y, z):
    m.box(x - 5.5, y - 1, z - 6.5, x + 5.5, y - 0.3, z + 5.5, 'yellow'); m.box(x - 4.3, y - 0.3, z - 4.3, x + 4.3, y + 2.5, z + 4.3, 'yellow')


def goggles(m, x, y, z):
    headband(m, x, y, z)
    for sx in (-1, 1):
        m.box(x + sx * 2.5 - 1.3, y - 5.6, z - 4.5, x + sx * 2.5 + 1.3, y - 3.6, z - 4.15, 'orange')
    m.box(x - 4.2, y - 5, z - 4.3, x + 4.2, y - 4.3, z + 4.2, 'dark_brown')


def top_hat(m, x, y, z):
    m.box(x - 6, y - 0.4, z - 6, x + 6, y + 0.4, z + 6, 'black'); m.box(x - 3.6, y + 0.4, z - 3.6, x + 3.6, y + 6, z + 3.6, 'black')
    m.box(x - 3.7, y + 0.8, z - 3.7, x + 3.7, y + 1.8, z + 3.7, 'red'); m.box(x + 2, y + 1, z - 3.9, x + 3.4, y + 3, z - 3.7, 'holly')


# ---------------------------------------------------------------- the other fourteen stalls
def flame(m, x, y, z):
    m.box(x - 0.3, y, z - 0.3, x + 0.3, y + 0.9, z + 0.3, 'g_flame')


def candle(m, x, y, z, h, col, r=0.8):
    m.cyl('y', x, z, y, y + h, r, r, col); flame(m, x, y + h, z)


def candles_goods(m, W, Dp, rnd):
    for y in (25, 32):                                                 # rows of candles on the shelves
        for x in range(-W + 4, W - 3, 2):
            candle(m, x, y, Dp - 4, rnd.uniform(1.5, 4), rnd.choice(['red', 'white', 'cream', 'green', 'gold']), 0.6)
    for k, (x, h, c) in enumerate(((-19, 6, 'red'), (-16, 4, 'white'), (-13, 7, 'green'), (-10, 5, 'gold'), (12, 8, 'red'),
                                    (15, 5, 'cream'), (18, 6, 'white'))):
        candle(m, x, 16.5, -Dp + 1.5 + (k % 2), h, c, 1.1)              # pillar candles on the counter
    m.disc(0, -Dp + 2, 16.5, 17, 4, 3, 'holly')                        # advent wreath with four candles
    for k in range(4):
        a = k * math.pi / 2 + 0.6
        candle(m, 3 * math.cos(a), 17, -Dp + 2 + 2.2 * math.sin(a), 3 + k * 0.5, ['purple', 'purple', 'pink', 'purple'][k], 0.5)
    for i, x in enumerate(range(-W + 2, W, 6)):                        # dipped candles hanging in pairs from the awning
        m.box(x - 1, 38.6, -Dp - 7.3, x + 1, 38.9, -Dp - 7.1, 'tan')
        for dx in (-0.8, 0.8):
            m.cyl('y', x + dx, -Dp - 7.2, 33, 38.6, 0.35, 0.35, ['red', 'white', 'green', 'gold'][i % 4])


def candles_extras(m, W, Dp, rnd):
    m.box(-W - 9, 1.5, -6, -W - 3, 8, 2, 'yellow')                      # beehive crate with honeycomb
    for k in range(3):
        m.box(-W - 9.2, 2.5 + k * 2, -5.5, -W - 2.8, 3.2 + k * 2, 1.5, 'orange')
    m.box(-W - 9.2, 8, -6.2, -W - 2.8, 8.6, 2.2, 'snow')
    lantern_post(m, W + 7, -Dp - 2)
    D.pine(m, W + 9, 0, 6, 24, 4.5, lights=['g_flame', 'g_yellow2', 'g_white'])


def toys_goods(m, W, Dp, rnd):
    x0 = -20                                                           # toy train on the counter
    for k, c in enumerate(('red', 'blue', 'green')):
        x = x0 + k * 4.2
        m.box(x, 17.2, -Dp + 0.5, x + 3.6, 19.6 + (k == 0) * 1.4, -Dp + 3.5, c)
        for dx in (0.8, 2.8):
            m.cyl('z', x + dx, 17.2, -Dp + 0.2, -Dp + 3.8, 0.7, 0.7, 'black')
    m.box(x0 + 0.6, 21, -Dp + 1.4, x0 + 1.6, 22.6, -Dp + 2.6, 'black')
    m.cyl('y', -4, -Dp + 2, 16.5, 19.5, 2, 2, 'red'); m.disc(-4, -Dp + 2, 19.3, 19.8, 2.1, 2.1, 'white')   # drum
    m.ell(4, 19, -Dp + 2.2, 2, 2.4, 1.8, 'brown'); m.ell(4, 22.6, -Dp + 2.2, 1.6, 1.5, 1.5, 'brown')      # teddy
    for sx in (-1, 1):
        m.ell(4 + sx * 1.3, 23.9, -Dp + 2.2, 0.6, 0.6, 0.5, 'brown')
    m.box(2.8, 21.2, -Dp + 0.5, 5.2, 21.8, -Dp + 0.9, 'red')
    for k in range(6):                                                 # letter blocks
        x = 9 + (k % 3) * 2.2
        m.box(x, 16.5 + (k // 3) * 2, -Dp + 1, x + 2, 18.5 + (k // 3) * 2, -Dp + 3, ['red', 'yellow', 'blue', 'green', 'orange', 'purple'][k])
    for y in (25, 32):                                                 # toy soldiers and rocking horses on the shelves
        for x in range(-W + 4, W - 4, 4):
            if (x // 4 + y) % 2:
                m.box(x, y, Dp - 4.5, x + 1.6, y + 2.5, Dp - 3.5, 'red'); m.box(x, y + 2.5, Dp - 4.5, x + 1.6, y + 3.4, Dp - 3.5, 'skin')
                m.box(x - 0.1, y + 3.4, Dp - 4.6, x + 1.7, y + 5, Dp - 3.4, 'black')
            else:
                m.tube([(x - 0.5, y + 0.5, Dp - 4), (x + 1.5, y, Dp - 4), (x + 3.5, y + 0.5, Dp - 4)], 0.5, ['red'])
                m.box(x, y + 1, Dp - 4.5, x + 3, y + 2.4, Dp - 3.5, 'white'); m.box(x + 2.4, y + 2.4, Dp - 4.4, x + 3.4, y + 4, Dp - 3.6, 'white')
    for i, x in enumerate(range(-W + 1, W, 5)):                        # wooden stars hanging from the awning
        m.box(x + 1.4, 36, -Dp - 7.3, x + 1.6, 39.2, -Dp - 7.1, 'white')
        m.pixels(['..s..', 'sssss', '.sss.', 's...s'], x, 36.4, -Dp - 6.9, 0.6, {'s': ['gold', 'light_wood', 'red'][i % 3]}, 0.4)


def toys_extras(m, W, Dp, rnd):
    x, z = -W - 7, -Dp + 2                                             # giant toy soldier guarding the stall
    m.box(x - 1.6, 1.5, z - 1, x - 0.2, 8, z + 1, 'navy'); m.box(x + 0.2, 1.5, z - 1, x + 1.6, 8, z + 1, 'navy')
    m.box(x - 2, 8, z - 1.4, x + 2, 15, z + 1.4, 'red'); m.box(x - 2.05, 9.5, z - 1.45, x + 2.05, 10.3, z + 1.45, 'gold')
    m.box(x - 1.5, 15, z - 1.4, x + 1.5, 18, z + 1.4, 'skin'); m.box(x - 1.7, 18, z - 1.6, x + 1.7, 22.5, z + 1.6, 'black')
    m.box(x - 0.9, 16.4, z - 1.5, x + 0.9, 16.8, z - 1.4, 'black')
    for k, (c, r) in enumerate((('green', 'red'), ('blue', 'white'), ('red', 'gold'))):
        m.present(W + 3 + k * 2.5, 1.5 + (k == 2) * 4, -Dp + k * 2, W + 7 + k * 2.5, 5.5 + (k == 2) * 4, -Dp + 4 + k * 2, c, r, w=0.6)
    D.pine(m, W + 9, 0, 8, 24, 4.5, lights=['g_red', 'g_yellow', 'g_blue', 'g_green'])


def fish(m, x, y, z, col, L=3.6):
    m.ell(x, y, z, L / 2, 0.6, 0.8, col)
    m.box(x + L / 2 - 0.2, y - 0.7, z - 0.2, x + L / 2 + 0.8, y + 0.7, z + 0.2, col)


def fish_goods(m, W, Dp, rnd):
    m.box(-21, 16.5, -Dp - 0.8, 21, 17.6, -Dp + 4.5, 'light_blue')     # bed of crushed ice
    for _ in range(14):
        x = rnd.uniform(-20, 20)
        m.box(x - 0.6, 17.6, -Dp + rnd.uniform(-0.5, 3.5), x + 0.6, 17.9, -Dp + rnd.uniform(0.5, 4), 'white')
    for k in range(9):
        fish(m, -18 + k * 4.4, 18.3, -Dp + 1 + (k % 2) * 2, ['silver', 'pink', 'gray', 'orange'][k % 4])
    for y in (25, 32):                                                 # jars of pickled herring = cans
        for x in range(-W + 4, W - 3, 3):
            m.cyl('y', x, Dp - 4, y, y + 2.5, 1, 1, rnd.choice(['silver', 'gold', 'teal']))
    for i, x in enumerate(range(-W + 1, W, 4)):                        # smoked fish hanging by the tail
        m.box(x - 0.1, 36, -Dp - 7.3, x + 0.1, 39.2, -Dp - 7.1, 'tan')
        m.ell(x, 34, -Dp - 7.2, 0.7, 2, 0.5, ['ginger', 'dark_ginger'][i % 2])
        m.box(x - 0.6, 35.8, -Dp - 7.4, x + 0.6, 36.4, -Dp - 7, ['ginger', 'dark_ginger'][i % 2])
    for k in range(5):                                                 # fishing net on the back wall
        m.box(-W + 3, 36 + k * 1.6, Dp - 2.4, W - 3, 36.2 + k * 1.6, Dp - 2.2, 'dark_gray')
    for x in range(-W + 3, W - 2, 3):
        m.box(x, 36, Dp - 2.4, x + 0.2, 42.6, Dp - 2.2, 'dark_gray')


def fish_extras(m, W, Dp, rnd):
    for k in range(2):
        m.cyl('y', -W - 6, -Dp + 2 + k * 7, 1.5, 9.5, 3, 3, 'wood', n=3)
        m.disc(-W - 6, -Dp + 2 + k * 7, 9.5, 10, 2.6, 2.6, 'light_blue')
        fish(m, -W - 6, 10.4, -Dp + 2 + k * 7, 'silver')
    m.tube([(W + 4, 1.5, -Dp), (W + 9, 20, -Dp + 2)], 0.5, ['brown'])   # fishing rod leaning on the stall
    m.tube([(W + 9, 20, -Dp + 2), (W + 10, 12, -Dp + 2)], 0.15, ['white'], step=0.4)
    m.box(W + 3, 1.5, -Dp + 4, W + 10, 5, -Dp + 10, 'light_wood'); m.box(W + 3.2, 5, -Dp + 4.2, W + 9.8, 5.5, -Dp + 9.8, 'light_blue')
    lantern_post(m, W + 7, Dp - 2)


def pretzel(m, x, y, z, ps=0.5, col='ginger'):
    m.pixels(['.ppp.ppp.', 'p...p...p', 'p..p.p..p', '.pp...pp.', '..p...p..', '...ppp...'], x, y, z, ps, {'p': col}, 0.6)


def pretzels_goods(m, W, Dp, rnd):
    for i, x in enumerate(range(-W, W - 2, 6)):                        # giant pretzels hanging from the awning
        m.box(x + 2.2, 37, -Dp - 7.3, x + 2.4, 39.2, -Dp - 7.1, 'red')
        pretzel(m, x, 37.2, -Dp - 7.0, 0.55, ['ginger', 'dark_ginger'][i % 2])
    for k in range(5):                                                 # loaves and stollen on the counter
        x = -19 + k * 4.5
        m.ell(x, 17.6, -Dp + 2, 1.9, 1.2, 1.2, ['tan', 'ginger', 'tan', 'cream', 'ginger'][k])
        if k == 3:
            m.box(x - 1.8, 18.6, -Dp + 1, x + 1.8, 18.9, -Dp + 3, 'white')
    m.box(5, 16.5, -Dp, 13, 18, -Dp + 4, 'light_wood')                # basket of rolls
    for k in range(6):
        m.ell(6.3 + (k % 3) * 2.7, 18.6, -Dp + 1.2 + (k // 3) * 1.8, 1, 0.8, 0.8, 'tan')
    pretzel(m, 15, 22.4, -Dp + 2, 0.6)                                 # pretzel stand
    m.box(17.2, 16.5, -Dp + 1.8, 17.6, 19.6, -Dp + 2.2, 'dark_brown')
    for y in (25, 32):
        for x in range(-W + 4, W - 4, 4):
            m.ell(x + 1.5, y + 1, Dp - 4, 1.6, 1, 1.2, rnd.choice(['tan', 'ginger', 'dark_ginger']))


def pretzels_extras(m, W, Dp, rnd):
    for k in range(3):                                                 # flour sacks
        m.box(-W - 9 + k * 0.3, 1.5 + k * 5, -5 + k, -W - 3 - k * 0.3, 6.5 + k * 5, 2 - k, 'cream')
        m.box(-W - 9.1 + k * 0.3, 3 + k * 5, -5.1 + k, -W - 2.9 - k * 0.3, 3.6 + k * 5, 2.1 - k, 'red')
    m.box(W + 3, 1.5, -Dp, W + 11, 7.5, -Dp + 6, 'yellow')             # hay bale
    m.box(W + 2.9, 3, -Dp - 0.1, W + 11.1, 3.6, -Dp + 6.1, 'gold')
    D.pine(m, W + 8, 0, 6, 22, 4, lights=['g_red', 'g_white'])


def lollipop(m, x, z, y0, h, r, a, b):
    m.box(x - 0.25, y0, z - 0.25, x + 0.25, y0 + h, z + 0.25, 'white')
    m.cyl('z', x, y0 + h + r, z - 0.4, z + 0.4, r, r, a)
    m.cyl('z', x, y0 + h + r, z - 0.5, z + 0.5, r * 0.55, r * 0.55, b)
    m.cyl('z', x, y0 + h + r, z - 0.6, z + 0.6, r * 0.2, r * 0.2, a)


def candy_goods(m, W, Dp, rnd):
    for k in range(6):                                                 # jars of sweets
        x = -20 + k * 4
        m.box(x - 1.4, 16.5, -Dp + 0.5, x + 1.4, 20.5, -Dp + 3.5, 'white')
        for j in range(5):
            m.box(x - 1.3 + (j % 2) * 1.2, 16.8 + j * 0.7, -Dp + 0.4, x - 0.1 + (j % 2) * 1.2, 17.6 + j * 0.7, -Dp + 0.6,
                  ['red', 'green', 'yellow', 'purple', 'pink'][(j + k) % 5])
        m.box(x - 1.6, 20.5, -Dp + 0.3, x + 1.6, 21.3, -Dp + 3.7, ['red', 'green', 'gold'][k % 3])
    for k in range(4):
        lollipop(m, 6 + k * 3.5, -Dp + 2, 16.5, 4 + (k % 2) * 2, 1.5, ['red', 'blue', 'green', 'purple'][k], 'white')
    for y in (25, 32):                                                 # gumdrops and wrapped sweets
        for x in range(-W + 4, W - 3, 2):
            m.ell(x, y + 0.8, Dp - 4, 0.8, 0.9, 0.8, rnd.choice(['red', 'green', 'yellow', 'purple', 'orange']), ymin=y)
    for i, x in enumerate(range(-W + 1, W, 5)):                        # wrapped candies hanging from the awning
        m.box(x + 1.4, 36.5, -Dp - 7.3, x + 1.6, 39.2, -Dp - 7.1, 'white')
        c = ['red', 'green', 'gold', 'purple', 'blue'][i % 5]
        m.pixels(['c...c', 'cc.cc', 'ccccc', 'cc.cc', 'c...c'], x, 37, -Dp - 6.9, 0.6, {'c': c}, 0.6)
        m.box(x + 0.9, 35, -Dp - 7.4, x + 2.1, 36.4, -Dp - 6.8, 'white')


def candy_extras(m, W, Dp, rnd):
    D.cane(m, -W - 6, -Dp + 2, 0, 26, 3, 1.6)                           # giant candy canes either side
    D.cane(m, W + 6, -Dp + 2, 0, 26, 3, 1.6, hook=-1)
    lollipop(m, -W - 7, 6, 1.5, 14, 3.5, 'pink', 'white')
    lollipop(m, W + 7, 6, 1.5, 12, 3, 'teal', 'white')


def trees_goods(m, W, Dp, rnd):
    for k, x in enumerate((-18, -9, 9, 18)):                           # potted little trees on the counter
        m.cyl('y', x, -Dp + 2, 16.5, 18.5, 1.6, 1.6, ['red', 'brown', 'green', 'red'][k])
        D.pine(m, x, 18.5, -Dp + 2, 8, 2.2, snow=k % 2 == 0, lights=['g_red', 'g_yellow'] if k == 1 else None)
    for y in (25, 32):                                                 # saplings in pots
        for x in range(-W + 4, W - 3, 4):
            m.cyl('y', x, Dp - 4, y, y + 1.4, 0.9, 0.9, 'brick')
            m.ell(x, y + 2.8, Dp - 4, 1, 1.4, 1, 'pine')
    for i, x in enumerate(range(-W + 1, W, 3)):                        # pine cones hanging from the awning
        L = [1, 2.2, 1.6][i % 3]
        m.box(x - 0.05, 37.5 - L, -Dp - 7.25, x + 0.05, 39.2, -Dp - 7.15, 'red')
        m.ell(x, 36.6 - L, -Dp - 7.2, 0.7, 1.1, 0.7, 'dark_brown')


def trees_extras(m, W, Dp, rnd):
    for k in range(3):                                                 # cut trees leaning in a row, wrapped in netting
        x = -W - 6 - k * 0.5
        D.pine(m, x, 0, -Dp + 2 + k * 8, 20 - k * 2, 3.6)
    for k in range(4):                                                 # log pile
        for j in range(3 - k // 2):
            m.cyl('z', W + 5 + j * 2.6 + (k % 2) * 1.3, 2.7 + k * 2.2, -Dp - 2, -Dp + 6, 1.2, 1.2, 'wood')
    m.cyl('y', W + 11, Dp - 4, 0, 4, 2, 2, 'wood'); m.disc(W + 11, Dp - 4, 4, 4.4, 2.1, 2.1, 'tan')        # stump with an axe
    m.box(W + 10.8, 4.4, Dp - 4.2, W + 11.2, 10, Dp - 3.8, 'brown'); m.box(W + 10, 4, Dp - 4.4, W + 12, 6, Dp - 3.6, 'silver')


def ring(m, cx, cy, z, r, t, col, n=20):
    m.tube([(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n), z) for k in range(n + 1)], t, [col], step=t * 0.6)


def wreath(m, cx, cy, z, r=2.6, berries=True, bow_col='red'):
    ring(m, cx, cy, z, r, 1.3, 'holly')
    if berries:
        for k in range(5):
            a = k * 1.3
            m.box(cx + r * math.cos(a) - 0.3, cy + r * math.sin(a) - 0.3, z - 0.9, cx + r * math.cos(a) + 0.3, cy + r * math.sin(a) + 0.3, z - 0.6, 'red')
    D.bow(m, cx, cy - r, z - 0.7, bow_col, 0.7)


def poinsettia(m, x, y, z, s=1.0):
    m.cyl('y', x, z, y, y + 1.6 * s, 1.2 * s, 1.2 * s, 'gold')
    for a in range(5):
        t = a * 2 * math.pi / 5
        m.box(x + 1.4 * s * math.cos(t) - 0.6 * s, y + 1.6 * s, z + 1.4 * s * math.sin(t) - 0.6 * s,
              x + 1.4 * s * math.cos(t) + 0.6 * s, y + 2.2 * s, z + 1.4 * s * math.sin(t) + 0.6 * s, 'red')
    m.box(x - 0.4 * s, y + 2, z - 0.4 * s, x + 0.4 * s, y + 2.5 * s, z + 0.4 * s, 'yellow')


def wreaths_goods(m, W, Dp, rnd):
    for k, x in enumerate((-16, -8, 8, 16)):                           # wreaths on the back wall
        wreath(m, x, 39, Dp - 2.3, 3, bow_col=['red', 'gold', 'red', 'navy'][k])
    for y in (25, 32):
        for x in range(-W + 5, W - 4, 5):
            poinsettia(m, x, y, Dp - 4, 0.8)
    for k in range(5):
        poinsettia(m, -18 + k * 4, 16.5, -Dp + 2, 1.0)
    for k in range(3):                                                 # holly bundles
        x = 6 + k * 5
        for j in range(4):
            m.box(x + j * 0.8 - 1.2, 16.5, -Dp + 1, x + j * 0.8 - 0.6, 18.4, -Dp + 3, 'holly')
        m.box(x - 1, 18.2, -Dp + 1.5, x + 1.8, 18.8, -Dp + 2.5, 'red')
    for i, x in enumerate(range(-W + 2, W, 7)):                        # mistletoe balls hanging from the awning
        m.box(x - 0.1, 36, -Dp - 7.3, x + 0.1, 39.2, -Dp - 7.1, 'red')
        m.ell(x, 35, -Dp - 7.2, 1.3, 1.1, 1.3, 'green')
        m.box(x - 0.3, 34, -Dp - 7.5, x + 0.3, 34.6, -Dp - 6.9, 'white')


def wreaths_extras(m, W, Dp, rnd):
    m.box(-W - 11, 4, -Dp, -W - 3, 5, -Dp + 10, 'light_wood')            # flower cart
    for z in (-Dp + 1, -Dp + 9):
        m.cyl('z', -W - 7, 3, z - 0.4, z + 0.4, 2.5, 2.5, 'dark_brown')
    for k in range(4):
        poinsettia(m, -W - 9 + (k % 2) * 4, 5, -Dp + 2.5 + (k // 2) * 5, 1.1)
    wreath(m, W + 1.2, 10, -Dp + 6, 3)
    lantern_post(m, W + 7, -Dp - 2)


def skate(m, x, y, z, col='white'):
    m.box(x, y, z - 0.5, x + 1.4, y + 3, z + 0.5, col); m.box(x, y, z - 0.5, x + 2.6, y + 1.2, z + 0.5, col)
    m.box(x - 0.3, y - 0.8, z - 0.15, x + 2.9, y, z + 0.15, 'silver')


def skates_goods(m, W, Dp, rnd):
    for i, x in enumerate(range(-W + 1, W - 2, 5)):                    # pairs of skates hanging by the laces
        m.box(x + 1, 37, -Dp - 7.3, x + 3.4, 39.2, -Dp - 7.1, 'white')
        skate(m, x, 33.6, -Dp - 7.6, ['white', 'cream', 'black'][i % 3]); skate(m, x + 2, 33.2, -Dp - 6.8, ['white', 'cream', 'black'][i % 3])
    for k in range(4):                                                 # bobble hats and mittens on the counter
        x = -18 + k * 5
        c = ['red', 'green', 'navy', 'white'][k]
        m.box(x - 1.6, 16.5, -Dp + 1, x + 1.6, 18.6, -Dp + 3.4, c); m.ell(x, 19.2, -Dp + 2.2, 0.9, 0.8, 0.9, 'white' if c != 'white' else 'red')
    for k in range(3):
        x = 5 + k * 5
        m.box(x, 16.5, -Dp + 0.5, x + 3, 17.3, -Dp + 4, ['red', 'teal', 'purple'][k])
    for y in (25, 32):                                                 # boots
        for x in range(-W + 4, W - 4, 4):
            c = rnd.choice(['dark_brown', 'brown', 'red', 'black'])
            m.box(x, y, Dp - 5, x + 1.4, y + 3, Dp - 3, c); m.box(x, y, Dp - 5, x + 2.6, y + 1.2, Dp - 3, c)
            m.box(x - 0.1, y + 2.6, Dp - 5.1, x + 1.5, y + 3.2, Dp - 2.9, 'white')


def skates_extras(m, W, Dp, rnd):
    x0, z0 = -W - 12, -Dp                                               # red sled
    for s in (0, 6):
        m.tube([(x0, 1.5, z0 + s), (x0 + 8, 1.5, z0 + s), (x0 + 10, 3.5, z0 + s), (x0 + 9, 5, z0 + s)], 0.6, ['gold'])
    m.box(x0, 3, z0 - 0.5, x0 + 8, 4, z0 + 6.5, 'red')
    for k in range(2):                                                 # skis leaning on the side wall
        m.box(W + 1.5 + k * 1.5, 1.5, -Dp + 3 + k * 4, W + 2.1 + k * 1.5, 22, -Dp + 4.5 + k * 4, ['blue', 'red'][k])
    D.pine(m, W + 9, 0, 4, 24, 4.5, lights=['g_cool', 'g_blue', 'g_white'])


def lights_goods(m, W, Dp, rnd):
    for i, x in enumerate(range(-W + 1, W, 4)):                        # lanterns hanging at different heights
        L = [0.5, 2, 1.2, 2.8][i % 4]
        m.box(x - 0.05, 37.4 - L, -Dp - 7.25, x + 0.05, 39.2, -Dp - 7.15, 'black')
        m.box(x - 1.1, 34.4 - L, -Dp - 8.3, x + 1.1, 37.4 - L, -Dp - 6.1, 'black')
        m.box(x - 0.8, 34.7 - L, -Dp - 8.4, x + 0.8, 37.1 - L, -Dp - 6, ['g_flame', 'g_white', 'g_cool'][i % 3])
    for k in range(4):                                                 # coils of fairy lights on the counter
        x = -18 + k * 5.5
        ring(m, x, 18, -Dp + 2, 1.6, 0.4, 'dark_green', 14)
        for j in range(6):
            a = j * math.pi / 3
            m.box(x + 1.6 * math.cos(a) - 0.3, 18 + 1.6 * math.sin(a) - 0.3, -Dp + 1.4, x + 1.6 * math.cos(a) + 0.3,
                  18 + 1.6 * math.sin(a) + 0.3, -Dp + 1.8, ['g_red', 'g_yellow', 'g_blue', 'g_green'][(j + k) % 4])
    for k in range(3):                                                 # jars of glowing lights
        x = 6 + k * 5
        m.box(x - 1.4, 16.5, -Dp + 0.8, x + 1.4, 20.5, -Dp + 3.6, ['g_yellow', 'g_cool', 'g_purple'][k])
        m.box(x - 1.6, 20.5, -Dp + 0.6, x + 1.6, 21.2, -Dp + 3.8, 'silver')
    for y in (25, 32):
        for x in range(-W + 4, W - 3, 4):
            m.box(x, y, Dp - 5, x + 2, y + 2.4, Dp - 3, 'black'); m.box(x + 0.3, y + 0.3, Dp - 5.1, x + 1.7, y + 2.1, Dp - 2.9, 'g_flame')
    bulbs_along(m, [(-W + 3, 43, Dp - 2.4), (0, 40, Dp - 2.4), (W - 3, 43, Dp - 2.4)], ['g_red', 'g_blue', 'g_yellow', 'g_green'], every=1.6)


def lights_extras(m, W, Dp, rnd):
    lantern_post(m, -W - 7, -Dp - 2)
    lantern_post(m, W + 7, -Dp - 2)
    D.pine(m, W + 9, 0, 8, 24, 4.5, lights=['g_red', 'g_yellow', 'g_blue', 'g_green', 'g_purple'])


def bell(m, x, y, z, r=1.2, col='gold'):
    m.ell(x, y + r, z, r, r * 1.2, r, col, ymin=y)
    m.box(x - r * 1.2, y, z - r * 1.2, x + r * 1.2, y + 0.4, z + r * 1.2, col)
    m.ell(x, y - 0.1, z, r * 0.35, r * 0.35, r * 0.35, 'dark_gold')


def bells_goods(m, W, Dp, rnd):
    for i, x in enumerate(range(-W + 1, W, 3)):                        # bells of different sizes
        L = [0.5, 2, 1, 2.5, 1.5][i % 5]
        m.box(x - 0.05, 37.4 - L, -Dp - 7.25, x + 0.05, 39.2, -Dp - 7.15, 'red')
        bell(m, x, 35 - L, -Dp - 7.2, 0.8 + (i % 3) * 0.25, ['gold', 'silver', 'gold'][i % 3])
    m.box(-19, 16.5, -Dp + 0.5, -11, 19, -Dp + 3.5, 'dark_gray')           # anvil
    m.box(-17.5, 19, -Dp + 0.8, -12.5, 20.6, -Dp + 3.2, 'dark_gray'); m.box(-20.5, 20.6, -Dp + 0.5, -10, 21.8, -Dp + 3.5, 'dark_gray')
    m.box(-9, 16.5, -Dp, -1, 17.2, -Dp + 4, 'dark_brown')                   # sleigh bell strap
    for k in range(5):
        bell(m, -8 + k * 1.6, 17.2, -Dp + 2, 0.55)
    for k in range(4):                                                     # horseshoes
        x = 4 + k * 4
        m.pixels(['s.s', 's.s', 'sss'], x, 19, -Dp + 2, 0.8, {'s': 'silver'}, 0.4)
    for y in (25, 32):
        for x in range(-W + 4, W - 3, 3):
            bell(m, x, y, Dp - 4, 0.7, rnd.choice(['gold', 'silver', 'gold', 'brick']))


def bells_extras(m, W, Dp, rnd):
    m.box(-W - 12, 1.5, -Dp, -W - 3, 10, -Dp + 8, 'brick')                 # little forge with glowing coals
    m.box(-W - 11, 10, -Dp + 1, -W - 4, 10.6, -Dp + 7, 'g_flame')
    m.box(-W - 9, 10, -Dp + 6, -W - 6, 24, -Dp + 8, 'dark_gray')
    for i in range(4):
        m.ell(-W - 7.5 + math.sin(i) * 0.8, 26 + i * 2.6, -Dp + 7, 1 + i * 0.3, 0.8 + i * 0.2, 1 + i * 0.3, 'silver' if i % 2 else 'white')
    lantern_post(m, W + 7, -Dp - 2)


def cider_goods(m, W, Dp, rnd):
    for k in range(2):                                                     # barrels on their side with taps
        x = -14 + k * 9
        m.cyl('z', x, 21, -Dp + 0.5, -Dp + 5, 3.4, 3.4, 'wood', n=3)
        m.box(x - 3.5, 18.5, -Dp + 1.2, x + 3.5, 19.1, -Dp + 4.2, 'dark_gray')
        m.box(x - 0.3, 19, -Dp - 0.3, x + 0.3, 21, -Dp + 0.5, 'gold'); m.box(x - 0.6, 19, -Dp - 0.6, x + 0.6, 19.5, -Dp, 'gold')
    m.box(-21, 16.5, -Dp, -18.5, 18.5, -Dp + 4, 'dark_gray')
    m.ell(9, 19.5, -Dp + 2, 3.5, 3, 3, 'dark_gray', n=3)                   # steaming pot
    m.box(5, 16.5, -Dp + 0.5, 13, 17, -Dp + 3.5, 'g_flame')
    for k in range(3):
        m.box(8 + k * 0.6, 21.8, -Dp + 1.5, 8.4 + k * 0.6, 25, -Dp + 1.9, 'ginger')
    for i in range(4):
        r = 1 + i * 0.4
        m.ell(9 + i * 0.6, 26 + i * 3, -Dp + 2, r, r * 0.7, r, 'white')
    for k in range(4):
        m.cyl('y', 15.5 + (k % 2) * 3, -Dp + 1.5 + (k // 2) * 2, 16.5, 19, 1, 1, ['red', 'cream'][k % 2])
    for y in (25, 32):                                                     # crates of apples
        for x in range(-W + 4, W - 4, 6):
            m.box(x, y, Dp - 5.5, x + 5, y + 1.6, Dp - 2.5, 'light_wood')
            for j in range(3):
                m.ell(x + 1 + j * 1.5, y + 2, Dp - 4, 0.8, 0.7, 0.8, rnd.choice(['red', 'red', 'green', 'gold']))
    for i, x in enumerate(range(-W + 2, W, 6)):                            # garland of dried apple rings
        m.box(x - 0.1, 37, -Dp - 7.3, x + 0.1, 39.2, -Dp - 7.1, 'tan')
        ring(m, x, 35.8, -Dp - 7.2, 1, 0.5, 'cream', 10); m.box(x - 1.3, 35.6, -Dp - 7.3, x - 0.9, 36, -Dp - 7.1, 'red')


def cider_extras(m, W, Dp, rnd):
    for k in range(3):
        m.cyl('y', -W - 6 + (k == 2) * 3, -Dp + 2 + k * 6 - (k == 2) * 3, 1.5 + (k == 2) * 8, 9.5 + (k == 2) * 8, 3, 3, 'wood', n=3)
    m.disc(-W - 3, -Dp + 5, 17.5, 18.2, 2.8, 2.8, 'snow')
    m.box(W + 3, 1.5, -Dp, W + 10, 6, -Dp + 5, 'light_wood')                # apple crate
    for j in range(6):
        m.ell(W + 4.2 + (j % 3) * 2.3, 6.8, -Dp + 1.2 + (j // 3) * 2.4, 1, 0.9, 1, ['red', 'red', 'green'][j % 3])
    D.pine(m, W + 8, 0, 8, 22, 4, lights=['g_red', 'g_yellow'])


def rocket(m, x, y, z, h, col, r=0.7):
    m.cyl('y', x, z, y, y + h, r, r, col)
    m.box(x - r * 1.1, y + h * 0.4, z - r * 1.1, x + r * 1.1, y + h * 0.5, z + r * 1.1, 'white')
    m.cyl('y', x, z, y + h, y + h + r, r * 0.6, r * 0.6, 'gold'); m.box(x - 0.15, y - h * 0.6, z - 0.15, x + 0.15, y, z + 0.15, 'tan')


def fireworks_goods(m, W, Dp, rnd):
    for k in range(9):                                                     # rockets standing in racks
        rocket(m, -19 + k * 2.6, 19, -Dp + 2, rnd.uniform(3, 6), ['red', 'blue', 'green', 'gold', 'purple'][k % 5])
    m.box(-21, 16.5, -Dp + 1, 3, 19, -Dp + 3, 'dark_brown')
    for k in range(3):
        m.box(7 + k * 4.5, 16.5, -Dp + 0.5, 10 + k * 4.5, 19.5, -Dp + 3.5, ['red', 'navy', 'red'][k])
        m.box(7 + k * 4.5, 18, -Dp + 0.4, 10 + k * 4.5, 18.6, -Dp + 3.6, 'white')
    for y in (25, 32):
        for x in range(-W + 4, W - 3, 2):
            m.ell(x, y + 0.7, Dp - 4, 0.7, 0.7, 0.7, rnd.choice(['red', 'blue', 'gold', 'green', 'purple', 'white']))
    for i, x in enumerate(range(-W + 1, W, 5)):                            # glowing stars hanging from the awning
        m.box(x + 1.4, 36.5, -Dp - 7.3, x + 1.6, 39.2, -Dp - 7.1, 'gold')
        m.pixels(['..s..', 'sssss', '.sss.', 's...s'], x, 36.8, -Dp - 6.9, 0.6, {'s': ['g_star', 'g_red', 'g_blue', 'g_green', 'g_purple'][i % 5]}, 0.6)


def fireworks_extras(m, W, Dp, rnd):
    rocket(m, -W - 7, 6, -Dp + 3, 18, 'red', 1.8)                           # giant display rocket
    m.box(-W - 9.5, 1.5, -Dp + 0.5, -W - 4.5, 6, -Dp + 5.5, 'dark_gray')
    for k, (c, r) in enumerate((('navy', 'gold'), ('red', 'white'))):
        m.present(W + 3 + k * 2, 1.5 + k * 4, -Dp + k * 2, W + 8 + k * 2, 5.5 + k * 4, -Dp + 5 + k * 2, c, r, w=0.6)
    lantern_post(m, W + 9, Dp - 2)


def note(m, x, y, z, col, ps=0.6):
    m.pixels(['.cc', '.c.', '.c.', 'cc.', 'cc.'], x, y, z, ps, {'c': col}, 0.4)


def music_goods(m, W, Dp, rnd):
    for k in range(4):                                                     # note blocks
        x = -19 + k * 4
        m.box(x - 1.6, 16.5, -Dp + 0.5, x + 1.6, 19.7, -Dp + 3.7, 'brown')
        note(m, x - 0.8, 19.1, -Dp + 0.4, 'black', 0.45)
    m.box(-2, 16.5, -Dp + 0.5, 4, 21, -Dp + 4.5, 'dark_brown'); m.box(-1.6, 21, -Dp + 1, 3.6, 21.3, -Dp + 4, 'black')   # jukebox
    m.disc(1, -Dp + 2.5, 21.3, 21.6, 1.8, 1.8, 'black'); m.disc(1, -Dp + 2.5, 21.6, 21.7, 0.6, 0.6, 'red')
    m.cyl('y', 9, -Dp + 2, 16.5, 19.5, 2, 2, 'blue'); m.disc(9, -Dp + 2, 19.3, 19.8, 2.1, 2.1, 'white')   # drum
    m.tube([(14, 17.5, -Dp + 2), (17, 19, -Dp + 2), (19, 22, -Dp + 2)], 0.8, ['gold'])                     # horn
    m.cyl('y', 19, -Dp + 2, 22, 23.5, 1.6, 1.6, 'gold')
    for x in range(-W + 5, W - 4, 6):                                       # records on the back wall
        for y in (27.5, 34.5):
            m.cyl('z', x, y, Dp - 2.6, Dp - 2.3, 2.2, 2.2, 'black')
            m.cyl('z', x, y, Dp - 2.7, Dp - 2.5, 0.8, 0.8, rnd.choice(['red', 'gold', 'green', 'teal', 'purple']))
    for i, x in enumerate(range(-W + 1, W, 4)):                            # glowing notes hanging from the awning
        m.box(x + 0.9, 37, -Dp - 7.3, x + 1.1, 39.2, -Dp - 7.1, 'gold')
        note(m, x, 37, -Dp - 6.9, ['g_red', 'g_green', 'g_blue', 'g_yellow', 'g_purple'][i % 5])


def music_extras(m, W, Dp, rnd):
    x, z = -W - 7, -Dp + 3                                                 # carolling snowman with a song sheet
    m.ell(x, 5, z, 4, 3.6, 4, 'snow'); m.ell(x, 11, z, 3, 2.8, 3, 'snow'); m.ell(x, 16, z, 2.2, 2.2, 2.2, 'snow')
    m.box(x - 0.3, 15.8, z - 4, x + 0.3, 16.4, z - 2, 'carrot')
    for sx in (-1, 1):
        m.box(x + sx * 0.8 - 0.25, 16.8, z - 2.2, x + sx * 0.8 + 0.25, 17.3, z - 2, 'black')
    m.box(x - 2.4, 17.6, z - 2.4, x + 2.4, 18.2, z + 2.4, 'black'); m.box(x - 1.6, 18.2, z - 1.6, x + 1.6, 21, z + 1.6, 'black')
    m.box(x - 2.2, 10, z - 3.5, x + 2.2, 12.8, z - 3.2, 'paper')
    D.pine(m, W + 9, 0, 4, 24, 4.5, lights=['g_red', 'g_green', 'g_blue', 'g_yellow'])


def gifts_goods(m, W, Dp, rnd):
    for k in range(3):                                                     # rolls of wrapping paper
        y = 17.5
        for j in range(7):
            m.cyl('x', y + k * 2.1, -Dp + 2, -20 + j * 2, -18 + j * 2, 1, 1, [('red', 'white'), ('green', 'gold'), ('blue', 'white')][k][j % 2])
    for k in range(4):
        x = 2 + k * 4.5
        m.present(x, 16.5, -Dp + 0.5, x + 3.5, 19 + (k % 2), -Dp + 4, ['green', 'gold', 'purple', 'red'][k], ['red', 'red', 'gold', 'white'][k], w=0.5)
    for y in (25, 32):                                                     # ribbon spools
        for x in range(-W + 4, W - 3, 3):
            m.cyl('z', x, y + 1.2, Dp - 5, Dp - 3.5, 1.2, 1.2, rnd.choice(['red', 'gold', 'green', 'blue', 'pink', 'silver']))
    for i, x in enumerate(range(-W + 1, W, 5)):                            # bows hanging from the awning
        m.box(x + 1.4, 36.5, -Dp - 7.3, x + 1.6, 39.2, -Dp - 7.1, 'gold')
        D.bow(m, x + 1.5, 35.5, -Dp - 7.2, ['red', 'gold', 'green', 'blue', 'pink'][i % 5], 0.9)


def gifts_extras(m, W, Dp, rnd):
    pile = (('red', 'gold', 6, 5), ('green', 'red', 5, 4), ('blue', 'white', 4, 4), ('purple', 'gold', 4, 3), ('gold', 'red', 3, 3))
    y = 1.5
    for k, (c, r, s, h) in enumerate(pile):                                # stack of presents taller than the counter
        x = -W - 8 + k * 0.4
        m.present(x - s / 2, y, -Dp + 3 - s / 2, x + s / 2, y + h, -Dp + 3 + s / 2, c, r, w=0.6)
        y += h + 0.9
    for k, (c, r) in enumerate((('pink', 'white'), ('teal', 'gold'), ('red', 'green'))):
        m.present(W + 3 + k * 2.5, 1.5, -Dp + k * 2.5, W + 7 + k * 2.5, 5 + k, -Dp + 4 + k * 2.5, c, r, w=0.6)
    D.pine(m, W + 9, 0, 8, 24, 4.5, lights=['g_red', 'g_yellow', 'g_blue', 'g_green'])


# ---------------------------------------------------------------- the twenty stalls and what they trade
# sells: (item, how many, price in coins)   buys: (item, how many, coins paid)
# ids without a namespace are minecraft:, santa: items need Santa's Workbench and xmas: items Gingerbread Oven.
def S(key, name, sign, look, villager, goods, extras, recipe, sells, buys):
    roof, aw1, aw2, bg, fg, posts, crest = look
    return dict(key=key, name=name, sign=sign, roof=roof, aw1=aw1, aw2=aw2, bg=bg, fg=fg, posts=posts, crest=crest,
                villager=villager, goods=goods, extras=extras, recipe=recipe, sells=sells, buys=buys)


PRESENTS = ['present', 'present_red', 'present_blue', 'present_gold', 'present_candy', 'present_purple', 'present_silver', 'present_pink']
STALLS = [
    S('cookies', 'Cookie Stall', 'COOKIES', ('dark_red', 'red', 'white', 'dark_red', 'gold', 'cane', 'cross'),
      ('brown', 'green', straw_hat), farmer_goods, farmer_extras, 'cookie',
      [('xmas:cookie_gingerbread', 4, 3), ('xmas:cookie_sugar', 4, 3), ('xmas:cookie_chocolate_chip', 4, 3), ('xmas:cookie_snickerdoodle', 4, 3),
       ('xmas:cookie_peppermint_chocolate', 4, 4), ('cookie', 8, 2), ('xmas:pumpkin_pie_slice', 2, 3), ('xmas:apple_pie_slice', 2, 3)],
      [('wheat', 20, 2), ('sugar', 16, 2), ('cocoa_beans', 12, 2)]),
    S('roasts', 'Roast Chestnut Grill', 'ROASTS', ('brown', 'dark_red', 'cream', 'black', 'gold', 'red', 'cross'),
      ('white', 'red', headband), butcher_goods, butcher_extras, 'cooked_beef',
      [('cooked_beef', 4, 4), ('cooked_porkchop', 4, 4), ('cooked_chicken', 4, 3), ('cooked_mutton', 4, 3), ('baked_potato', 8, 3), ('rabbit_stew', 1, 4)],
      [('beef', 10, 2), ('porkchop', 10, 2), ('chicken', 10, 2), ('potato', 20, 2)]),
    S('cocoa', 'Hot Cocoa Hut', 'COCOA', ('purple', 'purple', 'gold', 'navy', 'gold', 'gold', 'star'),
      ('purple', 'gold', cleric_hood), cleric_goods, cleric_extras, 'cocoa_beans',
      [('xmas:hot_cocoa', 1, 3), ('xmas:hot_cocoa_marshmallow', 1, 4), ('xmas:eggnog', 1, 4), ('xmas:marshmallow', 4, 2), ('xmas:cinnamon', 4, 2),
       ('xmas:cinnamon_bun', 2, 3), ('honey_bottle', 2, 3)],
      [('cocoa_beans', 10, 2), ('milk_bucket', 1, 2)]),
    S('sweaters', 'Knitted Sweater Stall', 'SWEATERS', ('dark_green', 'green', 'white', 'dark_green', 'white', 'red', 'cross'),
      ('brown', 'white', wool_hat), shepherd_goods, shepherd_extras, 'shears',
      [('santa:sweater_red', 1, 10), ('santa:sweater_green', 1, 10), ('santa:sweater_blue', 1, 10), ('santa:sweater_snowflake_navy', 1, 10),
       ('santa:sweater_gingerbread', 1, 10), ('santa:sweater_hearts', 1, 10), ('santa:sweater_snowman', 1, 10), ('santa:sweater_candy_cane', 1, 10),
       ('santa:bobble_beanie', 1, 6), ('red_wool', 8, 2)],
      [('white_wool', 16, 2), ('string', 16, 2)]),
    S('books', 'Book & Card Stall', 'BOOKS', ('navy', 'blue', 'white', 'navy', 'gold', 'gold', 'cross'),
      ('white', 'dark_red', librarian_cap), librarian_goods, librarian_extras, 'book',
      [('book', 1, 2), ('writable_book', 1, 4), ('bookshelf', 1, 6), ('paper', 16, 2), ('name_tag', 1, 10), ('empty_map', 1, 4),
       ('santa:card_stand', 1, 8), ('santa:christmas_guide', 1, 2)],
      [('paper', 24, 2), ('leather', 6, 2), ('sugar_cane', 24, 2)]),
    S('baubles', 'Ornament Shop', 'BAUBLES', ('teal', 'teal', 'white', 'dark_red', 'gold', 'cane', 'star'),
      ('white', 'gold', monocle_cap), cartographer_goods, cartographer_extras, 'glass',
      [('santa:ornament_red', 2, 4), ('santa:ornament_gold', 2, 4), ('santa:ornament_blue', 2, 4), ('santa:ornament_green', 2, 4),
       ('santa:ornament_silver', 2, 4), ('santa:ornament_purple', 2, 4), ('santa:star_lantern', 1, 8), ('santa:garland', 4, 6)],
      [('glass', 16, 2), ('amethyst_shard', 8, 2)]),
    S('candles', 'Candle Maker', 'CANDLES', ('dark_red', 'gold', 'dark_red', 'dark_red', 'cream', 'gold', 'bell'),
      ('cream', 'red', beanie('dark_red')), candles_goods, candles_extras, 'candle',
      [('candle', 2, 2), ('red_candle', 2, 2), ('green_candle', 2, 2), ('white_candle', 2, 2), ('yellow_candle', 2, 2),
       ('santa:window_candle', 1, 5), ('santa:christmas_candles', 1, 6)],
      [('honeycomb', 6, 2), ('string', 12, 2)]),
    S('toys', 'Toy Stall', 'TOYS', ('red', 'red', 'green', 'green', 'gold', 'cane', 'star'),
      ('green', 'red', elf_hat), toys_goods, toys_extras, 'painting',
      [('santa:teddy_bear', 1, 8), ('santa:toy_train', 1, 8), ('santa:rocking_horse', 1, 10), ('santa:toy_drum', 1, 6), ('santa:yo_yo', 1, 4),
       ('santa:spinning_top', 1, 4), ('santa:toy_robot', 1, 10), ('santa:toy_airplane', 1, 10), ('santa:wooden_blocks', 1, 5),
       ('santa:jack_in_the_box', 1, 8)],
      [('oak_planks', 32, 2), ('stick', 32, 2)]),
    S('fish', 'Smoked Fish Stall', 'FISH', ('navy', 'navy', 'white', 'teal', 'white', 'white', 'cross'),
      ('navy', 'yellow', fisher_hat), fish_goods, fish_extras, 'cod',
      [('cooked_cod', 4, 3), ('cooked_salmon', 4, 4), ('dried_kelp', 8, 2), ('tropical_fish', 1, 4), ('fishing_rod', 1, 5)],
      [('cod', 12, 2), ('salmon', 8, 2), ('ink_sac', 8, 2)]),
    S('bakery', 'Pretzel Bakery', 'PRETZELS', ('brown', 'orange', 'cream', 'dark_brown', 'gold', 'light_wood', 'bell'),
      ('white', 'tan', chef_hat), pretzels_goods, pretzels_extras, 'bread',
      [('bread', 4, 3), ('cake', 1, 8), ('pumpkin_pie', 2, 4), ('xmas:fruitcake', 1, 8), ('xmas:christmas_pudding', 1, 6),
       ('xmas:cinnamon_bun', 2, 3), ('xmas:yule_log', 1, 10), ('xmas:carrot_cake', 1, 10)],
      [('wheat', 20, 2), ('egg', 12, 2), ('milk_bucket', 1, 2)]),
    S('candy', 'Sweet Shop', 'CANDY', ('pink', 'pink', 'white', 'red', 'white', 'cane', 'star'),
      ('pink', 'white', beanie('red')), candy_goods, candy_extras, 'sugar',
      [('xmas:candy_cane', 4, 3), ('xmas:lollipop', 2, 3), ('xmas:peppermint_candy', 6, 2), ('xmas:gumdrop_red', 6, 2), ('xmas:gumdrop_green', 6, 2),
       ('xmas:gumdrop_yellow', 6, 2), ('xmas:fudge', 2, 3), ('xmas:toffee', 3, 3), ('xmas:chocolate_bar', 2, 3), ('xmas:chocolate_coins', 4, 3)],
      [('sugar', 16, 2), ('sugar_cane', 24, 2)]),
    S('trees', 'Christmas Tree Lot', 'TREES', ('dark_green', 'dark_green', 'cream', 'dark_brown', 'white', 'garland', 'star'),
      ('dark_green', 'red', beanie('red', 'white')), trees_goods, trees_extras, 'spruce_sapling',
      [('santa:christmas_tree', 1, 8), ('santa:christmas_tree_medium', 1, 14), ('santa:tall_christmas_tree', 1, 24), ('spruce_sapling', 4, 3),
       ('spruce_log', 8, 3), ('spruce_leaves', 16, 3)],
      [('stick', 32, 2), ('spruce_log', 16, 3)]),
    S('wreaths', 'Wreath & Poinsettia Stall', 'WREATHS', ('dark_red', 'dark_green', 'red', 'dark_green', 'gold', 'garland', 'cross'),
      ('green', 'red', santa_cap), wreaths_goods, wreaths_extras, 'sweet_berries',
      [('santa:wreath', 1, 8), ('santa:door_wreath', 1, 8), ('santa:poinsettia', 2, 5), ('santa:mistletoe', 2, 5), ('santa:holly_centerpiece', 1, 8),
       ('sweet_berries', 8, 2), ('vine', 8, 2)],
      [('sweet_berries', 16, 2), ('spruce_leaves', 24, 2)]),
    S('skates', 'Winter Wear & Skates', 'SKATES', ('slate', 'light_blue', 'white', 'navy', 'white', 'silver', 'star'),
      ('light_blue', 'white', beanie('light_blue')), skates_goods, skates_extras, 'leather_boots',
      [('santa:santa_hat', 1, 8), ('santa:elf_hat', 1, 8), ('santa:reindeer_antlers', 1, 8), ('santa:earmuffs', 1, 6), ('santa:santa_coat', 1, 14),
       ('santa:santa_pants', 1, 12), ('santa:santa_boots', 1, 8), ('santa:elf_shoes', 1, 8), ('santa:pajama_top', 1, 10), ('santa:pajama_pants', 1, 10)],
      [('leather', 6, 2), ('rabbit_hide', 8, 2)]),
    S('lights', 'Lights & Lanterns', 'LIGHTS', ('black', 'black', 'gold', 'black', 'gold', 'garland', 'star'),
      ('dark_gray', 'gold', top_hat), lights_goods, lights_extras, 'lantern',
      [('lantern', 2, 4), ('soul_lantern', 2, 5), ('torch', 16, 2), ('glowstone', 2, 4), ('sea_lantern', 1, 6), ('santa:string_lights_warm', 4, 6),
       ('santa:string_lights_redgreen', 4, 6), ('santa:string_lights_multi', 4, 6), ('santa:icicle_lights', 4, 6), ('santa:candy_cane_lamp', 1, 10)],
      [('coal', 12, 2), ('glowstone_dust', 8, 2)]),
    S('bells', 'Bell Forge', 'BELLS', ('dark_gray', 'dark_red', 'gold', 'black', 'gold', 'gold', 'bell'),
      ('dark_brown', 'dark_gray', goggles), bells_goods, bells_extras, 'iron_ingot',
      [('bell', 1, 16), ('santa:jingle_bells', 1, 6), ('santa:golden_bells', 1, 8), ('iron_bars', 8, 3), ('santa:candy_cane_sword', 1, 12),
       ('santa:candy_cane_pickaxe', 1, 12)],
      [('iron_ingot', 4, 3), ('coal', 12, 2)]),
    S('cider', 'Apple Cider Barn', 'CIDER', ('dark_red', 'red', 'cream', 'dark_green', 'gold', 'light_wood', 'cross'),
      ('dark_green', 'tan', straw_hat), cider_goods, cider_extras, 'apple',
      [('apple', 6, 2), ('golden_apple', 1, 16), ('honey_bottle', 2, 3), ('xmas:apple_pie', 1, 8), ('xmas:apple_pie_slice', 2, 3),
       ('glow_berries', 8, 3), ('sweet_berries', 8, 2)],
      [('apple', 12, 2), ('sugar', 16, 2)]),
    S('fireworks', 'Fireworks Stand', 'FIREWORKS', ('navy', 'navy', 'red', 'black', 'gold', 'cane', 'star'),
      ('red', 'gold', top_hat), fireworks_goods, fireworks_extras, 'gunpowder',
      [('firework_rocket', 4, 3), ('firework_star', 2, 3), ('gunpowder', 4, 3), ('paper', 12, 2), ('santa:snowball_launcher', 1, 12)],
      [('gunpowder', 6, 3), ('paper', 24, 2)]),
    S('music', 'Music & Carols', 'MUSIC', ('purple', 'lilac', 'white', 'purple', 'white', 'garland', 'bell'),
      ('lilac', 'white', santa_cap), music_goods, music_extras, 'noteblock',
      [('noteblock', 1, 4), ('jukebox', 1, 10), ('santa:christmas_jukebox', 1, 16), ('music_disc_cat', 1, 16), ('music_disc_blocks', 1, 16),
       ('music_disc_far', 1, 16), ('goat_horn', 1, 12), ('santa:toy_drum', 1, 6)],
      [('amethyst_shard', 8, 2), ('bone', 12, 2)]),
    S('gifts', 'Gift Wrap Stall', 'GIFTS', ('red', 'gold', 'red', 'red', 'white', 'cane', 'bell'),
      ('red', 'white', elf_hat), gifts_goods, gifts_extras, 'paper',
      [('santa:' + p, 1, 6) for p in PRESENTS] + [('santa:gift_box', 1, 10), ('santa:present_stack', 1, 12), ('string', 8, 2)],
      [('paper', 24, 2), ('string', 12, 2)]),
]


def build(spec):
    m = D.Model()
    stall(m, spec['sign'], spec['roof'], spec['aw1'], spec['aw2'], spec['bg'], spec['fg'], spec['posts'], spec['crest'],
          spec['villager'], spec['goods'], spec['extras'], seed=STALLS.index(spec))
    return m


# ---------------------------------------------------------------- the coin press and the coin
SYMBOLS = {   # 5x5 reel pictures
    'bell': (['.ggg.', 'ggggg', 'ggggg', 'ggggg', '..d..'], {'g': 'gold', 'd': 'dark_gold'}),
    'star': (['..y..', 'yyyyy', '.yyy.', '.y.y.', 'y...y'], {'y': 'yellow'}),
    'tree': (['..g..', '.ggg.', 'ggggg', '..b..', '..b..'], {'g': 'green', 'b': 'brown'}),
    'cane': (['.rw..', 'w..r.', '...w.', '...r.', '...w.'], {'r': 'red', 'w': 'red'}),
}
SPIN = 4                                                         # reel frames (block state market:spin)


def slot_machine(m):
    """Coin Press as a two-block Christmas slot machine, front -z, y 0..32 (the top block is y 16..32)."""
    m.box(-7.5, 0, -6.5, 7.5, 2, 6.5, 'dark_red'); m.box(-7.6, 2, -6.6, 7.6, 2.6, 6.6, 'gold')      # plinth
    m.box(-6.5, 2.6, -5.5, 6.5, 13, 5.5, 'red')                                                      # lower cabinet
    for x in (-6.5, 5.6):                                                                            # candy-cane corner trims
        for k, y in enumerate(range(3, 13)):
            m.box(x - 0.1, y, -5.7, x + 1, y + 1, -4.8, 'white' if k % 2 else 'red')
    m.box(-3.6, 4, -7.4, 3.6, 4.8, -5.5, 'silver'); m.box(-3.6, 4.8, -7.6, 3.6, 5.6, -7.2, 'silver')   # payout tray
    for x, z in ((-2, -6.6), (0.5, -6), (2.2, -6.8), (-0.6, -6.9)):
        m.cyl('y', x, z, 4.8, 5.1, 0.8, 0.8, 'gold')
    m.box(-2.6, 5.4, -5.7, 2.6, 7.6, -5.5, 'black'); m.box(-2.3, 5.7, -5.75, 2.3, 7.3, -5.7, 'g_window')  # payout chute
    words(m, 'COINS', 0, 11.6, -5.55, 0.42, 'gold')
    m.box(-6.8, 13, -7, 6.8, 14.4, 5.6, 'dark_red'); m.box(-6.9, 14.4, -7.1, 6.9, 14.8, 5.7, 'gold')  # button deck
    for k, c in enumerate(('g_red', 'g_green', 'g_yellow')):
        m.box(-5 + k * 2.4, 14.8, -6.4, -3.6 + k * 2.4, 15.4, -5.2, c)
    m.box(2.8, 14.8, -6.5, 5.8, 15.1, -4.8, 'silver'); m.box(3.6, 15.1, -5.9, 5, 15.2, -5.4, 'black')   # nugget slot
    m.box(-6, 14.8, -4.5, 6, 26, 4.5, 'red')                                                         # upper cabinet
    m.box(-5.4, 16.6, -4.75, 5.4, 23.4, -4.5, 'gold')                                                # reel window
    for i in range(3):
        x0 = -4.8 + i * 3.3
        m.box(x0, 17.2, -4.85, x0 + 3, 22.8, -4.75, 'white')
    m.box(-5.4, 19.85, -4.97, 5.4, 20.15, -4.87, 'red')                                             # pay line
    for f in range(SPIN):
        m.use('r%d' % f)
        for i in range(3):
            rows, cmap = SYMBOLS[list(SYMBOLS)[(f * (i + 1) + i) % 4]]
            m.pixels(rows, -4.8 + i * 3.3 + 0.25, 21.25, -4.86, 0.5, cmap, 0.1)
    m.use('root')
    words(m, 'XMAS', 0, 25.4, -4.55, 0.4, 'gold')
    m.box(-6.6, 26, -5.2, 6.6, 30, 5.2, 'dark_red')                                                  # lit marquee
    m.box(-5.6, 26.6, -5.35, 5.6, 29.4, -5.2, 'gold')
    words(m, 'COINS', 0, 29.05, -5.4, 0.42, 'dark_red')
    for k in range(13):                                                                              # chase lights round it
        x = -6.2 + k
        for y in (26.1, 29.4):
            m.box(x - 0.25, y, -5.5, x + 0.25, y + 0.5, -5.3, ('g_red', 'g_yellow', 'g_green')[(k + (y > 27)) % 3])
    m.box(-6.6, 30, -5.2, 6.6, 30.6, 5.2, 'snow')                                                    # snow, holly and a star
    m.box(-5.5, 30.6, -1, -3.3, 31.2, 1, 'holly'); m.box(-4.6, 31.2, -0.3, -4, 31.6, 0.3, 'red')
    m.pixels(['..s..', 'sssss', '.s.s.'], -1.25, 32, 0, 0.5, {'s': 'g_star'}, 0.5)
    m.box(5.8, 17, -1.2, 7.4, 19.4, 1.2, 'silver')                                                   # lever housing
    m.use('l0')                                                                                      # lever up
    m.box(6.3, 19.4, -0.3, 6.9, 27, 0.3, 'silver'); m.ell(6.6, 27.7, 0, 0.9, 0.9, 0.9, 'red')
    m.use('l1')                                                                                      # lever pulled
    m.tube([(6.6, 18.4, 0), (6.6, 19.4, -6.4)], 0.6, ['silver']); m.ell(6.6, 19.5, -7, 0.9, 0.9, 0.9, 'red')
    m.use('root')


def split_halves(cubes):
    """Cut a 32 px tall model into the bottom block (y 0..16) and the top block (shifted down 16)."""
    lo, hi = [], []
    for x0, y0, z0, x1, y1, z1, c, b in cubes:
        if y0 < 16 and min(y1, 16) - y0 >= 0.02: lo.append([x0, y0, z0, x1, min(y1, 16), z1, c, b])
        if y1 > 16 and y1 - max(y0, 16) >= 0.02: hi.append([x0, max(y0, 16) - 16, z0, x1, y1 - 16, z1, c, b])
    return lo, hi


COIN = ['..oooo..', '.oyyyyo.', 'oyyddyyo', 'oydyydyo', 'oydyydyo', 'oyyddyyo', '.oyyyyo.', '..oooo..']


def coin_icon():
    img = Image.new('RGBA', (16, 16))
    pal = {'o': (150, 98, 20), 'y': (246, 200, 60), 'd': (196, 140, 30)}
    for r, row in enumerate(COIN):
        for c, ch in enumerate(row):
            if ch != '.':
                for dx in (0, 1):
                    for dy in (0, 1):
                        img.putpixel((c * 2 + dx, r * 2 + dy), pal[ch] + (255,))
    for p in ((5, 4), (4, 5), (5, 5)):
        img.putpixel(p, (255, 248, 200, 255))                       # shine
    return img


# ---------------------------------------------------------------- writing the pack
ROOT = os.path.join(HERE, '..', 'ChristmasMarket')
BP, RP = os.path.join(ROOT, 'ChristmasMarket_BP'), os.path.join(ROOT, 'ChristmasMarket_RP')
VERSION = [1, 0, 2]
FACES = ['north', 'south', 'east', 'west', 'up', 'down']


def dump(path, data, compact=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, **({'separators': (',', ':')} if compact else {'indent': 2}))
        f.write('\n')


def uid(name):
    import uuid
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'christmas-market/' + name))


def entity_geo(gid, cubes):
    r = lambda v: round(v + 0.0, 3)
    out = []
    for x0, y0, z0, x1, y1, z1, c, b in cubes:
        if c in ('clear', 'glass'): continue
        face = {'uv': D.uv(c), 'uv_size': [4, 4]}
        out.append({'origin': [r(x0), r(y0), r(z0)], 'size': [r(x1 - x0), r(y1 - y0), r(z1 - z0)], 'uv': {f: dict(face) for f in FACES}})
    return {'format_version': '1.12.0', 'minecraft:geometry': [{
        'description': {'identifier': gid, 'texture_width': D.TEX, 'texture_height': D.TEX,
                        'visible_bounds_width': 6, 'visible_bounds_height': 6, 'visible_bounds_offset': [0, 2, 0]},
        'bones': [{'name': 'root', 'pivot': [0, 0, 0], 'cubes': out}]}]}


def palette(glow_alpha):
    """Palette sheet in make_decor's layout; glow colours get `glow_alpha` (0 = fully emissive on entities)."""
    img = Image.new('RGBA', (D.TEX, D.TEX))
    d = ImageDraw.Draw(img)
    for i, n in enumerate(D.NAMES):
        x, y = i % 16 * D.SW, i // 16 * D.SW
        col = D.GLOW[n][0] + (glow_alpha,) if n in D.GLOW else D.BASE[n] + (0 if n == 'clear' else 255,)
        d.rectangle([x, y, x + D.SW - 1, y + D.SW - 1], fill=col)
    return img


def check_items():
    """Every traded item must exist: vanilla ids from tools/vanilla_items.txt, ours from the other packs."""
    vanilla = {l.strip() for l in open(os.path.join(HERE, 'vanilla_items.txt')) if l.strip() and not l.startswith('#')}
    ours = set()
    for f in glob_json('*/*_BP/items/**/*.json') + glob_json('*/*_BP/blocks/*.json'):
        d = json.load(open(f))
        for k in ('minecraft:item', 'minecraft:block'):
            if k in d: ours.add(d[k]['description']['identifier'])
    bad = []
    for s in STALLS:
        for item, n, price in s['sells'] + s['buys'] + [(s['recipe'], 1, 0)]:
            ok = item in ours if ':' in item else item in vanilla
            if not ok: bad.append('%s: %s' % (s['key'], item))
            if n > 64 or price > 64: bad.append('%s: %s stack too big' % (s['key'], item))
    assert not bad, bad


def glob_json(pat):
    import glob
    return glob.glob(os.path.join(HERE, '..', pat), recursive=True)


def full(item):
    return item if ':' in item else 'minecraft:' + item


def write_pack(icons):
    check_items()
    lang = ['## Christmas Market', 'item.market:gold_coin=Gold Coin', 'item.market:coin_press=Coin Press', 'tile.market:slot_machine.name=Coin Press', 'tile.market:slot_machine_top.name=Coin Press']
    item_tex = {'market_gold_coin': {'textures': 'textures/items/gold_coin'}}
    os.makedirs(os.path.join(RP, 'textures', 'items'), exist_ok=True)
    os.makedirs(os.path.join(RP, 'textures', 'entity'), exist_ok=True)
    os.makedirs(os.path.join(RP, 'textures', 'blocks'), exist_ok=True)
    coin_icon().save(os.path.join(RP, 'textures', 'items', 'gold_coin.png'))
    palette(0).save(os.path.join(RP, 'textures', 'entity', 'market_palette.png'))
    palette(255).save(os.path.join(RP, 'textures', 'blocks', 'market_palette.png'))
    dump(os.path.join(BP, 'items', 'gold_coin.json'), {'format_version': '1.21.40', 'minecraft:item': {
        'description': {'identifier': 'market:gold_coin', 'menu_category': {'category': 'items'}},
        'components': {'minecraft:icon': 'market_gold_coin', 'minecraft:max_stack_size': 64}}})
    for s in STALLS:
        key, ent, item = s['key'], 'market:stall_' + s['key'], 'market:%s_stall' % s['key']
        m = build(s)
        dump(os.path.join(RP, 'models', 'entity', 'stall_%s.geo.json' % key), entity_geo('geometry.market_stall_' + key, m.cubes), compact=True)
        dump(os.path.join(RP, 'entity', 'stall_%s.entity.json' % key), {'format_version': '1.10.0', 'minecraft:client_entity': {
            'description': {'identifier': ent, 'materials': {'default': 'entity_emissive_alpha'},
                            'textures': {'default': 'textures/entity/market_palette'},
                            'geometry': {'default': 'geometry.market_stall_' + key}, 'render_controllers': ['controller.render.default']}}})
        dump(os.path.join(BP, 'entities', 'stall_%s.json' % key), {'format_version': '1.21.40', 'minecraft:entity': {
            'description': {'identifier': ent, 'is_spawnable': False, 'is_summonable': True},
            'components': {
                'minecraft:type_family': {'family': ['market_stall', 'inanimate']},
                'minecraft:health': {'value': 100, 'max': 100},
                'minecraft:damage_sensor': {'triggers': [{'cause': 'all', 'deals_damage': 'no'}]},
                'minecraft:collision_box': {'width': 2.6, 'height': 3.6},
                'minecraft:custom_hit_test': {'hitboxes': [{'width': 3.4, 'height': 4.2, 'pivot': [0, 2.1, 0]}]},
                'minecraft:physics': {},
                'minecraft:pushable': {'is_pushable': False, 'is_pushable_by_piston': False},
                'minecraft:knockback_resistance': {'value': 1},
                'minecraft:fire_immune': {},
                'minecraft:persistent': {},
                'minecraft:movement': {'value': 0},
                'minecraft:economy_trade_table': {'display_name': 'entity.%s.name' % ent, 'table': 'trading/market/%s.json' % key,
                                                  'new_screen': True, 'persist_trades': True},
                'minecraft:behavior.trade_with_player': {'priority': 1}}}})
        trade = lambda wants, gives: {'wants': [wants], 'gives': [gives], 'max_uses': 64, 'trader_exp': 1, 'reward_exp': False}
        trades = [trade({'item': 'market:gold_coin', 'quantity': p}, {'item': full(i), 'quantity': n}) for i, n, p in s['sells']]
        trades += [trade({'item': full(i), 'quantity': n}, {'item': 'market:gold_coin', 'quantity': p}) for i, n, p in s['buys']]
        dump(os.path.join(BP, 'trading', 'market', key + '.json'), {'tiers': [{'total_exp_required': 0, 'trades': trades}]})
        dump(os.path.join(BP, 'items', '%s_stall.json' % key), {'format_version': '1.21.40', 'minecraft:item': {
            'description': {'identifier': item, 'menu_category': {'category': 'items'}},
            'components': {'minecraft:icon': 'market_%s_stall' % key, 'minecraft:max_stack_size': 1,
                           'minecraft:entity_placer': {'entity': ent}}}})
        dump(os.path.join(BP, 'recipes', '%s_stall.json' % key), {'format_version': '1.20.10', 'minecraft:recipe_shapeless': {
            'description': {'identifier': 'market:%s_stall_recipe' % key}, 'tags': ['crafting_table'],
            'unlock': {'context': 'AlwaysUnlocked'},
            'ingredients': [{'item': 'minecraft:spruce_planks'}] * 3 + [{'item': 'minecraft:white_wool'},
                            {'item': 'minecraft:gold_nugget'}, {'item': full(s['recipe'])}],
            'result': {'item': item, 'count': 1}}})
        icons[key].save(os.path.join(RP, 'textures', 'items', '%s_stall.png' % key))
        item_tex['market_%s_stall' % key] = {'textures': 'textures/items/%s_stall' % key}
        lang += ['item.%s=%s (Christmas Market)' % (item, s['name']), 'entity.%s.name=%s' % (ent, s['name'])]
    # Coin Press: one item that places the slot machine's bottom block; the script adds the top block
    m = D.Model(); slot_machine(m)
    lo, hi = split_halves(m.cubes)
    bones = m.bones
    dump(os.path.join(RP, 'models', 'blocks', 'slot_machine.geo.json'), D.geo_json('geometry.market_slot_machine', lo, ['root']))
    dump(os.path.join(RP, 'models', 'blocks', 'slot_machine_top.geo.json'), D.geo_json('geometry.market_slot_machine_top', hi, bones))
    mats = {'*': {'texture': 'market_palette', 'render_method': 'alpha_test'},
            'glow': {'texture': 'market_palette', 'render_method': 'alpha_test', 'face_dimming': False, 'ambient_occlusion': False}}
    rot = [{'condition': "q.block_state('minecraft:cardinal_direction') == '%s'" % d, 'components': {'minecraft:transformation': {'rotation': [0, r, 0]}}}
           for d, r in (('north', 0), ('west', 90), ('south', 180), ('east', 270))]
    facing = {'minecraft:placement_direction': {'enabled_states': ['minecraft:cardinal_direction'], 'y_rotation_offset': 180}}
    hidden = {'category': 'none', 'is_hidden_in_commands': True}
    box = lambda h: {'origin': [-7, 0, -6], 'size': [14, h, 12]}
    common = lambda gid, h, light, loot: {
        'minecraft:geometry': gid, 'minecraft:material_instances': mats, 'minecraft:collision_box': box(h), 'minecraft:selection_box': box(h),
        'minecraft:destructible_by_mining': {'seconds_to_destroy': 1.5}, 'minecraft:light_emission': light, 'minecraft:loot': loot,
        'minecraft:custom_components': ['market:coin_press']}
    dump(os.path.join(BP, 'blocks', 'slot_machine.json'), {'format_version': '1.21.40', 'minecraft:block': {
        'description': {'identifier': 'market:slot_machine', 'menu_category': hidden, 'traits': facing},
        'components': common('geometry.market_slot_machine', 16, 6, 'loot_tables/blocks/coin_press.json'), 'permutations': rot}})
    vis = {'r%d' % f: "q.block_state('market:spin') == %d" % f for f in range(SPIN)}
    vis.update({'l%d' % k: "q.block_state('market:lever') == %d" % k for k in (0, 1)})
    top = common({'identifier': 'geometry.market_slot_machine_top', 'bone_visibility': vis}, 16, 9, 'loot_tables/empty.json')
    dump(os.path.join(BP, 'blocks', 'slot_machine_top.json'), {'format_version': '1.21.40', 'minecraft:block': {
        'description': {'identifier': 'market:slot_machine_top', 'menu_category': hidden, 'traits': facing,
                        'states': {'market:spin': list(range(SPIN)), 'market:lever': [0, 1]}},
        'components': top, 'permutations': rot}})
    dump(os.path.join(BP, 'loot_tables', 'blocks', 'coin_press.json'), {'pools': [{'rolls': 1, 'entries': [{'type': 'item', 'name': 'market:coin_press'}]}]})
    dump(os.path.join(BP, 'loot_tables', 'empty.json'), {'pools': []})
    dump(os.path.join(BP, 'items', 'coin_press.json'), {'format_version': '1.21.40', 'minecraft:item': {
        'description': {'identifier': 'market:coin_press', 'menu_category': {'category': 'items'}},
        'components': {'minecraft:icon': 'market_coin_press', 'minecraft:max_stack_size': 64,
                       'minecraft:block_placer': {'block': 'market:slot_machine'}}}})
    icon = D.Model(); icon.cubes = [c for c in m.cubes if c[7] in ('root', 'r0', 'l0')]
    zrender(icon, size=32, pitch=14, ss=6, icon=True).save(os.path.join(RP, 'textures', 'items', 'coin_press.png'))
    item_tex['market_coin_press'] = {'textures': 'textures/items/coin_press'}
    dump(os.path.join(BP, 'recipes', 'coin_press.json'), {'format_version': '1.20.10', 'minecraft:recipe_shaped': {
        'description': {'identifier': 'market:coin_press_recipe'}, 'tags': ['crafting_table'], 'unlock': {'context': 'AlwaysUnlocked'},
        'pattern': ['III', 'GRG', 'CCC'],
        'key': {'I': {'item': 'minecraft:iron_ingot'}, 'G': {'item': 'minecraft:gold_ingot'}, 'R': {'item': 'minecraft:redstone'},
                'C': {'item': 'minecraft:cobblestone'}},
        'result': {'item': 'market:coin_press', 'count': 1}}})
    dump(os.path.join(RP, 'textures', 'terrain_texture.json'), {
        'resource_pack_name': 'christmas_market', 'texture_name': 'atlas.terrain', 'padding': 8, 'num_mip_levels': 4,
        'texture_data': {'market_palette': {'textures': 'textures/blocks/market_palette'}}})
    dump(os.path.join(RP, 'textures', 'item_texture.json'), {'resource_pack_name': 'christmas_market', 'texture_name': 'atlas.items',
                                                            'texture_data': item_tex})
    dump(os.path.join(RP, 'blocks.json'), {'format_version': '1.21.40', 'market:slot_machine': {'sound': 'metal'}, 'market:slot_machine_top': {'sound': 'metal'}})
    os.makedirs(os.path.join(RP, 'texts'), exist_ok=True)
    open(os.path.join(RP, 'texts', 'en_US.lang'), 'w').write('\n'.join(lang) + '\n')
    dump(os.path.join(RP, 'texts', 'languages.json'), ['en_US'])
    rp_id, bp_id = uid('rp'), uid('bp')
    dump(os.path.join(RP, 'manifest.json'), {'format_version': 2, 'header': {
        'name': 'Christmas Market RP', 'description': 'Villager market stalls, gold coins and the Coin Press', 'uuid': rp_id,
        'version': VERSION, 'min_engine_version': [1, 21, 90]}, 'modules': [{'type': 'resources', 'uuid': uid('rp-module'), 'version': VERSION}]})
    dump(os.path.join(BP, 'manifest.json'), {'format_version': 2, 'header': {
        'name': 'Christmas Market BP', 'description': 'Villager market stalls, gold coins and the Coin Press', 'uuid': bp_id,
        'version': VERSION, 'min_engine_version': [1, 21, 90]},
        'modules': [{'type': 'data', 'uuid': uid('bp-data'), 'version': VERSION},
                    {'type': 'script', 'language': 'javascript', 'uuid': uid('bp-script'), 'version': VERSION, 'entry': 'scripts/main.js'}],
        'dependencies': [{'uuid': rp_id, 'version': VERSION}, {'module_name': '@minecraft/server', 'version': '2.0.0'}]})
    icon = zrender(build(STALLS[0]), size=256, ss=2, icon=True)
    icon.save(os.path.join(RP, 'pack_icon.png')); icon.save(os.path.join(BP, 'pack_icon.png'))


def main():
    icons = {}
    for s in STALLS:
        img = zrender(build(s), size=32, yaw=28, pitch=14, ss=6, icon=True)
        icons[s['key']] = img
    write_pack(icons)
    print('built %d market stalls' % len(STALLS))
    if '--preview' in sys.argv:
        try:
            font = ImageFont.load_default(size=30)
        except TypeError:
            font = ImageFont.load_default()
        out = os.path.join(HERE, '..', 'previews')
        os.makedirs(out, exist_ok=True)
        tiles = []
        for s in STALLS:
            img = zrender(build(s), size=600, yaw=28, pitch=18)
            ImageDraw.Draw(img).text((16, 12), s['name'], fill=(255, 255, 255, 255), font=font)
            tiles.append(img)
        for part in range(2):                                         # two sheets of ten
            sheet = Image.new('RGBA', (600 * 5, 600 * 2))
            for i, t in enumerate(tiles[part * 10:part * 10 + 10]):
                sheet.paste(t, ((i % 5) * 600, (i // 5) * 600))
            sheet.save(os.path.join(out, 'market_sheet_%d.png' % (part + 1)))
        m = D.Model(); slot_machine(m)
        for f, bones in enumerate((('root', 'r0', 'l0'), ('root', 'r2', 'l1'))):
            v = D.Model(); v.cubes = [c for c in m.cubes if c[7] in bones]
            zrender(v, size=500).save(os.path.join(out, 'market_coin_press%s.png' % ('' if f == 0 else '_pulled')))


if __name__ == '__main__':
    main()
