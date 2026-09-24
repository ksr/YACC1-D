"""relayout_placements.py - the RE-LAYOUT placement options of the memory card v2.0 (2026-09-24). Plain data + plain
geometry (no KiCad import): read by gen_relayout.py, which builds one board per option.

Ken's decision (2026-09-24): lay out the whole card again with the CF section designed in. The circuit stays the v2.0
netlist exactly (the built card v1.3 incl. IC15 + the CF section); the built card's placement and copper are discarded.
Kept from the built card: the board outline (177.8 x 114.0 mm), the bus connector X1 (position, orientation, its two
mounting holes) - the card plugs into the same backplane - and the 4-layer stack-up with the In1 GND / In2 VCC planes.

Coordinates are the built board's (mm, y down; outline x 17.72..195.55, y 10.00..124.02; X1 on the x = 17.7 edge). The
card stands on X1 in the cage, so board +x is UP: x = 195.55 is the card's FREE TOP EDGE (J2 goes there), y = 10 and
y = 124 are its two free side edges.

A placement entry is  ref -> (cx, cy, o):
  (cx, cy)  the centre of the part's PAD bounding box (not the footprint origin, which differs between the Eagle and
            the KiCad libraries); gen_relayout.py then snaps pad 1 onto the 1.27 mm grid of the bus connector's pins
            (X1 A1 = 22.83, 106.22), so every pad of the card lies on one 1.27 mm grid.
  o         for a DIP: "h" = horizontal, pin 1 bottom left (the built card's orientation), "h180" = pin 1 top right,
            "v" = vertical, pin 1 top left, "v180" = pin 1 bottom right; for any other part the KiCad rotation in
            degrees of its footprint as drawn in its library.
"""
import math

GRID = 1.27
GRID_ORIGIN = (22.83, 106.22)                 # X1 pin A1: X1's pins are on this 1.27 mm grid
EDGE = (17.722, 10.0, 195.552, 124.02)
SPAN = {14: 15.24, 16: 17.78, 20: 22.86, 28: 33.02}   # DIP pad-row length (pin 1 to pin n/2)
DIP_ROT = {"h": 0, "h180": 180, "v": 270, "v180": 90}  # Eagle DIL library; the KiCad DIP library is +90

# the TAODAN CF-IDE40 plugged straight onto J2 (gen_mem_v2.py has the same figures)
TAODAN_LEN = 70.0            # adapter board along the header axis
LOW_BEYOND = 12.0            # keep-low zone past each end of the 50.8 mm pin row (nothing over ~8 mm)
LOW_SIDE = 7.0               # keep-low half-width either side of the header centre line
# J2 = Connector_IDC:IDC-Header_2x20_P2.54mm_Vertical at rotation 0: pad 1 = origin, odd pins down the column at x0
# (inboard: almost every IDE signal is on an odd pin), even pins 2.54 mm outboard, shroud to x0 + 5.72; with the odd
# column at x = 189.23 the shroud ends 0.6 mm inside the top edge.
J2_X = 189.23

# the built card's 100 nF caps and their ICs, and C25-C29 (the CF section's); C20-C23 (the built card's caps with no
# IC beside them, removed from v2.0 on 2026-09-24) are SPARE_A/B/C below
CAP_OF = {"IC1": "C1", "IC2": "C2", "IC13": "C3", "IC9": "C4", "IC8": "C5", "IC5": "C6", "IC4": "C7", "IC7": "C8",
          "IC10": "C9", "IC6": "C10", "IC11": "C11", "IC12": "C12", "IC14": "C13", "IC26": "C14", "IC27": "C15",
          "IC28": "C16", "IC29": "C17", "IC3": "C18", "IC15": "C19", "IC18": "C24", "IC30": "C25", "IC31": "C26",
          "IC32": "C27", "IC33": "C28", "IC34": "C29"}
