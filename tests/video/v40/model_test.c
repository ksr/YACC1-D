/*
 * Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
 */

/*
 * model_test.c - software/videomodel.h's video card V4 on its own (2026-11-14; docs/cards/video-v4.md): the ports and
 * the two control registers, the 64K behind the window, the text-only build, the PS/2 controller on the same ports as
 * V2.0's, and the arithmetic of VSYNC / DE to the clock at 16 dots a count from 25.175 MHz.
 * Built and run by tests/video/v40/run.py. Prints one line per failed check and "model: N failed".
 */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "../../../software/videomodel.h"

static int fails;
#define CHECK(c, ...) do { if (!(c)) { fails++; printf("FAIL %d: ", __LINE__); printf(__VA_ARGS__); printf("\n"); } } while (0)

static void fresh(const char *card, const char *keys, const char *textonly) {
    memset(&vid, 0, sizeof vid); memset(&vid2, 0, sizeof vid2); vid_clk = 0;
    setenv("Y1VID_CARD", card, 1);
    if (keys) setenv("Y1VID_KEYS", keys, 1); else unsetenv("Y1VID_KEYS");
    if (textonly) setenv("Y1VID_TEXTONLY", textonly, 1); else unsetenv("Y1VID_TEXTONLY");
    unsetenv("Y1VID_KBD"); unsetenv("Y1VID_DOTS"); unsetenv("Y1_CLOCK");
    vid_init();
}

static int at(unsigned long long clk, int port) { vid_clk = clk; return vid_io_read(port); }

/* the clock at which the 6845's count n begins: a count is 16 dots of 25.175 MHz, the CPU clock 1 MHz */
static unsigned long long count_clk(unsigned long long n) { return (n * 16 * 1000000ULL + 25175000ULL - 1) / 25175000ULL; }

