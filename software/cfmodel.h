/*
 * Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
 */

/*
 * cfmodel.h - the CompactFlash card model shared by both YACC1 emulators (2026-09-22).
 *
 * The card (docs/system/OS-PLAN.md, decision 1) sits in I/O space on two ports: P8 is a write-only register-select
 * latch (bits 0..2 = the ATA task-file register, bit 3 = CF reset on the card, ignored by the model) and P9 is the data port: a read
 * or write of P9 strobes -IOR/-IOW on the selected register. The CF runs in 8-bit True IDE mode. The handshake is
 * the one p8xemu models for the P8X's memory-mapped card (p8x/emulator/p8xemu.c): BSY is never asserted (a transfer
 * is instantaneous), DRQ is raised while a 512-byte buffer streams through the data register and dropped when it
 * drains, ERR on an unknown command. Registers: 0 data, 1 error/feature, 2 sector count (accepted, single-sector
 * model), 3..5 LBA0..2, 6 drive/head (LBA mode bit; bit 4 selects the drive, 2026-11-05), 7 status/command.
 * Commands: $EF SET FEATURES, $EC IDENTIFY, $20 READ SECTORS, $30 WRITE SECTORS. With no image attached every read
 * returns $FF, as a floating bus would, so a bounded status poll times out instead of hanging.
 *
 * Drive 1, the IDE slave (2026-11-05, for /bin/mkdisk): the second image, cf_attach2(path) for -C. The task-file
 * registers are shared, as on one IDE cable; a drive with no image reads $FF, and its commands are ignored.
 *
 * Include after <stdio.h>/<string.h>/<stdint.h>; call cf_attach(path) for -c, then cf_io_write(port, v) for OUTA/OUTI
 * on P8/P9 and cf_io_read(port) for INP on P9.
 */
#ifndef CFMODEL_H
#define CFMODEL_H

#define CF_PORT_SEL  8
#define CF_PORT_DATA 9

static struct {
    FILE *imgs[2];                                /* drive 0 (-c), drive 1 (-C) */
    uint8_t buf[512];
    int idx, drq, err, write;
    uint8_t sel, feat, scnt, lba0, lba1, lba2, head;
} cf;
#define CF_IMG (cf.imgs[(cf.head >> 4) & 1])      /* the selected drive's image */

static long cf_lba(void) { return ((long)(cf.head & 0x0F) << 24) | ((long)cf.lba2 << 16) | ((long)cf.lba1 << 8) | cf.lba0; }
static void cf_seek(void) { if (CF_IMG) fseek(CF_IMG, cf_lba() * 512L, SEEK_SET); }

static int cf_attach_to(int d, const char *path) {   /* open, or create a zero-filled 256-sector image */
    cf.imgs[d] = fopen(path, "r+b");
    if (!cf.imgs[d]) {
        cf.imgs[d] = fopen(path, "w+b");
        if (!cf.imgs[d]) return 0;
        uint8_t z[512]; memset(z, 0, sizeof z);
        for (int i = 0; i < 256; i++) fwrite(z, 1, 512, cf.imgs[d]);
        fflush(cf.imgs[d]);
    }
    return 1;
}
static int cf_attach(const char *path) { return cf_attach_to(0, path); }
static int cf_attach2(const char *path) { return cf_attach_to(1, path); }

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
        case 0x20: memset(cf.buf, 0, 512); cf_seek(); if (CF_IMG) { size_t n = fread(cf.buf, 1, 512, CF_IMG); (void)n; }
                   cf.idx = 0; cf.drq = 1; cf.err = 0; cf.write = 0; break;         /* READ SECTORS */
        case 0x30: cf.idx = 0; cf.drq = 1; cf.err = 0; cf.write = 1; break;         /* WRITE SECTORS */
        default:   cf.err = 1; cf.drq = 0; break;
    }
}

static uint8_t cf_io_read(int port) {
    if (port != CF_PORT_DATA || !CF_IMG) return 0xFF;
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
                if (cf.write && CF_IMG) { cf_seek(); fwrite(cf.buf, 1, 512, CF_IMG); fflush(CF_IMG); }
                cf.idx = 0; cf.drq = 0; cf.write = 0;
            }
            return;
        case 1: cf.feat = v; return;
        case 2: cf.scnt = v; return;
        case 3: cf.lba0 = v; return;
        case 4: cf.lba1 = v; return;
        case 5: cf.lba2 = v; return;
        case 6: cf.head = v; return;
        default: if (CF_IMG) cf_command(v); return;
    }
}

#endif
