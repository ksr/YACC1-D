# Author: Claude (Anthropic) for Ken Rother, 2026
"""MkDocs hook: a relative link to a repository file that is not part of the site (a source, a schematic, a datasheet)
becomes a link to that file on GitHub; an image that is not part of the site is shown from GitHub's raw files."""
import os, posixpath, re
from urllib.parse import unquote

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository this folder is in
GH = "https://github.com/ksr/YACC1-D"
RAW = "https://raw.githubusercontent.com/ksr/YACC1-D/main/"
LINK = re.compile(r'(!?)\[((?:[^\[\]]|\[[^\]]*\])*)\]\((<[^>]+>|[^)\s]+)((?:\s+"[^"]*")?)\)')
stats = {"github": 0}


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
