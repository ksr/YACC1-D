/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */

/* 
 * File:   main.c
 * Author: ken
 *
 * Created on October 20, 2016, 10:43 PM
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "code.h"
//#include "../opcodes.h"
#include "../../CommonHeaderFiles/opcodes.h"


#define PORTS_PER_CHIP 2
#define PINS_PER_PORT 8

#define BYTES_PER_LINE 8
#define LINES_PER_INSTRUCTION 32
#define INSTRUCTION_SIZE BYTES_PER_LINE * LINES_PER_INSTRUCTION
#define INSTRUCTIONS 256
#define MEMORY_SIZE BYTES_PER_LINE*LINES_PER_INSTRUCTION*INSTRUCTIONS

#define INSTRUCTIONS_TO_OUTPUT 48

int currentInstruction = 0;
int ucodeLine = 0;

unsigned char cntlMemory[MEMORY_SIZE] = {}; // RAM Image

unsigned char currentLine[BYTES_PER_LINE] = {}; // 

int showDetail = 0;

void clearCntlMemory() {
    for (int i = 0; i < MEMORY_SIZE; i++)
        cntlMemory[i] = 0;
}

unsigned char outAsciiHex(unsigned char c) {
    if ((c >= 0) && (c <= 9))
        return ('0' + c);
    else
        return ('A' + (c - 10));

}

void writeAsciiByte(FILE *f, unsigned char c) {
    unsigned char hi, lo;
    char outData[1];

    hi = (c & 0xf0) >> 4;
    lo = c & 0x0f;

    fputc(outAsciiHex(hi), f);
    fputc(outAsciiHex(lo), f);

}

/*
 * Format "%AIXXXXXXXX....XXXXX-"
   "%"  Start charachter
   "A" Checksum (not including instruction number) (Ignore for now) - 2 hex assci chars
   "I" Instruction Number (0-255)- 2 hex ascii chars
   "XXXXXXXX....XXXXX" Data Bytes -  2 hex ascii chars
    "-" End Instruction data character
    "!" END ALL
 * 
 */

#define START_CHAR '%'
#define END_INS_CHAR '-'
#define END_ALL '!'

void dumpCntlMemory() {
    unsigned char checksum;
    int i, j;
    FILE *dumper;
    dumper = fopen("test.123", "wb");
    //for(int i=0;i<MEMORY_SIZE;i++)
    fwrite(cntlMemory, 1, MEMORY_SIZE, dumper);
    fclose(dumper);

    FILE *dumper2;
    dumper2 = fopen("test.hex", "w");
    for (i = 0; i < INSTRUCTIONS_TO_OUTPUT; i++) {
        checksum = 0;
        for (j = 0; j < INSTRUCTION_SIZE; j++) {
            checksum += cntlMemory[i * INSTRUCTION_SIZE + j];
        }
        printf("Instruction=%02x", i);
        fputc(START_CHAR, dumper2);
        writeAsciiByte(dumper2, checksum);
        writeAsciiByte(dumper2, i);

        for (j = 0; j < INSTRUCTION_SIZE; j++) {
            writeAsciiByte(dumper2, cntlMemory[i * INSTRUCTION_SIZE + j]);

        }
        printf("\n");
        fputc(END_INS_CHAR, dumper2);
        fputc('\n', dumper2);
    }
    fputc(END_ALL, dumper2);
    fputc('\n', dumper2);
    //flush(dumper2)
    fclose(dumper2);
}

void clearCurrentLine() {
    for (int i = 0; i < BYTES_PER_LINE; i++)
        currentLine[i] = 0;
}

void showCurrentLine() {
    for (int i = 0; i < BYTES_PER_LINE; i++)
        printf("%02x ", currentLine[i]);
    printf("\n");
    //printf("BYTE[%i]=%x\n", i, currentLine[i]);
}

void showCntlMemory(int instruction) {
    int lineStart;

    if (showDetail) {
        printf("Show Instruction=%02x\n", instruction);
        lineStart = BYTES_PER_LINE * LINES_PER_INSTRUCTION * instruction;
        for (int j = 0; j < LINES_PER_INSTRUCTION; j++) {
            printf("Line[%d] = ", j);
            for (int i = 0; i < BYTES_PER_LINE; i++) {
                printf("%02x ", cntlMemory[lineStart + j * BYTES_PER_LINE + i]);
            }
            printf("\n");
        }
    }
}

