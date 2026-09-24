#!/usr/bin/env python3
"""check_netlist.py - prove the I/O card v2.0 schematic (and each placement-option board) = v1.1 + the CF section.

usage: check_netlist.py <v2.0 schematic .net> <v1.1 schematic .net> <v1.1 .kicad_pcb> [<v2.0 board .kicad_pcb> ...]
       (both .net files from: kicad-cli sch export netlist --format kicadsexpr <root .kicad_sch>)

What must hold, exactly (io_v2_netlist.expected() builds the expectation):
  schematic  every net of v1.1 is in v2.0 with the same pins and the same name, except that
               - -IO-SEL4 / -IO-SEL5 (v1.1: sheet-5 local labels) are global now and ALSO carry the CF section's pins,
               - DATA0-7, -IO-RD, -IO-WR, -RESET, VCC, GND also carry the CF section's pins,
               - nets KiCad names after a pin (Net-(...)) are compared by their pins only;
             every CF section net (io_v2_netlist.NETS) is there with exactly its pins (name /Sheet 7/<name>, or the
             shared name); there is no other net; every pin KiCad leaves unconnected is either unconnected on v1.1 or a
             documented CF no-connect, and nothing else is unconnected; every part is v1.1's (same value, footprint)
             or a CF part (value, footprint of cf_netlist.py), and nothing else.
  board      every pad of every footprint is on exactly the net the v2.0 schematic gives that pin (same names), the
             pads with no net are exactly the schematic's unconnected pins + the v1.1 pads no schematic pin names
             (mounting holes, DB9 lugs, Y1 pad 1), and the footprints are the schematic's parts with the same library
             footprints and values (v1.1 parts: the value on the v1.1 board, which is the Eagle board's).
Exit status 0 only if everything matches. Plain Python (no KiCad import).
"""
import os, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import io_v2_netlist as NL                        # noqa: E402
from compare_netlist import sparse, kids, val     # noqa: E402  (the CF card's s-expression helpers; NL put it on the path)


def read_net(path):
    root = sparse(open(path).read())[0]
    parts = {}
    for comp in kids(kids(root, "components")[0], "comp"):
        ref = val(comp, "ref")
        if not ref.startswith("#"):
            parts[ref] = (val(comp, "value"), val(comp, "footprint"))
    nets = {}
    for net in kids(kids(root, "nets")[0], "net"):
        nodes = {(val(nd, "ref"), val(nd, "pin")) for nd in kids(net, "node") if not val(nd, "ref").startswith("#")}
        if nodes:
            nets[val(net, "name")] = nodes
    return nets, parts


def auto(name):
    return name.startswith("Net-(") or name.startswith("unconnected-(")


def check_schematic(v2file, v11file):
    v11_nets, v11_parts = read_net(v11file)
    want, want_parts, want_lone, notes = NL.expected(v11_nets, v11_parts)
    got, got_parts = read_net(v2file)
    bad = []
    got_lone = set()
    for n, s in list(got.items()):
        if n.startswith("unconnected-("):
            if len(s) != 1:
                bad.append("unconnected net %s has %d pins" % (n, len(s)))
            got_lone |= s
            del got[n]
    by_pins = {frozenset(s): n for n, s in got.items()}
    matched = set()
    for n, s in want.items():
        if auto(n):
            g = by_pins.get(frozenset(s))
            if g is None:
                bad.append("net %s %s missing (by pins)" % (n, sorted(s)))
            elif not auto(g):
                bad.append("net %s is named %s in v2.0" % (n, g))
            else:
                matched.add(g)
            continue
        if n not in got:
            bad.append("net %s missing" % n)
            continue
        matched.add(n)
        if got[n] != s:
            bad.append("net %s differs: missing %s, extra %s" % (n, sorted(s - got[n]), sorted(got[n] - s)))
    for n in sorted(set(got) - matched):
        bad.append("extra net %s %s" % (n, sorted(got[n])))
    if got_lone != want_lone:
        bad.append("unconnected pins differ: should be connected %s; should be unconnected %s"
                   % (sorted(got_lone - want_lone), sorted(want_lone - got_lone)))
    for ref, vf in want_parts.items():
        if ref not in got_parts:
            bad.append("part %s missing" % ref)
        elif got_parts[ref] != vf:
            bad.append("part %s is %s, should be %s" % (ref, got_parts[ref], vf))
    for ref in sorted(set(got_parts) - set(want_parts)):
        bad.append("extra part %s" % ref)
    # summary
    cf_nets = [n for n in want if n.startswith("/%s/" % NL.CF_SHEET)]
    shared = [n for n in NL.SHARED + NL.POWER]
    npins = sum(len(s) for s in want.values())
    print("schematic: v1.1 %d parts / %d nets  +  CF section %d parts / %d own nets, %d pins joined onto %d shared nets"
          % (len(v11_parts), len(v11_nets), len(NL.PARTS), len(cf_nets),
             sum(len(v) for n, v in NL.NETS.items() if n in shared), len(shared)))
    print("           expected v2.0: %d parts, %d named/auto nets holding %d pins, %d unconnected pins (%d v1.1 + %d CF "
          "no-connect)" % (len(want_parts), len(want), npins, len(want_lone),
                           len(want_lone) - sum(len(v) for v in NL.NO_CONNECT.values()),
                           sum(len(v) for v in NL.NO_CONNECT.values())))
    for x in notes:
        print("           " + x)
    print("           KiCad v2.0 schematic: %d parts, %d nets, %d unconnected pins: %s"
          % (len(got_parts), len(got), len(got_lone), "MATCH" if not bad else "MISMATCH"))
    for x in bad:
        print("    ", x)
    return not bad, got, got_lone, got_parts


