#!/usr/bin/env python3
"""Sanity-check both add-ons: every obtainable block/item has a recipe and a name, every recipe points at
real things, and every model / texture / loot table / script id that is referenced exists.

    python3 tools/check_packs.py        # prints problems, exit code 1 if any
"""
import glob, json, os, re, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
PACKS = {'santa': 'SantasWorkbench', 'xmas': 'GingerbreadOven'}
problems = []


def load(p):
    try:
        return json.load(open(p))
    except Exception as e:
        problems.append('bad json %s: %s' % (p, e))
        return {}


def walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)


blocks, items, geos, terrain, itemtex, lang, loot = {}, {}, set(), set(), set(), set(), set()
recipes, stations = [], {'crafting_table', 'furnace', 'smoker', 'campfire', 'soul_campfire', 'blast_furnace', 'stonecutter', 'smithing_table'}
for pack in PACKS.values():
    for bp in glob.glob(os.path.join(ROOT, pack, '*_BP')):
        for f in glob.glob(bp + '/blocks/*.json'):
            b = load(f).get('minecraft:block', {})
            ident = b.get('description', {}).get('identifier')
            blocks[ident] = (f, b)
            for c in walk(b):
                if 'minecraft:crafting_table' in c:
                    stations.update(c['minecraft:crafting_table'].get('crafting_tags', []))
        for f in glob.glob(bp + '/items/*.json'):
            it = load(f).get('minecraft:item', {})
            items[it.get('description', {}).get('identifier')] = (f, it)
        for f in glob.glob(bp + '/recipes/*.json'):
            recipes.append((f, load(f)))
        loot.update(os.path.relpath(f, bp) for f in glob.glob(bp + '/loot_tables/**/*.json', recursive=True))
    for rp in glob.glob(os.path.join(ROOT, pack, '*_RP')):
        for f in glob.glob(rp + '/models/**/*.json', recursive=True):
            for g in load(f).get('minecraft:geometry', []):
                geos.add(g['description']['identifier'])
        for name, store in (('terrain_texture.json', terrain), ('item_texture.json', itemtex)):
            p = os.path.join(rp, 'textures', name)
            if os.path.exists(p):
                for k, v in load(p).get('texture_data', {}).items():
                    store.add(k)
                    for t in (v['textures'] if isinstance(v['textures'], list) else [v['textures']]):
                        t = t['path'] if isinstance(t, dict) else t
                        if not glob.glob(os.path.join(rp, t) + '.*'):
                            problems.append('%s: texture %s -> missing file %s' % (name, k, t))
        for f in glob.glob(rp + '/texts/*.lang'):
            lang.update(l.split('=')[0].strip() for l in open(f, encoding='utf-8') if '=' in l)

# ---- blocks: model, textures, loot, name
for ident, (f, b) in blocks.items():
    comp = b.get('components', {})
    for c in [comp] + [p.get('components', {}) for p in b.get('permutations', [])]:
        g = c.get('minecraft:geometry')
        gid = g.get('identifier') if isinstance(g, dict) else g
        if gid and not gid.startswith('minecraft:geometry.') and gid not in geos:
            problems.append('%s: geometry %s not found' % (ident, gid))
        for k, mi in (c.get('minecraft:material_instances') or {}).items():
            if mi.get('texture') and mi['texture'] not in terrain:
                problems.append('%s: material %s uses unknown texture %s' % (ident, k, mi['texture']))
        lt = c.get('minecraft:loot')
        if lt and lt not in loot:
            problems.append('%s: loot table %s missing' % (ident, lt))
    hidden = b.get('description', {}).get('menu_category', {}).get('category') == 'none'
    if not hidden and 'tile.%s.name' % ident not in lang:
        problems.append('%s: no name in en_US.lang' % ident)
    bones = set()
    if isinstance(comp.get('minecraft:geometry'), dict):
        bones = set(comp['minecraft:geometry'].get('bone_visibility', {}))
    for k, vals in b.get('description', {}).get('states', {}).items():
        if isinstance(vals, list) and len(vals) > 16:
            problems.append('%s: state %s has %d values (max 16)' % (ident, k, len(vals)))

# ---- items: icon + name
for ident, (f, it) in items.items():
    comp = it.get('components', {})
    icon = comp.get('minecraft:icon')
    icon = icon.get('textures', {}).get('default') if isinstance(icon, dict) and 'textures' in icon else icon.get('texture') if isinstance(icon, dict) else icon
    if icon and icon not in itemtex:
        problems.append('%s: icon %s not in item_texture.json' % (ident, icon))
    if 'item.%s' % ident not in lang and 'item.%s.name' % ident not in lang and 'minecraft:display_name' not in comp:
        problems.append('%s: no name in en_US.lang' % ident)
    bp = comp.get('minecraft:block_placer', {}).get('block')
    if bp and bp not in blocks:
        problems.append('%s: places unknown block %s' % (ident, bp))

