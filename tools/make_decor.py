#!/usr/bin/env python3
"""Builds the big decoration set for Santa's Workbench: models, textures, block + recipe files,
lang lines and scripts/decor_config.js. Safe to re-run; it overwrites only what it generates.

    python3 tools/make_decor.py            # build into SantasWorkbench/
    python3 tools/make_decor.py --preview  # also render previews/decor_sheet.png

Model space is in pixels: x = viewer's right, y = up, z = away from the viewer (front faces -z).
The base block's cell spans x,z in [-8, 8], y in [0, 16]; extra cells are whole blocks offset by
16 px and become `<id>_partN` blocks that the script places and removes together.
"""
import json, math, os, random, re, sys
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', 'SantasWorkbench')
BP, RP = os.path.join(ROOT, 'SantasWorkbench_BP'), os.path.join(ROOT, 'SantasWorkbench_RP')

# ---------------------------------------------------------------- palette
BASE = dict(
    white=(244, 244, 244), snow=(230, 238, 248), icing=(252, 250, 246), cream=(240, 226, 190), paper=(248, 242, 226),
    red=(196, 28, 38), dark_red=(128, 16, 24), pink=(238, 128, 168), orange=(232, 128, 40), carrot=(240, 116, 26),
    yellow=(244, 212, 60), gold=(232, 182, 52), dark_gold=(168, 118, 30), tan=(212, 178, 132), skin=(242, 202, 170),
    cheek=(232, 140, 140), ginger=(178, 104, 50), dark_ginger=(122, 66, 30), light_wood=(196, 150, 100),
    wood=(146, 96, 56), brown=(108, 68, 38), dark_brown=(66, 40, 24), green=(46, 146, 66), dark_green=(22, 84, 40),
    pine=(30, 104, 56), holly=(18, 70, 36), mint=(150, 222, 190), teal=(36, 140, 146), light_blue=(150, 198, 238),
    blue=(48, 88, 188), navy=(26, 34, 80), purple=(128, 58, 168), lilac=(190, 150, 222), black=(26, 26, 32),
    coal=(40, 40, 46), dark_gray=(68, 68, 76), gray=(128, 128, 138), stone=(162, 160, 160), slate=(86, 96, 112),
    silver=(196, 200, 210), brick=(158, 68, 48), plaster=(236, 230, 216), glass=(200, 230, 255),
)
# glow colours: lit colour, unlit colour, twinkle phase (a/b twinkle out of step, f flickers, s steady)
GLOW = dict(
    g_red=((255, 70, 70), (110, 34, 34), 'a'), g_red2=((255, 70, 70), (110, 34, 34), 'b'),
    g_green=((90, 255, 110), (34, 96, 44), 'a'), g_green2=((90, 255, 110), (34, 96, 44), 'b'),
    g_blue=((90, 150, 255), (36, 56, 110), 'a'), g_blue2=((90, 150, 255), (36, 56, 110), 'b'),
    g_yellow=((255, 226, 90), (116, 100, 40), 'a'), g_yellow2=((255, 226, 90), (116, 100, 40), 'b'),
    g_purple=((214, 120, 255), (82, 44, 104), 'a'), g_white=((255, 244, 214), (150, 146, 136), 'a'),
    g_cool=((214, 240, 255), (150, 164, 178), 'a'), g_cool2=((214, 240, 255), (150, 164, 178), 'b'),
    g_window=((255, 206, 110), (58, 64, 84), 's'), g_flame=((255, 196, 70), (90, 80, 70), 'f'),
    g_star=((255, 222, 120), (170, 150, 100), 'f'), g_snow=((255, 255, 255), (206, 208, 214), 's'),
    g_cane_red=((255, 60, 64), (150, 40, 44), 's'), g_cane_white=((255, 255, 255), (200, 200, 204), 's'),
    g_stain_r=((255, 90, 90), (90, 40, 46), 's'), g_stain_b=((110, 160, 255), (40, 52, 90), 's'),
    g_stain_y=((255, 220, 100), (96, 86, 50), 's'),
)
NAMES = list(BASE) + list(GLOW)
TEX, SW = 128, 8                      # 16 x 16 swatches of 8 px
PHASE = dict(a=[1, .75, .45, .75], b=[.45, .75, 1, .75], f=[1, .86, 1, .8], s=[1, 1, 1, 1])
assert len(NAMES) <= 256


def uv(c):
    i = NAMES.index(c)
    return [i % 16 * SW + 2, i // 16 * SW + 2]


def write_textures():
    def sheet(colour, frames=1):
        img = Image.new('RGBA', (TEX, TEX * frames))
        d = ImageDraw.Draw(img)
        for f in range(frames):
            for i, n in enumerate(NAMES):
                x, y = i % 16 * SW, i // 16 * SW + f * TEX
                d.rectangle([x, y, x + SW - 1, y + SW - 1], fill=colour(n, f) + (255,))
        return img

    def lit(n, f):
        if n not in GLOW:
            return BASE[n]
        on, off, ph = GLOW[n]
        k = PHASE[ph][f]
        return tuple(round(o + (a - o) * k) for a, o in zip(on, off))

    out = os.path.join(RP, 'textures', 'blocks')
    sheet(lambda n, f: BASE.get(n) or GLOW[n][1]).save(os.path.join(out, 'decor.png'))
    sheet(lit, 4).save(os.path.join(out, 'decor_lit.png'))
    Image.new('RGBA', (16, 16), (205, 232, 255, 40)).save(os.path.join(out, 'glass.png'))


# ---------------------------------------------------------------- modelling helpers
class Model:
    def __init__(self):
        self.cubes, self.bones, self.bone = [], ['root'], 'root'

    def use(self, bone):
        if bone not in self.bones:
            self.bones.append(bone)
        self.bone = bone
        return self

    def box(self, x0, y0, z0, x1, y1, z1, c):
        assert c in NAMES, c
        x0, x1 = sorted((x0, x1)); y0, y1 = sorted((y0, y1)); z0, z1 = sorted((z0, z1))
        if min(x1 - x0, y1 - y0, z1 - z0) >= 0.02:
            self.cubes.append([x0, y0, z0, x1, y1, z1, c, self.bone])

    def cyl(self, axis, a, b, lo, hi, ra, rb, c, n=None):
        """Round bar along `axis` ('x','y','z'); (a, b) is its centre in the other two axes (in xyz order)."""
        r = max(ra, rb)
        n = n or (1 if r < 0.8 else 2 if r < 2 else 3 if r < 4.5 else 4)
        for k in range(n):
            t = (k + .5) / n * math.pi / 2 if n > 1 else math.pi / 4
            da, db = (ra * math.cos(t), rb * math.sin(t)) if n > 1 else (ra, rb)
            p = {'x': (lo, a - da, b - db, hi, a + da, b + db), 'y': (a - da, lo, b - db, a + da, hi, b + db),
                 'z': (a - da, b - db, lo, a + da, b + db, hi)}[axis]
            self.box(*p, c)

    def disc(self, cx, cz, y0, y1, rx, rz, c, n=None):
        self.cyl('y', cx, cz, y0, y1, rx, rz, c, n)

    def ell(self, cx, cy, cz, rx, ry, rz, c, ymin=-99, ymax=99, step=0.8, n=None):
        k = max(2, round(2 * ry / step))
        for i in range(k):
            ya, yb = cy - ry + 2 * ry * i / k, cy - ry + 2 * ry * (i + 1) / k
            if yb <= ymin or ya >= ymax:
                continue
            f = math.sqrt(max(0.0, 1 - (((ya + yb) / 2 - cy) / ry) ** 2))
            self.disc(cx, cz, max(ya, ymin), min(yb, ymax), rx * f, rz * f, c, n)

    def tube(self, pts, t, cols, stripe=None, step=None, tz=None):
        """Chain of small cubes along a polyline; cols cycle every `stripe` px of length."""
        step, s = step or t * 0.45, 0.0
        tz = tz or t
        for a, b in zip(pts, pts[1:]):
            L = math.dist(a, b)
            n = max(1, math.ceil(L / step))
            for i in range(n + (b is pts[-1])):
                p = [a[q] + (b[q] - a[q]) * i / n for q in range(3)]
                c = cols[int((s + L * i / n) / stripe) % len(cols)] if stripe else cols[0]
                self.box(p[0] - t / 2, p[1] - t / 2, p[2] - tz / 2, p[0] + t / 2, p[1] + t / 2, p[2] + tz / 2, c)
            s += L

    def pixels(self, rows, x0, ytop, z, ps, cmap, depth=0.2):
        """Pixel art on a plane facing -z; '.' is empty. Runs of one colour merge into one cube."""
        for r, row in enumerate(rows):
            k = 0
            while k < len(row):
                ch, e = row[k], k
                while e + 1 < len(row) and row[e + 1] == ch:
                    e += 1
                if ch != '.':
                    self.box(x0 + k * ps, ytop - (r + 1) * ps, z - depth, x0 + (e + 1) * ps, ytop - r * ps, z, cmap[ch])
                k = e + 1

    def present(self, x0, y0, z0, x1, y1, z1, c, rib, w=0.9, bow=True):
        self.box(x0, y0, z0, x1, y1, z1, c)
        cx, cz, e = (x0 + x1) / 2, (z0 + z1) / 2, 0.06
        self.box(cx - w / 2, y0, z0 - e, cx + w / 2, y1 + e, z1 + e, rib)
        self.box(x0 - e, y0, cz - w / 2, x1 + e, y1 + e, cz + w / 2, rib)
        if bow:
            s = min(1.6, (x1 - x0) / 4)
            self.box(cx - s - 0.3, y1, cz - 0.4, cx - 0.2, y1 + 0.9, cz + 0.4, rib)
            self.box(cx + 0.2, y1, cz - 0.4, cx + s + 0.3, y1 + 0.9, cz + 0.4, rib)
            self.box(cx - 0.4, y1, cz - 0.4, cx + 0.4, y1 + 0.6, cz + 0.4, rib)

    def roof(self, x0, x1, zc, y0, half, dy, dz, c, snow='snow'):
        """Stepped gable roof, ridge along x, with a snow (or icing) lip on every step."""
        k = 0
        while half - k * dz > 0.3:
            h, y = half - k * dz, y0 + k * dy
            self.box(x0, y, zc - h, x1, y + dy, zc + h, c)
            if snow:
                top = h - dz <= 0.3
                self.box(x0, y + dy, zc - h, x1, y + dy + 0.3, zc - h + (2 * h if top else dz), snow)
                if not top:
                    self.box(x0, y + dy, zc + h - dz, x1, y + dy + 0.3, zc + h, snow)
            k += 1
        return y0 + k * dy


def arc(cx, cy, r, a0, a1, n, z=0.0):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n)), z)
            for i in range(n + 1)]


