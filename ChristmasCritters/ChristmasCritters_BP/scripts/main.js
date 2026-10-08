import { world, system, ItemStack } from "@minecraft/server";

const PETS = new Set(["xmas:reindeer", "xmas:penguin", "xmas:gingerbread_man", "xmas:toy_soldier"]);
const ICE = new Set(["minecraft:ice", "minecraft:packed_ice", "minecraft:blue_ice", "minecraft:frosted_ice"]);
const any = (list) => list[Math.floor(Math.random() * list.length)];
const stack = (id, n = 1) => { try { return new ItemStack(id, n); } catch (e) { return undefined; } };   // undefined = that add-on isn't on
const isCreative = (p) => String(p.getGameMode()).toLowerCase() === "creative";
const niceName = (e) => e.nameTag || e.typeId.slice(5).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

function useOneFromHand(player) {
  if (isCreative(player)) return;
  const inv = player.getComponent("minecraft:inventory")?.container;
  const it = inv?.getItem(player.selectedSlotIndex);
  if (!it) return;
  if (it.amount <= 1) inv.setItem(player.selectedSlotIndex, undefined);
  else { it.amount -= 1; inv.setItem(player.selectedSlotIndex, it); }
}

function hearts(entity) {
  try { entity.dimension.spawnParticle("minecraft:heart_particle", { x: entity.location.x, y: entity.location.y + 1, z: entity.location.z }); } catch (e) {}
}

// ---- sneak + tap your own pet: sit / stay, again: follow. Gingerbread men also take any Oven cookie to tame ----
world.beforeEvents.playerInteractWithEntity.subscribe((e) => {
  const { player, target, itemStack } = e;
  if (!PETS.has(target.typeId)) return;
  const tame = target.getComponent("minecraft:tameable");
  if (player.isSneaking && tame?.isTamed && tame.tamedToPlayerId === player.id) {
    e.cancel = true;                                   // don't mount the reindeer etc.
    system.run(() => {
      const sitting = target.getProperty("xmas:sitting");
      target.triggerEvent(sitting ? "xmas:stand" : "xmas:sit");
      player.onScreenDisplay.setActionBar(niceName(target) + (sitting ? " is following you" : " is staying here"));
    });
    return;
  }
  if (target.typeId === "xmas:gingerbread_man" && !tame?.isTamed && itemStack?.typeId.startsWith("xmas:cookie")) {
    e.cancel = true;
    system.run(() => {
      try { target.getComponent("minecraft:tameable").tame(player); } catch (err) { return; }
      useOneFromHand(player);
      hearts(target);
    });
  }
});

// ---- toy soldier kit: place a soldier that already belongs to you ----
system.beforeEvents.startup.subscribe((startup) => {
  startup.itemComponentRegistry.registerCustomComponent("xmas:soldier_kit", {
    onUseOn(e) {
      const player = e.source, b = e.block;
      if (!player || player.typeId !== "minecraft:player") return;
      system.run(() => {
        const s = b.dimension.spawnEntity("xmas:toy_soldier", { x: b.x + 0.5, y: b.y + 1, z: b.z + 0.5 });
        try { s.getComponent("minecraft:tameable").tame(player); } catch (err) {}
        b.dimension.playSound("random.anvil_use", s.location, { volume: 0.5, pitch: 1.6 });
        useOneFromHand(player);
      });
    },
  });
});

// ---- drops that come from the other two add-ons (fallbacks keep it working without them) ----
world.afterEvents.entityDie.subscribe((e) => {
  const d = e.deadEntity;
  let loot;
  if (d.typeId === "xmas:gingerbread_man") loot = stack("xmas:cookie_gingerbread_gingerbread_man", 1 + Math.floor(Math.random() * 2)) || stack("minecraft:cookie", 2);
  else if (d.typeId === "xmas:toy_soldier") loot = stack("santa:toy_parts", 1 + Math.floor(Math.random() * 3)) || stack("minecraft:iron_nugget", 4);
  if (!loot) return;
  try { d.dimension.spawnItem(loot, d.location); } catch (err) {}
});

// ---- santa: visits on snowy nights, leaves a present when you get close, then vanishes ----
const PRESENTS = ["santa:present", "santa:present_red", "santa:present_cyan", "santa:present_blue", "santa:present_purple",
                  "santa:present_candy", "santa:present_gold", "santa:present_pink", "santa:present_orange", "santa:present_silver"];
const FALLBACK_GIFTS = [["minecraft:golden_apple", 1], ["minecraft:cookie", 8], ["minecraft:emerald", 4], ["minecraft:cake", 1]];
function santaVisit(santa) {
  if (santa.getDynamicProperty("gifted")) return;
  santa.setDynamicProperty("gifted", true);
  const gift = stack(any(PRESENTS)) || stack(...any(FALLBACK_GIFTS));
  const at = santa.location;
  santa.dimension.spawnItem(gift, at);
  santa.dimension.playSound("note.bell", at, { volume: 1, pitch: 1.2 });
  system.runTimeout(() => {
    try {
      for (let i = 0; i < 8; i++) santa.dimension.spawnParticle("minecraft:snowflake_particle", { x: at.x + Math.random() - 0.5, y: at.y + 1 + Math.random(), z: at.z + Math.random() - 0.5 });
      santa.triggerEvent("xmas:leave");
    } catch (err) {}
  }, 60);
}

// ---- elves turn up in villages: each villager gets one roll, max 2 elves around any villager ----
function maybeElf(villager) {
  if (villager.getDynamicProperty("xmas_elf_roll")) return;
  villager.setDynamicProperty("xmas_elf_roll", true);
  if (Math.random() > 0.3) return;
  const dim = villager.dimension, l = villager.location;
  if (dim.getEntities({ type: "xmas:elf", location: l, maxDistance: 32 }).length >= 2) return;
  try { dim.spawnEntity("xmas:elf", { x: l.x + 1, y: l.y, z: l.z + 1 }); } catch (err) {}
}

let tick = 0;
system.runInterval(() => {
  tick++;
  for (const player of world.getAllPlayers()) {
    const dim = player.dimension, near = { location: player.location, maxDistance: 64 };
    // penguins belly-slide on ice and in water
    for (const p of dim.getEntities({ type: "xmas:penguin", ...near })) {
      try {
        const v = p.getVelocity(), moving = Math.hypot(v.x, v.z) > 0.06;
        const below = dim.getBlock({ x: p.location.x, y: p.location.y - 0.5, z: p.location.z });
        const slide = !p.getProperty("xmas:sitting") && (p.isInWater || (moving && below && ICE.has(below.typeId)));
        if (p.getProperty("xmas:sliding") !== slide) p.setProperty("xmas:sliding", slide);
      } catch (err) {}
    }
    if (tick % 2 === 0) {
      for (const s of dim.getEntities({ type: "xmas:santa", location: player.location, maxDistance: 5 })) santaVisit(s);
    }
    if (tick % 20 === 0) {
      for (const v of dim.getEntities({ type: "minecraft:villager_v2", ...near })) maybeElf(v);
    }
  }
}, 10);
