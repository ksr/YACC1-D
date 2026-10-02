/*
 * Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
 */

/* disasm.c - the YACC1 disassembler, /BIN/DISASM (2026-09-29): machine code back to the source the assemblers take.
     disasm [-s] FILE [START [COUNT]]    a program file as if loaded: from its load address (the directory entry's,
                                         where `load` and `run` put it; /BIN programs load at 5000), or from START,
                                         to its end or for COUNT bytes
     disasm [-s] -m ADDR [COUNT]         memory: COUNT bytes (default 40) from ADDR, e.g. disasm -m F000 20 (the ROM
                                         monitor's first instructions)
   START, ADDR and COUNT are hex. The instructions shown are those that START in the range; the last one is completed
   past its end while there are bytes (to the file's end, or $FFFF). One line an instruction:
       AAAA  bb bb bb  MNEMONIC OPERANDS              e.g.  C000  19 CF FF  MVIW R1,0CFFFH
   the address, the instruction's bytes, then the instruction in RC/asm's dialect - what the host assembler, /BIN/ASM
   and /BIN/ASMC assemble back to the same bytes: numbers as hex with an H and a leading 0 before a letter (12H, 0FFH,
   0F000H: never a minus, which RC/asm drops), registers R0..R7, ports P0..PF, one space between the fields. A byte
   that begins no instruction is `DB nnH`: not an opcode (00, A5, AE, F8, F9, FA, FF), an operand byte whose fixed
   bits are wrong (JSRUR's register byte over 7), or an instruction cut off by the end of the bytes. So the output
   always reassembles; data between the code comes out as instructions or DBs, and still reassembles byte for byte.
   -s  source only: an ORG line, then each instruction indented, without the address and bytes (disasm -s F > F.ASM,
       then asm F.ASM gives the same bytes back)
   The table is os/dis_optab.c, generated from software/assembler/yacc1.def by tools/gen_y1_distab.py - the file the
   assemblers' tables come from - so disasm cannot disagree with them; the generator also checks every opcode against
   software/opcodes.h. It decodes by fixed bits and operand fields, not by a list of opcodes: an instruction added to
   yacc1.def is disassembled after `make -C os`.
   Output is putchar (stdout: > and | work), errors eputs (the screen). The file is read with GETC, never loaded, so
   disasm (at $5000, like every command) can show any program, itself included; memory is read with peek.
   Host build: tests/disasm/host_disasm.c compiles this file on the Mac (int = unsigned short) against an emulation of
   the few syscalls it uses; tests/disasm/run.py reassembles its output for every source of tests/asm's corpus, every
   /BIN program and the ROM. y1cc subset: int unsigned, no recursion. */
#include "../lib_fs.c"
#include "../lib_err.c"
#include "../dis_optab.c"

int mem, src;             /* -m: memory, -s: source only */
int fh;                   /* the file (not -m) */
int faddr, last, done;    /* the next address to fetch, the last one there is, all fetched */
int addr;                 /* the address of win[0] */
char win[DT_MAXLEN];      /* the bytes from addr on */
int wn;
char *rec;                /* the instruction found by decode(), its operands */
int av[4];
char w[64];
char ent[32];
int hbad;
char *HX = "0123456789ABCDEF";

void pc2(int v) { putchar(HX[(v >> 4) & 15]); putchar(HX[v & 15]); }
void pstr(char *s) { while (*s) putchar(*s++); }
void hb(int v) { if ((v & 255) > 159) putchar('0'); pc2(v); putchar('H'); }                 /* 12H, 0FFH */
void hw(int v) { if (v > 40959) putchar('0'); pc2(v >> 8); pc2(v); putchar('H'); }         /* 5000H, 0F000H */

int hexw(char *s) {       /* 1..4 hex digits; hbad when not */
    int v, n, c;
    v = 0; n = 0; hbad = 0;
    while ((c = *s++)) {
        if (c >= '0' && c <= '9') c = c - '0';
        else if (c >= 'A' && c <= 'F') c = c - 'A' + 10;
        else if (c >= 'a' && c <= 'f') c = c - 'a' + 10;
        else { hbad = 1; return 0; }
        v = v * 16 + c; n++;
    }
    if (n == 0 || n > 4) hbad = 1;
    return v;
}

void fill() {             /* the window up to DT_MAXLEN bytes, while there are bytes */
    int c;
    while (wn < DT_MAXLEN && !done) {
        if (mem) c = peek(faddr);
        else { c = fgetc(fh); if (c == 65535) { done = 1; return; } }
        win[wn++] = c;
        if (faddr == last) done = 1;
        faddr++;
    }
}

char *cname(int k, int v) {     /* class k's name for value v (length, characters), 0 if none */
    char *p;
    p = dt_c[k];
    if (v >= *p) return 0;
    p++;
    while (v) { p = p + *p + 1; v--; }
    if (!*p) return 0;
    return p;
}

