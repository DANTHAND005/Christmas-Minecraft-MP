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
    silver=(196, 200, 210), brick=(158, 68, 48), plaster=(236, 230, 216), glass=(200, 230, 255), clear=(0, 0, 0),
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
                d.rectangle([x, y, x + SW - 1, y + SW - 1], fill=colour(n, f) + (0 if n == 'clear' else 255,))   # clear = invisible
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
    Image.new('RGBA', (16, 16), (205, 232, 255, 60)).save(os.path.join(out, 'glass.png'))


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


FONT = dict(zip('0123456789ADEFNOSTVY', [
    ['111', '101', '101', '101', '111'], ['010', '110', '010', '010', '111'], ['111', '001', '111', '100', '111'],
    ['111', '001', '011', '001', '111'], ['101', '101', '111', '001', '001'], ['111', '100', '111', '001', '111'],
    ['111', '100', '111', '101', '111'], ['111', '001', '010', '010', '010'], ['111', '101', '111', '101', '111'],
    ['111', '101', '111', '001', '111'], ['010', '101', '111', '101', '101'], ['110', '101', '101', '101', '110'],
    ['111', '100', '110', '100', '111'], ['111', '100', '110', '100', '100'], ['101', '111', '111', '111', '101'],
    ['111', '101', '101', '101', '111'], ['111', '100', '111', '001', '111'], ['111', '010', '010', '010', '010'],
    ['101', '101', '101', '101', '010'], ['101', '101', '010', '010', '010']]))


def text(m, s, cx, ytop, z, ps, col, depth=0.12):
    """Pixel-font text centred on cx, on a plane facing -z."""
    rows = ['.'.join(FONT[ch][r] for ch in s).replace('0', '.') for r in range(5)]
    m.pixels(rows, cx - len(rows[0]) * ps / 2, ytop, z, ps, {'1': col}, depth)


def wall_box(m, face, w, a0, y0, d0, a1, y1, d1, c):
    """Box on a wall: face n/s/e/w, wall plane at w, a = along the wall, d = distance out from it."""
    if face == 'n': m.box(a0, y0, w - d1, a1, y1, w - d0, c)
    if face == 's': m.box(a0, y0, w + d0, a1, y1, w + d1, c)
    if face == 'w': m.box(w - d1, y0, a0, w - d0, y1, a1, c)
    if face == 'e': m.box(w + d0, y0, a0, w + d1, y1, a1, c)


def window(m, face, w, a0, y0, a1, y1, frame='white', pane='g_window', cols=2, rows=2, sill='snow', shutters=None):
    wall_box(m, face, w, a0, y0, 0, a1, y1, 0.08, pane)
    t = 0.3
    for b in ((a0 - t, y0 - t, a0, y1 + t), (a1, y0 - t, a1 + t, y1 + t), (a0, y1, a1, y1 + t), (a0, y0 - t, a1, y0)):
        wall_box(m, face, w, b[0], b[1], 0, b[2], b[3], 0.3, frame)
    for i in range(1, cols):
        a = a0 + (a1 - a0) * i / cols
        wall_box(m, face, w, a - 0.12, y0, 0, a + 0.12, y1, 0.2, frame)
    for i in range(1, rows):
        y = y0 + (y1 - y0) * i / rows
        wall_box(m, face, w, a0, y - 0.12, 0, a1, y + 0.12, 0.2, frame)
    if sill:
        wall_box(m, face, w, a0 - 0.5, y0 - 0.7, 0, a1 + 0.5, y0 - 0.3, 0.8, frame)
        wall_box(m, face, w, a0 - 0.4, y0 - 0.3, 0.1, a1 + 0.4, y0 - 0.05, 0.75, sill)
    if shutters:
        sw = (a1 - a0) / 2
        wall_box(m, face, w, a0 - t - sw, y0 - t, 0, a0 - t, y1 + t, 0.25, shutters)
        wall_box(m, face, w, a1 + t, y0 - t, 0, a1 + t + sw, y1 + t, 0.25, shutters)
        for a in (a0 - t - sw / 2, a1 + t + sw / 2):
            for k in range(3):
                y = y0 + (y1 - y0) * (k + 0.6) / 3.2
                wall_box(m, face, w, a - sw * 0.3, y, 0.25, a + sw * 0.3, y + 0.15, 0.32, 'dark_green' if shutters != 'dark_green' else 'holly')


def snowroof(m, x0, x1, zc, y0, half, dy, dz, col, axis='x', icicles=True):
    """Stepped gable roof (ridge along `axis`) under a thick snow coat; the roof colour shows at the edges."""
    def bx(a0, y_0, b0, a1, y_1, b1, c):
        if axis == 'x': m.box(a0, y_0, b0, a1, y_1, b1, c)
        else: m.box(b0, y_0, a0, b1, y_1, a1, c)
    k = 0
    while half - k * dz > 0.25:
        h, y = half - k * dz, y0 + k * dy
        bx(x0, y, zc - h, x1, y + dy, zc + h, col)
        bx(x0 + 0.3, y + dy * 0.4, zc - h - 0.1, x1 - 0.3, y + dy + 0.35, zc + h + 0.1, 'snow')
        k += 1
    if icicles:
        for i in range(int((x1 - x0) / 1.3)):
            a = x0 + 0.6 + i * 1.3
            L = (0.6, 1.2, 0.4, 0.9)[i % 4]
            for s in (-1, 1):
                bx(a, y0 - L, zc + s * (half - 0.25) - 0.15, a + 0.4, y0, zc + s * (half - 0.25) + 0.15, 'light_blue')
    return y0 + k * dy + 0.35


def glass_dome(m, cy, R, ymin, slices=7, t=0.12):
    """Hollow glass ball made of thin octagonal rings, so you only ever look through two panes."""
    ys = [cy - R + 2 * R * i / slices for i in range(slices + 1)]
    for ya, yb in zip(ys, ys[1:]):
        if yb <= ymin:
            continue
        ya = max(ya, ymin)
        r = R * math.sqrt(max(0.0, 1 - (((ya + yb) / 2 - cy) / R) ** 2))
        if r < 1.2:
            m.box(-r, ya, -r, r, yb, r, 'glass')
            continue
        a, c = 0.45 * r, 0.8 * r
        for sx in (-1, 1):
            m.box(sx * r - t / 2, ya, -a, sx * r + t / 2, yb, a, 'glass')               # sides
            m.box(-a, ya, sx * r - t / 2, a, yb, sx * r + t / 2, 'glass')               # front/back
            for sz in (-1, 1):                                                          # stepped corners
                m.box(sx * a, ya, sz * c - t / 2, sx * c, yb, sz * c + t / 2, 'glass')
                m.box(sx * c - t / 2, ya, sz * a, sx * c + t / 2, yb, sz * c, 'glass')
                m.box(sx * a - t / 2, ya, sz * c, sx * a + t / 2, yb, sz * r, 'glass')
                m.box(sx * c, ya, sz * a - t / 2, sx * r, yb, sz * a + t / 2, 'glass')


def bow(m, cx, y, cz, col, s=1.0, knot=None):
    """Bow-tie bow sitting at height y: solid loops that flare out from a centre knot."""
    yc = y + 0.85 * s
    for sg in (-1, 1):
        for a0, a1, h in ((0.45, 1.0, 0.7), (1.0, 1.6, 1.25), (1.6, 2.1, 1.7)):
            xa, xb = sorted((cx + sg * a0 * s, cx + sg * a1 * s))
            m.box(xa, yc - h * s / 2, cz - 0.35 * s, xb, yc + h * s / 2, cz + 0.35 * s, col)
        xa, xb = sorted((cx + sg * 1.2 * s, cx + sg * 1.9 * s))           # dark fold inside each loop
        m.box(xa, yc - 0.2 * s, cz - 0.4 * s, xb, yc + 0.2 * s, cz - 0.35 * s, knot or col)
    m.box(cx - 0.5 * s, yc - 0.5 * s, cz - 0.45 * s, cx + 0.5 * s, yc + 0.5 * s, cz + 0.45 * s, knot or col)


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