PINS = {"IC1": 28, "IC2": 28, "IC13": 28, "IC5": 20, "IC8": 20, "IC9": 20, "IC26": 20, "IC27": 20, "IC28": 20,
        "IC29": 20, "IC34": 20, "IC7": 16, "IC11": 16, "IC30": 16, "IC32": 16, "IC3": 14, "IC4": 14, "IC6": 14,
        "IC10": 14, "IC12": 14, "IC14": 14, "IC15": 14, "IC18": 14, "IC31": 14, "IC33": 14}


def row(ic, left, y, o="h"):
    """a horizontal DIP whose pin-1 column (o = "h") or pin-n column ("h180") is at x = left, centre row y, plus its
    100 nF cap standing just left of it (the built card's arrangement: the cap beside pin 1 / VCC)"""
    s = SPAN[PINS[ic]]
    out = {ic: (left + s / 2, y, o)}
    out[CAP_OF[ic]] = (left - 5.08, y, 90)
    return out


def col(ic, x, top, o="v"):
    """a vertical DIP, pin 1 top left (o = "v"), its left pin column at x, its top pin at y = top, the cap above it"""
    s = SPAN[PINS[ic]]
    out = {ic: (x + 3.81, top + s / 2, o)}
    out[CAP_OF[ic]] = (x + 3.81, top - 4.445, 0)
    return out


def merge(*ds):
    out = {}
    for d in ds:
        for k, v in d.items():
            assert k not in out, "placed twice: %s" % k
            out[k] = v
    return out


# the block-map jumper group as the built card has it (user-facing; U$1 at the y = 10 side edge): RN7 / U$1 / RN8,
# the ROM-row NAND IC18 and its cap, pads exactly where the built card has them
UBLOCK_BUILT = {"RN7": (110.46, 13.51, 180), "U$1": (111.73, 21.13, 0), "RN8": (110.46, 30.02, 0),
                "IC18": (137.13, 18.59, "h"), "C24": (125.73, 18.59, 90)}


def labels(j2_pin1_y, pwr, act, jp2, j3, side="left"):
    """the silkscreen labels of the user-facing parts: "CF: P8/P9" just past the far end of J2's shroud, PWR / ACT
    beside the two LEDs (side "left" of them, "over" = smaller y, "under" = larger y), the IDE pin-20 jumper JP2 and
    the adapter power header J3 (pin 1 first). Texts: (s, x, y, size, angle, justify l/c/r)"""
    last = j2_pin1_y + 19 * 2.54
    out = [("CF: P8/P9", J2_X, last + 9.0, 1.2, 0, "c")]
    for s, (x, y) in (("PWR", pwr), ("ACT", act)):
        out.append({"left": (s, x - 4.0, y, 1.0, 0, "r"), "over": (s, x, y - 4.4, 1.0, 0, "c"),
                    "under": (s, x, y + 4.4, 1.0, 0, "c")}[side])
    out.append(("PIN20 +5V", jp2[0] - 2.2, jp2[1] + 1.27, 0.8, 0, "r"))
    out.append(("+5V G G nc", j3[0] - 2.2, j3[1], 0.8, 0, "r"))
    return out


def shift(d, dx, dy):
    return {k: (v[0] + dx, v[1] + dy, v[2]) for k, v in d.items()}


def j2(pin1_y):
    """J2 on the free top edge, rotation 0: its pad-bbox centre for pad 1 at (J2_X, pin1_y)"""
    return {"J2": (J2_X + 1.27, pin1_y + 19 * 1.27, 0)}


# C20-C23: the built card has these four 100 nF caps with no IC beside them (C20-C22 in a column below C19, C23 under
# the ROM); the re-layout options kept them as plane-to-plane decoupling spread over the board: C20/C21 at the bus
# connector's two power groups (X1 A1-C2 / A31-C32), C22/C23 at the far end of the planes. REMOVED from the circuit
# afterwards (Ken, 2026-09-24: mem_v2_netlist.REMOVED): the option boards and trial routes are the review record from
# before and keep them (so these positions stay); finish_v2.py make takes them off the final board.
SPARE_A = {"C20": (35.56, 117.47, 90), "C21": (35.56, 16.51, 90), "C22": (179.07, 121.92, 0), "C23": (146.05, 121.29, 0)}
SPARE_B = {"C20": (35.56, 117.47, 90), "C21": (35.56, 16.51, 90), "C22": (179.07, 13.97, 0), "C23": (146.05, 121.29, 0)}
SPARE_C = {"C20": (35.56, 117.47, 90), "C21": (35.56, 16.51, 90), "C22": (146.05, 121.29, 0), "C23": (177.8, 13.97, 0)}

