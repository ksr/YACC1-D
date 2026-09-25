#!/usr/bin/env python3
"""/BIN/ASM under Y1/OS on both emulators (2026-09-25): sources on a copy of os/disk.img, target.session assembles
them with `asm` (and runs two of the results), then the files it wrote are fetched from the image and compared with
what the host assembler RC/asm makes of the same sources.

  target.py [--update] [--keep]
    --update   rewrite target.int.out / target.uc.out from this run (check them by eye first)
    --keep     leave the disk images in tests/asm/build/target/

The sources (in /S on the disk; a y1cc compile is made here with the options os/Makefile uses):
  HELLO.ASM   os/commands/hello.c (y1cc --os): assembled to a program file and to Intel hex, the program run
  ECHOX.ASM   os/commands/echo.c (y1cc --os --xisa): the program file, run
  CAT.ASM     os/commands/cat.c (y1cc --os): 27K of source, the program file, run on /FRUIT.TXT
  MONITOR.ASM firmware/monitor/monitor.asm, the ROM monitor: Intel hex, must be firmware/monitor/monitor.img
  ISA.ASM     tests/ucemu/isa.asm (the instruction test program, with its $F000 boot stub): Intel hex
  QUIRKS.ASM  tests/asm/src/quirks.asm with its two-level INCLUDE (quirks1.inc, quirks2.inc): Intel hex + program
  CC4.ASM     software/compiler/c/target/calls.c (y1cc --os --xisa): pass 4 of the multi-pass C compiler, 58,585
              bytes and 3,037 lines, the one pass whose assembly is under Y1/OS's 64K: the program file
  ERR.ASM     tests/asm/src/err_undef.asm: an error, the message, no output file
The comparison: every program file byte-identical to RC/asm's bytes (first to last address, zero gaps) with its load
and exec address; every .IMG byte-identical to RC/asm's .img; ERR's output absent; fsck passes. The transcripts are
compared too (the per-program summaries, the error messages, the programs' own output).
"""
import os, sys, re, shutil, subprocess, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
B = os.path.join(HERE, "build", "target")
Y1CC = os.path.join(ROOT, "software/compiler/y1cc.py")
spec = importlib.util.spec_from_file_location("osrun", os.path.join(ROOT, "tests/os/run.py"))
osrun = importlib.util.module_from_spec(spec); spec.loader.exec_module(osrun)
sys.path.insert(0, HERE)
import run as asmrun                              # noqa: E402  (tests/asm/run.py: rcasm(), hexmem())

# host file -> disk name; (disk output, kind, source) for the checks: kind "bin" = a program file, "img" = Intel hex
SOURCES = [("hello.asm", "/S/HELLO.ASM"), ("echox.asm", "/S/ECHOX.ASM"), ("cat.asm", "/S/CAT.ASM"),
           ("monitor.asm", "/S/MONITOR.ASM"), ("isa.asm", "/S/ISA.ASM"), ("quirks.asm", "/S/QUIRKS.ASM"),
           ("quirks1.inc", "/S/quirks1.inc"), ("quirks2.inc", "/S/quirks2.inc"), ("cc4.asm", "/S/CC4.ASM"),
           ("err.asm", "/S/ERR.ASM")]
OUTPUTS = [("/S/HELLO", "bin", "hello"), ("/S/HELLO.IMG", "img", "hello"), ("/S/ECHOX", "bin", "echox"),
           ("/S/CAT", "bin", "cat"), ("/S/MON.IMG", "img", "monitor"), ("/S/ISA.IMG", "img", "isa"),
           ("/S/Q.IMG", "img", "quirks"), ("/S/QUIRKS", "bin", "quirks"), ("/S/CC4", "bin", "cc4")]
ABSENT = ["/S/ERR", "/S/NOSUCH"]
LIMITS = (90000000, 1500000000)                   # instructions (int) / microcode steps (uc): ~78M / ~1.3G needed (2026-09-25)


