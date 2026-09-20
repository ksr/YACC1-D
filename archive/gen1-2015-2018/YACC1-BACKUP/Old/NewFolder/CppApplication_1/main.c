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
#include "../opcodes.h"


#define PORTS_PER_CHIP 2
#define PINS_PER_PORT 8

#define BYTES_PER_LINE 8
#define LINES_PER_INSTRUCTION 32
#define INSTRUCTION_SIZE BYTES_PER_LINE * LINES_PER_INSTRUCTION
#define INSTRUCTIONS 256
#define MEMORY_SIZE BYTES_PER_LINE*LINES_PER_INSTRUCTION*INSTRUCTIONS

#define INSTRUCTIONS_TO_OUTPUT 16

int currentInstruction = 0;
int ucodeLine = 0;

unsigned char cntlMemory[MEMORY_SIZE] = {}; // RAM Image

unsigned char currentLine[BYTES_PER_LINE] = {}; // 

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
        printf("Instruction=%d", i);
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
    writeCurrentLine();
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
    setBit("ADDR-REG-FUNC-RD"); // no need to set addr reg id 0,0 == PC
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
    writeCurrentLine();
}

void endInstruction() {
    clearCurrentLine();
    setBit("UCODE-COUNT-RESET");
    writeCurrentLine();
    printf("End Instruction=%d lines=%d\n",currentInstruction,ucodeLine);
}

int main(int argc, char** argv) {
    
    /* Basic Sequencer memory test OUT ON - OUT OFF - uPC Reset 

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
*/
    
    
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
    setBit("BRANCH-RD-LO");
    setBit("BRANCH-RD-HI");
    setBit("ADDR-REG-FUNC-RD");
    writeCurrentLine();
    setBit("ADDR-REG-LD-LO");
    //setBit("ADDR-REG-LD-HI");
    writeCurrentLine();
    clearBit("ADDR-REG-LD-LO");
    //clearBit("ADDR-REG-LD-HI");
    writeCurrentLine();
    // load branch register next 2 pc locations
    // set brannch condion test
    // branch on condition
    clearCurrentLine();
    endInstruction();
    showCntlMemory(BRANCH);

    // Branch IN == 1
    doInstruction(BRANCH_IN_TRUE);
    loadNextInstruction();
    clearCurrentLine();
    loadBranchRegister();
    clearCurrentLine();
    setBit("BRANCH-RD-LO");
    setBit("BRANCH-RD-HI");
    setBit("ADDR-REG-FUNC-RD");
    setBit("TEST-IN");
    writeCurrentLine();
    setBit("ADDR-REG-LD-LO");
    setBit("ADDR-REG-LD-HI");
    writeCurrentLine();
    clearBit("ADDR-REG-LD-LO");
    clearBit("ADDR-REG-LD-HI");
    writeCurrentLine();
    // load branch register next 2 pc locations
    // set brannch condion test
    // branch on condition
    writeCurrentLine();
    endInstruction();
    showCntlMemory(BRANCH_IN_TRUE);

    // Branch IN == 0
    doInstruction(BRANCH_IN_FALSE);
    loadNextInstruction();
    clearCurrentLine();
    // load branch register next 2 pc locations
    // set brannch condion test
    // branch on condition
    writeCurrentLine();
    endInstruction();
    showCntlMemory(BRANCH_IN_FALSE);

    // LOAD Accumulator Immediate
    doInstruction(LD_ACC_I);
    loadNextInstruction();
    clearCurrentLine();
    setBit("ALU-FUNC");
    setBit("ADDR-REG-FUNC-RD"); // no need to set addr reg id 0,0 == PC
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
    setBit("ADDR-REG-FUNC-RD"); // no need to set addr reg id 0,0 == PC
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
    showCntlMemory(ADD_ACC_I);

    // Branch Accumulator != 0
    doInstruction(BRANCH_ACC_NZ);
    loadNextInstruction();
    clearCurrentLine();
    loadBranchRegister();
    clearCurrentLine();
    setBit("BRANCH-RD-LO");
    setBit("BRANCH-RD-HI");
    setBit("ADDR-REG-FUNC-RD");
    setBit("ALU2");
    setBit("AC-RD");
    setBit("AC-LD-INV"); // ???wrong this is now testing ac = 255, inv causes all sigs to 0
    writeCurrentLine();
    setBit("ADDR-REG-LD-LO");
    //setBit("ADDR-REG-LD-HI");
    writeCurrentLine();
    clearBit("ADDR-REG-LD-LO");
    //clearBit("ADDR-REG-LD-HI");
    writeCurrentLine();
    endInstruction();
    showCntlMemory(BRANCH_ACC_NZ);


    dumpCntlMemory();
    printf("Done\n");
    return (EXIT_SUCCESS);
}

