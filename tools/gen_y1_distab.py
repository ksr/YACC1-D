#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""gen_y1_distab.py - the disassembler's instruction table, generated from software/assembler/yacc1.def (2026-09-29),
so that /BIN/DISASM (os/commands/disasm.c) decodes exactly what the assemblers (RC/asm on the Mac, /BIN/ASM and
/BIN/ASMC on the machine) encode: the three read the same file and cannot drift apart.

  gen_y1_distab.py [DEF] [-o os/dis_optab.c]     write the table (default: yacc1.def -> os/dis_optab.c)
  gen_y1_distab.py --check                        exit 1 if os/dis_optab.c is not what yacc1.def gives (tests/disasm)
  gen_y1_distab.py --list                         print the decode table, one opcode a line (for reading)

How. The .def file is read and every construction line compiled exactly as the native assembler's table generator
does it (tools/gen_y1_optab.py: read_def, shape, translate - a copy of RC/asm's Translate()), and then run BACKWARDS:
  1. An INSTRUCTION is a pattern whose construction writes bytes only (no ORG/DS/END/EQU, no DB/DW list) and whose
     first byte, the opcode, depends on nothing but its register/port operands. That leaves out the directives,
     `DW \\W` and `DB HIGH \\W` (their first byte is the operand) and the library markers.
  2. Each operand's bits are traced through the construction (Translate's effect, gen_y1_optab.ref_run) one bit at
     a time: every operand bit must land on exactly one bit of the output, never cleared, never shared. So each
     byte of an instruction is FIXED bits (what the pattern writes whatever the operands) plus FIELDS, runs of an
     operand's bits: `MVIB \\{regs},\\B` / `10|1 \\2` is byte 0 = 00010rrr (fixed 11111000 = 00010000, field reg bits
     0-2), byte 1 = the byte operand; `POPR` / `08 \\1<4&f0` is byte 1 = 0rrr0000; `MOVRR Rx,Ry` / `0F |2<4|1` is byte 1 =
     0yyy0xxx. A construction that is not such a mapping stops the generator (add it to disasm.c and here together).
  3. Operand classes are decoded to the first name the .def gives a value, and only for the values the MACHINE has:
     registers R0..R7. The class also lists R8=8 and R9=9, which RC/asm accepts but which OR a 1 into the opcode's
     next field (`MVIB R8` = $18 = `MVIW R0`; docs/programming/ASSEMBLER.md section 4, CLAUDE.md "R0-R7"); ports
     keep all 16 (P0..PF). With that, every opcode byte belongs to at most one instruction - checked here - so the
     table is one lookup, and the decode of the rest is exact: a byte whose fixed bits are wrong (`JSRUR` with $08
     in its operand) or a truncated instruction is not an instruction, and disasm prints it as a DB.
  4. Every instruction is checked on every combination of its class operands and on random byte/word operands: the
     table's decode of Translate's bytes gives back the operands, and the opcode is software/opcodes.h's number for
     that mnemonic (the emulators' and the microcode generator's table: a second, independent source).

The C file (y1cc subset: numeric array initialisers, none over MAXINIT numbers, the limit of y1cc's multi-pass
compiler on the machine, as in os/asm_optab.c):
  DT_MAXLEN        the longest instruction (3)
  dt_cK[]          class K: the number of values n, then for each value 0..n-1 its name (length, characters; length 0
                   = no name, not decodable); dt_c[] points at them
  dt_iN[]          instruction N: the mnemonic (length, characters), the length L in bytes, the operand shape as in
                   os/asm_optab.c (1 whitespace - printed as one space, 4 a byte \\B, 5 a word \\W, 8+k class k, 33..126
                   that character), 0, then per byte 0..L-1: fixed mask, fixed value, the number of fields, and per field
                   three numbers: operand*16 + the operand's lowest bit, the byte's lowest bit, the mask after shifting
                   (operand |= ((byte >> bit) & mask) << lowest bit)
  dt_qM[]          32 instructions each; dt_rec(n) returns instruction n's record
  dt_oM[]          opcodes 32M..32M+31: the instruction's number + 1, 0 = not an instruction; dt_opc(op) looks it up
