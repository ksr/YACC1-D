#!/usr/bin/env python3
"""tests/native/profile.py - where the native compiler's time goes (2026-09-25): instructions per function.

Runs programs of tests/native/run.py's list through the native compiler and assembler on the instruction-level
emulator with its PC histogram (`emulator -P FILE`: a block of per-address counts for every program Y1/OS starts),
then names the addresses: the program area ($5000-$CFFF) from the running program's assembly (the pass, /BIN/CC,
/BIN/ASM: os/build), the OS ($1000-$4FFF) from the OS's (the assembly or the C one, as os/build/os-sel says), the
ROM as one entry. An address counts for the nearest label before it that is not one of y1cc's generated ones
(`Ltop12`...), so a C function's count includes its loops; in the OS a routine's local labels (`fg_in`) count apart.
The labels' addresses come from the host assembler's listing (-l) of the same assembly.

  profile.py [name ...] [-n N] [--no-all]
    name       programs of run.py's PROGRAMS (default: hello fib cecho ccat cc4)
    -n N       the N biggest functions of each step (default 12)
    --no-all   without the summary over every step (by step, the biggest functions overall, the OS's share)
The tables go to stdout; nothing is checked (run.py does that). The work files are in tests/native/build/profile.
"""
import os, sys, re, subprocess, shutil, collections
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import run

OS = run.OS
ASM = run.ASM
BUILD = os.path.join(HERE, "build", "profile")       # (git-ignored, as run.py's build/)


def labels_of(asm_path, tag):
    """[(address, name)] of the function labels of an assembly file, from the host assembler's listing"""
    d = os.path.join(BUILD, "lst", tag); os.makedirs(d, exist_ok=True)
    src_dir = os.path.dirname(asm_path)
    for f in os.listdir(src_dir):                       # the file and whatever it INCLUDEs beside it
        if f.endswith((".asm", ".inc")): shutil.copy(os.path.join(src_dir, f), d)
    shutil.copy(run.twin.DEF, d); open(os.path.join(d, "rcasm.rc"), "w").write("-h\n-l\n")
    base = os.path.basename(asm_path)[:-4]
    shutil.copy(asm_path, os.path.join(d, base + ".asm"))
    lst = subprocess.run([ASM, base, "-d=yacc1"], cwd=d, capture_output=True, text=True, errors="replace").stdout
    out = []
    for line in lst.splitlines():
        m = re.match(r"^\s*\d+ ([0-9a-fA-F]{4}):(?: [0-9a-fA-F]{2})*\s+(\w+):", line)
        if m and not re.match(r"^L[a-z]+\d+$", m.group(2)): out.append((int(m.group(1), 16), m.group(2)))
    out.sort()
    return out


def name_of(labels, addr):
    lo, hi = 0, len(labels) - 1; best = None
    while lo <= hi:
        mid = (lo + hi) // 2
        if labels[mid][0] <= addr: best = labels[mid][1]; lo = mid + 1
        else: hi = mid - 1
    return best or "?"


def main():
    av = sys.argv[1:]
    n = 12
    if "-n" in av: n = int(av[av.index("-n") + 1]); del av[av.index("-n"):av.index("-n") + 2]
    names = [a for a in av if not a.startswith("-")] or ["hello", "fib", "cecho", "ccat", "cc4"]
    progs = [p for p in run.PROGRAMS if p[0] in names]
    shutil.rmtree(BUILD, ignore_errors=True); os.makedirs(BUILD)
    run.BUILD = BUILD
    run.sh(["make", "-s", "-C", OS])
    oskind = open(os.path.join(OS, "build/os-sel")).read().strip() if os.path.exists(os.path.join(OS, "build/os-sel")) else "asm"
    oslab = labels_of(os.path.join(OS, "build", "asm" if oskind == "asm" else "c", "y1os.asm"), "os")
    img = os.path.join(BUILD, "prof.img")
    run.make_disk(progs, img)
    hist = os.path.join(BUILD, "pc.txt")
    subprocess.run([run.EMUS["int"], "-x", "-m", "-c", img, "-l", "40000000000", "-P", hist],
                   input=run.script(progs).encode(), capture_output=True)
    blocks = []; cur = None
    for line in open(hist):
        if line.startswith("program"): cur = collections.Counter(); blocks.append(cur); continue
        a, c = line.split(); cur[int(a, 16)] += int(c)
    blocks = blocks[1:]                                 # block 0: the monitor and the boot
    steps = []
    for p in progs:
        for w in run.steps_of(p): steps.append((p, w))
    if len(blocks) != len(steps): sys.exit("profile: %d program blocks, expected %d" % (len(blocks), len(steps)))
    cache = {}

    def prog_labels(p, w):
        if w == "cc": f = os.path.join(OS, "build/bin/cc.asm")
        elif w == "asm": f = os.path.join(OS, "build/bin/asm.asm")
        elif w.startswith("cc"): f = os.path.join(OS, "build/cc", run.PASSN[int(w[2:]) - 1] + ".asm")
        else: return []
        if f not in cache: cache[f] = labels_of(f, os.path.basename(f)[:-4])
        return cache[f]

    total = collections.Counter(); bystep = collections.Counter()
    for (p, w), b in zip(steps, blocks):
        if w in ("run", "ref"): continue
        pl = prog_labels(p, w); fc = collections.Counter()
        for a, c in b.items():
            if 0x5000 <= a < 0xD000: fc[name_of(pl, a)] += c
            elif 0x1000 <= a < 0x5000: fc["OS " + name_of(oslab, a)] += c
            elif a >= 0xE000: fc["ROM"] += c
            else: fc["other $%04X" % a] += c
        s = sum(fc.values()); bystep[w] += s
        for k, v in fc.items(): total[(w, k)] += v
        print("%s %s: %d instructions; %s" % (p[0], w, s, ", ".join(
            "%s %.1f%%" % (k, 100.0 * v / s) for k, v in fc.most_common(n))))
    if "--no-all" not in av:
        allsum = sum(bystep.values())
        print("\nall compiles and assemblies: %d instructions" % allsum)
        print("by step: " + ", ".join("%s %.1f%%" % (k, 100.0 * v / allsum) for k, v in
                                      sorted(bystep.items(), key=lambda kv: -kv[1])))
        byfn = collections.Counter()
        for (w, k), v in total.items(): byfn[k if k.startswith(("OS ", "ROM")) else "%s:%s" % (w, k)] += v
        print("the biggest: " + ", ".join("%s %.1f%%" % (k, 100.0 * v / allsum) for k, v in byfn.most_common(3 * n)))
        osf = collections.Counter()
        for (w, k), v in total.items():
            if k.startswith("OS "): osf[k] += v
        print("the OS: %.1f%% of it; %s" % (100.0 * sum(osf.values()) / allsum, ", ".join(
            "%s %.1f%%" % (k[3:], 100.0 * v / allsum) for k, v in osf.most_common(n))))
    shutil.rmtree(BUILD, ignore_errors=True)


if __name__ == "__main__":
    main()