int decode() {            /* the instruction at win[]: its length, rec and av[] set; 0 = none (a DB) */
    int k, n, j, nf, b, a;
    char *p;
    k = dt_opc(win[0]);
    if (!k) return 0;
    rec = dt_rec(k - 1);
    p = rec + *rec + 1;
    n = *p++;
    if (n > wn) return 0;                     /* cut off by the end of the bytes */
    while (*p) p++;                           /* the operand shape */
    p++;
    av[0] = 0; av[1] = 0; av[2] = 0; av[3] = 0;
    for (j = 0; j < n; j++) {
        b = win[j];
        if ((b & p[0]) != p[1]) return 0;     /* a fixed bit is wrong */
        nf = p[2]; p = p + 3;
        while (nf) {
            a = p[0] >> 4;
            av[a] = av[a] | (((b >> p[1]) & p[2]) << (p[0] & 15));
            p = p + 3; nf--;
        }
    }
    p = rec + *rec + 2; a = 0;                /* every register/port operand must have a name */
    while ((b = *p++)) {
        if (b == 4 || b == 5) a++;
        else if (b >= 8 && b < 33) { if (!cname(b - 8, av[a])) return 0; a++; }
    }
    return n;
}

void operands() {         /* the instruction decode() found, as source */
    char *p, *q;
    int n, c, a;
    p = rec; n = *p++;
    while (n) { putchar(*p++); n--; }
    p++; a = 0;
    while ((c = *p++)) {
        if (c == 1) putchar(' ');
        else if (c == 4) hb(av[a++]);
        else if (c == 5) hw(av[a++]);
        else if (c >= 8 && c < 33) { q = cname(c - 8, av[a++]); n = *q++; while (n) { putchar(*q++); n--; } }
        else putchar(c);
    }
}

void usage() {
    puts("usage: disasm [-s] FILE [START [COUNT]]   disasm [-s] -m ADDR [COUNT]   (hex; -s: source only)");
}

void main() {
    char *a;
    int start, stop, n, i, have;
    a = argstr();
    while (1) {
        a = argword(a, w, 63);
        if (w[0] == '-' && (w[1] == 'm' || w[1] == 'M') && !w[2]) mem = 1;
        else if (w[0] == '-' && (w[1] == 's' || w[1] == 'S') && !w[2]) src = 1;
        else break;
    }
    if (!w[0] || w[0] == '-') { usage(); return; }
    last = 65535;
    if (mem) {
        start = hexw(w);
        if (hbad) { eput2("disasm: bad address: ", w); return; }
        n = 64;
    } else {
        fh = fopen(w);
        if (!fh) { eput2("disasm: not found: ", w); return; }
        fentry(ent);
        start = ent_load(ent);
        n = ent_len(ent);
        if (!n && !ent_lenx(ent)) { fclose(fh); return; }        /* an empty file: nothing to show */
        if (!ent_lenx(ent) && n - 1 <= 65535 - start) last = start + n - 1;
    }
    a = argword(a, w, 63);
    have = mem;
    if (!mem && w[0]) {                       /* FILE's START */
        i = hexw(w);
        if (hbad) { eput2("disasm: bad address: ", w); fclose(fh); return; }
        if (i < start || i > last) { eput2("disasm: START is not in the file: ", w); fclose(fh); return; }
        if (i != start && !fseek(fh, 0, i - start)) { eputs("disasm: cannot seek"); fclose(fh); return; }
        start = i;
        a = argword(a, w, 63);
    }
    if (w[0]) {                               /* COUNT */
        n = hexw(w);
        if (hbad) { eput2("disasm: bad count: ", w); if (!mem) fclose(fh); return; }
        have = 1;
    }
    if (have) {                               /* instructions start at start..stop */
        if (!n) { if (!mem) fclose(fh); return; }
        stop = start + n - 1;
        if (stop < start) stop = 65535;
    } else stop = last;
    faddr = start; addr = start; wn = 0; done = 0;
    fill();
    if (src && wn) { pstr("        ORG "); hw(start); putchar(10); }
    while (wn) {
        n = decode();
        if (src) pstr("        ");
        else {
            pc2(addr >> 8); pc2(addr); pstr("  ");
            for (i = 0; i < DT_MAXLEN; i++) {
                if (i < n || (i == 0 && !n)) { pc2(win[i]); putchar(' '); }
                else pstr("   ");
            }
            putchar(' ');
        }
        if (n) operands();
        else { pstr("DB "); hb(win[0]); n = 1; }
        putchar(10);
        for (i = n; i < wn; i++) win[i - n] = win[i];
        wn = wn - n;
        fill();
        i = addr + n;
        if (i < addr || i > stop) break;      /* past the range (or past $FFFF) */
        addr = i;
    }
    if (!mem) fclose(fh);
}
