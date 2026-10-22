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
"""
import os, sys
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
data = lambda w: (tuple(s for s in SOURCES if on(w, s)), field(w, "REG-RD-ID"), on(w, "-2-BYTE-OPERAND-SEL"))
def moves_addr(w):
    """the register on the address bus is counted or loaded in this step"""
    a = field(w, "ADDR-REG-ID")
    cnt = on(w, "-REG-FUNC-RD") and (on(w, "-REG-UP") or on(w, "-REG-DN")) and field(w, "REG-RD-ID") == a
    ld = on(w, "-REG-FUNC-LD") and (on(w, "REG-LD-LO") or on(w, "REG-LD-HI")) and field(w, "REG-LD-ID") == a
    return cnt or ld

fails = 0
def check(name, ok, detail=""):
    global fails
    fails += not ok
    print("%-62s %s  %s" % (name, "PASS" if ok else "FAIL", detail))

writes, bad_w, adjacent, together = 0, [], [], []
read_min, read_where = 99, None
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
            for k in range(i, j + 2):                         # the loads that take the memory's byte
                if k < 64 and k - 1 >= i and on(st[k - 1], "-MEM-RD") and any(on(st[k], n) for n in LEADING):
                    if k - a < read_min:
                        read_min, read_where = k - a, "%s steps %d-%d" % (nm, a, k)
                if k <= j and any(on(st[k], n) for n in TRAILING) and on(st[k], "-REG-FUNC-LD"):
                    if k + 1 - a < read_min:
                        read_min, read_where = k + 1 - a, "%s steps %d-%d" % (nm, a, k + 1)
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
T = dict(pipe=28,           # 74LS374 pipeline register CLK -> Q (sequencer-logic card)
         reg=38 + 30,       # register card: 74LS139 select -> Y, then the 74LS244 address buffer's enable
         s85=16,            # 74S85 A/B -> A=B (BOARDSEL)
         ls04=15, ls08=20, ls00=15, ls20=15, als08=14, hct08=25,
         lsmux=14,          # 74LS157 data -> output (the select is fixed in direct mode)
         tAA=55, tOE=30, tWP=45, tDW=25, tAS=0, tWR=0, tDH=0,   # AS6C62256-55
         hct244=25, hct244en=30,    # 74HCT244 A -> Y, enable -> output
         setup=20)          # the slowest destination's set-up (74LS374)
addr_on_bus = T["pipe"] + T["reg"]
gsel = addr_on_bus + T["s85"] + T["ls08"]                    # BOARDSEL AND ADDR11 (IC47/B)
memrd = T["pipe"] + T["ls04"]                                # IC46/B
grdoe = max(gsel, memrd) + T["ls00"]                         # IC19/A
ram_oe = grdoe + T["hct08"] + T["als08"]                     # IC54/A, IC1/B -> the RAM's -OE
data_addr = addr_on_bus + T["lsmux"] + T["tAA"]              # through the 157s
data_oe = ram_oe + T["tOE"]
bus_en = max(gsel, memrd) + T["ls20"] + T["hct244en"]        # IC45/B -> IC55's enable
read_ns = max(max(data_addr, data_oe) + T["hct244"], bus_en) + T["setup"]
we_fall = T["pipe"] + T["ls04"] + T["ls08"] + T["ls20"]      # IC46/C, IC47/C, IC45/A: -WE after the strobe's edge
print("\ndirect mode, worst case from the step edge: address on the bus %d ns, the RAM's -OE %d ns, data at the "
      "latch %d ns (with its set-up); -WE follows -MEM-WR by at most %d ns" % (addr_on_bus, ram_oe, read_ns, we_fall))
for mhz in (1, 6):
    step = 2 * 1000 / mhz
    read_margin = read_min * step - read_ns
    wp = step - we_fall                                       # -WE width, the late fall against an instant rise
    dw = wp - T["hct244en"]                                   # IC40 drives GD from -WE's fall + its enable time
    hold = step - we_fall                                     # address and data held a whole step after -MEM-WR
    check("direct mode at %d MHz (a step %.0f ns): read" % (mhz, step), read_margin > 0,
          "window %.0f, needs %d: margin %.0f ns" % (read_min * step, read_ns, read_margin))
    check("direct mode at %d MHz: write -WE width (tWP %d)" % (mhz, T["tWP"]), wp >= T["tWP"], "%.0f ns" % wp)
    check("direct mode at %d MHz: data set-up to -WE rise (tDW %d)" % (mhz, T["tDW"]), dw >= T["tDW"], "%.0f ns" % dw)
    check("direct mode at %d MHz: address set-up / hold (tAS, tWR 0)" % mhz, hold > 0,
          "address stable %.0f ns before -WE falls and %.0f ns after it rises" % (step, hold))
print("the clock limit of direct mode alone: %.1f MHz (one-step read window); the machine's own limit is lower "
      "(review M-2: about 6 MHz with the 28C64 ROM in the one-step windows)" % (2 * 1000 / read_ns * read_min))
print("v20 direct-mode timing: %s" % ("ALL PASS" if not fails else "%d FAIL" % fails))
sys.exit(1 if fails else 0)
