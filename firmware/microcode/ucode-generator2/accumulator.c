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

void aluOp(int func) {
    setSignal("-ALU-FUNC");
    /* YACC1-D 2026-09-23: clear the shift-out flip-flop before every add/subtract. The carry flip-flop IC9A latches
       CO/BO OR SHIFT-OUT (IC7A) on every add/sub/shift AC-LD, so a 1 left in IC9B by an earlier shift set the carry
       of the next add/subtract (found on the machine: 300-1000 gave $FE44, divisions after a puthex gave $FFFF;
       tests/bench/diag/div.c). A parallel load of the shift register (SHIFT_LOAD, -SR-LD) clocks IC9B with D = 0
       (IC32 selects 0 in load mode) and touches neither the accumulator nor the carry. Mode set one step before the
       strobe, as shiftOp() does. */
    if ((func & 7) == ALUADD || (func & 7) == ALUSUB) {
        setAlu(SHIFT_LOAD);
        writeCurrentLine();
        setSignal("-SR-LD");
        writeCurrentLine();
        clearSignal("-SR-LD");
    }
    setAlu(func);
    writeCurrentLine();
    setSignal("-AC-LD");
    writeCurrentLine();
    clearSignal("-AC-LD");
    writeCurrentLine();
}

void shiftOp(int instruction, int mode) {

    startInstruction(instruction);
    loadNextInstruction();
    initCurrentLine();

    setSignal("-ALU-FUNC");
    setAlu(SHIFT_LOAD);
    writeCurrentLine();
    setSignal("-SR-LD");
    writeCurrentLine();
    clearSignal("-SR-LD");
    writeCurrentLine();
    setAlu(mode);
    writeCurrentLine();
    setSignal("-SR-LD");
    writeCurrentLine();
    clearSignal("-SR-LD");
    writeCurrentLine();

    setAlu(ALUSHIFT);
    writeCurrentLine();
    setSignal("-AC-LD");
    writeCurrentLine();
    clearSignal("-AC-LD");
    writeCurrentLine(); // clear reg-func-rd?

    endInstruction();
    showCntlMemory(instruction);
}


/* YACC1-D 2026-09-24: the 16-bit register arithmetic of ADDIW and SHL16, built from the proven single-byte steps
   (MVRLA/MVRHA/MVARL/MVARH and aluOp). Each byte goes through the accumulator; the low byte's add sets the carry
   flip-flop and the high byte's add (ALUADD|CARRY_SHIFT) takes it in, with only register moves between the two
   (MVARL/MVRHA do not clock the carry), the idiom ADDI/ADDIC and ADDT/ADDTC already use. aluOp() clears SHIFT-OUT
   before each add. Afterwards: ACC = the result's high byte, carry = the carry out of bit 15, TMP0 untouched. */
static void accFromRegByte(int reg, int hi) {       /* MVRLA / MVRHA: ACC <- Rn.lo or Rn.hi, the read left asserted */
    setSignal("-REG-FUNC-RD");
    setRdId(reg);
    setSignal(hi ? "-REG-RD-HI" : "-REG-RD-LO");
    if (hi) setSignal("-HL-SWAP");
    setSignal("-ALU-FUNC");
    setAlu(ALUDATA);
    writeCurrentLine();
    setSignal("-AC-LD");
    writeCurrentLine();
    clearSignal("-AC-LD");
    writeCurrentLine();
}
static void releaseRegRead(void) {
    clearSignal("-REG-RD-LO");
    clearSignal("-REG-RD-HI");
    clearSignal("-HL-SWAP");
    clearSignal("-REG-FUNC-RD");
    writeCurrentLine();
}
static void regByteFromAcc(int reg, int hi) {       /* MVARL / MVARH: Rn.lo or Rn.hi <- ACC */
    setSignal("-ALU-FUNC");
    setAlu(ALUDATA);
    setSignal("-AC-RD");
    writeCurrentLine();
    setSignal("-REG-FUNC-LD");
    if (hi) setSignal("-HL-SWAP");
    setLdId(reg);
    writeCurrentLine();
    setSignal(hi ? "REG-LD-HI" : "REG-LD-LO");
    writeCurrentLine();
    clearSignal(hi ? "REG-LD-HI" : "REG-LD-LO");
    writeCurrentLine();
    clearSignal("-REG-FUNC-LD");
    clearSignal("-HL-SWAP");
    clearSignal("-AC-RD");
    writeCurrentLine();
}

