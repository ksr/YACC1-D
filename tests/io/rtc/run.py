#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""tests/io/rtc/run.py - the I/O card V1.2's clock in both emulators (2026-11-20; docs/cards/rtc.md,
software/rtcmodel.h with Y1IO_CARD=v1.2). No hardware: the card is designed, not built.

  run.py [-v]      -v prints each run's console output

1. model_test.c, the model on its own: the registers in binary and BCD, 12- and 24-hour, the calendar (leap years,
   99 to 00), UIP's window, SET and the oscillator's DV bits, the day-of-the-week counter, the 114 bytes of RAM,
   register C's flags (UF, PF by the rate, AF with its don't-care bytes, IRQF), the CPU clock, a chip never set, and
   the chip on the host's clock.
2. rtc.asm through the monitor on the instruction-level emulator (int) and the microcode one (uc), with
   Y1RTC_TIME: a YACC1 program finds the chip, reads it, sets it across the end of 2099, waits for seconds to pass
   (they pass on the machine's own clocks, so both emulators print the same), uses the RAM and reads the flags.
3. The same program with no card named: the V1.1 card of the machine, nothing on ports 6 and 7 - the chip is not
   found, and the program still ends.
4. A card or a time that does not exist is refused by both emulators.
"""
import os, re, sys, shutil, subprocess, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
ASM = os.path.join(ROOT, "software/assembler/asm"); DEF = os.path.join(ROOT, "software/assembler/yacc1.def")
EMUS = [("int", os.path.join(ROOT, "software/emulator/emulator")), ("uc", os.path.join(ROOT, "software/ucemu/y1ucemu"))]
LST = open(os.path.join(ROOT, "firmware/monitor/monitor.lst"), errors="replace").read()
MON_EXIT = re.search(r"^([0-9a-f]{4})h: CMD_EXIT\b", LST, re.M).group(1).upper()
WANT = {"RTC": "A5 5A", "REGS": "26 06 80", "FOUND": "1A 0B 14 0C 22", "SET": "58 59 00", "AFTER": "00 01 01 00 00 01",
        "RAM": "11 22 33", "FLAGS": "10 00"}
VERBOSE = "-v" in sys.argv
fails = 0


def check(name, ok, why=""):
    global fails
    print("%-40s %s%s" % (name, "PASS" if ok else "FAIL", "" if ok else "  " + why))
    if not ok: fails += 1


def run(emu, img, env, limit=None):
    # the fast emulator's 0 command ends in the monitor's stop loop, so its run ends at the limit
    uc = emu.endswith("y1ucemu")
    cmd = [emu, "-x", "-m", "-l", str(limit or (400000000 if uc else 20000000))] + (["-E", MON_EXIT] if uc else [])
    e = {k: v for k, v in os.environ.items() if not k.startswith(("Y1IO_", "Y1RTC_")) and k != "Y1_CLOCK"}
    r = subprocess.run(cmd, input=img + b"G3000" + b"0", capture_output=True, env=dict(e, **env), timeout=600)
    out = r.stdout.decode("latin1").replace("\r", "")
    if VERBOSE: print(out[-500:] + r.stderr.decode("latin1")[-300:])
    return r.returncode, out, r.stderr.decode("latin1")


def main():
    d = tempfile.mkdtemp()

    # 1. the model
    exe = os.path.join(d, "model_test")
    r = subprocess.run(["cc", "-O1", "-Wall", "-Wextra", "-Werror", "-o", exe, os.path.join(HERE, "model_test.c")],
                       capture_output=True, text=True)
    check("model_test builds", r.returncode == 0, r.stderr[-400:])
    if r.returncode == 0:
        r = subprocess.run([exe], capture_output=True, text=True)
        check("model_test", r.returncode == 0 and "rtc model: 0 failed" in r.stdout, r.stdout[-800:])

    # 2. a YACC1 program and the chip
    shutil.copy(DEF, d); open(os.path.join(d, "rcasm.rc"), "w").write("-h\n")
    shutil.copy(os.path.join(HERE, "rtc.asm"), d)
    r = subprocess.run([ASM, "rtc", "-d=yacc1"], cwd=d, capture_output=True)
    if not re.search(rb"^0 Errors", r.stdout, re.M): sys.exit("rtc.asm did not assemble:\n" + r.stdout.decode("latin1")[-600:])
    img = open(os.path.join(d, "rtc.img"), "rb").read()
    card = {"Y1IO_CARD": "v1.2", "Y1RTC_TIME": "2026-11-20 12:34:00"}
    got = {}
    for tag, emu in EMUS:
        rc, out, err = run(emu, img, card)
        g = got[tag] = dict(re.findall(r"^(RTC|REGS|FOUND|SET|AFTER|RAM|FLAGS) (.*?) *$", out, re.M))
        check("the clock from a program, %s" % tag, "DONE" in out and g == WANT,
              "\n".join("%s: %s (want %s)" % (k, g.get(k), v) for k, v in WANT.items() if g.get(k) != v) or out[-300:])
    check("the clock from a program, int = uc", got["int"] == got["uc"] and bool(got["int"]))
    rc, out, err = run(EMUS[0][1], img, dict(card, Y1_CLOCK="3500000"))
    g = dict(re.findall(r"^(SET|AFTER|FLAGS) (.*?) *$", out, re.M))
    check("at a 3.5 MHz CPU clock, int", "DONE" in out and all(g.get(k) == WANT[k] for k in g) and len(g) == 3, str(g))

    # 3. the V1.1 card: nothing on ports 6 and 7. The program's waits for a second never end, so the run stops at its limit
    for tag, emu in EMUS:
        rc, out, err = run(emu, img, {}, limit=80000000 if tag == "uc" else 3000000)
        m = re.search(r"^RTC ([0-9A-F]{2} [0-9A-F]{2}) *$", out, re.M)
        check("no clock on the V1.1 card, %s" % tag, bool(m) and m.group(1) != WANT["RTC"] and "REGS" in out and
              "DONE" not in out and (tag != "uc" or m.group(1) == "FF FF"), "RTC %s" % (m and m.group(1)))

    # 4. what does not exist
    for tag, emu in EMUS:
        rc, out, err = run(emu, img, {"Y1IO_CARD": "v9"}, limit=1000)
        check("Y1IO_CARD=v9 is refused, %s" % tag, rc == 2 and "the I/O cards are v1.1 and v1.2" in err, "%d %s" % (rc, err[-120:]))
        rc, out, err = run(emu, img, {"Y1IO_CARD": "v1.2", "Y1RTC_TIME": "tomorrow"}, limit=1000)
        check("Y1RTC_TIME=tomorrow is refused, %s" % tag, rc == 2 and "a time is" in err, "%d %s" % (rc, err[-120:]))

    shutil.rmtree(d)
    print("rtc: %d failed" % fails)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
