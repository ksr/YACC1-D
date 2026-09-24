/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../../opcodes.h"
#include "code.h"
#include "CodeGen.h"

/* YACC1-D 2026-09-24: LDR's and STR's second halves, shared with LDZ/STZ (the lines are LDR's and STR's own, moved
   here unchanged: records $E8-$F7 are byte-identical). IR holds the operand address. */
void loadRegFromIR(int reg) {               /* Rn.hi <- [IR], IR++, Rn.lo <- [IR] */
    putMemAtRegOnBus(IR);
    setSignal("-REG-FUNC-LD");
    setLdId(reg);
    setSignal("-HL-SWAP");
    writeCurrentLine();
    setSignal("REG-LD-HI");
    writeCurrentLine();
    clearSignal("REG-LD-HI");
    writeCurrentLine();
    clearSignal("-REG-FUNC-LD");
    clearSignal("-HL-SWAP");
    writeCurrentLine();
    setRdId(IR);
    writeCurrentLine();
    incrementReg(IR);

    putMemAtRegOnBus(IR);
    setSignal("-REG-FUNC-LD");
    setLdId(reg);
    writeCurrentLine();
    setSignal("REG-LD-LO");
    writeCurrentLine();
    clearSignal("REG-LD-LO");
    writeCurrentLine();
    clearSignal("-REG-FUNC-LD");
    writeCurrentLine();
}

void storeRegAtIR(int reg) {                /* [IR] <- Rn.hi, IR++, [IR] <- Rn.lo */
    setSignal("-REG-FUNC-RD");
    setRdId(reg);
    setSignal("-HL-SWAP");
    writeCurrentLine();
    putBustoRegMem(IR, "-REG-RD-HI");
    writeCurrentLine();
    setRdId(IR);
    writeCurrentLine();
    incrementReg(IR);

    clearSignal("-HL-SWAP");
    setSignal("-REG-FUNC-RD");
    setRdId(reg);
    writeCurrentLine();
    putBustoRegMem(IR, "-REG-RD-LO");
    writeCurrentLine();
}

/* YACC1-D 2026-09-24: LDZ/STZ's operand address: IR.hi <- ZP.hi, IR.lo <- the offset byte at PC, PC++.
   The first move is register to register on the HIGH lane: ZP (R6, card 1) is read with -REG-RD-HI only and IR
   (R2, card 0) is loaded with REG-LD-HI only; the two cards' straight transceivers carry the byte on DATA8..15
   (no -HL-SWAP: the swap is one bus line for both cards, and both ends here use the high lane). DATA0..7 carries
   card 1's pull-ups ($FF, the unread low lane) while nothing else drives it: memory is not read in this move.
   Source asserted one line before the load strobe and held one line after it, as MVIW does. */
void zpageAddress(void) {
    setSignal("-REG-FUNC-RD");
    setRdId(ZP);
    setSignal("-REG-RD-HI");
    setSignal("-REG-FUNC-LD");
    setLdId(IR);
    writeCurrentLine();
    setSignal("REG-LD-HI");
    writeCurrentLine();
    clearSignal("REG-LD-HI");
    writeCurrentLine();
    clearSignal("-REG-RD-HI");
    clearSignal("-REG-FUNC-RD");
    clearSignal("-REG-FUNC-LD");
    writeCurrentLine();

    putMemAtRegOnBus(PC);
    setSignal("-REG-FUNC-LD");
    setLdId(IR);
    writeCurrentLine();
    setSignal("REG-LD-LO");
    writeCurrentLine();
    clearSignal("REG-LD-LO");
    writeCurrentLine();
    clearSignal("-REG-FUNC-LD");
    clearSignal("-MEM-RD");
    writeCurrentLine();
    incrementReg(PC);
}

