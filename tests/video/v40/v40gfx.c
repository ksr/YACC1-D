/*
 * Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026
 */

/* v40gfx.c - a picture on the video card V4's graphics layer, drawn by a YACC1 program (2026-11-20): the whole way
   from a program to the screen. os/lib_gfx.c does the drawing; y1cc compiles this for the monitor's G3000.

   The ROM's video unit sets the card up (the 6845's table, the text screen cleared); the picture is drawn in direct
   mode with the layer hidden, then shown:
     a frame round the 640 x 400 dots, the two diagonals, and a fan of sixteen lines from the middle, one to each
     point of a rectangle 400 x 300 - every direction a line can take;
     a block of 64 x 32 dots filled line by line, then two lines through it with the inverting ink;
     three lines of text in the text layer, which the card ORs with the graphics.
   tests/video/v40/run.py draws the same scene in Python and compares the graphics RAM byte for byte. */
#include "../../../os/lib_gfx.c"

int fx[16] = { 520, 520, 520, 420, 320, 220, 120, 120, 120, 120, 120, 220, 320, 420, 520, 520 };
int fy[16] = { 200, 275, 350, 350, 350, 350, 350, 275, 200, 125,  50,  50,  50,  50,  50, 125 };

void text(int row, int col, char *s) {
    int a;
    a = 0xD000 + row * 80 + col;
    while (*s) { poke(a, *s); a++; s++; }
}

void main() {
    int i;
    bios(0xFFBC, 0, 1);
    gfx_ctl(0);
    gfx_clear();
    gfx_line(0, 0, 639, 0, GFX_SET);
    gfx_line(639, 0, 639, 399, GFX_SET);
    gfx_line(639, 399, 0, 399, GFX_SET);
    gfx_line(0, 399, 0, 0, GFX_SET);
    gfx_line(0, 0, 639, 399, GFX_SET);
    gfx_line(639, 0, 0, 399, GFX_SET);
    for (i = 0; i < 16; i++) gfx_line(320, 200, fx[i], fy[i], GFX_SET);
    for (i = 0; i < 32; i++) gfx_line(32, 336 + i, 95, 336 + i, GFX_SET);
    gfx_line(24, 332, 103, 371, GFX_INV);
    gfx_line(103, 332, 24, 371, GFX_INV);
    text(1, 2, "YACC1 video card V4");
    text(2, 2, "640 x 400 graphics, drawn by a YACC1 program");
    text(23, 14, "the text layer over the graphics layer: 80 x 25");
    gfx_show(1);
    puts("GFX DONE");
}