def cane(m, x, z, y0, y1, r, t, cols=('red', 'white'), hook=1):
    """Candy cane standing at (x, z) from y0 to y1, hook of radius r curling towards +x (hook=1) or -x."""
    cx = x + r * hook
    pts = [(x, y0, z), (x, y1 - r, z)] + [(p[0], p[1], z) for p in arc(cx, y1 - r, r, 180 if hook > 0 else 0, 0 if hook > 0 else 180, 10)]
    pts.append((cx + r * hook, y1 - r - r * 0.7, z))
    m.tube(pts, t, list(cols), stripe=t * 0.9)


# ---------------------------------------------------------------- the decorations
SPECS = []


def deco(**spec):
    def wrap(fn):
        spec['build'] = fn
        SPECS.append(spec)
        return fn
    return wrap


GUMDROPS = ['red', 'green', 'yellow', 'purple', 'orange', 'pink']


@deco(id='gingerbread_house', name='Gingerbread House', cells=[(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)], frames=2, light=10,
      cfg=dict(flip=True, sound_on='random.door_open', sound_off='random.door_close'),
      recipe=['wheat', 'wheat', 'sugar', 'cocoa_beans', 'white_dye', 'torch'])
def gingerbread_house(m):
    m.box(-8, 0, -8, 24, 0.5, 8, 'snow')
    m.box(-5, 0.5, -5, 21, 13, 6, 'ginger')
    for y in (4.5, 8.7):                                   # scored "brick" lines
        m.box(-5.1, y, -5.1, 21.1, y + 0.3, 6.1, 'dark_ginger')
    for x in (-5.5, 20.5):                                 # piped icing corners
        for z in (-5.5, 5.5):
            m.box(x, 0.5, z, x + 1, 13, z + 1, 'icing')
    m.box(-5.5, 12.4, -5.5, 21.5, 13.1, 6.5, 'icing')
    top = m.roof(-7, 23, 0.5, 13, 8.3, 1.0, 0.68, 'dark_ginger', snow='icing')
    for i, x in enumerate(range(-5, 22, 3)):               # gumdrops on the ridge
        m.ell(x + 0.5, top + 0.8, 0.5, 0.9, 0.9, 0.9, GUMDROPS[i % 6])
    m.box(14, 17, 2, 18, 28.5, 6, 'red')                   # peppermint chimney
    for y in (20, 22.5, 25):
        m.box(13.9, y, 1.9, 18.1, y + 1, 6.1, 'white')
    m.box(13.5, 28.5, 1.5, 18.5, 29.4, 6.5, 'icing')
    for i, x in enumerate([v * 1.5 - 7 for v in range(21)]):   # icing drips under the front eave
        m.box(x, 13 - (0.6 if i % 2 else 1.3), -8.0, x + 0.7, 13, -7.4, 'icing')
    # front door: frame, glowing hall, door closed (f0) / swung open (f1)
    m.box(4.4, 0.5, -5.5, 11.6, 10.6, -5, 'icing')
    m.box(5, 0.5, -5.6, 11, 10, -5.5, 'g_window')
    m.use('f0')
    m.box(5, 0.5, -6.1, 11, 10, -5.6, 'brown')
    m.box(5.6, 1.2, -6.3, 10.4, 4.6, -6.1, 'dark_ginger')
    m.box(7.2, 6.6, -6.3, 8.8, 8.4, -6.1, 'g_window')
    m.box(9.4, 4.6, -6.6, 10.2, 5.4, -6.1, 'red')
    m.use('f1')
    m.box(4.6, 0.5, -11.6, 5.1, 10, -5.6, 'brown')
    m.box(4.3, 4.6, -10.8, 4.6, 5.4, -10, 'red')
    m.use('root')
    for x0 in (-3, 15):                                    # front windows + flower boxes of gumdrops
        m.box(x0 - 0.5, 4, -5.6, x0 + 4.5, 9.5, -5, 'icing')
        m.box(x0, 4.5, -5.7, x0 + 4, 9, -5.6, 'g_window')
        m.box(x0 + 1.75, 4.5, -5.9, x0 + 2.25, 9, -5.6, 'icing')
        m.box(x0, 6.5, -5.9, x0 + 4, 7, -5.6, 'icing')
        m.box(x0 - 0.5, 3.2, -6.6, x0 + 4.5, 4, -5, 'red')
        for k in range(4):
            m.ell(x0 + 0.5 + k * 1.0, 4.4, -5.8, 0.45, 0.45, 0.45, GUMDROPS[k + (x0 > 0)])
    for x in (-5.6, 21.1):                                 # side windows
        m.box(x, 4.5, -2, x + 0.5, 9.5, 3, 'icing')
        m.box(x - 0.1 if x < 0 else x + 0.5, 5, -1.5, x if x < 0 else x + 0.6, 9, 2.5, 'g_window')
    for i, x in enumerate([v * 2.4 - 4.6 for v in range(11)]):  # gumdrop border along the base
        if not 3.5 < x < 12:
            m.ell(x, 1.1, -5.9, 0.6, 0.6, 0.6, GUMDROPS[i % 6])
    cane(m, -6.6, -6.6, 0.5, 16, 1.4, 1.1, hook=1)
    cane(m, 22.6, -6.6, 0.5, 16, 1.4, 1.1, hook=-1)
    for x in (6.6, 9.4):                                   # peppermint stepping stones
        m.disc(x, -7, 0.5, 0.8, 1.1, 0.8, 'white')
        m.disc(x, -7, 0.8, 0.9, 0.6, 0.4, 'red')


def village(m, wall, roof_col, door, trim):
    m.box(-7.5, 0, -7.5, 7.5, 0.5, 7.5, 'snow')
    m.box(-6, 0.5, -4.5, 6, 9, 5, wall)
    m.box(-6.3, 8.6, -4.8, 6.3, 9.2, 5.3, trim)
    m.box(-1.1, 0.5, -4.8, 1.1, 4.6, -4.5, door)
    m.box(0.5, 2.2, -4.95, 0.9, 2.6, -4.8, 'gold')
    return m.roof(-7, 7, 0.25, 9, 6.6, 0.8, 0.85, roof_col)


@deco(id='village_bakery', name='Village Bakery', night=True, light=9, tick=[100, 200],
      recipe=['brick', 'brick', 'wheat', 'torch'])
def village_bakery(m):
    village(m, 'brick', 'dark_red', 'brown', 'cream')
    for y in (2.6, 4.8, 7):                                # mortar lines
        m.box(-6.05, y, -4.55, 6.05, y + 0.2, 5.05, 'tan')
    m.box(-5.4, 1.4, -4.7, -1.7, 5, -4.5, 'g_window')     # shop window with loaves
    m.box(1.7, 1.4, -4.7, 5.4, 5, -4.5, 'g_window')
    for x in (-4.9, -3.2, 2.2, 3.9):
        m.box(x, 1.4, -4.9, x + 1.2, 2.1, -4.7, 'tan')
    for i in range(12):                                    # striped awning
        x = -6 + i
        m.box(x, 5.4, -6.4, x + 1, 5.9, -4.5, 'red' if i % 2 else 'white')
        m.box(x, 5.9, -5.4, x + 1, 6.3, -4.5, 'red' if i % 2 else 'white')
    m.box(-3, 6.6, -4.9, 3, 8.2, -4.5, 'light_wood')       # sign with a loaf
    m.box(-1.3, 7, -5.1, 1.3, 7.8, -4.9, 'tan')
    m.box(3.5, 11, 1.5, 5.5, 15.5, 3.5, 'brick')           # chimney
    m.box(3.3, 15.5, 1.3, 5.7, 16, 3.7, 'snow')


@deco(id='village_toy_shop', name='Village Toy Shop', night=True, light=9, tick=[100, 200],
      recipe=['oak_planks', 'blue_dye', 'glass', 'torch'])
def village_toy_shop(m):
    village(m, 'blue', 'red', 'red', 'white')
    m.box(-5.6, 1.2, -5.6, -1.6, 6, -4.5, 'white')        # bay window frame
    m.box(-5.2, 1.6, -5.7, -2, 5.6, -5.6, 'g_window')
    m.box(1.6, 1.2, -5.6, 5.6, 6, -4.5, 'white')
    m.box(2, 1.6, -5.7, 5.2, 5.6, -5.6, 'g_window')
    for x, c in ((-4.8, 'red'), (-3.4, 'green'), (2.4, 'yellow'), (3.9, 'purple')):   # toys in the window
        m.box(x, 1.6, -5.9, x + 0.9, 2.5, -5.7, c)
    m.box(-4.2, 2.5, -5.85, -3.9, 3.3, -5.7, 'brown')
    m.box(-2.5, 6.6, -4.9, 2.5, 8.3, -4.5, 'gold')         # sign with a star
    m.pixels(['.y.', 'yyy', '.y.'], -0.6, 8.1, -4.9, 0.4, {'y': 'yellow'})
    m.box(-6.4, 0.5, -4.9, -6, 9, -4.5, 'white')
    m.box(6, 0.5, -4.9, 6.4, 9, -4.5, 'white')


@deco(id='village_cottage', name='Village Cottage', night=True, light=9, tick=[100, 200],
      recipe=['oak_planks', 'oak_planks', 'white_dye', 'torch'])
