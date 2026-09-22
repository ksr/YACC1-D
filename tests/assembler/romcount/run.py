#!/usr/bin/env python3
"""tests/assembler/romcount/run.py - assemble romcount.asm, compare with the committed image and binary, and run it on
the microcode emulator with the input-switch line low (mirror the switches) and high (count from the switch value)."""
import os, sys, shutil, subprocess, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
ASM = os.path.join(ROOT, "software/assembler/asm"); DEF = os.path.join(ROOT, "software/assembler/yacc1.def")
UCEMU = os.path.join(ROOT, "software/ucemu/y1ucemu"); IMG2BIN = os.path.join(ROOT, "tools/img2bin.py")


def leds(args, limit):
    r = subprocess.run([UCEMU, "-x", "-f", os.path.join(HERE, "romcount.img"), "-L", "-l", str(limit)] + args,
                       capture_output=True, text=True)
    lines = r.stderr.splitlines()
    fights = [l for l in lines if "bus fights: 0 in 0" in l]
    return [l for l in lines if l.startswith(("LED=", "TIL=", "ON", "OFF"))], bool(fights)


def main():
    failed = 0
    d = tempfile.mkdtemp()
    shutil.copy(os.path.join(HERE, "romcount.asm"), d); shutil.copy(DEF, d); open(os.path.join(d, "rcasm.rc"), "w").write("-h\n")
    r = subprocess.run([ASM, "romcount", "-d=yacc1"], cwd=d, capture_output=True, text=True)
    img = open(os.path.join(d, "romcount.img")).read()
    if img != open(os.path.join(HERE, "romcount.img")).read(): print("FAIL romcount.img differs from the assembly"); failed += 1
    else: print("PASS romcount.img == assembled")
    subprocess.run([sys.executable, IMG2BIN, os.path.join(d, "romcount.img"), os.path.join(d, "romcount.bin"), "--base", "0xE000",
                    "--end", "0x10000", "--fill", "0xFF", "--size", "8192"], capture_output=True)
    if open(os.path.join(d, "romcount.bin"), "rb").read() != open(os.path.join(HERE, "romcount.bin"), "rb").read():
        print("FAIL romcount.bin differs"); failed += 1
    else: print("PASS romcount.bin == img2bin of the image (8192 bytes)")

    got, clean = leds(["-s", "0x25", "-i", "0"], 20000)
    if got == ["LED=25", "TIL=25"] and clean: print("PASS input low: mirrors the switches, no ON")
    else: print("FAIL input low: %s clean=%s" % (got, clean)); failed += 1
    got, clean = leds(["-s", "0x25", "-i", "1"], 1500000)
    if got[:9] == ["LED=25", "TIL=25", "ON", "LED=26", "TIL=26", "LED=27", "TIL=27", "LED=28", "TIL=28"] and clean: print("PASS input high: counts from the switches")
    else: print("FAIL input high: %s clean=%s" % (got[:9], clean)); failed += 1
    got, clean = leds(["-s", "0xFD", "-i", "1"], 1200000)
    l = [g for g in got if g.startswith("LED=")]
    if l[:4] == ["LED=FD", "LED=FE", "LED=FF", "LED=00"] and clean: print("PASS wraps FF -> 00")
    else: print("FAIL wrap: %s" % l[:4]); failed += 1
    print("%d failed" % failed); sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
