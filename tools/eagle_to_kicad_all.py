#!/usr/bin/env python3
"""Convert EVERY Eagle design under hardware/ (active and deprecated revisions) into a KiCad 10 project.

For each Eagle .sch/.brd pair (or a lone .sch / .brd) this makes, next to the Eagle folder,
    <item>/kicad/<rev>/            (mirrors <item>/eagle/<rev>/ ; eagle/deprecated/<rev>/ -> kicad/deprecated/<rev>/)
        <project>.kicad_pro                project (rules: OSH Park 6 mil track / 5 mil clearance / 10 mil drill / 4 mil annular)
        <project>.kicad_sch + -sheetN      schematic: tools/kicad/eagle_sch_to_kicad.py (one sub-sheet per Eagle sheet)
        <project>-eagle.kicad_sym          project symbol library (units = Eagle gates)
        <project>.kicad_pcb                board: KiCad's Eagle board reader, then tools/kicad/finish_board.py
        <project>-eagle.pretty/            project footprint library extracted from the board
        sym-lib-table, fp-lib-table
        reports/netlist.net, netlist-compare.txt   PROOF: schematic netlist vs the pad netlist embedded in the imported board
        reports/erc.json, drc.json, <project>-schematic.pdf, <project>-top.png, -bottom.png
        README.md                          what was converted, the proof result, residual ERC/DRC counts
and an index hardware/KICAD.md (with --only, just the converted designs' rows are replaced/inserted).  Designs listed in a folder's pdf/SKIP.txt (label-only duplicates) are skipped.
A kicad/<rev>/ folder holding a MASTER marker file is hand-maintained: never written by this tool, listed separately in the index.
The Eagle files are never touched. Output is regenerated from scratch on every run (deterministic converter).
usage: eagle_to_kicad_all.py [--only <substring>]   (any python3; re-executes itself under KiCad's python for pcbnew)
"""
import os, sys, subprocess, tempfile, shutil, json, re, time, collections
KPY = "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3"
KICAD = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); HW = os.path.join(ROOT, "hardware")
TK = os.path.join(ROOT, "tools", "kicad")
if os.path.realpath(sys.executable) != os.path.realpath(KPY) and "--inner" not in sys.argv:
    os.execv(KPY, [KPY, os.path.abspath(__file__), "--inner"] + sys.argv[1:])
import pcbnew
sys.path.insert(0, TK)
import finish_board
only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
SKIPWORDS = ("cards", "bus", "eagle", "kicad", "accessories")

def skipped(design):
    sk = os.path.join(os.path.dirname(design), "pdf", "SKIP.txt")
    return os.path.exists(sk) and os.path.basename(design) in [l.strip() for l in open(sk) if l.strip() and not l.startswith("#")]

def slug(s):
    return re.sub(r"-+", "-", re.sub(r"[^A-Za-z0-9.]+", "-", s)).strip("-").lower()

def designs():
    """-> list of (source dir rel HW, design base name, sch path|None, brd path|None)"""
    found = collections.defaultdict(dict)
    for r, ds, fs in os.walk(HW):
        ds[:] = [d for d in ds if d != "kicad"]
        for f in fs:
            ext = os.path.splitext(f)[1].lower()
            if ext in (".sch", ".brd"):
                p = os.path.join(r, f)
                if skipped(p) or ".old" in f.lower(): continue   # "X.brd.old.brd" = a superseded copy kept beside the real one
                found[(os.path.relpath(r, HW), os.path.splitext(f)[0])][ext[1:]] = p
    out = []
    for (rel, base), d in sorted(found.items()):
        if only and only not in os.path.join(rel, base): continue
        out.append((rel, base, d.get("sch"), d.get("brd")))
    return out

def dest_for(rel, base, shared):
    parts = rel.split(os.sep)
    parts = [("kicad" if p == "eagle" else p) for p in parts]
    if "kicad" not in parts: parts.append("kicad")
    if shared: parts.append(slug(base))
    dest = os.path.join(HW, *[slug(p) if p not in ("kicad", "deprecated") else p for p in parts])
    name_parts = [p for p in parts if p not in SKIPWORDS and p != "deprecated"]
    return dest, slug("-".join(name_parts))

def run(cmd, timeout=900):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

