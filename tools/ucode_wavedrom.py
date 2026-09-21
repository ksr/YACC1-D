#!/usr/bin/env python3
"""Timing diagrams for the YACC1 ISA, generated from the microcode.

Control levels come straight from firmware/microcode/ucode-generator2/test.hex (64 steps x 64 signals per opcode,
bit positions from firmware/microcode/yaccsignaldata2.h). On top of that a small TTL timing model (assumed, typical
LS-era parts - see TIMING) places the bus responses: what the register card puts on the address bus, when memory data
is valid, when the instruction register / accumulator / PC actually change. Rendered with wavedrom-cli (npx).

usage: ucode_wavedrom.py --all [--out DIR]            every opcode in firmware/opcodes.h -> docs/isa/<MNEMONIC>.svg + README.md index\n       ucode_wavedrom.py OPCODE [OPCODE ...] [--out DIR]   e.g. ucode_wavedrom.py ADDI 0xB0
"""
import os, re, sys, json, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- assumed timing, as fractions of one microcode clock period (documented in the diagram footer)
TIMING = {
    "pipe":  0.05,   # 74LS374 pipeline register: control lines change ~30 ns after the uCODE clock edge
    "reg":   0.12,   # register card: selected register on the address bus ~40 ns after the select lines settle
    "mem":   0.30,   # memory: data valid ~150-250 ns after address stable and -MEM-RD (62256 / 28C64)
    "latch": 0.00,   # loads (IR, ACC, PC increment) take effect at the trailing edge of their pulse
}

def signal_table():
    s = open(os.path.join(ROOT, "firmware/microcode/yaccsignaldata2.h")).read()
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S); s = re.sub(r"//.*", "", s)
    return [(n, (int(a) - 1) * 2 + int(b), int(c)) for n, a, b, c in
            re.findall(r'\{\s*"([^"]+)"\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\}', s)]

def microcode():
    recs = {}
    for tok in open(os.path.join(ROOT, "firmware/microcode/ucode-generator2/test.hex")).read().split("%"):
        tok = tok.strip()
        if len(tok) < 4: continue
        ins = int(tok[2:4], 16); body = tok[4:].split("Z")[0].split("!")[0].strip()
        d = [int(body[i:i + 2], 16) for i in range(0, len(body) - len(body) % 2, 2)]
        recs[ins] = (d + [0] * 512)[:512]
    return recs

def opcode_names():
    s = open(os.path.join(ROOT, "firmware/opcodes.h")).read()
    out = {}
    for name, val in re.findall(r"#define\s+(\w+)\s+(0[xX][0-9A-Fa-f]+|\d+)", s):
        v = int(val, 0)
        if v < 256 and not name.startswith("OPCODE_") and name != "OPCODES_H": out.setdefault(v, name)
    return out

def active(word, byte, bit, name):
    v = (word[byte] >> bit) & 1
    return (v == 0) if name.startswith("-") else (v == 1)

def level_wave(levels, name, phase):
    """control line: high/low per step, shifted right by 'phase' of a period (pipeline delay)"""
    w = "".join(("l" if name.startswith("-") else "h") if a else ("h" if name.startswith("-") else "l") for a in levels)
    return {"name": name, "wave": w, "phase": -phase}

def bus_wave(vals, name, phase, hiz=None):
    """value per step; identical consecutive values merge; None = high-Z"""
    wave, data, prev = "", [], object()
    for v in vals:
        if v == prev: wave += "."
        elif v is None: wave += "z"; prev = v
        else: wave += "="; data.append(str(v)); prev = v
    d = {"name": name, "wave": wave, "phase": -phase}
    if data: d["data"] = data
    return d

