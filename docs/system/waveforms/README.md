# docs/system/waveforms — index register load / read timing

Two WaveDrom timing diagrams drawn in 2020-08 for the Index Register card: `REG-LD` (register load: -REG-FUNC-LD,
REG-LD-ID, -REG-LD-LO, valid bus data) and `REG-RD` (register read: -BUS-EN, REG-RD-ID, -REG-FUNC-RD, -REG-RD-LO, data
out). Each is kept as its WaveJSON source (`.json`, paste into https://wavedrom.com/editor.html to edit or re-render)
and as the rendered picture (`.svg`, opens in any browser).

They were migrated as Safari web archives of the WaveDrom editor page (`Utilities/Waveforms/*.webarchive` in YACCS);
those carried 600 KB of the site's JavaScript each, including Google's public analytics key, which GitHub's secret
scanning flagged on 2026-09-21. The archives were removed (skip rule in `tools/migrate_dryrun.py`) and the two diagrams
extracted from them; nothing of Ken's was lost.
