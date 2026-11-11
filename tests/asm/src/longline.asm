; Author: Claude (Anthropic) for Ken Rother's YACC1 project, 2026

; longline.asm - lines of 100 to 254 characters, for tests/asm/run.py (2026-11-11). Every line assembles in RC/asm
; (software/assembler) with 0 errors and /bin/asm must produce the same bytes. Until 2026-11-11 RC/asm died with
; status 133 and no message on a line whose text after the label, or after the leading blanks, was 100 characters
; or more (docs/programming/ASSEMBLER.md, quirk 12). 254 characters is the limit (err_line.asm has 255). The
; lengths matter: run.py checks that the longest line here is 254 characters. Not a program: never run.
        ORG 3000H
; 19 operands after a label, 102 characters after the colon: the line that showed the fault
t1:     DB 000h,001h,002h,003h,004h,005h,006h,007h,008h,009h,00ah,00bh,00ch,00dh,00eh,00fh,010h,011h,012h
; no label: 127 characters after the leading blanks
        DB 020h,021h,022h,023h,024h,025h,026h,027h,028h,029h,02ah,02bh,02ch,02dh,02eh,02fh,030h,031h,032h,033h,034h,035h,036h,037h,038h
; exactly 99 and exactly 100 characters after the colon, then after the leading blanks (99 always assembled)
e99: DB 001H,002H,003H,004H,005H,006H,007H,008H,009H,00AH,00BH,00CH,00DH,00EH,00FH,010H,011H,012H,00007
e100: DB 001H,002H,003H,004H,005H,006H,007H,008H,009H,00AH,00BH,00CH,00DH,00EH,00FH,010H,011H,012H,013H,7
        DB 001H,002H,003H,004H,005H,006H,007H,008H,009H,00AH,00BH,00CH,00DH,00EH,00FH,010H,011H,012H,013H,7
        DB 001H,002H,003H,004H,005H,006H,007H,008H,009H,00AH,00BH,00CH,00DH,00EH,00FH,010H,011H,012H,013H,07
; words, a string in double quotes (upper-cased) with a ';' and a ':' past column 100, one in single quotes (as written)
        DW 01111H,02222H,03333H,04444H,05555H,06666H,07777H,08888H,09999H,0AAAAH,0BBBBH,0CCCCH,0DDDDH,0EEEEH,0FFFFH,01111H,02222H,03333H,04444H,05555H
msg:    DB "the quick brown fox jumps over the lazy dog, and the lazy dog takes no notice of the quick brown fox at all; none: not one bit",13,10,0
        DB 'the quick brown fox jumps over the lazy dog, and the lazy dog takes no notice of the quick brown fox at all, none, not one bit'
; one expression of 23 tokens and 107 characters as a byte, and as a word
        LDAI 0000001H+0000002H+0000003H+0000004H+0000005H+0000006H+0000007H+0000008H+0000009H+0000010H+0000011H+0000012H
        MVIW R3,0000001H+0000002H+0000003H+0000004H+0000005H+0000006H+0000007H+0000008H+0000009H+0000010H+0000011H+0000012H+1000H
; a label of 29 characters, the longest, and lines that name it four times (with -x its cross-reference lines too:
; until 2026-11-11 the cross-reference died with status 134 at a referenced label of 20 characters or more)
abcdefghijabcdefghijabcdefghi: DB 040h,041h,042h,043h,044h,045h,046h,047h,048h,049h,04ah,04bh,04ch,04dh,04eh,04fh,050h,051h,052h,053h
        DW abcdefghijabcdefghijabcdefghi,abcdefghijabcdefghijabcdefghi+1,(abcdefghijabcdefghijabcdefghi).0,(abcdefghijabcdefghijabcdefghi).1
        MVIW R4,(abcdefghijabcdefghijabcdefghi+256).1+(abcdefghijabcdefghijabcdefghi).0*2+(abcdefghijabcdefghijabcdefghi-abcdefghijabcdefghijabcdefghi)+3
; a short instruction whose comment takes the line to 254 characters, then data lines of 253 and of 254
        LDAI 5                          ; the comment counts towards the 254 characters of a line the comment counts towards the 254 characters of a line the comment counts towards the 254 characters of a line the comment counts towards the 254 character
        DB 001H,002H,003H,004H,005H,006H,007H,008H,009H,00AH,00BH,00CH,00DH,00EH,00FH,010H,011H,012H,013H,014H,015H,016H,017H,018H,019H,01AH,01BH,01CH,01DH,01EH,01FH,020H,021H,022H,023H,024H,025H,026H,027H,028H,029H,02AH,02BH,02CH,02DH,02EH,02FH,030H,07
        DB 001H,002H,003H,004H,005H,006H,007H,008H,009H,00AH,00BH,00CH,00DH,00EH,00FH,010H,011H,012H,013H,014H,015H,016H,017H,018H,019H,01AH,01BH,01CH,01DH,01EH,01FH,020H,021H,022H,023H,024H,025H,026H,027H,028H,029H,02AH,02BH,02CH,02DH,02EH,02FH,030H,007
last:   DB 001H,002H,003H,004H,005H,006H,007H,008H,009H,00AH,00BH,00CH,00DH,00EH,00FH,010H,011H,012H,013H,014H,015H,016H,017H,018H,019H,01AH,01BH,01CH,01DH,01EH,01FH,020H,021H,022H,023H,024H,025H,026H,027H,028H,029H,02AH,02BH,02CH,02DH,02EH,02FH,030H,007
        HALT
