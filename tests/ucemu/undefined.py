#!/usr/bin/env python3
"""Undefined opcodes halt cleanly (design review H-4, fixed 2026-09-29).

Until 2026-09-29 the microcode generator left the records of opcodes it never generates all-zero, and every control
line is active-low, so fetching one asserted every strobe at once (-MEM-RD with -MEM-WR, every load and read) for 62
steps of bus fights until COUNT-FAULT stopped the clock. Now each gets the HALT record. This checks, on the tree's
test.hex:
  1. no record is all-zero;
  2. each undefined opcode, fetched from the ROM at reset on the microcode emulator, HALTs after its fetch with no
     bus fight (the same 7 steps as HALT, $03, which is run too as the reference).
"""
import os, sys, subprocess, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
EMU = os.path.join(ROOT, "software/ucemu/y1ucemu")
HEX = os.path.join(ROOT, "firmware/microcode/ucode-generator2/test.hex")
UNDEFINED = [0xA5, 0xAE, 0xF8, 0xF9, 0xFA]      # the opcodes nothing in ucode-generator2 generates

ok = True
records = {int(l[3:5], 16): l[5:-2] for l in open(HEX) if l.startswith("%")}
zero = ["$%02X" % o for o, d in sorted(records.items()) if set(d) == {"0"}]
print("%-34s %s" % ("all-zero records in test.hex", "none" if not zero else "FAIL " + " ".join(zero)))
ok &= not zero

with tempfile.TemporaryDirectory() as tmp:
    for op in [0x03] + UNDEFINED:
        img = os.path.join(tmp, "op.hex")          # one byte at $F000: reset fetches it through FORCE-ROM
        csum = (-(0x01 + 0xF0 + 0x00 + 0x00 + op)) & 0xFF
        open(img, "w").write(":01F00000%02X%02X\n:00000001FF\n" % (op, csum))
        r = subprocess.run([EMU, "-x", "-l", "2000", "-u", HEX, "-f", img], stdin=subprocess.DEVNULL,
                           capture_output=True, text=True)
        status = r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "(no status)"
        good = status.startswith("HALT at F000 after 1 instructions, 7 steps") and "bus fights: 0 " in status
        print("%-34s %s" % ("$%02X%s" % (op, " (HALT)" if op == 0x03 else ""), "PASS" if good else "FAIL: " + status))
        ok &= good

print("undefined opcodes:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