def import_board(brd, tmp):
    src = os.path.join(tmp, os.path.basename(brd)); shutil.copy2(brd, src)
    board = pcbnew.PCB_IO_MGR.Load(pcbnew.PCB_IO_MGR.EAGLE, src)
    if board is None: raise RuntimeError("Eagle importer returned nothing")
    dropped = 0; U = pcbnew.UNDEFINED_LAYER
    for item in list(board.GetDrawings()) + list(board.GetTracks()):
        if item.GetLayer() == U: board.Remove(item); dropped += 1
    for z in list(board.Zones()):
        if z.GetLayer() == U: z.SetLayer(pcbnew.Cmts_User); dropped += 1
    for fp in board.GetFootprints():
        for item in list(fp.GraphicalItems()):
            if item.GetLayer() == U: fp.Remove(item); dropped += 1
    bb = board.GetBoundingBox(); mv = pcbnew.VECTOR2I(pcbnew.FromMM(10) - bb.GetX(), pcbnew.FromMM(10) - bb.GetY())
    for coll in (board.GetFootprints(), board.GetTracks(), board.GetDrawings(), board.Zones()):
        for item in list(coll): item.Move(mv)
    kp = os.path.join(tmp, "imported.kicad_pcb"); pcbnew.PCB_IO_KICAD_SEXPR().SaveBoard(kp, board)
    info = dict(layers=board.GetCopperLayerCount(), parts=len(list(board.GetFootprints())),
                tracks=sum(1 for t in board.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T),
                vias=sum(1 for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T), dropped=dropped)
    return kp, info

def count_by(items, key="type"):
    c = collections.Counter(i.get(key, "?") for i in items); return dict(sorted(c.items()))

