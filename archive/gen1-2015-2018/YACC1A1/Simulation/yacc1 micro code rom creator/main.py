__author__ = 'ken'

import sys

#Create empty ROM image

rom=[0xff for i in range(8192)]

# microcode rom bit assignments

bits =  {'R0-DOUT':0, \
         'R0-AOUT':1, \
         'R0-DIN':2, \
         'R1-DOUT':3, \
         'R1-AOUT':4, \
         'R1-DIN':5, \
         'R2-DOUT':6, \
         'R2-AOUT':7, \
         'R2-DIN':8, \
         'R3-DOUT':9, \
         'R3-AOUT':10, \
         'R3-DIN':11, \
         'IOADDR': 12,\
         'IOR' :13,\
         'IOW' :14,\
         'MEM-IN':15, \
         'MEM-OUT': 16,\
         'MEM-WR':17,\
         'PC-DOUT':18, \
         'PC-AOUT':19, \
         'PC-LD':20, \
         'PC-INC':21,\
         'LD-BR' :22,\
         'R-LD' : 23,\
         'R-CT' :24 ,\
         'COND0' : 25 ,\
         'COND1' : 26 ,\
         'COND2':27, \
         'SP-DIN': 28,\
         'SP-AOUT': 29,\
         'LD-INS':30, \
         'RST-UC':31, \
         'ALUSEL0': 32,\
         'ALUSEL1' :33, \
         'ALUSEL2' :34, \
         'ALUSEL3' :35, \
         'AC-IN':36,\
         'AC-OUT':37,\
         'AC-WR':38,\
         'INT-START': 39,\
         'INT-END': 40,\
         'INT-EN': 41,\
         'unused3': 42,\
         'unused4': 43,\
         'unused5': 44,\
         'INT-JMP': 45,\
         'LON': 46,\
         'LOFF': 47,};

# Conditional Branch Selector

conditional =  {'BR':[0, ""],\
                'DZ':[1, "COND0"], \
                'DNZ':[2,"COND1"],\
                'GT':[3, "COND1 COND0"],\
                'LT':[4, "COND2"],\
                'EQ':[5, "COND2 COND0"],\
                'UNUSED1':[6, "COND2 COND1"],\
                'UNUSED2': [7, "COND2 COND1 COND0"],
                }

# ALU functon select

aluSel = {'AND' : [15, "AULSEL3 ALUSEL2 ALUSEL1 ALUSEL0"],\
          'OR' :  [14, "ALUSEL3 ALUSEL2 ALUSEL1"],\
          'XOR' : [13, "ALUSEL3 ALUSEL2 ALUSEL0"],\
          'NOT' : [12, "ALUSEL3 ALUSEL2"],\
          'ADD' : [11, "ALUSEL3 ALUSEL1 ALUSEL0"], \
          }

#Microcode generation utility routines

def instruction(f,ins):
    f.write(":ins %02x\n" % ins)

def noop(f):
    f.write("-\n")

def endInstruction(f):

    f.write("RST-UC\n")
    f.write(":end\n")

def fetch(f):
    noop(f)
    f.write("PC-AOUT" +  " MEM-OUT" + "\n")
    f.write("PC-AOUT" +   " MEM-OUT" + " LD-INS"+ "\n")
    f.write("PC-INC\n")

def pcInc(f):
    f.write("PC-INC\n")

# Generate Microcode "Assembler" code

