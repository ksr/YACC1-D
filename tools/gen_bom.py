#!/usr/bin/env python3
"""gen_bom.py - bills of material for the YACC1 from the ACTIVE Eagle schematics (2026-09-23).

Parses the <part> elements of every schematic that is in the machine (docs/system/MACHINE.md, hardware/FABRICATED.md)
plus the three bench boards, and writes docs/bom/:

    docs/bom/<board>.md   every part (designator, value, device, package, library, Eagle technology) sorted by
                          designator; the same parts grouped by value+package with quantities, for ordering; and a
                          count of ICs / passives / connectors / others
    docs/bom/README.md    the consolidated bill across the machine (quantity per value+package, which boards use it;
                          the two index-register cards count twice; the bench boards listed separately) and the list
                          of boards covered with their schematic paths and part counts

Facts come only from the schematic XML: <part name= library= deviceset= device= value= technology=>. The package is
looked up in the schematic's embedded <libraries> (deviceset/device -> package). A part without a package (supply
symbols GND/VCC/+5V, frames) is not a part and is skipped. A missing value falls back to the deviceset with the Eagle
technology substituted for its '*' (74*244 + LS -> 74LS244); when the schematic gives no technology the '*' is left in
place rather than guessed. Boards are listed in BOARDS below - edit that table when the machine changes.

    python3 tools/gen_bom.py            regenerate docs/bom/ (idempotent apart from the generation date line)
    python3 tools/gen_bom.py --check    regenerate into a temp dir and diff against docs/bom/ (exit 1 on a difference)
"""
import os, re, sys, time, glob, shutil, tempfile, collections, difflib
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs/bom")
TOOL = "tools/gen_bom.py"

# (key, title, schematic path relative to the repo, role, copies, note)
# role: "machine" = on the bus in the machine; "bench" = bring-up / test boards plugged in only for sessions.
# Source of the list: docs/system/MACHINE.md "Cards on the bus" and hardware/FABRICATED.md "In the machine".
BOARDS = [
    ("backplane",        "Backplane V2.0",                 "hardware/bus/backplane/eagle/v2.0/yacc2buss.sch",                                    "machine", 1, "8 slots, Bus Template V3.2 signal names"),
    ("sequencer-logic",  "Sequencer logic v2.1",           "hardware/cards/sequencer-logic/eagle/v2.1/Sequencer-Logic-Prod-V2.1l.sch",           "machine", 1, "the 218 mm 'V2.1l' board"),
    ("sequencer-memory", "Sequencer memory V2.1",          "hardware/cards/sequencer-memory/eagle/v2.1/Sequencer-Memory-V2.1.sch",               "machine", 1, "microcode RAM/EEPROM + ATmega328 loader; IC9 takes the EEPROM adaptor"),
    ("eeprom-adaptor",   "Sequencer EEPROM adaptor",       "hardware/cards/sequencer-memory/accessories/eeprom-adaptor/eeprom adaptor.sch",      "machine", 1, "plugs into IC9 of the sequencer-memory card, two 24Cxx"),
    ("alu",              "ALU V3.2",                       "hardware/cards/alu/eagle/v3.2/ALU V3.2.sch",                                         "machine", 1, ""),
    ("register",         "Index Registers 1.1",            "hardware/cards/register/eagle/v1.1/Index Registers - 1.1.sch",                       "machine", 2, "two cards: R0-R3 and R4-R7 (J3 selects the card)"),
    ("io",               "I/O V1.1",                       "hardware/cards/io/eagle/v1.1/IO V1.1.sch",                                           "machine", 1, "UART, switch/LED port, TIL311s, LCD"),
    ("memory",           "Memory v1.3 (built card, Fusion export)", "hardware/cards/memory/eagle/v1.3/Memory V1.3.sch", "machine", 1, "two 62256 + 28C64, FORCE-ROM remap, TMP registers, IC15 buffer enable; eagle/deprecated/v1.3-do-not-use is an earlier save"),
    ("video",            "Video V1.0 (Fusion export)",     "hardware/cards/video/eagle/v1.0-fusion-export-2026-09-18/Video_1.0.sch",             "machine", 1, "installed for bring-up, 6845 socket empty (MACHINE.md); KiCad v1.1 is the design master"),
    ("bus-tester",       "Bus Test Card v1.1",             "hardware/cards/bus-tester/eagle/v1.1/tester.sch",                                    "bench",   1, "plugged in for bring-up sessions"),
    ("mem-switch",       "Mem Switch V1.1 (bring-up)",     "hardware/cards/mem-switch/eagle/v1.1/Mem Switch V1.1.sch",                           "bench",   1, "16-byte switch ROM at $0000"),
    ("mem-register",     "Mem Register V1.0 (bring-up)",   "hardware/cards/mem-register/eagle/v1.0/Mem Register V1.0.sch",                       "bench",   1, "16-byte RAM at $0010"),
]

