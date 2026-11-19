#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""print_1to1.py - the 1:1 check print of the YACC1 I/O card V1.2 (US Letter, portrait): print it at 100 %, measure
its two 100 mm bars, and lay the parts whose fit matters on it before any order - the DB9, a toggle, a TIL311, the
LCD module and the cell's holder.

    python3 print_1to1.py <geometry .json> <out .pdf>

The JSON comes from gen_io12.py geom (KiCad's Python reads the board; this script needs only reportlab, which the
system python3 has). build.sh writes io-v1.2-1to1.pdf beside the board on every build.

The sheet shows the board at 1:1, component side up, as the card stands in the backplane: the bus connector X1 at
the bottom, the front edge at the top, so the silkscreen reads upright. Black is the silkscreen as the board has it
(KiCad's own outlines of every text and line); grey is each pad, with its hole at the drilled size in white (a cross
in the holes of 1.5 mm and more); blue is the parts' bodies (the Fab layer); yellow marks the five parts to lay on
it, numbered. Beside the board: what the board has for each of the five (pins, pitches, holes), measured here from
the pads, to hold against the part or its data sheet. A 100 mm bar across and one down: both must measure 100 mm, or
the print is not 1:1. The foot carries the board file's SHA-256: the same board gives the same PDF, byte for byte.
"""
import sys, json, math
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.pdfgen.canvas import FILL_EVEN_ODD
from reportlab.pdfbase.pdfmetrics import stringWidth

PW, PH = letter                                # 612 x 792 pt = 215.9 x 279.4 mm
L0, B0 = 17.0, 36.0                            # the standing board's bottom left corner on the page, mm
COL = 143.0                                    # the text column beside the board, mm from the left
BLUE = colors.Color(0.10, 0.30, 0.85)
PAD = colors.Color(0.74, 0.74, 0.74)
MARK = colors.Color(1.0, 0.95, 0.62)
CALL = colors.Color(0.85, 0.33, 0.05)
GREY = colors.Color(0.40, 0.40, 0.40)

# the parts to lay on the print: (number, references, what the part is, the side of the board its number stands on,
# the reference its leader goes to)
KEY = [
    (1, ["J1"], "DB9 socket, right angle", "r", "J1"),
    (2, ["S%d" % n for n in range(9)], "M9040P toggle", "l", "S7"),
    (3, ["DS1", "DS2"], "TIL311", "r", "DS2"),
    (4, ["DS3"], "LCD module, 16 x 2", "l", "DS3"),
    (5, ["BT1"], "CR2032 holder, Keystone 103", "r", "BT1"),
]


def dist(a, b):
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


def facts(n, fps, edge):
    """what the board has for key part n, from its pads and body: the lines of the table"""
    if n == 1:
        f = fps["J1"]
        p = {q["n"]: q for q in f["pads"] if q["n"] != "SH"}
        sh = [q for q in f["pads"] if q["n"] == "SH"]
        d = dist(p["1"], p["5"])
        ux, uy = (p["5"]["x"] - p["1"]["x"]) / d, (p["5"]["y"] - p["1"]["y"]) / d     # along the row of pins 1-5
        rows = abs((p["6"]["x"] - p["1"]["x"]) * uy - (p["6"]["y"] - p["1"]["y"]) * ux)
        return ["%d pins in two rows %.2f mm apart" % (len(p), rows),
                "%.2f mm from pin to pin, holes %.2f mm" % (dist(p["1"], p["2"]), p["1"]["drill"][0]),
                "mounting holes %.2f mm apart, %.2f mm" % (dist(sh[0], sh[1]), sh[0]["drill"][0]),
                "their line %.2f mm inside the front edge" % (edge[2] - sh[0]["x"]),
                "the body %.1f mm beyond the edge" % (f["box"][2] - edge[2])]
    if n == 2:
        f = fps["S0"]
        p = {q["n"]: q for q in f["pads"]}
        return ["three lugs %.2f mm apart, holes %.2f mm" % (dist(p["1"], p["2"]), p["1"]["drill"][0]),
                "pads %.2f x %.2f mm" % tuple(p["1"]["size"]),
                "switch to switch %.2f mm (S7 ... S0)" % dist(p["2"], {q["n"]: q for q in fps["S1"]["pads"]}["2"])]
    if n == 3:
        f = fps["DS1"]
        p = {q["n"]: q for q in f["pads"]}
        gone = [str(k) for k in range(1, 15) if str(k) not in p]
        return ["%d pins of 14: no pin %s" % (len(p), ", ".join(gone)),
                "rows %.2f mm apart, %.2f mm from pin to pin" % (dist(p["1"], p["14"]), dist(p["1"], p["2"])),
                "holes %.2f mm" % p["1"]["drill"][0]]
    if n == 4:
        f = fps["DS3"]
        p = {q["n"]: q for q in f["pads"] if q["n"]}
        h = [q for q in f["pads"] if not q["n"]]
        span = sorted((max(q["x"] for q in h) - min(q["x"] for q in h), max(q["y"] for q in h) - min(q["y"] for q in h)))
        body = sorted((f["box"][2] - f["box"][0], f["box"][3] - f["box"][1]))
        return ["%d pins in a row, %.2f mm apart" % (len(p), dist(p["1"], p["2"])),
                "holes %.2f mm" % p["1"]["drill"][0],
                "four mounting holes %.2f mm, not plated," % h[0]["drill"][0],
                "%.2f x %.2f mm apart" % (span[1], span[0]),
                "pin 1 is %.2f mm from the nearest of them" % min(dist(p["1"], q) for q in h),
                "the module %.1f x %.1f mm" % (body[1], body[0])]
    f = fps["BT1"]
    p = {q["n"]: q for q in f["pads"]}
    return ["two pins %.2f mm apart, holes %.2f mm" % (dist(p["1"], p["2"]), p["1"]["drill"][0]),
            "+ is pin 1, the square pad"]


def main(src, out):
    d = json.load(open(src))
    ex0, ey0, ex1, ey1 = d["edge"]
    fps = {f["ref"]: f for f in d["fps"]}
    # the card standing: the board's x runs up the page, its y across (a quarter turn of the drawing, not a mirror)
    XY = lambda x, y: ((L0 + (y - ey0)) * mm, (B0 + (x - ex0)) * mm)
    W, H = ey1 - ey0, ex1 - ex0                                # the standing board: across and up
    name = "%s %s" % (d["card"], d["rev"])
    c = canvas.Canvas(out, pagesize=(PW, PH), pageCompression=1, invariant=1)
    c.setTitle("%s - 1:1 check print" % name)
    c.setAuthor("YACC1-D hardware/cards/io/kicad/v1.2/print_1to1.py")

    def text(s, x, y, size=6.6, font="Helvetica", color=colors.black, anchor="l", angle=0):
        c.saveState()
        c.setFillColor(color)
        c.setFont(font, size)
        c.translate(x * mm, y * mm)
        c.rotate(angle)
        {"l": c.drawString, "c": c.drawCentredString, "r": c.drawRightString}[anchor](0, 0, s)
        c.restoreState()

    def wrapped(s, x, y, width, size=6.6, font="Helvetica", lead=3.0, color=colors.black):
        line = ""
        for w in s.split():
            t = (line + " " + w).strip()
            if stringWidth(t, font, size) <= width * mm:
                line = t
            else:
                text(line, x, y, size, font, color)
                y -= lead
                line = w
        text(line, x, y, size, font, color)
        return y - lead

    def filled(polys, color):
        c.setFillColor(color)
        for poly in polys:
            p = c.beginPath()
            for r in poly:
                p.moveTo(*XY(*r[0]))
                for q in r[1:]:
                    p.lineTo(*XY(*q))
                p.close()
            c.drawPath(p, stroke=0, fill=1, fillMode=FILL_EVEN_ODD)

    def box(f):                                                # a part's body on the page: left, bottom, right, top
        (a, b), (e, g) = XY(f["box"][0], f["box"][1]), XY(f["box"][2], f["box"][3])
        return a, b, e, g

    def bar(x, y, up):
        """a 100 mm bar from (x, y), across or up, a tick every 10 mm"""
        c.setStrokeColor(colors.black)
        c.setLineWidth(0.8)
        dx, dy = (0, 1) if up else (1, 0)
        c.line(x * mm, y * mm, (x + 100 * dx) * mm, (y + 100 * dy) * mm)
        for k in range(11):
            h = 3.5 if k % 5 == 0 else 2.0
            c.line((x + 10 * k * dx) * mm, (y + 10 * k * dy) * mm,
                   (x + 10 * k * dx - h * dy) * mm, (y + 10 * k * dy + h * dx) * mm)
        if up:                                                 # its words run up the page, on the side away from the ticks
            text("0", x + 3.4, y, 7, angle=90)
            text("100 mm", x + 3.4, y + 100, 7, anchor="r", angle=90)
            text("CHECK: exactly 100 mm", x + 3.4, y + 50, 7.5, "Helvetica-Bold", anchor="c", angle=90)
        else:
            text("0", x, y - 3.4, 7, anchor="c")
            text("100 mm", x + 100, y - 3.4, 7, anchor="c")
            text("CHECK: exactly 100 mm", x + 50, y - 3.6, 7.5, "Helvetica-Bold", anchor="c")

    # --- the parts to lay on it, marked under everything else
    c.setFillColor(MARK)
    for n, refs, what, side, at in KEY:
        for r in refs:
            a, b, e, g = box(fps[r])
            c.rect(a, b, e - a, g - b, stroke=0, fill=1)
    # --- the board: silkscreen, outline, pads, bodies, holes
    filled(d["silk"], colors.black)
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.7)
    c.rect(L0 * mm, B0 * mm, W * mm, H * mm, stroke=1, fill=0)
    pads = [p for f in d["fps"] for p in f["pads"]]
    filled([[p["poly"]] for p in pads], PAD)
    filled(d["fab"], BLUE)
    for p in pads:
        dia = p["drill"][0]
        if not dia:
            continue
        if p["drill"][1] != dia:
            raise SystemExit("print_1to1: a slot (pad %s): only round holes are drawn" % p["n"])
        x, y = XY(p["x"], p["y"])
        c.setFillColor(colors.white)
        c.setStrokeColor(colors.black)
        c.setLineWidth(0.3)
        c.circle(x, y, dia / 2 * mm, stroke=1, fill=1)
        if dia >= 1.5:
            c.setLineWidth(0.15)
            c.line(x - dia / 2 * mm, y, x + dia / 2 * mm, y)
            c.line(x, y - dia / 2 * mm, x, y + dia / 2 * mm)
    # --- the numbers of the parts to lay on it, at the board's sides
    for n, refs, what, side, at in KEY:
        a, b, e, g = box(fps[at])
        y = (b + g) / 2
        x0, x1 = ((L0 - 7) * mm, a) if side == "l" else ((L0 + W + 7) * mm, e)
        c.setStrokeColor(CALL)
        c.setLineWidth(0.5)
        c.line(x0, y, x1, y)
        c.setFillColor(CALL)
        c.circle(x0, y, 2.6 * mm, stroke=0, fill=1)
        text(str(n), x0 / mm, y / mm - 1.15, 9, "Helvetica-Bold", colors.white, "c")
    # --- the edges
    low = min(x for poly in d["silk"] for r in poly for x, y in r)   # the connector's outline hangs over the edge
    text("BUS CONNECTOR X1: the card stands on this edge", L0 + W / 2, B0 + (low - ex0) - 3.3, 6.5, color=GREY,
         anchor="c")
    text("FRONT EDGE: the top of the standing card", L0, B0 + H + 1.6, 6.5, color=GREY)
    # --- the bars
    bar(L0, 17.0, False)
    bar(204.0, 60.0, True)
    # --- the title and the column beside the board
    text("%s - 1:1 check print, component side up" % name, L0, PH / mm - 9.5, 12, "Helvetica-Bold")
    text("The board is %.1f x %.1f mm, drawn as the card stands in the backplane." % (H, W), L0, PH / mm - 14.0, 7.5)
    y = B0 + H - 1.0
    text("How to use this sheet", COL, y, 8, "Helvetica-Bold")
    y -= 4.0
    for s in ('1. Print on US Letter at 100 % ("Actual size"), not "Fit" or "Scale to fit".',
              "2. Measure both bars with a ruler: each must be exactly 100 mm. If not, the print is not 1:1.",
              "3. Lay each numbered part on its yellow place, pins on the holes. Every pin must stand in a white "
              "hole and the body inside its blue outline."):
        y = wrapped(s, COL, y, 52, lead=3.0) - 0.8
    y -= 1.0
    y = wrapped("Black: the silkscreen. Grey: pads. White: holes at the drilled size. Blue: the parts' bodies. "
                "Yellow: the parts to lay on it.", COL, y, 52, 6.2, "Helvetica-Oblique", 2.8, GREY) - 3.0
    text("What the board has for each", COL, y, 8, "Helvetica-Bold")
    y -= 5.2
    for n, refs, what, side, at in KEY:
        c.setFillColor(CALL)
        c.circle((COL + 2.2) * mm, (y + 0.9) * mm, 2.2 * mm, stroke=0, fill=1)
        text(str(n), COL + 2.2, y - 0.05, 8, "Helvetica-Bold", colors.white, "c")
        who = refs[0] if len(refs) == 1 else ("%s-%s" % (refs[0], refs[-1]) if len(refs) > 2 else ", ".join(refs))
        text(who, COL + 6.0, y, 7.2, "Helvetica-Bold")
        y -= 3.2
        text(what, COL + 6.0, y, 6.8, "Helvetica-Bold")
        y -= 3.2
        for line in facts(n, fps, d["edge"]):
            y = wrapped(line, COL + 6.0, y, 47)
        y -= 2.6
    wrapped("The figures are measured from this board's pads and bodies: hold them against the part itself or "
            "its data sheet.", COL, y, 52, 6.2, "Helvetica-Oblique", 2.8, GREY)
    # --- the foot
    text("%s (%s) - 1:1 check print - %s, SHA-256 %s - print_1to1.py"
         % (name, d["date"], d["pcb"], d["sha256"][:16]), L0, 7.5, 6.2, color=GREY)
    c.showPage()
    c.save()
    print("print_1to1: %s, US Letter portrait, the board %.1f x %.1f mm at 1:1 (board file %s)"
          % (out.split("/")[-1], H, W, d["sha256"][:12]))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