def village(m, wall, roof_col, door, trim, base='stone'):
    """Shared shell: snowy plot, walls with a foundation, corner trim, snowy roof. Front wall is at z = -4."""
    m.box(-7.6, 0, -7.6, 7.6, 0.5, 7.6, 'snow')
    m.box(-6, 0.5, -4, 6, 8.6, 5.5, wall)
    m.box(-6.15, 0.5, -4.15, 6.15, 1.4, 5.65, base)
    for x in (-6.2, 5.8):
        for z in (-4.2, 5.3):
            m.box(x, 0.5, z, x + 0.4, 8.6, z + 0.4, trim)
    m.box(-6.25, 8.3, -4.25, 6.25, 8.7, 5.75, trim)
    for i, z in enumerate((-6.6, -5.6, -4.6)):                 # stepping-stone path to the door
        m.box(-0.8 + (0.2 if i % 2 else -0.2), 0.5, z, 0.8 + (0.2 if i % 2 else -0.2), 0.62, z + 0.7, 'gray')
    return snowroof(m, -7.1, 7.1, 0.75, 8.5, 6.6, 0.6, 0.55, roof_col)


def door_at(m, x0, x1, y1, col, knob='gold', glow=False):
    m.box(x0 - 0.35, 0.5, -4.3, x1 + 0.35, y1 + 0.35, -4, 'dark_brown')
    m.box(x0, 0.5, -4.25, x1, y1, -4.05, col)
    for x in (x0 + (x1 - x0) / 3, x0 + 2 * (x1 - x0) / 3):
        m.box(x - 0.06, 0.6, -4.32, x + 0.06, y1 - 0.2, -4.25, 'dark_brown' if col != 'dark_brown' else 'brown')
    if glow:
        m.box(x0 + 0.4, y1 - 1.6, -4.33, x1 - 0.4, y1 - 0.5, -4.25, 'g_window')
    m.box(x1 - 0.55, 2.4, -4.5, x1 - 0.25, 2.8, -4.25, knob)
    m.box(x0 - 0.5, 0.5, -5.1, x1 + 0.5, 0.85, -4, 'stone')           # doorstep


@deco(id='village_bakery', name='Village Bakery', night=True, light=9, tick=[100, 200],
      recipe=['brick', 'brick', 'wheat', 'torch'])
def village_bakery(m):
    village(m, 'brick', 'dark_red', 'brown', 'cream')
    for y in (2.6, 4.8, 7):                                # mortar lines
        m.box(-6.05, y, -4.05, 6.05, y + 0.2, 5.55, 'tan')
    door_at(m, -1, 1, 4.6, 'brown', glow=True)
    for a0 in (-5.2, 1.9):                                 # shop windows full of loaves
        window(m, 'n', -4, a0, 1.8, a0 + 3.3, 4.8, frame='cream', cols=3, rows=1, sill=None)
        for k in range(3):
            m.box(a0 + 0.25 + k * 1.1, 1.85, -4.45, a0 + 0.95 + k * 1.1, 2.4, -4.1, 'tan')
    for i in range(13):                                    # striped awning with a scalloped edge
        x = -6.5 + i
        c = 'red' if i % 2 else 'white'
        m.box(x, 5.3, -6.2, x + 1, 5.7, -4, c)
        m.box(x, 5.7, -5.2, x + 1, 6.1, -4, c)
        m.box(x + 0.2, 4.9, -6.3, x + 0.8, 5.3, -6.0, c)
    m.box(-3, 6.5, -4.4, 3, 8.1, -4, 'light_wood')        # sign with a loaf
    m.box(-1.3, 6.9, -4.6, 1.3, 7.7, -4.4, 'tan')
    m.box(-0.9, 7.7, -4.6, 0.9, 7.9, -4.4, 'tan')
    for z in (-1, 2.5):                                    # side windows
        window(m, 'e', 6, z, 3, z + 2, 6, frame='cream')
        window(m, 'w', -6, z, 3, z + 2, 6, frame='cream')
    m.box(3.5, 10.5, 2.5, 5.5, 15.4, 4.5, 'brick')         # chimney
    m.box(3.3, 15.4, 2.3, 5.7, 15.9, 4.7, 'snow')


@deco(id='village_toy_shop', name='Village Toy Shop', night=True, light=9, tick=[100, 200],
      recipe=['oak_planks', 'blue_dye', 'glass', 'torch'])
def village_toy_shop(m):
    village(m, 'teal', 'red', 'red', 'white', base='white')
    door_at(m, -0.9, 0.9, 4.8, 'red', glow=True)
    m.box(-6.05, 1.4, -4.1, 6.05, 1.6, 5.6, 'white')
    for a0 in (-5.4, 1.6):                                 # display windows with toys inside
        window(m, 'n', -4, a0, 2.0, a0 + 3.8, 5.0, frame='white', cols=2, rows=1, sill=None)
        m.box(a0 - 0.4, 1.4, -4.8, a0 + 4.2, 2.0, -4, 'white')
    m.box(-4.9, 2.0, -4.5, -4.0, 2.9, -4.15, 'brown')      # teddy
    m.box(-4.75, 2.9, -4.5, -4.15, 3.5, -4.15, 'brown')
    m.box(-3.5, 2.0, -4.5, -2.0, 2.7, -4.15, 'red')         # train
    m.box(-3.4, 2.7, -4.5, -2.8, 3.3, -4.15, 'green')
    m.box(2.1, 2.0, -4.5, 3.0, 2.9, -4.15, 'yellow')        # blocks + soldier
    m.box(2.3, 2.9, -4.5, 2.8, 3.4, -4.15, 'blue')
    m.box(3.7, 2.0, -4.5, 4.3, 3.8, -4.15, 'red')
    m.box(3.7, 3.8, -4.5, 4.3, 4.5, -4.15, 'black')
    for i in range(13):                                    # awning
        x = -6.5 + i
        c = 'red' if i % 2 else 'white'
        m.box(x, 5.5, -5.8, x + 1, 5.9, -4, c)
        m.box(x + 0.2, 5.15, -5.9, x + 0.8, 5.5, -5.6, c)
    m.box(-3.6, 6.2, -4.3, 3.6, 8.2, -4, 'gold')           # TOYS sign
    m.box(-3.3, 6.45, -4.4, 3.3, 7.95, -4.3, 'red')
    text(m, 'TOYS', 0, 7.65, -4.4, 0.24, 'white', depth=0.1)
    for z in (-1, 2.5):
        window(m, 'e', 6, z, 3, z + 2, 6, frame='white')
        window(m, 'w', -6, z, 3, z + 2, 6, frame='white')
    cane(m, -6.6, -5.2, 0.5, 6, 0.8, 0.6, hook=1)
    cane(m, 6.6, -5.2, 0.5, 6, 0.8, 0.6, hook=-1)


@deco(id='village_cottage', name='Village Cottage', night=True, light=9, tick=[100, 200],
      recipe=['oak_planks', 'oak_planks', 'white_dye', 'torch'])
