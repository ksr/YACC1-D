/* lib_apath.c - make a path absolute (Y1/OS, 2026-09-23).
     abspath(out, a) -> the characters of a used (the word ends at NUL or space)
       out  <- the absolute path: the current directory (getcwd) + "/" + a when a is relative, then "." components
               dropped and ".." ones folded into their parent, so "/BIN/../MAN/" comes out "/MAN"; no trailing "/"
               except for the root itself. out must hold APLEN (128) bytes; a longer result is cut there.
   Y1/OS resolves relative paths itself, so a command needs this only where it shows or compares paths (find,
   grep -r, mv's "same file" check, cp -r's "into itself" check, the tree walker).
   Ported from P8X os/commands/lib_apath.c 2026-09-23, changes: getcwd() for SYS_GETCWD, the . and .. folding
   is new (the P8X version only prefixed the CWD), the output is bounded. */
#include "lib_fs.c"
#define APLEN 128

int abspath(char *out, char *a) {
    char tmp[APLEN];
    int i, j, n, used;
    n = 0;
    if (*a != '/') { n = getcwd(tmp); tmp[n++] = '/'; }
    for (used = 0; a[used] && a[used] != ' '; used++) if (n < APLEN - 1) tmp[n++] = a[used];
    tmp[n] = 0;
    i = 0; out[0] = '/'; j = 1;                  /* fold the components into out */
    while (tmp[i]) {
        while (tmp[i] == '/') i++;
        if (!tmp[i]) break;
        n = 0;
        while (tmp[i + n] && tmp[i + n] != '/') n++;
        if (n == 1 && tmp[i] == '.') { i += n; continue; }
        if (n == 2 && tmp[i] == '.' && tmp[i + 1] == '.') {
            if (j > 1) { j--; while (j > 1 && out[j - 1] != '/') j--; if (j > 1) j--; }
            i += n; continue;
        }
        if (j > 1) out[j++] = '/';
        while (n) { out[j++] = tmp[i++]; n--; }
    }
    out[j] = 0;
    return used;
}