# Classification by Eagle library / package (designators are not regular enough: the mem-switch DIP switches are
# named 0000..1111, the I/O LEDs 0..7, the sequencer LEDs FAULT/READY/LOADING).
IC_LIBS = {"74xx-us", "74xx-eu", "74ttl-din", "40xx", "atmel", "cdp", "exar", "maxim", "memory", "memory-hitachi",
           "memory-idt", "memory-nec", "micro-motorola", "microchip", "SparkFun-DigitalIC", "linear", "st-microelectronics"}
IC_PKG = re.compile(r"^(DIL|DIP|PDIP|SO|SOIC|SOP|SSOP|TSSOP|PLCC|LCC|TQFP|QFP)", re.I)
PASSIVE_LIBS = {"rcl", "resistor", "resistor-net", "resistor-sil", "SparkFun-Capacitors", "eagle-ltspice", "capacitor",
                "SparkFun-Resistors", "diode"}
PASSIVE_SET = re.compile(r"^(R|C|RN|RNX\d*|L|CPOL|CAP|RES|RESISTOR|CAPACITOR|DIODE)([-_]|$)", re.I)   # adafruit's R-US_, C-US_, ...
CONN_LIBS = {"con-vg", "con-lstb", "con-subd", "pinhead", "pinhead_3row", "Connector", "SparkFun-Connectors", "jumper", "wirepad",
             "con-amp", "con-molex"}


def classify(lib, deviceset, package):
    if lib in IC_LIBS or IC_PKG.match(package or ""):
        return "IC"
    if lib in CONN_LIBS:
        return "connector"
    if lib in PASSIVE_LIBS or PASSIVE_SET.match(deviceset):
        return "passive"
    return "other"          # LEDs, switches, crystals, displays, the ATmega socket's crystal, ...


def natural_key(name):
    return [(0, int(t)) if t.isdigit() else (1, t.lower()) for t in re.split(r"(\d+)", name)]


def read_parts(path):
    """-> list of dicts for every part with a package, plus the count of package-less symbols skipped."""
    root = ET.parse(path).getroot()
    devices = {}
    for lib in root.findall(".//libraries/library"):
        for ds in lib.findall("devicesets/deviceset"):
            for d in ds.findall("devices/device"):
                devices[(lib.get("name"), ds.get("name"), d.get("name") or "")] = d.get("package") or ""
    parts, skipped = [], 0
    for p in root.findall(".//parts/part"):
        lib, ds, dev = p.get("library") or "", p.get("deviceset") or "", p.get("device") or ""
        pkg = devices.get((lib, ds, dev), "")
        if not pkg:
            skipped += 1
            continue
        tech = p.get("technology") or ""
        value = (p.get("value") or "").strip()
        if not value:
            value = ds.replace("*", tech) if tech else ds
        parts.append({"name": p.get("name"), "value": value, "deviceset": ds, "device": dev, "package": pkg,
                      "library": lib, "technology": tech, "kind": classify(lib, ds, pkg)})
    parts.sort(key=lambda x: natural_key(x["name"]))
    return parts, skipped, root.get("version") or "?"


def md(s):
    return (s or "").replace("|", "\\|")


def group(parts):
    g = collections.OrderedDict()
    for p in parts:
        g.setdefault((p["value"], p["package"]), []).append(p["name"])
    return sorted(g.items(), key=lambda kv: (-len(kv[1]), kv[0][0].lower(), kv[0][1]))