def village_cottage(m):
    village(m, 'plaster', 'dark_brown', 'dark_brown', 'dark_brown')
    m.box(-6.05, 4.5, -4.12, 6.05, 4.85, 5.62, 'dark_brown')   # timber frame
    for x in (-2.2, 1.85):
        m.box(x, 1.4, -4.12, x + 0.35, 8.4, -4, 'dark_brown')
    for i in range(5):                                     # diagonal braces, stepped
        m.box(-5.8 + i * 0.7, 4.85 + i * 0.7, -4.12, -5.3 + i * 0.7, 5.55 + i * 0.7, -4, 'dark_brown')
        m.box(5.3 - i * 0.7, 4.85 + i * 0.7, -4.12, 5.8 - i * 0.7, 5.55 + i * 0.7, -4, 'dark_brown')
    door_at(m, -0.9, 0.9, 4.2, 'wood')
    m.cyl('z', 0, 3.2, -4.6, -4.35, 0.75, 0.75, 'pine')        # door wreath
    m.box(-0.25, 2.3, -4.7, 0.25, 2.7, -4.6, 'red')
    for a0 in (-5, 3.2):
        window(m, 'n', -4, a0, 1.9, a0 + 1.8, 3.9, frame='white', shutters='dark_green')
        window(m, 'n', -4, a0, 5.9, a0 + 1.8, 7.7, frame='white', sill=None)
    for z in (-1.5, 2.5):
        window(m, 'e', 6, z, 2.4, z + 1.8, 4.4, frame='white', shutters='dark_green')
        window(m, 'w', -6, z, 2.4, z + 1.8, 4.4, frame='white', shutters='dark_green')
    m.box(-2.3, 4.7, -4.9, -1.5, 5.7, -4.3, 'black')           # lantern by the door
    m.box(-2.15, 4.85, -5.0, -1.65, 5.55, -4.9, 'g_flame')
    m.box(-4.8, 10, 2.6, -2.6, 15.3, 4.8, 'stone')             # chimney
    m.box(-4.8, 12, 2.55, -2.6, 12.25, 4.85, 'gray')
    m.box(-5, 15.3, 2.4, -2.4, 15.8, 5, 'snow')
    for x in (-7.2, -4.8, 4.8, 7.2):                           # bits of picket fence
        m.box(x - 0.25, 0.5, -7.3, x + 0.25, 2.6, -6.8, 'white')
        m.box(x - 0.3, 2.6, -7.35, x + 0.3, 2.9, -6.75, 'snow')
    for x0, x1 in ((-7.2, -4.8), (4.8, 7.2)):
        for y in (1.2, 2.1):
            m.box(x0, y, -7.2, x1, y + 0.3, -6.9, 'white')


@deco(id='village_church', name='Village Church', night=True, light=9, tick=[100, 200],
      recipe=['cobblestone', 'cobblestone', 'gold_nugget', 'torch'])
def village_church(m):
    m.box(-7.6, 0, -7.6, 7.6, 0.5, 7.6, 'snow')
    m.box(-4.4, 0.5, -1.5, 4.4, 8, 7.2, 'stone')               # nave
    for y in (2.2, 4.2, 6.2):                                  # stone courses
        m.box(-4.45, y, -1.55, 4.45, y + 0.18, 7.25, 'gray')
    m.box(-4.55, 0.5, -1.6, 4.55, 1.2, 7.35, 'gray')
    snowroof(m, -1.8, 7.5, 0, 7.8, 5.2, 0.85, 0.6, 'slate', axis='z')
    for z in (0, 2.6, 5.2):                                    # tall arched stained-glass windows
        for face, w in (('e', 4.4), ('w', -4.4)):
            wall_box(m, face, w, z, 2.4, 0, z + 1.4, 5.6, 0.08, 'g_stain_b')
            wall_box(m, face, w, z + 0.2, 5.6, 0, z + 1.2, 6.1, 0.08, 'g_stain_r')
            wall_box(m, face, w, z + 0.45, 6.1, 0, z + 0.95, 6.4, 0.08, 'g_stain_y')
            wall_box(m, face, w, z + 0.55, 2.4, 0, z + 0.85, 5.6, 0.12, 'g_stain_y')
            for b in ((z - 0.3, 2.1, z, 6.1), (z + 1.4, 2.1, z + 1.7, 6.1), (z - 0.1, 2.1, z + 1.5, 2.4)):
                wall_box(m, face, w, b[0], b[1], 0, b[2], b[3], 0.3, 'gray')
    m.box(-2.6, 0.5, -6.2, 2.6, 10.4, -1.4, 'stone')           # bell tower
    for y in (2.2, 4.2, 6.2, 8.2):
        m.box(-2.65, y, -6.25, 2.65, y + 0.18, -1.35, 'gray')
    for x in (-2.9, 2.3):                                      # corner buttresses
        m.box(x, 0.5, -6.5, x + 0.6, 6, -5.9, 'gray')
    m.box(-1.1, 0.5, -6.45, 1.1, 3.6, -6.2, 'brown')           # arched double door
    m.box(-0.7, 3.6, -6.45, 0.7, 4.1, -6.2, 'brown')
    m.box(-0.06, 0.6, -6.5, 0.06, 4.0, -6.45, 'dark_brown')
    m.box(-1.4, 0.5, -6.4, -1.1, 4.0, -6.2, 'gray')
    m.box(1.1, 0.5, -6.4, 1.4, 4.0, -6.2, 'gray')
    m.box(-1.0, 4.0, -6.4, 1.0, 4.4, -6.2, 'gray')
    m.box(-1.6, 0.5, -7.4, 1.6, 0.8, -6.2, 'gray')             # steps
    m.pixels(['.rbr.', 'byyyb', 'ryryr', 'byyyb', '.rbr.'], -1.0, 7.6, -6.2, 0.4,     # rose window
             {'r': 'g_stain_r', 'b': 'g_stain_b', 'y': 'g_stain_y'}, depth=0.1)
    m.box(-1.25, 5.3, -6.3, 1.25, 5.5, -6.2, 'gray')
    m.box(-1.25, 7.6, -6.3, 1.25, 7.8, -6.2, 'gray')
    m.box(-2.8, 10.4, -6.4, 2.8, 10.8, -1.2, 'gray')           # belfry with a gold bell
    for x in (-2.6, 1.9):
        for z in (-6.2, -2.1):
            m.box(x, 10.8, z, x + 0.7, 12.2, z + 0.7, 'stone')
    m.disc(0, -3.8, 11, 12, 0.7, 0.7, 'gold')
    m.box(-0.1, 12, -3.9, 0.1, 12.3, -3.7, 'dark_gold')
    m.box(-2.8, 12.2, -6.4, 2.8, 12.6, -1.2, 'gray')
    for i in range(5):                                         # spire
        h = 2.4 - i * 0.5
        m.box(-h, 12.6 + i * 0.55, -3.8 - h, h, 13.15 + i * 0.55, -3.8 + h, 'slate')
    m.box(-0.12, 15.0, -3.9, 0.12, 16, -3.7, 'gold')           # cross
    m.box(-0.45, 15.5, -3.9, 0.45, 15.72, -3.7, 'gold')
    for x in (-5.8, 5.8):                                      # lamp posts
        m.box(x - 0.15, 0.5, -6.6, x + 0.15, 4, -6.3, 'black')
        m.box(x - 0.45, 4, -6.9, x + 0.45, 5, -6.0, 'black')
        m.box(x - 0.3, 4.1, -6.95, x + 0.3, 4.9, -5.95, 'g_flame')
        m.box(x - 0.5, 5, -6.95, x + 0.5, 5.3, -5.95, 'snow')


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
    m.box(-7.8, 0.4, 7.2, 7.8, 15.6, 8, 'dark_brown')          # frame
    m.box(-7.3, 0.9, 6.9, 7.3, 15.1, 7.2, 'wood')
    m.box(-7.0, 1.0, 6.7, 7.0, 12.5, 6.9, 'dark_green')        # board
    for x, y in ((-6.6, 12.0), (6.2, 1.2), (-6.7, 1.3), (6.3, 11.9), (0.1, 12.1)):   # a few painted snowflakes
        m.box(x, y, 6.65, x + 0.35, y + 0.35, 6.7, 'white')
    m.box(-7.0, 12.5, 6.5, 7.0, 15.0, 6.9, 'red')               # banner
    m.box(-7.0, 12.5, 6.4, 7.0, 12.75, 6.5, 'gold')
    m.box(-7.0, 14.75, 6.4, 7.0, 15.0, 6.5, 'gold')
    text(m, 'ADVENT', 0, 14.45, 6.5, 0.38, 'gold')
    for s_ in (-1, 1):                                           # holly in the corners
        x = s_ * 6.2
        m.box(x - 0.6, 13.2, 6.3, x + 0.6, 13.8, 6.5, 'holly')
        m.box(x - 0.3, 13.0, 6.3, x + 0.3, 14.1, 6.5, 'holly')
        m.box(x - 0.2, 13.4, 6.15, x + 0.2, 13.7, 6.3, 'red')
    order = list(range(1, 25))
    random.Random(24).shuffle(order)
    cols, x0, y0, w, h = 6, -6.9, 1.15, 13.8 / 6, 11.2 / 4
    scheme = [('red', 'gold'), ('paper', 'red'), ('gold', 'dark_red'), ('red', 'white'), ('paper', 'green')]
    treats = ['red', 'yellow', 'pink', 'brown', 'white', 'green', 'gold', 'purple']
    for idx, n in enumerate(order):
        a, b = x0 + idx % cols * w + 0.15, y0 + idx // cols * h + 0.2
        c, d = a + w - 0.3, b + h - 0.4
        col, ink = scheme[n % 5]
        m.use('root')
        m.box(a, b, 6.6, c, d, 6.7, 'dark_brown')               # little cupboard behind the door
        m.use('c%d' % n)
        m.box(a, b, 6.3, c, d, 6.6, col)
        text(m, str(n), (a + c) / 2, (b + d) / 2 + 0.55, 6.3, 0.2, ink, depth=0.08)
        m.box(c - 0.35, b + 0.35, 6.2, c - 0.15, b + 0.6, 6.3, 'gold')
        m.use('o%d' % n)
        m.box(a - 0.12, b, 6.6 - (c - a) * 0.8, a + 0.04, d, 6.6, col)     # door swung open on its hinge
        t = treats[n % 8]                                          # wrapped sweet waiting inside
        cx, cy = (a + c) / 2, (b + d) / 2
        m.box(cx - 0.45, cy - 0.35, 6.25, cx + 0.45, cy + 0.35, 6.6, t)
        m.box(cx - 0.8, cy - 0.2, 6.35, cx - 0.45, cy + 0.2, 6.6, t)
        m.box(cx + 0.45, cy - 0.2, 6.35, cx + 0.8, cy + 0.2, 6.6, t)
    m.use('root')


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
    for a in (45, 135, 225, 315):                              # little gold feet
        x, z = 5.2 * math.cos(math.radians(a)), 5.2 * math.sin(math.radians(a))
        m.ell(x, 0.5, z, 0.9, 0.5, 0.9, 'gold', ymin=0)
    m.disc(0, 0, 0.5, 1.3, 6.6, 6.6, 'dark_brown')             # turned wooden base
    m.disc(0, 0, 1.3, 2.7, 6.1, 6.1, 'wood')
    m.disc(0, 0, 1.8, 2.1, 6.2, 6.2, 'gold')
    m.disc(0, 0, 2.7, 3.4, 6.4, 6.4, 'gold')
    m.box(-2.2, 1.35, -6.3, 2.2, 2.65, -6.05, 'gold')          # plaque
    m.box(-1.8, 1.6, -6.4, 1.8, 2.4, -6.3, 'dark_gold')
    m.disc(0, 0, 3.4, 4.0, 5.7, 5.7, 'snow')                    # the scene: snowy ground
    m.ell(-2.5, 4.0, 2.5, 2.4, 0.6, 2.2, 'snow', ymin=4.0)
    m.box(-3.8, 4.0, 0.4, -0.6, 6.4, 3.2, 'red')                # cottage with a lit window
    snowroof(m, -4.1, -0.3, 1.8, 6.3, 1.9, 0.38, 0.42, 'dark_red', icicles=False)
    m.box(-2.6, 4.0, 0.3, -1.8, 5.5, 0.4, 'brown')
    m.box(-1.4, 4.8, 0.3, -0.8, 5.5, 0.4, 'g_window')
    m.box(-3.5, 4.8, 0.3, -2.9, 5.5, 0.4, 'g_window')
    m.box(-1.4, 7.6, 2.2, -0.9, 8.6, 2.7, 'brick')
    for (tx, tz, s) in ((2.6, 1.6, 1.0), (3.8, -0.8, 0.7)):     # fir trees
        m.box(tx - 0.2, 4.0, tz - 0.2, tx + 0.2, 4.6, tz + 0.2, 'brown')
        for i in range(4):
            r = (1.7 - i * 0.38) * s
            m.disc(tx, tz, 4.5 + i * 1.05 * s, 5.4 + i * 1.05 * s, r, r, 'pine')
            m.disc(tx, tz, 5.25 + i * 1.05 * s, 5.4 + i * 1.05 * s, r * 0.8, r * 0.8, 'snow')
        m.box(tx - 0.3, 4.6 + 4.2 * s, tz - 0.3, tx + 0.3, 5.2 + 4.2 * s, tz + 0.3, 'yellow')
    m.ell(0.6, 4.7, -2.4, 0.85, 0.75, 0.85, 'white')            # snowman
    m.ell(0.6, 5.9, -2.4, 0.6, 0.55, 0.6, 'white')
    m.box(0.5, 5.85, -3.3, 0.7, 6.0, -2.95, 'carrot')
    m.box(0.2, 6.4, -2.8, 1.0, 6.5, -2.0, 'black')
    m.box(0.35, 6.5, -2.65, 0.85, 7.0, -2.15, 'black')
    m.box(0.0, 5.35, -3.05, 1.2, 5.6, -1.8, 'red')
    for x in (-4.0, -3.2, -2.4):                                 # fence
        m.box(x, 4.0, -3.2, x + 0.25, 5.0, -2.95, 'light_wood')
    m.box(-4.1, 4.6, -3.15, -2.0, 4.8, -3.0, 'light_wood')
    m.box(2.6, 4.0, -3.2, 2.8, 6.4, -3.0, 'black')              # lamp post
    m.box(2.45, 6.4, -3.35, 2.95, 6.9, -2.85, 'g_flame')
    glass_dome(m, 10.0, 6.0, 3.4)
    rnd = random.Random(3)
    for f in range(1, 4):
        m.use('f%d' % f)
        for _ in range(18):
            r, a, y = rnd.uniform(0, 4.4), rnd.uniform(0, 6.283), rnd.uniform(5.0, 15.0)
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
    'santa': (['...rr..', '..rrrw.', '.wwwww.', '.sksks.', '.swwws.', '..www..'], 'light_blue',
              {'r': 'red', 'w': 'white', 's': 'skin', 'k': 'black'}),
}


