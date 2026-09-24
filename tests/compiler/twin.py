#!/usr/bin/env python3
"""twin.py - y1cc.py against its C twin software/compiler/c/y1cc (2026-09-24): the whole compile corpus
(tests/compiler/corpus.py: the compiler tests in four option sets, the bench sources, os/y1os.c, every /BIN command,
tests/os programs, and software/compiler/c/target.c = y1cc.c compiling itself) through both compilers; the assembly
must be byte-identical (the header's timestamp masked), an expected compile error must be the same message, and
the -l summary must be the same line.

  twin.py [-v] [--keep] [--16] [name ...]   name = a corpus path substring to run only those; --16 = the check
                                       build y1cc16 (int = unsigned short, unsigned char: the YACC1's types)
  twin.py --size ASM                   (make target) the size of y1cc.c compiled by y1cc.py against the 32K area

Builds the twin first (make -C software/compiler/c). Exit 1 on any difference.
"""
import os, sys, subprocess, shutil, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus

ROOT = corpus.ROOT
PY = os.path.join(ROOT, "software/compiler/y1cc.py")
CDIR = os.path.join(ROOT, "software/compiler/c")
TWIN = os.path.join(CDIR, "y1cc")
BUILD = os.path.join(corpus.HERE, "build", "twin")


def run(cmd, out):
    r = subprocess.run(cmd + ["-o", out, "-l"], cwd=ROOT, capture_output=True)
    text = corpus.normalize(open(out, encoding="latin1").read()) if r.returncode == 0 and os.path.exists(out) else None
    summary = r.stdout.decode("latin1").replace(out, "OUT").strip()
    return r.returncode, text, summary, r.stderr.decode("latin1").strip()


DEF = os.path.join(ROOT, "software/assembler/yacc1.def")


def def_sizes():
    """Instruction lengths from the assembler's own pattern file: each pattern line is followed by its output
    bytes (`04 hi(1) lo(1)` = 3 bytes)."""
    lines = open(DEF).read().splitlines()
    i = lines.index("*") + 1; sizes = {}
    while i + 1 < len(lines) and lines[i].strip() != "*":
        mn = lines[i].split()[0].upper(); n = len(lines[i + 1].split()); i += 2
        sizes.setdefault(mn, n)
    return sizes


def estimate(text, sizes=None):
    """(code, data, bss) bytes of an assembly text: instructions by yacc1.def, DB/DW by their items, DS = bss.
    Checked against the assembler's Object Code on the whole corpus (make target prints the check)."""
    sizes = sizes or def_sizes(); code = data = bss = 0
    for line in text.splitlines():
        if line.startswith(";"): continue
        m = re.match(r"^\w+:\s*(.*)$", line); rest = (m.group(1) if m else line).split(";")[0].strip()
        if not rest: continue
        mn, _, args = rest.partition(" "); mn = mn.upper(); args = args.strip()
        if mn in ("ORG", "END"): continue
        if mn == "DB": data += len(args.split(","))
        elif mn == "DW": data += 2 * len(args.split(","))
        elif mn == "DS": bss += int(args, 0)
        else: code += sizes[mn]
    return code, data, bss


