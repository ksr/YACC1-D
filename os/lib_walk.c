/* lib_walk.c - walk a directory tree without recursion (Y1/OS, 2026-09-23): tree, find, dir -R, grep -r, cp -r.
     walk_open(path)  start at a directory (relative or absolute; "" = the current one); 1 ok, 0 not a directory
     walk_next()      the next entry, depth first in directory order ("." and ".." skipped); 1 = one in
                      went (the 32-byte entry) / wname (its name) at depth wlev (0 = in the start directory),
                      wpath = the directory holding it (absolute); 0 = the walk is over
     wdown            walk_next sets it to 1 for a directory, which the NEXT walk_next then enters; clear it
                      first to skip that subtree (dir without -R, find's pruning)
     walk_full(out)   out <- wpath + "/" + wname (WFLEN = 144 bytes)
     walk_close()     stop early (closes the directory handle)
     wtrunc           1 when a directory was not entered because WMAX (8) levels or APLEN path bytes ran out
   How: an explicit level stack instead of the P8X recursion (y1cc rejects recursion, and its static frames would
   share one set of locals anyway). Each level keeps the length of wpath and how many entries of that directory
   were read; ONE directory handle is open at a time: entering a subdirectory closes the parent's handle, and
   leaving it reopens the parent by path and skips the entries already read. So a walk costs one of the four
   handles, and a command can open files (grep -r) or create them (cp -r) along the way.
   The P8X walkers (tree/find/dir/grep/cp) recorded each level's children before descending because the BIOS
   FNEXT cursor was global; here the order is plain pre-order: a directory's contents follow it directly. */
#include "lib_apath.c"
#define WMAX 8
#define WFLEN 144
char wpath[APLEN], went[32], wname[13];
int wplen[WMAX], widx[WMAX], wlev, wdh, wdown, wtrunc;

int walk_open(char *path) {
    int n;
    abspath(wpath, path);
    n = strlen(wpath);
    wdown = 0; wtrunc = 0; wlev = 0; wplen[0] = n; widx[0] = 0;
    wdh = opendir(wpath);
    return wdh != 0;
}

void walk_close() { if (wdh) fclose(wdh); wdh = 0; }

int walk_next() {
    int n, i;
    if (wdown) {                                 /* enter the directory walk_next returned last */
        wdown = 0;
        n = wplen[wlev];
        if (wlev + 1 < WMAX && n + 14 < APLEN) {
            walk_close();
            if (n > 1) wpath[n++] = '/';
            strcpy(wpath + n, wname);
            wlev++; wplen[wlev] = n + strlen(wname); widx[wlev] = 0;
        } else wtrunc = 1;
    }
    while (1) {
        if (!wdh) {                              /* (re)open this level and skip what was read before */
            wdh = opendir(wpath);
            if (wdh) for (i = widx[wlev]; i; i--) if (!readdir(wdh, went)) break;
        }
        if (wdh && readdir(wdh, went)) {
            widx[wlev]++;
            ent_name(went, wname);
            if (wname[0] == '.' && (!wname[1] || (wname[1] == '.' && !wname[2]))) continue;
            wdown = ent_isdir(went);
            return 1;
        }
        walk_close();                            /* this level is done: back to the parent */
        if (wlev == 0) return 0;
        wlev--; wpath[wplen[wlev]] = 0;
    }
}

void walk_full(char *out) {
    int n;
    strcpy(out, wpath); n = strlen(out);
    if (n > 1) out[n++] = '/';
    strcpy(out + n, wname);
}
