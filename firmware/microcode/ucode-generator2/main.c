/*
 * Author: Ken Rother (original)
 * Changes: Claude (Anthropic), 2026 - see tools/patched_files.txt
 */

/* 
 * File:   main.c
 * Author: ken
 *
 * Created on October 20, 2016, 10:43 PM
 * 
 *Build sequencer microcode
 * 
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../yaccsignaldefine.h"
#include "../yaccsignaldata2.h"
#include "../../opcodes.h"

#include "code.h"
#include "CodeGen.h"

void branchInstructions();
void registerOnlyInstructions();
void ioInstructions();
void accumulatorInstructions();
void doMemory();
void haltRecord(int ins);
int recordEmpty(int ins);
extern unsigned char currentLine[];
extern unsigned char cntlMemory[];
extern int eolInfo[];
extern int pendingRelease;                  /* YACC1-D 2026-09-29: the three-step prologue (loadNextInstruction) */
unsigned char releaseLine[BYTES_PER_LINE];
int releasesWritten = 0;
int m1Masked = 0;                           /* YACC1-D 2026-09-29: count steps written without -MEM-RD (m1Mask) */
int lineHas(char *signal);
void removeIdleSteps();


//#define DEBUG 1

/*
 * Format "%AIXXXXXXXX....XXXXX-"
   "%"  Start character
   "A" Checksum (not including instruction number) (Ignore for now) - 2 hex assci chars
   "I" Instruction Number (0-255)- 2 hex ascii chars
   "XXXXXXXX....XXXXX" Data Bytes -  2 hex ascii chars
    "-" End Instruction data character
    "!" END ALL
 * 
 */

/* 
 * Search for signal in signals array and return index
 */
int findSignal(char *signal) {

    for (int i = 0; strlen(signals[i].name) != 0; i++)
        if (strcmp(signal, signals[i].name) == 0)
            return (i);
    return (-1);
}

/* 
 * set signal to active, if signal name starts with '-', meaning active low
 * signal is set low, otherwise set high
 */
void setSignal(char *signal) {

    int signalNum;

    if ((signalNum = findSignal(signal)) == -1) {
        printf("Error %s not found\n", signal);
        exit(1);
    }

    if (signals[signalNum].name[0] == '-')
        bitOff(signalNum);
    else
        bitOn(signalNum);
}

/* 
 * set signal to inactive, if signal name starts with '-', meaning active low
 * signal is set high, otherwise set low
 */
void clearSignal(char *signal) {

    int signalNum;

    if ((signalNum = findSignal(signal)) == -1) {
        printf("Error %s not found\n", signal);
        exit(1);
    }

    if (signals[signalNum].name[0] == '-')
        bitOn(signalNum);
    else
        bitOff(signalNum);
}

/* 
 * loop through all signal lines and set to default state
 */
void initCurrentLine() {
    clearCurrentLine();
    for (int i = 0; strlen(signals[i].name) != 0; i++) {

#ifdef DEBUG
        printf("initCurrent line [%d] [%s] \n", i, signals[i].name);
#endif
        clearSignal(signals[i].name);
        setAddrId(PC);
        setSignal("-VMA"); // Hack prevent ROM mapping from triggering
    }
}

/*
 * Called at the start of processing a new instruction
 */
void startInstruction(int instruction) {
    startUcodeBlock(instruction);
    //clearCurrentLine(); should not be required
    initCurrentLine();
    setAddrId(PC);
    setSignal("-VMA"); // Hack prevent ROM mapping from triggering
    if (instruction == 0) {
        setSignal("OUT-OFF");
    }
#ifdef PROLOGUE6
    writeCurrentLine(); // KEN maybe only need these 2 extra Lines 0&1 for Instruction 0 so maybe test
    //writeCurrentLine(); step 7
#endif
    /* YACC1-D 2026-09-29: the three-step prologue has no idle step 0: loadNextInstruction() writes it */
}

/* 
 * Called at the completion of processing an instruction
 */
