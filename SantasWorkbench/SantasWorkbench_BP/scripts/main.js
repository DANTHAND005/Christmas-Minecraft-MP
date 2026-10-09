import { world, system, ItemStack, BlockPermutation, EquipmentSlot } from "@minecraft/server";
import { ActionFormData, ModalFormData } from "@minecraft/server-ui";
import { NEW_DECOR, NEW_PARTS } from "./decor_config.js";

const TOYS = ["santa:teddy_bear", "santa:toy_train", "santa:toy_soldier", "santa:spinning_top", "santa:rubber_duck", "santa:yo_yo", "santa:rocking_horse", "santa:jack_in_the_box", "santa:nutcracker", "santa:toy_drum", "santa:toy_robot", "santa:snow_globe", "santa:toy_airplane", "santa:toy_penguin", "santa:toy_car", "santa:toy_sled", "santa:stuffed_reindeer", "santa:toy_snowman", "santa:wooden_blocks", "santa:toy_castle"];
// Every present gives one toy and one food. With the Gingerbread Oven add-on on, the food can be any of its foods:
// a food group is picked first (so 30 cookie kinds don't crowd out the rest), then any item in it.
const C = ["chocolate_chip", "gingerbread", "peppermint_chocolate", "snickerdoodle", "sugar"];
const S = ["", "_gingerbread_man", "_heart", "_snowflake", "_star", "_tree"];
const OVEN_FOOD = [
  { n: 3, ids: C.flatMap((c) => S.map((s) => "xmas:cookie_" + c + s)) },
  { n: 2, ids: ["xmas:candy_cane", "xmas:chocolate_bar", "xmas:chocolate_coins", "xmas:fudge", "xmas:lollipop", "xmas:marshmallow",
                "xmas:peppermint_candy", "xmas:toffee", "xmas:gumdrop_red", "xmas:gumdrop_green", "xmas:gumdrop_blue",
                "xmas:gumdrop_yellow", "xmas:gumdrop_purple"] },
  { n: 1, ids: ["xmas:hot_cocoa", "xmas:hot_cocoa_marshmallow", "xmas:eggnog"] },
  { n: 1, ids: ["xmas:ice_cream_vanilla", "xmas:ice_cream_chocolate", "xmas:ice_cream_peppermint", "xmas:ice_cream_strawberry",
                "xmas:ice_cream_gingerbread", "xmas:ice_cream_candy_cane_crunch", "xmas:ice_cream_matcha"] },
  { n: 1, ids: ["xmas:christmas_pudding", "xmas:pumpkin_pie_slice", "xmas:apple_pie_slice", "xmas:cinnamon_bun", "xmas:yule_log"] },
  { n: 1, ids: ["xmas:red_velvet_cake", "xmas:carrot_cake", "xmas:fruitcake", "xmas:peppermint_chocolate_cake", "xmas:pumpkin_pie",
                "xmas:apple_pie", "xmas:big_christmas_pudding", "xmas:cinnamon_bun_tray"] },
];
const PLAIN_FOOD = [["minecraft:cookie", 3], ["minecraft:pumpkin_pie", 1], ["minecraft:sweet_berries", 4], ["minecraft:cake", 1], ["minecraft:golden_apple", 1]];
const any = (list) => list[Math.floor(Math.random() * list.length)];
function makeStack(id, n) { try { return new ItemStack(id, n); } catch (e) { return undefined; } }   // unknown item = that add-on is off
function pickFood() {
  const g = any(OVEN_FOOD);
  return makeStack(any(g.ids), g.n) || makeStack(...any(PLAIN_FOOD));   // falls back to vanilla food without the oven pack
}
function pickGifts() { return [makeStack(any(TOYS), 1), pickFood()].filter(Boolean); }
// ---- toy animations: right-click steps the block through its frames ----
const TOY_ANIM = {"teddy_bear": {"seq": [1, 0, 1, 0], "delay": 4, "sound": "note.harp"}, "toy_train": {"seq": [1, 0, 1, 0, 1, 0, 1, 0, 1, 0], "delay": 2, "sound": "note.flute", "particle": "minecraft:campfire_smoke_particle"}, "toy_soldier": {"seq": [1, 1, 1, 1, 0], "delay": 4, "sound": "note.snare"}, "spinning_top": {"seq": [1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2], "delay": 1, "sound": "random.click"}, "rubber_duck": {"seq": [1, 0], "delay": 3, "sound": "mob.bat.idle"}, "yo_yo": {"seq": [1, 2, 1, 0, 1, 2, 1, 0], "delay": 2, "sound": "random.click"}, "rocking_horse": {"seq": [1, 0, 2, 0, 1, 0, 2, 0, 1, 0, 2, 0], "delay": 3, "sound": "mob.horse.gallop"}, "jack_in_the_box": {"open": [1, 2, 3, 2], "close": [1, 0], "delay": 2, "sound": "random.pop"}, "nutcracker": {"seq": [1, 0, 1, 0, 1, 0], "delay": 3, "sound": "random.click", "every": true}, "toy_drum": {"seq": [1, 2, 1, 2, 1, 2, 1, 2, 0], "delay": 2, "sound": "note.bd", "every": true}, "toy_robot": {"seq": [1, 2, 1, 2, 0], "delay": 3, "sound": "note.bit", "every": true}, "snow_globe": {"seq": [1, 2, 3, 1, 2, 3, 0], "delay": 4, "sound": "note.chime"}, "toy_airplane": {"seq": [1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 0], "delay": 1, "sound": "random.click"}, "toy_penguin": {"seq": [1, 0, 1, 0, 1, 0, 1, 0], "delay": 2, "sound": "note.xylophone"}};
const busy = new Set();
function playToy(block, dimension) {
  const anim = TOY_ANIM[block.typeId.slice("santa:".length)];
  if (!anim) return;
  const loc = { x: block.x, y: block.y, z: block.z }, key = dimension.id + loc.x + "," + loc.y + "," + loc.z, type = block.typeId;
  if (busy.has(key)) return;
  const center = { x: loc.x + 0.5, y: loc.y + 0.5, z: loc.z + 0.5 };
  const seq = anim.seq || (block.permutation.getState("santa:frame") === 0 ? anim.open : anim.close);
  busy.add(key);
  const sound = () => { try { dimension.playSound(anim.sound, center, { volume: 0.6 }); } catch (e) {} };
  sound();
  if (anim.particle) { try { dimension.spawnParticle(anim.particle, { x: center.x, y: center.y + 0.6, z: center.z }); } catch (e) {} }
  const step = (i) => {
    try {
      const b = dimension.getBlock(loc);
      if (!b || b.typeId !== type || i >= seq.length) { busy.delete(key); return; }
      b.setPermutation(b.permutation.withState("santa:frame", seq[i]));
      if (anim.every && i > 0) sound();
      system.runTimeout(() => step(i + 1), anim.delay);
    } catch (e) { busy.delete(key); console.warn("santa toy error: " + e); }
  };
  step(0);
}

