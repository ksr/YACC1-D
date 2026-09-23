; =====================================================================================================================
; y1os.asm - Y1/OS v0.2 (2026-09-23): the YACC1 disk operating system, hand-written in YACC1 assembly.
;
; The same OS as y1os.c (v0.1, the C version compiled by y1cc, which stays in the tree as THE SPECIFICATION and is
; still built with `make -C os OS=c`): the same shell, commands, messages, syscall numbers, arguments, results and
; side effects, the same redirection and pipes, the same RAM areas and the same bytes on the card. Every routine
; below names the C function it implements; where the C does something odd, this does it too (os/README.md lists
; those behaviours, BACKLOG.md the ones worth changing). The console transcripts of tests/os are the contract.
;
; Loaded from the CompactFlash card (LBA 1.., OSCNT sectors) to $1000 by the monitor's O command, which JSRURs
; $1000; `exit` RETs to the monitor. Console and sectors come from the ROM's BIOS vectors ($FFC0..).
;
; Build: os/Makefile (make -C os): os/mkstrings.py turns os/strings.txt into build/asm/y1os_str.inc (the messages as
; numeric DB bytes: the assembler upper-cases its source), then software/assembler/asm assembles this file there.
;
; ---- conventions -----------------------------------------------------------------------------------------------
; Registers: R0 = PC, R1 = SP. R2 is NEVER used: on the machine LDA/STA/LDT/STT/LDR/STR load the operand address into
;   R2 (the interpreter hides it in a ninth register). R3 = the main value / result (16 bits), R4, R5 = operands and
;   pointers, R6, R7 = scratch (the ROM's CFREAD/CFWRITE clobber them). ACC, TMP: byte work and compares.
; Results: a routine that returns a number leaves it in R3 (16 bits, the syscall's SYSRES) and, for a yes/no or a
;   handle, the same in ACC so that the caller can BRZ/BRNZ at once. ret0/ret1/reta/retr3 are the shared exits.
; 16-bit arithmetic: an add is ADDT/ADDI then ADDTC/ADDIC with nothing but register moves between them (the carry
;   flip-flop is clocked by every ADD, SUB and SHIFT on the machine, but only by adds and CSHL/CSHR on the
;   interpreter); nothing here tests the carry after a shift or a subtract, and nothing uses BRC. Compares: high
;   bytes first (BRLT/BRGT/BREQ/BRNEQ compare ACC with TMP, unsigned), then low bytes.
; Never used (no microcode or broken on the machine): LDTVR, STTVR, OUTVR, BR16Z, BR16NZ, BRNC.
; Words in RAM are big-endian (LDR/STR order); directory entries on the card are little-endian and handled bytewise.
; Every variable is static (one fixed address), like y1cc's frames: nothing here recurses and nothing re-enters.
; THE STATIC-FRAME RULE, assembly edition: the console syscalls (CONOUT, CONIN, CONST, KEYIN) and everything they
;   reach (cout, fs_putc, fs_getc, hrec, hbuf, zero512, cfrd, cfwr, key_in) use registers and their own variables
;   only and never print: the shell calls cout from the middle of anything, and a program's CONOUT may arrive while
;   the shell sits in run_prog. Their errors are return codes (a byte that cannot be written is dropped).
;
; RAM (os/README.md "Memory"): the code from $1000 up; $4A00-$4FFF the OS's variables (cleared at boot), with
;   SBUF 512-aligned and HTAB page-aligned so that an entry's offset and a handle's record fall out of the address.
;   $0400-$0BFF the four handles' sector buffers (hbuf), SYSARG/SYSRES/CFLBA/SYSTAB/ARGBUF in the $0F page.
; =====================================================================================================================

; ---- the ROM's BIOS vectors (firmware/monitor/monitor.asm, org $FFC0: JSR routine / RET each) -----------------
B_CHAROUT:  EQU 0FFC4H          ; ACC -> the console (preserves every register, ACC and TMP)
B_UARTIN:   EQU 0FFE8H          ; -> ACC: a console byte, echoed; CR becomes LF
B_CFREAD:   EQU 0FFF0H          ; CFLBA0..2 = sector, R7 = buffer: 512 bytes in, R7 += 512, ACC = 0 ok (R6 clobbered)
B_CFWRITE:  EQU 0FFF4H          ; the same, out
B_CONST:    EQU 0FFF8H          ; -> ACC = 1 when a console byte waits
B_UARTINNE: EQU 0FFFCH          ; -> ACC: a console byte without echo

; ---- the $0F page (firmware/abi/README.md, os/lib_abi.c) --------------------------------------------------------
SYSARG0:    EQU 0F06H           ; the syscall arguments and result (big-endian words; y1cc's sys())
SYSARG1:    EQU 0F08H
SYSARG2:    EQU 0F0AH
SYSRES:     EQU 0F0CH
CFLBA0:     EQU 0F10H           ; the sector number for CFREAD/CFWRITE, low byte first (24 bits)
CFLBA1:     EQU 0F11H
CFLBA2:     EQU 0F12H
SYSTAB:     EQU 0F14H           ; the syscall jump table, 22 big-endian word entries (os/README.md)
ARGBUF:     EQU 0F40H           ; a program's command tail, 127 characters + NUL

; ---- P8XFS v2 and the handle records -------------------------------------------------------------------------------
ROOT_LBA:   EQU 33              ; the root directory's extent: LBA 33..36
ROOT_SECS:  EQU 4
F_FILE:     EQU 1               ; entry flags (byte 24): 0 = the end of the directory, 255 = deleted
F_DIR:      EQU 2
M_READ:     EQU 1               ; handle modes (0 = free)
M_WRITE:    EQU 2
M_DIR:      EQU 3
H_POS:      EQU 1               ; a handle's record (16 bytes at HTAB + 16h): +0 mode, then big-endian words:
H_LEN:      EQU 3               ;   position, length (a directory: its extent's bytes), the sector held in the
H_CUR:      EQU 5               ;   buffer (65535 none), the start LBA. Because HTAB is page-aligned and the
H_LBA:      EQU 7               ;   records 16-aligned, `MVRLA R4 / ANDI 0F0H / ORI H_x / MVARL R4` reaches field x
SI_EMPTY:   EQU 255             ; si_h of a pipe stage after one that wrote its own > file: empty input

        ORG 1000H

; =====================================================================================================================
; main (y1os.c main): the boot, then the shell's loop. Entered by the monitor's JSRUR; returns to it on `exit`.
; =====================================================================================================================
os_start:
        MVIW R3,4A00H           ; clear the OS's RAM, $4A00-$4FFF (as y1cc's main clears its BSS): every handle
os_clr: LDAI 0                  ; free, no write open, no redirection, the e_* entry all zero
        STAVR R3
        INCR R3
        MVRHA R3
        LDTI 50H
        BRNEQ os_clr
        MVIW R3,ROOT_LBA        ; the current directory is the root, "/"
        STR R3,CWD_LBA
        MVIW R3,ROOT_SECS
        STR R3,CWD_SECS
        LDAI 47
        STA CWDPATH
        MVIW R3,systab_init     ; install(): SYSTAB <- the 22 handler addresses
        MVIW R4,SYSTAB
        MVIB R5,44
os_ins: LDAVR R3
        STAVR R4
        INCR R3
        INCR R4
        DECR R5
        MVRLA R5
        BRNZ os_ins
        JSR read_free           ; the volume's free pointer
        BRZ os_up
        MVIW R3,S_CFERR
        BR puts                 ; (puts RETs to the monitor)
os_up:  MVIW R3,S_BANNER
        JSR puts
ml_top: MVIW R3,CWDPATH         ; the prompt: the current path and "> "
        JSR putstr
        MVIW R3,S_PROMPT
        JSR putstr
        JSR readline
        JSR crlf
        JSR split               ; ACC = the number of commands, 0 = a bad line
        STA NSEG
        BRZ ml_syn
        LDTI 1
        BREQ ml_go              ; one command (an empty one is fine: `> F` makes F empty)
        MVIW R4,SEG             ; a pipeline: every command must be there
        MVARL R5
ml_ck:  LDAVR R4
        MVARH R6
        INCR R4
        LDAVR R4
        MVARL R6
        INCR R4
        LDAVR R6
        BRZ ml_syn
        DECR R5
        MVRLA R5
        BRNZ ml_ck
        BR ml_go
ml_syn: MVIW R3,S_SYNTAX
        JSR eputs
        BR ml_top
ml_go:  LDAI 0
        STA KSEG
        STA QUIT
ml_st:  JSR stage               ; stage k's < and > files, or its pipe files
        BRZ ml_bad
        LDA KSEG                ; quit = run_cmd(seg[k])
        SHL
        ADDI (SEG).0
        MVARL R4
        LDAI (SEG).1
        MVARH R4
        LDAVR R4
        MVARH R3
        INCR R4
        LDAVR R4
        MVARL R3
        JSR run_cmd
        STA QUIT
        JSR io_reset            ; files closed (a written one registered), the console back
        LDA QUIT
        BRNZ ml_end
        LDA KSEG
        ADDI 1
        STA KSEG
        MVAT
        LDA NSEG
        BRGT ml_st              ; k < n: the next command
        BR ml_end
ml_bad: JSR io_reset            ; a stage could not open its files (it said so): the rest is dropped
ml_end: LDA NSEG
        LDTI 1
        BREQ ml_nq
        MVIW R3,S_PIPE0         ; after a pipeline: its temp files go
        JSR fs_delete
        MVIW R3,S_PIPE1
        JSR fs_delete
ml_nq:  LDA QUIT
        BRZ ml_top
        MVIW R3,S_BYE
        BR puts                 ; "bye", and back to the monitor

; the shared exits: R3 (and ACC) = 0 / 1 / ACC / R3 (ACC = 0 exactly when R3 is 0)
ret0:   MVIW R3,0
        LDAI 0
        RET
ret1:   MVIW R3,1
        LDAI 1
        RET
reta:   MVARL R3
        LDAI 0
        MVARH R3
        MVRLA R3
        RET
retr3:  MVRLA R3
        MVAT
        MVRHA R3
        ORT
rts:    RET

; =====================================================================================================================
; The syscall handlers (y1os.c h_*): SYSARG0..2 in, SYSRES out. A program reaches them with y1cc's sys(): the
; arguments stored, JSRUR through SYSTAB, SYSRES read. The compiled caller keeps nothing in a register across the
; call, so a handler may clobber R3-R7, ACC and TMP (y1cc's --os rt_putc/rt_getc save their R3/R4 themselves).
; =====================================================================================================================
systab_init:                    ; SYSTAB's contents, copied at boot (lib_abi.c SYS_OPEN = 0 ... SYS_STDIO = 21)
        DW h_open
        DW h_read
        DW h_getc
        DW h_close
        DW h_create
        DW h_write
        DW h_putc
        DW h_delete
        DW h_mkdir
        DW h_rmdir
        DW h_opendir
        DW h_readdir
        DW h_resolve
        DW h_getcwd
        DW h_chdir
        DW h_rename
        DW h_entry
        DW h_conin
        DW h_const
        DW h_conout
        DW h_keyin
        DW h_stdio

h_open:     LDR R3,SYSARG0
            JSR fs_open
            BR retres
h_read:     LDR R3,SYSARG0
            LDR R5,SYSARG1
            JSR fs_read
            BR retres
h_getc:     LDR R3,SYSARG0
            JSR fs_getc
            BR retres
h_close:    LDR R3,SYSARG0
            JSR fs_close
            BR retres
h_create:   LDR R3,SYSARG1
            STR R3,CR_LOAD
            LDR R3,SYSARG2
            STR R3,CR_EXEC
            LDR R3,SYSARG0
            JSR fs_create
            BR retres
h_write:    LDR R3,SYSARG2
            STR R3,FW_N
            LDR R3,SYSARG0
            LDR R5,SYSARG1
            JSR fs_write
            BR retres
h_putc:     LDR R3,SYSARG0
            LDA SYSARG1+1           ; the byte: the low half of the big-endian word
            JSR fs_putc
            BR retres
h_delete:   LDR R3,SYSARG0
            JSR fs_delete
            BR retres
h_mkdir:    LDR R3,SYSARG0
            JSR fs_mkdir
            BR retres
h_rmdir:    LDR R3,SYSARG0
            JSR fs_rmdir
            BR retres
h_opendir:  LDR R3,SYSARG0
            JSR fs_opendir
            BR retres
h_readdir:  LDR R3,SYSARG0
            LDR R5,SYSARG1
            JSR fs_readdir
            BR retres
h_resolve:  LDR R3,SYSARG0
            LDR R5,SYSARG1
            JSR fs_resolve
            BR retres
h_getcwd:   LDR R4,SYSARG0          ; fs_getcwd: strcpy(buf, cwdpath); return strlen(buf)
            MVIW R3,CWDPATH
            JSR strcpy
            LDR R3,SYSARG0
            JSR strlen
            MOVRR R4,R3
            BR retres
h_chdir:    LDR R3,SYSARG0
            JSR fs_chdir
            BR retres
h_rename:   LDR R3,SYSARG0
            LDR R5,SYSARG1
            JSR fs_rename
            BR retres
h_entry:    MVIW R4,ERAW            ; fs_entry: the entry the last lookup found -> buf; 1
            LDR R5,SYSARG0
            JSR cpy32
            MVIW R3,1
            BR retres
h_conin:    LDA SI_H                ; con_in: the < file / pipe (65535 at its end), else the keyboard
            BRZ h_keyin
            MVARL R3
            LDAI 0
            MVARH R3
            JSR fs_getc
            BR retres
h_keyin:    JSR key_in              ; key_in: always the keyboard
            BR retres
h_const:    LDA SI_H                ; con_st: a < file / pipe never blocks (1), else the ROM's CONST
            BRNZ hct_1
            JSR B_CONST
            BR hct_a
hct_1:      LDAI 1
hct_a:      MVARL R3
            LDAI 0
            MVARH R3
            BR retres
h_stdio:    MVIW R3,0               ; bit 0: stdin redirected, bit 1: stdout redirected
            LDA SI_H
            BRZ hst_o
            INCR R3
hst_o:      LDA SO_H
            BRZ retres
            INCR R3
            INCR R3
retres:     STR R3,SYSRES
            RET
; h_conout (con_out): the byte to the > / >> / pipe file, else the raw console. SYSRES is left untouched.
h_conout:   LDA SYSARG0+1
            MVAT
            LDA SO_H
            BRNZ hco_f
            MVTA
            BR B_CHAROUT
hco_f:      MVARL R3
            LDAI 0
            MVARH R3
            MVTA
            BR fs_putc              ; (its result is dropped, as in C)

; key_in: a console byte without echo -> R3; 65535 on Ctrl-D (4) and on NUL (the emulators' end of input).
; Clobbers ACC, TMP.
key_in:     JSR B_UARTINNE
            BRZ ki_end
            LDTI 4
            BREQ ki_end
            MVARL R3
            LDAI 0
            MVARH R3
            RET
ki_end:     MVIW R3,0FFFFH
            RET

; =====================================================================================================================
; Console output for the shell (y1cc's putchar/puts/putstr/putnum/puthex under --os, and y1os.c eputs/crlf)
; =====================================================================================================================
; cout: the byte in ACC to stdout: the shell's > / >> / pipe file (SO_H), else the raw console. What CONOUT is for a
; program. Preserves R3, R4, R5; clobbers R6, R7, ACC, TMP.
cout:   MVAT
        LDA SO_H
        BRNZ cout_f
        MVTA
        BR B_CHAROUT
cout_f: PUSHR R3
        PUSHR R4
        PUSHR R5
        MVARL R3
        LDAI 0
        MVARH R3
        MVTA
        JSR fs_putc
        POPR R5
        POPR R4
        POPR R3
        RET

; putstr: the NUL-terminated string at R3 to stdout (R3 ends on the NUL). puts: the same and a newline. crlf: "\n".
putstr: LDAVR R3
        BRZ rts
        JSR cout
        INCR R3
        BR putstr
puts:   JSR putstr
crlf:   LDAI 10
        BR cout

; eputs: the string at R3 and a newline on the RAW console, whatever stdout is (the shell's diagnostics).
eputs:  LDAVR R3
        BRZ ep_nl
        JSR B_CHAROUT
        INCR R3
        BR eputs
ep_nl:  LDAI 10
        BR B_CHAROUT

; putnum: R3 as an unsigned decimal to stdout ("0" for 0). Clobbers R3-R7, ACC, TMP.
putnum: LDAI 0
        STA PN_LEAD             ; no digit printed yet
        MVIW R4,pn_tab
pn_dig: LDAVR R4                ; R5 = the power of ten, R6 = its negation (0 = the end of the table)
        MVARH R5
        INCR R4
        LDAVR R4
        MVARL R5
        INCR R4
        MVRHA R5
        MVAT
        MVRLA R5
        ORT
        BRZ pn_one
        LDAVR R4
        MVARH R6
        INCR R4
        LDAVR R4
        MVARL R6
        INCR R4
        MVIB R7,0               ; the digit
pn_sub: MVRHA R5                ; while R3 >= R5: R3 -= R5 (+= its negation), digit++
        MVAT
        MVRHA R3
        BRLT pn_out
        BRNEQ pn_do
        MVRLA R5
        MVAT
        MVRLA R3
        BRLT pn_out
pn_do:  MVRLA R6
        MVAT
        MVRLA R3
        ADDT
        MVARL R3
        MVRHA R6
        MVAT
        MVRHA R3
        ADDTC
        MVARH R3
        INCR R7
        BR pn_sub
pn_out: MVRLA R7
        BRNZ pn_put
        LDA PN_LEAD
        BRZ pn_dig              ; a leading zero
        LDAI 0
pn_put: ADDI 48
        JSR cout
        LDAI 1
        STA PN_LEAD
        BR pn_dig
pn_one: MVRLA R3                ; the units, always
        ADDI 48
        BR cout
pn_tab: DW 10000
        DW 55536                ; 65536 - 10000
        DW 1000
        DW 64536
        DW 100
        DW 65436
        DW 10
        DW 65526
        DW 0

; puthex: R3 as four hex digits (upper case) to stdout. Clobbers R6, R7, ACC, TMP.
puthex: MVRHA R3
        JSR phex2
        MVRLA R3
phex2:  PUSH
        SHR
        SHR
        SHR
        SHR
        JSR phex1
        POP
        ANDI 15
phex1:  LDTI 9
        BRGT ph_af
        ADDI 48
        BR cout
ph_af:  ADDI 55
        BR cout

; =====================================================================================================================
; Strings (y1lib.c strlen/strcpy/strcmp, y1os.c upper/lower/word/hexnum)
; =====================================================================================================================
; strlen: R3 = a string -> R4 = its length, R5 -> its NUL; R3 kept. Clobbers ACC.
strlen: MOVRR R3,R5
        MVIW R4,0
sl_lp:  LDAVR R5
        BRZ rts
        INCR R5
        INCR R4
        BR sl_lp

; strcpy: the string at R3 (with its NUL) -> R4. Clobbers R3, R4, ACC.
strcpy: LDAVR R3
        STAVR R4
        INCR R3
        INCR R4
        BRNZ strcpy
        RET

; streq: the strings at R3 and R4 -> ACC = 1 equal, 0 not. Clobbers R3, R4, TMP.
streq:  LDAVR R4
        MVAT
        LDAVR R3
        BRNEQ se_no
        INCR R3
        INCR R4
        BRNZ streq
        LDAI 1
        RET
se_no:  LDAI 0
        RET

; upper / lower: the string at R3 in place, a-z -> A-Z / A-Z -> a-z. Clobbers R3, ACC, TMP.
upper:  LDAVR R3
        BRZ rts
        LDTI 97
        BRLT up_nx
        LDTI 122
        BRGT up_nx
        SUBI 32
        STAVR R3
up_nx:  INCR R3
        BR upper
lower:  LDAVR R3
        BRZ rts
        LDTI 65
        BRLT lo_nx
        LDTI 90
        BRGT lo_nx
        ADDI 32
        STAVR R3
lo_nx:  INCR R3
        BR lower

; word: NUL-terminate the word at R3 -> R3 = what follows it (the spaces skipped). Clobbers ACC, TMP.
word:   LDAVR R3
        BRZ wd_sp
        LDTI 32
        BREQ wd_cut
        INCR R3
        BR word
wd_cut: LDAI 0
        STAVR R3
        INCR R3
wd_sp:  LDAVR R3
        LDTI 32
        BRNEQ rts
        INCR R3
        BR wd_sp

; hexnum: the hex digits at R3 -> R4 (stops at the first other character; 0-9 A-F a-f). Clobbers R3, ACC, TMP.
hexnum: MVIW R4,0
hx_lp:  LDAVR R3
        INCR R3
        LDTI 48
        BRLT rts
        LDTI 57
        BRGT hx_a
        SUBI 48
        BR hx_add
hx_a:   LDTI 65
        BRLT rts
        LDTI 70
        BRGT hx_l
        SUBI 55
        BR hx_add
hx_l:   LDTI 97
        BRLT rts
        LDTI 102
        BRGT rts
        SUBI 87
hx_add: PUSH                    ; v = (v << 4) | digit
        MVRLA R4
        SHR
        SHR
        SHR
        SHR
        MVAT
        MVRHA R4
        SHL
        SHL
        SHL
        SHL
        ORT
        MVARH R4
        MVRLA R4
        SHL
        SHL
        SHL
        SHL
        MVARL R4
        POP
        MVAT
        MVRLA R4
        ORT
        MVARL R4
        BR hx_lp

; cpy32: 32 bytes from R4 to R5 (a directory entry). Clobbers R4, R5, R7, ACC.
cpy32:  MVIB R7,32
c32_lp: LDAVR R4
        STAVR R5
        INCR R4
        INCR R5
        DECR R7
        MVRLA R7
        BRNZ c32_lp
        RET

; add34: R3 += R4 (16 bits). Clobbers ACC, TMP.
add34:  MVRLA R4
        MVAT
        MVRLA R3
        ADDT
        MVARL R3
        MVRHA R4
        MVAT
        MVRHA R3
        ADDTC
        MVARH R3
        RET

; zero512: 512 zero bytes from R5, a 512-aligned buffer (R5 ends 512 higher). Clobbers R5, ACC.
zero512: LDIVR R5,0
        INCR R5
        MVRLA R5
        BRNZ zero512
        MVRHA R5
        ANDI 1
        BRNZ zero512
        RET

; =====================================================================================================================
; Sectors (y1os.c cfread/cfwrite): R6 = the LBA (CFLBA2 = 0: 16-bit sectors), R7 = the 512-byte buffer.
; ACC = 0 ok (so BRNZ = a card error). Clobbers R6, R7 (+512), ACC; the ROM routine also loads R2 (LDA), never ours.
; =====================================================================================================================
cfrd:   MVRLA R6
        STA CFLBA0
        MVRHA R6
        STA CFLBA1
        LDAI 0
        STA CFLBA2
        BR B_CFREAD
cfwr:   MVRLA R6
        STA CFLBA0
        MVRHA R6
        STA CFLBA1
        LDAI 0
        STA CFLBA2
        BR B_CFWRITE

; read_free: FREE_LBA <- the boot block's free pointer (bytes 4-5, LE) -> ACC = 0 ok, else a card error. At boot and
; after every program (run_prog): a program may move it (/BIN/PACK).
read_free:
        MVIW R6,0
        MVIW R7,SBUF
        JSR cfrd
        BRNZ rts
        LDA SBUF+4
        MVARL R3
        LDA SBUF+5
        MVARH R3
        STR R3,FREE_LBA
        LDAI 0
        RET

; write_free: the boot block's free pointer <- FREE_LBA (read, patch, write).
write_free:
        MVIW R6,0
        MVIW R7,SBUF
        JSR cfrd
        BRNZ rts
        LDR R3,FREE_LBA
        MVRLA R3
        STA SBUF+4
        MVRHA R3
        STA SBUF+5
        MVIW R6,0
        MVIW R7,SBUF
        BR cfwr

; =====================================================================================================================
; Directory entries (y1os.c take_entry, put_name, set_entry, name_is, find_in, find_slot, resolve, parent_of,
; tombstone). An entry is 32 bytes: name[12] (space-padded) start[4] length[4] load[2] exec[2] flags, little-endian.
; =====================================================================================================================
; take_entry: R3 -> an entry in SBUF: ERAW <- it; E_LBA, E_LEN, E_LOAD, E_EXEC, E_OFF (its offset in SBUF) and
; E_SECS = ceil(length / 512), 1 at least, counting the 64K multiples of byte 18. (E_SLBA is the caller's.)
; Clobbers R4, R5, R7, ACC, TMP.
take_entry:
        MOVRR R3,R4
        MVIW R5,ERAW
        JSR cpy32
        MVRHA R3                ; e_off = R3 - SBUF (SBUF is 512-aligned)
        ANDI 1
        MVARH R4
        MVRLA R3
        MVARL R4
        STR R4,E_OFF
        LDA ERAW+12
        MVARL R4
        LDA ERAW+13
        MVARH R4
        STR R4,E_LBA
        LDA ERAW+20
        MVARL R4
        LDA ERAW+21
        MVARH R4
        STR R4,E_LOAD
        LDA ERAW+22
        MVARL R4
        LDA ERAW+23
        MVARH R4
        STR R4,E_EXEC
        LDA ERAW+16
        MVARL R4
        LDA ERAW+17
        MVARH R4
        STR R4,E_LEN
        LDA ERAW+18             ; e_secs = (len >> 9) + lenhi * 128 (16 bits), + 1 when len & 511, 1 if 0
        SHR
        MVARH R5                ;   high byte: lenhi >> 1
        LDA ERAW+18
        ANDI 1
        BRZ te_a
        LDAI 80H
te_a:   MVAT
        MVRHA R4
        SHR
        ORT
        MVARL R5                ;   low byte: (len.hi >> 1) | (lenhi & 1) << 7
        MVRLA R4
        BRNZ te_inc
        MVRHA R4
        ANDI 1
        BRZ te_z
te_inc: INCR R5
te_z:   MVRLA R5
        BRNZ te_st
        MVRHA R5
        BRNZ te_st
        INCR R5
te_st:  STR R5,E_SECS
        RET

; put_name: the 12-byte name field at R3 <- the NUL-terminated name at R5, space-padded. Clobbers R3, R5, R6, ACC.
put_name:
        MVIB R6,12
pnm_lp: LDAVR R5
        BRNZ pnm_ch
        LDAI 32
        BR pnm_st
pnm_ch: INCR R5
pnm_st: STAVR R3
        INCR R3
        DECR R6
        MVRLA R6
        BRNZ pnm_lp
        RET

; set_entry: the entry at R3 <- name R5, start SE_LBA, length SE_LEN, load SE_LOAD, exec SE_EXEC, flags SE_FLAG;
; every other byte 0. Clobbers R3-R6, ACC.
set_entry:
        JSR put_name            ; R3 -> byte 12
        LDR R4,SE_LBA
        JSR st_le               ; 12, 13
        MVIW R4,0
        JSR st_le               ; 14, 15
        LDR R4,SE_LEN
        JSR st_le               ; 16, 17
        MVIW R4,0
        JSR st_le               ; 18, 19
        LDR R4,SE_LOAD
        JSR st_le               ; 20, 21
        LDR R4,SE_EXEC
        JSR st_le               ; 22, 23
        LDA SE_FLAG
        STAVR R3                ; 24
        MVIB R6,7
se_z:   INCR R3                 ; 25..31
        LDIVR R3,0
        DECR R6
        MVRLA R6
        BRNZ se_z
        RET
st_le:  MVRLA R4                ; R4 little-endian at R3, R3 += 2
        STAVR R3
        INCR R3
        MVRHA R4
        STAVR R3
        INCR R3
        RET

; nm_set: R4 = a name's length n -> NM_N = min(n, 12) characters to compare, NM_SP = 12 - NM_N spaces after them
; (name_is's `i < n` for every i < 12, with n a 16-bit count). Clobbers ACC, TMP.
nm_set: MVRHA R4
        BRNZ nms_12
        MVRLA R4
        LDTI 12
        BRLT nms_st
nms_12: LDAI 12
nms_st: STA NM_N
        MVAT
        LDAI 12
        SUBT
        STA NM_SP
        RET

; name_is: does the entry at R3 carry the name at R5 (NM_N characters, then NM_SP spaces)? -> ACC = 1 / 0.
; R3, R5 kept. Clobbers R4, R6, R7, TMP.
name_is:
        MOVRR R3,R6
        MOVRR R5,R7
        LDA NM_N
        MVARL R4
ni_c:   MVRLA R4
        BRZ ni_s
        LDAVR R7
        MVAT
        LDAVR R6
        BRNEQ ni_no
        INCR R6
        INCR R7
        DECR R4
        BR ni_c
ni_s:   LDA NM_SP
        MVARL R4
ni_sl:  MVRLA R4
        BRZ ni_yes
        LDAVR R6
        LDTI 32
        BRNEQ ni_no
        INCR R6
        DECR R4
        BR ni_sl
ni_yes: LDAI 1
        RET
ni_no:  LDAI 0
        RET

; find_in: look for the name at R5 (R4 characters) in the directory extent R3 (FI_SECS sectors) -> ACC = R3 = 1
; found (take_entry: E_*, ERAW; E_SLBA = its sector, which is in SBUF), 0 not found (the $00 end mark or the end of
; the extent; a card error prints "CF read error"). Deleted ($FF) entries are skipped. Clobbers R3-R7.
find_in:
        STR R3,FI_LBA           ; the sector being scanned
        STR R5,FI_NM
        JSR nm_set
        LDR R3,FI_SECS
        STR R3,FI_LEFT
fi_sec: LDR R3,FI_LEFT
        MVRLA R3
        BRNZ fi_rd
        MVRHA R3
        BRZ ret0
fi_rd:  DECR R3
        STR R3,FI_LEFT
        LDR R6,FI_LBA
        MVIW R7,SBUF
        JSR cfrd
        BRNZ fi_err
        MVIW R3,SBUF            ; R3 -> the entry
fi_ent: MVRLA R3                ; its flags (the offset + 24 stays inside the page)
        ADDI 24
        MVARL R4
        MVRHA R3
        MVARH R4
        LDAVR R4
        BRZ ret0
        LDTI 255
        BREQ fi_nx
        LDR R5,FI_NM
        JSR name_is
        BRNZ fi_hit
fi_nx:  MVRLA R3
        ADDI 32
        MVARL R3
        MVRHA R3
        ADDIC 0
        MVARH R3
        LDTI (SBUF+512).1
        BRNEQ fi_ent
        LDR R3,FI_LBA
        INCR R3
        STR R3,FI_LBA
        BR fi_sec
fi_hit: LDR R4,FI_LBA
        STR R4,E_SLBA
        JSR take_entry
        BR ret1
fi_err: MVIW R3,S_CFERR
        JSR eputs
        BR ret0

; find_slot: the first free slot ($00 end mark or $FF tombstone) of the extent R3 (FI_SECS sectors) -> ACC = R3 = 1
; with E_SLBA/E_OFF (its sector in SBUF), 0 when the directory is full or on a card error. Clobbers R3-R7.
find_slot:
        STR R3,FI_LBA
        LDR R3,FI_SECS
        STR R3,FI_LEFT
fsl_sc: LDR R3,FI_LEFT
        MVRLA R3
        BRNZ fsl_rd
        MVRHA R3
        BRZ ret0
fsl_rd: DECR R3
        STR R3,FI_LEFT
        LDR R6,FI_LBA
        MVIW R7,SBUF
        JSR cfrd
        BRNZ ret0
        MVIW R3,SBUF+24         ; R3 -> the flags of the entry
fsl_e:  LDAVR R3
        BRZ fsl_hit
        LDTI 255
        BREQ fsl_hit
        MVRLA R3
        ADDI 32
        MVARL R3
        MVRHA R3
        ADDIC 0
        MVARH R3
        LDTI (SBUF+512).1
        BRNEQ fsl_e
        LDR R3,FI_LBA
        INCR R3
        STR R3,FI_LBA
        BR fsl_sc
fsl_hit: LDR R4,FI_LBA
        STR R4,E_SLBA
        MVRLA R3                ; e_off = R3 - 24 - SBUF
        SUBI 24
        MVARL R4
        MVRHA R3
        ANDI 1
        MVARH R4
        STR R4,E_OFF
        BR ret1

; resolve: walk the path at R3 -> ACC = R3 = 1 found (the final entry in E_*/ERAW, its directory in RLBA/RSECS), 0.
; Absolute /A/B or relative; "" and "/" are the current / root directory themselves (a made-up '.' entry, no slot:
; E_SLBA = 0); a trailing slash ends the walk (on a file too); a component over 12 characters is not found.
; Clobbers R3-R7.
resolve:
        LDAVR R3
        LDTI 47
        BRNEQ rs_rel
        INCR R3
        MVIW R4,ROOT_LBA
        STR R4,RLBA
        MVIW R4,ROOT_SECS
        STR R4,RSECS
        BR rs_go
rs_rel: LDR R4,CWD_LBA
        STR R4,RLBA
        LDR R4,CWD_SECS
        STR R4,RSECS
rs_go:  LDAVR R3
        BRNZ rs_wk
        LDR R4,RLBA             ; the directory itself
        STR R4,E_LBA
        LDR R5,RSECS
        STR R5,E_SECS
        MVRLA R5                ; e_len = rsecs * 512 (16 bits)
        SHL
        MVARH R6
        LDAI 0
        MVARL R6
        STR R6,E_LEN
        MVIW R6,0
        STR R6,E_LOAD
        STR R6,E_EXEC
        STR R6,E_SLBA
        STR R6,E_OFF
        MVIW R3,ERAW            ; e_raw: ".", 11 spaces, 20 zeros; start, length, F_DIR
        LDIVR R3,46
        INCR R3
        MVIB R6,11
rs_sp:  LDIVR R3,32
        INCR R3
        DECR R6
        MVRLA R6
        BRNZ rs_sp
        MVIB R6,20
rs_z:   LDIVR R3,0
        INCR R3
        DECR R6
        MVRLA R6
        BRNZ rs_z
        MVRLA R4
        STA ERAW+12
        MVRHA R4
        STA ERAW+13
        MVRLA R5
        SHL
        STA ERAW+17
        LDAI F_DIR
        STA ERAW+24
        BR ret1
rs_wk:  MOVRR R3,R4             ; n = the component's length (up to '/' or the end)
        MVIW R5,0
rs_ln:  LDAVR R4
        BRZ rs_l2
        LDTI 47
        BREQ rs_l2
        INCR R4
        INCR R5
        BR rs_ln
rs_l2:  MVRHA R5
        BRNZ ret0
        MVRLA R5
        LDTI 12
        BRGT ret0
        STR R4,RS_P             ; p += n
        LDR R4,RSECS
        STR R4,FI_SECS
        MOVRR R5,R4
        MOVRR R3,R5
        LDR R3,RLBA
        JSR find_in
        BRZ ret0
        LDR R3,RS_P
        LDAVR R3
        BRZ ret1                ; the end of the path
        INCR R3                 ; a '/'
        LDAVR R3
        BRZ ret1                ; a trailing slash
        LDA ERAW+24
        LDTI F_DIR
        BRNEQ ret0
        LDR R4,E_LBA
        STR R4,RLBA
        LDR R4,E_SECS
        STR R4,RSECS
        BR rs_wk

; parent_of: the path at R3 -> ACC = 1 with P_LBA/P_SECS = the directory that holds its last component and LEAF ->
; that component (inside PBUF, a copy), 1..12 characters and not . or ..; 0 otherwise (a path of 0 or over 62
; characters, a parent that is missing or not a directory). Clobbers R3-R7.
parent_of:
        JSR strlen
        MVRHA R4
        BRNZ ret0
        MVRLA R4
        BRZ ret0
        LDTI 62
        BRGT ret0
        MVIW R4,PBUF
        JSR strcpy
        MVIW R3,PBUF            ; R5 -> the last '/', 0 none
        MVIW R5,0
po_sc:  LDAVR R3
        BRZ po_sd
        LDTI 47
        BRNEQ po_sn
        MOVRR R3,R5
po_sn:  INCR R3
        BR po_sc
po_sd:  MVRHA R5
        BRNZ po_has
        MVIW R3,PBUF            ; no '/': the leaf is the whole path, in the current directory
        STR R3,LEAF
        LDR R4,CWD_LBA
        STR R4,P_LBA
        LDR R4,CWD_SECS
        STR R4,P_SECS
        BR po_lf
po_has: MOVRR R5,R3
        INCR R3
        STR R3,LEAF
        MVRLA R5
        LDTI (PBUF).0
        BRNEQ po_sub
        MVRHA R5
        LDTI (PBUF).1
        BRNEQ po_sub
        MVIW R4,ROOT_LBA        ; "/leaf": the root
        STR R4,P_LBA
        MVIW R4,ROOT_SECS
        STR R4,P_SECS
        BR po_lf
po_sub: LDAI 0                  ; "a/b/leaf": resolve "a/b"
        STAVR R5
        MVIW R3,PBUF
        JSR resolve
        BRZ ret0
        LDA ERAW+24
        LDTI F_DIR
        BRNEQ ret0
        LDR R4,E_LBA
        STR R4,P_LBA
        LDR R4,E_SECS
        STR R4,P_SECS
po_lf:  LDR R3,LEAF
        JSR strlen
        MVRHA R4
        BRNZ ret0
        MVRLA R4
        BRZ ret0
        LDTI 12
        BRGT ret0
        LDAVR R3                ; not "." or ".."
        LDTI 46
        BRNEQ ret1
        MVRLA R4
        LDTI 1
        BREQ ret0
        LDTI 2
        BRNEQ ret1
        INCR R3
        LDAVR R3
        LDTI 46
        BREQ ret0
        BR ret1

; leaf_find: find_in(p_lba, p_secs, leaf, strlen(leaf)). Clobbers R3-R7.
leaf_find:
        LDR R3,LEAF
        JSR strlen
        MOVRR R3,R5
        LDR R3,P_SECS
        STR R3,FI_SECS
        LDR R3,P_LBA
        BR find_in

; tombstone: flag the entry at E_SLBA/E_OFF deleted ($FF). Clobbers R4, R6, R7, ACC.
tombstone:
        LDR R6,E_SLBA
        MVIW R7,SBUF
        JSR cfrd
        BRNZ rts
        LDR R4,E_OFF
        MVRLA R4
        ADDI 24
        MVARL R4
        MVRHA R4
        ADDI (SBUF).1
        MVARH R4
        LDIVR R4,255
        LDR R6,E_SLBA
        MVIW R7,SBUF
        BR cfwr

; =====================================================================================================================
; Handles (y1os.c new_handle, open_ent, mode_of, hb): records at HTAB + 16h, buffers at hbuf(h). Handle 0 has a
; record too, never opened: fs_putc(0, c) with no write open reaches it (and the buffer $0200), exactly as the C's
; h_*[0] and hb(0) (see os/README.md, the notes on the assembly OS).
; =====================================================================================================================
; hrec: ACC = handle -> R4 -> its record (the mode byte). Clobbers ACC.
hrec:   SHL
        SHL
        SHL
        SHL
        MVARL R4
        LDAI (HTAB).1
        MVARH R4
        RET

; hbuf: ACC = handle -> R5 = its 512-byte buffer, $0400 + 512 (h - 1). Clobbers ACC.
hbuf:   SHL
        ADDI 2
        MVARH R5
        LDAI 0
        MVARL R5
        RET

; new_handle: -> ACC = the first free handle 1..4, 0 none.
new_handle:
        LDA HTAB+16
        BRZ nh_1
        LDA HTAB+32
        BRZ nh_2
        LDA HTAB+48
        BRZ nh_3
        LDA HTAB+64
        BRZ nh_4
        LDAI 0
        RET
nh_1:   LDAI 1
        RET
nh_2:   LDAI 2
        RET
nh_3:   LDAI 3
        RET
nh_4:   LDAI 4
        RET

; mode_of: R3 = a handle (16 bits) -> ACC = its mode, 0 (free) for 0 and above 4; R4 -> its record for 1..4.
; R3 kept.
mode_of:
        MVRHA R3
        BRNZ mo_0
        MVRLA R3
        BRZ mo_0
        LDTI 4
        BRGT mo_0
        JSR hrec
        LDAVR R4
        RET
mo_0:   LDAI 0
        RET

; open_ent: a handle on the entry in E_* with mode ACC (M_READ: a file, its length; M_DIR: its extent, secs * 512)
; -> ACC = R3 = the handle, 0 none free. Clobbers R4, R5.
open_ent:
        STA OE_MODE
        JSR new_handle
        BRZ ret0
        STA OE_H
        JSR hrec
        LDA OE_MODE
        STAVR R4                ; mode
        LDAI 0
        INCR R4
        STAVR R4                ; position 0
        INCR R4
        STAVR R4
        LDA OE_MODE
        LDTI M_DIR
        BREQ oe_d
        LDR R5,E_LEN
        BR oe_l
oe_d:   LDR R5,E_SECS
        MVRLA R5
        SHL
        MVARH R5
        LDAI 0
        MVARL R5
oe_l:   INCR R4                 ; length
        MVRHA R5
        STAVR R4
        INCR R4
        MVRLA R5
        STAVR R4
        LDAI 255                ; no sector in the buffer
        INCR R4
        STAVR R4
        INCR R4
        STAVR R4
        LDR R5,E_LBA            ; start
        INCR R4
        MVRHA R5
        STAVR R4
        INCR R4
        MVRLA R5
        STAVR R4
        LDA OE_H
        BR reta

; =====================================================================================================================
; The file layer (y1os.c fs_*): what the shell's commands and the syscalls share.
; =====================================================================================================================
; fs_open: the path at R3 -> ACC = R3 = a read handle, 0 (not found, not a file, 64K or more, no handle free).
fs_open:
        JSR resolve
        BRZ ret0
        LDA ERAW+24
        LDTI F_FILE
        BRNEQ ret0
        LDA ERAW+18
        BRNZ ret0
        LDAI M_READ
        BR open_ent

; fs_opendir: the path at R3 -> ACC = R3 = a directory handle, 0.
fs_opendir:
        JSR resolve
        BRZ ret0
        LDA ERAW+24
        LDTI F_DIR
        BRNEQ ret0
        LDAI M_DIR
        BR open_ent

; fs_read: handle R3 (read or directory), buffer R5 -> R3 = the bytes of the file in the sector holding the
; position, read straight into the buffer; the position moves to the end of that sector. 0 at the end, for another
; handle, on a card error. Clobbers R3-R7.
fs_read:
        JSR mode_of
        BRZ ret0
        LDTI M_WRITE
        BREQ ret0
        MOVRR R5,R7             ; the destination
        INCR R4                 ; R3 = the position, R5 = the length
        LDAVR R4
        MVARH R3
        INCR R4
        LDAVR R4
        MVARL R3
        INCR R4
        LDAVR R4
        MVARH R5
        INCR R4
        LDAVR R4
        MVARL R5
        MVRHA R5                ; position >= length: 0
        MVAT
        MVRHA R3
        BRLT fr_in
        BRNEQ ret0
        MVRLA R5
        MVAT
        MVRLA R3
        BRLT fr_in
        BR ret0
fr_in:  MVRLA R4                ; R6 = start + position / 512
        ANDI 0F0H
        ORI H_LBA
        MVARL R4
        LDAVR R4
        MVARH R6
        INCR R4
        LDAVR R4
        MVARL R6
        MVRHA R3
        SHR
        MVAT
        MVRLA R6
        ADDT
        MVARL R6
        MVRHA R6
        ADDIC 0
        MVARH R6
        JSR cfrd
        BRNZ ret0
        MVRHA R3                ; R3 = s = the sector's first byte (position & ~511)
        ANDI 0FEH
        MVARH R3
        LDAI 0
        MVARL R3
        MVRHA R3                ; R6 = n = length - s (s's low byte is 0: no borrow)
        MVAT
        MVRHA R5
        SUBT
        MVARH R6
        MVRLA R5
        MVARL R6
        MVRHA R6                ; n = 512 at most
        LDTI 2
        BRLT fr_n
        BRNEQ fr_512
        MVRLA R6
        BRZ fr_n
fr_512: MVIW R6,512
fr_n:   MVRHA R6                ; position = s + n
        MVAT
        MVRHA R3
        ADDT
        MVARH R3
        MVRLA R6
        MVARL R3
        MVRLA R4
        ANDI 0F0H
        ORI H_POS
        MVARL R4
        MVRHA R3
        STAVR R4
        INCR R4
        MVRLA R3
        STAVR R4
        MOVRR R6,R3
        BR retr3

; fs_getc: read handle R3 -> R3 = its next byte through the handle's buffer, 65535 at the end (and for anything
; that is not a read handle, and on a card error). CONIN's path: no variables, no printing. Clobbers R4-R7.
fs_getc:
        JSR mode_of
        LDTI M_READ
        BRNEQ fg_end
        MVRLA R3
        JSR hbuf                ; R5 = the buffer
        INCR R4                 ; R3 = the position
        LDAVR R4
        MVARH R3
        INCR R4
        LDAVR R4
        MVARL R3
        INCR R4                 ; position >= length: the end
        LDAVR R4
        MVAT
        MVRHA R3
        BRLT fg_in
        BRNEQ fg_end
        INCR R4
        LDAVR R4
        MVAT
        MVRLA R3
        BRLT fg_in
        BR fg_end
fg_in:  MVRLA R4                ; the sector s = position / 512 in the buffer already?
        ANDI 0F0H
        ORI H_CUR
        MVARL R4
        LDAVR R4
        BRNZ fg_rd              ; (65535 = none; s < 128)
        INCR R4
        LDAVR R4
        MVAT
        MVRHA R3
        SHR
        BREQ fg_hav
fg_rd:  MVRLA R4                ; read it: start + s
        ANDI 0F0H
        ORI H_LBA
        MVARL R4
        LDAVR R4
        MVARH R6
        INCR R4
        LDAVR R4
        MVARL R6
        MVRHA R3
        SHR
        MVAT
        MVRLA R6
        ADDT
        MVARL R6
        MVRHA R6
        ADDIC 0
        MVARH R6
        MOVRR R5,R7
        JSR cfrd
        BRNZ fg_end
        MVRLA R4                ; cur = s
        ANDI 0F0H
        ORI H_CUR
        MVARL R4
        LDIVR R4,0
        INCR R4
        MVRHA R3
        SHR
        STAVR R4
fg_hav: MVRHA R3                ; R5 -> buffer + (position & 511)
        ANDI 1
        MVAT
        MVRHA R5
        ADDT
        MVARH R5
        MVRLA R3
        MVARL R5
        INCR R3                 ; position + 1
        MVRLA R4
        ANDI 0F0H
        ORI H_POS
        MVARL R4
        MVRHA R3
        STAVR R4
        INCR R4
        MVRLA R3
        STAVR R4
        LDAVR R5
        BR reta
fg_end: MVIW R3,0FFFFH
        LDAI 255
        RET

; fs_readdir: directory handle R3, buffer R5 -> ACC = R3 = 1 with the next live entry (32 bytes) in the buffer, 0 at
; the end (the $00 mark moves the position to the end), for another handle, on a card error. Clobbers R3-R7.
fs_readdir:
        STR R5,RD_BUF
        JSR mode_of
        LDTI M_DIR
        BRNEQ ret0
        MVRLA R3
        JSR hbuf                ; R5 = the buffer
        INCR R4                 ; R3 = the position, RD_LEN = the length
        LDAVR R4
        MVARH R3
        INCR R4
        LDAVR R4
        MVARL R3
        INCR R4
        LDAVR R4
        MVARH R6
        INCR R4
        LDAVR R4
        MVARL R6
        STR R6,RD_LEN
frd_lp: LDR R6,RD_LEN           ; while position < length
        MVRHA R6
        MVAT
        MVRHA R3
        BRLT frd_in
        BRNEQ frd_out
        MVRLA R6
        MVAT
        MVRLA R3
        BRLT frd_in
frd_out: MOVRR R3,R6            ; the position stays where the scan ended
        BR frd_sp
frd_in: MVRLA R4                ; the sector in the buffer?
        ANDI 0F0H
        ORI H_CUR
        MVARL R4
        LDAVR R4
        BRNZ frd_rd
        INCR R4
        LDAVR R4
        MVAT
        MVRHA R3
        SHR
        BREQ frd_hv
frd_rd: MVRLA R4
        ANDI 0F0H
        ORI H_LBA
        MVARL R4
        LDAVR R4
        MVARH R6
        INCR R4
        LDAVR R4
        MVARL R6
        MVRHA R3
        SHR
        MVAT
        MVRLA R6
        ADDT
        MVARL R6
        MVRHA R6
        ADDIC 0
        MVARH R6
        MOVRR R5,R7
        JSR cfrd
        BRNZ ret0
        MVRLA R4
        ANDI 0F0H
        ORI H_CUR
        MVARL R4
        LDIVR R4,0
        INCR R4
        MVRHA R3
        SHR
        STAVR R4
frd_hv: MVRHA R3                ; R6 -> the entry, R7 -> its flags
        ANDI 1
        MVAT
        MVRHA R5
        ADDT
        MVARH R6
        MVRLA R3
        MVARL R6
        ADDI 24
        MVARL R7
        MVRHA R6
        MVARH R7
        LDAVR R7
        BRZ frd_end
        MVAT                    ; (TMP = the flags)
        MVRLA R3                ; position += 32
        ADDI 32
        MVARL R3
        MVRHA R3
        ADDIC 0
        MVARH R3
        MVTA
        LDTI 255
        BREQ frd_lp             ; deleted: the next one
        MVRLA R4                ; a live entry: the position, the copy, 1
        ANDI 0F0H
        ORI H_POS
        MVARL R4
        MVRHA R3
        STAVR R4
        INCR R4
        MVRLA R3
        STAVR R4
        MOVRR R6,R4
        LDR R5,RD_BUF
        JSR cpy32
        BR ret1
frd_end: LDR R6,RD_LEN          ; the end mark: the position goes to the end
frd_sp: MVRLA R4
        ANDI 0F0H
        ORI H_POS
        MVARL R4
        MVRHA R6
        STAVR R4
        INCR R4
        MVRLA R6
        STAVR R4
        BR ret0

; fs_create: a new file, the path at R3, load CR_LOAD, exec CR_EXEC -> ACC = R3 = the write handle (WH), 0 (a write
; already open, a bad path, a directory of that name, no handle free). It is written at the free pointer and
; registered at CLOSE; a same-named FILE is replaced then, in its own slot (W_OSLBA/W_OOFF), so until then it is whole.
; Clobbers R3-R7.
fs_create:
        LDA WH
        BRNZ ret0
        JSR parent_of
        BRZ ret0
        MVIW R3,0
        STR R3,W_OSLBA
        JSR leaf_find
        BRZ fc_new
        LDA ERAW+24
        LDTI F_FILE
        BRNEQ ret0
        LDR R3,E_SLBA
        STR R3,W_OSLBA
        LDR R3,E_OFF
        STR R3,W_OOFF
fc_new: JSR new_handle
        BRZ ret0
        STA WH                  ; (wh = h; nothing below reads it before the end)
        JSR hrec
        LDIVR R4,M_WRITE        ; mode
        LDAI 0
        INCR R4                 ; position, length, cur = 0
        STAVR R4
        INCR R4
        STAVR R4
        INCR R4
        STAVR R4
        INCR R4
        STAVR R4
        INCR R4
        STAVR R4
        INCR R4
        STAVR R4
        LDR R5,FREE_LBA         ; start = the free pointer
        INCR R4
        MVRHA R5
        STAVR R4
        INCR R4
        MVRLA R5
        STAVR R4
        LDA WH
        JSR hbuf
        JSR zero512
        LDR R3,LEAF
        MVIW R4,WNAME
        JSR strcpy
        LDR R3,P_LBA
        STR R3,W_DLBA
        LDR R3,P_SECS
        STR R3,W_DSECS
        LDR R3,CR_LOAD
        STR R3,W_LOAD
        LDR R3,CR_EXEC
        STR R3,W_EXEC
        LDA WH
        BR reta

; fs_putc: append the byte in ACC through write handle R3 (the 16-bit word must equal WH, and one must be open) ->
; ACC = R3 = 1, 0 (not the open write handle, 65535 bytes reached, a card error). A full buffer goes to the card when the next byte
; arrives. CONOUT's path: only PC_BYTE, no printing. Clobbers R4-R7, TMP.
fs_putc:
        STA PC_BYTE
        LDA WH
        BRZ ret0                ; no write open: nothing (h = 0 passed 0 == 0 and wrote LBA 0 until 2026-09-23)
        MVAT
        MVRLA R3
        BRNEQ ret0
        MVRHA R3
        BRNZ ret0
        MVRLA R3
        JSR hbuf                ; R5 = the buffer
        MVRLA R3
        JSR hrec
        INCR R4                 ; R3 = the position
        LDAVR R4
        MVARH R3
        INCR R4
        LDAVR R4
        MVARL R3
        LDTI 255                ; 65535: full
        BRNEQ fp_1
        MVRHA R3
        BREQ ret0
fp_1:   MVRLA R3                ; position & 511 == 0 and position != 0: flush the full buffer first
        BRNZ fp_put
        MVRHA R3
        BRZ fp_put
        ANDI 1
        BRNZ fp_put
        MVRLA R4                ; R6 = start + cur
        ANDI 0F0H
        ORI H_CUR
        MVARL R4
        LDAVR R4
        MVARH R7
        INCR R4
        LDAVR R4
        MVARL R7
        INCR R4
        LDAVR R4
        MVARH R6
        INCR R4
        LDAVR R4
        MVARL R6
        MVRLA R7
        MVAT
        MVRLA R6
        ADDT
        MVARL R6
        MVRHA R7
        MVAT
        MVRHA R6
        ADDTC
        MVARH R6
        MOVRR R5,R7
        JSR cfwr
        BRNZ ret0
        MVRLA R4                ; cur + 1
        ANDI 0F0H
        ORI H_CUR
        MVARL R4
        LDAVR R4
        MVARH R6
        INCR R4
        LDAVR R4
        MVARL R6
        INCR R6
        MVRLA R6
        STAVR R4
        DECR R4
        MVRHA R6
        STAVR R4
        JSR zero512             ; a fresh buffer (R5 comes back 512 higher)
        MVRHA R5
        SUBI 2
        MVARH R5
fp_put: MVRHA R3                ; buffer[position & 511] = the byte
        ANDI 1
        MVAT
        MVRHA R5
        ADDT
        MVARH R5
        MVRLA R3
        MVARL R5
        LDA PC_BYTE
        STAVR R5
        INCR R3                 ; position + 1
        MVRLA R4
        ANDI 0F0H
        ORI H_POS
        MVARL R4
        MVRHA R3
        STAVR R4
        INCR R4
        MVRLA R3
        STAVR R4
        BR ret1

; fs_append (the shell's >>, not a syscall): the path at R3 -> ACC = R3 = a write handle positioned at the end of
; the file (a new file if there is none). When the file's extent ends at the free pointer the handle continues in
; place; otherwise its sectors are copied to the free pointer first. The old file is untouched either way until
; CLOSE writes the new entry over the old one. 0: a directory of that name, 64K or more, a card error, no handle.
; Clobbers R3-R7.
fs_append:
        STR R3,AP_PATH
        JSR resolve
        BRZ ap_new
        LDA ERAW+24
        LDTI F_FILE
        BRNEQ ap_new
        LDA ERAW+18
        BRNZ ret0
        LDR R3,E_LBA
        STR R3,AP_OLBA
        LDR R3,E_LEN
        STR R3,AP_LEN
        MVRHA R3                ; n = ceil(len / 512)
        SHR
        MVARL R4
        LDAI 0
        MVARH R4
        MVRLA R3
        BRNZ ap_i
        MVRHA R3
        ANDI 1
        BRZ ap_nn
ap_i:   INCR R4
ap_nn:   STR R4,AP_N
        LDR R5,FREE_LBA         ; base = n && olba + e_secs == free_lba ? olba : free_lba
        MVRLA R4
        BRZ ap_b                ; (n <= 128)
        LDR R3,AP_OLBA
        LDR R4,E_SECS
        JSR add34
        MVRLA R3
        MVAT
        MVRLA R5
        BRNEQ ap_b
        MVRHA R3
        MVAT
        MVRHA R5
        BRNEQ ap_b
        LDR R5,AP_OLBA
ap_b:   STR R5,AP_BASE
        LDR R3,E_LOAD           ; h = fs_create(path, e_load, e_exec)
        STR R3,CR_LOAD
        LDR R3,E_EXEC
        STR R3,CR_EXEC
        LDR R3,AP_PATH
        JSR fs_create
        BRZ ret0
        JSR hrec                ; start = base
        MVRLA R4
        ORI H_LBA
        MVARL R4
        LDR R5,AP_BASE
        MVRHA R5
        STAVR R4
        INCR R4
        MVRLA R5
        STAVR R4
        MVIW R3,0
        STR R3,AP_S
ap_lp:  LDR R3,AP_S             ; for s < n: read old sector s; unless it is the last or the file stays in
        LDA AP_N+1              ; place, write it at base + s (the last one stays in the buffer)
        MVAT
        MVRLA R3
        BREQ ap_dn
        LDR R4,AP_OLBA
        JSR add34
        MOVRR R3,R6
        LDA WH
        JSR hbuf
        MOVRR R5,R7
        JSR cfrd
        BRNZ ap_ab
        LDR R3,AP_S
        INCR R3
        LDA AP_N+1
        MVAT
        MVRLA R3
        BREQ ap_nx
        LDR R3,AP_BASE
        LDR R4,AP_OLBA
        MVRLA R3
        MVAT
        MVRLA R4
        BRNEQ ap_cp
        MVRHA R3
        MVAT
        MVRHA R4
        BREQ ap_nx
ap_cp:  LDR R4,AP_S
        JSR add34
        MOVRR R3,R6
        LDA WH
        JSR hbuf
        MOVRR R5,R7
        JSR cfwr
        BRNZ ap_ab
ap_nx:  LDR R3,AP_S
        INCR R3
        STR R3,AP_S
        BR ap_lp
ap_dn:  LDA AP_N+1              ; if n: cur = n - 1; position = len
        BRZ ap_p
        MVARL R3
        LDAI 0
        MVARH R3
        DECR R3
        LDA WH
        JSR hrec
        MVRLA R4
        ORI H_CUR
        MVARL R4
        MVRHA R3
        STAVR R4
        INCR R4
        MVRLA R3
        STAVR R4
ap_p:   LDA WH
        JSR hrec
        MVRLA R4
        ORI H_POS
        MVARL R4
        LDR R3,AP_LEN
        MVRHA R3
        STAVR R4
        INCR R4
        MVRLA R3
        STAVR R4
        LDA WH
        BR reta
ap_ab:  LDA WH                  ; abandoned: nothing registered, the old file stands
        JSR hrec
        LDAI 0
        STAVR R4
        STA WH
        BR ret0
ap_new: MVIW R3,0               ; no such file (or a directory: fs_create refuses it)
        STR R3,CR_LOAD
        STR R3,CR_EXEC
        LDR R3,AP_PATH
        BR fs_create

; fs_write: handle R3, buffer R5, FW_N bytes -> R3 = the bytes written (fs_putc each; stops at the first refused).
; Clobbers R3-R7.
fs_write:
        STR R3,FW_H
        STR R5,FW_P
        MVIW R3,0
fw_lp:  STR R3,FW_I
        LDR R4,FW_N             ; i < n?
        MVRHA R4
        MVAT
        MVRHA R3
        BRLT fw_go
        BRNEQ retr3
        MVRLA R4
        MVAT
        MVRLA R3
        BRLT fw_go
        BR retr3
fw_go:  LDR R5,FW_P
        LDAVR R5
        INCR R5
        STR R5,FW_P
        LDR R3,FW_H
        JSR fs_putc
        LDR R3,FW_I
        BRZ retr3
        INCR R3
        BR fw_lp

; new_slot: where CLOSE registers the file: the replaced file's own slot if it still holds that file (a del or ren
; while the write was open: not), else the first free one -> ACC = 1 with E_SLBA/E_OFF, its sector in SBUF; 0.
; Clobbers R3-R7.
new_slot:
        LDR R6,W_OSLBA
        MVRLA R6
        BRNZ ns_old
        MVRHA R6
        BRZ ns_fnd
ns_old: MVIW R7,SBUF
        JSR cfrd
        BRNZ ret0
        LDR R3,W_OOFF           ; R3 -> the old entry
        MVRHA R3
        ADDI (SBUF).1
        MVARH R3
        MVRLA R3
        ADDI 24
        MVARL R4
        MVRHA R3
        MVARH R4
        LDAVR R4
        LDTI F_FILE
        BRNEQ ns_fnd
        PUSHR R3
        MVIW R3,WNAME
        JSR strlen
        JSR nm_set
        POPR R3
        MVIW R5,WNAME
        JSR name_is
        BRZ ns_fnd
        LDR R3,W_OSLBA
        STR R3,E_SLBA
        LDR R3,W_OOFF
        STR R3,E_OFF
        BR ret1
ns_fnd: LDR R3,W_DSECS
        STR R3,FI_SECS
        LDR R3,W_DLBA
        BR find_slot

; fs_close: handle R3 -> R3 = 0 not open; a read or directory handle: its mode (1 / 3, as the C returns it); the
; write handle: 1 when the last sector, the entry and the free pointer are written, 0 not (the handle is freed
; either way). Clobbers R3-R7.
fs_close:
        JSR mode_of
        BRZ ret0
        LDTI M_WRITE
        BREQ fcl_w
        MVAT
        LDIVR R4,0
        MVTA
        BR reta
fcl_w:  STR R4,CL_REC
        LDAI 0
        STA CL_OK
        MVRLA R4                ; R6 = start + cur: the buffer's sector
        ORI H_CUR
        MVARL R4
        LDAVR R4
        MVARH R5
        INCR R4
        LDAVR R4
        MVARL R5
        STR R5,CL_CUR
        INCR R4
        LDAVR R4
        MVARH R6
        INCR R4
        LDAVR R4
        MVARL R6
        STR R6,CL_LBA
        MVRLA R5
        MVAT
        MVRLA R6
        ADDT
        MVARL R6
        MVRHA R5
        MVAT
        MVRHA R6
        ADDTC
        MVARH R6
        MVRLA R3
        JSR hbuf
        MOVRR R5,R7
        JSR cfwr                ; the last (maybe partial, maybe empty) sector
        BRNZ fcl_e
        JSR new_slot
        BRZ fcl_e
        LDR R3,CL_LBA           ; set_entry(e_off, w_name, lba, position, w_load, w_exec, F_FILE)
        STR R3,SE_LBA
        LDR R4,CL_REC
        MVRLA R4
        ORI H_POS
        MVARL R4
        LDAVR R4
        MVARH R3
        INCR R4
        LDAVR R4
        MVARL R3
        STR R3,SE_LEN
        LDR R3,W_LOAD
        STR R3,SE_LOAD
        LDR R3,W_EXEC
        STR R3,SE_EXEC
        LDAI F_FILE
        STA SE_FLAG
        LDR R3,E_OFF
        MVRHA R3
        ADDI (SBUF).1
        MVARH R3
        MVIW R5,WNAME
        JSR set_entry
        LDR R6,E_SLBA
        MVIW R7,SBUF
        JSR cfwr
        BRNZ fcl_e
        LDR R3,CL_LBA           ; free_lba = lba + cur + 1
        LDR R4,CL_CUR
        JSR add34
        INCR R3
        STR R3,FREE_LBA
        JSR write_free
        LDAI 1
        STA CL_OK
fcl_e:  LDAI 0
        STA WH
        LDR R4,CL_REC
        LDIVR R4,0
        LDA CL_OK
        BR reta

; close_all: close what a program left open (a pending write is registered), not the shell's redirect files.
close_all:
        LDAI 1
        STA CA_H
ca_lp:  JSR hrec
        LDAVR R4
        BRZ ca_nx
        LDA SI_H
        MVAT
        LDA CA_H
        BREQ ca_nx
        LDA SO_H
        MVAT
        LDA CA_H
        BREQ ca_nx
        MVARL R3
        LDAI 0
        MVARH R3
        JSR fs_close
ca_nx:  LDA CA_H
        ADDI 1
        STA CA_H
        LDTI 5
        BRNEQ ca_lp
        RET

; fs_delete: the path at R3 -> ACC = R3 = 1 tombstoned (even when the card then fails), 0 not a file.
fs_delete:
        JSR resolve
        BRZ ret0
        LDA ERAW+24
        LDTI F_FILE
        BRNEQ ret0
        LDR R3,E_SLBA
        MVRLA R3
        BRNZ fd_ok
        MVRHA R3
        BRZ ret0
fd_ok:  JSR tombstone
        BR ret1

; fs_mkdir: the path at R3 -> ACC = R3 = 1: a 4-sector extent at the free pointer with '.' and '..', as p8xfs.py
; mkdir writes it; 0 (a write open, a bad path, the name taken, the directory full, a card error). Clobbers R3-R7.
fs_mkdir:
        LDA WH
        BRNZ ret0
        JSR parent_of
        BRZ ret0
        JSR leaf_find
        BRNZ ret0
        LDR R3,P_SECS
        STR R3,FI_SECS
        LDR R3,P_LBA
        JSR find_slot
        BRZ ret0
        LDR R3,FREE_LBA
        STR R3,MK_NL
        STR R3,SE_LBA           ; set_entry(e_off, leaf, nl, 2048, 0, 0, F_DIR)
        MVIW R3,2048
        STR R3,SE_LEN
        MVIW R3,0
        STR R3,SE_LOAD
        STR R3,SE_EXEC
        LDAI F_DIR
        STA SE_FLAG
        LDR R3,E_OFF
        MVRHA R3
        ADDI (SBUF).1
        MVARH R3
        LDR R5,LEAF
        JSR set_entry
        LDR R6,E_SLBA
        MVIW R7,SBUF
        JSR cfwr
        BRNZ ret0
        MVIW R5,SBUF            ; the extent's first sector: '.' and '..'
        JSR zero512
        MVIW R3,SBUF
        MVIW R5,S_DOT
        JSR set_entry
        LDR R3,P_LBA
        STR R3,SE_LBA
        LDR R3,P_SECS
        MVRLA R3
        SHL
        MVARH R3
        LDAI 0
        MVARL R3
        STR R3,SE_LEN
        MVIW R3,SBUF+32
        MVIW R5,S_DOTDOT
        JSR set_entry
        LDR R6,MK_NL
        MVIW R7,SBUF
        JSR cfwr
        BRNZ ret0
        MVIW R3,SBUF            ; the other three: empty
        MVIB R4,64
mk_z:   LDIVR R3,0
        INCR R3
        DECR R4
        MVRLA R4
        BRNZ mk_z
        LDR R3,MK_NL
        MVIB R4,3
mk_w:   INCR R3
        MOVRR R3,R6
        MVIW R7,SBUF
        JSR cfwr
        BRNZ ret0
        DECR R4
        MVRLA R4
        BRNZ mk_w
        INCR R3                 ; free_lba = nl + 4
        STR R3,FREE_LBA
        JSR write_free
        BR ret1

; fs_rmdir: the path at R3 -> ACC = R3 = 1: an empty directory (only '.' and '..' live) tombstoned; 0 (not a
; directory, not empty, '.', '..', the root or the current directory itself, a card error). Clobbers R3-R7.
fs_rmdir:
        JSR resolve
        BRZ ret0
        LDA ERAW+24
        LDTI F_DIR
        BRNEQ ret0
        LDR R3,E_SLBA
        MVRLA R3
        BRNZ rm_1
        MVRHA R3
        BRZ ret0
rm_1:   LDA ERAW
        LDTI 46
        BREQ ret0
        LDR R3,E_SLBA
        STR R3,RM_SLBA
        LDR R3,E_OFF
        STR R3,RM_OFF
        LDR R3,E_LBA
        STR R3,RM_LBA
        LDR R3,E_SECS
        STR R3,RM_LEFT
rm_sc:  LDR R3,RM_LEFT
        MVRLA R3
        BRNZ rm_rd
        MVRHA R3
        BRZ rm_ok
rm_rd:  DECR R3
        STR R3,RM_LEFT
        LDR R6,RM_LBA
        MVIW R7,SBUF
        JSR cfrd
        BRNZ ret0
        MVIW R3,SBUF
rm_en:  MVRLA R3
        ADDI 24
        MVARL R4
        MVRHA R3
        MVARH R4
        LDAVR R4
        BRZ rm_ok               ; the end mark: empty
        LDTI 255
        BREQ rm_nx
        MVIW R4,1
        JSR nm_set
        MVIW R5,S_DOT
        JSR name_is
        BRNZ rm_nx
        MVIW R4,2
        JSR nm_set
        MVIW R5,S_DOTDOT
        JSR name_is
        BRZ ret0                ; a live entry other than . and ..
rm_nx:  MVRLA R3
        ADDI 32
        MVARL R3
        MVRHA R3
        ADDIC 0
        MVARH R3
        LDTI (SBUF+512).1
        BRNEQ rm_en
        LDR R3,RM_LBA
        INCR R3
        STR R3,RM_LBA
        BR rm_sc
rm_ok:  LDR R3,RM_SLBA
        STR R3,E_SLBA
        LDR R3,RM_OFF
        STR R3,E_OFF
        JSR tombstone
        BR ret1

; fs_resolve: the path at R3, buffer R5 (0: none) -> ACC = R3 = 1 found (the entry copied to the buffer), 0.
fs_resolve:
        STR R5,RV_BUF
        JSR resolve
        BRZ ret0
        LDR R5,RV_BUF
        MVRLA R5
        BRNZ rv_cp
        MVRHA R5
        BRZ ret1
rv_cp:  MVIW R4,ERAW
        JSR cpy32
        BR ret1

; fs_rename: the path at R3, the new name at R5 -> ACC = R3 = 1: the entry renamed in place (same slot, same
; directory); 0 (not found, '.', '..', the root, a bad name: empty, over 12, starting '.', holding '/', taken).
; Clobbers R3-R7.
fs_rename:
        STR R5,RN_NEW
        JSR resolve
        BRZ ret0
        LDR R3,E_SLBA
        MVRLA R3
        BRNZ rn_1
        MVRHA R3
        BRZ ret0
rn_1:   LDA ERAW
        LDTI 46
        BREQ ret0
        LDR R3,E_SLBA
        STR R3,RN_SLBA
        LDR R3,E_OFF
        STR R3,RN_OFF
        LDR R3,RLBA
        STR R3,RN_DLBA
        LDR R3,RSECS
        STR R3,RN_DSECS
        LDR R3,RN_NEW
        JSR strlen              ; R4 = n
        MVRHA R4
        BRNZ ret0
        MVRLA R4
        BRZ ret0
        LDTI 12
        BRGT ret0
        LDAVR R3
        LDTI 46
        BREQ ret0
        MOVRR R3,R5
rn_sl:  LDAVR R5
        BRZ rn_f
        LDTI 47
        BREQ ret0
        INCR R5
        BR rn_sl
rn_f:   MOVRR R3,R5             ; the new name taken?
        LDR R3,RN_DSECS
        STR R3,FI_SECS
        LDR R3,RN_DLBA
        JSR find_in
        BRNZ ret0
        LDR R6,RN_SLBA
        MVIW R7,SBUF
        JSR cfrd
        BRNZ ret0
        LDR R3,RN_OFF
        MVRHA R3
        ADDI (SBUF).1
        MVARH R3
        LDR R5,RN_NEW
        JSR put_name
        LDR R6,RN_SLBA
        MVIW R7,SBUF
        JSR cfwr
        BRNZ ret0
        BR ret1

; path_pop: CWDPATH loses its last component ("/A/B" -> "/A", "/A" -> "/"). CWDPATH lies in one page.
; Clobbers R3-R5, ACC, TMP.
path_pop:
        MVIW R3,CWDPATH
        JSR strlen              ; R5 -> the NUL (cwdpath + n)
pp_lp:  MVRLA R5                ; while n > 1 && cwdpath[n - 1] != '/': n--
        LDTI (CWDPATH+1).0
        BRLT pp_af
        BREQ pp_af
        DECR R5
        LDAVR R5
        INCR R5
        LDTI 47
        BREQ pp_af
        DECR R5
        BR pp_lp
pp_af:  MVRLA R5                ; if n > 1: n-- (keep "/" alone)
        LDTI (CWDPATH+1).0
        BRLT pp_z
        BREQ pp_z
        DECR R5
pp_z:   LDIVR R5,0
        RET

; path_push: CWDPATH += "/" + the R4 characters at R3 (nothing when it would pass 62). Clobbers R3-R5, ACC, TMP.
path_push:
        STR R3,PU_NM
        STR R4,PU_N
        MVIW R3,CWDPATH
        JSR strlen              ; R4 = l, R5 -> the NUL
        MOVRR R4,R3             ; l + n + 2 > 62: no room
        LDR R4,PU_N
        JSR add34
        INCR R3
        INCR R3
        MVRHA R3
        BRNZ rts
        MVRLA R3
        LDTI 62
        BRGT rts
        MVRLA R5                ; l > 1: a '/' first
        LDTI (CWDPATH+1).0
        BRLT pu_cp
        BREQ pu_cp
        LDIVR R5,47
        INCR R5
pu_cp:  LDR R3,PU_NM
        LDR R4,PU_N
pu_lp:  MVRLA R4
        BRNZ pu_c
        MVRHA R4
        BRZ pu_z
pu_c:   LDAVR R3
        STAVR R5
        INCR R3
        INCR R5
        DECR R4
        BR pu_lp
pu_z:   LDIVR R5,0
        RET

; fs_chdir: the path at R3 -> ACC = R3 = 1 ok, 0 not found, 2 not a directory. CWDPATH follows the components as
; they are typed ('..' pops, '.' stays); on a failure it is restored from PBUF. Clobbers R3-R7.
fs_chdir:
        STR R3,CD_P
        MVIW R3,CWDPATH         ; the path to restore
        MVIW R4,PBUF
        JSR strcpy
        LDAI 1
        STA CD_R
        LDR R3,CD_P
        LDAVR R3
        LDTI 47
        BRNEQ cd_rel
        MVIW R4,ROOT_LBA
        STR R4,CD_LBA
        MVIW R4,ROOT_SECS
        STR R4,CD_SECS
        LDAI 47
        STA CWDPATH
        LDAI 0
        STA CWDPATH+1
        INCR R3
        STR R3,CD_P
        BR cd_lp
cd_rel: LDR R4,CWD_LBA
        STR R4,CD_LBA
        LDR R4,CWD_SECS
        STR R4,CD_SECS
cd_lp:  LDR R3,CD_P
        LDAVR R3
        BRZ cd_dn
        MOVRR R3,R5             ; n = the component's length
        MVIW R4,0
cd_cn:   LDAVR R5
        BRZ cd_n2
        LDTI 47
        BREQ cd_n2
        INCR R5
        INCR R4
        BR cd_cn
cd_n2:  MVRLA R4
        BRNZ cd_fd
        MVRHA R4
        BRNZ cd_fd
        INCR R3                 ; an empty component ("//"): skip the '/'
        STR R3,CD_P
        BR cd_lp
cd_fd:  STR R4,CD_N
        MOVRR R3,R5
        LDR R3,CD_SECS
        STR R3,FI_SECS
        LDR R3,CD_LBA
        JSR find_in
        BRNZ cd_f1
        LDAI 0
        STA CD_R
        BR cd_dn
cd_f1:  LDA ERAW+24
        LDTI F_DIR
        BREQ cd_f2
        LDAI 2
        STA CD_R
        BR cd_dn
cd_f2:  LDR R3,CD_P             ; ".." pops, "." stays, a name is pushed
        LDR R4,CD_N
        MVRHA R4
        BRNZ cd_psh
        MVRLA R4
        LDTI 2
        BREQ cd_2
        LDTI 1
        BRNEQ cd_psh
        LDAVR R3
        LDTI 46
        BREQ cd_nx
        BR cd_psh
cd_2:   LDAVR R3
        LDTI 46
        BRNEQ cd_psh
        INCR R3
        LDAVR R3
        LDTI 46
        BRNEQ cd_psh
        JSR path_pop
        BR cd_nx
cd_psh: LDR R3,CD_P
        LDR R4,CD_N
        JSR path_push
cd_nx:  LDR R4,E_LBA            ; into it
        STR R4,CD_LBA
        LDR R4,E_SECS
        STR R4,CD_SECS
        LDR R3,CD_P
        LDR R4,CD_N
        JSR add34
        STR R3,CD_P
        BR cd_lp
cd_dn:  LDA CD_R
        LDTI 1
        BREQ cd_ok
        MVIW R3,PBUF
        MVIW R4,CWDPATH
        JSR strcpy
        LDA CD_R
        BR reta
cd_ok:  LDR R3,CD_LBA
        STR R3,CWD_LBA
        LDR R3,CD_SECS
        STR R3,CWD_SECS
        BR ret1

; =====================================================================================================================
; The built-in commands (y1os.c dir_of, file_of, cmd_*, load_file, run_prog, try_prog). Each takes its argument
; tail in R3; messages go to the raw console (eputs), output to stdout (cout).
; =====================================================================================================================
; dir_of / file_of: a directory / read handle on the path at R3 for the shell, with the messages -> ACC = R3 = it, 0.
dir_of: JSR resolve
        BRNZ do_1
        MVIW R3,S_NOTFOUND
        JSR eputs
        BR ret0
do_1:   LDA ERAW+24
        LDTI F_DIR
        BREQ do_2
        MVIW R3,S_NOTDIR
        JSR eputs
        BR ret0
do_2:   LDAI M_DIR
        BR open_ent
file_of:
        JSR resolve
        BRNZ fo_1
        MVIW R3,S_NOTFOUND
        JSR eputs
        BR ret0
fo_1:   LDA ERAW+24
        LDTI F_FILE
        BREQ fo_2
        MVIW R3,S_ISDIR
        JSR eputs
        BR ret0
fo_2:   LDA ERAW+18
        BRZ fo_3
        MVIW R3,S_TOOBIG
        JSR eputs
        BR ret0
fo_3:   LDAI M_READ
        BR open_ent

; dir [path]: name, <DIR> or size, and a file's load address; then the count.
cmd_dir:
        JSR dir_of
        BRZ rts
        STR R3,DR_H
        MVIW R3,0
        STR R3,DR_FILES
dr_lp:  LDR R3,DR_H
        MVIW R5,DENT
        JSR fs_readdir
        BRZ dr_end
        MVIW R3,DENT
        MVIB R4,12
dr_nm:  LDAVR R3
        JSR cout
        INCR R3
        DECR R4
        MVRLA R4
        BRNZ dr_nm
        LDAI 32
        JSR cout
        LDA DENT+24
        LDTI F_DIR
        BRNEQ dr_fl
        MVIW R3,S_DIRTAG
        JSR putstr
        BR dr_at
dr_fl:  LDA DENT+18
        BRZ dr_ln
        MVARL R3
        LDAI 0
        MVARH R3
        JSR putnum
        MVIW R3,S_X64K
        JSR putstr
dr_ln:  LDA DENT+16
        MVARL R3
        LDA DENT+17
        MVARH R3
        JSR putnum
dr_at:  LDA DENT+24
        LDTI F_FILE
        BRNEQ dr_nl
        LDA DENT+20
        MVARL R3
        LDA DENT+21
        MVARH R3
        MVRLA R3
        BRNZ dr_ad
        MVRHA R3
        BRZ dr_nl
dr_ad:  MVIW R3,S_AT
        JSR putstr
        LDA DENT+20
        MVARL R3
        LDA DENT+21
        MVARH R3
        JSR puthex
dr_nl:  JSR crlf
        LDR R3,DR_FILES
        INCR R3
        STR R3,DR_FILES
        BR dr_lp
dr_end: LDR R3,DR_H
        JSR fs_close
        LDR R3,DR_FILES
        JSR putnum
        MVIW R3,S_ENTRIES
        BR puts

; cd path
cmd_cd: JSR fs_chdir
        BRZ cc_nf
        LDTI 2
        BRNEQ rts
        MVIW R3,S_NOTDIR
        BR eputs
cc_nf:  MVIW R3,S_NOTFOUND
        BR eputs

; pwd
cmd_pwd:
        MVIW R3,CWDPATH
        BR puts

; cat path / type path: the file, sector by sector through SBUF, to stdout.
cmd_cat:
        JSR file_of
        BRZ rts
        STR R3,CT_H
ct_lp:  LDR R3,CT_H
        MVIW R5,SBUF
        JSR fs_read
        BRZ ct_end
        MOVRR R3,R4
        MVIW R3,SBUF
ct_o:   LDAVR R3
        JSR cout
        INCR R3
        DECR R4
        MVRLA R4
        BRNZ ct_o
        MVRHA R4
        BRNZ ct_o
        BR ct_lp
ct_end: LDR R3,CT_H
        BR fs_close

; load_file: the file at the path R3 -> its load address (whole sectors, inside $5000-$CFFF, not empty) -> ACC = 1,
; 0 (said why). E_* stay the file's.
load_file:
        JSR file_of
        BRZ ret0
        STR R3,LF_H
        LDR R4,E_LOAD           ; e_load < $5000, >= $D000, or e_secs > ($D000 - e_load) >> 9: refused
        MVRHA R4
        LDTI 50H
        BRLT lf_bad
        LDTI 0D0H
        BRLT lf_in
        BR lf_bad
lf_in:  MVRLA R4                ; ($D000 - e_load) >> 9 = the high byte of the difference >> 1
        BRZ lf_nb
        MVRHA R4
        MVAT
        LDAI 0CFH
        SUBT
        BR lf_d
lf_nb:  MVRHA R4
        MVAT
        LDAI 0D0H
        SUBT
lf_d:   SHR
        MVAT
        LDR R5,E_SECS
        MVRHA R5
        BRNZ lf_bad
        MVRLA R5
        BRGT lf_bad
        LDR R5,E_LEN            ; an empty file: refused (2026-09-23; it loaded a sector and `run` jumped into it)
        MVRLA R5
        BRNZ lf_ok
        MVRHA R5
        BRZ lf_bad
lf_ok:
        STR R4,LF_DST
lf_rd:  LDR R3,LF_H             ; while (fs_read(h, dst)) dst += 512
        LDR R5,LF_DST
        JSR fs_read
        BRZ lf_dn
        LDR R5,LF_DST
        MVRHA R5
        ADDI 2
        MVARH R5
        STR R5,LF_DST
        BR lf_rd
lf_dn:  LDR R3,LF_H
        JSR fs_close
        BR ret1
lf_bad: LDR R3,LF_H
        JSR fs_close
        MVIW R3,S_BADLOAD
        JSR eputs
        BR ret0

; load path: "loaded N bytes at $AAAA"
cmd_load:
        JSR load_file
        BRZ rts
        MVIW R3,S_LOADED
        JSR putstr
        LDR R3,E_LEN
        JSR putnum
        MVIW R3,S_BYTESAT
        JSR putstr
        LDR R3,E_LOAD
        JSR puthex
        BR crlf

; run_prog: the program in E_* (loaded): the tail at R3 -> ARGBUF (127 characters at most), call its exec address
; (JSRUR, R3 = R7 = it), then close what it left open and re-read the free pointer (pack lowers it).
run_prog:
        MVIW R4,ARGBUF
        MVIB R5,127
rp_cp:  MVRLA R5
        BRZ rp_z
        LDAVR R3
        BRZ rp_z
        STAVR R4
        INCR R3
        INCR R4
        DECR R5
        BR rp_cp
rp_z:   LDIVR R4,0
        LDR R7,E_EXEC
        MOVRR R7,R3
        JSRUR R7
        JSR close_all
        BR read_free

; run path [args]
cmd_run:
        STR R3,RU_PATH
        JSR word
        STR R3,RU_ARGS
        LDR R3,RU_PATH
        JSR load_file
        BRZ rts
        LDR R3,RU_ARGS
        BR run_prog

; save path addr len (hex): memory -> a new file with that load and exec address.
cmd_save:
        STR R3,SV_PATH
        JSR word
        STR R3,SV_A
        JSR word
        STR R3,SV_L
        LDR R3,SV_A
        LDAVR R3
        BRZ sv_use
        LDR R3,SV_L
        LDAVR R3
        BRZ sv_use
        LDR R3,SV_A
        JSR hexnum
        STR R4,SV_ADDR
        STR R4,CR_LOAD
        STR R4,CR_EXEC
        LDR R3,SV_L
        JSR hexnum
        STR R4,SV_LEN
        LDR R3,SV_PATH
        JSR fs_create
        BRNZ sv_ok
        MVIW R3,S_CANTMAKE
        BR eputs
sv_ok:  STR R3,SV_H
        LDR R4,SV_LEN
        STR R4,FW_N
        LDR R5,SV_ADDR
        JSR fs_write
        STR R3,SV_N
        LDR R3,SV_H             ; closed even after a short write
        JSR fs_close
        BRZ sv_err
        LDR R3,SV_N
        LDR R4,SV_LEN
        MVRLA R3
        MVAT
        MVRLA R4
        BRNEQ sv_err
        MVRHA R3
        MVAT
        MVRHA R4
        BRNEQ sv_err
        MVIW R3,S_SAVED
        JSR putstr
        LDR R3,SV_LEN
        JSR putnum
        MVIW R3,S_BYTES
        BR puts
sv_err: MVIW R3,S_WRITEERR
        BR eputs
sv_use: MVIW R3,S_SAVEUSE
        BR eputs

; del path / mkdir path / rmdir path
cmd_del:
        JSR fs_delete
        BRNZ rts
        MVIW R3,S_NOTAFILE
        BR eputs
cmd_mkdir:
        JSR fs_mkdir
        BRNZ rts
        MVIW R3,S_CANTMKDIR
        BR eputs
cmd_rmdir:
        JSR fs_rmdir
        BRNZ rts
        MVIW R3,S_NOTEMPTY
        BR eputs

; ren path newname
cmd_ren:
        STR R3,RE_PATH
        JSR word
        LDAVR R3
        BRNZ re_go
        MVIW R3,S_RENUSE
        BR eputs
re_go:  MOVRR R3,R5
        LDR R3,RE_PATH
        JSR fs_rename
        BRNZ rts
        MVIW R3,S_CANTREN
        BR eputs

; help / ?
cmd_help:
        MVIW R3,S_HELP1
        JSR puts
        MVIW R3,S_HELP2
        JSR puts
        MVIW R3,S_HELP3
        JSR puts
        MVIW R3,S_HELP4
        BR puts

; try_prog: the word at R3 (lower case) as a program: ACC = 1: /BIN/NAME, 0: NAME here (upper-cased, as the Makefile
; puts programs); the tail at R5 -> ACC = 1 it is one (loaded and run, or said why not), 0 it is not.
try_prog:
        STA TP_BIN
        STR R5,TP_ARGS
        JSR strlen
        MVRHA R4
        BRNZ ret0
        MVRLA R4
        LDTI 12
        BRGT ret0
        MVIW R4,TPBUF
        LDA TP_BIN
        BRZ tp_cp
        PUSHR R3
        MVIW R3,S_BIN
        JSR strcpy
        DECR R4                 ; onto the NUL
        POPR R3
tp_cp:  JSR strcpy
        MVIW R3,TPBUF
        JSR upper
        MVIW R3,TPBUF
        JSR resolve
        BRZ ret0
        LDA ERAW+24
        LDTI F_FILE
        BRNEQ ret0
        MVIW R3,TPBUF
        JSR load_file
        BRZ ret1
        LDR R3,TP_ARGS
        JSR run_prog
        BR ret1

; =====================================================================================================================
; The shell (y1os.c readline, run_cmd, split, pipename, stage, io_reset)
; =====================================================================================================================
; readline: a console line -> LINE (up to 128 characters, NUL-terminated); the ROM's UARTIN echoes; BS and DEL
; rub out ("\b \b" through stdout, the console at the prompt). Ends at LF, CR or NUL.
readline:
        MVIW R3,LINE            ; R3 = LINE + n (LINE is page-aligned: n = R3's low byte)
rl_lp:  JSR B_UARTIN
        BRZ rl_end
        LDTI 10
        BREQ rl_end
        LDTI 13
        BREQ rl_end
        LDTI 8
        BREQ rl_bs
        LDTI 127
        BREQ rl_bs
        MVAT
        MVRLA R3
        ANDI 80H                ; n < 128
        BRNZ rl_lp
        MVTA
        STAVR R3
        INCR R3
        BR rl_lp
rl_bs:  MVRLA R3
        BRZ rl_lp
        DECR R3
        LDAI 8
        JSR cout
        LDAI 32
        JSR cout
        LDAI 8
        JSR cout
        BR rl_lp
rl_end: LDIVR R3,0
        RET

; run_cmd: one command (a pipeline stage) at R3: its word lower-cased, then /BIN/NAME, the built-ins, NAME here
; -> ACC = 1 `exit`, 0 otherwise.
run_cmd:
        LDAVR R3
        BRZ ret0                ; `> F` alone: nothing to run
        STR R3,RC_CMD
        JSR word
        STR R3,RC_REST
        LDR R3,RC_CMD
        JSR lower
        LDR R3,RC_CMD
        MVIW R4,S_EXIT
        JSR streq
        BRNZ ret1
        LDR R3,RC_CMD           ; a /BIN program wins over a built-in of the same name
        LDR R5,RC_REST
        LDAI 1
        JSR try_prog
        BRNZ ret0
        MVIW R6,cmdtab
rc_lp:  LDAVR R6
        MVARH R4
        INCR R6
        LDAVR R6
        MVARL R4
        INCR R6
        MVRHA R4
        BRZ rc_no
        LDR R3,RC_CMD
        JSR streq
        BRNZ rc_hit
        INCR R6
        INCR R6
        BR rc_lp
rc_hit: LDAVR R6
        MVARH R7
        INCR R6
        LDAVR R6
        MVARL R7
        LDR R3,RC_REST
        JSRUR R7
        BR ret0
rc_no:  LDR R3,RC_CMD           ; NAME in the current directory
        LDR R5,RC_REST
        LDAI 0
        JSR try_prog
        BRNZ ret0
        MVIW R3,S_WHAT
        JSR eputs
        BR ret0
cmdtab: DW S_CDIR
        DW cmd_dir
        DW S_CCD
        DW cmd_cd
        DW S_CPWD
        DW cmd_pwd
        DW S_CCAT
        DW cmd_cat
        DW S_CTYPE
        DW cmd_cat
        DW S_CLOAD
        DW cmd_load
        DW S_CRUN
        DW cmd_run
        DW S_CSAVE
        DW cmd_save
        DW S_CDEL
        DW cmd_del
        DW S_CREN
        DW cmd_ren
        DW S_CMKDIR
        DW cmd_mkdir
        DW S_CRMDIR
        DW cmd_rmdir
        DW S_CHELP
        DW cmd_help
        DW S_CQ
        DW cmd_help
        DW 0

; split: LINE -> up to 4 commands split at '|' outside quotes: SEG[] (their text, trailing spaces cut), RIN[] and
; ROUT[] (the < and > / >> file names, 0 none, NUL-terminated where they stand), RAPP[] (1: >>) -> ACC = the count,
; 0 = a bad line (a clause without a name, a clause twice, a word after a clause, a 5th command).
split:  MVIW R3,LINE            ; R3 = p
        LDAI 0
        STA SP_N
sp_cmd: LDAVR R3                ; one command per pass: skip its leading spaces
        LDTI 32
        BRNEQ sp_bg
        INCR R3
        BR sp_cmd
sp_bg:   STR R3,SP_B
        MVIW R4,0
        STR R4,SP_RI
        STR R4,SP_RO
        LDAI 0
        STA SP_RA
        STA SP_Q
sp_tx:  LDAVR R3                ; the text: up to a | < > outside quotes
        STA SP_C
        BRZ sp_te
        LDTI 39
        BREQ sp_qt
        LDTI 34
        BREQ sp_qt
        LDA SP_Q
        BRNZ sp_tn
        LDA SP_C
        LDTI 124
        BREQ sp_te
        LDTI 60
        BREQ sp_te
        LDTI 62
        BREQ sp_te
sp_tn:  INCR R3
        BR sp_tx
sp_qt:  LDA SP_Q                ; a quote opens, or closes the one open
        BRNZ sp_q2
        LDA SP_C
        STA SP_Q
        BR sp_tn
sp_q2:  MVAT
        LDA SP_C
        BRNEQ sp_tn
        LDAI 0
        STA SP_Q
        BR sp_tn
sp_te:  MOVRR R3,R4             ; e = p; drop the trailing spaces; *e = 0
        LDR R5,SP_B
sp_tr:  MVRLA R4
        MVAT
        MVRLA R5
        BRNEQ sp_t1
        MVRHA R4
        MVAT
        MVRHA R5
        BREQ sp_t2
sp_t1:  DECR R4
        LDAVR R4
        INCR R4
        LDTI 32
        BRNEQ sp_t2
        DECR R4
        BR sp_tr
sp_t2:  LDIVR R4,0
sp_rd:  LDA SP_C                ; the redirect clauses, while c is < or >
        LDTI 60
        BREQ sp_r1
        LDTI 62
        BREQ sp_r1
        BR sp_seg
sp_r1:  LDIVR R3,0              ; *p++ = 0; ">>" appends
        INCR R3
        LDA SP_C
        LDTI 62
        BRNEQ sp_r2
        LDAVR R3
        LDTI 62
        BRNEQ sp_r2
        LDAI 1
        STA SP_RA
        LDIVR R3,0
        INCR R3
sp_r2:  LDAVR R3                ; the name: after any spaces, up to a space | < > or the end
        LDTI 32
        BRNEQ sp_r3
        INCR R3
        BR sp_r2
sp_r3:  MOVRR R3,R4
sp_r4:  LDAVR R3
        BRZ sp_r5
        LDTI 32
        BREQ sp_r5
        LDTI 124
        BREQ sp_r5
        LDTI 60
        BREQ sp_r5
        LDTI 62
        BREQ sp_r5
        INCR R3
        BR sp_r4
sp_r5:  MVRLA R3                ; no name: bad
        MVAT
        MVRLA R4
        BRNEQ sp_r6
        MVRHA R3
        MVAT
        MVRHA R4
        BREQ sp_bad
sp_r6:  LDA SP_C
        LDTI 60
        BRNEQ sp_r7
        LDR R5,SP_RI            ; a second < : bad
        MVRHA R5
        BRNZ sp_bad
        STR R4,SP_RI
        BR sp_r8
sp_r7:  LDR R5,SP_RO            ; a second > : bad
        MVRHA R5
        BRNZ sp_bad
        STR R4,SP_RO
sp_r8:  LDAVR R3                ; the spaces after it become NULs
        LDTI 32
        BRNEQ sp_r9
        LDIVR R3,0
        INCR R3
        BR sp_r8
sp_r9:  LDAVR R3
        STA SP_C
        BR sp_rd
sp_seg: LDA SP_N                ; seg[n] = b, rin[n] = ri, rout[n] = ro, rapp[n] = ra; n++
        SHL
        MVAT
        ADDI (SEG).0
        MVARL R4
        LDAI (SEG).1
        MVARH R4
        LDR R5,SP_B
        MVRHA R5
        STAVR R4
        INCR R4
        MVRLA R5
        STAVR R4
        MVTA
        ADDI (RIN).0
        MVARL R4
        LDR R5,SP_RI
        MVRHA R5
        STAVR R4
        INCR R4
        MVRLA R5
        STAVR R4
        MVTA
        ADDI (ROUT).0
        MVARL R4
        LDR R5,SP_RO
        MVRHA R5
        STAVR R4
        INCR R4
        MVRLA R5
        STAVR R4
        LDA SP_N
        ADDI (RAPP).0
        MVARL R4
        LDA SP_RA
        STAVR R4
        LDA SP_N
        ADDI 1
        STA SP_N
        LDA SP_C                ; the end of the line: the count
        BRZ sp_ret
        LDTI 124                ; a word after a clause, or a fifth command: bad
        BRNEQ sp_bad
        LDA SP_N
        LDTI 4
        BREQ sp_bad
        LDIVR R3,0
        INCR R3
        BR sp_cmd
sp_ret: LDA SP_N
        RET
sp_bad: LDAI 0
        RET

; pipename: ACC = k -> R3 = the pipe file stage k writes: /PIPE0.TMP (k even), /PIPE1.TMP (k odd). Clobbers ACC.
pipename:
        ANDI 1
        BRNZ pn_p1
        MVIW R3,S_PIPE0
        RET
pn_p1:  MVIW R3,S_PIPE1
        RET

; stage: open stage KSEG's input and output (of NSEG) -> ACC = 1 (SI_H, SO_H set), 0 cannot (said so).
; Input: its < file, else (k > 0) the pipe file the stage before wrote (none: SI_EMPTY), else the console.
; Output: its > / >> file (then an older pipe file for the next stage goes), else (not the last) a pipe file,
; else the console.
stage:  LDA KSEG
        SHL
        ADDI (RIN).0
        MVARL R4
        LDAI (RIN).1
        MVARH R4
        LDAVR R4
        MVARH R3
        INCR R4
        LDAVR R4
        MVARL R3
        MVRHA R3
        BRZ st_nin
        JSR fs_open
        STA SI_H
        BRNZ st_out
        MVIW R3,S_CANTREAD
        JSR eputs
        BR ret0
st_nin: LDA KSEG
        BRZ st_out
        SUBI 1
        JSR pipename
        JSR fs_open
        BRNZ st_si
        LDAI SI_EMPTY
st_si:  STA SI_H
st_out: LDA KSEG
        SHL
        ADDI (ROUT).0
        MVARL R4
        LDAI (ROUT).1
        MVARH R4
        LDAVR R4
        MVARH R3
        INCR R4
        LDAVR R4
        MVARL R3
        MVRHA R3
        BRNZ st_fl
        JSR st_more             ; no > file: a pipe to the next command, or the console
        BRZ ret1
        LDA KSEG
        JSR pipename
        MVIW R4,0
        STR R4,CR_LOAD
        STR R4,CR_EXEC
        JSR fs_create
        BR st_set
st_fl:  LDA KSEG
        ADDI (RAPP).0
        MVARL R4
        LDAI (RAPP).1
        MVARH R4
        LDAVR R4
        BRZ st_cr
        JSR fs_append
        BR st_fd
st_cr:  MVIW R4,0
        STR R4,CR_LOAD
        STR R4,CR_EXEC
        JSR fs_create
st_fd:  STA ST_H
        JSR st_more             ; the next stage reads an empty input, not a stale pipe file
        BRZ st_hh
        LDA KSEG
        JSR pipename
        JSR fs_delete
st_hh:   LDA ST_H
st_set: STA SO_H
        BRNZ ret1
        MVIW R3,S_CANTWRITE
        JSR eputs
        BR ret0
st_more: LDA KSEG               ; -> ACC = 1 when k + 1 < n
        ADDI 1
        MVAT
        LDA NSEG
        BRGT sm_1
        LDAI 0
        RET
sm_1:   LDAI 1
        RET

; io_reset: back to the console; closing a written file registers it.
io_reset:
        LDA SO_H
        MVARL R3
        LDAI 0
        STA SO_H
        MVARH R3
        MVRLA R3
        BRZ io_i
        JSR fs_close
io_i:   LDA SI_H
        MVARL R3
        LDAI 0
        STA SI_H
        MVARH R3
        MVRLA R3
        BRZ rts
        BR fs_close

; =====================================================================================================================
; The messages (os/strings.txt, made into numeric DB lines by os/mkstrings.py)
; =====================================================================================================================
        INCLUDE y1os_str.inc
os_end:                         ; the end of the image: it must stay below $4A00 (the Makefile checks)

; =====================================================================================================================
; The OS's RAM, $4A00-$4FFF (not in the image; cleared at boot)
; =====================================================================================================================
        ORG 4A00H
LINE:       DS 130              ; the command line (page-aligned: readline counts with the low byte)
CWDPATH:    DS 64               ; the current path, for the prompt and GETCWD (inside one page: path_pop/push)
PBUF:       DS 64               ; a working copy of a path (parent_of) / the path to restore (fs_chdir)
ERAW:       DS 32               ; the entry the last lookup found, as on the card (ENTRY, RESOLVE copy it out)
DENT:       DS 32               ; cmd_dir's entry
WNAME:      DS 13               ; the write handle's name
TPBUF:      DS 20               ; try_prog's "/BIN/NAME"
        ORG 4B80H
SEG:        DS 8                ; split's result: the pipeline's commands (words; SEG..RAPP inside one page)
RIN:        DS 8                ; their < file names (0 none)
ROUT:       DS 8                ; their > / >> file names
RAPP:       DS 4                ; 1: that > is >>
        ORG 4C00H
SBUF:       DS 512              ; the OS's sector buffer: directory scans, the boot block (512-aligned)
        ORG 4E00H
HTAB:       DS 80               ; the handle records, HTAB + 16h for h = 0..4 (page-aligned; 0 is never opened)
; words (big-endian)
FREE_LBA:   DS 2                ; the volume's free-sector pointer (boot block bytes 4-5), kept in step on the card
CWD_LBA:    DS 2                ; the current directory's extent
CWD_SECS:   DS 2
RLBA:       DS 2                ; the directory resolve() walked last
RSECS:      DS 2
P_LBA:      DS 2                ; parent_of(): the directory that holds the leaf
P_SECS:     DS 2
LEAF:       DS 2                ; parent_of(): -> the leaf (in PBUF)
E_LBA:      DS 2                ; the entry the last lookup found (flags and length's 64K count: ERAW+24, ERAW+18)
E_SECS:     DS 2
E_LEN:      DS 2
E_LOAD:     DS 2
E_EXEC:     DS 2
E_SLBA:     DS 2                ; where it sits: sector and offset (0/0: the root / current directory itself)
E_OFF:      DS 2
W_DLBA:     DS 2                ; the write handle's directory, header, and the file it replaces (0: none)
W_DSECS:    DS 2
W_LOAD:     DS 2
W_EXEC:     DS 2
W_OSLBA:    DS 2
W_OOFF:     DS 2
FI_LBA:     DS 2                ; find_in / find_slot
FI_SECS:    DS 2
FI_LEFT:    DS 2
FI_NM:      DS 2
RS_P:       DS 2                ; resolve
SE_LBA:     DS 2                ; set_entry's fields
SE_LEN:     DS 2
SE_LOAD:    DS 2
SE_EXEC:    DS 2
CR_LOAD:    DS 2                ; fs_create's load and exec
CR_EXEC:    DS 2
RD_BUF:     DS 2                ; fs_readdir
RD_LEN:     DS 2
FW_H:       DS 2                ; fs_write
FW_P:       DS 2
FW_N:       DS 2
FW_I:       DS 2
CL_REC:     DS 2                ; fs_close
CL_CUR:     DS 2
CL_LBA:     DS 2
AP_PATH:    DS 2                ; fs_append
AP_OLBA:    DS 2
AP_LEN:     DS 2
AP_N:       DS 2
AP_BASE:    DS 2
AP_S:       DS 2
MK_NL:      DS 2                ; fs_mkdir
RM_SLBA:    DS 2                ; fs_rmdir
RM_OFF:     DS 2
RM_LBA:     DS 2
RM_LEFT:    DS 2
RV_BUF:     DS 2                ; fs_resolve
RN_NEW:     DS 2                ; fs_rename
RN_SLBA:    DS 2
RN_OFF:     DS 2
RN_DLBA:    DS 2
RN_DSECS:   DS 2
CD_P:       DS 2                ; fs_chdir
CD_LBA:     DS 2
CD_SECS:    DS 2
CD_N:       DS 2
PU_NM:      DS 2                ; path_push
PU_N:       DS 2
DR_H:       DS 2                ; cmd_dir
DR_FILES:   DS 2
CT_H:       DS 2                ; cmd_cat
LF_H:       DS 2                ; load_file
LF_DST:     DS 2
RU_PATH:    DS 2                ; cmd_run
RU_ARGS:    DS 2
SV_PATH:    DS 2                ; cmd_save
SV_A:       DS 2
SV_L:       DS 2
SV_ADDR:    DS 2
SV_LEN:     DS 2
SV_H:       DS 2
SV_N:       DS 2
RE_PATH:    DS 2                ; cmd_ren
TP_ARGS:    DS 2                ; try_prog
RC_CMD:     DS 2                ; run_cmd
RC_REST:    DS 2
SP_B:       DS 2                ; split
SP_RI:      DS 2
SP_RO:      DS 2
; bytes
WH:         DS 1                ; the write handle in use, 0 none (CREATE and MKDIR allocate at the free pointer)
SI_H:       DS 1                ; the shell's redirection: 0 = the console, else the < file / pipe handle
SO_H:       DS 1                ;   (SI_EMPTY: an empty input) and the > / >> / pipe handle
NM_N:       DS 1                ; name_is's counts
NM_SP:      DS 1
SE_FLAG:    DS 1
PC_BYTE:    DS 1                ; fs_putc's byte
OE_MODE:    DS 1                ; open_ent
OE_H:       DS 1
CL_OK:      DS 1                ; fs_close
CA_H:       DS 1                ; close_all
CD_R:       DS 1                ; fs_chdir's result
PN_LEAD:    DS 1                ; putnum: a digit printed
TP_BIN:     DS 1                ; try_prog
SP_N:       DS 1                ; split
SP_C:       DS 1
SP_Q:       DS 1
SP_RA:      DS 1
NSEG:       DS 1                ; the shell: commands in the line, the one running, `exit` seen
KSEG:       DS 1
QUIT:       DS 1
ST_H:       DS 1                ; stage
ram_end:                        ; must stay below $5000 (the programs)
        END 1000H
