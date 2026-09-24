#!/usr/bin/env python3
"""passes.py - the multi-pass y1cc against the Y1/OS program area (2026-09-24; software/compiler/README.md, "The
multi-pass compiler"). For each of the nine passes (software/compiler/c/cc1_lex.c .. cc9_final.c):

  1. the Y1/OS program: y1cc.py compiles the pass as an --os program at $5000 (software/compiler/c/target/NAME.c:
     its Y1/OS table sizes ylim/NAME.h, the Y1/OS I/O layer target_io.c, the pass), the host assembler assembles it
     (0 errors, its label count), and the bytes are counted: code + data = the image (checked against the
     assembler's Object Code), + the uninitialised data (the tables, the static frames of every function) = what the
     loaded program occupies;
  2. its stack: the pass's y1cc assembly is read for how many bytes each function has on the stack at each call
     (pushed operands, parked arguments, a recursive callee's saved frame, the return address); the pass is built on
     the Mac with the same Y1/OS table sizes and with -finstrument-functions (stackprobe.c), and the whole compile
     corpus (the nine passes' own sources are in it) is compiled through that chain (y1ccps): the probe replays the
     YACC1 stack on every call and records the deepest point. Calls it cannot see (the runtime helpers, the Y1/OS
     I/O layer, a syscall) are counted statically at their call sites, a syscall with SYSCALL_STACK bytes for the OS;
  3. capacity: the same chain's output is compared with y1cc.py's: identical, or which table overflowed; and how
     many compiles keep every intermediate file and the output under Y1/OS's 64K file size.

  passes.py [-v]          the table, the programs that do not fit (the limit that stopped them); -v: the probe's
                          unmeasured calls, every compile with a file over 64K

The program area is $5000-$CFFF (32,768 bytes): image + uninitialised data + stack must fit in it, the stack at
the top (software/compiler/README.md, "The stack"). Exit 1 if a pass does not fit, or on an assembly that differs.
"""
import os, re, sys, subprocess, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus, twin

ROOT = corpus.ROOT
CDIR = os.path.join(ROOT, "software/compiler/c")
PY = os.path.join(ROOT, "software/compiler/y1cc.py")
ASM = os.path.join(ROOT, "software/assembler/asm")
B = os.path.join(CDIR, "build", "y1")
PASSES = [(1, "cc1_lex", "lex"), (2, "cc2_parse", "parse"), (3, "cc3_decl", "decl"), (4, "cc4_calls", "calls"),
          (5, "cc5_layout", "layout"), (6, "cc6_stmt", "stmt"), (7, "cc7_sema", "sema"), (8, "cc8_emit", "emit"),
          (9, "cc9_final", "final")]
AREA = 0xD000 - 0x5000
SYSCALL_STACK = 64          # what a Y1/OS syscall handler may push below the caller (an allowance, not measured)
BIOS_STACK = 16             # a ROM routine called with bios()
HOST_PATHPOOL = 1200        # the capacity run's path pool (Mac paths are absolute); every other table is Y1/OS's


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, errors="replace", **kw)


def build_target(src, lim):
    """the pass as a Y1/OS program (software/compiler/c/target/NAME.c): its assembly, the assembler's verdict"""
    os.makedirs(B, exist_ok=True)
    shutil.copy(twin.DEF, B); open(os.path.join(B, "rcasm.rc"), "w").write("-h\n")
    c = os.path.join(CDIR, "target", lim + ".c")
    r = sh([sys.executable, PY, c, "-o", os.path.join(B, lim + ".asm"), "--org", "0x5000", "--os"], cwd=ROOT)
    if r.returncode: sys.exit("passes: y1cc.py cannot compile %s: %s" % (src, r.stderr.strip()))
    r = sh([ASM, lim, "-d=yacc1"], cwd=B)
    m = {k: re.search(p, r.stdout) for k, p in (("errors", r"(\d+) Errors"), ("labels", r"(\d+) Labels"),
                                                 ("object", r"Object Code:(\d+) bytes"))}
    return open(os.path.join(B, lim + ".asm")).read(), {k: int(v.group(1)) if v else None for k, v in m.items()}


def defined_in(paths):
    names = set()
    for p in paths:
        for m in re.finditer(r"^\w[\w\s\*]*?\b(\w+)\s*\([^;{]*\)\s*\{", open(p).read(), re.M): names.add(m.group(1))
    return names