def card(m, kind, x0, y0, z0, w=3.6, h=4.8, lean=0.32):
    """Greeting card leaning back against the step behind it (drawn in thin stepped rows)."""
    rows, bg, cmap = CARDS[kind]
    n = 16
    for i in range(n):                                          # the card face, leaning back
        y = y0 + h * i / n
        z = z0 + lean * (y - y0)
        m.box(x0, y, z, x0 + w, y + h / n + 0.02, z + 0.25, bg)
        m.box(x0 + 0.08, y, z + 0.25, x0 + w - 0.08, y + h / n + 0.02, z + 0.3, 'paper')
    m.box(x0 - 0.05, y0 + h - 0.12, z0 + lean * h - 0.05, x0 + w + 0.05, y0 + h + 0.05, z0 + lean * h + 0.3, 'gold')
    ps = min((w - 0.8) / len(rows[0]), (h - 1.0) / len(rows))
    ax = x0 + (w - ps * len(rows[0])) / 2
    top = y0 + h - (h - ps * len(rows)) / 2
    for r, row in enumerate(rows):                              # artwork follows the lean
        y = top - (r + 0.5) * ps
        m.pixels([row], ax, top - r * ps, z0 + lean * (y - y0), ps, cmap, depth=0.1)


@deco(id='card_stand', name='Christmas Card Stand', recipe=['paper', 'paper', 'paper', 'stick'])
def card_stand(m):
    for y0, z0 in ((0, -5.4), (1.8, -1.6), (3.6, 2.0)):        # three-step stand with dark lips
        m.box(-7.6, y0, z0, 7.6, y0 + 1.8, 5.4, 'light_wood')
        m.box(-7.7, y0 + 1.5, z0 - 0.1, 7.7, y0 + 1.8, z0 + 0.25, 'wood')
        m.box(-7.7, y0, z0 - 0.1, 7.7, y0 + 0.25, z0 + 0.25, 'wood')
    m.box(-7.7, 0, 5.2, 7.7, 5.6, 5.5, 'wood')
    card(m, 'tree', -7.0, 1.8, -5.0)
    card(m, 'snowman', -1.8, 1.8, -5.0)
    card(m, 'bauble', 3.4, 1.8, -5.0)
    card(m, 'wreath', -4.4, 3.6, -1.2)
    card(m, 'ginger', 0.8, 3.6, -1.2)
    card(m, 'star', -1.8, 5.4, 2.4, w=3.4, h=4.4)
    card(m, 'santa', 2.8, 5.4, 2.4, w=3.4, h=4.4)
    card(m, 'cane', -6.4, 5.4, 2.4, w=3.4, h=4.4)
    for x in (-7.4, 7.0):                                        # posts with a string of mini cards
        m.box(x, 5.4, 4.8, x + 0.4, 14.4, 5.2, 'wood')
        m.box(x - 0.15, 14.4, 4.65, x + 0.55, 14.8, 5.35, 'gold')
    pts = [(x, 13.8 - 1.4 * (1 - (x / 7.2) ** 2), 5.0) for x in [i * 0.9 - 7.2 for i in range(17)]]
    m.tube(pts, 0.22, ['red'])
    minis = [('red', 'g'), ('paper', 'r'), ('green', 'w'), ('navy', 'y'), ('paper', 'g')]
    for i, (bg, ink) in enumerate(minis):
        x = -5.4 + i * 2.7
        y = 13.8 - 1.4 * (1 - (x / 7.2) ** 2)
        m.box(x - 0.2, y - 0.35, 4.75, x + 0.2, y + 0.25, 5.25, 'light_wood')        # clothes peg
        m.box(x - 0.9, y - 2.6, 4.85, x + 0.9, y - 0.2, 5.0, bg)
        m.pixels(['.x.', 'xxx', '.x.'], x - 0.45, y - 0.9, 4.85, 0.3,
                 {'x': {'g': 'green', 'r': 'red', 'w': 'white', 'y': 'yellow'}[ink]}, depth=0.08)
    m.box(-7.2, 1.8, -1.4, -5.8, 2.9, 0.0, 'holly')             # sprig of holly
    m.box(-6.8, 2.9, -1.0, -6.3, 3.4, -0.5, 'red')


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


