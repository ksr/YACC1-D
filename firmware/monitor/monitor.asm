;
; Basic Interpreter Entry points
;
basic_list:   EQU 0e000h
basic_run:    EQU 0e010h
basic_cold:   EQU 0e020h
basic_test:   EQU 0e030h
basic_interprter: EQU 0e040h
basic_parse:  EQU 0e050h
basic_copy:   EQU 0e060h
;
; Hardware info
;
UARTA0:       EQU 000h
UARTA1:       EQU 008h
UARTA2:       EQU 010h
UARTA3:       EQU 018h
UARTA4:       EQU 020h
UARTA5:       EQU 028h
UARTA6:       EQU 030h
UARTA7:       EQU 038h

SWITCHLED:    EQU 001H
LCDENABLE:    EQU 002H
LCDREGISTER:  EQU 004H
UARTCS:       EQU 040H
TIL311:       EQU 080H

CNTL-PORT:    EQU "P0"
DATAPORT:     EQU "P1"

;
; MONITOR MODES
;
NOMODE:       EQU 0
EXAMINEMODE:  EQU 1
DUMPMODE:     EQU 2
BLOCKMODE:    EQU 3
FILLMODE:     EQU 4
LOADMODE:     EQU 5         ; 2026-09-23: after a ':' load, CR/LF at the prompt do nothing