void endInstruction() {
    writeCurrentLine();
    setSignal("UCODE-COUNT-RESET");
    writeCurrentLine();
    endUcodeBlock();
    //clearCurrentLine(); // Probably not needed since current line is inited in startInstruction
}

/* 
 * Utility routines for setting bits
 */

void setRegBit(char *signal, int regBit) {
    if (regBit)
        setSignal(signal);
    else
        clearSignal(signal);
}

void setAddrId(int reg) {
    setRegBit("ADDR-REG-ID0", reg & 0x0001);
    setRegBit("ADDR-REG-ID1", reg & 0x0002);
    setRegBit("ADDR-REG-ID2", reg & 0x0004);
    setRegBit("ADDR-REG-ID3", reg & 0x0008);
}

void setRdId(int reg) {
    setRegBit("REG-RD-ID0", reg & 0x0001);
    setRegBit("REG-RD-ID1", reg & 0x0002);
    setRegBit("REG-RD-ID2", reg & 0x0004);
    setRegBit("REG-RD-ID3", reg & 0x0008);
}

void setLdId(int reg) {
    setRegBit("REG-LD-ID0", reg & 0x0001);
    setRegBit("REG-LD-ID1", reg & 0x0002);
    setRegBit("REG-LD-ID2", reg & 0x0004);
    setRegBit("REG-LD-ID3", reg & 0x0008);
}

void setAlu(int aluBits) {
    //printf("setALU %d\n", aluBits);
    setRegBit("ALU0", aluBits & 0x0001);
    setRegBit("ALU1", aluBits & 0x0002);
    setRegBit("ALU2", aluBits & 0x0004);
    setRegBit("ALU3", aluBits & 0x0008);
}

void setIo(int ioBits) {
    //printf("setIO %d\n", ioBits);
    setRegBit("IOADDR0", ioBits & 0x0001);
    setRegBit("IOADDR1", ioBits & 0x0002);
    setRegBit("IOADDR2", ioBits & 0x0004);
    setRegBit("IOADDR3", ioBits & 0x0008);
}

/* 
 * Code Generation Utility Routines
 */

void loadNextInstruction() {
    //Load Reg 0 in ADDR Reg 0
    //Put data from MEM at (ADDR REG 0) on bus
    //load instruction register
    //increment Reg 0

    //initCurrentLine(); // not needed, load next instruction is always done at start of instruction and initCurrentLIne is called
#ifdef PROLOGUE6
    /* the 2016-2026 prologue, six steps: 0 idle (written by startInstruction), 1 -MEM-RD, 2 + LD-INS-REG, 3 -MEM-RD,
       4 PC++ with -MEM-RD still on (review M-1: memory and the register card's $FFFF both drive the bus), 5 release */
    putMemAtRegOnBus(PC);
    setSignal("LD-INS-REG"); // rising or falling?
    writeCurrentLine();
    clearSignal("LD-INS-REG");
    writeCurrentLine(); // -reg-up is rising edge
    incrementReg(PC);
    clearSignal("-MEM-RD"); //STEP 9 DO NOT LEAVE DATA BUS DRIVEN WITH INSTRUCTION FETCHED FROM MEM  
#else
    /* YACC1-D 2026-09-29: the three-step prologue (design review L-1, which also removes M-1 from the fetch).
     *   step 0  -MEM-RD at PC                  the opcode is read; step 0 lasts three clocks (after the reset step)
     *   step 1  -MEM-RD, LD-INS-REG            the IR latches at this step's LEADING edge the byte step 0 left on the
     *                                          bus; -MEM-RD stays on through the step as hold time
     *   step 2  -REG-FUNC-RD, -REG-UP on PC    no -MEM-RD any more, so the register card's $FFFF drives alone
     * Steps 0 and 1 come from the PREVIOUS opcode's record (the IR changes in step 1, the new record's words appear
     * from step 2), so they must be identical in every record - they are, all records run this code - and step 2 is
     * too. The PC counts when -REG-UP rises at the end of step 2. The old prologue ended with a release step that
     * dropped -REG-UP and -REG-FUNC-RD with the selection unchanged; here the record's first body step follows
     * directly, which is the same thing whenever that step keeps REG-RD-ID = PC and asserts no -REG-UP/-REG-DN or
     * -2-BYTE-OPERAND-SEL (else the register select could change while -REG-UP is still low, and a decoder glitch
     * would count another register). writeCurrentLine() checks the first body line and writes the release step in
     * front of it only when it is not such a line (releaseIfNeeded, below). */
    putMemAtRegOnBus(PC);                   // step 0
    setSignal("LD-INS-REG");
    writeCurrentLine();                     // step 1
    clearSignal("LD-INS-REG");
    clearSignal("-MEM-RD");
    setRdId(PC);
    setSignal("-REG-FUNC-RD");
    setSignal("-REG-UP");
    writeCurrentLine();                     // step 2
    clearSignal("-REG-UP");
    clearSignal("-REG-FUNC-RD");
    memcpy(releaseLine, currentLine, sizeof releaseLine);
    pendingRelease = 1;
#endif
}

