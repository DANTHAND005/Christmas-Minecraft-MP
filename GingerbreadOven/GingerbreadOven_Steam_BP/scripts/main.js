import { world, system, ItemStack, BlockPermutation } from "@minecraft/server";
import { ActionFormData } from "@minecraft/server-ui";

// ---- steam rising from hot cocoa while it is held ----
const STEAMING = new Set(["xmas:hot_cocoa", "xmas:hot_cocoa_marshmallow"]);

system.runInterval(() => {
  for (const player of world.getAllPlayers()) {
    try {
      const inventory = player.getComponent("minecraft:inventory");
      if (!inventory || !inventory.container) continue;
      const item = inventory.container.getItem(player.selectedSlotIndex);
      if (!item || !STEAMING.has(item.typeId)) continue;

      const head = player.getHeadLocation();
      const look = player.getViewDirection();
      let rx = -look.z, rz = look.x;
      const len = Math.hypot(rx, rz) || 1;
      rx /= len; rz /= len;
      const spot = {
        x: head.x + look.x * 0.6 + rx * 0.3,
        y: head.y - 0.45 + look.y * 0.3,
        z: head.z + look.z * 0.6 + rz * 0.3,
      };
      player.dimension.spawnParticle("minecraft:white_smoke_particle", spot);
    } catch (e) {
      // ignore: player may be loading in or changing dimension
    }
  }
}, 8);

// ---- Jolly: a cosmetic "effect" from eating any Christmas food ----
// Add-ons can't create real status effects, so Jolly shows as a Santa icon and timer on the action bar plus sparkles.
const JOLLY_SECONDS = 10;
function giveJolly(player) { try { player.setDynamicProperty("jolly", JOLLY_SECONDS); } catch (e) {} }
world.afterEvents.itemCompleteUse.subscribe((e) => { if (e.source && e.itemStack.typeId.startsWith("xmas:")) giveJolly(e.source); });
system.runInterval(() => {
  for (const p of world.getAllPlayers()) {
    try {
      const left = p.getDynamicProperty("jolly");
      if (typeof left !== "number" || left <= 0) continue;
      p.setDynamicProperty("jolly", left > 1 ? left - 1 : undefined);
      const m = Math.floor((left - 1) / 60), sec = String((left - 1) % 60).padStart(2, "0");
      p.onScreenDisplay.setActionBar(" Jolly " + m + ":" + sec);
      const l = p.location;
      p.dimension.spawnParticle("minecraft:villager_happy", { x: l.x + (Math.random() - 0.5), y: l.y + 1 + Math.random(), z: l.z + (Math.random() - 0.5) });
    } catch (e) {}
  }
}, 20);

// ---- chimney smoke on placed Gingerbread Ovens ----
// Ovens are remembered when placed or opened (so ovens from older builds join the first time someone uses them).
const OVEN = "xmas:gingerbread_oven";
function ovenList() { try { return JSON.parse(world.getDynamicProperty("ovens") || "[]"); } catch (e) { return []; } }
function ovenTag(block) { return block.dimension.id + "|" + block.x + "|" + block.y + "|" + block.z; }
function rememberOven(block, keep) {
  const list = ovenList().filter((t) => t !== ovenTag(block));
  if (keep) list.push(ovenTag(block));
  world.setDynamicProperty("ovens", JSON.stringify(list));
}
world.afterEvents.playerPlaceBlock.subscribe((e) => { if (e.block.typeId === OVEN) rememberOven(e.block, true); });
world.afterEvents.playerInteractWithBlock.subscribe((e) => {
  if (e.block.typeId === OVEN && !ovenList().includes(ovenTag(e.block))) rememberOven(e.block, true);
});
world.afterEvents.playerBreakBlock.subscribe((e) => { if (e.brokenBlockPermutation.type.id === OVEN) rememberOven(e.block, false); });
system.runInterval(() => {
  const players = world.getAllPlayers();
  for (const tag of ovenList()) {
    const [dimId, xs, ys, zs] = tag.split("|"); const x = +xs, y = +ys, z = +zs;
    if (!players.some((p) => p.dimension.id === dimId && Math.abs(p.location.x - x) < 48 && Math.abs(p.location.z - z) < 48)) continue;
    try {
      const dim = world.getDimension(dimId);
      const b = dim.getBlock({ x, y, z });
      if (!b) continue;                                       // chunk not loaded
      if (b.typeId !== OVEN) { rememberOven(b, false); continue; }
      dim.spawnParticle("minecraft:campfire_smoke_particle", { x: x + 0.5, y: y + 1.35, z: z + 0.5 });
    } catch (e) {}
  }
}, 40);

// ---- cookie plate helpers ----
const FLAVORS = ["gingerbread", "sugar", "chocolate_chip", "snickerdoodle", "peppermint_chocolate"];
const SHAPES = ["", "star", "tree", "heart", "gingerbread_man", "snowflake"];
const SHAPE_NAMES = ["round", "star", "tree", "heart", "gingerbread man", "snowflake"];