// ---- gift boxes: fill with your own items, wrap, give; the placed present opens to those items ----
const GIFTS = [["santa:gift_green", "santa:present", "Green"], ["santa:gift_red", "santa:present_red", "Red"], ["santa:gift_cyan", "santa:present_cyan", "Cyan"], ["santa:gift_blue", "santa:present_blue", "Snowy Blue"], ["santa:gift_purple", "santa:present_purple", "Purple"], ["santa:gift_candy", "santa:present_candy", "Candy Cane"], ["santa:gift_gold", "santa:present_gold", "Gold"], ["santa:gift_pink", "santa:present_pink", "Polka Dot"], ["santa:gift_orange", "santa:present_orange", "Orange"], ["santa:gift_silver", "santa:present_silver", "Silver"]];   // [wrapped gift item, present block, colour name]
const GIFT_MAX = 9;
const giftKey = (dim, l) => "gift:" + dim.id + ":" + l.x + "," + l.y + "," + l.z;
function readGift(stack) { try { return JSON.parse(stack.getDynamicProperty("gift") || "null"); } catch (e) { return null; } }
function stackName(s) { return { rawtext: [{ translate: s.localizationKey }, { text: " x" + s.amount }] }; }
function giveItem(player, id, n) {
  const inv = player.getComponent("minecraft:inventory").container;
  while (n > 0) { const k = Math.min(n, 64); const st = new ItemStack(id, k); const left = inv.addItem(st); if (left) player.dimension.spawnItem(left, player.location); n -= k; }
}
function heldBox(player) {
  const inv = player.getComponent("minecraft:inventory").container, slot = player.selectedSlotIndex, it = inv.getItem(slot);
  return it && it.typeId === "santa:gift_box" ? { inv, slot, it } : null;
}
function saveBox(h, data) { h.it.setDynamicProperty("gift", JSON.stringify(data)); h.it.setLore(data.items.map((e) => e.n + " x " + e.id.replace(/^.*:/, "").replace(/_/g, " "))); h.inv.setItem(h.slot, h.it); }
function boxMenu(player) {
  const h = heldBox(player); if (!h) return;
  const data = readGift(h.it) || { items: [] };
  const form = new ActionFormData().title("Gift Box").body(data.items.length + " / " + GIFT_MAX + " stacks inside. Enchantments and custom names are not kept.")
    .button("Put something in").button("Take something out").button("Wrap it up");
  form.show(player).then((r) => {
    if (r.canceled) return;
    if (r.selection === 0) addMenu(player); else if (r.selection === 1) takeMenu(player); else wrapMenu(player);
  }).catch((e) => console.warn("gift box menu: " + e));
}
function addMenu(player) {
  const h = heldBox(player); if (!h) return;
  const data = readGift(h.it) || { items: [] };
  if (data.items.length >= GIFT_MAX) { player.onScreenDisplay.setActionBar("The gift box is full"); return; }
  const slots = [];
  for (let i = 0; i < h.inv.size; i++) {
    const s = h.inv.getItem(i);
    if (s && i !== h.slot && s.typeId !== "santa:gift_box" && !s.typeId.startsWith("santa:gift_")) slots.push(i);
  }
  if (!slots.length) { player.onScreenDisplay.setActionBar("Nothing to put in"); return; }
  const form = new ActionFormData().title("Put in the gift box");
  for (const i of slots) form.button(stackName(h.inv.getItem(i)));
  form.show(player).then((r) => {
    if (r.canceled || r.selection === undefined) return;
    const h2 = heldBox(player); if (!h2) return;
    const d = readGift(h2.it) || { items: [] }, i = slots[r.selection], s = h2.inv.getItem(i);
    if (!s || d.items.length >= GIFT_MAX) return;
    d.items.push({ id: s.typeId, n: s.amount }); h2.inv.setItem(i, undefined); saveBox(h2, d);
    boxMenu(player);
  }).catch((e) => console.warn("gift add menu: " + e));
}
function takeMenu(player) {
  const h = heldBox(player); if (!h) return;
  const data = readGift(h.it) || { items: [] };
  if (!data.items.length) { player.onScreenDisplay.setActionBar("The gift box is empty"); return; }
  const form = new ActionFormData().title("Take out");
  for (const e of data.items) { const st = makeStack(e.id, 1); form.button(st ? { rawtext: [{ translate: st.localizationKey }, { text: " x" + e.n }] } : e.id + " x" + e.n); }
  form.show(player).then((r) => {
    if (r.canceled || r.selection === undefined) return;
    const h2 = heldBox(player); if (!h2) return;
    const d = readGift(h2.it) || { items: [] }; const [e] = d.items.splice(r.selection, 1);
    if (!e) return;
    saveBox(h2, d); giveItem(player, e.id, e.n); boxMenu(player);
  }).catch((e) => console.warn("gift take menu: " + e));
}
function wrapMenu(player) {
  const h = heldBox(player); if (!h) return;
  const data = readGift(h.it) || { items: [] };
  if (!data.items.length) { player.onScreenDisplay.setActionBar("Put something in first"); return; }
  const form = new ModalFormData().title("Wrap the gift").dropdown("Wrapping paper", GIFTS.map((g) => g[2])).textField("To (optional)", "a friend's name");
  form.show(player).then((r) => {
    if (r.canceled || !r.formValues) return;
    const h2 = heldBox(player); if (!h2) return;
    const d = readGift(h2.it) || { items: [] }; if (!d.items.length) return;
    const to = String(r.formValues[1] || "").trim().slice(0, 30);
    const gift = new ItemStack(GIFTS[r.formValues[0]][0], 1);
    gift.setDynamicProperty("gift", JSON.stringify({ items: d.items, from: player.name, to }));
    gift.setLore([(to ? "To: " + to : "A present"), "From: " + player.name]);
    h2.inv.setItem(h2.slot, gift);
    try { player.dimension.playSound("random.orb", player.location); } catch (e) {}
    player.onScreenDisplay.setActionBar("Wrapped! Place it down to give it.");
  }).catch((e) => console.warn("gift wrap menu: " + e));
}
// placing a wrapped gift: remember what was in hand (before), then attach it to the placed present (after)
const pendingGift = new Map();
world.beforeEvents.playerInteractWithBlock.subscribe((e) => {
  if (e.itemStack && e.itemStack.typeId.startsWith("santa:gift_")) { const g = readGift(e.itemStack); if (g) pendingGift.set(e.player.id, g); }
});
world.afterEvents.playerPlaceBlock.subscribe((e) => {
  const g = pendingGift.get(e.player.id); pendingGift.delete(e.player.id);
  if (g && e.block.typeId.startsWith("santa:present")) world.setDynamicProperty(giftKey(e.dimension, e.block), JSON.stringify(g));
});
function takeGiftData(dimension, loc) {
  const k = giftKey(dimension, loc); let g = null;
  try { g = JSON.parse(world.getDynamicProperty(k) || "null"); } catch (e) {}
  world.setDynamicProperty(k, undefined); return g;
}

// ---- decorations: right-click switches lights on/off (with a flicker) or rings the bells; the reindeer grazes now and then ----
const DECOR = {"christmas_tree": {"toggle": true, "flicker": true, "sound": "random.click"}, "christmas_tree_medium": {"toggle": true, "flicker": true, "sound": "random.click"}, "tall_christmas_tree": {"toggle": true, "flicker": true, "sound": "random.click"}, "string_lights_multi": {"toggle": true, "flicker": true, "sound": "random.click"}, "string_lights_warm": {"toggle": true, "flicker": true, "sound": "random.click"}, "string_lights_redgreen": {"toggle": true, "flicker": true, "sound": "random.click"}, "candy_cane_lamp": {"toggle": true, "flicker": true, "sound": "random.click"}, "christmas_candles": {"toggle": true, "sound_on": "fire.ignite", "sound_off": "random.fizz"}, "golden_bells": {"anim": [1, 2, 1, 2, 1, 0], "delay": 2, "sound": "block.bell.hit", "every": 2}, "lawn_reindeer": {"toggle": true, "flicker": true, "sound": "random.click", "idle": [2, 1, 1, 1, 2, 0], "idle_delay": 6}};
Object.assign(DECOR, NEW_DECOR);
const decorBusy = new Set();
// ---- big decorations are a base block plus _partN blocks; PARTS lists each part's [right, up, back] offset in blocks
const PARTS = {"santa:christmas_tree_medium": [[0, 1, 0]], "santa:tall_christmas_tree": [[0, 1, 0], [0, 2, 0]], "santa:candy_cane_lamp": [[0, 1, 0], [0, 2, 0]],
               "santa:giant_candy_cane": [[0, 1, 0], [0, 2, 0]], "santa:lawn_reindeer": [[0, 1, 0]]};