/* YACC1-D 2026-09-29: true when the line in currentLine asserts the signal */
int lineHas(char *signal) {
    int n = findSignal(signal);
    int byte = (signals[n].chip - 1) * PORTS_PER_CHIP + signals[n].port;
    int bit = (currentLine[byte] >> signals[n].bit) & 1;
    return signals[n].name[0] == '-' ? !bit : bit;
}

/* YACC1-D 2026-09-29 (design review M-1): a step that counts a register (-REG-FUNC-RD with -REG-UP or -REG-DN) opens
 * the register card's transceivers with no read strobe, so the card drives $FFFF onto DATA0..15; if -MEM-RD is on in
 * that step, the memory card's LS245 drives against it. The generator's sequences read an operand, latch it, hold,
 * then increment the address register with -MEM-RD still on; nothing uses the bus of the increment step (the checks:
 * tests/ucemu/prologue.py rule 5 - no load or write in that step, no leading-edge latch in the next). So
 * writeCurrentLine() writes such a line without -MEM-RD and puts -MEM-RD back into the current line afterwards: the
 * step after still reads at the new address, as before. Only that bit of those steps changes, no step count.
 * -DPROLOGUE6 (the image before 2026-09-29's prologue and M-1 work) keeps the old words. */
int m1Mask() {
#ifdef PROLOGUE6
    return 0;
#else
    if (!(lineHas("-REG-FUNC-RD") && (lineHas("-REG-UP") || lineHas("-REG-DN")) && lineHas("-MEM-RD")))
        return 0;
    clearSignal("-MEM-RD");
    m1Masked++;
    return 1;
#endif
}

void m1Unmask() {
    setSignal("-MEM-RD");
}

/* YACC1-D 2026-09-29: called by writeCurrentLine() for the first line after the three-step prologue: unless that line
 * keeps the register selection on PC with no count strobe (see loadNextInstruction), write the release step first */
void releaseIfNeeded() {
    int rdId = lineHas("REG-RD-ID0") | lineHas("REG-RD-ID1") << 1 | lineHas("REG-RD-ID2") << 2 | lineHas("REG-RD-ID3") << 3;
    if (rdId == PC && !lineHas("-REG-UP") && !lineHas("-REG-DN") && !lineHas("-2-BYTE-OPERAND-SEL"))
        return;
    unsigned char body[BYTES_PER_LINE];
    memcpy(body, currentLine, sizeof body);
    memcpy(currentLine, releaseLine, sizeof body);
    writeCurrentLine();                     // step 3: the release (pendingRelease is already 0)
    memcpy(currentLine, body, sizeof body);
    releasesWritten++;
}

/* might be an issue if current setRdId reg is different from one here */
void incrementReg(int reg) {
    setRdId(reg);
    setSignal("-REG-FUNC-RD");
    //writeCurrentLine();
    setSignal("-REG-UP");
    writeCurrentLine();
    
    clearSignal("-REG-UP");
    //writeCurrentLine();  step 1 cleanup
    clearSignal("-REG-FUNC-RD");
    writeCurrentLine();
}

