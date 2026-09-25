#!/usr/bin/env python3
"""print_1to1.py - the 1:1 printable check sheet (US Letter, landscape) of a standoff placement option of the memory
card v2.0: lay the CF-to-IDE adapter (HX-2118P) on the print and see where its holes, header and slot land.

    python3 print_1to1.py <geometry .json> <out .pdf>

The JSON comes from gen_standoff.py geom (KiCad's python reads the board; this script needs only reportlab, which the
system python3 has). build.sh writes memory-v2.0-standoff-<opt>-1to1.pdf beside the renders.

Page 1: the board at 1:1, component side up, the bus-connector edge (X1) on the left, the JP1 end at the top; a 10 mm
grid numbered in mm from the bus-connector edge (x) and from the JP1 end (y) - the same grid as the first fit print
(its "JP2 end" is this JP1 end); parts shaded (footprint extents), pads dotted; J2 highlighted with its pin 1; the
adapter drawn in place (outline, the two standoff holes with crosses, the header shroud and pins, its pin-1 end, the
CF slot edge, the power pads), the ribbon zone, the ROM and its keep-clear zone; a 100 mm check bar.
Page 2: the side view at 1:1 (the height stack: card, J2 + plug, ribbon, standoffs, adapter, CF card) and the notes.
Every page carries the date and time it was made.
"""
import sys, json, datetime
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib import colors

PW, PH = landscape(letter)                     # 792 x 612 pt = 279.4 x 215.9 mm
L0, T0 = 20.0, 36.0                            # board origin (bus edge, JP1 end) on the page: mm from left / top
STAMP = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
BLUE = colors.Color(0.1, 0.3, 0.85)
ADFILL = colors.Color(0.2, 0.45, 1.0, alpha=0.10)
ORANGE = colors.Color(0.98, 0.72, 0.30)
ROMFILL = colors.Color(1.0, 0.93, 0.55)
RED = colors.Color(0.8, 0.1, 0.1)
GRID = colors.Color(0.72, 0.80, 0.95)
GREEN = colors.Color(0.1, 0.55, 0.2)