int main(void) {
    static uint8_t mem[65536];

    /* the ports, the status, the 6845 */
    fresh("v4", NULL, NULL);
    CHECK(vid2.card == 4, "Y1VID_CARD=v4");
    for (int p = 0; p < 16; p++) CHECK(vid_io_owns(p) == (p >= 10), "port %X", p);
    CHECK(at(0, 0xC) == 0x70, "status %02X, want 70 (the ID $7x, no DOTS bit)", at(0, 0xC));
    CHECK(at(0, 0xA) == -1 && at(0, 0xF) == -1, "PA / PF read float");
    vid_io_write(0xA, 15); vid_io_write(0xB, 0x5A); vid_io_write(0xA, 15);
    CHECK(at(0, 0xB) == 0x5A, "R15 through PA/PB");
    setenv("Y1VID_DOTS", "6", 1); vid_init(); unsetenv("Y1VID_DOTS");
    CHECK(at(0, 0xC) == 0x70 && vid2.dots == 16, "Y1VID_DOTS means nothing on V4");

    /* the window: PLANE's four bits and CPAGE of control 1; control 2 on PF, not part of the address */
    fresh("v4", NULL, NULL);
    vid_io_write(0xC, 0x1D);                              /* CPU page 1, plane 13 */
    vid_write(0xD805, 0x77, mem);
    CHECK(vid2.gram[32768 + 13 * 2048 + 5] == 0x77 && mem[0xD805] == 0, "the window: page 1 plane 13");
    vid_io_write(0xC, 0x0D);
    CHECK(vid_read(0xD805, mem) == 0, "page 0 plane 13 is another byte");
    vid_io_write(0xC, 0x3D | 0xC0);                       /* DPAGE, GFX-ON and XOR are not in the CPU's address */
    CHECK(vid_read(0xD805, mem) == 0x77, "control 1 bits 5-7 leave the window where it is");
    vid_io_write(0xF, 0xFF);
    CHECK(vid2.control2 == 0xFF && vid_read(0xD805, mem) == 0x77 && vid2.control == 0xFD, "control 2 on PF");
    for (int c = 0; c < 32; c++) { vid_io_write(0xC, (uint8_t)c); vid_write(0xDFFF, (uint8_t)(0x80 + c), mem); }
    int bad = 0;
    for (int c = 0; c < 32; c++) { vid_io_write(0xC, (uint8_t)c); bad += vid_read(0xDFFF, mem) != 0x80 + c; }
    CHECK(bad == 0, "32 plane / page pairs, each its own byte: %d wrong", bad);
    vid_write(0xD005, 0x61, mem); CHECK(mem[0xD005] == 0x61 && vid_read(0xD005, mem) == 0x61, "text RAM in mem[]");
    vid.absent = 1; CHECK(!vid_io_owns(0xC) && vid_read(0xD805, mem) == -1, "-N: no card, no ports");

    /* the text-only build */
    fresh("v4.0", NULL, "1");
    CHECK(at(0, 0xC) == 0x78, "text-only: status %02X, want 78", at(0, 0xC));
    vid_write(0xD800, 0x12, mem);
    CHECK(vid_read(0xD800, mem) == -1 && vid2.gram[0] == 0, "text-only: the window floats, writes go nowhere");

    /* the PS/2 controller is V2.0's, on PD / PE */
    fresh("4", "ab", NULL);
    CHECK(at(0, 0xD) == 1 && at(0, 0xE) == 'a', "a key on PD / PE");
    CHECK(at(19, 0xD) == 0 && at(20, 0xD) == 1 && at(20, 0xE) == 'b', "the next after 20 us");
    vid_clk = 100; vid_io_write(0xD, 0x01); CHECK(at(100, 0xD) == 4 && at(120, 0xD) == 0, "BUSY for 20 us after a command");

    /* VSYNC / DE with the card's table (the note's section 3): 50 counts a line of 635.6 ns each, 525 lines, VSYNC from
       line 448 for 16 lines (the 6845's own pulse), DE for 40 counts on 400 lines */
    fresh("v4", NULL, NULL);
    CHECK(at(count_clk(448 * 50), 0xC) == 0x70, "no VSYNC before the 6845 is set up");
    static const uint8_t tab[10] = { 49, 40, 42, 0x26, 31, 13, 25, 28, 0, 15 };
    for (int r = 0; r < 10; r++) { vid_io_write(0xA, (uint8_t)r); vid_io_write(0xB, tab[r]); }
    unsigned long long vs = count_clk(448ULL * 50), ve = count_clk(464ULL * 50), frame = count_clk(525ULL * 50);
    CHECK((at(vs - 1, 0xC) & 2) == 0 && (at(vs, 0xC) & 2) == 2, "VSYNC rises at line 448 (clock %llu)", vs);
    CHECK((at(ve - 1, 0xC) & 2) == 2 && (at(ve, 0xC) & 2) == 0, "VSYNC falls 16 lines later (clock %llu)", ve);
    CHECK(frame == 16684, "a frame is %llu clocks, want 16684 (59.94 Hz)", frame);
    CHECK((at(vs + frame, 0xC) & 2) == 2, "VSYNC again a frame later");
    CHECK((at(0, 0xC) & 4) == 4 && (at(count_clk(40) - 1, 0xC) & 4) == 4 && (at(count_clk(40), 0xC) & 4) == 0,
          "DE for 40 counts (25.4 us)");
    CHECK((at(count_clk(50), 0xC) & 4) == 4, "DE again on the next line");
    CHECK((at(count_clk(399ULL * 50), 0xC) & 4) == 4 && (at(count_clk(400ULL * 50), 0xC) & 4) == 0, "DE on 400 lines");
    setenv("Y1_CLOCK", "3500000", 1); vid_init(); unsetenv("Y1_CLOCK");
    CHECK((at(vs * 7 / 2 - 4, 0xC) & 2) == 0 && (at(vs * 7 / 2 + 4, 0xC) & 2) == 2, "a 3.5 MHz CPU: 3.5 times the clocks");

    CHECK(vid_in(0xD800) && vid_in(0xDFFF) && !vid_in(0xE000) && !vid_in(0xCFFF), "the block $D000-$DFFF");
    vid_dump(mem);                                        /* no -V, no Y1VIDSTATE: prints nothing */
    printf("model: %d failed\n", fails);
    return fails != 0;
}