Object.assign(PARTS, NEW_PARTS);
const FRONT = { north: [0, -1], south: [0, 1], west: [-1, 0], east: [1, 0] };   // which way a placed block faces (towards the player)
function partPos(from, dir, o, sign = 1) {   // right = viewer's right looking at the front, back = away from the viewer
  const [fx, fz] = FRONT[dir] || FRONT.north;
  return { x: from.x + sign * (o[0] * fz - o[2] * fx), y: from.y + sign * o[1], z: from.z + sign * (-o[0] * fx - o[2] * fz) };
}
function splitId(id) { const m = id.match(/^(santa:.+)_part(\d+)$/); return m && PARTS[m[1]] ? [m[1], Number(m[2])] : [id, 0]; }
function stackOf(block) {
  const [id, n] = splitId(block.typeId), offs = PARTS[id];
  if (!offs) return [block];
  const dir = block.permutation.getState("minecraft:cardinal_direction");
  const base = n ? block.dimension.getBlock(partPos(block, dir, offs[n - 1], -1)) : block;
  if (!base || base.typeId !== id) return [block];
  const out = [base];
  offs.forEach((o, k) => { const b = base.dimension.getBlock(partPos(base, dir, o)); if (b && b.typeId === id + "_part" + (k + 1)) out.push(b); });
  return out;
}
function setStack(stack, state, value) { for (const b of stack) { try { b.setPermutation(b.permutation.withState(state, value)); } catch (e) {} } }
world.afterEvents.playerPlaceBlock.subscribe((e) => {
  const b = e.block, offs = PARTS[b.typeId];
  if (!offs) return;
  const dir = b.permutation.getState("minecraft:cardinal_direction");
  const spots = offs.map((o) => b.dimension.getBlock(partPos(b, dir, o)));
  if (spots.some((s) => !s || !s.isAir)) {
    const id = b.typeId; b.setType("minecraft:air");
    if (String(e.player.getGameMode()).toLowerCase() !== "creative") b.dimension.spawnItem(new ItemStack(id, 1), b.center());
    const tall = offs.every((o) => !o[0] && !o[2]);
    e.player.onScreenDisplay.setActionBar(tall ? "This needs " + (offs.length + 1) + " blocks of empty space above the ground" : "Not enough empty space here for this decoration");
    return;
  }
  spots.forEach((s, k) => s.setPermutation(BlockPermutation.resolve(b.typeId + "_part" + (k + 1), { "minecraft:cardinal_direction": dir })));
});
function breakStack(event) {   // breaking any piece removes the whole decoration (the base drops it once)
  const { block, dimension, brokenBlockPermutation, player } = event;
  const [id, n] = splitId(brokenBlockPermutation.type.id), offs = PARTS[id];
  if (!offs) return;
  const dir = brokenBlockPermutation.getState("minecraft:cardinal_direction");
  const base = n ? partPos(block, dir, offs[n - 1], -1) : { x: block.x, y: block.y, z: block.z };
  const tc = DECOR[id.slice("santa:".length)];
  if (tc && tc.ambient) {   // forget the town's on/off switch and silence it
    world.setDynamicProperty(townKey(dimension, base), undefined);
    try { dimension.runCommand(`stopsound @a[x=${base.x},y=${base.y},z=${base.z},r=48] ${tc.ambient}`); } catch (e) {}
  }
  [[0, 0, 0], ...offs].forEach((o, k) => {
    const p = partPos(base, dir, o);
    if (p.x === block.x && p.y === block.y && p.z === block.z) return;
    const b = dimension.getBlock(p);
    if (b && b.typeId === (k ? id + "_part" + k : id)) b.setType("minecraft:air");
  });
  if (n && player && String(player.getGameMode()).toLowerCase() !== "creative") dimension.spawnItem(new ItemStack(id, 1), { x: base.x + 0.5, y: base.y + 0.5, z: base.z + 0.5 });
}
// towns: right-click toggles a looping animation + soundscape; off by default
const townKey = (dimension, l) => "town:" + dimension.id + ":" + l.x + "," + l.y + "," + l.z;
const townOn = (dimension, l) => world.getDynamicProperty(townKey(dimension, l)) === true;
function stepStates(block, dimension, state, seq, delay, onStep) {
  const stack = stackOf(block), base = stack[0];
  const loc = { x: base.x, y: base.y, z: base.z }, type = base.typeId, key = dimension.id + loc.x + "," + loc.y + "," + loc.z;
  if (decorBusy.has(key)) return;
  decorBusy.add(key);
  const step = (i) => {
    try {
      const b = dimension.getBlock(loc);
      if (!b || b.typeId !== type || i >= seq.length) { decorBusy.delete(key); return; }
      const tcfg = DECOR[type.slice("santa:".length)];
      if (tcfg && tcfg.ambient && !townOn(dimension, loc)) { decorBusy.delete(key); setStack(stackOf(b), state, 0); return; }
      setStack(stackOf(b), state, seq[i]);
      if (onStep) onStep(i);
      system.runTimeout(() => step(i + 1), delay);
    } catch (e) { decorBusy.delete(key); console.warn("santa decor error: " + e); }
  };
  step(0);
}
function decorSound(dimension, block, id, pitch) {
  try { dimension.playSound(id, { x: block.x + 0.5, y: block.y + 0.5, z: block.z + 0.5 }, { volume: 0.7, pitch: pitch || 1 }); } catch (e) {}
}
function useDecor(block, dimension, player) {
  const stack = stackOf(block), base = stack[0];
  const cfg = DECOR[base.typeId.slice("santa:".length)];
  if (!cfg) return;
  if (cfg.advent) { openAdvent(base, dimension, player); return; }
  if (cfg.flip) {   // doors: frame 0 shut, 1 open
    const open = base.permutation.getState("santa:frame") === 1;
    setStack(stack, "santa:frame", open ? 0 : 1);
    decorSound(dimension, base, open ? cfg.sound_off : cfg.sound_on);
    return;
  }
  if (cfg.ambient) {   // towns
    const on = !townOn(dimension, base);
    world.setDynamicProperty(townKey(dimension, base), on ? true : undefined);
    if (on) {
      ambientNext.delete(dimension.id + base.x + "," + base.y + "," + base.z);
      playAmbient(base, dimension, cfg);
      stepStates(base, dimension, "santa:frame", cfg.idle, cfg.idle_delay, (i) => animExtras(cfg, base, dimension, cfg.idle[i], i));
    } else {
      try { dimension.runCommand(`stopsound @a[x=${base.x},y=${base.y},z=${base.z},r=48] ${cfg.ambient}`); } catch (e) {}
      setStack(stackOf(base), "santa:frame", 0);
    }
    if (player) player.onScreenDisplay.setActionBar(on ? "Town animation and music: ON" : "Town animation and music: OFF");
    decorSound(dimension, base, "random.click", on ? 1.2 : 0.8);
    return;
  }
  if (cfg.anim) {
    stepStates(base, dimension, "santa:frame", cfg.anim, cfg.delay, (i) => {
      if (cfg.sound && i % (cfg.every || 99) === 0) decorSound(dimension, base, cfg.sound, 1.2 + Math.random() * 0.3);
      if (cfg.puffs) animExtras({ puffs: cfg.puffs }, base, dimension, cfg.anim[i], i);
    });
    if (cfg.particle) {
      for (let i = 0; i < 12; i++) {
        try { dimension.spawnParticle(cfg.particle, { x: base.x + 0.2 + Math.random() * 0.6, y: base.y + 0.4 + Math.random() * 0.6, z: base.z + 0.2 + Math.random() * 0.6 }); } catch (e) {}
      }
    }
    return;
  }
  if (!cfg.toggle) return;
  const on = base.permutation.getState("santa:on") === 1;
  if (on) {
    setStack(stack, "santa:on", 0);
    decorSound(dimension, base, cfg.sound_off || cfg.sound, 0.8);
  } else {
    decorSound(dimension, base, cfg.sound_on || cfg.sound, 1.2);
    if (cfg.flicker) stepStates(base, dimension, "santa:on", [1, 0, 1, 0, 1], 2);
    else setStack(stack, "santa:on", 1);
  }
}
function playerNear(block, dimension, r) {   // only animate big decorations someone can see (saves work on phones)
  try { return dimension.getPlayers({ location: { x: block.x + 0.5, y: block.y, z: block.z + 0.5 }, maxDistance: r }).length > 0; } catch (e) { return true; }
}
const ambientNext = new Map();   // town key -> tick its ambience can play again
function playAmbient(block, dimension, cfg) {
  const key = dimension.id + block.x + "," + block.y + "," + block.z, now = system.currentTick;
  if (now < (ambientNext.get(key) || 0)) return;
  ambientNext.set(key, now + Math.round(cfg.ambient_len * 20) + 10);
  try { dimension.playSound(cfg.ambient, { x: block.x + 0.5, y: block.y + 1, z: block.z + 2.5 }, { volume: 0.9 }); } catch (e) {}
}
function idleDecor(block, dimension) {
  const cfg = DECOR[block.typeId.slice("santa:".length)];
  if (!cfg) return;
  if (cfg.ambient && !townOn(dimension, block)) return;
  if (cfg.idle && cfg.near && !playerNear(block, dimension, cfg.near)) return;
  if (cfg.ambient) playAmbient(block, dimension, cfg);
  if (cfg.night) {   // village windows light up from dusk to dawn
    const t = world.getTimeOfDay(), on = t > 12500 && t < 23500 ? 1 : 0;
    if (block.permutation.getState("santa:on") !== on) block.setPermutation(block.permutation.withState("santa:on", on));
    return;
  }
  if (cfg.idle && (!cfg.toggle || block.permutation.getState("santa:on") === 1))
    stepStates(block, dimension, "santa:frame", cfg.idle, cfg.idle_delay, (i) => animExtras(cfg, block, dimension, cfg.idle[i], i));
}
// smoke puffs (model pixels per frame, e.g. the toy train's chimney) and an idle sound such as a "choo-choo"
function animExtras(cfg, base, dimension, frame, i) {
  try {
    if (cfg.puffs && cfg.puffs[frame]) {
      const p = cfg.puffs[frame], dir = base.permutation.getState("minecraft:cardinal_direction");
      const at = partPos({ x: base.x + 0.5, y: base.y, z: base.z + 0.5 }, dir, [p[0] / 16, p[1] / 16, p[2] / 16]);
      dimension.spawnParticle("minecraft:campfire_smoke_particle", at);
    }
    if (cfg.idle_sound && i % (cfg.idle_every || 99) === 0) {
      decorSound(dimension, base, cfg.idle_sound, 1.5);
      system.runTimeout(() => decorSound(dimension, base, cfg.idle_sound, 1.2), 4);   // choo... choo
    }
  } catch (e) {}
}
// advent calendar: each click opens the next door and pops out one treat
function openAdvent(block, dimension, player) {
  const day = block.permutation.getState("santa:day_a") * 16 + block.permutation.getState("santa:day_b");   // split: states max 16 values
  if (day >= 24) { if (player) player.onScreenDisplay.setActionBar("All 24 doors are open. Merry Christmas!"); return; }
  block.setPermutation(block.permutation.withState("santa:day_a", (day + 1) >> 4).withState("santa:day_b", (day + 1) & 15));
  decorSound(dimension, block, "random.orb", 1.3 + day / 40);
  const treat = pickFood();
  if (treat) { treat.amount = 1; dimension.spawnItem(treat, { x: block.x + 0.5, y: block.y + 0.6, z: block.z + 0.5 }); }
  if (player) player.onScreenDisplay.setActionBar("Door " + (day + 1) + " of 24");
}

