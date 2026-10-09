import { world, system, ItemStack, BlockPermutation, GameMode } from "@minecraft/server";

// ---- Coin Press: a two-block slot machine. Hold gold nuggets (1 coin each) or gold ingots (9 coins each) and use it:
// the lever pulls, the reels spin and the coins drop out. Sneak to press the whole stack at once.
const RATES = { "minecraft:gold_nugget": 1, "minecraft:gold_ingot": 9 };
const BOTTOM = "market:slot_machine", TOP = "market:slot_machine_top";
const spinning = new Set();

function give(player, stack) {
  const left = player.getComponent("minecraft:inventory").container.addItem(stack);
  if (left) player.dimension.spawnItem(left, player.location);
}

function halves(block) {
  const bottom = block.typeId === TOP ? block.below() : block;
  return { bottom, top: bottom.above() };
}

function pressCoins(player, block) {
  const { bottom, top } = halves(block);
  if (!top || top.typeId !== TOP) return;
  const key = `${bottom.x},${bottom.y},${bottom.z}`;
  if (spinning.has(key)) return;
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
  const dim = bottom.dimension, c = bottom.center();
  spinning.add(key);
  top.setPermutation(top.permutation.withState("market:lever", 1));
  dim.playSound("random.click", c, { pitch: 0.8 });
  let tick = 0;
  const run = system.runInterval(() => {
    try {
      const t = dim.getBlock(top.location);
      if (!t || t.typeId !== TOP) { system.clearRun(run); spinning.delete(key); return; }
      tick++;
      if (tick < 12) {                                              // reels spin
        t.setPermutation(t.permutation.withState("market:spin", tick % 4).withState("market:lever", tick < 4 ? 1 : 0));
        if (tick % 2 === 0) dim.playSound("note.hat", c, { pitch: 1.2 + tick * 0.05, volume: 0.5 });
        return;
      }
      system.clearRun(run);
      spinning.delete(key);
      t.setPermutation(t.permutation.withState("market:spin", Math.floor(Math.random() * 4)).withState("market:lever", 0));
      let coins = used * rate;
      while (coins > 0) {
        const n = Math.min(64, coins);
        give(player, new ItemStack("market:gold_coin", n));
        coins -= n;
      }
      dim.playSound("random.orb", c, { pitch: 1.4 });
      dim.playSound("note.bell", c, { pitch: 1.6 });
      try { dim.spawnParticle("minecraft:villager_happy", { x: c.x, y: c.y + 1.2, z: c.z }); } catch (e) {}
      player.onScreenDisplay.setActionBar(`§6+${used * rate} Gold Coin${used * rate > 1 ? "s" : ""}`);
    } catch (e) { system.clearRun(run); spinning.delete(key); }
  }, 2);
}

function placeTop(block) {
  const above = block.above();
  if (!above || !above.isAir) {                                     // no room: give the press back
    block.dimension.spawnItem(new ItemStack("market:coin_press", 1), block.center());
    block.setType("minecraft:air");
    return;
  }
  const dir = block.permutation.getState("minecraft:cardinal_direction");
  above.setPermutation(BlockPermutation.resolve(TOP, { "minecraft:cardinal_direction": dir }));
}

function breakPair(block, player, brokenType) {
  if (brokenType === BOTTOM) {
    const top = block.above();
    if (top && top.typeId === TOP) top.setType("minecraft:air");
  } else {
    const bottom = block.below();
    if (bottom && bottom.typeId === BOTTOM) {
      bottom.setType("minecraft:air");
      if (player && player.getGameMode() !== GameMode.Creative)
        bottom.dimension.spawnItem(new ItemStack("market:coin_press", 1), bottom.center());
    }
  }
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
    onPlace(e) { if (e.block.typeId === BOTTOM) system.run(() => placeTop(e.dimension.getBlock(e.block.location))); },
    onPlayerBreak(e) {
      const type = e.brokenBlockPermutation.type.id, loc = e.block.location, p = e.player;
      system.run(() => breakPair(e.dimension.getBlock(loc), p, type));
    },
  });
});
