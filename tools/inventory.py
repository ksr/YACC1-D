#!/usr/bin/env python3
"""Index the YACCS tree and report what is unique where. Read-only."""
import os, sys, hashlib, time, collections, json, signal
SF_DATALESS = 0x40000000
class Timeout(Exception): pass
def _alarm(signum, frame): raise Timeout()
signal.signal(signal.SIGALRM, _alarm)
ROOT = "/Users/ksr77/Documents/YACCS"
CURRENT = ["YACC1-2020", "YACC1-2024", "newgit/YACC1-2020", "YACC gitversion/YACC1-2020"]
OLD = ["YACCS-OLD/" + d for d in sorted(os.listdir(os.path.join(ROOT, "YACCS-OLD"))) if not d.startswith(".")]
OTHER = ["YACC1-master", "test", "video"]
SKIP_DIRS = {".git", "build", "dist", "__pycache__"}   # CAMOutputs was wrongly skipped until 2026-09-20; nbproject/ kept (NetBeans project defs), nbproject/private/ skipped
SKIP_SUFFIX = (".DS_Store", ".o", ".dSYM", ".b#1", ".b#2", ".b#3", ".b#4", ".b#5", ".b#6", ".b#7", ".b#8", ".b#9",
               ".s#1", ".s#2", ".s#3", ".s#4", ".s#5", ".s#6", ".s#7", ".s#8", ".s#9", ".l#1", ".l#2", ".l#3")
DOC = (".md", ".txt", ".rtf", ".pdf", ".docx", ".doc", ".pptx", ".xlsx", ".numbers", ".pages", ".webarchive", ".key")
SRC = (".c", ".h", ".ino", ".asm", ".py", ".pde", ".def", ".sh", ".circ", ".sch", ".brd", ".lbr", ".dru", ".ulp", ".scr",
       ".kicad_sch", ".kicad_pcb", ".img", ".hex", ".lst", ".ino.hex")
MEDIA = (".jpg", ".jpeg", ".png", ".heic", ".mov", ".mp4", ".m4v", ".gif")
MECH = (".stl", ".skp", ".svg", ".dxf", ".f3d", ".step", ".stp", ".3mf", ".scad")

def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

index = {}   # relpath -> dict
dataless, unreadable = [], []
for base in CURRENT + OLD + OTHER:
    top = os.path.join(ROOT, base)
    for dirpath, dirs, files in os.walk(top):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.endswith(".dSYM") and not d.endswith(".app")
                   and not (d == "private" and os.path.basename(dirpath) == "nbproject")]
        for f in files:
            if f.endswith(SKIP_SUFFIX) or f.startswith("."):
                continue
            p = os.path.join(dirpath, f)
            try:
                st = os.stat(p)
            except OSError:
                continue
            if getattr(st, "st_flags", 0) & SF_DATALESS:
                h = "dataless:%d" % st.st_size; dataless.append(os.path.relpath(p, ROOT))
            elif st.st_size > 200 * 1024 * 1024:
                h = "big:%d" % st.st_size
            else:
                signal.alarm(5)
                try:
                    h = md5(p)
                except (Timeout, OSError):
                    h = "unreadable:%d" % st.st_size; unreadable.append(os.path.relpath(p, ROOT))
                finally:
                    signal.alarm(0)
            index[os.path.relpath(p, ROOT)] = dict(base=base, size=st.st_size, mtime=st.st_mtime, md5=h, name=f)
json.dump(index, open(sys.argv[1], "w"))
print("indexed %d files; dataless (not on disk): %d; unreadable: %d" % (len(index), len(dataless), len(unreadable)))
for x in (dataless + unreadable)[:15]: print("   ", x)
json.dump(dict(dataless=dataless, unreadable=unreadable), open(sys.argv[1] + ".missing", "w"))
