#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""speed.py - where the machine's time goes (2026-11-05): a shell line under Y1/OS, measured in clocks.

  speed.py [--dir PATH] [--top N] [--cmd LINE] [target ...]
    make [target ...] in PATH on the disk (default /src/os/commands, everything); --cmd runs LINE there instead
    --top N   the N biggest functions (default 25)

Boots a copy of os/disk.img on the instruction-level emulator with its PC histogram (`emulator -P`: a block for every
program Y1/OS starts, with instructions and clocks per address, the opcodes, the CF sectors). The clocks come from
software/opclocks.h, every opcode's length in the microcode, so they are the machine's, not an estimate: every opcode
has one length (tests/native/clocks.py checks the total against the microcode emulator). The time is at 1 MHz.

Prints the total; the time by program (each compiler pass, asm, make...); by where it runs (the program, the OS, the
ROM's routines); the biggest functions; the opcodes by clocks; the sectors read and written. Addresses are named from
the host assembler's listings, as tests/native/profile.py does. The session's own echoed lines say which program each
block is. Boot and the shell before the first program are left out; the time in the shell between programs is
in the block of the program before it. Work files in tools/build/speed (git-ignored).
"""
import os, re, sys, shutil, subprocess, collections
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OS = os.path.join(ROOT, "os")
B = os.path.join(HERE, "build", "speed")
EMU = os.path.join(ROOT, "software/emulator/emulator")
ASM = os.path.join(ROOT, "software/assembler/asm")
DEF = os.path.join(ROOT, "software/assembler/yacc1.def")
PASSN = "lex parse decl calls layout stmt sema emit final".split()


def labels_of(path, tag):
    """[(address, name)] of a source's labels (not y1cc's generated ones), from the host assembler's listing"""
    d = os.path.join(B, "lst", tag)
    os.makedirs(d, exist_ok=True)
    src = os.path.dirname(path)
    for f in os.listdir(src):
        if f.endswith((".asm", ".inc")) and os.path.isfile(os.path.join(src, f)): shutil.copy(os.path.join(src, f), d)
    shutil.copy(DEF, d)
    open(os.path.join(d, "rcasm.rc"), "w").write("-h\n-l\n")
    base = os.path.basename(path)[:-4]
    lst = subprocess.run([ASM, base, "-d=yacc1"], cwd=d, capture_output=True, text=True, errors="replace").stdout
    out = []
    for line in lst.splitlines():
        m = re.match(r"^\s*\d+ ([0-9a-fA-F]{4}):(?: [0-9a-fA-F]{2})*\s+(\w+):", line)
        if m and not re.match(r"^(L[a-z]+\d+|[a-z_]+_[a-z]+\d+)$", m.group(2)): out.append((int(m.group(1), 16), m.group(2)))
    return sorted(out)


def name_of(labels, addr):
    lo, hi, best = 0, len(labels) - 1, "?"
    while lo <= hi:
        mid = (lo + hi) // 2
        if labels[mid][0] <= addr: best = labels[mid][1]; lo = mid + 1
        else: hi = mid - 1
    return best


