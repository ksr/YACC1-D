#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""monvariant.py - the monitor's source for one of its two builds on the branch video-v2 (2026-11-14).

  monvariant.py v4 [IN.asm] [OUT.asm]     the video card V4's ROM (default: firmware/monitor/monitor.asm -> stdout)
  monvariant.py v2 [IN.asm] [OUT.asm]     the V2.0 ROM: the source as it stands, its tags taken off

The assembler has no conditional assembly, so firmware/monitor/monitor.asm carries both builds marked line by line:
a line that ends in the tag ;;V2 is the V2.0 ROM's only, a line that begins ;;V4 (and a blank) is the V4 ROM's only.
As the file stands the ;;V4 lines are comments: assembling it gives the V2.0 ROM. For v4 this drops the ;;V2 lines
and takes the tag off the ;;V4 lines. Plain Python."""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def variant(text, card):
    out = []
    for line in text.split("\n"):
        mine, other = (";;V4", ";;V2") if card == "v4" else (";;V2", ";;V4")
        if line.startswith(";;V4 ") or line == ";;V4":       # a V4 line: a comment in the file as it stands
            if card == "v4": out.append(line[5:])
            continue
        if re.search(r";;V2\s*$", line):                     # a V2.0 line
            if card == "v2": out.append(re.sub(r"\s*;;V2\s*$", "", line))
            continue
        out.append(line)
    return "\n".join(out)


def main():
    a = sys.argv[1:]
    if not a or a[0] not in ("v2", "v4"):
        sys.exit(__doc__)
    src = a[1] if len(a) > 1 else os.path.join(ROOT, "firmware", "monitor", "monitor.asm")
    text = variant(open(src).read(), a[0])
    if len(a) > 2: open(a[2], "w").write(text)
    else: sys.stdout.write(text)


if __name__ == "__main__":
    main()