void decrementReg(int reg) {
    setRdId(reg);
    setSignal("-REG-FUNC-RD");
    writeCurrentLine();
    setSignal("-REG-DN");
    writeCurrentLine();
    clearSignal("-REG-DN");
    //writeCurrentLine(); step 3 cleanup
    clearSignal("-REG-FUNC-RD");
    writeCurrentLine();
}

void putMemAtRegOnBus(int reg) {
    setAddrId(reg);
    setSignal("-VMA");
    setSignal("-MEM-RD");
    writeCurrentLine(); // not needed if if reg loads on rising edge?

}

void putBustoRegMem(int reg, char *source) { // Source is either Accumulator TMP registers, if index reg needs more work
    setAddrId(reg);
    setSignal("-VMA");
    setSignal(source);
    writeCurrentLine();
    setSignal("-MEM-WR");
    writeCurrentLine();
    clearSignal("-MEM-WR");
    writeCurrentLine();
    clearSignal(source);
    //clearSignal("-VMA"); step 8
    writeCurrentLine();

}

/* YACC1-D 2026-09-29: the HALT record (the fetch, then SOFT-HALT), also used for every undefined opcode (H-4) */
void haltRecord(int ins) {
    startInstruction(ins);
    loadNextInstruction();
    initCurrentLine();
    setSignal("SOFT-HALT");
    writeCurrentLine();
    endInstruction();
    showCntlMemory(ins);
}

/* YACC1-D 2026-09-29: true when nothing has written the opcode's record (all 64 lines still zero) */
int recordEmpty(int ins) {
    extern unsigned char cntlMemory[];
    for (int i = 0; i < INSTRUCTION_SIZE; i++)
        if (cntlMemory[ins * INSTRUCTION_SIZE + i])
            return 0;
    return 1;
}

/* YACC1-D 2026-09-29: idle steps (design review S1, tools/ucode_review.py: nothing asserted but -VMA) removed after
 * generation where the hardware does not need them. The generator's set-up / strobe / release pattern leaves a step
 * with nothing asserted between many pairs of steps; taking it out makes its two neighbours P and N adjacent, so what
 * P switches off and N switches on now happen on the same edge. That is harmless unless an edge needs the idle step:
 *   - P ends a trailing-edge strobe (REG-LD-LO/HI: 74LS192 LOAD is level-sensitive; -MEM-WR, -IO-WR): the idle step
 *     is its hold time;
 *   - N has a leading-edge latch (IR, operand, branch, INT, TMP, AC, shift register): it would take P's bus instead
 *     of the idle step's;
 *   - N loads or writes (REG-LD-LO/HI, -MEM-WR, -IO-WR): selects, address and data must settle a step before;
 *   - P counts (-REG-UP/-REG-DN) and N changes REG-RD-ID or -2-BYTE-OPERAND-SEL: the count edge would meet a change
 *     of register selection, and a decoder glitch would count another register (the rule of the three-step
 *     prologue, releaseIfNeeded above);
 *   - N counts and its register selection is not already P's (or P counts too: the two counts would merge);
 *   - -2-BYTE-OPERAND-SEL starts in N (it replaces REG-RD-ID/REG-LD-ID: the same selection change);
 *   - I/O (-IO-RD reads the UART's FIFO, -IO-ADDR-LD), BR-TEST (a level-sampled latch), INT-EN/INT-START/-INTA or
 *     SOFT-HALT in P or N; OUT-ON/OUT-OFF in the idle step unless P and N have the same;
 *   - N is the reset step with anything but the reset bit (M-7: its strobes would be one clock long);
 *   - the idle step's selection (ADDR-REG-ID, REG-RD-ID, REG-LD-ID, ALU, IOADDR) is neither P's nor N's: it is a
 *     set-up step of its own.
 * One data-bus driver switching off and another on at the same edge (review A3: a few ns of overlap) is allowed, as
 * at many step boundaries already. Steps 0-2 (the prologue, common to all records) are never touched. The pass
 * removes one step at a time and re-checks the new neighbours. -DKEEPIDLE (and -DPROLOGUE6) leave the records as
 * written; tests/ucemu/idle.py checks the result against that image with its own copy of these rules. */
