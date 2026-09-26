; =====================================================================================================================
; kermit_io.asm - /BIN/KERMIT's line I/O and per-byte loops (2026-09-26): packets in and out of the console UART,
; the block checks, and the data field encoded and decoded.
;
; Why assembly: at 1 MHz the YACC1 runs ~30,000 instructions a second, and 38400 baud brings a character every 260 us.
; The loop below takes 279 clocks a character when one is waiting, so with the 16C550's 16-byte receive FIFO switched
; on (kermit.c does it) it falls behind by 7% and a burst of ~220 characters fits; a whole 96-character packet is
; safe. The same loop compiled from C by y1cc took ~1,100 clocks a character: a burst of ~21 would have overflowed
; the FIFO, and C-Kermit's first packet alone is ~26. The other routines are here for speed alone: with only krx and
; ktx in assembly kermit spent 398 instructions a received byte and 525 a sent one, most of them in the CRC and in
; E-Kermit's encode/decode loops as y1cc compiles them; with these, 118 and 132 (os/README.md "kermit").
;
; Not a program: os/mkkio.py assembles this file twice (at 0000H and at 1000H), finds the words that differ (the
; absolute addresses: branches and the parameter words), and writes os/kermit_io.c, the bytes as a C array plus that
; relocation list; kermit.c adds the array's address to each listed word once at start-up and calls the entries with
; y1cc's call(). mkkio.py writes a #define KIO_<label> for every entry and parameter below (their offsets), and
; kermit.c pokes the parameters, calls an entry, and peeks what it left:
;   krx   read a packet                     ktx   send KCNT bytes from KBUF
;   kcrc  R3 = the CRC of KCNT bytes        ksum  R3 = the 16-bit sum of KCNT bytes (block checks 3, and 1 and 2)
;   kdec  decode a packet's data field      kenc  encode plain file bytes into a data field (E-Kermit's decode() and
;         (all of it)                             getpkt() fast paths: kermit.c does the rest in C)
;   KBUF KCNT (words)  the buffer and a count; krx: KCNT = the most bytes it may store after the LEN byte
;   KTIMO (word)  krx: seconds to wait for the packet's SOH (0 = 65536 seconds)
;   KTAB  (word)  kcrc: a page-aligned 512-byte table, the low bytes of the 256 CRC entries, then the high bytes
;   KOUT  (word)  kdec, kenc: where the next output byte goes      KROOM (word) kenc: how many more fit
;   KC    (byte)  kenc: the byte in hand (getpkt's lookahead)       KTXT  (byte) kdec: 1 = drop CR (text mode)
;   KRQ KEQ KCQ (bytes)  the repeat, 8th-bit and control prefixes in use; 0 = not in use (a prefix is printable)
;
; krx returns in R3:  0        no SOH within KTIMO seconds (a timeout)
;                     n        a packet: KBUF[0] = its LEN character, KBUF[1..n-1] = SEQ TYPE DATA CHECK (n - 1 =
;                              LEN - 32 bytes, read by count: the terminator after them is left in the UART and
;                              skipped by the next krx, like any byte before an SOH)
;                     0FFFDH   a Ctrl-C arrived while waiting for an SOH (kermit.c counts three in a row: quit)
;                     0FFFEH   a bad packet: LEN out of range (a long packet, fewer than 3 bytes, more than KCNT), or
;                              a gap of more than ~2 s inside it; the caller NAKs it
; An SOH in the LEN position starts the packet again; an SOH later inside a packet is just data (the checksum fails
; and the caller NAKs, after which the sender repeats the packet).
;
; The UART: P0 selects (UARTCS $40 | register << 3), P1 is the register (docs/cards/io.md section 4.1). LSR bit 0 =
; data ready, bit 5 = transmit holding register (FIFO) empty. Polling LSR is how the ROM's own uartinne works; the ROM
; routine is not used here because it turns CR into LF and costs a JSR per character.
;
; Time: there is no timer, so a timeout is a count of polls. One pass of the wait loop (OUTI, INP, ANDI, BRNZ, DECR,
; MVRLA, BRNZ) is 25+23+23+41+19+19+41 = 191 clocks (a record of N microcode steps is 2N - 1 clocks), every 256th
; pass 60 more: 191.23 on average, so PPS = 5229 passes are one second at 1 MHz (the microcode emulator measures
; 1,000,111 clocks: tests/kermit/run.py --calib). At another clock every timeout scales with it. The emulators poll
; much faster than 1 MHz for the first 20,000 empty polls (~3.8 s of the machine's time) after any input or output,
; then each poll waits up to 1 ms there (~5 times the machine's 191 us): a 2 s timeout passes at once, a 5 s one
; takes about 6 s.
;
; Registers (krx): R3 the result, R4 seconds, R5 the poll budget, R6 the count, R7 the buffer; ACC and TMP. Every
; routine keeps R1 and never uses R2 (the machine's hidden address register; LDR/LDT/LDA load it) and may change
; R3-R7, ACC and TMP; y1cc's call() reloads its page register R6 afterwards. The 2021 instruction set only (no
; LDZ/STZ/ADDIW/SHL16), so it runs on the machine's present microcode whether kermit.c is built with --xisa or not.
; =====================================================================================================================

U_RBR:  EQU 40H                 ; UARTCS | 0 << 3: RBR (read) / THR (write)
U_LSR:  EQU 68H                 ; UARTCS | 5 << 3: line status
PPS:    EQU 5229                ; wait-loop passes a second at 1 MHz (above)
GAP:    EQU 10458               ; the budget for the rest of a packet once its SOH is in: ~2 s of waiting

        ORG 0000H               ; (os/mkkio.py assembles it here and at 1000H)
        BR krx
        BR ktx
        BR kcrc
        BR ksum
        BR kdec
        BR kenc
KBUF:   DW 0
KCNT:   DW 0
KTIMO:  DW 0
KTAB:   DW 0
KOUT:   DW 0
KROOM:  DW 0
KC:     DB 0
KTXT:   DB 0
KRQ:    DB 0
KEQ:    DB 0
KCQ:    DB 0

; ---- krx: read one packet ----------------------------------------------------------------------------------------
krx:    LDR  R7,KBUF
        LDR  R4,KTIMO
        MVIW R5,PPS
hunt:   OUTI P0,U_LSR           ; wait for a character, KTIMO seconds at most
        INP  P1
        ANDI 1
        BRNZ hgot
        DECR R5
        MVRLA R5
        BRNZ hunt
        MVRHA R5
        BRNZ hunt
        MVIW R5,PPS             ; one second more gone
        DECR R4
        MVRLA R4
        BRNZ hunt
        MVRHA R4
        BRNZ hunt
        MVIW R3,0               ; timeout
        RET
hgot:   OUTI P0,U_RBR
        INP  P1
        LDTI 1
        BREQ soh
        LDTI 3
        BRNEQ hunt              ; not an SOH, not a Ctrl-C: skip it (a terminator, noise, the other side's echo)
        MVIW R3,0FFFDH
        RET

soh:    MVIW R5,GAP             ; the LEN character
lwait:  OUTI P0,U_LSR
        INP  P1
        ANDI 1
        BRNZ lgot
        DECR R5
        MVRLA R5
        BRNZ lwait
        MVRHA R5
        BRNZ lwait
        BR   bad
lgot:   OUTI P0,U_RBR
        INP  P1
        LDTI 1
        BREQ soh                ; another SOH: the packet starts again
        STAVR R7                ; KBUF[0] = LEN
        INCR R7
        ADDI 0E0H               ; n = LEN - 32 (no SUB: its carry is not the same on the machine and the emulators)
        LDTI 3
        BRLT bad                ; LEN below 35 (a long packet's blank LEN too): not a packet this reads
        LDT  KCNT+1
        BRGT bad                ; longer than the buffer
        MVIW R3,0
        MVARL R3
        INCR R3                 ; the result: n + 1 bytes stored
        MVIW R6,0
        MVARL R6                ; n bytes to come
body:   OUTI P0,U_LSR           ; 279 clocks a character when it is already there
        INP  P1
        ANDI 1
        BRZ  bwait
        OUTI P0,U_RBR
        INP  P1
        STAVR R7
        INCR R7
        DECR R6
        MVRLA R6
        BRNZ body
        RET
bwait:  DECR R5
        MVRLA R5
        BRNZ body
        MVRHA R5
        BRNZ body
bad:    MVIW R3,0FFFEH
        RET

; ---- ktx: send KCNT bytes from KBUF --------------------------------------------------------------------------------
ktx:    LDR  R7,KBUF
        LDR  R6,KCNT
tpoll:  OUTI P0,U_LSR
        INP  P1
        ANDI 20H                ; THRE: room for a character
        BRZ  tpoll
        OUTI P0,U_RBR
        LDAVR R7
        OUTA P1
        INCR R7
        DECR R6
        MVRLA R6
        BRNZ tpoll
        MVRHA R6
        BRNZ tpoll
        RET

; ---- kcrc: the block-check-3 CRC of KCNT bytes at KBUF ------------------------------------------------------------
; Kermit's CRC-CCITT (E-Kermit chk3: crc = (crc >> 8) ^ T[(crc ^ b) & 255], T built by kermit.c from E-Kermit's two
; nibble tables), a byte a table look-up: the new low byte is crc.hi ^ Tlo[i], the new high byte Thi[i]. With the
; halves on their own pages the index is just a register's low byte. 16 instructions a byte (the C took ~210).
kcrc:   LDR  R7,KBUF
        LDR  R6,KCNT
        LDR  R4,KTAB            ; R4 -> Tlo, R5 -> Thi (the next page)
        MVRHA R4
        ADDI 1
        MVARH R5
        MVIW R3,0
cloop:  LDAVR R7
        MVAT
        MVRLA R3
        XORT                    ; i = (crc ^ b) & 255
        MVARL R4
        MVARL R5
        LDAVR R4
        MVAT
        MVRHA R3
        XORT
        MVARL R3                ; lo = crc.hi ^ Tlo[i]
        LDAVR R5
        MVARH R3                ; hi = Thi[i]
        INCR R7
        DECR R6
        MVRLA R6
        BRNZ cloop
        MVRHA R6
        BRNZ cloop
        RET

; ---- ksum: the 16-bit sum of KCNT bytes at KBUF (block check 1 folds it to 6 bits, 2 keeps 12) --------------------
; ADDT then ADDIC 0 with only register moves between: the one carry use that is the same on the machine and both
; emulators (docs/programming/ISA-REFERENCE.md section 6).
ksum:   LDR  R7,KBUF
        LDR  R6,KCNT
        MVIW R3,0
sloop:  LDAVR R7
        MVAT
        MVRLA R3
        ADDT
        MVARL R3
        MVRHA R3
        ADDIC 0
        MVARH R3
        INCR R7
        DECR R6
        MVRLA R6
        BRNZ sloop
        MVRHA R6
        BRNZ sloop
        RET

; ---- kdec: decode KCNT (1..94) bytes of packet data at KBUF to KOUT; KOUT is left after the last byte -----------------
; E-Kermit's decode() for file data: [repeat prefix, count] [8th-bit prefix] [control prefix] character, in that
; order; a count of 0 or over 94 is taken as 1 (a broken sender); under the control prefix ?..95 (? @ A-Z [ \ ] ^ _,
; and the same with bit 7) are flipped by 64 (DEL and the control characters), anything else is itself. In text mode
; (KTXT) a decoded CR is dropped. The caller leaves room: one unit can give 94 bytes, 94 bytes of data 2,822. A
; prefix at the very end of the data (a broken packet) stops the loop (KCNT would pass 0). ~29 instructions a
; plain character (the C took ~110).
; Registers: R7 in, R6 count, R5 out, R4 the repeat count, R3.lo the character, R3.hi its 8th bit.
kdec:   LDR  R7,KBUF
        LDR  R6,KCNT
        LDR  R5,KOUT
dunit:  MVIW R4,1
        MVIW R3,0
        LDAVR R7                ; the next character
        INCR R7
        DECR R6
        LDT  KRQ
        BRNEQ dnorpt
        LDAVR R7                ; a repeat count
        INCR R7
        DECR R6
        ADDI 0E0H               ; - 32
        MVARL R4
        BRZ  drone
        LDTI 94
        BRGT drone
        BR   drok
drone:  MVIB R4,1
drok:   LDAVR R7                ; the character it repeats
        INCR R7
        DECR R6
dnorpt: LDT  KEQ
        BRNEQ dnoeb
        LDAI 80H
        MVARH R3                ; bit 7 set
        LDAVR R7
        INCR R7
        DECR R6
        ANDI 7FH
dnoeb:  LDT  KCQ
        BRNEQ dnoctl
        LDAVR R7                ; the prefixed character
        INCR R7
        DECR R6
        MVARL R3
        ANDI 7FH
        LDTI 63
        BRLT dctl1              ; below ?: itself
        LDTI 95
        BRGT dctl1              ; above _: itself
        MVRLA R3
        XORI 40H
        MVARL R3
dctl1:  MVRLA R3
dnoctl: MVAT
        MVRHA R3
        ORT                     ; with its 8th bit
        MVARL R3
        LDA  KTXT
        BRZ  dput
        MVRLA R3
        LDTI 13
        BREQ dnext              ; text: no CR
dput:   MVRLA R3
        MVAT
dout:   MVTA
        STAVR R5
        INCR R5
        DECR R4
        MVRLA R4
        BRNZ dout
dnext:  MVRHA R6
        BRNZ ddone              ; passed 0: a prefix without its character
        MVRLA R6
        BRNZ dunit
ddone:  STR  R5,KOUT
        RET

; ---- kenc: file bytes straight into the data field ------------------------------------------------------------------
; KC = the byte in hand (a real byte), KBUF/KCNT = the rest of the file buffer (the next byte first), KOUT/KROOM = the
; data field. E-Kermit's encode1() for every byte that needs no repeat count and no 8th-bit prefix: a control
; character (bits 0-6 below 32, or DEL) goes as the control prefix and the byte XOR 64; a prefix character in use
; as the control prefix and itself; anything else as itself (bit 7 included when no 8th-bit prefix is in use). Then
; the next byte is the one in hand. Stops, leaving every word updated, when the buffer has no next byte (the caller
; refills), when repeat counts are on and the next byte is the same (a run: encode() counts it), at a byte with bit 7
; while 8th-bit prefixing is on, or when the room is used up (a prefixed byte needs 2). ~31 instructions a byte.
kenc:   LDR  R7,KBUF
        LDR  R6,KCNT
        LDR  R5,KOUT
        LDR  R4,KROOM
eloop:  MVRLA R6                ; the lookahead byte must be there
        BRNZ ehave
        MVRHA R6
        BRZ  edone
ehave:  LDA  KRQ
        BRZ  enorun
        LDAVR R7                ; the next byte
        LDT  KC
        BREQ edone              ; the same: a run
enorun: LDA  KC
        MVAT
        ANDI 80H
        BRZ  e7
        LDA  KEQ
        BRNZ edone              ; bit 7 with 8th-bit prefixing: encode()
e7:     MVTA
        ANDI 7FH                ; bits 0-6
        LDTI 32
        BRLT ectl
        LDTI 127
        BREQ ectl
        LDT  KCQ
        BREQ epfx
        LDT  KRQ                ; (0 when not in use: never matches, bits 0-6 are 32 or more here)
        BREQ epfx
        LDT  KEQ
        BREQ epfx
        LDA  KC                 ; as itself
        STAVR R5
        INCR R5
        DECR R4
        BR   enext
ectl:   LDA  KC
        XORI 40H
        BR   etwo
epfx:   LDA  KC
etwo:   MVAT                    ; TMP = what follows the prefix
        MVRLA R4
        ANDI 0FEH
        BRZ  edone              ; room for 1 only
        LDA  KCQ
        STAVR R5
        INCR R5
        MVTA
        STAVR R5
        INCR R5
        DECR R4
        DECR R4
enext:  LDAVR R7                ; the next byte is now in hand
        STA  KC
        INCR R7
        DECR R6
        MVRLA R4
        BRNZ eloop              ; the room is at most 94: its low byte counts
edone:  STR  R7,KBUF
        STR  R6,KCNT
        STR  R5,KOUT
        STR  R4,KROOM
        RET
