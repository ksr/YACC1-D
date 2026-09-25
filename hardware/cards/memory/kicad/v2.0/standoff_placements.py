"""standoff_placements.py - the STANDOFF placement options of the memory card v2.0 (Ken, 2026-09-24): the CF-to-IDE
adapter (an HX-2118P) mounts flat on two M3 standoffs ON the memory card, fed by a short straight IDE ribbon from J2.
Plain data + plain geometry (no KiCad import): read by gen_standoff.py (boards, checks) and print_1to1.py (the 1:1
print, through the geometry JSON gen_standoff.py writes).

Board coordinates as everywhere in this folder (mm, y down): outline x 17.747..195.527, y 10.025..123.995; x = 17.7 is
the bus connector X1's edge, x = 195.5 the card's FREE TOP EDGE in the cage; y = 10 is the JP1 end (where the top-edge
options had JP2), y = 124 the other side edge (the PWR LED corner).

Ken's decisions (2026-09-24):
  - J2 runs PARALLEL to X1 (its long axis along y), about 1/3 of the way from the bus edge to the top edge (pin rows at
    board x ~ 77 +/- 10 mm), just BESIDE the adapter's header edge on the bus-connector side, not under the adapter.
  - The adapter sits above the card on two standoffs, its header edge toward the bus connector, its CF slot toward
    the free top edge (a CF card is pushed in toward the bus).
  - The ROM IC13 (28C64) is pulled and reburnt now and then: nothing above it (adapter, standoffs, ribbon), room to
    lever it out or to fit a ZIF socket (ROM_KEEP below).
  - The LEDs stay where they are (the free top-edge corner at y = 124); X1, the outline, JP1 and the U$1 block
    jumpers stay where the built card has them.

The adapter, as measured from Ken's photo and checked by Ken with a 1:1 print (the "view": component side up, IDE
header at the top; view x to the right along the header edge, view y down from the header edge):
  board 60.0 (along the header) x 44.0 mm; male 2x20 2.54 mm shrouded header along one 60 mm edge, pin 20 MISSING (the
  key: no +5 V through IDE pin 20); two M3 holes only, both at the header end, 52.0 mm apart (+/- 0.7), centred on the
  header, 15.3 mm from the header edge, 4.0 mm in from the side edges; the CF slot opens at the far edge (44 mm from
  the header edge); four unpopulated power pads in a row between the header and the holes, just inboard of the
  RIGHT-hand hole (probably +5V / GND / GND / +12V, floppy style: Ken to confirm); pin 1 at the LEFT end of the header.

View -> board (the adapter turned so that its header edge faces the bus connector and its slot the top edge, component
side still up): view "up" (toward the header edge) = board -x, so view "left" = board +y. Hence board x = XA + view y,
board y = YMAX - view x, where XA is the adapter's header edge and YMAX its y-max side edge. The adapter's LEFT end
(pin 1) is its board y-MAX end; the right-hand hole (beside the power pads) is the y-min hole.

A placement entry is as in relayout_placements.py: ref -> (cx, cy, o), (cx, cy) the pad-bbox centre, o = "h" / "h180"
/ "v" / "v180" for a DIP or the KiCad rotation; gen_relayout.place_fp snaps pad 1 onto the 1.27 mm grid of X1's pins.
"""
import math
import relayout_placements as RP
from relayout_placements import row, merge, UBLOCK_BUILT

G = 2.54

# ---------------------------------------------------------------------------------------------------------------------
# the adapter (view coordinates, mm; see above)
HX = dict(
    name="HX-2118P CF-to-IDE",
    w=60.0,                     # along the header edge (view x)
    d=44.0,                     # header edge -> CF slot edge (view y)
    hole_edge=15.3,             # hole centres from the header edge
    hole_side=4.0,              # hole centres from the side edges (4.0 / 56.0 in view x: 52.0 apart, centred)
    hole_pitch=52.0,
    hole_dia=3.3,               # measured ~3.2-3.5 (M3 clearance)
    rows=(4.6, 7.14),           # the header's two pin rows from the header edge (outer, inner) - template figures
    col0=5.87,                  # the pin-1 END column from the LEFT side edge; 20 columns at 2.54 mm, centred
    shroud=(2.67, 1.30, 57.33, 10.44),   # the header's shroud (view x0, y0, x1, y1), the template's
    pwr=(40.0, 11.6, 52.0, 14.2),        # the four power pads: APPROXIMATE box (view), just inboard of the right hole
)
STANDOFF = 15.0             # proposed standoff length (M3 hex, female-female, 5.5 mm across flats), mm
STANDOFF_ALT = 12.0         # the shorter alternative (tighter over socketed DIPs)
HEX_R = 3.2                 # half the across-corners size of a 5.5 mm AF hex standoff (6.35 / 2)
WASHER_R = 3.5              # M3 washer 7 mm OD (bottom side: nut / screw head + washer)
KEEPOUT_D = 7.0             # copper keep-out circle around each hole, all four layers (tracks, vias, planes)
PAD_CLEAR = 4.0             # no pad copper within this radius of a hole centre (the washer + 0.5 mm)
BODY_CLEAR = 3.5            # no part body within this radius of a hole centre (the standoff hex + 0.3 mm)
UNDER_MAX = 11.0            # the tallest part allowed under the adapter (mm above the card): 15 mm standoff - ~2.5 mm
                            # of pin tails under the adapter - margin; sockets + DIPs ~8.5-9.5, disc caps ~8-10