;
; Monitor variables 0x0f00 - 0x0fff
;
monmode:        EQU 0f00h
continue_addr:  EQU 0f02h
lderr:          EQU 0f01h    ; 2026-09-23: nonzero when a record of the current ':' load failed
interupt_cnt:   EQU 0f04h
;
; CompactFlash driver variables (YACC1-D 2026-09-22) and the OS/program argument buffer
;
CFLBA0:         EQU 0f10h    ; sector number for CFREAD/CFWRITE, low byte
CFLBA1:         EQU 0f11h
CFLBA2:         EQU 0f12h    ; high byte (24-bit LBA)
ARGBUF:         EQU 0f40h    ; 64 bytes: the OS leaves a program's command tail here (NUL-terminated)
OSBASE:         EQU 1000h    ; where the boot command loads the OS image (LBA 1..OSCNT) and calls it
line_buffer:    EQU 0f80h    ; 112 bytes long max ($0FF0-$0FFF are the video variables since 2026-09-25)
;
; Video card (YACC1-D 2026-09-25): MC6845 CRTC + IDT7134 dual-port RAM in the $D000 block (docs/cards/video.md).
; The driver is always in the ROM; VIDAUTO decides whether reset also starts it. Until the card is debugged it does
; not: reset only probes $D000 (VIDPRES, the banner says VIDEO CARD FOUND) and homes the cursor variables; V I
; initialises the CRTC and clears the screen, V M1 (or Y1/OS's `video on`) turns the mirroring on.
;
VIDAUTO:        EQU 0        ; 1 = reset also runs V I (CRTC table, clear, home) and sets VIDMIR when a card is found
VIDRAM:         EQU 0d000h   ; display RAM, CPU side (A11 = 0); its first byte is the probe byte
VIDSIZE:        EQU 2048     ; the RAM the CPU reaches (IC15 A11R grounded): VIDRAM..VIDRAM+2047
VCOLS:          EQU 80       ; screen geometry: 80 x 24 = 1,920 bytes of the 2K, one byte per character
VROWS:          EQU 24       ;   (VCOLS*(VROWS-1) must be a multiple of 8 and at most 2,040: the scroll's loop)
VCRTCA:         EQU 0d800h   ; 6845 address register: A11 = 1, A1 = 0, A0 = 0 (the netlist reading of the card; the
VCRTCD:         EQU 0d802h   ;   card README says $D400/$D402 - one edit here). Data register: A1 = 1, after the
                             ;   RS-to-A1 bench fix (hardware/cards/video/docs/fix-6845-register-select.md)
VIDPRES:        EQU 0ff0h    ; 1 = display RAM answered at VIDRAM at reset (or at the last V P)
VIDMIR:         EQU 0ff1h    ; nonzero = CHAROUT/UARTOUT also write to the screen (only while VIDPRES is 1)
VIDCUR:         EQU 0ff2h    ; nonzero = keep the CRTC's cursor (R14/R15) at the text cursor (set by V I)
VROW:           EQU 0ff3h    ; text cursor row 0..VROWS-1
VCOL:           EQU 0ff4h    ; text cursor column 0..VCOLS-1
VCHAR:          EQU 0ff5h    ; the driver's scratch byte
VLINE:          EQU 0ff6h    ; word ($0FF6 high, $0FF7 low): the address of the cursor row's first byte


;
; Setup Stack, use R1 0eff -> down to 0c00 (but no checking)
;
STACK: EQU 0EFFh

;
; remap eprom from 0x0000 to 0xf000 by initial access to 0xf003 via BRanch
;
         ORG 0f000h
         BR eprom
         ORG 0f003h
eprom:
;
; Setup Stack
;
         MVIW R1,STACK

; SERIAL OUT SETUP
;
         OUTI  P0,(UARTA3!UARTCS)
         OUTI  P1,080H

         OUTI  P0,(UARTA0!UARTCS)
;         OUTI  P1,12 ;9600
         OUTI P1,3 ;38400

         OUTI  P0,(UARTA1!UARTCS)
         OUTI  P1,00

         OUTI  P0,(UARTA3!UARTCS)
         OUTI  P1,03H

; Set intial monitor mode

;         MVIB R6,NOMODE

          LDAI NOMODE
          STA MONMODE
          ldai 05h
          sta interupt_cnt
          JSR vidreset     ; 2026-09-25: probe the video card, home its cursor (starts it only if VIDAUTO)
;
; Main
;
          JSR lblink
          MVIW R7,hello
          JSR stringout
          LDA VIDPRES
          BRZ novidmsg
          MVIW R7,MSGVIDEO
          JSR stringout
novidmsg:
          JSR basic_cold   ; initialize basic interpreter
                           ; hack should this pass in token buffer ptr
;
; additional proof of life
;
; show first 16 bytes of ROM & REGISTERS
;
         MVIW R7,0f000h
         JSR showaddr
         JSR show16
         JSR showregs
         MVIW R7,CRLF
         JSR stringout
;
; show test code addr to use with go command
;
         MVIW R7,tttt
         JSR showaddr
         MVIW R7,CRLF
         JSR stringout
;
; if INPUT high start the monitor
;
        iaddr isrcode
        INTE
        BRINH cmdloop
;
; else run test/code below at completetion blink OUT LED jump to cmdloop
;
tttt:
        MVIW R7,TESTMSG
        JSR stringout
;
; Tests to be run at startup
;

;
; startup tests complete
;
        BR cmdloop
;
;
;
; (the T-menu bench tests, 1,062 bytes, were removed 2026-09-22 to make room for the CF driver and the boot command;
;  they are in git history and in tests/assembler/history-2020/)
; added for emulator eat cr
eat_nl:
;1      BRDEV eat_nl_done
;1      PUSH
;1      JSR uartin
;1      pop
eat_nl_done:
      ret
;
; Output Prompt
:

cmdloop:
      MVIW R7,PROMPT
      JSR stringout
;
;
; Input test
;
;intest:
;      JSR uartin
;      jsr showbytea
;      BR intest
;
; end test
;
      JSR uartin
      JSR toupper

;
; added for emulator eat cr
;
      jsr eat_nl
      LDTI 'H'
      BRNEQ testexamine
      MVIW R7,CRLF
      JSR stringout
      MVIW R7,helpmenu
      JSR stringout
      BR cmdloop

testexamine:
      LDTI ':'          ; 2026-09-23: an Intel-hex record starts load mode
      BREQ hexload
      LDTI '0'
      BREQ cmd_exit
      LDTI 'B'
      BREQ dumpblock
      LDTI 'C'
      BREQ cmd_basic_copy
      LDTI 'D'
      BREQ dump
      LDTI 'E'
      BREQ examine
      LDTI 'F'
      BREQ fillblock
      LDTI 'G'
      BREQ go
      LDTI 'O'
      BREQ boot
      ldti 'I'
      BREQ interpreter
      LDTI 'L'
      BREQ cmd_basiclist
      LDTI 'P'
      BREQ cmd_basicparse
      LDTI 'R'
      BREQ dumpreg
      LDTI 'V'          ; 2026-09-25: the video unit
      BREQ cmd_video
      LDTI 'Y'
      BREQ cmd_basic_test
      LDTI 'Z'
      BREQ cmd_basic
      LDTI 0Dh        ; hardware continue
      BREQ continue
;
; add for emulator
; hardware sends 0dh on CR but emulator sends 0dh 0ah
; code at top of loop eats the 0dh if running in emulator
; so continue on 0ah as well
;
      LDTI 0ah      ; emulator continue
      BREQ continue

      MVIW R7,CRLF

      JSR stringout

      MVIW R7,ERROR
      JSR stringout

      MVIW R7,helpmenu
      JSR stringout
      BR cmdloop
;
continue:

;       MVRLA R6
       LDA MONMODE

       LDTI BLOCKMODE
       BREQ dumpblockcont

       LDTI DUMPMODE
       BREQ dumpcont

       LDTI EXAMINEMODE
       BREQ examinecont

       LDTI FILLMODE
       BREQ fillcont
       BR cmdloop

stop:   BR stop

cmd_exit:
      BRDEV stop
      DB 0

cmd_basic:
        MVIW R7,CRLF
        JSR stringout
       jsr basic_run
       BR cmdloop

cmd_basicparse:
        ;build input string
        ;point register to BUFFER
        ;loop fetch chars
        ;until CR
        ;be sure line ends with a NULL or CR
        ;what does parse require???
        MVIW R7,BASIC_PARSEMSG
        JSR stringout

        mviw r3,line_buffer
parse_inputloop:
        jsr uartin
        stavr r3
        incr r3
        ldti 0ah  ;1 changed from 0a to 0D for new emulator code, changed back
;       halt
        brneq parse_inputloop
        mviw r7,line_buffer
        jsr show16
        mviw r7,line_buffer
        JSR BASIC_PARSE
        mviw r7,0400H
;        jsr show256
        BR cmdloop
do_parse:
        JSR basic_parse
        BR cmdloop

interpreter:
        JSR BASIC_INTERPRTER
        BR CMDLOOP

cmd_basiclist:
        MVIW R7,CRLF
        JSR stringout
        JSR basic_list
        BR cmdloop

cmd_basic_copy:
        MVIW R7,CRLF
        JSR stringout
        JSR basic_copy
        BR cmdloop

cmd_basic_test:
        MVIW R7,CRLF
        JSR stringout
        JSR basic_test
        BR cmdloop

dumpblock:
;      MVIB R6,BLOCKMODE
       LDTI BLOCKMODE
       STT monmode

       MVIW R7,DUMPBLOCKMSG
       JSR stringout
       jsr getaddress
       str r7,continue_addr
       MVIW R7,CRLF
       JSR stringout

dumpblockcont:
       ldr r7,continue_addr
       jsr show256
       str r7,continue_addr
       BR cmdloop
;
; dump 16 bytes on 16 byte boundry
;
dump:
;       MVIB R6,DUMPMODE
       LDTI DUMPMODE
       STT monmode
       MVIW R7,DUMPMSG
       JSR stringout
       jsr getaddress
       str r7,continue_addr
       MVIW R7,CRLF
       JSR stringout

dumpcont:
       ldr r7,continue_addr
       jsr showaddr
       jsr show16
       str r7,continue_addr
       BR cmdloop

examine:
;       MVIB R6,EXAMINEMODE
      LDTI EXAMINEMODE
      STT monmode
      MVIW R7,EXAMINEMSG
      JSR stringout
      jsr getaddress
      str r7,continue_addr
      MVIW R7,CRLF
      JSR stringout

examinecont:
      ldr r7,continue_addr
      JSR showaddr
      LDAI ' '
      JSR uartout

      JSR SHOWBYTE

      JSR uartin
      LDTI 01bh
      BREQ examdone
      LDTI '-'
      BREQ examdone
      LDTI 0dh
      BREQ examnext
      LDTI 0ah
      BREQ examnext
      JSR getbytec      ; 2026-09-25: the shared two-digit reader
      STAVR R7

examnext:
      INCR R7
      str r7,continue_addr
      LDAI 0ah
      JSR uartout
      LDAI 0dh
      JSR uartout
      BR examinecont

examdone:
      MVIW R7,CRLF
      JSR stringout
      BR cmdloop

fillblock:
;       MVIB R6,FILLMODE
       LDTI FILLMODE
       STT monmode

       MVIW R7,FILLMSG
       JSR stringout
       jsr getaddress
       STR r7,continue_addr
       MVIW R7,CRLF
       JSR stringout

fillcont:
      ldr r7,continue_addr
      jsr showaddr
      MVIW R7,CRLF
      JSR stringout
      ldr r7,continue_addr
morefill:
      LDAI 0
      STAVR R7
      INCR R7
      MVRLA R7
      ANDI  0FFH
      BRNZ morefill
      str r7,continue_addr
      LDAI 0ah
      JSR uartout
      LDAI 0dh
      JSR uartout
      BR cmdloop


go:
      MVIW R7,GOMSG
      JSR stringout
      jsr getaddress
;
; YACC1-D 2026-09-22: was BRVR R7, which is an INDIRECT jump (PC <- the word AT the address, see the
; microcode: branch() fetches the target through R7 like BR fetches its operand through the PC), so G jumped
; through whatever was stored at AAAA. JSRUR R7 jumps TO AAAA and pushes a return address: the program ends
; with RET and lands back in the command loop.
;
      JSRUR R7
      BR cmdloop

dumpreg:
      JSR showregs
;      MVIB R6,NOMODE
      LDTI NOMODE
      STT monmode

      BR cmdloop

;
; ---- CompactFlash driver (YACC1-D 2026-09-22) -----------------------------------------------------------
; The card sits on two ports: P8 = register-select latch (ATA task-file register 0-7), P9 = data.
; 8-bit True IDE mode. Registers: 0 data, 1 error/feature, 2 sector count, 3-5 LBA0-2, 6 drive/head, 7 status/cmd.
; Entry points (also BIOS vectors at 0FFECh..): cfinit  ACC = 0 ok / 1 error (absent card times out);
;   cfread   sector CFLBA0..2 -> (R7), R7 += 512, ACC = 0 ok / 1 error;   cfwrite  (R7) -> sector, R7 += 512, same;
;   R6 and TMP are clobbered. const  ACC = 1 when a console byte waits (0 otherwise).
;
CFSEL_DATA:  EQU 0
CFSEL_FEAT:  EQU 1
CFSEL_SCNT:  EQU 2
CFSEL_LBA0:  EQU 3
CFSEL_LBA1:  EQU 4
CFSEL_LBA2:  EQU 5
CFSEL_HEAD:  EQU 6
CFSEL_CMD:   EQU 7
;
; wait while BSY (bit 7), bounded to 65536 polls; returns the status in ACC
cfwait:
        MVIW R6,0
cfwaitl:
        OUTI P8,CFSEL_CMD
        INP P9
        ANDI 080H
        BRZ cfwaitd
        DECR R6
        MVRLA R6
        BRNZ cfwaitl
        MVRHA R6
        BRNZ cfwaitl
cfwaitd:
        OUTI P8,CFSEL_CMD
        INP P9
        RET
;
; wait until DRQ (bit 3), bounded; returns the status in ACC
cfdrq:
        MVIW R6,0
cfdrql:
        OUTI P8,CFSEL_CMD
        INP P9
        ANDI 008H
        BRNZ cfdrqd
        DECR R6
        MVRLA R6
        BRNZ cfdrql
        MVRHA R6
        BRNZ cfdrql
cfdrqd:
        OUTI P8,CFSEL_CMD
        INP P9
        RET
;
cfinit:
        JSR cfwait
        OUTI P8,CFSEL_HEAD
        OUTI P9,0E0H            ; LBA mode, drive 0
        OUTI P8,CFSEL_FEAT
        OUTI P9,001H            ; feature 1: 8-bit transfers
        OUTI P8,CFSEL_CMD
        OUTI P9,0EFH            ; SET FEATURES
        JSR cfwait
        ANDI 001H               ; ERR bit; an absent card reads FFh and times out -> 1
        RET
;
; task file <- CFLBA0..2, LBA mode, one sector
cfsetl:
        OUTI P8,CFSEL_LBA0
        LDA CFLBA0
        OUTA P9
        OUTI P8,CFSEL_LBA1
        LDA CFLBA1
        OUTA P9
        OUTI P8,CFSEL_LBA2
        LDA CFLBA2
        OUTA P9
        OUTI P8,CFSEL_HEAD
        OUTI P9,0E0H
        OUTI P8,CFSEL_SCNT
        OUTI P9,1
        RET
;
cfread:
        JSR cfwait
        JSR cfsetl
        OUTI P8,CFSEL_CMD
        OUTI P9,020H            ; READ SECTORS
        JSR cfdrq
        ANDI 008H
        BRZ cferr
        OUTI P8,CFSEL_DATA
        MVIW R6,512
cfrdl:
        INP P9
        STAVR R7
        INCR R7
        DECR R6
        MVRLA R6
        BRNZ cfrdl
        MVRHA R6
        BRNZ cfrdl
        LDAI 0
        RET
cferr:
        LDAI 1
        RET
;
cfwrite:
        JSR cfwait
        JSR cfsetl
        OUTI P8,CFSEL_CMD
        OUTI P9,030H            ; WRITE SECTORS
        JSR cfdrq
        ANDI 008H
        BRZ cferr
        OUTI P8,CFSEL_DATA
        MVIW R6,512
cfwrl:
        LDAVR R7
        OUTA P9
        INCR R7
        DECR R6
        MVRLA R6
        BRNZ cfwrl
        MVRHA R6
        BRNZ cfwrl
        JSR cfwait
        ANDI 001H
        RET
;
; const: ACC = 1 when a console byte is waiting. The emulator's port-2 console has no status: always ready.
const:
        BRDEV consthw
        LDAI 1
        RET
consthw:
        OUTI P0,(UARTCS!UARTA5)
        INP P1
        ANDI 001H
        RET
;
; O command: boot. Read the boot block (LBA 0) to OSBASE, check 'P8' and OSCNT, read OSCNT sectors from LBA 1
; to OSBASE and call it; the OS returns with RET.
;
;
; ':' - Intel-hex loader (YACC1-D 2026-09-23). A ':' at the prompt starts load mode: the rest of the record is read
; without echo (uartinne), its bytes stored from its address on, and the record acknowledged with one character:
;   .  stored and the checksum is right
;   ?  a bad hex digit or a bad checksum
;   !  refused or not verified: an address outside $1000-$DFFF (the monitor's page, the stack and the ROM are
;      protected; any write to $E000-$FFFF would reach the 28C64, review M2), or the byte read back differently
; Between records everything up to the next ':' is skipped (CR, LF, blanks), so an assembler .img can be pasted into
; a terminal or sent as is; ESC (or a NUL, the emulators' end of input) abandons, between records or inside one. The end record (type 01) prints
; LOADED, or LOADED WITH ERRORS when any record failed, and returns to the prompt. Records of other types are read
; and checked but not stored. Host side: tools/monload.py paces the characters (the UART has no FIFO enabled: one
; character of buffering) and waits for each acknowledgement. Registers: R3 checksum, R4 count, R5 type,
; R6 record status (0 ok, 1 bad hex, 2 refused/unverified), R7 the address; never R2.
;
hexload:
        LDTI  LOADMODE
        STT   monmode
        LDTI  0
        STT   lderr
ldrec:
        MVIW  R3,0
        MVIW  R4,0
        MVIW  R6,0
        JSR   ldbyte            ; byte count
        MVARL R4
        JSR   ldbyte            ; address high
        MVARH R7
        JSR   ldbyte            ; address low
        MVARL R7
        JSR   ldbyte            ; record type
        MVARL R5
ldloop:
        MVRLA R4
        BRZ   ldsum
        JSR   ldbyte
        PUSH
        MVRLA R5
        BRNZ  ldskip            ; not a data record: check only
        MVRHA R7                ; protect everything outside $1000-$DFFF
        LDTI  00fh
        BRGT  ldlowok
        BR    ldref
ldlowok:
        LDTI  0dfh
        BRGT  ldref
        POP
        STAVR R7
        MVAT
        LDAVR R7                ; read it back
        BREQ  ldnext
        MVIW  R6,2
        BR    ldnext
ldref:
        MVIW  R6,2
ldskip:
        POP
ldnext:
        INCR  R7
        DECR  R4
        BR    ldloop
ldsum:
        JSR   ldbyte            ; the checksum: the record's bytes now sum to zero
        MVRLA R6
        LDTI  1
        BREQ  ldbadrec
        MVRLA R3
        BRNZ  ldbadrec
        MVRLA R6
        BRNZ  ldrefrec
        MVRLA R5
        LDTI  1
        BREQ  ldeof
        LDAI  '.'
        JSR   uartout
        BR    ldwait
ldbadrec:
        LDAI  '?'
        BR    ldflag
ldrefrec:
        LDAI  '!'
ldflag:
        JSR   uartout
        LDTI  1
        STT   lderr
        MVRLA R5
        LDTI  1
        BREQ  ldeof
ldwait:
        JSR   uartinne          ; skip to the next ':'
        BRZ   ldabort
        LDTI  ':'
        BREQ  ldrec
        LDTI  01bh
        BREQ  ldabort
        BR    ldwait
ldeof:
        LDA   lderr
        BRNZ  ldeofbad
        MVIW  R7,MSGLOADED
        JSR   stringout
        BR    cmdloop
ldeofbad:
        MVIW  R7,MSGLOADERR
        JSR   stringout
        BR    cmdloop
ldabort:
        MVIW  R7,MSGLOADAB
        JSR   stringout
        BR    cmdloop
;
; ldbyte: two hex digits (no echo) -> ACC, added into the checksum R3; a bad digit sets R6 = 1 and gives 0
;
ldbyte:
        JSR   ldhex
        SHL
        SHL
        SHL
        SHL
        ANDI  0f0h
        PUSH
        JSR   ldhex
        MVAT
        POP
        ORT
        PUSH
        MVAT
        MVRLA R3
        ADDT
        MVARL R3
        POP
        RET
;
; ldhex: one hex digit (no echo) -> ACC 0..15; anything else sets R6 = 1 and gives 0
;
ldhex:
        JSR   uartinne
        BRZ   ldhexab           ; NUL (the emulators' end of input) or ESC abandon, even inside a record
        LDTI  01bh
        BREQ  ldhexab
        JSR   toupper
        LDTI  '0'
        BRLT  ldhexbad
        LDTI  '9'
        BRGT  ldhexaf
        SUBI  '0'
        RET
ldhexaf:
        LDTI  'A'
        BRLT  ldhexbad
        LDTI  'F'
        BRGT  ldhexbad
        SUBI  037h
        RET
ldhexbad:
        MVIW  R6,1
        LDAI  0
        RET
ldhexab:                        ; out of any depth of ldbyte/ldhex: the loader runs from the command loop, whose
        MVIW  R1,STACK          ; stack is empty, so resetting it drops the return addresses and pushed bytes
        BR    ldabort
MSGLOADED: DB 0ah,0dh,"LOADED",0ah,0dh,0
MSGLOADERR: DB 0ah,0dh,"LOADED WITH ERRORS",0ah,0dh,0
MSGLOADAB: DB 0ah,0dh,"LOAD ABANDONED",0ah,0dh,0
;
boot:
        MVIW R7,MSGBOOT
        JSR stringout
        JSR cfinit
        BRNZ bootfail
        LDAI 0
        STA CFLBA0
        STA CFLBA1
        STA CFLBA2
        MVIW R7,OSBASE
        JSR cfread
        BRNZ bootfail
        LDA OSBASE
        LDTI 'P'
        BRNEQ bootnos
        LDA OSBASE+1
        LDTI '8'
        BRNEQ bootnos
        LDA OSBASE+3            ; OSCNT
        BRZ bootnos
        MVARL R5
        MVIW R7,OSBASE
        LDAI 1
        STA CFLBA0
bootl:
        JSR cfread
        BRNZ bootfail
        LDA CFLBA0
        ADDI 1
        STA CFLBA0
        DECR R5
        MVRLA R5
        BRNZ bootl
        MVIW R7,OSBASE
        JSRUR R7
        BR cmdloop
bootfail:
        MVIW R7,MSGCFERR
        JSR stringout
        BR cmdloop
bootnos:
        MVIW R7,MSGNOOS
        JSR stringout
        BR cmdloop
MSGBOOT: DB 0ah,0dh,"BOOT FROM CF",0ah,0dh,0
MSGCFERR: DB "CF ERROR",0ah,0dh,0
MSGNOOS: DB "NO OS ON THE CARD",0ah,0dh,0
;
; ---- Video card driver (YACC1-D 2026-09-25) --------------------------------------------------------------------
; The screen is VCOLS x VROWS bytes from VIDRAM, row after row; a byte's bits 0-5 pick one of the 64 glyphs of the
; character EPROM (the card latches VDATA0..5 only), bit 7 is inverse video, bit 6 is unused. The driver stores
; ASCII with $60-$7F moved to $40-$5F (upper case), so a 2513-style set (code = ASCII bits 0-5) shows the text as sent. Cursor: VROW/VCOL, VLINE =
; the address of the row. vputc handles CR (column 0), LF (column 0 of the next row: Y1/OS ends lines with LF
; alone), BS (one left, no erase), TAB (spaces to the next multiple of 8), FF (clear + home); other control bytes and
; DEL are ignored; a character in the last column wraps; LF on the last row scrolls (the whole screen moves up one
; row, the last row is blanked). Only instructions of the 2021 set: no LDZ/STZ/ADDIW/SHL16/BRUR, no R2.
;
; vidreset: at reset. Mirroring and the CRTC cursor off, cursor home, probe; with VIDAUTO also V I + mirroring on.
vidreset:
        LDAI 0
        STA VIDMIR
        STA VIDCUR
        JSR vhome
        JSR vprobe
        LDAI VIDAUTO
        BRZ vidrx
        LDA VIDPRES
        BRZ vidrx
        JSR vinit
        LDAI 1
        STA VIDMIR
vidrx:  RET
;
; vprobe: VIDPRES (and ACC) = 1 when the byte at VIDRAM keeps $55 and then $AA, else 0; the old byte is put back.
; An undecoded block reads what was last on the bus: between each STA and its LDA the LDA's own opcode and operand
; bytes ($E4 $D0 $00) cross the bus, so a floating bus reads $00, not the pattern.
vprobe:
        LDA VIDRAM
        PUSH
        LDAI 055h
        STA VIDRAM
        LDA VIDRAM
        LDTI 055h
        BRNEQ vprno
        LDAI 0aah
        STA VIDRAM
        LDA VIDRAM
        LDTI 0aah
        BRNEQ vprno
        LDAI 1
        BR vprset
vprno:  LDAI 0
vprset: STA VIDPRES
        POP
        STA VIDRAM
        LDA VIDPRES
        RET
;
; vinit: the CRTC's 16 registers from vcrtab, the CRTC cursor on, then vcls (R7 clobbered)
vinit:
        MVIW R7,vcrtab
        LDAI 0
vinitl: STA VCRTCA
        PUSH
        LDAVR R7
        STA VCRTCD
        INCR R7
        POP
        ADDI 1
        LDTI 16
        BRNEQ vinitl
        LDAI 1
        STA VIDCUR
; vcls: every byte of the display RAM a space, cursor home
vcls:   LDAI ' '
        JSR vfill
; vhome: cursor to row 0, column 0 (R7 clobbered)
vhome:  LDAI 0
        STA VROW
        STA VCOL
        MVIW R7,VIDRAM
        STR R7,VLINE
        RET
;
; vfill: ACC to all VIDSIZE bytes of the display RAM, 8 per pass (R7, TMP clobbered, R5 kept)
vfill:  PUSHR R5
        MVAT
        MVIW R7,VIDRAM
        MVIB R5,(VIDSIZE/8).0
vfilll: MVTA
        STAVR R7
        INCR R7
        STAVR R7
        INCR R7
        STAVR R7
        INCR R7
        STAVR R7
        INCR R7
        STAVR R7
        INCR R7
        STAVR R7
        INCR R7
        STAVR R7
        INCR R7
        STAVR R7
        INCR R7
        DECR R5
        MVRLA R5
        BRNZ vfilll
        POPR R5
        RET
;
; vputc: ACC to the screen at the cursor (see above). Keeps R3-R7 and TMP; ACC is not kept (charout has its copy).
vputc:  STA VCHAR
        MVTA
        PUSH
        PUSHR R7
        LDA VCHAR
        ANDI 07fh
        LDTI 020h
        BRLT vpctl
        LDTI 07fh
        BREQ vpdone
        JSR vupper
        JSR vpchar
vpdone: JSR vcursor
        POPR R7
        POP
        MVAT
        RET
vpctl:  LDTI 0dh
        BREQ vpcr
        LDTI 0ah
        BREQ vplf
        LDTI 08h
        BREQ vpbs
        LDTI 0ch
        BREQ vpff
        LDTI 09h
        BRNEQ vpdone
vptab:  LDAI ' '
        JSR vpchar
        LDA VCOL
        ANDI 7
        BRNZ vptab
        BR vpdone
vpcr:   LDAI 0
        STA VCOL
        BR vpdone
vplf:   JSR vlf
        BR vpdone
vpbs:   LDA VCOL
        BRZ vpdone
        SUBI 1
        STA VCOL
        BR vpdone
vpff:   JSR vcls
        BR vpdone
;
; vpchar: ACC stored at the cursor, the cursor one right; past the last column to the next row (R7, TMP clobbered)
vpchar: PUSH
        JSR vcaddr
        POP
        STAVR R7
        LDA VCOL
        ADDI 1
        STA VCOL
        LDTI VCOLS
        BRNEQ vpchx
        JSR vlf
vpchx:  RET
;
; vlf: column 0 of the next row; on the last row the screen scrolls instead (R7, TMP clobbered)
vlf:    LDAI 0
        STA VCOL
        LDA VROW
        ADDI 1
        LDTI VROWS
        BREQ vscroll
        STA VROW
        LDR R7,VLINE
        LDTI VCOLS
        JSR vaddt
        STR R7,VLINE
        RET
;
; vscroll: rows 1..VROWS-1 up one row (8 bytes per pass), the last row blanked; R5/R6 kept, R7 clobbered
vscroll:
        PUSHR R6
        PUSHR R5
        MVIW R6,VIDRAM+VCOLS
        MVIW R7,VIDRAM
        MVIB R5,(VCOLS*(VROWS-1)/8).0
vscrl:  LDAVR R6
        STAVR R7
        INCR R6
        INCR R7
        LDAVR R6
        STAVR R7
        INCR R6
        INCR R7
        LDAVR R6
        STAVR R7
        INCR R6
        INCR R7
        LDAVR R6
        STAVR R7
        INCR R6
        INCR R7
        LDAVR R6
        STAVR R7
        INCR R6
        INCR R7
        LDAVR R6
        STAVR R7
        INCR R6
        INCR R7
        LDAVR R6
        STAVR R7
        INCR R6
        INCR R7
        LDAVR R6
        STAVR R7
        INCR R6
        INCR R7
        DECR R5
        MVRLA R5
        BRNZ vscrl
        MVIB R5,VCOLS
vscrb:  LDIVR R7,' '
        INCR R7
        DECR R5
        MVRLA R5
        BRNZ vscrb
        POPR R5
        POPR R6
        RET
;
; vupper: $60-$7F down to $40-$5F (lower case to upper; the monitor's toupper also moves [ \ ] ^ _, which the
; 64-glyph set has)
vupper: LDTI 060h
        BRLT vuppx
        SUBI 020h
vuppx:  RET
;
; vcaddr: R7 = VLINE + VCOL, the cursor's address (TMP clobbered)
vcaddr: LDT VCOL
        LDR R7,VLINE
; vaddt: R7 += TMP (8 bits). The ADDIC follows the ADDI with only register moves between: the carry is the add's
; on the machine and on both emulators (docs/programming/ISA-REFERENCE.md section 6)
vaddt:  MVRLA R7
        ADDT
        MVARL R7
        MVRHA R7
        ADDIC 0
        MVARH R7
        RET
;
; vcursor: with VIDCUR set, the CRTC's cursor registers R14/R15 <- the cursor's offset from VIDRAM (R7 clobbered)
vcursor:
        LDA VIDCUR
        BRZ vcurx
        JSR vcaddr
        LDAI 14
        STA VCRTCA
        MVRHA R7
        SUBI (VIDRAM).1
        STA VCRTCD
        LDAI 15
        STA VCRTCA
        MVRLA R7
        STA VCRTCD
vcurx:  RET
;
; vidctl: the video entry at $FFBC (JSR vidctl / RET, below the full vector table), for Y1/OS and programs.
; ACC = 0 probe (ACC = VIDPRES), 1 init (V I), 2 clear + home (V C); anything else: ACC = VIDPRES.
; A caller checks that $FFBC holds $04 (JSR) first: an older ROM has $FF there. Clobbers R5-R7, TMP.
vidctl: LDTI 1
        BREQ vctli
        LDTI 2
        BREQ vctlc
        BRNZ vctlx
        JSR vprobe
        BR vctlx
vctli:  JSR vinit
        BR vctlx
vctlc:  JSR vcls
vctlx:  LDA VIDPRES
        RET
;
; ---- V: the video unit (monitor command) ---------------------------------------------------------------------
; V then a letter (blanks skipped); numbers are hex, blanks between them optional. V? (or any other letter) lists:
;   VS  status          VP  probe again      VI  init (CRTC, clear, home)     VC  clear, home
;   VM1 / VM0  mirror on / off               VW rr cc text  text at row rr, column cc (not the cursor)
;   VB aaaa bb bb ..  bytes from aaaa ($Dxxx only)   VF bb  fill the 2K     VD  the screen as text (not mirrored)
;   VR rr [vv]  write CRTC register rr, or read it
;
cmd_video:
        LDTI NOMODE
        STT monmode
        JSR vskip
        JSR toupper
        LDTI 'S'
        BREQ vcstat
        LDTI 'P'
        BREQ vcprob
        LDTI 'I'
        BREQ vcinit
        LDTI 'C'
        BREQ vcclr
        LDTI 'M'
        BREQ vcmir
        LDTI 'W'
        BREQ vcwrt
        LDTI 'B'
        BREQ vcbyt
        LDTI 'F'
        BREQ vcfil
        LDTI 'D'
        BREQ vcdump
        LDTI 'R'
        BREQ vcreg
        MVIW R7,VHELP
        BR vcmsg
vcprob: JSR vprobe
        BR vcstat
vcinit: JSR vinit
        BR vcstat
vcclr:  JSR vcls
        BR vcok
vcmir:  JSR vskip                ; '1' ($31) -> 1, '0' ($30) -> 0
        ANDI 1
        STA VIDMIR
vcstat: MVIW R7,MSGVST          ; VIDPRES, VIDMIR, VIDCUR, VROW, VCOL ($0FF0-$0FF4), each after its label
        MVIW R6,VIDPRES
vcstl:  JSR stringout
        INCR R7
        LDAVR R6
        JSR showbytea
        INCR R6
        MVRLA R6
        LDTI (VCOL+1).0
        BRNEQ vcstl
vcok:   MVIW R7,CRLF
vcmsg:  JSR stringout
        BR cmdloop
vcbad:  MVIW R1,STACK           ; from any depth: the V command runs from the command loop, whose stack is empty
vcbadl: JSR uartin              ; the rest of the line is dropped (else its characters would run as commands:
        LDTI 0ah                ; a 0 would stop the machine)
        BREQ vcbadx
        LDTI 0dh
        BRNEQ vcbadl
vcbadx: MVIW R7,MSGVBAD
        BR vcmsg
;
; VW rr cc text: rows 0..VROWS-1, columns 0..VCOLS-1; one blank after cc is the separator, the text runs to CR/LF
; (upper-cased, stored as typed, it may run on into the next rows but stops at the end of the display RAM)
vcwrt:  JSR vgetb
        LDTI VROWS-1
        BRGT vcbad
        PUSH
        JSR vgetb
        LDTI VCOLS-1
        BRGT vcbad
        STA VCHAR
        POP
        MVIW R7,VIDRAM
vcwrl:  BRZ vcwrc
        PUSH
        LDTI VCOLS
        JSR vaddt
        POP
        SUBI 1
        BR vcwrl
vcwrc:  LDT VCHAR
        JSR vaddt
        JSR uartin
        LDTI ' '
        BRNEQ vcwrs
vcwrn:  JSR uartin
vcwrs:  LDTI 0dh
        BREQ vcok
        LDTI 0ah
        BREQ vcok
        JSR vupper
        STAVR R7
        INCR R7
        MVRHA R7
        LDTI (VIDRAM+VIDSIZE).1
        BRNEQ vcwrn
        BR vcok
;
; VB aaaa bb bb ..: bytes stored from aaaa on, to CR/LF; aaaa must be in VIDRAM's 4K block and the bytes stop at its
; end (never the ROM). Mind the card: an odd address in the CRTC half is the JP1 latch, which drives the bus even
; while the CPU writes (docs/cards/video.md finding 6.4)
vcbyt:  JSR vgetb
        MVARH R7
        JSR vgetb
        MVARL R7
vcbytl: MVRHA R7
        ANDI 0f0h
        LDTI (VIDRAM).1
        BRNEQ vcbad             ; outside the block (or run off its end): ? and nothing stored there
        JSR vskip
        LDTI 0dh
        BREQ vcok
        LDTI 0ah
        BREQ vcok
        JSR getbytec
        STAVR R7
        INCR R7
        BR vcbytl
;
; VF bb: fill the 2K display RAM (a RAM test by eye: VF55, VD)
vcfil:  JSR vgetb
        JSR vfill
        BR vcok
;
; VD: the screen as text, one row per line after its hex row number; each byte shown as its glyph would be under the
; 2513-style assumption (bits 0-5: 00-1F = @..underscore, 20-3F = blank..?). Mirroring is paused meanwhile.
vcdump: LDA VIDMIR
        PUSH
        LDAI 0
        STA VIDMIR
        MVIW R7,CRLF
        JSR stringout
        MVIW R7,VIDRAM
        MVIB R5,0
vcdrow: MVRLA R5
        JSR showbytea
        LDAI ' '
        JSR charout
        MVIB R6,VCOLS
vcdcol: LDAVR R7
        ADDI 020h
        ANDI 03fh
        ADDI 020h
        JSR charout
        INCR R7
        DECR R6
        MVRLA R6
        BRNZ vcdcol
        PUSHR R7
        MVIW R7,CRLF
        JSR stringout
        POPR R7
        INCR R5
        MVRLA R5
        LDTI VROWS
        BRNEQ vcdrow
        POP
        STA VIDMIR
        BR cmdloop
;
; VR rr [vv]: rr to the CRTC's address register, then vv to its data register, or with no vv read the data register
; (only R12-R17 read back on a 6845; the rest read what the bus floats to)
vcreg:  JSR vgetb
        STA VCRTCA
        JSR vskip
        LDTI 0dh
        BREQ vcregr
        LDTI 0ah
        BREQ vcregr
        JSR getbytec
        STA VCRTCD
        BR vcok
vcregr: MVIW R7,CRLF
        JSR stringout
        LDA VCRTCD
        JSR showbytea
        BR vcok
;
; vskip: the next console character that is not a blank; vgetb: two hex digits after any blanks -> ACC
vskip:  JSR uartin
        LDTI ' '
        BREQ vskip
        RET
vgetb:  JSR vskip
        BR getbytec
;
; the CRTC registers R0..R15 for vinit. Timing ASSUMED (no crystal value in the tree, docs/cards/video.md 3.4): a
; 10 MHz dot clock, 5 dots a character (IC28 divides by 5), 8 scan lines a row (RA0..2): a 2 MHz character clock,
; 127 characters a line = 63.5 us (15.7 kHz), 32 rows + 6 lines = 262 lines (60 Hz), non-interlaced. Re-derive R0-R7
; when the crystal is known; R1/R6 follow VCOLS/VROWS.
vcrtab: DB 126            ; R0  horizontal total - 1
        DB VCOLS          ; R1  characters displayed
        DB 98             ; R2  horizontal sync position
        DB 10             ; R3  sync width (HS 10 characters)
        DB 31             ; R4  vertical total - 1 (rows)
        DB 6              ; R5  vertical total adjust (scan lines)
        DB VROWS          ; R6  rows displayed
        DB 28             ; R7  vertical sync position (row)
        DB 0              ; R8  interlace mode: off
        DB 7              ; R9  scan lines per row - 1
        DB 067h           ; R10 cursor start line 7, blinking (1/16 field rate)
        DB 7              ; R11 cursor end line 7
        DB 0              ; R12 start address high
        DB 0              ; R13 start address low
        DB 0              ; R14 cursor address high
        DB 0              ; R15 cursor address low
;
getaddress:
;
; Read 4 char address and return in R7 (2026-09-25: two getbyte calls; getbyte is shared with E and V)
;
            Push
            JSR getbyte
            MVARH R7
            JSR getbyte
            MVARL R7
            POP
            RET
;
; getbyte: two hex digits from the console -> ACC; getbytec: the same with the first digit already read, in ACC
;
getbyte:    JSR uartin
getbytec:   JSR getnibblec
            SHL
            SHL
            SHL
            SHL
            ANDI 0f0h
            Push
            JSR getnibble
            ANDI 0FH
            MVAT
            Pop
            ORT
            RET
;
; getnibble return in accumulator
;
getnibble:
          JSR uartin
getnibblec:
          LDTI '9'
          BRGT INAF
          SUBI '0'
          RET
INAF:     JSR toupper
          SUBI 'A'
          ADDI 10
          RET
;
; value in accumulator convert to uppercase
;
toupper:  LDTI 'Z'
          BRGT lower
          RET
lower:
          SUBI 020h
          RET
;
; display R7 (old r3) followed by
; ":" and " " for showaddr and nothing for shownum
;
showaddr:   Push
            MVRHA R7
            SHR
            SHR
            SHR
            SHR
            JSR shownibble
            MVRHA R7
            ANDI 0FH
            JSR shownibble
            MVRLA R7
            SHR
            SHR
            SHR
            SHR
            JSR shownibble
            MVRLA R7
            ANDI 0FH
            JSR shownibble
            LDAI ':'
            JSR uartout
            LDAI ' '
            JSR uartout
            POP
            RET

shownum:
showr7:     Push
            MVRHA R7
            SHR
            SHR
            SHR
            SHR
            JSR shownibble
            MVRHA R7
            ANDI 0FH
            JSR shownibble
            MVRLA R7
            SHR
            SHR
            SHR
            SHR
            JSR shownibble
            MVRLA R7
            ANDI 0FH
            JSR shownibble
            POP
            RET
;
;
;
showregs:
            pushr r7
            pushr r7
            MVIW R7,CRLF
            JSR stringout
            MOVRR r0,r7
            jsr showaddr
            MOVRR r1,r7
            jsr showaddr
            MOVRR r2,r7
            jsr showaddr
            MOVRR r3,r7
            jsr showaddr
            MOVRR r4,r7
            jsr showaddr
            MOVRR r5,r7
            jsr showaddr
            MOVRR r6,r7
            jsr showaddr
            popr r7
            jsr showaddr
            push
            ldai ' '
            jsr uartout
            pop
            jsr showcarry

            MVIW R7,CRLF
            JSR stringout
            popr r7
            RET
;
; display upto 16 bytes point to by R7 (old r3), stops on a 16 byte boundry
; increments R7
;
show16:     JSR showbyte
            INCR R7
            LDAI ' '
            JSR uartout
            MVRLA R7
            ANDI 0FH
            BRNZ show16
            LDAI 0ah
            JSR uartout
            LDAI 0dh
            JSR uartout
            RET
;
; display upto 256 bytes point to by R7 (old r3),
; stops on a 256 byte boundry, increments R7
;
show256:
          push
show256loop:
          jsr showaddr
          jsr show16

;         MVIW R7,CRLF
;         JSR stringout

          MVRLA R7
          ANDI  0FFH
          BRNZ show256loop
          JSR uartout
          LDAI 0dh
          JSR uartout
          pop
          RET
;
; Output ASCII representation of a BYTE pointed to by R7 (OLD r7)
; or use showbytea in accumulator
; both destructive for accumulator - no longer true with push/pop
:
showbyte:   PUSH
            LDAVR R7
            SHR
            SHR
            SHR
            SHR
            JSR shownibble
            LDAVR R7
            ANDI 0FH
            JSR shownibble
            POP
            RET
;
showbytea:  PUSH
            PUSH
            SHR
            SHR
            SHR
            SHR
            JSR shownibble
            POP
            ANDI 0FH
            JSR shownibble
            POP
            RET
;
; Show carry flag
;
showcarry:
            Push
            brc show_yescarry
            ldai 'X'
            JSR uartout
            pop
            ret
show_yescarry:
            ldai 'C'
            JSR uartout
            pop
            ret

;
; Display nibble in accumulator ((this looks wrong) destructive)
;  destroys tmp register  - maybe add pusht - popt
;
shownibble:  PUSH
             LDTI 9
             BRGT AF
             ADDI '0'
             JSR uartout
             Pop
             RET

AF:          SUBI 10
             ADDI 'A'
             JSR uartout
             Pop
             RET
;
;
; output accumulator to LEDS or Hex displays (non distructive)
;
ledout:
        OUTI  P0,(SWITCHLED)
        OUTA  P1
        RET
;
; OLD: Output null terminated string pointed to by R2 to UART then send CR and LF
; Advances R2 to end of string
;
; Output null terminated string pointed to by R7 to UART
; Advances R7 to end of string
;
stringout:
        Push
sloop:
        LDAVR R7
        BRZ sloopdone
        JSR uartout
        INCR R7
        BR sloop
;
; (not done send CR and LF)
;
sloopdone:
        POP
        RET
;
; output accumulator to UART, wait for UART out available
;
charout:
uartout:
;
; 2026-09-25: the video mirror. With VIDMIR and VIDPRES set the byte also goes to the screen (vputc, which keeps
; every register and TMP); with VIDMIR 0 this costs a PUSH, an LDA, a BRZ and a POP, and the UART path below is as
; it was. ACC, TMP and R3-R7 are kept either way (R2 is LDA's address register, as in every LDA).
;
        PUSH
        LDA VIDMIR
        BRZ chnovid
        LDA VIDPRES
        BRZ chnovid
        POP
        PUSH
        JSR vputc
chnovid:
        POP
;
; add for emulator, outputs via putch
;
        BRDEV emulator2
        outa p2
        ret
;
emulator2:
        PUSH
        push
;
; doubt 2nd push pop is needed, to be tested
;
uartoutw:
;
; test uart out is available
;
        OUTI  P0,(UARTCS!UARTA5)
        INP   p1
        ANDI  040h
        BRZ   uartoutw
        POP
        OUTI  P0,UARTCS
        OUTA  P1
;
; may not be needed
       Pop
       RET

;
; wait for UART character available then input to accumulator
;
; Looks like this echos out character
; should this be settable via a flag
;
uartin:
;
; added for emulator, emulator P2 reads a char via getch
;
        BRDEV emulator3
        inp p2
        ret
;
emulator3:
;
; wait for a charater available at input
;
        OUTI  P0,(UARTCS!UARTA5)
        INP   p1
        ANDI  01h
        BRZ   uartin
        OUTI  P0,(UARTCS)
        INP   P1
        ldti 0dh          ; cobvert 0x0d to 0x0a
        brneq uartinc
        ldai 0ah
uartinc:
        JSR   LEDOUT
;
; emulator
;
;        ldti  0ah
;        breq uartin
        JSR   uartout
        RET
;
; uartinne: uartin WITHOUT the echo and the LED (2026-09-23, vector $FFFC): Y1/OS's CONIN syscall reads the
; console for a program (a filter reading its input) and the shell echoes what it wants itself. Same paths:
; port 2 on the instruction-level emulator (BRDEV), the UART on the machine; CR becomes LF.
;
uartinne:
        BRDEV uartinnehw
        inp p2
        ret
uartinnehw:
        OUTI  P0,(UARTCS!UARTA5)
        INP   p1
        ANDI  01h
        BRZ   uartinnehw
        OUTI  P0,(UARTCS)
        INP   P1
        ldti 0dh
        brneq uartinnec
        ldai 0ah
uartinnec:
        RET
;
; (LONGDELAY, SHORTDELAY, switchtoggle, switchin, TIL311out and nblink - never called - and the T-menu's help
;  strings were removed 2026-09-25 to make room for the video unit; git history has them)
;
; quick blink LED
;
blink:
;
; added for emulator, return immediately to skip counting
; destroys r7
;
;       ret
        Push
        ON
        MVIW R7,03FFh
onloop:
        DECR R7
        MVRHA R7
        BRNZ onloop

        OFF
        MVIW R7,003FFh
offloop:
        DECR R7
        MVRHA R7
        BRNZ offloop
        Pop
        RET
;
; long blink LED
;
lblink:
;
; emulator change, return immediately to skip counting
; destroys r7
;
;       ret
        Push
        ON
        MVIW R7,018FFh
lonloop:
        DECR R7
        MVRHA R7
        BRNZ lonloop

        OFF
        MVIW R7,018FFh
loffloop:
        DECR R7
        MVRHA R7
        BRNZ loffloop
        Pop
        RET
;
;
; MONITOR STRINGS
;
hello:  DB 0ah,0dh,"YACC 2020: hello world  ROM 2026-09-25",0ah,0dh,0    ; the build date tells ROMs apart at a glance
PROMPT: DB ">",0
CRLF: DB 0ah,0dh,0
ERROR: DB "UNRECOGINIZED COMMAND",0ah,0dh,0
DUMPMSG: DB 0ah,0dh,"DUMP ADDR:",0
DUMPBLOCKMSG: DB 0ah,0dh,"DUMP BLOCK ADDR:",0
FILLMSG: DB 0ah,0dh,"FILL BLOCK ADDR:",0
GOMSG: DB 0ah,0dh,"GO ADDRESS:",0
EXAMINEMSG: DB 0ah,0Dh,"EXAMINE ADDRESS:",0
BASIC_PARSEMSG: DB 0ah,0dh,"Enter Line:",0
;
helpmenu:                   ; (2026-09-25: reworded shorter to make room for the video unit)
DB "0      EXIT (EMULATOR ONLY)",0ah,0dh
DB "H      THIS HELP",0ah,0dh,0ah,0dh
DB "B AAAA SHOW MEMORY FROM AAAA TO A 256 BOUNDARY, CR THE NEXT 256",0ah,0dh
DB "C      COPY THE BASIC TEST PROGRAM INTO THE INTERPRETER BUFFER",0ah,0dh
DB "D AAAA SHOW MEMORY FROM AAAA TO A 16 BOUNDARY, CR THE NEXT 16",0ah,0dh
DB "E AAAA SHOW AAAA:XX; HEX XX STORES, CR THE NEXT, ESC OR - ENDS",0ah,0dh
DB "F AAAA FILL WITH 0 FROM AAAA TO A 256 BOUNDARY, CR THE NEXT 256",0ah,0dh
DB "G AAAA CALL AAAA (JSRUR R7: THE PROGRAM ENDS WITH RET)",0ah,0dh
DB "I      BASIC",0ah,0dh
DB "L      LIST BASIC",0ah,0dh
DB "O      BOOT THE OS FROM THE CF CARD (LBA 1.., OSCNT SECTORS, TO 1000H)",0ah,0dh
DB "P      ENTER A PROGRAM LINE TO BASIC",0ah,0dh
DB "R      SHOW REGISTERS",0ah,0dh
DB "V      VIDEO CARD (V? LISTS ITS COMMANDS)",0ah,0dh
DB "Y      RUN THE BASIC TEST CODE",0ah,0dh
DB "Z      RUN THE PROGRAM WITH THE BASIC INTERPRETER",0ah,0dh
DB ":      INTEL-HEX LOAD (. PER RECORD, ? BAD RECORD, ! REFUSED ADDRESS)",0ah,0dh
DB 0
;
; the video unit's strings (2026-09-25)
;
MSGVIDEO: DB "VIDEO CARD FOUND",0ah,0dh,0
MSGVST: DB 0ah,0dh,"VIDEO ",0,"  MIRROR ",0,"  CRTC ",0,"  ROW ",0,"  COL ",0
MSGVBAD: DB " ?",0ah,0dh,0
VHELP:
DB 0ah,0dh,"VS STATUS  VP PROBE  VI INIT CRTC+CLEAR  VC CLEAR  VM1/VM0 MIRROR ON/OFF",0ah,0dh
DB "VW RR CC TEXT  VB AAAA BB BB..  VF BB  VD SCREEN AS TEXT  VR RR [VV] CRTC REG",0ah,0dh,0
;
TESTMSG: DB "Run test code",0ah,0dh,0



;
; OLD
;
;
;LCD
;
;xlcdtest:
;        OUTI P0,(LCDENABLE)

;        MVIW R3,1fFFh
;xdelay0:
;        DECR R3
;        MVRHA R3
;        BRNZ xdelay0

;        OUTI P1,3CH

;        MVIW R3,1fFFh
;xdelay1:
;        DECR R3
;        MVRHA R3
;        BRNZ xdelay1

;        OUTI P1,01H

;        MVIW R3,1fFFh
;xdelay2:
;        DECR R3
;        MVRHA R3
;        BRNZ xdelay2

;        OUTI P1,0FH

;        MVIW R3,1fFFh
;xdelay3:
;        DECR R3
;        MVRHA R3
;        BRNZ xdelay3

;        OUTI P0,(LCDENABLE!LCDREGISTER)

;        MVIW R3,1fFFh
;xdelay4:
;        DECR R3
;        MVRHA R3
;        BRNZ xdelay4

;        OUTI P1,'A'

;xdelay5:
;        DECR R3
;        MVRHA R3
;        BRNZ xdelay5

;        OUTI P1,'B'

;xaddtest:
;      OUTI  P0,(SWITCHLED)
;      INP   P1
;      ADDI  001H
;      OUTA  P1

;xandtest:
;      OUTI  P0,(SWITCHLED)
;      INP   P1
;      ANDI  055H
;      OUTA  P1

;xxortest:
;     OUTI  P0,(SWITCHLED)
;     INP   P1
;     XORI  055H
;     OUTA  P1
;      JSRUR R2

;
; Interupt sevice routine
;
  org 0ff90h
isrcode:
;  halt
  push
  pushr r7
  lda interupt_cnt
isrloop:
  jsr BLINK
  subi 1
  brnz isrloop
  popr r7
  pop
; halt
  iret


;
; BIOS ENTRY Points
;
;
; The video entry (2026-09-25): the 16-vector table below is full, so the video driver's one entry sits just under
; it, at a fixed address like the vectors: ACC = 0 probe, 1 init, 2 clear (vidctl). An older ROM has $FF here.
;
    org 0ffbch
e_vidctl:
    jsr vidctl
    ret

    org 0ffc0h

e_stringout:
    jsr stringout
    ret
e_charout:
    jsr charout
    ret
e_uartout:
    jsr uartout
    ret
e_showaddr:
    jsr showaddr
    ret
e_toupper:
    jsr toupper
    ret
e_showr7:
    jsr showr7
    ret
e_showbyte:
    jsr showbyte
    ret
e_ showregs:
    jsr SHOWREGS
    ret
e_showbytea:
    jsr showbytea
    ret
e_showcarry:
    jsr showcarry
    ret
e_uartin:
    jsr uartin
    ret
e_cfinit:
    jsr cfinit
    ret
e_cfread:
    jsr cfread
    ret
e_cfwrite:
    jsr cfwrite
    ret
e_const:
    jsr const
    ret
e_uartinne:                 ; $FFFC, the last slot (2026-09-23): console byte without echo
    jsr uartinne
    ret
;
; The End ($10000: the table fills the ROM to its last byte)
;