def village_cottage(m):
    village(m, 'plaster', 'dark_red', 'dark_brown', 'dark_brown')
    for x in (-6.05, -2.4, 2.4, 5.65):                     # timber frame
        m.box(x, 0.5, -4.6, x + 0.4, 9, -4.5, 'dark_brown')
    m.box(-6, 4.6, -4.6, 6, 5, -4.5, 'dark_brown')
    for x0 in (-5, 2.9):
        m.box(x0, 5.6, -4.7, x0 + 2.1, 8, -4.5, 'g_window')
        m.box(x0 + 0.9, 5.6, -4.8, x0 + 1.2, 8, -4.7, 'dark_brown')
        m.box(x0, 1.6, -4.7, x0 + 2.1, 3.8, -4.5, 'g_window')
        m.box(x0, 1.2, -5.2, x0 + 2.1, 1.6, -4.5, 'snow')
    m.cyl('z', 0, 3.5, -4.9, -4.6, 0.9, 0.9, 'pine')          # door wreath
    m.box(-0.3, 2.4, -5, 0.3, 2.9, -4.9, 'red')
    m.box(-4.5, 11, 2, -2.5, 15.6, 4, 'stone')              # chimney + smoke puff
    m.box(-4.7, 15.6, 1.8, -2.3, 16, 4.2, 'snow')


@deco(id='village_church', name='Village Church', night=True, light=9, tick=[100, 200],
      recipe=['cobblestone', 'cobblestone', 'gold_nugget', 'torch'])
def village_church(m):
    m.box(-7.5, 0, -7.5, 7.5, 0.5, 7.5, 'snow')
    m.box(-4.5, 0.5, -2, 4.5, 8, 7, 'stone')               # nave
    k, y = 0, 8.0
    while 5.4 - k * 0.9 > 0.3:                              # steep roof, ridge front-to-back
        h = 5.4 - k * 0.9
        m.box(-h, y, -2.2, h, y + 1.1, 7.3, 'slate')
        m.box(-h, y + 1.1, -2.2, -h + 0.9, y + 1.4, 7.3, 'snow')
        m.box(h - 0.9, y + 1.1, -2.2, h, y + 1.4, 7.3, 'snow')
        k, y = k + 1, y + 1.1
    for z in (0, 3, 5.6):                                   # stained side windows
        for x, c in ((-4.6, 'g_stain_r'), (4.5, 'g_stain_b')):
            m.box(x, 3, z, x + 0.1, 6.4, z + 1.2, c)
            m.box(x, 6.4, z + 0.3, x + 0.1, 6.8, z + 0.9, 'g_stain_y')
    m.box(-2.6, 0.5, -6, 2.6, 11, -1.5, 'stone')           # bell tower
    m.box(-2.8, 10.6, -6.2, 2.8, 11.2, -1.3, 'gray')
    m.box(-0.9, 0.5, -6.2, 0.9, 3.8, -6, 'brown')           # arched door
    m.box(-0.6, 3.8, -6.2, 0.6, 4.3, -6, 'brown')
    m.box(-0.7, 5.4, -6.2, 0.7, 7.6, -6, 'g_stain_y')       # round window
    m.box(-0.4, 5.2, -6.2, 0.4, 7.8, -6, 'g_stain_r')
    m.box(-1.6, 11.2, -5.4, 1.6, 12.8, -2.1, 'stone')       # open belfry with bell
    m.box(-1.1, 11.2, -5.6, 1.1, 12.6, -1.9, 'dark_gray')
    m.disc(0, -3.75, 11.5, 12.5, 0.6, 0.6, 'gold')
    for i in range(5):                                      # steeple
        h = 2.6 - i * 0.55
        m.box(-h, 12.8 + i * 0.6, -3.75 - h, h, 13.4 + i * 0.6, -3.75 + h, 'slate')
    m.box(-0.15, 15.2, -3.85, 0.15, 16, -3.65, 'gold')       # cross
    m.box(-0.5, 15.5, -3.85, 0.5, 15.75, -3.65, 'gold')


@deco(id='sleigh', name="Santa's Sleigh", cells=[(0, 0, 0), (0, 0, 1)],
      recipe=['red_dye', 'oak_planks', 'oak_planks', 'gold_ingot', 'iron_ingot'])
def sleigh(m):
    for x in (-5.8, 5.8):                                   # gold runners with front curl
        pts = [(x, 0.4, 22.5), (x, 0.4, -3), (x, 1.2, -5.6), (x, 3.2, -7.2), (x, 5.8, -7.6), (x, 7.8, -6.6),
               (x, 8.4, -5), (x, 7.6, -3.8), (x, 6.6, -4.4)]
        m.tube(pts, 0.9, ['gold'])
        m.tube([(x, 0.4, 22.5), (x, 1.6, 23.8)], 0.9, ['gold'])
        for z in (0, 8, 16):
            m.box(x - 0.4, 0.8, z, x + 0.4, 3.2, z + 0.8, 'dark_gold')
    m.box(-6.5, 3, -2, 6.5, 4, 21, 'dark_red')              # floor
    prof = [(-2, 5.5), (-1, 7), (0, 8.4), (1, 9), (12, 9), (13, 11), (14, 12.6), (15, 13.6), (21, 13.6)]
    for (za, ha), (zb, _) in zip(prof, prof[1:]):           # side panels with gold trim
        for x in (-6.5, 5.6):
            m.box(x, 3, za, x + 0.9, ha, zb, 'red')
            m.box(x - 0.1, ha - 0.6, za, x + 1.0, ha, zb, 'gold')
            m.box(x - 0.15, 3.6, za, x + 1.05, 4.1, zb, 'gold')
    m.box(-6.5, 3, -2.6, 6.5, 6.2, -1.9, 'red')            # dash + back
    m.box(-6.6, 5.6, -2.7, 6.6, 6.3, -1.9, 'gold')
    m.box(-6.5, 3, 20.4, 6.5, 13.6, 21.2, 'red')
    m.box(-6.6, 13, 20.3, 6.6, 13.8, 21.3, 'gold')
    m.pixels(['.ggg.', 'g...g', 'g.g.g', 'g..g.', '.gg..'], -1.25, 11.5, 21.35, 0.5, {'g': 'gold'}, depth=-0.15)
    m.box(-5.6, 4, 9, 5.6, 6.6, 13, 'dark_red')            # seat + backrest
    m.box(-5.6, 6.6, 12, 5.6, 11.4, 13.4, 'dark_red')
    for x in (-3.8, 0, 3.8):
        m.box(x - 0.2, 4.3, 8.8, x + 0.2, 11, 13.5, 'red')
    m.box(-5.6, 4, 0.5, 5.6, 5, 4, 'brown')                 # footboard + blanket
    m.box(-4, 5, 0.5, 4, 5.4, 6, 'green')
    for z in (1.5, 3.5, 5.5):
        m.box(-4.05, 5, z, 4.05, 5.45, z + 0.5, 'red')
    m.ell(0, 9.5, 17.5, 5, 5.5, 3, 'brown', ymin=4)        # toy sack + presents
    m.box(-1, 14.4, 16.5, 1, 15.4, 18.5, 'gold')
    m.present(-5.5, 4, 14, -1.5, 8.5, 18, 'green', 'gold')
    m.present(1.5, 4, 14.5, 5.5, 9, 19.5, 'blue', 'silver')
    m.present(-5, 8.5, 14.5, -1.5, 12, 18, 'purple', 'white')
    m.present(1.8, 9, 15, 5, 12.5, 19, 'red', 'gold')
    m.present(-1.2, 12.6, 14.6, 1.6, 15, 17, 'gold', 'red', bow=False)


def nut_jaw(m, dy):
    m.box(-1.9, 21.4 + dy, -3.0, 1.9, 22.4 + dy, -2.4, 'skin')
    m.box(-2.4, 19.2 + dy, -3.1, 2.4, 21.6 + dy, -2.2, 'white')
    m.box(-1.6, 18.6 + dy, -3.0, 1.6, 19.4 + dy, -2.4, 'white')
    if dy:
        m.box(-1.4, 22.4 + dy, -2.65, 1.4, 22.5, -2.55, 'black')
        m.box(-1.2, 22.25, -2.75, 1.2, 22.5, -2.6, 'white')


@deco(id='nutcracker_statue', name='Nutcracker Statue', cells=[(0, 0, 0), (0, 1, 0)], frames=2,
      cfg=dict(anim=[1, 0, 1, 0, 1, 0], delay=3, sound='random.click', every=2),
      recipe=['oak_log', 'red_dye', 'ink_sac', 'gold_nugget', 'white_dye'])
