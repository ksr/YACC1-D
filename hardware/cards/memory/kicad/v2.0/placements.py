"""placements.py - the placement options of the memory card v2.0 board (2026-09-24). Plain data, read by gen_mem_v2.py.

Coordinates are the v1.3 board's (mm, y down; outline x 17.72..195.55, y 10.00..124.02, bus connector X1 on the left
edge). Seen in the machine the card stands on X1: board +x is UP, so the x = 195.55 edge is the card's free top edge,
and y = 10 / y = 124 are its two free side edges.

  FAB_MOVES  applied in EVERY option: the TMP registers IC26-IC29 and the data-bus pull-downs RN5/RN6 go where the
             FABRICATED card has them. The converted v1.3 board (like the tree's Eagle .brd, an earlier save of the
             design) keeps these six parts OUTSIDE the board outline, unrouted; the 2025 gerbers and pick-and-place file
             (../../eagle/v1.3/fab/Memory V1_2025-06-27.zip, "Memory V1.3 v4") put them on the board: ref -> (dx, dy)
             from the v1.3 KiCad position = the fab position (Eagle x + 17.72, 124.02 - Eagle y).
  IC15_SPOT  the fabricated card also has an IC15 74ALS11N at Eagle (151.13, 53.34) -> KiCad (168.85, 70.68), which no
             schematic in the tree has (README.md): every option keeps its DIL14 footprint area free.
  moves      v1.3 parts that move in this option: ref -> (dx, dy[, rotation]) (their v1.3 copper that ended on a moved
             pad is dropped; build.sh then trims whatever that leaves dangling or in conflict)
  place      every CF part: ref -> (x, y, rotation) of the footprint origin = pad 1 (KiCad THT libraries).
             DIPs at rotation 90: pin 1 bottom left, pins to the right, the other row 7.62 mm above (the v1.3 ICs'
             orientation). J2 (IDC 2x20 shrouded) at rotation 0: pin 1 top, odd pins down the left column, even pins
             2.54 mm to the right; 180: pin 1 bottom, odd pins up the right column, even pins 2.54 mm to the left;
             270: pin 1 right, odd pins to the left, even row 2.54 mm below.
"""

# ---- the fabricated card's positions for the six parts the v1.3 conversion keeps off the board --------------------
FAB_MOVES = {
    "IC26": (147.32, -111.76), "IC27": (147.32, -110.49), "IC28": (147.32, -109.22), "IC29": (147.32, -107.80),
    "RN5": (29.21, -69.85), "RN6": (57.15, -74.93),
}
IC15_SPOT = (160.2, 66.0, 177.5, 75.4)          # x0, y0, x1, y1: DIL14 pads 161.23..176.47 x 66.87..74.49 + margin

# ---- common pieces --------------------------------------------------------------------------------------------------
# the three empty v1.3 IC slots below IC15, right of the pre-placed caps C20/C21/C22 (x 156.18, y 84.62/98.59/111.30).
# Pin 1 at x 159.1: the v1.3 DATA0 track (B.Cu, x 160.30, y 75.4-101.5) then runs between pins 1 and 2 with clearance,
# and a DIP20 ends at x 183.5, clear of an IDE header at the x = 195.55 edge.
ROWX = 159.1
SLOTS = {
    "IC34": (ROWX, 84.62 + 3.81, 90),           # 74LS245 P9 data buffer (row of C20)
    "IC32": (ROWX, 98.59 + 3.81, 90),           # 74LS175 P8 latch (row of C21)
    "IC33": (ROWX, 112.59 + 3.81, 90),          # 74LS08 (row of C22, 1.3 mm lower: room for R12/R13 above it)
    "C29": (162.0, 78.0, 0),                    # IC34 decoupling, above it (clear of the IC15 spot)
    "C27": (182.8, 101.1, 90),                  # IC32 decoupling, at its right end
    "C28": (180.5, 114.8, 90),                  # IC33 decoupling, at its right end
    "R10": (161.5, 91.6, 0), "R11": (173.8, 91.6, 0),     # IORDY / -PDIAG pull-ups, between IC34 and IC32
    "R12": (161.5, 105.3, 0), "R13": (173.8, 105.3, 0),   # -DASP pull-up / -DMACK high, between IC32 and IC33
}
# the band under the ROM (IC13 ends at y 102.4), right of IC9; pads clear of the v1.3 BADDR3-5 / DATA1 tracks
# at y 102.7-104.0
BOTTOM_ICS = {
    "IC30": (97.5, 113.0, 90),                  # 74LS138 port decode
    "C25": (119.5, 111.5, 90),
    "IC31": (132.0, 113.0, 90),                 # 74LS32 strobe gating (right of C23)
    "C26": (151.5, 111.5, 90),
}
SILK_TITLE = "YACC1 MEMORY BOARD V2.0"

