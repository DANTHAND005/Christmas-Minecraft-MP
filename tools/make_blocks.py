#!/usr/bin/env python3
"""Christmas building blocks for Santa's Workbench: candy blocks (full cubes with their own textures) and the
Christmas light path, whose bulbs run along every edge that doesn't touch another light path block.

    python3 tools/make_blocks.py        (run after tools/make_decor.py; it reuses its palette textures)
"""
import json, math, os, random, sys
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_decor as D

ROOT = D.ROOT
BP, RP = D.BP, D.RP
TEX = os.path.join(RP, 'textures', 'blocks')


def img(fn):
    im = Image.new('RGBA', (16, 16))
    for x in range(16):
        for y in range(16):
            im.putpixel((x, y), tuple(max(0, min(255, round(v))) for v in fn(x, y)) + (255,))
    return im


def mul(c, k):
    return tuple(v * k for v in c)


def noise(x, y, seed=0):
    return ((x * 73856093) ^ (y * 19349663) ^ (seed * 83492791)) % 7 / 6.0


RED, WHITE, MINT = (206, 30, 42), (246, 246, 242), (40, 164, 76)
GINGER, DGINGER = (176, 102, 48), (122, 66, 28)
ICING = (250, 250, 248)


def stripes(a, b):
    return img(lambda x, y: mul(a if ((x + y) // 4) % 2 == 0 else b, 0.94 + 0.06 * noise(x, y)))


def peppermint():
    def f(x, y):
        dx, dy = x - 7.5, y - 7.5
        r = math.hypot(dx, dy)
        if r > 7.6: return mul(WHITE, 0.92)
        if r < 1.6: return WHITE
        seg = int((math.atan2(dy, dx) + math.pi) / (2 * math.pi) * 8 + r * 0.18) % 2      # swirled wedges
        return RED if seg else WHITE
    return img(f)


def gingerbread():
    """Smooth baked gingerbread: warm brown, darker rim, faint horizontal grain."""
    def f(x, y):
        if x in (0, 15) or y in (0, 15): return (132, 74, 30)
        if x in (1, 14) or y in (1, 14): return (160, 92, 40)
        grain = 0.04 if (y + (x // 5)) % 4 == 0 else -0.03 if (y * 3 + x // 4) % 7 == 0 else 0
        return mul((186, 112, 52), 1 + grain + 0.02 * noise(x, y, 1))
    return img(f)


def iced_gingerbread():
    base = gingerbread()
    for i in range(16):                                            # wavy piped icing around the edge
        w = 1 + (i % 4 in (1, 2))
        for d in range(w):
            for p in ((i, d), (i, 15 - d), (d, i), (15 - d, i)):
                base.putpixel(p, ICING + (255,))
    for p in ((5, 5), (10, 5), (5, 10), (10, 10), (7, 7), (8, 8)):  # little icing dots
        base.putpixel(p, ICING + (255,))
    return base


def icing_top():
    return img(lambda x, y: mul(ICING, 0.95 + 0.05 * noise(x, y, 5)))


def icing_side():
    drips = [5, 7, 4, 9, 6, 4, 8, 11, 5, 6, 10, 4, 7, 5, 9, 6]       # how far each column of icing drips down
    return img(lambda x, y: mul(ICING, 0.97) if y < drips[x] else mul((236, 214, 226), 0.95 + 0.05 * noise(x, y)))


def gumdrop(c):
    def f(x, y):
        if random.Random(x * 131 + y * 17).random() < 0.07: return (255, 255, 255)   # a few sugar sparkles
        shade = 1.08 - 0.2 * (y / 15) + 0.05 * noise(x, y)
        return mul(c, shade)
    return img(f)


def chocolate(c):
    def f(x, y):
        lx, ly = x % 8, y % 8
        if lx == 7 or ly == 7: return mul(c, 0.7)                  # grooves between the squares
        if lx == 0 or ly == 0: return mul(c, 1.18)                 # bevel highlight
        return mul(c, 1.0 - 0.04 * noise(x, y))
    return img(f)


def fudge_bricks():
    def f(x, y):
        row = y // 4
        off = 4 if row % 2 else 0
        if y % 4 == 3 or (x + off) % 8 == 7: return (176, 134, 96)   # mortar
        return mul((92, 52, 30), 0.9 + 0.15 * noise(x, y, 2))
    return img(f)


def cookie_tile():
    chips = {(4, 4), (11, 3), (7, 8), (3, 11), (12, 11), (9, 13), (5, 7)}
    def f(x, y):
        if x in (0, 15) or y in (0, 15): return (150, 104, 56)      # baked edge of the tile
        if (x, y) in chips or (x - 1, y) in chips: return (70, 40, 22)
        return mul((222, 176, 110), 0.93 + 0.1 * noise(x, y, 4))
    return img(f)


BLOCKS = [   # id, name, textures (all faces, or dict up/side/down), sound, recipe ingredients, count
    ('candy_cane_block', 'Candy Cane Block', stripes(RED, WHITE), 'stone', ['sugar', 'sugar', 'sugar', 'red_dye', 'white_dye'], 8),
    ('mint_candy_block', 'Mint Candy Cane Block', stripes(MINT, WHITE), 'stone', ['sugar', 'sugar', 'sugar', 'green_dye', 'white_dye'], 8),
    ('peppermint_block', 'Peppermint Block', peppermint(), 'stone', ['sugar', 'sugar', 'red_dye', 'snowball'], 8),
    ('gingerbread_block', 'Gingerbread Block', gingerbread(), 'wood', ['wheat', 'wheat', 'wheat', 'sugar', 'cocoa_beans'], 8),
    ('iced_gingerbread_block', 'Iced Gingerbread Block', iced_gingerbread(), 'wood', ['wheat', 'wheat', 'sugar', 'cocoa_beans', 'snowball'], 8),
    ('icing_block', 'Icing Block', {'up': icing_top(), 'side': icing_side(), 'down': gingerbread()}, 'snow', ['sugar', 'sugar', 'sugar', 'snowball', 'snowball'], 8),
    ('gumdrop_block_red', 'Red Gumdrop Block', gumdrop((210, 32, 44)), 'slime', ['sugar', 'slime_ball', 'red_dye'], 8),
    ('gumdrop_block_green', 'Green Gumdrop Block', gumdrop((44, 176, 70)), 'slime', ['sugar', 'slime_ball', 'green_dye'], 8),
    ('gumdrop_block_yellow', 'Yellow Gumdrop Block', gumdrop((240, 200, 40)), 'slime', ['sugar', 'slime_ball', 'yellow_dye'], 8),
    ('gumdrop_block_purple', 'Purple Gumdrop Block', gumdrop((140, 60, 190)), 'slime', ['sugar', 'slime_ball', 'purple_dye'], 8),
    ('chocolate_block', 'Chocolate Block', chocolate((104, 58, 32)), 'wood', ['cocoa_beans', 'cocoa_beans', 'cocoa_beans', 'sugar'], 8),
    ('white_chocolate_block', 'White Chocolate Block', chocolate((236, 222, 192)), 'wood', ['cocoa_beans', 'sugar', 'sugar', 'white_dye'], 8),
    ('fudge_bricks', 'Fudge Bricks', fudge_bricks(), 'stone', ['cocoa_beans', 'cocoa_beans', 'sugar', 'brick'], 8),
    ('cookie_tile', 'Cookie Tiles', cookie_tile(), 'wood', ['cookie', 'cookie', 'cookie', 'cookie'], 8),
]


# ---------------------------------------------------------------- the Christmas light path
BULBS = ['g_red', 'g_blue2', 'g_yellow', 'g_green2', 'g_red2', 'g_blue', 'g_yellow2', 'g_green']
# Edges are world directions. Block models are mirrored on x (model +x is world west), z is not.
EDGES = {'n': ('z', -1), 's': ('z', 1), 'e': ('x', -1), 'w': ('x', 1)}


PATH_VARIANTS = 4                                                   # random pebble / snow / crack layouts, one picked per block


def pebble(m, x, z, r, col, rnd):
    """A rounded-looking pebble: a flat base with a smaller cap on top, slightly off-centre."""
    d = r * rnd.uniform(0.6, 1.0)
    m.box(x - r, 13.6, z - d, x + r, 13.6 + r * 0.35 + 0.1, z + d, col)
    ox, oz = rnd.uniform(-0.2, 0.2) * r, rnd.uniform(-0.2, 0.2) * r
    m.box(x - r * 0.65 + ox, 13.6, z - d * 0.65 + oz, x + r * 0.65 + ox, 13.6 + r * 0.6 + 0.12, z + d * 0.65 + oz, col)


def light_path_model():
    m = D.Model()
    m.box(-8, 0, -8, 8, 13.6, 8, 'stone')                           # flat stone walkway slab
    clamp = lambda v, r: max(-7.8 + r, min(7.8 - r, v))
    for v in range(PATH_VARIANTS):
        m.use('v%d' % v)
        rnd = random.Random(100 + v)
        jx, jz = rnd.uniform(-3, 3), rnd.uniform(-3, 3)               # joints split the top into uneven flagstones
        m.box(jx - 0.12, 13.6, -8, jx + 0.12, 13.63, 8, 'gray')
        m.box(-8, 13.6, jz - 0.12, jx, 13.63, jz + 0.12, 'gray')
        jz2 = rnd.uniform(-3, 3)
        m.box(jx, 13.6, jz2 - 0.12, 8, 13.63, jz2 + 0.12, 'gray')
        x, z = rnd.uniform(-5, 5), rnd.uniform(-5, 5)                 # a hairline crack
        for j in range(rnd.randint(2, 4)):
            L = rnd.uniform(0.7, 1.6) * rnd.choice((-1, 1))
            if j % 2: m.box(x, 13.6, min(z, z + L), x + 0.15, 13.62, max(z, z + L), 'dark_gray'); z += L
            else: m.box(min(x, x + L), 13.6, z, max(x, x + L), 13.62, z + 0.15, 'dark_gray'); x += L
        for _ in range(rnd.randint(8, 13)):                           # pebbles: random spots, mostly small, a few semi-big
            r = rnd.choice([0.2, 0.25, 0.3, 0.3, 0.4, 0.4, 0.5, 0.6, 0.75, 0.9])
            pebble(m, clamp(rnd.uniform(-7, 7), r), clamp(rnd.uniform(-7, 7), r), r,
                   rnd.choice(['gray', 'gray', 'dark_gray', 'slate', 'silver', 'tan']), rnd)
        for _ in range(rnd.randint(3, 5)):                            # snow splatters: a clump and flecks thrown around it
            w, d = rnd.uniform(0.5, 1.6), rnd.uniform(0.4, 1.3)
            x, z = clamp(rnd.uniform(-7, 7), w), clamp(rnd.uniform(-7, 7), d)
            m.box(x - w, 13.6, z - d, x + w, 13.6 + rnd.uniform(0.12, 0.3), z + d, 'snow')
            m.box(x - w * 0.6 + 0.3, 13.6, z - d - 0.35, x + w * 0.5, 13.7, z + d + 0.3, 'snow')   # softens the clump outline
            for _ in range(rnd.randint(2, 4)):
                fr = rnd.uniform(0.12, 0.35)
                fx, fz = clamp(x + rnd.uniform(-2.5, 2.5), fr), clamp(z + rnd.uniform(-2.5, 2.5), fr)
                m.box(fx - fr, 13.6, fz - fr, fx + fr, 13.68, fz + fr, 'white')
    for k, (edge, (axis, side)) in enumerate(EDGES.items()):         # C9-style bulbs on a wire that wanders a little
        m.use('l' + edge)
        rnd = random.Random(10 + k)
        c = 7.0 * side
        def put(t, cc, y0, y1, h, col):
            m.box(*((t - h, y0, cc - h, t + h, y1, cc + h) if axis == 'z' else (cc - h, y0, t - h, cc + h, y1, t + h)), col)
        pts = [(-8, 0.0)] + [(t, rnd.uniform(-0.3, 0.3)) for t in (-4, 0, 4)] + [(8, 0.0)]
        for (t0, o0), (t1, o1) in zip(pts, pts[1:]):
            cc = c + (o0 + o1) / 2
            m.box(*((t0, 13.6, cc - 0.1, t1, 13.75, cc + 0.1) if axis == 'z' else (cc - 0.1, 13.6, t0, cc + 0.1, 13.75, t1)), 'dark_green')
        cols = [rnd.choice([g, g + '2']) for g in rnd.sample(['g_red', 'g_blue', 'g_yellow', 'g_green'], 4)]   # all four colours, random order
        for j, t in enumerate((-5.6, -2.0, 2.0, 5.6)):
            t += rnd.uniform(-0.6, 0.6)
            cc = c + pts[1 + (t > -2) + (t > 2)][1] * 0.5                 # roughly on the wire
            put(t, cc, 13.6, 14.15, 0.22, 'dark_green')                       # socket
            for y0, y1, h in ((14.15, 14.4, 0.24), (14.4, 14.95, 0.33), (14.95, 15.3, 0.25), (15.3, 15.5, 0.12)):
                put(t, cc, y0, y1, h, cols[j])                                # teardrop bulb
    m.use('root')
    return m


def main():
    os.makedirs(TEX, exist_ok=True)
    tt_path = os.path.join(RP, 'textures', 'terrain_texture.json')
    tt = json.load(open(tt_path))
    lang, sounds = [], {}
    for ident, name, tex, sound, recipe, count in BLOCKS:
        faces = tex if isinstance(tex, dict) else {'all': tex}
        mats = {}
        for face, im in faces.items():
            key = 'santa_%s%s' % (ident, '' if face == 'all' else '_' + face)
            im.save(os.path.join(TEX, key[6:] + '.png'))
            tt['texture_data'][key] = {'textures': 'textures/blocks/' + key[6:]}
            for f in (['*'] if face == 'all' else ['up'] if face == 'up' else ['down'] if face == 'down' else ['*']):
                mats[f] = {'texture': key, 'render_method': 'opaque'}
        block = {'format_version': '1.21.40', 'minecraft:block': {
            'description': {'identifier': 'santa:' + ident, 'menu_category': {'category': 'construction'}},
            'components': {'minecraft:geometry': 'minecraft:geometry.full_block', 'minecraft:material_instances': mats,
                           'minecraft:destructible_by_mining': {'seconds_to_destroy': 0.8},
                           'minecraft:destructible_by_explosion': {'explosion_resistance': 3}}}}
        D.dump(os.path.join(BP, 'blocks', ident + '.json'), block)
        D.dump(os.path.join(BP, 'recipes', ident + '.json'), {'format_version': '1.20.10', 'minecraft:recipe_shapeless': {
            'description': {'identifier': 'santa:%s_recipe' % ident}, 'tags': ['santa_bench'], 'unlock': [{'item': 'santa:workbench'}],
            'ingredients': [{'item': 'minecraft:' + i} for i in recipe], 'result': {'item': 'santa:' + ident, 'count': count}}})
        lang.append('tile.santa:%s.name=%s (Workshop Block)' % (ident, name))
        sounds['santa:' + ident] = {'sound': sound}

    # light path: model with one bone of bulbs per edge, edge states set by the script
    m = light_path_model()
    D.dump(os.path.join(RP, 'models', 'blocks', 'light_path.geo.json'), D.geo_json('geometry.santa_light_path', m.cubes, m.bones))
    edges = ['santa:' + e for e in EDGES]
    states = {e: [1, 0] for e in edges}                              # 1 = lights on that edge (default: a lone tile is lit all round)
    states['santa:v'] = list(range(PATH_VARIANTS))                    # which random pebble/snow layout (picked by the script)
    vis = {'l' + e[6:]: "q.block_state('%s') == 1" % e for e in edges}
    vis.update({'v%d' % v: "q.block_state('santa:v') == %d" % v for v in range(PATH_VARIANTS)})
    lit = D.materials({'glow'}, True)
    block = {'format_version': '1.21.40', 'minecraft:block': {
        'description': {'identifier': 'santa:light_path', 'menu_category': {'category': 'construction'}, 'states': states},
        'components': {
            'minecraft:geometry': {'identifier': 'geometry.santa_light_path', 'bone_visibility': vis},
            'minecraft:material_instances': lit,
            'minecraft:collision_box': {'origin': [-8, 0, -8], 'size': [16, 14, 16]},
            'minecraft:selection_box': {'origin': [-8, 0, -8], 'size': [16, 14, 16]},
            'minecraft:destructible_by_mining': {'seconds_to_destroy': 0.6},
            'minecraft:light_emission': 11,
            'minecraft:custom_components': ['santa:light_path']},
        'permutations': [{'condition': ' && '.join("q.block_state('%s') == 0" % e for e in edges),
                          'components': {'minecraft:light_emission': 0}}]}}            # a middle tile has no bulbs, so no glow
    D.dump(os.path.join(BP, 'blocks', 'light_path.json'), block)
    D.dump(os.path.join(BP, 'recipes', 'light_path.json'), {'format_version': '1.20.10', 'minecraft:recipe_shapeless': {
        'description': {'identifier': 'santa:light_path_recipe'}, 'tags': ['santa_bench'], 'unlock': [{'item': 'santa:workbench'}],
        'ingredients': [{'item': 'minecraft:' + i} for i in ['cobblestone', 'cobblestone', 'cobblestone', 'glowstone_dust', 'string']],
        'result': {'item': 'santa:light_path', 'count': 8}}})
    lang.append('tile.santa:light_path.name=Christmas Light Path (Workshop Block)')
    sounds['santa:light_path'] = {'sound': 'stone'}

    D.dump(tt_path, tt)
    bj = os.path.join(RP, 'blocks.json')
    data = json.load(open(bj)) if os.path.exists(bj) else {'format_version': '1.21.40'}
    data.update(sounds)
    D.dump(bj, data)
    lp = os.path.join(RP, 'texts', 'en_US.lang')
    ours = {l.split('=')[0] for l in lang}
    old = [l for l in open(lp).read().splitlines() if l.split('=')[0] not in ours]
    open(lp, 'w').write('\n'.join(old + lang) + '\n')
    print('built %d candy blocks + light path' % len(BLOCKS))


if __name__ == '__main__':
    main()