void accumulatorInstructions() {
    int ins, reg;

    //Move register low to accumulator
    for (reg = 0; reg < 8; reg++) {
        ins = MVRLA | (reg & 0x07);
        startInstruction(ins);
        loadNextInstruction();
        initCurrentLine();

        setSignal("-REG-FUNC-RD");
        setRdId(reg);
        setSignal("-REG-RD-LO");
        setSignal("-ALU-FUNC");
        setAlu(ALUDATA);
        writeCurrentLine();
        setSignal("-AC-LD");
        writeCurrentLine();
        clearSignal("-AC-LD");
        writeCurrentLine();

        endInstruction();
        showCntlMemory(ins);
    }

    //Move register high to accumulator
    for (reg = 0; reg < 8; reg++) {
        ins = MVRHA | (reg & 0x07);
        startInstruction(ins);
        loadNextInstruction();
        initCurrentLine();

        setSignal("-REG-FUNC-RD");
        setRdId(reg);
        setSignal("-REG-RD-HI");
        setSignal("-HL-SWAP");
        setSignal("-ALU-FUNC");
        setAlu(ALUDATA);
        writeCurrentLine();
        setSignal("-AC-LD");
        writeCurrentLine();
        clearSignal("-AC-LD");
        writeCurrentLine();

        endInstruction();
        showCntlMemory(ins);
    }

    //Move accumulator to register Low
    for (reg = 0; reg < 8; reg++) {
        ins = MVARL | (reg & 0x07);
        startInstruction(ins);
        loadNextInstruction();
        initCurrentLine();

        setSignal("-ALU-FUNC");
        setAlu(ALUDATA);
        setSignal("-AC-RD");
        writeCurrentLine();

        setSignal("-REG-FUNC-LD");
        setLdId(reg);

        writeCurrentLine();
        setSignal("REG-LD-LO");
        writeCurrentLine();
        clearSignal("REG-LD-LO");
        writeCurrentLine();
        clearSignal("-REG-FUNC-LD");

        writeCurrentLine();

        endInstruction();
        showCntlMemory(ins);
    }

    //Move accumulator to register High
    for (reg = 0; reg < 8; reg++) {
        ins = MVARH | (reg & 0x07);
        startInstruction(ins);
        loadNextInstruction();
        initCurrentLine();

        setSignal("-ALU-FUNC");
        setAlu(ALUDATA);
        setSignal("-AC-RD");
        writeCurrentLine();

        setSignal("-REG-FUNC-LD");
        setSignal("-HL-SWAP"); // needs testing Sept 21 entering address in montitor not working
        setLdId(reg);

        writeCurrentLine();
        setSignal("REG-LD-HI");
        writeCurrentLine();
        clearSignal("REG-LD-HI");
        writeCurrentLine();
        clearSignal("-REG-FUNC-LD");
        writeCurrentLine();

        endInstruction();
        showCntlMemory(ins);
    }

    //Load accumulator From MEM pointed to by REG
    for (reg = 0; reg < 8; reg++) {
        ins = LDAVR | (reg & 0x07);
        startInstruction(ins);
        loadNextInstruction();
        initCurrentLine();

        putMemAtRegOnBus(reg);

        setSignal("-ALU-FUNC");
        setAlu(ALUDATA);
        writeCurrentLine();
        setSignal("-AC-LD");
        writeCurrentLine();
        clearSignal("-AC-LD");
        writeCurrentLine();

        endInstruction();
        showCntlMemory(ins);
    }

    //Store accumulator at  MEM pointed to by REG
    for (reg = 0; reg < 8; reg++) {
        ins = STAVR | (reg & 0x07);
        startInstruction(ins);
        loadNextInstruction();
        initCurrentLine();

        setSignal("-ALU-FUNC");
        setAlu(ALUDATA);
        writeCurrentLine();

        putBustoRegMem(reg, "-AC-RD");

        endInstruction();
        showCntlMemory(ins);
    }

    //load accumulator immediate
    ins = LDAI;
    startInstruction(ins);
    loadNextInstruction();
    initCurrentLine();

    putMemAtRegOnBus(PC);

    setSignal("-ALU-FUNC");
    setAlu(ALUDATA);
    writeCurrentLine();
    setSignal("-AC-LD");
    writeCurrentLine();
    clearSignal("-AC-LD");
    writeCurrentLine();

    incrementReg(PC);

    endInstruction();
    showCntlMemory(ins);

// Math and Logic operations
    
//Invert accumulator 
    ins = INVA;
    startInstruction(ins);
    loadNextInstruction();
    initCurrentLine();

    setSignal("-ALU-FUNC");
    setAlu(ALUDATA);
    setSignal("-AC-RD");
    setSignal("-AC-LD-INV");
    writeCurrentLine();
    setSignal("-AC-LD");
    writeCurrentLine();
    clearSignal("-AC-LD");
    writeCurrentLine();

    endInstruction();
    showCntlMemory(ins);

//Addition
    
    //Add to accumulator low immediate 8 bit
    ins = ADDI;
    startInstruction(ins);
    loadNextInstruction();
    initCurrentLine();

    putMemAtRegOnBus(PC);

    aluOp(ALUADD);

    incrementReg(PC);

    endInstruction();
    showCntlMemory(ins);
    
    //Add to accumulator low immediate 8 bit with carry
    ins = ADDIC;
    startInstruction(ins);
    loadNextInstruction();
    initCurrentLine();

    putMemAtRegOnBus(PC);

    aluOp(ALUADD|CARRY_SHIFT);

    incrementReg(PC);

    endInstruction();
    showCntlMemory(ins);
    
    //ADD TMP to accumulator
    ins = ADDT;
    startInstruction(ins);
    loadNextInstruction();
    initCurrentLine();

    setSignal("-TMP-REG-RD0");
    clearSignal("-MEM-RD");
    writeCurrentLine();

    aluOp(ALUADD);

    endInstruction();
    showCntlMemory(ins);
    
    //ADD TMP accumulator with CARRY
    ins = ADDTC;
    startInstruction(ins);
    loadNextInstruction();
    initCurrentLine();

    setSignal("-TMP-REG-RD0");
    clearSignal("-MEM-RD");
    writeCurrentLine();

    aluOp(ALUADD|CARRY_SHIFT);

    endInstruction();
    showCntlMemory(ins);

#define subnew
#ifdef subnew
// subtraction
    
    // Sub from accumulator low immediate 8 bit
    ins = SUBI;
    startInstruction(ins);
    loadNextInstruction();
    initCurrentLine();

    putMemAtRegOnBus(PC);
    aluOp(ALUSUB);
    incrementReg(PC);
    
    endInstruction();
    showCntlMemory(ins);

    // sub TMP from accumulator
    ins = SUBT;
    startInstruction(ins);
    loadNextInstruction();
    initCurrentLine();

    setSignal("-TMP-REG-RD0");
    clearSignal("-MEM-RD");
    writeCurrentLine();
    aluOp(ALUSUB);

    endInstruction();
    showCntlMemory(ins);
#endif
    
#ifdef subold
// subtraction
    
    // Sub from accumulator low immediate 8 bit
    ins = SUBI;
    startInstruction(ins);
    loadNextInstruction();
    initCurrentLine();

    setSignal("-AC-RD");
    setSignal("-ALU-FUNC");
    writeCurrentLine();
    setSignal("-TMP-REG-LD1");
    writeCurrentLine();
    clearSignal("-TMP-REG-LD1");
    writeCurrentLine();
    clearSignal("-AC-RD");
    writeCurrentLine();

    putMemAtRegOnBus(PC);

    setAlu(ALUDATA);
    setSignal("-AC-LD");
    writeCurrentLine();
    clearSignal("-AC-LD");
    writeCurrentLine();
    clearSignal("-MEM-RD");
    setSignal("-TMP-REG-RD1");
    writeCurrentLine();

    aluOp(ALUSUB);

    incrementReg(PC);

    endInstruction();
    showCntlMemory(ins);

    // sub TMP from accumulator
    ins = SUBT;
    startInstruction(ins);
    loadNextInstruction();
    initCurrentLine();

    setSignal("-AC-RD");
    setSignal("-ALU-FUNC");
    writeCurrentLine();
    setSignal("-TMP-REG-LD1");
    writeCurrentLine();
    clearSignal("-TMP-REG-LD1");
    writeCurrentLine();
    clearSignal("-AC-RD");
    writeCurrentLine();

    //putMemAtRegOnBus(PC);
    setSignal("-TMP-REG-RD0");

    setAlu(ALUDATA);
    setSignal("-AC-LD");
    writeCurrentLine();
    clearSignal("-AC-LD");
    writeCurrentLine();
    //clearSignal("-MEM-RD");
    clearSignal("-TMP-REG-RD0");
    setSignal("-TMP-REG-RD1");
    writeCurrentLine();

    aluOp(ALUSUB);

    //incrementReg(PC);

    endInstruction();
    showCntlMemory(ins);
#endif
    
//Boolean
    
    //AND to  Accum low immediate 8 bit
    ins = ANDI;
    startInstruction(ins);
    loadNextInstruction();
    initCurrentLine();

    putMemAtRegOnBus(PC);

    aluOp(ALUAND);

    incrementReg(PC);

    endInstruction();
    showCntlMemory(ins);
    
    //AND Accum with tmp
    ins = ANDT;
    startInstruction(ins);
    loadNextInstruction();
    initCurrentLine();

    setSignal("-TMP-REG-RD0");
    writeCurrentLine();

    aluOp(ALUAND);

    endInstruction();
    showCntlMemory(ins);

    //OR to Accum low immediate 8 bit
    ins = ORI;
    startInstruction(ins);
    loadNextInstruction();
    initCurrentLine();

    putMemAtRegOnBus(PC);

    aluOp(ALUOR);

    incrementReg(PC);

    endInstruction();
    showCntlMemory(ins);
    
    //OR Accum with tmp
    ins = ORT;
    startInstruction(ins);
    loadNextInstruction();
    initCurrentLine();

    setSignal("-TMP-REG-RD0");
    clearSignal("-MEM-RD");
    writeCurrentLine();

    aluOp(ALUOR);

    endInstruction();
    showCntlMemory(ins);

    //XORI to  Accum low immediate 8 bit
    ins = XORI;
    startInstruction(ins);
    loadNextInstruction();
    initCurrentLine();

    putMemAtRegOnBus(PC);

    aluOp(ALUXOR);

    incrementReg(PC);

    endInstruction();
    showCntlMemory(ins);

    //XOR to  Accum with tmp
    ins = XORT;
    startInstruction(ins);
    loadNextInstruction();
    initCurrentLine();

    setSignal("-TMP-REG-RD0");
    clearSignal("-MEM-RD");
    writeCurrentLine();

    aluOp(ALUXOR);

    endInstruction();
    showCntlMemory(ins);
    
    shiftOp(SHL, (SHIFT_LEFT | SHIFT_ZERO));
    shiftOp(SHR, (SHIFT_RIGHT | SHIFT_ZERO));
    shiftOp(RSHL, (SHIFT_LEFT | SHIFT_RING));
    shiftOp(RSHR, (SHIFT_RIGHT | SHIFT_RING));
    shiftOp(PSHR, (SHIFT_RIGHT | SHIFT_PROP));
    shiftOp(CSHL, (SHIFT_LEFT | SHIFT_CARRY));
    shiftOp(CSHR, (SHIFT_RIGHT | SHIFT_CARRY));

    // Move accumulator to TMP register
    ins = MVAT;
    startInstruction(ins);
    loadNextInstruction();
    initCurrentLine();

    setSignal("-ALU-FUNC");
    setAlu(ALUDATA);
    setSignal("-AC-RD");
    writeCurrentLine();
    setSignal("-TMP-REG-LD0");
    writeCurrentLine();
    clearSignal("-TMP-REG-LD0");
    writeCurrentLine();

    endInstruction();
    showCntlMemory(ins);

    // Move TMP register to accumulator
    ins = MVTA;
    startInstruction(ins);
    loadNextInstruction();
    initCurrentLine();

    setSignal("-TMP-REG-RD0");
    writeCurrentLine();
    setSignal("-ALU-FUNC");
    setAlu(ALUDATA);
    writeCurrentLine();
    setSignal("-AC-LD");
    writeCurrentLine();
    clearSignal("-AC-LD");
    writeCurrentLine();

    endInstruction();
    showCntlMemory(ins);

    /* YACC1-D 2026-09-24: ADDIW Rn,#w ($C0-$C7), 3 bytes (w big-endian, as MVIW): Rn <- Rn + w. The high byte of w
       is fetched first into TMP1 (the microcode's scratch register: LDIVR and PUSHR use it, no instruction reads it),
       the low byte is added straight from memory like ADDI, the high byte from TMP1 with the carry like ADDTC.
       Replaces MVRLA/ADDI/MVARL/MVRHA/ADDIC/MVARH (8 bytes) with the same result, ACC and carry. */
    for (reg = 0; reg < 8; reg++) {
        ins = ADDIW | (reg & 0x07);
        startInstruction(ins);
        loadNextInstruction();
        initCurrentLine();

        putMemAtRegOnBus(PC);               /* TMP1 <- w.hi, PC++ */
        setSignal("-TMP-REG-LD1");
        writeCurrentLine();
        clearSignal("-TMP-REG-LD1");
        writeCurrentLine();
        clearSignal("-MEM-RD");
        writeCurrentLine();
        incrementReg(PC);

        accFromRegByte(reg, 0);             /* ACC <- Rn.lo */
        releaseRegRead();
        putMemAtRegOnBus(PC);               /* ACC <- ACC + w.lo (carry out), PC++ */
        aluOp(ALUADD);
        clearSignal("-MEM-RD");
        writeCurrentLine();
        incrementReg(PC);
        regByteFromAcc(reg, 0);             /* Rn.lo <- ACC */

        accFromRegByte(reg, 1);             /* ACC <- Rn.hi */
        releaseRegRead();
        setSignal("-TMP-REG-RD1");          /* ACC <- ACC + TMP1 + carry */
        writeCurrentLine();
        aluOp(ALUADD | CARRY_SHIFT);
        clearSignal("-TMP-REG-RD1");
        writeCurrentLine();
        regByteFromAcc(reg, 1);             /* Rn.hi <- ACC */

        endInstruction();
        showCntlMemory(ins);
    }

    /* YACC1-D 2026-09-24: SHL16 Rn ($C8-$CF), 1 byte: Rn <- Rn << 1, as Rn + Rn: each byte of Rn is loaded into ACC and
       added to itself (the register keeps driving the bus through the add). The carry ends as bit 15 of the old Rn.
       Replaces MVRLA/MVAT/ADDT/MVARL/MVRHA/MVAT/ADDTC/MVARH (8 bytes), without touching TMP. */
    for (reg = 0; reg < 8; reg++) {
        ins = SHL16 | (reg & 0x07);
        startInstruction(ins);
        loadNextInstruction();
        initCurrentLine();

        accFromRegByte(reg, 0);             /* ACC <- Rn.lo, then ACC <- ACC + Rn.lo */
        aluOp(ALUADD);
        releaseRegRead();
        regByteFromAcc(reg, 0);

        accFromRegByte(reg, 1);             /* ACC <- Rn.hi, then ACC <- ACC + Rn.hi + carry */
        aluOp(ALUADD | CARRY_SHIFT);
        releaseRegRead();
        regByteFromAcc(reg, 1);

        endInstruction();
        showCntlMemory(ins);
    }
}
