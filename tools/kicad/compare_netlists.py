#!/usr/bin/env python3
"""Prove the converted KiCad schematic matches the imported Eagle board, pad for pad.

usage: compare_netlists.py <schematic netlist .net (kicad-cli sch export netlist --format kicadsexpr)> <board .kicad_pcb>

Both sides are reduced to a partition of (reference, pad) pairs into nets; single-pin
nets (unconnected pins) and power symbols (#...) are ignored. The two partitions must be
identical. Net names are compared separately as a courtesy (Eagle auto-names like N$12
may legitimately differ).
"""
import re, sys, collections

def parse_sexpr(s):
    toks = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+', s)
    def rd(i):
        out = []
        while i < len(toks):
            t = toks[i]
            if t == "(":
                sub, i = rd(i + 1); out.append(sub)
            elif t == ")":
                return out, i + 1
            else:
                out.append(t[1:-1] if t.startswith('"') else t); i += 1
        return out, i
    return rd(0)[0]

def board_nets(path):
    board = parse_sexpr(open(path).read())[0]
    nets = collections.defaultdict(set)
    for el in board:
        if isinstance(el, list) and el and el[0] == "footprint":
            ref = next((p[2] for p in el if isinstance(p, list) and p[:2] == ["property", "Reference"]), None)
            for p in el:
                if isinstance(p, list) and p and p[0] == "pad":
                    net = next((q[1] for q in p if isinstance(q, list) and q and q[0] == "net"), None)
                    if net:
                        nets[net].add((ref, p[1]))
    return nets

def schematic_nets(path):
    s = open(path).read()
    nets = {}
    for n, body in re.findall(r'\(net\s+\(code "\d+"\)\s+\(name "([^"]+)"\)(.*?)(?=\n\t\t\(net\s|\n\t\)\n\))', s, re.S):
        nets[n] = set(re.findall(r'\(node\s+\(ref "([^"]+)"\)\s+\(pin "([^"]+)"\)', body))
    return nets

def main(netfile, pcbfile):
    K = schematic_nets(netfile); B = board_nets(pcbfile)
    norm = lambda nodes: frozenset((r, p) for r, p in nodes if not r.startswith("#"))
    Kn = {n: norm(v) for n, v in K.items() if len(norm(v)) > 1}
    Bn = {n: norm(v) for n, v in B.items() if len(norm(v)) > 1}
    Ks, Bs = set(Kn.values()), set(Bn.values())
    print("schematic: %d components, %d multi-pin nets; board: %d multi-pin nets" % (
        len(set(r for v in K.values() for r, _ in v)), len(Ks), len(Bs)))
    print("identical net groups: %d of %d" % (len(Ks & Bs), max(len(Ks), len(Bs))))
    ok = True
    for n, v in sorted(Kn.items()):
        if v not in Bs:
            ok = False; print("  ONLY IN SCHEMATIC %-10s %s" % (n, sorted(v)))
    for n, v in sorted(Bn.items()):
        if v not in Ks:
            ok = False; print("  ONLY ON BOARD     %-10s %s" % (n, sorted(v)))
    kp = set().union(*Ks) if Ks else set(); bp = set().union(*Bs) if Bs else set()
    if bp - kp: ok = False; print("  pads connected on board but not in schematic:", sorted(bp - kp))
    if kp - bp: ok = False; print("  pads connected in schematic but not on board:", sorted(kp - bp))
    renamed = [(n, next(m for m, w in Bn.items() if w == v)) for n, v in Kn.items() if v in Bs and Bn.get(n) != v]
    if renamed: print("  same connectivity, different net name:", renamed)
    print("RESULT:", "MATCH" if ok else "MISMATCH")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
