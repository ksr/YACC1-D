/* lib_abi.c - the YACC1 ROM (monitor + BIOS) addresses a program or the OS uses, from firmware/monitor/monitor.asm
   (2026-09-22), and since 2026-09-23 the Y1/OS syscall interface (numbers and RAM addresses; the C wrappers are in
   lib_fs.c). Use with y1cc's bios(addr, r7, acc): R7 and ACC are set, the routine is JSRed, ACC comes back.
   Console: CHAROUT (ACC = byte), UARTIN (-> ACC, echoes on the machine), CONST (-> 1 when a byte waits).
   A program's normal output is NOT these: y1cc --os compiles putchar/puts/getchar to the syscalls CONOUT/CONIN,
   which the shell redirects; bios(CHAROUT, 0, c) is the raw console, for diagnostics (lib_err.c eputs).
   CompactFlash: set CFLBA0..2 with poke(), then CFREAD/CFWRITE with R7 = a 512-byte buffer (R7 advances); ACC = 0 ok.
   ARGBUF: 128 bytes ($0F40..$0FBF, ARGMAX = 127 characters + NUL) where the OS leaves a program's command tail;
   argstr() returns its address.
   Syscalls: sys(SYS_x, a, b, c) evaluates a, b, c into SYSARG0..2, JSRURs the word at SYSTAB + 2*SYS_x and returns
   SYSRES, always a full 16-bit word: 1/0 for yes/no, a handle or 0, a count, a byte or 65535 for none/end of file
   (all in the monitor's free variable space $0F06..$0F0F and $0F14..$0F3F; firmware/abi/README.md). Y1/OS fills
   SYSTAB at boot with funcaddr(handler); a handler reads SYSARGn with peekw() and writes SYSRES with pokew(). */
#define STRINGOUT 0xFFC0
#define CHAROUT   0xFFC4
#define UARTOUT   0xFFC8
#define SHOWADDR  0xFFCC
#define UARTIN    0xFFE8
#define CFINIT    0xFFEC
#define CFREAD    0xFFF0
#define CFWRITE   0xFFF4
#define CONST     0xFFF8
#define UARTINNE  0xFFFC
#define SYSARG0   0x0F06
#define SYSARG1   0x0F08
#define SYSARG2   0x0F0A
#define SYSRES    0x0F0C
#define CFLBA0    0x0F10
#define CFLBA1    0x0F11
#define CFLBA2    0x0F12
#define SYSTAB    0x0F14
/* SYSTAB2 (2026-09-25): the 32-entry table, $4FC0..$4FFF in the OS's RAM. SYSTAB ($0F14..$0F3F) holds entries 0..21
   (ARGBUF follows it, so it cannot grow); the OS fills both, SYSTAB2's first 22 words the same. y1cc's sys() reads
   SYSTAB for a constant 0..21 (so every program compiled before is unchanged) and SYSTAB2 for 22..31; a computed
   number reaches 0..21 */
#define SYSTAB2   0x4FC0
/* STATUS (2026-09-25): the status of the program that ran last, 0 when main returned, else what it gave EXIT; the
   next program finds it here (a shell's $?) */
#define STATUS    0x0F0E
#define SYS_OLD   21      /* the last entry SYSTAB has */
/* The video card (2026-09-25, ROM 2026-09-25 and later; firmware/abi/README.md "Video"): the ROM probes $D000 at reset
   (VIDPRES) and, while VIDMIR is nonzero and VIDPRES 1, CHAROUT/UARTOUT also write every console byte to the screen.
   VIDCTL is the video entry below the full vector table: bios(VIDCTL, 0, n), n = 0 probe, 1 init (CRTC registers,
   clear, home), 2 clear + home; ACC = VIDPRES. An older ROM has $FF at $FFBC (VIDSIG = $04 = the JSR there) */
#define VIDCTL    0xFFBC
#define VIDSIG    4
#define VIDPRES   0x0FF0
#define VIDMIR    0x0FF1
#define VIDCUR    0x0FF2
#define VROW      0x0FF3
#define VCOL      0x0FF4
#define ARGBUF    0x0F40
/* ARGBUF holds up to ARGMAX = 127 characters + NUL ($0F40..$0FBF, since 2026-09-23; the upper half overlays the
   monitor's line buffer, which is idle while the OS runs) */
