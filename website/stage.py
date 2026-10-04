# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""Copy the YACC1-D documents the website uses into stage/, keeping each file's repository path, so the links between
them keep working. Anything not copied is linked to GitHub by hooks.py."""
import glob, os, shutil

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository this folder is in
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "stage")
FILES = ["BACKLOG.md", "hardware/README.md", "hardware/FABRICATED.md", "os/README.md",
         "firmware/README.md", "embedded/README.md", "tools/README.md", "tests/README.md",
         "software/compiler/README.md", "software/assembler/README.md", "software/emulator/README.md",
         "software/ucemu/README.md", "software/disassembler/README.md"]
GLOBS = ["docs/**/*.md", "docs/isa/*.svg", "docs/**/*.png"]

shutil.rmtree(OUT, ignore_errors=True)
n = 0
paths = set(FILES)
for g in GLOBS:
    paths |= {os.path.relpath(p, REPO) for p in glob.glob(os.path.join(REPO, g), recursive=True)}
for rel in sorted(paths):
    src = os.path.join(REPO, rel)
    if not os.path.isfile(src): continue
    dst = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst); n += 1
# the visitor home page (home.md here) is the site's index; the repository README becomes the "Working on the code"
# page (links to README.md from other documents then point at GitHub, through hooks.py)
shutil.copy2(os.path.join(HERE, "home.md"), os.path.join(OUT, "index.md")); n += 1
shutil.copy2(os.path.join(REPO, "README.md"), os.path.join(OUT, "repository.md")); n += 1
# one page per timing diagram (docs/isa/NAME.md): heading, what the instruction does (from the ISA reference), its
# operands / bytes / steps (from the diagram index), the diagram (click: full size), previous / next opcode, back to
# the index; the index's links then go to these pages instead of the bare SVGs
import re
isa_dir = os.path.join(OUT, "docs", "isa")
idx_path = os.path.join(isa_dir, "README.md")
idx = open(idx_path, encoding="utf-8").read()
rows = []
for line in idx.splitlines():
    c = [x.strip() for x in line.strip().strip("|").split("|")]
    if len(c) == 6 and c[0].startswith("$"):
        m = re.match(r"\[(\w+)\.svg\]", c[5])
        if m and os.path.exists(os.path.join(isa_dir, m.group(1) + ".svg")):
            rows.append(dict(op=c[0], mn=c[1], operands=c[2], nbytes=c[3], steps=c[4], name=m.group(1)))
desc = {}
header = []
for line in open(os.path.join(REPO, "docs/programming/ISA-REFERENCE.md"), encoding="utf-8"):
    c = [x.strip().replace("\\|", "|") for x in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
    if c and c[0] == "Opcode": header = c; continue
    if len(c) >= 5 and c[0].startswith("$") and c[1].startswith("`"):
        syntax, what = c[1].strip("`"), c[4]
        if len(header) > 4 and header[4] == "Branches when": what = "branches when " + what
        if len(c) > 5 and len(header) > 5 and header[5] == "Carry FF" and c[5]: what += " (carry: %s)" % c[5]
        desc.setdefault(syntax.split()[0], (syntax, what))
# the two records that are not instructions a program writes (docs/system/ARCHITECTURE.md)
desc.setdefault("START", ("START", "the reset record: RESET clears the instruction register, so the machine runs this "
                                   "record first - it fetches from PC = 0 and goes"))
desc.setdefault("INT", ("INT", "the interrupt entry: with an interrupt pending and enabled the instruction register takes "
                               "$FF instead of the fetched opcode; this record pushes the PC and jumps to the interrupt vector"))
for i, r in enumerate(rows):
    prev, nxt = rows[i - 1] if i else None, rows[i + 1] if i + 1 < len(rows) else None
    syntax, what = desc.get(r["mn"], (r["mn"], ""))
    lines = ["# %s \u2014 opcode %s" % (r["mn"], r["op"]), ""]
    lines.append("**`%s`**%s" % (syntax, (" \u2014 " + what) if what else ""))
    lines += ["", "| Operands | Bytes | Microcode steps |", "|---|---|---|",
              "| %s | %s | %s |" % (r["operands"] or "\u2014", r["nbytes"] or "\u2014", r["steps"]), ""]
    lines += ["[![%s timing diagram](%s.svg)](%s.svg \"Open the diagram full size\")" % (r["mn"], r["name"], r["name"]), ""]
    lines += ["*One column per microcode step. The control lines are read from the microcode image; the address bus, data "
              "bus and registers at the bottom are a model. [How to read the diagrams](README.md) \u00b7 "
              "[the instruction set](../programming/ISA-REFERENCE.md)*", ""]
    nav = []
    if prev: nav.append("[\u2190 %s (%s)](%s.md)" % (prev["mn"], prev["op"], prev["name"]))
    nav.append("[All opcodes](README.md)")
    if nxt: nav.append("[%s (%s) \u2192](%s.md)" % (nxt["mn"], nxt["op"], nxt["name"]))
    lines.append(" \u00b7 ".join(nav))
    open(os.path.join(isa_dir, r["name"] + ".md"), "w", encoding="utf-8").write("\n".join(lines) + "\n"); n += 1
idx = re.sub(r"\[(\w+)\.svg\]\(\1\.svg\)", lambda m: "[%s](%s.md)" % (m.group(1), m.group(1)), idx)
open(idx_path, "w", encoding="utf-8").write(idx)
print("timing-diagram pages: %d (descriptions found for %d)" % (len(rows), sum(1 for r in rows if r["mn"] in desc)))
# photos for the home page, resized for the web (the originals in media/ are 3000-4000 px, 27 MB)
from PIL import Image
PHOTOS = {"system1.jpeg": 1400, "sequencer top.jpeg": 700, "alu v3.2 top.jpeg": 700, "index register v1.1 top.jpeg": 700,
          "memory v1.2 top.jpeg": 700, "io v1.1 top.jpeg": 700, "test board v1.1 top.jpeg": 700}
os.makedirs(os.path.join(OUT, "media"), exist_ok=True)
for name, width in PHOTOS.items():
    im = Image.open(os.path.join(REPO, "media", name))
    try:
        from PIL import ImageOps; im = ImageOps.exif_transpose(im)
    except Exception: pass
    im.thumbnail((width, width * 2))
    im.convert("RGB").save(os.path.join(OUT, "media", name.replace(" ", "-").replace(".jpeg", ".jpg")), quality=84)
    n += 1
print("staged %d files" % n)
