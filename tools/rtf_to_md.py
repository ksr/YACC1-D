#!/usr/bin/env python3
"""Give every .rtf note outside archive/ a Markdown twin beside it (same name, .md), so the notes are readable and
diffable in git. The .rtf stays the original; the .md is GENERATED (re-run after editing an .rtf; edit the .md only
once you retire the .rtf). Uses macOS `textutil` for the RTF -> text step. Idempotent; removes twins whose .rtf is gone."""
import os, subprocess, time, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
made = removed = 0
for root, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in (".git", "archive")]
    for f in files:
        if f.lower().endswith(".rtf"):
            src = os.path.join(root, f); dst = src[:-4] + ".md"
            txt = subprocess.run(["textutil", "-convert", "txt", "-stdout", src], capture_output=True, text=True).stdout
            txt = txt.replace("\r\n", "\n").replace("\r", "\n").replace("\t", "    ").rstrip() + "\n"
            txt = re.sub(r"\n{3,}", "\n\n", txt)
            head = "*Converted from `%s` (saved %s) by `tools/rtf_to_md.py`; the .rtf is the original.*\n\n" % (f, time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(src))))
            body = head + txt
            if not os.path.exists(dst) or open(dst).read() != body:
                open(dst, "w").write(body); made += 1
        elif f.endswith(".md") and os.path.exists(os.path.join(root, f[:-3] + ".rtf")) is False and f != "README.md":
            # a twin whose .rtf disappeared: only remove if it carries our header
            p = os.path.join(root, f)
            try:
                first = open(p).readline()
            except Exception: continue
            if first.startswith("*Converted from `") and not os.path.exists(os.path.join(root, first.split("`")[1])):
                os.remove(p); removed += 1
print("markdown twins written/updated: %d, orphans removed: %d" % (made, removed))
