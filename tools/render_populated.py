# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""Render a KiCad board fully populated, for pictures: copy the .kicad_pcb to a temporary file, attach KiCad's standard
3D model to every footprint that has none (the Eagle-converted parts), and render that copy with kicad-cli.
The board file itself is never changed.

    python3 tools/render_populated.py BOARD.kicad_pcb OUT_PREFIX [--check]

writes OUT_PREFIX-top.png (flat, from above), OUT_PREFIX-bottom.png and OUT_PREFIX-angled.png (a three-quarter view),
all with KiCad's high-quality renderer. --check only lists what each footprint gets.

Each rule names the standard model and two of its pads: the model is placed so its first pad sits on the footprint's
pad of that name, and turned (in 90-degree steps) so the line to the second pad points the same way as on the board.
"""
import math, os, re, subprocess, sys

CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
M = "${KICAD10_3DMODEL_DIR}/"

# Eagle footprint name -> (model, origin pad, second pad, where the second pad is in the model's own footprint)
RULES = {
    "C025-050X050": ("Capacitor_THT.3dshapes/C_Disc_D5.0mm_W2.5mm_P2.50mm.step", "1", "2", (2.5, 0)),
    "C025-025X050": ("Capacitor_THT.3dshapes/C_Disc_D3.0mm_W2.0mm_P2.50mm.step", "1", "2", (2.5, 0)),
    "0207_7": ("Resistor_THT.3dshapes/R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal.step", "1", "2", (7.62, 0)),
    "0207_10": ("Resistor_THT.3dshapes/R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal.step", "1", "2", (10.16, 0)),
    "E2,5-7": ("Capacitor_THT.3dshapes/CP_Radial_D6.3mm_P2.50mm.step", "+", "-", (2.5, 0)),
    "LED5MM": ("LED_THT.3dshapes/LED_D5.0mm.step", "K", "A", (2.54, 0)),
    "HC49U-V": ("Crystal.3dshapes/Crystal_HC49-4H_Vertical.step", "1", "2", (4.88, 0)),
    "MA03-1": ("Connector_PinHeader_2.54mm.3dshapes/PinHeader_1x03_P2.54mm_Vertical.step", "1", "2", (0, 2.54)),
    "1X03": ("Connector_PinHeader_2.54mm.3dshapes/PinHeader_1x03_P2.54mm_Vertical.step", "1", "2", (0, 2.54)),
    "MA04-2": ("Connector_PinHeader_2.54mm.3dshapes/PinHeader_2x04_P2.54mm_Vertical.step", "1", "3", (0, 2.54)),
    "2X07": ("Connector_PinHeader_2.54mm.3dshapes/PinHeader_2x07_P2.54mm_Vertical.step", "1", "3", (0, 2.54)),
    "RN-5": ("Resistor_THT.3dshapes/R_Array_SIP5.step", "1", "2", (2.54, 0)),
    "RN-9": ("Resistor_THT.3dshapes/R_Array_SIP9.step", "1", "2", (2.54, 0)),
    "SIL9": ("Resistor_THT.3dshapes/R_Array_SIP9.step", "1", "2", (2.54, 0)),
    "FABC96R": ("Connector_DIN.3dshapes/DIN41612_C_3x32_Male_Horizontal_THT.step", "A1", "A2", (2.54, 0)),
    "F09HP": ("Connector_Dsub.3dshapes/DSUB-9_Socket_Horizontal_P2.77x2.54mm_EdgePinOffset9.40mm.step",
              "1", "2", (-2.77, 0)),
}


def footprints(text):
    """(start, end) of every top-level (footprint ...) block."""
    out, i = [], 0
    while True:
        i = text.find("\n\t(footprint ", i)
        if i < 0:
            return out
        depth, j = 0, i + 2
        while True:
            c = text[j]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            elif c == '"':
                j = text.index('"', j + 1)
            j += 1
        out.append((i + 1, j + 1))
        i = j


def rule_for(name, pads):
    base = name.split(":")[-1]
    if base in RULES:
        return RULES[base]
    m = re.match(r"DIL(\d+)", base)
    if m and "1" in pads and "2" in pads:
        n = int(m.group(1))
        p1, pn = pads["1"], pads.get(str(n))
        w = 15.24 if pn and abs(math.dist(p1, pn) - 15.24) < abs(math.dist(p1, pn) - 7.62) else 7.62
        return ("Package_DIP.3dshapes/DIP-%d_W%.2fmm.step" % (n, w), "1", "2", (0, 2.54))
    return None


def model_block(model, offset, rot):
    return ('\t\t(model "%s%s"\n\t\t\t(offset\n\t\t\t\t(xyz %.4f %.4f 0)\n\t\t\t)\n\t\t\t(scale\n\t\t\t\t(xyz 1 1 1)\n'
            '\t\t\t)\n\t\t\t(rotate\n\t\t\t\t(xyz 0 0 %d)\n\t\t\t)\n\t\t)\n' % (M, model, offset[0], offset[1], rot))


def populate(text, report):
    pieces, last = [], 0
    for a, b in footprints(text):
        block = text[a:b]
        name = block.split('"')[1]
        ref = re.search(r'\(property "Reference" "([^"]*)"', block)
        ref = ref.group(1) if ref else "?"
        if "(model " in block:
            report.append("%-6s %-40s has a model" % (ref, name)); continue
        pads = {}
        for m in re.finditer(r'\(pad "([^"]*)"[^(]*\(at ([-\d.]+) ([-\d.]+)', block):
            pads.setdefault(m.group(1), (float(m.group(2)), float(m.group(3))))
        rule = rule_for(name, pads)
        if not rule or rule[1] not in pads or rule[2] not in pads:
            report.append("%-6s %-40s no model (left bare)" % (ref, name)); continue
        model, pa, pb, std = rule
        (ax, ay), (bx, by) = pads[pa], pads[pb]
        # angles with y up (board files have y down)
        ang = math.degrees(math.atan2(-(by - ay), bx - ax) - math.atan2(-std[1], std[0]))
        rot = -int(round(ang / 90.0)) * 90 % 360   # KiCad turns models clockwise for a positive angle
        pieces += [text[last:b - 1], model_block(model, (ax, -ay), rot), "\t"]
        last = b - 1
        report.append("%-6s %-40s %s, rotate %d" % (ref, name, model.split("/")[-1], rot))
    pieces.append(text[last:])
    return "".join(pieces)


def main():
    board, prefix = sys.argv[1], sys.argv[2]
    report = []
    text = populate(open(board, encoding="utf-8").read(), report)
    print("\n".join(report))
    if "--check" in sys.argv:
        return
    if True:
        # the copy sits beside the original (same project, libraries and variables)
        pcb = os.path.join(os.path.dirname(os.path.abspath(board)), ".render-populated.kicad_pcb")
        open(pcb, "w", encoding="utf-8").write(text)
        try:
            views = {"top": ["--side", "top"], "bottom": ["--side", "bottom"],
                     "angled": ["--side", "top", "--perspective", "--rotate", "-40,0,20", "--zoom", "0.9", "--floor"]}
            for view, args in views.items():
                out = "%s-%s.png" % (prefix, view)
                subprocess.run([CLI, "pcb", "render", "--quality", "high", "--width", "2000", "--height", "1400",
                                "--background", "opaque" if view == "angled" else "transparent"] + args +
                               ["-o", out, pcb], check=True, capture_output=True)
                print("wrote", out)
        finally:
            os.remove(pcb)


if __name__ == "__main__":
    main()