def stack_table(asm, name):
    """per function: the call sites (callee, bytes on the stack below the function's entry, return address
    included) and the deepest point of its own code; the functions of the Y1/OS I/O layer are folded into their
    callers (the Mac build has its own I/O)"""
    funcs = {}; cur = None; order = []
    for line in asm.splitlines():
        m = re.match(r"^f_(\w+):$", line)
        if m: cur = m.group(1); funcs[cur] = []; order.append(cur); continue
        m = re.match(r"^(rt_\w+):", line)
        if line.startswith("; runtime"): cur = line.split()[-1]; funcs[cur] = []; order.append(cur); continue
        if line.startswith(("; dropped", "bss_start")) or re.match(r"^\w+: DS ", line): continue
        if cur and (line.startswith(" ") or re.match(r"^\w+:", line)): funcs[cur].append(line)
    sites = {}; local = {}
    for f, lines in funcs.items():
        d = 0; mx = 0; r6 = 0; lab = {}; dead = False; s = []
        warn = not f.startswith("rt_f")              # rt_fsave / rt_frest push and pop in a loop: counted at their calls
        for line in lines:
            m = re.match(r"^(\w+):\s*(.*)$", line)
            if m:
                if m.group(1) in lab:
                    if dead: d = lab[m.group(1)]
                    elif lab[m.group(1)] != d and warn: print("  stack: depth differs at %s in %s" % (m.group(1), f))
                lab[m.group(1)] = d; dead = False
                line = m.group(2)
                if not line: continue
            parts = line.split(None, 1); mn = parts[0].upper(); arg = parts[1].split(";")[0].strip() if len(parts) > 1 else ""
            if mn == "PUSHR": d += 2
            elif mn == "POPR": d -= 2
            elif mn == "PUSH": d += 1
            elif mn == "POP": d -= 1
            elif mn == "MVIW" and arg.startswith("R6,") and arg[3:].isdigit(): r6 = int(arg[3:])
            elif mn == "JSR":
                if arg == "rt_fsave": s.append(("rt_fsave", d + 2 + r6)); d += r6
                elif arg == "rt_frest": s.append(("rt_frest", d + 2)); d -= r6
                elif arg.startswith("f_"): s.append((arg[2:], d + 2))
                elif arg.startswith("rt_"): s.append((arg, d + 2))
                else: s.append(("<bios>", d + 2 + BIOS_STACK))
            elif mn == "JSRUR": s.append(("<syscall>", d + 2 + SYSCALL_STACK))
            elif mn in ("BR", "BRZ", "BRNZ", "BREQ", "BRNEQ", "BRLT", "BRGT") and re.match(r"^\w+$", arg) and not arg.isdigit():
                lab.setdefault(arg, d)
                if arg in lab and lab[arg] != d and warn: print("  stack: depth differs at a branch to %s in %s" % (arg, f))
            if mn in ("BR", "RET", "BRUR"): dead = True
            mx = max(mx, d)
        sites[f] = s; local[f] = mx
    return sites, local


def static_depth(f, sites, local, seen=()):
    """the deepest point below f's entry, following its calls (for the functions the probe does not see)"""
    if f in ("<bios>", "<syscall>"): return 0
    if f in seen or f not in sites: return local.get(f, 0)
    return max([local[f]] + [n + static_depth(g, sites, local, seen + (f,)) for g, n in sites[f]])


def write_probe_table(asm, src, lim, path):
    sites, local = stack_table(asm, lim)
    pass_funcs = defined_in([os.path.join(CDIR, p) for p in (src + ".c", "pcommon.c", "pnames.c", "past.c", "plabel.c")])
    with open(path, "w") as out:
        out.write("P %s\n" % lim)
        for f in sites:
            if f not in pass_funcs and f != "main": continue
            deep = local[f]                          # its own code, and whatever it calls that the probe cannot see
            for g, n in sites[f]:
                if g not in pass_funcs: deep = max(deep, n + static_depth(g, sites, local))
            out.write("F %s %d\n" % (f, deep))
        for f in sites:
            best = {}
            for g, n in sites[f]:
                if g in pass_funcs: best[g] = max(best.get(g, 0), n)
            for g, n in best.items(): out.write("E %s %s %d\n" % (f, g, n))


def build_probes():
    """cc1_s..cc9_s: each pass on the Mac with its Y1/OS table sizes, instrumented; the driver y1ccps"""
    cc = ["cc", "-std=c89", "-O0", "-w", "-I" + CDIR]
    for n, src, lim in PASSES:
        w = os.path.join(B, "probe_%s.c" % lim)
        limits = open(os.path.join(CDIR, "ylim", lim + ".h")).read()
        # the one table that differs: the paths of the source files, which on the Mac are absolute and several
        # times longer than on Y1/OS (/SRC/C/CC1_LEX.C)
        limits = re.sub(r"#define PATHPOOL\s+\d+", "#define PATHPOOL %d" % HOST_PATHPOOL, limits)
        open(os.path.join(B, "probe_lim_%s.h" % lim), "w").write(limits)
        open(w, "w").write('#include "%s/probe_lim_%s.h"\n#include "%s/%s.c"\n' % (B, lim, CDIR, src))
        o = os.path.join(CDIR, "cc%d_s" % n)
        r = sh(cc + ["-finstrument-functions", "-c", w, "-o", w[:-2] + ".o"])
        if r.returncode: sys.exit("passes: " + r.stderr)
        r = sh(cc + ['-DPROBE_NAME="%s"' % lim, w[:-2] + ".o", os.path.join(CDIR, "host_io.c"),
                     os.path.join(CDIR, "stackprobe.c"), "-o", o])
        if r.returncode: sys.exit("passes: " + r.stderr)
    shutil.copy(os.path.join(CDIR, "y1ccp"), os.path.join(CDIR, "y1ccps"))


