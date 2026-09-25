#!/usr/bin/env python3
"""gen_y1_optab.py - the native assembler's instruction table, generated from software/assembler/yacc1.def
(2026-09-25), so that /BIN/ASM (os/commands/asm.c) and the host assembler (software/assembler, RC/asm) can never
disagree about an instruction.

  gen_y1_optab.py [DEF] [-o os/asm_optab.c]      write the table (default: yacc1.def -> os/asm_optab.c)
  gen_y1_optab.py --check                          exit 1 if os/asm_optab.c is not what yacc1.def gives (tests/asm)

The .def file is read the way RC/asm's Read_Def_File() reads it (asm.c): a title line, CLASS blocks up to a `*`,
then two lines per translation (the pattern, trimmed; the construction line as read) up to the next `*`. Each
construction line is compiled here by a Python copy of RC/asm's Translate() (asmcmds.c) that records what it would
do instead of doing it, so the target only interprets a short list of operations; the patterns are kept in RC/asm's
order and grouped by their first word (the mnemonic), which WildMatch() must match literally anyway.

The C file (y1cc subset: numeric array initialisers only) holds:
  op_cnK[], op_cvK[]  operand class K: its names (`len name` each, in .def order, then 0) and their values;
             op_cn[] / op_cv[] point at them
  op_bN[]    hash chain N: its records one after the other, then a 0; a record is the mnemonic, 0, the number of
             patterns, then per pattern its operand shape (ends with 0), the number of operation bytes, the
             operations. The chain of a mnemonic is ophash(mnemonic, OPSEED), as asm.c's hash() computes it, with
             the first seed that keeps every chain within one initialiser (MAXINIT).
  op_h0[], op_h1[]  the chains 0..31 and 32..63 (op_bx, a lone 0, for an empty one)
Operand shape bytes: 1 whitespace (one or more), 4 \\B (byte), 5 \\W (word), 6 \\L (byte list), 7 \\M (word list),
8+k class k, 33..126 that character literally.
Operations (B is the byte being built, as in Translate; the high nibble is the kind, i the argument):
  1 write B, B = 0          16+d B = B*16 + d         32+i B = arg i & 255 (\\n on a byte argument, lo(n))
  48+i B = bits 8-15 of arg i (hi(n))                 64+i B |= arg i & 255 (|n)      80+i B |= (arg i & 255) << 4 (|n<4)
  96 then m: B &= m         112+i the DB list in arg i (\\L), 120+i the DW list (\\M)
  128+i ORG   144+i DS   160+i END (the start address)   176+i EQU   192 a library directive RC/asm has and this
  assembler refuses (PUBLIC, EXTERN, LIB PROC/ENDP)    208 then n: B = n
B is followed at generation time while it is a constant, so a run of hex digits is one LIT (encode()); every
pattern's encoding is checked against a model of Translate on random arguments before the file is written.
A construction the target cannot interpret (\\N, \\D, %, |n>s ...) stops the generator with a message: add it to
asm.c and here together.
"""
import os, sys, random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEF = os.path.join(ROOT, "software/assembler/yacc1.def")
OUT = os.path.join(ROOT, "os/asm_optab.c")
OPHASH = 64                     # chains (asm.c: hash(mnemonic, n, OPSEED) & 63; op_h0[] holds 0..31, op_h1[] 32..63)
MAXINIT = 62                    # numbers in one initialiser: what y1cc's multi-pass compiler takes with its Y1/OS
                                # table sizes (software/compiler/c/ylim/decl.h NODES_MAX 128: 2 per number + 3)

WS, BYTE, WORD, LIST, MLIST, CLS = 1, 4, 5, 6, 7, 8
OUTB, DIG, ARG, HI, ORA, ORA4, AND, LISTB, LISTW, ORG, DS, END, EQU, UNSUP, LIT = \
    1, 16, 32, 48, 64, 80, 96, 112, 120, 128, 144, 160, 176, 192, 208


