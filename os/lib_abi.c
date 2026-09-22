/* lib_abi.c - the YACC1 ROM (monitor + BIOS) addresses a program or the OS uses, from firmware/monitor/monitor.asm
   (2026-09-22). Use with y1cc's bios(addr, r7, acc): R7 and ACC are set, the routine is JSRed, ACC comes back.
   Console: CHAROUT (ACC = byte), UARTIN (-> ACC, echoes on the machine), CONST (-> 1 when a byte waits).
   CompactFlash: set CFLBA0..2 with poke(), then CFREAD/CFWRITE with R7 = a 512-byte buffer (R7 advances); ACC = 0 ok.
   ARGBUF: 64 bytes where the OS leaves a program's command tail; argstr() returns its address. */
#define STRINGOUT 0xFFC0
#define CHAROUT   0xFFC4
#define UARTOUT   0xFFC8
#define SHOWADDR  0xFFCC
#define UARTIN    0xFFE8
#define CFINIT    0xFFEC
#define CFREAD    0xFFF0
#define CFWRITE   0xFFF4
#define CONST     0xFFF8
#define CFLBA0    0x0F10
#define CFLBA1    0x0F11
#define CFLBA2    0x0F12
#define ARGBUF    0x0F40
#define OSBASE    0x1000
#define TPA       0x5000
#define TPATOP    0xD000
