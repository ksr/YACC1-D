#!/usr/bin/env python3
"""Y1/OS tests: build os/disk.img, boot it on both emulators with a scripted console session, compare transcripts.

  run.py [--keep] [--update]
    --update   rewrite the expected transcripts from this run (after checking them by eye)

Sessions live in tests/os/*.session (one console line per line, sent after the monitor's O command boots the
OS). The expected transcript is NAME.int.out for the instruction-level emulator and NAME.uc.out for the microcode
emulator (the latter shows the monitor's input echo, as the machine does). The comparison starts at "BOOT FROM CF"
and ends after the OS says "bye" and the monitor prompt returns.
"""
import os, sys, glob, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OS = os.path.join(ROOT, "os")
EMUS = [("int", os.path.join(ROOT, "software/emulator/emulator"), ["-l", "6000000"]),
        ("uc", os.path.join(ROOT, "software/ucemu/y1ucemu"), ["-l", "80000000"])]


def transcript(emu, extra, script):
    p = subprocess.Popen([emu, "-x", "-m", "-c", os.path.join(OS, "disk.img")] + extra, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try: out, err = p.communicate(script, timeout=600)
    except subprocess.TimeoutExpired: p.kill(); out, err = p.communicate(); return None, "timeout"
    s = out.decode("latin1")
    i = s.find("BOOT FROM CF"); j = s.find("bye", i)
    if i < 0 or j < 0: return None, "no boot/bye in the output: " + s[-300:]
    k = s.find(">", j)                           # the monitor prompt after the OS returned
    status = err.decode("latin1").strip().splitlines()[-1] if err.strip() else ""
    return s[i:k + 1], status


def main():
    update = "--update" in sys.argv
    r = subprocess.run(["make", "-s", "-C", OS], capture_output=True, text=True)
    if r.returncode: sys.exit("os build failed:\n" + r.stdout[-800:] + r.stderr[-800:])
    passed = failed = 0
    for sess in sorted(glob.glob(os.path.join(HERE, "*.session"))):
        name = os.path.basename(sess)[:-8]
        script = b"O\n" + open(sess, "rb").read()
        for tag, emu, extra in EMUS:
            got, status = transcript(emu, extra, script)
            exp_file = os.path.join(HERE, "%s.%s.out" % (name, tag))
            if got is None: print("%-12s %-4s FAIL  %s" % (name, tag, status)); failed += 1; continue
            if update: open(exp_file, "w", newline="").write(got)
            if not os.path.exists(exp_file): print("%-12s %-4s FAIL  no %s (run with --update)" % (name, tag, os.path.basename(exp_file))); failed += 1; continue
            exp = open(exp_file, newline="").read()          # keep the CR LF pairs the monitor prints
            if got == exp: print("%-12s %-4s PASS  %s" % (name, tag, status[:90])); passed += 1
            else:
                open(os.path.join(HERE, "%s.%s.got" % (name, tag)), "w", newline="").write(got)
                print("%-12s %-4s FAIL  transcript differs (see %s.%s.got)" % (name, tag, name, tag)); failed += 1
    print("%d passed, %d failed" % (passed, failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