def nutcracker_statue(m):
    m.box(-6, 0, -6, 6, 2, 6, 'dark_green')                # plinth
    m.box(-6.3, 1.6, -6.3, 6.3, 2.2, 6.3, 'gold')
    m.box(-5.4, 2.2, -5.4, 5.4, 2.7, 5.4, 'dark_green')
    for s in (-1, 1):
        x0, x1 = sorted((s * 0.5, s * 3))
        m.box(x0 - 0.1, 2.7, -3.6, x1 + 0.1, 7, 1.6, 'black')    # boots
        m.box(x0 - 0.2, 6.5, -1.9, x1 + 0.2, 7.2, 1.8, 'gold')
        m.box(x0, 7, -1.4, x1, 11, 1.4, 'white')                # trousers
        m.box(x0 - 0.05, 7, -1.45, x0 + 0.4 if s < 0 else x0 + 0.4, 11, -1.35, 'red')
        xa, xb = sorted((s * 3.6, s * 5.4))
        m.box(xa, 12.6, -1.3, xb, 19.6, 1.3, 'red')            # sleeves, cuffs, gloves
        m.box(xa - 0.1, 12.6, -1.4, xb + 0.1, 13.6, 1.4, 'gold')
        m.box(xa + 0.1, 11.2, -1.1, xb - 0.1, 12.6, 1.1, 'white')
        m.box(xa - 0.4, 19.2, -2, xb + 0.4, 20.6, 2, 'gold')     # epaulettes
        for z in (-1.6, -0.5, 0.6):
            m.box(xb - 0.5 if s > 0 else xa, 18.4, z, xb if s > 0 else xa + 0.5, 19.2, z + 0.6, 'dark_gold')
    m.box(-3.9, 10.5, -2.5, 3.9, 13, 2.5, 'red')           # coat
    m.box(-3.6, 12, -2.2, 3.6, 20.2, 2.2, 'red')
    m.box(-3.7, 12.6, -2.3, 3.7, 13.6, 2.3, 'black')
    m.box(-0.8, 12.4, -2.6, 0.8, 13.8, -2.25, 'gold')
    for y in (14.6, 16.2, 17.8):
        m.box(-2.6, y, -2.35, 2.6, y + 0.35, -2.2, 'gold')
        m.box(-0.4, y - 0.2, -2.55, 0.4, y + 0.55, -2.3, 'gold')
    m.box(4.3, 8, -1.8, 4.8, 23.5, -1.3, 'silver')           # sceptre in the right hand
    m.ell(4.55, 24, -1.55, 0.7, 0.7, 0.7, 'gold')
    m.box(-2.6, 20.2, -2.6, 2.6, 20.9, 2.6, 'gold')         # collar
    m.box(-2.6, 20.9, -2.6, 2.6, 26.6, 2.6, 'skin')         # head
    m.box(-2.8, 21.2, -0.6, 2.8, 26, 2.8, 'white')          # hair
    for s in (-1, 1):
        xa, xb = sorted((s * 0.7, s * 1.7))
        m.box(xa, 24.3, -2.75, xb, 25.1, -2.6, 'black')
        m.box(xa - 0.1, 25.4, -2.75, xb + 0.1, 25.8, -2.6, 'white')
        xa, xb = sorted((s * 1.4, s * 2.3))
        m.box(xa, 23.1, -2.7, xb, 23.9, -2.6, 'cheek')
    m.box(-0.5, 23.1, -3.5, 0.5, 24.7, -2.6, 'skin')        # nose
    m.box(-0.35, 23.2, -3.6, 0.35, 23.7, -3.5, 'cheek')
    m.box(-2.1, 22.5, -2.95, 2.1, 23.1, -2.6, 'white')      # moustache
    m.box(-2.1, 22, -2.95, -1.5, 22.5, -2.6, 'white')
    m.box(1.5, 22, -2.95, 2.1, 22.5, -2.6, 'white')
    m.use('f0'); nut_jaw(m, 0)
    m.use('f1'); nut_jaw(m, -1.3)
    m.use('root')
    m.box(-2.9, 26.6, -2.9, 2.9, 31.2, 2.9, 'black')        # busby hat + plume
    m.box(-3.0, 26.6, -3.0, 3.0, 27.4, 3.0, 'gold')
    m.box(-0.9, 28, -3.05, 0.9, 30, -2.9, 'gold')
    m.box(-0.5, 28.4, -3.15, 0.5, 29.6, -3.05, 'red')
    m.box(-0.6, 31.2, -1.4, 0.6, 32, 0.2, 'red')
    m.box(-0.35, 29.5, -3.4, 0.35, 32, -2.9, 'red')


@deco(id='advent_calendar', name='Advent Calendar', advent=True, collision=None, cfg=dict(advent=True),
      recipe=['paper', 'paper', 'cookie', 'green_dye'])
def advent_calendar(m):
    m.box(-7.6, 0.6, 7, 7.6, 15.4, 8, 'dark_brown')        # frame + green board
    m.box(-7, 1.2, 6.6, 7, 12.6, 7, 'dark_green')
    m.box(-7, 12.6, 6.4, 7, 14.8, 7, 'red')                  # banner with a gold star
    m.box(-7, 14.5, 6.3, 7, 14.8, 6.4, 'gold')
    m.box(-7, 12.6, 6.3, 7, 12.9, 6.4, 'gold')
    m.pixels(['..y..', '.yyy.', 'yyyyy', '.y.y.'], -1.0, 14.5, 6.3, 0.4, {'y': 'yellow'}, depth=0.15)
    for x in (-6.2, 5.2):                                    # holly sprigs in the banner corners
        m.box(x, 13.1, 6.2, x + 1, 14.2, 6.4, 'holly')
        m.box(x + 0.3, 13.4, 6.05, x + 0.7, 13.8, 6.2, 'red')
    order = list(range(1, 25))
    random.Random(24).shuffle(order)
    cols, rows, x0, y0 = 6, 4, -6.6, 1.5
    w, h = 13.2 / cols, 10.9 / rows
    colours = ['red', 'white', 'gold', 'green', 'light_blue', 'pink']
    treats = ['g_red', 'yellow', 'pink', 'brown', 'white', 'g_green']
    for idx, n in enumerate(order):
        cx, ry = idx % cols, idx // cols
        a, b = x0 + cx * w + 0.2, y0 + ry * h + 0.25
        c, d = a + w - 0.4, b + h - 0.5
        col = colours[(n * 7) % 6]
        m.use('root')
        m.box(a, b, 6.55, c, d, 6.6, 'dark_brown')          # recess behind the door
        m.use('c%d' % n)
        m.box(a, b, 6.15, c, d, 6.55, col)
        m.box(c - 0.5, (b + d) / 2 - 0.2, 6.0, c - 0.2, (b + d) / 2 + 0.2, 6.15, 'gold' if col != 'gold' else 'red')
        dots = n if n <= 4 else (n % 4) + 1                  # a little pip count so doors look numbered
        for k in range(min(dots, 4)):
            m.box(a + 0.3 + k * 0.4, d - 0.55, 6.05, a + 0.55 + k * 0.4, d - 0.3, 6.15, 'dark_red' if col != 'red' else 'white')
        m.use('o%d' % n)
        m.box(a - 0.05, b, 6.55 - (c - a), a + 0.25, d, 6.55, col)    # door swung open on its left hinge
        m.ell((a + c) / 2, (b + d) / 2, 6.3, 0.55, 0.55, 0.3, treats[n % 6])


def bell(m, dx):
    ys = [(10.0, 10.6, 0.45), (9.4, 10.0, 0.95), (8.6, 9.4, 1.35), (8.0, 8.6, 1.85)]
    for y0, y1, r in ys:
        sh = dx * (10.6 - (y0 + y1) / 2) / 2.6
        m.disc(sh, 6.0, y0, y1, r, min(r, 1.0), 'gold')
    m.disc(dx * 1.2, 6.0, 7.5, 8.0, 0.4, 0.4, 'dark_gold')


@deco(id='door_wreath', name='Wreath with Bell', frames=3, collision=None,
      cfg=dict(anim=[1, 2, 1, 2, 1, 2, 0], delay=2, sound='note.bell', every=1),
      recipe=['spruce_leaves', 'spruce_leaves', 'red_dye', 'gold_nugget', 'iron_nugget'])
def door_wreath(m):
    rnd = random.Random(7)
    cy = 9.2
    for i in range(36):                                      # leafy ring
        a = math.radians(i * 10)
        for rr in (3.9, 5.4):
            x, y = rr * math.cos(a), cy + rr * math.sin(a)
            s = rnd.uniform(1.3, 2.0)
            m.box(x - s / 2, y - s / 2, rnd.uniform(5.6, 6.4), x + s / 2, y + s / 2, 7.6, rnd.choice(['pine', 'dark_green', 'green', 'holly']))
    for i in range(10):                                      # berries, baubles, cones
        a = math.radians(i * 36 + 12)
        x, y = 4.7 * math.cos(a), cy + 4.7 * math.sin(a)
        if i % 3 == 0:
            m.ell(x, y, 5.4, 0.7, 0.9, 0.6, 'brown')
        elif i % 3 == 1:
            m.ell(x, y, 5.4, 0.6, 0.6, 0.6, 'gold')
        else:
            for dx, dy in ((0, 0), (0.6, 0.4), (-0.5, 0.5)):
                m.box(x + dx - 0.3, y + dy - 0.3, 5.2, x + dx + 0.3, y + dy + 0.3, 5.6, 'red')
    m.box(-0.35, cy + 2.5, 6.6, 0.35, 16, 7.0, 'red')         # ribbon the bell hangs from
    m.box(-3.2, 3.4, 5.3, -0.6, 5.4, 6.4, 'red')             # bow at the bottom
    m.box(0.6, 3.4, 5.3, 3.2, 5.4, 6.4, 'red')
    m.box(-0.7, 3.6, 5.1, 0.7, 5.2, 6.4, 'dark_red')
    m.box(-1.8, 0.6, 5.6, -0.8, 3.6, 6.2, 'red')
    m.box(0.8, 0.6, 5.6, 1.8, 3.6, 6.2, 'red')
    for f, dx in enumerate((0, -1.0, 1.0)):
        m.use('f%d' % f); bell(m, dx)
    m.use('root')
    m.box(-0.25, 10.6, 5.8, 0.25, cy + 2.6, 6.2, 'dark_gold')


@deco(id='snow_globe_display', name='Snow Globe Display', frames=4,
      cfg=dict(anim=[1, 2, 3, 1, 2, 3, 1, 2, 3, 0], delay=3, sound='note.chime', every=3, particle='minecraft:snowflake_particle'),
      recipe=['glass', 'glass', 'snowball', 'gold_nugget', 'spruce_planks'])