def convert(rel, base, sch, brd, dest, project):
    """-> dict for the README/index"""
    r = dict(rel=rel, base=base, dest=dest, project=project, sch=bool(sch), brd=bool(brd), notes=[], proof="n/a", status="ok")
    if os.path.exists(os.path.join(dest, "MASTER")): raise RuntimeError("%s is a hand-maintained master (MASTER marker); refusing to regenerate" % dest)
    if os.path.isdir(dest): shutil.rmtree(dest)
    os.makedirs(os.path.join(dest, "reports"))
    rep = os.path.join(dest, "reports"); tmp = tempfile.mkdtemp(prefix="e2k-")
    try:
        # ---- project file first (rules from the pilot; KiCad only honours the project lib tables when a .kicad_pro exists)
        pro = json.load(open(os.path.join(TK, "project-template.kicad_pro")))
        pro["meta"]["filename"] = project + ".kicad_pro"
        json.dump(pro, open(os.path.join(dest, project + ".kicad_pro"), "w"), indent=2)
        # ---- schematic
        net = None
        if sch:
            c = run([sys.executable, os.path.join(TK, "eagle_sch_to_kicad.py"), sch, dest, project])
            if c.returncode != 0:
                r["status"] = "SCHEMATIC CONVERT FAILED: " + (c.stderr or c.stdout).strip().splitlines()[-1][:200]; return r
            r["sch_stats"] = (c.stdout.strip().splitlines() or [""])[0]
            root_sch = os.path.join(dest, project + ".kicad_sch"); net = os.path.join(rep, "netlist.net")
            k = run([KICAD, "sch", "export", "netlist", "--format", "kicadsexpr", "-o", net, root_sch])
            if k.returncode != 0: r["notes"].append("netlist export failed: " + (k.stderr or k.stdout).strip()[-200:]); net = None
            k = run([KICAD, "sch", "export", "pdf", "-o", os.path.join(rep, project + "-schematic.pdf"), root_sch])
            if k.returncode != 0: r["notes"].append("schematic PDF failed")
            # readability: overlapping text and anything off the drawing frame (tools/kicad/sch_overlaps.py)
            import sch_overlaps
            ov = collections.Counter()
            for fn in sorted(os.listdir(dest)):
                if fn.endswith(".kicad_sch"): ov.update(sch_overlaps.analyse(os.path.join(dest, fn))["counts"])
            r["overlaps"] = dict(ov)
        # ---- board
        if brd:
            import io, contextlib
            buf = io.StringIO()
            fd = os.dup(2); os.dup2(os.open(os.devnull, os.O_WRONLY), 2)   # pcbnew prints a harmless "create wxApp" assertion on stderr
            try:
                try:
                    kp, binfo = import_board(brd, tmp); r["board"] = binfo
                except Exception as ex:
                    r["status"] = "BOARD IMPORT FAILED: " + str(ex).splitlines()[0][:200]; return r
                with contextlib.redirect_stdout(buf):
                    finish_board.main(kp, dest, project, net if net else "-")
            finally:
                os.dup2(fd, 2); os.close(fd)
            r["finish"] = buf.getvalue().strip().splitlines()
            pcb = os.path.join(dest, project + ".kicad_pcb")
            if not sch:   # board-only project still needs its footprint library table
                with open(os.path.join(dest, "fp-lib-table"), "w") as fh:
                    fh.write("(fp_lib_table\n\t(version 7)\n\t(lib (name \"%s-eagle\")(type \"KiCad\")(uri \"${KIPRJMOD}/%s-eagle.pretty\")(options \"\")(descr \"Footprints extracted from the imported Eagle board\"))\n)\n" % (project, project))
        else:
            fl = os.path.join(dest, "fp-lib-table")
            if os.path.exists(fl): os.remove(fl)   # schematic-only project: no footprint library
        # ---- ERC now that the footprint library exists (footprint fields resolve), then DRC
        if sch:
            k = run([KICAD, "sch", "erc", "--format", "json", "--severity-all", "--exit-code-violations", "-o", os.path.join(rep, "erc.json"), root_sch])
            try:
                e = json.load(open(os.path.join(rep, "erc.json")))
                r["erc"] = count_by([v for s in e.get("sheets", []) for v in s.get("violations", [])])
            except Exception as ex: r["notes"].append("ERC: " + str(ex)[:120])
        if brd:
            k = run([KICAD, "pcb", "drc", "--format", "json", "--severity-all", "--exit-code-violations", "-o", os.path.join(rep, "drc.json"), pcb])
            try:
                d = json.load(open(os.path.join(rep, "drc.json")))
                r["drc"] = {"violations": count_by(d.get("violations", [])), "unconnected": len(d.get("unconnected_items", [])),
                            "parity": len(d.get("schematic_parity", []))}
            except Exception as ex: r["notes"].append("DRC: " + str(ex)[:120])
            for side in ("top", "bottom"):
                k = run([KICAD, "pcb", "render", "--side", side, "--width", "1600", "--height", "1200", "-o", os.path.join(rep, "%s-%s.png" % (project, side)), pcb])
                if k.returncode != 0: r["notes"].append("render %s failed" % side)
        # ---- proof
        if sch and brd and net:
            c = run([sys.executable, os.path.join(TK, "compare_netlists.py"), net, pcb])
            open(os.path.join(rep, "netlist-compare.txt"), "w").write(c.stdout + c.stderr)
            m = re.search(r"identical net groups: (\d+) of (\d+)", c.stdout)
            r["proof"] = ("MATCH" if c.returncode == 0 else "MISMATCH") + (" (%s/%s nets)" % (m.group(1), m.group(2)) if m else "")
            r["proof_detail"] = [l for l in c.stdout.splitlines() if l.startswith("  ")][:12]
        elif not sch: r["proof"] = "n/a (board only)"
        elif not brd: r["proof"] = "n/a (schematic only)"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        for f in os.listdir(dest):
            if f.endswith(".kicad_prl"): os.remove(os.path.join(dest, f))   # per-user UI state kicad-cli writes; not part of the project
    return r