void doInstruction(int instruction) {
    currentInstruction = instruction;
    clearCurrentLine();
    ucodeLine = 0;
}

void writeCurrentLine() {
    int lineToWrite;

    lineToWrite = currentInstruction * LINES_PER_INSTRUCTION * BYTES_PER_LINE + ucodeLine*BYTES_PER_LINE;
    for (int i = 0; i < BYTES_PER_LINE; i++)
        cntlMemory[lineToWrite + i] = currentLine[i];
    ucodeLine++;
    if (ucodeLine >= LINES_PER_INSTRUCTION) {
        printf("ucode lines overflow");
        exit(1);
    }
}

int findSignal(char *signal) {

    for (int i = 0; signals[i].name != NULL; i++)
        if (strcmp(signal, signals[i].name) == 0)
            return (i);
    return (-1);
}

void setBit(char *signal) {

    int signalNum;
    int byteToChange;
    int bitToChange;
    unsigned char newByte;

    if ((signalNum = findSignal(signal)) == -1) {
        printf("Error %s not found\n", signal);
        exit(1);
    }
    byteToChange = (signals[signalNum].chip - 1) * PORTS_PER_CHIP + signals[signalNum].port;
    bitToChange = signals[signalNum].bit;

    newByte = 0x01 << bitToChange;
    currentLine[byteToChange] = currentLine[byteToChange] | newByte;
}

void clearBit(char *signal) {

    int signalNum;
    int byteToChange;
    int bitToChange;
    unsigned char newByte;

    if ((signalNum = findSignal(signal)) == -1) {
        printf("Error %s not found\n", signal);
        exit(1);
    }

    byteToChange = (signals[signalNum].chip - 1) * PORTS_PER_CHIP + signals[signalNum].port;
    bitToChange = signals[signalNum].bit;

    newByte = 0x01 << bitToChange;
    newByte = 0xff ^ newByte;
    currentLine[byteToChange] = currentLine[byteToChange] & newByte;
}

void loadNextInstruction() {
    //output PC onto the address bus
    //read mem at pc address
    //load instruction register
    //increment pc (part of new instruction)

    clearCurrentLine();
    setBit("ADDR-REG-FUNC-RD"); // no need to set addr reg id 0,0 == PC
    setBit("ADDR-REG-ADDR-RD");
    writeCurrentLine();//this probably not needed
    setBit("MEM-RD");
    writeCurrentLine();
    setBit("LD-INS-REG");
    writeCurrentLine();
    clearBit("LD-INS-REG"); // if reg is edge triggered, clearing can be part of next ins
    setBit("ADDR-REG-UP");
    writeCurrentLine();
    clearBit("MEM-RD");
    clearBit("ADDR-REG-UP");
    writeCurrentLine();
}

void loadBranchRegister() {
    //load the next two PC bytes format HHLL into branch register
    setBit("ADDR-REG-FUNC-RD"); //sp/pc sel on old card try without
    setBit("ADDR-REG-ADDR-RD");
    writeCurrentLine(); // maybe not required
    setBit("MEM-RD");
    writeCurrentLine();
    setBit("BRANCH-LD-HI");
    writeCurrentLine();
    clearBit("BRANCH-LD-HI"); // if branch reg +ve edge triggered next write not required
    writeCurrentLine();
    setBit("ADDR-REG-UP");
    writeCurrentLine();
    clearBit("ADDR-REG-UP");// if addr  +ve edge triggered next write not required
    writeCurrentLine();
    setBit("BRANCH-LD-LO");
    writeCurrentLine();
    clearBit("BRANCH-LD-LO");// if branch reg +ve edge triggered next write not required
    writeCurrentLine();
    setBit("ADDR-REG-UP");
    writeCurrentLine();
    clearBit("ADDR-REG-UP");
    writeCurrentLine();
}

void endInstruction() {
    clearCurrentLine(); // this should be optional, perhaps set by a param
    setBit("UCODE-COUNT-RESET");
    writeCurrentLine();
    printf("Instruction=%02x (hex) lines=%d (dec)\n", currentInstruction, ucodeLine);
}

