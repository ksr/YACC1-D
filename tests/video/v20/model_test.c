/*
 * Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
 */

/*
 * model_test.c - software/videomodel.h's video card V2.0 on its own (2026-11-10): the parts a program on the emulators
 * cannot reach on its own - the console as the PS/2 keyboard (Y1VID_KBD=stdin, which takes the monitor's input
 * away), the controller's timing to the clock, the interrupt request - and the arithmetic of VSYNC / DE to the clock.
 * Built and run by tests/video/v20/run.py. Prints one line per failed check and "model: N failed".
 */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "../../../software/videomodel.h"

static int fails;
#define CHECK(c, ...) do { if (!(c)) { fails++; printf("FAIL %d: ", __LINE__); printf(__VA_ARGS__); printf("\n"); } } while (0)

static const char *con; static size_t conpos;           /* the fake console: its bytes, then the end of input */
static int con_ready(void) { return 1; }                 /* the emulators' poll says "ready" at the end too (reads 0) */
static int con_get(void) { return con[conpos] ? (uint8_t)con[conpos++] : 0; }

static void fresh(const char *card, const char *keys, const char *kbd, const char *dots, const char *textonly) {
    memset(&vid, 0, sizeof vid); memset(&vid2, 0, sizeof vid2); vid_clk = 0;
    if (card) setenv("Y1VID_CARD", card, 1); else unsetenv("Y1VID_CARD");
    if (keys) setenv("Y1VID_KEYS", keys, 1); else unsetenv("Y1VID_KEYS");
    if (kbd) setenv("Y1VID_KBD", kbd, 1); else unsetenv("Y1VID_KBD");
    if (dots) setenv("Y1VID_DOTS", dots, 1); else unsetenv("Y1VID_DOTS");
    if (textonly) setenv("Y1VID_TEXTONLY", textonly, 1); else unsetenv("Y1VID_TEXTONLY");
    unsetenv("Y1_CLOCK");
    vid_init();
    vid_key_ready = con_ready; vid_key_get = con_get;
}

static int at(unsigned long long clk, int port) { vid_clk = clk; return vid_io_read(port); }

