/* kermit.c - Kermit file transfer over the console line: /BIN/KERMIT (Y1/OS, 2026-09-26)
     kermit -r [-a ADDR] [-n] [-k] [-l N]    receive files into the current directory, named by the sender
     kermit -s FILE... [-B|-T] [-b N]        send files (globs work: kermit -s *.C)
     kermit -x [-a ADDR] [-n] [-k] [-l N]    server: the other Kermit SENDs, GETs, then FINISH or BYE
     kermit -h                               usage
   The other end is C-Kermit (or tools/y1kermit.py) on the machine at the far end of the console cable: the same
   UART, 38400 8N1, no flow control, as the shell's own console. Standard Kermit: short packets (up to 94), window 1
   (stop-and-wait), block checks 1, 2 and 3 (16-bit CRC), control-character prefixing, repeat counts, 8th-bit
   prefixing when the other side asks for it (the line itself is 8 bits), attribute packets (the file size and
   text/binary). Received names: the leaf only, upper case, at most 12 characters (NAME.EXT kept when it has to be
   shortened), characters other than A-Z 0-9 . _ - become _. A file is received into KERMIT.TMP and renamed when it
   is complete, so an existing file of that name is replaced only by a whole new one (-n: never replaced, the new
   file gets a new name), and a failed transfer leaves nothing (-k: keeps what arrived). Nothing is printed while
   packets flow (the console IS the line); a summary comes at the end. Three Ctrl-Cs while kermit waits for a
   packet cancel it. man kermit, os/README.md "kermit", docs/procedures/KERMIT.md (the Mac side).

   Ported 2026-09-26 from E-Kermit 1.8 (25 May 2021) by Frank da Cruz, the Kermit Project's embedded Kermit:
   its protocol module kermit.c, the control loop of main.c and the I/O module unixio.c; the originals are in
   os/upstream/ekermit-1.8 (unmodified; its README.md: where from, the checksums). The protocol logic, its state
   machine and the names of its routines are E-Kermit's; the changes, for the y1cc subset and for Y1/OS:
   - no function pointers: the k_data I/O callbacks (rxd txd openf finfo readf writef closef) are direct calls;
     no struct pointer either: the one k_data is the global struct k, k_response the r_ globals
   - no long: file sizes and counts are 24-bit pairs (hi, lo); int is unsigned, so E-Kermit's negative codes are
     constants (EOF 65535, s_first 2 for its -1, X_ERROR 9) and prev = (r_seq + 63) & 63
   - no #ifdef: the features are fixed as above (E-Kermit's F_AT, F_CRC, and neither F_LP long packets nor F_SSW
     simulated windows); one packet slot instead of the window slot table; the CRC tables are initialised data
   - packets are read by their LEN field by kermit_io.asm (krx), not up to a terminator, and every field is handled
     with an explicit length (a raw NUL cannot cut one short); the checks take (buffer, count)
   - the per-byte loops are kermit_io.asm too (3-4 times fewer instructions than y1cc's code for them): the block
     checks (kcrc with a 512-byte table built from E-Kermit's, ksum), decode() of file data (kdec, into a buffer big
     enough for a whole packet's repeats, written a sector's worth at a time), and getpkt()'s bytes that need no
     repeat count or 8th-bit prefix (kenc); E-Kermit's C still does names, runs and 8th-bit prefixes; the data field
     is built in the outgoing packet itself (no copy)
   - timeouts and retry limits (E-Kermit has neither: "only one Kermit needs to time out"): kermit_io.asm polls
     the UART with a count calibrated for 1 MHz; the time the other Kermit asks for, else 5 s; 10 retries a packet,
     60 while waiting for the transfer to start (the user is switching to the Mac)
   - encode()'s recursion for a run of two is a second call of encode1(); a refused A packet (ACK "N") skips the
     file with Z "D" (E-Kermit ignored it); a NAK counts as a retry for the sender too
   - server mode (-x) is new: I, S, R (GET) and G F / G L (FINISH, BYE) in the idle state
   - files: the Y1/OS file API (lib_fs.c); text mode strips CR on receive and sends LF as CR LF; binary is the
     default both ways; received names cleaned, KERMIT.TMP + rename, -n, -a ADDR for the load/exec address

   E-Kermit's notice, which its licence asks every copy of its source to keep:

   Copyright (C) 1995, 2021,
   Trustees of Columbia University in the City of New York.
   All rights reserved.

   Redistribution and use in source and binary forms, with or without
   modification, are permitted provided that the following conditions are met:

   * Redistributions of source code must retain the above copyright notice,
     this list of conditions and the following disclaimer.

   * Redistributions in binary form must reproduce the above copyright notice,
     this list of conditions and the following disclaimer in the documentation
     and/or other materials provided with the distribution.

   * Neither the name of Columbia University nor the names of its contributors
     may be used to endorse or promote products derived from this software
     without specific prior written permission.

   THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
   AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
   IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
   ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
   LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
   CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
   SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
   INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
   CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
   ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
   POSSIBILITY OF SUCH DAMAGE. */
#include "../lib_globx.c"
#include "../lib_err.c"
#include "y1lib.c"
#include "../kermit_io.c"

#define SOH       1
#define CR        13
#define SP        32
#define P_PKTLEN  94          /* the longest short packet (no long packets) */
#define P_S_TIMO  15          /* the timeout I ask the other Kermit to use (E-Kermit: 40) */
#define P_R_TIMO  5           /* my timeout until the other Kermit says otherwise */
#define P_RETRY   10          /* retries a packet */
#define P_WAIT    60          /* retries before the transfer has started */
#define FN_MAX    64
#define IBUFLEN   128         /* file input buffer (READN gives at most a sector's rest) */
#define OBUFLEN   512         /* file output: written when this much is waiting (a sector a WRITE, or more) */
#define OBUFMAX   3400        /* + what one packet can add: 94 data bytes decode to at most 2,822 */
#define EOF       65535
#define CAP_AT    8
#define TEXT      0
#define BINARY    1
#define NOTYPE    2           /* gattr(): no "A" or "B" in the attributes */
#define GLMAX     32          /* files in a send list */
#define LOGMAX    16          /* files remembered for the summary */
#define R_WAIT    1           /* receive states */
#define R_FILE    2
#define R_ATTR    3
#define R_DATA    4
#define S_INIT    11          /* send states */
#define S_FILE    12
#define S_ATTR    13
#define S_DATA    14
#define S_EOF     15
#define S_EOT     16
#define SV_IDLE   20          /* the server, waiting for a command */
#define W_SEND    1
#define W_RECV    2
#define K_INIT    0
#define K_RUN     1
#define K_SEND    6
#define X_OK      0
#define X_DONE    3
#define X_ERROR   9

