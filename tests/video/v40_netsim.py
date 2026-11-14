#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""tests/video/v40_netsim.py - the video card V4's netlist run as a circuit, and its timing check (2026-11-12).

  v40_netsim.py [-v] [--limits] [--faults]
      -v        prints every run's measurements
      --limits  also searches the shortest microcode step the window works at, in each mode
      --faults  also breaks the netlist in memory, one wiring fault at a time, and reports whether the runs notice

hardware/cards/video/kicad/v4.0/v40_netlist.py is simulated gate for gate, with delays in nanoseconds. The simulator
and the models of the parts both designs use (the 74F and 74ACT parts, the 128K RAM) are the V3 check's
(tests/video/v30_netsim.py, imported here); added are the 74ACT157, the 74ACT244 with its enable times, the 74S85,
the text RAM's display port, the character generator, and the two test benches:

  the 6845      a model of its display side: at every falling edge of the clock the card gives it, it puts out the
                next count of a script (MA, RA, DE, CURSOR, HSYNC, VSYNC), each after its delay, and checks the
                clock's low and high times.
  the machine   the bus as the microcode drives it. A write: the address and the data a step before -MEM-WR, the
                strobe one step, both held a step after. A read: -MEM-RD and the address early in a step, the byte
                taken at the step's end (25 ns before it: the backplane and the slowest destination's set-up). An
                OUT: the port number and the data two steps before -IO-WR, a step after. These are what
                tests/video/v20_timing.py (checks 1-3) and v30_netsim.py's records() read out of test.hex; the
                address's and the strobes' delays from the step's edge are v20_timing.py's (register selected, 85 C).
                The bus operations start at every phase of the dot counter.

The delays are the parts' data-sheet figures, minimum and maximum, a rising and a falling output apart; every run is
repeated at the corners of the V3 check: the 6845 slow or fast, the card's parts all slow or all fast, and the two
mixed corners that set a part's rising outputs against its falling ones (what shows a runt pulse on a clock).

What is checked:
  the picture   every count of the script comes out as its two characters and its two graphics bytes, bit 7 first,
                16 dots, 27 dots after the 6845 stepped, on the guns a dot later; the cursor's form on the half CURH
                names; nothing where DE is low; text OR graphics, XOR, TEXT-OFF, the three colour bits, the display
                page; nothing of the graphics layer while GFX-ON = 0; the text-only build.
  the window    slot mode (the layer shown): a byte written through $D800-$DFFF lands at page, plane, offset and
                nowhere else, whatever the strobe's phase, with a whole write pulse; a byte read is on the bus when
                the microcode takes it; the picture is not disturbed. Direct mode: the same at the machine's 6 MHz;
                switching the mode writes nothing.
  the ports     each strobe answers its own port only; the status byte; the two control registers.
  the syncs     HSYNC and VSYNC at the connector, both polarities; VSYNC cut to the second HSYNC after its rise.
  everywhere    every flip-flop's, register's and shift register's set-up and hold; the RAM's write pulse, data
                set-up and address; no pulse shorter than 5 ns on any clock, clear, preset or -WE; in the four
                straight corners no two outputs on a net for more than 3 ns at a handover; the 6845's clock.
                The table at the end has the least set-up and the least hold margin of each kind.

