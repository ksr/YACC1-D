# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""python3 software/gatemodel [options] - the video card's bus path from its netlist (2026-10-11).

  -o FILE        write the C header for y1ucemu -G (software/ucemu/videogate.h; the ucemu Makefile does this)
  --check FILE   exit 1 if FILE differs from what would be generated (tests/video/gate.py)
  --describe     each revision: the netlist, the board corrections, the settings and reworks with their documents, the
                 chips on the bus path and the ones checked to be off it
  --table REV    the decode of one revision, one line per bus-input combination
"""
import os, sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "gatemodel"

from gatemodel import video          # noqa: E402


def main(argv):
    if "-o" in argv:
        path = argv[argv.index("-o") + 1]
        open(path, "w").write(video.generate())
        return 0
    if "--check" in argv:
        path = argv[argv.index("--check") + 1]
        same = os.path.exists(path) and open(path).read() == video.generate()
        print("%s: %s" % (path, "current" if same else "DIFFERS from the netlist and software/gatemodel (regenerate with -o)"))
        return 0 if same else 1
    if "--describe" in argv:
        print("\n\n".join(video.Card(r).describe() for r in video.REVS)); return 0
    if "--table" in argv:
        card = video.Card(argv[argv.index("--table") + 1]); sig = video.index_signals([card])
        print(" ".join(sig))
        for i, r in enumerate(video.table(card, sig)):
            print("%s  ram=%-5s crtc=%-5s rs=%d latch=%d %s %s" % (format(i, "0%db" % len(sig))[::-1], r["ram"], r["crtc"], r["rs"], r["latch"],
                                                              "; ".join(r["events"]), r["undriven"]))
        return 0
    print(__doc__); return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
