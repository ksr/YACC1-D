#!/usr/bin/env python3
"""Remove files that an earlier migrate_run.py placed but the CURRENT plan no longer wants (after a rules change).
Reads every migration/run-log-*.tsv; a 'copied' destination is stale when it is neither in dryrun-plan.tsv nor
one of migrate_run.py's EXTRA sources. Then prunes empty dirs under hardware/ and archive/. Never touches
YACCS. Prints what it removed. Run: dryrun -> purge -> run -> gen_fabricated -> audit."""
import csv, os, glob, fnmatch, sys, importlib.util
DST = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("mr", os.path.join(DST, "tools", "migrate_run.py")); mr = importlib.util.module_from_spec(spec)
sys.argv = [sys.argv[0]]; spec.loader.exec_module(mr)
plan_rows = list(csv.DictReader(open(os.path.join(DST, "migration/dryrun-plan.tsv")), delimiter="\t"))
keep = {r["destination"] for r in plan_rows}
plan_md5 = {}                         # destination -> set of md5s the plan now wants there
for r in plan_rows: plan_md5.setdefault(r["destination"], set()).add(r["md5"])
import hashlib
def h(p):
    m = hashlib.md5()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""): m.update(c)
    return m.hexdigest()
for sdir, ddir, mode in mr.EXTRA:
    for root, dirs, files in os.walk(sdir):
        dirs[:] = [d for d in dirs if not any(fnmatch.fnmatch(d, j) for j in mr.JUNK) and not (root == sdir and d == "tools" and ddir.endswith("/kicad"))]
        for fn in files:
            if not any(fnmatch.fnmatch(fn, j) for j in mr.JUNK): keep.add(os.path.join(ddir, os.path.relpath(os.path.join(root, fn), sdir)))
PATCHED = {l.split("\t")[0].strip() for l in open(os.path.join(DST, "tools/patched_files.txt")) if l.strip() and not l.startswith("#")}
removed = []
for lf in glob.glob(os.path.join(DST, "migration/run-log-*.tsv")):
    for r in csv.DictReader(open(lf), delimiter="\t"):
        stale = r["destination"] not in keep
        if not stale and r["destination"] in plan_md5 and r["result"] == "copied":
            p_ = os.path.join(DST, r["destination"])          # destination still planned: stale only if the bytes on disk are not what the plan wants
            stale = os.path.isfile(p_) and h(p_) not in plan_md5[r["destination"]]
        if r["destination"] in PATCHED: continue          # deliberately edited in the tree: never reverted
        if r["result"] == "copied" and stale:
            p = os.path.join(DST, r["destination"])
            if os.path.isfile(p): os.remove(p); removed.append(r["destination"])
for top in ("hardware", "archive", "software", "firmware", "embedded", "docs", "tests"):
    for root, dirs, files in os.walk(os.path.join(DST, top), topdown=False):
        if root != os.path.join(DST, top) and not os.listdir(root): os.rmdir(root)
print("stale files removed: %d" % len(removed)); [print("   ", x) for x in removed[:20]]
