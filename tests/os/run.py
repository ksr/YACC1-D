#!/usr/bin/env python3
"""Y1/OS tests: build os/disk.img, boot it on both emulators with a scripted console session, compare transcripts.

  run.py [name ...] [--keep] [--update]
    name       run only these sessions
    --update   rewrite the expected transcripts from this run (after checking them by eye)
    --keep     leave the per-run disk images in tests/os/build/

Sessions live in tests/os/*.session (one console line per line, sent after the monitor's O command boots the
OS; a Ctrl-D byte ends a program's console input). The expected transcript is NAME.int.out for the instruction-level
emulator and NAME.uc.out for the microcode emulator (the latter shows the monitor's input echo, as the machine
does). The comparison starts at "BOOT FROM CF" and ends after the OS says "bye" and the monitor prompt returns.

Every run boots a fresh COPY of os/disk.img (tests/os/build/NAME.TAG.img): the emulators write the CF image in place
(software/cfmodel.h), and since 2026-09-23 the OS writes files. After a session listed in HOST the copy is checked
from the host side with tools/p8xfs.py (fsck, ls, get + compare), which proves the OS's writes are what the host
tool would have written. The per-emulator step limits (LIMITS) end a run: after `exit` the monitor spins on an
empty console until the limit, so a limit is a wall-clock budget, not a pass/fail line.
"""
import os, sys, glob, subprocess, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OS = os.path.join(ROOT, "os")
FS = os.path.join(ROOT, "tools/p8xfs.py")
BUILD = os.path.join(HERE, "build")
EMUS = [("int", os.path.join(ROOT, "software/emulator/emulator")),
        ("uc", os.path.join(ROOT, "software/ucemu/y1ucemu"))]
LIMITS = {"basic": (8000000, 120000000),         # instructions (int) / microcode steps (uc): the session must finish
          "api": (12000000, 200000000),          # inside them; a program-heavy session needs more (2026-09-23)
          "write": (14000000, 220000000),
          "wave1": (8000000, 110000000),         # 4.5M / 62M needed (2026-09-23)
          "wave2": (9000000, 130000000)}         # 5.7M / 79M needed
DEFAULT_LIMIT = (12000000, 200000000)

# host-side checks on the disk image a session leaves behind: ("fsck",) must pass; ("ls", path, present, absent)
# lists a directory and checks names; ("get", path, hostfile, nbytes) fetches a file and compares it with the first
# nbytes (0 = all) of a host file
HOST = {
    "api": [("fsck",), ("get", "/COPY.TXT", "os/disk/README.TXT", 0)],
    "write": [("fsck",),
              ("ls", "/", ["T", "T2", "SAVED.BIN"], ["README.TXT"]),
              ("ls", "/T", ["KEEP.TXT"], ["COPY.TXT", "H.BIN", "SUB"]),
              ("get", "/T/KEEP.TXT", "os/disk/README.TXT", 0),
              ("get", "/T2/HELLO", "os/build/bin/hello.bin", 16),
              ("get", "/SAVED.BIN", "os/build/bin/hello.bin", 0x84)],
    "vi": [("fsck",), ("ls", "/", ["T.TXT"], [])],
    "wave2": [("fsck",),
              ("ls", "/T", ["E1", "E2", "FRUIT.TXT", "H", "S"], []),
              ("ls", "/U", ["E3", "S"], ["E1", "E2", "FRUIT.TXT", "H"]),
              ("ls", "/U/S", ["F2.TXT", "FRUIT.TXT", "FRUIT2.TXT", "H", "F1.TXT"], ["README.TXT"]),
              ("get", "/FRUIT.TXT", "os/disk/FRUIT.TXT", 0),
              ("get", "/T/S/F2.TXT", "os/disk/FRUIT2.TXT", 0),
              ("get", "/U/S/F1.TXT", "os/disk/FRUIT.TXT", 0),
              ("get", "/U/S/H", "os/build/bin/hello.bin", 0)],
}