def diagram(op, sig, recs, names):
    w = recs[op]; steps = [w[i * 8:i * 8 + 8] for i in range(64)]
    S = {n: (b, bt) for n, b, bt in sig}
    def on(step, n): b, bt = S[n]; return active(steps[step], b, bt, n)
    def bus(step, prefix): return sum(((steps[step][S[nm][0]] >> S[nm][1]) & 1) << int(nm[-1]) for nm in S if re.fullmatch(prefix + r"\d", nm))
    last = next((i for i in range(64) if on(i, "UCODE-COUNT-RESET")), 63); n = last + 1
    # ---- control rows: only signals that change, grouped
    groups = [("bus cycle", ["-VMA", "-MEM-RD", "-MEM-WR", "-IO-RD", "-IO-WR"]),
              ("registers", ["-REG-FUNC-RD", "-REG-FUNC-LD", "-REG-UP", "-REG-DN", "-REG-RD-LO", "-REG-RD-HI", "REG-LD-LO", "REG-LD-HI", "-SRC-ADDR", "-DEST-ADDR", "-TMP-REG-RD0", "-TMP-REG-LD0", "-TMP-REG-RD1", "-TMP-REG-LD1"]),
              ("ALU / accumulator", ["-ALU-FUNC", "-AC-LD", "-AC-LD-INV", "-AC-RD", "-SR-LD", "-HL-SWAP"]),
              ("branch / interrupt", ["BRANCH-LD-LO", "BRANCH-LD-HI", "-BRANCH-RD", "BR-TEST", "-INT-JMP", "-INTA", "INT-EN", "INT-START", "INT-LD-LO", "INT-LD-HI"]),
              ("sequencer / misc", ["LD-INS-REG", "-2-BYTE-OPERAND-SEL", "OPERAND-CLK", "-IO-ADDR-LD", "OUT-ON", "OUT-OFF", "SOFT-HALT", "UCODE-COUNT-RESET"])]
    used = set(); rows = []
    for title, members in groups:
        grp = []
        for nm in members:
            if nm in S and any(on(i, nm) for i in range(n)):
                grp.append(level_wave([on(i, nm) for i in range(n)], nm, TIMING["pipe"])); used.add(nm)
        for nm in S:   # anything else in this group's spirit that changed and is not listed
            pass
        if grp: rows += grp + [{}]
    others = [nm for nm in S if nm not in used and not re.fullmatch(r"(REG-RD-ID|REG-LD-ID|ADDR-REG-ID|IOADDR|ALU|SPARE)\d?", nm)
              and any(on(i, nm) for i in range(n))]
    if others: rows += [level_wave([on(i, nm) for i in range(n)], nm, TIMING["pipe"]) for nm in others] + [{}]
    for pre, lab in (("ADDR-REG-ID", "ADDR-REG-ID[3:0]"), ("REG-RD-ID", "REG-RD-ID[3:0]"), ("REG-LD-ID", "REG-LD-ID[3:0]"), ("ALU", "ALU-FUNC[3:0]"), ("IOADDR", "IOADDR[3:0]")):
        vals = ["%X" % bus(i, pre) for i in range(n)]
        if len(set(vals)) > 1 or (vals[0] != "0" and pre != "ADDR-REG-ID"): rows.append(bus_wave(vals, lab, TIMING["pipe"]))
    rows.append({})
    # ---- derived bus behaviour (the timing model)
    # registers: value labels only ("PC", "PC+1", "R1", "R1+1", "target" once loaded from the bus); the register card
    # increments the register selected by REG-RD-ID on -REG-UP / decrements on -REG-DN (with -REG-FUNC-RD), and loads
    # the register selected by REG-LD-ID from the data bus on -REG-LD-LO / -REG-LD-HI (with -REG-FUNC-LD).
    regval = {k: ("PC" if k == 0 else "R%X" % k) for k in range(16)}; inc = {k: 0 for k in range(16)}; loaded = set()
    def regname(k): return ("target" if k == 0 else "R%X'" % k) if k in loaded else regval[k] + ("+%d" % inc[k] if inc[k] > 0 else ("%d" % inc[k] if inc[k] < 0 else ""))
    addr, data, pcrow, irrow, accrow, tmprow = [], [], [], [], [], []
    ir = "IR"; acc = "ACC"; tmp = "TMP"
    def ends(i, n_): return i + 1 == n or not on(i + 1, n_)
    for i in range(n):
        a = regname(bus(i, "ADDR-REG-ID")); addr.append(a)
        # what drives the data bus this step
        if on(i, "-AC-RD"): d = "ACC"
        elif on(i, "-REG-RD-LO") and on(i, "-REG-FUNC-RD"): d = regname(bus(i, "REG-RD-ID")) + ".lo"
        elif on(i, "-REG-RD-HI") and on(i, "-REG-FUNC-RD"): d = regname(bus(i, "REG-RD-ID")) + ".hi"
        elif "-TMP-REG-RD0" in S and on(i, "-TMP-REG-RD0"): d = "TMP0"
        elif "-TMP-REG-RD1" in S and on(i, "-TMP-REG-RD1"): d = "TMP1"
        elif on(i, "-BRANCH-RD"): d = "BRANCH reg"
        elif on(i, "-IO-RD"): d = "IN P%X" % bus(i, "IOADDR")
        elif on(i, "-MEM-RD"): d = "M[%s]" % a
        else: d = None
        data.append(d)
        if on(i, "LD-INS-REG") and ends(i, "LD-INS-REG"): ir = "%s ($%02X)" % (names.get(op, "?"), op)
        irrow.append(ir)
        if on(i, "-AC-LD") and ends(i, "-AC-LD"):
            f = bus(i, "ALU"); acc = ("ALU%X(ACC,%s)" % (f, d or "?")) if on(i, "-ALU-FUNC") else (d or "?")
        accrow.append(acc)
        for t, nm in ((0, "-TMP-REG-LD0"), (1, "-TMP-REG-LD1")):
            if nm in S and on(i, nm) and ends(i, nm): tmp = d or "?"
        tmprow.append(tmp)
        pcrow.append(regname(0))
        if on(i, "-REG-FUNC-RD"):
            k = bus(i, "REG-RD-ID")
            if on(i, "-REG-UP") and ends(i, "-REG-UP"): inc[k] += 1
            if on(i, "-REG-DN") and ends(i, "-REG-DN"): inc[k] -= 1
        if on(i, "-REG-FUNC-LD"):
            k = bus(i, "REG-LD-ID")
            for nm in ("REG-LD-LO", "REG-LD-HI"):
                if on(i, nm) and ends(i, nm): loaded.add(k)
    # data becomes valid an access time after the address and -MEM-RD are both stable
    rows += [bus_wave(addr, "ADDRESS BUS", TIMING["pipe"] + TIMING["reg"]),
             bus_wave(data, "DATA BUS", TIMING["pipe"] + TIMING["reg"] + TIMING["mem"]),
             bus_wave(irrow, "IR", TIMING["pipe"] + TIMING["latch"]),
             bus_wave(accrow, "ACC", TIMING["pipe"] + TIMING["latch"])]
    if len(set(tmprow)) > 1: rows.append(bus_wave(tmprow, "TMP", TIMING["pipe"] + TIMING["latch"]))
    rows.append(bus_wave(pcrow, "PC (R0)", TIMING["pipe"] + TIMING["latch"]))
    head = [{"name": "uCODE CLK", "wave": "p" + "." * (n - 1)},
            {"name": "step", "wave": "=" * n, "data": [str(i) for i in range(n)]}, {}]
    return {"signal": head + rows,
            "head": {"text": "%s  (opcode $%02X)  -  %d microcode steps" % (names.get(op, "?"), op, n), "tick": 0},
            "config": {"hscale": 2}}