# the ROM keep-clear zone around IC13's pads: both SHORT ends 10 mm (lever it out; a 28-pin ZIF socket, ~50 x 15 mm,
# fits), the long sides 2 mm; no other part in it, and neither it nor the ROM under the adapter, a standoff or the ribbon
ROM = "IC13"
ROM_END = 10.0
ROM_SIDE = 2.0
ROM_ADAPTER_GAP = 3.0       # the ROM's zone this far from the adapter outline, the standoffs and the ribbon zone


def adapter(xa, yc):
    """the adapter in board coordinates for header edge x = xa, centre y = yc (the header, and J2, centred on it)"""
    ymax = yc + HX["w"] / 2
    B = lambda vx, vy: (xa + vy, ymax - vx)
    s = HX["shroud"]
    p = HX["pwr"]
    pins = []
    for k in range(20):
        vx = HX["col0"] + k * G
        pins.append((B(vx, HX["rows"][0]), B(vx, HX["rows"][1])))
    return dict(
        xa=xa, yc=yc, ymax=ymax,
        outline=(xa, ymax - HX["w"], xa + HX["d"], ymax),
        holes=[B(HX["hole_side"], HX["hole_edge"]), B(HX["w"] - HX["hole_side"], HX["hole_edge"])],   # y-max, y-min
        shroud=(xa + s[1], ymax - s[2], xa + s[3], ymax - s[0]),
        pins=pins,                      # per column (outer row, inner row), column 0 = the pin-1 END (y max)
        pin1_end_y=ymax - HX["col0"],
        pwr=(xa + p[1], ymax - p[2], xa + p[3], ymax - p[0]),
        slot_x=xa + HX["d"],
    )


# J2 = Connector_IDC:IDC-Header_2x20_P2.54mm_Vertical at ROTATION 180: pad 1 at (px, py1), the odd pins 1..39 running
# toward -y at x = px, the even pins 2..40 at px - 2.54 (bus side), the shroud's key slot on the odd-row (+x) side, the
# shroud x px-5.83..px+3.29, y py1-53.47..py1+5.21 (courtyard px-6.22..px+3.68, py1-53.86..py1+5.60).
# Why 180: a straight (untwisted) ribbon joins two headers that are oriented alike. The adapter's pin 1 is at its
# board y-MAX end, so J2's pin 1 must be at its y-max end too; with standard 2-row numbering (pin 2 across from pin 1,
# the same handedness on every box header, KiCad's footprint and the IDC plug alike) that puts J2's odd row on +x.
J2_ROT = 180
J2_GAP = 0.8                # J2's courtyard (px + 3.68) to the adapter's header edge, mm


def j2(px, py1):
    return {"J2": (px - G / 2, py1 - 19 * G / 2, J2_ROT)}


# J2 WITH ITS PLUG (coordinator / Ken, 2026-09-24, after the review of the first options): a shrouded header is ~9 mm
# tall and the IDC plug on it another ~9 mm (~18 mm, taller than the 15 mm standoffs), and the plug body is wider than
# the shroud (~1-1.5 mm each side). So the PLUG ENVELOPE (the shroud + 1.5 mm all round, 18 mm tall) stays clear of
# the adapter outline and of every other part's body, and the adapter's header edge stands ~3-5 mm from J2's shroud
# so the ribbon can fold up out of J2's plug and down into the adapter's (on the adapter's header, ~15 + 1.6 + 9 mm up).
# Options a / b were made before this rule (J2_GAP 0.8 mm from J2's courtyard = 1.19 mm from its shroud): the record.
PLUG_SIDE = 1.5             # the IDC plug body past the shroud, each side, mm
PLUG_H = 18.0               # J2 + its plug above the card, mm
J2_SHROUD_GAP = 3.0         # J2's shroud to the adapter's header edge (Ken: ~3-5 mm), options c / d / e
RIBBON = "~5-8 cm"          # the ribbon between the two plugs (see ribbon_length() and the README)