void registerOnlyInstructions() {
    int reg;
    int ins;

    //Decrement Register
    for (reg = 0; reg < 8; reg++) {
        ins = DECR | (reg & 0x07);
        startInstruction(ins);
        loadNextInstruction();
        initCurrentLine();

        decrementReg(reg);

        endInstruction();
        showCntlMemory(ins);
    }

    //Increment Register
    for (reg = 0; reg < 8; reg++) {
        ins = INCR | (reg & 0x07);
        startInstruction(ins);
        loadNextInstruction();
        initCurrentLine();

        incrementReg(reg);

        endInstruction();
        showCntlMemory(ins);
    }

    //load register low immediate 8 bit
    for (reg = 0; reg < 8; reg++) {
        ins = MVIB | (reg & 0x07);
        startInstruction(ins);
        loadNextInstruction();
        initCurrentLine();

        putMemAtRegOnBus(PC);

        setSignal("-REG-FUNC-LD");
        setLdId(reg);
        writeCurrentLine();
        setSignal("REG-LD-LO");
        writeCurrentLine();
        clearSignal("REG-LD-LO");
        writeCurrentLine();
        clearSignal("-REG-FUNC-LD");
        incrementReg(PC);

        endInstruction();
        showCntlMemory(ins);
    }

    //load tmp reg 0 immediate 
    ins = LDTI;
    startInstruction(ins);
    loadNextInstruction();
    initCurrentLine();

    putMemAtRegOnBus(PC);

    setSignal("-TMP-REG-LD0");
    writeCurrentLine();
    clearSignal("-TMP-REG-LD0");
    writeCurrentLine();
    incrementReg(PC);

    endInstruction();
    showCntlMemory(ins);

    //load register low & hi immediate 16 bit
    for (reg = 0; reg < 8; reg++) {
        ins = MVIW | (reg & 0x07);
        startInstruction(ins);
        loadNextInstruction();
        initCurrentLine();

        putMemAtRegOnBus(PC);

        setSignal("-REG-FUNC-LD");
        setLdId(reg);
        setSignal("-HL-SWAP");
        writeCurrentLine();
        setSignal("REG-LD-HI");
        writeCurrentLine();
        clearSignal("REG-LD-HI");
        writeCurrentLine();
        clearSignal("-REG-FUNC-LD");
        clearSignal("-HL-SWAP");

        incrementReg(PC);

        putMemAtRegOnBus(PC);

        setSignal("-REG-FUNC-LD");
        setLdId(reg);

        writeCurrentLine();
        setSignal("REG-LD-LO");
        writeCurrentLine();
        clearSignal("REG-LD-LO");
        writeCurrentLine();


        clearSignal("-REG-FUNC-LD");
        incrementReg(PC);

        endInstruction();
        showCntlMemory(ins);
    }
    //
    ins = MOVRR;
    startInstruction(ins);
    loadNextInstruction();
    initCurrentLine();

    putMemAtRegOnBus(PC);
    setSignal("OPERAND-CLK");
    writeCurrentLine();
    clearSignal("OPERAND-CLK");
    writeCurrentLine();
    clearSignal("-MEM-RD");
    writeCurrentLine();
    incrementReg(PC);

    setSignal("-2-BYTE-OPERAND-SEL");
    setSignal("-REG-FUNC-LD");
    setSignal("-REG-FUNC-RD");
    writeCurrentLine();

    setSignal("-REG-RD-LO");
    setSignal("-REG-RD-HI");
    writeCurrentLine();

    setSignal("REG-LD-LO");
    setSignal("REG-LD-HI");
    writeCurrentLine();

    clearSignal("REG-LD-LO");
    clearSignal("REG-LD-HI");
    writeCurrentLine();

    clearSignal("-REG-RD-LO");
    clearSignal("-REG-RD-HI");
    writeCurrentLine();

    endInstruction();
    showCntlMemory(ins);

    for (reg = 0; reg < 8; reg++) {
        ins = LDR | (reg & 0x07);
        startInstruction(ins);
        loadNextInstruction();
        initCurrentLine();

        putMemAtRegOnBus(PC);
        setSignal("-REG-FUNC-LD");
        setLdId(IR);
        setSignal("-HL-SWAP");
        setSignal("REG-LD-HI");
        writeCurrentLine();
        clearSignal("REG-LD-HI");
        writeCurrentLine();
        clearSignal("-REG-FUNC-LD");
        clearSignal("-HL-SWAP");
        writeCurrentLine();
        incrementReg(PC);

        putMemAtRegOnBus(PC);
        setSignal("-REG-FUNC-LD");
        setLdId(IR);
        writeCurrentLine();
        setSignal("REG-LD-LO");
        writeCurrentLine();
        clearSignal("REG-LD-LO");
        writeCurrentLine();
        clearSignal("-REG-FUNC-LD");
        clearSignal("-MEM-RD");
        writeCurrentLine();
        incrementReg(PC);

        loadRegFromIR(reg);

        endInstruction();
        showCntlMemory(ins);
    }

    for (reg = 0; reg < 8; reg++) {
        ins = STR | (reg & 0x07);
        startInstruction(ins);
        loadNextInstruction();
        initCurrentLine();

        putMemAtRegOnBus(PC);
        setSignal("-REG-FUNC-LD");
        setLdId(IR);
        setSignal("-HL-SWAP");
        writeCurrentLine();
        setSignal("REG-LD-HI");
        writeCurrentLine();
        clearSignal("REG-LD-HI");
        writeCurrentLine();
        clearSignal("-REG-FUNC-LD");
        clearSignal("-HL-SWAP");
        writeCurrentLine();
        incrementReg(PC);

        putMemAtRegOnBus(PC);
        setSignal("-REG-FUNC-LD");
        setLdId(IR);
        writeCurrentLine();
        setSignal("REG-LD-LO");
        writeCurrentLine();
        clearSignal("REG-LD-LO");
        writeCurrentLine();
        clearSignal("-REG-FUNC-LD");
        clearSignal("-MEM-RD");
        writeCurrentLine();
        incrementReg(PC);

        storeRegAtIR(reg);

        endInstruction();
        showCntlMemory(ins);
    }

    /* YACC1-D 2026-09-24: LDZ Rn,d ($80-$87) and STZ Rn,d ($88-$8F), two bytes: the word at (R6.hi : d), big-endian
       like LDR/STR. R6 (ZP) is the page register: only its high byte is used. The operand address is built in IR
       (R2) as LDR/STR build it, from the page register instead of a second address byte: zpageAddress(), then the
       LDR/STR tails above. d = 255 reads/writes its second byte at (page+1):00 (IR counts through). Rn = R2 is
       meaningless (IR is the address); Rn = R0 is never loaded (the R0 load gate), as for LDR. */
    for (reg = 0; reg < 8; reg++) {
        ins = LDZ | (reg & 0x07);
        startInstruction(ins);
        loadNextInstruction();
        initCurrentLine();
        zpageAddress();
        loadRegFromIR(reg);
        endInstruction();
        showCntlMemory(ins);
    }
    for (reg = 0; reg < 8; reg++) {
        ins = STZ | (reg & 0x07);
        startInstruction(ins);
        loadNextInstruction();
        initCurrentLine();
        zpageAddress();
        storeRegAtIR(reg);
        endInstruction();
        showCntlMemory(ins);
    }

    ins = LDA;
    startInstruction(ins);
    loadNextInstruction();
    initCurrentLine();

    putMemAtRegOnBus(PC);
    setSignal("-REG-FUNC-LD");
    setLdId(IR);
    setSignal("-HL-SWAP");
    setSignal("REG-LD-HI");
    writeCurrentLine();
    clearSignal("REG-LD-HI");
    writeCurrentLine();
    clearSignal("-REG-FUNC-LD");
    clearSignal("-HL-SWAP");
    writeCurrentLine();
    incrementReg(PC);

    putMemAtRegOnBus(PC);
    setSignal("-REG-FUNC-LD");
    setLdId(IR);
    writeCurrentLine();
    setSignal("REG-LD-LO");
    writeCurrentLine();
    clearSignal("REG-LD-LO");
    writeCurrentLine();
    clearSignal("-REG-FUNC-LD");
    clearSignal("-MEM-RD");
    writeCurrentLine();
    incrementReg(PC);

    putMemAtRegOnBus(IR);
    setSignal("-ALU-FUNC");
    setAlu(ALUDATA);
    writeCurrentLine();
    setSignal("-AC-LD");
    writeCurrentLine();
    clearSignal("-AC-LD");
    writeCurrentLine();

    endInstruction();
    showCntlMemory(ins);

    ins = LDT;
    startInstruction(ins);
    loadNextInstruction();
    initCurrentLine();

    putMemAtRegOnBus(PC);
    setSignal("-REG-FUNC-LD");
    setLdId(IR);
    setSignal("-HL-SWAP");
    setSignal("REG-LD-HI");
    writeCurrentLine();
    clearSignal("REG-LD-HI");
    writeCurrentLine();
    clearSignal("-REG-FUNC-LD");
    clearSignal("-HL-SWAP");
    writeCurrentLine();
    incrementReg(PC);

    putMemAtRegOnBus(PC);
    setSignal("-REG-FUNC-LD");
    setLdId(IR);
    writeCurrentLine();
    setSignal("REG-LD-LO");
    writeCurrentLine();
    clearSignal("REG-LD-LO");
    writeCurrentLine();
    clearSignal("-REG-FUNC-LD");
    clearSignal("-MEM-RD");
    writeCurrentLine();
    incrementReg(PC);

    putMemAtRegOnBus(IR);
    setSignal("-TMP-REG-LD0");
    writeCurrentLine();
    clearSignal("-TMP-REG-LD0");
    writeCurrentLine();

    endInstruction();
    showCntlMemory(ins);

    ins = STA;
    startInstruction(ins);
    loadNextInstruction();
    initCurrentLine();

    putMemAtRegOnBus(PC);
    setSignal("-REG-FUNC-LD");
    setLdId(IR);
    setSignal("-HL-SWAP");
    setSignal("REG-LD-HI");
    writeCurrentLine();
    clearSignal("REG-LD-HI");
    writeCurrentLine();
    clearSignal("-REG-FUNC-LD");
    clearSignal("-HL-SWAP");
    writeCurrentLine();
    incrementReg(PC);

    putMemAtRegOnBus(PC);
    setSignal("-REG-FUNC-LD");
    setLdId(IR);
    writeCurrentLine();
    setSignal("REG-LD-LO");
    writeCurrentLine();
    clearSignal("REG-LD-LO");
    writeCurrentLine();
    clearSignal("-REG-FUNC-LD");
    clearSignal("-MEM-RD");
    writeCurrentLine();
    incrementReg(PC);

    setSignal("-ALU-FUNC");
    setAlu(ALUDATA);
    writeCurrentLine();

    putBustoRegMem(IR, "-AC-RD");

    endInstruction();
    showCntlMemory(ins);


    ins = STT;
    startInstruction(ins);
    loadNextInstruction();
    initCurrentLine();

    putMemAtRegOnBus(PC);
    setSignal("-REG-FUNC-LD");
    setLdId(IR);
    setSignal("-HL-SWAP");
    setSignal("REG-LD-HI");
    writeCurrentLine();
    clearSignal("REG-LD-HI");
    writeCurrentLine();
    clearSignal("-REG-FUNC-LD");
    clearSignal("-HL-SWAP");
    writeCurrentLine();
    incrementReg(PC);

    //putBustoRegMem(IR, "-REG-RD-LO");
    putMemAtRegOnBus(PC);
    setSignal("-REG-FUNC-LD");
    setLdId(IR);
    writeCurrentLine();
    setSignal("REG-LD-LO");
    writeCurrentLine();
    clearSignal("REG-LD-LO");
    writeCurrentLine();
    clearSignal("-REG-FUNC-LD");
    clearSignal("-MEM-RD");
    writeCurrentLine();
    incrementReg(PC);

    putBustoRegMem(IR, "-TMP-REG-RD0");

    endInstruction();
    showCntlMemory(ins);
}