def snow_globe_display(m):
    m.disc(0, 0, 0, 1, 6.6, 6.6, 'dark_brown')
    m.disc(0, 0, 1, 3.2, 6, 6, 'wood')
    m.disc(0, 0, 3.2, 3.8, 6.2, 6.2, 'gold')
    m.disc(0, 0, 3.8, 4.3, 5.4, 5.4, 'dark_gold')
    m.box(-2, 1.4, -6.25, 2, 2.8, -5.9, 'gold')              # name plaque
    m.box(-1.5, 1.8, -6.35, 1.5, 2.4, -6.25, 'dark_gold')
    m.disc(0, 0, 4.3, 4.9, 4.9, 4.9, 'snow')                 # tiny winter scene
    m.box(-3.4, 4.9, -0.2, -0.6, 7.2, 2.4, 'red')
    m.roof(-3.6, -0.4, 1.1, 7.2, 1.7, 0.45, 0.45, 'dark_red')
    m.box(-2.3, 4.9, -0.3, -1.7, 6, -0.2, 'brown')
    m.box(-1.2, 5.6, -0.3, -0.8, 6.3, -0.2, 'g_window')
    for i, r in enumerate((1.6, 1.25, 0.9, 0.55)):            # tree
        m.disc(2, 1.2, 5.3 + i * 1.0, 6.4 + i * 1.0, r, r, 'pine')
    m.box(1.85, 4.9, 1.05, 2.15, 5.3, 1.35, 'brown')
    m.box(1.7, 9.3, 0.9, 2.3, 9.9, 1.5, 'yellow')
    m.ell(1, 5.5, -2.4, 0.8, 0.7, 0.8, 'white')              # snowman
    m.ell(1, 6.6, -2.4, 0.55, 0.5, 0.55, 'white')
    m.box(0.9, 6.5, -3.2, 1.1, 6.7, -2.9, 'carrot')
    m.present(-2.4, 4.9, -3.4, -1.4, 5.7, -2.4, 'green', 'gold', w=0.3, bow=False)
    m.ell(0, 10.1, 0, 5.6, 5.8, 5.6, 'glass', ymin=4.3, step=1.6, n=2)   # glass dome
    rnd = random.Random(3)
    for f in range(1, 4):
        m.use('f%d' % f)
        for _ in range(16):
            r, a, y = rnd.uniform(0, 4.2), rnd.uniform(0, 6.283), rnd.uniform(5.2, 14.5)
            m.box(r * math.cos(a) - 0.2, y, r * math.sin(a) - 0.2, r * math.cos(a) + 0.2, y + 0.4, r * math.sin(a) + 0.2, 'white')
    m.use('root')


CARDS = {
    'tree': (['...y...', '...g...', '..ggg..', '.grggg.', '..ggg..', '.gggrg.', 'ggggggg', '...b...'], 'paper',
             {'y': 'yellow', 'g': 'green', 'r': 'red', 'b': 'brown'}),
    'snowman': (['..kkk..', '..kkk..', '.kkkkk.', '..www..', '..wow..', '.wwwww.', '.wwkww.', '.wwwww.'], 'navy',
                {'k': 'black', 'w': 'white', 'o': 'orange'}),
    'wreath': (['..ggg..', '.g...g.', 'g.....g', 'g.....g', '.g...g.', '..grg..', '..r.r..'], 'cream',
               {'g': 'green', 'r': 'red'}),
    'star': (['...y...', '..yyy..', 'yyyyyyy', '.yyyyy.', '..y.y..', '.y...y.'], 'navy', {'y': 'yellow'}),
    'bauble': (['...k...', '..yyy..', '.rrrrr.', 'rrwrrrr', 'rrrrrrr', '.rrrrr.', '..rrr..'], 'white',
               {'k': 'dark_gray', 'y': 'gold', 'r': 'red', 'w': 'white'}),
    'ginger': (['..ggg..', '..gwg..', 'ggggggg', '..gwg..', '..ggg..', '.gg.gg.', '.g...g.'], 'light_blue',
               {'g': 'ginger', 'w': 'white'}),
    'cane': (['..rwr..', '.w...r.', '.r...w.', '.....r.', '.....w.', '.....r.', '.....w.'], 'green',
             {'r': 'red', 'w': 'white'}),
}


def card(m, kind, x0, y0, z):
    rows, bg, cmap = CARDS[kind]
    w, h = 3.6, 4.6
    m.box(x0, y0, z, x0 + w, y0 + h, z + 0.35, bg)
    m.box(x0 + 0.15, y0 - 0.0, z + 0.35, x0 + w - 0.15, y0 + h - 0.4, z + 1.2, 'paper')   # back half of the fold
    ps = min((w - 0.6) / len(rows[0]), (h - 0.8) / len(rows))
    m.pixels(rows, x0 + (w - ps * len(rows[0])) / 2, y0 + h - (h - ps * len(rows)) / 2, z, ps, cmap, depth=0.12)


@deco(id='card_stand', name='Christmas Card Stand', recipe=['paper', 'paper', 'paper', 'stick'])
def card_stand(m):
    m.box(-7.5, 0, -5, 7.5, 1, 5, 'light_wood')              # stepped stand
    m.box(-7.5, 1, -0.5, 7.5, 3, 5, 'light_wood')
    m.box(-7.5, 3, 2.5, 7.5, 5, 5, 'light_wood')
    for y in (1, 3, 5):
        m.box(-7.6, y - 0.25, -5.1 if y == 1 else (-0.6 if y == 3 else 2.4), 7.6, y, 5.1, 'wood')
    card(m, 'tree', -6.6, 1, -4.2)
    card(m, 'snowman', -1.8, 1, -4.4)
    card(m, 'bauble', 3.0, 1, -4.1)
    card(m, 'wreath', -4.6, 3, -0.2)
    card(m, 'ginger', 0.8, 3, 0.0)
    card(m, 'star', -2.2, 5, 2.8)
    card(m, 'cane', 3.0, 5, 2.9)
    m.box(-7.2, 5, 3, -5.8, 6.2, 4.4, 'holly')               # sprig of holly
    m.box(-6.8, 6.2, 3.5, -6.3, 6.7, 4.0, 'red')


@deco(id='path_cane', name='Candy Cane Path Light', toggle=True, light=8, collision=None,
      cfg=dict(toggle=True, flicker=True, sound='random.click'),
      recipe=['red_dye', 'white_dye', 'glowstone_dust', 'stick'])
def path_cane(m):
    m.ell(0, 0, 0, 3, 1.2, 2.6, 'snow', ymin=0)
    cane(m, -1.2, 0, 0.3, 12.5, 1.9, 1.4, cols=('g_cane_red', 'g_cane_white'), hook=1)
    m.box(-2.3, 9.2, -0.9, -0.1, 10.4, 0.9, 'green')         # little bow
    m.box(-2.6, 8.4, -0.5, -1.9, 9.2, 0.5, 'green')
    m.box(-0.6, 8.4, -0.5, 0.1, 9.2, 0.5, 'green')
    m.box(-1.5, 9.4, -1.05, -0.9, 10.2, -0.9, 'dark_green')


@deco(id='lightup_snowman', name='Light-Up Snowman', cells=[(0, 0, 0), (0, 1, 0)], toggle=True, light=12,
      cfg=dict(toggle=True, flicker=True, sound='random.click'),
      recipe=['snowball', 'snowball', 'snowball', 'glowstone_dust', 'coal'])
def lightup_snowman(m):
    m.ell(0, 6.5, 0, 6.5, 6.5, 6.3, 'g_snow', ymin=0)
    m.ell(0, 16.2, 0, 5, 4.8, 4.8, 'g_snow')
    m.ell(0, 24, 0, 3.8, 3.8, 3.8, 'g_snow')
    for y in (13.4, 15.6, 17.8):                             # coal buttons
        z = -math.sqrt(max(0, 4.8 ** 2 - (y - 16.2) ** 2)) - 0.1
        m.box(-0.5, y, z - 0.3, 0.5, y + 0.9, z + 0.4, 'coal')
    for s in (-1, 1):                                        # eyes
        m.box(s * 1.3 - 0.45, 24.6, -3.7, s * 1.3 + 0.45, 25.5, -3.2, 'coal')
    for i, x in enumerate((-1.6, -0.8, 0, 0.8, 1.6)):        # smile
        y = 22.5 - (0.5 if 0 < i < 4 else 0) - (0.2 if i == 2 else 0)
        m.box(x - 0.3, y, -3.55, x + 0.3, y + 0.5, -3.1, 'coal')
    m.box(-0.45, 23.6, -4.8, 0.45, 24.5, -3.3, 'carrot')     # carrot nose
    m.box(-0.3, 23.75, -6, 0.3, 24.3, -4.8, 'carrot')
    m.disc(0, 0, 20.2, 21.6, 4.1, 4.1, 'red')                # scarf
    m.disc(0, 0, 20.6, 21.0, 4.15, 4.15, 'green')
    m.box(1.2, 15.2, -5.2, 2.8, 21, -4.0, 'red')
    for y in (16.2, 18.2):
        m.box(1.15, y, -5.25, 2.85, y + 0.5, -3.95, 'green')
    m.disc(0, 0, 27.4, 28.0, 3.8, 3.8, 'black')              # top hat
    m.box(-2.5, 28, -2.5, 2.5, 32, 2.5, 'black')
    m.box(-2.55, 28, -2.55, 2.55, 29, 2.55, 'red')
    m.box(0.8, 28.4, -2.75, 1.8, 29.6, -2.5, 'holly')
    for s in (-1, 1):                                        # twig arms
        m.tube([(s * 4.4, 17.5, 0), (s * 7.5, 19.5, 0), (s * 10.5, 22, 0)], 0.6, ['brown'])
        m.tube([(s * 8.5, 20.3, 0), (s * 9.4, 22.6, 0)], 0.45, ['brown'])
        m.tube([(s * 10.5, 22, 0), (s * 11.6, 22.4, 0)], 0.45, ['brown'])