static int wHas(const unsigned char *w, char *signal) {
    int n = findSignal(signal);
    int byte = (signals[n].chip - 1) * PORTS_PER_CHIP + signals[n].port;
    int bit = (w[byte] >> signals[n].bit) & 1;
    return signals[n].name[0] == '-' ? !bit : bit;
}

static int wField(const unsigned char *w, char *prefix) {
    char name[32];
    int v = 0;
    for (int i = 0; i < 4; i++) {
        snprintf(name, sizeof name, "%s%d", prefix, i);
        if (findSignal(name) >= 0 && wHas(w, name))
            v |= 1 << i;
    }
    return v;
}

static int wAny(const unsigned char *w, char **list) {
    for (int i = 0; list[i]; i++)
        if (wHas(w, list[i]))
            return 1;
    return 0;
}

static int wIdle(const unsigned char *w) {
    for (int i = 0; strlen(signals[i].name) != 0; i++) {
        char *n = signals[i].name;
        if (!strcmp(n, "-VMA") || !strcmp(n, "OUT-OFF") || !strcmp(n, "OUT-ON") || !strcmp(n, "SPARE3"))
            continue;
        if (!strncmp(n, "ADDR-REG-ID", 11) || !strncmp(n, "REG-RD-ID", 9) || !strncmp(n, "REG-LD-ID", 9) ||
            !strncmp(n, "IOADDR", 6) || (!strncmp(n, "ALU", 3) && strlen(n) == 4))
            continue;       /* selection fields: not "asserted" */
        if (wHas(w, n))
            return 0;
    }
    return 1;
}

static int sameSelection(const unsigned char *a, const unsigned char *b) {
    return wField(a, "ADDR-REG-ID") == wField(b, "ADDR-REG-ID") && wField(a, "REG-RD-ID") == wField(b, "REG-RD-ID") &&
           wField(a, "REG-LD-ID") == wField(b, "REG-LD-ID") && wField(a, "ALU") == wField(b, "ALU") &&
           wField(a, "IOADDR") == wField(b, "IOADDR");
}

static char *LEADING[] = {"LD-INS-REG", "OPERAND-CLK", "BRANCH-LD-LO", "BRANCH-LD-HI", "INT-LD-LO", "INT-LD-HI",
                          "-TMP-REG-LD0", "-TMP-REG-LD1", "-AC-LD", "-SR-LD", 0};
static char *TRAILING[] = {"REG-LD-LO", "REG-LD-HI", "-MEM-WR", "-IO-WR", 0};
static char *COUNTS[] = {"-REG-UP", "-REG-DN", 0};
static char *ACTIONS[] = {"BR-TEST", "INT-EN", "INT-START", "SOFT-HALT", "-INTA", "-IO-ADDR-LD", "-IO-RD", "-IO-WR", 0};

static int idleRemovable(const unsigned char *p, const unsigned char *i, const unsigned char *n) {
    if (!wIdle(i)) return 0;
    if (wAny(p, TRAILING) || wAny(n, LEADING) || wAny(n, TRAILING)) return 0;
    if (wAny(p, ACTIONS) || wAny(n, ACTIONS)) return 0;
    if (wHas(i, "OUT-ON") != wHas(p, "OUT-ON") || wHas(i, "OUT-ON") != wHas(n, "OUT-ON")) return 0;
    if (wHas(i, "OUT-OFF") != wHas(p, "OUT-OFF") || wHas(i, "OUT-OFF") != wHas(n, "OUT-OFF")) return 0;
    if (wHas(n, "UCODE-COUNT-RESET")) {                 /* the reset step must be a pure hold */
        unsigned char t[BYTES_PER_LINE];
        memcpy(t, n, sizeof t);
        int r = findSignal("UCODE-COUNT-RESET");
        t[(signals[r].chip - 1) * PORTS_PER_CHIP + signals[r].port] ^= 1 << signals[r].bit;   /* active-high: clear it */
        if (!wIdle(t)) return 0;
    }
    int rdP = wField(p, "REG-RD-ID"), rdN = wField(n, "REG-RD-ID");
    int twoP = wHas(p, "-2-BYTE-OPERAND-SEL"), twoN = wHas(n, "-2-BYTE-OPERAND-SEL");
    if (wAny(p, COUNTS) && (rdN != rdP || twoN)) return 0;
    if (wAny(n, COUNTS) && (rdN != rdP || twoN != twoP || wAny(p, COUNTS))) return 0;
    if (twoN && !twoP) return 0;
    if (!sameSelection(i, p) && !sameSelection(i, n)) return 0;
    return 1;
}

