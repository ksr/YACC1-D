#!/usr/bin/env python3
"""hardware/PROVENANCE.md: for every board version folder under hardware/, where it came from in the old
YACCS tree and how old its files REALLY are.

'Source' = the YACCS folder the migration copied from (from migration/dryrun-plan.tsv).
'Real date' = the OLDEST modification time of ANY byte-identical copy of that file anywhere in YACCS
(tools/yaccs-index-*.json). Git checkouts stamp their own date on everything (gitversion 2025-03-06,
newgit 2026-05-21), so the newest date means nothing; the oldest copy is when the content last changed.
'Copies' = how many identical copies exist and in which top-level YACCS folders.
"""
import os, csv, json, time, collections, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); HW = os.path.join(ROOT, "hardware")
IDX = sorted(p for p in os.listdir(os.path.join(ROOT, "tools")) if p.startswith("yaccs-index-") and p.endswith(".json"))[-1]
idx = json.load(open(os.path.join(ROOT, "tools", IDX)))
by_md5 = collections.defaultdict(list)
for k, e in idx.items(): by_md5[e["md5"]].append((e["mtime"], k))
plan = [r for r in csv.DictReader(open(os.path.join(ROOT, "migration/dryrun-plan.tsv")), delimiter="\t") if r["mode"] == "copy" and r["destination"].startswith("hardware/")]
folders = collections.OrderedDict()
for r in plan:
    m = re.match(r"(hardware/(?:cards|bus)/[^/]+/(?:eagle(?:/deprecated)?/[^/]+|accessories/[^/]+))/(.+)$", r["destination"])
    if not m: continue
    folders.setdefault(m.group(1), []).append((m.group(2), r["source"], r["md5"]))
def top(path):
    p = path.split("/")
    return p[1] if p[0] == "YACCS-OLD" else p[0] if p[0] != "YACC gitversion" and p[0] != "newgit" else p[0] + "/" + p[1]
def short_top(t):
    return {"YACC gitversion/YACC1-2020": "gitversion", "newgit/YACC1-2020": "newgit", "YACC1-2020": "2020", "YACC1-2024": "2024"}.get(t, t)
rows = []
for folder, files in folders.items():
    srcdirs = collections.Counter(os.path.dirname(s_) for f_, s_, h in files if "/" not in f_)
    srcdir = srcdirs.most_common(1)[0][0] if srcdirs else os.path.dirname(files[0][1])
    design = sorted((f_, s_, h) for f_, s_, h in files if "/" not in f_ and f_.lower().endswith((".sch", ".brd")))
    if not design:
        rows.append((folder.replace("hardware/", ""), srcdir, "(no .sch/.brd)", "-", "-")); continue
    first = True
    for f_, s_, h in design:
        copies = sorted(by_md5.get(h, []))
        oldest = time.strftime("%Y-%m-%d", time.localtime(copies[0][0])) if copies else "?"
        tops = sorted({short_top(top(k)) for _, k in copies})
        rows.append((folder.replace("hardware/", "") if first else "", srcdir if first else "", f_, oldest, "%d in %s" % (len(copies), ", ".join(tops))))
        first = False
with open(os.path.join(HW, "PROVENANCE.md"), "w") as f:
    f.write("# Provenance of every board version\n\nGenerated %s by `tools/gen_provenance.py`. **Source** = the YACCS folder the files were copied from. "
            "**Real date** = the oldest modification date of any byte-identical copy anywhere in YACCS: git checkouts (gitversion = 2025-03-06, newgit = 2026-05-21) "
            "stamp their own date on every file, so a version whose oldest copy is 2020 was made in 2020 whatever the checkout says. **Copies** = identical copies and the YACCS folders holding them "
            "(2020/2024 = the non-git working copies with real dates; YACC1-2020-ORIG = Aug-2020 snapshot, YACC1-2020-OLD = Jan-2021, July 2021 backup, YACC1A/A1/B/BACKUP = 2016-18 gen-1 backups).\n\n"
            "| Version folder | Source in YACCS | Design file | Real date (oldest identical copy) | Copies |\n|---|---|---|---|---|\n")
    for r in rows: f.write("| %s | %s | `%s` | %s | %s |\n" % (("`%s`" % r[0]) if r[0] else "", ("`%s`" % r[1]) if r[1] else "", r[2], r[3], r[4]))
print("%d rows" % len(rows))
for r in rows: print("%-52s %-34s %-11s %s" % (r[0][:52], r[2][:34], r[3], r[4][:60]))
