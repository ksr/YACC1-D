; y1cc: div.c  (2026-09-23 18:15)
; R3 = expression accumulator, R4 = operand, R5-R7 runtime scratch, R2 never used (hardware IR)
        ORG 12288
f_main:
        MVIW R3,bss_start
Lz1:
        MVRHA R3
        LDTI (bss_end).1
        BRNEQ Lzg2
        MVRLA R3
        LDTI (bss_end).0
        BREQ Lzd3
Lzg2:
        LDAI 0
        STAVR R3
        INCR R3
        BR Lz1
Lzd3:
        MVIW R3,s4
        STR R3,pr_s
        MVIW R3,64836
        STR R3,pr_v
        JSR f_pr
        MVIW R3,64836
        STR R3,main_x
        MVIW R4,10
        JSR rt_divmod
        STR R3,main_q
        MVIW R3,s5
        STR R3,pr_s
        LDR R3,main_q
        STR R3,pr_v
        JSR f_pr
        LDR R3,main_x
        MVIW R4,10
        JSR rt_divmod
        MOVRR R5,R3
        STR R3,main_r
        MVIW R3,s6
        STR R3,pr_s
        LDR R3,main_r
        STR R3,pr_v
        JSR f_pr
        MVIW R3,32768
        STR R3,main_x
        MVIW R3,s7
        STR R3,pr_s
        LDR R3,main_x
        MVIW R4,10
        JSR rt_divmod
        STR R3,pr_v
        JSR f_pr
        MVIW R3,32767
        STR R3,main_x
        MVIW R3,s8
        STR R3,pr_s
        LDR R3,main_x
        MVIW R4,10
        JSR rt_divmod
        STR R3,pr_v
        JSR f_pr
        MVIW R3,40000
        STR R3,main_x
        MVIW R3,s9
        STR R3,pr_s
        LDR R3,main_x
        MVIW R4,10
        JSR rt_divmod
        STR R3,pr_v
        JSR f_pr
        MVIW R3,700
        STR R3,main_x
        MVIW R3,s10
        STR R3,pr_s
        LDR R3,main_x
        MVIW R4,10
        JSR rt_divmod
        STR R3,pr_v
        JSR f_pr
        MVIW R3,65535
        STR R3,main_x
        MVIW R3,s11
        STR R3,pr_s
        LDR R3,main_x
        MVIW R4,7
        JSR rt_divmod
        STR R3,pr_v
        JSR f_pr
        MVIW R3,32768
        STR R3,main_x
        MVIW R3,s12
        STR R3,pr_s
        LDR R3,main_x
        LDAI 0
        CSHL
        MVRHA R3
        CSHR
        MVARH R3
        MVRLA R3
        CSHR
        MVARL R3
        STR R3,pr_v
        JSR f_pr
        MVIW R3,16384
        STR R3,main_x
        MVIW R3,s13
        STR R3,pr_s
        LDR R3,main_x
        MVRLA R3
        MVAT
        ADDT
        MVARL R3
        MVRHA R3
        MVAT
        ADDTC
        MVARH R3
        STR R3,pr_v
        JSR f_pr
        MVIW R3,64836
        STR R3,main_x
        MVIW R3,s14
        STR R3,pr_s
        LDR R3,main_x
        LDAI 0
        CSHL
        MVRHA R3
        CSHR
        MVARH R3
        MVRLA R3
        CSHR
        MVARL R3
        LDAI 0
        CSHL
        MVRHA R3
        CSHR
        MVARH R3
        MVRLA R3
        CSHR
        MVARL R3
        LDAI 0
        CSHL
        MVRHA R3
        CSHR
        MVARH R3
        MVRLA R3
        CSHR
        MVARL R3
        STR R3,pr_v
        JSR f_pr
        MVIW R3,300
        STR R3,main_x
        MVIW R3,1000
        STR R3,main_q
        MVIW R3,s15
        STR R3,pr_s
        LDR R3,main_x
        LDR R4,main_q
        JSR rt_sub
        STR R3,pr_v
        JSR f_pr
        MVIW R3,50000
        STR R3,main_x
        MVIW R3,20000
        STR R3,main_q
        MVIW R3,s16
        STR R3,pr_s
        LDR R3,main_x
        LDR R4,main_q
        MVRLA R4
        MVAT
        MVRLA R3
        ADDT
        MVARL R3
        MVRHA R4
        MVAT
        MVRHA R3
        ADDTC
        MVARH R3
        STR R3,pr_v
        JSR f_pr
        MVIW R3,300
        STR R3,main_x
        MVIW R3,7
        STR R3,main_q
        MVIW R3,s17
        STR R3,pr_s
        LDR R3,main_x
        LDR R4,main_q
        JSR rt_mul
        STR R3,pr_v
        JSR f_pr
        MVIW R3,40000
        STR R3,main_x
        MVIW R3,3
        STR R3,main_q
        MVIW R3,s18
        STR R3,pr_s
        LDR R3,main_x
        LDR R4,main_q
        JSR rt_mul
        STR R3,pr_v
        JSR f_pr
        MVIW R3,s19
        STR R3,putstr_s
        JSR f_putstr
        LDAI 10
        JSR rt_putc
        RET