def j2_geom(px, py1, gap=None):
    """J2's geometry for pad 1 at (px, py1); the adapter's header edge xa = J2's courtyard + J2_GAP (a / b) or J2's
    shroud + gap (the plug-envelope options)"""
    sh = (px - 5.83, py1 - 53.47, px + 3.29, py1 + 5.21)
    return dict(px=px, py1=py1, shroud=sh,
                court=(px - 6.22, py1 - 53.86, px + 3.68, py1 + 5.60),
                plug=(sh[0] - PLUG_SIDE, sh[1] - PLUG_SIDE, sh[2] + PLUG_SIDE, sh[3] + PLUG_SIDE),
                xa=px + 3.68 + J2_GAP if gap is None else px + 3.29 + gap, gap=gap,
                yc=py1 - 19 * G / 2)


def ribbon_length(jg, ad, standoff=15.0):
    """the ribbon between the two plugs, mm: straight up out of J2's plug (top at PLUG_H), over, and down into the
    adapter's plug (on the adapter's header: standoff + 1.6 board + 9 header + 9 plug), with a loop ~6 mm above the
    higher plug; the bends as quarter circles. The minimum; a real cable wants ~1-2 cm more to plug in comfortably"""
    top_a = standoff + 1.6 + 9.0 + 9.0
    loop = top_a + 6.0
    dx = (ad["shroud"][0] + ad["shroud"][2]) / 2 - (jg["px"] - G / 2)
    r = min(dx / 2, 6.0)
    return (loop - PLUG_H - r) + (loop - top_a - r) + max(dx - 2 * r, 0) + math.pi * r


def ribbon_zone(jg, ad):
    """the ribbon's footprint over the card: from J2's shroud to the adapter's shroud, the ribbon's width (J2's shroud
    length) - the ribbon arches up out of J2's plug and down into the adapter's; nothing tall under it"""
    return (jg["shroud"][0], jg["shroud"][1], ad["shroud"][2], jg["shroud"][3])


def vcol(ic, x, top, o="v"):
    """a vertical DIP (pins along y), pin 1 top left, its left pin column at x, its top pin at y = top, its cap above
    it (relayout_placements.col)"""
    return RP.col(ic, x, top, o)


# ---------------------------------------------------------------------------------------------------------------------
# the parts every option places alike
C1 = 40.64                                            # column 1 (the bus side): the TMP registers + address buffers
Y = [24.13 + 13.97 * i for i in range(8)]
COL1 = merge(row("IC27", C1, Y[0]), row("IC29", C1, Y[1]), row("IC26", C1, Y[2]), row("IC28", C1, Y[3]),
             row("IC9", C1, Y[4]), row("IC8", C1, Y[5]),
             {"RN5": (C1 + 10.16, 105.41, 0), "RN6": (C1 + 10.16, 110.49, 0)})
FIXED = merge(UBLOCK_BUILT, {"JP1": (25.37, 14.78, 0)},
              {"PWR0": (191.74, 120.19, 180), "LED1": (182.88, 120.19, 180)})     # the LEDs stay (Ken)
CFX = 89.79                  # the CF column: pin-1 column of its horizontal DIPs (their caps 5.08 mm left)
MEMX = 121.92                # the RAM / glue column under and beside the adapter's slot half
# the top-edge column: the block decode (IC7, IC4) beside the U$1 jumpers and IC18, the ROM standing vertical at the
# free top edge (reachable with the card in the cage), a column of vertical glue DIPs between it and the RAMs
TOPX = 157.48
ROMSPEC = {"IC13": (182.88, 72.39, "v"), "C3": (170.18, 60.96, 90)}


def silk(jg, ad, extra=()):
    """board texts (s, x, y, size, angle, justify): the adapter note, PIN 1 at J2, the J3 pins"""
    out = [("PIN 1", jg["px"] + 4.6, jg["py1"] + 0.2, 0.9, 90, "c"),
           ("CF: P8/P9", jg["px"] - 1.27, jg["shroud"][3] + 1.6, 1.0, 0, "c")]
    return out + list(extra)