def ophash(name, seed):
    """asm.c hash(s, n, seed): h = seed, then h = h*5 + c over the bytes (16 bits), the two bytes XORed, mod 64."""
    h = seed
    for c in name.encode("latin1"):
        h = (h * 5 + c) & 0xFFFF
    return (h ^ (h >> 8)) % OPHASH


def fgets(f, n):
    """C fgets(buf, n, f): up to n-1 characters, the newline kept; '' at end of file."""
    s = ""
    while len(s) < n - 1:
        c = f.read(1)
        if not c: break
        s += c
        if c == "\n": break
    return s


def cut(s):                     # Buffer[strlen(Buffer)-1] = '\0'
    return s[:-1]


def ws(c):                      # RC/asm tests `c <= ' '` on signed chars: control characters, space and 128..255
    return ord(c) <= 32 or ord(c) >= 128


def trim(s):
    i = 0
    while i < len(s) and ws(s[i]): i += 1
    s = s[i:]
    while s and ws(s[-1]): s = s[:-1]
    return s


def read_def(path):
    f = open(path, "r", encoding="latin1", newline="")
    title = cut(fgets(f, 80))
    classes = []
    buf = cut(fgets(f, 80))
    while not buf.startswith("*"):
        if buf == "OPTION 16BIT":
            sys.exit("gen_y1_optab: OPTION 16BIT (2-byte address units) is not supported by the native assembler")
        if buf.startswith("CLASS"):
            name = buf[6:]
            text = cut(fgets(f, 200))
            entries = []
            for e in text.split(","):
                if "=" not in e: sys.exit("gen_y1_optab: class %s: bad entry %r" % (name, e))
                t, v = e.split("=", 1)
                entries.append((t, int(v)))
            classes.append((name, entries))
        buf = cut(fgets(f, 80))
    trans = []
    buf = fgets(f, 80)
    while not buf.startswith("*"):
        if buf == "": sys.exit("gen_y1_optab: no closing * in %s" % path)
        cmd = trim(buf)
        dest = fgets(f, 80)
        trans.append((cmd, dest))
        buf = fgets(f, 80)
    return title, classes, trans


def shape(cmd, classes):
    """The pattern after its first word -> shape bytes; also the argument kinds in order (B, W, L, M)."""
    i = 0
    while i < len(cmd) and not ws(cmd[i]): i += 1
    first, rest = cmd[:i], cmd[i:]
    if "\\" in first: sys.exit("gen_y1_optab: a wildcard in the mnemonic of %r" % cmd)
    out, kinds = [], []
    j = 0
    while j < len(rest):
        c = rest[j]
        if ws(c):
            while j < len(rest) and ws(rest[j]): j += 1
            out.append(WS); continue
        if c == "\\":
            k = rest[j + 1]
            if k == "B": out.append(BYTE); kinds.append("B"); j += 2
            elif k == "W": out.append(WORD); kinds.append("W"); j += 2
            elif k == "L": out.append(LIST); kinds.append("L"); j += 2
            elif k == "M": out.append(MLIST); kinds.append("M"); j += 2
            elif k == "{":
                e = rest.index("}", j)
                name = rest[j + 2:e]
                idx = [n for n, _ in classes].index(name) if name in [n for n, _ in classes] else None
                if idx is None: sys.exit("gen_y1_optab: unknown class %r in %r" % (name, cmd))
                out.append(CLS + idx); kinds.append("B"); j = e + 1
            else: sys.exit("gen_y1_optab: wildcard \\%s in %r is not supported by the native assembler" % (k, cmd))
            continue
        if not 33 <= ord(c) <= 126: sys.exit("gen_y1_optab: character %r in %r" % (c, cmd))
        out.append(ord(c)); j += 1
    return first, out, kinds


HEX = "0123456789ABCDEFabcdef"


def hexv(c):
    if c not in HEX: sys.exit("gen_y1_optab: %r is not a hex digit (RC/asm's char_to_hex would return garbage)" % c)
    return int(c, 16)


