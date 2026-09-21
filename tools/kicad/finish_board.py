#!/usr/bin/env python3
"""Post-process the kicad-cli Eagle board import into a finished project board.

Run with KiCad's bundled Python (it needs the pcbnew module):
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \
      tools/finish_board.py <imported.kicad_pcb> <project dir> <project name> <schematic netlist .net | ->

Steps:
  1. extract every embedded footprint into <project>-eagle.pretty so the schematic's
     Footprint fields ("<project>-eagle:<package>") resolve and the project is self-contained
  2. move the stray dimension-layer line that the Eagle connector package put on Edge.Cuts
     onto a user layer (it was never part of the board outline)
  3. apply the OSH Park 4-layer rules the Eagle design used (6 mil track, 10 mil drill,
     4 mil annular, 5 mil clearance) as the board's constraints and default net class
  4. link each footprint to its schematic symbol (sheet path + symbol UUID from the netlist)
  5. refill the two power-plane zones
  6. save as <project dir>/<project>.kicad_pcb
"""
import sys, os, re
import pcbnew

MM = pcbnew.FromMM

def main(src, outdir, project, netfile):
    board = pcbnew.LoadBoard(src)
    libname = project + "-eagle"

    # 1. stray Edge.Cuts line inside footprints -> User.Drawings
    moved = 0
    for fp in board.GetFootprints():
        for item in fp.GraphicalItems():
            if item.GetLayer() == pcbnew.Edge_Cuts:
                item.SetLayer(pcbnew.Dwgs_User); moved += 1
    print("footprint graphics moved off Edge.Cuts:", moved)

    # 2. footprint library (after the Edge.Cuts fix, so the library copy matches the board copy)
    pretty = os.path.join(outdir, libname + ".pretty")
    os.makedirs(pretty, exist_ok=True)
    plugin = pcbnew.PCB_IO_KICAD_SEXPR()
    seen = set()
    for fp in board.GetFootprints():
        fpid = fp.GetFPID()
        name = fpid.GetLibItemName().wx_str() if hasattr(fpid.GetLibItemName(), "wx_str") else str(fpid.GetLibItemName())
        if name in seen:
            continue
        seen.add(name)
        plugin.FootprintSave(pretty, fp)   # KiCad normalises position/orientation on save
    print("footprints saved to %s: %d" % (pretty, len(seen)))
    for fp in board.GetFootprints():
        fpid = fp.GetFPID()
        name = fpid.GetLibItemName().wx_str() if hasattr(fpid.GetLibItemName(), "wx_str") else str(fpid.GetLibItemName())
        fp.SetFPIDAsString(libname + ":" + name)

    # 3. design rules (OSH Park 4-layer, as in the Eagle .dru)
    ds = board.GetDesignSettings()
    ds.m_MinClearance = MM(0.127)          # 5 mil
    ds.m_TrackMinWidth = MM(0.1524)        # 6 mil
    ds.m_ViasMinSize = MM(0.4572)          # 18 mil (10 mil drill + 2 x 4 mil)
    ds.m_MinThroughDrill = MM(0.254)       # 10 mil
    ds.m_ViasMinAnnularWidth = MM(0.1016)  # 4 mil
    ds.m_HoleClearance = MM(0.127)
    ds.m_HoleToHoleMin = MM(0.254)
    ds.m_CopperEdgeClearance = MM(0.381)   # 15 mil
    nets = board.GetNetInfo()
    ncs = ds.GetNetSettings() if hasattr(ds, "GetNetSettings") else ds.m_NetSettings
    try:
        default = ncs.GetDefaultNetclass()
        default.SetClearance(MM(0.127)); default.SetTrackWidth(MM(0.1524))
        default.SetViaDiameter(MM(0.4572)); default.SetViaDrill(MM(0.254))
    except Exception as e:
        print("netclass update skipped:", e)

    # 4. link footprints to schematic symbols via the netlist (ref -> sheetpath + uuid)
    links = {}
    s = open(netfile).read() if netfile and netfile != "-" and os.path.exists(netfile) else ""   # '-' = board-only project, nothing to link
    for block in re.split(r'\n\t\t\(comp\s', s)[1:]:
        ref = re.search(r'\(ref "([^"]+)"\)', block)
        sp = re.search(r'\(sheetpath\s+\(names "[^"]*"\)\s+\(tstamps "([^"]+)"\)', block)
        ts = re.search(r'\n\t\t\t\(tstamps "([^"]+)"', block)   # multi-unit parts list several; the first is the anchor
        if ref and sp and ts:
            links[ref.group(1)] = sp.group(1).rstrip("/") + "/" + ts.group(1)
    linked = 0
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if ref in links:
            fp.SetPath(pcbnew.KIID_PATH(links[ref])); linked += 1
    print("footprints linked to schematic symbols: %d of %d" % (linked, len(board.GetFootprints())))

    # 5. zones
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    print("zones filled:", len(board.Zones()))

    # 6. save
    out = os.path.join(outdir, project + ".kicad_pcb")
    board.SetFileName(out)
    pcbnew.SaveBoard(out, board)
    print("saved", out)

if __name__ == "__main__":
    main(*sys.argv[1:5])
