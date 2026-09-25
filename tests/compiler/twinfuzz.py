#!/usr/bin/env python3
"""twinfuzz.py - random C programs in the y1cc subset through y1cc.py and the C twin (2026-09-24); the assembly (or the
error message) must be the same. A complement to twin.py: the corpus is real programs, this is every operator,
type and statement shape mixed at random, including recursion, switch tables, struct members, pointer arithmetic,
string and array initialisers, and some programs y1cc must reject; before them a fixed list of 60 invalid programs
(ERRORS) whose error messages must match. Compile-only (nothing is run).

  twinfuzz.py [N] [--seed S] [--keep] [--chain | --chain16] [--xisa]
                                           N programs (default 300), reproducible from the seed; --chain compares
                                           y1cc.py with the multi-pass compiler (software/compiler/c/y1ccp, cc1..cc9)
                                           instead of y1cc.c, --chain16 with its 16-bit check build; both add ORDER,
                                           programs with two errors found in different passes; --xisa adds that
                                           option to every compile (the page, LDZ/STZ, ADDIW, SHL16; 2026-09-24)
"""
import os, sys, random, subprocess, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus

ROOT = corpus.ROOT
PY = os.path.join(ROOT, "software/compiler/y1cc.py")
TWIN = os.path.join(ROOT, "software/compiler/c/y1cc")
BUILD = os.path.join(corpus.HERE, "build", "twinfuzz")

INTS = ["g0", "g1", "g2", "gi"]
CHARS = ["c0", "c1"]
BINOPS = ["+", "-", "*", "/", "%", "&", "|", "^", "<<", ">>", "==", "!=", "<", ">", "<=", ">=", "&&", "||"]


# fixed programs that must fail: the same message from both compilers (2026-09-24: 60 of 60)
ERRORS = [
    'void main() { x = 1; }',
    'void main() { int a; a = f(); }',
    'int f(int a) { return a; } void main() { f(1, 2); }',
    'int f(int a); void main() { f(1); }',
    'void main() { int a; a = 70000; }',
    "void main() { int a; a = 'q; }",
    'void main() { puts("abc); }',
    '/* unterminated\nvoid main() {}',
    '#define X (1)\nvoid main() {}',
    '#include <stdio.h>\nvoid main() {}',
    '#include "nosuch.h"\nvoid main() {}',
    'void main() { int a; a = 1 @ 2; }',
    'void main() { int a[3]; a = 1; }',
    'struct S { int x; }; void main() { struct S s; s.y = 1; }',
    'void main() { int a; a.x = 1; }',
    'void main() { int a; *a = 1; }',
    'void main() { int a; a[1] = 1; }',
    'void main() { 3 = 4; }',
    'void main() { break; }',
    'void main() { continue; }',
    'void main() { case 1: ; }',
    'void main() { int a; switch (a) { case 1: case 1: ; } }',
    'void main() { int a; switch (a) { default: ; default: ; } }',
    'void main() { outp(20, 1); }',
    'void main() { sys(30); }',
    'void main() { sys(); }',
    'void main() { int a; a = bios(a, 1, 2); }',
    'void main() { int a; a = funcaddr(a); }',
    'int g; int g; void main() {}',
    'int a[]; void main() {}',
    'int *p = "x"; char c = "y"; void main() {}',
    'int a[2] = {1, 2, 3}; void main() {}',
    'int x = y; void main() {}',
    'int x = &nosuch; void main() {}',
    'struct S { int a; }; void f(struct S s) {} void main() { }',
    'struct S { int a; }; void f(struct S s) {} void main() { struct S t; f(t); }',
    'void f() {}',
    'void main() { int a; a = (1 + 2; }',
    'void main() { int a; a = sizeof(struct Q); }',
    'int a[sizeof(struct Q)]; void main() {}',
    'void main() { int a; a = 3 ? ; }',
    'void main() { struct S *p; p->x = 1; }',
    'int main2() { return 1; } void main() { funcaddr(nosuch); }',
    "void main() { int a; a = '\\q'; }",
    'void main() { char *s; s = "a\\qb"; }',
    'int f(int n) { return g(n); } int g(int n) { return f(n); } void main() { f(1); }',
    'void main() { int x; x = f(&x); } int f(int *p) { return *p; }',
    '//#define Q abc\nvoid main() {}',
    '#define Q 0x\nvoid main() {}',
    'void main() { int a; a = 0x; }',
    'struct { int a; }; void main() {}',
    'int 3x; void main() {}',
    'void main() { int a; a = f(1)(2); }',
    'void main() { "s"(1); }',
    'void main() { int a; a = x.y.z; }',
    'void main() { struct S s; }',
    'char c = {1}; void main() {}',
    'int t[2] = {{1}, 2}; void main() {}',
    'char *q[] = {1, "a"}; char b[2] = {"x"}; void main() {}',
    'int x = 5; int y = x; void main() {}',
]

