#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""v20_timing.py - the video card V2.0's direct mode (GFX-ON = 0: the CPU owns the graphics RAM) against the machine's
microcode (2026-10-22). No hardware; part of `make check`.

Direct mode turns the graphics window $D800-$DFFF into a plain SRAM: the muxes hold the CPU address, the RAM's -WE is
the CPU's write strobe (GWR = window AND -MEM-WR) through three gates, its -OE the window read, and the byte reaches the
bus through a 74HCT244 (IC55). Whether that works at a given clock depends on how the microcode places the address and
the data around -MEM-WR and -MEM-RD, so this test reads firmware/microcode/ucode-generator2/test.hex and checks:

  1. every -MEM-WR strobe: one step long, the address (ADDR-REG-ID, the operand select) and the data source the same in
     the step before and the step after, the address register neither counted nor loaded in those steps (a write never
     has to be gated against address or data changes: they change only a whole step away);
  2. no -MEM-RD in the step next to a -MEM-WR (the RAM's outputs and the write buffer never meet on GD);
  3. the shortest read window: steps from the address becoming stable to the edge that takes the byte;
  4. the records that write a port (OUT PC switches the mode): every memory strobe in them addresses PC, so no window
     access can meet the moment the mode changes unless code runs from the window;

then works out the direct-mode budget with the parts' data-sheet delays at 1 MHz and 6 MHz (the clock periods the
machine has run at) and fails if any margin is negative. The delay figures are maxima at 5 V / 25 C: 74LS from the TI
data book (as the review hardware/DESIGN-REVIEW-video-v2.0.md uses them), 74HCT from the NXP sheets (To verify against
the parts bought), the AS6C62256-55 from docs/datasheets/AS6C62256.pdf.