OPTIONS = {
    # ------------------------------------------------------------------------------------------------------------------
    "a": dict(
        title="IDE header at the top edge, beside the TMP registers; CF chips in the three empty slots + under the ROM",
        moves={},
        place={
            "J2": (191.79, 64.76, 180),         # pin 1 at the BOTTOM right, pins upwards, even row inboard: the CF
                                                #   data pins (3-17) at the lower end, nearest IC34; body 0.5 mm from
                                                #   the x = 195.55 edge
            **SLOTS, **BOTTOM_ICS,
            "RN9": (97.0, 119.0, 0),            # CF D0-7 pull-ups, second line under the ROM band
            "J3": (132.0, 119.5, 90), "C30": (145.0, 119.5, 0),   # adapter power + bulk cap
            "JP2": (190.5, 80.0, 0),            # below the keep-low zone
            "R14": (190.5, 99.0, 90), "LED1": (189.3, 106.5, 0),  # ACT above PWR0, in the card's LED corner
        },
        text_moves={},
        silk=[("CF: P8/P9", 186.0, 72.6, 1.0, 0), ("ACT", 185.6, 106.5, 1.0, 90)],
    ),
    # ------------------------------------------------------------------------------------------------------------------
    "b": dict(
        title="IDE header along the y = 124 side edge under the ROM; C23 moves up; small parts in the top-edge strip",
        moves={"C23": (0.0, -7.5)},
        place={
            "J2": (148.26, 117.7, 270),         # pin 1 at the RIGHT end, pins leftwards, even row at the edge side:
                                                #   the CF data pins (3-17) at the right, nearest IC34
            **SLOTS,
            "IC30": (97.5, 112.7, 90), "C25": (119.5, 111.2, 90),     # between the BADDR tracks and J2
            "IC31": (132.0, 112.7, 90), "C26": (151.5, 111.2, 90),
            "JP2": (163.0, 119.5, 90),          # beyond the keep-low zone, right of J2's end
            "RN9": (190.5, 34.0, 90),           # the top-edge strip (x 186-195), top to bottom
            "J3": (190.5, 40.0, 0), "C30": (189.5, 55.0, 0),
            "R14": (190.5, 75.0, 90), "LED1": (189.3, 106.5, 0),
        },
        text_moves={},
        silk=[("CF: P8/P9", 92.4, 119.0, 1.0, 90), ("ACT", 185.6, 106.5, 1.0, 90)],
    ),
    # ------------------------------------------------------------------------------------------------------------------
    "c": dict(
        title="IDE header at the top edge, lower half, level with the CF chips; small CF parts in the top corner",
        moves={},
        place={
            "J2": (189.25, 56.0, 0),            # pins 1..40 downwards: CF data pins (3-17) just above IC34, DA0-2
                                                #   (33/35/36) level with IC32; the keep-low zone ends 0.6 mm short
                                                #   of PWR0
            **SLOTS, **BOTTOM_ICS,
            "RN9": (97.0, 119.0, 0),
            "J3": (132.0, 119.5, 90), "C30": (145.0, 119.5, 0),
            "LED1": (189.3, 15.0, 0),           # ACT in the top corner, above the keep-low zone
            "R14": (190.5, 31.0, 90),
            "JP2": (190.5, 35.0, 0),
        },
        text_moves={},
        silk=[("CF: P8/P9", 186.0, 112.5, 1.0, 0), ("ACT", 186.3, 15.0, 1.0, 90)],
    ),
}