#define ARGMAX    127
#define OSBASE    0x1000
#define TPA       0x5000
#define TPATOP    0xD000

/* the syscall numbers (entry n of SYSTAB); see os/README.md for arguments and results */
#define SYS_OPEN     0    /* (path) -> handle 1..4, 0 not found / not a file / no handle free */
#define SYS_READ     1    /* (handle, buf512) -> bytes put in buf from the sector holding the position; 0 at the end */
#define SYS_GETC     2    /* (handle) -> next byte, 65535 at the end */
#define SYS_CLOSE    3    /* (handle) -> 1; a written file is registered in its directory here */
#define SYS_CREATE   4    /* (path, load, exec) -> handle, 0 cannot (a same-named file is replaced) */
#define SYS_WRITE    5    /* (handle, buf, n) -> bytes written */
#define SYS_PUTC     6    /* (handle, byte) -> 1, 0 cannot */
#define SYS_DELETE   7    /* (path) -> 1 tombstoned, 0 not a file */
#define SYS_MKDIR    8    /* (path) -> 1, 0 cannot (exists, parent missing, no slot, a write is open) */
#define SYS_RMDIR    9    /* (path) -> 1, 0 not a directory or not empty */
#define SYS_OPENDIR  10   /* (path) -> handle, 0 not a directory ("" = the current directory) */
#define SYS_READDIR  11   /* (handle, buf32) -> 1 with the next live 32-byte entry in buf, 0 at the end */
#define SYS_RESOLVE  12   /* (path, buf32 or 0) -> 1 found (entry copied to buf), 0 not found */
#define SYS_GETCWD   13   /* (buf) -> length; the current directory's path, NUL-terminated, in buf (up to 64 bytes) */
#define SYS_CHDIR    14   /* (path) -> 1, 0 not found, 2 not a directory */
#define SYS_RENAME   15   /* (oldpath, newname) -> 1, 0 cannot (the entry keeps its directory; newname is a bare name) */
#define SYS_ENTRY    16   /* (buf32) -> 1; the 32-byte entry the last OPEN/OPENDIR/RESOLVE/CREATE... found, copied */
/* 17, 18: stdin (the shell's < file or pipe, else the console); 19: stdout; 20: the keyboard; 21: which is which */
#define SYS_CONIN    17   /* () -> next stdin byte, no echo; 65535 at the end / Ctrl-D (y1cc --os: getchar) */
#define SYS_CONST    18   /* () -> 1 when a stdin byte is waiting (a file: bytes left; console: ROM CONST) */
#define SYS_CONOUT   19   /* (byte) -> nothing: to stdout, the > / >> file or pipe, else CHAROUT (--os: putchar) */
#define SYS_KEYIN    20   /* () -> a key: ALWAYS the console, no echo; 65535 at Ctrl-D (pager, vi, dump, examine) */
#define SYS_STDIO    21   /* () -> bit 0 stdin redirected, bit 1 stdout redirected (the last in SYSTAB; 22.. SYSTAB2) */
/* 22..: in SYSTAB2 only (y1cc's sys() reaches them with a constant number), 2026-09-25 */
#define SYS_EXIT     22   /* (status) -> does not return: the program ends as if main returned; STATUS = status */
#define SYS_EXEC     23   /* (path, args) -> 0 when path is not a program that loads into $5000-$CFFF (or the path
                             is over 63 characters); else does not return: the caller ends (its files closed as when
                             a program returns) and path runs with args (up to 127 characters) as its command tail */
#define SYS_SEEK     24   /* (handle, hi, lo) -> 1: a read handle's position is now hi:lo (24 bits: hi 0..255), not
                             past the length; 0 not a read handle, past the end, a card error */
#define SYS_READN    25   /* (handle, buf, n) -> the bytes put in buf: up to n, the bytes n GETCs would give, but
                             never past the end of the position's sector (so fewer than n before the end too); 0 at
                             the end, for n = 0, for anything but a read handle; mixes with GETC and SEEK */
#define SYS_LAST     25
