#!/usr/bin/env python3
"""tests/monload/run.py - the monitor's ':' Intel-hex loader (2026-09-23) and tools/monload.py.

  1. a compiled C program (tests/compiler/hello.c) sent as its .img then G3000, on both emulators: one '.' per data
     record, LOADED, and the program's output
  2. the error paths on both emulators: a bad checksum and a bad hex digit answer '?', a record at $E000 (ROM) and one
     at $0F80 (the monitor's page) answer '!', the good record is stored (D 4000 shows it), the ROM is unchanged
     (D E000 shows the image's first bytes), the end record says LOADED WITH ERRORS; ':' then ESC says LOAD ABANDONED
  3. tools/monload.py itself, talking to the microcode emulator through a pseudo-terminal: load, --go 3000, output
"""
import os, sys, pty, tty, shutil, select, subprocess, tempfile, threading

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CC = os.path.join(ROOT, "software/compiler/y1cc.py"); ASM = os.path.join(ROOT, "software/assembler/asm")
DEF = os.path.join(ROOT, "software/assembler/yacc1.def")
EMUS = [("int", [os.path.join(ROOT, "software/emulator/emulator"), "-x", "-m", "-l", "3000000"]),
        ("uc", [os.path.join(ROOT, "software/ucemu/y1ucemu"), "-x", "-m", "-l", "40000000"])]


def rec(addr, typ, data):
    b = bytes([len(data), addr >> 8, addr & 0xFF, typ]) + bytes(data)
    return ":" + (b + bytes([(-sum(b)) & 0xFF])).hex().upper()


def build_hello(d):
    shutil.copy(DEF, d); open(os.path.join(d, "rcasm.rc"), "w").write("-h\n")
    subprocess.run([sys.executable, CC, os.path.join(ROOT, "tests/compiler/hello.c"), "-o", os.path.join(d, "hello.asm")], check=True)
    subprocess.run([ASM, "hello", "-d=yacc1"], cwd=d, capture_output=True)
    return os.path.join(d, "hello.img")


def run(cmd, data):
    r = subprocess.run(cmd, input=data, capture_output=True, timeout=600)
    return r.stdout.decode("latin1")


def main():
    d = tempfile.mkdtemp(); failed = 0
    img = build_hello(d)
    ndata = sum(1 for l in open(img) if l.startswith(":") and l[7:9] == "00")
    rom = open(os.path.join(ROOT, "firmware/rom/shipped/rom.bin"), "rb").read()

    # 1. load + run
    for tag, cmd in EMUS:
        out = run(cmd, open(img, "rb").read() + b"G3000")
        i = out.find(".")
        ok = i >= 0 and out[i:i + ndata] == "." * ndata and "LOADED" in out and "Hello, YACC1!" in out and "done" in out
        print("%-5s %-4s %s" % ("load", tag, "PASS  %d records, LOADED, G3000 ran hello.c" % ndata if ok else "FAIL\n" + out[-400:]))
        failed += not ok

    # 2. error paths
    bad_sum = rec(0x4010, 0, [1, 2])[:-2] + "00"
    bad_hex = ":01402000G0" + "00"
    session = "".join([rec(0x4000, 0, [0x55, 0xAA]), bad_sum, rec(0xE000, 0, [0x12]), rec(0x0F80, 0, [0x34]), bad_hex,
                       ":00000001FF", "D4000", ":01\x1b", "DE000"]).encode()     # ESC inside a record
    for tag, cmd in EMUS:
        out = run(cmd, session)
        acks = "".join(c for c in out[out.find("RUN TEST CODE") if "RUN TEST CODE" in out else 0:] if c in ".?!")
        want_rom = "E000: " + " ".join("%02X" % b for b in rom[:7])      # the bytes BASIC writes there; the fill differs (0 vs $FF)
        checks = [("acks .?!!?", acks.startswith(".?!!?")), ("LOADED WITH ERRORS", "LOADED WITH ERRORS" in out),
                  ("4000: 55 AA", "55 AA" in out.upper()), ("LOAD ABANDONED", "LOAD ABANDONED" in out),
                  ("ROM unchanged at E000", want_rom in out.upper())]
        bad = [n for n, ok in checks if not ok]
        print("%-5s %-4s %s" % ("error", tag, "PASS  ? on bad checksum/digit, ! on $E000/$0F80, stored, ROM intact, ESC abandons"
                                  if not bad else "FAIL %s\n%s" % (bad, out[-600:])))
        failed += bool(bad)

    # 3. the host tool through a pty to the microcode emulator
    m, s = pty.openpty(); tty.setraw(m); tty.setraw(s)
    emu = subprocess.Popen(EMUS[1][1][:-2] + ["-l", "60000000"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
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
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools/monload.py"), img, "--port", os.ttyname(s), "--delay", "0",
                        "--go", "3000", "--listen", "4", "--timeout", "20"], capture_output=True, text=True, timeout=300)
    stop.set(); emu.kill()
    ok = r.returncode == 0 and "records loaded" in r.stdout and "Hello, YACC1!" in r.stdout
    print("%-5s %-4s %s" % ("tool", "uc", "PASS  tools/monload.py loaded and ran hello.c over a pty" if ok else "FAIL\n" + r.stdout[-500:] + r.stderr[-500:]))
    failed += not ok

    print("%d failed" % failed); sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