# programs with two errors found by different passes of the multi-pass compiler (--chain only): the first in
# y1cc.py's order must win - a lexer error before any parse error (y1cc.py lexes first; y1cc.c does not, so these
# are not run against it), a statement error after an earlier expression's, main compiled first, funcaddr() by
# function order, a size error at the DS line or the frame save (2026-09-24)
ORDER = [
    'void main() { int a; a = (1 + 2; } char *s = "unterminated',
    'void main() { int a; a = ; }\nint b = 0x;',
    'void main() { break; x = nosuch; }',
    'void main() { x = nosuch; break; }',
    'int f() { break; } void main() { f(); nosuch = 1; }',
    'int f() { nosuch2 = 1; } void main() { f(); break; }',
    'void main() { struct Q q; }',
    'void main() { struct Q q; int a; a = b; }',
    'int r(int n) { struct Q q; if (n) return r(n - 1); return 0; } void main() { r(3); }',
    'void main() { int a; switch (a) { case 1: x = 1; case 1: ; } }',
    'void main() { int a; switch (b) { case 1: case 1: ; } }',
    'int g(int a) { return funcaddr(h); } int h() { return funcaddr(k); } void main() { g(1); h(); }',
    'int h(); int g() { return funcaddr(k2); } int h() { return funcaddr(k1); } void main() { g(); h(); }',
    'int g() { return funcaddr(k3) + funcaddr(1); } void main() { g(); }',
    'int h() { return 1; } int g() { return funcaddr(k4); } int h() { return funcaddr(k5); } void main() { g(); h(); }',
    'void main() { int a; a = sizeof(f(nosuch)); } int f(int x) { return x; }',
    'void main() { int a; a = 1 ? nosuch : 2; }',
    'int f(int a, int b) { return a; } void main() { f(1); x = 1; }',
    'void main() { int *p; p->x = 1; q = 2; }',
    'int main2() { main2(); } void main() { int a; a = main2() + nosuch; }',
]


