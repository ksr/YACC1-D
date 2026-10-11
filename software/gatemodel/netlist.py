# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""KiCad netlist reader for the gate-level card models (2026-10-11), after the ELF repository's s5emu/netlist.py.

Reads the `reports/netlist.net` KiCad writes for a card (tools/eagle_to_kicad_all.py made the YACC1 ones) and gives:
  parts   {ref: Part(ref, value, lib)}         lib = the KiCad lib part name, e.g. 74xx-us_74x08_N_pwrhidden
  pins    {(ref, pin): (net, function)}        function = the pin's name in the symbol (I0, ~{CER}, RS, ...)
  pintype {(ref, pin): type}                   input, output, tri_state, open_collector, passive, power_in ...
  nets    {net: [(ref, pin), ...]}

The schematic's netlist is not always the board: board() applies the board's own connections where a card's
`netlist-compare.txt` (tools/kicad/compare_netlists.py) lists a net group "ONLY ON BOARD". Reworks and settings are
edits on the netlist, so they stay data a photo or a meter can correct:
  lift(ref, pin)                     the pin is bent out of its socket: it leaves its net (it floats)
  wire(ref, pin, to_ref, to_pin)     a wire from the pin to another pin: it joins that pin's net
  short(net_a, net_b)                a wire between two nets: they become one (net_a keeps its name)
  jumper(ref_a, pin_a, ref_b, pin_b) a jumper fitted across two header pins
Every edit is recorded in `edits` with the reason given.
"""
import re
from collections import namedtuple

Part = namedtuple("Part", "ref value lib")


def _sexp(text):
    toks = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', text)
    stack = [[]]
    for t in toks:
        if t == "(": stack.append([])
        elif t == ")": x = stack.pop(); stack[-1].append(x)
        else: stack[-1].append(t[1:-1].replace('\\"', '"') if t[0] == '"' else t)
    return stack[0][0]


def _get(node, key):
    return next((x for x in node if isinstance(x, list) and x and x[0] == key), None)


class Netlist:
    def __init__(self, path):
        self.path = path
        with open(path) as f: tree = _sexp(f.read())
        self.parts = {}
        for c in _get(tree, "components")[1:]:
            lib = _get(c, "libsource")
            ref = _get(c, "ref")[1]
            self.parts[ref] = Part(ref, _get(c, "value")[1], _get(lib, "part")[1] if lib else "")
        self.pins = {}; self.pintype = {}
        for n in _get(tree, "nets")[1:]:
            name = _get(n, "name")[1]
            if name.startswith("/Sheet"): name = name.split("/")[-1]          # hierarchical labels: the plain name
            for node in n:
                if isinstance(node, list) and node[0] == "node":
                    ref, pin = _get(node, "ref")[1], _get(node, "pin")[1]
                    fn = (_get(node, "pinfunction") or [None, pin])[1]
                    if fn.endswith("_" + pin): fn = fn[:-len(pin) - 1]           # the converter's "O_3": "O"
                    self.pins[(ref, pin)] = (name, fn)
                    self.pintype[(ref, pin)] = (_get(node, "pintype") or [None, ""])[1].split("+")[0]
        self.edits = []

    # ------------------------------------------------------------------ queries
    @property
    def nets(self):
        out = {}
        for key, (net, _) in self.pins.items(): out.setdefault(net, []).append(key)
        return out

    def net(self, ref, pin): return self.pins[(ref, str(pin))][0]
    def function(self, ref, pin): return self.pins[(ref, str(pin))][1]

    def part_pins(self, ref):
        """{function: net} for one part (a function that repeats, like GND, keeps the last)"""
        return {fn: net for (r, _), (net, fn) in self.pins.items() if r == ref}

    def pin_of(self, ref, function):
        for (r, p), (_, fn) in self.pins.items():
            if r == ref and fn == function: return p
        raise KeyError("%s has no pin %s" % (ref, function))

    # ------------------------------------------------------------------ the board
    def board(self, compare_path):
        """apply the board's connections where they differ from the schematic: every 'ONLY ON BOARD NET [pins]' line of
        a netlist-compare.txt puts those pins on NET; its 'same connectivity, different net name' pairs give KiCad's
        generated names (Net-(IC1A-I0)) back their Eagle names (N$1), the ones the card's documents use"""
        names = {}
        for line in open(compare_path):
            if "same connectivity, different net name" in line:
                names = dict(re.findall(r"\('([^']+)', '([^']+)'\)", line))
        for k, (net, fn) in list(self.pins.items()):
            if net.startswith("Net-(") and net in names: self.pins[k] = (names[net], fn)
        for line in open(compare_path):
            m = re.match(r"\s*ONLY ON BOARD\s+(\S+)\s+\[(.*)\]\s*$", line)
            if not m: continue
            net = m.group(1)
            for ref, pin in re.findall(r"\('([^']+)', '([^']+)'\)", m.group(2)):
                old, fn = self.pins[(ref, pin)]
                if old != net:
                    self.pins[(ref, pin)] = (net, fn)
                    self.edits.append(("board", "%s.%s is on %s on the board (the schematic: %s)" % (ref, pin, net, old),
                                       compare_path))

    # ------------------------------------------------------------------ reworks and settings
    def lift(self, ref, pin, why=""):
        pin = str(pin); net, fn = self.pins[(ref, pin)]
        self.pins[(ref, pin)] = ("lifted:%s.%s" % (ref, pin), fn)
        self.edits.append(("lift", "%s.%s (%s) lifted off %s" % (ref, pin, fn, net), why))

    def wire(self, ref, pin, to_ref, to_pin, why=""):
        pin = str(pin); to = self.net(to_ref, to_pin); fn = self.pins[(ref, pin)][1]
        self.pins[(ref, pin)] = (to, fn)
        self.edits.append(("wire", "%s.%s (%s) wired to %s.%s (%s)" % (ref, pin, fn, to_ref, to_pin, to), why))

    def short(self, net_a, net_b, why=""):
        if net_a == net_b: return
        for k, (net, fn) in self.pins.items():
            if net == net_b: self.pins[k] = (net_a, fn)
        self.edits.append(("short", "%s joined to %s" % (net_b, net_a), why))

    def jumper(self, ref_a, pin_a, ref_b, pin_b, why=""):
        a, b = self.net(ref_a, pin_a), self.net(ref_b, pin_b)
        if b in ("VCC", "GND", "+5V"): a, b = b, a                       # a supply keeps its name
        for k, (net, fn) in self.pins.items():
            if net == b: self.pins[k] = (a, fn)
        self.edits.append(("jumper", "%s.%s-%s.%s fitted (%s = %s)" % (ref_a, pin_a, ref_b, pin_b, b, a), why))

    def apply(self, edits):
        """[(op, args..., why)] as the card revisions list them"""
        for op, *args in edits: getattr(self, op)(*args)