"""
import os, sys, re, random, itertools

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import gen_y1_optab as G                         # noqa: E402  (read_def, shape, translate, ref_run: one reading of the .def)

DEF = os.path.join(ROOT, "software/assembler/yacc1.def")
OPCODES = os.path.join(ROOT, "software/opcodes.h")
OUT = os.path.join(ROOT, "os/dis_optab.c")
MAXINIT = G.MAXINIT
DECODE_LIMIT = {"regs": 8}                       # class values the machine has (R0..R7); other classes: all of them


def arg_kinds(sh):
    """The operands of a shape in order: 'B', 'W', 'L', 'M' or ('C', class index)."""
    out = []
    for x in sh:
        if x == G.BYTE: out.append("B")
        elif x == G.WORD: out.append("W")
        elif x == G.LIST: out.append("L")
        elif x == G.MLIST: out.append("M")
        elif G.CLS <= x < 33: out.append(("C", x - G.CLS))
    return out


def run_bytes(sym, args):
    """Translate's bytes for these operands, or None if it does anything but write bytes."""
    eff = G.ref_run(sym, list(args) + [0] * (4 - len(args)))
    if any(e[0] != "byte" for e in eff): return None
    return [e[1] for e in eff]


def opcodes_h():
    """software/opcodes.h: {mnemonic: opcode} (placeholders OPCODE_xx, START and INT are not instructions)."""
    ops = {}
    for m in re.finditer(r"^#define\s+(\w+)\s+(0[xX][0-9a-fA-F]+)", open(OPCODES).read(), re.M):
        if m.group(1).startswith("OPCODE_") or m.group(1) in ("START", "INT"): continue
        ops[m.group(1)] = int(m.group(2), 16)
    return ops