function parseCookie(typeId) {
  if (!typeId.startsWith("xmas:cookie_")) return null;
  const rest = typeId.slice("xmas:cookie_".length);
  for (let f = 0; f < FLAVORS.length; f++) {
    const name = FLAVORS[f];
    if (rest === name) return { flavor: f + 1, shape: 0 };
    if (rest.startsWith(name + "_")) {
      const sh = SHAPES.indexOf(rest.slice(name.length + 1));
      if (sh > 0) return { flavor: f + 1, shape: sh };
    }
  }
  return null;
}
const FLAVOR_NAMES = ["Gingerbread", "Sugar", "Chocolate Chip", "Snickerdoodle", "Peppermint Chocolate"];
function cookieName(id) {
  const c = parseCookie(id);
  return FLAVOR_NAMES[c.flavor - 1] + " Cookie" + (c.shape ? " (" + SHAPE_NAMES[c.shape] + ")" : "");
}
function say(player, text) {
  try { player.onScreenDisplay.setActionBar(text); } catch (e) {}
}
function giveItem(player, id, count) {
  const inv = player.getComponent("minecraft:inventory").container;
  while (count > 0) {
    const n = Math.min(count, 64);
    const left = inv.addItem(new ItemStack(id, n));
    if (left) player.dimension.spawnItem(left, player.location);
    count -= n;
  }
}
function sumOf(data) { return Object.values(data).reduce((a, b) => a + b, 0); }

// ---- candy bowl look: up to 4 heaps and 3 fullness steps ----
const CANDY = {
  "xmas:candy_cane": { kind: 1, name: "Candy Cane" },
  "xmas:chocolate_coins": { kind: 2, name: "Chocolate Coins" },
  "xmas:lollipop": { kind: 3, name: "Lollipop" },
  "xmas:fudge": { kind: 4, name: "Fudge" },
  "xmas:toffee": { kind: 5, name: "Toffee" },
  "xmas:gumdrop_red": { kind: 6, name: "Red Gumdrop" },
  "xmas:gumdrop_green": { kind: 6, name: "Green Gumdrop" },
  "xmas:gumdrop_blue": { kind: 6, name: "Blue Gumdrop" },
  "xmas:gumdrop_yellow": { kind: 6, name: "Yellow Gumdrop" },
  "xmas:gumdrop_purple": { kind: 6, name: "Purple Gumdrop" },
};
function showBowl(block, clean, total) {
  const byKind = {};
  for (const id of Object.keys(clean)) { byKind[CANDY[id].kind] = (byKind[CANDY[id].kind] || 0) + clean[id]; }
  const top = Object.keys(byKind).map(Number).sort((a, b) => byKind[b] - byKind[a] || a - b).slice(0, 4);
  // spread kinds over all four quarters (diagonals for two kinds) so the bowl always looks full and mixed
  const spread = [[0, 0, 0, 0], [0, 1, 1, 0], [0, 1, 2, 0], [0, 1, 2, 3]];
  const kinds = top.length ? spread[top.length - 1].map((i) => top[i]) : [];
  const fill = total === 0 ? 0 : total <= 3 ? 1 : total <= 6 ? 2 : 3;
  let perm = block.permutation.withState("xmas:fill", fill);
  for (let i = 0; i < 4; i++) perm = perm.withState("xmas:h" + (i + 1), kinds[i] || 0);
  block.setPermutation(perm);
}

// ---- cookie plate look: three spots show the most common kinds (k = flavor * 6 + shape); pile height is the block type ----
function showPlate(block, clean, total) {
  if (total === 0) { block.setPermutation(BlockPermutation.resolve("xmas:cookie_plate")); return; }
  const top = Object.keys(clean).sort((a, b) => clean[b] - clean[a] || (a < b ? -1 : 1)).slice(0, 3)
    .map((id) => { const c = parseCookie(id); return (c.flavor - 1) * 6 + c.shape; });
  const spread = [[0, 0, 0], [0, 1, 0], [0, 1, 2]][top.length - 1];
  const tier = total <= 3 ? 1 : total <= 6 ? 2 : 3;
  const states = {};   // each kind is split into a (k >> 4) and b (k & 15): enum states max out at 16 values
  for (let i = 0; i < 2; i++) { const k = top[spread[i]]; states["xmas:a" + (i + 1)] = k >> 4; states["xmas:b" + (i + 1)] = k & 15; }
  states["xmas:f3"] = Math.floor(top[spread[2]] / 6);   // third spot shows the flavour as a round cookie (fewer block permutations)
  block.setPermutation(BlockPermutation.resolve("xmas:cookie_plate_" + tier, states));
}