def transcript(emu, limit, img, script):
    p = subprocess.Popen([emu, "-x", "-m", "-c", img, "-l", str(limit)], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try: out, err = p.communicate(script, timeout=900)
    except subprocess.TimeoutExpired: p.kill(); out, err = p.communicate(); return None, "timeout"
    s = out.decode("latin1")
    i = s.find("BOOT FROM CF"); j = s.find("\nbye", i)
    if i < 0 or j < 0: return None, "no boot/bye in the output (limit too low?): " + s[-300:]
    k = s.find(">", j)                           # the monitor prompt after the OS returned
    status = err.decode("latin1").strip().splitlines()[-1] if err.strip() else ""
    return s[i:k + 1], status


def p8xfs(*args):
    r = subprocess.run([sys.executable, FS] + list(args), capture_output=True, text=True, cwd=ROOT)
    return r.returncode, r.stdout + r.stderr


def host_check(name, img):
    """Run the HOST checks for a session on its disk image; returns a list of failure strings."""
    fails = []
    for chk in HOST.get(name, []):
        if chk[0] == "fsck":
            rc, out = p8xfs("fsck", img)
            if rc: fails.append("fsck failed:\n" + out.strip())
        elif chk[0] == "ls":
            rc, out = p8xfs("ls", img, chk[1])
            names = {l.split()[0] for l in out.splitlines()[2:] if l.strip() and not l.endswith("entries") and not l.endswith("entry")}
            for n in chk[2]:
                if n not in names: fails.append("ls %s: %s missing (got %s)" % (chk[1], n, sorted(names)))
            for n in chk[3]:
                if n in names: fails.append("ls %s: %s should be gone" % (chk[1], n))
        elif chk[0] == "get":
            tmp = img + ".get"
            rc, out = p8xfs("get", img, chk[1], "--out", tmp)
            if rc: fails.append("get %s: %s" % (chk[1], out.strip())); continue
            want = open(os.path.join(ROOT, chk[2]), "rb").read()
            if chk[3]: want = want[:chk[3]]
            got = open(tmp, "rb").read(); os.remove(tmp)
            if got != want: fails.append("get %s: %d bytes, differs from %s (%d bytes)" % (chk[1], len(got), chk[2], len(want)))
    return fails


def main():
    update = "--update" in sys.argv; keep = "--keep" in sys.argv
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    r = subprocess.run(["make", "-s", "-C", OS], capture_output=True, text=True)
    if r.returncode: sys.exit("os build failed:\n" + r.stdout[-800:] + r.stderr[-800:])
    os.makedirs(BUILD, exist_ok=True)
    passed = failed = 0
    for sess in sorted(glob.glob(os.path.join(HERE, "*.session"))):
        name = os.path.basename(sess)[:-8]
        if only and name not in only: continue
        script = b"O\n" + open(sess, "rb").read()
        for (tag, emu), limit in zip(EMUS, LIMITS.get(name, DEFAULT_LIMIT)):
            img = os.path.join(BUILD, "%s.%s.img" % (name, tag))
            shutil.copy(os.path.join(OS, "disk.img"), img)
            got, status = transcript(emu, limit, img, script)
            exp_file = os.path.join(HERE, "%s.%s.out" % (name, tag))
            if got is None: print("%-12s %-4s FAIL  %s" % (name, tag, status)); failed += 1; continue
            if update: open(exp_file, "w", newline="").write(got)
            if not os.path.exists(exp_file): print("%-12s %-4s FAIL  no %s (run with --update)" % (name, tag, os.path.basename(exp_file))); failed += 1; continue
            exp = open(exp_file, newline="").read()          # keep the CR LF pairs the monitor prints
            fails = host_check(name, img)
            if got != exp:
                open(os.path.join(HERE, "%s.%s.got" % (name, tag)), "w", newline="").write(got)
                fails.insert(0, "transcript differs (see %s.%s.got)" % (name, tag))
            if fails:
                print("%-12s %-4s FAIL  %s" % (name, tag, "; ".join(fails))); failed += 1
            else:
                print("%-12s %-4s PASS  %s%s" % (name, tag, status[:70], "  host: p8xfs ok" if name in HOST else "")); passed += 1
            if not keep: os.remove(img)
    print("%d passed, %d failed" % (passed, failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