int main(void) {
    static uint8_t mem[65536];

    /* the V1.0 card: none of PA-PF is the card's; $D800 is the 6845 as before */
    fresh("v1.0", NULL, NULL, NULL, NULL);
    for (int p = 0; p < 16; p++) CHECK(!vid_io_owns(p), "v1.0 owns port %X", p);
    vid_write(0xD800, 14, mem); vid_write(0xD802, 0x2A, mem); vid_write(0xD800, 14, mem);
    CHECK(vid_read(0xD802, mem) == 0x2A, "v1.0: R14 through $D802");

    /* V2.0 (the default on the branch video-v2): PA-PF, the status, the window */
    fresh(NULL, NULL, NULL, NULL, NULL);
    CHECK(vid2.card == 2, "the default card is V2.0");
    for (int p = 0; p < 16; p++) CHECK(vid_io_owns(p) == (p >= 10), "v2.0 port %X", p);
    CHECK(at(0, 0xC) == 0x50, "status %02X, want 50", at(0, 0xC));
    CHECK(at(0, 0xA) == -1 && at(0, 0xF) == -1, "PA / PF read float");
    vid_io_write(0xA, 15); vid_io_write(0xB, 0x5A); vid_io_write(0xA, 15);
    CHECK(at(0, 0xB) == 0x5A, "R15 through PA/PB");
    vid_io_write(0xA, 1); vid_io_write(0xB, 64); CHECK(at(0, 0xB) == 0, "R1 reads 0 (write-only)");
    vid_io_write(0xC, 0x0B);                              /* CPU page 1, plane 3 */
    vid_write(0xD805, 0x77, mem);
    CHECK(vid2.gram[16384 + 3 * 2048 + 5] == 0x77 && mem[0xD805] == 0, "the window: page 1 plane 3");
    vid_io_write(0xC, 0x03);
    CHECK(vid_read(0xD805, mem) == 0, "page 0 plane 3 is another byte");
    vid_write(0xD005, 0x41, mem); CHECK(mem[0xD005] == 0x41 && vid_read(0xD005, mem) == 0x41, "text RAM in mem[]");
    vid.absent = 1; CHECK(!vid_io_owns(0xC) && vid_read(0xD805, mem) == -1, "-N: no card, no ports");

    fresh("v2.0", NULL, NULL, "6", "1");
    CHECK(at(0, 0xC) == 0x59, "DOTS open, text-only: status %02X, want 59", at(0, 0xC));
    vid_write(0xD800, 0x12, mem);
    CHECK(vid_read(0xD800, mem) == -1 && vid2.gram[0] == 0, "text-only: the window floats, writes go nowhere");

    /* the keyboard queue (Y1VID_KEYS): FULL, the byte, the 20 us reload, the latch's last byte with FULL clear */
    fresh("v2.0", "a\\x41\\r\\\\", NULL, NULL, NULL);
    CHECK(at(0, 0xD) == 1, "FULL at once");
    CHECK(at(0, 0xE) == 'a', "PE = a");
    CHECK(at(19, 0xD) == 0, "FULL clear for 20 us");
    CHECK(at(10, 0xE) == 'a', "PE with FULL clear: the last byte again");
    CHECK(at(20, 0xD) == 1 && at(20, 0xE) == 'A', "\\x41");
    CHECK(at(40, 0xE) == 0x0D, "\\r");
    CHECK(at(60, 0xE) == '\\', "\\\\");
    CHECK(at(100, 0xD) == 0, "empty");

    /* commands: BUSY for 20 us, interrupts, acknowledge, flush */
    fresh("v2.0", "xyz", NULL, NULL, NULL);
    vid_clk = 1000; vid_io_write(0xD, 0x01);
    CHECK(at(1000, 0xD) == 5, "FULL + BUSY: %02X", at(1000, 0xD));
    CHECK(at(1020, 0xD) == 1, "BUSY over after 20 us");
    CHECK(vid_irq(), "INTREQ AND FULL");
    vid_io_write(0xD, 0x03); CHECK(!vid_irq(), "acknowledged");
    CHECK(at(1030, 0xE) == 'x' && !vid_irq(), "read: FULL clear");
    CHECK(at(1050, 0xD) == 1 && vid_irq(), "the next byte asks again");
    vid_io_write(0xD, 0x06); CHECK(at(1060, 0xE) == 'y' && at(1100, 0xD) == 0, "flush: the latched byte stays, z goes");
    vid_io_write(0xD, 0x15); CHECK(vid2.leds == 5, "LEDs");
    vid_io_write(0xD, 0x02); CHECK(!vid_irq(), "interrupts off");

    /* Y1VID_KBD=stdin: the console's bytes, LF back to the keyboard's CR, nothing at the end of input */
    con = "ok\n"; conpos = 0;
    fresh("v2.0", NULL, "stdin", NULL, NULL);
    CHECK(vid2.kbd_stdin, "KBD=stdin");
    CHECK(at(0, 0xE) == 'o' && at(20, 0xE) == 'k' && at(40, 0xE) == 0x0D, "o k CR");
    CHECK(at(60, 0xD) == 0 && at(80, 0xD) == 0, "end of input: no key");
    fresh("v1.0", NULL, "stdin", NULL, NULL);
    CHECK(!vid2.kbd_stdin, "KBD=stdin needs the V2.0 card");

    /* VSYNC / DE: the MDA table, 8 dots: 1.5 characters a clock, 81 a line, 370 lines; VSYNC from line 312 for 16 */
    fresh("v2.0", NULL, NULL, NULL, NULL);
    CHECK(at(16848, 0xC) == 0x50, "no VSYNC before the 6845 is set up");
    static const uint8_t mda[10] = { 80, 64, 68, 10, 45, 2, 32, 39, 0, 7 };
    for (int r = 0; r < 10; r++) { vid_io_write(0xA, r); vid_io_write(0xB, mda[r]); }
    CHECK((at(16847, 0xC) & 2) == 0 && (at(16848, 0xC) & 2) == 2, "VSYNC rises at clock 16848");
    CHECK((at(17711, 0xC) & 2) == 2 && (at(17712, 0xC) & 2) == 0, "VSYNC falls 16 lines (864 clocks) later");
    CHECK((at(16848 + 19980, 0xC) & 2) == 2 && (at(16847 + 19980, 0xC) & 2) == 0, "a frame is 19980 clocks (50.05 Hz)");
    CHECK((at(0, 0xC) & 4) == 4 && (at(42, 0xC) & 4) == 4 && (at(43, 0xC) & 4) == 0, "DE for 64 characters");
    CHECK((at(54, 0xC) & 4) == 4, "DE again on the next line (54 clocks)");
    CHECK((at(256 * 54, 0xC) & 4) == 0, "no DE below row 32");
    fresh("v2.0", NULL, NULL, "6", NULL);
    for (int r = 0; r < 10; r++) { vid_io_write(0xA, r); vid_io_write(0xB, mda[r]); }
    CHECK((at(12635, 0xC) & 2) == 0 && (at(12636, 0xC) & 2) == 2, "6 dots: 2 characters a clock, VSYNC at 12636");
    setenv("Y1_CLOCK", "2000000", 1); vid_init(); unsetenv("Y1_CLOCK");
    CHECK((at(2 * 12636 - 1, 0xC) & 2) == 0 && (at(2 * 12636, 0xC) & 2) == 2, "a 2 MHz CPU: twice the clocks");

    CHECK(vid_in(0xD800) && vid_in(0xDFFF) && !vid_in(0xE000) && !vid_in(0xCFFF), "the block $D000-$DFFF");
    vid_dump(mem);                                        /* no -V, no Y1VIDSTATE: prints nothing */
    printf("model: %d failed\n", fails);
    return fails != 0;
}
