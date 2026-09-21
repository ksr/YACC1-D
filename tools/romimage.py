#!/usr/bin/env python3
"""The memory card's 8K ROM image ($E000-$FFFF) built from the SOURCES the emulator loads: firmware/basic/basic.img at
$E000 and firmware/monitor/monitor.img at $F000 (both Intel hex), gaps filled with $FF as on an unprogrammed EEPROM.
Tests compare the chip against this, so "ROM PASS" means "the chip holds exactly what the emulator runs"."""
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def intel_hex(path):
    img = {}
    for l in open(path):
        l = l.strip()
        if l.startswith(":") and l[7:9] == "00":
            n = int(l[1:3], 16); a = int(l[3:7], 16)
            for i in range(n): img[a + i] = int(l[9 + 2 * i:11 + 2 * i], 16)
    return img
def rom_image():
    img = {}
    for f in ("firmware/basic/basic.img", "firmware/monitor/monitor.img"):
        for a, v in intel_hex(os.path.join(ROOT, f)).items():
            assert 0xE000 <= a <= 0xFFFF, "%s defines $%04X outside the ROM" % (f, a)
            assert a not in img, "basic.img and monitor.img overlap at $%04X" % a
            img[a] = v
    return bytes(img.get(a, 0xFF) for a in range(0xE000, 0x10000))
if __name__ == "__main__":
    r = rom_image(); print("8192 bytes; %d defined by basic.img + monitor.img, rest $FF" % sum(1 for a in range(0xE000, 0x10000) if a in {}))