void cmd(char *str, int reg) {
    if (reg)
        setBit(str);
}

void setRdId(int reg) {
    cmd("REG-BRD-RD-ID", reg & 0x1000);
    cmd("REG-RD-ID0", reg & 0x0001);
    cmd("REG-RD-ID1", reg & 0x0010);
    cmd("REG-RD-ID2", reg & 0x0100);
}

void setLdId(int reg) {
    cmd("REG-BRD-LD-ID", reg & 0x1000);
    cmd("REG-LD-ID0", reg & 0x0001);
    cmd("REG-LD-ID1", reg & 0x0010);
    cmd("REG-LD-ID2", reg & 0x0100);

}

int main(int argc, char** argv) {
    int reg;
    int ins;

    //basicTest(); //basic sequencer test led on, led off, reset counter

    clearCntlMemory();
    clearCurrentLine();

    doInstruction(START);
    loadNextInstruction();
    showCntlMemory(START);

    // OUT ON
    doInstruction(OUT_ON);
    loadNextInstruction();
    clearCurrentLine();

    // out on
    setBit("OUT-ON");
    writeCurrentLine();

    endInstruction();
    showCntlMemory(OUT_ON);

    // OUT OFF
    doInstruction(OUT_OFF);
    loadNextInstruction();
    clearCurrentLine();

    // out off
    setBit("OUT-OFF");
    writeCurrentLine();

    endInstruction();
    showCntlMemory(OUT_OFF);

    // Branch
    doInstruction(BRANCH);
    loadNextInstruction();
    clearCurrentLine();

    loadBranchRegister();
    clearCurrentLine();
    setBit("BRANCH-RD-LO"); //output branch register
    setBit("BRANCH-RD-HI");
    setBit("ADDR-REG-FUNC-RD"); //sp/pc select on old card, try without
    writeCurrentLine();

    // ALU 0-2 condition bits all set to 0 therefore selected condition (0) is HIGH forcing a branch

    setBit("ADDR-REG-LD-LO"); //load branch register
    //setBit("ADDR-REG-LD-HI"); //FIX on new card
    writeCurrentLine();
    clearBit("ADDR-REG-LD-LO");
    //clearBit("ADDR-REG-LD-HI"); //Fix on new card
    writeCurrentLine();

    endInstruction();
    showCntlMemory(BRANCH);

    // Branch IN == 1 // This needs to be fixed, input will be part of regular branch logic
    doInstruction(BRANCH_IN_TRUE);
    loadNextInstruction();
    clearCurrentLine();

    loadBranchRegister();
    clearCurrentLine();
    setBit("BRANCH-RD-LO"); //output branch register
    setBit("BRANCH-RD-HI");
    setBit("ADDR-REG-FUNC-RD"); //sp/pc sel on old card try without
    setBit("TEST-IN"); //set test condition // this will be set via ALU settings
    writeCurrentLine();
    setBit("ADDR-REG-LD-LO");
    //setBit("ADDR-REG-LD-HI");
    writeCurrentLine();
    clearBit("ADDR-REG-LD-LO");
    //clearBit("ADDR-REG-LD-HI");
    writeCurrentLine();

    endInstruction();
    showCntlMemory(BRANCH_IN_TRUE);

    // Branch IN == 0 // This needs to be fixed, input will be part of regular branch logic
    doInstruction(BRANCH_IN_FALSE);
    loadNextInstruction();
    clearCurrentLine();

    // Code missing 

    endInstruction();
    showCntlMemory(BRANCH_IN_FALSE);


    // LOAD Accumulator Immediate
    doInstruction(LD_ACC_I);
    loadNextInstruction();
    clearCurrentLine();

    setBit("ALU-FUNC");
    setBit("ADDR-REG-FUNC-RD"); //sp/pc sel on old card try without
    setBit("ADDR-REG-ADDR-RD");
    writeCurrentLine();
    setBit("MEM-RD");
    writeCurrentLine();
    setBit("AC-LD");
    writeCurrentLine();
    clearBit("AC-LD");
    writeCurrentLine();
    setBit("ADDR-REG-UP");
    writeCurrentLine();
    clearBit("ADDR-REG-UP");
    writeCurrentLine();
    endInstruction();
    showCntlMemory(LD_ACC_I);

    // Add to Accumulator Immediate
    doInstruction(ADD_ACC_I);
    loadNextInstruction();
    clearCurrentLine();
    setBit("ALU-FUNC");
    setBit("ALU0");
    setBit("ALU1");
    setBit("ALU2");
    //setBit("ALU3");
    setBit("ADDR-REG-FUNC-RD"); //sp/pc sel on old card try without
    setBit("ADDR-REG-ADDR-RD"); //put PC address on the address bus
    writeCurrentLine();
    setBit("MEM-RD"); //output memory
    writeCurrentLine();
    setBit("AC-LD"); //latch data on data bus, from memory, into accumulator
    writeCurrentLine();
    clearBit("AC-LD");
    writeCurrentLine();
    setBit("ADDR-REG-UP"); // advance PC to next location
    writeCurrentLine();
    clearBit("ADDR-REG-UP");
    writeCurrentLine();

    endInstruction();
    showCntlMemory(ADD_ACC_I);

    // Branch Accumulator != 0
    doInstruction(BRANCH_ACC_NZ);
    loadNextInstruction();
    clearCurrentLine();

    loadBranchRegister();
    clearCurrentLine();
    setBit("BRANCH-RD-LO"); // OUTPUT the BRANCH register
    setBit("BRANCH-RD-HI");
    setBit("ADDR-REG-FUNC-RD"); //sp/pc sel on old card try without
    setBit("ALU2"); // set branch condition
    setBit("AC-LD-INV"); // ???wrong this is now testing ac = 255, inv causes all sigs to 0
    setBit("AC-RD"); //output accumulator to compare logic for branch test
    writeCurrentLine();
    setBit("ADDR-REG-LD-LO"); //load branch register (if condition met)
    //setBit("ADDR-REG-LD-HI"); // FIX with new SP card
    writeCurrentLine();
    clearBit("ADDR-REG-LD-LO");
    //clearBit("ADDR-REG-LD-HI"); //FIC with new SP card
    writeCurrentLine();

    endInstruction();
    showCntlMemory(BRANCH_ACC_NZ);

    // OUT Accumulator, addr pointed to by SP
    doInstruction(ACC_OUT);
    loadNextInstruction();
    clearCurrentLine();

    setBit("ADDR-REG-ADDR-RD");
    setBit("ALU-FUNC");
    setBit("AC-RD");
    writeCurrentLine();
    setBit("I/O-WR");
    writeCurrentLine();
    clearBit("I/O-RD");
    writeCurrentLine();

    endInstruction();
    showCntlMemory(ACC_OUT);

    // Load SP immediate
    doInstruction(LD_SP_I);
    loadNextInstruction();
    clearCurrentLine();

    setBit("ADDR-ID0"); // bypass branch logic for non PC operations
    // fix for new sp/pc card with address out latch mechanism
    writeCurrentLine();
    //load the next two PC bytes format HHLL SP register
    setBit("ADDR-REG-FUNC-RD"); //sp/pc sel on old card try without
    setBit("ADDR-REG-ADDR-RD");
    writeCurrentLine();
    setBit("MEM-RD");
    writeCurrentLine();
    setBit("BRANCH-LD-HI");
    writeCurrentLine();
    clearBit("BRANCH-LD-HI");
    writeCurrentLine();
    setBit("ADDR-REG-UP");
    writeCurrentLine();
    clearBit("ADDR-REG-UP");
    writeCurrentLine();
    setBit("BRANCH-LD-LO");
    writeCurrentLine();
    clearBit("BRANCH-LD-LO");
    writeCurrentLine();
    setBit("ADDR-REG-UP");
    writeCurrentLine();
    clearBit("ADDR-REG-UP");
    clearBit("MEM-RD");
    writeCurrentLine();
    setBit("BRANCH-RD-LO"); //output branch register
    setBit("BRANCH-RD-HI");
    writeCurrentLine();
    setBit("ADDR-REG-LD-LO"); //load branch register
    //setBit("ADDR-REG-LD-HI"); //FIX on new card
    writeCurrentLine();
    clearBit("ADDR-REG-LD-LO");
    //clearBit("ADDR-REG-LD-HI"); //Fix on new card
    writeCurrentLine();

    endInstruction();
    showCntlMemory(LD_SP_I);

    //load register immediate 8 bit
    for (reg = 0; reg < 8; reg++) {
        ins = LD_REG_I | (reg & 0x07);
        doInstruction(ins);
        loadNextInstruction();
        clearCurrentLine();

        setBit("ADDR-REG-FUNC-RD"); //sp/pc sel on old card try without
        setBit("ADDR-REG-ADDR-RD"); // output pc address onto address bus
        setBit("REG-FUNC-LD"); //enable register card for loading, 
        setBit("1-BYTE-OPERAND-SEL");
        writeCurrentLine();
        setBit("MEM-RD"); //output memory (location for address bus) to data bus
        writeCurrentLine();
        setLdId(reg); //set the ID bits for the register
        writeCurrentLine();
        setBit("REG-LD-LO"); //load register
        writeCurrentLine();
        clearBit("REG-LD-LO");
        writeCurrentLine();
        setBit("ADDR-REG-UP"); //increment pc
        writeCurrentLine();
        clearBit("ADDR-REG-UP");
        writeCurrentLine();

        endInstruction();
        showCntlMemory(ins);
    }

    // move register low to accumulator
    for (int reg = 0; reg < 8; reg++) {
        ins = MV_REG_ACC | (reg & 0x07);
        doInstruction(ins);
        loadNextInstruction();
        clearCurrentLine();

        setBit("REG-FUNC-RD"); //enable register card for loading, 
        setBit("1-BYTE-OPERAND-SEL");
        writeCurrentLine();
        setRdId(reg); //set the ID bits for the register
        writeCurrentLine();
        setBit("REG-RD-LO"); // Output register onto data bus
        writeCurrentLine();


        setBit("ALU-FUNC");
        writeCurrentLine();
        setBit("AC-LD");
        writeCurrentLine();
        clearBit("AC-LD");
        writeCurrentLine();

        endInstruction();
        showCntlMemory(ins);
    }

    // move accumulator to register low
    for (int reg = 0; reg < 8; reg++) {
        ins = MV_ACC_REG | (reg & 0x07);
        doInstruction(ins);
        loadNextInstruction();
        clearCurrentLine();

        setBit("REG-FUNC-LD");
        setBit("1-BYTE-OPERAND-SEL");
        writeCurrentLine();
        setLdId(reg);
        writeCurrentLine();
        setBit("ALU-FUNC");
        setBit("AC-RD");
        writeCurrentLine();
        setBit("REG-LD-LO");
        writeCurrentLine();
        clearBit("REG-LD-LO");
        writeCurrentLine();

        endInstruction();
        showCntlMemory(ins);
    }

    // Out Register (addr pointed to by sp)
    for (int reg = 0; reg < 8; reg++) {
        ins = OUT_REG | (reg & 0x07);
        doInstruction(ins);
        loadNextInstruction();
        clearCurrentLine();

        setBit("REG-FUNC-RD");
        setBit("1-BYTE-OPERAND-SEL");
        writeCurrentLine();
        setRdId(reg);
        writeCurrentLine();
        setBit("REG-RD-LO"); // Output register onto data bus
        writeCurrentLine();
        setBit("ADDR-REG-ADDR-RD");
        writeCurrentLine();
        
        setBit("I/O-WR");
        writeCurrentLine();
        clearBit("I/O-RD");
        writeCurrentLine();

        endInstruction();
        showCntlMemory(ins);
    }

    dumpCntlMemory();
    printf("Done\n");
    return (EXIT_SUCCESS);
}

int basicTest() {
    //Basic Sequencer memory test OUT ON - OUT OFF - uPC Reset 

    clearCntlMemory();
    doInstruction(0);

    clearCurrentLine();
    setBit("OUT-ON");
    writeCurrentLine();

    clearCurrentLine();
    setBit("OUT-OFF");
    writeCurrentLine();

    clearCurrentLine();
    setBit("UCODE-COUNT-RESET");
    writeCurrentLine();

    dumpCntlMemory();
    printf("Done\n");
    return (EXIT_SUCCESS);

}