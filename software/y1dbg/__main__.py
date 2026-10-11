# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""y1dbg - the YACC1 debugger: the microcode-level emulator (software/ucemu/y1ucemu -D) with a live video screen.

  python3 software/y1dbg [options]            (or, in software/: python3 -m y1dbg)
  python3 software/y1dbg --ui web             the browser debugger on http://127.0.0.1:8803/

Starts y1ucemu with the tree's control store and ROM (BASIC + monitor, as -m does), stopped at the reset, with the
monitor's and BASIC's symbols loaded, and opens the terminal UI (or, with --ui web, serves the browser debugger on
127.0.0.1). With -c or --script the commands run first and their output is printed; then a UI opens only with --ui tui
or web (tui is the default without commands), so a script ends and the emulator with it. `help` in the UI lists the
commands; software/y1dbg/README.md has the rest.
"""
import argparse, os, sys

if __package__ in (None, ""):              # run as a directory (python3 software/y1dbg): import the package
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "y1dbg"

from y1dbg.emu import Emulator, EmulatorError, ROOT     # noqa: E402
from y1dbg.debugger import Symbols                      # noqa: E402
from y1dbg.shell import Shell                           # noqa: E402

DEF_SYMS = [os.path.join(ROOT, "firmware/monitor/monitor.lst"), os.path.join(ROOT, "firmware/basic/basic.lst")]


def split_commands(text):
    """'a; b' -> ['a', 'b']; '\\;' is a semicolon inside a command"""
    out, cur, i = [], "", 0
    while i < len(text):
        if text[i] == "\\" and text[i + 1:i + 2] == ";": cur += ";"; i += 2; continue
        if text[i] == ";": out.append(cur); cur = ""; i += 1; continue
        cur += text[i]; i += 1
    out.append(cur)
    return [c.strip() for c in out if c.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="y1dbg", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-f", "--load", action="append", default=[], help="an Intel-hex image to load (repeatable; y1ucemu -f)")
    ap.add_argument("-u", "--ucode", help="another control store (y1ucemu -u; default the tree's test.hex)")
    ap.add_argument("--disk", help="a CompactFlash image (y1ucemu -c)")
    ap.add_argument("--no-rom", action="store_true", help="no BASIC + monitor ROM (y1ucemu without -m): an image is the ROM")
    ap.add_argument("--no-video", action="store_true", help="no video card (y1ucemu -N)")
    ap.add_argument("--video-rev", metavar="REV", help="the video card at gate level from its netlist (y1ucemu -G REV): v1.0 = "
                                                       "as fitted; `software/ucemu/y1ucemu -G list` names the others")
    ap.add_argument("--emu-arg", action="append", default=[], help="another y1ucemu option, as it is (repeatable), e.g. --emu-arg=-H")
    ap.add_argument("--emu", default=None, help="the emulator (default software/ucemu/y1ucemu)")
    ap.add_argument("--sym", action="append", default=[], help="symbols from an RC/asm listing (repeatable; default the monitor's and BASIC's)")
    ap.add_argument("-c", "--command", action="append", default=[], help="commands to run, separated by ';' (repeatable)")
    ap.add_argument("--script", help="a file of commands, one a line")
    ap.add_argument("--ui", choices=["tui", "web", "none"], help="tui (the default without -c/--script), web (the browser) or none")
    ap.add_argument("--port", type=int, default=None, help="--ui web: the port on 127.0.0.1 (default 8803; 0 = any free port)")
    ap.add_argument("--chargen", help="--ui web: draw with this 2732 character-generator image (read from the card's EPROM) "
                                      "instead of tools/vidsim.py's font")
    ap.add_argument("--timeout", type=float, default=60.0, help="seconds a scripted c / until / waitfor may run (default 60)")
    ap.add_argument("--log", help="the emulator's stderr to this file (the UI's default: discarded)")
    a = ap.parse_args(argv)

    lines = []
    if a.script: lines += open(a.script).read().splitlines()
    for c in a.command: lines += split_commands(c)
    ui = a.ui or ("none" if lines else "tui")

    args = [] if a.no_rom else ["-m"]
    for f in a.load: args += ["-f", os.path.abspath(f)]
    if a.ucode: args += ["-u", os.path.abspath(a.ucode)]
    if a.disk: args += ["-c", os.path.abspath(a.disk)]
    if a.no_video: args += ["-N"]
    if a.video_rev: args += ["-G", a.video_rev]
    args += a.emu_arg
    log = open(a.log, "w") if a.log else (open(os.devnull, "w") if ui == "tui" else None)
    kw = {"exe": a.emu} if a.emu else {}
    try:
        emu = Emulator(args, log=log, **kw)
    except EmulatorError as e:
        print("y1dbg: %s" % e, file=sys.stderr); return 2
    syms = Symbols()
    for f in a.sym or ([] if a.no_rom else DEF_SYMS):
        if os.path.exists(f): syms.load(f)
    sh = Shell(emu, syms, timeout=a.timeout)
    ran = []                                           # the commands' output, for the browser's command log
    try:
        for line in lines:
            if line.strip() in ("q", "quit", "exit"): break
            out = sh.exec(line)
            print("> " + line)
            if out: print(out)
            sys.stdout.flush()
            ran += ["> " + line] + ([out] if out else [])
        if ui == "tui":
            from y1dbg import tui
            tui.run(sh)
        elif ui == "web":
            from y1dbg import web
            web.serve(sh, web.PORT if a.port is None else a.port, a.chargen, lambda t: print(t, flush=True), ran)
    finally:
        emu.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