class Gen:
    def __init__(self, rnd):
        self.r = rnd

    def const(self):
        return self.r.choice(["0", "1", "2", "3", "4", "7", "8", "16", "255", "256", "300", "4096", "65535",
                              "0x7F", "0xFF00", "'a'", "'\\n'", "N", "M", "sizeof(int)", "sizeof(struct S)"])

    def lval(self, locs, d):
        c = self.r.randrange(9)
        if c == 0: return self.r.choice(INTS + CHARS + ["lc", "lv", "n"])
        if c == 1: return "arr[%s]" % self.idx(locs, d)
        if c == 2: return "carr[%s]" % self.idx(locs, d)
        if c == 3: return "st.%s" % self.r.choice(["a", "b", "d[1]", "d[%s]" % self.idx(locs, d)])
        if c == 4: return "sp->%s" % self.r.choice(["a", "b", "d[2]"])
        if c == 5: return "*p"
        if c == 6: return "p[%s]" % self.idx(locs, d)
        if c == 7: return "s[%s]" % self.idx(locs, d)
        return "la[%s]" % self.idx(locs, d) if "la" in locs else "g0"

    def idx(self, locs, d):
        return self.r.choice(["0", "1", "3", "i", "(i & 3)", "c0 & 7"]) if d > 2 else "(%s & 3)" % self.expr(locs, d + 1)

    def expr(self, locs, d=0):
        r = self.r
        if d > 3 or r.random() < 0.25:
            return r.choice([self.const(), self.lval(locs, d), r.choice(INTS + CHARS + ["lc", "lv", "n"]), '"str"',
                             "arr", "carr" if r.random() < 0.3 else "i", "la" if r.random() < 0.05 else "lv"])
        c = r.randrange(16)
        if c < 6: return "(%s %s %s)" % (self.expr(locs, d + 1), r.choice(BINOPS), self.expr(locs, d + 1))
        if c == 6: return "(%s ? %s : %s)" % (self.expr(locs, d + 1), self.expr(locs, d + 1), self.expr(locs, d + 1))
        if c == 7: return "%s(%s)" % (r.choice(["-", "!", "~"]), self.expr(locs, d + 1))
        if c == 8: return "(%s = %s)" % (self.lval(locs, d), self.expr(locs, d + 1))
        if c == 9: return "(%s %s= %s)" % (self.lval(locs, d), r.choice(["+", "-", "*", "/", "%", "&", "|", "^", "<<", ">>"]),
                                           self.expr(locs, d + 1))
        if c == 10: return "(%s)" % (r.choice(["%s++", "%s--", "++%s", "--%s"]) % self.lval(locs, d))
        if c == 11: return "f1(%s, %s)" % (self.expr(locs, d + 1), self.expr(locs, d + 1))
        if c == 12: return "rec(%s)" % self.expr(locs, d + 1)
        if c == 13: return r.choice(["*(p + %s)", "*(s + %s)", "(p + %s)[1]", "&arr[%s]", "(s - %s)[2]"]) % self.expr(locs, d + 1)
        if c == 14: return r.choice(["getchar()", "peek(%s)" % self.expr(locs, d + 1), "strlen(s)", "ch(%s)" % self.expr(locs, d + 1),
                                     "sys(3, %s)" % self.expr(locs, d + 1), "p - arr", "sizeof arr", "sizeof(st)"])
        return "(%s)" % self.expr(locs, d + 1)

    def stmt(self, locs, d=0, loop=False):
        r = self.r
        c = r.randrange(14 if d < 3 else 6)
        if c < 3: return "%s = %s;" % (self.lval(locs, 0), self.expr(locs))
        if c == 3: return "%s;" % self.expr(locs)
        if c == 4: return r.choice(["putchar(%s);", "putnum(%s);", "poke(%s, 1);", "outp(2, %s);"]) % self.expr(locs)
        if c == 5: return ("break;" if loop and r.random() < 0.5 else "continue;") if loop else "return %s;" % self.expr(locs)
        if c == 6: return "if (%s) %s else %s" % (self.expr(locs), self.block(locs, d + 1, loop), self.block(locs, d + 1, loop))
        if c == 7: return "if (%s) %s" % (self.expr(locs), self.block(locs, d + 1, loop))
        if c == 8: return "for (i = 0; i < %s; i++) %s" % (r.choice(["3", "n", "c0"]), self.block(locs, d + 1, True))
        if c == 9: return "while (%s) %s" % (self.expr(locs), self.block(locs, d + 1, True))
        if c == 10:
            cases = sorted(set(r.choice([0, 1, 2, 3, 5, 9, 17, 40, 200, 255, 256, 1000, 65535]) for _ in range(r.randrange(1, 7))))
            body = " ".join("case %d: %s %s" % (k, self.stmt(locs, d + 1, loop), "break;" if r.random() < 0.7 else "")
                            for k in cases)
            if r.random() < 0.5: body += " default: %s" % self.stmt(locs, d + 1, loop)
            return "switch (%s) { %s }" % (self.expr(locs), body)
        if c == 11: return "{ %s %s }" % (self.stmt(locs, d + 1, loop), self.stmt(locs, d + 1, loop))
        if c == 12: return ";"
        return "%s = rec(%s) + f1(%s, 2);" % (self.lval(locs, 0), self.expr(locs), self.expr(locs))

    def block(self, locs, d, loop):
        return "{ %s }" % " ".join(self.stmt(locs, d, loop) for _ in range(self.r.randrange(1, 4)))

    def program(self):
        r = self.r
        locs = ["la", "lc", "lv"]
        out = ['#include "y1lib.c"', "#define N %d" % r.choice([3, 10, 300]), "#define M 'x'",
               "struct S { int a; char b; int d[3]; };",
               "int g0; int g1 = 5; int g2 = %s; char c0; char c1 = 'z'; int gi;" % r.choice(["0", "N * 2", "-1", "0x1234"]),
               "int arr[8] = {1, 2, 3}; char carr[8] = \"abc\"; int *p = arr; char *s = \"hello\";",
               "char *tab[] = {\"a\", \"bb\", 0}; int tab2[] = {N, M, 3}; int *pp = &g1;",
               "struct S st; struct S *sp = &st; int i;",
               "char ch(int x) { return x + 1; }",
               "int rec(int n);",
               "int f1(int a, char b) { int la[4]; char lc; int lv; int n; n = a; lc = b; lv = a; %s return lv + la[0]; }"
               % " ".join(self.stmt(locs) for _ in range(r.randrange(1, 5))),
               "int rec(int n) { int la[4]; char lc; int lv; if (n == 0) return 1; lv = n; %s return rec(n - 1) + lv; }"
               % " ".join(self.stmt(locs) for _ in range(r.randrange(0, 3))),
               "int helper(int n, int m) { int la[2]; char lc; int lv; lv = n + m; %s return lv; }"
               % " ".join(self.stmt(locs) for _ in range(r.randrange(1, 4))),
               "void main() { int la[4]; char lc; int lv; int n; n = 3; %s }"
               % " ".join(self.stmt(locs) for _ in range(r.randrange(2, 8)))]
        if r.random() < 0.3: out.append("int unused(int x) { return x * 2; }")
        if r.random() < 0.2: out[-1 if "unused" not in out[-1] else -2] += " int bad() { return nosuch; }"
        return "\n".join(out) + "\n"


