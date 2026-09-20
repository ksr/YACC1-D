*Converted from `Notes.rtf` (saved 2025-03-06) by `tools/rtf_to_md.py`; the .rtf is the original.*

Sequencer Logic V2.0

Next version V2.1

Add SR Flip Flop out of extra gates for Branch Cond

SET with and of BRTest and BRCond
Clear with code-count-reset

Separate 2 byte opcode into 
    2 byte reg
    2 byte IO

If design goes down to 8 registers bit 3 of reg rd and ld can be repurposed

Cleanup naming sheet 5 - signal names for halt continue area
Ic36/8 FP-CONT
IC36.2 FP-HALT
IC36/9 -FP-CONT
IC36/1 -FP-HALT

U-Soft-Halt not connected to usoft-halt
    Should be the same signal

Not all index card notes transferred here yet
Expose Ucode-Count-Reset & Ins number for external debugger
Maybe expose reset signal

HALT LED