# ---------------------------------------------------------------------------------------------------------------------
OPTIONS = {}

# A: the built card's topology, re-flowed: bus-side column (buffers + strobes), decode column, memory column, and a
#    right-hand column with the TMP registers above and the CF chips below; J2 on the top edge, lower half; PWR/ACT
#    LEDs, JP2, J3 in the top-edge corner at y = 10 (clear of the adapter overhang).
C1, C2, C3, C4 = 40.64, 76.2, 109.22, 153.67
Y = [24.13 + 13.97 * i for i in range(8)]             # 24.13 38.10 52.07 66.04 80.01 93.98 107.95 (121.92)
OPTIONS["a"] = dict(
    title="Built topology re-flowed: TMP above the CF chips in the right column, J2 lower half of the top edge",
    place=merge(
        row("IC14", C1, Y[0]), row("IC6", C1, Y[1]), row("IC5", C1, Y[2]), row("IC9", C1, Y[3]),
        row("IC3", C1, Y[4]), row("IC8", C1, Y[5]),
        {"RN5": (C1 + 10.16, 105.41, 0), "RN6": (C1 + 10.16, 110.49, 0)},
        row("IC7", C2, Y[0]), row("IC4", C2, Y[1]), row("IC15", C2, Y[2]), row("IC11", C2, Y[3]),
        row("IC12", C2, Y[4]), row("IC10", C2, Y[5]), row("IC30", C2, Y[6]),
        UBLOCK_BUILT,
        row("IC1", C3, 44.45), row("IC2", C3, 67.31), row("IC13", C3, 90.17), row("IC31", C3, Y[6]),
        row("IC26", C4, 17.78), row("IC27", C4, 31.75), row("IC28", C4, 45.72), row("IC29", C4, 59.69),
        row("IC34", C4, 73.66), row("IC32", C4, 87.63), row("IC33", C4, 101.6),
        {"R10": (C4 + 5.08, 113.03, 0), "R11": (C4 + 17.78, 113.03, 0),
         "R12": (C4 + 5.08, 118.11, 0), "R13": (C4 + 17.78, 118.11, 0)},
        {"RN9": (181.61, 78.74, 90)},
        j2(64.77),
        {"PWR0": (191.77, 15.24, 0), "R2": (180.34, 19.05, 90),
         "LED1": (191.77, 24.13, 0), "R14": (184.15, 19.05, 90),
         "JP2": (191.77, 33.02, 0), "J3": (191.77, 41.91, 0), "C30": (182.88, 48.26, 0),
         **SPARE_A},
        {"JP1": (25.37, 14.78, 0)},
    ),
    silk=labels(64.77, (191.77, 15.24), (191.77, 24.13), (191.77, 33.02), (191.77, 41.91), side="under"),
)