def translate(dest, kinds, cmd):
    """RC/asm Translate() (asmcmds.c) with the effects recorded as symbolic operations (tuples, see encode());
    noout decides the final write exactly as there."""
    if not dest.endswith("\n"): sys.exit("gen_y1_optab: construction of %r has no newline (Translate reads past it)" % cmd)
    d = dest + "\0\0\0"
    ops = []
    p = 0
    noout = " "

    def arg(ch):
        i = ord(ch) - 49
        if not 0 <= i < len(kinds): sys.exit("gen_y1_optab: argument %r out of range in %r" % (ch, cmd))
        return i
    while d[p] != "\0":
        if "0" <= d[p] <= "9": ops.append(("DIG", ord(d[p]) - 48))
        if "A" <= d[p] <= "F": ops.append(("DIG", ord(d[p]) - 55))
        for k in "OBSE":                        # four separate ifs in Translate, in this order
            if d[p] == "\\" and d[p + 1] == k:
                p += 2; i = arg(d[p]); p += 1
                ops.append(({"O": "ORG", "B": "DS", "S": "END", "E": "EQU"}[k], i)); noout = "Y"
        if d[p] == "\\" and d[p + 1] in "PRQX":
            return [("UNSUP",)]                 # library directives: the native assembler refuses them
        if d[p] == "|":
            p += 1; i = arg(d[p]); p += 1
            if d[p] == "<": p += 1; ops.append(("ORA", i, hexv(d[p])))
            elif d[p] == ">": sys.exit("gen_y1_optab: |n>s in %r is not supported by the native assembler" % cmd)
            else: p -= 1; ops.append(("ORA", i, 0))
            noout = " "
        if d[p] == "&":
            p += 1; j = hexv(d[p]) * 16; p += 1; j += hexv(d[p])
            ops.append(("AND", j)); noout = " "
        if d[p] == "%": sys.exit("gen_y1_optab: %% (nibble swap) in %r is not supported by the native assembler" % cmd)
        if d[p:p + 3] == "lo(":
            p += 3; i = arg(d[p]); ops.append(("ARG", i)); p += 1; noout = " "
        if d[p:p + 3] == "hi(":
            p += 3; i = arg(d[p]); ops.append(("HI", i)); p += 1; noout = " "
        if d[p] == "\\":
            p += 1; i = arg(d[p]); t = kinds[i]
            if t == "B": ops.append(("ARG", i)); noout = " "
            elif t in "LM": ops.append(("LIST", i, t)); noout = "Y"
            elif t == "W": pass                 # Translate does nothing for a word argument here
            else: sys.exit("gen_y1_optab: \\%s on a %s argument in %r" % (d[p], t, cmd))
        p += 1
        if d[p] == " ": ops.append(("OUT",)); p += 1; noout = "Y"
    if noout != "Y": ops.append(("OUT",))
    return ops


def encode(ops, cmd):
    """Symbolic operations -> the bytes asm.c's run() interprets. B's value is followed at generation time while it
    is a constant (hex digits, &mm on a constant, 0 after a write), so a run of digits becomes one LIT n, emitted
    only when B is used and not already that value at run time; a digit on an unknown B stays a DIG."""
    out = []
    k = 0                                        # B's value at generation time, None = depends on an argument
    rt = 0                                       # B's value at run time as far as known (None = unknown)

    def need():
        nonlocal rt
        if k is not None and rt != k: out.extend([LIT, k]); rt = k
    for op in ops:
        t = op[0]
        if t == "DIG":
            if k is not None: k = (k * 16 + op[1]) & 255
            else: out.append(DIG + op[1]); rt = None
        elif t == "OUT": need(); out.append(OUTB); k = rt = 0
        elif t == "ARG": out.append(ARG + op[1]); k = rt = None
        elif t == "HI": out.append(HI + op[1]); k = rt = None
        elif t == "ORA":
            if op[2] not in (0, 4): sys.exit("gen_y1_optab: |n<%d in %r is not supported by the native assembler" % (op[2], cmd))
            need(); out.append((ORA if op[2] == 0 else ORA4) + op[1]); k = rt = None
        elif t == "AND":
            if k is not None: k &= op[1]
            else: out.extend([AND, op[1]]); rt = None
        elif t == "LIST": out.append((LISTB if op[2] == "L" else LISTW) + op[1])
        elif t == "UNSUP": out.append(UNSUP)
        else: out.append({"ORG": ORG, "DS": DS, "END": END, "EQU": EQU}[t] + op[1])
    return out