struct k_data {               /* E-Kermit's struct k_data, less what these features do not use (one field a line:
                                 y1cc takes one declarator per struct member) */
    int binary;               /* this file: 1 binary, 0 text */
    int xfermode;             /* 1 = -B or -T given: the attributes do not change it */
    int state;                /* R_... / S_... / SV_IDLE */
    int what;                 /* W_SEND or W_RECV */
    int s_first;              /* getpkt(): 1 at a file's start, 0 inside, 2 at its end (E-Kermit: -1) */
    int cancel;               /* 1 cancel the file, 2 the group (E-Kermit's; nothing here sets it) */
    int ikeep;                /* -k: keep a file that did not arrive whole */
    int s_seq;                /* the sequence number sent last */
    int r_seq;                /* the one expected next */
    int s_soh;                /* the packet start I send */
    int s_eom;                /* the terminator the other side wants */
    int size;                 /* the data field being built */
    int osize;                /* its size before the last character */
    int r_timo;               /* my timeout (seconds): what the other side asked for */
    int s_timo;               /* the timeout I ask the other side to use */
    int r_maxlen;             /* the longest packet I take */
    int s_maxlen;             /* the longest the other side takes */
    int parity;               /* nonzero: 8th-bit prefixing in decode() (E-Kermit's use of it) */
    int retry;                /* tries a packet */
    int tries;                /* tries so far (new: E-Kermit counted NAKs only) */
    int s_ctlq;               /* the control prefix I send */
    int r_ctlq;               /* the one I receive */
    int ebq;                  /* the 8th-bit prefix */
    int ebqflg;               /* 8th-bit prefixing in encode() */
    int rptq;                 /* the repeat prefix */
    int s_rpt;                /* the run counted so far */
    int rptflg;               /* repeat counts negotiated */
    int bct;                  /* block check type 1..3 */
    int bctf;                 /* 1: type 3 on every packet (-b 5) */
    int capas;                /* capabilities: CAP_AT only */
    int opktlen;              /* the length of the packet in opkt */
    int obufpos;              /* bytes waiting in obuf */
    int zincnt;               /* bytes left in zinbuf */
    char *zinptr;             /* the next of them */
    char *istring;            /* getpkt() from a string (a name) instead of the file */
    char *filename;           /* the path of the file being sent */
};
struct k_data k;

char ipkt[104];               /* the packet read: LEN SEQ TYPE DATA CHECK (krx), a NUL after the data */
char opkt[104];               /* the packet sent last, kept for a resend */
char *xdata;                  /* the data field being built: opkt + 4, where spkt() wants it (no copy) */
char ack_s[32];               /* my Send-Init parameters */
char s_remain[8];             /* the encoding of the character that did not fit the last packet */
char obuf[OBUFMAX];
char zinbuf[2 * IBUFLEN + 2];
char tbuf[IBUFLEN];
char r_filename[FN_MAX];      /* E-Kermit's k_response: the name as sent, then as stored */
int r_szhi, r_szlo;           /* the size the attributes announced */
int r_sfhi, r_sflo;           /* bytes so far */
char gl[GLMAX * GSLOT];       /* the send list */
int gln, glk;
char wname[16];               /* the name a received file will have */
char tmpname[] = "KERMIT.TMP";
char errmsg[80];              /* what went wrong, for the summary */
char logn[LOGMAX * 13];
int logh[LOGMAX], logl[LOGMAX];
int nlog, nfiles, ih, oh, loadaddr, noclobber, server, finish, stopped, ccount;
char ent[32], nbuf[12];
char crcspace[768];           /* kcrc's table: 512 bytes on a page boundary somewhere in here */
char *ctab;

/* CRC-CCITT tables, as E-Kermit's K_INIT fills them (initialised data here) */
int crcta[] = {0, 4225, 8450, 12675, 16900, 21125, 25350, 29575, 33800, 38025, 42250, 46475, 50700, 54925, 59150, 63375};
int crctb[] = {0, 4489, 8978, 12955, 17956, 22445, 25910, 29887, 35912, 40385, 44890, 48851, 51820, 56293, 59774, 63735};

int tochar(int c) { return (c + SP) & 255; }
int xunchar(int c) { return (c - SP) & 255; }

/* ---- the line (E-Kermit's rxd / txd, unixio.c readpkt / tx_data) ------------------------------------------------ */
void kio_fix() {                              /* relocate kermit_io's absolute addresses to where kio[] is */
    int i, o, w, base;
    base = kio;
    for (i = 0; kio_rel[i]; i++) {
        o = kio_rel[i];
        w = (kio[o] << 8) + kio[o + 1] + base;
        kio[o] = w >> 8; kio[o + 1] = w & 255;
    }
}

int readpkt(int timo) {                       /* 0 timeout, 65533 Ctrl-C, 65534 bad, else LEN + the bytes after it */
    int n;
    pokew(kio + KIO_KBUF, ipkt); pokew(kio + KIO_KCNT, P_PKTLEN); pokew(kio + KIO_KTIMO, timo);
    n = call(kio + KIO_KRX);
    if (n && n < 65533) ipkt[n] = 0;
    return n;
}

int tx_data(char *p, int n) {
    pokew(kio + KIO_KBUF, p); pokew(kio + KIO_KCNT, n);
    call(kio + KIO_KTX);
    return X_OK;
}

void fifo(int on) {                           /* the 16C550's FIFOs: on (and cleared) for a transfer, off after */
    outp(0, 0x68);
    while (!(inp(1) & 0x40)) ;                /* the transmitter empty first: this would drop what it holds */
    outp(0, 0x50);                            /* FCR */
    if (on) outp(1, 7); else outp(1, 0);
}

/* ---- numbers: 24 bits as (hi, lo) ---------------------------------------------------------------------------- */
int nhi, nlo;

void n_mad(int d) {                           /* (nhi:nlo) = (nhi:nlo) * 10 + d */
    int b0, b1;
    b0 = (nlo & 255) * 10 + d;
    b1 = (nlo >> 8) * 10 + (b0 >> 8);
    nhi = nhi * 10 + (b1 >> 8);
    nlo = ((b1 & 255) << 8) | (b0 & 255);
}