def write_readme(r, fabricated):
    dest = r["dest"]; p = r["project"]; rel = r["rel"]
    L = ["# %s — KiCad conversion" % p, "",
         "Generated %s by `tools/eagle_to_kicad_all.py` from the Eagle design `%s` in `hardware/%s/`. **The Eagle files are the "
         "record of what was designed and built; this KiCad project is derived from them and is regenerated from scratch on every "
         "run of the tool** (hand edits here will be lost - once a card is edited in KiCad, remove it from the tool's list). "
         "%s" % (time.strftime("%Y-%m-%d"), r["base"], rel,
                 "This revision was FABRICATED (see `hardware/FABRICATED.md`)." if fabricated else "This revision was never fabricated (or its build status is unknown, see `hardware/FABRICATED.md`)."), ""]
    if r["status"] != "ok": L += ["**CONVERSION FAILED: %s**" % r["status"], ""]
    L += ["## Files", "", "| File | What it is |", "|---|---|", "| `%s.kicad_pro` | project; OSH Park rules (6 mil track, 5 mil clearance, 10 mil drill, 4 mil annular) |" % p]
    if r["sch"]:
        n = len([f for f in os.listdir(dest) if re.match(re.escape(p) + r"-sheet\d+\.kicad_sch$", f)])
        L += ["| `%s.kicad_sch` | root sheet; %d sub-sheet(s) `%s-sheetN.kicad_sch` mirror the Eagle sheets |" % (p, n, p),
              "| `%s-eagle.kicad_sym` | project symbol library generated from the Eagle libraries used (units = Eagle gates) |" % p]
    if r["brd"]:
        b = r.get("board", {})
        L += ["| `%s.kicad_pcb` | the board: %d copper layers, %d footprints, %d track segments, %d vias%s |" % (
                  p, b.get("layers", 0), b.get("parts", 0), b.get("tracks", 0), b.get("vias", 0),
                  ("; %d items on unmapped Eagle layers dropped" % b["dropped"]) if b.get("dropped") else ""),
              "| `%s-eagle.pretty/` | project footprint library extracted from the imported board |" % p]
    L += ["| `reports/` | %s |" % ", ".join(x for x in [
              "ERC (`erc.json`)" if r["sch"] else "", "DRC (`drc.json`)" if r["brd"] else "", "schematic PDF" if r["sch"] else "",
              "board renders (`-top.png`, `-bottom.png`)" if r["brd"] else "", "netlist + `netlist-compare.txt`" if r["sch"] and r["brd"] else ""] if x), ""]
    L += ["## Proof", "", "Schematic-vs-board netlist comparison (`tools/kicad/compare_netlists.py`: every (reference, pad) partition must be identical): **%s**" % r["proof"]]
    if r.get("proof_detail"): L += ["", "```"] + r["proof_detail"] + ["```"]
    if r.get("overlaps") is not None:
        o = r["overlaps"]
        L += ["", "## Readability", "", "`tools/kicad/sch_overlaps.py` over every sheet: text over text %d, text over a symbol body %d, text "
              "crossed by a line %d, items off the drawing frame or on the title block %d. What is left is mostly the Eagle "
              "drawing itself (parts placed that close in Eagle) or KiCad drawing pin numbers centred on short pins." % (
                  o.get("text/text", 0), o.get("text/body", 0), o.get("text/line", 0), o.get("frame", 0))]
    L += ["", "## Residual ERC / DRC", ""]
    if r.get("erc") is not None:
        L += ["ERC by type: " + (", ".join("%s %d" % (k, v) for k, v in r["erc"].items()) or "none") + ".",
              "`isolated_pin_label` = the converter's per-net global labels (cosmetic); `power_pin_not_driven` / unused-unit notes are the same ones KiCad's own Eagle importer leaves. "
              "`unconnected_wire_endpoint` / `pin_not_connected` = wire stubs Eagle leaves bare (mostly net wires ending on a bus, which is drawn as graphics here); "
              "since 2026-09-23 the converter no longer hangs a label on every such end (that was most of the label clutter), so they show as KiCad warnings.", ""]
    if r.get("drc") is not None:
        d = r["drc"]
        L += ["DRC by type: " + (", ".join("%s %d" % (k, v) for k, v in d["violations"].items()) or "none") + "; unconnected items %d; schematic parity %d." % (d["unconnected"], d["parity"]),
              "Silk-over-pad and clearance notes reflect the Eagle design as drawn; unconnected items are Eagle airwires (parts the design left unrouted).", ""]
    if r["notes"]: L += ["## Notes", ""] + ["- " + n for n in r["notes"]] + [""]
    if r.get("sch_stats"): L += ["Converter: " + r["sch_stats"], ""]
    open(os.path.join(dest, "README.md"), "w").write("\n".join(L))

