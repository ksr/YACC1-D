#!/usr/bin/env python3
"""Every file in YACC1-D must be explained: a plan row (hash re-checked), an extra source from migrate_run.py's
log, a hand-made file (tools/, migration/, front-page docs, placeholder README.md, session captures), or a
generated FABRICATED marker/index. Prints buckets, hash mismatches, unexplained files, and plan rows missing
from disk. Run from anywhere. Exit code 1 if anything is unexplained/mismatched/missing."""
import csv, os, hashlib, glob, collections, sys
DST = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAND_MADE = ("firmware/rom/eprom-captured-", "tests/video/", "tests/memory/", "hardware/cards/video/docs/", "embedded/bus-tester/readback/", "embedded/sequencer-card/readback/", "tests/sequencer/", "tests/assembler/ledcount/", "tests/assembler/brur/", "docs/system/waveforms/", "embedded/sequencer-card/sequencer4/", "hardware/DESIGN-REVIEW", "software/compiler/", "tests/compiler/", "software/ucemu/", "tests/ucemu/", "mk/", "os/", "tests/os/", "software/cfmodel.h", "firmware/abi/README.md")   # session artefacts / bench tests written in YACC1-D, not from YACCS      # session artefacts that are not from YACCS
PATCHED = {l.split("\t")[0].strip() for l in open(os.path.join(DST, "tools/patched_files.txt")) if l.strip() and not l.startswith("#")}
def h(p):
    m = hashlib.md5()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""): m.update(c)
    return m.hexdigest()
plan = {r["destination"]: r for r in csv.DictReader(open(os.path.join(DST, "migration/dryrun-plan.tsv")), delimiter="\t")}
logged = {r["destination"] for lf in glob.glob(os.path.join(DST, "migration/run-log-*.tsv"))
          for r in csv.DictReader(open(lf), delimiter="\t") if r["result"] in ("copied", "already", "clash")}
buckets = collections.Counter(); unexplained = []; bad = []
for root, dirs, files in os.walk(DST):
    dirs[:] = [d for d in dirs if d != ".git"]
    for f in files:
        p = os.path.join(root, f); rel = os.path.relpath(p, DST)
        if os.path.islink(p): buckets["generated: layout links (tools/layout_links.py)"] += 1; continue
        if rel in PATCHED: buckets["mine: patched migrated source (tools/patched_files.txt)"] += 1; continue
        if rel in plan:
            r = plan[rel]; buckets["plan: " + r["mode"]] += 1
            if r["mode"] in ("copy", "archive") and not rel.endswith("Readme.md") and h(p) != r["md5"]: bad.append(rel)
        elif rel in logged: buckets["extra sources (kicad pilot, Arduino libs, eagle conv)"] += 1
        elif rel.startswith(("tools/", "migration/")) or rel in ("README.md", "MIGRATION.md", ".gitignore", ".gitattributes", "BACKLOG.md", "docs/system/MACHINE.md", "docs/system/OS-PLAN.md"): buckets["mine: tools/migration/front-page docs"] += 1
        elif f == "README.md": buckets["mine: placeholder README.md"] += 1
        elif f == "Makefile": buckets["mine: hand-written Makefile (2026-09)"] += 1
        elif rel.startswith(HAND_MADE): buckets["mine: session captures"] += 1
        elif rel.startswith("hardware/bus/blank-card/eagle/v3.2/"): buckets["mine: derived design (Blank V3.2, tools/make_blank_v32.py)"] += 1
        elif rel == "hardware/PROVENANCE.md": buckets["generated: provenance index (tools/gen_provenance.py)"] += 1
        elif rel == "firmware/rom/shipped/rom.bin": buckets["generated: 8K burn image of shipped/rom (tools/img2bin.py --fill 0xFF --size 8192)"] += 1
        elif f.endswith(".md") and os.path.exists(os.path.join(root, f[:-3] + ".rtf")): buckets["generated: Markdown twins of .rtf notes (tools/rtf_to_md.py)"] += 1
        elif f == "FABRICATED" or rel == "hardware/FABRICATED.md": buckets["generated: FABRICATED markers/index"] += 1
        elif rel == "hardware/NEWER-DESIGNS-vs-ACTIVE.txt": buckets["generated: design comparison report (tools/compare_eagle.py)"] += 1
        elif f == "SKIP.txt" and os.path.basename(root) == "pdf": buckets["mine: pdf/SKIP.txt lists"] += 1
        elif rel.startswith("hardware/cards/video/kicad/v1.1/"): buckets["mine: KiCad design masters (MASTER marker)"] += 1
        elif rel.startswith("docs/isa/"): buckets["generated: ISA timing diagrams (tools/ucode_wavedrom.py)"] += 1
        elif (rel.startswith("hardware/") and "/kicad/" in rel) or rel == "hardware/KICAD.md": buckets["generated: KiCad conversions (tools/eagle_to_kicad_all.py)"] += 1
        elif (f.endswith("-board.pdf") and os.path.basename(root) == "pdf") or rel == "hardware/BOARDS.md": buckets["generated: board PDFs (tools/brd_to_pdf.py)"] += 1
        elif (f.endswith("-schematic.pdf") and os.path.basename(root) == "pdf") or rel == "hardware/SCHEMATICS.md": buckets["generated: schematic PDFs (tools/sch_to_pdf.py)"] += 1
        else: unexplained.append(rel)
# build products and other git-ignored files are not part of the tree's content
if unexplained:
    import subprocess
    r = subprocess.run(["git", "check-ignore", "--stdin"], cwd=DST, input="\n".join(unexplained), capture_output=True, text=True)
    ignored = set(r.stdout.split("\n")) if r.returncode in (0, 1) else set()
    buckets["ignored by git (build products)"] += len([u for u in unexplained if u in ignored])
    unexplained = [u for u in unexplained if u not in ignored]
for k, v in sorted(buckets.items(), key=lambda kv: -kv[1]): print("%6d  %s" % (v, k))
missing = [d for d, r in plan.items() if r["mode"] in ("copy", "archive") and not os.path.exists(os.path.join(DST, d))]
print("hash mismatches: %d %s" % (len(bad), bad[:10])); print("unexplained files: %d %s" % (len(unexplained), unexplained[:10]))
print("plan rows missing from disk: %d %s" % (len(missing), missing[:10]))
sys.exit(1 if (bad or unexplained or missing) else 0)