def board_page(key, title, sch, role, copies, note, parts, skipped, eagle_version, date):
    counts = collections.Counter(p["kind"] for p in parts)
    L = []
    L.append("# BOM: %s\n" % title)
    L.append("GENERATED by `%s` on %s from `%s` (Eagle %s) - do not edit; edit the schematic and re-run `make bom`.  " % (TOOL, date, sch, eagle_version))
    L.append("Role: %s%s.%s\n" % (role, " x%d in the machine" % copies if copies > 1 else "", (" " + note + ".") if note else ""))
    L.append("%d parts (%d ICs, %d passives, %d connectors/headers/jumpers, %d others); %d supply/frame symbols skipped. "
             "Value = the schematic's value attribute, or the deviceset with the Eagle technology substituted for `*` "
             "(a `*` left in a value means the schematic names no technology: the part number was never filled in)."
             % (len(parts), counts["IC"], counts["passive"], counts["connector"], counts["other"], skipped))
    L.append("")
    L.append("## Parts by designator\n")
    L.append("| Designator | Value | Device (deviceset/device) | Package | Library | Technology | Class |")
    L.append("|---|---|---|---|---|---|---|")
    for p in parts:
        dev = p["deviceset"] + ("/" + p["device"] if p["device"] else "")
        L.append("| %s | %s | %s | %s | %s | %s | %s |" % (md(p["name"]), md(p["value"]), md(dev), md(p["package"]), md(p["library"]), md(p["technology"]), p["kind"]))
    L.append("")
    L.append("## Order list (value + package)\n")
    L.append("| Qty | Value | Package | Designators |")
    L.append("|---|---|---|---|")
    for (value, pkg), names in group(parts):
        L.append("| %d | %s | %s | %s |" % (len(names), md(value), md(pkg), md(", ".join(names))))
    # values that differ only in case, spaces or comma-vs-dot are almost always typos in the schematic (".1uf" vs ",1uf")
    norm = collections.defaultdict(set)
    for p in parts:
        norm[(p["value"].lower().replace(",", ".").replace(" ", ""), p["package"])].add(p["value"])
    dup = [sorted(v) for v in norm.values() if len(v) > 1]
    if dup:
        L.append("")
        L.append("Values in this schematic that differ only in case, spacing or comma-vs-dot (probably the same part, check the schematic): " +
                 "; ".join(" / ".join("`%s`" % x for x in d) for d in dup) + ".")
    L.append("")
    return "\n".join(L) + "\n"


