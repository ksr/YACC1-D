/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */

/* 
 * File:   main.c
 * Author: ksr77
 *
 * Created on December 12, 2016, 9:26 AM
 */

#include <stdio.h>
#include <stdlib.h>
#include "../opcodes.h"

/*
 * 
 */

#define MEMORY_SIZE 32768
#define SEGMENT_SIZE 32

unsigned char EPROMMemory[MEMORY_SIZE] = {};  // RAM Image

/*
#define OUT_ON          0x01
#define OUT_OFF         0x02
#define BRANCH          0x03
#define BRANCH_IN_TRUE  0x04
#define BRANCH_IN_FALSE 0x05
#define LD_ACC_I        0x06
#define ADD_ACC_I       0x07
#define BRANCH_ACC_NZ   0x08
 */

unsigned char prog0[SEGMENT_SIZE]={
    OUT_ON,
    OUT_ON,
    OUT_OFF,
    BRANCH,0x00,0x01
};
unsigned char prog1[SEGMENT_SIZE]={
    OUT_OFF,
    BRANCH_IN_TRUE,0x00,0x01,
    OUT_ON,
    BRANCH,0x00,0x00
};
unsigned char prog2[SEGMENT_SIZE]={
    LD_ACC_I, 0xfe,
    ADD_ACC_I, 0x1,
    BRANCH_ACC_NZ,0x00,0x02,
    OUT_ON,
    LD_ACC_I, 0xfe,
    ADD_ACC_I, 0x01,
    BRANCH_ACC_NZ, 0x00,0x0A,
    OUT_OFF,
    BRANCH, 0x00,0x00
};

void clearEPROMMemory() {
    for (int i = 0; i < MEMORY_SIZE; i++)
        EPROMMemory[i] = 0;
}
void dumpEPROMMemory(){
    FILE *dumpFile;
    
    dumpFile=fopen("eprom.bin","wb");
    fwrite(EPROMMemory,1, MEMORY_SIZE, dumpFile);
    fclose(dumpFile);
}

void writeSegment(int segment, unsigned char code[]) {
    int index;

    index = segment * SEGMENT_SIZE;
    
    for (int i = 0; i < SEGMENT_SIZE; i++)
        EPROMMemory[index + i] = 0x00;
    
    for (int i = 0; i < SEGMENT_SIZE; i++)
        EPROMMemory[index + i] = code[i];
}

int main(int argc, char** argv) {

    clearEPROMMemory();
    writeSegment(0,prog0);
    writeSegment(1,prog1);
    writeSegment(2,prog2);
    
    dumpEPROMMemory();
    return (EXIT_SUCCESS);
}