# ---- recipes: results, ingredients, stations, duplicates
made, seen_ids, combos = set(), {}, {}
custom = set(blocks) | set(items)
for f, r in recipes:
    for kind, body in r.items():
        if not kind.startswith('minecraft:recipe'):
            continue
        rid = body.get('description', {}).get('identifier')
        if rid in seen_ids:
            problems.append('duplicate recipe id %s (%s, %s)' % (rid, seen_ids[rid], f))
        seen_ids[rid] = f
        res = body.get('result') or body.get('output')
        for x in (res if isinstance(res, list) else [res]):
            rid_item = x.get('item') if isinstance(x, dict) else x
            if rid_item:
                made.add(rid_item)
                if rid_item.split(':')[0] in PACKS and rid_item not in custom:
                    problems.append('%s: result %s does not exist' % (os.path.basename(f), rid_item))
        ings = body.get('ingredients') or list((body.get('key') or {}).values()) + ([body['input']] if 'input' in body else [])
        names = []
        for x in ings:
            n = x.get('item') if isinstance(x, dict) else x
            if n:
                names.append(n)
                if n.split(':')[0] in PACKS and n not in custom:
                    problems.append('%s: ingredient %s does not exist' % (os.path.basename(f), n))
        for t in body.get('tags', []):
            if t not in stations:
                problems.append('%s: crafting tag %s has no station' % (os.path.basename(f), t))
        if kind == 'minecraft:recipe_shapeless':
            key = (tuple(body.get('tags', [])), tuple(sorted(names)))
            if key in combos:
                problems.append('same ingredients in %s and %s' % (combos[key], os.path.basename(f)))
            combos[key] = os.path.basename(f)

SCRIPT_MADE = re.compile(r'santa:gift_(?!box)')   # wrapped gifts come from filling a Gift Box, not from a recipe
obtainable = [i for i, (f, b) in blocks.items() if b.get('description', {}).get('menu_category', {}).get('category') != 'none'] + list(items)
for ident in sorted(obtainable):
    if ident not in made and not SCRIPT_MADE.match(ident) and not (ident in blocks and any(i.get('minecraft:block_placer', {}).get('block') == ident for _, i in [items[k] for k in items]
                                                       for i in [i.get('components', {})])):
        problems.append('%s: no crafting recipe' % ident)

# ---- scripts: every quoted santa:/xmas: id exists (ignores component names and prefixes)
registered = set()
for pack in PACKS.values():
    for js in glob.glob(os.path.join(ROOT, pack, '*_BP', 'scripts', '*.js')):
        registered.update(re.findall(r'registerCustomComponent\("([^"]+)"', open(js).read()))
for pack in PACKS.values():
    for js in glob.glob(os.path.join(ROOT, pack, '*_BP', 'scripts', '*.js')):
        src = open(js).read()
        for ns, name in set(re.findall(r'"(santa|xmas):([a-z0-9_]+)"', src)):
            ident = ns + ':' + name
            if ident not in custom and ident not in registered and not ident.endswith('_') and \
                    not any(c.startswith(ident + '_') for c in custom) and \
                    not re.fullmatch(r'(santa|xmas):(on|frame|open|day_a|day_b|fill|[habf]\d?|[nsew]|cut|slices|steam|level|kind|bites)', ident):
                problems.append('%s: script mentions %s, which is not a block or item' % (os.path.basename(js), ident))
for ident, (f, b) in blocks.items():
    for c in walk(b):
        for cc in c.get('minecraft:custom_components', []) if isinstance(c.get('minecraft:custom_components'), list) else []:
            if cc not in registered:
                problems.append('%s: custom component %s is never registered by a script' % (ident, cc))
        if 'santa:idle' in (c.get('minecraft:custom_components') or []) and 'minecraft:tick' not in c:
            problems.append('%s: santa:idle without minecraft:tick' % ident)

total = 0                                         # Minecraft slows down past 65536 block permutations
for ident, (f, b) in blocks.items():
    d = b.get('description', {})
    n = 1
    for v in d.get('states', {}).values():
        n *= len(v) if isinstance(v, list) else 1
    pd = d.get('traits', {}).get('minecraft:placement_direction', {}).get('enabled_states', [])
    n *= 4 if 'minecraft:cardinal_direction' in pd else 1
    total += n
if total > 65536:
    problems.append('%d block permutations (Minecraft warns above 65536)' % total)
print('%d blocks, %d items, %d recipes checked, %d block permutations' % (len(blocks), len(items), len(recipes), total))
for p in problems:
    print(' -', p)
print('OK' if not problems else '%d problem(s)' % len(problems))
sys.exit(1 if problems else 0)
