#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""mkfont.py - the window kernel's font as assembly (2026-11-20): firmware/video/chargen-v40.bin's codes $20-$7E, the
video card V4's own glyphs, 16 bytes each (the scan lines from the top, bit 7 the left dot), as the label WK_FONT.

  python3 os/wm/mkfont.py > wkfont.inc

os/wm/wmk.asm (and tests/wm/wkdemo.asm) INCLUDE it last; os/Makefile and tests/wm/run.py make it."""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def text():
    cg = open(os.path.join(ROOT, "firmware/video/chargen-v40.bin"), "rb").read()
    return ("; wkfont.inc - made by os/wm/mkfont.py from firmware/video/chargen-v40.bin: do not edit\nWK_FONT:\n" +
            "".join("        DB " + ", ".join("0%02xh" % b for b in cg[c * 16:c * 16 + 16]) + "\n" for c in range(32, 127)))


if __name__ == "__main__":
    sys.stdout.write(text())