f_putstr:
Ltop20:
        LDR R3,putstr_s
        LDAVR R3
        BRZ Lend21
        LDR R3,putstr_s
        MOVRR R3,R4
        INCR R3
        STR R3,putstr_s
        MOVRR R4,R3
        LDAVR R3
        JSR rt_putc
        BR Ltop20
Lend21:
        RET
f_puthex2:
        LDR R3,puthex2_n
        MVIW R4,4
        JSR rt_shr
        MVRLA R3
        ANDI 15
        MVARL R3
        MVRHA R3
        ANDI 0
        MVARH R3
        LDAI 0
        MVARH R3
        STR R3,puthex2_d
        LDA puthex2_d+1
        LDTI 10
        BRLT Ls24
        BR Lf22
Ls24:
        LDR R3,puthex2_d
        MVRLA R3
        ADDI 48
        MVARL R3
        MVRHA R3
        ADDIC 0
        MVARH R3
        BR Le23
Lf22:
        LDR R3,puthex2_d
        MVRLA R3
        ADDI 65
        MVARL R3
        MVRHA R3
        ADDIC 0
        MVARH R3
        MVRLA R3
        ADDI 246
        MVARL R3
        MVRHA R3
        ADDIC 255
        MVARH R3
Le23:
        MVRLA R3
        JSR rt_putc
        LDR R3,puthex2_n
        MVRLA R3
        ANDI 15
        MVARL R3
        MVRHA R3
        ANDI 0
        MVARH R3
        LDAI 0
        MVARH R3
        STR R3,puthex2_d
        LDA puthex2_d+1
        LDTI 10
        BRLT Ls27
        BR Lf25
Ls27:
        LDR R3,puthex2_d
        MVRLA R3
        ADDI 48
        MVARL R3
        MVRHA R3
        ADDIC 0
        MVARH R3
        BR Le26
Lf25:
        LDR R3,puthex2_d
        MVRLA R3
        ADDI 65
        MVARL R3
        MVRHA R3
        ADDIC 0
        MVARH R3
        MVRLA R3
        ADDI 246
        MVARL R3
        MVRHA R3
        ADDIC 255
        MVARH R3
Le26:
        MVRLA R3
        JSR rt_putc
        RET
f_puthex:
        LDR R3,puthex_n
        MVRHA R3
        MVARL R3
        LDAI 0
        MVARH R3
        STR R3,puthex2_n
        JSR f_puthex2
        LDR R3,puthex_n
        STR R3,puthex2_n
        JSR f_puthex2
        RET
f_pr:
        LDR R3,pr_s
        STR R3,putstr_s
        JSR f_putstr
        LDR R3,pr_v
        STR R3,puthex_n
        JSR f_puthex
        LDAI 10
        JSR rt_putc
        RET
; dropped (never called): putnum
; dropped (never called): strlen
; dropped (never called): strcmp
; dropped (never called): strcpy
; dropped (never called): memset
; runtime rt_sub
rt_sub: MVRHA R4
        INVA
        MVARH R4
        MVRLA R4
        INVA
        MVAT
        LDAI 255
        ADDI 1
        MVRLA R3
        ADDTC
        MVARL R3
        MVRHA R4
        MVAT
        MVRHA R3
        ADDTC
        MVARH R3
        RET
