#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""tests/native/mkdisk.py - Y1/OS rebuilds itself onto a new disk and boots from it (2026-11-05).

On the instruction-level emulator, a copy of os/disk.img as drive 0 and an empty image as drive 1 (-C):

  1, 2  cd /src, make, make install    every program, then the kernel, built by the machine (kermit excepted:
                                       os/mksrcmk.py NATIVE_NO) and installed in /bin, /lib/cc and /lib/y1os
        make clean                     the build's output leaves /src
  3     cd /, mkdisk                   drive 1: the boot block, the new kernel, a volume, this disk's files

and the host checks the new image: fsck; OSCNT and the kernel's sectors against os/build/y1os-asm.bin; and every
file, with its bytes, load and exec address, against os/disk.img, the disk the session started from: what the machine
built is the host's byte for byte, so the new disk is the same system, compacted. Nothing else may be on it. Then

  4     the new image alone, as drive 0: O, a few commands, a program built there and run, a second mkdisk refused
        for want of a drive; fsck again.

  mkdisk.py [--keep]      --keep: leave tests/native/build/mkdisk/ (old.img, new.img, the two sessions)
"""
import os, sys, re, subprocess, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OS = os.path.join(ROOT, "os")
B = os.path.join(HERE, "build", "mkdisk")
EMU = os.path.join(ROOT, "software/emulator/emulator")
FS = [sys.executable, os.path.join(ROOT, "tools/p8xfs.py")]
sys.path.insert(0, os.path.join(ROOT, "tools"))
import p8xfs as P
sys.path.insert(0, os.path.join(ROOT, "tests", "os"))
import run as osrun                                  # tree_files: {path: (bytes, load, exec)}
LIMIT = "200000000000"                               # instructions


def session(name, script, *drives):
    r = subprocess.run([EMU, "-x", "-m", "-l", LIMIT] + list(drives), input=script.encode(), capture_output=True)
    out = r.stdout.decode("latin1")
    open(os.path.join(B, name + ".txt"), "w").write(out)
    return out


def main():
    subprocess.run(["make", "-s", "-C", OS], check=True)
    shutil.rmtree(B, ignore_errors=True)
    os.makedirs(B)
    old, new = os.path.join(B, "old.img"), os.path.join(B, "new.img")
    shutil.copy(os.path.join(OS, "disk.img"), old)
    fails = []

    out = session("build", "O\ncd /src\nmake\nmake install\nmake clean\ncd /\nmkdisk\nexit\n0\n", "-c", old, "-C", new)
    if "sh: stopped" in out: fails.append("a script stopped (see build.txt)")
    if not re.search(r"\n\r?bye", out): fails.append("the first session did not end")
    m = re.search(r"mkdisk: (\d+) sectors of kernel, (\d+) files, (\d+) directories, free pointer (\d+)", out)
    if not m: fails.append("mkdisk's summary is missing: " + out[-300:])
    r = subprocess.run(FS + ["fsck", new], capture_output=True, text=True)
    if r.returncode: fails.append("fsck of the new disk: " + (r.stdout + r.stderr)[-300:])

    img = P.read_img(new)
    kernel = open(os.path.join(OS, "build/y1os-asm.bin"), "rb").read()
    n = (len(kernel) + 511) // 512
    if img[:3] != b"P8\x02" or img[3] != n: fails.append("the boot block: %r, OSCNT %d, want %d" % (bytes(img[:3]), img[3], n))
    if bytes(img[512:512 + len(kernel)]) != kernel: fails.append("the kernel's sectors differ from os/build/y1os-asm.bin")
    want = osrun.tree_files(P.read_img(os.path.join(OS, "disk.img")))[0]
    got = osrun.tree_files(img)[0]
    for p in sorted(set(want) | set(got)):
        if p not in got: fails.append("missing on the new disk: " + p)
        elif p not in want: fails.append("extra on the new disk: " + p)
        elif want[p] != got[p]: fails.append("differs on the new disk: %s (%d / %d bytes)" % (p, len(got[p][0]), len(want[p][0])))

    boot = session("boot", "O\nls /\ncat fruit.txt | sort | uniq | head -2\nmkdisk\ncd /src/os/commands\nmake touch\n"
                   "cd /\nrun /src/os/commands/touch /made.here\ndir /made.here\nexit\n0\n", "-c", new)
    if "BOOT FROM CF" not in boot or not re.search(r"\n\r?bye", boot): fails.append("the new disk did not boot and end (see boot.txt)")
    if "apple 3 red" not in boot: fails.append("the new disk's commands did not run")
    if "mkdisk: no drive 1" not in boot: fails.append("mkdisk with no drive 1 was not refused")
    if not re.search(r"touch: \d+ bytes", boot) or not re.search(r"0  made\.here", boot):
        fails.append("a program built on the new disk did not run")
    r = subprocess.run(FS + ["fsck", new], capture_output=True, text=True)
    if r.returncode: fails.append("fsck after booting the new disk: " + (r.stdout + r.stderr)[-300:])

    print("mkdisk: %s kernel sectors, %s files, %s directories on the new disk" % m.groups()[:3] if m else "mkdisk: no summary")
    for f in fails[:30]: print("  FAIL " + f)
    print("mkdisk: %d problems" % len(fails))
    if not fails and "--keep" not in sys.argv: shutil.rmtree(B)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
