#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""bus_records.py - what the microcode does on the bus, as the video card's timing check assumes it (2026-10-22 and
2026-11-11, from the V2.0 and V3 cards' checks; on its own since 2026-11-18, when those designs left the tree). No
hardware; part of `make check`.

tests/video/v40_netsim.py drives the card's bus side as the microcode drives the machine's bus. This test reads
firmware/microcode/ucode-generator2/test.hex and checks that the microcode does so:

  1. every -MEM-WR strobe: one step long, the address (ADDR-REG-ID, the operand select) and the data source the same in
     the step before and the step after, the address register neither counted nor loaded in those steps (a write never
     has to be gated against address or data changes: they change only a whole step away);
  2. no -MEM-RD in the step next to a -MEM-WR (a memory's outputs and the write data never meet);
  3. the shortest read window: steps from the address becoming stable to the edge that takes the byte;
  4. the records that write a port: every memory strobe in them addresses PC, so no window access can meet the moment
     a port changes the video card's mode unless code runs from the window;
  5. the I/O records: the port number, and for an OUT the data, on the bus two steps before the strobe; -IO-WR one
     step, the port number and the data staying a step after it; an IN's byte taken at least a step into -IO-RD.
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

def records():
    """the microcode's I/O records, which the video card's bus bench imitates: what it relies on is checked here against the tree's
    test.hex. Returns the faults"""
    sig, recs = W.signal_table(), W.microcode()
    S = {n: (b, bt) for n, b, bt in sig}
    on = lambda w, n: W.active(w, S[n][0], S[n][1], n)
    port = lambda w: sum(on(w, "IOADDR%d" % i) << i for i in range(4))
    src = lambda w: tuple(n for n in ("-AC-RD", "-ALU-FUNC", "-MEM-RD", "-TMP-REG-RD0", "-TMP-REG-RD1", "-REG-FUNC-RD") if on(w, n))
    out = []; nw = nr = 0; drops = 0
    for op in range(256):
        w = recs[op]; st = [w[i * 8:i * 8 + 8] for i in range(64)]
        last = next((i for i in range(64) if on(st[i], "UCODE-COUNT-RESET")), 63)
        for i in range(1, last + 1):
            for strobe in ("-IO-WR", "-IO-RD"):
                if not on(st[i], strobe) or on(st[i - 1], strobe): continue
                j = i
                while j < last and on(st[j + 1], strobe): j += 1
                if i < 3 or port(st[i - 2]) != port(st[i]) or port(st[i - 1]) != port(st[i]):
                    out.append("opcode %02X: the port number is not on the bus two steps before %s" % (op, strobe))
                if any(port(st[k]) != port(st[i]) for k in range(i, j + 1)): out.append("opcode %02X: the port number moves during %s" % (op, strobe))
                if strobe == "-IO-WR":
                    nw += 1
                    if j != i: out.append("opcode %02X: -IO-WR is %d steps" % (op, j - i + 1))
                    if j + 1 > last or port(st[j + 1]) != port(st[i]): out.append("opcode %02X: the port number goes with -IO-WR" % op)
                    if not src(st[i]) or any(src(st[k]) != src(st[i]) for k in (i - 2, i - 1, j + 1) if k <= last) or j + 1 > last:
                        out.append("opcode %02X: the data is not on the bus from two steps before -IO-WR to a step after" % op)
                else:
                    nr += 1
                    takes = [k for k in range(i, min(j + 2, last + 1)) if on(st[k], "-AC-LD")]
                    if not takes or takes[0] < i + 1: out.append("opcode %02X: the byte is taken less than a step into -IO-RD" % op)
                    if j == last or port(st[j + 1]) != port(st[i]): drops += 1
    if not nw or not nr: out.append("no I/O records found in the microcode")
    return out, "%d OUT and %d IN records: the port number and the data two steps before a strobe, a step after -IO-WR; " \
                "%d of the IN records drop the port number with -IO-RD" % (nw, nr, drops)


out, what = records()
check("5. the I/O records: port and data two steps before the strobe", not out, what if not out else "; ".join(out[:4]))
print("bus records: %s" % ("ALL PASS" if not fails else "%d FAIL" % fails))
sys.exit(1 if fails else 0)
