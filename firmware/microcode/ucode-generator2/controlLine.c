/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */

#include "stdio.h"
#include <stdlib.h>
#include <string.h>

#include "code.h"
#include "CodeGen.h"
#include "../yaccsignaldefine.h"

#define START_CHAR '%'
#define END_INS_CHAR '-'
#define END_ALL '!'

//#define DEBUG 1

extern struct signal signals[];

unsigned char cntlMemory[MEMORY_SIZE] = {}; // RAM Image
unsigned char currentLine[BYTES_PER_LINE] = {}; // 

int eolInfo[INSTRUCTIONS] = {0,};
int ucodeLine = 0;
int currentUcodeBlock = -1;

int showDetail = 1;

void writeAsciiByte(FILE *f, unsigned char c);

void clearCntlMemory() {
    for (int i = 0; i < MEMORY_SIZE; i++)
        cntlMemory[i] = 0;
}

void startUcodeBlock(int index) {
    currentUcodeBlock = index;
    ucodeLine = 0;
}

void endUcodeBlock() {
#ifdef DEBUG
    printf("Instruction=%02x (hex) lines=%d (dec)\n", currentUcodeBlock, ucodeLine);
#endif
    eolInfo[currentUcodeBlock] = ucodeLine;
}

void clearCurrentLine() {
    for (int i = 0; i < BYTES_PER_LINE; i++)
        currentLine[i] = 0;
}

void writeCurrentLine() {
    int lineToWrite;
    int dup;
#ifdef DEBUG
    printf("Write line [%d]\n", ucodeLine);
#endif 
    lineToWrite = currentUcodeBlock * LINES_PER_INSTRUCTION * BYTES_PER_LINE + ucodeLine*BYTES_PER_LINE;

    // if not first line if this line is same as previous them skip
    if (ucodeLine != 0) {
        dup = 1;
        for (int i = 0; i < BYTES_PER_LINE; i++)
            if (cntlMemory[lineToWrite + i - BYTES_PER_LINE] != currentLine[i])
                dup = 0;
        if (dup){
            printf("dup found %d %d\n", currentUcodeBlock, ucodeLine);
            return;
        }
    }


    for (int i = 0; i < BYTES_PER_LINE; i++)
        cntlMemory[lineToWrite + i] = currentLine[i];
    ucodeLine++;
    if (ucodeLine > LINES_PER_INSTRUCTION) {
        printf("ucode lines overflow %02x", currentUcodeBlock);
        exit(1);
    }

}

void showCurrentLine() {
#ifdef DEBUG
    printf("[%d]", ucodeLine);
    for (int i = 0; i < BYTES_PER_LINE; i++)
        printf("%02x ", currentLine[i]);
    printf("\n");
    //printf("BYTE[%i]=%x\n", i, currentLine[i]);
#endif
}

void bitOn(int signalNum) {

    int byteToChange;
    int bitToChange;
    unsigned char newByte;

    byteToChange = (signals[signalNum].chip - 1) * PORTS_PER_CHIP + signals[signalNum].port;
    bitToChange = signals[signalNum].bit;

    newByte = 0x01 << bitToChange;

    currentLine[byteToChange] = currentLine[byteToChange] | newByte;
#ifdef DEBUG
    printf("bitOn-[%d - %s] %d %d %x %x \n", signalNum, signals[signalNum].name, byteToChange, bitToChange, newByte, currentLine[byteToChange]);
#endif
}

void bitOff(int signalNum) {

    int byteToChange;
    int bitToChange;
    unsigned char newByte;

    byteToChange = (signals[signalNum].chip - 1) * PORTS_PER_CHIP + signals[signalNum].port;
    bitToChange = signals[signalNum].bit;

    newByte = 0x01 << bitToChange;
    newByte = 0xff ^ newByte;
    currentLine[byteToChange] = currentLine[byteToChange] & newByte;
#ifdef DEBUG
    printf("bitOff-[%d - %s] %d %d %x %x \n", signalNum, signals[signalNum].name, byteToChange, bitToChange, newByte, currentLine[byteToChange]);
#endif
}