def genCodes():

    print("GenCodes")
    f = open('codefile', 'w')

    #initial instruction after reset
    instruction(f,0x00)
    fetch(f)
    endInstruction(f)

    #interupt handler code
    instruction(f,0xff)
    noop(f)
    f.write("PC-AOUT" +  " MEM-OUT" + "\n")
    f.write("PC-AOUT" +   " MEM-OUT" + " LD-INS"+ "\n")
    noop(f)
    f.write("INT-START\n")
    f.write("SP-AOUT  PC-DOUT MEM-IN\n")        #save pc to stack
    f.write("SP-AOUT  PC-DOUT MEM-IN  MEM-WR\n")

    f.write("R-CT\n");                     #decrement sp
    f.write("%s %s\n" % ("R-CT", "SP-DIN"))

    f.write("INT-JMP MEM-OUT\n")    #load PC with addr INT-JMP location (0xff)
    f.write("INT-JMP MEM-OUT LD-BR\n")
    f.write("PC-LD\n");
    f.write("PC-LD PC-INC\n");
    endInstruction(f)

    #MOV R R
    for src in range(0,4):
        for dst in range(0,4):
            if src == dst :continue
            else:
                instruction(f,0b00000000 | src <<2 | dst)
                fetch(f)
                f.write("%s%i%s" % ("R",src,"-DOUT\n"))
                f.write("%s%i%s %s%i%s" %("R",src,"-DOUT","R", dst,"-DIN\n"))
                endInstruction(f)

    #LD R I
    for src in range(0,4):
        for dst in range(0,4):
            if src == dst :continue
            else:
                instruction(f,0b00010000 | src <<2 | dst)
                fetch(f)
                f.write("%s%i%s %s\n" % ("R",src,"-AOUT","MEM-OUT"))
                f.write("%s%i%s %s %s%i%s\n" % ("R",src,"-AOUT","MEM-OUT","R",dst,"-DIN"))
                endInstruction(f)

    #STR
    for src in range(0,4):
        for dst in range(0,4):
            if src == dst :continue
            else:
                instruction(f,0b00100000 | src <<2 | dst)
                fetch(f)
                f.write("%s%i%s %s %s%i%s\n" % ("R",src,"-DOUT","MEM-IN", "R",dst,"-AOUT"))
                f.write("%s%i%s %s %s%i%s %s\n" % ("R",src,"-DOUT","MEM-IN", "R",dst,"-AOUT","MEM-WR"))
                endInstruction(f)

    #LDRI
    for dst in range(0,4):
        instruction(f,0b01000000 | dst)
        fetch(f)
        f.write("%s %s\n" % ("PC-AOUT","MEM-OUT"))
        f.write("%s %s %s%i%s\n" % ("PC-AOUT","MEM-OUT","R",dst,"-DIN"))
        pcInc(f)
        endInstruction(f)

    #OUTVR
    for dst in range(0,4):
        instruction(f,0b01111100 | dst)
        fetch(f)
        f.write("PC-AOUT  MEM-OUT\n");
        f.write("PC-AOUT  MEM-OUT IOADDR\n");
        f.write(" %s %s%i%s\n" % ("MEM-OUT","R",dst,"-AOUT"))
        f.write("%s %s %s%i%s\n" % ("MEM-OUT","IOW","R",dst,"-AOUT"))
        pcInc(f)
        endInstruction(f)

    #BR
    instruction(f,0b10000000)
    fetch(f)
    f.write("PC-AOUT  MEM-OUT\n");
    f.write("PC-AOUT  MEM-OUT LD-BR\n");
    f.write("PC-LD\n");
    f.write("PC-LD PC-INC\n");
    #pcInc(f)
    endInstruction(f)

    #INC
    for dst in range(0,4):
        instruction(f, 0b11000000 |dst)
        fetch(f)
        f.write("R-LD R-CT\n");
        f.write("%s %s %s%i%s\n" % ("R-LD", "R-CT", "R",dst,"-DIN"))
        endInstruction(f)

    #DEC
    for dst in range(0,4):
        instruction(f, 0b11000100 |dst)
        fetch(f)
        f.write("R-CT\n");
        f.write("%s %s%i%s\n" % ("R-CT", "R",dst,"-DIN"))
        endInstruction(f)

    #LDA
    for dst in range(0,4):
        instruction(f, 0b11010000 |dst)
        fetch(f)
        f.write("%s%i%s %s\n" % ("R",dst,"-DOUT","AC-IN"))
        f.write("%s%i%s %s %s\n" % ("R",dst,"-DOUT","AC-IN","AC-WR"))
        endInstruction(f)

    #STRA
    for dst in range(0,4):
        instruction(f, 0b11010100 |dst)
        fetch(f)
        f.write("%s\n" % ("AC-OUT"))
        f.write("%s%i%s %s\n" % ("R",dst,"-DIN","AC-OUT"))
        endInstruction(f)

    #ADD
    for dst in range(0,4):
        instruction(f, 0b11011000 |dst)
        fetch(f)
        f.write("%s%i%s\n" % ("R",dst,"-DOUT"))
        f.write("%s%i%s %s\n" % ('R',dst,'-DOUT',aluSel.get('ADD')[1]))
        f.write("%s%i%s %s %s\n" % ('R',dst,'-DOUT', aluSel.get('ADD')[1], "AC-WR"))
        endInstruction(f)

    #BRZ
    for dst in range(0,4):
        instruction(f,0b01001000|dst)
        fetch(f)
        f.write("PC-AOUT  MEM-OUT\n")
        f.write("PC-AOUT  MEM-OUT LD-BR\n")
        f.write("%s%i%s %s\n" % ('R',dst,'-DOUT',conditional.get('DZ')[1]))
        f.write("%s%i%s %s %s\n" % (('R',dst,'-DOUT',conditional.get('DZ')[1], "PC-LD")))
        pcInc(f)
        endInstruction(f)

    #BRNZ
    for dst in range(0,4):
        instruction(f,0b01001100|dst)
        fetch(f)
        f.write("PC-AOUT  MEM-OUT\n")
        f.write("PC-AOUT  MEM-OUT LD-BR\n")
        f.write("%s%i%s %s\n" % ('R',dst,'-DOUT',conditional.get('DNZ')[1]))
        f.write("%s%i%s %s %s\n" % (('R',dst,'-DOUT',conditional.get('DNZ')[1], "PC-LD")))
        pcInc(f)
        endInstruction(f)

    #CALL
    for dst in range(0,4):
        instruction(f,0b11111000|dst)
        fetch(f)
        f.write("SP-AOUT  PC-DOUT MEM-IN\n")        #save pc to stack
        f.write("SP-AOUT  PC-DOUT MEM-IN  MEM-WR\n")
        f.write("R-CT\n");                     #decrement sp
        f.write("%s %s\n" % ("R-CT", "SP-DIN"))

        f.write("%s%i%s\n" % ('R',dst,'-DOUT',))    #call routine pointed to by R
        f.write("%s%i%s %s\n" % (('R',dst,'-DOUT', "LD-BR")))
        f.write("PC-LD\n");
        f.write("PC-LD PC-INC\n")

        endInstruction(f)

    #RET
    instruction(f,0b10100010)
    fetch(f)
    f.write("R-CT R-LD\n");
    f.write("%s %s\n" % ("R-CT R-LD", "SP-DIN"))

    f.write("SP-AOUT  MEM-OUT\n")
    f.write("SP-AOUT  MEM-OUT LD-BR\n")
    f.write("PC-LD\n");
    f.write("PC-LD PC-INC\n");
    endInstruction(f)

    #IRET
    instruction(f,0b10100100)
    fetch(f)
    f.write("R-CT R-LD\n");
    f.write("%s %s\n" % ("R-CT R-LD", "SP-DIN"))

    f.write("SP-AOUT  MEM-OUT\n")
    f.write("SP-AOUT  MEM-OUT LD-BR\n")
    f.write("PC-LD\n")
    f.write("INT-END PC-LD PC-INC\n")
    endInstruction(f)

    #LOFF
    instruction(f,0b10100000)
    fetch(f)
    f.write("LOFF\n")
    endInstruction(f)

    #LON
    instruction(f,0b10100001)
    fetch(f)
    f.write("LON\n")
    endInstruction(f)

    #INTE
    instruction(f,0b10100011)
    fetch(f)
    f.write("INT-EN\n")
    endInstruction(f)

    #LDSP
    instruction(f,0b10000001)
    fetch(f)
    f.write("PC-AOUT  MEM-OUT\n");
    f.write("PC-AOUT  MEM-OUT SP-DIN\n");
    pcInc(f)
    endInstruction(f)