def size_report(asm):
    """(make target) the size of y1cc.c compiled by y1cc.py as a Y1/OS program: too big for the assembler (over
    1,000 labels, over 64K), so the bytes are counted from the assembly with yacc1.def's instruction lengths;
    the count is first checked against the assembler on every corpus program that assembles."""
    sizes = def_sizes(); ok = bad = 0
    tmp = os.path.join(BUILD, "sizecheck"); os.makedirs(tmp, exist_ok=True)
    shutil.copy(DEF, tmp); open(os.path.join(tmp, "rcasm.rc"), "w").write("-h\n")
    for i, (tag, src, opts) in enumerate(corpus.items()):
        if tag in ("err", "self"): continue
        a = os.path.join(tmp, "p%d.asm" % i)
        if subprocess.run([sys.executable, PY, src, "-o", a] + opts, cwd=ROOT, capture_output=True).returncode: continue
        r = subprocess.run([os.path.join(ROOT, "software/assembler/asm"), "p%d" % i, "-d=yacc1"], cwd=tmp,
                           capture_output=True, text=True, errors="replace")
        m = re.search(r"Object Code:(\d+) bytes", r.stdout)
        c, d, _ = estimate(open(a).read(), sizes)
        if m and int(m.group(1)) == c + d: ok += 1
        else: bad += 1; print("  size estimate differs for %s %s: %s vs %d" % (src, opts, m and m.group(1), c + d))
    shutil.rmtree(tmp, ignore_errors=True)
    print("size count checked against the assembler: %d programs exact, %d differ" % (ok, bad))
    text = open(asm).read()
    code, data, bss = estimate(text, sizes)
    area = 0xD000 - 0x5000
    print("y1cc.c as a Y1/OS program: code %d + data %d = image %d bytes, + uninitialised %d = %d bytes, "
          "against the %d-byte program area ($5000-$CFFF): %.1f times it (%d bytes over); the image alone is "
          "%s the 64K address space" % (code, data, code + data, bss, code + data + bss, area,
                                        (code + data + bss) / area, code + data + bss - area,
                                        "OVER" if code + data > 65536 else "within"))
    lines = text.splitlines(); funcs = []; cur = None; n = 0
    for l in lines:
        m = re.match(r"^(f_\w+):$", l)
        if m or l.startswith("; runtime") or l.startswith("; dropped"):
            if cur: funcs.append((n, cur))
            cur = m.group(1)[2:] if m else None; n = 0; continue
        if cur and l.startswith("        "): n += estimate(l, sizes)[0]
    funcs.sort(reverse=True)
    groups = {}
    for n, f in funcs:
        g = ("lexer" if f.startswith("lx_") or f in ("lex_one", "skip_space", "split_word", "esc_val", "parse_int0") else
             "parser" if f in ("program", "toplevel", "struct_def", "base_and_ptr", "initializer", "param", "block",
                               "stmt", "expr", "assign", "assign_op", "logic_or", "logic_and", "binary", "in_level",
                               "unary", "postfix", "primary", "const_expr", "tok_name", "need_tok", "tk", "tv",
                               "is_op", "is_kw", "perr", "perr_tok", "e_tok", "eat", "accept", "accept_kw",
                               "is_type_start") else
             "runtime text (emit_runtime)" if f in ("emit_runtime", "rt", "rtn") else
             "target I/O + lib_fs" if f in ("io_argc", "io_arg", "io_open", "io_getc", "io_close", "io_find",
                                           "io_create", "io_put", "io_finish", "io_out", "io_fail", "io_date",
                                           "main", "fopen", "fgetc", "fclose", "fcreate", "fputc", "fresolve",
                                           "argword") else
             "code generator")
        groups[g] = groups.get(g, 0) + n
    print("%d functions, %d bytes of code; by part: %s" % (len(funcs), sum(n for n, _ in funcs),
          ", ".join("%s %d" % kv for kv in sorted(groups.items(), key=lambda kv: -kv[1]))))
    print("the biggest functions: " + ", ".join("%s %d" % (f, n) for n, f in funcs[:12]))


def main():
    av = sys.argv[1:]
    if av and av[0] == "--size": size_report(av[1]); return
    verbose = "-v" in av; keep = "--keep" in av
    only = [a for a in av if not a.startswith("-")]
    twin, target = (TWIN + "16", "y1cc16") if "--16" in av else (TWIN, "y1cc")
    r = subprocess.run(["make", "-s", "-C", CDIR, target], capture_output=True, text=True)
    if r.returncode or r.stderr.strip():
        sys.exit("twin: building the C twin failed or warned:\n" + r.stdout + r.stderr)
    shutil.rmtree(BUILD, ignore_errors=True)
    for side in ("py", "c"): os.makedirs(os.path.join(BUILD, side))
    same = errs = 0; bad = []
    for i, (tag, src, opts) in enumerate(corpus.items()):
        if only and not any(o in src for o in only): continue
        base = "%03d_%s_%s.asm" % (i, tag, os.path.basename(src)[:-2])
        p = run([sys.executable, PY, src] + opts, os.path.join(BUILD, "py", base))
        c = run([twin, src] + opts, os.path.join(BUILD, "c", base))
        if p[0] == 0:
            ok = c[0] == 0 and p[1] == c[1] and p[2] == c[2]
            why = "" if ok else ("C twin failed: " + c[3][-200:] if c[0] else
                                 "assembly differs" if p[1] != c[1] else "-l summary differs: %r / %r" % (p[2], c[2]))
            same += ok
        else:
            ok = c[0] != 0 and p[3] == c[3]
            why = "" if ok else "error: y1cc.py %r, twin %r" % (p[3][-160:], c[3][-160:])
            errs += ok
        if not ok: bad.append((src, opts, why))
        if verbose or not ok:
            print("%-44s %-30s %s" % (src, " ".join(opts), "identical" if ok and p[0] == 0 else
                                      "same error" if ok else "DIFFERENT: " + why), flush=True)
    print("twin%s: %d programs identical, %d identical errors, %d DIFFERENT" % (" (y1cc16: 16-bit int, unsigned char)"
          if "--16" in av else "", same, errs, len(bad)))
    if not keep and not bad: shutil.rmtree(BUILD, ignore_errors=True)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
