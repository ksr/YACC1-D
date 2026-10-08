#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""tests/y1term/run.py - tools/y1term.py --send against the microcode emulator through a pty (2026-10-08).

good.bas: lower case, a tab, a blank line and a '#' comment, FOR/NEXT; sent with --new --run, must exit 0 and RUN
must print Hello, 1, 2, 3 and 21 (6 lines sent). bad.bas: line 20 is `print !`; must exit 1 and name it (file line 2) as SYNTAX ERROR, and
lines 10 and 30 must still be stored (a LIST through the same pty shows them).
"""
import os, sys, pty, tty, select, subprocess, threading

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
UCEMU = os.path.join(ROOT, "software/ucemu/y1ucemu")


def with_emulator(fn):
    m, s = pty.openpty(); tty.setraw(m); tty.setraw(s)
    emu = subprocess.Popen([UCEMU, "-x", "-m", "-l", "400000000"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    stop = threading.Event()

    def pump():
        while not stop.is_set():
            r, _, _ = select.select([m, emu.stdout], [], [], 0.05)
            if m in r:
                b = os.read(m, 256)
                if b: emu.stdin.write(b); emu.stdin.flush()
            if emu.stdout in r:
                b = os.read(emu.stdout.fileno(), 256)
                if not b: break
                os.write(m, b)
    t = threading.Thread(target=pump, daemon=True); t.start()
    try:
        return fn(os.ttyname(s))
    finally:
        stop.set(); emu.kill(); emu.wait()


def y1term(port, *args):
    return subprocess.run([sys.executable, os.path.join(ROOT, "tools/y1term.py"), "--port", port, "--delay", "0",
                           "--timeout", "120", "--run-timeout", "300"] + list(args),
                          capture_output=True, text=True, timeout=900)


def main():
    if not os.path.exists(UCEMU): sys.exit("missing %s (run `make` at the repo root)" % UCEMU)
    failed = 0
    r = with_emulator(lambda p: y1term(p, "--send", os.path.join(HERE, "good.bas"), "--new", "--run"))
    out = "\n".join(l.strip() for l in r.stdout.replace("\r", "\n").split("\n") if l.strip())
    want = ["Hello\n1\n2\n3\n21"]
    ok = (r.returncode == 0 and all(w in out for w in want) and "6 lines sent" in r.stderr
          and "all accepted" in r.stderr)
    print("%-5s %s" % ("good", "PASS  6 lines sent, RUN printed Hello 1 2 3 21" if ok else "FAIL\n" + out[-600:] + r.stderr[-400:]))
    failed += not ok

    def bad(p):
        r1 = y1term(p, "--send", os.path.join(HERE, "bad.bas"), "--new")
        lst = os.path.join(HERE, "build_list.bas")
        open(lst, "w").write("list\n")
        r2 = y1term(p, "--send", lst)
        os.remove(lst)
        return r1, r2
    r1, r2 = with_emulator(bad)
    o2 = "\n".join(l.strip() for l in r2.stdout.replace("\r", "\n").split("\n") if l.strip())
    ok = (r1.returncode == 1 and "line 2: 20 print !  -> SYNTAX ERROR" in r1.stderr
          and "10 PRINT 1" in o2 and "30 PRINT 3" in o2 and "20 PRINT" not in o2)
    print("%-5s %s" % ("bad", "PASS  line 20 reported as SYNTAX ERROR, lines 10 and 30 stored" if ok
                       else "FAIL\n" + r1.stderr[-400:] + o2[-400:]))
    failed += not ok
    print("%d failed" % failed)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