void stringnum(char *s, int n) {              /* decimal digits -> (nhi:nlo) */
    nhi = 0; nlo = 0;
    while (n && *s == ' ') { s++; n--; }
    while (n && *s >= '0' && *s <= '9') { n_mad(*s - '0'); s++; n--; }
}

int numstring(int hi, int lo, char *buf) {    /* (hi:lo) -> decimal in buf, NUL-ended; returns its length */
    char d[10]; int n, r, t, q1, q0, i;
    n = 0;
    while (1) {
        r = hi % 10; hi = hi / 10;
        t = r * 256 + (lo >> 8); q1 = t / 10; r = t % 10;
        t = r * 256 + (lo & 255); q0 = t / 10; r = t % 10;
        lo = (q1 << 8) + q0;
        d[n++] = '0' + r;
        if (!hi && !lo) break;
    }
    for (i = 0; i < n; i++) buf[i] = d[n - 1 - i];
    buf[n] = 0;
    return n;
}

void sofar_add(int n) { r_sflo = r_sflo + n; if (r_sflo < n) r_sfhi++; }

/* ---- the block checks (E-Kermit chk1 chk2 chk3, over a count instead of up to a NUL) --------------------------- */
/* The loops are kermit_io's ksum and kcrc: in C they cost ~30 and ~210 instructions a byte, a third of the work */
int chk2(char *p, int n) { pokew(kio + KIO_KBUF, p); pokew(kio + KIO_KCNT, n); return call(kio + KIO_KSUM); }
int chk1(char *p, int n) { int c; c = chk2(p, n); return (((c & 0xC0) >> 6) + c) & 63; }
int chk3(char *p, int n) { pokew(kio + KIO_KBUF, p); pokew(kio + KIO_KCNT, n); return call(kio + KIO_KCRC); }

void crcinit() {                              /* T[i] = crcta[i >> 4] ^ crctb[i & 15], as bytes on two pages */
    int h, l, t; char alo[16], ahi[16], blo[16], bhi[16];
    t = crcspace; t = (t + 255) & 0xFF00; ctab = t;
    pokew(kio + KIO_KTAB, ctab);
    for (h = 0; h < 16; h++) { alo[h] = crcta[h]; ahi[h] = crcta[h] >> 8; blo[h] = crctb[h]; bhi[h] = crctb[h] >> 8; }
    for (h = 0; h < 16; h++)
        for (l = 0; l < 16; l++) { t = h * 16 + l; ctab[t] = alo[h] ^ blo[l]; ctab[t + 256] = ahi[h] ^ bhi[l]; }
}

/* ---- packets out ---------------------------------------------------------------------------------------------- */
int spkt(int typ, int seq, int len, char *data) {   /* E-Kermit spkt(): build, remember and send a packet */
    int i, j; char *buf;
    buf = opkt;
    i = 0;
    buf[i++] = k.s_soh;
    buf[i++] = tochar(len + k.bct + 2);
    buf[i++] = tochar(seq);
    buf[i++] = typ;
    if (data == buf + 4) i = i + len;          /* built in place (xdata) */
    else while (len) { buf[i++] = *data; data++; len--; }
    if (k.bct == 1) { j = chk1(buf + 1, i - 1); buf[i++] = tochar(j); }
    else if (k.bct == 2) {
        j = chk2(buf + 1, i - 1);
        buf[i++] = tochar((j >> 6) & 63); buf[i++] = tochar(j & 63);
    } else {
        j = chk3(buf + 1, i - 1);
        buf[i++] = tochar(j >> 12); buf[i++] = tochar((j >> 6) & 63); buf[i++] = tochar(j & 63);
    }
    buf[i++] = k.s_eom;
    k.s_seq = seq;
    k.opktlen = i;
    return tx_data(buf, i);
}

int limit() { return (k.state == R_WAIT || k.state == S_INIT) ? P_WAIT : k.retry; }

void setmsg(char *s) { strcpy(errmsg, s); }

void epkt(char *msg) {                         /* a (fatal) Error packet */
    if (!k.bctf) k.bct = 1;
    spkt('E', 0, strlen(msg), msg);
    if (!errmsg[0]) setmsg(msg);
}

int resend() {                                 /* the last packet again (a NAK, a timeout, a duplicate) */
    if (!k.opktlen) return X_OK;
    if (++k.tries > limit()) { epkt("Too many retries"); return X_ERROR; }
    return tx_data(opkt, k.opktlen);
}

int nak(int seq) {
    spkt('N', seq, 0, 0);
    if (++k.tries > limit()) { epkt("Too many retries"); return X_ERROR; }
    return X_OK;
}

int ack(int seq, char *text) {
    int len;
    len = 0;
    if (text) len = strlen(text);
    spkt('Y', seq, len, text);
    k.r_seq = (k.r_seq + 1) & 63;
    return X_OK;
}

int nxtpkt() { k.s_seq = (k.s_seq + 1) & 63; return 0; }

/* ---- parameters (E-Kermit spar / rpar) ------------------------------------------------------------------------ */
void spar(char *s, int datalen) {              /* set what the other Kermit asked for */
    int x;
    s--;                                       /* line up with the field numbers */
    if (datalen >= 1) {
        k.s_maxlen = xunchar(s[1]);
        if (k.s_maxlen == 0) k.s_maxlen = 80;  /* the protocol's default */
        if (k.s_maxlen > P_PKTLEN) k.s_maxlen = P_PKTLEN;
        if (k.s_maxlen < 20) k.s_maxlen = 20;
    }
    if (datalen >= 2) { x = xunchar(s[2]); if (x) k.r_timo = x; }
    if (datalen >= 5) k.s_eom = xunchar(s[5]);
    if (datalen >= 6) k.r_ctlq = s[6];
    if (datalen >= 7) {                        /* 8th-bit prefix */
        k.ebq = s[7];
        if ((s[7] > 32 && s[7] < 63) || (s[7] > 95 && s[7] < 127)) {
            if (!k.parity) k.parity = 1;
            k.ebqflg = 1;
        } else if (s[7] == 'Y' && k.parity) { k.ebqflg = 1; k.ebq = '&'; }
    }
    if (datalen >= 8) {                        /* block check */
        k.bct = s[8] - '0';
        if (k.bct < 1 || k.bct > 3) k.bct = 1;
        if (k.bctf) k.bct = 3;
    }
    if (datalen >= 9) {                        /* repeat counts */
        if ((s[9] > 32 && s[9] < 63) || (s[9] > 95 && s[9] < 127)) { k.rptq = s[9]; k.rptflg = 1; }
    }
    if (datalen >= 10) {                       /* capabilities: only attributes are kept */
        x = xunchar(s[10]);
        if (!(x & CAP_AT)) k.capas = k.capas & ~CAP_AT;
    } else k.capas = 0;
}