// ---- holiday tools: Jingle Bells plays the tune, the Snowball Launcher fires bursts of snowballs ----
const JINGLE = [["E", 1], ["E", 1], ["E", 2], ["E", 1], ["E", 1], ["E", 2], ["E", 1], ["G", 1], ["C", 1.5], ["D", 0.5], ["E", 4], ["F", 1], ["F", 1], ["F", 1.5], ["F", 0.5], ["F", 1], ["E", 1], ["E", 1], ["E", 0.5], ["E", 0.5], ["E", 1], ["D", 1], ["D", 1], ["E", 1], ["D", 2], ["G", 2]];
const NOTE = { C: -6, D: -4, E: -2, F: -1, G: 1 };   // semitones from F#, the note sounds' base pitch
const jingling = new Set(), launchCool = new Map();
function playJingle(player) {
  if (jingling.has(player.id)) return;
  jingling.add(player.id);
  let t = 0;
  for (const [n, beats] of JINGLE) {
    system.runTimeout(() => {
      try {
        const l = player.location;
        player.dimension.playSound("note.bell", l, { pitch: Math.pow(2, NOTE[n] / 12), volume: 0.8 });
        player.dimension.spawnParticle("minecraft:note_particle", { x: l.x, y: l.y + 2.2, z: l.z });
      } catch (e) {}
    }, Math.round(t));
    t += beats * 5;
  }
  system.runTimeout(() => jingling.delete(player.id), Math.round(t) + 5);
}
function takeSnowball(player) {
  if (String(player.getGameMode()).toLowerCase() === "creative") return true;
  const inv = player.getComponent("minecraft:inventory").container;
  for (let s = 0; s < inv.size; s++) {
    const it = inv.getItem(s);
    if (it && it.typeId === "minecraft:snowball") { if (it.amount > 1) { it.amount -= 1; inv.setItem(s, it); } else inv.setItem(s, undefined); return true; }
  }
  return false;
}
function useLauncher(player) {
  const now = system.currentTick;
  if ((launchCool.get(player.id) || 0) > now) return;
  launchCool.set(player.id, now + 12);
  for (let i = 0; i < 3; i++) {
    system.runTimeout(() => {
      try {
        if (!takeSnowball(player)) { if (i === 0) player.onScreenDisplay.setActionBar("Out of snowballs"); return; }
        const head = player.getHeadLocation(), d = player.getViewDirection();
        const ball = player.dimension.spawnEntity("minecraft:snowball", { x: head.x + d.x * 0.9, y: head.y + d.y * 0.9 - 0.1, z: head.z + d.z * 0.9 });
        const proj = ball.getComponent("minecraft:projectile");
        if (proj) { proj.owner = player; proj.shoot({ x: d.x * 2.4, y: d.y * 2.4, z: d.z * 2.4 }, { uncertainty: 2 }); }
        else ball.applyImpulse({ x: d.x * 2, y: d.y * 2, z: d.z * 2 });
        player.dimension.playSound("random.bow", player.location, { pitch: 1.6, volume: 0.6 });
      } catch (e) { console.warn("santa launcher error: " + e); }
    }, i * 3);
  }
}

