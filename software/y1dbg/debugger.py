# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""Symbols, addresses, the disassembler and the video screen - what the shell and the UIs share.

Symbols come from RC/asm listings (firmware/monitor/monitor.lst, firmware/basic/basic.lst, any program's .lst): the
cross-reference table at a listing's end gives every name's value ("f06ah: CMDLOOP - <  193> ..."), the body says
which names are labels and which are EQUs and how each was written. Code labels name addresses in the disassembly;
an EQU names one only when its value is $0100 or more and no label has it (variables such as VROW = $0FF3, not
constants such as VROWS = 24). Every name works in an address argument, in any case.

The disassembler is /BIN/DISASM's table (tools/gen_y1_distab.py, read from software/assembler/yacc1.def, the file the
assemblers use), so it decodes exactly what they encode, the --xisa instructions (LDZ/STZ, ADDIW, SHL16) included;
a byte that starts no instruction is a DB. Operands are written as RC/asm takes them (0F06AH, 3EH, R3, P1).

The screen is the video card's display RAM drawn the way the card does (docs/cards/video.md, tools/vidsim.py): the
6845's R1 columns x R6 rows from start address R12:R13 once a program has written R1 and R6, else the monitor's 80 x
24 from $D000 (as software/videomodel.h's -V); a byte's bits 0-5 pick the glyph (2513 order: $00-$1F = @ A..Z [ \\ ]
^ _, $20-$3F = space ! .. ?), bit 7 is inverse video, bit 6 is not wired. The 6845 scans 4K; a cell past the CPU's 2K
shows the upper half nobody can write (#). The cursor is R14:R15 unless R10 says "off".
"""
import os, re, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
REGS = ["r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7"]


class Symbols:
    def __init__(self):
        self.by_name = {}            # lower-case name -> value
        self.label = {}              # address -> name (code labels, then address-like EQUs)
        self.files = []

    def load(self, path):
        text = open(path, errors="replace").read()
        spelled, equ = {}, set()
        for m in re.finditer(r"^\s*\d+ [0-9a-fA-F]{4}:[ 0-9a-fA-F]*?\s([A-Za-z_]\w*):(.*)$", text, re.M):
            spelled.setdefault(m.group(1).upper(), m.group(1))
            if re.match(r"\s*\.?equ\b", m.group(2), re.I): equ.add(m.group(1).upper())
        for m in re.finditer(r"^\s*\d*\s*[0-9a-fA-F ]*?\s([A-Za-z_]\w*):(.*)$", text, re.M):   # continuation lines
            spelled.setdefault(m.group(1).upper(), m.group(1))
            if re.match(r"\s*\.?equ\b", m.group(2), re.I): equ.add(m.group(1).upper())
        n = 0; later = []
        for m in re.finditer(r"^([0-9a-fA-F]{4})h: (\S+)\s+- <", text, re.M):
            v = int(m.group(1), 16); up = m.group(2).upper(); name = spelled.get(up, m.group(2).lower())
            self.by_name[name.lower()] = v; n += 1
            if up in equ:
                if v >= 0x100: later.append((v, name))
            else:
                self.label.setdefault(v, name)
        for v, name in later:
            self.label.setdefault(v, name)
        self.files.append(path)
        return n

    def name(self, a):
        return self.label.get(a)

    def tag(self, a):
        s = self.label.get(a)
        return " <%s>" % s if s else ""


def parse_addr(text, syms, regs=None):
    """hex (F06A, $F06A, 0xF06A, 0F06AH), a symbol, or a register name (r0..r7, pc, sp) when regs are known;
    name+hex / name-hex offsets"""
    t = text.strip()
    m = re.match(r"^(.+?)([+-])([0-9A-Fa-f]+)$", t)
    if m and not re.match(r"^[0-9A-Fa-f]+$", m.group(1)) and not t.lower().startswith("0x"):
        base = parse_addr(m.group(1), syms, regs); off = int(m.group(3), 16)
        return (base + off if m.group(2) == "+" else base - off) & 0xFFFF
    low = t.lower()
    if low in syms.by_name: return syms.by_name[low]
    if regs is not None:
        if low in REGS: return regs["r"][int(low[1])]
        if low == "pc": return regs["pc"]
        if low == "sp": return regs["r"][1]
    if low.startswith("$"): return int(low[1:], 16) & 0xFFFF
    if low.startswith("0x"): return int(low[2:], 16) & 0xFFFF
    if low.endswith("h") and re.match(r"^[0-9a-f]+h$", low): return int(low[:-1], 16) & 0xFFFF
    if re.match(r"^[0-9a-f]+$", low): return int(low, 16) & 0xFFFF
    raise ValueError("not an address: %s" % text)


# ---------------------------------------------------------------------------------------------------- disassembler
_TABLE = None


def _table():
    global _TABLE
    if _TABLE is None:
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import gen_y1_distab as D           # noqa: E402  (the decode table of /BIN/DISASM, from yacc1.def)
        import gen_y1_optab as G            # noqa: E402
        title, classes, allowed, insts, opmap = D.build(D.DEF)
        _TABLE = (allowed, insts, opmap, D.decode, G)
    return _TABLE


def _hb(v):
    return ("0" if (v & 255) > 159 else "") + "%02XH" % (v & 255)


def _hw(v):
    return ("0" if v > 40959 else "") + "%04XH" % v


def disasm(read, a, syms=None):
    """-> (length, text, target): one instruction at a; read(addr, n) -> bytes; target = a word operand (or None)"""
    allowed, insts, opmap, decode, G = _table()
    data = read(a, 3)
    n = opmap.get(data[0])
    if n is not None:
        first, sh, kinds, L, bytes_, _, cmd = insts[n]
        args = decode(bytes_, data[:L], len(kinds))
        if args is not None and all(args[i] in allowed[k[1]] for i, k in enumerate(kinds) if isinstance(k, tuple)):
            out, i, target = first, 0, None
            for c in sh:
                if c == G.WS: out += " "
                elif c == G.BYTE: out += _hb(args[i]); i += 1
                elif c == G.WORD:
                    target = args[i]; out += _hw(args[i])
                    if syms and syms.name(args[i]): out += " <%s>" % syms.name(args[i])
                    i += 1
                elif G.CLS <= c < 33: out += allowed[c - G.CLS][args[i]]; i += 1
                else: out += chr(c)
            return L, out, target
    return 1, "DB " + _hb(data[0]), None


def listing(read, a, count, syms=None):
    """[(addr, bytes, text)] for count instructions from a"""
    out = []
    for _ in range(count):
        L, text, _ = disasm(read, a, syms)
        out.append((a, read(a, L), text)); a = (a + L) & 0xFFFF
    return out


# ---------------------------------------------------------------------------------------------------- the screen
def glyph(b):
    return chr(((b + 0x20) & 0x3F) + 0x20)


def screen(v):
    """the card's state (the server's `video` reply) -> dict: cols, rows, start, source, lines (text), inverse
    (per line, a list of booleans), cursor ((row, col) or None)"""
    regs, written = v["regs"], v["written"]
    ram = bytes.fromhex(v["ram"])
    crtc = written[1] and written[6] and regs[1] and regs[6]
    if crtc:
        cols, rows, start = regs[1], regs[6] & 0x7F, (regs[12] & 0x3F) << 8 | regs[13]
    else:
        cols, rows, start = 80, 24, 0
    lines, inverse = [], []
    for r in range(rows):
        s, inv = [], []
        for c in range(cols):
            ma = (start + r * cols + c) & 0xFFF
            if ma >= 2048: s.append("#"); inv.append(False); continue
            b = ram[ma]; s.append(glyph(b)); inv.append(bool(b & 0x80))
        lines.append("".join(s)); inverse.append(inv)
    cursor = None
    cur = (regs[14] & 0x3F) << 8 | regs[15]
    if (written[10] or written[14] or written[15]) and (regs[10] >> 5) & 3 != 1:
        off = (cur - start) & 0x3FFF
        if off < rows * cols: cursor = (off // cols, off % cols)
    return {"cols": cols, "rows": rows, "start": start, "absent": v.get("absent", 0),
            "source": "CRTC R1/R6/R12/R13" if crtc else "default geometry", "lines": lines, "inverse": inverse,
            "cursor": cursor}
