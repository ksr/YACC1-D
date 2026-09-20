Last updated Sept 6 2016 Herb Johnson

rca.asm		RCA Tiny BASIC based on Lee Hart / TMSI version 
rca.prn		check and fix to match RCA's hex dump,
rca.hex		and modified for A18 cross-assembler

1802reg.asm		equates for R0...RF registers

tiny_basic_1.jpg	pages from RCA manual MPM-203 of
tiny_basic_2.jpg	RCA Tiny BASIC hex dump
			from Chuck Yakym via Yahoo cosmacelf group.
			please verify by comparison. 
			Let me know of any differences. Thank you.

18S020_TinyBASIC_edit.rtf
			RTF formatted, manual for TB from MPM-203
18S020_TinyBASIC_edit.txt
			unformatted, manual for TB from MPM-203
			Please compare with PDF of MPM-203 manual

lee_vs_rca.txt	notes, hex disassembly of RCA TB 
			vs TMSI Tiny BASIC source
			by Herb Johnson Sept 2016

tb_pittman.txt	exerpt of Tiny BASIC from Pittman, IL code only

hart_TB_IL.txt	IL op codes - same for TMSI and Pittman

tmsi_vs_tb.txt	Lee Hart formerly of TMSI, compares RCA Tiny BASIC,
			Pittman TB for 1802, and TMSI TB. 
			
tb_speedup.*	From Tom Pittman's "The First Book of Tiny BASIC Programs"
			speedup to find GOTO and GOSUB's - untested patch

tb_yakym_cold.*	Chuck Yakym's patch to speed up cold-start search for RAM

chuck_tb_relocate.htm  Chuck Yakym's comments on relocating Tiny BASIC


According to Tom Pittman's Web site, http://www.ittybittycomputers.com/
he says "Tiny BASIC is free to use." 
He asks the following be added to his Tiny BASIC codes: 
"TinyBasic interpreter Copyright 1976 Itty Bitty Computers, used by permission." 