OPTIONS = {}

# ---------------------------------------------------------------------------------------------------------------------
# a: the adapter CENTRED on the card's y span (over the CF column and the RAMs' left ends); J2 at pin rows x 76.2 / 78.7;
#    the CF column beside J2 under the adapter's header half (IC32 DA latch, IC31 strobes, IC34 data buffer between
#    the standoffs, IC33 / IC30 past J2's pin-1 end); R10-R13, IC14, J3 and C30 at J2's y-min end; RN9 past its pin-1
#    end; RAMs and IC5 / IC15 / IC11 in the column at x 122; ROM at the top edge.
PXA, PY1A = 78.71, 90.98
JA = j2_geom(PXA, PY1A)
ADA = adapter(JA["xa"], JA["yc"])
OPTIONS["a"] = dict(
    title="Adapter centred (y %.1f-%.1f), CF column beside J2, ROM at the top edge" % (ADA["outline"][1], ADA["outline"][3]),
    j2=(PXA, PY1A),
    place=merge(
        COL1, FIXED, j2(PXA, PY1A),
        {"JP2": (68.58, 68.58, 0)},                                       # beside J2 pin 20 (bus side)
        row("IC32", CFX, 50.8), row("IC31", CFX, 64.77), row("IC34", CFX, 78.74),
        row("IC33", CFX, 102.87), row("IC30", CFX, 116.84),
        {"RN9": (69.85, 110.49, 90)},
        {"R10": (69.85, 29.21, 90), "R11": (73.66, 29.21, 90), "R12": (77.47, 29.21, 90), "R13": (81.28, 29.21, 90)},
        row("IC14", 72.39, 16.51),
        {"J3": (93.98, 34.29, 90), "C30": (93.98, 25.4, 0)},
        row("IC1", MEMX, 43.18), row("IC2", MEMX, 64.77),
        row("IC5", MEMX, 86.36), row("IC15", MEMX, 100.33), row("IC11", MEMX, 114.3),
        row("IC7", TOPX, 17.78), row("IC4", TOPX, 31.75),
        ROMSPEC,
        vcol("IC6", 158.75, 46.99), vcol("IC12", 158.75, 69.85), vcol("IC10", 158.75, 92.71),
        row("IC3", 176.53, 106.68),
        {"R14": (167.64, 116.84, 0), "R2": (167.64, 121.92, 0)},
    ),
)

# b: the adapter toward the y = 124 side edge (y %.1f-%.1f); the same columns, the CF rows between and below the
#    standoffs; the space J2 leaves at the y = 10 end takes IC6, IC30 / IC33 and the CF pull-ups R10-R13.
PXB, PY1B = 78.71, 117.65
JB = j2_geom(PXB, PY1B)
ADB = adapter(JB["xa"], JB["yc"])
OPTIONS["b"] = dict(
    title="Adapter toward the y = 124 edge (y %.1f-%.1f), CF column beside J2, ROM at the top edge" % (
        ADB["outline"][1], ADB["outline"][3]),
    j2=(PXB, PY1B),
    place=merge(
        COL1, FIXED, j2(PXB, PY1B),
        {"JP2": (68.58, 90.17, 0)},
        row("IC33", CFX, 77.47), row("IC31", CFX, 91.44), row("IC34", CFX, 105.41),
        row("IC32", CFX, 53.34), row("IC30", CFX, 40.64),
        {"RN9": (68.58, 110.49, 90)},
        {"R10": (69.85, 50.8, 90), "R11": (73.66, 50.8, 90), "R12": (77.47, 50.8, 90), "R13": (81.28, 50.8, 90)},
        row("IC14", 72.39, 16.51), row("IC6", 72.39, 29.21),
        {"J3": (93.98, 60.96, 90), "C30": (113.03, 58.42, 0)},
        row("IC1", MEMX, 43.18), row("IC2", MEMX, 64.77),
        row("IC5", MEMX, 86.36), row("IC15", MEMX, 100.33), row("IC11", MEMX, 114.3),
        row("IC7", TOPX, 17.78), row("IC4", TOPX, 31.75),
        ROMSPEC,
        vcol("IC12", 158.75, 69.85), vcol("IC10", 158.75, 92.71),
        row("IC3", 176.53, 106.68),
        {"R14": (167.64, 116.84, 0), "R2": (167.64, 121.92, 0)},
    ),
)