// ---- benches: right-click a bench block to sit on it (one seat per block, so a 2-block bench seats two) ----
const SEAT_Y = 0.35;   // ponytail: seat height tuned by eye; raise/lower if sitters float or sink into the bench
const FACING = { north: 180, south: 0, west: 90, east: -90 };
function sit(player, block) {
  if (!player || player.getComponent("minecraft:riding")) return;
  const at = { x: block.x + 0.5, y: block.y + SEAT_Y, z: block.z + 0.5 };
  if (block.dimension.getEntities({ type: "santa:seat", location: at, maxDistance: 0.5 }).length) {
    player.onScreenDisplay.setActionBar("Someone is already sitting there");
    return;
  }
  const seat = block.dimension.spawnEntity("santa:seat", at);
  seat.setRotation({ x: 0, y: FACING[block.permutation.getState("minecraft:cardinal_direction")] ?? 0 });
  seat.getComponent("minecraft:rideable").addRider(player);
}
system.runInterval(() => {   // empty seats, or seats whose bench is gone, remove themselves
  for (const id of ["overworld", "nether", "the_end"]) {
    for (const seat of world.getDimension(id).getEntities({ type: "santa:seat" })) {
      try {
        const under = seat.dimension.getBlock({ x: Math.floor(seat.location.x), y: Math.floor(seat.location.y), z: Math.floor(seat.location.z) });
        const benchGone = !under || !under.typeId.startsWith("santa:snowy_bench");
        if (benchGone || !seat.getComponent("minecraft:rideable").getRiders().length) seat.remove();
      } catch (e) {}
    }
  }
}, 20);

// ---- gumdrop blocks: land on one and you bounce back up (sneak to stay put) ----
const lastFallSpeed = new Map();
system.runInterval(() => {
  for (const p of world.getAllPlayers()) {
    try {
      const vy = p.getVelocity().y, prev = lastFallSpeed.get(p.id) ?? 0;
      lastFallSpeed.set(p.id, vy);
      if (prev < -0.3 && vy > -0.05 && !p.isSneaking) {          // just landed after a real fall
        const under = p.dimension.getBlock({ x: Math.floor(p.location.x), y: Math.floor(p.location.y - 0.2), z: Math.floor(p.location.z) });
        if (under && under.typeId.startsWith("santa:gumdrop_block")) p.applyKnockback({ x: 0, z: 0 }, Math.min(1.1, -prev * 0.85));
      }
    } catch (e) {}
  }
}, 1);

system.beforeEvents.startup.subscribe((startup) => {
  startup.itemComponentRegistry.registerCustomComponent("santa:launcher", { onUse(e) { system.run(() => useLauncher(e.source)); } });
  startup.itemComponentRegistry.registerCustomComponent("santa:jingle", { onUse(e) { system.run(() => playJingle(e.source)); } });
  startup.itemComponentRegistry.registerCustomComponent("santa:gift_box", { onUse(e) { system.run(() => boxMenu(e.source)); } });
  startup.blockComponentRegistry.registerCustomComponent("santa:multipart", { onPlayerBreak(e) { breakStack(e); } });
  startup.blockComponentRegistry.registerCustomComponent("santa:seat", { onPlayerInteract(e) { system.run(() => sit(e.player, e.block)); } });
  startup.blockComponentRegistry.registerCustomComponent("santa:decor", { onPlayerInteract(e) { useDecor(e.block, e.dimension, e.player); } });
  startup.blockComponentRegistry.registerCustomComponent("santa:idle", { onTick(e) { idleDecor(e.block, e.dimension); } });   // only on blocks with minecraft:tick
  startup.blockComponentRegistry.registerCustomComponent("santa:toy", { onPlayerInteract(event) { playToy(event.block, event.dimension); } });
  startup.blockComponentRegistry.registerCustomComponent("santa:present", {
    onPlayerInteract(event) {
      const { block, dimension } = event;
      if (block.permutation.getState("santa:open") !== 0) return;     // already opening
      const loc = { x: block.x, y: block.y, z: block.z }, type = block.typeId;
      const center = { x: loc.x + 0.5, y: loc.y + 0.5, z: loc.z + 0.5 };
      try { dimension.playSound("random.pop", center); } catch (e) {}
      const step = (n) => {
        try {
          const b = dimension.getBlock(loc);
          if (!b || b.typeId !== type) return;
          if (n <= 4) { b.setPermutation(b.permutation.withState("santa:open", n)); system.runTimeout(() => step(n + 1), 3); return; }
          b.setType("minecraft:air");
          for (let i = 0; i < 10; i++) {
            dimension.spawnParticle("minecraft:totem_particle", { x: center.x + (Math.random() - 0.5) * 0.6, y: center.y + 0.3, z: center.z + (Math.random() - 0.5) * 0.6 });
          }
          try { dimension.playSound("random.levelup", center, { volume: 0.5, pitch: 1.6 }); } catch (e) {}
          const g = takeGiftData(dimension, loc);
          if (g) {
            for (const it of g.items) { for (let n = it.n; n > 0; n -= 64) { const st = makeStack(it.id, Math.min(n, 64)); if (st) dimension.spawnItem(st, center); } }
            if (event.player) event.player.onScreenDisplay.setActionBar("A present from " + g.from + "!");
          } else {
            for (const gift of pickGifts()) dimension.spawnItem(gift, center);
          }
        } catch (e) { console.warn("santa present error: " + e); }
      };
      step(1);
    },
    onPlayerBreak(event) {   // a filled gift goes back to its wrapped item; a plain present drops itself
      try {
        const { block, dimension, brokenBlockPermutation, player } = event;
        const g = takeGiftData(dimension, block);
        if (player && String(player.getGameMode()).toLowerCase() === "creative") return;
        const type = brokenBlockPermutation.type.id, center = block.center();
        if (g) {
          const entry = GIFTS.find((x) => x[1] === type);
          const it = new ItemStack(entry ? entry[0] : GIFTS[0][0], 1);
          it.setDynamicProperty("gift", JSON.stringify(g)); it.setLore([(g.to ? "To: " + g.to : "A present"), "From: " + g.from]);
          dimension.spawnItem(it, center);
        } else dimension.spawnItem(new ItemStack(type, 1), center);
      } catch (e) { console.warn("santa present break error: " + e); }
    },
  });
});

// =====================================================================================================
// ---- Christmas update: milk & cookies, snow machine, jukebox, snowball pile, outfit bonus, guide ----
// =====================================================================================================
const posKey = (prefix, b) => prefix + ":" + b.dimension.id + ":" + b.x + "," + b.y + "," + b.z;
const isCreativeP = (p) => p && String(p.getGameMode()).toLowerCase() === "creative";
function takeOne(player, id) {   // remove one `id` from the held stack; true if it was there
  const inv = player.getComponent("minecraft:inventory")?.container, slot = player.selectedSlotIndex;
  const it = inv?.getItem(slot);
  if (!it || it.typeId !== id) return false;
  if (isCreativeP(player)) return true;
  if (it.amount <= 1) inv.setItem(slot, undefined); else { it.amount -= 1; inv.setItem(slot, it); }
  return true;
}
function give(player, stack) {
  const left = player.getComponent("minecraft:inventory")?.container?.addItem(stack);
  if (left) player.dimension.spawnItem(left, player.location);
}

// ---- milk & cookies: left out overnight, Santa eats them and leaves a present beside the plate ----
const SPOTS = [[1, 0], [-1, 0], [0, 1], [0, -1], [1, 1], [-1, 1], [1, -1], [-1, -1]];
function santaVisits(block) {
  const dim = block.dimension;
  block.setPermutation(block.permutation.withState("santa:empty", 1));
  world.setDynamicProperty(posKey("plate", block), undefined);
  const spot = SPOTS.map(([dx, dz]) => dim.getBlock({ x: block.x + dx, y: block.y, z: block.z + dz }))
    .find((b) => b && b.isAir && b.below() && !b.below().isAir && !b.below().isLiquid);
  const gift = { items: pickGifts().map((s) => ({ id: s.typeId, n: s.amount })), from: "Santa", to: "" };
  if (spot) {
    spot.setType(any(GIFTS)[1]);
    world.setDynamicProperty(giftKey(dim, spot), JSON.stringify(gift));
  } else {   // no room for a present: Santa leaves the gifts on the plate instead
    for (const it of gift.items) { const s = makeStack(it.id, it.n); if (s) dim.spawnItem(s, block.center()); }
  }
  const c = block.center();
  for (let i = 0; i < 12; i++) dim.spawnParticle("minecraft:totem_particle", { x: c.x + Math.random() - 0.5, y: c.y + Math.random(), z: c.z + Math.random() - 0.5 });
  try { dim.playSound("random.levelup", c, { volume: 0.6, pitch: 1.4 }); } catch (e) {}
}