Since the re-review (hardware/DESIGN-REVIEW-video-v2.0-r2.md R2-5, 2026-10-23) every read window is classed by how its
address reached the bus at the window's first edge, with the register cards as fitted (SN74HC244N address buffers,
SN74HC193N counters, register.md):
  * selected: the register put on the address bus in that step (pipeline + 74LS139 + the HC244's enable);
  * counted, within the window: the register counted at that edge (-REG-UP/-DN released: pipeline, the card's 74LS32,
    the HC193 carry ripple - two carry stages and the third chip's Q for A8-A10, the highest bits that change inside
    $D800-$DFFF - then the HC244), the board select already settled;
  * counted into the window: a count that changes A11-A15 (three carry stages and a Q), then the GSEL path;
each at two corners: 25 C maxima, and 85 C for the HC / HCT parts (the HC193 at 1.25 x its 25 C figures, To verify).
A counted one-step window is the code fetch (PC), a pop (SP: RET, IRET, POPR) or BRVR's second vector byte; the
software rules (the card's README) keep code out of the window at every clock, and the stack and BRVR vector tables
out of it at 6 MHz. The test reports every case at 1 and 6 MHz and FAILS if a case the rules permit has a negative
margin.
"""
import os, sys, collections
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import ucode_wavedrom as W                                   # noqa: E402  (the test.hex reader)

sig, recs, names = W.signal_table(), W.microcode(), W.opcode_names()
S = {n: (b, bt) for n, b, bt in sig}
on = lambda w, n: W.active(w, S[n][0], S[n][1], n)
def field(w, prefix):
    return sum(((w[S[n][0]] >> S[n][1]) & 1) << int(n[len(prefix):]) for n in S
               if n.startswith(prefix) and n[len(prefix):].isdigit())
SOURCES = ["-AC-RD", "-ALU-FUNC", "-TMP-REG-RD0", "-TMP-REG-RD1", "-REG-FUNC-RD", "-REG-RD-LO", "-REG-RD-HI",
           "-HL-SWAP", "-BRANCH-RD", "-INT-JMP", "-IO-RD", "-MEM-RD"]
LEADING = ["LD-INS-REG", "OPERAND-CLK", "BRANCH-LD-LO", "BRANCH-LD-HI", "INT-LD-LO", "INT-LD-HI", "-TMP-REG-LD0",
           "-TMP-REG-LD1", "-AC-LD", "-SR-LD"]                # take the bus at the leading edge of their step
TRAILING = ["REG-LD-LO", "REG-LD-HI"]                         # take it at the trailing edge (level-sensitive)
addr = lambda w: (field(w, "ADDR-REG-ID"), on(w, "-2-BYTE-OPERAND-SEL"))
def counts(w, r):
    """register r is counted in this step: the count takes effect at the step's trailing edge"""
    return on(w, "-REG-FUNC-RD") and (on(w, "-REG-UP") or on(w, "-REG-DN")) and field(w, "REG-RD-ID") == r
data = lambda w: (tuple(s for s in SOURCES if on(w, s)), field(w, "REG-RD-ID"), on(w, "-2-BYTE-OPERAND-SEL"))
def moves_addr(w):
    """the register on the address bus is counted or loaded in this step"""
    a = field(w, "ADDR-REG-ID")
    cnt = counts(w, a)
    ld = on(w, "-REG-FUNC-LD") and (on(w, "REG-LD-LO") or on(w, "REG-LD-HI")) and field(w, "REG-LD-ID") == a
    return cnt or ld

fails = 0
def check(name, ok, detail=""):
    global fails
    fails += not ok
    print("%-62s %s  %s" % (name, "PASS" if ok else "FAIL", detail))

writes, bad_w, adjacent, together = 0, [], [], []
read_min, read_where = 99, None
windows = []                                                  # (record, opcode, first step, steps, how, register)
io_addr = set()
for op in range(256):
    w = recs[op]
    st = [w[i * 8:i * 8 + 8] for i in range(64)]
    last = next((i for i in range(64) if on(st[i], "UCODE-COUNT-RESET")), 63)
    nm = names.get(op, "$%02X" % op)
    for i in range(last + 1):
        if on(st[i], "-MEM-RD") and on(st[i], "-MEM-WR"):
            together.append((nm, i))
        if on(st[i], "-MEM-WR") and not on(st[i - 1], "-MEM-WR"):
            j = i
            while j + 1 <= last and on(st[j + 1], "-MEM-WR"):
                j += 1
            writes += 1
            pre, post = st[i - 1], st[j + 1]
            ok = (j == i and addr(pre) == addr(st[i]) == addr(post) and data(pre) == data(st[i]) == data(post)
                  and not moves_addr(pre) and not moves_addr(st[i]))
            if not ok:
                bad_w.append("%s step %d" % (nm, i))
            if on(pre, "-MEM-RD") or on(post, "-MEM-RD"):
                adjacent.append("%s step %d" % (nm, i))
        if on(st[i], "-MEM-RD") and not on(st[i - 1], "-MEM-RD"):
            j = i
            while j + 1 <= last and on(st[j + 1], "-MEM-RD"):
                j += 1
            a = i                                             # the address has been stable since step a
            while a > 0 and addr(st[a - 1]) == addr(st[i]) and not moves_addr(st[a - 1]):
                a -= 1
            reg, opsel = addr(st[i])
            how = "counted" if a > 0 and not opsel and counts(st[a - 1], reg) else "selected"
            ks = []
            for k in range(i, j + 2):                         # the loads that take the memory's byte
                if k < 64 and k - 1 >= i and on(st[k - 1], "-MEM-RD") and any(on(st[k], n) for n in LEADING):
                    ks.append(k - a)
                if k <= j and any(on(st[k], n) for n in TRAILING) and on(st[k], "-REG-FUNC-LD"):
                    ks.append(k + 1 - a)
            if ks:
                windows.append((nm, op, a, min(ks), how, "op" if opsel else reg))
                if min(ks) < read_min:
                    read_min, read_where = min(ks), "%s steps %d-%d" % (nm, a, a + min(ks))
    if any(on(st[i], "-IO-WR") for i in range(last + 1)):
        for i in range(last + 1):
            if on(st[i], "-MEM-RD") or on(st[i], "-MEM-WR"):
                io_addr.add((nm, addr(st[i])))

check("1. every -MEM-WR: one step, address and data held a step each side", not bad_w and writes > 0,
      "%d strobes%s" % (writes, (": " + ", ".join(bad_w[:4])) if bad_w else ""))
check("2. no -MEM-RD next to a -MEM-WR, never both in one step", not adjacent and not together,
      ", ".join((adjacent + ["%s %d" % t for t in together])[:4]))
check("3. shortest read window (address stable -> the latching edge)", read_min >= 1,
      "%d step = 2 clocks (%s)" % (read_min, read_where))
check("4. records with -IO-WR: every memory strobe addresses PC", io_addr and all(a == (0, False) for _, a in io_addr),
      "%d records" % len({n for n, _ in io_addr}))

# ---- the budget (ns, maxima). The step edge is t = 0; a step is two clock periods.
# Two corners: 25 C maxima, and 85 C for the HC / HCT parts (74LS: TI gives 25 C only; the HC193's 85 C values assumed
# 1.25 x its 25 C maxima, To verify). The register cards' parts as fitted: SN74HC244N, SN74HC193N (register.md).
T25 = dict(pipe=28,         # 74LS374 pipeline register CLK -> Q (sequencer-logic card)
           ls139=38,        # register card: 74LS139 select -> Y (the address-register decode)
           hc244en=38, hc244=30,     # register card: 74HC244 address buffer, enable -> output / A -> Y
           ls32=22,         # register card: the count gate (-Rn-RDSEL OR -REG-UP) -> the HC193's UP
           hc193q=43, hc193co=30,    # 74HC193 UP -> Q, UP -> CO (the carry to the next chip)
           s85=16,          # 74S85 A/B -> A=B (BOARDSEL)
           ls04=15, ls08=20, ls00=15, ls20=15, als08=14, hct08=25,
           lsmux=14,        # 74LS157 data -> output (the select is fixed in direct mode)
           tAA=55, tOE=30, tWP=45, tDW=25, tAS=0, tWR=0, tDH=0,   # AS6C62256-55
           hct244=25, hct244en=30,   # 74HCT244 (IC55) A -> Y, enable -> output
           bus=5,           # the backplane
           setup=20)        # the slowest destination's set-up (74LS374)
T85 = dict(T25, hc244en=48, hc244=38, hc193q=54, hc193co=38, hct08=30, hct244=31, hct244en=38)
T = T25


def read_path(T, how):
    """ns from the step edge to the byte at its destination (set-up included), for a window whose address arrived
    'selected', 'counted' (within the window) or 'into' (a count that crosses into the window)"""
    sel = T["pipe"] + T["ls139"] + T["hc244en"]               # the register's address on the bus
    if how == "selected":
        a = g = sel
    else:                                                     # the count edge, the card's OR, the HC193 ripple
        stages = 2 if how == "counted" else 3                 # A8-A10 (third chip) / A11-A15 (third or fourth)
        a = T["pipe"] + T["ls32"] + stages * T["hc193co"] + T["hc193q"] + T["hc244"]
        g = sel if how == "counted" else a                    # within the window GSEL has settled with the select
    gsel = g + T["s85"] + T["ls08"]                           # BOARDSEL AND ADDR11 (IC47/B)
    memrd = T["pipe"] + T["ls04"]                             # IC46/B
    grdoe = max(gsel, memrd) + T["ls00"]                      # IC19/A
    ram_oe = grdoe + T["hct08"] + T["als08"]                  # IC54/A, IC1/B -> the RAM's -OE
    data = max(a + T["lsmux"] + T["tAA"], ram_oe + T["tOE"]) + T["hct244"]
    bus_en = max(gsel, memrd) + T["ls20"] + T["hct244en"]     # IC45/B -> IC55's enable
    return max(data, bus_en) + T["bus"] + T["setup"], a, ram_oe


def rule(op, reg, how, mhz):
    """the software rule that keeps a window of this kind out of $D800-$DFFF at this clock, or None (permitted)"""
    if how == "selected":
        return None
    if reg == 0:
        return "no code in the window (every clock)"
    if mhz > 1 and 0xD8 <= op <= 0xDF:                       # BRVR Rn: the vector's second byte after a count
        return "6 MHz: no BRVR vector table in the window"
    if mhz > 1 and reg == 1:
        return "6 MHz: no stack in the window"
    return None


read_ns, addr_on_bus, ram_oe = read_path(T, "selected")
we_fall = T["pipe"] + T["ls04"] + T["ls08"] + T["ls20"]      # IC46/C, IC47/C, IC45/A: -WE after the strobe's edge
print("\ndirect mode, worst case from the step edge (25 C): address on the bus %d ns, the RAM's -OE %d ns, data at the "
      "latch %d ns (with its set-up); -WE follows -MEM-WR by at most %d ns" % (addr_on_bus, ram_oe, read_ns, we_fall))

# ---- the read windows by kind (R2-5): margins at 1 and 6 MHz, 25 / 85 C
kinds = collections.OrderedDict()
for nm, op, a, n, how, reg in windows:
    what = ("operand" if reg == "op" else "code (PC)" if reg == 0 else
            "BRVR vector" if 0xD8 <= op <= 0xDF else "stack (SP)" if reg == 1 else "data (R2-R7)")
    for h in ((how,) if how == "selected" else ("counted", "into")):
        key = (h, what, n)
        kinds.setdefault(key, [op, reg, 0, []])
        kinds[key][2] += 1
        if len(kinds[key][3]) < 3:
            kinds[key][3].append("%s:%d" % (nm, a))
LABEL = {"selected": "register selected", "counted": "counted, in the window", "into": "counted into the window"}
worst = {1: None, 6: None}                                    # the smallest margin of a permitted window
print("\nread windows by how the address arrived (margin = window - path, ns; 25 C / 85 C; * = ruled out by the rule "
      "named):")
print("  %-24s %-14s %5s %4s  %-13s %-13s  %s" % ("address", "register", "steps", "n", "1 MHz", "6 MHz", "examples"))
for (h, what, n), (op, reg, cnt, ex) in sorted(kinds.items(), key=lambda kv: (kv[0][2], list(LABEL).index(kv[0][0]), kv[0][1])):
    cells, notes = [], []
    for mhz in (1, 6):
        step = 2 * 1000 / mhz
        m25 = n * step - read_path(T25, h)[0]
        m85 = n * step - read_path(T85, h)[0]
        r = rule(op, reg, h, mhz)
        if r is None and (worst[mhz] is None or min(m25, m85) < worst[mhz][0]):
            worst[mhz] = (min(m25, m85), "%s, %s, %d step(s)" % (LABEL[h], what, n))
        if r is None and min(m25, m85) < 0:
            check("read, %s, %s, %d step(s) at %d MHz: permitted" % (LABEL[h], what, n, mhz), False,
                  "margin %.0f / %.0f ns" % (m25, m85))
        if r and min(m25, m85) < 0 and r not in notes:
            notes.append(r)
        cells.append("%5.0f/%-5.0f%s" % (m25, m85, "*" if r and min(m25, m85) < 0 else " "))
    print("  %-24s %-14s %5d %4d  %-13s %-13s  %s%s" % (LABEL[h], what, n, cnt, cells[0], cells[1], ", ".join(ex),
          ("   * " + "; ".join(notes)) if notes else ""))
for mhz in (1, 6):
    check("R2-5: every read window the rules permit, at %d MHz (25 / 85 C)" % mhz, worst[mhz][0] >= 0,
          "the closest: %.0f ns (%s)" % worst[mhz])
for mhz in (1, 6):
    step = 2 * 1000 / mhz
    read_margin = read_min * step - max(read_path(T25, "selected")[0], read_path(T85, "selected")[0])
    wp = step - we_fall                                       # -WE width, the late fall against an instant rise
    dw = wp - T["hct244en"]                                   # IC40 drives GD from -WE's fall + its enable time
    hold = step - we_fall                                     # address and data held a whole step after -MEM-WR
    check("direct mode at %d MHz (a step %.0f ns): read, register selected" % (mhz, step), read_margin > 0,
          "window %.0f, needs %d (25 C) / %d (85 C): margin %.0f ns" % (
              read_min * step, read_ns, read_path(T85, "selected")[0], read_margin))
    check("direct mode at %d MHz: write -WE width (tWP %d)" % (mhz, T["tWP"]), wp >= T["tWP"], "%.0f ns" % wp)
    check("direct mode at %d MHz: data set-up to -WE rise (tDW %d)" % (mhz, T["tDW"]), dw >= T["tDW"], "%.0f ns" % dw)
    check("direct mode at %d MHz: address set-up / hold (tAS, tWR 0)" % mhz, hold > 0,
          "address stable %.0f ns before -WE falls and %.0f ns after it rises" % (step, hold))
print("the clock limit of direct mode alone: %.1f MHz (one-step read window, a selected register, 85 C); the machine's "
      "own limit is lower (review M-2: about 6 MHz with the 28C64 ROM in the one-step windows)" % (
          2 * 1000 / read_path(T85, "selected")[0] * read_min))
print("v20 direct-mode timing: %s" % ("ALL PASS" if not fails else "%d FAIL" % fails))
sys.exit(1 if fails else 0)