int rpar(int type) {                           /* send my parameters: an S packet, or the ACK to one */
    char *d; int b;
    d = ack_s;
    d[0] = tochar(k.r_maxlen);                 /* the longest packet I take */
    d[1] = tochar(k.s_timo);                   /* when I want to be timed out */
    d[2] = tochar(0);                          /* no padding */
    d[3] = 64;                                 /* ctl(0) */
    d[4] = tochar(CR);                         /* the terminator I want */
    d[5] = k.s_ctlq;
    if (k.ebq == 'Y' && k.parity) { k.ebq = '&'; d[6] = '&'; } else d[6] = k.ebq;
    if (k.bctf) d[7] = '5'; else d[7] = k.bct + '0';
    d[8] = k.rptq;
    d[9] = tochar(k.capas);
    d[10] = tochar(1);                         /* window 1 */
    d[11] = 0;
    b = k.bct;
    if (!k.bctf) k.bct = 1;                    /* S and its ACK always carry a type-1 check */
    if (type == 'Y') ack(0, d); else spkt('S', 0, 11, d);
    if (!k.bctf) k.bct = b;
    return X_OK;
}

/* ---- data (E-Kermit decode / encode / getpkt) ----------------------------------------------------------------- */
int writefile(char *s, int n) {
    if (fwrite(oh, s, n) != n) return X_ERROR;
    sofar_add(n);
    return X_OK;
}

int decode(char *inbuf, int n, int f) {        /* f 0: the file name to r_filename; 1: file data to the file */
    int a, a7, b8, rpt, fl; char *end;
    if (f) {                                   /* file data: kermit_io's kdec, then write when a sector's worth */
        if (!n) return X_OK;
        poke(kio + KIO_KRQ, k.rptflg ? k.rptq : 0);
        poke(kio + KIO_KEQ, k.parity ? k.ebq : 0);
        poke(kio + KIO_KCQ, k.r_ctlq);
        poke(kio + KIO_KTXT, !k.binary);
        pokew(kio + KIO_KBUF, inbuf); pokew(kio + KIO_KCNT, n); pokew(kio + KIO_KOUT, obuf + k.obufpos);
        call(kio + KIO_KDEC);
        k.obufpos = peekw(kio + KIO_KOUT) - obuf;
        if (k.obufpos >= OBUFLEN) {
            a = writefile(obuf, k.obufpos);
            k.obufpos = 0;
            return a;
        }
        return X_OK;
    }
    fl = 0; end = inbuf + n;                   /* a name (or an E packet's text): E-Kermit's loop, into r_filename */
    while (inbuf < end) {
        a = *inbuf++;
        rpt = 1;
        if (k.rptflg && a == k.rptq) {
            rpt = xunchar(*inbuf++);
            if (rpt > 94 || !rpt) rpt = 1;
            a = *inbuf++;
        }
        b8 = 0;
        if (k.parity && a == k.ebq) { b8 = 128; a = *inbuf++ & 127; }
        if (a == k.r_ctlq) {
            a = *inbuf++;
            a7 = a & 127;
            if (a7 >= 63 && a7 <= 95) a = a ^ 64;
        }
        a = a | b8;
        while (rpt) { if (fl < FN_MAX - 1) r_filename[fl++] = a; rpt--; }
    }
    r_filename[fl] = 0;
    return X_OK;
}

int readfile() {                               /* refill zinbuf; the first byte, or EOF */
    int n, i, j, c;
    if (k.binary) j = n = freadn(ih, zinbuf, IBUFLEN);
    else {
        j = freadn(ih, tbuf, IBUFLEN);
        n = 0;
        for (i = 0; i < j; i++) { c = tbuf[i]; if (c == 10) zinbuf[n++] = CR; zinbuf[n++] = c; }
    }
    if (!n) return EOF;
    sofar_add(j);                              /* the file's bytes (text mode sends more) */
    k.zinptr = zinbuf + 1;
    k.zincnt = n - 1;
    return zinbuf[0];
}

void encode1(int a) {                          /* one character into xdata, prefixed as needed */
    int a7, b8;
    a7 = a & 127; b8 = a & 128;
    if (k.ebqflg && b8) { xdata[k.size++] = k.ebq; a = a7; }
    if (a7 < 32 || a7 == 127) { xdata[k.size++] = k.s_ctlq; a = a ^ 64; }
    else if (a7 == k.s_ctlq) xdata[k.size++] = k.s_ctlq;
    else if (k.ebqflg && a7 == k.ebq) xdata[k.size++] = k.s_ctlq;
    else if (k.rptflg && a7 == k.rptq) xdata[k.size++] = k.s_ctlq;
    xdata[k.size++] = a;
    xdata[k.size] = 0;
}

void encode(int a, int next) {                 /* with run-length encoding: a run is counted until it breaks */
    if (k.rptflg) {
        if (a == next) {
            if (++k.s_rpt < 94) return;
            if (k.s_rpt == 94) {
                xdata[k.size++] = k.rptq; xdata[k.size++] = tochar(k.s_rpt);
                k.s_rpt = 0;
            }
        } else if (k.s_rpt == 1) {             /* a run of two: the character twice */
            k.s_rpt = 0;
            encode1(a);
            if (k.size <= k.s_maxlen - 4) k.osize = k.size;
            encode1(a);
            return;
        } else if (k.s_rpt > 1) {
            xdata[k.size++] = k.rptq; xdata[k.size++] = tochar(++k.s_rpt);
            k.s_rpt = 0;
        }
    }
    encode1(a);
}

int gp_c;                                      /* getpkt()'s character in hand (E-Kermit: a static local) */

int nextin() {                                 /* the next byte to send: E-Kermit's zgetc(), or the string's */
    int c;
    if (k.istring) { c = *k.istring; k.istring++; return c ? c : EOF; }
    if (!k.zincnt) return readfile();
    k.zincnt--;
    c = *k.zinptr; k.zinptr++;
    return c;
}