def santa_body(m, lean):
    """Inflatable Santa; `lean` shears everything sideways with height (0 = upright)."""
    sh = lambda y: lean * (y / 32) ** 1.5 * 3.2
    b = Model()
    b.disc(0, 0, 0, 0.6, 5, 5, 'dark_gray')                  # blower base
    for s in (-1, 1):
        b.box(s * 0.6, 0.6, -4.2, s * 3.2, 3.8, 0.6, 'black')   # boots
    b.ell(0, 11, 0, 6.6, 8.2, 5.6, 'red', ymin=2.4)          # round body
    b.disc(0, 0, 3.0, 4.6, 6.0, 5.1, 'white')                # fur hem
    b.disc(0, 0, 10, 11.6, 6.8, 5.9, 'black')                # belt + buckle
    b.box(-1.3, 9.6, -6.15, 1.3, 12, -5.8, 'gold')
    b.box(-0.6, 10.2, -6.25, 0.6, 11.4, -6.1, 'black')
    b.box(-0.9, 4.6, -5.7, 0.9, 10, -5.2, 'white')           # front fur strip
    b.box(-0.9, 11.6, -5.6, 0.9, 17.5, -4.6, 'white')
    for s in (-1, 1):                                        # waving arms
        b.tube([(s * 5.6, 14, 0), (s * 8.4, 17, 0), (s * 9.6, 20.6, 0)], 2.6, ['red'])
        b.box(s * 9.6 - 1.5, 20.6, -1.5, s * 9.6 + 1.5, 21.6, 1.5, 'white')
        b.ell(s * 9.6, 22.6, 0, 1.2, 1.2, 1.1, 'black')
    b.ell(0, 22.6, 0, 4.2, 4.0, 4.0, 'skin')                 # head
    b.ell(0, 20.6, -1.6, 4.2, 3.4, 2.8, 'white')             # beard
    b.box(-2.6, 21.8, -4.4, 2.6, 22.6, -3.7, 'white')        # moustache
    b.box(-0.6, 22.4, -4.6, 0.6, 23.6, -3.8, 'cheek')        # nose
    for s in (-1, 1):
        b.box(s * 1.5 - 0.45, 23.8, -3.95, s * 1.5 + 0.45, 24.8, -3.6, 'black')
        b.box(s * 2.5 - 0.5, 22.8, -3.6, s * 2.5 + 0.5, 23.5, -3.3, 'cheek')
        b.box(s * 1.5 - 0.7, 25.0, -3.8, s * 1.5 + 0.7, 25.5, -3.4, 'white')
    b.disc(0, 0, 25.4, 27.0, 4.5, 4.4, 'white')              # hat
    for i in range(5):
        r = 3.8 - i * 0.7
        b.disc(i * 0.45, 0, 27 + i * 0.9, 27.9 + i * 0.9, r, r, 'red')
    b.ell(2.6, 31.2, 0, 0.9, 0.8, 0.9, 'white')
    for x, y, z in ((5.5, 12, 0), (-5.5, 12, 0)):            # tether lines
        b.box(x + (0.6 if x > 0 else -0.6) - 0.15, 0, z - 0.15, x + (0.6 if x > 0 else -0.6) + 0.15, y, z + 0.15, 'gray')
    for c in b.cubes:
        d = sh((c[1] + c[4]) / 2)
        m.cubes.append([c[0] + d, c[1], c[2], c[3] + d, c[4], c[5], c[6], m.bone])


@deco(id='inflatable_santa', name='Inflatable Santa', cells=[(0, 0, 0), (0, 1, 0)], frames=3, tick=[60, 140],
      cfg=dict(anim=[1, 0, 2, 0, 1, 0], delay=4, sound='dig.cloth', every=2, idle=[1, 0, 2, 0], idle_delay=6),
      recipe=['red_wool', 'red_wool', 'white_wool', 'string', 'redstone'])
def inflatable_santa(m):
    for f, lean in enumerate((0, -1, 1)):
        m.use('f%d' % f); santa_body(m, lean)
    m.use('root')


@deco(id='present_stack', name='Present Stack', cells=[(0, 0, 0), (0, 1, 0)],
      recipe=['paper', 'paper', 'red_dye', 'green_dye', 'string'])
def present_stack(m):
    m.present(-7, 0, -6, 3.5, 7, 5, 'red', 'gold')
    m.present(4, 0, -7, 7.5, 4.5, -2.5, 'green', 'red')
    m.present(4, 0, -1.5, 7.5, 9, 6.5, 'purple', 'gold')
    m.present(-6, 7, -5, 3, 13, 4, 'blue', 'silver')
    m.present(-5, 13, -4, 2, 18.5, 3, 'gold', 'red')
    m.box(-3.6, 18.5, -3, 1.4, 22.5, 2, 'white')             # candy-stripe box
    for i in range(5):
        m.box(-3.65 + i, 18.5, -3.05, -3.15 + i, 22.5, 2.05, 'red')
    m.present(-3.6, 18.5, -3, 1.4, 22.5, 2, 'white', 'green', w=0.8)
    m.present(-2.6, 22.5, -2, 0.6, 25.4, 1, 'pink', 'white', w=0.6)
    for x, y in ((-2.2, 23.2), (-0.6, 24.4), (0.1, 23.0)):  # polka dots
        m.box(x, y, -2.06, x + 0.5, y + 0.5, -2.0, 'white')
    m.pixels(['..y..', '.yyy.', 'yyyyy', '.yyy.', 'y...y'], -2.0, 31.6, 0, 0.8, {'y': 'gold'}, depth=0.6)
    m.box(-1.3, 25.4, -0.3, -0.3, 27.6, 0.3, 'gold')
    m.box(5.8, 4.5, -7.05, 7.0, 6.0, -6.95, 'paper')          # gift tag
    m.box(-6.95, 3, -6.1, -5.2, 5, -6.0, 'paper')


@deco(id='snowy_bench', name='Snowy Bench', cells=[(0, 0, 0), (1, 0, 0)], collision=8,
      recipe=['oak_planks', 'oak_planks', 'iron_ingot', 'snowball'])
def snowy_bench(m):
    for x in (-5.5, 20.5):                                   # cast iron ends
        m.box(x, 0, -4.5, x + 1, 6, -3.5, 'dark_gray')
        m.box(x, 0, 3, x + 1, 14.5, 4, 'dark_gray')
        m.box(x, 5.4, -4.5, x + 1, 6.2, 4, 'dark_gray')
        m.tube([(x + 0.5, 9.4, -4.2), (x + 0.5, 9.4, -1.5), (x + 0.5, 10.4, 1.2), (x + 0.5, 10.4, 3.4)], 0.9, ['dark_gray'])
        m.box(x + 0.1, 6.2, -4.3, x + 0.9, 9.4, -3.7, 'dark_gray')
        m.ell(x + 0.5, 0, 0, 2.2, 1.0, 5.2, 'snow', ymin=0)
    for i in range(4):                                       # seat slats
        m.box(-6, 6.2, -4.4 + i * 2.1, 22, 7.2, -2.8 + i * 2.1, 'wood')
    for i in range(3):                                       # back slats
        m.box(-6, 8.4 + i * 2.2, 3.2, 22, 9.9 + i * 2.2, 4.0, 'wood')
    m.box(-6, 13.7, 2.9, 22, 14.3, 4.3, 'snow')              # snow on the back + seat
    m.ell(17, 7.2, 0, 3.6, 1.2, 3.2, 'snow', ymin=7.2)
    m.ell(-2.5, 7.2, -1, 2.4, 0.9, 2.4, 'snow', ymin=7.2)
    for i in range(7):                                       # plaid blanket over the middle
        c = ['red', 'red', 'green', 'red', 'red', 'dark_green', 'red'][i]
        x = 4.5 + i
        m.box(x, 7.2, -2.5, x + 1, 7.6, 3.2, c)
        m.box(x, 7.6, 3.2, x + 1, 12.8, 3.0 + 1.0, c)
        m.box(x, 2.6, -4.7, x + 1, 7.6, -4.3, c)
    for z in (-1, 1.5):
        m.box(4.45, 7.25, z, 11.55, 7.65, z + 0.4, 'yellow')
    m.disc(13, -1, 7.2, 9.2, 0.9, 0.9, 'red')                # mug of cocoa
    m.disc(13, -1, 9.0, 9.3, 0.75, 0.75, 'brown')
    m.box(13.9, 7.7, -1.2, 14.4, 8.8, -0.8, 'red')


@deco(id='light_arch', name='Light-Up Arch', cells=[(i, j, 0) for j in range(3) for i in range(2)], toggle=True, light=12,
      collision={0: [-7, 0, -3, 4, 16, 6], 1: [3, 0, -3, 4, 16, 6], 2: [-7, 0, -3, 4, 16, 6], 3: [3, 0, -3, 4, 16, 6]},
      cfg=dict(toggle=True, flicker=True, sound='random.click'),
      recipe=['spruce_leaves', 'spruce_leaves', 'glowstone_dust', 'glowstone_dust', 'string'])
def light_arch(m):
    path = [(-5, 0.8, 0), (-5, 32, 0)] + arc(8, 32, 13, 180, 0, 24) + [(21, 0.8, 0)]
    m.tube(path, 2.4, ['pine', 'dark_green', 'pine', 'green'], stripe=1.0)
    bulbs = ['g_red', 'g_green2', 'g_blue', 'g_yellow2', 'g_red2', 'g_green', 'g_blue2', 'g_yellow']
    k, s = 0, 0.0
    for a, b in zip(path, path[1:]):                         # bulbs every ~2.6 px, front, back and outside
        L = math.dist(a, b)
        while s <= L:
            p = [a[q] + (b[q] - a[q]) * s / L for q in range(3)]
            c = bulbs[k % 8]
            for z in (-1.8, 1.4):
                m.box(p[0] - 0.45, p[1] - 0.45, z, p[0] + 0.45, p[1] + 0.45, z + 0.4, c)
            k, s = k + 1, s + 2.6
        s -= L
    for x in (-5, 21):                                       # snowy planters
        m.box(x - 2.4, 0, -2.4, x + 2.4, 1.8, 2.4, 'dark_gray')
        m.box(x - 2.5, 1.8, -2.5, x + 2.5, 2.3, 2.5, 'snow')
        m.box(x - 1.2, 32.6, -1.6, x + 1.2, 34.4, -1.2, 'red')    # bows at the shoulders
        m.box(x - 0.4, 30.4, -1.6, x + 0.4, 32.6, -1.3, 'red')
    m.pixels(['...y...', '..yyy..', 'yyyyyyy', '.yyyyy.', '..y.y..', '.y...y.'], 5.2, 47.8, -1.4, 0.75,
             {'y': 'g_star'}, depth=0.8)


@deco(id='icicle_lights', name='Icicle Lights', toggle=True, light=10, collision=None,
      cfg=dict(toggle=True, flicker=True, sound='random.click'),
      recipe=['ice', 'glowstone_dust', 'string'])
