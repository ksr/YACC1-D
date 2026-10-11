# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""Gate-level logic for one card's bus path, built from its KiCad netlist (2026-10-11), after the ELF repository's
s5emu/logic.py.

Net values: 0, 1, X (unknown: two drivers that disagree, an undefined input, a rail with no source) and None (nothing
drives the net: it floats). A floating input reads 1 on a TTL part (LS, ALS, S) and X on an NMOS or CMOS part (the
MC6845, the IDT7134).

Every section of a chip is one Gate: an output net, its input nets, how it drives (totem-pole "tp" or open-collector
"oc", which only pulls low) and the chip's supply. Logic, by the KiCad lib part name (checked against the pin names):
  74x00 74x08 74x32 74x86   quad NAND / AND / OR / XOR, pins (1,2->3) (4,5->6) (9,10->8) (12,13->11)
  74x04                     hex inverter; 74x05 74x06 74x16 the open-collector ones (pull-ups make the high)
  74x85                     4-bit comparator with cascade inputs (A=B_O: 0 as soon as one known bit differs)
Bus devices (their control pins are read after the logic settles; their data pins are the bus DATA lines only):
  7134    IDT7134 dual-port RAM, the bus (right) port: ~{CER}, ~{OER}, R/~{WR}, A0R-A11R, I/O0R-7R
  6845    MC6845 register interface: CS (active low), E, R/~{W}, RS, D0-7
  74x373  a 74LS373 whose outputs are bus DATA lines (the video card's JP1 read-back latch): OC, ENC, 1D-8D
Passive parts: a resistor with one end on a supply is a pull of the other end (RNX4: pin 1 is the common end); a
capacitor from a net to GND with a resistor from that net to a gate output is an RC node (the 6845's E one-shot,
R1/C1): before a strobe it follows the resistor's far end, during the strobe it keeps that level (the pulse width is
timing and is not modelled).

Power: a supply net is sourced when the card's bus connector has a power pin on it; a chip whose VCC pin is on an
unsourced supply is unpowered: its outputs drive nothing (the phantom power through input clamps is analog), and a
pull to such a rail gives X.

