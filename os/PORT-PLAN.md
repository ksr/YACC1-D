# PORT-PLAN — bringing the P8X/OS commands to Y1/OS

Survey date 2026-09-23; **waves 0-2 done the same day (section 8, and the Status column of section 2)**. Read-only survey of `~/Developer/p8x/os/commands/*.c` (46 commands + 18 shared
`lib_*.c` helpers), `p8x/os/man/` (86 pages), the P8X shell's built-in dispatch (`p8x/os/p8xos.asm`
`DISPATCH:`/`KWTAB`), `p8x/os/run.sh` (what lands on the disk), and the development tools under `p8x/apps/`,
`p8x/basic/`, `p8x/compiler/`. Target: Y1/OS (`os/y1os.c`, programs at `$5000..$CFFF` = 32K, y1cc static
frames, serial console only). The port is a **fork** (Ken, 2026-09-22/23): nothing is kept in sync with P8X
afterwards, so the P8X sources are a starting point, not a shared tree.

Sizes quoted as "p8cc B" are the P8X binaries built for this survey with `clib.py` + `p8cc.py` + `p8xasm.py`
into a scratch directory (code + global data, as the P8X `/binc` build). y1cc images have measured 0.76–0.88x
the p8cc size for the same source (`software/compiler/README.md`), so the Y1 estimate is roughly
**0.8 x p8cc B** plus any buffer the P8X version kept outside its image (`RDBUF` at `$FC00`, the assembler's
symbol table, the compiler's arenas).

---

## 1. What every port has to change (the mechanical pass)

These apply to the whole set and are what "PORT AS-IS" means below: nothing command-specific, only this pass.

1. **`//#use X` becomes `#include "lib_X.c"`.** y1cc has a textual `#include` (each file once, searched beside
   the source then in `lib/`), so P8X's host-side `tools/clib.py` splicing is not needed. Keep the lib files
   named `lib_<token>.c` so the P8X man pages for the libraries (`man stdin`, `man glob`, ...) stay true.
2. **`lib_abi.c` is replaced, not ported.** `os/lib_abi.c` already names the ROM vectors; it gains the file-API
   entry points the concurrent OS work defines. OS-PLAN decision 6: the jump table keeps the *shape* of the
   P8X `$20xx` syscalls, with P1/A becoming R7/ACC.
3. **`bios()` no longer returns a carry bit.** P8X's `bios()` packs `A | carry<<8`, and the commands test
   `& 256` for "not found" / "end of file" / "end of directory" — **69 sites** across the set (cat 3, cp 4,
   del 1, cmp 4, diff 2, dir 4, grep 2, find 1, mv 3, md 4, man 3, tree 1, touch 2, vi 2, lib_stdin 3,
   lib_globx 1, lib_abi 3, the rest in graphics apps). y1cc's `bios(addr, r7, acc)` returns ACC (8 bits) and
   `call(addr)` returns R3 (16 bits, no arguments). **Every one of those 69 tests is rewritten** to whatever
   status convention the file API settles on (see section 5, item A: this is the one design point the API and
   the port must agree on first).
4. **`RDBUF` (`$FC00`) goes away.** P8X commands hand FOPEN a 512-byte page just below the stack, outside their
   image. On the Y1 the read buffer is either the API's own (preferred: the OS owns one per open handle) or a
   `char rdbuf[512]` inside the program (costs 512 B of the 32K per command).
5. **Argument tail.** P8X commands scan `argstr()` until NUL, CR (13) or space; Y1/OS's ARGBUF is 64 bytes,
   NUL-terminated (`$0F40..$0F7F`). The scans still work; the 64-byte cap bites `dep addr b b b ...`,
   `awk 'program' file`, `sed s/old/new/g file` and `cp -r /LONG/PATH /OTHER/LONG/PATH`. Either widen ARGBUF
   (there is room: the OS data is below `$5000`) or accept the limit and say so in the man pages.
6. **Console EOF.** P8X `getchar()` returns 65535 at end of input (`SYS_GETC` carry: Ctrl-D on the console,
   EOF on a `<` file). y1cc's `getchar()` returns 0 at end of input on the emulator and blocks on the machine
   (`uartin`). `lib_stdin.c`'s `nextc()` relies on the 65535 sentinel, so the filters (`wc`, `sort`, ...) with
   no file argument need the OS's `getc` to define EOF (Ctrl-D -> 65535) — otherwise they never finish when
   reading the console.
7. **Raw console.** `CONIN` (no echo), `CONOUT`, `CONST` map to `UARTIN`, `CHAROUT`, `CONST` — but the lib_abi
   header says `UARTIN` **echoes on the machine**. `vi`, `more`, `md`, `dump` need a key read *without* echo.
   Either the OS exposes a raw-in vector or the ROM gets a no-echo entry (section 5, item F).
8. **Case.** Y1/OS upper-cases the command word for the `/BIN` lookup and file names are case-sensitive;
   P8X names are case-insensitive globs. `lib_glob.c` already folds case for matching; `man` must upper-case
   or the `/MAN` files must be installed in the case the command uses (the P8X pages are lower-case names).
9. **Language.** y1cc accepts p8cc's subset **plus** `++ --`, `+=`, `?:`, `switch`, `break`/`continue` and
   `#define`, so P8X's "native-cc dialect" (no `++`, decls at top, callee before caller) compiles unchanged —
   nothing needs rewriting for syntax. `char` is unsigned on both; `int` is unsigned on both (the P8X `& 255`
   masks are harmless). y1cc has no signed types: P8X code that does `0 - eval(3)` (sheet) is fine, unsigned.
10. **No recursion** (at the time of the port; y1cc supports recursion since 2026-09-24, see its README). y1cc rejected
    any function reachable from itself (call graph checked at compile time).
    Section 3 lists every recursive function found; the shared ones (`gmatch`, `matchhere`) are fixed once in
    wave 0, the per-command ones (`walk`, `collect`, `copy_tree`, `outn`, `eval`) in their wave.
11. **Memory constants in help text and man pages**: `$5900` (P8X TPA) -> `$5000`; `/d1`, `mount`, `screen`,
    `finder`, `kermit` lines dropped; `bin` -> `BIN`. `dump`/`dep`/`examine` warn "don't touch `$5000..`"
    (they live there) instead of `$5900`.
12. **Line endings.** y1cc `puts` appends LF only; P8X commands emit LF too (`putchar(10)`), `vi` writes
    VT100 escapes through `CONOUT`. Files are LF-terminated on both. No CR/LF surprises found.

---

## 2. The command table

Columns: **Src** = lines in `p8x/os/commands/<name>.c`; **p8cc B** = P8X binary; **Cat** = category;
**Calls** = BIOS/OS entry points used, via `//#use abi` names (plus the libs it splices);
**Rec** = recursion (own functions / through a spliced lib); **P8X-specific** = what ties it to the P8X;
**Verdict** = PORT AS-IS (mechanical pass only) / PORT WITH CHANGES / DEFER / SKIP (the survey);
**Status** = what the port did (2026-09-23, section 8): DONE (the mechanical pass, maybe a small extra) / CHANGED (and why) /
DEFERRED / SKIPPED / DROPPED.

Every command below also has a hand-assembled twin in `p8x/os/commands-asm/*.asm` (P8X ISA) for the 28 names
`dir pwd cat wc grep cp mv head tail more sort uniq sed find diff tree vi touch man dep dump examine disasm
awk cmp image del help`; those are **ignored** for the port (P8X assembly), noted here only so nobody looks
for them later. On the P8X the asm twins ARE `/bin`; the C builds ship to `/binc`. On the Y1 the C build is
the only build.

### 2.1 Console-only (5)

| Name | Src | p8cc B | Purpose | Calls | Rec | P8X-specific | Verdict | Status |
|---|---|---|---|---|---|---|---|---|
| pwd | 29 | 282 | print the CWD | SYS_GETCWD | none | none | **PORT AS-IS** (needs `getcwd`) | DONE (getcwd) |
| help | 44 | 2,148 | the shell command reference (static text) | puts | none | text names P8X built-ins, `/d1`, graphics, kermit, `$5900` | **PORT WITH CHANGES**: rewrite the text for the Y1/OS built-ins + ported /BIN set | CHANGED: text rewritten for the Y1/OS built-ins and /BIN set |
| dep | 80 | 893 | deposit hex bytes: `dep addr b b ...` | poke; lib_err | none | warns about the `$5900` TPA | **PORT AS-IS** (ARGBUF 64 B caps the byte list; text `$5000`) | DONE |
| dump | 101 | 1,127 | hex-dump 256 bytes from `addr`, key pages, `.` quits | peek, CONIN | none | none | **PORT AS-IS** (CONIN -> raw key; needs the no-echo read, item F) | CHANGED: key = conin (no echo), q or Ctrl-D quit too, LF line ends |
| examine | 96 | 1,175 | interactive examine/modify from `addr` | peek, poke, getchar | none | relies on SYS_GETC echo behaviour | **PORT AS-IS** (getchar echo differs: check the Enter handling, ~5 lines) | CHANGED: conin without echo, examine echoes the digits; Enter = CR or LF |

### 2.2 File readers and stdin filters (14)

All of these use `lib_stdin.c` (file-or-stdin, glob expansion) unless noted; the file side is
FRESOLVE + FOPEN + FGETB + SYS_GETCWD, the glob side adds FOPENDIR/FNEXT/SYS_OPENCWD/SYS_DIRENTRY/FSDIRBUF.

| Name | Src | p8cc B | Purpose | Calls | Rec | P8X-specific | Verdict | Status |
|---|---|---|---|---|---|---|---|---|
| cat | 120 | 4,498 | print file(s)/glob, or stdin -> stdout | FRESOLVE FOPEN FGETB SYS_GETCWD FSDIRBUF; libs glob globx dirent err | lib: gmatch | `FSDIRBUF` page `$FA` dance so a glob walk does not clobber the open `>` write stream | **PORT AS-IS** once wave 0 libs exist; drop the FSDIRBUF call if the Y1 API separates dir and write buffers | CHANGED: several names, globs and `-` (console) via lib_stdin; replaced `cat2`; replaces the built-in (/BIN first) |
| wc | 134 | 5,715 | lines/words/bytes (24-bit) of file/glob/stdin | stdin lib | lib: gmatch | none | **PORT AS-IS** (replaces the current raw-sector `os/commands/wc.c`) | CHANGED: several names; 32-bit counters (lib_num) for the 24-bit byte arrays |
| head | 55 | 4,711 | first N lines | stdin lib | lib: gmatch | none | **PORT AS-IS** | DONE (+ several names) |
| tail | 93 | 15,450 | last N lines (N<=40, 10K ring buffer) | stdin lib | lib: gmatch | none | **PORT AS-IS** (10,240 B buffer is inside the image: ~13K on Y1, fits) | DONE (+ several names) |
| more | 78 | 4,760 | page 23 lines, key from the *console* not stdin | stdin lib + CONIN | lib: gmatch | none | **PORT AS-IS** (raw key, item F) | CHANGED: the pager moved to lib_more.c (shared with man, md) |
| sort | 108 | 15,619 | sort <=128 lines of <=79 chars, in memory | stdin lib | lib: gmatch | none | **PORT AS-IS** (10K buffer) | CHANGED: 200 lines (was 128), insertion sort of an index, a warning when lines are dropped |
| uniq | 64 | 5,475 | collapse adjacent duplicates | stdin rdline streq | lib: gmatch | none | **PORT AS-IS** | DONE (strcmp for streq) |
| sed | 116 | 7,031 | `s/re/new/[g]` on file/stdin | stdin rdline regex | lib: gmatch, matchhere | none | **PORT AS-IS** after the regex de-recursion (wave 0) | DONE (iterative lib_regex) |
| awk | 242 | 9,092 | one-rule awk: fields, `/re/ {print $N ...}`, NR/NF | stdin regex | lib: gmatch, matchhere | none | **PORT AS-IS** after wave 0 (program is one quoted arg: ARGBUF 64 B) | DONE (iterative lib_regex; several input names) |
| cmp | 125 | 10,228 | byte compare, file1 in an 8K buffer, file2 streamed (single read stream) | FRESOLVE FOPEN FGETB; apath err | none | the ONE-read-stream BIOS forces the buffer | **PORT AS-IS**; if the Y1 API gives two read handles it can stream both (optional simplification, -8K) | CHANGED: both files streamed through two handles (no 8K limit) |
| diff | 147 | 17,516 | prefix/suffix line diff, <=96 lines x 79 per file (15K buffers) | FRESOLVE FOPEN FGETB; apath err | none | same single-stream shape | **PORT AS-IS** (~15K image on Y1; fits) | CHANGED: 150 lines per file (was 96), a warning past that |
| man | 78 | 804 | stream `/man/<name>` | FRESOLVE FOPEN FGETB PUTS | none | `/man` prefix, error via raw PUTS | **PORT AS-IS** (`/MAN` + case rule, item 8) | CHANGED: /MAN + upper-cased name, through the lib_more pager; no argument = the page list |
| md | 417 | 9,801 | render Markdown on the console with a `--More--` pager | FRESOLVE FOPEN FGETB CONIN; apath | none | none (pure text: headings, lists, code, emphasis) | **PORT AS-IS** (raw key) — needed for `/DOCS/*.MD` | CHANGED: lib_more pager; consecutive lines join into one paragraph (the Y1 docs are hard-wrapped); indented tables/fences; /DOCS fallback and list |
| grep | 225 | 10,953 | basic-regex line filter; `-r` walks the CWD tree | stdin regex globx dirent + FNEXT SYS_OPENCWD FSDIRBUF SYS_GETCWD | **own: collect** (the `-r` walk); lib: gmatch, matchhere | `FNEXT` cursor is global BIOS state -> two-phase record-then-descend; 48 x 96 path list | **PORT WITH CHANGES**: `collect()` iterative (explicit dir stack, ~40 lines); listed again under directory tools because of `-r` | CHANGED: `-r` walks with lib_walk and searches as it goes (no 36-file cap), takes a start dir; `NAME:` prefix with several files |

### 2.3 File writers (4)

| Name | Src | p8cc B | Purpose | Calls | Rec | P8X-specific | Verdict | Status |
|---|---|---|---|---|---|---|---|---|
| touch | 69 | 877 | create empty files if missing (exists-test = open for read) | FRESOLVE FOPEN FWOPEN FCLOSE; apath | none | "resolve before FWOPEN" ordering (SBUF sharing) | **PORT AS-IS** (`create` + `close`; the ordering note vanishes if handles have their own buffers) | DONE (fresolve + fcreate/fclose) |
| del | 48 | 794 | tombstone file(s) | FRESOLVE FDELETE; apath | none | none | **PORT AS-IS** (`delete(path)`) | CHANGED: globs added; the message names the file; replaces the built-in |
| mv | 132 | 5,678 | move/rename = copy + delete; glob source into a dir | FRESOLVE FOPEN FGETB FWOPEN FPUTB FCLOSE FDELETE FOPENDIR; apath streq globx dirent err | lib: gmatch | no rename primitive in P8XFS; SBUF ordering | **PORT AS-IS**; becomes ~40 lines if the Y1 API adds `rename` (section 5, item C) | CHANGED: RENAME syscall within a directory (item C); copy + delete across directories keeps load/exec; directories rename in place; one file can go into a directory |
| cp | 209 | 6,556 | copy file / glob / `-r` subtree, makes dirs via SYS_MKDIR | FRESOLVE FOPEN FGETB FWOPEN FPUTB FCLOSE FOPENDIR FNEXT FSDIRBUF SYS_MKDIR; apath dirent globx glob err | **own: copy_tree**; lib: gmatch | record-then-descend (global FNEXT cursor) | **PORT WITH CHANGES**: `copy_tree()` iterative (explicit stack of (src,dst,dir-LBA), ~60 lines) | CHANGED: `-r` via lib_walk (one dir handle + read + write handle); load/exec kept (item E); a file into a directory; quiet |

### 2.4 Directory tools (3)

| Name | Src | p8cc B | Purpose | Calls | Rec | P8X-specific | Verdict | Status |
|---|---|---|---|---|---|---|---|---|
| dir | 406 | 7,339 | list a dir/glob, sorted by name or `-S` size, `-R` recursive; 24-bit sizes | FOPENDIR FNEXT FSDIRBUF SYS_OPENCWD + dirent (SYS_DIRENTRY, SYS_OPENDIR); glob apath err | **own: walk** | descends by 16-bit dir LBA (pokes `LBA1` on the P8X side historically); FSDIRBUF | **PORT WITH CHANGES**: `walk()` iterative (per-level child-LBA arrays already exist; turn the recursion into a level stack, ~50 lines). Y1/OS's built-in `dir` shows load addresses: add that column (readdir must expose load/exec) | CHANGED: `-R` via lib_walk as `ls -R` blocks with headers; load-address column; replaces the built-in |
| find | 158 | 3,001 | recursive name match (glob or substring) under the CWD | FNEXT FSDIRBUF SYS_GETCWD SYS_OPENCWD; glob dirent | **own: walk** | same record-then-descend | **PORT WITH CHANGES**: iterative walk (~40 lines) | CHANGED: lib_walk (true pre-order), optional start dir |
| tree | 87 | 1,031 | depth-first indented tree of the CWD | FNEXT FSDIRBUF SYS_OPENCWD; dirent | **own: walk** | same | **PORT WITH CHANGES**: iterative walk (~30 lines; the simplest of the three — do it first and reuse the shape) | CHANGED: lib_walk (true pre-order), optional start dir |

### 2.5 System / P8X-specific (2)

| Name | Src | p8cc B | Purpose | Calls | Rec | P8X-specific | Verdict | Status |
|---|---|---|---|---|---|---|---|---|
| disasm | 164 | 3,990 | disassemble `[start,end)` from memory | peek; lib_distab (143 P8X opcodes, generated from `genucode.OPC`) | none | the entire opcode table is the P8X ISA | **SKIP**. A YACC1 `disasm` is a new ~200-line tool whose table is generated from `software/assembler/yacc1.def` (the same generator idea as `gen_p8xdis.py`); the driver loop in `disasm.c` (hex parse, `AAAA: bb bb MNEMONIC`) is reusable | SKIPPED (as the verdict) |
| kermit | 98 | 1,597 | file transfer over the SECOND ACIA (`$FF08/$FF09`) | FRESOLVE FOPEN FGETB FWOPEN FPUTB FCLOSE FDELETE + peek/poke of the ACIA | none | the 2nd serial port | **SKIP for now** (single UART on the YACC1). Revisit as DEFER if the IO card's UART becomes a second port: the packet logic is 60 lines and port-agnostic behind `a2put`/`a2get` | SKIPPED (as the verdict) |

### 2.6 Graphics or window manager (17)

All drive the GL port `$FF50..$FF57` through `lib_gfx.c`/`lib_g3d.c` or the resident WM syscalls
`$2027..$2051`; the YACC1 has no graphics card, and OS-PLAN phase 4 is a text-mode 6845 video card, so
none of these will ever run as written.

| Name | Src | p8cc B | Purpose | Calls | Rec | Verdict | Status |
|---|---|---|---|---|---|---|---|
| camera | 98 | 10,741 | look-at camera, redraw scene | gfx g3d g3cam, GL regs | lib: glbyt/glwrd | **SKIP** (GL engine) | SKIPPED (as the verdict) |
| clsave | 92 | 2,165 | save a GL command list to a file | FRESOLVE FWOPEN FPUTB FCLOSE + GL | lib | **SKIP** | SKIPPED (as the verdict) |
| cube | 207 | 19,115 | spinning wireframe cube | gfx g3d | lib | **SKIP** | SKIPPED (as the verdict) |
| gl | 116 | 2,396 | send a GL script file to the card | FRESOLVE FOPEN FGETB + GL | lib | **SKIP** | SKIPPED (as the verdict) |
| house | 147 | 2,337 | the animated house demo | gfx | lib | **SKIP** | SKIPPED (as the verdict) |
| image | 202 | 4,033 | view/grab P8I pictures | file API + GL + CONIN | lib | **SKIP** | SKIPPED (as the verdict) |
| page | 42 | 917 | framebuffer page sync/flip | gfx | lib | **SKIP** | SKIPPED (as the verdict) |
| rotate | 75 | 1,447 | set rotation matrix, redraw | gfx | lib | **SKIP** | SKIPPED (as the verdict) |
| tri | 151 | 15,948 | one 3D triangle from the shell | gfx g3d | lib | **SKIP** | SKIPPED (as the verdict) |
| screen | 49 | 464 | glass-TTY on/off (`GCONEN`, `GCLS $014E`) | peek/poke OS flag | none | **SKIP** (no glass TTY) | SKIPPED (as the verdict) |
| paint | 436 | 10,186 | vector paint, mouse via lib_ptr | GL + SYS_EXEC + ptr | none | **SKIP** | SKIPPED (as the verdict) |
| desk | 420 | 15,528 | the client-side window-system demo (lib_wm) | file API + SYS_EXEC + wm + ptr | none | **SKIP** | SKIPPED (as the verdict) |
| wdesk | 533 | 9,347 | desktop client on the resident WM kernel (`SYS_WK*`, `SYS_RUNSH`) | 11 WM syscalls + file API | none | **SKIP** | SKIPPED (as the verdict) |
| sheet | 552 | 16,323 | spreadsheet for the graphics desktop | file API + GL + SYS_EXEC | **own: eval** (expression parser) | **DEFER**: the cell model + `eval` (precedence climbing, ~100 lines) are console-portable; the grid drawing is GL. A VT100 version is a rewrite of ~200 lines, only if wanted | DEFERRED (as the verdict) |
| finder | 590 | 12,762 | full-screen file browser + app launcher (two-mode P4) | FOPENDIR FNEXT FRESOLVE FWOPEN FPUTB FCLOSE FDELETE SYS_GETCWD SYS_RUNSH + GL | none | **DEFER** until a text console exists; also needs `SYS_EXEC`/`SYS_RUNSH` (chain to another program) which Y1/OS does not have | DEFERRED (as the verdict) |
| term | 87 | 1,493 | on-screen shell in the app frame | SYS_EXEC SYS_RUNSH GCLS GTRESUME | none | **SKIP** (it is the glass TTY + exec chaining; the serial console is already a terminal) | SKIPPED (as the verdict) |
| write | 222 | 5,853 | full-screen text editor for the GL display (2K buffer) | file API + GL + ptr + SYS_EXEC | none | **DEFER**: `vi` covers the serial console; `write` only makes sense on the phase-4 video card | DEFERRED (as the verdict) |

### 2.7 Development tools (1 in os/commands + 4 elsewhere)

| Name | Source | Lines | P8X binary | Purpose | Calls | Rec | P8X-specific | Verdict | Status |
|---|---|---|---|---|---|---|---|---|---|
| vi | `os/commands/vi.c` | 442 | 15,837 (9,040 of it the text buffer) | modal VT100 editor: hjkl, i/a/A/o, x, dd, u, /pat, :w :q :wq | CONIN CONOUT FRESOLVE FOPEN FGETB FWOPEN FPUTB FCLOSE; apath | **own: outn** (decimal printer for ANSI args) | raw key without echo; `RDBUF` | **PORT WITH CHANGES**: `outn` iterative (10 lines); key read = no-echo vector (item F); ~13K on Y1, fits with room for a bigger buffer | IN PROGRESS in a separate session (2026-09-23): os/commands/vi.c |
| edit | `apps/p8xedit.asm` | 783 asm | 1,602 | line editor (L/A/I/D/W/Q), 12K buffer, root dir only | BIOS file calls | — | P8X assembly only, no C source | **PORT WITH CHANGES = rewrite in C** (~250 new lines: the command loop is trivial once `vi`'s file load/save code exists) — or skip it, `vi` supersedes it. Recommend: skip unless a non-VT100 terminal is in use | DEFERRED (wave 3; vi covers it) |
| asm | `apps/asm.c` + `apps/opctab.c` (generated) | 542 + 141 | 9,945 (C); asm twin 4,065 | two-pass P8X assembler on-target; hashed symbol table at `$A800..$D140` (1,664 symbols), `;#use` includes | FRESOLVE FOPEN FGETB FWOPEN FPUTB FCLOSE FDELETE FFIND FSDIRBUF SYS_GETCWD CONOUT PUTS | none | the P8X ISA table, the P8X source syntax (`.org/.byte/.word`, `LDP1 #`, `(P3+d)`), symbol-table addresses above `$D000` | **PORT WITH CHANGES (major)**: keep the two-pass driver, symbol hash and file plumbing; replace the opcode table with one generated from `yacc1.def` and the operand parser with the RC/asm dialect y1cc emits (`ORG/DB/DW/DS`, `MVIW Rn,imm`, `LDR R3,label`, case-folded labels <=29 chars). Tables must move under `$D000`: with ~8K of code there is room for ~1,000 symbols at `$A000..$CFFF`. Output must be a load-address-tagged /BIN file (item E). ~400 lines changed + a ~100-line generator | DEFERRED (wave 3) |
| cc | `apps/cc.c` (twin of `apps/p8xcc.asm` 10,182 B; host `compiler/p8cc.c` 2,174 lines) | 1,178 | 21,306 + ~11K of tables at `$D400..$F000` | native C compiler emitting P8X assembly | FRESOLVE FOPEN FGETB FSDIRBUF SYS_GETCWD | **21 recursive functions** (recursive-descent parser: `gexpr gterm gfact gunary stmt st_if st_while st_for funcdef ...`) | P8X back end; tables above `$D000`; ~32K total | **DEFER**. Blocked twice: y1cc has no stack-frame mode (the parser cannot compile) and the back end would have to be y1cc.py's (R3 accumulator, static frames) rewritten in C. That is the self-hosting milestone, not a port; expect ~1,500 new lines and a fit problem against 32K (P8X needed 39.8K of TPA plus tables) | DEFERRED (as the verdict) |
| basic | `basic/basic.c` (+ `glkwtab.c`); asm `basic/p8xbasic.asm` 9,347 B | 1,166 | 21,775 (C) | P8X BASIC with GL graphics keywords | CONIN CONOUT FRESOLVE FOPEN FGETB FWOPEN FPUTB FCLOSE FCREATE FFIND FLOADAT SYS_GETCWD + GL | **9 recursive functions** (`expr term factor stmt stmtline st_if st_run parget rgbtail`) | GL keyword table, P8X file calls, `PROG` at fixed addresses | **SKIP the P8X BASIC.** OS-PLAN phase 3 already decides: the YACC1's *own* ROM BASIC is re-assembled at a TPA address as `/BIN/BASIC`. `basic.c` only becomes interesting if that BASIC is ever replaced; it would need the parser de-recursed or y1cc stack frames, and the GL half (`T_LINE`, `T_GL`, `IMAGE`...) stripped | SKIPPED (as the verdict) |

`compiler/p8cc.c` (the host-sized self-hosting compiler, 265K of tables) is not a target program on either
machine and is out of scope.

### 2.8 Shared libraries (18) — what each becomes

| Lib | Lines | Used by | Recursion | Verdict | Status |
|---|---|---|---|---|---|
| lib_abi | 67 | everything | — | **REPLACE** with `os/lib_abi.c` + the file-API names (concurrent work) | DONE: os/lib_abi.c (+ os/lib_fs.c wrappers) |
| lib_mem | 21 (generated) | graphics + screen + asm/cc/basic | — | **REPLACE**: Y1 needs only `TPA $5000`, `TPATOP $D000`, `ARGBUF` (already in `os/lib_abi.c`) | DROPPED: TPA/TPATOP/ARGBUF are in lib_abi.c |
| lib_apath | 49 | del touch cp mv cmp diff md vi clsave gl image | none | **PORT AS-IS** (`getcwd`) | CHANGED: . and .. folded, output bounded (APLEN 128) |
| lib_stdin | 113 | cat wc grep head tail more sort uniq sed awk | lib: gmatch | **PORT WITH CHANGES**: API names, drop `RDBUF`, keep the 65535 EOF sentinel; `getchar()` EOF depends on item B | CHANGED: every word of the tail (files, globs, `-`), sepfiles, curname, notfound(); one handle at a time |
| lib_dirent | 50 | dir find tree cp grep cat globx desk finder wdesk | none | **PORT WITH CHANGES**: it is a veneer over `SYS_DIRENTRY` (18-byte snapshot: name[12], flag, len24, lba16) and `SYS_OPENDIR` (by LBA). If the Y1 `readdir` fills a struct, `de_*()` become one-line accessors | DROPPED: lib_fs.c readdir() fills a 32-byte entry, the ent_* accessors read it |
| lib_glob | 44 | cat wc grep head tail more sort uniq sed awk cp mv dir find | **gmatch is recursive** (`*` tries every suffix) | **PORT WITH CHANGES**: the classic iterative wildcard match (remember the last `*` position and backtrack there; ~35 lines, no stack) | CHANGED: iterative gmatch (one backtrack point) |
| lib_globx | 106 | the same + lib_stdin | lib: gmatch | **PORT WITH CHANGES**: opendir/readdir names; drop `FSDIRBUF` if handles own their buffers | CHANGED: its own opendir handle (no FSDIRBUF), isglob() |
| lib_regex | 86 | grep sed awk | **matchhere is recursive** (tail recursion on `c*`, `c+`, `c?`, and on the literal case) | **PORT WITH CHANGES**: with only single-character quantifiers the matcher can be made iterative with a small explicit backtrack stack of `(re, t)` pairs (depth <= pattern length; ~70 lines). Keep the P8X test cases (`grep`/`sed` c_*_test.sh inputs) as the oracle | CHANGED: matchhere with an explicit backtrack stack (32 points) |
| lib_rdline | 35 | uniq sed | none | **PORT AS-IS** | DONE |
| lib_streq | 17 | uniq mv | none | **PORT AS-IS** (or use `y1lib.c`'s `strcmp`) | DROPPED: y1lib.c strcmp |
| lib_err | 29 | most commands | none | **PORT WITH CHANGES**: `eputs()` writes to the *console* (raw `PUTS`/`CONOUT`) so `?errors` never land in a `>` file; on the Y1 that is `bios(CHAROUT, ...)` per byte — 10 lines. Matters only once redirection exists | CHANGED: putchar-based at first; since 2026-09-23 (redirection) bios(CHAROUT) per byte, as planned |
| lib_distab | 8 (generated) | disasm | — | **SKIP** (P8X opcodes) | SKIPPED |
| lib_gfx, lib_g3d, lib_g3cam | 187 / 603 / 100 | graphics | glbyt/glwrd (mutual) | **SKIP** | SKIPPED |
| lib_wm, lib_ptr, lib_ps2 | 297 / 158 / 153 | desk paint finder sheet term write | none | **SKIP** (WM, xterm mouse reports, PS/2 window `$FF58`) | SKIPPED |

### 2.9 The P8X shell built-ins (for the OS side, not the command port)

`p8xos.asm` `DISPATCH`/`KWTAB` keeps 17 words in the kernel: `load run save pack cd mkdir rmdir fsck path
exit mon format mount umount sh make bootload` (plus `<`/`>`/`>>`/`|` redirection, Tab completion and the
`history` ring documented in `man history`, `man sh`, `man make`). `dir pwd cat tree del help dump` were
moved OUT to `/bin` on the P8X; Y1/OS today has `dir cd pwd cat/type load run help exit` as built-ins.
Recommendation: keep Y1/OS's `dir`/`pwd`/`cat` built-ins as the bootstrap set (a freshly formatted card has no
`/BIN`, the P8X README's own argument for keeping `mkdir` resident) and let the ported `/BIN/DIR` (sorted, `-R`,
`-S`, globs), `PWD`, `CAT` (globs, stdin) coexist; the shell already falls through to `/BIN` for unknown
words, so the built-ins win only when typed exactly. `save pack mkdir rmdir fsck format` are Y1/OS write
support (BACKLOG); `path sh make bootload mount umount` are later.

---

## 3. Recursion inventory (y1cc rejects all of these)

| Function | Where | Shape | Fix |
|---|---|---|---|
| `gmatch` | lib_glob.c | `*` recurses on every suffix | iterative two-pointer match with one backtrack point |
| `matchhere` | lib_regex.c | tail-recursive on the rest of the pattern | explicit backtrack stack |
| `walk` | tree.c, dir.c, find.c | depth-first over subdirectories; per-level child-LBA arrays already exist because the FNEXT cursor is global | a level stack `(lba, child index)` sized by max depth (P8X used ~11 levels) |
| `collect` | grep.c (`-r`) | same walk, phase 1 of two | same level stack |
| `copy_tree` | cp.c (`-r`) | walk + mkdir + copy per level | same, with the (src, dst) path pair per level |
| `outn` | vi.c | recursive decimal printer | print into a 5-char buffer backwards |
| `eval` | sheet.c | precedence-climbing expression parser | operand/operator stacks (only if sheet is ever revived) |
| `glbyt`/`glwrd` | lib_gfx.c | mutual (first-call init) | graphics, skipped |
| 21 functions | apps/cc.c | recursive-descent compiler | blocked on y1cc stack frames |
| 9 functions | basic/basic.c | recursive-descent interpreter | skipped (ROM BASIC relocation instead) |

Everything else in the portable set is already iterative (the P8X authors kept `matchhere` single-function
and avoided mutual recursion because the native `p8cc.c` refused forward declarations — that discipline is
what makes this port cheap).

---

## 4. File-API calls the portable set needs (check the OS side against this)

Mapped from the P8X BIOS/OS names actually used by the commands in waves 0–3:

| P8X call | Used by | Y1 API call needed |
|---|---|---|
| `SYS_GETCWD` (path -> buf) | pwd, lib_apath, lib_stdin, find, grep, cat | `getcwd(buf)` |
| `FRESOLVE` + `FOPEN` (path -> read stream) | cat cmp diff grep head tail more sort uniq sed awk wc man md cp mv touch vi (+libs) | `open(path)` for read |
| `FGETB` (byte, carry = EOF) | the same | `getc(h)` / `read(h, buf, n)` with an explicit EOF result |
| `FWOPEN` + `FPUTB` + `FCLOSE` | cp mv touch vi (asm, edit later) | `create(path)`, `write(h, byte-or-buf)`, `close(h)` (registers the entry) |
| `FDELETE` | del mv (vi? no) | `delete(path)` |
| `SYS_MKDIR` | cp -r | `mkdir(path)` |
| `FOPENDIR` (by path) / `SYS_OPENCWD` (the CWD) / `SYS_OPENDIR` (by 16-bit LBA) | dir find tree grep cp lib_globx | `opendir(path)`; descending by LBA is optional if `opendir(cur + "/" + name)` is acceptable (slower, one resolve per level) |
| `FNEXT` + `SYS_DIRENTRY` (name[12], flag, 24-bit len, 16-bit LBA) | the same | `readdir(h, entry)` — the entry must carry name, file/dir flag, **24-bit length**, start LBA, and (Y1/OS's own `dir` shows it) **load/exec address** |
| `FSDIRBUF` (move the dir cursor off the shared write buffer) | dir find tree grep cp cat lib_globx | **nothing**, if every handle owns its buffer — the single biggest simplification available to the port (removes 7 call sites and the "resolve DST before FWOPEN" folklore in cp/mv/touch) |
| `CONIN` (raw key, no echo) | dump more md vi | a no-echo console read (item F) |
| `CONOUT` / `PUTS` (raw console, bypassing stdout) | vi lib_err man | `CHAROUT` exists; `STRINGOUT` exists |
| `CONST` | lib_ptr only | already in `os/lib_abi.c` |
| `SYS_GETC`/`SYS_PUTC`/`SYS_PUTS` (the redirectable streams) | every command via `getchar/putchar/puts` | y1cc builtins already go to the console; redirection is a shell feature (item B) |
| `SYS_EXEC`, `SYS_RUNSH`, `SYS_WK*` | graphics apps only | not needed for waves 0–3 |
| `chdir` | nobody (cd is a built-in) | not needed by the commands |
| `rmdir` | nobody (built-in) | not needed by the commands |

## 5. Things the concurrent file-API design may be missing (or must decide)

- **A. How a 16-bit or two-part result comes back.** y1cc `bios()` returns ACC (8 bits) and `call(addr)`
  returns R3 but takes no arguments. `getc` must distinguish 256 byte values from EOF; `readdir` returns
  a 24-bit length; `getcwd` fills a buffer. Options: (1) results in ACC with a status byte the program reads
  with `peek(OS_STATUS)`; (2) `bios()` returns 0..255 = byte and 255-with-status for EOF; (3) extend y1cc so
  `call()` takes arguments and the API is plain C functions in a jump table returning R3 (the cleanest: the
  API is then written and tested as C, and `lib_abi.c` becomes `#define open(p) ((int(*)(...))...)`, which
  y1cc cannot express — so it would be a compiler builtin). Whatever is chosen, it is what the 69 `& 256`
  sites become; decide it before wave 1, not after.
- **B. Console EOF and redirection.** The filters need `getchar()` to return 65535 at Ctrl-D (P8X `SYS_GETC`)
  or they hang on the console when no file is given. Shell `<file`, `>file`, `>>`, `|` are P8X shell features
  (`OUTCH`/`REDIRF`, `PIPE.TMP`), not in Y1/OS yet; the commands degrade gracefully (file argument instead of
  `<`), but `sort | uniq`, `cat *.C >ALL.C` wait for the shell. Recommend the API's console `getc` implements
  Ctrl-D now and the shell redirection lands as its own backlog item. **Done 2026-09-23**: `<` `>` `>>` `|` in the
  shell, CONOUT/KEYIN/STDIO syscalls, `y1cc --os` (`os/README.md`, `os/man/shell`).
- **C. `rename`.** P8XFS has no rename; P8X `mv` is copy + delete (132 lines, 5.7K). A `rename(old, new)`
  that rewrites the directory entry in place (same directory) would make `mv` a 40-line command and is cheap
  on the OS side (one entry rewrite). Optional.
- **D. Two read handles at once?** The P8X BIOS has ONE read stream, ONE write stream, ONE directory
  cursor. `cmp`/`diff` buffer file1 in memory, `dir -R`/`find`/`tree`/`grep -r`/`cp -r` record a level's
  entries before descending. If the Y1 API supports N open handles (each with its own 512-byte buffer), the
  ports keep their P8X shape (works with one handle) and can be simplified later; if it supports only one,
  nothing changes. State the number in the API doc.
- **E. `create` with load/exec addresses.** Y1/OS `run` uses the entry's load/exec; the P8X `FCLOSE` registers
  0/0 which the OS reads as "the TPA". The on-target assembler's output (wave 3) and `cp` of a `/BIN` program
  must preserve them: `create(path, load, exec)` or a `setexec(h, load, exec)` before `close`, and `cp` must
  copy them (P8X `cp` does not — a `cp`'d program on the P8X relies on the 0 = TPA default).
- **F. Raw console read without echo, and console status.** `vi` (modal keys), `more`/`md` (--More--),
  `dump` (page/quit key) need `CONIN`-style input. `UARTIN` echoes on the machine (per `os/lib_abi.c`); the ROM
  or the OS needs a no-echo entry, and `vi` also wants `CONST` (it has it) — nothing in the listed API covers
  this.
- **G. `seek` / file size / `stat`.** Not needed by any command in waves 0–3 (`tail` uses a ring buffer,
  `touch` tests existence by opening, sizes come from `readdir`). Skip unless `more` is ever made bidirectional.
- **H. Wildcard expansion** is done inside the commands (`lib_globx`, needs `opendir`/`readdir` on an
  arbitrary path + `getcwd`); the shell needs nothing. The 64-byte ARGBUF is the real limit (item 5 above).
- **I. Error output separate from stdout** (`eputs`): only matters once `>` exists; `CHAROUT` suffices. **Done
  2026-09-23**: `lib_err.c` eputs() is `bios(CHAROUT, 0, c)` per byte.
- **J. Directory entry snapshot vs live cursor.** `SYS_DIRENTRY` copies the current entry out so the program
  can keep it while the cursor moves; `readdir(h, entry)` filling a caller struct gives the same for free.

---

## 6. Porting order

### Wave 0 — the shared libraries and the mechanical recipe (prerequisite, ~400 lines)
`lib_abi.c` (exists; + API names), `lib_mem.c` (replace, 10 lines), `lib_apath.c`, `lib_rdline.c`,
`lib_streq.c` (as-is), `lib_err.c` (10 lines), `lib_stdin.c` (~30 lines changed), `lib_dirent.c` (~20),
`lib_globx.c` (~20), `lib_glob.c` (iterative `gmatch`, ~35 new), `lib_regex.c` (iterative `matchhere`, ~70 new).
Deliverable: a `os/lib/` directory the `Makefile` builds against, plus one "hello file" test per lib. Depends
on section 5 item A being settled. Effort: ~250 lines modified + ~150 new.

### Wave 1 — console-only and simple file readers (quick wins, ~300 lines touched over 2,127 source lines)
`pwd` `help` (text rewrite, 40 lines) `dep` `dump` `examine` `man` `cat` `wc` (replaces the raw-sector
stand-in) `head` `tail` `more` `sort` `uniq` `sed` `awk` `cmp` `diff` `md`. Each is the mechanical pass
(`#include`, `& 256` rewrite, `RDBUF`, help text) — 10–15 lines per command. All fit comfortably: the largest
(`diff` 17.5K p8cc, ~15K on Y1) leaves half the TPA free. Bring the `/MAN` pages for these 18 + the Y1/OS
built-ins (`cd dir pwd cat load run help exit mon`) + the 11 library pages, and the `/DOCS/*.MD` idea
(`md` reads them). Needs from the OS: `open/getc/close`, `getcwd`, console EOF, raw key.

### Wave 2 — file writers and directory tools (~350 lines touched over 1,334 source lines)
`touch` `del` `mv` (as-is) then `tree` (first iterative walk, the template) `find` `dir` `grep -r` `cp -r`
(recursion rewrites ~180 lines total + mechanical ~170). Needs from the OS: `create/write/close/delete/mkdir`,
`opendir/readdir` with the entry fields listed in section 4, and a decision on item D. Also the moment to
decide whether `/BIN/DIR` replaces the built-in `dir` (it is 7.3K p8cc, ~6K on Y1, sorted, 24-bit sizes, `-R`).

### Wave 3 — development tools (~550–800 lines)
- `vi` (~80 lines: `outn`, no-echo key, file API). ~13K image; the text buffer can grow from 9K to ~16K.
- `asm` (~400 lines changed + ~100-line table generator from `yacc1.def`): the on-target assembler for the
  RC/asm dialect y1cc emits. Size: ~8K code + symbol table under `$D000` (~1,000 symbols at `$A000..$CFFF`).
  Needs item E (load/exec on `create`).
- `edit`: skip (P8X assembly only; `vi` covers it) unless a ~250-line C rewrite is wanted for dumb terminals.
- `cc`: DEFER (needs y1cc stack frames and a YACC1 back end in C; the 32K TPA is also too small for the P8X
  design's tables — the P8X needed ~40K + tables). Track under the compiler backlog, not the port.
- `basic`: SKIP the P8X one; OS-PLAN phase 3 relocates the YACC1 ROM BASIC as `/BIN/BASIC`.
- Sizes against the 32K area: every wave-1/2 command < 16K; `vi` ~13K; `asm` ~8K + tables; `cc` ~32K
  (does not fit); `basic.c` ~18K + program buffer (fits, if it were ever wanted).

### Deferred (graphics / video-card era)
`write`, `finder`, `sheet` (console re-implementations are plausible once a screen + keyboard exist, phase 4);
`kermit` (second UART). 4 commands.

### Skipped (P8X-specific)
`disasm` (P8X ISA; write a YACC1 one from `yacc1.def` later), `screen`, `term`, and the 13 GL/WM programs
`camera clsave cube gl house image page rotate tri paint desk wdesk` plus the libs `gfx g3d g3cam wm ptr ps2
distab`. 16 commands.

### Man pages and docs
The P8X `os/man/` is 86 plain-text pages (3,561 lines, ~72 columns, NAME/SYNOPSIS/DESCRIPTION/OPTIONS/
EXAMPLES/SEE ALSO). Bring over as text: the pages for every ported command (waves 1–3: ~28), the Y1/OS
built-ins (`cd dir pwd cat load run help exit mon`, editing each for Y1/OS behaviour), and the library pages
(`abi apath dirent err glob globx regex stdin rdline streq mem`). Install them as `/MAN/<name>` from
`os/man/` by the Y1 `Makefile` (the P8X `run.sh` globs `os/man/*`), with the `man` command from wave 1.
Rewrite, don't copy blindly: `$5900`, `/d1`, `screen`, `SYS_*` numbers and the `-h` conventions differ. The
P8X `run.sh` also ships eleven `.MD` docs to `/docs` for `md`; the Y1 equivalents are `docs/system/OS-PLAN.md`,
`os/README.md`, `software/compiler/README.md`.

### Testing
The P8X has a per-command host harness (`emulator/test/c_*_test.sh`) with expected outputs; Y1/OS has
`tests/os/run.py` scripted sessions on both emulators. Add one session per ported command reusing the P8X
expected output where the semantics are unchanged (`sort`, `uniq`, `grep`, `sed`, `awk`, `wc`, `diff`, `cmp`
are pure text-in/text-out and their P8X expectations transfer verbatim).

---

## 7. Counts

| Category | Commands | Verdicts |
|---|---|---|
| console-only | 5 (pwd help dep dump examine) | 4 as-is, 1 with changes (help text) |
| file-read | 14 (awk cat cmp diff grep head man md more sed sort tail uniq wc) | 13 as-is, 1 with changes (grep -r) |
| file-write | 4 (cp mv del touch) | 3 as-is, 1 with changes (cp -r) |
| directory | 3 (dir find tree) | 3 with changes (iterative walk) |
| system / P8X-specific | 2 (disasm kermit) | 2 skip |
| graphics or WM | 17 | 3 defer (write finder sheet), 14 skip |
| development tool | 5 (vi + asm cc basic edit) | vi + asm with changes, edit rewrite-or-skip, cc defer, basic skip |
| **total** | **50** (46 in os/commands + 4 apps) | **20 as-is, 9 with changes, 5 defer, 16 skip** |
| shared libs | 18 | 4 as-is, 6 with changes, 2 replace, 6 skip |
| shell built-ins (OS side) | 17 on P8X, 8 on Y1/OS | write support + path/sh/make later (BACKLOG) |
| man pages | 86 | ~48 to bring over as edited text |

Effort in lines of C to touch: wave 0 ~400, wave 1 ~300 (+40 help text), wave 2 ~350, wave 3 ~550–800
(vi 80, asm ~500, edit 250 optional). About 1,600–1,900 lines of C over ~5,500 lines of ported source, most
of it the mechanical pass; the only design work is the iterative matchers/walkers and the assembler's front end.

---

## 8. What was done (2026-09-23: waves 0, 1 and 2)

The API questions of section 5 were settled by Y1/OS v0.1 before the port began (`os/README.md`): every syscall
returns a full 16-bit word, 65535 = end of file / end of console input (item A: the 69 `& 256` tests became
`== 65535` or 0 tests); `conin()` is Ctrl-D-terminated and echo-free (items B, F); `RENAME` exists (item C); four
handles, each with its own 512-byte buffer (item D, so every `FSDIRBUF` call and the "resolve DST before FWOPEN"
folklore went away); `fcreate(path, load, exec)` (item E: cp and mv keep load/exec); ARGBUF is 127 characters
(item 5).

**Wave 0 - the libraries** (`os/lib_*.c`, each `#include`s what it needs; y1cc includes a file once):
`lib_stdin.c` (every word of the tail: files, globs, `-` for the console, read as one stream; `sepfiles` ends each
file with a line feed for the line tools; `curname` for grep's prefix), `lib_rdline.c`, `lib_glob.c` (iterative
`gmatch`: one backtrack point), `lib_globx.c` (`glob_expand` on its own directory handle, `isglob`), `lib_regex.c`
(`matchhere` with an explicit stack of choice points: `*`/`+` resume with one more repetition, `?` with none; same
match order as the recursive P8X one, checked on 18 cases), `lib_apath.c` (absolute path, `.`/`..` folded),
`lib_err.c`, and three new ones: **`lib_walk.c`** (the recursion-free tree walker every recursive command now uses:
a level stack of path length + entries read, ONE directory handle, closed on the way down and reopened and skipped
forward on the way up, 8 levels; true pre-order), **`lib_more.c`** (the `--More--` pager of more, man and md),
**`lib_num.c`** (32-bit counts as two ints). Dropped: `lib_mem`, `lib_dirent` (the `ent_*` accessors of lib_fs.c),
`lib_streq` (y1lib `strcmp`).

**Wave 1** pwd help dep dump examine man cat wc head tail more sort uniq sed awk cmp diff md; **wave 2** touch del
mv tree find dir grep cp. `cat2` (the v0.1 API test) is gone, `cat` replaces it; the v0.1 `wc` and `cp` were
replaced by the ports. Every command's header comment says what it does, its options, and "ported from P8X ...,
changes: ...".

Sizes (image + uninitialised data, against the 32,768-byte program area $5000..$CFFF; `make -C os sizes`, and the
build fails a program over 32K):

| Wave | Command | Image | Data | Total |
|---|---|---|---|---|
| 1 | pwd | 186 | 69 | 255 |
| 1 | help | 1,739 | 1 | 1,740 |
| 1 | dep | 665 | 21 | 686 |
| 1 | dump | 1,119 | 29 | 1,148 |
| 1 | examine | 1,039 | 27 | 1,066 |
| 1 | man | 1,411 | 130 | 1,541 |
| 1 | cat | 2,530 | 1,794 | 4,324 |
| 1 | wc | 3,163 | 1,836 | 4,999 |
| 1 | head | 2,704 | 1,798 | 4,502 |
| 1 | tail | 3,136 | 12,048 | 15,184 |
| 1 | more | 2,793 | 1,804 | 4,597 |
| 1 | sort | 3,326 | 18,212 | 21,538 |
| 1 | uniq | 2,748 | 2,312 | 5,060 |
| 1 | sed | 4,285 | 2,636 | 6,921 |
| 1 | awk | 5,552 | 2,768 | 8,320 |
| 1 | cmp | 1,142 | 171 | 1,313 |
| 1 | diff | 1,613 | 24,185 | 25,798 |
| 1 | md | 5,725 | 4,350 | 10,075 |
| 2 | touch | 603 | 127 | 730 |
| 2 | del | 1,940 | 1,806 | 3,746 |
| 2 | mv | 4,172 | 3,004 | 7,176 |
| 2 | tree | 2,138 | 398 | 2,536 |
| 2 | find | 2,823 | 628 | 3,451 |
| 2 | dir | 5,255 | 2,113 | 7,368 |
| 2 | grep | 5,749 | 2,823 | 8,572 |
| 2 | cp | 5,399 | 3,515 | 8,914 |

The largest are `diff` (two 12,000-byte line buffers), `sort` (16,000) and `tail` (10,240): data, not code; the
biggest code is grep, awk, md, cp and dir at 5.2-5.8K. Every one leaves at least 6.9K of the 32K free.

Decisions made on the way:
- **The shell runs `/BIN/NAME` before its built-ins** (`os/y1os.c` main, `try_prog`): otherwise the ported `dir`,
  `cat`, `pwd`, `del` and `help` could never be reached (the built-ins matched first). The built-ins stay for a card
  without `/BIN`; `type` is always the built-in cat. The v0.1 sessions (`basic`, `api`, `write`) now exercise the
  /BIN versions; their expected transcripts were regenerated and read line by line.
- **Man pages**: `os/man/NAME` (plain text, 72 columns) -> `/MAN/NAME` in upper case; `man` upper-cases the word and
  pages through lib_more; `man` alone lists the pages. The pages cover the /BIN commands, the shell built-ins
  (cd load run save ren mkdir rmdir exit type, and mon = the ROM monitor) and the libraries (abi fs apath err glob
  globx regex stdin rdline walk num, and pager = lib_more.c).
- **`/DOCS`** for `md`: `os/README.md` (OS.MD), the compiler README (Y1CC.MD), OS-PLAN.md (OSPLAN.MD), this file
  (PORT.MD) and `os/docs/mddemo.md` (MDDEMO.MD, one example of everything md renders). md now joins consecutive
  lines into one paragraph: the Y1 documents are hard-wrapped at ~115 columns, which the line-per-paragraph P8X
  renderer broke into ragged fragments.
- **Sample data** `/FRUIT.TXT` and `/FRUIT2.TXT` (7 lines each, one line different) so the filters can be tried, and
  tested, without redirection.
- The instruction-level emulator ends console input at a lower-case `q` (an old quit key in `mygetchar()`), which
  cut `uniq` to `uni`: the sessions type `UNIQ` and `Q`; BACKLOG has the item. The microcode emulator is unaffected.

Tests: `tests/os/wave1.session` (every wave-1 command, the pager with a `Q`, examine/dep/dump on $6000) and
`tests/os/wave2.session` (a tree built with mkdir/touch/cp, then tree, dir -R/-S/glob, find, grep -r, cp -r (and
its refusal to copy into itself), cp of a glob, mv rename/into/across, del with a glob, a moved program run from
its new directory), both on both emulators, wave2 with host-side p8xfs checks (fsck, ls of three directories, four
files fetched and compared).

Not done here: `vi` (a separate session), wave 3 (`asm`, a YACC1 `disasm`), redirection/pipes (the shell: until
then a filter reads files or the console), and everything section 2 marks DEFERRED or SKIPPED.