def gift(m, x0, y0, z0, x1, y1, z1, c, rib, pattern=None, pat='white', bow_col=None, bow_s=1.0):
    """Wrapped present: paper pattern on the front and right faces, ribbon cross, big bow."""
    m.box(x0, y0, z0, x1, y1, z1, c)
    m.box(x0 - 0.05, y1 - 0.25, z0 - 0.05, x1 + 0.05, y1, z1 + 0.05, c)      # lid edge
    m.box(x0 - 0.12, y1 - 0.9, z0 - 0.12, x1 + 0.12, y1 - 0.25, z1 + 0.12, c)
    if pattern == 'stripes':
        for x in [x0 + 0.4 + i * 1.2 for i in range(int((x1 - x0) / 1.2))]:
            m.box(x, y0, z0 - 0.04, x + 0.5, y1 - 0.9, z0, pat)
        for z in [z0 + 0.4 + i * 1.2 for i in range(int((z1 - z0) / 1.2))]:
            m.box(x1, y0, z, x1 + 0.04, y1 - 0.9, z + 0.5, pat)
    if pattern == 'dots':
        rnd = random.Random(int(x0 * 7 + y0 * 13))
        for _ in range(int((x1 - x0) * (y1 - y0) / 3)):
            x, y = rnd.uniform(x0 + 0.2, x1 - 0.6), rnd.uniform(y0 + 0.2, y1 - 1.4)
            m.box(x, y, z0 - 0.04, x + 0.4, y + 0.4, z0, pat)
            z, y = rnd.uniform(z0 + 0.2, z1 - 0.6), rnd.uniform(y0 + 0.2, y1 - 1.4)
            m.box(x1, y, z, x1 + 0.04, y + 0.4, z + 0.4, pat)
    cx, cz, e = (x0 + x1) / 2, (z0 + z1) / 2, 0.16
    m.box(cx - 0.45, y0, z0 - e, cx + 0.45, y1 + 0.05, z1 + e, rib)
    m.box(x0 - e, y0, cz - 0.45, x1 + e, y1 + 0.05, cz + 0.45, rib)
    if bow_col is not False:
        bow(m, cx, y1 + 0.05, cz, bow_col or rib, bow_s)


@deco(id='present_stack', name='Present Stack', cells=[(0, 0, 0), (0, 1, 0)],
      recipe=['paper', 'paper', 'red_dye', 'green_dye', 'string'])
def present_stack(m):
    gift(m, -6.8, 0, -6, 2.4, 7.5, 4.8, 'red', 'gold', 'dots', 'white', bow_col=False)
    gift(m, 3.0, 0, -7.0, 7.4, 4.6, -2.4, 'green', 'red', 'stripes', 'dark_green', bow_s=0.9)
    gift(m, 3.0, 0, -1.6, 7.4, 9.2, 5.2, 'purple', 'silver', 'stripes', 'lilac', bow_s=0.9)
    gift(m, -5.6, 7.5, -5.0, 1.4, 13.0, 3.6, 'blue', 'white', 'dots', 'light_blue', bow_col=False)
    gift(m, -4.6, 13.0, -4.0, 0.6, 17.6, 2.6, 'gold', 'red', bow_col=False)
    gift(m, -3.8, 17.6, -3.2, 0.0, 21.4, 1.6, 'white', 'green', 'stripes', 'red', bow_col=False)
    gift(m, -3.0, 21.4, -2.4, -0.6, 23.8, 0.4, 'pink', 'white', 'dots', 'white', bow_s=0.9)
    m.box(-2.0, 25.2, -1.2, -1.6, 26.6, -0.8, 'gold')                       # star on a little stem
    m.pixels(['...y...', '..yyy..', 'yyyyyyy', '.yyyyy.', '..y.y..', '.y...y.'], -4.4, 31.4, -0.7, 0.7,
             {'y': 'g_star'}, depth=0.6)
    m.box(-0.1, 7.6, -6.5, 1.6, 9.6, -6.35, 'paper')                        # gift tag
    m.box(0.2, 9.6, -6.45, 0.4, 10.4, -6.4, 'red')
    m.box(-6.4, 0, -7.3, -3.6, 0.5, -6.1, 'snow')                           # a little drift of snow


@deco(id='snowy_bench', name='Snowy Bench', cells=[(0, 0, 0), (1, 0, 0)], collision=8,
      recipe=['oak_planks', 'oak_planks', 'iron_ingot', 'snowball'])