# B: the TMP registers right at the bus connector (they use nothing but the data bus and four strobes, which all enter
#    at X1's upper half), the address buffers below them; strobes/data buffer/FORCE-ROM glue in column 2; memories in
#    column 3 under the block-map jumpers; the right-hand column is the CF section (+ the two block-decode chips IC7 /
#    IC4 at its top, beside IC18 and the jumpers); J2 centred on the top edge; PWR LED where the built card has it.
YB = [43.18, 64.77, 86.36]                             # memory rows, 21.59 mm pitch
OPTIONS["b"] = dict(
    title="TMP registers at the bus connector; right-hand column = CF section; J2 centred on the top edge",
    place=merge(
        row("IC27", C1, Y[0]), row("IC29", C1, Y[1]), row("IC26", C1, Y[2]), row("IC28", C1, Y[3]),
        row("IC9", C1, Y[4]), row("IC8", C1, Y[5]),
        {"RN5": (C1 + 10.16, 105.41, 0), "RN6": (C1 + 10.16, 110.49, 0)},
        row("IC14", C2, Y[0]), row("IC6", C2, Y[1]), row("IC5", C2, Y[2]), row("IC11", C2, Y[3]),
        row("IC12", C2, Y[4]), row("IC10", C2, Y[5]), row("IC3", C2, Y[6]),
        UBLOCK_BUILT,
        row("IC1", C3, YB[0]), row("IC2", C3, YB[1]), row("IC13", C3, YB[2]), row("IC15", C3, 104.14),
        row("IC7", C4, 17.78), row("IC4", C4, 31.75), row("IC33", C4, 45.72), row("IC34", C4, 59.69),
        row("IC31", C4, 73.66), row("IC32", C4, 87.63), row("IC30", C4, 101.6),
        {"RN9": (181.61, 62.23, 90),
         "R10": (176.53, 93.98, 90), "R11": (180.34, 93.98, 90), "R12": (176.53, 107.95, 90), "R13": (180.34, 107.95, 90)},
        j2(50.8),
        {"PWR0": (191.74, 120.19, 180), "LED1": (182.88, 120.19, 180),
         "R2": (167.64, 121.92, 0), "R14": (167.64, 116.84, 0),
         "JP2": (191.77, 15.24, 0), "J3": (191.77, 27.94, 0), "C30": (185.42, 22.86, 0),
         **SPARE_B},
        {"JP1": (25.37, 14.78, 0)},
    ),
    silk=labels(50.8, (191.74, 120.19), (182.88, 120.19), (191.77, 15.24), (191.77, 27.94), side="over"),
)

# C: option A's columns 1-3; the right-hand column turned round: the CF chips at the top, the TMP registers below; J2
#    on the top edge, upper half; the PWR LED stays where the built card has it (y = 124 corner), ACT beside it.
OPTIONS["c"] = dict(
    title="Option A with the right-hand column turned round: CF above the TMP registers, J2 upper half of the top edge",
    place=merge(
        {k: v for k, v in OPTIONS["a"]["place"].items()
         if k in ("IC14", "C13", "IC6", "C10", "IC5", "C6", "IC9", "C4", "IC3", "C18", "IC8", "C5", "RN5", "RN6",
                  "IC7", "C8", "IC4", "C7", "IC15", "C19", "IC11", "C11", "IC12", "C12", "IC10", "C9", "IC30", "C25",
                  "RN7", "U$1", "RN8", "IC18", "C24", "IC1", "C1", "IC2", "C2", "IC13", "C3", "IC31", "C26", "JP1")},
        row("IC33", C4, Y[0] - 6.35), row("IC34", C4, Y[1] - 6.35), row("IC32", C4, Y[2] - 6.35),
        row("IC26", C4, Y[3] - 6.35), row("IC28", C4, Y[4] - 6.35), row("IC27", C4, Y[5] - 6.35),
        row("IC29", C4, Y[6] - 6.35),
        {"RN9": (181.61, 33.02, 90),
         "R10": (180.34, 52.07, 90), "R11": (180.34, 64.77, 90), "R12": (180.34, 77.47, 90), "R13": (180.34, 90.17, 90)},
        j2(21.59),
        {"PWR0": (191.74, 120.19, 180), "R2": (177.77, 120.19, 180),
         "LED1": (191.74, 111.76, 180), "R14": (177.77, 113.03, 180),
         "JP2": (191.77, 86.36, 0), "J3": (191.77, 95.25, 0), "C30": (185.42, 104.14, 0),
         **SPARE_C},
    ),
    silk=labels(21.59, (191.74, 120.19), (191.74, 111.76), (191.77, 86.36), (191.77, 95.25)),
)
