"""placements.py - the placement options of the I/O card v2.0 board (2026-09-23). Plain data, read by gen_io_v2.py.

Coordinates are the v1.1 board's (mm, y down; outline x 17.75..195.53, y 10.03..124.00, bus connector X1 on the left
edge). Seen in the machine the card stands on X1: board +x is UP (logic, then the switch row, the LCD, the LED row at
the top) and board y = 10 is the card's left side as you face it.

  moves   v1.1 parts that move: ref -> (dx, dy)  (their v1.1 copper that ended on a moved pad is dropped; build.sh then
          trims whatever that leaves dangling or in conflict)
  place   every CF part: ref -> (x, y, rotation) of the footprint origin = pad 1 (KiCad THT libraries). Rotation 0: DIPs
          and the IDE header run pin 1 at the top, downwards (+y); 90: pin 1 bottom left, pins to the right (the v1.1
          ICs' orientation); 270 on the IDE header: pin 1 at the right, odd pins leftwards, even row below
  adapter (x, y, w, h, edge): the CF-to-IDE adapter's outline as seen from above, and the side its IDE connector is on
"""

# the v1.1 parts that can take a small move
SWITCHES = ["S%d" % i for i in range(8)] + ["IN0", "INPUT0"]
TOP_ROW = ["IC3", "C16", "IC10", "C15"]                 # the 74LS244 and the control latch, above the UART

# common to every option
ACT_LED = {                                             # ACT beside OUT and PWR, in the card's LED column
    "R15": (172.0, 113.2, 0),
    "LED1": (185.4, 113.2, 0),
}
SILK_COMMON = [
    # (text, x, y, size, angle)
    ("HL STRAP: P0-P7 ONLY", 29.5, 105.4, 1.0, 0),       # above IO-ADDR-HL0 ("L" end = P0-P7: jumpers 3-5, 4-6)
    ("(CF on P4/P5)", 29.5, 107.1, 1.0, 0),
    ("<- NOT P4/P5", 41.5, 118.9, 0.9, 0),              # right of IO-ADDR0 (pins 5-8 = P5, P4)
    ("NOT P4/P5", 75.2, 118.9, 0.9, 0),                 # left of DATA-ADDR0
    ("ACT", 191.9, 113.2, 1.2, 90),
]

OPTIONS = {
    # ------------------------------------------------------------------------------------------------------------------
    "a": dict(
        title="IDE header in the band between the logic and the switch row; glue chips along the top edge",
        moves={**{r: (3.8, 0) for r in SWITCHES}, **{r: (0, 2.54) for r in TOP_ROW}},
        place={
            "J2": (110.9, 18.0, 0),                     # pins 1..40 downwards, data pins at the top end
            "RN3": (105.4, 16.2, 270),                  # CF D0-7 pull-ups beside the data pins
            # top strip (IC3/IC10 moved down one pitch): C20 IC14 | C18 IC12 | C21 IC15, bottom row y = 19.3
            "C20": (32.0, 11.68, 270), "IC14": (35.36, 19.3, 90),
            "C18": (53.96, 11.68, 270), "IC12": (57.26, 19.3, 90),
            "C21": (75.86, 11.68, 270), "IC15": (79.16, 19.3, 90),
            # lower band (under the IDE header)
            "IC13": (104.4, 76.0, 0), "C19": (115.5, 76.0, 270),
            "R11": (102.0, 99.0, 0), "R12": (102.0, 102.1, 0), "R13": (102.0, 105.2, 0), "R14": (102.0, 108.3, 0),
            "JP2": (115.6, 99.0, 0),
            "J3": (101.8, 113.0, 90), "C22": (113.5, 113.0, 0),
            **ACT_LED,
        },
        adapter=(57.0, 12.0, 43.0, 60.0, "right"),
        text_moves={"YACC1 IO V2.0": (30.5, 96.5)},
        silk=SILK_COMMON,
    ),
    # ------------------------------------------------------------------------------------------------------------------
    # CHOSEN by Ken 2026-09-23. Kept as reviewed; the one later change (JP2 moved clear of the adapter overhang) is
    # route_v2.py FINAL_MOVES, applied when the routed board io-v2.0.kicad_pcb is made from this option.
    "b": dict(
        title="IDE header along the top edge; the four CF chips in a column between the logic and the switch row",
        moves={**{r: (3.8, 0) for r in SWITCHES}, **{r: (0, 2.54) for r in TOP_ROW}},
        place={
            "J2": (101.0, 14.5, 270),                   # pin 1 at the right end, odd row nearest the edge
            "RN3": (21.5, 14.3, 0),                     # top left corner, clear of X1's body
            "JP2": (40.5, 17.8, 90),
            # the column (x 107..117 once the switches moved up), top to bottom
            "IC15": (108.3, 14.0, 0), "C21": (108.8, 40.2, 0),
            "IC13": (108.3, 44.0, 0), "C19": (108.8, 65.0, 0),
            "IC12": (108.3, 68.2, 0), "C18": (108.8, 86.6, 0),
            "IC14": (108.3, 89.8, 0), "C20": (108.8, 108.3, 0),
            # left, under the crystal
            "R11": (31.0, 53.0, 0), "R12": (31.0, 56.1, 0), "R13": (31.0, 59.2, 0), "R14": (31.0, 62.3, 0),
            "J3": (31.0, 67.5, 90), "C22": (42.8, 67.5, 0),
            **ACT_LED,
        },
        adapter=(47.0, 12.0, 60.0, 43.0, "top"),
        text_moves={"YACC1 IO V2.0": (30.5, 96.5)},
        silk=SILK_COMMON + [("CF IDE -> adapter", 49.0, 22.3, 1.0, 0)],
    ),
    # ------------------------------------------------------------------------------------------------------------------
    "c": dict(
        title="switches, ICs and the LCD stay: only the MAX232/UART caps and JP1 move; CF chips in the free pockets",
        moves={
            "C4": (0, 26.16), "C1": (6.39, 19.81), "C2": (0, 19.97), "C3": (6.39, 13.61),   # MAX232 caps: 2x2 below
            "C7": (-55.04, -2.5),                                                            # IC1's cap: by its VCC pin
            "JP1": (0, -7.3),                                                                # null-modem jumper: up
        },
        place={
            "J2": (107.43, 18.0, 0),                    # the band, freed of the MAX232 caps
            "RN3": (102.0, 20.0, 270),
            "IC15": (104.4, 90.6, 0), "C21": (104.6, 87.5, 0),
            "IC13": (33.5, 95.3, 90), "C19": (33.0, 97.9, 0),
            "IC12": (129.4, 108.3, 90), "C18": (130.0, 96.5, 0),
            "IC14": (148.6, 108.3, 90), "C20": (157.5, 96.5, 0),
            "R11": (31.0, 52.5, 0), "R12": (31.0, 55.6, 0), "R13": (31.0, 58.7, 0), "R14": (31.0, 61.8, 0),
            "JP2": (45.0, 52.5, 0),
            "J3": (31.0, 66.5, 90), "C22": (42.8, 67.0, 0),
            **ACT_LED,
        },
        adapter=(57.0, 16.0, 43.0, 60.0, "right"),
        text_moves={},
        silk=SILK_COMMON,
    ),
}