def ref_run(ops, args):
    """Translate's effect on arguments args (the symbolic operations): the bytes written, the directives."""
    b, eff = 0, []
    for op in ops:
        t = op[0]
        if t == "DIG": b = (b * 16 + op[1]) & 255
        elif t == "OUT": eff.append(("byte", b)); b = 0
        elif t == "ARG": b = args[op[1]] & 255
        elif t == "HI": b = (args[op[1]] >> 8) & 255
        elif t == "ORA": b = (b | ((args[op[1]] & 255) << op[2])) & 255
        elif t == "AND": b &= op[1]
        else: eff.append((t,) + op[1:])
    return eff


def enc_run(code, args):
    """The same, as asm.c's run() interprets the encoded bytes."""
    b, eff, p = 0, [], 0
    while p < len(code):
        op = code[p]; p += 1
        v = args[op & 3]; kind = op & 0xF0
        if op == OUTB: eff.append(("byte", b)); b = 0
        elif kind == DIG: b = (b * 16 + (op & 15)) & 255
        elif kind == ARG: b = v & 255
        elif kind == HI: b = (v >> 8) & 255
        elif kind == ORA: b = (b | v) & 255
        elif kind == ORA4: b = (b | (v << 4)) & 255
        elif kind == AND: b &= code[p]; p += 1
        elif kind == LISTB: eff.append(("LIST", op & 3, "M" if op & 8 else "L"))
        elif kind == LIT: b = code[p]; p += 1
        elif op == UNSUP: eff.append(("UNSUP",))
        else: eff.append(({ORG: "ORG", DS: "DS", END: "END", EQU: "EQU"}[kind], op & 3))
    return eff


def build(path):
    title, classes, trans = read_def(path)
    if len(classes) > 8: sys.exit("gen_y1_optab: more than 8 classes")
    cls = []                                     # per class: (names: len name ..., 0), (values)
    for name, entries in classes:
        cn, cv = [], []
        for t, v in entries:
            if not 1 <= len(t) <= 15 or not 0 <= v <= 255: sys.exit("gen_y1_optab: class entry %s=%d" % (t, v))
            cn += [len(t)] + [ord(c) for c in t]; cv.append(v)
        cn.append(0)
        if len(cn) > MAXINIT or len(cv) > MAXINIT: sys.exit("gen_y1_optab: class %s over %d bytes" % (name, MAXINIT))
        cls.append((cn, cv))
    groups = {}                                  # mnemonic -> [(shape, ops)] in .def order
    order = []
    for cmd, dest in trans:
        first, sh, kinds = shape(cmd, classes)
        if len(kinds) > 4: sys.exit("gen_y1_optab: more than 4 arguments in %r" % cmd)
        sym = translate(dest, kinds, cmd)
        ops = encode(sym, cmd)
        rnd = random.Random(cmd)                 # the encoding must do what Translate does, on any arguments
        for args in [[0] * 4, [0xFFFF] * 4, [0x1234, 0x5678, 0x9ABC, 0xDEF0]] + \
                    [[rnd.randrange(65536) for _ in range(4)] for _ in range(50)]:
            if ref_run(sym, args) != enc_run(ops, args):
                sys.exit("gen_y1_optab: internal error: the encoding of %r differs from Translate" % cmd)
        if first not in groups: groups[first] = []; order.append(first)
        groups[first].append((sh, ops, cmd))
    recs = {}
    for name in order:
        if not 1 <= len(name) <= 15: sys.exit("gen_y1_optab: mnemonic %r" % name)
        if len(groups[name]) > 255: sys.exit("gen_y1_optab: too many patterns for %s" % name)
        rec = [ord(c) for c in name] + [0, len(groups[name])]
        for sh, ops, _ in groups[name]:
            if len(ops) > 255: sys.exit("gen_y1_optab: construction too long in %r" % name)
            rec += sh + [0, len(ops)] + ops
        recs[name] = rec
    for seed in range(4096):                     # the first seed whose every chain fits one initialiser
        buckets = [[] for _ in range(OPHASH)]
        for name in order: buckets[ophash(name, seed)] += recs[name]
        if all(len(b) + 1 <= MAXINIT for b in buckets): break
    else: sys.exit("gen_y1_optab: no hash seed keeps every chain under %d bytes" % MAXINIT)
    for b in buckets:
        if b: b.append(0)                        # a 0 where the next record's name would start ends the chain
    tab, head = buckets, seed
    return title, classes, trans, order, groups, cls, tab, head