// ---- stored containers (candy bowl, cookie plate): contents live in world data keyed by the block's position ----
const STORES = {
  bowl: { prefix: "bowl:", title: "Candy Bowl", max: 10, unit: "candies", is: (t) => t === "xmas:candy_bowl",
          accepts: (id) => !!CANDY[id], name: (id) => CANDY[id].name, show: showBowl },
  plate: { prefix: "plate:", title: "Cookie Plate", max: 9, unit: "cookies", is: (t) => t.startsWith("xmas:cookie_plate"),
           accepts: (id) => !!parseCookie(id), name: cookieName, show: showPlate },
};
function storeKey(cfg, block) { return cfg.prefix + block.dimension.id + ":" + block.x + "," + block.y + "," + block.z; }
function loadStore(cfg, block) {
  try { const raw = world.getDynamicProperty(storeKey(cfg, block)); return raw ? JSON.parse(raw) : {}; } catch (e) { return {}; }
}
function saveStore(cfg, block, data) {
  const clean = {};
  for (const id of Object.keys(data)) { if (data[id] > 0) clean[id] = data[id]; }
  const total = sumOf(clean);
  world.setDynamicProperty(storeKey(cfg, block), total === 0 ? undefined : JSON.stringify(clean));
  cfg.show(block, clean, total);
}
function openStoreMenu(cfg, player, block) {
  const dimension = block.dimension;
  const loc = { x: block.x, y: block.y, z: block.z };
  const data = loadStore(cfg, block);
  const ids = Object.keys(data).filter((id) => data[id] > 0);
  const form = new ActionFormData().title(cfg.title).body(sumOf(data) + " / " + cfg.max + " " + cfg.unit + ". Tap one to take it out.");
  for (const id of ids) form.button(cfg.name(id) + "  x" + data[id]);
  form.button("Take everything");
  form.show(player).then((res) => {
    if (res.canceled || res.selection === undefined) return;
    const b = dimension.getBlock(loc);
    if (!b || !cfg.is(b.typeId)) return;
    const cur = loadStore(cfg, b);
    if (res.selection >= ids.length) {
      for (const id of Object.keys(cur)) giveItem(player, id, cur[id]);
      saveStore(cfg, b, {});
    } else {
      const id = ids[res.selection];
      if (cur[id] > 0) { cur[id] -= 1; giveItem(player, id, 1); saveStore(cfg, b, cur); }
    }
  }).catch((e) => console.warn("xmas " + cfg.title + " menu error: " + e));
}
function storeComponent(cfg) {
  return {
    onPlayerInteract(event) {
      try {
        const { block, player, dimension } = event;
        if (!player) return;
        const inv = player.getComponent("minecraft:inventory").container;
        const slotIndex = player.selectedSlotIndex;
        const held = inv.getItem(slotIndex);
        const data = loadStore(cfg, block);
        const total = sumOf(data);
        if (held && cfg.accepts(held.typeId)) {
          if (total >= cfg.max) { say(player, "The " + cfg.title.toLowerCase() + " is full"); return; }
          const n = player.isSneaking ? Math.min(held.amount, cfg.max - total) : 1;
          data[held.typeId] = (data[held.typeId] || 0) + n;
          if (String(player.getGameMode()).toLowerCase() !== "creative") {
            if (held.amount > n) { held.amount -= n; inv.setItem(slotIndex, held); }
            else inv.setItem(slotIndex, undefined);
          }
          saveStore(cfg, block, data);
          try { dimension.playSound("random.pop", block.center()); } catch (e) {}
          say(player, cfg.title + ": " + (total + n) + " / " + cfg.max);
        } else if (!held) {
          if (total === 0) { say(player, "The " + cfg.title.toLowerCase() + " is empty"); return; }
          openStoreMenu(cfg, player, block);
        }
      } catch (e) {
        console.warn("xmas " + cfg.title + " error: " + e);
      }
    },
    onPlayerBreak(event) {
      try {
        const { block, dimension } = event;
        const data = loadStore(cfg, block);
        for (const id of Object.keys(data)) {
          for (let left = data[id]; left > 0; left -= 64) dimension.spawnItem(new ItemStack(id, Math.min(left, 64)), block.center());
        }
        world.setDynamicProperty(storeKey(cfg, block), undefined);
      } catch (e) {
        console.warn("xmas " + cfg.title + " break error: " + e);
      }
    },
  };
}

// ---- placeable cakes: right-click eats a slice, 7 slices per cake ----
system.beforeEvents.startup.subscribe((startup) => {
  startup.blockComponentRegistry.registerCustomComponent("xmas:cake", {
    onPlayerInteract(event) {
      try {
        const { block, player, dimension } = event;
        if (!player) return;
        const bites = block.permutation.getState("xmas:bites");
        player.addEffect("saturation", 2, { amplifier: 0, showParticles: false });
        giveJolly(player);
        try { dimension.playSound("random.eat", block.center()); } catch (e) {}
        if (bites >= 6) {
          block.setType("minecraft:air");
        } else {
          block.setPermutation(block.permutation.withState("xmas:bites", bites + 1));
        }
      } catch (e) {
        console.warn("xmas cake error: " + e);
      }
    },
  });
  startup.blockComponentRegistry.registerCustomComponent("xmas:cookie_plate", storeComponent(STORES.plate));
  startup.blockComponentRegistry.registerCustomComponent("xmas:candy_bowl", storeComponent(STORES.bowl));
});