for _k, _o in OPTIONS.items():
    _jg = j2_geom(*_o["j2"])
    _o["jg"] = _jg
    _o["adapter"] = adapter(_jg["xa"], _jg["yc"])
    _o["silk"] = silk(_jg, _o["adapter"])


# =====================================================================================================================
# c / d / e (Ken, 2026-09-24, later: "I am OK to move the IDE connector and CF card towards the top edge as long as the
# ROM stays uncovered - it might help reduce vias"). Same concept (J2 parallel to X1, just beside the adapter's header
# edge on the bus side, straight ribbon, adapter on two standoffs, slot toward the top edge), but J2 and the adapter go
# AS FAR TOWARD THE TOP EDGE AS THEY CAN, with J2's plug envelope clear of the adapter (J2_SHROUD_GAP): J2's odd row at
# x 144.75 (the last 1.27 mm grid column that keeps the slot edge on the board), the adapter x 151.04-195.04, its CF
# slot edge 0.49 mm inside the top edge (x 195.53). The card then flows as the top-edge board did (43 vias):
# X1 | column 1 (TMP registers, address buffers) | column 2 (glue, IC5) | column 3 (the memories) | J2 | the adapter
# over the CF chips: J2 is no longer a wall between the bus and the memories; only the CF section's own lines (DATA0-7,
# IO-ADDR, strobes, reset, ~15) pass it, round its ends or between its pins. Column 3 closes up by 6.35 mm against the
# top-edge board to leave J2's plug envelope free (its 28-pin bodies end at x 137.1, the envelope starts at 137.4).
# The three differ in where the ROM IC13 goes (it shares 23 bus lines with the RAMs IC1 / IC2):
#   c  ROM horizontal at the TOP EDGE beside the adapter, between it and the LEDs (y = 124 side); J2 mid-card
#   d  ROM in the MEMORY COLUMN with the RAMs, its bottom row (the RAMs right above it, IC15 at the top), below J2's
#      pin-1 end; J2 mid-card
#   e  ROM in the MEMORY COLUMN with the RAMs, its top row (under the U$1 jumpers), above J2's pin-39 end; J2 and the
#      adapter toward the y = 124 side (as far as the LEDs allow), the block decode IC7 / IC4 and the port decode IC30
#      in the top-edge corner beside the jumpers
# (A fourth, the ROM at the top edge in the JP1 corner with the adapter toward the LEDs, routed worst: 113 vias.)
COL2X = 74.93                # column 2 pin-1 column (top-edge board 76.20)
COL3X = 102.87               # column 3 pin-1 column (top-edge board 109.22)
PXT = 144.75                 # J2's odd row: xa = 151.04, slot edge 195.04
COL2 = merge(row("IC14", COL2X, Y[0]), row("IC6", COL2X, Y[1]), row("IC5", COL2X, Y[2]), row("IC11", COL2X, Y[3]),
             row("IC12", COL2X, Y[4]), row("IC10", COL2X, Y[5]), row("IC3", COL2X, Y[6]))
LEDR = {"R14": (167.64, 116.84, 0), "R2": (167.64, 121.92, 0)}


def cf_under(ad, ic4=True, ic33="h1"):
    """the CF section under the adapter (sockets + disc caps + axial resistors only): the header half between the two
    standoffs holds IC32 (DA latch, near J2 pins 33-36), IC31 (strobes, near pins 23 / 25) and IC34 (data buffer,
    beside D0-D7 = pins 3-17, the pin-1 end); the slot half holds IC4 beside the y-min standoff H2 (ic4), IC33 (reset /
    enable / ACT) beside the y-max one H1 (ic33 "h1") or H2 ("h2"), and between them the pull-ups R10-R13 and RN9"""
    xa, y0 = ad["xa"], ad["outline"][1]
    cfx = xa + 6.98                     # header half: caps at xa + 1.90
    slot = xa + 26.03                   # slot half: caps at xa + 20.95, 5.15 mm from the standoff centre line
    out = merge(row("IC32", cfx, y0 + 17.78), row("IC31", cfx, y0 + 31.75), row("IC34", cfx, y0 + 45.72),
                row("IC33", slot, y0 + (55.88 if ic33 == "h1" else 6.35)),
                {"R%d" % (10 + k): (xa + 28.57 + 3.81 * k, y0 + 19.05, 90) for k in range(4)},
                {"RN9": (xa + 41.27, y0 + 38.1, 90)})
    if ic4:
        out.update(row("IC4", slot, y0 + 6.35))
    return out


