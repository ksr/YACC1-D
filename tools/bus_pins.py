#!/usr/bin/env python3
# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""bus_pins.py - the YACC1 bus connector's pinout, one line for each of its 96 pins:

    X1 A3 ADDR0

read from the bus's canonical schematic, the Bus Template V3.2 (hardware/bus/bus-template/eagle/v3.2/Bus Template
V3.2.sch; docs/system/BUS.md section 3 is the same table, with who drives each line). It is what pcb-check compares
a new card's bus connector with before an order: in the card's pcb-check.ini,

    bus_pins = python3 ../../../../../tools/bus_pins.py

A card's own connector may carry another reference: bus_pins.py --ref J1.

The template's connector is the part X1 (library con-vg, FABC96R); a pin's pad comes from the library's connects
(gate and pin -> pad), a pad's signal from the net its pin is on. Plain Python, no KiCad."""
import os, sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "hardware", "bus", "bus-template", "eagle", "v3.2", "Bus Template V3.2.sch")
CONNECTOR = "X1"


def pinout(path=TEMPLATE):
    """{pad: signal} of the template's bus connector"""
    root = ET.parse(path).getroot()
    part = next(p for p in root.iter("part") if p.get("name") == CONNECTOR)
    lib = next(x for x in root.iter("library") if x.get("name") == part.get("library"))
    dset = next(x for x in lib.iter("deviceset") if x.get("name") == part.get("deviceset"))
    dev = next(x for x in dset.iter("device") if x.get("name") == (part.get("device") or ""))
    pad = {(c.get("gate"), c.get("pin")): c.get("pad") for c in dev.iter("connect")}
    out = {}
    for net in root.iter("net"):
        for pr in net.iter("pinref"):
            if pr.get("part") == CONNECTOR:
                out[pad[(pr.get("gate"), pr.get("pin"))].upper()] = net.get("name")
    return out


def main():
    ref = sys.argv[sys.argv.index("--ref") + 1] if "--ref" in sys.argv else CONNECTOR
    pins = pinout()
    if len(pins) != 96:
        sys.exit("bus_pins: %d pins of the connector are on nets in the template, not 96" % len(pins))
    for p in sorted(pins, key=lambda p: (p[0], int(p[1:]))):
        print(ref, p, pins[p])


if __name__ == "__main__":
    main()
