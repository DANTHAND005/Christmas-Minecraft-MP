import { world, system, ItemStack, BlockPermutation } from "@minecraft/server";
import { ActionFormData, ModalFormData } from "@minecraft/server-ui";

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
const decorBusy = new Set();
// ---- tall decorations (trees, lamp post, giant cane, reindeer) are a base block with part blocks stacked on top ----
const MULTI = {"santa:christmas_tree_medium": 2, "santa:tall_christmas_tree": 3, "santa:candy_cane_lamp": 3, "santa:giant_candy_cane": 3, "santa:lawn_reindeer": 2};
function stackOf(block) {
  const m = block.typeId.match(/^(santa:.+)_part(\d+)$/);
  const base = m ? block.dimension.getBlock({ x: block.x, y: block.y - Number(m[2]), z: block.z }) : block;
  const id = m ? m[1] : block.typeId;
  if (!base || base.typeId !== id) return [block];
  const out = [base];
  for (let k = 1; k < (MULTI[id] || 1); k++) {
    const b = base.dimension.getBlock({ x: base.x, y: base.y + k, z: base.z });
    if (b && b.typeId === id + "_part" + k) out.push(b);
  }
  return out;
}
function setStack(stack, state, value) { for (const b of stack) { try { b.setPermutation(b.permutation.withState(state, value)); } catch (e) {} } }
world.afterEvents.playerPlaceBlock.subscribe((e) => {
  const b = e.block, n = MULTI[b.typeId];
  if (!n) return;
  const dir = b.permutation.getState("minecraft:cardinal_direction");
  for (let k = 1; k < n; k++) {
    const above = b.dimension.getBlock({ x: b.x, y: b.y + k, z: b.z });
    if (!above || !above.isAir) {
      const id = b.typeId; b.setType("minecraft:air");
      if (String(e.player.getGameMode()).toLowerCase() !== "creative") b.dimension.spawnItem(new ItemStack(id, 1), b.center());
      e.player.onScreenDisplay.setActionBar("This needs " + n + " blocks of empty space above the ground");
      return;
    }
  }
  for (let k = 1; k < n; k++) {
    b.dimension.getBlock({ x: b.x, y: b.y + k, z: b.z }).setPermutation(BlockPermutation.resolve(b.typeId + "_part" + k, { "minecraft:cardinal_direction": dir }));
  }
});
function breakStack(event) {   // breaking any piece removes the whole decoration (the base drops it once)
  const { block, dimension, brokenBlockPermutation, player } = event;
  const id = brokenBlockPermutation.type.id, m = id.match(/^(santa:.+)_part(\d+)$/);
  const baseId = m ? m[1] : id, baseY = m ? block.y - Number(m[2]) : block.y;
  for (let k = 0; k < (MULTI[baseId] || 1); k++) {
    const y = baseY + k; if (y === block.y) continue;
    const b = dimension.getBlock({ x: block.x, y, z: block.z });
    if (b && (b.typeId === baseId || b.typeId === baseId + "_part" + k)) b.setType("minecraft:air");
  }
  if (m && player && String(player.getGameMode()).toLowerCase() !== "creative") dimension.spawnItem(new ItemStack(baseId, 1), { x: block.x + 0.5, y: baseY + 0.5, z: block.z + 0.5 });
}
function stepStates(block, dimension, state, seq, delay, onStep) {
  const stack = stackOf(block), base = stack[0];
  const loc = { x: base.x, y: base.y, z: base.z }, type = base.typeId, key = dimension.id + loc.x + "," + loc.y + "," + loc.z;
  if (decorBusy.has(key)) return;
  decorBusy.add(key);
  const step = (i) => {
    try {
      const b = dimension.getBlock(loc);
      if (!b || b.typeId !== type || i >= seq.length) { decorBusy.delete(key); return; }
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
function useDecor(block, dimension) {
  const stack = stackOf(block), base = stack[0];
  const cfg = DECOR[base.typeId.slice("santa:".length)];
  if (!cfg) return;
  if (cfg.anim) {
    stepStates(base, dimension, "santa:frame", cfg.anim, cfg.delay, (i) => { if (i % (cfg.every || 99) === 0) decorSound(dimension, base, cfg.sound, 1.2 + Math.random() * 0.3); });
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
function idleDecor(block, dimension) {
  const cfg = DECOR[block.typeId.slice("santa:".length)];
  if (cfg && cfg.idle && block.permutation.getState("santa:on") === 1) stepStates(block, dimension, "santa:frame", cfg.idle, cfg.idle_delay);
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

system.beforeEvents.startup.subscribe((startup) => {
  startup.itemComponentRegistry.registerCustomComponent("santa:launcher", { onUse(e) { system.run(() => useLauncher(e.source)); } });
  startup.itemComponentRegistry.registerCustomComponent("santa:jingle", { onUse(e) { system.run(() => playJingle(e.source)); } });
  startup.itemComponentRegistry.registerCustomComponent("santa:gift_box", { onUse(e) { system.run(() => boxMenu(e.source)); } });
  startup.blockComponentRegistry.registerCustomComponent("santa:multipart", { onPlayerBreak(e) { breakStack(e); } });
  startup.blockComponentRegistry.registerCustomComponent("santa:decor", {
    onPlayerInteract(e) { useDecor(e.block, e.dimension); },
    onTick(e) { idleDecor(e.block, e.dimension); },
  });
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
