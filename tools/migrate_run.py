#!/usr/bin/env python3
"""Execute the migration plan produced by migrate_dryrun.py. The source tree is READ ONLY.

usage: migrate_run.py <migration dir> [--src ~/Documents/YACCS] [--dst ~/Developer/YACC1-D]

For each plan row:
  copy / archive : shutil.copy2 (keeps the original mtime), then the copy is re-hashed and must
                   match the source. An existing destination with the same bytes is skipped
                   (re-runnable); an existing destination with DIFFERENT bytes is never
                   overwritten - it is logged as a clash and left alone.
  manifest       : nothing copied; path, size, sha256 and source location go to
                   large-files-manifest.tsv (no LFS, GitHub refuses > 100 MB).
  skip           : nothing.
Then the out-of-tree sources (KiCad pilot, Arduino libraries, stray Eagle project) listed in
EXTRA are copied the same way. Everything done is logged to run-log-<date>.tsv.
"""
import sys, os, csv, shutil, hashlib, time, fnmatch

SRC = os.path.expanduser("~/Documents/YACCS")
DST = os.path.expanduser("~/Developer/YACC1-D")
JUNK = ("*.b#?", "*.s#?", "*.l#?", ".DS_Store", "*.pyc", "__pycache__")
EXTRA = [   # (absolute source dir, destination dir, mode)
    # the pilot's tools/ subfolder is NOT copied: the maintained converter/prover/finisher live in tools/kicad (newer than the pilot copy)
    # the 2026-09-19 memory-card pilot (~/Documents/YACCS/kicad/memory-card-v1.3) is no longer copied: since 2026-09-20 every
    # design is converted by tools/eagle_to_kicad_all.py into <item>/kicad/<rev>/ with the same tools
    (os.path.expanduser("~/Documents/Arduino/libraries/YACC"), "embedded/libraries/YACC", "copy"),
    (os.path.expanduser("~/Documents/Arduino/old-libraries/Adafruit_MCP23017_Arduino_Library"),
     "embedded/libraries/Adafruit_MCP23017_Arduino_Library", "copy"),
    (os.path.expanduser("~/Documents/Arduino/old-libraries/extEEPROM"), "embedded/libraries/extEEPROM", "copy"),   # JChristensen extEEPROM, used by the deprecated sequencer2 sketch
    (os.path.expanduser("~/Documents/eagle/projects/video"), "archive/eagle-projects/video-lm1881-conv", "archive"),
]

def h(path, algo="md5"):
    m = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            m.update(chunk)
    return m.hexdigest()

def main(migdir):
    global SRC, DST
    args = sys.argv[2:]
    if "--src" in args: SRC = os.path.expanduser(args[args.index("--src") + 1])
    if "--dst" in args: DST = os.path.expanduser(args[args.index("--dst") + 1])
    rows = list(csv.DictReader(open(os.path.join(migdir, "dryrun-plan.tsv")), delimiter="\t"))
    for sdir, ddir, mode in EXTRA:
        for root, dirs, files in os.walk(sdir):
            dirs[:] = [d for d in dirs if not any(fnmatch.fnmatch(d, j) for j in JUNK) and not (root == sdir and d == "tools" and ddir.endswith("/kicad"))]
            for fn in files:
                if any(fnmatch.fnmatch(fn, j) for j in JUNK): continue
                sp = os.path.join(root, fn)
                rows.append({"mode": mode, "destination": os.path.join(ddir, os.path.relpath(sp, sdir)), "source": sp, "md5": ""})
    pf = os.path.join(DST, "tools/patched_files.txt")
    patched = {l.split("\t")[0].strip() for l in open(pf) if l.strip() and not l.startswith("#")} if os.path.exists(pf) else set()
    log = open(os.path.join(migdir, "run-log-%s.tsv" % time.strftime("%Y-%m-%d")), "a")
    log.write("time\tresult\tmode\tdestination\tsource\n")
    stats = {"copied": 0, "already": 0, "clash": 0, "manifest": 0, "skip": 0, "missing": 0, "bytes": 0}
    manifest = open(os.path.join(migdir, "large-files-manifest.tsv"), "w")
    manifest.write("destination\tsize\tsha256\tsource (absolute)\n")
    def note(result, r):
        log.write("%s\t%s\t%s\t%s\t%s\n" % (time.strftime("%H:%M:%S"), result, r["mode"], r["destination"], r["source"]))
        stats[result] += 1
    for i, r in enumerate(rows):
        sp = r["source"] if os.path.isabs(r["source"]) else os.path.join(SRC, r["source"])
        dp = os.path.join(DST, r["destination"])
        if r["mode"] in ("skip", "drop"):
            note("skip", r); continue
        if not os.path.isfile(sp):
            note("missing", r); continue
        if r["mode"] == "manifest":
            manifest.write("%s\t%d\t%s\t%s\n" % (r["destination"], os.path.getsize(sp), h(sp, "sha256"), sp))
            note("manifest", r); continue
        smd5 = h(sp)
        if r["destination"] in patched and os.path.exists(dp):
            note("already", r); continue                     # deliberately edited in the tree (tools/patched_files.txt)
        if os.path.exists(dp):
            if h(dp) == smd5:
                note("already", r); continue
            note("clash", r); continue
        os.makedirs(os.path.dirname(dp), exist_ok=True)
        shutil.copy2(sp, dp)
        if h(dp) != smd5:
            os.remove(dp); raise SystemExit("verify failed: %s" % dp)
        stats["bytes"] += os.path.getsize(dp)
        note("copied", r)
        if i % 500 == 0: print("  %d/%d" % (i, len(rows)), flush=True)
    log.close(); manifest.close()
    print("done:", {k: v for k, v in stats.items() if k != "bytes"}, "%.1f MB copied" % (stats["bytes"] / 1e6))

if __name__ == "__main__":
    main(sys.argv[1])