def build(path):
    title, classes, trans = G.read_def(path)
    allowed = []                                 # per class: {value: first name}, decodable values only
    for name, entries in classes:
        lim = DECODE_LIMIT.get(name, 256)
        vals = {}
        for t, v in entries:
            if v < lim and v not in vals: vals[v] = t
        allowed.append(vals)
    insts = []                                   # (mnemonic, shape, kinds, length, per byte (mask, val, fields))
    seen = set()
    for cmd, dest in trans:
        first, sh, _ = G.shape(cmd, classes)
        kinds = arg_kinds(sh)
        if any(k in ("L", "M") for k in kinds): continue            # DB/DW lists: data, not instructions
        sym = G.translate(dest, ["B" if k == "B" or isinstance(k, tuple) else k for k in kinds], cmd)
        base = run_bytes(sym, [0] * len(kinds))
        if not base: continue                                        # directives, library markers
        # the opcode must not depend on a byte or word operand (DW \W, DB HIGH \W: data)
        data = False
        for i, k in enumerate(kinds):
            if isinstance(k, tuple): continue
            for bit in range(8 if k == "B" else 16):
                a = [0] * len(kinds); a[i] = 1 << bit
                if run_bytes(sym, a)[0] != base[0]: data = True
        if data: continue
        if first in seen: sys.exit("gen_y1_distab: a second instruction pattern for %s (%r)" % (first, cmd))
        seen.add(first)
        L = len(base)
        where = {}                               # (operand, bit) -> (byte, bit)
        for i, k in enumerate(kinds):
            nb = 8 if k == "B" else 16 if k == "W" else max(allowed[k[1]]).bit_length()
            for bit in range(nb):
                a = [0] * len(kinds); a[i] = 1 << bit
                out = run_bytes(sym, a)
                if out is None or len(out) != L: sys.exit("gen_y1_distab: %r: the length depends on an operand" % cmd)
                diff = [(j, o) for j in range(L) for o in range(8) if (out[j] ^ base[j]) >> o & 1]
                if len(diff) != 1 or not out[diff[0][0]] >> diff[0][1] & 1:
                    sys.exit("gen_y1_distab: %r: operand %d bit %d is not copied to one output bit (%s); "
                             "disasm cannot decode it" % (cmd, i + 1, bit, diff))
                if diff[0] in where.values(): sys.exit("gen_y1_distab: %r: two operand bits on one output bit" % cmd)
                where[(i, bit)] = diff[0]
        bytes_ = []
        for j in range(L):
            mapped = [(i, b, o) for (i, b), (jj, o) in sorted(where.items()) if jj == j]
            mask = 255
            for _, _, o in mapped: mask &= ~(1 << o)
            fields = []                          # runs: same operand, consecutive bits, same shift
            for i, b, o in mapped:
                if fields and fields[-1][0] == i and fields[-1][1] + fields[-1][3] == b and fields[-1][2] + fields[-1][3] == o:
                    fields[-1][3] += 1
                else: fields.append([i, b, o, 1])
            bytes_.append((mask, base[j] & mask, [(i, b, o, (1 << w) - 1) for i, b, o, w in fields]))
        insts.append((first, sh, kinds, L, bytes_, sym, cmd))
    # the opcode map, and the proof that the table decodes what Translate encodes
    opmap = {}
    for n, (first, sh, kinds, L, bytes_, sym, cmd) in enumerate(insts):
        cls = [i for i, k in enumerate(kinds) if isinstance(k, tuple)]
        rnd = random.Random(cmd)
        for combo in itertools.product(*[sorted(allowed[kinds[i][1]]) for i in cls]):
            for trial in range(6):
                args = [0] * len(kinds)
                for i, k in enumerate(kinds):
                    if k == "B": args[i] = [0, 255, rnd.randrange(256)][min(trial, 2)]
                    elif k == "W": args[i] = [0, 65535, rnd.randrange(65536)][min(trial, 2)]
                for i, v in zip(cls, combo): args[i] = v
                out = run_bytes(sym, args)
                got = decode(bytes_, out, len(kinds))
                if got != args: sys.exit("gen_y1_distab: internal error: %r %s -> %s decodes to %s" % (cmd, args, out, got))
                if trial == 0:
                    if out[0] in opmap and opmap[out[0]] != n:
                        sys.exit("gen_y1_distab: opcode $%02X is both %s and %s" % (out[0], insts[opmap[out[0]]][0], first))
                    opmap[out[0]] = n
    for op in range(256):                        # every byte the table accepts as an opcode is one Translate makes
        for n, ins in enumerate(insts):
            m, v, _ = ins[4][0]
            if op & m == v and opmap.get(op) != n:
                sys.exit("gen_y1_distab: opcode $%02X matches %s's fixed bits but is not one of its encodings" % (op, ins[0]))
    oh = opcodes_h()                             # the second source: the emulators' and microcode generator's numbers
    for n, ins in enumerate(insts):
        lo = min(op for op, k in opmap.items() if k == n)
        if ins[0] not in oh: sys.exit("gen_y1_distab: %s is not in software/opcodes.h" % ins[0])
        if oh[ins[0]] != lo: sys.exit("gen_y1_distab: %s is $%02X in yacc1.def, $%02X in software/opcodes.h" % (ins[0], lo, oh[ins[0]]))
    for name in oh:
        if name not in [i[0] for i in insts]: sys.exit("gen_y1_distab: software/opcodes.h's %s is not an instruction of yacc1.def" % name)
    return title, classes, allowed, insts, opmap


def decode(bytes_, data, nargs):
    """The table's decode, as disasm.c does it: None when a fixed bit is wrong."""
    args = [0] * nargs
    for (mask, val, fields), b in zip(bytes_, data):
        if b & mask != val: return None
        for i, bl, o, m in fields: args[i] |= ((b >> o) & m) << bl
    return args


def c_array(name, vals, per=24):
    if len(vals) > MAXINIT: sys.exit("gen_y1_distab: %s has %d numbers, over %d" % (name, len(vals), MAXINIT))
    lines = ["    " + ",".join(str(v) for v in vals[i:i + per]) for i in range(0, len(vals), per)]
    return "char %s[] = {\n%s\n};\n" % (name, ",\n".join(lines))


