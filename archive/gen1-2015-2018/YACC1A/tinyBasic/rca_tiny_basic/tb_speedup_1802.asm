;"TinyBasic interpreter Copyright 1976 Itty Bitty Computers,
; used by permission." 
;
;...I found that execution became excruciatingly slow, 
;simply due to the memory scan for GOTOs, GOSUBs, and RETURNs. 
;A simple patch to the interpreter converts it to a binary search,
;for about an order of magnitude speedup in execution time. 
;The necessary changes are listed in the Appendix. 
;- Tom Pittman, The First Book of Tiny BASIC Programs</
;
; APPENDIX - Binary Search Speedup Code 1802
; TINY BASIC BINARY SEARCH SPEEDUP -- 81 MAY 9 0000 ... 
; NOTE: one-byte Lines with Line in [3328 35831 bomb

 ORG 05DDH
FLINE: LBR SRCH 

 ORG 192 ;.. ASSUME THIS IS VACANT 

SRCH: PHI 11 
 LDA 13 
 PLO 11 
 INC 13 
 INC 13 
 LDA 13 ;.. GET PROG END
 SMI 1 
 PHI 8 
HALF: SEX 2 ;.. BISECT THE REGION
 GHI 11 
 STR 2 
 GHI 8 
 SM 
 LBNF FLINE 
 SHR 
 LBZ FLINE ;.. TOO SMALL 
 ADD
 PHI 15 
 LDI 0 
 PLO 15 
 INC 15 
FLNO: LDA 15 ;.. FIND A LINE NUMBER 
 XRI 13 
 BNZ FLNO
 INC 15 
 ADCI 1 
 SHR 
 BDF FLNO-1 ;..(SKIP TWO TO SYNC) 
 SEX 15 
 LDA 15 ;..END? 
 OR 
 BZ HIGHR ;.. YES. 
 GLO 10 
 SM
 DEC 15 
 GHI 10 
 SMB 
 BNF HIGHR 
 GLO 15 ;.. TOO LOW
 PLO 11 
 GHI 15 
 PHI 11 
 BR HALF
HIGHR: GHI 15 ;.. TOO HIGH 
 BR HALF-1  

 END