def prepare():
    os.makedirs(B, exist_ok=True)
    for name, src, opts in (("hello", "os/commands/hello.c", []), ("echox", "os/commands/echo.c", ["--xisa"]),
                            ("cat", "os/commands/cat.c", []), ("cc4", "software/compiler/c/target/calls.c", ["--xisa"])):
        subprocess.run([sys.executable, Y1CC, os.path.join(ROOT, src), "-o", os.path.join(B, name + ".asm"),
                        "--org", "0x5000", "--os"] + opts, check=True)
    for name, src in (("monitor", "firmware/monitor/monitor.asm"), ("isa", "tests/ucemu/isa.asm"),
                      ("quirks", "tests/asm/src/quirks.asm"), ("quirks1", "tests/asm/src/quirks1.inc"),
                      ("quirks2", "tests/asm/src/quirks2.inc"), ("err", "tests/asm/src/err_undef.asm")):
        shutil.copy(os.path.join(ROOT, src), os.path.join(B, name + (".inc" if src.endswith(".inc") else ".asm")))
    asmrun.prepare(B)
    want = {}
    for name in ("hello", "echox", "cat", "monitor", "isa", "quirks", "cc4"):
        ok, errs, img, start = asmrun.rcasm(B, name)
        if not ok: sys.exit("RC/asm reports errors for %s: %s" % (name, errs))
        _, mem = asmrun.hexmem(img)
        lo = min(mem)
        want[name] = (open(img, "rb").read(), bytes(mem.get(a, 0) for a in range(lo, max(mem) + 1)), lo,
                      start if start else lo)
    return want


def main():
    update = "--update" in sys.argv; keep = "--keep" in sys.argv
    r = subprocess.run(["make", "-s", "-C", os.path.join(ROOT, "os")], capture_output=True, text=True)
    if r.returncode: sys.exit("os build failed:\n" + r.stdout[-800:] + r.stderr[-800:])
    want = prepare()
    script = b"O\n" + open(os.path.join(HERE, "target.session"), "rb").read()
    failed = 0
    for (tag, emu), limit in zip(osrun.EMUS, LIMITS):
        img = os.path.join(B, "disk.%s.img" % tag)
        shutil.copy(os.path.join(ROOT, "os/disk.img"), img)
        rc, out = osrun.p8xfs("mkdir", img, "/S")
        if rc: sys.exit("mkdir /S: " + out)
        for host, disk in SOURCES:
            rc, out = osrun.p8xfs("put", img, os.path.join(B, host), "--name", disk)
            if rc: sys.exit("put %s: %s" % (disk, out))
        got, status = osrun.transcript(emu, limit, img, script)
        exp_file = os.path.join(HERE, "target.%s.out" % tag)
        fails = []
        if got is None: fails.append(status)
        else:
            if update: open(exp_file, "w", newline="").write(got)
            if not os.path.exists(exp_file): fails.append("no %s (run with --update)" % os.path.basename(exp_file))
            elif not osrun.same(got, open(exp_file, newline="").read()):
                open(os.path.join(B, "target.%s.got" % tag), "w", newline="").write(got)
                fails.append("transcript differs (see tests/asm/build/target/target.%s.got)" % tag)
        rc, out = osrun.p8xfs("fsck", img)
        if rc: fails.append("fsck: " + out.strip()[-200:])
        files, _ = osrun.tree_files(osrun.P.read_img(img))
        for disk, kind, name in OUTPUTS:
            if disk not in files: fails.append("%s missing" % disk); continue
            data, load, exe = files[disk]
            himg, hbin, lo, start = want[name]
            if kind == "img" and data != himg: fails.append("%s differs from RC/asm's .img" % disk)
            if kind == "bin" and (data != hbin or load != lo or exe != start):
                fails.append("%s: %d bytes load %04X exec %04X, RC/asm: %d bytes load %04X exec %04X" % (
                    disk, len(data), load, exe, len(hbin), lo, start))
        if files.get("/S/MON.IMG", (b"",))[0] != open(os.path.join(ROOT, "firmware/monitor/monitor.img"), "rb").read():
            fails.append("/S/MON.IMG is not firmware/monitor/monitor.img (the monitor in the ROM)")
        for disk in ABSENT:
            if disk in files: fails.append("%s should not exist" % disk)
        print("asm target  %-4s %s  %s" % (tag, "FAIL" if fails else "PASS", "; ".join(fails) if fails else status[:70]))
        failed += bool(fails)
        if not keep: os.remove(img)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