def main():
    ds = designs()
    bycount = collections.Counter(rel for rel, *_ in ds)
    fab = set()
    for r_, d_, f_ in os.walk(HW):
        if "FABRICATED" in f_: fab.add(os.path.relpath(r_, HW))
    results = []; t0 = time.time()
    for rel, base, sch, brd in ds:
        dest, project = dest_for(rel, base, bycount[rel] > 1)
        t = time.time(); print("%-60s -> %s" % (os.path.join(rel, base), os.path.relpath(dest, HW)), end=" ", flush=True)
        try:
            r = convert(rel, base, sch, brd, dest, project)
        except Exception as ex:
            r = dict(rel=rel, base=base, dest=dest, project=project, sch=bool(sch), brd=bool(brd), notes=[], proof="n/a", status="CRASHED: " + str(ex)[:200])
            os.makedirs(dest, exist_ok=True)
        r["fabricated"] = rel in fab
        write_readme(r, r["fabricated"]); results.append(r)
        print("%s  proof=%s  (%.0fs)" % (r["status"] if r["status"] != "ok" else "ok", r["proof"], time.time() - t), flush=True)
    def index_row(r):
        erc = sum(r["erc"].values()) if r.get("erc") else "-"
        drc = ("%d + %d unconnected" % (sum(r["drc"]["violations"].values()), r["drc"]["unconnected"])) if r.get("drc") else "-"
        o = r.get("overlaps")
        ovl = ("%d" % (o.get("text/text", 0) + o.get("text/body", 0) + o.get("text/line", 0))) if o is not None else "-"
        off = ("%d" % o.get("frame", 0)) if o is not None else "-"
        return "| `%s` | [`%s`](%s/) | %s | %s | %s | %s | %s | %s | %s |\n" % (
            os.path.join(r["rel"], r["base"]), r["project"], os.path.relpath(r["dest"], HW), "yes" if r["fabricated"] else "no",
            r["proof"], erc, drc, ovl, off, "ok" if r["status"] == "ok" else "**" + r["status"] + "**")
    kmd = os.path.join(HW, "KICAD.md")
    if only and os.path.exists(kmd):
        # --only: splice the converted designs' rows into the existing index (replace by Eagle design, else insert
        # in sorted order); the rest of the index and its date stay as they were
        lines = open(kmd).read().split("\n"); rows = {}
        first = next(i for i, l in enumerate(lines) if l.startswith("| `"))
        last = first
        while last < len(lines) and lines[last].startswith("| `"): last += 1
        for l in lines[first:last]: rows[l.split("`")[1]] = l
        for r in results: rows[os.path.join(r["rel"], r["base"])] = index_row(r).rstrip("\n")
        lines[first:last] = [rows[k] for k in sorted(rows, key=lambda k: (os.path.dirname(k), os.path.basename(k)))]   # = designs() order
        open(kmd, "w").write("\n".join(lines))
    if not only:
        with open(os.path.join(HW, "KICAD.md"), "w") as f:
            f.write("# KiCad conversions\n\nGenerated %s by `tools/eagle_to_kicad_all.py`: every Eagle design under `hardware/` (active and deprecated "
                    "revisions) converted to a KiCad 10 project in the matching `kicad/<rev>/` folder. The Eagle files remain the record of what was built; "
                    "these projects are derived and regenerated from scratch by the tool. **Proof** = the schematic netlist extracted by KiCad "
                    "compared pad-for-pad with the netlist embedded in the imported Eagle board (`tools/kicad/compare_netlists.py`). "
                    "Each project's README has the details and the residual ERC/DRC counts.\n\n"
                    "**Overlaps** = `tools/kicad/sch_overlaps.py` over all sheets: text/text + text/body + text/line collisions, "
                    "and items off the drawing frame.\n\n"
                    "| Eagle design | KiCad project | Built | Proof | ERC | DRC | Overlaps | Off frame | Status |\n|---|---|---|---|---|---|---|---|---|\n" % time.strftime("%Y-%m-%d"))
            for r in results: f.write(index_row(r))
        masters = sorted(os.path.relpath(r_, HW) for r_, d_, f_ in os.walk(HW) if "MASTER" in f_ and "/kicad/" in r_ + "/")
        if masters:
            with open(os.path.join(HW, "KICAD.md"), "a") as f:
                f.write("\n## Hand-maintained masters (not generated; `MASTER` marker file)\n\n")
                for m in masters: f.write("- [`%s`](%s/) — see its README\n" % (m, m))
    ok = sum(1 for r in results if r["status"] == "ok"); match = sum(1 for r in results if r["proof"].startswith("MATCH"))
    mism = [r for r in results if r["proof"].startswith("MISMATCH")]; bad = [r for r in results if r["status"] != "ok"]
    print("\n%d designs: %d converted, %d proofs MATCH, %d MISMATCH, %d failed  (%.0f min)" % (len(results), ok, match, len(mism), len(bad), (time.time() - t0) / 60))
    for r in mism: print("   MISMATCH", os.path.join(r["rel"], r["base"]), "->", r["proof"])
    for r in bad: print("   FAILED  ", os.path.join(r["rel"], r["base"]), "->", r["status"])
    return 0

if __name__ == "__main__": sys.exit(main())