/* YACC1-D 2026-09-20: resolve a path relative to the folder this executable is in, so the program works from a
   Finder double-click or any working directory. */
#include <libgen.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#ifdef __APPLE__
#include <mach-o/dyld.h>
#endif
extern const char *g_argv0;
static void exe_relative(char *out, size_t outlen, const char *rel) {
    char exe[4096], dir[4096];
#ifdef __APPLE__
    uint32_t n = sizeof(exe);
    if (_NSGetExecutablePath(exe, &n) != 0) strncpy(exe, g_argv0, sizeof(exe) - 1);
#else
    strncpy(exe, g_argv0, sizeof(exe) - 1);
#endif
    exe[sizeof(exe) - 1] = 0;
    if (realpath(exe, dir) == NULL) strncpy(dir, exe, sizeof(dir) - 1);
    snprintf(out, outlen, "%s/%s", dirname(dir), rel);
}

void dumpCntlMemory() {
    unsigned char checksum;
    int i, j, k;
    FILE *dumper;
    char outpath[4096];
    exe_relative(outpath, sizeof outpath, "test.123"); dumper = fopen(outpath, "wb");   /* YACC1-D: outputs beside the executable */
    //for(int i=0;i<MEMORY_SIZE;i++)
    fwrite(cntlMemory, 1, MEMORY_SIZE, dumper);
    fclose(dumper);

    FILE *dumper2;
    exe_relative(outpath, sizeof outpath, "test.hex"); dumper2 = fopen(outpath, "w");
    for (i = 0; i < INSTRUCTIONS_TO_OUTPUT; i++) {
        checksum = 0;
        for (j = 0; j < INSTRUCTION_SIZE; j++) {
            checksum += cntlMemory[i * INSTRUCTION_SIZE + j];
        }
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

    exe_relative(outpath, sizeof outpath, "test.hexz"); dumper2 = fopen(outpath, "w");
    printf("microcode written beside the program: test.123, test.hex, test.hexz\n");
    for (i = 0; i < INSTRUCTIONS_TO_OUTPUT; i++) {
        checksum = 0;
        for (j = 0; j < INSTRUCTION_SIZE; j++) {
            checksum += cntlMemory[i * INSTRUCTION_SIZE + j];
        }
        fputc(START_CHAR, dumper2);
        writeAsciiByte(dumper2, checksum);
        writeAsciiByte(dumper2, i);

        for (j = 0; j < eolInfo[i]; j++) {
            for (k = 0; k < BYTES_PER_LINE; k++) {
                writeAsciiByte(dumper2, cntlMemory[i * INSTRUCTION_SIZE + j * BYTES_PER_LINE + k]);
            }
        }
//        if (j < LINES_PER_INSTRUCTION) {
//            fputc('Z', dumper2);
        for(;j<LINES_PER_INSTRUCTION;j++){
            for (k = 0; k < BYTES_PER_LINE; k++) {
                writeAsciiByte(dumper2,0x00);
            }
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

void showCntlMemory(int instruction) {

    if (showDetail) {
#ifdef DEBUG        
        printf("Show Instruction=%02x\n", instruction);
        lineStart = BYTES_PER_LINE * LINES_PER_INSTRUCTION * instruction;
        for (int j = 0; j < LINES_PER_INSTRUCTION; j++) {
            printf("Line[%d] = ", j);
            for (int i = 0; i < BYTES_PER_LINE; i++) {
                printf("%02x ", cntlMemory[lineStart + j * BYTES_PER_LINE + i]);
            }
            printf("\n");
        }
#endif
    }
}

unsigned char outAsciiHex(unsigned char c) {
    if ((c >= 0) && (c <= 9))
        return ('0' + c);
    else
        return ('A' + (c - 10));
}

void writeAsciiByte(FILE *f, unsigned char c) {
    unsigned char hi, lo;

    hi = (c & 0xf0) >> 4;
    lo = c & 0x0f;

    fputc(outAsciiHex(hi), f);
    fputc(outAsciiHex(lo), f);
}