// ---- snow machine ----
function snowTick(block) {
  if (block.permutation.getState("santa:on") !== 1) return;
  const dim = block.dimension, c = block.center();
  try { dim.spawnParticle("santa:snow_spray", { x: c.x, y: block.y + 0.9, z: c.z }); } catch (e) {}   // burst out of the nozzle
  for (let i = 0; i < 8; i++) {
    dim.spawnParticle("minecraft:snowflake_particle", { x: c.x + (Math.random() - 0.5) * 12, y: c.y + 1.5 + Math.random() * 3, z: c.z + (Math.random() - 0.5) * 12 });
  }
  if (Math.random() > 0.35) return;
  const a = Math.random() * Math.PI * 2, r = Math.random() * 6;   // one snow layer at a random spot within 6 blocks
  const x = Math.floor(block.x + Math.cos(a) * r), z = Math.floor(block.z + Math.sin(a) * r);
  for (let y = block.y + 4; y >= block.y - 4; y--) {
    const b = dim.getBlock({ x, y, z });
    if (!b || b.isAir) continue;
    if (b.isLiquid || b.typeId === "minecraft:snow_layer" || b.typeId.startsWith("santa:")) return;
    const above = b.above();
    if (above && above.isAir) { try { above.setType("minecraft:snow_layer"); } catch (e) {} }
    return;
  }
}

// ---- snowball piles join up with piles next to them (bridge balls fill the gap) ----
const PILE_DIRS = { east: [1, 0], west: [-1, 0], north: [0, -1], south: [0, 1] };
function refreshPile(b) {
  if (!b || b.typeId !== "santa:snowball_pile") return;
  let perm = b.permutation;
  for (const [d, [dx, dz]] of Object.entries(PILE_DIRS)) {
    const n = b.dimension.getBlock({ x: b.x + dx, y: b.y, z: b.z + dz });
    perm = perm.withState("santa:" + d, !!n && n.typeId === "santa:snowball_pile");
  }
  b.setPermutation(perm);
}
function refreshPilesAround(b) {
  refreshPile(b);
  for (const [dx, dz] of Object.values(PILE_DIRS)) refreshPile(b.dimension.getBlock({ x: b.x + dx, y: b.y, z: b.z + dz }));
}

// ---- christmas jukebox ----
const SONGS = {"jingle_bells": ["Jingle Bells", 47.7], "deck_the_halls": ["Deck the Halls", 57.4], "we_wish_you": ["We Wish You a Merry Christmas", 42.5], "silent_night": ["Silent Night", 88.9], "joy_to_the_world": ["Joy to the World", 79.5]};   // key: [title, seconds]
const SONG_KEYS = Object.keys(SONGS);
const playing = new Map();   // block key -> { sound, until }
function stopSong(block) {
  const p = playing.get(posKey("juke", block)); playing.delete(posKey("juke", block));
  if (p) { try { block.dimension.runCommand(`stopsound @a[x=${block.x},y=${block.y},z=${block.z},r=64] ${p.sound}`); } catch (e) {} }
}
function jukeboxMenu(block, player) {
  const form = new ActionFormData().title("Christmas Jukebox").body("Pick a song to play.");
  SONG_KEYS.forEach((k) => form.button(SONGS[k][0]));
  form.button("Stop the music");
  form.show(player).then((r) => {
    if (r.canceled || r.selection === undefined) return;
    const b = block.dimension.getBlock(block.location);
    if (!b || b.typeId !== "santa:christmas_jukebox") return;
    stopSong(b);
    if (r.selection >= SONG_KEYS.length) { b.setPermutation(b.permutation.withState("santa:playing", 0)); return; }
    const k = SONG_KEYS[r.selection], sound = "santa.jukebox." + k;
    b.dimension.playSound(sound, b.center(), { volume: 1.0 });
    playing.set(posKey("juke", b), { sound, until: system.currentTick + Math.ceil(SONGS[k][1] * 20) });
    b.setPermutation(b.permutation.withState("santa:playing", 1));
    player.onScreenDisplay.setActionBar("Now playing: " + SONGS[k][0]);
  }).catch((e) => console.warn("jukebox menu: " + e));
}