def main(src, out):
    d = json.load(open(src))
    ex0, ey0, ex1, ey1 = d["edge"]
    X = lambda x: (L0 + (x - ex0)) * mm
    Y = lambda y: PH - (T0 + (y - ey0)) * mm
    gx = lambda x: x - ex0                         # board mm -> print grid mm
    gy = lambda y: y - ey0
    c = canvas.Canvas(out, pagesize=(PW, PH))
    c.setTitle("YACC1 memory card v2.0 - standoff option %s - 1:1" % d["opt"].upper())
    c.setAuthor("YACC1-D hardware/cards/memory/kicad/v2.0/print_1to1.py")
    ad, j2 = d["adapter"], d["j2"]
    fps = {f["ref"]: f for f in d["fps"]}

    def rect(R, stroke=colors.black, fill=None, w=0.5, dash=None):
        c.saveState()
        c.setStrokeColor(stroke)
        c.setLineWidth(w)
        if dash:
            c.setDash(*dash)
        if fill is not None:
            c.setFillColor(fill)
        c.rect(X(R[0]), Y(R[3]), (R[2] - R[0]) * mm, (R[3] - R[1]) * mm, stroke=1 if stroke else 0,
               fill=1 if fill is not None else 0)
        c.restoreState()

    def text(s, x, y, size=6.5, font="Helvetica", color=colors.black, anchor="l", angle=0):
        c.saveState()
        c.setFillColor(color)
        c.setFont(font, size)
        c.translate(x, y)
        c.rotate(angle)
        {"l": c.drawString, "c": c.drawCentredString, "r": c.drawRightString}[anchor](0, 0, s)
        c.restoreState()

    def footer(page):
        text("YACC1 memory card v2.0 - standoff option %s - 1:1 check sheet - page %d/2 - made %s by print_1to1.py"
             % (d["opt"].upper(), page, STAMP), 12 * mm, 6 * mm, 6.5, color=colors.grey)
        text(STAMP, PW - 12 * mm, 6 * mm, 6.5, color=colors.grey, anchor="r")

    def checkbar(y0):
        c.setStrokeColor(colors.black)
        c.setLineWidth(0.8)
        x0 = 20 * mm
        c.line(x0, y0, x0 + 100 * mm, y0)
        for k in range(11):
            h = 3.5 if k % 5 == 0 else 2.0
            c.line(x0 + k * 10 * mm, y0, x0 + k * 10 * mm, y0 + h * mm)
        text("0", x0, y0 - 3.5 * mm, 7, anchor="c")
        text("100 mm", x0 + 100 * mm, y0 - 3.5 * mm, 7, anchor="c")
        text("CHECK: this bar must measure exactly 100 mm - print at 100 % / \"Actual size\", NOT \"Fit\" / "
             "\"Shrink to page\"", x0 + 106 * mm, y0 + 0.5 * mm, 7.5, "Helvetica-Bold")

    # ---------------------------------------------------------------------------------------------------------- page 1
    st = d.get("stats") or {}
    text("YACC1 memory card v2.0 - standoff option %s - 1:1, component side up" % d["opt"].upper(), 12 * mm,
         PH - 10 * mm, 12, "Helvetica-Bold")
    text(d["title"], 12 * mm, PH - 15 * mm, 8)
    text("Grid 10 mm, numbers = mm from the BUS-CONNECTOR edge (x, across) and from the JP1 end (y, down) - the same "
         "grid as the first fit print (its \"JP2 end\" = this JP1 end). Shaded = parts, dots = pads, blue = the "
         "adapter 15 mm above the card.", 12 * mm, PH - 19.5 * mm, 7)
    text("Lay the adapter on the blue outline, component side up, header toward the bus edge: its two holes must sit on "
         "the blue crosses, its header over the blue pin grid, pin 1 at the \"PIN 1 END\" mark.", 12 * mm,
         PH - 23 * mm, 7)
    # grid
    c.setStrokeColor(GRID)
    c.setLineWidth(0.3)
    for k in range(0, int(ex1 - ex0) + 1, 10):
        c.line(X(ex0 + k), Y(ey0), X(ex0 + k), Y(ey1))
        text("%d" % k, X(ex0 + k), Y(ey0) + 1.6 * mm, 6, color=BLUE, anchor="c")
    for k in range(0, int(ey1 - ey0) + 1, 10):
        c.line(X(ex0), Y(ey0 + k), X(ex1), Y(ey0 + k))
        text("%d" % k, X(ex0) - 8.6 * mm, Y(ey0 + k) - 0.8 * mm, 6, color=BLUE, anchor="r")
        c.line(X(ex0) - 8.3 * mm, Y(ey0 + k), X(ex0) - 7.8 * mm, Y(ey0 + k))
    text("x (mm from the bus-connector edge) ->", X(ex0) + 2 * mm, Y(ey0) + 4.6 * mm, 6, color=BLUE)
    text("BUS CONNECTOR EDGE (X1)", X(ex0) - 13 * mm, (Y(ey0) + Y(ey1)) / 2, 7, "Helvetica-Bold", anchor="c", angle=90)
    text("FREE TOP EDGE (card cage top)", X(ex1) + 3.5 * mm, (Y(ey0) + Y(ey1)) / 2, 7, "Helvetica-Bold", anchor="c",
         angle=90)
    text("JP1 end (y = 0)", X(ex1), Y(ey0) + 4.6 * mm, 6, color=BLUE, anchor="r")
    # ribbon zone, ROM keep-clear zone
    rect(d["ribbon"], ORANGE, None, 0.8, (3, 2))
    rz = d["rom"]
    rz = (max(rz[0], ex0), max(rz[1], ey0), min(rz[2], ex1), min(rz[3], ey1))     # the zone past an edge is air
    rect(rz, colors.Color(0.85, 0.55, 0.0), None, 0.9, (4, 2))
    # parts
    for f in d["fps"]:
        if f["hole"]:
            continue
        r = f["ref"]
        fill = colors.Color(0.87, 0.87, 0.87)
        if r == "J2":
            fill = ORANGE
        elif r == d["rom_ref"]:
            fill = ROMFILL
        elif r == "J3":
            fill = colors.Color(0.75, 0.9, 0.75)
        rect(f["box"], colors.Color(0.55, 0.55, 0.55), fill, 0.4)
    for f in d["fps"]:
        if f["hole"]:
            continue
        for p in f["pads"]:
            c.setFillColor(RED if f["ref"] == "J2" else colors.black)
            if f["ref"] == "J2" and p["n"] == "1":
                s = 1.7 * mm
                c.rect(X(p["x"]) - s / 2, Y(p["y"]) - s / 2, s, s, stroke=0, fill=1)
            else:
                c.circle(X(p["x"]), Y(p["y"]), 0.42 * mm, stroke=0, fill=1)
        bx = f["box"]
        cx, cy = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2
        tall = bx[3] - bx[1] > 1.6 * (bx[2] - bx[0])
        text(f["ref"], X(cx) + (0.9 * mm if tall else 0), Y(cy) - (0 if tall else 0.9 * mm), 5.5, "Helvetica-Bold",
             anchor="c", angle=90 if tall else 0)
    # the ROM label
    rom = fps[d["rom_ref"]]["box"]
    if rom[3] - rom[1] > rom[2] - rom[0]:                  # standing along y
        text("ROM - keep clear, removable", X((rom[0] + rom[2]) / 2) - 1.8 * mm, Y((rom[1] + rom[3]) / 2), 6.5,
             "Helvetica-Bold", colors.Color(0.6, 0.35, 0.0), "c", 90)
    else:
        text("ROM - keep clear, removable", X((rom[0] + rom[2]) / 2), Y((rom[1] + rom[3]) / 2) + 1.2 * mm, 6.5,
             "Helvetica-Bold", colors.Color(0.6, 0.35, 0.0), "c")
    text("keep-clear zone", X(rz[0]) + 0.8 * mm, Y(rz[3]) + 1.2 * mm, 5.5,
         color=colors.Color(0.6, 0.35, 0.0))
    # J2 = the IDE header ON THIS BOARD: solid, thick outline, its plug envelope dashed
    j2p1 = [p for p in fps["J2"]["pads"] if p["n"] == "1"][0]
    rect(j2["shroud"], RED, None, 1.6)
    if j2.get("plug"):
        rect(j2["plug"], RED, None, 0.6, (2, 1.5))
    text("J2 PIN 1", X(j2p1["x"]) - 1.6 * mm, Y(j2p1["y"]) - 5.2 * mm, 6.5, "Helvetica-Bold", RED, "r")
    jm = (j2["shroud"][1] + j2["shroud"][3]) / 2
    lbl = "J2 - IDE HEADER ON THIS BOARD (pin 1 "
    xl = X(j2["shroud"][0]) - 1.2 * mm
    wl = c.stringWidth(lbl + "  )", "Helvetica-Bold", 6.5)
    text(lbl, xl, Y(jm) - wl / 2, 6.5, "Helvetica-Bold", RED, "l", 90)
    c.setFillColor(RED)
    c.rect(xl - 4.4, Y(jm) - wl / 2 + c.stringWidth(lbl, "Helvetica-Bold", 6.5) + 0.8, 4.2, 4.2, stroke=0, fill=1)
    text(")", xl, Y(jm) - wl / 2 + c.stringWidth(lbl + "  ", "Helvetica-Bold", 6.5) + 1.0, 6.5, "Helvetica-Bold",
         RED, "l", 90)
    # the adapter
    o = ad["outline"]
    rect(o, BLUE, ADFILL, 1.3)
    rect(ad["shroud"], BLUE, None, 0.9, (3, 2))                  # the adapter's own header: dashed (15 mm up)
    text("ADAPTER'S IDE HEADER (on the adapter, 15 mm above)", X(ad["shroud"][0]) + 1.6 * mm,
         (Y(o[1]) + Y(o[3])) / 2, 5.5, "Helvetica-Bold", BLUE, "c", 90)
    c.setStrokeColor(BLUE)
    c.setLineWidth(3.0)
    c.line(X(ad["slot_x"]), Y(o[1]), X(ad["slot_x"]), Y(o[3]))
    text("CF CARD INSERTS HERE (into the adapter)", X(ad["slot_x"]) - 1.4 * mm, (Y(o[1]) + Y(o[3])) / 2,
         6, "Helvetica-Bold", BLUE, "c", 90)
    # the ribbon: arrows from J2 up to the adapter's header
    RIB = colors.Color(0.45, 0.45, 0.45)
    jx, hx0 = j2["px"] - 1.27, (ad["shroud"][0] + ad["shroud"][2]) / 2
    c.saveState()
    c.setStrokeColor(RIB)
    c.setFillColor(RIB)
    c.setLineWidth(0.9)
    for yy in (j2["shroud"][1] + 8.0, jm, j2["shroud"][3] - 8.0):
        c.line(X(jx), Y(yy), X(hx0) - 1.2 * mm, Y(yy))
        p = c.beginPath()
        p.moveTo(X(hx0), Y(yy))
        p.lineTo(X(hx0) - 1.6 * mm, Y(yy) + 0.8 * mm)
        p.lineTo(X(hx0) - 1.6 * mm, Y(yy) - 0.8 * mm)
        p.close()
        c.drawPath(p, stroke=0, fill=1)
    c.restoreState()
    for k, (outer, inner) in enumerate(ad["pins"]):
        for (x, y) in (outer, inner):
            c.setStrokeColor(BLUE)
            c.setLineWidth(0.5)
            c.circle(X(x), Y(y), 0.45 * mm, stroke=1, fill=0)
    (ox, oy), (ix, iy) = ad["pins"][0]
    c.setLineWidth(0.9)
    c.circle((X(ox) + X(ix)) / 2, Y(oy), 2.2 * mm, stroke=1, fill=0)
    text("ADAPTER PIN 1 END", X(ad["shroud"][2]) + 1.2 * mm, Y(oy) - 1.0 * mm, 6.5, "Helvetica-Bold", BLUE)
    (tx, ty), _ = ad["pins"][9]
    text("col. 10: pin 20 missing (key)", X(ad["shroud"][2]) + 1.0 * mm, Y(ty) - 0.8 * mm, 5, color=BLUE)
    c.setStrokeColor(BLUE)
    c.setLineWidth(0.4)
    c.setDash(2, 1.5)
    pw = ad["pwr"]
    c.rect(X(pw[0]), Y(pw[3]), (pw[2] - pw[0]) * mm, (pw[3] - pw[1]) * mm, stroke=1, fill=0)
    c.setDash()
    text("power pads (approx.)", X(pw[2]) + 0.8 * mm, Y((pw[1] + pw[3]) / 2) - 0.8 * mm, 5.5, color=BLUE)
    for k, (hx, hy) in enumerate(ad["holes"]):
        c.setStrokeColor(BLUE)
        c.setLineWidth(0.6)
        c.circle(X(hx), Y(hy), d["hx"]["hole_dia"] / 2 * mm, stroke=1, fill=0)
        c.setDash(1.5, 1.2)
        c.circle(X(hx), Y(hy), d["hex_r"] * mm, stroke=1, fill=0)
        c.setDash()
        c.setLineWidth(0.3)
        c.line(X(hx - 5), Y(hy), X(hx + 5), Y(hy))
        c.line(X(hx), Y(hy - 5), X(hx), Y(hy + 5))
        text("H%d  x %.1f / y %.1f" % (k + 1, gx(hx), gy(hy)), X(hx) + 4.0 * mm, Y(hy) + (1.8 if k else -3.6) * mm,
             6.5, "Helvetica-Bold", BLUE)
    c.setStrokeColor(colors.black)
    c.setLineWidth(1.0)
    c.rect(X(ex0), Y(ey1), (ex1 - ex0) * mm, (ey1 - ey0) * mm, stroke=1, fill=0)
    # callouts under the board, each with a leader to what it names
    calls = [
        ("J2 = the IDE header ON THIS BOARD (solid red, pin 1 = square pad); with its ribbon plug it stands ~%g mm; "
         "plug envelope dashed red" % d.get("plug_h", 18), RED, (jx, j2["shroud"][1] + 4.5)),
        ("SHORT 40-WIRE RIBBON, pin 1 to pin 1 (%s between the plugs): the grey arrows, J2 -> the adapter's header"
         % d.get("ribbon_text", "~5-8 cm"), colors.Color(0.4, 0.4, 0.4), ((j2["shroud"][2] + o[0]) / 2, j2["shroud"][3] - 8.0)),
        ("ADAPTER'S IDE HEADER (dashed blue): on the %s adapter, 15 mm above on standoffs H1 / H2 - the adapter does NOT "
         "plug into J2" % d["hx"]["name"].split()[0], BLUE, (hx0, o[3] - 3.0)),
        ("CF CARD INSERTS HERE (into the adapter): the thick blue slot edge; the card is pushed in toward the bus",
         BLUE, (ad["slot_x"], o[3] - 6.0)),
    ]
    def badge(x, y, n, col):                              # a numbered marker: the callout below says what it is
        c.saveState()
        c.setFillColor(colors.white)
        c.setStrokeColor(col)
        c.setLineWidth(0.8)
        c.circle(x, y, 1.9 * mm, stroke=1, fill=1)
        c.restoreState()
        text(str(n), x, y - 0.8 * mm, 7, "Helvetica-Bold", col, "c")

    for k, (s_, col, (tx, ty)) in enumerate(calls):
        yb = Y(ey1) - (6.5 + 4.4 * k) * mm
        badge(X(ex0) + 2 * mm, yb + 0.8 * mm, k + 1, col)
        text(s_, X(ex0) + 5 * mm, yb, 6.3, "Helvetica-Bold", col)
        badge(X(tx), Y(ty), k + 1, col)
    # the numbers, right of the board
    xs = X(ex1) + 8 * mm
    yy = Y(ey0) + 1 * mm
    lines = [
        ("Where things land (print grid, mm)", "Helvetica-Bold"),
        ("x from the bus edge, y from the JP1 end", None),
        ("H1 (pin-1 end): x %.1f  y %.1f" % (gx(ad["holes"][0][0]), gy(ad["holes"][0][1])), None),
        ("H2 (power-pad end): x %.1f  y %.1f" % (gx(ad["holes"][1][0]), gy(ad["holes"][1][1])), None),
        ("holes 52.0 apart, 3.2 mm drill, 7 mm copper keep-out", None),
        ("adapter x %.1f-%.1f, y %.1f-%.1f" % (gx(o[0]), gx(o[2]), gy(o[1]), gy(o[3])), None),
        ("  header edge x %.1f, CF slot edge x %.1f" % (gx(o[0]), gx(o[2])), None),
        ("J2 pin 1: x %.1f  y %.1f (square pad)" % (gx(j2p1["x"]), gy(j2p1["y"])), None),
        ("J2 pins y %.1f-%.1f, odd row x %.1f, even x %.1f" % (gy(j2["py1"] - 48.26), gy(j2["py1"]), gx(j2["px"]),
                                                              gx(j2["px"] - 2.54)), None),
        ("ROM %s keep-clear x %.1f-%.1f, y %.1f-%.1f" % (d["rom_ref"], gx(rz[0]), gx(rz[2]), gy(rz[1]), gy(rz[3])),
         None),
        ("  (on the board; past an edge it is free air)", None),
        ("", None),
        ("Standoffs", "Helvetica-Bold"),
        ("M3 hex %g mm female-female (5.5 AF)," % d["standoff"], None),
        ("M3 x 6 screws + washers both sides", None),
        ("adapter underside %g mm above the card" % d["standoff"], None),
        ("", None),
        ("Straight ribbon, pin 1 to pin 1", "Helvetica-Bold"),
        ("J2 pin 1 and the adapter's pin 1 at the", None),
        ("SAME end (y max): stripe on that end at", None),
        ("both plugs; the ribbon arches up from J2", None),
        ("and down into the adapter's header.", None),
        ("", None),
        ("Trial autoroute (Freerouting, unpolished)", "Helvetica-Bold"),
    ]
    if st:
        lines += [("unrouted %d, vias %d, track %d mm" % (st["unrouted"], st["vias"], st["length"]), None),
                  ("DRC copper violations: %s" % ("none" if not st["copper"] else st["copper"]), None)]
    else:
        lines += [("(not routed yet)", None)]
    for s, font in lines:
        text(s, xs, yy, 6.3 if font is None else 6.6, font or "Helvetica")
        yy -= 3.5 * mm
    checkbar(22 * mm)
    text("Also check with a ruler: the two blue hole crosses are 52.0 mm apart.", 20 * mm, 14 * mm, 7)
    footer(1)
    c.showPage()

    # ---------------------------------------------------------------------------------------------------------- page 2
    text("Side view at 1:1 - the height stack (section along x, seen from the y-max end; card component side up)",
         12 * mm, PH - 10 * mm, 12, "Helvetica-Bold")
    text("Heights are typical figures, not measured: box header 9, IDC plug on it +9 (~18), plug body ~1.5 wider than "
         "the shroud each side, socketed DIP 8.5-9.5, adapter 1.6 thick, CF holder + card ~6-8 on the adapter.",
         12 * mm, PH - 15 * mm, 7)
    Z0 = 100.0                                    # card top surface: mm from the page bottom
    Xs = lambda x: (L0 + (x - ex0)) * mm
    Zs = lambda z: (Z0 + z) * mm

    def box(x0, x1, z0, z1, stroke=colors.black, fill=None, w=0.5, dash=None):
        c.saveState()
        c.setStrokeColor(stroke)
        c.setLineWidth(w)
        if dash:
            c.setDash(*dash)
        if fill is not None:
            c.setFillColor(fill)
        c.rect(Xs(x0), Zs(z0), (x1 - x0) * mm, (z1 - z0) * mm, stroke=1, fill=1 if fill is not None else 0)
        c.restoreState()

    so = d["standoff"]
    box(ex0, ex1, -1.6, 0, colors.black, colors.Color(0.3, 0.6, 0.3))
    text("memory card (1.6 mm)", Xs(ex0 + 14), Zs(-1.6) - 3.2 * mm, 6.5)
    box(ex0 - 8.0, ex0 + 11.0, -6.0, 5.5, colors.black, colors.Color(0.8, 0.8, 0.8))
    text("X1", Xs(ex0 + 1.5), Zs(1), 6.5, "Helvetica-Bold", anchor="c")
    # low parts: sockets + DIPs along the card (the bus side of J2 and under the adapter)
    pe = j2.get("plug") or (j2["shroud"][0] - 1.5, 0, j2["shroud"][2] + 1.5, 0)
    ph = d.get("plug_h", 18.0)
    box(ex0 + 14, pe[0] - 0.3, 0, 9.0, colors.grey, colors.Color(0.9, 0.9, 0.9), dash=(2, 1))
    text("socketed DIPs ~9", Xs(ex0 + 30), Zs(4), 6, anchor="c")
    box(ad["outline"][0] + 1, ad["outline"][2] - 1, 0, 9.0, colors.grey, colors.Color(0.9, 0.9, 0.9), dash=(2, 1))
    text("DIPs under the adapter ~9", Xs(ad["holes"][0][0] + 3.5), Zs(4), 6)
    # J2 (on this board) + its ribbon plug, and the plug envelope
    box(j2["shroud"][0], j2["shroud"][2], 0, 9.0, RED, ORANGE, 1.0)
    box(pe[0], pe[2], 5.0, ph, RED, colors.Color(1.0, 0.85, 0.75), 0.7, (2, 1))
    text("J2 ON THIS BOARD, 9", Xs(pe[0]) - 1 * mm, Zs(3.0), 5.5, "Helvetica-Bold", RED, "r")
    text("its plug, top ~%g" % ph, Xs(j2["px"] - 1.27), Zs(ph - 4.0), 5.5, color=RED, anchor="c")
    text("plug envelope +%.1f each side" % d.get("plug_side", 1.5), Xs(pe[0]) - 1 * mm, Zs(ph - 1.5), 5.5, color=RED,
         anchor="r")
    # standoffs + adapter + its own header and plug + the CF card in its holder
    hx = ad["holes"][0][0]
    box(hx - 2.75, hx + 2.75, 0, so, BLUE, colors.Color(0.85, 0.88, 1.0), 0.6)
    box(hx - 1.6, hx + 1.6, -1.6 - 2.5, -1.6, BLUE, None, 0.5)
    text("M3 standoff %g" % so, Xs(hx) + 3.6 * mm, Zs(so - 4.0), 6.5, "Helvetica-Bold", BLUE)
    text("screw/nut + washer ~3 below", Xs(hx) + 3.6 * mm, Zs(-4.2), 5.5, color=BLUE)
    o = ad["outline"]
    box(o[0], o[2], so, so + 1.6, BLUE, colors.Color(0.55, 0.7, 1.0), 0.8)
    top = so + 1.6
    sh = ad["shroud"]
    box(sh[0], sh[2], top, top + 9.0, BLUE, colors.Color(0.85, 0.9, 1.0), 0.8)
    box(sh[0] - 1.5, sh[2] + 1.5, top + 4.0, top + 18.0, BLUE, None, 0.7, (2, 1))
    text("the adapter's OWN header (9) + plug, top ~%.0f" % (top + 18.0), Xs(sh[2] + 1.5) + 1.0 * mm, Zs(top + 14.0),
         5.5, color=BLUE)
    box(o[0] + 14, o[2], top, top + 8.0, BLUE, None, 0.6, (3, 1.5))
    box(o[2] - 38.0, o[2] + 4.0, top + 2.5, top + 5.8, colors.black, colors.Color(0.75, 0.75, 0.75), 0.6)
    text("CF card in its holder (pushed in from the slot edge, toward the bus)", Xs(o[2] - 19.0), Zs(top + 9.5), 5.5,
         anchor="c")
    text("adapter 1.6", Xs(o[2]) + 5.5 * mm, Zs(so), 6, color=BLUE)
    # the ribbon: up out of J2's plug, a loop, down into the adapter's plug
    c.saveState()
    c.setStrokeColor(colors.Color(0.5, 0.5, 0.5))
    c.setLineWidth(1.8)
    x_a, x_b = j2["px"] - 1.27, (sh[0] + sh[2]) / 2
    zt = top + 18.0 + 6.0
    p = c.beginPath()
    p.moveTo(Xs(x_a), Zs(ph))
    p.curveTo(Xs(x_a), Zs(zt + 3), Xs(x_b), Zs(zt + 3), Xs(x_b), Zs(top + 18.0))
    c.drawPath(p, stroke=1, fill=0)
    c.restoreState()
    text("SHORT 40-WIRE RIBBON, pin 1 to pin 1, %s between the plugs (min. ~%.0f mm)"
         % (d.get("ribbon_text", "~5-8 cm"), d.get("ribbon_min", 40)), Xs(x_a) - 3 * mm, Zs(zt + 1.5), 6,
         "Helvetica-Bold", colors.Color(0.4, 0.4, 0.4), "r")
    # height marks
    for z, s_ in ((ph, "J2's plug top ~%.0f" % ph), (top + 5.8, "CF card top ~%.0f" % (top + 5.8)),
                  (top + 18.0, "adapter's plug top ~%.0f" % (top + 18.0)), (zt + 1.5, "ribbon loop ~%.0f" % (zt + 1.5))):
        c.setStrokeColor(colors.Color(0.6, 0.2, 0.6))
        c.setLineWidth(0.3)
        c.setDash(1, 1)
        c.line(Xs(ex0), Zs(z), Xs(ex1 + 6), Zs(z))
        c.setDash()
        text(s_ + " mm above the card", Xs(ex1) + 7 * mm, Zs(z) - 0.8 * mm, 6.3, color=colors.Color(0.6, 0.2, 0.6))
    # notes
    notes = [
        "J2 is the IDE header ON THIS BOARD. The CF adapter does NOT plug into it: the adapter sits on two %g mm M3 standoffs "
        "and has its OWN IDE header; a short 40-wire ribbon (%s) joins the two, pin 1 to pin 1." % (so, d.get("ribbon_text", "")),
        "Standoffs: %g mm M3 hex female-female (5.5 mm across flats) + M3 x 6 screws and washers (or %g mm male-female "
        "with a nut under the card); %g mm keeps ~3.5 mm between socketed DIPs (~9 mm)" % (so, so, so),
        "and the adapter's pin tails (~2-2.5 mm under it). J2 with its plug stands ~%.0f mm, taller than the standoffs: "
        "its plug envelope stays outside the adapter outline." % ph,
        "Total height above the card: CF card ~%.0f mm, the plug on the adapter's header ~%.0f mm, the ribbon loop "
        "~%.0f mm; below the card: screw heads / nuts ~3 mm." % (top + 5.8, top + 18.0, zt + 1.5),
        "Slot pitch of the card cage: NOT KNOWN - if the neighbour card sits closer than ~%.0f mm above this card's "
        "component side, leave that slot empty." % (zt + 3),
        "Pin 20: the adapter has no pin 20 (key). J2 has it fitted: use a ribbon whose plugs have pin 20 OPEN, or pull "
        "J2's pin 20. JP2 (pin 20 = +5 V) stays OPEN.",
        "Power: the adapter takes +5 V through its power pads, by a short cable from J3 (+5V, G, G, nc) - pad order to "
        "be confirmed on the adapter.",
    ]
    yy = 52 * mm
    for s in notes:
        text(s, 12 * mm, yy, 7)
        yy -= 4.2 * mm
    checkbar(12 * mm)
    footer(2)
    c.showPage()
    c.save()
    print("1:1 print -> %s" % out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
