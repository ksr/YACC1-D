__author__ = 'ken'

import sys
import string

sourceFile = "workfile2.asm"
romImage = "loadrom"
#listfile = sys.stdout
listfile = "workfile2.lst"

def RI(parts):
    #print "I",parts
    storeRam(opcodes.get(parts[0])[1] | parts[1])
    storeRam(parts[2])
    if listfile:
        listfile.write("\t%s R%i 0x%02x" % (parts[0], parts[1]  , parts[2]))


def RR(parts):
    #print "RR",parts
    storeRam(opcodes.get(parts[0])[1] | parts[1] << 2 | parts[2])
    if listfile:
        listfile.write("\t\t%s R%i R%i" % (parts[0],parts[1]  , parts[2]))


def R(parts):
    #print "R",parts
    storeRam(opcodes.get(parts[0])[1] | parts[1])
    if listfile:
        listfile.write("\t\t%s R%i" % (parts[0],parts[1]))


def D(parts):
    #print "D",parts
    storeRam(opcodes.get(parts[0])[1])
    if listfile:
        listfile.write("\t\t%s" % (parts[0]))

def I(parts):
    #print "BR",parts
    storeRam(opcodes.get(parts[0])[1])
    storeRam(parts[1])
    if listfile:
        listfile.write("\t%s 0x%02x" % (parts[0],parts[1]))


def DIR(parts):
    #print "DIR",parts
    if parts[0] == '.orig':
        setRamPointer(parts[1])
        if listfile:
            listfile.write("\t\t\t%s %2x" % (parts[0],parts[1]))
    else:
        storeRam(parts[1])
        if listfile:
            listfile.write("\t\t%s 0x%2x" % (parts[0],parts[1]))




# Opcode Types
#
#   Dir Assembler Directive
#   RR  Register, Register      00 II RsRs RdRd     II = Instruction, RsRs = Source Reg,  RdRd = Dest Reg
#   RI  Register Immediate      01 IIII RR          IIII = Instruction, RR = Registr, Next Byte = Operand
#   R   Register                11 IIII RR          IIII = Instruction, RR = Register
#   I   Immediate               100 IIIII           IIIII = Instruction, Next Byte = Operand
#   D   Direct                  101 IIIII           IIIII = Instruction

#
# opcode, length, codeRoot, processing function
#

opcodes = {'.orig': [0, 0, DIR,"DIR"],
           '.data': [1, 0,DIR, "DIR"],
           'MOV': [1, 0b00000000, RR,"RR"],
           'LD':  [1, 0b00010000, RR,"RR"],
           'STR': [1, 0b00100000, RR,"RR"],

           'LDRI':  [2, 0b01000000, RI,"RI"],
           'BRZ':   [2, 0b01001000, RI,"RI"],
           'BRNZ':  [2, 0b01001100, RI,"RI"],
           'INR':   [2, 0b01110000, RI,"RI"],
           'OUTR':  [2, 0b01110100, RI,"RI"],
           'INVR':  [2, 0b01111000, RI,"RI"],
           'OUTVR': [2, 0b01111100, RI,"RI"],

           'BR':    [2, 0b10000000, I,"I"],
           'LDSP':  [2, 0b10000001, I,"I"],

           'LOFF':  [1, 0b10100000, D,"D"],
           'LON':   [1, 0b10100001, D,"D"],
           'RET':   [1, 0b10100010, D,"D"],
           'INTE':  [1, 0b10100011, D,"D"],
           'IRET':  [1, 0b10100100, D,"D"],

           'INC':   [1, 0b11000000, R,"R"],
           'DEC':   [1, 0b11000100, R,"R"],

           'BAZ':    [2, 0b11001000, I,"I"],
           'BANZ':   [2, 0b11001100, I,"I"],

           'LDA':   [1, 0b11010000, R,"R"],
           'STRA':  [1, 0b11010100, R,"R"],
           'ADD' :  [1, 0b11011000, R,"R"],
           'CALL':  [1, 0b11111000, R,"R"],
}

symbolTable = {"R0": 0, "R1": 1, "R2": 2, "R3": 3}


def dumpSymbols():
    print
    print "Symbol Table"
    for i in symbolTable:
        print i, "%02x" % symbolTable.get(i)


def dumpOpcodes():
    print "Opcode list"
    for i in opcodes:
        print i,
        for j in range(0, 3):
            print opcodes.get(i)[j],
        print

#
# RAM Buffer Array
#
ramSize = 256
ram = [0 for i in range(ramSize)]
ramPointer = 0


def dumpRam():
    for i in range(0, ramSize, 16):
        for j in range(0, 16):
            print "%02x" % ram[i + j],
        print


def storeRam(val):
    global ramPointer
    ram[ramPointer] = val
    if listfile:
        listfile.write("%02x "  % (val))
    ramPointer = ramPointer + 1


def setRamPointer(addr):
    global ramPointer
    ramPointer = addr

def getRamPointer():
    global ramPointer
    return(ramPointer)


#build symbol table
def pass1(program):
    pc = 0
    for line in program:
        startPos = 0

        parts = string.split(line)
        #print pc,parts,len(parts)
        if not parts: continue          #blank line
        if line[0] == '#': continue     #comment

        if line[0] == ':':              #label, all labels start with :
            label = parts[0][1:]        #skip over :
            symbolTable[label] = pc
            startPos = 1

        if len(parts) == 1 and line[0] == ':' :continue   #label only

        if parts[startPos] == ".orig":          #directive, add handler for all directives later, .data .bs
            pc = int(parts[startPos + 1], 16)
            #FIX if line had label reassign val to .orig value
        elif parts[startPos] == ".data":
            pc = pc + 1
        else:
            #print "add to pc",opcodes[parts[startPos]][0]
            pc = pc + opcodes[parts[startPos]][0]  #increase pc by number of bytes in opcode


def pass2(program):

    setRamPointer(0)

    for line in program:
        startPos = 0
        parts = string.split(line)

        if not parts: continue          #blank line
        if line[0] == '#': continue     #comment

        if line[0] == ':':              #skip over label
            startPos = 1

        if len(parts) == 1 and line[0] == ':' :continue   #label only
        if listfile:
            listfile.write("%04x  " % getRamPointer())

        for i in range(startPos+1, len(parts)):       #symbolic string subs all params
            if parts[i] in symbolTable.keys():
                parts[i] = symbolTable.get(parts[i])
            else:
                if type(parts[i]) == type("a"):       #convert alpha params to nums, assumes hex
                    parts[i] = int(parts[i], 16)

        opcodes.get(parts[startPos])[2]   (parts[startPos:])

        listfile.write("\n")

f = open(sourceFile, 'r')
if listfile:
    if listfile == sys.stdout:
        a=1
    else:
        listfile = open(listfile, 'w')

program = f.readlines()
pass1(program)
pass2(program)

#dumpRam()

f = open(romImage, 'w')
f.write("v2.0 raw\n")
for i in range (0,ramSize,8):
    for j in range (0,8):
        f.write ( "%02x"% ram[i+j])
        f.write (" ")
    f.write("\n")

print

dumpSymbols()