def j3_c30(ad, c30):
    """J3 just outside the adapter's y-min edge beside the power pads (as in a), C30 (10 uF, tall) at c30"""
    return {"J3": (ad["xa"] + 10.79, ad["outline"][1] - 2.56, 90), "C30": c30}


def _new(k, py1, title, place):
    jg = j2_geom(PXT, py1, J2_SHROUD_GAP)
    ad = adapter(jg["xa"], jg["yc"])
    OPTIONS[k] = dict(title=title % (ad["outline"][0], ad["outline"][2]), j2=(PXT, py1), gap=J2_SHROUD_GAP,
                      place=merge(COL1, FIXED, j2(PXT, py1), COL2, LEDR, place(ad)))


_new("c", 83.36, "J2 / adapter at the top edge (x %.1f-%.1f), ROM beside the adapter at the top edge (y = 124 side)",
     lambda ad: merge(
         row("IC1", COL3X, 43.18), row("IC2", COL3X, 64.77), row("IC15", COL3X, 86.36),
         row("IC30", COL3X, 104.14),                                         # CF port decode, on X1's side of J2
         {"IC13": (158.75 + 16.51, 104.14, "h"), "C3": (146.05, 104.14, 90)},  # ROM: zone x 148-202, y 93-115
         row("IC7", 153.67, 16.51), j3_c30(ad, (175.26, 25.4, 0)), cf_under(ad),
         {"JP2": (143.51, 119.38, 0)}))                                      # past J2's pin-1 end, out of the way
_new("d", 83.36, "J2 / adapter at the top edge (x %.1f-%.1f), ROM in the memory column (bottom row) with the RAMs",
     lambda ad: merge(
         row("IC15", COL3X, 43.18), row("IC1", COL3X, 64.77), row("IC2", COL3X, 83.82),   # the RAMs next to the ROM
         {"IC13": (COL3X + 16.51, 104.14, "h"), "C3": (110.49, 118.11, 0)},  # ROM: zone x 92-147, y 93-115
         row("IC30", 157.48, 101.6),                                         # past J2's pin-1 end, below the adapter
         row("IC7", 153.67, 16.51), j3_c30(ad, (175.26, 25.4, 0)), cf_under(ad),
         {"JP2": (190.5, 111.76, 0)}))
# d: IC5 (the memory data buffer) one row nearer the memories and the ROM (column 2, fifth row; IC12 takes its place),
# IC2's cap C2 steps down to clear it. The first placement (IC1 / IC2 / IC15 / ROM top to bottom, IC5 in the third
# row) never completed: BDATA5 / BDATA7 were left at the RAMs in all of 17 route orders
OPTIONS["d"]["place"].update(merge(row("IC12", COL2X, Y[2]), row("IC5", COL2X, Y[4])))
OPTIONS["d"]["place"]["C2"] = (97.79, 88.9, 90)
_new("e", 110.03, "J2 / adapter at the top edge (x %.1f-%.1f) toward the LEDs, ROM in the memory column (top row)",
     lambda ad: merge(
         {"IC13": (COL3X + 16.51, 42.72, "h"), "C3": (97.79, 57.79, 90)},   # ROM: zone x 92-147, y 32-54
         row("IC1", COL3X, 64.77), row("IC2", COL3X, 86.36), row("IC15", COL3X, 104.14),
         row("IC7", 162.56, 17.78), row("IC4", 162.56, 31.75), row("IC30", 162.56, 44.45),
         j3_c30(ad, (187.96, 52.07, 0)), cf_under(ad, ic4=False),
         {"JP2": (143.51, 120.02, 90)}))
# e: column 2 takes IC5 (20 pins) at its sixth row, clear of the ROM zone; IC2's cap C2 steps up to clear it
OPTIONS["e"]["place"].update(merge(row("IC12", COL2X, Y[2]), row("IC10", COL2X, Y[4]), row("IC5", COL2X, Y[5])))
OPTIONS["e"]["place"].update({"C2": (97.79, 83.82, 90), "R14": (158.75, 118.11, 0), "R2": (158.75, 121.92, 0)})

for _k, _o in OPTIONS.items():
    _jg = j2_geom(*_o["j2"], _o.get("gap"))
    _o["jg"] = _jg
    _o["adapter"] = adapter(_jg["xa"], _jg["yc"])
    _o["silk"] = silk(_jg, _o["adapter"])