def snowy_bench(m):
    for x in (-5.6, 20.6):                                      # curly cast-iron ends
        m.tube([(x, 0.3, -4.6), (x, 6.2, -4.6)], 1.0, ['black'])
        m.tube([(x, 0.3, 4.4), (x, 6.2, 3.4), (x, 15.4, 4.8)], 1.0, ['black'])
        m.tube([(x, 6.2, -4.6), (x, 6.2, 3.4)], 0.8, ['black'])
        m.tube([(x, 6.4, -4.6), (x, 9.6, -4.4), (x, 10.4, -2.0), (x, 10.6, 1.0), (x, 11.6, 3.8)], 0.8, ['black'])   # armrest
        m.tube([(p[0], p[1], p[2]) for p in [(x, 9.6 + 1.0 * math.sin(math.radians(a)), -4.4 - 1.0 * math.cos(math.radians(a))) for a in range(0, 300, 30)]], 0.6, ['black'])
        m.tube([(x, 0.3, -4.6), (x, 1.6, -5.6)], 0.8, ['black'])
        m.tube([(x, 0.3, 4.4), (x, 1.4, 5.4)], 0.8, ['black'])
        m.box(x - 1.2, 10.6, -3.2, x + 1.2, 11.2, 1.6, 'snow')
        m.ell(x, 0, 0, 2.6, 1.3, 5.6, 'snow', ymin=0)
    for i in range(5):                                          # seat slats
        z = -4.6 + i * 1.6
        m.box(-6.2, 6.6, z, 22.2, 7.4, z + 1.25, 'wood' if i % 2 else 'light_wood')
    for i in range(4):                                          # tilted back slats
        y, z = 8.2 + i * 1.8, 3.6 + i * 0.4
        m.box(-6.2, y, z, 22.2, y + 1.4, z + 0.8, 'wood' if i % 2 else 'light_wood')
    m.box(-6.2, 15.0, 4.4, 22.2, 15.5, 6.0, 'snow')
    m.ell(18.0, 7.4, -0.6, 3.8, 1.4, 3.6, 'snow', ymin=7.4)      # snow piles on the seat
    m.ell(-2.8, 7.4, 0.4, 2.6, 0.9, 2.8, 'snow', ymin=7.4)
    plaid = ['red', 'red', 'dark_green', 'red', 'red', 'green', 'red', 'red', 'dark_green', 'red']
    for i, c in enumerate(plaid):                               # plaid blanket draped over the middle
        x = 3.0 + i
        m.box(x, 7.4, -3.4, x + 1, 7.8, 3.4, c)                 # on the seat
        m.box(x, 2.8, -4.95, x + 1, 7.8, -4.55, c)              # hanging over the front edge
        m.box(x, 7.8, 3.2, x + 1, 15.6, 3.6, c)                 # up the backrest
        m.box(x, 15.6, 3.2, x + 1, 16.0, 6.2, c)                # folded over the top
    for y in (4.6, 9.8, 12.8):
        m.box(3.0, y, -5.0 if y < 6 else 3.15, 13.0, y + 0.3, -4.9 if y < 6 else 3.2, 'yellow')
    for z in (-1.2, 1.6):
        m.box(3.0, 7.8, z, 13.0, 7.85, z + 0.3, 'yellow')
    for x in [3.2 + i * 0.9 for i in range(11)]:                # fringe
        m.box(x, 2.2, -4.85, x + 0.4, 2.8, -4.65, 'red')
    m.disc(15.0, -1.5, 7.4, 9.6, 0.95, 0.95, 'red')             # mug of cocoa with marshmallows
    m.disc(15.0, -1.5, 9.4, 9.7, 0.8, 0.8, 'brown')
    m.box(14.6, 9.6, -1.8, 15.0, 9.95, -1.4, 'white')
    m.box(15.1, 9.6, -1.4, 15.5, 9.95, -1.0, 'white')
    m.box(15.9, 7.9, -1.7, 16.4, 9.1, -1.3, 'red')
    m.box(16.4, 8.2, -1.7, 16.6, 8.8, -1.3, 'red')
    m.box(22.6, 0, -6.6, 24.4, 0.4, -4.8, 'black')              # lantern on the ground
    m.box(22.8, 0.4, -6.4, 24.2, 3.0, -5.0, 'g_flame')
    for x in (22.7, 24.0):
        for z in (-6.5, -5.2):
            m.box(x, 0.4, z, x + 0.3, 3.0, z + 0.3, 'black')
    m.box(22.6, 3.0, -6.6, 24.4, 3.5, -4.8, 'black')
    m.box(23.3, 3.5, -5.9, 23.7, 4.2, -5.5, 'black')
    m.box(22.5, 3.5, -6.7, 24.5, 3.8, -4.7, 'snow')


@deco(id='light_arch', name='Light-Up Arch', cells=[(i, j, 0) for j in range(3) for i in range(3)], toggle=True, light=12,
      collision={0: [-8, 0, -4, 16, 16, 8], 2: [-8, 0, -4, 16, 16, 8], 3: [-8, 0, -4, 16, 16, 8], 5: [-8, 0, -4, 16, 16, 8]},
      cfg=dict(toggle=True, flicker=True, sound='random.click'),
      recipe=['spruce_leaves', 'spruce_leaves', 'glowstone_dust', 'glowstone_dust', 'string'])
def light_arch(m):
    L, R, top = -4.0, 36.0, 26.0                                   # 3 blocks wide, walk-through gap of ~2 blocks
    cx, rx, ry = (L + R) / 2, (R - L) / 2, 13.0
    curve = [(cx - rx * math.cos(math.radians(a)), top + ry * math.sin(math.radians(a)), 0) for a in range(0, 181, 6)]
    path = [(L, 1.0, 0), (L, top, 0)] + curve + [(R, 1.0, 0)]
    m.tube(path, 4.0, ['pine', 'dark_green', 'pine', 'green', 'holly'], stripe=0.8, step=1.2)   # thick garland
    rnd = random.Random(5)
    for a, b in zip(path, path[1:]):                               # needle tufts sticking out of the garland
        for _ in range(int(math.dist(a, b) / 1.6)):
            t = rnd.random()
            p = [a[q] + (b[q] - a[q]) * t for q in range(3)]
            dx, dz = rnd.choice([(2.2, 0), (-2.2, 0), (0, 2.2), (0, -2.2)])
            m.box(p[0] + dx - 0.6, p[1] - 0.6, p[2] + dz - 0.6, p[0] + dx + 0.6, p[1] + 0.6, p[2] + dz + 0.6, rnd.choice(['pine', 'dark_green']))
    bulbs = ['g_red', 'g_green2', 'g_blue', 'g_yellow2', 'g_red2', 'g_green', 'g_blue2', 'g_yellow', 'g_purple', 'g_white']
    k, s = 0, 0.0
    for a, b in zip(path, path[1:]):                               # big bulbs every 2.4 px on the front and the back
        d = math.dist(a, b)
        while s <= d:
            p = [a[q] + (b[q] - a[q]) * s / d for q in range(3)]
            for z, sh in ((-2.6, 0), (2.0, 1)):
                c = bulbs[(k + sh * 3) % 10]
                m.box(p[0] - 0.6, p[1] - 0.6, z, p[0] + 0.6, p[1] + 0.6, z + 0.6, c)
                m.box(p[0] - 0.25, p[1] + 0.6, z + 0.1, p[0] + 0.25, p[1] + 0.9, z + 0.5, 'dark_gray')
            k, s = k + 1, s + 2.4
        s -= d
    for i, x in enumerate((L, R)):                                 # snowy planters + red bows
        m.box(x - 3.4, 0, -3.4, x + 3.4, 2.6, 3.4, 'dark_red')
        m.box(x - 3.6, 2.2, -3.6, x + 3.6, 2.8, 3.6, 'gold')
        m.ell(x, 2.8, 0, 3.0, 1.0, 3.0, 'snow', ymin=2.8)
        bow(m, x, top - 1.6, -2.9, 'red', 1.3, knot='dark_red')
        m.box(x - 1.1, top - 6.0, -3.0, x - 0.4, top - 0.8, -2.6, 'red')      # ribbon tails
        m.box(x + 0.4, top - 6.4, -3.0, x + 1.1, top - 0.8, -2.6, 'red')
    m.pixels(['....y....', '...yyy...', 'yyyyyyyyy', '.yyyyyyy.', '..yyyyy..', '.yyy.yyy.', 'yy.....yy'], cx - 3.15, 46.4, -0.6, 0.7,
             {'y': 'g_star'}, depth=1.2)                                  # star sitting on the crest


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


def stamp(m, fn, dx, dy, dz, s=1.0):
    """Build another decoration into this model, scaled by s and moved; only its resting look is kept."""
    t = Model()
    fn(t)
    for c in t.cubes:
        if c[7] not in ('root', 'f0'):
            continue
        m.cubes.append([c[0] * s + dx, c[1] * s + dy, c[2] * s + dz, c[3] * s + dx, c[4] * s + dy, c[5] * s + dz, c[6], m.bone])


