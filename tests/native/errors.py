#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""tests/native/errors.py - the native compiler's error messages (2026-11-05).

The passes read one file at a time, except on the way to an error message: e_tok and nm_fetch open W.lit or W.nam while
the pass's own input is open, and go on to name what is wrong. That second handle is the one thing io_getc's fast path
must not confuse with the first (target_rd.c), and no other test reaches it under Y1/OS. So: bad programs, each stopped
in a different pass, compiled by /bin/cc on the instruction-level emulator; each message must be y1cc.py's, word for word.
"""
import os, re, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OS = os.path.join(ROOT, "os")
B = os.path.join(HERE, "build", "errors")
EMU = os.path.join(ROOT, "software/emulator/emulator")
CC = [sys.executable, os.path.join(ROOT, "software/compiler/y1cc.py")]
FS = [sys.executable, os.path.join(ROOT, "tools/p8xfs.py")]
# (name, source): cases with several reads of the file before the error, so that the first file's buffer is in use
PAD = "".join("int pad%d;\nint fp%d(int a) { return a + %d; }\n" % (i, i, i) for i in range(12))
CASES = [
    ("tokstr",   PAD + 'int main() { int a; a = 1 "x"; return a; }\n'),     # cc2 e_tok: the literal's bytes, from W.lit
    ("tokname",  PAD + "int main() { int a; a = 1 bad; return a; }\n"),     # cc2 e_tok: a name, nm_fetch
    ("sizeof",   PAD + "int main() { return sizeof(struct nosuch); }\n"),   # cc2 size_of: nm_fetch
    ("nostruct", PAD + "struct nosuch v;\nint main() { return 0; }\n"),     # a variable of an unknown struct
    ("nolocal",  PAD + "int main() { struct nosuch v; return 0; }\n"),      # cc6 v_serr
    ("undecl",   PAD + "int main() { return nosuch; }\n"),                  # cc8 e_name, twice
    ("nomember", PAD + "struct s { int a; };\nstruct s v;\nint main() { return v.b; }\n"),
    ("notstruct", PAD + "int v;\nint main() { return v.a; }\n"),
    ("nocall",   PAD + "int main() { return nofunc(1); }\n"),
]


def tidy(s, name):
    return re.sub(r"\S*%s\.c" % name, "%s.c" % name, s).strip()


def main():
    subprocess.run(["make", "-s", "-C", OS], check=True)
    shutil.rmtree(B, ignore_errors=True); os.makedirs(B)
    img = os.path.join(B, "disk.img")
    shutil.copy(os.path.join(OS, "disk.img"), img)
    subprocess.run(FS + ["mkdir", img, "/r"], check=True, capture_output=True)
    script = "O\ncd /r\n"
    want = {}
    for name, src in CASES:
        p = os.path.join(B, name + ".c")
        open(p, "w").write(src)
        r = subprocess.run(CC + [p, "-o", os.path.join(B, name + ".asm"), "--org", "0x5000", "--os"],
                           capture_output=True, text=True)
        if r.returncode == 0: sys.exit("errors: %s compiles on the host" % name)
        want[name] = tidy(r.stderr, name)
        subprocess.run(FS + ["put", img, p, "--name", "/r/" + name + ".c"], check=True, capture_output=True)
        script += "cc %s.c -o %s.asm --org 0x5000 --os\n" % (name, name)
    script += "exit\n0\n"
    r = subprocess.run([EMU, "-x", "-m", "-c", img, "-l", "40000000000"], input=script.encode(), capture_output=True)
    out = (r.stdout + r.stderr).decode("latin1").replace("\r", "")
    open(os.path.join(B, "session.txt"), "w").write(out)
    bad = 0
    seen = out.split("/r> ")[1:]                    # (a scripted session does not echo the lines typed)
    if len(seen) != len(CASES) + 1: print("errors: %d prompts for %d cases" % (len(seen), len(CASES))); bad += 1
    for (name, src), got in zip(CASES, seen):
        got = tidy(got, name)
        ok = got == want[name]
        print("%-9s %-5s %s" % (name, "PASS" if ok else "FAIL", want[name][:90]))
        if not ok: print("          got: %r" % got[:160]); bad += 1
    print("errors: %d failed" % bad)
    if not bad: shutil.rmtree(B)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