def main():
    verbose = "-v" in sys.argv
    r = sh(["make", "-s", "-C", CDIR, "passes"])
    if r.returncode: sys.exit(r.stdout + r.stderr)
    rows = []; tables = os.path.join(B, "stack")
    os.makedirs(tables, exist_ok=True)
    for n, src, lim in PASSES:
        asm, verdict = build_target(src, lim)
        code, data, bss = twin.estimate(asm)
        write_probe_table(asm, src, lim, os.path.join(tables, lim + ".txt"))
        rows.append((n, src, lim, code, data, bss, verdict))
    build_probes()
    out = os.path.join(B, "stack.out")
    if os.path.exists(out): os.remove(out)
    items = list(corpus.items())                    # (the passes themselves are in it: tag "pass")
    same = errs = 0; nofit = []; bad = []; tmp = os.path.join(B, "cap"); small = 0; big = []
    keep = os.path.join(tmp, "keep")
    os.makedirs(keep, exist_ok=True)
    for i, (tag, src, opts) in enumerate(items):
        pa = os.path.join(tmp, "%d.py.asm" % i); ca = os.path.join(tmp, "%d.t.asm" % i)
        p = sh([sys.executable, PY, src, "-o", pa] + opts, cwd=ROOT)
        env = dict(os.environ, Y1STACK_OUT=out, Y1STACK_TABLE_DIR=tables, Y1CCP_KEEP=keep)  # each probe: its table
        c = subprocess.run([os.path.join(CDIR, "y1ccps"), src, "-o", ca] + opts, cwd=ROOT, env=env,
                           capture_output=True, text=True, errors="replace")
        if c.returncode == 0:                       # Y1/OS files end at 64K: the largest file of this compile
            sizes = [(os.path.getsize(os.path.join(keep, f)), f[2:]) for f in os.listdir(keep) if f.startswith("w.")]
            sizes.append((os.path.getsize(ca), "asm"))
            mx = max(sizes)
            if mx[0] < 65536: small += 1
            else: big.append((mx[0], mx[1], src))
        if p.returncode:
            if c.returncode and c.stderr.strip() == p.stderr.strip(): errs += 1
            elif c.returncode and ("too many" in c.stderr or "full" in c.stderr or "too big" in c.stderr or
                                   "too deep" in c.stderr or "too long" in c.stderr):
                nofit.append((src, opts, c.stderr.strip()))
            else: bad.append((src, opts, "error: py %r, chain %r" % (p.stderr.strip()[-100:], c.stderr.strip()[-100:])))
            continue
        if c.returncode:
            nofit.append((src, opts, c.stderr.strip())); continue
        if corpus.normalize(open(pa, encoding="latin1").read()) == corpus.normalize(open(ca, encoding="latin1").read()): same += 1
        else: bad.append((src, opts, "assembly differs"))
    deep = {}
    for line in open(out) if os.path.exists(out) else []:
        name, d, unk = line.split()
        deep[name] = max(deep.get(name, 0), int(d))
        if int(unk) and verbose: print("  probe: %s met %s unmeasured calls" % (name, unk))
    print("%-4s %-11s %6s %5s %6s %6s %6s %6s %6s  %s" % ("pass", "", "code", "data", "image", "tables", "stack",
                                                         "total", "free", "assembler"))
    worst = 0
    for n, src, lim, code, data, bss, v in rows:
        st = deep.get(lim, 0); tot = code + data + bss + st
        worst = max(worst, tot)
        print("cc%-2d %-11s %6d %5d %6d %6d %6d %6d %6d  %s errors, %s labels%s" % (
            n, src[4:], code, data, code + data, bss, st, tot, AREA - tot, v["errors"], v["labels"],
            "" if v["object"] == code + data else ", OBJECT CODE %s" % v["object"]))
    print("compiled by the chain with the Y1/OS table sizes: %d identical, %d identical errors, %d do not fit, "
          "%d DIFFERENT" % (same, errs, len(nofit), len(bad)))
    for src, opts, why in nofit: print("  does not fit: %-44s %-24s %s" % (src, " ".join(opts), why))
    for src, opts, why in bad: print("  DIFFERENT: %s %s %s" % (src, " ".join(opts), why))
    big.sort(reverse=True)
    print("files: %d compiles keep every intermediate file and the output under Y1/OS's 64K; %d do not (the "
          "largest: %s)" % (small, len(big), ", ".join("%s %s %d" % (os.path.basename(s), f, n) for n, f, s in big[:6])))
    if verbose:
        for n, f, s in big: print("  over 64K: %-50s %-4s %d" % (s, f, n))
    sys.exit(1 if bad or worst > AREA else 0)


if __name__ == "__main__":
    main()
