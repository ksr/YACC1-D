#!/usr/bin/env python3
"""compare_netlist.py - prove the generated schematic AND board implement cf_netlist.py, pin for pin.

usage: compare_netlist.py <schematic netlist .net> <board .kicad_pcb>
       (the .net from: kicad-cli sch export netlist --format kicadsexpr yacc1-cf-card.kicad_sch)

Checks, each of which must hold exactly:
  schematic  every net of cf_netlist.NETS exists in the KiCad netlist with the same name (KiCad's "/" sheet prefix on
             label nets stripped) and exactly the same (reference, pin) set; there are no other multi-pin nets; every
             other pin of every part sits alone on an "unconnected-(...)" net and is either in NO_CONNECT or an unused
             bus-connector pin; every part of PARTS is present with its value and footprint; nothing else is (power
             symbols and flags, #..., are ignored).
  board      the same for the pads of the .kicad_pcb: each net's pad set equals NETS, pads with no net are exactly the
             NO_CONNECT pins, the unused X1 pins and the two unnumbered DIN mounting holes; every footprint's value
             and library footprint match PARTS.
Exit status 0 only if both match. Plain Python (no KiCad import).
"""
import os, re, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cf_netlist as N

_TOK = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')


def sparse(s):
    toks = _TOK.findall(s); pos = [0]

    def rd():
        out = []
        while pos[0] < len(toks):
            t = toks[pos[0]]; pos[0] += 1
            if t == "(": out.append(rd())
            elif t == ")": return out
            else: out.append(t[1:-1].replace('\\"', '"') if t.startswith('"') else t)
        return out
    return rd()


def kids(lst, key):
    return [x for x in lst if isinstance(x, list) and x and x[0] == key]


def val(lst, key, default=None):
    k = kids(lst, key)
    return k[0][1] if k and len(k[0]) > 1 else default


SYM_SUB = {"Device:CP": "Device:C_Polarized"}
WANT = {n: set(c) for n, c in N.NETS.items()}
NCSET = {(r, p) for r, ps in N.NO_CONNECT.items() for p in ps}
X1_USED = {p for n, c in N.NETS.items() for r, p in c if r == "X1"}
X1_UNUSED = {("X1", "%s%d" % (row, k)) for row in "ABC" for k in range(1, 33)} - {("X1", p) for p in X1_USED}
ALONE_OK = NCSET | X1_UNUSED


def norm(name):
    return name[1:] if name.startswith("/") else name


def compare(kind, got_nets, alone, parts):
    """got_nets: name -> set of (ref, pin) with >= 1 member on a named net; alone: set of (ref, pin) with no net"""
    bad = []
    got = {norm(n): v for n, v in got_nets.items()}
    for n, pins in WANT.items():
        if n not in got:
            bad.append("net %s missing" % n)
        elif got[n] != pins:
            bad.append("net %s differs: missing %s, extra %s" % (n, sorted(pins - got[n]), sorted(got[n] - pins)))
    for n in sorted(set(got) - set(WANT)):
        bad.append("extra net %s %s" % (n, sorted(got[n])))
    if alone != ALONE_OK:
        bad.append("unconnected pins differ: should be connected %s; should be unconnected %s"
                   % (sorted(alone - ALONE_OK), sorted(ALONE_OK - alone)))
    for ref, (value, symid, fpid, note) in N.PARTS.items():
        if ref not in parts:
            bad.append("part %s missing" % ref); continue
        v, fp = parts[ref]
        if v != value: bad.append("%s value %r != %r" % (ref, v, value))
        if fp != fpid: bad.append("%s footprint %r != %r" % (ref, fp, fpid))
    for ref in sorted(set(parts) - set(N.PARTS)):
        bad.append("extra part %s" % ref)
    npins = sum(len(v) for v in got.values())
    print("%-9s %d parts, %d nets / %d net pins, %d unconnected pins (%d no-connect + %d unused bus pins): %s"
          % (kind, len(parts), len(got), npins, len(alone), len(NCSET), len(X1_UNUSED),
             "MATCH" if not bad else "MISMATCH"))
    for b in bad:
        print("   ", b)
    return not bad


def schematic(netfile):
    root = sparse(open(netfile).read())[0]
    parts = {}
    for comp in kids(kids(root, "components")[0], "comp"):
        ref = val(comp, "ref")
        if ref.startswith("#"): continue
        parts[ref] = (val(comp, "value"), val(comp, "footprint"))
    nets, alone = {}, set()
    for net in kids(kids(root, "nets")[0], "net"):
        name = val(net, "name")
        nodes = {(val(nd, "ref"), val(nd, "pin")) for nd in kids(net, "node") if not val(nd, "ref").startswith("#")}
        if name.startswith("unconnected-("):
            if len(nodes) != 1:
                print("    unconnected net with %d pins: %s" % (len(nodes), name))
            alone |= nodes
        elif nodes:
            nets[name] = nodes
    return compare("schematic", nets, alone, parts)


def board(pcbfile):
    root = sparse(open(pcbfile).read())[0]
    parts, nets, alone = {}, collections.defaultdict(set), set()
    for fp in kids(root, "footprint"):
        props = {p[1]: p[2] for p in kids(fp, "property")}
        ref = props.get("Reference")
        parts[ref] = (props.get("Value"), fp[1])
        for pad in kids(fp, "pad"):
            num, net = pad[1], val(pad, "net")
            if num == "":                       # the DIN connector's two unnumbered mounting holes
                if net: nets[net].add((ref, "(mounting hole)"))
                continue
            if net and not net.startswith("unconnected-("):
                nets[net].add((ref, num))
            else:
                alone.add((ref, num))
    return compare("board", nets, alone, parts)


if __name__ == "__main__":
    ok_s = schematic(sys.argv[1])
    ok_b = board(sys.argv[2])
    print("RESULT:", "MATCH (schematic and board both implement cf_netlist.py exactly)" if ok_s and ok_b else "MISMATCH")
    sys.exit(0 if ok_s and ok_b else 1)