int getpkt() {                                 /* fill xdata from the file (or istring); returns its size */
    int i, next, maxlen, c;
    maxlen = k.s_maxlen - k.bct - 3;
    if (k.s_first == 1) {
        k.s_first = 0;
        s_remain[0] = 0;
        gp_c = nextin();
        if (gp_c == EOF) { k.s_first = 2; k.size = 0; return 0; }
    } else if (k.s_first == 2 && !s_remain[0]) { k.size = 0; return 0; }
    for (k.size = 0; (xdata[k.size] = s_remain[k.size]) != 0; k.size++) ;
    s_remain[0] = 0;
    if (k.s_first == 2) return k.size;
    if (!k.istring) {
        poke(kio + KIO_KRQ, k.rptflg ? k.rptq : 0);
        poke(kio + KIO_KEQ, k.ebqflg ? k.ebq : 0);
        poke(kio + KIO_KCQ, k.s_ctlq);
    }
    while (k.s_first != 2) {
        if (!k.istring && !k.s_rpt && k.zincnt) {     /* plain bytes: kermit_io's kenc, as encode() would */
            poke(kio + KIO_KC, gp_c);
            pokew(kio + KIO_KBUF, k.zinptr); pokew(kio + KIO_KCNT, k.zincnt);
            pokew(kio + KIO_KOUT, xdata + k.size); pokew(kio + KIO_KROOM, maxlen - k.size);
            call(kio + KIO_KENC);
            k.zinptr = peekw(kio + KIO_KBUF); k.zincnt = peekw(kio + KIO_KCNT);
            gp_c = peek(kio + KIO_KC);
            k.size = peekw(kio + KIO_KOUT) - xdata;
            if (k.size == maxlen) return k.size;
        }
        next = nextin();
        if (next == EOF) k.s_first = 2;
        c = gp_c;
        k.osize = k.size;
        encode(c, next);
        gp_c = next;
        if (k.size == maxlen) return k.size;
        if (k.size > maxlen) {                 /* past the end: keep the last character's encoding for next time */
            for (i = 0; (s_remain[i] = xdata[k.osize + i]) != 0; i++) ;
            k.size = k.osize;
            xdata[k.size] = 0;
            return k.size;
        }
    }
    return k.size;
}

int encstr(char *s) {                          /* the data field from a string (a file name) */
    k.s_first = 1; k.istring = s;
    getpkt();
    k.istring = 0; k.s_first = 1;
    return k.size;
}

int sdata() {                                  /* the next data packet; 0 at the end of the file */
    int len;
    if (k.cancel) return 0;
    len = getpkt();
    if (len < 1) return 0;
    spkt('D', k.s_seq, len, xdata);
    return len;
}

/* ---- attributes (E-Kermit gattr / sattr) ---------------------------------------------------------------------- */
int gattr(char *s, int n) {                    /* read the A packet: the size, text or binary */
    char *end; int c, aln, rc, got1;
    rc = NOTYPE; got1 = 0; end = s + n;
    while (s + 2 <= end) {
        c = s[0]; aln = xunchar(s[1]); s = s + 2;
        if (s + aln > end) break;
        if (c == '"' && aln) { if (s[0] == 'A') rc = TEXT; else if (s[0] == 'B') rc = BINARY; }
        else if (c == '1') { stringnum(s, aln); r_szhi = nhi; r_szlo = nlo; got1 = 1; }
        else if (c == '!' && !got1) {          /* the size in K */
            stringnum(s, aln);
            r_szhi = (nhi << 10) | (nlo >> 6); r_szlo = nlo << 10;
        }
        s = s + aln;
    }
    return rc;
}

int sattr() {                                  /* build and send the A packet */
    int i, x; char *p;
    i = 0;
    xdata[i++] = '"';
    if (k.binary) { xdata[i++] = tochar(2); xdata[i++] = 'B'; xdata[i++] = '8'; }
    else {
        xdata[i++] = tochar(3); xdata[i++] = 'A'; xdata[i++] = 'M'; xdata[i++] = 'J';
        xdata[i++] = '*'; xdata[i++] = tochar(1); xdata[i++] = 'A';
    }
    if (fresolve(k.filename, ent)) {
        r_szhi = ent_lenx(ent); r_szlo = ent_len(ent);
        x = numstring(r_szhi, r_szlo, nbuf);
        xdata[i++] = '1'; xdata[i++] = tochar(x);
        p = nbuf; while (*p) xdata[i++] = *p++;
    }
    xdata[i++] = '@'; xdata[i++] = ' ';
    xdata[i] = 0;
    return spkt('A', k.s_seq, i, xdata);
}

/* ---- files (E-Kermit's openf / closef / finfo, for Y1/OS) ---------------------------------------------------- */
char *leafof(char *p) { char *l; l = p; while (*p) { if (*p == '/') l = p + 1; p++; } return l; }

int exists(char *n) { return fresolve(n, ent); }