#
# Start of main
#

# Generate Assembler codes

genCodes()

# Parse Assembler code into ROM images

f = open('codefile', 'r')

maxUCode=0

state = "newins"

#parser state machine
# 1 Look for :ins
# 2 One or more lines of microcode
# 3 :end
#

for line in f:
    str = line.split()
    if state == "newins":
        if str[0] != ':ins':
            print "ins expected"
            sys.exit(0)
        addr = int(str[1], 16) * 32
        state = "opcodes"
    elif state =="opcodes":
        print str
        if str[0] == ":end":
            print "found end"
            if addr & 0x1f > maxUCode:
                maxUCode = addr & 0x1f
            state = "newins"
        else:
            romentry = 0
            for codes in str:
                if codes == '-': continue
                else:
                    print codes,bits[codes]
                    romentry |= (int(1 << bits[codes]))
            print "%08x" % addr,"=","%012x" % romentry
            rom[addr] = romentry
            addr += 1

print "Max uCode lines", maxUCode

#Generate Rom Images

f = open('rom1', 'w')
f.write("v2.0 raw\n")
for i in range (0,8192,8):
    for j in range (0,8):
        f.write ( "%08x" % (rom[i+j] & 0xffffffff))
        f.write (" ")
    f.write("\n")
f.close()


f = open('rom2', 'w')
f.write("v2.0 raw\n")
for i in range (0,8192,8):
    for j in range (0,8):
        f.write ( "%04x"% ((rom[i+j]>>32) & 0xffff))
        f.write (" ")
    f.write("\n")
f.close()

