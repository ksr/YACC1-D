# Terminus Font 4.49.1, bold 8 x 16, unmodified — the glyphs of the video card V4's character generator

`ter-u16b.bdf` and `OFL.TXT` are **exactly as distributed** in Terminus Font 4.49.1 by Dimitar Toshkov Zhekov. The
font file is the source `tools/vidsim.py chargen --card v4` reads to write `firmware/video/chargen-v40.bin`, the
image for the V4 card's AT28C64B (`firmware/video/README.md`); `tests/video/overlay_check.py`, in `make check`, checks
that the image is what the tool writes from this file. Nothing else of the font is kept: of its sizes and weights
only the bold of 8 x 16 dots, chosen 2026-11-14 from seven candidates drawn as the card's screen
(`docs/cards/video-v4.md` section 13).

| | |
|---|---|
| Home page | https://terminus-font.sourceforge.net/ |
| Downloaded | 2026-11-14, `curl -L https://sourceforge.net/projects/terminus-font/files/terminus-font-4.49/terminus-font-4.49.1.tar.gz/download` (the project's own files on SourceForge, nothing else) |
| Archive | `terminus-font-4.49.1.tar.gz`, 648,345 bytes; SHA-256 `d961c1b781627bf417f9b340693d64fc219e0113ad3a3af1a3424c7aa373ef79` (the archive itself is not kept; two of its files are, with their dates) |
| Licence | the SIL Open Font License, Version 1.1, in `OFL.TXT`: the font may be used, copied, changed and redistributed, with its copyright notice and the licence, and not sold by itself; a changed version keeps the licence and may not carry the reserved name |
| Copyright | (C) 2020 Dimitar Toshkov Zhekov, with Reserved Font Name "Terminus Font" |

`firmware/video/chargen-v40.bin` is made from this font - its glyphs unchanged, 128 of them chosen and laid out for
the card, each with its inverse - and is so a modified version in the licence's words: it is under the same licence,
and it is not called by the font's name.

SHA-256 of the two files as unpacked:

```
92861fecd6f94c5ecc764fc43df5a69eb000ae13a75f652c6525db0495274f0a  ter-u16b.bdf
c14f8d795784a547ea35e69c51dee2957bb71a1cdb492ec5321e4b61d3d97630  OFL.TXT
```
