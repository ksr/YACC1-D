#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""tests/cfcard/run.py - tools/cfcard.py without a card: write and read an image through a stand-in file, and check that
the tool refuses the Mac's internal disk (disk0) before anything is written."""
import os, sys, subprocess, tempfile, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOL = os.path.join(ROOT, "tools/cfcard.py"); IMG = os.path.join(ROOT, "os/disk.img")


def run(*a): return subprocess.run([sys.executable, TOOL] + list(a), capture_output=True, text=True)


def main():
    failed = 0
    if not os.path.exists(IMG): subprocess.run(["make", "-s", "-C", os.path.join(ROOT, "os")], capture_output=True)
    d = tempfile.mkdtemp(); card = os.path.join(d, "card.img"); back = os.path.join(d, "back.img")
    open(card, "wb").write(b"\xa5" * (8192 * 512))
    r = run("write", IMG, "--target-file", card)
    ok = r.returncode == 0 and "IDENTICAL" in r.stdout and open(card, "rb").read(os.path.getsize(IMG)) == open(IMG, "rb").read()
    print("write     %s" % ("PASS  image written to the stand-in card and read back identical" if ok else "FAIL " + r.stdout + r.stderr)); failed += not ok
    r = run("read", back, "--target-file", card)
    img = open(IMG, "rb").read(); got = open(back, "rb").read() if os.path.exists(back) else b""
    used = max(2048, img[4] | img[5] << 8) * 512        # read copies the volume's sectors in use (its free pointer;
    ok = r.returncode == 0 and len(got) >= used and got == img[:len(got)]   # 2026-11-03: the 4 MB image is not all used)
    print("read      %s" % ("PASS  read back (%d bytes, the sectors in use) matches the image" % len(got) if ok else "FAIL " + r.stdout + r.stderr)); failed += not ok
    r = run("write", IMG, "--disk", "disk0", "--yes")
    ok = r.returncode != 0 and "refusing disk0" in (r.stderr + r.stdout)
    print("refuse    %s" % ("PASS  the internal disk is refused before any write" if ok else "FAIL " + r.stdout + r.stderr)); failed += not ok
    r = run("write", IMG, "--disk", "disk0s1", "--yes")
    ok = r.returncode != 0 and "whole disk" in (r.stderr + r.stdout)
    print("partition %s" % ("PASS  a partition name is refused" if ok else "FAIL " + r.stdout + r.stderr)); failed += not ok
    shutil.rmtree(d)
    print("%d failed" % failed); sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