NOTES = ["Control levels are read from firmware/microcode/ucode-generator2/test.hex (one column per microcode step); active-low signals are drawn low when asserted.",
         "Bus rows (ADDRESS BUS, DATA BUS, IR, ACC, PC) come from an ASSUMED typical-LS timing model, not from measurements:",
         "  pipeline register (74LS374) outputs change %d%% of a step after the uCODE clock edge; the register card puts the selected register on the address bus %d%% of a step later;" % (TIMING["pipe"] * 100, TIMING["reg"] * 100),
         "  memory data is valid %d%% of a step after the address and -MEM-RD are both stable (62256 / 28C64); loads (IR, ACC, PC increment) take effect at the trailing edge of their pulse;" % (TIMING["mem"] * 100),
         "  'z' = nothing driving the bus; register values are labels only (PC+1, R1.lo, 'target' once a register was loaded from the bus). Timing constants: tools/ucode_wavedrom.py TIMING."]

def add_notes(svg_path, lines):
    """append a centred multi-line notes block under the rendered diagram (WaveDrom's footer is one centred line)"""
    s = open(svg_path).read()
    m = re.search(r'<svg[^>]*\sheight="(\d+)"', s); h = int(m.group(1))
    wm = re.search(r'<svg[^>]*\swidth="(\d+)"', s); w = int(wm.group(1))
    lh, top = 14, h + 10; extra = top + lh * len(lines) + 8 - h
    text = "".join('<text x="%d" y="%d" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="11" fill="#000">%s</text>' % (w // 2, top + lh * i, l.strip().replace("&", "&amp;").replace("<", "&lt;")) for i, l in enumerate(lines))
    s = re.sub(r'(<svg[^>]*\sheight=")%d"' % h, lambda mm: mm.group(1) + str(h + extra) + '"', s, count=1)
    s = re.sub(r'viewBox="0 0 (\d+) %d"' % h, lambda mm: 'viewBox="0 0 %s %d"' % (mm.group(1), h + extra), s, count=1)
    s = s.replace("</svg>", text + "</svg>")
    open(svg_path, "w").write(s)

def asm_forms():
    """mnemonic -> (operand syntax, instruction length in bytes) from software/assembler/yacc1.def"""
    lines = [l.rstrip("\n") for l in open(os.path.join(ROOT, "software/assembler/yacc1.def"))]
    out = {}
    for i in range(len(lines) - 1):
        m = re.match(r"([A-Z][A-Z0-9]*)(?:\s+(.*))?$", lines[i])
        if m and re.match(r"[0-9A-Fa-f]{2}", lines[i + 1].strip()):
            out.setdefault(m.group(1), ((m.group(2) or "").replace("\\{regs}", "Rn").replace("\\{ports}", "Pn").replace("\\B", "byte").replace("\\W", "addr"), len(lines[i + 1].split())))
    return out

def render(op, out, sig, recs, names):
    d = diagram(op, sig, recs, names); base = os.path.join(out, names.get(op, "OP%02X" % op))
    json.dump(d, open(base + ".json", "w"), indent=1)
    r = subprocess.run(["npx", "-y", "wavedrom-cli", "-i", base + ".json", "-s", base + ".svg"], capture_output=True, text=True)
    if r.returncode == 0: add_notes(base + ".svg", NOTES)
    return len(d["signal"][0]["wave"]), r.returncode == 0

def main():
    args = sys.argv[1:]; out = os.path.join(ROOT, "docs/isa")
    if "--out" in args: out = args[args.index("--out") + 1]; args = [a for a in args if a not in ("--out", out)]
    os.makedirs(out, exist_ok=True)
    sig, recs, names = signal_table(), microcode(), opcode_names(); byname = {v: k for k, v in names.items()}
    if "--all" in args:
        forms = asm_forms(); rows = []
        for op in sorted(names):
            if not any(recs.get(op, [])): rows.append((op, names[op], "", "", 0, None, "no microcode")); continue
            steps, ok = render(op, out, sig, recs, names)
            syn, nbytes = forms.get(names[op], ("", ""))
            rows.append((op, names[op], syn, nbytes, steps, names[op] + ".svg" if ok else None, "" if ok else "render failed"))
            print("%-8s $%02X %2s steps %s" % (names[op], op, steps, "ok" if ok else "FAILED"), flush=True)
        with open(os.path.join(out, "README.md"), "w") as f:
            f.write("# YACC1 ISA timing diagrams\n\nGenerated by `tools/ucode_wavedrom.py --all` (`make isa`) from the microcode image "
                    "`firmware/microcode/ucode-generator2/test.hex` and the signal table `firmware/microcode/yaccsignaldata2.h`: one WaveDrom "
                    "diagram per opcode defined in `firmware/opcodes.h`, control levels per microcode step plus the bus behaviour from an "
                    "ASSUMED typical-LS timing model (constants `TIMING` in the tool; every diagram says so in its notes). Register-indexed "
                    "families (e.g. MVIB $10-$17 = R0-R7) are drawn once, for the base opcode. `.json` = WaveDrom source, `.svg` = picture.\n\n"
                    "| Opcode | Mnemonic | Operands | Bytes | Microcode steps | Diagram |\n|---|---|---|---|---|---|\n")
            for op, nm, syn, nb, steps, svg, note in rows:
                f.write("| $%02X | %s | %s | %s | %s | %s |\n" % (op, nm, syn, nb, steps or "", ("[%s](%s)" % (svg, svg)) if svg else note))
        done = sum(1 for r in rows if r[5]); print("\n%d opcodes: %d diagrams, %d without microcode, index %s" % (len(rows), done, sum(1 for r in rows if r[6] == "no microcode"), os.path.join(out, "README.md")))
        return
    for a in args:
        op = byname.get(a.upper(), None) if not a.lower().startswith("0x") else int(a, 16)
        if op is None: op = int(a, 0)
        steps, ok = render(op, out, sig, recs, names)
        print("%s: %d steps -> %s%s" % (names.get(op, "?"), steps, os.path.join(out, names.get(op, "OP%02X" % op) + ".svg"), "" if ok else "  RENDER FAILED"))

if __name__ == "__main__": main()
