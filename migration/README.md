# migration/ — how YACC1-D was populated (2026-09-19)

The source tree `~/Documents/YACCS` was never modified. Everything here is reproducible from
`tools/yaccs-index-2026-09-20.json` (a hash of every file under YACCS, made by `tools/inventory.py`).

| File | What it is |
|---|---|
| `dryrun-summary.txt` | counts by mode and destination area |
| `dryrun-plan.tsv` | every decision: mode, destination, source, md5. Made by `tools/migrate_dryrun.py` |
| `run-log-2026-09-19.tsv` | what `tools/migrate_run.py` did with each row (copied / already / clash / manifest) |
| `dedup-dropped.tsv` | 3,288 files NOT copied because identical bytes went elsewhere; column 2 says where |
| `copy-duplicates.txt` | identical content that deliberately exists at two places in the current tree |
| `conflicts-relative-path.txt` | 28 paths whose content differed between the four current copies; newest was copied, the losers are under `archive/conflict-losers/` |
| `same-name-different-content.txt` | 179 file names with more than one distinct content anywhere in YACCS |
| `production-boards.txt` | fabricated revision per card (PCB/Production, corrected by Ken) |
| `large-files-manifest.tsv` | 7 files > 50 MB kept OUT of the tree (no LFS): path, size, sha256, where the bytes are |
| `unclassified.txt`, `conflicts-destination.txt` | both empty: every file was claimed, no two sources fought over one target |

Re-run cycle after any rules change: `tools/migrate_dryrun.py` -> `tools/migrate_purge.py` (drops files an earlier run placed that the new plan no longer wants) -> `tools/migrate_run.py` -> `tools/gen_fabricated.py` -> `tools/audit_tree.py` (must pass).

Rule semantics (since 2026-09-20): a rule whose path ends in `/` covers a folder, otherwise it names exactly one file; first match
wins, so file rules go before their folder rule. A `skip` decided for the live copies also applies to the same path in the
2020/2021 snapshots, and bytes that were deliberately skipped never resurface from any backup under another path.
Rule scope: a copy value of `GV`/`NG`/`C20`/`C24` = that live copy; `None` = any of the four live copies; `"ANY"` = every
source including the backup snapshots (used for the connector-spec PDFs). Patterns with `* ? [` are globs.
A `drop` rule means "this path is a duplicate of content kept elsewhere" (not copied from here or from the same path in
a snapshot, other holders untouched); `skip` means "unwanted" (its bytes never resurface from any backup).
Pick-and-place exports (`CAMOutputs/Assembly/PnP_*.txt`) are junk in backups (timestamp-only differences).

Rules of the migration: newest copy of a component wins; the four gen-1 and four 2020-era backups are
deduplicated by content into `archive/`; Eagle `.sch`/`.brd` pairs are never split; nothing over 50 MB
is committed. Second pass (same day): every FABRICATED revision was moved from `archive/` to its card folder
(see `hardware/FABRICATED.md`); the 193 files that pass vacated were deleted from this tree and re-copied to
their new places, then every plan row was re-verified. Third pass: fab output (63 files) routed into `<rev>/fab/` and BOM exports into `<rev>/bom/`. Fourth pass (2026-09-20):
Ken's ACTIVE version per card applied - lower versions moved to `eagle/deprecated/<rev>/` (227 files re-placed), same
purge / recopy / verify cycle each time. Fifth pass (2026-09-20): the inventory had been SKIPPING every `CAMOutputs`
directory (2,984 files, the Fusion CAM output of every 2020 board); re-indexed as `yaccs-index-2026-09-20.json`, re-planned,
661 more files copied into the `<rev>/fab/` folders, everything re-verified. `yaccs-index-2026-09-19.json` is kept for the record.

**REBUILT FROM SCRATCH 2026-09-20.** Because the index had been wrong once, the tree was emptied and repopulated
from a proven-complete index: `yaccs-find-2026-09-20.txt` is a raw `find . -type f` of YACCS (25,476 files) and every
line of it is accounted for (11,400 indexed; the rest are `.git/` internals, NetBeans `build/`/`dist/`, `nbproject/private/`,
`.o`/`.dSYM`, `.DS_Store`, Eagle `.lck` lock files and other dotfiles, the retired strawman + kicad pilot handled as
extra sources, and the one stray `dir struct` script). `nbproject/` project definitions are now KEPT with each C tool
(NetBeans 8.2 is what they were built with). `tools/audit_tree.py` then proves every file in YACC1-D is explained
(plan row with matching hash, extra source, hand-made, or generated) and `rebuild-diff-2026-09-20.txt` records the
diff against the previous tree: 3 leftovers (a `.DS_Store` and the 2026-09-18 EPROM capture, which was carried over). The two `Readme.md` files from the source that landed on my placeholder `README.md`
(case-insensitive disk) were merged: original text first, placeholder note below.