def c_array(ctype, name, vals, per=24):
    lines = []
    for i in range(0, len(vals), per):
        lines.append("    " + ",".join(str(v) for v in vals[i:i + per]))
    return "%s %s[] = {\n%s\n};\n" % (ctype, name, ",\n".join(lines))


def render(path):
    title, classes, trans, order, groups, cls, buckets, seed = build(path)
    rel = os.path.relpath(path, ROOT)
    total = sum(len(cn) + len(cv) for cn, cv in cls) + sum(len(b) for b in buckets) + 1
    s = ("/* asm_optab.c - GENERATED by tools/gen_y1_optab.py from %s: do not edit, run the generator\n"
         "   (os/Makefile does, and tests/asm/run.py checks that this file is current). The YACC1 instruction table\n"
         "   for /BIN/ASM (os/commands/asm.c): %d patterns of RC/asm's .def file (%s) under %d mnemonics,\n"
         "   %d operand classes, %d bytes; the formats are described in the generator. One array per hash chain\n"
         "   and no initialiser over %d numbers: what y1cc's multi-pass compiler takes on the machine. */\n"
         % (rel, len(trans), title.strip(), len(order), len(classes), total, MAXINIT))
    s += "#define OPSEED %d\n" % seed
    for k, (cn, cv) in enumerate(cls):
        s += "/* class %s */\n" % classes[k][0]
        s += c_array("char", "op_cn%d" % k, cn)
        s += c_array("char", "op_cv%d" % k, cv)
    s += "char *op_cn[] = {%s};\n" % ", ".join("op_cn%d" % k for k in range(len(cls)))
    s += "char *op_cv[] = {%s};\n" % ", ".join("op_cv%d" % k for k in range(len(cls)))
    s += "char op_bx[] = {0};\n"
    for i, b in enumerate(buckets):
        if b: s += c_array("char", "op_b%d" % i, b)
    names = ["op_b%d" % i if b else "op_bx" for i, b in enumerate(buckets)]
    for h in range(2):
        part = names[32 * h:32 * h + 32]
        s += "char *op_h%d[] = {\n" % h
        s += ",\n".join("    " + ", ".join(part[i:i + 11]) for i in range(0, len(part), 11)) + "\n};\n"
    return s


def main():
    a = sys.argv[1:]
    check = "--check" in a
    a = [x for x in a if x != "--check"]
    out = OUT
    if "-o" in a:
        i = a.index("-o"); out = a[i + 1]; del a[i:i + 2]
    path = a[0] if a else DEF
    s = render(path)
    if check:
        old = open(out).read() if os.path.exists(out) else ""
        if old != s:
            print("gen_y1_optab: %s is not current with %s (run tools/gen_y1_optab.py)" % (os.path.relpath(out, ROOT), os.path.relpath(path, ROOT)))
            sys.exit(1)
        print("gen_y1_optab: %s is current" % os.path.relpath(out, ROOT))
        return
    old = open(out).read() if os.path.exists(out) else None
    if old != s: open(out, "w").write(s)
    print("gen_y1_optab: %s -> %s (%s)" % (os.path.relpath(path, ROOT), os.path.relpath(out, ROOT), "written" if old != s else "unchanged"))


if __name__ == "__main__":
    main()
