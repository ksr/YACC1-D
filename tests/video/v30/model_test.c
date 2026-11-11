/*
 * Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
 */

/*
 * model_test.c - the video card V3 in software/videomodel.h and its HD63484 (software/acrtcmodel.h) on their own
 * (2026-11-11): the ports, the chip's registers and FIFOs, every command the model has - the manual's own examples
 * where it gives one - the font EPROM, the raster count, and the PS/2 keyboard and mouse. Built and run by
 * tests/video/v30/run.py. Prints one line per failed check and "model: N failed".
 */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include "../../../software/videomodel.h"

static int fails;
#define CHECK(c, ...) do { if (!(c)) { fails++; printf("FAIL %d: ", __LINE__); printf(__VA_ARGS__); printf("\n"); } } while (0)

static void fresh(const char *keys, const char *mouse) {
    memset(&vid, 0, sizeof vid); memset(&vid2, 0, sizeof vid2); memset(ac_ram, 0, sizeof ac_ram); vid_clk = 0;
    setenv("Y1VID_CARD", "v3", 1);
    if (keys) setenv("Y1VID_KEYS", keys, 1); else unsetenv("Y1VID_KEYS");
    if (mouse) setenv("Y1VID_MOUSE", mouse, 1); else unsetenv("Y1VID_MOUSE");
    unsetenv("Y1VID_KBD"); unsetenv("Y1_CLOCK");
    vid_init();
}
static void reg(int r, int v) { vid_io_write(0xA, (uint8_t)r); vid_io_write(0xB, (uint8_t)v); }          /* one register byte */
static void reg16(int r, int v) { reg(r, v >> 8); reg(r + 1, v & 0xFF); }
static void w(int v) { vid_io_write(0xB, (uint8_t)(v >> 8)); vid_io_write(0xB, (uint8_t)v); }             /* a FIFO word */
static void fifo(void) { vid_io_write(0xA, 0); }
static void settle(void) { if (vid_clk < ac.free_at) vid_clk = ac.free_at; }                              /* wait for the chip */
static void cmd(int n, ...) { va_list a; settle(); va_start(a, n); for (int i = 0; i < n; i++) w(va_arg(a, int)); va_end(a); }
static int rdw(void) { int h = vid_io_read(0xD); return h << 8 | vid_io_read(0xD); }
static void rwp(int dn, uint32_t a) { cmd(2, 0x080C, dn << 14 | (int)(a >> 12)); cmd(2, 0x080D, (int)(a << 4) & 0xFFFF); }
static uint32_t rwp_now(void) { return ac_rwp(); }

/* the chip started for 640 x 480: ABT off, the Base screen 40 words a line from word 0, a solid pattern */
static void start(void) {
    reg16(0x02, 0x0000);                                 /* CCR: ABT off, 1 bit a pixel */
    reg16(0x04, 0x8088);                                 /* OMR: master, stopped, static RAM, interleaved */
    reg16(0x06, 0x4000);                                 /* DCR: the Base screen on */
    vid_io_write(0xA, 0x82);                             /* the timing registers, the address stepping by itself */
    static const uint8_t t[] = { 0x63, 0x0C, 0x05, 0x4F, 0x02, 0x0D, 0x20, 0x02, 0x01, 0xE0 };
    for (unsigned i = 0; i < sizeof t; i++) vid_io_write(0xB, t[i]);
    reg16(0xCA, 0x0028); reg16(0xCC, 0x0000); reg16(0xCE, 0x0000);   /* MWR1 = 40, SAR1 = 0 */
    reg16(0x04, 0xC088);                                 /* STR */
    fifo();
    cmd(3, 0x0400, 0x4004, 0xAD80);                      /* ORG: the Base screen, word 19,160, dot 0: the bottom-left */
    cmd(2, 0x0800, 0x0000); cmd(2, 0x0801, 0xFFFF);      /* CL0, CL1 */
    cmd(3, 0x1800, 2, 0xFFFF);                           /* WPTN: pattern word 0 (two bytes) */
    cmd(2, 0x0805, 0x0000); cmd(2, 0x0806, 0x0000); cmd(2, 0x0807, 0x00F0);   /* PRC: word 0, bits 0-15 */
}
#define ORGW 19160