def icicle_lights(m):
    m.box(-8, 15, -0.25, 8, 15.5, 0.25, 'dark_gray')
    for i, L in enumerate([6, 9, 4, 11, 7, 5, 10, 3]):
        x = -7 + i * 2
        m.box(x - 0.12, 15 - 1.2, -0.12, x + 0.12, 15, 0.12, 'dark_gray')
        n = int(L / 1.1)
        for k in range(n):
            w = 0.95 - 0.55 * k / max(1, n - 1)
            y1 = 13.8 - k * 1.1
            m.box(x - w / 2, y1 - 1.0, -w / 2, x + w / 2, y1, w / 2, 'g_cool' if (i + k) % 2 else 'g_cool2')


@deco(id='window_candle', name='Window Candle', toggle=True, light=12, collision=None,
      cfg=dict(toggle=True, sound='random.click'),
      recipe=['candle', 'gold_nugget', 'glowstone_dust'])
def window_candle(m):
    m.disc(0, 0, 0, 0.6, 3.2, 3.2, 'gold')
    m.disc(0, 0, 0.6, 1.6, 2.1, 2.1, 'dark_gold')
    for a in range(0, 360, 60):                               # holly ring
        x, z = 2.6 * math.cos(math.radians(a)), 2.6 * math.sin(math.radians(a))
        m.box(x - 0.7, 0.6, z - 0.7, x + 0.7, 1.4, z + 0.7, 'holly' if a % 120 else 'green')
    for a in (30, 150, 270):
        x, z = 2.6 * math.cos(math.radians(a)), 2.6 * math.sin(math.radians(a))
        m.box(x - 0.3, 1.4, z - 0.3, x + 0.3, 2.0, z + 0.3, 'red')
    m.disc(0, 0, 1.6, 10, 1.05, 1.05, 'white')
    for x, z, y in ((0.7, -0.75, 8), (-0.8, -0.6, 7)):        # wax drips
        m.box(x - 0.25, y, z - 0.25, x + 0.25, 10.1, z + 0.25, 'cream')
    m.disc(0, 0, 10, 10.4, 0.5, 0.5, 'gold')
    m.ell(0, 11.3, 0, 0.6, 0.95, 0.6, 'g_flame')
    m.box(-0.2, 12.2, -0.2, 0.2, 12.7, 0.2, 'g_flame')


@deco(id='star_lantern', name='Star Lantern', toggle=True, light=14, collision=None,
      cfg=dict(toggle=True, flicker=True, sound='random.click'),
      recipe=['paper', 'paper', 'glowstone_dust', 'gold_nugget', 'string'])
def star_lantern(m):
    c = (0, 7.6, 0)
    m.box(-0.2, 13.4, -0.2, 0.2, 16, 0.2, 'dark_gray')
    m.box(-0.5, 15.4, -0.5, 0.5, 16, 0.5, 'gold')
    m.ell(*c, 2.2, 2.2, 2.2, 'g_star')
    dirs = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    dirs += [(a, b, 0) for a in (-1, 1) for b in (-1, 1)] + [(a, 0, b) for a in (-1, 1) for b in (-1, 1)] + \
            [(0, a, b) for a in (-1, 1) for b in (-1, 1)]
    for d in dirs:
        L = 5.6 if sum(map(abs, d)) == 1 else 4.0
        n = math.sqrt(sum(v * v for v in d))
        u = [v / n for v in d]
        k = 7
        for i in range(k):
            t = 1.6 + (L - 1.6) * i / (k - 1)
            w = 1.9 * (1 - i / k) + 0.25
            p = [c[q] + u[q] * t for q in range(3)]
            m.box(p[0] - w / 2, p[1] - w / 2, p[2] - w / 2, p[0] + w / 2, p[1] + w / 2, p[2] + w / 2,
                  'g_star' if i < k - 1 else 'g_white')


@deco(id='holly_centerpiece', name='Holly Centerpiece', toggle=True, light=10, collision=5,
      cfg=dict(toggle=True, sound_on='fire.ignite', sound_off='random.fizz'),
      recipe=['spruce_leaves', 'sweet_berries', 'candle', 'candle'])
def holly_centerpiece(m):
    m.box(-7, 0, -3.4, 7, 0.6, 3.4, 'dark_gold')
    m.box(-7.5, 0, -2.6, 7.5, 0.6, 2.6, 'dark_gold')
    m.box(-6.8, 0.6, -3.2, 6.8, 0.8, 3.2, 'gold')
    rnd = random.Random(11)
    for _ in range(46):                                      # holly leaves
        x, z = rnd.uniform(-6.4, 6.4), rnd.uniform(-2.6, 2.6)
        if any(abs(x - cx) < 1.4 and abs(z) < 1.4 for cx in (-4, 0, 4)):
            continue
        y = 0.8 + rnd.uniform(0, 1.6) * (1 - abs(x) / 8)
        lw, ld = (rnd.uniform(1.6, 2.4), rnd.uniform(0.8, 1.1)) if rnd.random() < .5 else (rnd.uniform(0.8, 1.1), rnd.uniform(1.6, 2.4))
        m.box(x - lw / 2, y, z - ld / 2, x + lw / 2, y + 0.45, z + ld / 2, rnd.choice(['holly', 'dark_green', 'green']))
    for x, z in ((-5.8, -1.6), (-2, 2.2), (2.2, -2.2), (5.6, 1.4)):   # pine cones
        for i in range(4):
            r = 0.9 - abs(i - 1.2) * 0.25
            m.box(x - 0.9 + i * 0.6, 1.0, z - r, x - 0.3 + i * 0.6, 1.0 + 2 * r, z + r, 'brown' if i % 2 else 'dark_brown')
    for _ in range(14):                                      # berries
        x, z = rnd.uniform(-6, 6), rnd.uniform(-2.4, 2.4)
        if any(abs(x - cx) < 1.4 and abs(z) < 1.4 for cx in (-4, 0, 4)):
            continue
        m.box(x - 0.3, 2.0, z - 0.3, x + 0.3, 2.6, z + 0.3, 'red')
    for cx, h in ((-4, 5.2), (0, 7.2), (4, 5.2)):            # candles
        m.disc(cx, 0, 0.8, 1.4, 1.3, 1.3, 'gold')
        m.disc(cx, 0, 1.4, 1.4 + h, 1.0, 1.0, 'red')
        m.box(cx - 0.08, 1.4 + h, -0.08, cx + 0.08, 1.9 + h, 0.08, 'black')
        m.ell(cx, 2.4 + h, 0, 0.45, 0.75, 0.45, 'g_flame')


# ---------------------------------------------------------------- writing the packs
FACES = ['north', 'south', 'east', 'west', 'up', 'down']
r3 = lambda v: round(v + 0.0, 3)


def build_models():
    for s in SPECS:
        m = Model()
        s['build'](m)
        s['model'] = m
        s.setdefault('cells', [(0, 0, 0)])


def split(spec):
    """Clip the model's cubes into one cube list per cell (cell-local coordinates)."""
    cells, out, lost = spec['cells'], [[] for _ in spec['cells']], 0.0
    cs = set(cells)
    for c in spec['model'].cubes:
        vol = (c[3] - c[0]) * (c[4] - c[1]) * (c[5] - c[2])
        kept = 0.0
        for n, (i, j, k) in enumerate(cells):
            lo = [-8 + 16 * i, 16 * j, -8 + 16 * k]
            hi = [8 + 16 * i, 16 + 16 * j, 8 + 16 * k]
            if (i - 1, j, k) not in cs: lo[0] -= 6
            if (i + 1, j, k) not in cs: hi[0] += 6
            if (i, j, k - 1) not in cs: lo[2] -= 6
            if (i, j, k + 1) not in cs: hi[2] += 6
            a = [max(c[q], lo[q]) for q in range(3)]
            b = [min(c[q + 3], hi[q]) for q in range(3)]
            if all(b[q] - a[q] > 0.01 for q in range(3)):
                kept += (b[0] - a[0]) * (b[1] - a[1]) * (b[2] - a[2])
                off = (16 * i, 16 * j, 16 * k)
                out[n].append([a[0] - off[0], a[1] - off[1], a[2] - off[2], b[0] - off[0], b[1] - off[1], b[2] - off[2], c[6], c[7]])
        lost += vol - kept
    if lost > 0.05:
        print('  note: %s lost %.2f px^3 outside its cells' % (spec['id'], lost))
    return out


def geo_json(gid, cubes, bones):
    by = {b: [] for b in bones}
    for x0, y0, z0, x1, y1, z1, c, b in cubes:
        face = {'uv': uv(c), 'uv_size': [4, 4]}
        if c in GLOW: face['material_instance'] = 'glow'
        if c == 'glass': face['material_instance'] = 'glass'
        by[b].append({'origin': [r3(x0), r3(y0), r3(z0)], 'size': [r3(x1 - x0), r3(y1 - y0), r3(z1 - z0)],
                      'uv': {f: dict(face) for f in FACES}})
    return {'format_version': '1.12.0', 'minecraft:geometry': [{
        'description': {'identifier': gid, 'texture_width': TEX, 'texture_height': TEX,
                        'visible_bounds_width': 4, 'visible_bounds_height': 4, 'visible_bounds_offset': [0, 1, 0]},
        'bones': [{'name': b, 'pivot': [0, 0, 0], 'cubes': by[b]} for b in bones]}]}


def bone_vis(bones):
    vis = {}
    for b in bones:
        if re.fullmatch(r'f\d+', b): vis[b] = "q.block_state('santa:frame') == %s" % b[1:]
        if re.fullmatch(r'c\d+', b): vis[b] = "q.block_state('santa:day') < %s" % b[1:]
        if re.fullmatch(r'o\d+', b): vis[b] = "q.block_state('santa:day') >= %s" % b[1:]
    return vis


def materials(uses, lit):
    m = {'*': {'texture': 'santa_decor', 'render_method': 'alpha_test'}}
    if 'glow' in uses:
        m['glow'] = {'texture': 'santa_decor_lit' if lit else 'santa_decor', 'render_method': 'alpha_test',
                     'face_dimming': not lit, 'ambient_occlusion': False}
    if 'glass' in uses:
        m['glass'] = {'texture': 'santa_glass', 'render_method': 'blend'}
    return m


