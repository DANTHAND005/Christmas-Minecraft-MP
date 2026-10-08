#!/usr/bin/env python3
"""Christmas building blocks for Santa's Workbench: candy blocks (full cubes with their own textures).

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

    D.dump(tt_path, tt)
    bj = os.path.join(RP, 'blocks.json')
    data = json.load(open(bj)) if os.path.exists(bj) else {'format_version': '1.21.40'}
    data.update(sounds)
    D.dump(bj, data)
    lp = os.path.join(RP, 'texts', 'en_US.lang')
    ours = {l.split('=')[0] for l in lang}
    old = [l for l in open(lp).read().splitlines() if l.split('=')[0] not in ours]
    open(lp, 'w').write('\n'.join(old + lang) + '\n')
    print('built %d candy blocks' % len(BLOCKS))


if __name__ == '__main__':
    main()
