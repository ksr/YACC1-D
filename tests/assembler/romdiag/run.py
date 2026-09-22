#!/usr/bin/env python3
"""tests/assembler/romdiag/run.py - assemble romdiag.asm, compare with the committed image/binary, and step it through
its stages on the microcode emulator with the input line flipped every 100,000 steps."""
import os, sys, shutil, subprocess, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
ASM = os.path.join(ROOT, "software/assembler/asm"); DEF = os.path.join(ROOT, "software/assembler/yacc1.def")
UCEMU = os.path.join(ROOT, "software/ucemu/y1ucemu"); IMG2BIN = os.path.join(ROOT, "tools/img2bin.py")
EXPECT = ["LED=25", "ON", "LED=AA", "LED=20", "LED=11", "LED=03", "LED=01", "LED=02", "LED=FF", "LED=55", "LED=00", "LED=01", "LED=02"]


def main():
    failed = 0
    d = tempfile.mkdtemp()
    shutil.copy(os.path.join(HERE, "romdiag.asm"), d); shutil.copy(DEF, d); open(os.path.join(d, "rcasm.rc"), "w").write("-h\n")
    subprocess.run([ASM, "romdiag", "-d=yacc1"], cwd=d, capture_output=True, text=True)
    if open(os.path.join(d, "romdiag.img")).read() != open(os.path.join(HERE, "romdiag.img")).read(): print("FAIL romdiag.img differs from the assembly"); failed += 1
    else: print("PASS romdiag.img == assembled")
    subprocess.run([sys.executable, IMG2BIN, os.path.join(d, "romdiag.img"), os.path.join(d, "romdiag.bin"), "--base", "0xE000",
                    "--end", "0x10000", "--fill", "0xFF", "--size", "8192"], capture_output=True)
    if open(os.path.join(d, "romdiag.bin"), "rb").read() != open(os.path.join(HERE, "romdiag.bin"), "rb").read(): print("FAIL romdiag.bin differs"); failed += 1
    else: print("PASS romdiag.bin == img2bin of the image")
    r = subprocess.run([UCEMU, "-x", "-f", os.path.join(HERE, "romdiag.img"), "-s", "0x25", "-i", "0", "-I", "100000", "-L", "-l", "2200000"],
                       capture_output=True, text=True)
    got = [l for l in r.stderr.splitlines() if l.startswith(("LED=", "ON", "OFF"))]
    clean = "bus fights: 0 in 0" in r.stderr
    if got[:len(EXPECT)] == EXPECT and clean: print("PASS stages on the microcode emulator: %s" % " ".join(g[4:] if g.startswith("LED=") else g for g in got[:len(EXPECT)]))
    else: print("FAIL stages: %s clean=%s" % (got[:len(EXPECT)], clean)); failed += 1
    print("%d failed" % failed); sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