def box_json(b):
    return {'origin': b[:3], 'size': b[3:]}


ROT = {'north': 0, 'west': 90, 'south': 180, 'east': 270}


def block_json(spec, n, uses):
    part = n > 0
    ident = 'santa:%s%s' % (spec['id'], '_part%d' % n if part else '')
    states = {}
    if spec.get('toggle'): states['santa:on'] = [1, 0]
    if spec.get('night'): states['santa:on'] = [0, 1]
    if spec.get('frames'): states['santa:frame'] = list(range(spec['frames']))
    if spec.get('advent'): states['santa:day'] = list(range(25))
    desc = {'identifier': ident, 'menu_category': {'category': 'none' if part else 'items'},
            'traits': {'minecraft:placement_direction': {'enabled_states': ['minecraft:cardinal_direction'], 'y_rotation_offset': 180}}}
    if states: desc['states'] = states
    gid = 'geometry.' + ident.replace(':', '_')
    vis = bone_vis(spec['model'].bones)
    col = spec.get('collision', 'full')
    if isinstance(col, dict): col = col.get(n)
    full = [-8, 0, -8, 16, 16, 16]
    comp = {
        'minecraft:geometry': {'identifier': gid, 'bone_visibility': vis} if vis else gid,
        'minecraft:material_instances': materials(uses, True),
        'minecraft:collision_box': False if col is None else box_json(full if col == 'full' else [-8, 0, -8, 16, col, 16] if isinstance(col, (int, float)) else col),
        'minecraft:selection_box': box_json(full),
        'minecraft:destructible_by_mining': {'seconds_to_destroy': 0.3},
    }
    if spec.get('light'):
        comp['minecraft:light_emission'] = spec['light']
    cc = (['santa:decor'] if spec.get('cfg') or spec.get('night') else []) + (['santa:multipart'] if len(spec['cells']) > 1 else [])
    if cc: comp['minecraft:custom_components'] = cc
    if spec.get('tick') and not part:
        comp['minecraft:tick'] = {'interval_range': spec['tick'], 'looping': True}
    if part: comp['minecraft:loot'] = 'loot_tables/empty.json'
    perms = [{'condition': "q.block_state('minecraft:cardinal_direction') == '%s'" % d,
              'components': {'minecraft:transformation': {'rotation': [0, r, 0]}}} for d, r in ROT.items()]
    if 'santa:on' in states and 'glow' in uses:
        off = {'minecraft:material_instances': materials(uses, False)}
        if spec.get('light'): off['minecraft:light_emission'] = 0
        perms.append({'condition': "q.block_state('santa:on') == 0", 'components': off})
    return {'format_version': '1.21.40', 'minecraft:block': {'description': desc, 'components': comp, 'permutations': perms}}


def recipe_json(spec):
    return {'format_version': '1.20.10', 'minecraft:recipe_shapeless': {
        'description': {'identifier': 'santa:%s_recipe' % spec['id']}, 'tags': ['santa_bench'],
        'unlock': [{'item': 'santa:workbench'}],
        'ingredients': [{'item': 'minecraft:' + i} for i in spec['recipe']],
        'result': {'item': 'santa:' + spec['id'], 'count': 1}}}


def dump(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')


def write_packs():
    write_textures()
    cfg, parts = {}, {}
    lang = []
    for s in SPECS:
        bones = s['model'].bones
        uses = {('glow' if c[6] in GLOW else 'glass' if c[6] == 'glass' else '') for c in s['model'].cubes}
        base_i = s['cells'][0]
        for n, cubes in enumerate(split(s)):
            ident = s['id'] + ('_part%d' % n if n else '')
            dump(os.path.join(RP, 'models', 'blocks', ident + '.geo.json'), geo_json('geometry.santa_' + ident, cubes, bones))
            dump(os.path.join(BP, 'blocks', ident + '.json'), block_json(s, n, uses))
            lang.append('tile.santa:%s.name=%s (Workshop Decor)' % (ident, s['name']))
        dump(os.path.join(BP, 'recipes', s['id'] + '.json'), recipe_json(s))
        c = dict(s.get('cfg') or {})
        if s.get('night'): c['night'] = True
        if c: cfg[s['id']] = c
        if len(s['cells']) > 1:
            parts['santa:' + s['id']] = [[i - base_i[0], j - base_i[1], k - base_i[2]] for i, j, k in s['cells'][1:]]
        print('  %-20s %2d cell(s) %4d cubes' % (s['id'], len(s['cells']), len(s['model'].cubes)))

    with open(os.path.join(BP, 'scripts', 'decor_config.js'), 'w') as f:
        f.write('// Generated by tools/make_decor.py - edit that file and re-run it instead of this one.\n')
        f.write('export const NEW_DECOR = %s;\n' % json.dumps(cfg))
        f.write('// extra blocks of each big decoration: [right, up, back] in blocks, seen from the front\n')
        f.write('export const NEW_PARTS = %s;\n' % json.dumps(parts))

    lp = os.path.join(RP, 'texts', 'en_US.lang')
    ours = {l.split('=')[0] for l in lang}
    old = [l for l in open(lp).read().splitlines() if l.split('=')[0] not in ours]
    open(lp, 'w').write('\n'.join(old + lang) + '\n')

    tp = os.path.join(RP, 'textures', 'terrain_texture.json')
    tt = json.load(open(tp))
    for k, v in (('santa_decor', 'decor'), ('santa_decor_lit', 'decor_lit'), ('santa_glass', 'glass')):
        tt['texture_data'][k] = {'textures': 'textures/blocks/' + v}
    dump(tp, tt)
    fp = os.path.join(RP, 'textures', 'flipbook_textures.json')
    fb = [e for e in json.load(open(fp)) if e['atlas_tile'] != 'santa_decor_lit']
    fb.append({'flipbook_texture': 'textures/blocks/decor_lit', 'atlas_tile': 'santa_decor_lit', 'ticks_per_frame': 8})
    dump(fp, fb)


# ---------------------------------------------------------------- preview renderer (painter's algorithm)
def render(spec, size=420, day=6):
    yaw, pitch = math.radians(32), math.radians(24)
    cam = (math.sin(yaw) * math.cos(pitch), math.sin(pitch), -math.cos(yaw) * math.cos(pitch))
    shade = {'up': 1.0, 'north': 0.86, 'east': 0.72, 'west': 0.72, 'south': 0.6, 'down': 0.5}
    normals = {'up': (0, 1, 0), 'down': (0, -1, 0), 'north': (0, 0, -1), 'south': (0, 0, 1), 'east': (1, 0, 0), 'west': (-1, 0, 0)}

    def visible(b):
        if b == 'root' or b == 'f0': return True
        if b[0] == 'c': return int(b[1:]) > day
        if b[0] == 'o': return int(b[1:]) <= day
        return False

    def proj(p):
        x, y, z = p
        dep = z * math.cos(yaw) - x * math.sin(yaw)
        return (x * math.cos(yaw) + z * math.sin(yaw), y * math.cos(pitch) + dep * math.sin(pitch), dep * math.cos(pitch) - y * math.sin(pitch))

    polys = []
    for x0, y0, z0, x1, y1, z1, c, b in spec['model'].cubes:
        if not visible(b): continue
        corners = {'north': [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)],
                   'south': [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
                   'west': [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)],
                   'east': [(x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)],
                   'up': [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)],
                   'down': [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)]}
        for f, pts in corners.items():
            if sum(a * b for a, b in zip(normals[f], cam)) <= 0: continue
            col = GLOW[c][0] if c in GLOW else BASE[c]
            k = 1.0 if c in GLOW else shade[f]
            rgba = tuple(int(v * k) for v in col) + ((40,) if c == 'glass' else (255,))
            o, u, v = pts[0], [pts[1][q] - pts[0][q] for q in range(3)], [pts[3][q] - pts[0][q] for q in range(3)]
            nu, nv = max(1, math.ceil(math.hypot(*u) / 1.5)), max(1, math.ceil(math.hypot(*v) / 1.5))
            for a in range(nu):
                for b in range(nv):
                    q = [[o[t] + u[t] * (a + da) / nu + v[t] * (b + db) / nv for t in range(3)] for da, db in ((0, 0), (1, 0), (1, 1), (0, 1))]
                    pp = [proj(p) for p in q]
                    polys.append((sum(p[2] for p in pp) / 4, [(p[0], p[1]) for p in pp], rgba))
    xs = [p[0] for _, ps, _ in polys for p in ps]; ys = [p[1] for _, ps, _ in polys for p in ps]
    sc = (size - 30) / max(max(xs) - min(xs), max(ys) - min(ys))
    ox, oy = (size - (max(xs) - min(xs)) * sc) / 2 - min(xs) * sc, (size - (max(ys) - min(ys)) * sc) / 2 + max(ys) * sc
    img = Image.new('RGBA', (size, size), (58, 66, 84, 255))
    d = ImageDraw.Draw(img, 'RGBA')
    for _, ps, rgba in sorted(polys, key=lambda t: -t[0]):
        d.polygon([(ox + x * sc, oy - y * sc) for x, y in ps], fill=rgba)
    d.text((8, 6), spec['name'], fill=(255, 255, 255, 255))
    return img


def preview_sheet(path):
    cols, size = 6, 300
    rows = math.ceil(len(SPECS) / cols)
    sheet = Image.new('RGBA', (cols * size, rows * size), (40, 44, 56, 255))
    for i, s in enumerate(SPECS):
        sheet.paste(render(s, size), (i % cols * size, i // cols * size))
    sheet.save(path)


if __name__ == '__main__':
    build_models()
    write_packs()
    if '--preview' in sys.argv:
        os.makedirs(os.path.join(HERE, '..', 'previews'), exist_ok=True)
        preview_sheet(os.path.join(HERE, '..', 'previews', 'decor_sheet.png'))
    print('built %d decorations' % len(SPECS))