def board_parts(pcb):
    """-> ({ref: (value, footprint)}, {(ref, pad) with no net}) of a .kicad_pcb"""
    root = sparse(open(pcb).read())[0]
    parts, nonet = {}, set()
    for fp in kids(root, "footprint"):
        props = {p[1]: p[2] for p in kids(fp, "property")}
        parts[props.get("Reference")] = (props.get("Value"), fp[1])
        for pad in kids(fp, "pad"):
            if not val(pad, "net"):
                nonet.add((props.get("Reference"), pad[1]))
    return parts, nonet


def check_board(pcb, sch_nets, sch_lone, sch_parts, v11_board):
    """v11_board: the v1.1 .kicad_pcb. Its footprints keep their Eagle board values (the converted symbols carry the
    Eagle deviceset names instead, e.g. 74LS00N vs 74*00, '' vs C-US: inherited, see ../v1.1), and its pads that no
    schematic pin names (X2's four mounting holes, J1's two DB9 lugs G1/G2, Y1 pad 1 of the 4-pad can) stay netless."""
    v11_parts, v11_nonet = board_parts(v11_board)
    pinless = {rp for rp in v11_nonet if rp not in sch_lone and not any(rp in s for s in sch_nets.values())}
    root = sparse(open(pcb).read())[0]
    parts, nets, alone, bad = {}, collections.defaultdict(set), set(), []
    for fp in kids(root, "footprint"):
        props = {p[1]: p[2] for p in kids(fp, "property")}
        ref = props.get("Reference")
        parts[ref] = (props.get("Value"), fp[1])
        for pad in kids(fp, "pad"):
            num, net = pad[1], val(pad, "net")
            if (ref, num) in pinless and not net:
                continue                                      # a v1.1 pad with no schematic pin (mounting holes etc.)
            if num == "":
                bad.append("unnumbered pad on %s (net %s)" % (ref, net))
                continue
            if net and not net.startswith("unconnected-("):
                nets[net].add((ref, num))
            else:
                alone.add((ref, num))
    for n, s in sch_nets.items():
        if nets.get(n) != s:
            bad.append("net %s: board %s, schematic %s" % (n, sorted(nets.get(n, ())), sorted(s)))
    for n in sorted(set(nets) - set(sch_nets)):
        bad.append("extra board net %s" % n)
    if alone != sch_lone:
        bad.append("unconnected pads differ from the schematic: %s / %s" % (sorted(alone - sch_lone),
                                                                           sorted(sch_lone - alone)))
    for ref, (v, f) in sch_parts.items():
        want = (v11_parts[ref][0], f) if ref in v11_parts else (v, f)
        if ref in v11_parts and v11_parts[ref][1] != f:
            bad.append("v1.1 footprint %s is %s on the v1.1 board, %s in the schematic" % (ref, v11_parts[ref][1], f))
        if parts.get(ref) != want:
            bad.append("footprint %s is %s, should be %s" % (ref, parts.get(ref), want))
    for ref in sorted(set(parts) - set(sch_parts)):
        bad.append("extra footprint %s" % ref)
    print("board %s: %d footprints, %d nets / %d pads, %d unconnected pads (+ %d pinless v1.1 pads): %s"
          % (os.path.basename(pcb), len(parts), len(nets), sum(len(s) for s in nets.values()), len(alone), len(pinless),
             "MATCH" if not bad else "MISMATCH"))
    for x in bad[:30]:
        print("    ", x)
    return not bad


if __name__ == "__main__":
    ok, sn, sl, sp = check_schematic(sys.argv[1], sys.argv[2])
    oks = [check_board(p, sn, sl, sp, sys.argv[3]) for p in sys.argv[4:]]
    good = ok and all(oks)
    print("RESULT:", "MATCH (v2.0 = v1.1 + the CF section, pin for pin%s)" % (
        "; every board = the schematic" if oks else "") if good else "MISMATCH")
    sys.exit(0 if good else 1)
