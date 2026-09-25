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


def j2_geom(px, py1):
    return dict(px=px, py1=py1, shroud=(px - 5.83, py1 - 53.47, px + 3.29, py1 + 5.21),
                court=(px - 6.22, py1 - 53.86, px + 3.68, py1 + 5.60), xa=px + 3.68 + J2_GAP,
                yc=py1 - 19 * G / 2)


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