void fixname(char *in) {                       /* a received name -> wname: 1..12 characters Y1/OS takes */
    char *s, *p; int n, d, c, i, e;
    s = in;
    for (p = in; *p; p++) if (*p == '/' || *p == 92 || *p == ':') s = p + 1;
    n = 0; d = 65535;
    while (s[n] && n < 60) {
        c = s[n];
        if (c >= 'a' && c <= 'z') c = c - 32;
        if (!((c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '.' || c == '_' || c == '-')) c = '_';
        if (c == '.') d = n;
        tbuf[n++] = c;
    }
    tbuf[n] = 0;
    if (tbuf[0] == '.') tbuf[0] = '_';         /* a leading dot is refused (., .., RENAME) */
    if (!n) { strcpy(wname, "KERMIT.DAT"); return; }
    if (n <= 12) { strcpy(wname, tbuf); return; }
    e = 0;                                     /* NAME.EXT: the extension cut to 3, the name to what is left */
    if (d != 65535 && d > 0) { e = n - d; if (e > 4) e = 4; }
    i = 0;
    while (i < 12 - e && i < (e ? d : n)) { wname[i] = tbuf[i]; i++; }
    for (c = 0; c < e; c++) wname[i++] = tbuf[d + c];
    wname[i] = 0;
}

void newname() {                               /* -n: the name is taken, find NAME~1 .. NAME~99 */
    int j, n, m;
    strcpy(tbuf, wname);
    for (j = 1; j < 100; j++) {
        m = j < 10 ? 2 : 3;
        n = strlen(tbuf); if (n > 12 - m) n = 12 - m;
        strcpy(wname, tbuf); wname[n] = '~';
        if (j < 10) { wname[n + 1] = '0' + j; wname[n + 2] = 0; }
        else { wname[n + 1] = '0' + j / 10; wname[n + 2] = '0' + j % 10; wname[n + 3] = 0; }
        if (!exists(wname)) return;
    }
}

int openfile(char *s, int mode) {              /* 1: read s; 2: create the file for wname */
    if (mode == 1) {
        ih = fopen(s);
        if (!ih) return X_ERROR;
        k.s_first = 1; k.zincnt = 0;
        return X_OK;
    }
    oh = fcreate(strcmp(wname, tmpname) ? tmpname : wname, loadaddr, loadaddr);
    if (!oh) return X_ERROR;
    k.obufpos = 0; r_sfhi = 0; r_sflo = 0;
    return X_OK;
}

void logit(char *n) {
    if (nlog < LOGMAX) {
        strcpy(logn + nlog * 13, n);
        logh[nlog] = r_sfhi; logl[nlog] = r_sflo;
        nlog++;
    }
    nfiles++;
}

int closefile(int c, int mode) {               /* mode 1: the file sent; 2: the file received (c 'D' = discard) */
    int rc;
    rc = X_OK;
    if (mode == 1) {
        if (ih) { fclose(ih); ih = 0; if (c != 'D') logit(leafof(k.filename)); }
        return X_OK;
    }
    if (!oh) return X_OK;
    fclose(oh); oh = 0;
    if (c == 'D' && !k.ikeep) { if (strcmp(wname, tmpname)) fdelete(tmpname); return X_OK; }
    if (strcmp(wname, tmpname)) {
        fdelete(wname);                        /* the old file of that name, if any (a directory stays) */
        if (!frename(tmpname, wname)) { setmsg("cannot rename KERMIT.TMP"); return X_ERROR; }
    }
    logit(wname);
    return rc;
}

void abortfiles() {                            /* after an error: close what is open, drop a partial file */
    if (ih) { fclose(ih); ih = 0; }
    if (oh && k.ikeep && k.obufpos) { writefile(obuf, k.obufpos); k.obufpos = 0; }
    if (oh) closefile('D', 2);
}

int nextfile() {                               /* the next file of the send list -> k.filename, or 0 (quietly:
                                                  the line is busy; main() checked the list before) */
    while (glk < gln) {
        k.filename = gl + glk * GSLOT;
        glk++;
        if (fresolve(k.filename, ent) && ent_isfile(ent)) return 1;
    }
    return 0;
}

int addfiles(char *w) {                        /* a word (or a glob) of names -> the send list */
    int n;
    if (isglob(w)) {
        n = glob_expand(w, gl + gln * GSLOT, GLMAX - gln);
        gln = gln + n;
        return n;
    }
    if (gln >= GLMAX) return 0;
    n = 0;
    while (w[n] && w[n] != ' ' && n < GSLOT - 1) { gl[gln * GSLOT + n] = w[n]; n++; }
    gl[gln * GSLOT + n] = 0;
    gln++;
    return 1;
}

/* ---- the protocol (E-Kermit kermit()) ------------------------------------------------------------------------- */
void reset() {                                 /* E-Kermit's K_INIT, and the server's return to idle */
    k.state = R_WAIT; k.what = W_RECV; k.s_first = 1;
    k.s_soh = SOH; k.s_eom = CR;
    k.s_seq = 0; k.r_seq = 0;
    k.r_timo = P_R_TIMO; k.s_timo = P_S_TIMO;
    k.s_maxlen = 80;
    k.retry = P_RETRY; k.tries = 0;
    k.s_ctlq = '#'; k.r_ctlq = '#';
    k.ebq = 'Y'; k.ebqflg = 0; k.parity = 0;
    k.rptq = '~'; k.rptflg = 0; k.s_rpt = 0;
    k.capas = CAP_AT;
    k.opktlen = 0; k.zincnt = 0; k.filename = 0; k.istring = 0;
    if (!k.xfermode) k.binary = BINARY;
}

int chkok(int chklen, int plen) {              /* does the packet in ipkt check with a type-chklen block check? */
    int n, v; char *c;
    if (plen < 2 + chklen) return 0;
    n = plen + 1 - chklen;                     /* LEN SEQ TYPE DATA */
    c = ipkt + n;
    if (chklen == 1) return xunchar(c[0]) == chk1(ipkt, n);
    if (chklen == 2) { v = (xunchar(c[0]) << 6) | xunchar(c[1]); return v == (chk2(ipkt, n) & 0xFFF); }
    v = (xunchar(c[0]) << 12) | (xunchar(c[1]) << 6) | xunchar(c[2]);
    return v == chk3(ipkt, n);
}

int kermit(int f, int len) {
    int rc, plen, datalen, seq, prev, chklen, t, s0;
    char *p, *s;

    if (f == K_INIT) { reset(); return X_OK; }
    if (f == K_SEND) {
        rpar('S');
        k.state = S_INIT; k.what = W_SEND;
        return X_OK;
    }
    if (len < 4) {                              /* a timeout or a bad packet */
        if (k.what == W_RECV) return nak(k.r_seq);
        return resend();
    }
    s = 0;
    if (k.what == W_RECV) { if (k.cancel == 1) s = "X"; else if (k.cancel == 2) s = "Z"; }
    plen = xunchar(ipkt[0]);                    /* SEQ TYPE DATA CHECK */
    seq = xunchar(ipkt[1]);
    t = ipkt[2];
    p = ipkt + 3;
    if (k.what == W_RECV && (t == 'N' || t == 'Y')) return X_OK;     /* an echo: ignore */
    if (k.state == SV_IDLE) k.r_seq = seq;      /* a new command: whatever its number */

    chklen = k.bct;
    if (k.bctf) chklen = 3;
    else if (t == 'S' || t == 'I' || k.state == S_INIT) chklen = 1;
    if (!chkok(chklen, plen)) {
        if ((t == 'E' || k.state == SV_IDLE) && chklen != 1 && chkok(1, plen)) chklen = 1;   /* E: may be type 1 */
        else if (k.state == SV_IDLE && chklen == 1 && k.bct != 1 && chkok(k.bct, plen)) chklen = k.bct;
        else if (k.what == W_RECV) return nak(k.r_seq);
        else return resend();
    }
    datalen = plen - 2 - chklen;
    p[datalen] = 0;
    if (t == 'E') {                             /* the other side gives up: keep its message */
        decode(p, datalen, 0);
        strcpy(errmsg, "the other Kermit says: ");
        r_filename[40] = 0;
        strcpy(errmsg + 23, r_filename);
        return X_ERROR;
    }

    prev = (k.r_seq + 63) & 63;
    if (seq != k.r_seq) {
        if (seq == prev) return resend();       /* the previous packet again: my answer was lost */
        if (k.what == W_RECV) return nak(k.r_seq);
        return resend();
    }
    if (k.what == W_SEND) {                     /* sending: this must be the ACK */
        if (t != 'Y') return resend();
        k.tries = 0;
        if (k.state == S_DATA && (k.cancel || p[0] == 'X' || p[0] == 'Z')) {
            closefile('D', 1);
            nxtpkt();
            spkt('Z', k.s_seq, 1, "D");
            if (p[0] == 'Z' || k.cancel == 2) glk = gln;     /* cancel the group */
            k.state = S_EOF;
            k.r_seq = k.s_seq;
            return X_OK;
        }
    } else k.tries = 0;

    switch (k.state) {
      case S_INIT:                              /* the other Kermit's parameters */
      case S_EOF:                               /* the ACK to Z */
        nxtpkt();
        if (k.state == S_INIT) spar(p, datalen);
        if (nextfile()) {
            if (openfile(k.filename, 1) != X_OK) { epkt("Cannot open file"); return X_ERROR; }
            encstr(leafof(k.filename));
            spkt('F', k.s_seq, k.size, xdata);
            r_sfhi = 0; r_sflo = 0;
            k.state = S_FILE;
        } else {
            spkt('B', k.s_seq, 0, 0);
            k.state = S_EOT;
        }
        k.r_seq = k.s_seq;
        return X_OK;

      case S_FILE:                              /* the ACK to F */
        nxtpkt();
        if (k.capas & CAP_AT) { sattr(); k.state = S_ATTR; }
        else if (sdata() == 0) {
            spkt('Z', k.s_seq, 0, 0);
            closefile(p[0], 1);
            k.state = S_EOF;
        } else k.state = S_DATA;
        k.r_seq = k.s_seq;
        return X_OK;

      case S_ATTR:                              /* the ACK to A: "N" = the file is refused, skip it */
      case S_DATA:                              /* the ACK to D */
        nxtpkt();
        if (k.state == S_ATTR && p[0] == 'N') {
            closefile('D', 1);
            spkt('Z', k.s_seq, 1, "D");
            k.state = S_EOF;
            k.r_seq = k.s_seq;
            return X_OK;
        }
        k.state = S_DATA;
        if (sdata() == 0) {
            spkt('Z', k.s_seq, 0, 0);
            closefile(p[0], 1);
            k.state = S_EOF;
        }
        k.r_seq = k.s_seq;
        return X_OK;

      case S_EOT:                               /* the ACK to B */
        return X_DONE;

      case SV_IDLE:                             /* the server: a command */
        if (t == 'I') { spar(p, datalen); rpar('Y'); k.r_seq = 0; return X_OK; }
        if (t == 'S') { spar(p, datalen); rpar('Y'); k.state = R_FILE; return X_OK; }
        if (t == 'R') {                         /* GET name: send it (a glob too) */
            decode(p, datalen, 0);
            gln = 0; glk = 0;
            addfiles(r_filename);
            if (!nextfile()) {                  /* as given, else in upper case (Y1/OS names are) */
                for (s = r_filename; *s; s++) if (*s >= 'a' && *s <= 'z') *s = *s - 32;
                gln = 0; glk = 0;
                addfiles(r_filename);
            }
            if (!nextfile()) { epkt("File not found"); k.r_seq = 0; errmsg[0] = 0; return X_OK; }
            glk = 0;
            rpar('S'); k.state = S_INIT; k.what = W_SEND;
            return X_OK;
        }
        if (t == 'G' && (p[0] == 'F' || p[0] == 'L')) { ack(k.r_seq, 0); finish = 1; return X_DONE; }
        epkt("Unimplemented server command");
        k.r_seq = 0; errmsg[0] = 0;
        return X_OK;

      case R_WAIT:                              /* waiting for the S packet */
        if (t == 'S') {
            spar(p, datalen);
            rpar('Y');
            k.state = R_FILE;
            return X_OK;
        }
        epkt("Unexpected packet type");
        return X_ERROR;

      case R_FILE:                              /* an F (a file) or a B (the end) */
        if (t == 'F') {
            decode(p, datalen, 0);
            fixname(r_filename);
            if (noclobber && exists(wname)) newname();
            r_szhi = 0; r_szlo = 0; r_sfhi = 0; r_sflo = 0;
            k.state = R_ATTR;
            if (!k.xfermode) k.binary = BINARY;
            encstr(wname);                     /* the ACK carries the name it will have, encoded (FOO~1: ~ is */
            spkt('Y', k.r_seq, k.size, xdata); /* the repeat prefix) - E-Kermit sent it as it was */
            k.r_seq = (k.r_seq + 1) & 63;
            return X_OK;
        }
        if (t == 'B') { ack(k.r_seq, 0); return X_DONE; }
        epkt("Unexpected packet type");
        return X_ERROR;

      case R_ATTR:                              /* A, D or Z */
        if (t == 'A') {
            rc = gattr(p, datalen);
            if (rc != NOTYPE && !k.xfermode) k.binary = rc;
            return ack(k.r_seq, "Y");
        }
        if (t == 'D') {
            if (openfile(wname, 2) != X_OK) { epkt("Cannot create the file"); return X_ERROR; }
            k.state = R_DATA;
            if (decode(p, datalen, 1) != X_OK) { epkt("Error writing data"); return X_ERROR; }
            return ack(k.r_seq, s);
        }
        if (t == 'Z') {                         /* an empty file */
            if (openfile(wname, 2) != X_OK) { epkt("Cannot create the file"); return X_ERROR; }
            if (closefile(p[0], 2) != X_OK) { epkt("Error closing the file"); return X_ERROR; }
            k.state = R_FILE;
            return ack(k.r_seq, s);
        }
        epkt("Unexpected packet type");
        return X_ERROR;

      case R_DATA:                              /* D or Z */
        if (t == 'D') {
            if (decode(p, datalen, 1) != X_OK) { epkt("Error writing data"); return X_ERROR; }
        } else if (t == 'Z') {
            if (k.obufpos) {
                s0 = writefile(obuf, k.obufpos);
                k.obufpos = 0;
                if (s0 != X_OK) { epkt("Error writing data"); return X_ERROR; }
            }
            if (closefile(p[0], 2) != X_OK) { epkt("Can't close file"); return X_ERROR; }
            k.state = R_FILE;
        } else { epkt("Unexpected packet type"); return X_ERROR; }
        return ack(k.r_seq, s);
    }
    epkt("Protocol error");
    return X_ERROR;
}

/* ---- the control loop (E-Kermit main.c) ----------------------------------------------------------------------- */
void idle() {                                  /* the server, between commands */
    reset();
    if (!k.bctf) k.bct = 1;
    k.state = SV_IDLE;
    gln = 0; glk = 0;
}

void run() {
    int len, status;
    ccount = 0;
    while (1) {
        len = readpkt(k.state == SV_IDLE ? 0 : k.r_timo);
        if (len == 65533) {                    /* Ctrl-C: three in a row cancel */
            if (++ccount >= 3) { setmsg("cancelled (Ctrl-C)"); abortfiles(); stopped = 1; return; }
            continue;
        }
        ccount = 0;
        if (len == 65534) len = 1;             /* a bad packet: NAK it as a timeout would be */
        if (k.state == SV_IDLE && len == 0) continue;     /* the server just waits */
        status = kermit(K_RUN, len);
        if (status == X_DONE) {
            if (server && !finish) { idle(); continue; }
            return;
        }
        if (status == X_ERROR) {
            abortfiles();
            if (server) { idle(); continue; }
            stopped = 1;
            return;
        }
    }
}

int hexval(char *s) {
    int v, c;
    v = 0;
    while ((c = *s)) {
        if (c >= 'a' && c <= 'f') c = c - 32;
        if (c >= '0' && c <= '9') v = v * 16 + c - '0';
        else if (c >= 'A' && c <= 'F') v = v * 16 + c - 'A' + 10;
        else return v;
        s++;
    }
    return v;
}

int decval(char *s) { int v; v = 0; while (*s >= '0' && *s <= '9') { v = v * 10 + *s - '0'; s++; } return v; }

void usage() {
    puts("usage: kermit -r [-a ADDR] [-n] [-k] [-l N]     receive files (the sender names them)");
    puts("       kermit -s FILE... [-B|-T] [-b 1|2|3|5]   send files (globs work)");
    puts("       kermit -x [-a ADDR] [-n] [-k]            server: the far end SENDs, GETs, FINISHes");
    puts("  -a ADDR  load/exec address (hex) of the files received   -n  never replace a file: a new name");
    puts("  -k  keep a file that did not arrive whole   -B/-T  binary (default)/text   -b  block check");
    puts("  -l N  longest packet to receive (20..94)    3 Ctrl-Cs cancel;  man kermit");
}

void report() {                                /* the summary, once the line is quiet */
    int i; char *what;
    what = k.what == W_SEND ? "sent" : "received";
    if (server) what = "moved";
    for (i = 0; i < nlog; i++) {
        putstr("  "); putstr(logn + i * 13); putstr("  ");
        numstring(logh[i], logl[i], nbuf); putstr(nbuf); puts(" bytes");
    }
    putstr("kermit: "); putnum(nfiles); putstr(nfiles == 1 ? " file " : " files "); puts(what);
    if (errmsg[0]) eput2("kermit: ", errmsg);
}

void main() {
    char *a, w[GSLOT]; int act, check, i, j;
    a = argstr();
    act = 0; check = 3; k.xfermode = 0; k.binary = BINARY; k.ikeep = 0; k.r_maxlen = P_PKTLEN;
    loadaddr = 0; noclobber = 0; server = 0;
    while (*a) {
        a = argword(a, w, GSLOT - 1);
        if (w[0] != '-') {
            if (act != 's') { eput2("kermit: what? ", w); return; }
            if (!addfiles(w)) eput2("kermit: no file matches ", w);
            continue;
        }
        if (w[1] == 'r' || w[1] == 's' || w[1] == 'x') {
            if (act) { eputs("kermit: one of -r, -s, -x"); return; }
            act = w[1];
        }
        else if (w[1] == 'B') { k.xfermode = 1; k.binary = BINARY; }
        else if (w[1] == 'T') { k.xfermode = 1; k.binary = TEXT; }
        else if (w[1] == 'k') k.ikeep = 1;
        else if (w[1] == 'n') noclobber = 1;
        else if (w[1] == 'a') { a = argword(a, w, GSLOT - 1); loadaddr = hexval(w); }
        else if (w[1] == 'b') {
            a = argword(a, w, GSLOT - 1); check = decval(w);
            if (check < 1 || check > 5 || check == 4) { eputs("kermit: block check 1, 2, 3 or 5"); return; }
        }
        else if (w[1] == 'l') {
            a = argword(a, w, GSLOT - 1); i = decval(w);
            if (i < 20 || i > P_PKTLEN) { eputs("kermit: -l 20..94"); return; }
            k.r_maxlen = i;
        }
        else { usage(); return; }
    }
    if (!act) { usage(); return; }
    if (act == 's') {                           /* only files: the protocol cannot say why it skips one */
        j = 0;
        for (i = 0; i < gln; i++) {
            a = gl + i * GSLOT;
            if (fresolve(a, ent) && ent_isfile(ent)) { if (j != i) strcpy(gl + j * GSLOT, a); j++; }
            else eput2("kermit: not a file: ", a);
        }
        gln = j;
        if (!gln) { eputs("kermit: -s: no files"); return; }
    }
    if (act == 'x') server = 1;
    kio_fix();
    crcinit();
    xdata = opkt + 4;
    if (act == 's') { putstr("kermit: sending "); putnum(gln); puts(gln == 1 ? " file: start the receiver" : " files: start the receiver"); }
    else if (server) puts("kermit: server; the other side: send, get, finish (3 Ctrl-Cs quit)");
    else puts("kermit: ready to receive: start the sender (3 Ctrl-Cs cancel)");
    fifo(1);
    kermit(K_INIT, 0);
    k.bct = check == 5 ? 3 : check;
    k.bctf = check == 5;
    if (act == 's') kermit(K_SEND, 0);
    else if (server) { idle(); k.bct = 1; }
    run();
    fifo(0);
    report();
    if (stopped) osexit(1);
}