int idleRemoved = 0;

void removeIdleSteps() {
    for (int op = 0; op < INSTRUCTIONS_TO_OUTPUT; op++) {
        unsigned char *rec = cntlMemory + op * INSTRUCTION_SIZE;
        int len = eolInfo[op];
        for (int i = 3; i < len - 1; ) {
            if (idleRemovable(rec + (i - 1) * BYTES_PER_LINE, rec + i * BYTES_PER_LINE, rec + (i + 1) * BYTES_PER_LINE)) {
                memmove(rec + i * BYTES_PER_LINE, rec + (i + 1) * BYTES_PER_LINE, (len - i - 1) * BYTES_PER_LINE);
                len--;
                memset(rec + len * BYTES_PER_LINE, 0, BYTES_PER_LINE);
                idleRemoved++;
                if (i > 3) i--;                     /* the new pair (i-1, i) may free the step before */
            } else
                i++;
        }
        eolInfo[op] = len;
    }
    printf("idle steps removed: %d\n", idleRemoved);
}

const char *g_argv0 = "";   /* YACC1-D 2026-09-20: for exe_relative() in controlLine.c */
int main(int argc, char** argv) {
    g_argv0 = argv[0];

    //basicTest(); //basic sequencer test led on, led off, reset counter
    //exit(0);

    clearCntlMemory();
    //clearCurrentLine();

    startInstruction(0); // what is this for??? microcode to fetch 1st instructon?
    loadNextInstruction();
    endInstruction(); // this is a test (seems to work)
    showCntlMemory(0);

    // HALT
    haltRecord(HALT);

    branchInstructions();

    registerOnlyInstructions();

    ioInstructions();

    accumulatorInstructions();

    doMemory();

    /* YACC1-D 2026-09-29 (design review H-4): an opcode nothing above generates used to keep an all-zero record, and
     * the control lines are active-low, so a zero word asserts every strobe at once (-MEM-RD with -MEM-WR, every
     * register and TMP load and read, -AC-RD, -BRANCH-RD...) for 61 steps until COUNT-FAULT stops the clock - a bus
     * fight on any stray fetch of $A5, $AE, $F8-$FA. Give every such opcode the HALT record: the machine stops with
     * the PC past the byte, CONT resumes at the next one, as both emulators stop on an undefined opcode. */
    for (int ins = 0; ins < INSTRUCTIONS_TO_OUTPUT; ins++)
        if (recordEmpty(ins))
            haltRecord(ins);

#if !defined(PROLOGUE6) && !defined(KEEPIDLE)
    removeIdleSteps();      /* YACC1-D 2026-09-29: the idle steps that can go (below) */
#endif



#ifdef NOTYET

    // Code missing 



    // Add to Accumulator Immediate
    startInstruction(ADD_ACC_I);
    loadNextInstruction();
    initCurrentLine();
    setSignal("ALU-FUNC");
    setSignal("ALU0");
    setSignal("ALU1");
    setSignal("ALU2");
    //setSignal("ALU3");
    setSignal("ADDR-REG-FUNC-RD"); //sp/pc sel on old card try without
    setSignal("ADDR-REG-ADDR-RD"); //put PC address on the address bus
    setSignal("-MEM-RD"); //output memory
    writeCurrentLine();
    setSignal("AC-LD"); //latch data on data bus, from memory, into accumulator
    writeCurrentLine();
    clearSignal("AC-LD");
    setSignal("ADDR-REG-UP"); // advance PC to next location
    writeCurrentLine();
    clearSignal("ADDR-REG-UP");
    writeCurrentLine();

    endInstruction();
    showCntlMemory(ADD_ACC_I);



    // Load SP immediate
    startInstruction(LD_SP_I);
    loadNextInstruction();
    initCurrentLine();

    setSignal("ADDR-ID0"); // bypass branch logic for non PC operations
    // fix for new sp/pc card with address out latch mechanism
    writeCurrentLine();
    //load the next two PC bytes format HHLL SP register
    setSignal("ADDR-REG-FUNC-RD"); //sp/pc sel on old card try without ??? should be off
    setSignal("ADDR-REG-ADDR-RD");
    setSignal("-MEM-RD");
    writeCurrentLine();
    setSignal("BRANCH-LD-HI");
    writeCurrentLine();
    clearSignal("BRANCH-LD-HI");
    ;
    setSignal("ADDR-REG-UP");
    writeCurrentLine();
    clearSignal("ADDR-REG-UP");
    writeCurrentLine();
    setSignal("BRANCH-LD-LO");
    writeCurrentLine();
    clearSignal("BRANCH-LD-LO");
    setSignal("ADDR-REG-UP");
    writeCurrentLine();
    clearSignal("ADDR-REG-UP");
    clearSignal("-MEM-RD");
    writeCurrentLine();
    setSignal("BRANCH-RD-LO"); //output branch register
    setSignal("BRANCH-RD-HI");
    writeCurrentLine();
    setSignal("ADDR-REG-LD-LO"); //load branch register
    //setSignal("ADDR-REG-LD-HI"); //FIX on new card
    writeCurrentLine();
    clearSignal("ADDR-REG-LD-LO");
    //clearSignal("ADDR-REG-LD-HI"); //Fix on new card
    writeCurrentLine();

    endInstruction();
    showCntlMemory(LD_SP_I);

    // Out Register (addr pointed to by sp)
    for (int reg = 0; reg < 8; reg++) {
        ins = OUT_REG | (reg & 0x07);
        startInstruction(ins);
        loadNextInstruction();
        initCurrentLine();

        setSignal("REG-FUNC-RD");
        setSignal("1-BYTE-OPERAND-SEL");
        setRdId(reg);
        setSignal("REG-RD-LO"); // Output register onto data bus
        setSignal("ADDR-REG-ADDR-RD");
        writeCurrentLine();

        setSignal("I/O-WR");
        writeCurrentLine();
        clearSignal("I/O-RD");
        writeCurrentLine();

        endInstruction();
        showCntlMemory(ins);
    }
#endif
    dumpCntlMemory();
#ifndef PROLOGUE6
    printf("three-step prologue: %d records needed the release step\n", releasesWritten);
    printf("M-1: %d count steps written without -MEM-RD\n", m1Masked);
#endif
    printf("Done\n");
    return (EXIT_SUCCESS);
}

/* 
 * Write test program directly into microcode, this will 
 * test if uCode program counter is logic is working
 */
void basicTest() {
    //Basic Sequencer memory test OUT ON - OUT OFF - uPC Reset 

    clearCntlMemory();
    showCurrentLine();
    startInstruction(0);

    showCurrentLine();

    initCurrentLine();
    showCurrentLine();
    setSignal("OUT-ON");
    showCurrentLine();
    writeCurrentLine();
    showCurrentLine();

    initCurrentLine();
    setSignal("OUT-OFF");
    showCurrentLine();
    writeCurrentLine();

    initCurrentLine();
    setSignal("UCODE-COUNT-RESET");
    showCurrentLine();
    writeCurrentLine();
    endInstruction();

    dumpCntlMemory();
#ifndef PROLOGUE6
    printf("three-step prologue: %d records needed the release step\n", releasesWritten);
    printf("M-1: %d count steps written without -MEM-RD\n", m1Masked);
#endif
    printf("Done\n");

}