def hm(clocks):
    s = clocks / 1e6
    return "%dh %02dm %02ds" % (s // 3600, s % 3600 // 60, s % 60) if s >= 3600 else "%dm %02ds" % (s // 60, s % 60)


def opnames():
    """opcode -> mnemonic, from firmware/opcodes.h"""
    names = {}
    for line in open(os.path.join(ROOT, "firmware/opcodes.h"), errors="replace"):
        m = re.match(r"\s*#define\s+(\w+)\s+0[xX]([0-9a-fA-F]+)", line)
        if m and not m.group(1).startswith("OPCODE_") and int(m.group(2), 16) < 256: names.setdefault(int(m.group(2), 16), m.group(1))
    return names


def main():
    av = sys.argv[1:]
    def opt(name, dflt):
        if name in av:
            i = av.index(name); v = av[i + 1]; del av[i:i + 2]; return v
        return dflt
    where = opt("--dir", "/src/os/commands"); top = int(opt("--top", "25")); cmd = opt("--cmd", None)
    line = cmd or " ".join(["make"] + av)
    subprocess.run(["make", "-s", "-C", OS], check=True)
    shutil.rmtree(B, ignore_errors=True); os.makedirs(B)
    img, hist = os.path.join(B, "disk.img"), os.path.join(B, "pc.txt")
    shutil.copy(os.path.join(OS, "disk.img"), img)
    r = subprocess.run([EMU, "-x", "-m", "-c", img, "-l", "400000000000", "-P", hist],
                       input=("O\ncd %s\n%s\nexit\n0\n" % (where, line)).encode(), capture_output=True)
    out = r.stdout.decode("latin1")
    open(os.path.join(B, "session.txt"), "w").write(out)
    if "sh: stopped" in out: print("speed: a script stopped (tools/build/speed/session.txt)")

    blocks, cur = [], None
    for ln in open(hist):
        w = ln.split()
        if w[0] == "program":
            cur = dict(pc=collections.Counter(), ins=0, clk=0, op=collections.Counter(), cfr=0, cfw=0); blocks.append(cur)
        elif w[0] == "op": cur["op"][int(w[1], 16)] += int(w[2])
        elif w[0] == "cf": cur["cfr"] += int(w[1]); cur["cfw"] += int(w[2])
        else:
            cur["pc"][int(w[0], 16)] += int(w[2]); cur["ins"] += int(w[1]); cur["clk"] += int(w[2])
    boot = blocks[0]; blocks = blocks[1:]

    # which program each block is: the session echoes every line of make.sh
    names = [line.split()[0].lower()]
    for m in re.finditer(r"> (cc|asm|del|cp|make|mkdisk|sysgen) ", out):
        w = m.group(1)
        names += ["cc"] + ["cc%d" % i for i in range(1, 10)] if w == "cc" else [w]
    names += ["?"] * max(0, len(blocks) - len(names))
    if len(names) > len(blocks): names = names[:len(blocks)]

    def prog_labels(w, cache={}):
        f = None
        if w == "asm": f = os.path.join(OS, "build/asma/asm.asm")
        elif re.match(r"cc\d$", w): f = os.path.join(OS, "build/cc", PASSN[int(w[2:]) - 1] + ".asm")
        elif w in ("cc", "make", "cp", "del"): f = os.path.join(OS, "build/bin", w + ".asm")
        if not f or not os.path.exists(f): return []
        if f not in cache: cache[f] = labels_of(f, os.path.basename(f)[:-4] + "_" + w)
        return cache[f]

    oslab = labels_of(os.path.join(OS, "build/asm/y1os.asm"), "os")
    romlab = labels_of(os.path.join(ROOT, "firmware/monitor/monitor.asm"), "rom")
    byprog = collections.Counter(); runs = collections.Counter(); area = collections.Counter(); fn = collections.Counter()
    ops = collections.Counter(); cfr = cfw = ins = 0
    for w, b in zip(names, blocks):
        byprog[w] += b["clk"]; runs[w] += 1; ins += b["ins"]; ops.update(b["op"]); cfr += b["cfr"]; cfw += b["cfw"]
        pl = prog_labels(w)
        for a, c in b["pc"].items():
            if 0x5000 <= a < 0xD000:
                area["the program"] += c; fn[w + " " + name_of(pl, a)] += c
            elif 0x1000 <= a < 0x5000:
                area["the OS"] += c; fn["OS " + name_of(oslab, a)] += c
            elif a >= 0xE000:
                area["the ROM"] += c; fn["ROM " + name_of(romlab, a)] += c
            else: area["other"] += c
    total = sum(byprog.values())
    print("%s, in %s" % (line, where))
    print("  %d clocks = %s at 1 MHz; %d instructions, %.2f clocks an instruction; %d programs started" %
          (total, hm(total), ins, total / max(ins, 1), len(blocks)))
    print("  CF: %d sectors read, %d written" % (cfr, cfw))
    print("  (booting the OS first: %s, not counted)" % hm(boot["clk"]))
    print("\nby program:")
    for w, c in sorted(byprog.items(), key=lambda kv: -kv[1]):
        print("  %-8s %5.1f%%  %11s  %d run%s" % (w, 100 * c / total, hm(c), runs[w], "" if runs[w] == 1 else "s"))
    print("\nby where it runs:")
    for w, c in area.most_common(): print("  %-12s %5.1f%%  %s" % (w, 100 * c / total, hm(c)))
    print("\nthe %d biggest functions:" % top)
    for w, c in fn.most_common(top): print("  %5.1f%%  %s" % (100 * c / total, w))
    nm = opnames()
    sys.path.insert(0, HERE)
    clk = {}
    for m in re.finditer(r"(\d+),", open(os.path.join(ROOT, "software/opclocks.h")).read().split("{", 1)[1]): clk[len(clk)] = int(m.group(1))
    print("\nthe opcodes by clocks:")
    for o, n in sorted(ops.items(), key=lambda kv: -kv[1] * clk.get(kv[0], 0))[:15]:
        name = nm.get(o) or ("%s R%d" % (nm[o & 0xF8], o & 7) if (o & 0xF8) in nm else "$%02X" % o)
        print("  %5.1f%%  %-10s %3d clocks x %9d" % (100 * n * clk.get(o, 0) / total, name, clk.get(o, 0), n))


if __name__ == "__main__":
    main()