def readme(boards, date):
    L = []
    L.append("# Bills of material - YACC1\n")
    L.append("GENERATED by `%s` on %s from the active Eagle schematics - do not edit; `make bom` regenerates this folder, "
             "`python3 %s --check` verifies it. Which revision is active comes from `docs/system/MACHINE.md` and "
             "`hardware/FABRICATED.md` (the table `BOARDS` in the tool).\n" % (TOOL, date, TOOL))
    L.append("Supply symbols and frames are not parts and are skipped. A `*` left in a value means the schematic names no Eagle "
             "technology for that deviceset (the exact part number is not in the tree). Every count is what the schematic draws; "
             "whether a socket is populated (the video card's 6845 is not, `docs/system/MACHINE.md`) is not in the schematic.\n")
    L.append("## Boards covered\n")
    L.append("| Board | Role | Copies | Schematic | Parts | ICs | Passives | Connectors | Others | Page |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for b in boards:
        c = collections.Counter(p["kind"] for p in b["parts"])
        L.append("| %s | %s | %d | `%s` | %d | %d | %d | %d | %d | [%s.md](%s.md) |" % (
            b["title"], b["role"], b["copies"], b["sch"], len(b["parts"]), c["IC"], c["passive"], c["connector"], c["other"], b["key"], b["key"]))
    L.append("")
    L.append("Not covered (not in the machine): the bus jumper boards (obsolete, not fitted), Blank V3.1/V3.2 and the bus template "
             "(templates), Bus Tester V3.1 (never ordered), the protocard, Address+TMP (retired 2021) and every `deprecated/` revision - "
             "see `hardware/FABRICATED.md`.\n")
    for role, heading, blurb in (("machine", "Consolidated bill: the machine",
                                  "Every board on the bus, the index-register card counted twice. Quantity = sum over boards x copies."),
                                 ("bench", "Consolidated bill: bench boards",
                                  "The bus tester and the two bring-up memory cards, plugged in only for sessions; listed separately so the machine's own total stays clean.")):
        sel = [b for b in boards if b["role"] == role]
        total = collections.OrderedDict()   # (value, package) -> {board: qty}
        for b in sel:
            for (value, pkg), names in group(b["parts"]):
                total.setdefault((value, pkg), collections.OrderedDict())[b["key"]] = len(names) * b["copies"]
        rows = sorted(total.items(), key=lambda kv: (-sum(kv[1].values()), kv[0][0].lower(), kv[0][1]))
        n_parts = sum(len(b["parts"]) * b["copies"] for b in sel)
        L.append("## %s\n" % heading)
        L.append("%s %d parts on %d boards (%d board instances), %d distinct value+package lines.\n" % (
            blurb, n_parts, len(sel), sum(b["copies"] for b in sel), len(rows)))
        L.append("| Qty | Value | Package | Boards (qty each) |")
        L.append("|---|---|---|---|")
        for (value, pkg), per in rows:
            L.append("| %d | %s | %s | %s |" % (sum(per.values()), md(value), md(pkg), ", ".join("%s (%d)" % (k, q) for k, q in per.items())))
        L.append("")
    return "\n".join(L) + "\n"


def render(date):
    boards = []
    for key, title, sch, role, copies, note in BOARDS:
        path = os.path.join(ROOT, sch)
        if not os.path.exists(path):
            sys.exit("gen_bom: missing schematic %s" % sch)
        parts, skipped, ver = read_parts(path)
        boards.append({"key": key, "title": title, "sch": sch, "role": role, "copies": copies, "note": note,
                       "parts": parts, "skipped": skipped, "eagle": ver})
    files = collections.OrderedDict()
    for b in boards:
        files[b["key"] + ".md"] = board_page(b["key"], b["title"], b["sch"], b["role"], b["copies"], b["note"], b["parts"], b["skipped"], b["eagle"], date)
    files["README.md"] = readme(boards, date)
    return files


def write_all(dest, files):
    os.makedirs(dest, exist_ok=True)
    for f in glob.glob(os.path.join(dest, "*.md")):
        if os.path.basename(f) not in files:
            os.remove(f)             # a board dropped from BOARDS
    for name, text in files.items():
        with open(os.path.join(dest, name), "w") as fh:
            fh.write(text)


DATE_LINE = re.compile(r"^GENERATED by `[^`]+` on \d{4}-\d{2}-\d{2}")


def normalize(text):
    return [DATE_LINE.sub("GENERATED on <date>", l) for l in text.splitlines()]


def main():
    date = time.strftime("%Y-%m-%d")
    files = render(date)
    if "--check" in sys.argv:
        tmp = tempfile.mkdtemp(prefix="yacc1-bom-")
        try:
            write_all(tmp, files)
            bad = 0
            for name in sorted(set(files) | {os.path.basename(f) for f in glob.glob(os.path.join(OUT, "*.md"))}):
                a, b = os.path.join(OUT, name), os.path.join(tmp, name)
                if not os.path.exists(a) or not os.path.exists(b):
                    print("docs/bom/%s: %s" % (name, "MISSING from docs/bom" if not os.path.exists(a) else "STALE (no longer generated)")); bad += 1; continue
                diff = list(difflib.unified_diff(normalize(open(a).read()), normalize(open(b).read()), "docs/bom/" + name, "regenerated/" + name, lineterm="", n=1))
                if diff:
                    print("\n".join(diff[:40])); bad += 1
            print("docs/bom: %s (%d files, date line ignored)" % ("UP TO DATE" if not bad else "%d file(s) DIFFER - run `make bom`" % bad, len(files)))
            sys.exit(1 if bad else 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    write_all(OUT, files)
    for name, text in files.items():
        print("docs/bom/%-22s %6d bytes" % (name, len(text)))


if __name__ == "__main__":
    main()