int main(void) {
    static uint8_t mem[65536];
    fresh(NULL, NULL);

    /* the card: ports PA-PF, the ID, nothing in the $D000 block, the chip as reset leaves it */
    CHECK(vid2.card == 3, "the card is the V3");
    for (int p = 0; p < 16; p++) CHECK(vid_io_owns(p) == (p >= 10), "port %X", p);
    CHECK((vid_io_read(0xE) & 0xF8) == 0x60, "IN PE: the ID $6x, TEXT 0: %02X", vid_io_read(0xE));
    CHECK(vid_io_read(0xA) == -1 && vid_io_read(0xB) == -1, "PA and PB are write-only");
    vid_write(0xD000, 0x41, mem); CHECK(vid_read(0xD000, mem) == -1 && mem[0xD000] == 0, "nothing at $D000");
    CHECK(vid_io_read(0xC) == 0x23, "status after reset %02X, want 23", vid_io_read(0xC));
    fifo(); cmd(2, 0x4800, 0x1234);
    CHECK(ac_ram[0] == 0 && vid_io_read(0xC) == 0x23, "ABT set by reset: the FIFO is shut");

    /* registers: a byte each, r80 up stepping the address register; the manual's ORG / WPR / RPR */
    start();
    CHECK(ac.reg[0x82] == 0x63 && ac.reg[0x85] == 0x4F && ac.reg[0x8B] == 0xE0 && ac.ar == 0, "the timing table by auto-increment");
    reg(0x02, 0x00); CHECK(ac.ar == 0x02, "no stepping below r80");
    fifo();
    cmd(2, 0x0801, 0x1111); cmd(1, 0x0C01);
    CHECK((vid_io_read(0xC) & 0x0C) == 0x04, "RFR after RPR"); CHECK(rdw() == 0x1111, "RPR CL1");
    CHECK((vid_io_read(0xC) & 0x04) == 0 && vid_io_read(0xD) == 0xFF, "the read FIFO empty again");
    cmd(2, 0x0801, 0xFFFF);
    settle(); w(0x0801); CHECK((vid_io_read(0xC) & 0x20) == 0, "CED 0 between a command's words"); w(0xFFFF);
    settle(); CHECK((vid_io_read(0xC) & 0x20) == 0x20, "CED 1 after it");

    /* WT, RD, MOD: the manual's examples at word $56 */
    rwp(0, 0x56); cmd(2, 0x4800, 0x5555);
    CHECK(ac_ram[0x56] == 0x5555 && rwp_now() == 0x57, "WT, RWP + 1");
    rwp(0, 0x56); cmd(1, 0x4400); CHECK(rdw() == 0x5555 && rwp_now() == 0x57, "RD");
    cmd(2, 0x0804, 0xFFFF); rwp(0, 0x56); cmd(2, 0x4C01, 0xAAAA); CHECK(ac_ram[0x56] == 0xFFFF, "MOD OR");
    cmd(2, 0x0804, 0x00FF); rwp(0, 0x56); cmd(2, 0x4C00, 0x1234); CHECK(ac_ram[0x56] == 0xFF34, "MOD replace under the mask");
    rwp(0, 0x56); cmd(2, 0x4C03, 0xFFFF); CHECK(ac_ram[0x56] == 0xFFCB, "MOD EOR under the mask");
    rwp(0, 0x56); cmd(2, 0x4C02, 0x000F); CHECK(ac_ram[0x56] == 0xFF0B, "MOD AND under the mask");

    /* CLR: the manual's example - screen 0, MW $10, from $56, AX = -4, AY = -6: 5 words x 7 lines, RWPe = $C6 */
    memset(ac_ram, 0, sizeof ac_ram);
    reg16(0xC2, 0x0010); fifo();
    rwp(0, 0x56); cmd(4, 0x5800, 0x1111, 0xFFFC, 0xFFFA);
    { int n = 0; for (int i = 0; i < 0x200; i++) n += ac_ram[i] == 0x1111;
      CHECK(n == 35 && ac_ram[0x52] == 0x1111 && ac_ram[0x56] == 0x1111 && ac_ram[0x51] == 0 && ac_ram[0x57] == 0 &&
            ac_ram[0xB2] == 0x1111 && ac_ram[0xB6] == 0x1111 && ac_ram[0xC2] == 0 && ac_ram[0x46] == 0, "CLR's area: %d words", n);
      CHECK(rwp_now() == 0xC6, "CLR RWPe %05X, want C6", rwp_now()); }
    cmd(2, 0x0804, 0x0F0F); rwp(0, 0x56); cmd(4, 0x5C03, 0xFFFF, 1, 1);          /* SCLR EOR, 2 x 2 going up */
    CHECK(ac_ram[0x56] == 0x1E1E && ac_ram[0x57] == 0x0F0F && ac_ram[0x46] == 0x0F0F && ac_ram[0x47] == 0x0F0F && rwp_now() == 0x36, "SCLR up");

    /* CPY: a 3 x 2 block to another place; the eight destination directions' end points; S = 1 turns it */
    memset(ac_ram, 0, sizeof ac_ram);
    for (int j = 0; j < 2; j++) for (int i = 0; i < 3; i++) ac_ram[0x100 + j * 16 + i] = (uint16_t)(0xA0 + j * 16 + i);   /* A0 A1 A2 / B0 B1 B2 */
    rwp(0, 0x200); cmd(5, 0x6100, 0x0000, 0x1000, 2, 0xFFFF);                    /* S 0, DSD 001: from $100, down */
    CHECK(ac_ram[0x200] == 0xA0 && ac_ram[0x202] == 0xA2 && ac_ram[0x210] == 0xB0 && ac_ram[0x212] == 0xB2 && rwp_now() == 0x220, "CPY down");
    rwp(0, 0x300); cmd(5, 0x6000, 0x0000, 0x1000, 2, 0xFFFF);                    /* DSD 000: the lines go up */
    CHECK(ac_ram[0x300] == 0xA0 && ac_ram[0x2F0] == 0xB0 && ac_ram[0x2F2] == 0xB2 && rwp_now() == 0x2E0, "CPY up");
    rwp(0, 0x400); cmd(5, 0x6300, 0x0000, 0x1000, 2, 0xFFFF);                    /* DSD 011: leftwards, down */
    CHECK(ac_ram[0x400] == 0xA0 && ac_ram[0x3FE] == 0xA2 && ac_ram[0x40E] == 0xB2 && rwp_now() == 0x420, "CPY mirrored");
    rwp(0, 0x500); cmd(5, 0x6800, 0x0000, 0x1000, 2, 0xFFFF);                    /* S 1, DSD 000: figure C14-2 */
    CHECK(ac_ram[0x500] == 0xA0 && ac_ram[0x501] == 0xB0 && ac_ram[0x4F0] == 0xA1 && ac_ram[0x4E1] == 0xB2, "CPY turned");
    CHECK(rwp_now() == 0x500 - 3 * 16, "RWPe = RWP - (AX + 1) x MW: %05X", rwp_now());
    for (int i = 0; i < 8; i++) ac_ram[0x600 + i * 16] = (uint16_t)(i + 1);       /* a column, moved up two lines over itself */
    rwp(0, 0x600); cmd(5, 0x6100, 0x0000, 0x6200, 0, 0xFFFB);                    /* from $620, 6 lines down, to $600 */
    CHECK(ac_ram[0x600] == 3 && ac_ram[0x650] == 8 && ac_ram[0x660] == 7, "an overlapping copy, the right way round");

    /* the font EPROM: MA19 high, the byte on both halves of a word; the even places' half, then the odd places' */
    CHECK(ac_rd(0x80A28) == 0x1C1C && ac_rd(0x80A00) == 0, "the EPROM: 'A' (row 1, place 1) line 1 = %04X", ac_rd(0x80A28));
    CHECK(ac_rd(0x802A8) == 0x3E3E, "'@' (row 1, place 0) line 1 = %04X", ac_rd(0x802A8));
    ac_wr(0x80A28, 0xFFFF); CHECK(ac_rd(0x80A28) == 0x1C1C, "writes to the EPROM are lost");
    CHECK(ac_rd(0x20000 + 5) == ac_rd(5) && ac_rd(0x7FFFF) == ac_rd(0x1FFFF), "the RAM repeats below the EPROM");
    /* the font's picture put together under the screen by two masked copies, as the ROM does; then text with one
       graphic copy a character (AGCPY ED00: down the columns, to the right), the pointer left at the next cell */
    memset(ac_ram, 0, sizeof ac_ram);
    cmd(2, 0x0804, 0x00FF); rwp(1, 19200); cmd(5, 0x7100, 0x0080, 0x0000, 15, 0xFFD1);
    cmd(2, 0x0804, 0xFF00); rwp(1, 19200); cmd(5, 0x7100, 0x0080, 0x7800, 15, 0xFFD1);
    CHECK(ac_ram[19200 + 17 * 40] == 0x1C3E && ac_ram[19200 + 16 * 40] == 0 && rwp_now() == 19200 + 48 * 40, "the picture: '@' and 'A' in a word: %04X", ac_ram[19200 + 17 * 40]);
    { unsigned n = 0; for (int l = 0; l < 480; l++) for (int k = 0; k < 40; k++) n += ac_ram[l * 40 + k] != 0;
      for (int l = 480; l < 528; l++) for (int k = 16; k < 40; k++) n += ac_ram[l * 40 + k] != 0;
      CHECK(n == 0, "nothing on the screen, nothing beside the picture: %u words", n); }
    cmd(3, 0x8000, 16, 463);                                                     /* row 1, column 2 */
    cmd(5, 0xED00, 0x00B0, 0xFFEF, 7, 0xFFF1); CHECK(ac.cx == 24 && ac.cy == 463, "the pointer at the next cell: (%d, %d)", ac.cx, ac.cy);
    cmd(5, 0xED00, 0x0098, 0xFFFF, 7, 0xFFF1);
    CHECK(ac_ram[681] == 0x3E41 && ac_ram[640] == 0 && ac_ram[641] == 0, "\"V3\"'s second line: %04X", ac_ram[681]);
    CHECK(v3_cell(0, 40, 1, 2) == 'V' && v3_cell(0, 40, 1, 3) == '3' && v3_cell(0, 40, 1, 4) == ' ', "read back as text");
    cmd(3, 0x8000, 16, 463); cmd(5, 0xED00, 0x0000, 0xFFDF, 7, 0xFFF1);          /* a lower case place: row 2 */
    cmd(5, 0xED00, 0x0000, 0xFFFF, 7, 0xFFF1);                                   /* and a blank over the '3' */
    CHECK(v3_cell(0, 40, 1, 2) == '@' && v3_cell(0, 40, 1, 3) == ' ', "a glyph replaces what was in the cell");
    ac_ram[680] ^= 0x0010; CHECK(v3_cell(0, 40, 1, 0) == '?', "a cell that is no glyph");

    /* dots: X with the bit number, Y up; a line leaves its last dot; a rectangle's four sides; a filled area */
    memset(ac_ram, 0, sizeof ac_ram);
    cmd(3, 0x8000, 0, 0); cmd(1, 0xCC00); CHECK(ac_ram[ORGW] == 0x0001, "DOT at the origin: bit 0 of word 19,160");
    cmd(3, 0x8000, 3, 2); cmd(1, 0xCC00); CHECK(ac_ram[ORGW - 80] == 0x0008, "(3, 2): two lines up, bit 3");
    cmd(3, 0x8000, 17, 1); cmd(1, 0xCC00); CHECK(ac_ram[ORGW - 40 + 1] == 0x0002, "(17, 1): the next word");
    cmd(3, 0x8400, 0xFFEE, 0xFFFF); cmd(1, 0xCC00);                              /* RMOVE (-18, -1) -> (-1, 0) */
    CHECK(ac_ram[ORGW - 1] == 0x8000, "(-1, 0): the word before, bit 15");
    memset(ac_ram, 0, sizeof ac_ram);
    cmd(3, 0x8000, 0, 0); cmd(3, 0x8800, 16, 0);
    CHECK(ac_ram[ORGW] == 0xFFFF && ac_ram[ORGW + 1] == 0 && ac.cx == 16 && ac.cy == 0, "ALINE: 16 dots, the end not drawn");
    cmd(3, 0x8C00, 0, 3); CHECK(ac_ram[ORGW + 1] == 1 && ac_ram[ORGW + 1 - 80] == 1 && ac_ram[ORGW + 1 - 120] == 0 && ac.cy == 3, "RLINE up");
    cmd(1, 0x0C12); CHECK(rdw() == 16, "RPR CP x"); cmd(1, 0x0C13); CHECK(rdw() == 3, "RPR CP y");
    cmd(1, 0x0C10); cmd(1, 0x0C11);
    { int h = rdw(), l = rdw(); uint32_t a = (uint32_t)(h & 0xFF) << 12 | (uint32_t)l >> 4;
      CHECK(h >> 14 == 1 && a == ORGW - 120 + 1 && (l & 15) == 0, "RPR DP: screen %d, word %u, dot %d", h >> 14, a, l & 15); }
    memset(ac_ram, 0, sizeof ac_ram);
    cmd(3, 0x8000, 100, 100); cmd(3, 0x9000, 110, 105);
    { int n = 0; for (unsigned i = 0; i < AC_RAMW; i++) n += __builtin_popcount(ac_ram[i]);
      CHECK(n == 30 && ac.cx == 100 && ac.cy == 100, "ARCT: %d dots on the rectangle, CP back at its start", n); }
    memset(ac_ram, 0, sizeof ac_ram);
    cmd(3, 0x8000, 0, 12); cmd(3, 0xC000, 31, 10);                               /* AFRCT (0,12)-(31,10): downwards */
    CHECK(ac_ram[ORGW - 480] == 0xFFFF && ac_ram[ORGW - 479] == 0xFFFF && ac_ram[ORGW - 400] == 0xFFFF && ac_ram[ORGW - 478] == 0 &&
          ac_ram[ORGW - 360] == 0 && ac_ram[ORGW - 520] == 0, "AFRCT: 32 x 3 dots");
    CHECK(ac.cx == 0 && ac.cy == 9, "AFRCT ends a line past the area: (%d, %d)", ac.cx, ac.cy);
    cmd(3, 0x8000, 4, 11); cmd(3, 0xC403, 3, 0);                                 /* RFRCT EOR: 4 dots of line 11 off */
    CHECK(ac_ram[ORGW - 440] == 0xFF0F, "RFRCT EOR: %04X", ac_ram[ORGW - 440]);

    /* the pattern RAM: a dashed line; colour mode 1 leaves the 0 dots alone; zoom doubles each pattern dot */
    memset(ac_ram, 0, sizeof ac_ram);
    cmd(3, 0x1800, 2, 0x000F); cmd(2, 0x0807, 0x0070); cmd(2, 0x0805, 0);        /* 1111 0000, eight dots long */
    cmd(2, 0x0800, 0xFFFF); cmd(3, 0x8000, 0, 0); cmd(3, 0x8808, 16, 0);         /* COL 01, CL0 all ones: it must not show */
    CHECK(ac_ram[ORGW] == 0x0F0F, "a dashed line: %04X", ac_ram[ORGW]);
    cmd(2, 0x0807, 0x0071); cmd(2, 0x0805, 0); cmd(3, 0x8000, 0, 1); cmd(3, 0x8808, 16, 1);
    CHECK(ac_ram[ORGW - 40] == 0x00FF, "the pattern at zoom 2: %04X", ac_ram[ORGW - 40]);
    cmd(2, 0x0800, 0x0000); cmd(3, 0x1800, 2, 0xFFFF); cmd(2, 0x0807, 0x00F0); cmd(2, 0x0805, 0);

    /* the area: drawing kept inside it (mode 2), stopped at its edge with ARD (mode 1) */
    memset(ac_ram, 0, sizeof ac_ram);
    cmd(2, 0x0808, 0); cmd(2, 0x0809, 0); cmd(2, 0x080A, 9); cmd(2, 0x080B, 9);
    cmd(3, 0x8000, 5, 5); cmd(3, 0x8840, 20, 5);
    CHECK(ac_ram[ORGW - 200] == 0x03E0 && (vid_io_read(0xC) & 0x40) == 0 && ac.cx == 20, "clipped to the area: %04X", ac_ram[ORGW - 200]);
    cmd(3, 0x8000, 5, 6); cmd(3, 0x8820, 20, 6);
    CHECK(ac_ram[ORGW - 240] == 0x03E0 && (vid_io_read(0xC) & 0x40) && ac.cx == 10, "stopped at the edge, ARD set, CP (%d, %d)", ac.cx, ac.cy);
    cmd(1, 0x0C12); (void)rdw(); CHECK((vid_io_read(0xC) & 0x40) == 0, "RPR clears ARD");

    /* a polyline and a polygon; the graphic copy, dot by dot, to a place that is not on a word's edge */
    memset(ac_ram, 0, sizeof ac_ram);
    cmd(3, 0x8000, 0, 0); cmd(6, 0x9800, 2, 8, 0, 8, 2);                         /* APLL (0,0)-(8,0)-(8,2) */
    CHECK(ac_ram[ORGW] == 0x01FF && ac_ram[ORGW - 40] == 0x0100 && ac_ram[ORGW - 80] == 0 && ac.cy == 2, "APLL: %04X", ac_ram[ORGW]);
    memset(ac_ram, 0, sizeof ac_ram);
    cmd(3, 0x8000, 0, 0); cmd(6, 0xA400, 2, 4, 0, 0, 4);                         /* RPLG: a triangle, closed */
    { int n = 0; for (unsigned i = 0; i < AC_RAMW; i++) n += __builtin_popcount(ac_ram[i]);
      settle(); CHECK(n == 12 && ac.cx == 0 && ac.cy == 0 && (vid_io_read(0xC) & 0x20), "RPLG: %d dots, closed", n); }
    memset(ac_ram, 0, sizeof ac_ram);
    ac_ram[ORGW] = 0x0005; ac_ram[ORGW - 40] = 0x0003;                           /* (0,0) (2,0) / (0,1) (1,1) */
    cmd(3, 0x8000, 21, 4); cmd(5, 0xE000, 0, 0, 2, 1);                           /* AGCPY 3 x 2 dots to (21, 4), going up */
    CHECK(ac_ram[ORGW - 160 + 1] == 0x00A0 && ac_ram[ORGW - 200 + 1] == 0x0060, "AGCPY: %04X %04X", ac_ram[ORGW - 159], ac_ram[ORGW - 199]);
    CHECK(ac.cx == 21 && ac.cy == 6, "AGCPY's end point (%d, %d)", ac.cx, ac.cy);

    /* two and four bits a pixel: the dot's field, the colour register's field at that place */
    memset(ac_ram, 0, sizeof ac_ram);
    reg(0x02, 0x02); fifo();                                                      /* GBM: 4 bits a pixel */
    cmd(2, 0x0801, 0x5555); cmd(3, 0x8000, 2, 0); cmd(1, 0xCC00);
    CHECK(ac_ram[ORGW] == 0x0500, "4 bits a pixel, dot 2: %04X", ac_ram[ORGW]);
    cmd(3, 0x8000, 5, 0); cmd(1, 0xCC00); CHECK(ac_ram[ORGW + 1] == 0x0050, "dot 5: the next word, its second field");
    reg(0x02, 0x00); fifo(); cmd(2, 0x0801, 0xFFFF);

    /* what the model does not draw says so; ABT clears it; a word that is no command */
    cmd(2, 0xA800, 10);
    CHECK((vid_io_read(0xC) & 0x80) && ac.missing == 1, "CRCL: CER set, counted");
    reg(0x02, 0x80); CHECK(vid_io_read(0xC) == 0x23, "ABT: status 23"); reg(0x02, 0x00); fifo();
    cmd(1, 0x3000); CHECK(vid_io_read(0xC) & 0x80, "$3000 is no command: CER"); reg(0x02, 0x80); reg(0x02, 0x00); fifo();

    /* time: a clear of the screen keeps the chip busy 84,504 2CLK cycles (42,252 by the table, twice that interleaved);
       meanwhile 16 bytes wait in the FIFO and a 17th is lost */
    rwp(1, 0); settle();
    { unsigned long long t0 = vid_clk;
      w(0x5800); w(0); w(39); w(0xFE21);
      CHECK(ac.free_at - t0 == 13427, "the clear takes %llu clocks at 1 MHz, want 13427", ac.free_at - t0);
      CHECK((vid_io_read(0xC) & 0x23) == 0x03, "busy: CED 0, the FIFO empty and ready");
      for (int i = 0; i < 4; i++) { w(0x0800); w(0x1234); }
      CHECK((vid_io_read(0xC) & 0x03) == 0x00, "16 bytes waiting: WFR 0, WFE 0");
      vid_io_write(0xB, 0x08); CHECK(ac.lost == 1, "a 17th byte is lost");
      vid_clk = ac.free_at - 1; CHECK((vid_io_read(0xC) & 0x20) == 0, "busy to the last clock");
      vid_clk = ac.free_at; CHECK(vid_io_read(0xC) == 0x23 && ac.pr[0] == 0x1234, "then idle: status %02X", vid_io_read(0xC));
      cmd(2, 0x0800, 0x0000); }
    reg16(0x04, 0xC080); fifo(); rwp(1, 0); settle();                            /* single access: the table's own time */
    { unsigned long long t0 = vid_clk; w(0x5800); w(0); w(39); w(0xFE21);
      CHECK(ac.free_at - t0 == 6714, "single access: %llu clocks, want 6714", ac.free_at - t0); }
    reg16(0x04, 0xC088); fifo(); settle();

    /* the raster count: 100 memory cycles a line, 525 lines, 3,146,875 memory cycles a second */
    vid_clk = 1000000; vid_io_write(0xA, 0x80);
    { int h = vid_io_read(0xD), l = vid_io_read(0xD);
      CHECK((h << 8 | l) == 493 && ac.ar == 0x82, "RCR after one second: %d, want 493", h << 8 | l); }
    reg16(0x04, 0x8088); vid_io_write(0xA, 0x80); (void)vid_io_read(0xD); CHECK(vid_io_read(0xD) == 0, "RCR 0 while the chip is stopped");

    /* the keyboard and the mouse: a key, a packet where \m puts it, a key; SRC says which; mouse off drops packets */
    fresh("a\\mb", "5,-3,1;-2,4,0");
    vid_clk = 0;
    CHECK((vid_io_read(0xE) & 0x07) == 0x01 && vid_io_read(0xF) == 'a', "a key, SRC 0");
    vid_clk += 20; CHECK((vid_io_read(0xE) & 0x07) == 0x03 && vid_io_read(0xF) == 0x29, "the packet's first byte, SRC 1: buttons 1, dy negative");
    vid_clk += 20; CHECK(vid_io_read(0xF) == 0x05, "dx"); vid_clk += 20; CHECK(vid_io_read(0xF) == 0xFD, "dy");
    vid_clk += 20; CHECK((vid_io_read(0xE) & 0x03) == 0x01 && vid_io_read(0xF) == 'b', "the next key");
    vid_clk += 20; CHECK((vid_io_read(0xE) & 0x03) == 0x03 && vid_io_read(0xF) == 0x18, "the second packet: dx negative");
    vid_io_write(0xE, 0x05);                                                     /* mouse off */
    CHECK((vid_io_read(0xE) & 0x04) == 0x04, "BUSY after a command");
    vid_clk += 40; CHECK((vid_io_read(0xE) & 0x05) == 0, "the mouse off: the rest of the packet waits, BUSY over");
    vid_io_write(0xE, 0x04); vid_clk += 40;                                      /* on again: it comes */
    CHECK((vid_io_read(0xE) & 0x03) == 0x03 && vid_io_read(0xF) == 0xFE, "the mouse on: the packet goes on");
    vid_clk += 20; CHECK(vid_io_read(0xF) == 0x04, "its last byte");
    fresh("\\mz", "1,1,0"); vid_io_write(0xE, 0x05);                             /* a key behind a waiting packet */
    vid_clk += 40; CHECK((vid_io_read(0xE) & 0x03) == 0x01 && vid_io_read(0xF) == 'z', "the key behind a waiting packet goes first");
    vid_io_write(0xE, 0x04); vid_clk += 40; CHECK((vid_io_read(0xE) & 0x03) == 0x03 && vid_io_read(0xF) == 0x08, "then the packet");
    vid_io_write(0xE, 0x15); CHECK(vid2.leds == 5, "the LEDs");

    printf("model: %d failed\n", fails);
    return fails != 0;
}
