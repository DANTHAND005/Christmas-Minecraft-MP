import { world, system, ItemStack } from "@minecraft/server";

// ---- Coin Press: hold gold nuggets (1 coin each) or gold ingots (9 coins each) and use the press.
// Sneak to press the whole stack at once.
const RATES = { "minecraft:gold_nugget": 1, "minecraft:gold_ingot": 9 };

function give(player, stack) {
  const left = player.getComponent("minecraft:inventory").container.addItem(stack);
  if (left) player.dimension.spawnItem(left, player.location);
}

function pressCoins(player, block) {
  const inv = player.getComponent("minecraft:inventory").container;
  const slot = player.selectedSlotIndex;
  const held = inv.getItem(slot);
  const rate = held && RATES[held.typeId];
  if (!rate) {
    player.onScreenDisplay.setActionBar("§6Hold gold nuggets or gold ingots to press them into coins");
    return;
  }
  const used = player.isSneaking ? held.amount : 1;
  if (used === held.amount) inv.setItem(slot, undefined);
  else { held.amount -= used; inv.setItem(slot, held); }
  let coins = used * rate;
  while (coins > 0) {
    const n = Math.min(64, coins);
    give(player, new ItemStack("market:gold_coin", n));
    coins -= n;
  }
  const c = block.center();
  block.dimension.playSound("random.anvil_land", c, { volume: 0.4, pitch: 1.8 });
  block.dimension.playSound("random.orb", c, { pitch: 1.4 });
  try { block.dimension.spawnParticle("minecraft:villager_happy", { x: c.x, y: c.y + 0.6, z: c.z }); } catch (e) {}
  player.onScreenDisplay.setActionBar(`§6+${used * rate} Gold Coin${used * rate > 1 ? "s" : ""}`);
}

// ---- Market stalls: face the player who set them up; sneak + hit packs a stall back into its item.
world.afterEvents.entitySpawn.subscribe(({ entity, cause }) => {
  if (cause !== "Spawned" || !entity.typeId.startsWith("market:stall_")) return;
  const p = entity.dimension.getPlayers({ location: entity.location, maxDistance: 12, closest: 1 })[0];
  const yaw = p ? Math.round((p.getRotation().y + 180) / 90) * 90 : 0;
  const l = entity.location;
  entity.teleport({ x: Math.floor(l.x) + 0.5, y: l.y, z: Math.floor(l.z) + 0.5 }, { rotation: { x: 0, y: yaw } });
});

world.afterEvents.entityHitEntity.subscribe(({ damagingEntity: p, hitEntity: stall }) => {
  if (p.typeId !== "minecraft:player" || !stall.typeId.startsWith("market:stall_")) return;
  if (!p.isSneaking) {
    p.onScreenDisplay.setActionBar("§7Use the stall to trade - sneak + hit to pack it up");
    return;
  }
  const key = stall.typeId.slice("market:stall_".length);
  stall.dimension.spawnItem(new ItemStack(`market:${key}_stall`, 1), stall.location);
  stall.dimension.playSound("random.pop", stall.location);
  stall.remove();
});

system.beforeEvents.startup.subscribe((startup) => {
  startup.blockComponentRegistry.registerCustomComponent("market:coin_press", {
    onPlayerInteract(e) { if (e.player) system.run(() => pressCoins(e.player, e.block)); },
  });
});