; runtime rt_mul
rt_mul: MVIW R5,0
rt_mul_l: MVRLA R4
        MVAT
        MVRHA R4
        ORT
        BRZ rt_mul_d
        MVRLA R4
        ANDI 1
        BRZ rt_mul_s
        MVRLA R3
        MVAT
        MVRLA R5
        ADDT
        MVARL R5
        MVRHA R3
        MVAT
        MVRHA R5
        ADDTC
        MVARH R5
rt_mul_s: MVRLA R3
        MVAT
        ADDT
        MVARL R3
        MVRHA R3
        MVAT
        ADDTC
        MVARH R3
        LDAI 0
        CSHL
        MVRHA R4
        CSHR
        MVARH R4
        MVRLA R4
        CSHR
        MVARL R4
        BR rt_mul_l
rt_mul_d: MOVRR R5,R3
        RET
; runtime rt_divmod
rt_divmod: MVIW R6,0
        MVIW R7,16
rt_dm_l: MVRLA R3
        MVAT
        ADDT
        MVARL R3
        MVRHA R3
        MVAT
        ADDTC
        MVARH R3
        MVRLA R6
        MVAT
        ADDTC
        MVARL R6
        MVRHA R6
        MVAT
        ADDTC
        MVARH R6
        MVRHA R4
        MVAT
        MVRHA R6
        BRLT rt_dm_n
        BRNEQ rt_dm_y
        MVRLA R4
        MVAT
        MVRLA R6
        BRLT rt_dm_n
rt_dm_y: MVRLA R4
        MVAT
        MVRLA R6
        BRLT rt_dm_b
        SUBT
        MVARL R6
        MVRHA R4
        MVAT
        MVRHA R6
        SUBT
        MVARH R6
        INCR R3
        BR rt_dm_n
rt_dm_b: SUBT
        MVARL R6
        MVRHA R4
        MVAT
        MVRHA R6
        SUBT
        SUBI 1
        MVARH R6
        INCR R3
rt_dm_n: DECR R7
        MVRLA R7
        BRNZ rt_dm_l
        MOVRR R6,R5
        RET
; runtime rt_shr
rt_shr: MVRLA R4
        BRZ rt_shr_d
rt_shr_l: LDAI 0
        CSHL
        MVRHA R3
        CSHR
        MVARH R3
        MVRLA R3
        CSHR
        MVARL R3
        DECR R4
        MVRLA R4
        BRNZ rt_shr_l
rt_shr_d: RET
; runtime rt_putc
rt_putc: BRDEV rt_putc_h
        OUTA P2
        RET
rt_putc_h: JSR 65476
        RET
s4:
        DB 65,32,54,52,56,51,54,61,0
s5:
        DB 66,32,54,52,56,51,54,47,49,48,61,0
s6:
        DB 67,32,54,52,56,51,54,37,49,48,61,0
s7:
        DB 68,32,51,50,55,54,56,47,49,48,61,0
s8:
        DB 69,32,51,50,55,54,55,47,49,48,61,0
s9:
        DB 70,32,52,48,48,48,48,47,49,48,61,0
s10:
        DB 71,32,55,48,48,47,49,48,61,0
s11:
        DB 72,32,54,53,53,51,53,47,55,61,0
s12:
        DB 73,32,51,50,55,54,56,62,62,49,61,0
s13:
        DB 74,32,49,54,51,56,52,60,60,49,61,0
s14:
        DB 75,32,54,52,56,51,54,62,62,51,61,0
s15:
        DB 76,32,51,48,48,45,49,48,48,48,61,0
s16:
        DB 77,32,53,48,48,48,48,43,50,48,48,48,48,61,0
s17:
        DB 78,32,51,48,48,42,55,61,0
s18:
        DB 79,32,52,48,48,48,48,42,51,61,0
s19:
        DB 69,78,68,0
bss_start:
main_x: DS 2
main_q: DS 2
main_r: DS 2
putstr_s: DS 2
puthex2_n: DS 2
puthex2_d: DS 2
puthex_n: DS 2
pr_s: DS 2
pr_v: DS 2
bss_end: DS 1
        END 12288