// ---- christmas guide: one per player per world; unlocks every Christmas recipe ----
const ALL_RECIPES = ["xmas:sleigh_harness_recipe", "xmas:toy_soldier_kit_recipe", "xmas:apple_pie_slice_recipe", "xmas:candy_cane_recipe", "xmas:chocolate_bar_recipe", "xmas:chocolate_coins_recipe", "xmas:christmas_pudding_recipe", "xmas:christmas_pudding_recipe_blue_egg", "xmas:christmas_pudding_recipe_brown_egg", "xmas:cinnamon_bun_recipe", "xmas:cinnamon_bun_recipe_blue_egg", "xmas:cinnamon_bun_recipe_brown_egg", "xmas:cinnamon_recipe", "xmas:cocoa_mug_marshmallow_recipe", "xmas:cocoa_mug_marshmallow_unpack_recipe", "xmas:cocoa_mug_recipe", "xmas:cocoa_mug_unpack_recipe", "xmas:cookie_chocolate_chip_gingerbread_man_recipe", "xmas:cookie_chocolate_chip_heart_recipe", "xmas:cookie_chocolate_chip_recipe", "xmas:cookie_chocolate_chip_snowflake_recipe", "xmas:cookie_chocolate_chip_star_recipe", "xmas:cookie_chocolate_chip_tree_recipe", "xmas:cookie_gingerbread_gingerbread_man_recipe", "xmas:cookie_gingerbread_heart_recipe", "xmas:cookie_gingerbread_recipe", "xmas:cookie_gingerbread_snowflake_recipe", "xmas:cookie_gingerbread_star_recipe", "xmas:cookie_gingerbread_tree_recipe", "xmas:cookie_peppermint_chocolate_gingerbread_man_recipe", "xmas:cookie_peppermint_chocolate_heart_recipe", "xmas:cookie_peppermint_chocolate_recipe", "xmas:cookie_peppermint_chocolate_snowflake_recipe", "xmas:cookie_peppermint_chocolate_star_recipe", "xmas:cookie_peppermint_chocolate_tree_recipe", "xmas:cookie_snickerdoodle_gingerbread_man_recipe", "xmas:cookie_snickerdoodle_gingerbread_man_recipe_blue_egg", "xmas:cookie_snickerdoodle_gingerbread_man_recipe_brown_egg", "xmas:cookie_snickerdoodle_heart_recipe", "xmas:cookie_snickerdoodle_heart_recipe_blue_egg", "xmas:cookie_snickerdoodle_heart_recipe_brown_egg", "xmas:cookie_snickerdoodle_recipe", "xmas:cookie_snickerdoodle_recipe_blue_egg", "xmas:cookie_snickerdoodle_recipe_brown_egg", "xmas:cookie_snickerdoodle_snowflake_recipe", "xmas:cookie_snickerdoodle_snowflake_recipe_blue_egg", "xmas:cookie_snickerdoodle_snowflake_recipe_brown_egg", "xmas:cookie_snickerdoodle_star_recipe", "xmas:cookie_snickerdoodle_star_recipe_blue_egg", "xmas:cookie_snickerdoodle_star_recipe_brown_egg", "xmas:cookie_snickerdoodle_tree_recipe", "xmas:cookie_snickerdoodle_tree_recipe_blue_egg", "xmas:cookie_snickerdoodle_tree_recipe_brown_egg", "xmas:cookie_sugar_gingerbread_man_recipe", "xmas:cookie_sugar_gingerbread_man_recipe_blue_egg", "xmas:cookie_sugar_gingerbread_man_recipe_brown_egg", "xmas:cookie_sugar_heart_recipe", "xmas:cookie_sugar_heart_recipe_blue_egg", "xmas:cookie_sugar_heart_recipe_brown_egg", "xmas:cookie_sugar_recipe", "xmas:cookie_sugar_recipe_blue_egg", "xmas:cookie_sugar_recipe_brown_egg", "xmas:cookie_sugar_snowflake_recipe", "xmas:cookie_sugar_snowflake_recipe_blue_egg", "xmas:cookie_sugar_snowflake_recipe_brown_egg", "xmas:cookie_sugar_star_recipe", "xmas:cookie_sugar_star_recipe_blue_egg", "xmas:cookie_sugar_star_recipe_brown_egg", "xmas:cookie_sugar_tree_recipe", "xmas:cookie_sugar_tree_recipe_blue_egg", "xmas:cookie_sugar_tree_recipe_brown_egg", "xmas:cutter_gingerbread_man_recipe", "xmas:cutter_heart_recipe", "xmas:cutter_snowflake_recipe", "xmas:cutter_star_recipe", "xmas:cutter_tree_recipe", "xmas:eggnog_glass_recipe", "xmas:eggnog_glass_unpack_recipe", "xmas:eggnog_recipe", "xmas:eggnog_recipe_blue_egg", "xmas:eggnog_recipe_brown_egg", "xmas:fudge_recipe", "xmas:gingerbread_oven_recipe", "xmas:gumdrop_blue_recipe", "xmas:gumdrop_green_recipe", "xmas:gumdrop_purple_recipe", "xmas:gumdrop_red_recipe", "xmas:gumdrop_yellow_recipe", "xmas:hot_cocoa_marshmallow_recipe", "xmas:hot_cocoa_recipe", "xmas:ice_cream_candy_cane_crunch_recipe", "xmas:ice_cream_chocolate_recipe", "xmas:ice_cream_gingerbread_recipe", "xmas:ice_cream_matcha_recipe", "xmas:ice_cream_peppermint_recipe", "xmas:ice_cream_strawberry_recipe", "xmas:ice_cream_vanilla_recipe", "xmas:lollipop_recipe", "xmas:marshmallow_recipe", "xmas:marshmallow_recipe_blue_egg", "xmas:marshmallow_recipe_brown_egg", "xmas:peppermint_candy_recipe", "xmas:pumpkin_pie_slice_recipe", "xmas:pumpkin_pie_slice_recipe_blue_egg", "xmas:pumpkin_pie_slice_recipe_brown_egg", "xmas:toffee_recipe", "xmas:yule_log_recipe", "xmas:yule_log_recipe_blue_egg", "xmas:yule_log_recipe_brown_egg", "xmas:apple_pie_recipe", "xmas:big_christmas_pudding_recipe", "xmas:candy_bowl_recipe", "xmas:carrot_cake_recipe", "xmas:carrot_cake_recipe_blue_egg", "xmas:carrot_cake_recipe_brown_egg", "xmas:cinnamon_bun_tray_recipe", "xmas:cookie_plate_recipe", "xmas:fruitcake_recipe", "xmas:peppermint_chocolate_cake_recipe", "xmas:pumpkin_pie_recipe", "xmas:red_velvet_cake_recipe", "xmas:red_velvet_cake_recipe_blue_egg", "xmas:red_velvet_cake_recipe_brown_egg", "xmas:yule_log_platter_recipe", "santa:advent_calendar_recipe", "santa:bobble_beanie_recipe", "santa:candy_cane_block_recipe", "santa:candy_cane_lamp_recipe", "santa:candy_cane_pickaxe_recipe", "santa:candy_cane_sword_recipe", "santa:card_stand_recipe", "santa:chocolate_block_recipe", "santa:christmas_candles_recipe", "santa:christmas_jukebox_recipe", "santa:christmas_tree_recipe", "santa:christmas_tree_medium_recipe", "santa:cookie_tile_recipe", "santa:door_wreath_recipe", "santa:earmuffs_recipe", "santa:elf_hat_recipe", "santa:elf_shoes_recipe", "santa:elf_tunic_recipe", "santa:frozen_lake_village_recipe", "santa:fudge_bricks_recipe", "santa:garland_recipe", "santa:giant_candy_cane_recipe", "santa:gift_box_recipe", "santa:gingerbread_block_recipe", "santa:gingerbread_house_recipe", "santa:golden_bells_recipe", "santa:gumdrop_block_green_recipe", "santa:gumdrop_block_purple_recipe", "santa:gumdrop_block_red_recipe", "santa:gumdrop_block_yellow_recipe", "santa:holly_centerpiece_recipe", "santa:iced_gingerbread_block_recipe", "santa:icicle_lights_recipe", "santa:icicles_recipe", "santa:icing_block_recipe", "santa:inflatable_santa_recipe", "santa:jack_in_the_box_recipe", "santa:jingle_bells_recipe", "santa:lawn_reindeer_recipe", "santa:light_arch_recipe", "santa:lightup_snowman_recipe", "santa:market_village_recipe", "santa:milk_cookies_recipe", "santa:mini_village_recipe", "santa:mint_candy_block_recipe", "santa:mistletoe_recipe", "santa:mrs_claus_dress_recipe", "santa:north_pole_village_recipe", "santa:nutcracker_recipe", "santa:nutcracker_statue_recipe", "santa:ornament_blue_recipe", "santa:ornament_gold_recipe", "santa:ornament_green_recipe", "santa:ornament_purple_recipe", "santa:ornament_red_recipe", "santa:ornament_silver_recipe", "santa:pajama_pants_recipe", "santa:pajama_top_recipe", "santa:path_cane_recipe", "santa:peppermint_block_recipe", "santa:poinsettia_recipe", "santa:present_blue_recipe", "santa:present_candy_recipe", "santa:present_cyan_recipe", "santa:present_gold_recipe", "santa:present_green_recipe", "santa:present_orange_recipe", "santa:present_pink_recipe", "santa:present_purple_recipe", "santa:present_red_recipe", "santa:present_silver_recipe", "santa:present_stack_recipe", "santa:railway_village_recipe", "santa:reindeer_antlers_recipe", "santa:rocking_horse_recipe", "santa:rubber_duck_recipe", "santa:santa_boots_recipe", "santa:santa_coat_recipe", "santa:santa_hat_recipe", "santa:santa_pants_recipe", "santa:workbench_recipe", "santa:sleigh_recipe", "santa:snow_globe_recipe", "santa:snow_globe_display_recipe", "santa:snow_machine_recipe", "santa:snowball_launcher_recipe", "santa:snowball_pile_recipe", "santa:snowy_bench_recipe", "santa:spinning_top_recipe", "santa:star_lantern_recipe", "santa:stocking_green_recipe", "santa:stocking_plaid_recipe", "santa:stocking_red_recipe", "santa:stocking_striped_recipe", "santa:string_lights_multi_recipe", "santa:string_lights_redgreen_recipe", "santa:string_lights_warm_recipe", "santa:stuffed_reindeer_recipe", "santa:sweater_bauble_recipe", "santa:sweater_blue_recipe", "santa:sweater_candy_cane_recipe", "santa:sweater_forest_recipe", "santa:sweater_gingerbread_recipe", "santa:sweater_green_recipe", "santa:sweater_hearts_recipe", "santa:sweater_midnight_recipe", "santa:sweater_mint_recipe", "santa:sweater_present_recipe", "santa:sweater_red_recipe", "santa:sweater_reindeer_gray_recipe", "santa:sweater_snowflake_navy_recipe", "santa:sweater_snowman_recipe", "santa:sweater_star_recipe", "santa:tall_christmas_tree_recipe", "santa:teddy_bear_recipe", "santa:toy_airplane_recipe", "santa:toy_car_recipe", "santa:toy_castle_recipe", "santa:toy_drum_recipe", "santa:toy_parts_recipe", "santa:toy_penguin_recipe", "santa:toy_robot_recipe", "santa:toy_sled_recipe", "santa:toy_snowman_recipe", "santa:toy_soldier_recipe", "santa:toy_train_recipe", "santa:victorian_village_recipe", "santa:village_bakery_recipe", "santa:village_church_recipe", "santa:village_cottage_recipe", "santa:village_toy_shop_recipe", "santa:white_chocolate_block_recipe", "santa:window_candle_recipe", "santa:wooden_blocks_recipe", "santa:wreath_recipe", "santa:yo_yo_recipe"];
const GUIDE_TEXT = [
  "§lHow to start§r", "Craft these two stations at a normal crafting table.", "",
  "§6Gingerbread Oven§r (Gingerbread Oven add-on)", "  Brick   Brick    Brick", "  Brick   Furnace  Brick", "  Brick   Brick    Brick", "",
  "§cSanta's Workbench§r", "  Red Wool  Red Wool        Red Wool", "  Planks    Crafting Table  Planks", "  Planks    (empty)         Planks",
  "  (planks are spruce)", "",
  "Every Christmas recipe is now unlocked in your recipe book. Foods are made in the Oven; decorations, toys, outfits and gadgets at the Workbench.",
].join("\n");
function unlockAll(player) {
  if (player.getDynamicProperty("santa:recipes_unlocked") === ALL_RECIPES.length) return;
  for (const id of ALL_RECIPES) { try { player.runCommand(`recipe give @s ${id}`); } catch (e) {} }   // missing add-on = skip
  player.setDynamicProperty("santa:recipes_unlocked", ALL_RECIPES.length);
}
world.afterEvents.playerSpawn.subscribe((e) => {
  const p = e.player;
  if (!e.initialSpawn || p.getDynamicProperty("santa:guide_given")) return;
  p.setDynamicProperty("santa:guide_given", true);
  give(p, new ItemStack("santa:christmas_guide", 1));
  p.sendMessage("§aMerry Christmas! §rYou got the §cChristmas Guide§r. You only get one, so keep it safe!");
});

