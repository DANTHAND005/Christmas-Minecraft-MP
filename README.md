# Christmas-Minecraft-MP
Bedrock add-ons: `SantasWorkbench/` and `GingerbreadOven/` hold the unpacked packs.
The big decorations are generated: edit `tools/make_decor.py`, then run
`python3 tools/make_decor.py --preview` (writes `previews/decor_sheet.png`) and zip the
two `SantasWorkbench_*` folders into `dist/SantasWorkbench.mcaddon`.
Before packaging, run `python3 tools/check_packs.py`: it checks recipes, names, models,
textures, script ids and the block-permutation budget for both add-ons.
Christmas Textures (leaves, vines, HUD, chests): `tools/glow_leaves.py`, `tools/christmas_chests.py` (spruce leaf lights) and `tools/christmas_hud.py`
(peppermint hearts, candy-cane hunger, candy-cane hotbar) regenerate their textures; zip the two
zip `ChristmasTextures_RP` into `dist/ChristmasTextures.mcpack`.
Building blocks (candy blocks): run `python3 tools/make_blocks.py` after `tools/make_decor.py`.

Christmas Market (`ChristmasMarket/`): 20 villager market stalls you trade with using gold coins, plus the Coin
Press (gold nugget = 1 coin, gold ingot = 9; sneak to press the whole stack). Run `python3 tools/make_market.py`
(`--preview` writes `previews/market_sheet_*.png`) and zip the two `ChristmasMarket_*` folders into
`dist/ChristmasMarket.mcaddon`. Trades use items from Santa's Workbench and Gingerbread Oven, so install those too.