def run(cmd, out):
    r = subprocess.run(cmd + ["-o", out], cwd=ROOT, capture_output=True)
    text = corpus.normalize(open(out, encoding="latin1").read()) if r.returncode == 0 and os.path.exists(out) else None
    return r.returncode, text, r.stderr.decode("latin1").strip()


def main():
    av = sys.argv[1:]
    n = int(next((a for a in av if a.isdigit()), "300"))
    seed = int(av[av.index("--seed") + 1]) if "--seed" in av else 1
    global BUILD, TWIN
    target = "y1cc"
    if "--chain" in av or "--chain16" in av:
        target = "passes"
        TWIN = os.path.join(ROOT, "software/compiler/c/y1ccp" + ("16" if "--chain16" in av else ""))
    r = subprocess.run(["make", "-s", "-C", os.path.dirname(TWIN), target], capture_output=True, text=True)
    if r.returncode: sys.exit(r.stdout + r.stderr)
    BUILD = os.path.join(BUILD, "seed%d" % seed)
    shutil.rmtree(BUILD, ignore_errors=True); os.makedirs(BUILD)
    rnd = random.Random(seed); g = Gen(rnd)
    X = ["--xisa"] if "--xisa" in av else []
    same = errs = 0; bad = []
    for k, text in enumerate(ERRORS + (ORDER if target == "passes" else [])):   # the error corpus first
        src = os.path.join(BUILD, "e%02d.c" % k)
        open(src, "w").write(text + "\n")
        p = run([sys.executable, PY, src] + X, src[:-2] + ".py.asm")
        c = run([TWIN, src] + X, src[:-2] + ".c.asm")
        if p[0] and c[0] and p[2] == c[2]: errs += 1
        elif p[0] == 0 and c[0] == 0 and p[1] == c[1]: same += 1
        else:
            bad.append(src); print("DIFFERENT %s: py %s | c %s" % (src, p[2][-120:], c[2][-120:]), flush=True)
    for k in range(n):
        src = os.path.join(BUILD, "f%04d.c" % k)
        open(src, "w").write(g.program())
        opts = rnd.choice([["--boot"], [], ["--os", "--org", "0x5000"], ["--no-brur", "--boot"], ["--vector"]]) + X
        if k % 5 == 2: opts = opts + ["--stack", "0xC7FF"]      # 2026-09-25 (not drawn: the seeds' programs stay)
        p = run([sys.executable, PY, src] + opts, src[:-2] + ".py.asm")
        c = run([TWIN, src] + opts, src[:-2] + ".c.asm")
        if p[0] == 0 and c[0] == 0 and p[1] == c[1]: same += 1
        elif p[0] and c[0] and p[2] == c[2]: errs += 1
        else:
            bad.append(src)
            print("DIFFERENT %s %s: py rc %d %s | c rc %d %s" % (src, opts, p[0], p[2][-120:], c[0], c[2][-120:]), flush=True)
    print("twinfuzz (seed %d%s): %d programs identical, %d identical errors, %d DIFFERENT" % (seed, " --xisa" if X else "", same, errs, len(bad)))
    if "--keep" not in av and not bad: shutil.rmtree(BUILD, ignore_errors=True)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