def person(m, x, y, z, coat, hat='red', legs='navy', arms='down', item=None):
    """Townsperson about 5 px tall, facing the front."""
    for sx in (-0.38, 0.38):
        m.box(x + sx - 0.27, y, z - 0.3, x + sx + 0.27, y + 1.6, z + 0.3, legs)
    m.box(x - 0.75, y + 1.5, z - 0.45, x + 0.75, y + 3.4, z + 0.45, coat)
    m.box(x - 0.78, y + 3.0, z - 0.5, x + 0.78, y + 3.4, z + 0.5, 'white' if coat != 'white' else 'red')   # scarf
    m.box(x - 0.55, y + 3.4, z - 0.55, x + 0.55, y + 4.5, z + 0.55, 'skin')
    m.box(x - 0.3, y + 3.85, z - 0.6, x - 0.12, y + 4.05, z - 0.55, 'black')
    m.box(x + 0.12, y + 3.85, z - 0.6, x + 0.3, y + 4.05, z - 0.55, 'black')
    m.box(x - 0.62, y + 4.4, z - 0.62, x + 0.62, y + 4.9, z + 0.62, hat)
    m.box(x - 0.2, y + 4.9, z - 0.2, x + 0.2, y + 5.3, z + 0.2, 'white')
    if arms == 'down':
        for sx in (-1, 1):
            m.box(x + sx * 0.75, y + 1.7, z - 0.25, x + sx * 1.1, y + 3.3, z + 0.25, coat)
    elif arms == 'out':
        for sx in (-1, 1):
            m.box(x + sx * 0.75, y + 2.9, z - 0.25, x + sx * 2.0, y + 3.3, z + 0.25, coat)
    elif arms == 'up':
        for sx in (-1, 1):
            m.box(x + sx * 0.75, y + 3.0, z - 0.25, x + sx * 1.1, y + 4.8, z + 0.25, coat)
    elif arms == 'front':
        for sx in (-1, 1):
            m.box(x + sx * 0.75 - 0.35 * (sx > 0), y + 2.4, z - 1.3, x + sx * 0.75 + 0.35 * (sx < 0), y + 2.8, z - 0.3, coat)
    if item == 'book':
        m.box(x - 0.6, y + 2.5, z - 1.5, x + 0.6, y + 3.3, z - 1.3, 'dark_red')
        m.box(x - 0.5, y + 2.6, z - 1.55, x + 0.5, y + 3.2, z - 1.5, 'paper')
    if item == 'gifts':
        m.present(x - 0.9, y + 2.0, z - 1.9, x + 0.9, y + 3.2, z - 0.6, 'green', 'red', w=0.3, bow=False)
        m.present(x - 0.6, y + 3.2, z - 1.7, x + 0.6, y + 3.9, z - 0.8, 'red', 'gold', w=0.25, bow=False)


def pine(m, x, y, z, h, r, snow=True, lights=None):
    m.box(x - 0.4, y, z - 0.4, x + 0.4, y + h * 0.15, z + 0.4, 'brown')
    n = max(3, int(h / 1.6))
    rnd = random.Random(int(x * 31 + z * 17 + y))
    for i in range(n):
        f = 1 - i / n
        rr = max(0.4, r * f)
        y0 = y + h * 0.12 + i * h * 0.85 / n
        m.disc(x, z, y0, y0 + h * 0.85 / n + 0.2, rr, rr, 'pine' if i % 2 else 'dark_green')
        if snow:
            m.disc(x, z, y0 + h * 0.85 / n, y0 + h * 0.85 / n + 0.25, rr * 0.75, rr * 0.75, 'snow')
        if lights and rr > 0.8:
            for k in range(3):
                a = rnd.uniform(0, 6.283)
                m.box(x + rr * math.cos(a) - 0.3, y0 + 0.3, z + rr * math.sin(a) - 0.3, x + rr * math.cos(a) + 0.3, y0 + 0.9,
                      z + rr * math.sin(a) + 0.3, lights[(i + k) % len(lights)])


def lamp(m, x, y, z):
    m.box(x - 0.2, y, z - 0.2, x + 0.2, y + 5.5, z + 0.2, 'black')
    m.box(x - 0.55, y + 5.5, z - 0.55, x + 0.55, y + 6.6, z + 0.55, 'g_flame')
    m.box(x - 0.65, y + 6.6, z - 0.65, x + 0.65, y + 7.0, z + 0.65, 'black')
    m.box(x - 0.6, y + 7.0, z - 0.6, x + 0.6, y + 7.2, z + 0.6, 'snow')


TOWN_CELLS = [(i, j, k) for j in range(2) for k in range(5) for i in (0, -2, -1, 1, 2)]   # base = front middle


@deco(id='mini_village', name='Mini Christmas Village', cells=TOWN_CELLS, frames=4, anim_only=True, light=7, tick=[30, 50],
      collision={n: 2 for n in range(25)},
      cfg=dict(anim=[1, 2, 3, 0, 1, 2, 3, 0], delay=5, sound='note.bell', every=4, idle=[1, 2, 3, 0], idle_delay=7),
      recipe=['oak_planks', 'snowball', 'snowball', 'glowstone_dust', 'torch', 'paper'])
def mini_village(m):
    G = 1.5                                                          # ground (snow) height
    m.box(-40, 0, -8, 40, G, 72, 'snow')
    m.box(-40, 0, -8, 40, 0.6, -7.6, 'light_wood')                  # tabletop edge
    rnd = random.Random(42)
    for _ in range(14):                                              # soft snow drifts
        x, z = rnd.uniform(-38, 38), rnd.uniform(-6, 38)
        if -27 < x < -1 and -5 < z < 13: continue                    # keep the pond clear
        m.ell(x, G, z, rnd.uniform(1.5, 3), 0.7, rnd.uniform(1.5, 3), 'snow', ymin=G)
    # back hill in two steps, with a ramp on the left for sledding
    m.box(-40, G, 40, 40, 5.5, 72, 'snow')
    m.box(-40, 5.5, 54, 40, 9.5, 72, 'snow')
    for i in range(10):
        m.box(-40, G, 22 + i * 1.8, -30, G + 0.4 * (i + 1), 24 + i * 1.8, 'snow')
    for x0, x1 in ((-40, 40),):
        m.box(x0, 5.2, 39.8, x1, 5.5, 40.2, 'white')
    # mountains with snow caps and pines
    for cx, h, w in ((-28, 28, 14), (-8, 20, 10), (10, 22, 11), (29, 30, 12)):
        n = min(int(h / 1.5), 14)                                     # tops stay under the 2-block limit
        for i in range(n):
            f = (1 - i / n) ** 0.75
            ww = w * f + 0.8
            sh = math.sin(i * 1.7 + cx) * 0.8                          # wobble so the slopes look natural
            col = 'snow' if i > n * 0.62 else ('stone' if i % 3 == 0 else 'slate')
            m.box(cx - ww + sh, 9.5 + i * 1.5 - 0.01, 70 - ww * 0.7 - 1.5, cx + ww + sh, 9.5 + i * 1.5 + 1.5, 72, col)
            if i > n * 0.45 and i <= n * 0.62:                        # snow streaks running down
                m.box(cx - ww * 0.4 + sh, 9.5 + i * 1.5 + 1.5, 70 - ww * 0.7 - 1.6, cx + ww * 0.1 + sh, 9.5 + i * 1.5 + 1.6, 72, 'snow')
    for x, z, h in ((-36, 60, 9), (-18, 58, 8), (-2, 60, 7), (18, 58, 9), (36, 60, 8), (-32, 46, 7), (34, 46, 6), (-6, 48, 6), (8, 50, 7)):
        pine(m, x, 9.5 if z >= 54 else 5.5, z, h, 2.2)
    # church on the hill, cottage and bakery on the lower step, toy shop + gingerbread on the street
    stamp(m, village_church, 0, 9.5, 60)
    stamp(m, village_cottage, -22, 5.5, 46)
    stamp(m, village_bakery, 22, 5.5, 46)
    stamp(m, village_toy_shop, -16, G, 28)
    stamp(m, gingerbread_house, 13, G, 28, s=0.5)
    pine(m, -30, G, 30, 8, 2.4)
    pine(m, 30, G, 30, 7, 2.2)
    # cobblestone path up to the church and a street across
    m.box(-2.5, G, 16, 2.5, G + 0.12, 40, 'stone')
    for i in range(6):
        m.box(-2.5, G + i * 0.7, 40 + i * 0.7, 2.5, G + (i + 1) * 0.7 + 0.1, 41 + i * 0.7, 'gray')
    m.box(-2.5, 5.5, 44, 2.5, 5.62, 54, 'stone')
    for i in range(6):
        m.box(-2.5, 5.5 + i * 0.7, 54 + i * 0.4, 2.5, 5.5 + (i + 1) * 0.7 + 0.1, 55 + i * 0.4, 'gray')
    m.box(-38, G, 16, 38, G + 0.12, 20, 'stone')
    for x in (-34, -18, 6, 20, 36):
        lamp(m, x, G, 21)
    lamp(m, 4, 5.5, 44)
    lamp(m, -4, 5.5, 50)
    # frozen pond
    m.disc(-14, 4, G - 0.2, G + 0.15, 12, 7.5, 'light_blue')
    m.disc(-14, 4, G + 0.15, G + 0.2, 10.5, 6.2, 'snow')                 # icy sheen (solid: one render method per block)
    for x in (-26.5, -1.5):
        m.box(x, G, 2.5, x + 1, G + 0.8, 5.5, 'snow')
    # big Christmas tree with lights, star and presents
    pine(m, 24, G, 6, 26, 6.5, snow=False, lights=['g_red', 'g_yellow2', 'g_blue', 'g_green2', 'g_purple', 'g_white'])
    m.pixels(['.y.', 'yyy', '.y.'], 23.1, 29.6, 6, 0.6, {'y': 'g_star'}, depth=0.6)
    for x, z, c, r in ((20.5, 0.5, 'red', 'gold'), (26.5, 0.8, 'blue', 'white'), (23.5, -0.5, 'green', 'red'), (28, 3, 'gold', 'red')):
        m.present(x - 1, G, z - 1, x + 1, G + 1.6, z + 1, c, r, w=0.35, bow=False)
    # a family building a snowman
    m.ell(-34, G + 1.6, 4, 1.8, 1.7, 1.8, 'white')
    m.ell(-34, G + 4.2, 4, 1.2, 1.1, 1.2, 'white')
    m.box(-34.2, G + 4.0, 2.4, -33.8, G + 4.4, 2.8, 'carrot')
    m.box(-35.1, G + 5.2, 3.1, -32.9, G + 5.5, 4.9, 'black')
    m.box(-34.7, G + 5.5, 3.5, -33.3, G + 6.6, 4.5, 'black')
    person(m, -37.5, G, 3, 'green', hat='white', arms='up')
    # carolers by the lamp
    for i, (c, h) in enumerate((('red', 'green'), ('blue', 'red'), ('purple', 'white'), ('dark_green', 'red'))):
        person(m, 2 + i * 2.4, G, 6 + (i % 2) * 0.8, c, hat=h, arms='front', item='book')
    lamp(m, 12.5, G, 7)
    # ---- the moving parts: four frames ----
    for f in range(4):
        m.use('f%d' % f)
        for k, (c, h) in enumerate((('red', 'white'), ('blue', 'red'), ('yellow', 'green'))):   # skaters circling the pond
            a = math.radians(f * 90 + k * 120 + 20)
            person(m, -14 + 8 * math.cos(a), G + 0.2, 4 + 4.3 * math.sin(a), c, hat=h, arms='out')
        sz = 40 - f * 5                                              # sled ride down the ramp
        sy = G + max(0.0, (sz - 22) / 1.8) * 0.4
        m.box(-37.5, sy, sz - 1.6, -32.5, sy + 0.5, sz + 1.6, 'red')
        m.box(-37.5, sy - 0.3, sz - 2.0, -37, sy, sz + 1.8, 'gold')
        m.box(-33, sy - 0.3, sz - 2.0, -32.5, sy, sz + 1.8, 'gold')
        person(m, -35, sy + 0.5, sz, 'orange', hat='blue', arms='out')
        bx = -27 + f * 1.6                                           # kid rolling a growing snowball
        r = 0.9 + f * 0.25
        m.ell(bx, G + r, 10, r, r, r, 'white')
        person(m, bx - r - 1.0, G, 10, 'pink', hat='purple', arms='front')
        wx = -6 + f * 3.5                                            # someone carrying presents down the street
        person(m, wx, G + 0.12, 18, 'dark_red', hat='green', arms='front', item='gifts')
    m.use('root')


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
        day = "(q.block_state('santa:day_a') * 16 + q.block_state('santa:day_b'))"
        if re.fullmatch(r'c\d+', b): vis[b] = '%s < %s' % (day, b[1:])
        if re.fullmatch(r'o\d+', b): vis[b] = '%s >= %s' % (day, b[1:])
    return vis