Since the design review of 2026-11-13 (hardware/cards/video/reviews/v4.0.md): the four clocks' series resistors
R20-R23 are in it, each as one delay (the resistor with its net's capacitance and wire: SERIES); the hold margins
are in the table (V4-5); the window is also run at 160 phases of a count, and with the later address of a register
that was counted, at 2.8 MHz (V4-4, V4-6). Not in it: a delay for each wire by its length - the clocks' loads all
see their net move at once.

Not checked here: the 6845's own minimum delays (assumed), signal quality, and a bench.
"""
import os, sys, io, copy, heapq, contextlib, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import v30_netsim as E                                              # noqa: E402  the simulator and the shared models
spec = importlib.util.spec_from_file_location("v40_netlist", os.path.join(ROOT, "hardware/cards/video/kicad/v4.0/v40_netlist.py"))
N = importlib.util.module_from_spec(spec); spec.loader.exec_module(N)
E.N = N                                                             # the simulator wires what this netlist says
VERBOSE = E.VERBOSE
DOT = E.DOT
COUNT = 16 * DOT

# ---- delays added to the V3 check's tables: (tPLH min, max, tPHL min, max) ns ----------------------------------------
# TI CD74ACT157 (SCHS340D), 5 V +- 0.5 V, 50 pF, -40..85 C: A / B to Y 2.5-8.6, select to Y 3.8-13.2.
# TI SN74ACT244 (SCAS517G), -40..85 C: A to Y 1.5-10, enable 1-10.5, disable 1.5-10.5.
# The bus side's parts see only the bus's strobes; their figures are the ones tests/video/v20_timing.py uses (TI 74LS,
# NXP 74HCT at 85 C, the 74S85), with small minimums.
E.TPD.update({("ACT", "157"): (2.5, 8.6, 2.5, 8.6), ("ACT", "244"): (1.5, 10.0, 1.5, 10.0),
              ("HCT", "04"): (4.0, 30.0, 4.0, 30.0), ("HCT", "08"): (4.0, 30.0, 4.0, 30.0), ("HCT", "244"): (4.0, 31.0, 4.0, 31.0),
              ("HCT", "273"): (5.0, 38.0, 5.0, 38.0), ("HCT", "74"): (5.0, 40.0, 5.0, 40.0),
              ("LS", "32"): (3.0, 22.0, 3.0, 22.0), ("LS", "138"): (5.0, 41.0, 5.0, 41.0), ("LS", "244"): (3.0, 18.0, 3.0, 18.0),
              ("LS", "*"): (3.0, 30.0, 3.0, 30.0), ("S", "85"): (3.0, 16.5, 3.0, 16.5)})
SELTPD = {("ACT", "157"): (3.8, 13.2, 3.8, 13.2)}
E.PRECLR.update({("HCT", "*"): (5.0, 40.0, 5.0, 40.0)})
E.ENABLE.update({("ACT", "244"): (1.0, 10.5), ("HCT", "244"): (4.0, 38.0), ("LS", "244"): (5.0, 30.0)})
E.DISABLE.update({("ACT", "244"): (1.5, 10.5), ("HCT", "244"): (4.0, 38.0), ("LS", "244"): (5.0, 25.0)})
E.SETUP.update({("HCT", "273"): (20.0, 5.0), ("HCT", "74"): (15.0, 3.0)})
# (the 74HCT74's hold: 3 ns on NXP's sheet, 0 on TI's. IC40's second flip-flop takes the first one's Q on their common
# clock, HSYNC: its hold margin is the first's least clock-to-output, which no sheet gives - 5 ns is taken above - less
# those 3 ns. Two flip-flops of one package as a shift register: the ordinary case.)
# The text RAM's display port and the character generator: (min, max) ns; where a sheet gives no minimum, a small one.
# Renesas 7134SA/LA (2021): tAA 55 (the commercial grade) or 70 (the slowest the sheet has; there is no 90), tOH 0.
# The 70 ns figure is used: it covers both. Atmel AT28C64B-15 (0270H): tACC 150, tOH 0.
TEXTRAM = {"aa": (10.0, 70.0), "oh": (0.0, 0.0)}
CHARGEN = {"acc": (20.0, 150.0), "oh": (0.0, 0.0)}
# The 6845 (Motorola MC6845 data sheet, one CRTC timing column for all three bus grades): outputs from the clock's
# falling edge - MA and RA 160 ns, DE, CURSOR and the syncs 250 ns at most; the clock low and high at least 150 ns
# each, 3.0 MHz at most. No minimums are given: 20 ns assumed (the stage's hold needs none: it has a whole dot)
D6845_MAX = {"ma": 160.0, "ra": 160.0, "de": 250.0, "cur": 250.0, "hs": 250.0, "vs": 250.0}
D6845_MIN = {"ma": 20.0, "ra": 20.0, "de": 20.0, "cur": 20.0, "hs": 20.0, "vs": 20.0}
PWCL, PWCH = 150.0, 150.0
# The machine's bus (tests/video/v20_timing.py: the sequencer's pipeline register 28 ns, a register's address on the
# bus through a 74LS139 and a 74HC244's enable 104 ns at 25 C, 114 at 85 C; the byte wanted 25 ns before the step ends)
BUS_SLOW = {"strobe": 28.0, "addr": 114.0, "take": 25.0}
BUS_FAST = {"strobe": 8.0, "addr": 35.0, "take": 25.0}
STEP_SLOT = 2000.0 / 3.5                                            # a microcode step at 3.5 MHz, slot mode's clock
STEP_DIRECT = 2000.0 / 6.0                                          # at 6 MHz, the machine's own limit
STEP_IO = 500.0                                                     # OUT and IN: nothing here is near the dot clock
SERIES = (0.3, 2.0)                                                 # a clock's 33 ohm series resistor with its net's
                                                                    # 40 to 60 pF and the wire behind it: one delay, ns
BUS_COUNTED = (218.0, 256.0)                                        # the address of a one-step read whose register was
                                                                    # counted in the step before (RET, POPR, BRVR's vector):
                                                                    # within the window, and into it (v20_timing.py, 85 C)
PS2 = ["IC%d" % n for n in range(41, 47)]                          # not simulated (V2.0's section, proved there)
WATCH = ("TDOT", "GDOT", "VR", "VG", "VB", "HSB", "VSB")


# ---- the added models -------------------------------------------------------------------------------------------------
class Mux157(E.Part):
    SEC = ((2, 3, 4), (5, 6, 7), (11, 10, 9), (14, 13, 12))        # (A, B, Y): S = 0 gives A, 1 gives B
    def init(self): self.sel = "?"; self.y = ["?"] * 4
    def eval(self):
        sel, g = self.v(1), self.v(15)
        moved = sel != self.sel; self.sel = sel
        for i, (a, b, y) in enumerate(self.SEC):
            val = 0 if g == 1 else None if sel is None else self.v(b) if sel == 1 else self.v(a)
            if val == self.y[i]: continue
            self.y[i] = val
            self.out(y, val, table=SELTPD if moved else None)


class Buf244(E.Part):
    """a '244 with its enable and disable times; an enabled half with nothing known on an input drives an unknown"""
    HALF = ((1, ((2, 18), (4, 16), (6, 14), (8, 12))), (19, ((11, 9), (13, 7), (15, 5), (17, 3))))
    def init(self): self.on = [None, None]
    def eval(self):
        for h, (oe, pairs) in enumerate(self.HALF):
            on = self.v(oe) == 0
            sw = on != self.on[h]; self.on[h] = on
            for a, y in pairs:
                val = (self.v(a) if self.v(a) is not None else "X") if on else None
                self.out(y, val, self.onoff(on) if sw else None)


class Cmp85(E.Part):
    def eval(self):
        a = [self.v(p) for p in (10, 12, 13, 15)]; b = [self.v(p) for p in (9, 11, 14, 1)]
        eq = None if None in a + b or self.v(3) is None else int(a == b and self.v(3) == 1)
        self.out(6, eq)


class TextRam(E.Part):
    """the IDT7134's display port (always enabled, read only): the byte at A0L-A11L after the access time. The CPU's
    port is not modelled: the test writes the memory directly"""
    AL = (6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 4, 3); DL = tuple(range(16, 24))
    def init(self): self.mem = {}; self.a = "?"
    def default(self, a): return (a * 5 + (a >> 8) * 37 + 0x21) & 255      # every address bit shows in the byte
    def byte(self, a): return self.mem.get(a, self.default(a))
    def eval(self):
        bits = [self.v(p) for p in self.AL]
        a = None if None in bits else sum(b << i for i, b in enumerate(bits))
        if a == self.a: return
        self.a = a
        k = 0 if self.s.corner == "min" else 1
        for i, p in enumerate(self.DL):
            self.out(p, "X", TEXTRAM["oh"][k]); self.out(p, "X" if a is None else self.byte(a) >> i & 1, max(TEXTRAM["aa"][k], TEXTRAM["oh"][k] + 0.1))


def glyph(code, line): return (code * 3 + line * 17 + 1) & 255       # the test character generator's byte
def cgen(a): return glyph(a >> 4 & 255, a & 15) ^ (0xFF if a >> 12 & 1 else 0)     # A12 = the cursor's form: turned over


class CharGen(E.Part):
    A = {0: 10, 1: 9, 2: 8, 3: 7, 4: 6, 5: 5, 6: 4, 7: 3, 8: 25, 9: 24, 10: 21, 11: 23, 12: 2}
    D = (11, 12, 13, 15, 16, 17, 18, 19)
    def init(self): self.a = "?"
    def eval(self):
        bits = [self.v(self.A[i]) for i in range(13)]
        a = None if None in bits else sum(b << i for i, b in enumerate(bits))
        if a == self.a: return
        self.a = a
        k = 0 if self.s.corner == "min" else 1
        for i, p in enumerate(self.D):
            self.out(p, "X", CHARGEN["oh"][k]); self.out(p, "X" if a is None else cgen(a) >> i & 1, max(CHARGEN["acc"][k], CHARGEN["oh"][k] + 0.1))


IDLE = {"ma": 0x3A5, "de": 0, "cur": 0, "hs": 0, "vs": 0}


class Crtc(E.Part):
    """the 6845's display side: a script of counts, one for each falling edge of its clock. A count is a dict: ma, ra
    (kept from the count before when absent), de, cur, hs, vs; counts with a 'tag' are logged with the time they began"""
    def init(self):
        self.ck = None; self.script = []; self.log = []; self.ra = 0; self.t_edge = None; self.steps = 0
        self.put(dict(IDLE, ra=0), {k: 0.0 for k in D6845_MAX})
    def put(self, c, d):
        for i in range(14): self.out(4 + i, c["ma"] >> i & 1, d["ma"])
        for i in range(5): self.out(38 - i, c["ra"] >> i & 1, d["ra"])
        self.out(18, c["de"], d["de"]); self.out(19, c["cur"], d["cur"]); self.out(39, c["hs"], d["hs"]); self.out(40, c["vs"], d["vs"])
    def eval(self):
        now = self.v(21); was = self.ck; self.ck = now
        if now == was or now is None or was is None: return
        t = self.s.t
        if self.t_edge is not None and self.steps > 1:
            width, need, what = t - self.t_edge, (PWCH if now == 0 else PWCL), ("high" if now == 0 else "low")
            self.s.note("6845 clock %s" % what, width - need, "%.1f ns at %.1f ns" % (width, t))
            if width < need: self.s.faults.append("%.1f ns: the 6845's clock %s for %.1f ns (%.0f wanted)" % (t, what, width, need))
        self.t_edge = t
        if now == 1: return
        self.steps += 1
        c = dict(IDLE, **(self.script.pop(0) if self.script else {}))
        c.setdefault("ra", self.ra); self.ra = c["ra"]
        if "tag" in c: self.log.append((t, c))
        self.put(c, self.s.d)


class SeriesR(E.Part):
    """a clock's series resistor (R20-R23): what is on pin 1 is on pin 2 a little later"""
    def init(self): self.x = "?"
    def eval(self):
        x = self.v(1)
        if x == self.x: return
        self.x = x
        self.s.drive(self.ref, 2, x, SERIES[0 if self.s.corner == "min" else 1])


class Tap:
    """records when a net changes (for the margins the parts' own checks do not give)"""
    def __init__(self, sim, net): self.s = sim; self.net = net; self.t = []; sim.byname.setdefault(net, []).append(self)
    def eval(self):
        if not self.t or self.t[-1][0] != self.s.t: self.t.append((self.s.t, self.s.val[self.net]))


_family = E.family
def family(value):
    if "68B45" in value: return "-", "crtc"
    if value.startswith("IDT7134"): return "-", "dpram"
    if "28C64" in value: return "-", "cgen"
    if value == "33": return "-", "rser"
    return _family(value)
E.family = family
E.MODELS.update({"157": Mux157, "244": Buf244, "85": Cmp85, "dpram": TextRam, "cgen": CharGen, "crtc": Crtc, "rser": SeriesR})
E.EDGE_PINS["crtc"] = (21,)


class Sim(E.Sim):
    """the V3 check's simulator, with the inputs that are asynchronous by design left out of the set-up checks:
    IC34/A's D (WRQ takes the CPU's write strobe: a synchronizer, with a whole dot before its output is used); the
    read latch IC30's D (the CPU's address may move in a slot: that slot's byte is not the one taken, and the read
    checks below time the one that is); the byte latch IC32's D in direct mode and in a count whose DE is low (what
    it takes then is never loaded: RA moves only in such a count, as a scan line ends); and everything while a
    control register is being written (quiet: the mode is switched in the vertical blanking)"""
    quiet = False
    def __init__(self, *a, **k):
        E.Sim.__init__(self, *a, **k)
        self.h2 = []                                    # [net, the clock's time, the hold wanted, what, where]
        self.last = _Last(self.last, self.moved)        # (the engine writes a net's time here whenever it moves)
    def setup(self, ref, pin, tsu, th, what):
        if (ref, str(pin)) == ("IC34", "2") or ref == "IC30" or self.quiet: return
        if ref == "IC32" and (self.val.get("GFXON") != 1 or self.val.get("SDE") != 1): return
        E.Sim.setup(self, ref, pin, tsu, th, what)
        net = self.netof.get((ref, str(pin)))
        if net not in (None, "VCC", "GND") and not (net in self.pull and not self.drv[net]):
            self.h2.append((net, self.t, th, what + " hold", "%s.%s (%s) at %.1f ns" % (ref, pin, net, self.t)))
    def moved(self, net, t):
        """the engine fails a run on a hold violation; this keeps the least hold margin of each kind for the table"""
        keep = []
        for h in self.h2:
            if h[0] == net and t > h[1]: self.note(h[3], t - h[1] - h[2], h[4])
            elif t - h[1] < 60.0: keep.append(h)
        self.h2 = keep


class _Last(dict):
    def __init__(self, d, cb): dict.__init__(self, d); self.cb = cb
    def __setitem__(self, k, v):
        self.cb(k, v); dict.__setitem__(self, k, v)


# ---- the bench --------------------------------------------------------------------------------------------------------
def build(d, count0=1, corner="max", text_only=False):
    """the card after -RESET, the block jumper on $D000, the bus idle, the dot clock not yet running"""
    Sim.count0 = count0; Sim.corner = corner
    s = Sim(fitted_out=PS2 + (list(N.TEXT_ONLY_LEFT_OFF) if text_only else []))
    s.count0 = count0; s.d = d; s.bus = BUS_FAST if corner == "min" else BUS_SLOW
    s.nck = 0; s.samples = {}; s.probes = []; s.pseq = 0; s.text_only = text_only
    for net in ("-IO-WR", "-IO-RD", "-MEM-RD", "-MEM-WR"): s.force(net, 1)
    s.force("-VMA", 0); s.force("SEL1", 0); s.force("-RESET", 0)   # SV1 5-6 fitted: the $D000 block
    for i in range(4): s.force("IO-ADDR%d" % i, 0)
    for i in range(16): s.force("ADDR%d" % i, 0)
    s.run(0.0)
    for m in s.parts.values(): m.eval()
    s.run(200.0); s.force("-RESET", 1); s.run(400.0)
    s.t0 = 400.0                                                    # the dot clock's edges are counted from here
    s.loads = [0, 0]                                                # the loads to expect of the text and the graphics shifter
    s.ctl = [0, 0]                                                  # what the two control registers hold
    s.taps = {n: Tap(s, n) for n in ["RDCK", "D2"] + ["GD%d" % i for i in range(8)]} if not text_only else {}
    if not text_only:                                               # what the graphics RAM holds before it is written:
        s.parts["IC28"].default = lambda a: (a * 7 + (a >> 8) * 13 + (a >> 11) * 29 + (a >> 15) * 101 + 0x51) & 255    # every address bit in it
    return s


def runp(s, t):
    while s.probes and s.probes[0][0] <= t:
        tp, _, f = heapq.heappop(s.probes); s.run(tp); f()
    s.run(t)


def clock(s, dots):
    """dots periods of the dot clock. samples[k] is what is on the wires in the period after the clock's edge k (taken
    just before edge k + 1); in that period the dot counter holds (count0 + k) mod 16"""
    for _ in range(dots):
        t = s.t0 + s.nck * DOT
        runp(s, t + DOT / 2 - 0.01); s.force("OSCO", 0)             # the oscillator's pin; CK is behind R20
        runp(s, t + DOT - 0.01)
        s.samples[s.nck] = {w: s.val.get(w) for w in WATCH}
        s.force("OSCO", 1); s.nck += 1


def clock_to(s, t):
    while s.t0 + s.nck * DOT < t: clock(s, 1)


def edge_of(s, t): return int(round((t - s.t0) / DOT))               # the dot clock edge nearest a time
def stream(s, net, first, n): return [s.samples[first + i][net] for i in range(n)]
def bits7(byte): return [byte >> (7 - i) & 1 for i in range(8)]     # bit 7 leaves first
def probe(s, t, f): s.pseq += 1; heapq.heappush(s.probes, (t, s.pseq, f))
def phase_time(s, phase, after):
    """the first time at or after `after` that is `phase` ns into a count (a count begins with the edge into dot 0)"""
    k0 = (-s.count0) % 16                                           # an edge into dot 0
    base = s.t0 + k0 * DOT - 0.01 + phase
    n = max(0, int((after - base) // COUNT) + 1)
    return base + n * COUNT


def out_port(s, port, value):
    """OUT: the port number and the data two steps before -IO-WR, the strobe a step, both a step after"""
    s.quiet = True
    for i in range(4): s.force("IO-ADDR%d" % i, port >> i & 1)
    for i in range(8): s.force("DATA%d" % i, value >> i & 1)
    s.force("-IO-WR", 0, 2 * STEP_IO); s.force("-IO-WR", 1, 3 * STEP_IO)
    for i in range(8): s.force("DATA%d" % i, None, 4 * STEP_IO)
    for i in range(4): s.force("IO-ADDR%d" % i, 0, 4 * STEP_IO)
    clock_to(s, s.t + 4 * STEP_IO + 2 * COUNT)                      # and two counts for the pipeline to forget
    s.quiet = False
    if port == 12: s.ctl[0] = value
    if port == 15: s.ctl[1] = value


def in_port(s, port):
    """IN: -IO-RD four steps, the byte taken a step into it; returns the byte (None for a line nothing drives)"""
    for i in range(4): s.force("IO-ADDR%d" % i, port >> i & 1)
    got = []
    t = s.t
    s.force("-IO-RD", 0, 2 * STEP_IO); s.force("-IO-RD", 1, 6 * STEP_IO)
    for i in range(4): s.force("IO-ADDR%d" % i, 0, 6 * STEP_IO)
    probe(s, t + 3 * STEP_IO, lambda: got.append([s.val["DATA%d" % i] if s.drv["DATA%d" % i] and any(
        x is not None for x in s.drv["DATA%d" % i].values()) else None for i in range(8)]))
    clock_to(s, t + 7 * STEP_IO)
    return got[0]


def mem_write(s, addr, value, step, t0):
    """a window write as the microcode does it: the address and the data from t0, -MEM-WR a step later for a step,
    both held a step more. Returns the time it is all over"""
    for i in range(16): s.force("ADDR%d" % i, addr >> i & 1, t0 - s.t)
    for i in range(8): s.force("DATA%d" % i, value >> i & 1, t0 - s.t)
    s.force("-MEM-WR", 0, t0 + step + s.bus["strobe"] - s.t); s.force("-MEM-WR", 1, t0 + 2 * step + s.bus["strobe"] - s.t)
    for i in range(8): s.force("DATA%d" % i, None, t0 + 3 * step - s.t)
    for i in range(16): s.force("ADDR%d" % i, 0, t0 + 3 * step - s.t)
    return t0 + 3 * step


def mem_read(s, addr, step, t0, got):
    """a one-step read window: -MEM-RD and then the address (a register selected in this step) after the step's edge
    at t0, the byte taken 25 ns before the step ends. got gets (byte or None, ns the bus was steady before the take)"""
    b = s.bus
    s.force("-MEM-RD", 0, t0 + b["strobe"] - s.t); s.force("-MEM-RD", 1, t0 + step + b["strobe"] - s.t)
    for i in range(16):
        s.force("ADDR%d" % i, addr >> i & 1, t0 + b["addr"] - s.t); s.force("ADDR%d" % i, 0, t0 + step + b["strobe"] + 5.0 - s.t)
    def take():
        v = [s.val["DATA%d" % i] for i in range(8)]
        got.append((None if None in v else sum(x << i for i, x in enumerate(v)), s.t - max(s.last["DATA%d" % i] for i in range(8))))
    probe(s, t0 + step - b["take"], take)
    return t0 + step + b["strobe"] + 5.0


def finish(s, checks):
    s.fights = {k: v for k, v in s.fights.items() if "TB" not in k[1]}   # not the test bench's own drivers
    return E.finish(s, "", checks)


# ---- what the picture should be ---------------------------------------------------------------------------------------
def gaddr(page, plane, offset): return page << 15 | plane << 11 | offset


def want(s, c):
    """the 16 dots of a count: (text, graphics, the three guns' dot), as the control registers stand"""
    c1, c2 = s.ctl
    tr = s.parts["IC14"]; ram = s.parts.get("IC28")
    curh, gfx, xor, dpage, textoff = c2 >> 1 & 1, c1 >> 6 & 1, c1 >> 7 & 1, c1 >> 5 & 1, c2 & 1
    text, graf = [], []
    for half in (0, 1):
        code = tr.byte(c["ma"] << 1 | half)
        flag = c.get("cur", 0) and half == curh
        text += bits7(cgen(flag << 12 | code << 4 | c["ra"])) if c.get("de") and not textoff else [0] * 8
        a = gaddr(dpage, c["ra"], c["ma"] << 1 | half)
        graf += bits7(ram.mem.get(a, ram.default(a))) if ram and c.get("de") and gfx else [0] * 8
    mix = [t ^ g for t, g in zip(text, graf)] if xor else [t | g for t, g in zip(text, graf)]
    return text, graf, mix


def show(s, script, chk, what):
    """run a script of counts and compare every tagged count's dots with want()"""
    crtc = s.parts["IC10"]; n0 = len(crtc.log)
    crtc.script = [dict(c) for c in script]
    clock_to(s, s.t + (len(script) + 5) * COUNT)
    if len(crtc.log) - n0 != sum(1 for c in script if "tag" in c): chk.append("%s: %d of the script's counts began" % (what, len(crtc.log) - n0))
    for t, c in crtc.log[n0:]:
        e = edge_of(s, t)                                           # the edge into dot 1: the 6845 stepped
        if (s.count0 + e) & 15 != 1: chk.append("%s: the 6845 stepped in dot %d" % (what, (s.count0 + e) & 15))
        text, graf, mix = want(s, c)
        if c["de"]: s.loads[0] += 2 * (1 - (s.ctl[1] & 1)); s.loads[1] += 2 * (s.ctl[0] >> 6 & 1)
        if stream(s, "TDOT", e + 27, 16) != text:
            chk.append("%s: count MA %03X RA %d DE %d: text %r, not %r" % (what, c["ma"], c["ra"], c["de"], stream(s, "TDOT", e + 27, 16), text))
        if not s.text_only and stream(s, "GDOT", e + 27, 16) != graf:
            chk.append("%s: count MA %03X RA %d: graphics %r, not %r" % (what, c["ma"], c["ra"], stream(s, "GDOT", e + 27, 16), graf))
        for gun, off in (("VR", 5), ("VG", 6), ("VB", 7)):
            w = [0] * 16 if s.ctl[1] >> off & 1 else mix
            if stream(s, gun, e + 28, 16) != w: chk.append("%s: count MA %03X: %s %r, not %r" % (what, c["ma"], gun, stream(s, gun, e + 28, 16), w))


def line(mas, ra, cur=None, blank=3):
    """a piece of a scan line: blank counts, the counts shown (one of them the cursor's), blank counts"""
    out = [{"ma": 0x111 + i, "ra": ra, "de": 0, "tag": 1} for i in range(blank)]
    out += [{"ma": m, "ra": ra, "de": 1, "cur": int(m == cur), "tag": 1} for m in mas]
    return out + [{"ma": 0x222 + i, "ra": ra, "de": 0, "tag": 1} for i in range(blank)]


# ---- the runs ---------------------------------------------------------------------------------------------------------
def picture(d, count0, corner):
    s = build(d, count0, corner); chk = []
    clock(s, 40)
    tr = s.parts["IC14"]
    for a, v in ((0, 0x41), (1, 0x42), (0x2AA, 0x00), (0x2AB, 0xFF), (0x7FE, 0x7F), (0x7FF, 0x80)): tr.mem[a] = v
    mas = (0x000, 0x001, 0x155, 0x2AA, 0x3FF, 0x200)
    show(s, line(mas, 5), chk, "after -RESET (text, no graphics)")
    out_port(s, 12, 0x40)                                           # GFX-ON
    show(s, line(mas, 5, cur=0x155), chk, "graphics on, the cursor on the left")
    out_port(s, 15, 0x02)                                           # CURH
    show(s, line(mas, 0, cur=0x155) + line(mas[:3], 15, cur=0x000), chk, "the cursor on the right")
    out_port(s, 12, 0xC0)                                           # XOR
    show(s, line(mas, 9), chk, "text XOR graphics")
    out_port(s, 12, 0x60)                                           # GFX-ON, the other page
    show(s, line(mas, 10), chk, "the display page 1")
    out_port(s, 15, 0x01)                                           # TEXT-OFF
    show(s, line(mas, 3), chk, "the text off")
    out_port(s, 15, 0xA0)                                           # red and blue off
    show(s, line(mas, 3), chk, "red and blue off")
    out_port(s, 15, 0x00); out_port(s, 12, 0x00)                    # direct mode: no graphics layer
    show(s, line(mas, 7), chk, "GFX-ON = 0")
    for ref, k in (("IC19", s.loads[0]), ("IC33", s.loads[1])):     # a load for each character and byte shown, no other
        if len(s.parts[ref].loads) != k: chk.append("%s was loaded %d times, %d wanted" % (ref, len(s.parts[ref].loads), k))
    return finish(s, chk)


def text_only(d, count0, corner):
    s = build(d, count0, corner, text_only=True); chk = []
    clock(s, 40)
    show(s, line((0x000, 0x155, 0x3FF), 6, cur=0x155), chk, "the text-only build")
    b = in_port(s, 12)
    if b[3] != 1 or b[4:] != [1, 1, 1, 0] or b[0] != 0: chk.append("the text-only build's status reads %r" % b)
    return finish(s, chk)


def read_margins(s, t_take, chk, what):
    """the read latch's clock that gave the byte taken: its set-up and hold against the RAM's data lines"""
    edges = [t for t, v in s.taps["RDCK"].t if v == 1 and t < t_take]
    if not edges: chk.append("%s: no read latch clock before the take" % what); return
    te = edges[-1]
    before = max((t for i in range(8) for t, v in s.taps["GD%d" % i].t if t <= te), default=-1e9)
    after = min((t for i in range(8) for t, v in s.taps["GD%d" % i].t if t > te), default=1e9)
    s.note("read latch set-up", te - before - E.SETUP[("ACT", "574")][0], "%s: steady %.1f ns" % (what, te - before))
    s.note("read latch hold", after - te - E.SETUP[("ACT", "574")][1], "%s: steady %.1f ns after its clock" % (what, after - te))
    if after - te < E.SETUP[("ACT", "574")][1]: chk.append("%s: the RAM's data moved %.1f ns after the read latch's clock" % (what, after - te))


def window(d, count0, corner, step=STEP_SLOT, phases=32, direct=False, addr=None):
    """the window in slot mode (GFX-ON = 1, the picture from page 0 while the CPU works on page 1) or in direct mode:
    a write and two reads at every phase of the count. addr: the address's delay from the step's edge, for a register
    that was counted (BUS_COUNTED) where the bus's own figure is a register selected"""
    s = build(d, count0, corner); chk = []
    if addr: s.bus = dict(s.bus, addr=addr)
    ram = s.parts["IC28"]
    clock(s, 40)
    # the CPU's page is the one not shown (slot mode), and two planes in turn: between them every two of the five
    # bits PLANE0-3 and CPAGE differ once, so two of them crossed would show
    cpage = 0 if direct else 1
    mode = (0 if direct else 0x40) | cpage << 4
    plane = 5
    out_port(s, 12, mode | plane)
    crtc = s.parts["IC10"]
    shown = [0x000, 0x155, 0x2AA, 0x3FF]
    n0 = len(crtc.log); wrote = []; reads = []
    for p in range(phases):
        if p == phases // 2: plane = 3; out_port(s, 12, mode | plane)
        off = 0x123 + 37 * p & 0x7FF; val = 0x5A ^ (p * 29 & 255)
        if not crtc.script: crtc.script = [{"ma": shown[i % 4] ^ (i >> 2 & 0x3F), "ra": 5, "de": 1, "tag": 1} for i in range(64)]
        t0 = phase_time(s, p * COUNT / phases, s.t + 30.0)
        end = mem_write(s, 0xD800 | off, val, step, t0)
        clock_to(s, end + 10.0)
        wrote.append((gaddr(cpage, plane, off), val))
        for a, expect in ((off, val), (off ^ 0x400, None)):         # the byte written; one never written
            if expect is None: expect = ram.default(gaddr(cpage, plane, a))
            got = []
            t1 = phase_time(s, p * COUNT / phases, s.t + 30.0)
            end = mem_read(s, 0xD800 | a, step, t1, got)
            clock_to(s, end + 10.0)
            reads.append((p, a, expect, got[0]))
            if not direct: read_margins(s, t1 + step - s.bus["take"], chk, "phase %d" % p)
    got_w = [(a, v) for _, a, v in ram.wrote]
    if sorted(set(got_w)) != sorted(set(wrote)) or [x for i, x in enumerate(got_w) if i == 0 or x != got_w[i - 1]] != wrote:
        chk.append("the RAM was written %s..., not %s..." % ([(hex(a), hex(v)) for a, v in got_w[:6]], [(hex(a), hex(v)) for a, v in wrote[:3]]))
    bad = [(p, a, e, g) for p, a, e, g in reads if g[0] != e]
    for p, a, e, g in bad[:4]: chk.append("phase %d: read %s at offset %03X, not %02X" % (p, "nothing" if g[0] is None else "%02X" % g[0], a, e))
    if bad: chk.append("%d of %d reads wrong" % (len(bad), len(reads)))
    s.note("read byte before its take", min(g[1] for p, a, e, g in reads), "the bus steady, the least of %d reads" % len(reads))
    # the picture went on (slot mode), or nothing of the layer was shown (direct mode)
    clock_to(s, s.t + 4 * COUNT)
    for t, c in crtc.log[n0:]:
        e = edge_of(s, t)
        if e + 44 >= s.nck: continue
        text, graf, mix = want(s, c)
        if stream(s, "GDOT", e + 27, 16) != graf: chk.append("the picture during the window's work: count MA %03X: %r, not %r" % (c["ma"], stream(s, "GDOT", e + 27, 16), graf)); break
        if stream(s, "TDOT", e + 27, 16) != text: chk.append("the text during the window's work: count MA %03X: %r, not %r" % (c["ma"], stream(s, "TDOT", e + 27, 16), text)); break
        if stream(s, "VG", e + 28, 16) != mix: chk.append("the picture during the window's work: count MA %03X on the guns" % c["ma"]); break
    return finish(s, chk)


def switching(d, count0, corner, phases=32):
    """direct mode and back at every phase of the count: nothing is written; then what direct mode wrote is shown"""
    s = build(d, count0, corner); chk = []
    ram = s.parts["IC28"]
    clock(s, 40)
    t1 = mem_write(s, 0xD800 | 0x2AA, 0xC3, STEP_DIRECT, s.t + 50.0); clock_to(s, t1 + 10.0)      # plane 0, page 0, offset 2AA
    n = len(ram.wrote)
    if [(a, v) for _, a, v in ram.wrote] != [(gaddr(0, 0, 0x2AA), 0xC3)]: chk.append("direct mode wrote %r" % ram.wrote)
    for p in range(phases):
        for v in (0x40, 0x00):
            t0 = phase_time(s, p * COUNT / phases, s.t + 10.0); clock_to(s, t0)
            out_port(s, 12, v)
    if len(ram.wrote) != n: chk.append("switching the mode wrote the RAM %d times: %r" % (len(ram.wrote) - n, [(hex(a), hex(v)) for _, a, v in ram.wrote[n:n + 4]]))
    out_port(s, 12, 0x40)
    show(s, line((0x155, 0x000), 0), chk, "what direct mode wrote")
    return finish(s, chk)


def ports(corner):
    s = build(D6845_MAX, 1, corner); chk = []
    clock(s, 40)
    names = {"CTL1CK": ("-IO-WR", 12), "CTL2CK": ("-IO-WR", 15), "STATOE#": ("-IO-RD", 12), "CMDCK": ("-IO-WR", 13),
             "PSTOE#": ("-IO-RD", 13), "PDOE#": ("-IO-RD", 14)}
    for port in range(16):
        for strobe in ("-IO-WR", "-IO-RD"):
            for i in range(4): s.force("IO-ADDR%d" % i, port >> i & 1)
            clock_to(s, s.t + 2 * STEP_IO); s.force(strobe, 0); clock_to(s, s.t + STEP_IO)
            for net, (st, pt) in names.items():
                if s.val[net] != (0 if (strobe, port) == (st, pt) else 1): chk.append("%s port %X: %s is %r" % (strobe, port, net, s.val[net]))
            if s.val["CRTCCS#"] != (0 if port in (10, 11) else 1): chk.append("%s port %X: the 6845's -CS is %r" % (strobe, port, s.val["CRTCCS#"]))
            if s.val["CRTCE"] != 1: chk.append("%s port %X: the 6845's E is %r in the strobe" % (strobe, port, s.val["CRTCE"]))
            s.force(strobe, 1); clock_to(s, s.t + STEP_IO)
            if s.val["CRTCE"] != 0: chk.append("the 6845's E is %r between strobes" % s.val["CRTCE"])
    for port, value, nets in ((12, 0xA5, N.CTL1), (15, 0xCB, N.CTL2), (12, 0x5A, N.CTL1), (15, 0x24, N.CTL2)):
        out_port(s, port, value)
        got = [s.val[n] if n else value >> i & 1 for i, n in enumerate(nets)]
        if got != [value >> i & 1 for i in range(8)]: chk.append("OUT port %X, %02X: the register holds %r" % (port, value, got))
    out_port(s, 12, 0); out_port(s, 15, 0)
    b = in_port(s, 12)
    if b[0] != 0 or b[3] != 0 or b[4:] != [1, 1, 1, 0]: chk.append("the status reads %r: bit 0 = 0, TEXT-ONLY 0 and the ID 0111 wanted" % b)
    for addr, txt, gs in ((0xD000, 0, 0), (0xD7FF, 0, 0), (0xD800, 1, 1), (0xDFFF, 1, 1), (0xC800, 1, 0), (0xE000, 1, 0), (0x5800, 1, 0)):
        for i in range(16): s.force("ADDR%d" % i, addr >> i & 1)
        clock_to(s, s.t + 200.0)
        if s.val["TXTCE#"] != txt or s.val["GSEL"] != gs: chk.append("address %04X: the text RAM's -CE %r, the window's select %r" % (addr, s.val["TXTCE#"], s.val["GSEL"]))
    return finish(s, chk)


def syncs(d, corner):
    s = build(d, 1, corner); chk = []
    clock(s, 40)
    def frame():
        crtc = s.parts["IC10"]; n0 = len(crtc.log)
        # a "line" is 6 counts here, HSYNC in its fifth; VSYNC rises with a line's first count and lasts 5 lines
        crtc.script = [{"ma": 0, "ra": 0, "de": 0, "hs": int(i % 6 == 4), "vs": int(12 <= i < 42), "tag": i} for i in range(60)]
        clock_to(s, s.t + 66 * COUNT)
        return {c["tag"]: edge_of(s, t) + 16 for t, c in crtc.log[n0:]}    # the stage has a count 15 dots after it began
    for polh, polv in ((0, 0), (1, 1)):
        out_port(s, 15, polh << 2 | polv << 3)
        at = frame()
        hs = lambda i: s.samples[at[i] + 6]["HSB"] ^ polh             # 0 in the pulse (negative), in the middle of a count
        vs = lambda i: s.samples[at[i] + 6]["VSB"] ^ polv
        if [hs(i) for i in range(2, 12)] != [1, 1, 0, 1, 1, 1, 1, 1, 0, 1]: chk.append("HSYNC at the connector (polarity bit %d): %r" % (polh, [hs(i) for i in range(2, 12)]))
        got = [vs(i) for i in range(10, 46)]
        # VSYNC rises in count 12; HSYNC's rises after it are counts 16 and 22: the pulse is counts 12-21
        if got != [1, 1] + [0] * 10 + [1] * 24: chk.append("VSYNC at the connector (polarity bit %d): %r" % (polv, got))
    return finish(s, chk)


def limit(direct, corner="max", lo=120.0, hi=900.0, addr=None):
    """the shortest microcode step at which the window's write and reads work at every phase: a binary search"""
    ok = lambda step: not window(D6845_MAX, 1, corner, step=step, phases=128, direct=direct, addr=addr)
    while hi - lo > 4.0:
        mid = (lo + hi) / 2
        if ok(mid): hi = mid
        else: lo = mid
    return hi


def faults():
    """the check checked: wiring faults put into the netlist in memory, one at a time, each of which a run must report.
    Returns the names of those that passed unnoticed"""
    good = copy.deepcopy(N.NETS)
    def move(pin, to):
        ref, p = pin.split(".")
        for pins in N.NETS.values():
            if (ref, p) in pins: pins.remove((ref, p))
        N.NETS.setdefault(to, []).append((ref, p))
    def swap(a, b):
        na, nb = ([k for k, pins in N.NETS.items() if tuple(x.split(".")) in pins][0] for x in (a, b))
        move(a, nb); move(b, na)
    D = D6845_MAX
    pic, win, txo = (lambda: picture(D, 1, "max")), (lambda: window(D, 1, "max")), (lambda: text_only(D, 1, "max"))
    cases = [
        ("two character generator bits crossed at the text shifter", lambda: swap("IC19.4", "IC19.16"), pic),
        ("two code bits crossed at the character generator", lambda: swap("IC18.6", "IC18.5"), pic),
        ("two scan-line bits crossed at the character generator", lambda: swap("IC18.10", "IC18.9"), pic),
        ("two stage bits crossed at the text RAM (SA7, SA8)", lambda: swap("IC14.14", "IC14.15"), pic),
        ("the cursor's half taken from D3, not NOT D3", lambda: move("IC22.4", "D3"), pic),
        ("the load not gated by DE", lambda: move("IC21.5", "PU"), pic),
        ("the half (D3) missing from the graphics address", lambda: move("IC24.2", "GND"), pic),
        ("two scan-line bits crossed at the mux (RA0, RA1)", lambda: swap("IC26.14", "IC27.2"), pic),
        ("the display page bit not wired to the mux (CPAGE on both)", lambda: move("IC27.14", "CPAGE"), pic),
        ("XOR mode not wired", lambda: move("IC38.5", "GND"), pic),
        ("the green gun's off bit on the blue gate", lambda: swap("IC39.9", "IC39.12"), pic),
        ("the mux's first section's inputs crossed", lambda: swap("IC24.2", "IC24.3"), win),
        ("two plane bits crossed at the mux (PLANE0, PLANE1)", lambda: swap("IC26.13", "IC27.3"), win),
        ("PLANE3 and CPAGE crossed at the mux", lambda: swap("IC27.10", "IC27.13"), win),
        ("the two page bits crossed at the mux", lambda: swap("IC27.13", "IC27.14"), win),
        ("the RAM's -OE not held off in a write slot", lambda: move("IC38.1", "GND"), win),
        ("the read latch clocked a dot early", lambda: move("IC30.11", "WEP#"), win),
        ("the write pulse following the strobe, not WRQ", lambda: move("IC37.9", "GWR"), win),
        ("no direct mode in the mux select", lambda: move("IC36.2", "GND"), lambda: window(D, 1, "max", step=STEP_DIRECT, direct=True)),
        ("WRQ preset, not cleared, in direct mode", lambda: (move("IC34.4", "GFXON"), move("IC34.1", "PU")), lambda: switching(D, 1, "max")),
        ("HSYNC not inverted before its polarity gate", lambda: move("IC22.9", "SHS"), lambda: syncs(D, "max")),
        ("VSYNC not cut short", lambda: move("IC36.13", "GND"), lambda: syncs(D, "max")),
        ("the text-only build's pull-down on GDOT missing", lambda: move("R8.1", "GND"), txo)]
    missed = []
    quiet = E.VERBOSE; E.VERBOSE = False
    try:
        for name, brk, run in cases:
            N.NETS.clear(); N.NETS.update(copy.deepcopy(good))
            brk()
            with contextlib.redirect_stdout(io.StringIO()):      # a run that fails prints its measurements
                out = run()
            if not out: missed.append(name)
    finally:
        N.NETS.clear(); N.NETS.update(good); E.VERBOSE = quiet
    return len(cases), missed


SUMMARY = {}
def collect(s_margin):
    for k, (slack, where) in s_margin.items():
        if k not in SUMMARY or slack < SUMMARY[k][0]: SUMMARY[k] = (slack, where)


_finish = E.finish
def _finish_and_collect(s, name, checks):
    collect(s.margin)
    return _finish(s, name, checks)
E.finish = _finish_and_collect


def main():
    fails = 0
    runs = [("ports, parts slow", ports, ("max",)), ("ports, parts fast", ports, ("min",))]
    for cn, d, corner, phases in (("6845 slow, parts slow", D6845_MAX, "max", (1, 6)), ("6845 slow, parts fast", D6845_MAX, "min", (1,)),
                                  ("6845 fast, parts slow", D6845_MIN, "max", (1,)), ("6845 fast, parts fast", D6845_MIN, "min", (1, 6)),
                                  ("6845 slow, rises fast, falls slow", D6845_MAX, "rise", (1,)), ("6845 slow, rises slow, falls fast", D6845_MAX, "fall", (1,)),
                                  ("6845 fast, rises fast, falls slow", D6845_MIN, "rise", (1,)), ("6845 fast, rises slow, falls fast", D6845_MIN, "fall", (1,))):
        for c0 in phases:
            runs.append(("the picture, %s, counter from %d" % (cn, c0), picture, (d, c0, corner)))
        runs.append(("the window in slot mode at 3.5 MHz, %s" % cn, window, (d, 1, corner)))
        runs.append(("the window in direct mode at 6 MHz, %s" % cn, lambda d, c0, corner: window(d, c0, corner, step=STEP_DIRECT, direct=True), (d, 1, corner)))
        runs.append(("switching the mode, %s" % cn, switching, (d, 1, corner)))
        runs.append(("the text-only build, %s" % cn, text_only, (d, 1, corner)))
    runs += [("the syncs, parts slow", syncs, (D6845_MAX, "max")), ("the syncs, parts fast", syncs, (D6845_MIN, "min")),
             ("the window in slot mode at 1 MHz, parts slow", lambda: window(D6845_MAX, 1, "max", step=2000.0, phases=16), ()),
             ("the window in direct mode at 1 MHz, parts slow", lambda: window(D6845_MAX, 1, "max", step=2000.0, phases=16, direct=True), ()),
             # 160 phases of a count, 4 ns apart: the worst one for a read lies between the 32 of the runs above
             ("the window in slot mode at 3.5 MHz, 160 phases, parts slow", lambda: window(D6845_MAX, 1, "max", phases=160), ()),
             # a stack or a BRVR vector table in the window: the address comes later (the design review's V4-4)
             ("slot mode at 2.8 MHz, the address counted within the window", lambda: window(D6845_MAX, 1, "max", step=2000.0 / 2.8, phases=64, addr=BUS_COUNTED[0]), ()),
             ("slot mode at 2.8 MHz, the address counted into the window", lambda: window(D6845_MAX, 1, "max", step=2000.0 / 2.8, phases=64, addr=BUS_COUNTED[1]), ())]
    for name, f, args in runs:
        out = f(*args)
        print("%-66s %s" % (name, "PASS" if not out else "FAIL"))
        for x in out[:12]: print("    " + x)
        fails += bool(out)
    print("the closest margins over all runs (ns to spare):")
    for k in sorted(SUMMARY, key=lambda k: SUMMARY[k][0])[:18]: print("    %-28s %7.1f   %s" % (k, SUMMARY[k][0], SUMMARY[k][1]))
    if "--faults" in sys.argv:
        keep = dict(SUMMARY)
        n, missed = faults()
        SUMMARY.clear(); SUMMARY.update(keep)
        print("wiring faults put into the netlist: %d of %d noticed%s" % (n - len(missed), n, "".join("\n    NOT NOTICED: " + m for m in missed)))
        fails += bool(missed)
    if "--limits" in sys.argv:
        for direct, name, addr in ((False, "slot mode, a register selected", None), (True, "direct mode, a register selected", None),
                                   (False, "slot mode, the address counted within the window", BUS_COUNTED[0]),
                                   (False, "slot mode, the address counted into the window", BUS_COUNTED[1])):
            st = limit(direct, addr=addr)
            print("the window in %s, parts slow: the shortest step %.0f ns, a CPU clock of %.2f MHz" % (name, st, 2000.0 / st))
    print("v40_netsim: %d failed" % fails)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