def render(path):
    title, classes, allowed, insts, opmap = build(path)
    rel = os.path.relpath(path, ROOT)
    maxlen = max(i[3] for i in insts)
    s = ("/* dis_optab.c - GENERATED by tools/gen_y1_distab.py from %s: do not edit, run the generator\n"
         "   (os/Makefile does, and tests/disasm/run.py checks that this file is current). The YACC1 decode table for\n"
         "   /BIN/DISASM (os/commands/disasm.c): %d instructions of RC/asm's .def file (%s), %d opcodes,\n"
         "   %d operand classes; the formats are described in the generator. No initialiser over %d numbers: what\n"
         "   y1cc's multi-pass compiler takes on the machine. */\n"
         % (rel, len(insts), title.strip(), len(opmap), len(classes), MAXINIT))
    s += "#define DT_MAXLEN %d\n" % maxlen
    for k, (name, _) in enumerate(classes):
        n = max(allowed[k]) + 1
        vals = [n]
        for v in range(n):
            t = allowed[k].get(v, "")
            vals += [len(t)] + [ord(c) for c in t]
        s += "/* class %s: values 0..%d */\n" % (name, n - 1)
        s += c_array("dt_c%d" % k, vals)
    s += "char *dt_c[] = {%s};\n" % ", ".join("dt_c%d" % k for k in range(len(classes)))
    for n, (first, sh, kinds, L, bytes_, sym, cmd) in enumerate(insts):
        rec = [len(first)] + [ord(c) for c in first] + [L] + sh + [0]
        for mask, val, fields in bytes_:
            rec += [mask, val, len(fields)]
            for i, bl, o, m in fields: rec += [i * 16 + bl, o, m]
        s += "/* %d: %s */\n" % (n, cmd.replace("*/", "* /"))
        s += c_array("dt_i%d" % n, rec)
    nq = (len(insts) + 31) // 32
    for q in range(nq):
        s += "char *dt_q%d[] = {\n    %s\n};\n" % (q, ",\n    ".join(
            ", ".join("dt_i%d" % n for n in range(r, min(r + 8, len(insts), 32 * q + 32)))
            for r in range(32 * q, min(32 * q + 32, len(insts)), 8)))
    for q in range(8):
        s += c_array("dt_o%d" % q, [opmap[op] + 1 if op in opmap else 0 for op in range(32 * q, 32 * q + 32)])
    s += "char *dt_o[] = {%s};\n" % ", ".join("dt_o%d" % q for q in range(8))
    s += "int dt_opc(int op) { char *t; t = dt_o[op >> 5]; return t[op & 31]; }\n"
    s += "char *dt_rec(int n) {\n"
    for q in range(nq - 1): s += "    if (n < %d) return dt_q%d[n - %d];\n" % (32 * q + 32, q, 32 * q)
    s += "    return dt_q%d[n - %d];\n}\n" % (nq - 1, 32 * (nq - 1))
    return s, insts, opmap, classes, allowed


def listing(path):
    _, insts, opmap, classes, allowed = render(path)
    for op in range(256):
        if op not in opmap: print("%02X  -" % op); continue
        first, sh, kinds, L, bytes_, _, cmd = insts[opmap[op]]
        print("%02X  %-7s %d byte%s  %s" % (op, first, L, "s" if L > 1 else " ", cmd))


def main():
    a = sys.argv[1:]
    check = "--check" in a
    if "--list" in a: listing(DEF); return
    a = [x for x in a if x != "--check"]
    out = OUT
    if "-o" in a:
        i = a.index("-o"); out = a[i + 1]; del a[i:i + 2]
    path = a[0] if a else DEF
    s = render(path)[0]
    old = open(out).read() if os.path.exists(out) else None
    if check:
        if old != s:
            print("gen_y1_distab: %s is not current with %s (run tools/gen_y1_distab.py)" % (os.path.relpath(out, ROOT), os.path.relpath(path, ROOT)))
            sys.exit(1)
        print("gen_y1_distab: %s is current" % os.path.relpath(out, ROOT))
        return
    if old != s: open(out, "w").write(s)
    print("gen_y1_distab: %s -> %s (%s)" % (os.path.relpath(path, ROOT), os.path.relpath(out, ROOT), "written" if old != s else "unchanged"))


if __name__ == "__main__":
    main()
