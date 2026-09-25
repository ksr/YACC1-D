/*
 * videomodel.h - the video card model shared by both YACC1 emulators (2026-09-25).
 *
 * The card (docs/cards/video.md) answers in the 4K block $D000-$DFFF: with ADDR11 low the CPU port of the IDT7134
 * display RAM (2K reachable, $D000-$D7FF), with ADDR11 high the MC6845's register interface at even addresses (A1
 * picks the address register (0) or the data register (1), as after the RS-to-A1 bench fix: $D800 / $D802, repeating
 * every 4 bytes) and the JP1 read-back latch at odd addresses (reads $FF: nothing jumpered, as on the bench). The
 * model keeps the display RAM in the emulator's own memory array, so a program sees plain RAM there as before.
 *
 *   -V   at exit (a -x HALT, the monitor's 0 command, a limit, any exit) print the screen on stderr: the geometry is the
 *        CRTC's R1 x R6 from R12/R13 when a program has written them, else the monitor's default 80 x 24 from $D000;
 *        each byte shown as its glyph under the 2513-style assumption (bits 0-5; 00-1F = @..underscore, 20-3F =
 *        blank..?), then the 18 CRTC registers
 *   -W   log every CRTC register write (and any write to the latch's odd addresses: a bus fight on the card) on stderr
 *   -N   no video card: $D000-$DFFF reads $FF (the ucemu model leaves the bus to its pull-ups) and ignores writes,
 *        to test the monitor's "not present" path
 *
 * Include after <stdio.h>/<stdint.h>. vid_in(a) says whether an address is the card's; vid_read/vid_write serve it,
 * with mem = the emulator's memory array (the display RAM half lives there).
 */
#ifndef VIDEOMODEL_H
#define VIDEOMODEL_H

#define VID_BASE   0xD000
#define VID_CRTC   0xD800                 /* ADDR11 high: the CRTC / latch half */
#define VID_COLS   80                     /* the monitor's default geometry (monitor.asm VCOLS/VROWS) */
#define VID_ROWS   24

static struct {
    int absent, dump, log;
    uint8_t sel, reg[18], written[18];
} vid;

static int vid_in(unsigned a) { return a >= 0xD000 && a <= 0xDFFF; }

static int vid_read(unsigned a, const uint8_t *mem) {   /* the byte a read of a returns; -1 = nothing drives the bus */
    if (vid.absent) return -1;
    if (a < VID_CRTC) return mem[a];
    if (a & 1) return 0xFF;                               /* the JP1 latch, nothing jumpered */
    if (!(a & 2)) return -1;                              /* the 6845's address register is write-only */
    if (vid.sel >= 12 && vid.sel <= 17) return vid.reg[vid.sel];   /* R12-R17 read back */
    return 0;                                             /* the write-only registers read 0 */
}

static void vid_write(unsigned a, uint8_t v, uint8_t *mem) {
    if (vid.absent) return;
    if (a < VID_CRTC) { mem[a] = v; return; }
    if (a & 1) { if (vid.log) fprintf(stderr, "video: write %02X to $%04X, the JP1 latch (a bus fight on the card)\n", v, a); return; }
    if (!(a & 2)) { vid.sel = v & 0x1F; return; }
    if (vid.sel < 18) {
        vid.reg[vid.sel] = v; vid.written[vid.sel] = 1;
        if (vid.log) fprintf(stderr, "video: CRTC R%d <- %02X\n", vid.sel, v);
    }
}

static void vid_dump(const uint8_t *mem) {
    if (!vid.dump) return;
    if (vid.absent) { fprintf(stderr, "video: no card (-N)\n"); return; }
    int cols = VID_COLS, rows = VID_ROWS; unsigned start = VID_BASE;
    int crtc = vid.written[1] && vid.written[6] && vid.reg[1] && vid.reg[6];
    if (crtc) { cols = vid.reg[1]; rows = vid.reg[6] & 0x7F; start = VID_BASE + (((vid.reg[12] & 0x3F) << 8 | vid.reg[13]) & 0x7FF); }
    fprintf(stderr, "video: %d x %d from $%04X (%s)\n", cols, rows, start, crtc ? "CRTC R1/R6/R12/R13" : "default geometry");
    fprintf(stderr, "+"); for (int c = 0; c < cols; c++) fputc('-', stderr); fprintf(stderr, "+\n");
    for (int r = 0; r < rows; r++) {
        fputc('|', stderr);
        for (int c = 0; c < cols; c++) {
            unsigned a = VID_BASE + (((start - VID_BASE) + r * cols + c) & 0x7FF);   /* the CPU sees 2K */
            fputc(((mem[a] + 0x20) & 0x3F) + 0x20, stderr);
        }
        fprintf(stderr, "|\n");
    }
    fprintf(stderr, "+"); for (int c = 0; c < cols; c++) fputc('-', stderr); fprintf(stderr, "+\n");
    fprintf(stderr, "video: CRTC");
    for (int i = 0; i < 18; i++) fprintf(stderr, vid.written[i] ? " %02X" : " --", vid.reg[i]);
    fprintf(stderr, "  (R0..R17, -- = never written)\n");
}

#endif