Only the bus path is evaluated: Circuit traces back from every control and address pin of the bus devices through
the modelled gates, and refuses to build when that trace reaches the output of a part with no model, a bus DATA line
or a device's own output. So the decode is a pure function of the bus inputs it reaches (address lines, -VMA,
-MEM-RD, -MEM-WR); the character generator, dot clock and shift register stay out of it.
"""
import re

X = "X"
DRIVING = ("output", "tri_state", "bidirectional", "open_collector", "open_emitter", "power_out")


def ttl(v): return 1 if v is None else v
def mos(v): return X if v is None else v
def inv(v): return v if v == X else 1 - v


class Gate:
    """one section: out = op(ins); drive 'tp' (totem-pole), 'oc' (open collector) or 'weak' (an RC node)"""
    def __init__(self, ref, op, ins, out, drive="tp", supply=None, read=ttl):
        self.ref, self.op, self.ins, self.out, self.drive, self.supply, self.read = ref, op, ins, out, drive, supply, read
        self.hold = None                                    # an RC node in its hold phase: the level it keeps

    def value(self, val, powered):
        if not powered: return None
        a = [self.read(val.get(n)) for n in self.ins]
        op = self.op
        if op == "rc":                                      # follows its resistor's far end, or keeps its level
            return self.hold[0] if self.hold is not None else val.get(self.ins[0])
        if op in ("nand", "and"):
            r = 0 if 0 in a else 1 if all(x == 1 for x in a) else X
            return inv(r) if op == "nand" else r
        if op in ("or", "nor"):
            r = 1 if 1 in a else 0 if all(x == 0 for x in a) else X
            return inv(r) if op == "nor" else r
        if op == "xor": return X if X in a else a[0] ^ a[1]
        if op == "inv":
            r = inv(a[0])
            if self.drive == "oc": return None if r == 1 else r     # high = released
            return r
        if op.startswith("cmp85"): return _cmp85(a, op)
        raise ValueError("no logic for %s" % op)


def _cmp85(a, op):
    A, B, (lt_i, eq_i, gt_i) = a[0:4], a[4:8], a[8:11]
    if op == "cmp85_eq":
        if eq_i == 0: return 0
        if any(x != X and y != X and x != y for x, y in zip(A, B)): return 0
        if X in A or X in B: return X
        return eq_i
    if X in A or X in B or X in (lt_i, eq_i, gt_i): return X
    va = sum(v << i for i, v in enumerate(A)); vb = sum(v << i for i, v in enumerate(B))
    if va > vb: res = (0, 0, 1)
    elif va < vb: res = (1, 0, 0)
    elif eq_i == 1: res = (0, 1, 0)
    else: res = (inv(gt_i), 0, inv(lt_i))
    return res[0] if op == "cmp85_lt" else res[2]


# ---------------------------------------------------------------------------------------------- bus devices
class Device:
    kind = ""
    def __init__(self, nl, ref, read):
        self.nl, self.ref, self.read = nl, ref, read
        self.f = nl.part_pins(ref)
        self.supply = self.f.get("VCC"); self.fitted = True

    def controls(self): return []


class DualPort(Device):
    """IDT7134, the right (bus) port"""
    kind = "DPRAM"
    def __init__(self, nl, ref):
        super().__init__(nl, ref, mos); f = self.f
        self.addr = [f["A%dR" % i] for i in range(12)]; self.data = [f["I/O%dR" % i] for i in range(8)]
        self.ce, self.oe, self.rw = f["~{CER}"], f["~{OER}"], f["R/~{WR}"]
    def controls(self): return [self.ce, self.oe, self.rw]


class CRTC(Device):
    """MC6845 CPU interface: selected while CS is low; an access while E is high; R/W high = read; RS 0 = the address
    register (write-only), 1 = the register it selects"""
    kind = "CRTC"
    def __init__(self, nl, ref):
        super().__init__(nl, ref, mos); f = self.f
        self.data = [f["D%d" % i] for i in range(8)]; self.addr = []
        self.cs, self.e, self.rw, self.rs = f["CS"], f["E"], f["R/~{W}"], f["RS"]
    def controls(self): return [self.cs, self.e, self.rw, self.rs]


class BusLatch(Device):
    """74LS373 with its outputs on the bus DATA lines: drives them while OC is low, Q = D while ENC is high"""
    kind = "LATCH"
    def __init__(self, nl, ref):
        super().__init__(nl, ref, ttl); f = self.f
        self.data = [f["%dQ" % i] for i in range(1, 9)]; self.addr = []
        self.d = [f["%dD" % i] for i in range(1, 9)]; self.oc, self.enc = f["OC"], f["ENC"]
    def controls(self): return [self.oc, self.enc] + self.d


QUAD = (("3", "1", "2"), ("6", "4", "5"), ("8", "9", "10"), ("11", "12", "13"))
HEX = (("2", "1"), ("4", "3"), ("6", "5"), ("8", "9"), ("10", "11"), ("12", "13"))
QUAD_OPS = {"00": "nand", "08": "and", "32": "or", "86": "xor"}
OC_INV = ("05", "06", "16")
PASSIVE = ("rcl_C", "rcl_CPOL", "rcl_R-", "eagle-ltspice_R", "led_", "crystal_", "cdp_RCA", "con-subd", "Connector_PINHD",
           "con-lstb_MA", "resistor-net")


def chip_type(lib):
    m = re.search(r"74x(\d+)", lib)
    if m: return m.group(1)
    if "7134" in lib: return "7134"
    if "6845" in lib: return "6845"
    if "FABC96" in lib: return "bus"
    if any(lib.startswith(p) for p in PASSIVE): return None
    return "unmodelled"


class Circuit:
    """the bus path of one card. bus = {signal: (connector ref, pin)}; fitted = refs in their sockets (None = all; an
    empty socket's pins float); power_pins = the connector pins that bring the supplies"""
    def __init__(self, nl, bus, power_pins, fitted=None):
        self.nl = nl; self.bus = bus
        self.signal_net = {s: nl.net(r, p) for s, (r, p) in bus.items()}
        self.net_signal = {n: s for s, n in self.signal_net.items()}
        nets = nl.nets
        # supplies: sourced when a connector power pin is on the net
        self.power = {}
        for net in ("VCC", "+5V", "GND"):
            if net not in nets: continue
            sourced = any((r, p) in power_pins for r, p in nets[net])
            self.power[net] = (0 if net == "GND" else 1) if sourced else X
        # passives: pulls and RC nodes
        self.pulls = {}; rcs = []
        resistors = [r for r, p in nl.parts.items() if re.match(r"(rcl_R-|eagle-ltspice_R)", p.lib)]
        for ref in resistors:
            (pa, a), (pb, b) = sorted((p, n) for (r, p), (n, _) in nl.pins.items() if r == ref)
            if a in self.power and b not in self.power: self.pulls.setdefault(b, self.power[a])
            elif b in self.power and a not in self.power: self.pulls.setdefault(a, self.power[b])
        for ref, part in nl.parts.items():
            if part.lib.startswith("resistor-net"):
                common = nl.net(ref, "1")
                if common in self.power:
                    for (r, p), (n, _) in nl.pins.items():
                        if r == ref and p != "1" and not n.startswith("unconnected"): self.pulls[n] = self.power[common]
        ends = {r: [n for (r2, _), (n, _) in nl.pins.items() if r2 == r] for r in nl.parts}
        for ref, part in sorted(nl.parts.items()):
            if not part.lib.startswith("rcl_C") or len(ends[ref]) != 2 or "GND" not in ends[ref]: continue
            node = [n for n in ends[ref] if n != "GND"][0]
            if node in self.power: continue
            rs = [r for r in resistors if node in ends[r]]
            if len(rs) == 1:
                far = [n for n in ends[rs[0]] if n != node][0]
                if far not in self.power: rcs.append(Gate("%s/%s" % (rs[0], ref), "rc", [far], node, "weak"))
        # chips
        self.gates = []; self.devices = []; self.unmodelled = []; self.empty = []
        for ref, part in sorted(nl.parts.items()):
            t = chip_type(part.lib)
            if t in (None, "bus"): continue
            if fitted is not None and ref not in fitted:
                self.empty.append(ref)
                if t in ("7134", "6845"):                    # an empty socket still has its select decoded
                    d = (DualPort if t == "7134" else CRTC)(nl, ref); d.fitted = False; self.devices.append(d)
                continue
            f = nl.part_pins(ref); supply = f.get("VCC")
            if t in QUAD_OPS:
                for o, a, b in QUAD:
                    if (ref, o) in nl.pins:
                        self._check(ref, o, "O"); self._check(ref, a, "I0"); self._check(ref, b, "I1")
                        self.gates.append(Gate("%s.%s" % (ref, o), QUAD_OPS[t], [nl.net(ref, a), nl.net(ref, b)], nl.net(ref, o), "tp", supply))
            elif t == "04" or t in OC_INV:
                for o, i in HEX:
                    if (ref, o) in nl.pins:
                        self._check(ref, o, "O"); self._check(ref, i, "I")
                        self.gates.append(Gate("%s.%s" % (ref, o), "inv", [nl.net(ref, i)], nl.net(ref, o), "oc" if t in OC_INV else "tp", supply))
            elif t == "85":
                ins = [f["A%d" % i] for i in range(4)] + [f["B%d" % i] for i in range(4)] + [f["A<B_I"], f["A=B_I"], f["A>B_I"]]
                for fn, op in (("A=B_O", "cmp85_eq"), ("A<B_O", "cmp85_lt"), ("A>B_O", "cmp85_gt")):
                    if not f[fn].startswith("unconnected"): self.gates.append(Gate("%s.%s" % (ref, fn), op, ins, f[fn], "tp", supply))
            elif t == "7134": self.devices.append(DualPort(nl, ref))
            elif t == "6845": self.devices.append(CRTC(nl, ref))
            elif t == "373" and any(nl.net(ref, nl.pin_of(ref, "%dQ" % i)) in self.net_signal for i in range(1, 9)):
                self.devices.append(BusLatch(nl, ref))
            else: self.unmodelled.append(ref)
        self.gates += rcs
        self.rcs = rcs
        self.cone, self.inputs = self._trace()
        self.gates = [g for g in self.gates if g.out in self.cone]
        self.rcs = [g for g in self.rcs if g.out in self.cone]
        self.order = self._order()

    def _check(self, ref, pin, fn):
        have = self.nl.function(ref, pin)
        if have != fn: raise ValueError("%s pin %s is %s in the netlist, the model expects %s" % (ref, pin, have, fn))

    def _trace(self):
        """the nets that can change a bus device's control or address pin -> (cone, bus inputs reached); refuses a
        cone that reaches an unmodelled output, a bus DATA line or a device's own output"""
        drivers = {}
        for g in self.gates: drivers.setdefault(g.out, []).append(g)
        todo = [n for d in self.devices for n in d.controls()]
        for d in self.devices:
            for n in d.addr:
                if n not in self.power and not self.net_signal.get(n, "").startswith("ADDR"):
                    raise ValueError("%s address pin on %s: not a bus address line or a supply" % (d.ref, n))
        seen = set()
        while todo:
            net = todo.pop()
            if net in seen: continue
            seen.add(net)
            for g in drivers.get(net, []): todo.extend(g.ins)
        data = {n for d in self.devices for n in d.data}
        modelled = {g.ref.split(".")[0] for g in self.gates} | {d.ref for d in self.devices}
        bad = []
        for (ref, pin), (net, fn) in self.nl.pins.items():
            if net not in seen or net in self.power: continue
            if self.nl.pintype.get((ref, pin)) not in DRIVING: continue
            if ref in self.unmodelled or (ref not in modelled and chip_type(self.nl.parts[ref].lib) not in (None, "bus")):
                if ref not in self.empty: bad.append("%s.%s (%s, unmodelled %s)" % (ref, pin, fn, self.nl.parts[ref].value))
            elif any(d.ref == ref and d.fitted for d in self.devices) and net not in data:
                bad.append("%s.%s (%s, a bus device's own output)" % (ref, pin, fn))
        for net in seen:
            s = self.net_signal.get(net)
            if s and s.startswith("DATA"): bad.append("%s (a bus data line feeds the decode)" % s)
        if bad: raise ValueError("%s: the bus path reaches parts with no model: %s" % (self.nl.path, "; ".join(sorted(bad))))
        inputs = sorted({self.net_signal[n] for n in seen if n in self.net_signal})
        return seen, inputs

    def _order(self):
        """gates in an order where each net's drivers come before its readers (a loop is left to settle()'s passes)"""
        by_out = {}
        for g in self.gates: by_out.setdefault(g.out, []).append(g)
        out, state = [], {}

        def visit(g):
            if state.get(id(g)): return
            state[id(g)] = 1
            for n in g.ins:
                for h in by_out.get(n, []): visit(h)
            out.append(g)
        for g in self.gates: visit(g)
        return out

    def powered(self, supply):
        return supply is None or self.power.get(supply, 1) == 1

    def settle(self, bus_levels):
        """bus_levels: {signal: 0/1}. -> ({net: value}, [contention text])"""
        val = dict(self.power)
        for s, v in bus_levels.items(): val[self.signal_net[s]] = v
        fixed = set(val)
        driven = {g.out for g in self.order}
        for net, p in self.pulls.items():
            if net not in fixed and net not in driven: val[net] = p
        for _ in range(50):
            changed = False; fights = []
            by_net = {}
            for g in self.order: by_net.setdefault(g.out, []).append(g)
            for net, gs in by_net.items():
                if net in fixed: continue
                act = [(g, g.value(val, self.powered(g.supply))) for g in gs]
                strong = [(g, v) for g, v in act if v is not None and g.drive != "weak"]
                weak = [(g, v) for g, v in act if v is not None and g.drive == "weak"]
                if strong:
                    vs = {v for _, v in strong}
                    r = vs.pop() if len(vs) == 1 else X
                    tp = [g for g, _ in strong if g.drive == "tp"]; oc = [g for g, _ in strong if g.drive == "oc"]
                    if len({v for _, v in strong}) > 1 or len(tp) > 1 or (tp and oc):
                        fights.append("%s driven by %s" % (net, " + ".join("%s=%s" % (g.ref, v) for g, v in strong)))
                elif weak: r = weak[0][1]
                else: r = None
                if r is None and net in self.pulls: r = self.pulls[net]
                if val.get(net, "unset") != r: val[net] = r; changed = True
            if not changed: return val, fights
        raise RuntimeError("%s: the bus path did not settle (an oscillator in the cone?)" % self.nl.path)

    def cycle(self, levels):
        """one bus cycle: the address and -VMA first (strobes inactive), then the strobes with the RC nodes holding
        what they had. levels: {signal: 0/1} for every input. -> (values during the strobe, contention)"""
        pre = dict(levels)
        for s in ("-MEM-RD", "-MEM-WR"):
            if s in pre: pre[s] = 1
        for g in self.rcs: g.hold = None
        v1, _ = self.settle(pre)
        for g in self.rcs: g.hold = (v1.get(g.out),)
        v2, fights = self.settle(levels)
        for g in self.rcs: g.hold = None
        return v2, fights
