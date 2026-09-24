/*
 * cfmodel.h - the CompactFlash card model shared by both YACC1 emulators (2026-09-22).
 *
 * The card (docs/system/OS-PLAN.md, decision 1) sits in I/O space on two ports: P4 is a write-only register-select
 * latch (bits 0..2 = the ATA task-file register, bit 3 = the CS1 block, unused here) and P5 is the data port: a read
 * or write of P5 strobes -IOR/-IOW on the selected register. The CF runs in 8-bit True IDE mode. The handshake is
 * the one p8xemu models for the P8X's memory-mapped card (p8x/emulator/p8xemu.c): BSY is never asserted (a transfer
 * is instantaneous), DRQ is raised while a 512-byte buffer streams through the data register and dropped when it
 * drains, ERR on an unknown command. Registers: 0 data, 1 error/feature, 2 sector count (accepted, single-sector
 * model), 3..5 LBA0..2, 6 drive/head (LBA mode bit; the device bit is ignored: one drive), 7 status/command.
 * Commands: $EF SET FEATURES, $EC IDENTIFY, $20 READ SECTORS, $30 WRITE SECTORS. With no image attached every read
 * returns $FF, as a floating bus would, so a bounded status poll times out instead of hanging.
 * Ports: P8/P9 until 2026-09-23, then P4/P5, when the interface moved onto the I/O card v2.0, whose own 74LS138
 * (IC5, strapped to P0-P7) decodes them on its spare outputs Y4/Y5 (docs/cards/cf.md).
 *
 * Include after <stdio.h>/<string.h>/<stdint.h>; call cf_attach(path) for -c, then cf_io_write(port, v) for OUTA/OUTI
 * on P4/P5 and cf_io_read(port) for INP on P5.
 */
#ifndef CFMODEL_H
#define CFMODEL_H

#define CF_PORT_SEL  4
#define CF_PORT_DATA 5

static struct {
    FILE *img;
    uint8_t buf[512];
    int idx, drq, err, write;
    uint8_t sel, feat, scnt, lba0, lba1, lba2, head;
} cf;

static long cf_lba(void) { return ((long)(cf.head & 0x0F) << 24) | ((long)cf.lba2 << 16) | ((long)cf.lba1 << 8) | cf.lba0; }
static void cf_seek(void) { if (cf.img) fseek(cf.img, cf_lba() * 512L, SEEK_SET); }

static int cf_attach(const char *path) {          /* open, or create a zero-filled 256-sector image */
    cf.img = fopen(path, "r+b");
    if (!cf.img) {
        cf.img = fopen(path, "w+b");
        if (!cf.img) return 0;
        uint8_t z[512]; memset(z, 0, sizeof z);
        for (int i = 0; i < 256; i++) fwrite(z, 1, 512, cf.img);
        fflush(cf.img);
    }
    return 1;
}

static void cf_identify(void) {                   /* ATA IDENTIFY: words 27..46 = model string, byte-swapped */
    const char *m = "YACC1-CF EMULATOR                       ";
    memset(cf.buf, 0, 512);
    for (int i = 0; i < 40; i += 2) { cf.buf[54 + i] = m[i + 1]; cf.buf[54 + i + 1] = m[i]; }
    cf.idx = 0; cf.drq = 1; cf.err = 0; cf.write = 0;
}

static void cf_command(uint8_t v) {
    switch (v) {
        case 0xEF: cf.err = 0; cf.drq = 0; break;                                   /* SET FEATURES (8-bit mode) */
        case 0xEC: cf_identify(); break;
        case 0x20: memset(cf.buf, 0, 512); cf_seek(); if (cf.img) { size_t n = fread(cf.buf, 1, 512, cf.img); (void)n; }
                   cf.idx = 0; cf.drq = 1; cf.err = 0; cf.write = 0; break;         /* READ SECTORS */
        case 0x30: cf.idx = 0; cf.drq = 1; cf.err = 0; cf.write = 1; break;         /* WRITE SECTORS */
        default:   cf.err = 1; cf.drq = 0; break;
    }
}

static uint8_t cf_io_read(int port) {
    if (port != CF_PORT_DATA || !cf.img) return 0xFF;
    switch (cf.sel & 7) {
        case 0: {                                                                   /* data */
            if (!cf.drq) return 0xFF;
            uint8_t v = cf.buf[cf.idx++];
            if (cf.idx >= 512) { cf.idx = 0; cf.drq = 0; }
            return v;
        }
        case 1: return cf.err ? 0x04 : 0x00;                                        /* error register: ABRT */
        case 2: return cf.scnt;
        case 3: return cf.lba0;
        case 4: return cf.lba1;
        case 5: return cf.lba2;
        case 6: return cf.head;
        default: return 0x40 | (cf.drq ? 0x08 : 0) | (cf.err ? 0x01 : 0);          /* status: DRDY, DRQ, ERR */
    }
}

static void cf_io_write(int port, uint8_t v) {
    if (port == CF_PORT_SEL) { cf.sel = v; return; }
    if (port != CF_PORT_DATA) return;
    switch (cf.sel & 7) {
        case 0:                                                                     /* data */
            if (!cf.drq) return;
            cf.buf[cf.idx++] = v;
            if (cf.idx >= 512) {
                if (cf.write && cf.img) { cf_seek(); fwrite(cf.buf, 1, 512, cf.img); fflush(cf.img); }
                cf.idx = 0; cf.drq = 0; cf.write = 0;
            }
            return;
        case 1: cf.feat = v; return;
        case 2: cf.scnt = v; return;
        case 3: cf.lba0 = v; return;
        case 4: cf.lba1 = v; return;
        case 5: cf.lba2 = v; return;
        case 6: cf.head = v; return;
        default: if (cf.img) cf_command(v); return;
    }
}

#endif
