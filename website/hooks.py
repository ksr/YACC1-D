# Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

"""MkDocs hook: a relative link to a repository file that is not part of the site (a source, a schematic, a datasheet)
becomes a link to that file on GitHub; an image that is not part of the site is shown from GitHub's raw files."""
import os, posixpath, re
from urllib.parse import unquote

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository this folder is in
GH = "https://github.com/ksr/YACC1-D"
RAW = "https://raw.githubusercontent.com/ksr/YACC1-D/main/"
LINK = re.compile(r'(!?)\[((?:[^\[\]]|\[[^\]]*\])*)\]\((<[^>]+>|[^)\s]+)((?:\s+"[^"]*")?)\)')
stats = {"github": 0}


def card_versions(card):
    """[(label, staged page)] for each design version of hardware/cards/<card>/, oldest first. A version
    is a folder under eagle/ or kicad/ with a README (the built card's Eagle export wins over its KiCad conversion);
    deprecated/ and option folders are not versions."""
    found = {}
    for tool in ("kicad", "eagle"):                               # eagle second, so it wins for the same version
        base = os.path.join(REPO, "hardware", "cards", card, tool)
        if not os.path.isdir(base): continue
        for name in os.listdir(base):
            m = re.match(r"v(\d+(?:\.\d+)*)", name, re.I)
            readme = os.path.join(base, name, "README.md")
            if m and os.path.isfile(readme):
                found[m.group(1)] = (os.path.join(base, name), "hardware/cards/%s/%s/%s/notes.md" % (card, tool, name))
    if not found: return []
    status = {}                                                  # version -> label, from tools/fabricated.py
    for c, folder, ver, st, note in re.findall(r'\(\s*"([^"]+)",\s*"([^"]+)",\s*"([^"]+)",\s*"([^"]+)",\s*"[^"]*",\s*"([^"]*)"',
                                             open(os.path.join(REPO, "tools", "fabricated.py"), encoding="utf-8").read()):
        if c != card or "deprecated" in folder: continue
        v = ver.lower().lstrip("v")
        if st == "in-machine": status[v] = "in the machine"
        elif st == "fabricated": status[v] = "ordered" if "not yet received" in note or "ORDERED" in note else "built"
    key = lambda v: [int(x) for x in v.split(".")]
    masters = [v for v, (d, _) in found.items() if os.path.exists(os.path.join(d, "MASTER")) and v not in status]
    if masters and len(found) > 1: status.setdefault(max(masters, key=key), "current design")   # the newest of several designs
    return [("V%s%s" % (v, " (%s)" % status[v] if v in status else ""), found[v][1]) for v in sorted(found, key=key)]


def on_config(config):
    """Each card in the Cards menu becomes a submenu: its theory-of-operation page, then one page per version."""
    for section in config["nav"]:
        if not (isinstance(section, dict) and "Cards" in section): continue
        items = []
        for item in section["Cards"]:
            (label, path), = item.items()
            card = os.path.splitext(os.path.basename(path))[0] if isinstance(path, str) else None
            versions = card_versions(card) if card and path.startswith("docs/cards/") else []
            if versions:
                items.append({label: [{"Theory of operation": path}] + [{l: p} for l, p in versions]})
            else:
                items.append(item)
        section["Cards"] = items
    return config


def on_page_markdown(markdown, page, config, files):
    site = {f.src_uri for f in files}
    here = posixpath.dirname(page.file.src_uri)

    def fix(m):
        bang, text, target, title = m.groups()
        t = target[1:-1] if target.startswith("<") else target
        if re.match(r"^[a-z][a-z0-9+.-]*:", t, re.I) or t.startswith("#") or t.startswith("/"): return m.group(0)
        path, _, frag = t.partition("#")
        if not path: return m.group(0)
        resolved = posixpath.normpath(posixpath.join(here, unquote(path)))
        if resolved in site or resolved.startswith(".."): return m.group(0)
        if not os.path.exists(os.path.join(REPO, resolved)): return m.group(0)       # leave MkDocs to report it
        stats["github"] += 1
        if bang: url = RAW + resolved
        else:
            kind = "tree" if os.path.isdir(os.path.join(REPO, resolved)) else "blob"
            url = "%s/%s/main/%s" % (GH, kind, resolved) + ("#" + frag if frag else "")
        return "%s[%s](<%s>%s)" % (bang, text, url, title)

    return LINK.sub(fix, markdown)


def on_post_build(config):
    print("hooks: %d links to files outside the site now point at GitHub" % stats["github"])
