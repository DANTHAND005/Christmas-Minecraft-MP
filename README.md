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
Building blocks (candy blocks, Christmas light path): run `python3 tools/make_blocks.py` after `tools/make_decor.py`.