// ---- outfit bonus: Christmas pieces in all 4 armor slots (any mix) = snowflakes + Jolly (speed + jump) ----
const SLOTS = [EquipmentSlot.Head, EquipmentSlot.Chest, EquipmentSlot.Legs, EquipmentSlot.Feet];
const jolly = new Set();
system.runInterval(() => {
  for (const p of world.getAllPlayers()) {
    let on = false;
    try { const eq = p.getComponent("minecraft:equippable"); on = SLOTS.every((s) => eq.getEquipment(s)?.typeId.startsWith("santa:")); } catch (e) {}
    if (!on) { jolly.delete(p.id); continue; }
    if (!jolly.has(p.id)) { jolly.add(p.id); p.onScreenDisplay.setActionBar("§bYou feel Jolly!§r Christmas outfit bonus"); }
    p.addEffect("speed", 80, { amplifier: 0, showParticles: false });
    p.addEffect("jump_boost", 80, { amplifier: 0, showParticles: false });
    const l = p.location;
    for (let i = 0; i < 4; i++) p.dimension.spawnParticle("minecraft:snowflake_particle", { x: l.x + (Math.random() - 0.5) * 1.6, y: l.y + 0.3 + Math.random() * 2, z: l.z + (Math.random() - 0.5) * 1.6 });
  }
}, 20);

system.beforeEvents.startup.subscribe((startup) => {
  const reg = startup.blockComponentRegistry;
  reg.registerCustomComponent("santa:milk_cookies", {
    onPlace(e) { if (e.block.typeId === "santa:milk_cookies") world.setDynamicProperty(posKey("plate", e.block), world.getDay()); },
    onTick(e) {
      const b = e.block;
      if (b.permutation.getState("santa:empty") === 1) return;
      const k = posKey("plate", b), placed = world.getDynamicProperty(k);
      if (placed === undefined) { world.setDynamicProperty(k, world.getDay()); return; }
      if (world.getDay() > placed && world.getTimeOfDay() < 12000) santaVisits(b);   // a night has passed
    },
    onPlayerInteract(e) {
      const { block, player } = e;
      if (!player) return;
      if (block.permutation.getState("santa:empty") === 1) {
        if (takeOne(player, "minecraft:cookie")) {
          block.setPermutation(block.permutation.withState("santa:empty", 0));
          world.setDynamicProperty(posKey("plate", block), world.getDay());
          player.onScreenDisplay.setActionBar("Refilled! Leave it out tonight for Santa.");
        } else player.onScreenDisplay.setActionBar("Santa ate everything! Use a cookie on the plate to refill it.");
      } else player.onScreenDisplay.setActionBar("Leave this out overnight. Santa might stop by...");
    },
    onPlayerBreak(e) { world.setDynamicProperty(posKey("plate", e.block), undefined); },
  });
  reg.registerCustomComponent("santa:snow_machine", {
    onTick(e) { snowTick(e.block); },
    onPlayerInteract(e) {
      const b = e.block, on = b.permutation.getState("santa:on") === 1;
      b.setPermutation(b.permutation.withState("santa:on", on ? 0 : 1));
      try { b.dimension.playSound("random.click", b.center()); } catch (err) {}
      e.player?.onScreenDisplay.setActionBar(on ? "Snow machine off" : "Snow machine on - let it snow!");
    },
  });
  reg.registerCustomComponent("santa:jukebox", {
    onPlayerInteract(e) { if (e.player) system.run(() => jukeboxMenu(e.block, e.player)); },
    onTick(e) {
      const b = e.block;
      if (b.permutation.getState("santa:playing") !== 1) return;
      const p = playing.get(posKey("juke", b));
      if (!p || system.currentTick > p.until) { playing.delete(posKey("juke", b)); b.setPermutation(b.permutation.withState("santa:playing", 0)); return; }
      const c = b.center();
      for (let i = 0; i < 2; i++) {   // rainbow notes floating out of the top
        const at = { x: c.x + (Math.random() - 0.5) * 0.6, y: b.y + 1.2 + Math.random() * 0.2, z: c.z + (Math.random() - 0.5) * 0.4 };
        try { b.dimension.spawnParticle("santa:rainbow_note", at); } catch (err) {}
      }
    },
    onPlayerBreak(e) { stopSong(e.block); },
  });
  reg.registerCustomComponent("santa:snowball_pile", {
    onPlace(e) { refreshPilesAround(e.block); },
    onPlayerBreak(e) { refreshPilesAround(e.block); },
    onPlayerInteract(e) {
      if (!e.player) return;
      give(e.player, new ItemStack("minecraft:snowball", 16));
      try { e.block.dimension.playSound("dig.snow", e.block.center()); } catch (err) {}
    },
  });
  startup.itemComponentRegistry.registerCustomComponent("santa:guide", {
    onUse(e) {
      const p = e.source;
      system.run(() => {
        unlockAll(p);
        new ActionFormData().title("Christmas Guide").body(GUIDE_TEXT).button("Close").show(p).catch(() => {});
      });
    },
  });
});