def materials(uses, lit):
    rm = 'blend' if 'glass' in uses else 'alpha_test'      # Minecraft wants one render_method for every instance of a block
    m = {'*': {'texture': 'santa_decor', 'render_method': rm}}
    if 'glow' in uses:
        m['glow'] = {'texture': 'santa_decor_lit' if lit else 'santa_decor', 'render_method': rm,
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
    animated = not spec.get('anim_only') or n in spec['anim_cells']   # anim_only: frame state only where things move
    if spec.get('frames') and animated: states['santa:frame'] = list(range(spec['frames']))
    if spec.get('advent'): states.update({'santa:day_a': [0, 1], 'santa:day_b': list(range(16))})   # day = a*16 + b (states max 16 values)
    desc = {'identifier': ident, 'menu_category': {'category': 'none' if part else 'items'},
            'traits': {'minecraft:placement_direction': {'enabled_states': ['minecraft:cardinal_direction'], 'y_rotation_offset': 180}}}
    if states: desc['states'] = states
    gid = 'geometry.' + ident.replace(':', '_')
    vis = bone_vis(spec['model'].bones) if animated else {}
    col = spec.get('collision', 'full')
    if isinstance(col, dict): col = col.get(n)
    full = [-8, 0, -8, 16, 16, 16]
    comp = {
        'minecraft:geometry': {'identifier': gid, 'bone_visibility': vis} if vis else gid,
        'minecraft:material_instances': materials(uses, True),
        'minecraft:collision_box': False if col is None else box_json(full if col == 'full' else [-8, 0, -8, 16, col, 16] if isinstance(col, (int, float)) else col),
        'minecraft:selection_box': False if n in spec.get('empty', ()) else box_json(full),
        'minecraft:destructible_by_mining': {'seconds_to_destroy': 0.3},
    }
    if spec.get('light'):
        comp['minecraft:light_emission'] = spec['light']
    cc = (['santa:decor'] if spec.get('cfg') or spec.get('night') else []) + (['santa:multipart'] if len(spec['cells']) > 1 else [])
    if spec.get('tick') and not part: cc.append('santa:idle')   # onTick only where minecraft:tick exists
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
        cells = split(s)
        s['anim_cells'] = {n for n, cubes in enumerate(cells) if any(c[7] != 'root' for c in cubes)}
        for n, cubes in enumerate(cells):
            s['empty'] = s.get('empty', set())
            if not cubes:   # Minecraft won't take an empty model: give it one invisible speck
                cubes = [[-0.05, 0, -0.05, 0.05, 0.1, 0.05, 'clear', 'root']]
                s['empty'].add(n)
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
def render(spec, size=420, day=6, yaw=32, pitch=24):
    yaw, pitch = math.radians(yaw), math.radians(pitch)
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
            rgba = tuple(int(v * k) for v in col) + ((60,) if c == 'glass' else (255,))
            o, u, v = pts[0], [pts[1][q] - pts[0][q] for q in range(3)], [pts[3][q] - pts[0][q] for q in range(3)]
            nu, nv = max(1, math.ceil(math.hypot(*u) / 1.5)), max(1, math.ceil(math.hypot(*v) / 1.5))
            if c == 'glass': nu = nv = 1
            for a in range(nu):
                for b in range(nv):
                    q = [[o[t] + u[t] * (a + da) / nu + v[t] * (b + db) / nv for t in range(3)] for da, db in ((0, 0), (1, 0), (1, 1), (0, 1))]
                    pp = [proj(p) for p in q]
                    polys.append((sum(p[2] for p in pp) / 4, [(p[0], p[1]) for p in pp], rgba))
    xs = [p[0] for _, ps, _ in polys for p in ps]; ys = [p[1] for _, ps, _ in polys for p in ps]
    sc = (size - 30) / max(max(xs) - min(xs), max(ys) - min(ys))
    ox, oy = (size - (max(xs) - min(xs)) * sc) / 2 - min(xs) * sc, (size - (max(ys) - min(ys)) * sc) / 2 + max(ys) * sc
    img = Image.new('RGB', (size, size), (58, 66, 84))   # RGB so translucent glass blends
    d = ImageDraw.Draw(img, 'RGBA')
    for _, ps, rgba in sorted(polys, key=lambda t: -t[0]):
        d.polygon([(ox + x * sc, oy - y * sc) for x, y in ps], fill=rgba)
    d.text((8, 6), spec['name'], fill=(255, 255, 255, 255))
    return img.convert('RGBA')


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
