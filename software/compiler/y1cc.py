#!/usr/bin/env python3
"""y1cc - a small C cross-compiler for the YACC1 (2026-09-22).

Emits YACC1 assembly for software/assembler (RC/asm, yacc1.def); the assembler turns it into an Intel-hex .img that
the emulator runs (`emulator -x -f prog.img`, see --boot) and that the monitor's loader will put in RAM on the machine.

The front end (lexer, parser, C subset) is the one of the P8X compiler (p8x/compiler/p8cc.py, same author/machine
family), so P8X C programs port with their source unchanged as far as the subset goes; the back end is new, written
for what the YACC1 actually has: an 8-bit accumulator (ACC) and 8-bit TMP register, a 74LS283 adder with a carry
flip-flop, eight 16-bit index registers R0-R7 of which R0 is the PC and R1 the stack pointer, byte loads/stores
through any index register (LDAVR/STAVR), absolute 16-bit loads/stores of an index register (LDR/STR), and
big-endian words in memory (high byte at the lower address, the order LDR/STR/DW/MVIW use).

The C subset
  types        int (16-bit UNSIGNED - as in p8cc, where int is used as unsigned), char (8-bit unsigned), pointers,
               arrays T a[N], struct/union (used by pointer or member; no by-value struct params/returns/assignment);
               `unsigned`, `const`, `static`, `void` accepted where they make sense
  top level    struct/union definitions, function definitions and prototypes, globals with constant initializers
               (scalars, strings, {lists}, char[] and pointer tables; [] length inferred from the initializer)
  statements   { }  decl (with initializer)  if/else  while  for(e;e;e)  switch/case/default  break  continue
               return [e]  expr;  ;
  expressions  =  += -= *= /= %= &= |= ^= <<= >>=   ++ -- (pre/post)   || &&  | ^ &  == != < > <= >=  << >>
               + - * / %   unary - ! ~ & *   a[i]  s.m  p->m   f(args)   sizeof(type)/sizeof(expr) (constant)
               literals: decimal, 0x hex, 'c', "string"; #define NAME value; #include "file" (textual, once)
  builtins     putchar(c)  getchar()  puts(s)  (console: port 2 on the emulator, the monitor's BIOS charout/uartin
                 vectors at $FFC4/$FFE8 on the machine; the runtime picks the path at run time with BRDEV;
                 with --os the Y1/OS syscalls CONOUT/CONIN instead, so the shell can redirect them)
               peek(addr) poke(addr,v)  peekw(addr) pokew(addr,v)   (byte / big-endian word memory access)
               inp(port) outp(port,v)   (INP/OUTA/OUTI: port is a constant 0..15)
               halt()  (HALT)   bios(addr, r7, acc) -> ACC   (JSR a monitor routine with R7 and ACC set up)
               call(addr) -> int  (JSRUR to an address in a variable: the OS running a program; returns its R3)
               argstr() -> char*  (the command tail the OS left for the program at $0F40, up to 127 chars + NUL)
               sys(n, a, b, c) -> int  (a Y1/OS syscall, 2026-09-23: a, b, c (any of them optional) go to the
                 parameter words SYSARG0..2 at $0F06/$0F08/$0F0A, entry n (0..21) of the OS's jump table SYSTAB at
                 $0F14 is JSRURed (22..31: SYSTAB2 at $4FC0, 2026-09-25; a computed n reaches 0..21), the result
                 word SYSRES at $0F0C comes back; os/lib_fs.c wraps them as fopen()...)
               funcaddr(f) -> int  (the address of function f: how the OS fills SYSTAB with pokew(SYSTAB+2*n,
                 funcaddr(handler)); f is kept in the image even if nothing calls it directly)
  recursion    (2026-09-24) direct and mutual: parameters and locals still live at fixed addresses (static frames);
               a call inside a recursive cycle pushes the callee's frame on the stack and pops it back after the
               return. main cannot be recursive; the address of a recursive function's local cannot be passed into
               a call inside its cycle (compile errors). See "Recursion" below and the README.
  limits       Compound assignment and
               ++/-- evaluate their lvalue twice (keep the lvalue side-effect free). No floating point, no long,
               no signed arithmetic (comparisons and division are unsigned), no function pointers.

Execution model (the part that is YACC1-specific)
  * R3 is the 16-bit expression accumulator: every expression leaves its value there (chars zero-extended).
    R4 is the second operand / scratch pointer, R5-R7 are scratch for the runtime helpers (R7 also carries the
    string pointer for the monitor's stringout). R2 is NEVER touched: on the hardware LDA/STA/LDT/STT/LDR/STR
    use R2 as the hidden operand-address register (the emulator uses a ninth register instead).
  * Variables are static: a global is a labelled word/byte, a function's parameters and locals are labelled slots
    in the function's own frame area (a char scalar occupies a 2-byte slot whose high byte is kept zero, so it is
    loaded with one LDR like an int; char arrays and struct members are true bytes). A load or store of a scalar
    is therefore one 3-byte LDR/STR. A function's slots are consecutive DS lines: its frame.
  * Recursion (2026-09-24): a call whose callee can reach the caller again (both in one strongly connected
    component of the call graph) saves the callee's whole frame on the R1 stack before the arguments are stored
    and restores it after the JSR (inline LDR/PUSHR ... POPR/STR up to 8 bytes, rt_fsave/rt_frest above that).
    Every other call, and every function outside a cycle, compiles exactly as before (tests/compiler/diffcheck.py).
  * Calls: the caller evaluates each argument into R3 and stores it straight into the callee's parameter slot
    (STR R3,slot), then JSR. If a later argument's evaluation could itself reach the callee (f(a, g()) where g
    calls f) the earlier arguments are parked on the stack meanwhile. The result comes back in R3. Return is RET.
  * 16-bit arithmetic is done byte-wise through ACC/TMP: + & | ^ inline (ADDT/ADDTC etc., 8-10 bytes), - via the
    runtime (two's-complement add; SUB's borrow is not usable: the emulator and the hardware disagree on it),
    * / % << >> via runtime loops (R5-R7). Shifts by small constants are inline; *2 /2 %2^k are shifts/masks.
  * Comparisons in conditions branch directly on the 8-bit comparators (BRLT/BRGT/BREQ/BRNEQ compare ACC with
    TMP): high bytes first, then low bytes; two char operands need only one compare. Unsigned, like p8cc.
  * The carry flag is used only inside ADDT/ADDTC pairs with nothing but register moves between them (the idiom
    the monitor's do_add16 proved on the hardware); plain shifts and subtracts never feed a following carry op.

Usage:  y1cc.py prog.c [-o prog.asm] [--org 0x3000] [--boot] [--vector] [--no-brur] [--os] [--xisa] [--stack ADDR] [-l]
  --org     load address (default $3000: $1000-$1FFF is BASIC's token buffer, which the monitor's boot clears,
            and the monitor's T tests scribble at $2000). main is first: the monitor's `G3000` calls it (JSRUR R7,
            monitor of 2026-09-22) and its RET returns to the command loop.
  --vector  layout for the monitor burned in 2021, whose G was BRVR R7 (an indirect jump through the word at the
            address, no return address): a 2-byte vector, a stub that JSRs main and restarts the monitor (BR $F000)
  --boot    append a boot stub at $F000 (SP=$0EFF, JSR main, HALT) so `emulator -x -f prog.img` runs it stand-alone
  --no-brur never emit BRUR ($AD, added 2026-09-22): a switch is always a compare chain. For the machine until its
            sequencer EEPROM holds the microcode with BRUR.
  --os      a Y1/OS program (2026-09-23; os/Makefile builds the OS and every /BIN command with it): putchar/puts
            go through the OS syscall CONOUT (19) and getchar through CONIN (17) instead of the ROM, so the shell
            can redirect them (`>`, `>>`, `<`, `|`). getchar still returns 0 at the end of input (CONIN's 65535).
            R3/R4 are preserved around the syscall. Without --os the console runtime is the ROM/port-2 one, unchanged.
  --xisa    (2026-09-24) use the instructions added to the microcode that day: LDZ/STZ Rn,d (the word at R6.hi:d, 2
            bytes instead of LDR/STR's 3) for the hottest 2-byte variables, placed in one 256-byte page at the end of
            the BSS (zpage, aligned by `zpad: DS (256-(zpad).0)&255`), R6 = the page register (main and every
            funcaddr() entry load it, and it is reloaded after anything that leaves compiled code: bios(), call(),
            sys(), the console helpers, rt_fsave/rt_frest); ADDIW Rn,#w for 16-bit constant adds; SHL16 R3 for << 1.
            R6 is then reserved: rt_divmod keeps its remainder in R5. Needs the 2026-09-24 microcode on the machine.
            Without the option the output is exactly what it was.
  --stack ADDR  (2026-09-25) main runs on a stack of its own that starts at ADDR (the first byte pushed; it grows
            down): main begins `MOVRR R1,R5 / MVIW R1,ADDR / PUSHR R5` and every return from main is
            `POPR R5 / MOVRR R5,R1 / RET`, so the caller's stack (the shell's, the monitor's) is as it was. For
            programs that need more than the 768-byte monitor stack (the native compiler's passes). The end of main
            always gets that epilogue (4 dead bytes after a final return). Without the option the output is exactly
            what it was.
  -l        print the line count / a summary
"""
import sys, os, re, time

ORG_DEFAULT = 0x3000        # $1000-$1FFF is BASIC's token buffer (cleared at every monitor boot), $2000.. the monitor's test scratch
STACK_TOP = 0x0EFF          # the monitor's stack (monitor.asm: STACK EQU 0EFFh)
MONITOR_RESTART = 0xF000    # where a program goes when main returns on the machine (the monitor's reset entry)
ARGBUF = 0x0F40             # the OS's command-tail buffer for programs (monitor.asm ARGBUF, 128 bytes since 2026-09-23); argstr()
SYSARG = 0x0F06             # sys() parameter block: SYSARG0/1/2 = $0F06/$0F08/$0F0A (big-endian words, the machine's own order)
SYSRES = 0x0F0C             # sys() result word, written by the OS handler
SYSTAB = 0x0F14             # the OS syscall jump table: 22 big-endian word entries $0F14..$0F3F, filled by Y1/OS at boot
SYS_CONIN = 17             # --os: getchar() is this syscall (os/lib_abi.c SYS_CONIN)
SYS_CONOUT = 19            # --os: putchar()/puts() go through this syscall (os/lib_abi.c SYS_CONOUT, 2026-09-23)
SYSOLD = 21                 # entries 0..21 are at SYSTAB (the monitor's free variable space: $0F06..$0F0F after its own
                            # variables, $0F14..$0F3F between CFLBA2 $0F12 and ARGBUF $0F40; firmware/abi/README.md)
SYSTAB2 = 0x4FC0            # (2026-09-25) the 32-entry table in the OS's RAM, $4FC0..$4FFF: entries 0..21 the same as
                            # SYSTAB's, 22..31 new; a constant n over 21 goes through it (a computed n: SYSTAB, 0..21)
SYSMAX = 31
BIOS_CHAROUT = 0xFFC4       # monitor BIOS vectors (monitor.asm, org 0ffc0h: 4 bytes per entry)
BIOS_UARTIN = 0xFFE8
LABEL_MAX = 29              # RC/asm: labels[][30]; a 30+ character label crashes the assembler

# --------------------------------------------------------------------------- #
# Lexer (p8cc's, plus #include, sizeof, break/continue, ++ -- and op=)
# --------------------------------------------------------------------------- #
KEYWORDS = {"int", "char", "void", "struct", "union", "unsigned", "const", "static",
            "if", "else", "while", "for", "return", "break", "continue", "sizeof", "switch", "case", "default"}
PUNCT = ["<<=", ">>=", "==", "!=", "<=", ">=", "<<", ">>", "&&", "||", "->", "++", "--",
         "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=",
         "{", "}", "(", ")", "[", "]", ";", ",", "=", ".", "?", ":",
         "+", "-", "*", "/", "%", "<", ">", "!", "&", "|", "^", "~"]
ESC = {"n": 10, "r": 13, "t": 9, "0": 0, "\\": 92, "'": 39, '"': 34, "a": 7, "b": 8, "f": 12, "e": 27}


def lex(src, path="<src>", included=None, macros=None):
    toks, i, n, line = [], 0, len(src), 1
    macros = {} if macros is None else macros           # object-like #define NAME value
    included = set() if included is None else included
    def err(m): sys.exit("y1cc: %s:%d: %s" % (path, line, m))
    while i < n:
        c = src[i]
        if c == "\n": line += 1; i += 1; continue
        if c in " \t\r\f": i += 1; continue
        if c == "#":                                    # preprocessor line: #define, #include; others ignored
            # its text up to the newline: a /* */ comment in it is one space and may go on over newlines (the line
            # then ends at the newline after it), a // comment ends it, neither inside quotes (2026-09-25: a comment
            # from a #define line onto the next left the next line to be lexed as code)
            eol, text, nl, q = i, [], 0, None
            while eol < n and src[eol] != "\n":
                ch = src[eol]
                if not q and src.startswith("/*", eol):
                    k = src.find("*/", eol + 2)
                    if k < 0: err("unterminated comment")
                    nl += src.count("\n", eol, k); text.append(" "); eol = k + 2; continue
                if not q and src.startswith("//", eol):
                    eol = src.find("\n", eol); eol = n if eol < 0 else eol; break
                if q:
                    if ch == q: q = None
                elif ch in "\"'": q = ch
                text.append(ch); eol += 1
            parts = "".join(text).split(None, 2)
            if parts and parts[0] == "#define" and len(parts) >= 3:
                v = parts[2].split()[0]
                try: macros[parts[1]] = int(v, 0)
                except ValueError:
                    if len(v) == 3 and v[0] == v[2] == "'": macros[parts[1]] = ord(v[1])
                    else: err("#define %s: value %r is not an integer" % (parts[1], v))
            elif parts and parts[0] == "#include" and len(parts) >= 2:
                m = re.match(r'"([^"]+)"', parts[1] if len(parts) == 2 else parts[1] + " " + parts[2])
                if not m: err("#include wants a \"file\"")
                inc = resolve_include(m.group(1), path)
                if inc not in included:                 # each file once
                    included.add(inc)
                    sub = lex(open(inc).read(), inc, included, macros)
                    toks.extend(sub[:-1])               # drop its eof
            line += nl; i = eol; continue
        if src.startswith("//", i):
            eol = src.find("\n", i); eol = n if eol < 0 else eol
            body = src[i + 2:eol].lstrip()               # "//#define NAME value" (p8cc style) also honoured
            if body.startswith("#define"):
                parts = body.split(None, 2)
                if len(parts) >= 3:
                    try: macros[parts[1]] = int(parts[2].split()[0], 0)
                    except ValueError: err("//#define %s: not an integer" % parts[1])
            i = eol; continue
        if src.startswith("/*", i):
            j = src.find("*/", i + 2)
            if j < 0: err("unterminated comment")
            line += src[i:j].count("\n"); i = j + 2; continue
        if c.isalpha() or c == "_":
            j = i + 1
            while j < n and (src[j].isalnum() or src[j] == "_"): j += 1
            w = src[i:j]
            if w in macros: toks.append(("num", macros[w], line)); i = j; continue
            toks.append(("kw" if w in KEYWORDS else "id", w, line)); i = j; continue
        if c.isdigit():
            j = i + 1
            if c == "0" and i + 1 < n and src[i + 1] in "xX":
                j = i + 2
                while j < n and src[j] in "0123456789abcdefABCDEF": j += 1
                if j == i + 2: err("bad hex constant")          # "0x" alone was a Python ValueError until 2026-09-24
                v = int(src[i + 2:j], 16)
            else:
                while j < n and src[j].isdigit(): j += 1
                v = int(src[i:j])
            if v > 0xFFFF: err("integer constant %s does not fit 16 bits" % src[i:j])   # int is 16-bit: no silent truncation
            toks.append(("num", v, line)); i = j; continue
        if c == "'":
            if src[i + 1] == "\\":
                if src[i + 2] not in ESC: err("bad escape \\%s" % src[i + 2])
                toks.append(("num", ESC[src[i + 2]], line)); i += 4; continue
            toks.append(("num", ord(src[i + 1]), line)); i += 3; continue
        if c == '"':
            j, buf = i + 1, []
            while j < n and src[j] != '"':
                if src[j] == "\\":
                    if src[j + 1] not in ESC: err("bad escape \\%s" % src[j + 1])
                    buf.append(ESC[src[j + 1]]); j += 2
                else:
                    buf.append(ord(src[j])); j += 1
            if j >= n: err("unterminated string")
            toks.append(("str", buf, line)); i = j + 1; continue
        for p in PUNCT:
            if src.startswith(p, i):
                toks.append(("op", p, line)); i += len(p); break
        else:
            err("bad character %r" % c)
    toks.append(("eof", None, line))
    return toks


def resolve_include(name, frompath):
    here = os.path.dirname(os.path.abspath(frompath))
    for d in (here, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib")):
        p = os.path.join(d, name)
        if os.path.exists(p): return os.path.abspath(p)
    sys.exit("y1cc: %s: cannot find #include \"%s\"" % (frompath, name))


# --------------------------------------------------------------------------- #
# Parser -> AST. A declared type is (base, ptr, count): base in {int, char, void, <struct tag>},
# ptr = pointer depth, count = array length (0 = scalar/pointer).
# --------------------------------------------------------------------------- #
class P:
    def __init__(self, toks): self.t = toks; self.i = 0
    def peek(self): return self.t[self.i]
    def kind(self): return self.t[self.i][0]
    def val(self): return self.t[self.i][1]
    def line(self): return self.t[self.i][2]
    def next(self): tok = self.t[self.i]; self.i += 1; return tok
    def err(self, m): sys.exit("y1cc: line %d: %s" % (self.line(), m))
    def eat(self, v):
        if self.t[self.i][1] != v: self.err("expected %r, got %r" % (v, self.t[self.i][1]))
        self.i += 1
    def accept(self, v):
        if self.t[self.i][1] == v: self.i += 1; return True
        return False
    def is_type_start(self):
        return self.val() in ("int", "char", "void", "struct", "union", "unsigned", "const", "static")

    def program(self):
        d = []
        while self.kind() != "eof":
            t = self.toplevel()
            if t[0] == "gvars": d.extend(t[1])
            else: d.append(t)
        return d

    def base_and_ptr(self):
        while self.val() in ("const", "static", "unsigned"): self.next()    # qualifiers: no effect
        if self.val() in ("struct", "union"):
            self.next(); tag = self.next()
            if tag[0] != "id": self.err("expected struct/union tag")
            base = tag[1]
        elif self.val() in ("int", "char", "void"):
            base = self.next()[1]
        elif self.t[self.i - 1][1] == "unsigned":
            base = "int"                                    # bare `unsigned`
        else:
            self.err("expected a type")
        ptr = 0
        while True:
            if self.accept("*"): ptr += 1
            elif self.val() == "const": self.next()
            else: break
        return base, ptr

    def struct_def(self):                                   # struct/union T { ... };
        kind = self.next()[1]
        tag = self.next()[1]; self.eat("{")
        members = []
        while self.val() != "}":
            base, ptr = self.base_and_ptr()
            nm = self.next()[1]; count = 0
            if self.accept("["): count = self.const_expr(); self.eat("]")
            self.eat(";")
            members.append(((base, ptr, count), nm))
        self.eat("}"); self.eat(";")
        return ("structdef", kind, tag, members)

    def const_expr(self):                                   # array sizes: a number or a #define'd number
        e = self.expr()
        v = fold(e)
        if v is None: self.err("constant expression expected")
        return v

    def toplevel(self):
        if self.val() in ("struct", "union") and self.t[self.i + 2][1] == "{":
            return self.struct_def()
        base, ptr = self.base_and_ptr()
        name = self.next()
        if name[0] != "id": self.err("expected name")
        name = name[1]
        if self.accept("("):
            params = []
            if self.val() == "void" and self.t[self.i + 1][1] == ")": self.next()
            elif self.val() != ")":
                params.append(self.param())
                while self.accept(","): params.append(self.param())
            self.eat(")")
            if self.accept(";"): return ("proto", (base, ptr, 0), name, params)
            return ("func", (base, ptr, 0), name, params, self.block())
        decls = []
        while True:                                         # int a, *b, c[3];
            arr = False; count = 0
            if self.accept("["):
                arr = True
                count = None if self.val() == "]" else self.const_expr()
                self.eat("]")
            init = None
            if self.accept("="): init = self.initializer()
            decls.append(("gvar", base, ptr, arr, count, name, init))
            if not self.accept(","): break
            ptr = 0                                     # a new declarator starts from the base type (int *p, q)
            while self.accept("*"): ptr += 1
            name = self.next()[1]
        self.eat(";")
        return decls[0] if len(decls) == 1 else ("gvars", decls)

    def initializer(self):                                  # constant global initializer
        if self.accept("{"):
            items = []
            if self.val() != "}":
                items.append(self.initializer())
                while self.accept(","):
                    if self.val() == "}": break
                    items.append(self.initializer())
            self.eat("}")
            return ("initlist", items)
        if self.kind() == "str": return ("initstr", self.next()[1])
        if self.accept("&"):                                # &variable
            nm = self.next()
            if nm[0] != "id": self.err("expected a name after &")
            return ("initaddr", nm[1])
        if self.kind() == "id" and self.t[self.i + 1][1] in (",", ";", "}"):   # an array's address
            return ("initaddr", self.next()[1])
        e = self.expr(); v = fold(e)
        if v is None: self.err("non-constant global initializer")
        return ("initnum", v)

    def param(self):
        base, ptr = self.base_and_ptr()
        nm = self.next()
        if nm[0] != "id": self.err("expected parameter name")
        if self.accept("["):                                # T a[] as a parameter = pointer
            self.eat("]"); ptr += 1
        return ((base, ptr, 0), nm[1])

    def block(self):
        self.eat("{"); s = []
        while self.val() != "}": s.append(self.stmt())
        self.eat("}"); return ("block", s)

    def stmt(self):
        v = self.val()
        if v == "{": return self.block()
        if self.is_type_start():
            base, ptr = self.base_and_ptr()           # the stars consumed here belong to the FIRST declarator
            decls = []
            while True:
                p = ptr; ptr = 0                        # later declarators start from the base type (int *p, q)
                while self.accept("*"): p += 1
                name = self.next()[1]; count = 0
                if self.accept("["):
                    count = self.const_expr(); self.eat("]")
                init = None
                if self.accept("="): init = self.expr()
                decls.append(("decl", (base, p, count), name, init))
                if not self.accept(","): break
            self.eat(";")
            return decls[0] if len(decls) == 1 else ("block", decls)
        if v == "if":
            self.next(); self.eat("("); c = self.expr(); self.eat(")")
            then = self.stmt(); els = self.stmt() if self.accept("else") else None
            return ("if", c, then, els)
        if v == "while":
            self.next(); self.eat("("); c = self.expr(); self.eat(")")
            return ("while", c, self.stmt())
        if v == "for":
            self.next(); self.eat("(")
            init = None if self.val() == ";" else self.expr(); self.eat(";")
            cond = None if self.val() == ";" else self.expr(); self.eat(";")
            post = None if self.val() == ")" else self.expr(); self.eat(")")
            return ("for", init, cond, post, self.stmt())
        if v == "return":
            self.next(); e = None if self.val() == ";" else self.expr()
            self.eat(";"); return ("return", e)
        if v == "switch":
            self.next(); self.eat("("); e = self.expr(); self.eat(")")
            if self.val() != "{": self.err("switch body must be a { block }")
            return ("switch", e, self.block())
        if v == "case":
            self.next(); k = self.const_expr(); self.eat(":"); return ("case", k)
        if v == "default": self.next(); self.eat(":"); return ("default",)
        if v == "break": self.next(); self.eat(";"); return ("break",)
        if v == "continue": self.next(); self.eat(";"); return ("continue",)
        if v == ";": self.next(); return ("empty",)
        e = self.expr(); self.eat(";"); return ("expr", e)

    def expr(self): return self.assign()

    ASSIGN_OPS = {"+=": "+", "-=": "-", "*=": "*", "/=": "/", "%=": "%", "&=": "&", "|=": "|", "^=": "^",
                  "<<=": "<<", ">>=": ">>"}
    def assign(self):
        left = self.logic_or()
        if self.val() == "?":                               # c ? a : b
            self.next(); a = self.assign(); self.eat(":"); b = self.assign()
            return ("cond", left, a, b)
        if self.val() == "=":
            self.next(); return ("assign", left, self.assign())
        if self.kind() == "op" and self.val() in self.ASSIGN_OPS:   # x op= e -> x = x op e (lvalue evaluated twice)
            op = self.ASSIGN_OPS[self.next()[1]]
            return ("assign", left, ("bin", op, left, self.assign()))
        return left

    def logic_or(self):
        left = self.logic_and()
        while self.val() == "||":
            self.next(); left = ("logor", left, self.logic_and())
        return left

    def logic_and(self):
        left = self.binary(0)
        while self.val() == "&&":
            self.next(); left = ("logand", left, self.binary(0))
        return left

    LEVELS = [["|"], ["^"], ["&"], ["==", "!="], ["<", ">", "<=", ">="],
              ["<<", ">>"], ["+", "-"], ["*", "/", "%"]]

    def binary(self, lvl):
        if lvl >= len(self.LEVELS): return self.unary()
        left = self.binary(lvl + 1)
        while self.val() in self.LEVELS[lvl]:
            op = self.next()[1]
            left = ("bin", op, left, self.binary(lvl + 1))
        return left

    def unary(self):
        v = self.val()
        if v in ("-", "!", "&", "*", "~"):
            self.next(); return ("unary", v, self.unary())
        if v in ("++", "--"):
            self.next(); return ("preinc", v, self.unary())
        if v == "sizeof":
            self.next()
            if self.val() == "(" and (self.t[self.i + 1][1] in ("int", "char", "struct", "union", "unsigned")):
                self.next(); base, ptr = self.base_and_ptr(); self.eat(")")
                return ("sizeoft", base, ptr)
            return ("sizeofe", self.unary())
        return self.postfix()

    def postfix(self):
        e = self.primary()
        while True:
            if self.val() == "(":
                self.next(); args = []
                if self.val() != ")":
                    args.append(self.expr())
                    while self.accept(","): args.append(self.expr())
                self.eat(")")
                if e[0] != "id": self.err("call of non-function")
                e = ("call", e[1], args)
            elif self.val() == "[":
                self.next(); idx = self.expr(); self.eat("]")
                e = ("index", e, idx)
            elif self.val() == ".":
                self.next(); e = ("member", e, self.next()[1])
            elif self.val() == "->":
                self.next(); e = ("arrow", e, self.next()[1])
            elif self.val() in ("++", "--"):
                e = ("postinc", self.next()[1], e)
            else:
                return e

    def primary(self):
        k, v, _ = self.peek()
        if k == "num": self.next(); return ("num", v)
        if k == "str": self.next(); return ("str", v)
        if k == "id":  self.next(); return ("id", v)
        if v == "(":
            self.next(); e = self.expr(); self.eat(")"); return e
        self.err("unexpected %r" % (v,))


def fold(e):
    """Constant-fold an expression of literals -> int (mod 2^16), or None."""
    k = e[0]
    if k == "num": return e[1] & 0xFFFF
    if k == "unary" and e[1] in ("-", "~", "!"):
        v = fold(e[2])
        if v is None: return None
        return {"-": (-v) & 0xFFFF, "~": (~v) & 0xFFFF, "!": int(v == 0)}[e[1]]
    if k == "bin":
        a, b = fold(e[2]), fold(e[3])
        if a is None or b is None: return None
        op = e[1]
        if op in ("/", "%") and b == 0: return None
        # one lambda per operator: an eager dict evaluated a // b for EVERY fold, so `2 * ZERO` crashed (2026-09-23)
        r = {"+": lambda: a + b, "-": lambda: a - b, "*": lambda: a * b, "/": lambda: a // b, "%": lambda: a % b,
             "&": lambda: a & b, "|": lambda: a | b, "^": lambda: a ^ b,
             "<<": lambda: a << (b & 15), ">>": lambda: a >> (b & 15), "==": lambda: int(a == b), "!=": lambda: int(a != b),
             "<": lambda: int(a < b), ">": lambda: int(a > b), "<=": lambda: int(a <= b), ">=": lambda: int(a >= b)}[op]()
        return r & 0xFFFF
    if k == "sizeoft": return sizeof(e[1], e[2])
    if k == "cond":
        c = fold(e[1])
        if c is None: return None
        return fold(e[2] if c else e[3])
    return None


# --------------------------------------------------------------------------- #
# Code generator
# --------------------------------------------------------------------------- #
STRUCTS = {}      # tag -> {"size": n, "members": {name: (offset, base, ptr, count)}}


def sizeof(base, ptr):
    if ptr > 0 or base == "int": return 2
    if base == "char": return 1
    if base in STRUCTS: return STRUCTS[base]["size"]
    sys.exit("y1cc: unknown type %r" % base)


def kx(k):
    """An assembler operand for a 16-bit constant: an int (masked) or a label expression (as is)."""
    return str(k & 0xFFFF) if isinstance(k, int) else k

def klo(k): return str(k & 0xFF) if isinstance(k, int) else "(%s).0" % k
def khi(k): return str((k >> 8) & 0xFF) if isinstance(k, int) else "(%s).1" % k
def kadd(k, off):
    if isinstance(k, int): return (k + off) & 0xFFFF
    return k if off == 0 else "%s+%d" % (k, off)


class Var:
    """A variable at a fixed address: label, type, storage. slot = a char kept in a zero-high 2-byte slot."""
    def __init__(self, label, base, ptr, count, slot=False):
        self.label, self.base, self.ptr, self.count, self.slot = label, base, ptr, count, slot
    def size(self):                       # bytes the variable occupies
        if self.count: return self.count * sizeof(self.base, self.ptr)
        if self.ptr == 0 and self.base in STRUCTS: return STRUCTS[self.base]["size"]
        return 2 if self.slot else sizeof(self.base, self.ptr)


class Gen:
    def __init__(self, org=ORG_DEFAULT, boot=False, vector=False, brur=True, osmode=False, xisa=False, stack=0):
        self.org, self.boot, self.vector, self.brur, self.osmode, self.xisa = org, boot, vector, brur, osmode, xisa
        self.stack = stack    # --stack ADDR (2026-09-25): main runs on its own stack from ADDR down; 0 = the caller's
        self.zset = set(); self.zvars = set(); self.zframes = set(); self.zused = False; self.roots = set()
        self.code = []; self.data = []; self.bss = []
        self.globals = {}     # name -> Var
        self.frames = {}      # func -> {name: Var}
        self.params = {}      # func -> [(Var, (base, ptr))]
        self.funcs = {}       # name -> (rbase, rptr, [param types])
        self.locals = {}
        self.strings = {}
        self.used = set()
        self.labels = set()   # lower-cased labels handed out (the assembler folds case)
        self.nl = 0
        self.func = None
        self.loops = []       # (break label, continue label)
        self.reach = {}       # func -> set of functions it can reach through calls
        self.stats = {}

    # ---- labels -------------------------------------------------------------
    def label(self, want):
        s = re.sub(r"[^A-Za-z0-9_]", "_", want)
        if not s or s[0].isdigit(): s = "_" + s
        base = s[:LABEL_MAX - 5]
        cand, n = s[:LABEL_MAX], 0
        while cand.lower() in self.labels:
            n += 1; cand = "%s_%d" % (base, n)
        self.labels.add(cand.lower()); return cand
    def lbl(self, b="L"): self.nl += 1; return self.label("%s%d" % (b, self.nl))
    def emit(self, *l): self.code.extend(l)
    def ins(self, mn, args=None): self.code.append("        %s %s" % (mn, args) if args is not None else "        " + mn)
    def need(self, h): self.used.add(h)

    # ---- symbols / types ----------------------------------------------------
    def vinfo(self, name):
        if name in self.locals: return self.locals[name]
        if name in self.globals: return self.globals[name]
        sys.exit("y1cc: undeclared identifier %r (in %s)" % (name, self.func))

    def struct_member(self, tag, mname):      # -> (offset, base, ptr, count)
        if tag not in STRUCTS: sys.exit("y1cc: not a struct/union: %r" % tag)
        ms = STRUCTS[tag]["members"]
        if mname not in ms: sys.exit("y1cc: %r has no member %r" % (tag, mname))
        return ms[mname]

    def member_tag(self, e):
        if e[0] == "member": return self.typeof_lval(e[1])[0]
        return self.typeof(e[1])[0]

    BUILTIN_TYPES = {"getchar": ("int", 0), "peek": ("int", 0), "peekw": ("int", 0), "inp": ("int", 0),
                     "bios": ("int", 0), "putchar": ("void", 0), "puts": ("void", 0), "poke": ("void", 0),
                     "pokew": ("void", 0), "outp": ("void", 0), "halt": ("void", 0),
                     "call": ("int", 0), "argstr": ("char", 1), "sys": ("int", 0), "funcaddr": ("int", 0)}
    def typeof(self, e):                      # -> (base, ptr) of e's VALUE (arrays decay)
        k = e[0]
        if k == "num": return ("int", 0)
        if k in ("member", "arrow"):
            _, mb, mp, mc = self.struct_member(self.member_tag(e), e[2])
            return (mb, mp + 1) if mc else (mb, mp)
        if k == "str": return ("char", 1)
        if k == "id":
            v = self.vinfo(e[1])
            return (v.base, v.ptr + 1) if v.count else (v.base, v.ptr)
        if k == "unary":
            if e[1] == "&":
                b, p = self.typeof_lval(e[2]); return (b, p + 1)
            if e[1] == "*":
                b, p = self.typeof(e[2]); return (b, p - 1)
            return ("int", 0)
        if k == "index":
            b, p = self.typeof(e[1]); return (b, p - 1)
        if k in ("assign", "preinc", "postinc"): return self.typeof_lval(e[2] if k != "assign" else e[1])
        if k == "cond": return self.typeof(e[2])
        if k == "call":
            if e[1] in self.BUILTIN_TYPES: return self.BUILTIN_TYPES[e[1]]
            if e[1] not in self.funcs: sys.exit("y1cc: call of undeclared function %r" % e[1])
            return self.funcs[e[1]][:2]
        if k == "bin":
            if e[1] in ("+", "-"):
                lt = self.typeof(e[2]); rt = self.typeof(e[3])
                if lt[1] > 0: return lt
                if rt[1] > 0 and e[1] == "+": return rt
            return ("int", 0)
        return ("int", 0)

    def typeof_lval(self, e):                 # type as an lvalue (no array decay)
        if e[0] == "id":
            v = self.vinfo(e[1]); return (v.base, v.ptr)
        if e[0] == "unary" and e[1] == "*":
            b, p = self.typeof(e[2])
            if p < 1: sys.exit("y1cc: dereference of a non-pointer")
            return (b, p - 1)
        if e[0] == "index":
            b, p = self.typeof(e[1])
            if p < 1: sys.exit("y1cc: index of a non-pointer")
            return (b, p - 1)
        if e[0] in ("member", "arrow"):
            _, mb, mp, _ = self.struct_member(self.member_tag(e), e[2])
            return (mb, mp)
        sys.exit("y1cc: not an lvalue: %r" % (e[0],))

    def is_char(self, e):                     # e's value is a char (1-byte type)
        return self.typeof(e) == ("char", 0)

    # ---- static addresses ---------------------------------------------------
    def static_addr(self, e):
        """The assembler expression for &e when e sits at a link-time constant address, else None."""
        k = e[0]
        if k == "id": return self.vinfo(e[1]).label
        if k == "str": return self.string(e[1])
        if k == "member":
            a = self.static_addr(e[1])
            if a is None: return None
            return kadd(a, self.struct_member(self.member_tag(e), e[2])[0])
        if k == "index":
            b = e[1]; i = fold(e[2])
            if i is None: return None
            if not self.is_array(b): return None
            a = self.static_addr(b)
            if a is None: return None
            bt, bp = self.typeof(b)
            return kadd(a, i * sizeof(bt, bp - 1))
        return None

    def is_array(self, e):                    # e is an array object (not a pointer variable)
        if e[0] == "id": return self.vinfo(e[1]).count > 0
        if e[0] in ("member", "arrow"): return self.struct_member(self.member_tag(e), e[2])[3] > 0
        return False

    def static_lval(self, e):
        """(addr expr, base, ptr, slot) for a scalar lvalue at a constant address, else None."""
        if e[0] == "id":
            v = self.vinfo(e[1])
            if v.count: return None
            return (v.label, v.base, v.ptr, v.slot)
        if e[0] in ("member", "index"):
            if self.is_array(e): return None
            a = self.static_addr(e)
            if a is None: return None
            b, p = self.typeof_lval(e)
            return (a, b, p, False)
        return None

    # ---- narrow (8-bit) values ----------------------------------------------
    def is_narrow(self, e):
        """The value of e fits a byte and is available as one: char loads, small constants, byte builtins."""
        k = e[0]
        if k == "num": return 0 <= e[1] <= 255
        if k == "call": return e[1] in ("getchar", "peek", "inp", "bios") or \
            (e[1] in self.funcs and self.funcs[e[1]][:2] == ("char", 0))
        if k in ("id", "index", "member", "arrow") or (k == "unary" and e[1] == "*"):
            return self.is_char(e) and not self.is_array(e)
        if k == "cond": return self.is_narrow(e[2]) and self.is_narrow(e[3])
        if k in ("assign", "preinc", "postinc"):              # the stored (truncated) value is what R3 holds
            return self.typeof(e) == ("char", 0)
        return False
    def simple_byte(self, e):                 # loadable into ACC without touching R3/R4/TMP
        return e[0] == "num" or (e[0] in ("id", "index", "member") and self.is_char(e) and
                                 self.static_lval(e) is not None)
    def byte_src(self, e):                    # assembler operand for a static char byte
        a, b, p, slot = self.static_lval(e)
        return kadd(a, 1) if slot else a
    def gen_byte_acc(self, e):
        """ACC = the byte value of a narrow e. A simple_byte source leaves R3/R4/TMP alone; otherwise R3 (and
        whatever the expression needs) is clobbered."""
        if e[0] == "num": self.ins("LDAI", str(e[1] & 0xFF)); return
        if self.simple_byte(e): self.ins("LDA", self.byte_src(e)); return
        if e[0] == "unary" and e[1] == "*": self.gen_expr(e[2]); self.ins("LDAVR", "R3"); return   # *p
        if e[0] in ("index", "member", "arrow"): self.gen_address(e); self.ins("LDAVR", "R3"); return
        self.gen_expr(e); self.ins("MVRLA", "R3")        # calls, conditionals, assignments: low byte of R3

    # ---- loads / stores of static variables ---------------------------------
    def ldst(self, mn, reg, addr):            # LDR/STR reg,addr - LDZ/STZ reg,(addr).0 when addr is a page variable's label
        if addr in self.zset: self.ins("LDZ" if mn == "LDR" else "STZ", "%s,(%s).0" % (reg, addr))
        else: self.ins(mn, "%s,%s" % (reg, addr))
    def zreload(self):                        # --xisa: R6 = the page again, after code that is not ours ran
        if self.zused: self.ins("MVIW", "R6,zpage")
    def load_static(self, reg, addr, base, ptr, slot):
        if slot or sizeof(base, ptr) == 2: self.ldst("LDR", reg, addr); return
        if sizeof(base, ptr) != 1: sys.exit("y1cc: struct/union used as a value")
        self.ins("LDA", str(addr)); self.ins("MVARL", reg); self.ins("LDAI", "0"); self.ins("MVARH", reg)
    def store_static_r3(self, addr, base, ptr, slot, narrow):
        """memory at addr = R3 (a char slot gets its high byte zeroed unless the value is known narrow)."""
        if sizeof(base, ptr) == 2: self.ldst("STR", "R3", addr); return
        if sizeof(base, ptr) != 1: sys.exit("y1cc: whole struct/array assignment not supported")
        if slot:
            if not narrow: self.ins("LDAI", "0"); self.ins("MVARH", "R3")
            self.ldst("STR", "R3", addr)
        else:
            self.ins("MVRLA", "R3"); self.ins("STA", str(addr))

    # ---- leaves: constants and static scalars, loadable into any register ------
    def is_leaf(self, e):
        k = e[0]
        if k in ("num", "str"): return True
        if k == "id": return True
        if k == "unary" and e[1] == "&": return self.static_addr(e[2]) is not None
        if k in ("index", "member"): return self.static_addr(e) is not None
        if k in ("sizeoft", "sizeofe"): return True
        return False
    def gen_leaf(self, reg, e):               # reg (R3/R4) = value of a leaf
        k = e[0]
        if k == "num": self.ins("MVIW", "%s,%d" % (reg, e[1] & 0xFFFF)); return
        if k == "str": self.ins("MVIW", "%s,%s" % (reg, self.string(e[1]))); return
        if k in ("sizeoft", "sizeofe"): self.ins("MVIW", "%s,%d" % (reg, self.sizeof_expr(e))); return
        if k == "unary": self.ins("MVIW", "%s,%s" % (reg, kx(self.static_addr(e[2])))); return
        if self.is_array(e): self.ins("MVIW", "%s,%s" % (reg, kx(self.static_addr(e)))); return
        sl = self.static_lval(e)
        if sl is None: sys.exit("y1cc: internal: leaf %r" % (e,))
        self.load_static(reg, *sl)

    def sizeof_expr(self, e):
        if e[0] == "sizeoft": return sizeof(e[1], e[2])
        x = e[1]
        if x[0] == "id":
            v = self.vinfo(x[1]); return v.count * sizeof(v.base, v.ptr) if v.count else sizeof(v.base, v.ptr)
        if x[0] == "str": return len(x[1]) + 1
        if self.is_array(x):
            _, mb, mp, mc = self.struct_member(self.member_tag(x), x[2]); return mc * sizeof(mb, mp)
        return sizeof(*self.typeof(x))

    # ---- 16-bit operations on R3 --------------------------------------------
    def add_const(self, k):                   # R3 += k (int or label expression)
        if isinstance(k, int):
            k &= 0xFFFF
            if k == 0: return
            if k <= 3:
                for _ in range(k): self.ins("INCR", "R3")
                return
            if k >= 0xFFFD:
                for _ in range(0x10000 - k): self.ins("DECR", "R3")
                return
            if self.xisa: self.ins("ADDIW", "R3,%d" % k); return
            if k & 0xFF == 0:                 # high byte only
                self.ins("MVRHA", "R3"); self.ins("ADDI", str(k >> 8)); self.ins("MVARH", "R3"); return
        elif self.xisa: self.ins("ADDIW", "R3,%s" % k); return
        self.ins("MVRLA", "R3"); self.ins("ADDI", klo(k)); self.ins("MVARL", "R3")
        self.ins("MVRHA", "R3"); self.ins("ADDIC", khi(k)); self.ins("MVARH", "R3")
    def add_r4(self):                         # R3 += R4 (the monitor's do_add16 idiom)
        self.ins("MVRLA", "R4"); self.ins("MVAT"); self.ins("MVRLA", "R3"); self.ins("ADDT"); self.ins("MVARL", "R3")
        self.ins("MVRHA", "R4"); self.ins("MVAT"); self.ins("MVRHA", "R3"); self.ins("ADDTC"); self.ins("MVARH", "R3")
    LOGIC = {"&": "ANDT", "|": "ORT", "^": "XORT"}
    LOGICI = {"&": "ANDI", "|": "ORI", "^": "XORI"}
    def logic_r4(self, op):                   # R3 = R3 op R4
        m = self.LOGIC[op]
        self.ins("MVRLA", "R4"); self.ins("MVAT"); self.ins("MVRLA", "R3"); self.ins(m); self.ins("MVARL", "R3")
        self.ins("MVRHA", "R4"); self.ins("MVAT"); self.ins("MVRHA", "R3"); self.ins(m); self.ins("MVARH", "R3")
    def logic_const(self, op, k):             # R3 = R3 op k
        m = self.LOGICI[op]; lo, hi = k & 0xFF, (k >> 8) & 0xFF
        ident = 0xFF if op == "&" else 0x00   # the byte value that leaves a byte unchanged
        if lo != ident: self.ins("MVRLA", "R3"); self.ins(m, str(lo)); self.ins("MVARL", "R3")
        if hi != ident: self.ins("MVRHA", "R3"); self.ins(m, str(hi)); self.ins("MVARH", "R3")
    def shl1(self):                           # R3 <<= 1 (R3 += R3)
        if self.xisa: self.ins("SHL16", "R3"); return
        self.ins("MVRLA", "R3"); self.ins("MVAT"); self.ins("ADDT"); self.ins("MVARL", "R3")
        self.ins("MVRHA", "R3"); self.ins("MVAT"); self.ins("ADDTC"); self.ins("MVARH", "R3")
    def shr1(self):                           # R3 >>= 1 (carry cleared, then rotate high and low through it)
        self.ins("LDAI", "0"); self.ins("CSHL")
        self.ins("MVRHA", "R3"); self.ins("CSHR"); self.ins("MVARH", "R3")
        self.ins("MVRLA", "R3"); self.ins("CSHR"); self.ins("MVARL", "R3")
    def scale_r3(self, esz):                  # R3 *= esz (element size)
        if esz == 1: return
        if esz == 2: self.shl1(); return
        if esz == 4: self.shl1(); self.shl1(); return
        self.ins("MVIW", "R4,%d" % esz); self.need("rt_mul"); self.ins("JSR", "rt_mul")
    def push_r3(self): self.ins("PUSHR", "R3")
    def pop_r4(self): self.ins("POPR", "R4")

    # ---- addresses (lvalues): address in R3 ---------------------------------
    def gen_address(self, e):
        k = e[0]
        a = self.static_addr(e)
        if a is not None: self.ins("MVIW", "R3,%s" % kx(a)); return
        if k == "unary" and e[1] == "*": self.gen_expr(e[2]); return
        if k == "member":
            self.gen_address(e[1]); self.add_const(self.struct_member(self.member_tag(e), e[2])[0]); return
        if k == "arrow":
            self.gen_expr(e[1]); self.add_const(self.struct_member(self.member_tag(e), e[2])[0]); return
        if k == "index":
            b, i = e[1], e[2]
            bt, bp = self.typeof(b); esz = sizeof(bt, bp - 1)
            ki = fold(i)
            if ki is not None:                             # base + constant
                self.gen_expr(b); self.add_const(ki * esz); return
            self.gen_expr(i); self.scale_r3(esz)
            sa = self.static_addr(b) if self.is_array(b) else None
            if sa is not None: self.add_const(sa); return  # array: + its label
            if self.is_leaf(b): self.gen_leaf("R4", b); self.add_r4(); return
            self.push_r3(); self.gen_expr(b); self.pop_r4(); self.add_r4(); return
        sys.exit("y1cc: not an lvalue: %r" % (k,))

    def deref_r3(self, base, ptr):            # R3 = *(R3) of type (base, ptr)
        sz = sizeof(base, ptr)
        if sz == 2:
            self.ins("LDAVR", "R3"); self.ins("MVAT"); self.ins("INCR", "R3"); self.ins("LDAVR", "R3")
            self.ins("MVARL", "R3"); self.ins("MVTA"); self.ins("MVARH", "R3")
        elif sz == 1:
            self.ins("LDAVR", "R3"); self.ins("MVARL", "R3"); self.ins("LDAI", "0"); self.ins("MVARH", "R3")
        else: sys.exit("y1cc: struct/union used as a value")

    # ---- expressions: result in R3 ------------------------------------------
    def gen_expr(self, e):
        k = e[0]
        if k == "num": self.ins("MVIW", "R3,%d" % (e[1] & 0xFFFF))
        elif k == "str": self.ins("MVIW", "R3,%s" % self.string(e[1]))
        elif k in ("sizeoft", "sizeofe"): self.ins("MVIW", "R3,%d" % self.sizeof_expr(e))
        elif k == "id":
            v = self.vinfo(e[1])
            if v.count: self.ins("MVIW", "R3,%s" % v.label)      # array -> its address
            else: self.load_static("R3", v.label, v.base, v.ptr, v.slot)
        elif k == "unary":
            op = e[1]
            if op == "&": self.gen_address(e[2])
            elif op == "*": self.gen_expr(e[2]); self.deref_r3(*self.typeof_lval(e))
            elif op == "!": self.materialize(e)
            elif op == "~": self.gen_expr(e[2]); self.not_r3()
            else:
                if fold(e) is not None: self.ins("MVIW", "R3,%d" % fold(e)); return
                self.gen_expr(e[2]); self.not_r3(); self.ins("INCR", "R3")
        elif k in ("index", "member", "arrow"):
            if self.is_array(e): self.gen_address(e); return  # array member decays
            sl = self.static_lval(e)
            if sl is not None: self.load_static("R3", *sl); return
            self.gen_address(e); self.deref_r3(*self.typeof_lval(e))
        elif k == "assign": self.gen_assign(e[1], e[2], want=True)
        elif k == "cond":
            no = self.lbl("Lf"); end = self.lbl("Le")
            self.gen_cond(e[1], no, False); self.gen_expr(e[2]); self.ins("BR", end)
            self.emit("%s:" % no); self.gen_expr(e[3]); self.emit("%s:" % end)
        elif k in ("logand", "logor"): self.materialize(e)
        elif k == "bin": self.gen_bin(e[1], e[2], e[3])
        elif k == "call": self.gen_call(e[1], e[2])
        elif k == "preinc": self.gen_assign(e[2], ("bin", "+" if e[1] == "++" else "-", e[2], ("num", 1)), want=True)
        elif k == "postinc":                              # value = the OLD value; the variable gets old +- 1
            lv = e[2]; step = ("num", 1); op = "+" if e[1] == "++" else "-"
            sl = self.static_lval(lv)
            if sl is not None and sizeof(sl[1], sl[2]) == 2:   # a word at a fixed address: old kept in R4
                self.gen_expr(lv); self.ins("MOVRR", "R3,R4")
                bt, bp = self.typeof(lv); esz = sizeof(bt, bp - 1) if bp else 1
                self.add_const(esz if op == "+" else -esz)
                self.ldst("STR", "R3", sl[0]); self.ins("MOVRR", "R4,R3")
            else:
                self.gen_expr(lv); self.push_r3()
                self.gen_assign(lv, ("bin", op, lv, step), want=False)
                self.ins("POPR", "R3")
        else: sys.exit("y1cc: cannot generate expr %r" % (k,))

    def not_r3(self):                         # R3 = ~R3
        self.ins("MVRLA", "R3"); self.ins("INVA"); self.ins("MVARL", "R3")
        self.ins("MVRHA", "R3"); self.ins("INVA"); self.ins("MVARH", "R3")

    # ---- assignment ---------------------------------------------------------
    def gen_assign(self, lhs, rhs, want=True):
        b, p = self.typeof_lval(lhs); sz = sizeof(b, p)
        if sz not in (1, 2): sys.exit("y1cc: whole struct/array assignment not supported (assign members)")
        narrow = self.is_narrow(rhs)
        sl = self.static_lval(lhs)
        if sl is not None:                                 # a scalar at a fixed address
            addr = sl[0]
            if sz == 1 and not sl[3] and self.simple_byte(rhs) and not want:   # byte = byte: through ACC only
                self.gen_byte_acc(rhs); self.ins("STA", addr); return
            self.gen_expr(rhs)
            self.store_static_r3(addr, sl[1], sl[2], sl[3], narrow)
            if want and sz == 1 and not narrow: self.ins("LDAI", "0"); self.ins("MVARH", "R3")   # the value is the stored byte
            return
        # through a computed address: value in R3, address in R4 (or the other way round for a leaf value)
        if sz == 1 and self.simple_byte(rhs):              # byte store: address -> R3, byte -> ACC
            self.gen_address(lhs); self.gen_byte_acc(rhs); self.ins("STAVR", "R3")
            if want: self.ins("MVARL", "R3"); self.ins("LDAI", "0"); self.ins("MVARH", "R3")
            return
        if self.is_leaf(rhs):                              # address in R3, value in R4
            self.gen_address(lhs); self.gen_leaf("R4", rhs)
            if sz == 2:
                self.ins("MVRHA", "R4"); self.ins("STAVR", "R3"); self.ins("INCR", "R3")
                self.ins("MVRLA", "R4"); self.ins("STAVR", "R3")
            else: self.ins("MVRLA", "R4"); self.ins("STAVR", "R3")
            if want: self.ins("MOVRR", "R4,R3")
            return
        if self.simple_address(lhs):                       # value in R3, address in R4 without touching R3
            self.gen_expr(rhs); self.load_address_r4(lhs)
        else:
            self.gen_address(lhs); self.push_r3(); self.gen_expr(rhs); self.pop_r4()
        if sz == 2:
            self.ins("MVRHA", "R3"); self.ins("STAVR", "R4"); self.ins("INCR", "R4")
            self.ins("MVRLA", "R3"); self.ins("STAVR", "R4")
        else:
            self.ins("MVRLA", "R3"); self.ins("STAVR", "R4")
            if want and not narrow: self.ins("LDAI", "0"); self.ins("MVARH", "R3")

    def simple_address(self, lhs):            # &lhs is a pointer variable (+ constant), loadable into R4 directly
        if lhs[0] == "unary" and lhs[1] == "*": return lhs[2][0] == "id" and self.static_lval(lhs[2]) is not None
        if lhs[0] == "arrow": return lhs[1][0] == "id" and self.static_lval(lhs[1]) is not None
        if lhs[0] == "index":
            return fold(lhs[2]) is not None and lhs[1][0] == "id" and self.static_lval(lhs[1]) is not None
        return False
    def load_address_r4(self, lhs):           # R4 = &lhs for a simple_address lhs (uses ACC only)
        if lhs[0] == "unary": self.gen_leaf("R4", lhs[2]); return
        if lhs[0] == "arrow":
            self.gen_leaf("R4", lhs[1]); off = self.struct_member(self.member_tag(lhs), lhs[2])[0]
        else:
            bt, bp = self.typeof(lhs[1]); self.gen_leaf("R4", lhs[1]); off = fold(lhs[2]) * sizeof(bt, bp - 1)
        off &= 0xFFFF
        if off == 0: return
        if off <= 3:
            for _ in range(off): self.ins("INCR", "R4")
            return
        if self.xisa: self.ins("ADDIW", "R4,%d" % off); return
        self.ins("MVRLA", "R4"); self.ins("ADDI", str(off & 0xFF)); self.ins("MVARL", "R4")
        self.ins("MVRHA", "R4"); self.ins("ADDIC", str(off >> 8)); self.ins("MVARH", "R4")

    # ---- binary operators ---------------------------------------------------
    COMMUTATIVE = ("+", "*", "&", "|", "^", "==", "!=")
    RELOPS = ("<", ">", "<=", ">=", "==", "!=")
    def binscale(self, op, a, b):
        """Pointer arithmetic: (a, b, scale) with the pointer on the left; scale = element size of the pointer."""
        scale = 1
        if op in ("+", "-"):
            lt, rt = self.typeof(a), self.typeof(b)
            if lt[1] > 0 and rt[1] == 0: scale = sizeof(lt[0], lt[1] - 1)
            elif op == "+" and rt[1] > 0 and lt[1] == 0: a, b = b, a; scale = sizeof(rt[0], rt[1] - 1)
        return a, b, scale

    def operands(self, op, a, b):
        """Leave a in R3 and b in R4, choosing the order that avoids a push/pop when a side is a leaf."""
        if self.is_leaf(b): self.gen_expr(a); self.gen_leaf("R4", b)
        elif self.is_leaf(a) and op in self.COMMUTATIVE: self.gen_expr(b); self.gen_leaf("R4", a)
        elif self.is_leaf(a): self.gen_expr(b); self.ins("MOVRR", "R3,R4"); self.gen_leaf("R3", a)
        else: self.gen_expr(b); self.push_r3(); self.gen_expr(a); self.pop_r4()

    def gen_bin(self, op, a, b):
        c = fold(("bin", op, a, b))
        if c is not None: self.ins("MVIW", "R3,%d" % c); return
        if op in self.RELOPS: self.materialize(("bin", op, a, b)); return
        if op == "-" and self.typeof(a)[1] > 0 and self.typeof(b)[1] > 0:   # pointer - pointer = element count
            lt = self.typeof(a); esz = sizeof(lt[0], lt[1] - 1)
            self.operands(op, a, b); self.need("rt_sub"); self.ins("JSR", "rt_sub")
            if esz == 2: self.shr1()
            elif esz != 1: self.ins("MVIW", "R4,%d" % esz); self.need("rt_divmod"); self.ins("JSR", "rt_divmod")
            return
        a, b, scale = self.binscale(op, a, b)
        kb = fold(b)
        if op in ("+", "-"):
            if kb is not None:
                self.gen_expr(a); self.add_const(kb * scale if op == "+" else -(kb * scale)); return
            if scale != 1:                                 # pointer +- int: scale the int first
                self.gen_expr(b); self.scale_r3(scale)
                if op == "+":
                    if self.is_leaf(a): self.gen_leaf("R4", a); self.add_r4(); return
                    self.push_r3(); self.gen_expr(a); self.pop_r4(); self.add_r4(); return
                self.ins("MOVRR", "R3,R4")
                if self.is_leaf(a): self.gen_leaf("R3", a)
                else: self.ins("PUSHR", "R4"); self.gen_expr(a); self.pop_r4()
                self.need("rt_sub"); self.ins("JSR", "rt_sub"); return
            if op == "+" and scale == 1:
                ka = fold(a)
                if ka is not None: self.gen_expr(b); self.add_const(ka); return
            self.operands(op, a, b)
            if op == "+": self.add_r4()
            else: self.need("rt_sub"); self.ins("JSR", "rt_sub")
            return
        if op in ("&", "|", "^"):
            if kb is not None: self.gen_expr(a); self.logic_const(op, kb); return
            ka = fold(a)
            if ka is not None: self.gen_expr(b); self.logic_const(op, ka); return
            self.operands(op, a, b); self.logic_r4(op); return
        if op == "*":
            ka = fold(a)
            if kb is None and ka is not None: a, b, kb = b, a, ka
            if kb is not None:
                if kb == 0: self.gen_expr(a); self.ins("MVIW", "R3,0"); return
                if kb == 1: self.gen_expr(a); return
                if kb in (2, 4, 8):
                    self.gen_expr(a)
                    for _ in range(kb.bit_length() - 1): self.shl1()
                    return
                if kb == 256:
                    self.gen_expr(a); self.ins("MVRLA", "R3"); self.ins("MVARH", "R3"); self.ins("LDAI", "0"); self.ins("MVARL", "R3"); return
            self.operands(op, a, b); self.need("rt_mul"); self.ins("JSR", "rt_mul"); return
        if op in ("/", "%"):
            if kb is not None and kb > 0 and kb & (kb - 1) == 0:      # power of two
                sh = kb.bit_length() - 1
                self.gen_expr(a)
                if op == "%": self.logic_const("&", kb - 1); return
                if sh == 8: self.ins("MVRHA", "R3"); self.ins("MVARL", "R3"); self.ins("LDAI", "0"); self.ins("MVARH", "R3"); return
                if sh <= 3:
                    for _ in range(sh): self.shr1()
                    return
                self.ins("MVIW", "R4,%d" % sh); self.need("rt_shr"); self.ins("JSR", "rt_shr"); return
            self.operands(op, a, b); self.need("rt_divmod"); self.ins("JSR", "rt_divmod")
            if op == "%": self.ins("MOVRR", "R5,R3")
            return
        if op in ("<<", ">>"):
            if kb is not None:
                kb &= 0xFFFF
                self.gen_expr(a)
                if kb == 0: return
                if kb >= 16: self.ins("MVIW", "R3,0"); return
                if kb == 8:
                    if op == "<<": self.ins("MVRLA", "R3"); self.ins("MVARH", "R3"); self.ins("LDAI", "0"); self.ins("MVARL", "R3")
                    else: self.ins("MVRHA", "R3"); self.ins("MVARL", "R3"); self.ins("LDAI", "0"); self.ins("MVARH", "R3")
                    return
                if kb <= 3:
                    for _ in range(kb): (self.shl1 if op == "<<" else self.shr1)()
                    return
                self.ins("MVIW", "R4,%d" % kb)
            else:
                self.operands(op, a, b)
            h = "rt_shl" if op == "<<" else "rt_shr"
            self.need(h); self.ins("JSR", h); return
        sys.exit("y1cc: operator %r not supported" % op)

    # ---- conditions ---------------------------------------------------------
    def materialize(self, e):                 # a condition as a 0/1 VALUE in R3
        t = self.lbl("Lt"); end = self.lbl("Le")
        self.gen_cond(e, t, True)
        self.ins("MVIW", "R3,0"); self.ins("BR", end)
        self.emit("%s:" % t); self.ins("MVIW", "R3,1"); self.emit("%s:" % end)

    NEG = {"<": ">=", ">=": "<", ">": "<=", "<=": ">", "==": "!=", "!=": "=="}
    def branch_rel(self, rel, label, lo=None):
        """After ACC = L.hi (or L for bytes) and TMP = R.hi: jump to label when L rel R. lo: a function that
        loads the low bytes (ACC = L.lo, TMP = R.lo) for a second-level compare; None for byte operands."""
        if lo is None:
            if rel == "==": self.ins("BREQ", label)
            elif rel == "!=": self.ins("BRNEQ", label)
            elif rel == "<": self.ins("BRLT", label)
            elif rel == ">": self.ins("BRGT", label)
            else:
                skip = self.lbl("Ls")
                self.ins("BRGT" if rel == "<=" else "BRLT", skip); self.ins("BR", label); self.emit("%s:" % skip)
            return
        skip = self.lbl("Ls")
        if rel == "==": self.ins("BRNEQ", skip); lo(); self.ins("BREQ", label)
        elif rel == "!=": self.ins("BRNEQ", label); lo(); self.ins("BRNEQ", label)
        elif rel in ("<", "<="):
            self.ins("BRLT", label); self.ins("BRNEQ", skip); lo()
            if rel == "<": self.ins("BRLT", label)
            else: self.ins("BRGT", skip); self.ins("BR", label)
        else:
            self.ins("BRGT", label); self.ins("BRNEQ", skip); lo()
            if rel == ">": self.ins("BRGT", label)
            else: self.ins("BRLT", skip); self.ins("BR", label)
        self.emit("%s:" % skip)

    def gen_relcond(self, rel, a, b, label, when):
        if not when: rel = self.NEG[rel]
        ka, kb = fold(a), fold(b)
        # two bytes: one compare (ACC = a, TMP = b)
        if self.is_narrow(a) and self.is_narrow(b) and not (ka is not None and kb is not None):
            if kb is not None:
                self.gen_byte_acc(a); self.ins("LDTI", str(kb & 0xFF))
            elif self.simple_byte(b):
                self.gen_byte_acc(a); self.ins("LDT", self.byte_src(b))
            elif self.simple_byte(a):
                self.gen_byte_acc(b); self.ins("MVAT"); self.gen_byte_acc(a)
            else:
                self.gen_byte_acc(a); self.ins("PUSH"); self.gen_byte_acc(b); self.ins("MVAT"); self.ins("POP")
            self.branch_rel(rel, label); return
        # 16 bits: L in R3, R in R4 or a constant; high bytes first, low bytes only when they are equal
        if kb is None and ka is not None and rel in ("==", "!="): a, b, kb = b, a, ka
        if kb == 0 and rel in ("==", "!="):                # x == 0 / x != 0: OR the bytes, one branch
            self.gen_expr(a)
            self.ins("MVRLA", "R3"); self.ins("MVAT"); self.ins("MVRHA", "R3"); self.ins("ORT")
            self.ins("BRZ" if rel == "==" else "BRNZ", label); return
        if kb is not None:
            self.gen_expr(a)
            self.ins("MVRHA", "R3"); self.ins("LDTI", str((kb >> 8) & 0xFF))
            lo = lambda: (self.ins("MVRLA", "R3"), self.ins("LDTI", str(kb & 0xFF)))
        else:
            self.operands(rel, a, b)
            self.ins("MVRHA", "R4"); self.ins("MVAT"); self.ins("MVRHA", "R3")
            lo = lambda: (self.ins("MVRLA", "R4"), self.ins("MVAT"), self.ins("MVRLA", "R3"))
        self.branch_rel(rel, label, lo)

    def gen_cond(self, e, label, when):
        """Jump to label if (truth of e) == when, else fall through."""
        k = e[0]
        c = fold(e)
        if c is not None:
            if bool(c) == when: self.ins("BR", label)
            return
        if k == "bin" and e[1] in self.RELOPS: self.gen_relcond(e[1], e[2], e[3], label, when); return
        if k == "unary" and e[1] == "!": self.gen_cond(e[2], label, not when); return
        if k == "logand":
            if not when: self.gen_cond(e[1], label, False); self.gen_cond(e[2], label, False)
            else:
                f = self.lbl("La"); self.gen_cond(e[1], f, False); self.gen_cond(e[2], label, True); self.emit("%s:" % f)
            return
        if k == "logor":
            if when: self.gen_cond(e[1], label, True); self.gen_cond(e[2], label, True)
            else:
                t = self.lbl("Lo"); self.gen_cond(e[1], t, True); self.gen_cond(e[2], label, False); self.emit("%s:" % t)
            return
        j = "BRNZ" if when else "BRZ"
        if self.is_narrow(e):                              # a byte: load it and test
            self.gen_byte_acc(e); self.ins(j, label); return
        if k == "bin" and e[1] == "&" and fold(e[3]) is not None and fold(e[3]) <= 255:   # (x & mask8)
            self.gen_expr(e[2]); self.ins("MVRLA", "R3"); self.ins("ANDI", str(fold(e[3]))); self.ins(j, label); return
        self.gen_expr(e)
        self.ins("MVRLA", "R3"); self.ins("MVAT"); self.ins("MVRHA", "R3"); self.ins("ORT"); self.ins(j, label)

    # ---- calls --------------------------------------------------------------
    def port(self, e):
        p = fold(e)
        if p is None or not 0 <= p <= 15: sys.exit("y1cc: port must be a constant 0..15")
        return "P%X" % p
    def gen_call(self, name, args):
        if name == "putchar":
            if self.is_narrow(args[0]): self.gen_byte_acc(args[0])
            else: self.gen_expr(args[0]); self.ins("MVRLA", "R3")
            self.need("rt_putc"); self.ins("JSR", "rt_putc"); return
        if name == "getchar":
            self.need("rt_getc"); self.ins("JSR", "rt_getc")
            self.ins("MVARL", "R3"); self.ins("LDAI", "0"); self.ins("MVARH", "R3"); return
        if name == "puts":
            self.gen_expr(args[0]); self.need("rt_puts"); self.need("rt_putc"); self.ins("JSR", "rt_puts"); return
        if name == "peek":
            self.gen_expr(args[0]); self.deref_r3("char", 0); return
        if name == "peekw":
            self.gen_expr(args[0]); self.deref_r3("int", 0); return
        if name in ("poke", "pokew"):                      # memory at addr = value (byte / big-endian word)
            addr, val = args[0], args[1]
            if name == "poke" and self.simple_byte(val):
                self.gen_expr(addr); self.gen_byte_acc(val); self.ins("STAVR", "R3"); return
            if self.is_leaf(addr): self.gen_expr(val); self.gen_leaf("R4", addr)
            else: self.gen_expr(addr); self.push_r3(); self.gen_expr(val); self.pop_r4()
            if name == "pokew": self.ins("MVRHA", "R3"); self.ins("STAVR", "R4"); self.ins("INCR", "R4")
            self.ins("MVRLA", "R3"); self.ins("STAVR", "R4"); return
        if name == "inp":
            self.ins("INP", self.port(args[0])); self.ins("MVARL", "R3"); self.ins("LDAI", "0"); self.ins("MVARH", "R3"); return
        if name == "outp":                                 # always OUTA: the emulator's console (port 2) ignores OUTI
            if self.is_narrow(args[1]): self.gen_byte_acc(args[1])
            else: self.gen_expr(args[1]); self.ins("MVRLA", "R3")
            self.ins("OUTA", self.port(args[0])); return
        if name == "halt": self.ins("HALT"); return
        if name == "call":                                 # call(addr): JSRUR to a computed address; R3 = what it returns
            self.gen_expr(args[0]); self.ins("MOVRR", "R3,R7"); self.ins("JSRUR", "R7"); self.zreload(); return
        if name == "argstr":                               # the OS leaves a program's command tail at ARGBUF
            self.ins("MVIW", "R3,%d" % ARGBUF); return
        if name == "sys":                                  # sys(n, a, b, c): Y1/OS syscall n through SYSTAB (2026-09-23)
            if not 1 <= len(args) <= 4: sys.exit("y1cc: sys() takes 1 to 4 arguments (the number, then up to three)")
            n = fold(args[0])
            if n is not None and not 0 <= n <= SYSMAX: sys.exit("y1cc: sys() number must be 0..%d" % SYSMAX)
            if n is None:                                  # a computed number: its table slot's address, parked on the stack
                self.gen_expr(args[0]); self.shl1(); self.add_const(SYSTAB); self.push_r3()
            parked = []
            for i, a in enumerate(args[1:]):               # a later argument that calls anything could run a sys() itself
                hazard = any(self.calls_in(later) for later in args[i + 2:])
                self.gen_expr(a)
                if hazard: self.push_r3(); parked.append(i)
                else: self.ins("STR", "R3,%d" % (SYSARG + 2 * i))
            for i in reversed(parked): self.pop_r4(); self.ins("STR", "R4,%d" % (SYSARG + 2 * i))
            if n is not None: self.ins("LDR", "R7,%d" % ((SYSTAB if n <= SYSOLD else SYSTAB2) + 2 * n))
            else:
                self.ins("POPR", "R3"); self.ins("LDAVR", "R3"); self.ins("MVAT"); self.ins("INCR", "R3")
                self.ins("LDAVR", "R3"); self.ins("MVARL", "R7"); self.ins("MVTA"); self.ins("MVARH", "R7")
            self.ins("JSRUR", "R7"); self.zreload(); self.ins("LDR", "R3,%d" % SYSRES); return
        if name == "funcaddr":                             # funcaddr(f): the address of function f, as an int
            if len(args) != 1 or args[0][0] != "id" or args[0][1] not in self.flabel:
                sys.exit("y1cc: funcaddr() wants the name of a defined function (in %s)" % self.func)
            self.ins("MVIW", "R3,%s" % self.flabel[args[0][1]]); return
        if name == "bios":                                 # bios(addr, r7, acc) -> ACC
            addr = fold(args[0])
            if addr is None: sys.exit("y1cc: bios() address must be a constant")
            self.gen_expr(args[1]); self.ins("MOVRR", "R3,R7")
            if self.is_narrow(args[2]): self.gen_byte_acc(args[2])
            else: self.gen_expr(args[2]); self.ins("MVRLA", "R3")
            self.ins("JSR", str(addr)); self.zreload(); self.ins("MVARL", "R3"); self.ins("LDAI", "0"); self.ins("MVARH", "R3"); return
        if name not in self.funcs: sys.exit("y1cc: call of undeclared function %r" % name)
        rb, rp, ptypes = self.funcs[name]
        if len(args) != len(ptypes): sys.exit("y1cc: %s() takes %d argument(s), %d given" % (name, len(ptypes), len(args)))
        if name not in self.params: sys.exit("y1cc: %s() has no definition" % name)
        slots = self.params[name]
        rec = self.func in self.reach.get(name, ())       # a call inside a recursive cycle (the callee can reach us)
        if rec:
            for a in args:
                v = self.escapes(a)
                if v is not None:
                    sys.exit("y1cc: %s(): the address of local %r is passed to %s(), which can re-enter %s() "
                             "(a recursive function's locals live in static slots): use a global" % (self.func, v, name, self.func))
            self.frame_save(name)
        parked = []
        for i, a in enumerate(args):
            var = slots[i]
            hazard = any(self.reaches(name, later) for later in args[i + 1:])
            if rec and name == self.func and not hazard:  # a self-call: storing this argument overwrites the caller's
                pn = self.param_name(name, var)            # own parameter, which a later argument may still read
                hazard = any(self.mentions(later, pn) for later in args[i + 1:])
            self.gen_expr(a)
            if var.slot and not self.is_narrow(a): self.ins("LDAI", "0"); self.ins("MVARH", "R3")
            if hazard: self.push_r3(); parked.append(var)
            else: self.ldst("STR", "R3", var.label)
        for var in reversed(parked):
            self.pop_r4(); self.ldst("STR", "R4", var.label)
        self.ins("JSR", self.flabel[name])
        if rec: self.frame_restore(name)

    # ---- recursion: save / restore a callee's static frame around a call inside its recursive cycle ------
    FRAME_INLINE = 8                          # frames up to this many bytes are pushed word by word, inline
    def frame_block(self, f):                 # (first label, bytes) of f's slots: contiguous DS lines (compile_func)
        vs = list(self.frames[f].values())
        return (vs[0].label if vs else None), sum(v.size() for v in vs)
    def frame_save(self, f):
        """Push f's whole frame (parameters and locals) on the R1 stack. Uses R4 inline or R5-R7 in rt_fsave;
        nothing is live in a register at the start of a call sequence (every call clobbers them)."""
        lab, n = self.frame_block(f)
        if not n: return
        z = f in self.zframes                 # --xisa: the whole frame is in the page
        if n <= self.FRAME_INLINE:
            for off in range(0, n - 1, 2):
                self.ins("LDZ", "R4,(%s).0" % kadd(lab, off)) if z else self.ins("LDR", "R4,%s" % kadd(lab, off))
                self.ins("PUSHR", "R4")
            if n & 1: self.ins("LDA", kadd(lab, n - 1)); self.ins("PUSH")
            return
        self.ins("MVIW", "R5,%s" % lab); self.ins("MVIW", "R6,%d" % n); self.need("rt_fsave"); self.ins("JSR", "rt_fsave")
    def frame_restore(self, f):
        """Pop f's frame back (the reverse of frame_save). R3, the callee's result, is not touched."""
        lab, n = self.frame_block(f)
        if not n: return
        if n <= self.FRAME_INLINE:
            if n & 1: self.ins("POP"); self.ins("STA", kadd(lab, n - 1))
            for off in reversed(range(0, n - 1, 2)):
                self.ins("POPR", "R4")
                if f in self.zframes: self.ins("STZ", "R4,(%s).0" % kadd(lab, off))
                else: self.ins("STR", "R4,%s" % kadd(lab, off))
            return
        self.ins("MVIW", "R5,%s" % kadd(lab, n - 1)); self.ins("MVIW", "R6,%d" % n); self.need("rt_frest"); self.ins("JSR", "rt_frest")

    def param_name(self, f, var):             # the name under which f's parameter slot var is declared
        return next(n for n, v in self.frames[f].items() if v is var)
    def mentions(self, node, name):           # does the expression tree name the variable `name` anywhere?
        if isinstance(node, (list, tuple)):
            if len(node) == 2 and node[0] == "id": return node[1] == name
            return any(self.mentions(x, name) for x in node)
        return False

    def local_root(self, x):                  # the local variable whose storage the lvalue x lies in, or None
        if x[0] == "id": return x[1] if x[1] in self.locals else None
        if x[0] == "member": return self.local_root(x[1])
        if x[0] == "index" and self.is_array(x[1]): return self.local_root(x[1])
        return None
    def escapes(self, e):                     # a local whose ADDRESS the value of e may carry (&x, a decayed array)
        k = e[0]
        if k == "unary" and e[1] == "&": return self.local_root(e[2])
        if k in ("id", "member", "index") and self.is_array(e): return self.local_root(e)
        if k == "bin" and e[1] in ("+", "-"): return self.escapes(e[2]) or self.escapes(e[3])
        if k == "cond": return self.escapes(e[2]) or self.escapes(e[3])
        if k == "assign": return self.escapes(e[2])
        return None

    def reaches(self, callee, node):          # does evaluating node call something that can run callee?
        for c in self.calls_in(node):
            if c == callee or callee in self.reach.get(c, ()): return True
        return False
    def calls_in(self, node, acc=None):
        if acc is None: acc = set()
        if isinstance(node, (list, tuple)):
            if len(node) >= 2 and node[0] == "call" and isinstance(node[1], str): acc.add(node[1])
            for x in node: self.calls_in(x, acc)
        return acc

    def funcaddrs_in(self, node, acc=None):  # the functions whose address is taken with funcaddr(f)
        if acc is None: acc = set()
        if isinstance(node, (list, tuple)):
            if len(node) >= 3 and node[0] == "call" and node[1] == "funcaddr":
                a = node[2]
                if len(a) != 1 or a[0][0] != "id": sys.exit("y1cc: funcaddr() wants the name of a function")
                acc.add(a[0][1])
            for x in node: self.funcaddrs_in(x, acc)
        return acc

    # ---- statements ---------------------------------------------------------
    def gen_stmt(self, s):
        k = s[0]
        if k == "block":
            for st in s[1]: self.gen_stmt(st)
        elif k == "decl":
            if s[3] is not None: self.gen_assign(("id", s[2]), s[3], want=False)
        elif k == "expr":
            e = s[1]
            if e[0] == "assign": self.gen_assign(e[1], e[2], want=False)
            elif e[0] in ("preinc", "postinc"):
                self.gen_assign(e[2], ("bin", "+" if e[1] == "++" else "-", e[2], ("num", 1)), want=False)
            else: self.gen_expr(e)
        elif k == "empty": pass
        elif k == "return":
            if s[1] is not None:
                self.gen_expr(s[1])
                if self.funcs[self.func][:2] == ("char", 0) and not self.is_narrow(s[1]):
                    self.ins("LDAI", "0"); self.ins("MVARH", "R3")
            self.ret()
        elif k == "if":
            els = self.lbl("Lelse"); end = self.lbl("Lend")
            self.gen_cond(s[1], els if s[3] else end, False)
            self.gen_stmt(s[2])
            if s[3]:
                self.ins("BR", end); self.emit("%s:" % els); self.gen_stmt(s[3])
            self.emit("%s:" % end)
        elif k == "while":
            top = self.lbl("Ltop"); end = self.lbl("Lend")
            self.emit("%s:" % top); self.gen_cond(s[1], end, False)
            self.loops.append((end, top)); self.gen_stmt(s[2]); self.loops.pop()
            self.ins("BR", top); self.emit("%s:" % end)
        elif k == "for":
            init, cond, post, body = s[1], s[2], s[3], s[4]
            top = self.lbl("Ltop"); end = self.lbl("Lend"); cont = self.lbl("Lnext")
            if init is not None: self.gen_stmt(("expr", init))
            self.emit("%s:" % top)
            if cond is not None: self.gen_cond(cond, end, False)
            self.loops.append((end, cont)); self.gen_stmt(body); self.loops.pop()
            self.emit("%s:" % cont)
            if post is not None: self.gen_stmt(("expr", post))
            self.ins("BR", top); self.emit("%s:" % end)
        elif k == "break":
            if not self.loops: sys.exit("y1cc: break outside a loop or switch")
            self.ins("BR", self.loops[-1][0])
        elif k == "continue":
            cont = next((c for _, c in reversed(self.loops) if c is not None), None)
            if cont is None: sys.exit("y1cc: continue outside a loop")
            self.ins("BR", cont)
        elif k == "switch": self.gen_switch(s[1], s[2])
        elif k == "label": self.emit("%s:" % s[1])
        elif k in ("case", "default"): sys.exit("y1cc: case/default outside a switch (or nested inside a statement)")
        else: sys.exit("y1cc: cannot generate stmt %r" % (k,))

    # ---- switch: a BRUR jump table when it is smaller than the compare chain ----------------------------
    def gen_switch(self, e, body):
        """switch (e) { case k: ... default: ... }. Case labels must be direct statements of the switch block (or
        of plain nested blocks). Dispatch: the compare chain (5 bytes/case when every case fits a byte, 13
        otherwise) or, with BRUR allowed, a jump table (about 49 bytes + 2 per slot of the case range) - whichever
        is smaller. Fall-through, break and default work as in C; continue reaches the enclosing loop."""
        end = self.lbl("Lsw"); cases = []; default = None
        def relabel(block):
            out = []
            for st in block[1]:
                if st[0] == "case":
                    lab = self.lbl("Lc"); k = st[1] & 0xFFFF
                    if any(v == k for v, _ in cases): sys.exit("y1cc: duplicate case %d" % k)
                    cases.append((k, lab)); out.append(("label", lab))
                elif st[0] == "default":
                    nonlocal default
                    if default: sys.exit("y1cc: two defaults in a switch")
                    default = self.lbl("Ld"); out.append(("label", default))
                elif st[0] == "block": out.append(relabel(st))
                else: out.append(st)
            return ("block", out)
        body = relabel(body)
        miss = default or end
        self.gen_expr(e)
        if cases:
            lo, hi = min(v for v, _ in cases), max(v for v, _ in cases)
            byte_cases = hi <= 255
            chain = (3 + 5 * len(cases) + (0 if self.is_narrow(e) else 4)) if byte_cases else (13 * len(cases) + 3)
            table = 49 + 2 * (hi - lo + 1)
            if self.brur and table < chain: self.switch_table(cases, lo, hi, miss)
            elif byte_cases:
                if not self.is_narrow(e): self.ins("MVRHA", "R3"); self.ins("BRNZ", miss)
                self.ins("MVRLA", "R3")
                for v, lab in cases: self.ins("LDTI", str(v)); self.ins("BREQ", lab)
                self.ins("BR", miss)
            else:
                for v, lab in cases:
                    skip = self.lbl("Ls")
                    self.ins("MVRHA", "R3"); self.ins("LDTI", str(v >> 8)); self.ins("BRNEQ", skip)
                    self.ins("MVRLA", "R3"); self.ins("LDTI", str(v & 0xFF)); self.ins("BREQ", lab)
                    self.emit("%s:" % skip)
                self.ins("BR", miss)
        else: self.ins("BR", miss)
        self.loops.append((end, None)); self.gen_stmt(body); self.loops.pop()
        self.emit("%s:" % end)

    def switch_table(self, cases, lo, hi, miss):
        """R3 = switch value: subtract lo, range-check against the table size, index the table of addresses,
        BRUR through it. Holes in the range jump to miss (default or the end)."""
        tab = self.lbl("Lt"); n = hi - lo + 1
        self.add_const(-lo)
        self.ins("MVRHA", "R3"); self.ins("LDTI", str(n >> 8))
        self.branch_rel(">=", miss, lambda: (self.ins("MVRLA", "R3"), self.ins("LDTI", str(n & 0xFF))))
        self.shl1(); self.add_const(tab)
        self.deref_r3("int", 0)
        self.ins("BRUR", "R3")
        slots = {v: lab for v, lab in cases}
        self.data.append("%s:" % tab)
        for v in range(lo, hi + 1): self.data.append("        DW %s" % slots.get(v, miss))

    # ---- strings, data ------------------------------------------------------
    def string(self, bs):
        key = tuple(bs)
        if key not in self.strings:
            lab = self.lbl("s"); self.strings[key] = lab
            self.data.append("%s:" % lab); self.data.extend(self.db_lines(list(bs) + [0]))
        return self.strings[key]
    def db_lines(self, bs):                   # the assembler upper-cases source lines: never DB "text"
        return ["        DB " + ",".join(str(b & 0xFF) for b in bs[i:i + 16]) for i in range(0, len(bs), 16)]

    def collect_decls(self, s):
        k = s[0]
        if k == "decl": yield s
        elif k == "block":
            for st in s[1]: yield from self.collect_decls(st)
        elif k == "if":
            yield from self.collect_decls(s[2])
            if s[3]: yield from self.collect_decls(s[3])
        elif k == "while": yield from self.collect_decls(s[2])
        elif k == "for": yield from self.collect_decls(s[4])

    def layout_func(self, name, params, body):
        """Fixed slots for the parameters and every local of a function (first declaration of a name wins)."""
        frame = {}; plist = []
        self.flabel[name] = self.label("f_" + name)
        for (base, ptr, _), pnm in params:
            if ptr == 0 and base in STRUCTS: sys.exit("y1cc: struct passed by value (%s) not supported" % pnm)
            v = Var(self.label("%s_%s" % (name, pnm)), base, ptr, 0, slot=(ptr == 0 and base == "char"))
            frame[pnm] = v; plist.append(v)
        for d in self.collect_decls(body):
            (base, ptr, count), nm = d[1], d[2]
            if nm in frame: continue
            frame[nm] = Var(self.label("%s_%s" % (name, nm)), base, ptr, count, slot=(ptr == 0 and base == "char" and not count))
        self.frames[name] = frame; self.params[name] = plist

    def compile_func(self, name, params, body):
        self.func = name; self.locals = self.frames[name]; self.loops = []
        start = len(self.code)
        self.emit("%s:" % self.flabel[name])
        if name in self.roots: self.zreload()     # --xisa: main and the funcaddr() entries set the page register
        if name == "main" and self.stack:         # --stack: the caller's SP saved on the program's own stack
            self.ins("MOVRR", "R1,R5"); self.ins("MVIW", "R1,%d" % self.stack); self.ins("PUSHR", "R5")
        if name == "main": self.emit_bss_clear()
        self.gen_stmt(body)
        if name == "main" and self.stack: self.ret()      # --stack: always (dead after a final return: 4 bytes)
        if not self.code[-1].strip() == "RET": self.ins("RET")
        for v in self.locals.values(): self.bss.append("%s: DS %d" % (v.label, v.size()))
        self.stats[name] = len(self.code) - start

    def ret(self):
        """RET; in main with --stack (2026-09-25) the caller's SP comes back first (R3, the result, is kept)."""
        if self.func == "main" and self.stack:
            self.ins("POPR", "R5"); self.ins("MOVRR", "R5,R1")
        self.ins("RET")

    def emit_bss_clear(self):
        """C promises zero-initialised globals; the image carries no bytes for them (DS), and RAM powers up random
        (the microcode emulator fills it with $FF, which caught this 2026-09-22). main starts by clearing every DS
        slot (bss_start..bss_end): 20 bytes, a few thousand steps."""
        loop = self.lbl("Lz"); go = self.lbl("Lzg"); done = self.lbl("Lzd")
        self.ins("MVIW", "R3,bss_start")
        self.emit("%s:" % loop); self.ins("MVRHA", "R3"); self.ins("LDTI", "(bss_end).1"); self.ins("BRNEQ", go)
        self.ins("MVRLA", "R3"); self.ins("LDTI", "(bss_end).0"); self.ins("BREQ", done)
        self.emit("%s:" % go); self.ins("LDAI", "0"); self.ins("STAVR", "R3"); self.ins("INCR", "R3"); self.ins("BR", loop)
        self.emit("%s:" % done)
        self.labels.update(("bss_start", "bss_end"))

    def declare_global(self, base, ptr, arr, count, name, init):
        if arr and count is None:
            if init is None: sys.exit("y1cc: array %r needs a size or an initializer" % name)
            if init[0] == "initstr" and base == "char" and ptr == 0: count = len(init[1]) + 1
            elif init[0] == "initlist": count = len(init[1])
            else: sys.exit("y1cc: cannot infer the size of %r" % name)
        if name in self.globals: sys.exit("y1cc: global %r declared twice" % name)
        v = Var(self.label("g_" + name), base, ptr, count if arr else 0)
        self.globals[name] = v
        self.gvars.append((v, base, ptr, arr, count, init))
    def emit_globals(self):                   # after every global has its label (initializers may point at any)
        for v, base, ptr, arr, count, init in self.gvars:
            if init is None: self.bss.append("%s: DS %d" % (v.label, v.size())); continue
            lines = self.const_data(base, ptr, arr, count, init)
            self.data.append("%s:" % v.label); self.data.extend(lines)

    def const_data(self, base, ptr, arr, count, init):
        esz = sizeof(base, ptr); out = []
        word = lambda x: out.append("        DW %s" % x)
        def addr_of(nm):
            if nm not in self.globals: sys.exit("y1cc: initializer names unknown global %r" % nm)
            return self.globals[nm].label
        if not arr:
            if init[0] == "initstr":
                if ptr == 0: sys.exit("y1cc: string initializer for a non-pointer")
                word(self.string(init[1]))
            elif init[0] == "initaddr":
                if esz != 2: sys.exit("y1cc: address initializer for a non-pointer")
                word(addr_of(init[1]))
            elif init[0] == "initnum":
                if esz == 2: word(init[1] & 0xFFFF)
                else: out.extend(self.db_lines([init[1]]))
            else: sys.exit("y1cc: brace initializer for a scalar")
            return out
        if base == "char" and ptr == 0 and init[0] == "initstr":
            bs = list(init[1])[:count] + [0] * max(0, count - len(init[1]))
            return self.db_lines(bs[:count])
        if init[0] != "initlist": sys.exit("y1cc: array needs a brace initializer or a string")
        items = init[1]
        if len(items) > count: sys.exit("y1cc: too many initializers")
        bytes_ = []
        for it in items:
            if it[0] in ("initstr", "initaddr"):
                if esz != 2: sys.exit("y1cc: string/address initializer for a non-pointer element")
                if bytes_: out.extend(self.db_lines(bytes_)); bytes_ = []
                word(self.string(it[1]) if it[0] == "initstr" else addr_of(it[1]))
            elif it[0] == "initnum":
                if esz == 2: word(it[1] & 0xFFFF)
                else: bytes_.append(it[1])
            else: sys.exit("y1cc: nested brace initializer not supported")
        if bytes_: out.extend(self.db_lines(bytes_))
        rem = count - len(items)
        if rem: out.extend(self.db_lines([0] * (rem * esz)))   # REAL zeros in the image: DS would leave RAM as it powers up
        return out

    def register_struct(self, kind, tag, members):
        off = 0; size = 0; m = {}
        for (base, ptr, count), nm in members:
            sz = (count * sizeof(base, ptr)) if count else sizeof(base, ptr)
            m[nm] = (0 if kind == "union" else off, base, ptr, count)
            if kind == "union": size = max(size, sz)
            else: off += sz
        STRUCTS[tag] = {"size": (size if kind == "union" else off), "members": m}

    # ---- call graph: reachability (for the no-recursion rule and argument hazards) --------------
    def build_reach(self, bodies):
        direct = {f: {c for c in self.calls_in(b) if c in bodies} for f, b in bodies.items()}
        reach = {}
        for f in bodies:
            seen = set(); work = list(direct[f])
            while work:
                g = work.pop()
                if g in seen: continue
                seen.add(g); work.extend(direct.get(g, ()))
            reach[f] = seen
        self.reach = reach
        # Recursion (2026-09-24): a function that can reach itself belongs to a recursive cycle (a strongly connected
        # component of the call graph); calls INSIDE a cycle save and restore the callee's static frame (gen_call).
        # main cannot be part of one: it starts by clearing the BSS, and the boot/monitor entry calls it once.
        if "main" in reach["main"]:
            sys.exit("y1cc: main() can call itself (via %s): main cannot be recursive"
                     % ", ".join(sorted(c for c in direct["main"] if c == "main" or "main" in reach.get(c, ()))))

    def zpage_plan(self, order, bodies):
        """--xisa: which variables go into the 256-byte page that LDZ/STZ address through R6. Every 2-byte BSS variable
        (an uninitialised global, a parameter or local) is a candidate; a function in a recursive cycle is one
        candidate with its whole frame (rt_fsave/frame_save need it contiguous) when the frame is 1..256 bytes. The
        weight of a candidate = how many times its variables are named in the live functions' bodies (every ("id", x)
        of the tree, x resolved as vinfo would in that function); density = weight // its size in words. Greedy: the
        densest first (ties: the earlier in BSS order), taken if it still fits in 256 bytes. The C twin and the passes
        (cc6) compute exactly this."""
        def zsize(v):                                       # size, 0 for an unknown type (no error here: y1cc
            if v.ptr == 0 and v.base not in ("int", "char") and v.base not in STRUCTS: return 0   # reports it later)
            return v.size()
        cnt = {}
        def walk(node, f):
            if isinstance(node, (list, tuple)):
                if len(node) == 2 and node[0] == "id" and isinstance(node[1], str):
                    v = self.frames[f].get(node[1]) or self.globals.get(node[1])
                    if v is not None: cnt[id(v)] = cnt.get(id(v), 0) + 1
                    return
                for x in node: walk(x, f)
        for f in order: walk(bodies[f], f)
        units = []                                          # (function or None, [vars]) in BSS order
        for v, base, ptr, arr, count, init in self.gvars:
            if init is None and zsize(v) == 2: units.append((None, [v]))
        for f in order:
            vs = list(self.frames[f].values())
            if f in self.reach.get(f, ()):
                n = 0; bad = False                          # (a variable of unknown size keeps the frame out)
                for v in vs:
                    n += zsize(v); bad = bad or zsize(v) == 0
                    if n > 256: break
                if 0 < n <= 256 and not bad: units.append((f, vs))
            else: units.extend((None, [v]) for v in vs if zsize(v) == 2)
        info = []
        for f, vs in units:
            size = sum(zsize(v) for v in vs); w = sum(cnt.get(id(v), 0) for v in vs) & 0xFFFF
            info.append((size, w, w // ((size + 1) // 2)))
        done = [False] * len(units); used = 0
        while True:
            best = -1
            for i, (size, w, d) in enumerate(info):
                if not done[i] and w and (best < 0 or d > info[best][2]): best = i
            if best < 0: break
            done[best] = True
            if used + info[best][0] <= 256:
                used += info[best][0]; f, vs = units[best]
                if f is not None: self.zframes.add(f)
                for v in vs: self.zvars.add(id(v)); self.zset.add(v.label)
        self.zused = bool(self.zvars)

    def gen_program(self, decls, src_name):
        STRUCTS.clear(); self.flabel = {}
        for d in decls:
            if d[0] == "structdef": self.register_struct(d[1], d[2], d[3])
        for d in decls:
            if d[0] in ("func", "proto"): self.funcs[d[2]] = (d[1][0], d[1][1], [p[0] for p in d[3]])
        self.gvars = []
        for d in decls:
            if d[0] == "gvar": self.declare_global(*d[1:])
        self.emit_globals()
        bodies = {d[2]: d[4] for d in decls if d[0] == "func"}
        if "main" not in bodies: sys.exit("y1cc: no main()")
        self.build_reach(bodies)
        roots = {"main"}                  # a function named in funcaddr() is an entry point too (the OS's syscall
        for b in bodies.values():         # handlers, reached by JSRUR through SYSTAB): keep it and what it reaches
            for f in self.funcaddrs_in(b):
                if f not in bodies: sys.exit("y1cc: funcaddr(%s): no such function" % f)
                roots.add(f)
        live = set(roots)
        for r in roots: live |= self.reach[r]
        order = ["main"] + [d[2] for d in decls if d[0] == "func" and d[2] != "main" and d[2] in live]
        for d in decls:
            if d[0] == "func" and d[2] in live: self.layout_func(d[2], d[3], d[4])
        self.roots = roots
        if self.xisa: self.zpage_plan(order, bodies)
        # Image layout: main first, so the monitor's `G AAAA` (JSRUR R7 since the 2026-09-22 monitor: a call)
        # enters it directly and its RET returns to the command loop. --vector emits the layout for the
        # monitor as burned in 2021, whose G was `BRVR R7` = an indirect jump through the word AT the address
        # (PC <- [AAAA], docs/isa/steps.txt) that pushes no return address: a 2-byte vector, then a stub that
        # calls main and restarts the monitor with BR $F000.
        self.emit("; y1cc: %s  (%s)" % (src_name, time.strftime("%Y-%m-%d %H:%M")),
                  "; R3 = expression accumulator, R4 = operand, R5-R7 runtime scratch, R2 never used (hardware IR)",
                  "        ORG %d" % self.org)
        if self.vector:
            self.emit("        DW start                ; vector for the 2021 monitor's G command (BRVR = PC <- [org])",
                      "start:  JSR %s" % self.flabel["main"],
                      "        BR %d                 ; back to the monitor (restart)" % MONITOR_RESTART)
        fdefs = {d[2]: d for d in decls if d[0] == "func"}
        for name in order:
            d = fdefs[name]; self.compile_func(name, d[3], d[4])
        dropped = [d[2] for d in decls if d[0] == "func" and d[2] not in live]
        for n in dropped: self.emit("; dropped (never called): %s" % n)
        self.code = self.peephole(self.code)
        self.emit_runtime()
        self.code.extend(self.data)
        # --xisa: the page first in the BSS, aligned to 256 bytes by zpad (the assembler resolves zpad in pass 1); the
        # padding sits before bss_start, so main's BSS clear does not spend time on it
        if self.zused: self.emit("zpad: DS (256-(zpad).0)&255")
        self.emit("bss_start:")
        if self.zused:
            self.emit("zpage:")
            self.code.extend(l for l in self.bss if l.split(":")[0] in self.zset)       # the page's variables, BSS order
        self.code.extend(l for l in self.bss if l.split(":")[0] not in self.zset)
        self.emit("bss_end: DS 1")       # a byte so the label is a real address even for an empty BSS
        if self.boot:
            # The first BR is what the monitor does too: after reset the memory card's FORCE-ROM maps every fetch into
            # $F000-$FFFF until an address with A15 high is presented; a branch to $F003 presents one. Without it
            # `JSR main` would land in the ROM window (seen on the microcode emulator 2026-09-22).
            self.emit("; boot stub for `emulator -x -f prog.img` / `y1ucemu -x -m -f prog.img`: release FORCE-ROM, stack, main, HALT",
                      "        ORG %d" % 0xF000, "        BR %d" % 0xF003, "        MVIW R1,%d" % STACK_TOP,
                      "        JSR %s" % self.flabel["main"], "        HALT", "        END %d" % 0xF000)
        else:
            self.emit("        END %d" % self.org)

    # ---- peephole -----------------------------------------------------------
    def peephole(self, code):
        def ins(l): return l.startswith("        ")
        def parts(l): s = l.strip().split(None, 1); return (s[0], s[1] if len(s) > 1 else "")
        changed = True
        while changed:
            changed = False; out = []; i = 0
            while i < len(code):
                a = code[i]; b = code[i + 1] if i + 1 < len(code) else None
                if b is not None and ins(a):
                    ma, aa = parts(a)
                    if ins(b):
                        mb, ab = parts(b)
                        if (ma, mb) in (("STR", "LDR"), ("STZ", "LDZ")) and aa == ab and aa.startswith("R3,"):
                            out.append(a); i += 2; changed = True; continue      # store then reload: drop the reload
                        if ((ma in ("STR", "LDR") and mb == "LDR") or (ma in ("STZ", "LDZ") and mb == "LDZ")) and \
                                aa.startswith("R3,") and ab == "R4," + aa[3:]:
                            out.append(a); out.append("        MOVRR R3,R4"); i += 2; changed = True; continue
                        if ma == "MOVRR" and mb == "MOVRR" and aa == "R3,R4" and ab == "R4,R3":
                            out.append(a); i += 2; changed = True; continue
                    elif ma == "BR" and b.strip().startswith(aa + ":"):
                        i += 1; changed = True; continue                             # jump to the next line
                out.append(a); i += 1
            code = out
        return code

    # ---- runtime ------------------------------------------------------------
    def emit_runtime(self):
        R = {}
        # R3 = R3 - R4 as R3 + ~R4 + 1; R4 is clobbered (its bytes are complemented in place so that nothing but
        # register moves sits between the two ADDTC, the idiom the hardware has proved).
        R["rt_sub"] = ["rt_sub: MVRHA R4", "        INVA", "        MVARH R4", "        MVRLA R4", "        INVA",
                       "        MVAT", "        LDAI 255", "        ADDI 1",        # carry = 1
                       "        MVRLA R3", "        ADDTC", "        MVARL R3", "        MVRHA R4", "        MVAT",
                       "        MVRHA R3", "        ADDTC", "        MVARH R3", "        RET"]
        # R3 = R3 * R4 (low 16 bits): shift-and-add, R5 accumulates, R4 is consumed bit by bit
        R["rt_mul"] = ["rt_mul: MVIW R5,0",
                       "rt_mul_l: MVRLA R4", "        MVAT", "        MVRHA R4", "        ORT", "        BRZ rt_mul_d",
                       "        MVRLA R4", "        ANDI 1", "        BRZ rt_mul_s",
                       "        MVRLA R3", "        MVAT", "        MVRLA R5", "        ADDT", "        MVARL R5",
                       "        MVRHA R3", "        MVAT", "        MVRHA R5", "        ADDTC", "        MVARH R5",
                       "rt_mul_s: MVRLA R3", "        MVAT", "        ADDT", "        MVARL R3",
                       "        MVRHA R3", "        MVAT", "        ADDTC", "        MVARH R3",
                       "        LDAI 0", "        CSHL", "        MVRHA R4", "        CSHR", "        MVARH R4",
                       "        MVRLA R4", "        CSHR", "        MVARL R4", "        BR rt_mul_l",
                       "rt_mul_d: MOVRR R5,R3", "        RET"]
        # R3 = R3 / R4, R5 = R3 % R4 (unsigned, restoring division; R6 = remainder, R7 = bit counter).
        # The low byte's borrow is detected with the comparator (SUB's borrow is not portable between the
        # emulator and the hardware), then applied to the high byte with SUBI 1.
        R["rt_divmod"] = ["rt_divmod: MVIW R6,0", "        MVIW R7,16",
                          "rt_dm_l: MVRLA R3", "        MVAT", "        ADDT", "        MVARL R3",
                          "        MVRHA R3", "        MVAT", "        ADDTC", "        MVARH R3",
                          "        MVRLA R6", "        MVAT", "        ADDTC", "        MVARL R6",
                          "        MVRHA R6", "        MVAT", "        ADDTC", "        MVARH R6",
                          "        MVRHA R4", "        MVAT", "        MVRHA R6",
                          "        BRLT rt_dm_n", "        BRNEQ rt_dm_y",
                          "        MVRLA R4", "        MVAT", "        MVRLA R6", "        BRLT rt_dm_n",
                          "rt_dm_y: MVRLA R4", "        MVAT", "        MVRLA R6", "        BRLT rt_dm_b",
                          "        SUBT", "        MVARL R6", "        MVRHA R4", "        MVAT", "        MVRHA R6",
                          "        SUBT", "        MVARH R6", "        INCR R3", "        BR rt_dm_n",
                          "rt_dm_b: SUBT", "        MVARL R6", "        MVRHA R4", "        MVAT", "        MVRHA R6",
                          "        SUBT", "        SUBI 1", "        MVARH R6", "        INCR R3",
                          "rt_dm_n: DECR R7", "        MVRLA R7", "        BRNZ rt_dm_l",
                          "        MOVRR R6,R5", "        RET"]
        R["rt_shl"] = ["rt_shl: MVRLA R4", "        BRZ rt_shl_d",
                       "rt_shl_l: MVRLA R3", "        MVAT", "        ADDT", "        MVARL R3",
                       "        MVRHA R3", "        MVAT", "        ADDTC", "        MVARH R3",
                       "        DECR R4", "        MVRLA R4", "        BRNZ rt_shl_l", "rt_shl_d: RET"]
        R["rt_shr"] = ["rt_shr: MVRLA R4", "        BRZ rt_shr_d",
                       "rt_shr_l: LDAI 0", "        CSHL", "        MVRHA R3", "        CSHR", "        MVARH R3",
                       "        MVRLA R3", "        CSHR", "        MVARL R3",
                       "        DECR R4", "        MVRLA R4", "        BRNZ rt_shr_l", "rt_shr_d: RET"]
        # console: BRDEV does not branch on the emulator (port 2 = the terminal) and always branches on the
        # machine (the monitor's BIOS charout / uartin vectors drive the UART)
        R["rt_putc"] = ["rt_putc: BRDEV rt_putc_h", "        OUTA P2", "        RET",
                        "rt_putc_h: JSR %d" % BIOS_CHAROUT, "        RET"]
        R["rt_getc"] = ["rt_getc: BRDEV rt_getc_h", "        INP P2", "        RET",
                        "rt_getc_h: JSR %d" % BIOS_UARTIN, "        RET"]
        if self.osmode:
            # --os (2026-09-23): the console goes through Y1/OS, so the shell can redirect it (> file, pipes).
            # putchar = syscall CONOUT (19): the byte -> SYSARG0 as a big-endian word (high byte 0), JSRUR the word at
            # SYSTAB+38. getchar = syscall CONIN (17), the byte from SYSRES; CONIN's 65535 (end of input: Ctrl-D, NUL,
            # the end of a < file) becomes 0, the end-of-input byte getchar returns on the emulator (INP P2).
            # R3 and R4 survive both (rt_puts walks its string in R3; compiled code keeps nothing else in a
            # register across a call); the OS handler is compiled code and clobbers R5-R7, ACC, TMP.
            R["rt_putc"] = ["rt_putc: PUSHR R3", "        PUSHR R4", "        MVARL R3", "        LDAI 0",
                            "        MVARH R3", "        STR R3,%d" % SYSARG, "        LDR R7,%d" % (SYSTAB + 2 * SYS_CONOUT),
                            "        JSRUR R7", "        POPR R4", "        POPR R3", "        RET"]
            R["rt_getc"] = ["rt_getc: PUSHR R3", "        PUSHR R4", "        LDR R7,%d" % (SYSTAB + 2 * SYS_CONIN),
                            "        JSRUR R7", "        LDR R5,%d" % SYSRES, "        POPR R4", "        POPR R3",
                            "        MVRHA R5", "        BRNZ rt_getc_e", "        MVRLA R5", "        RET",
                            "rt_getc_e: LDAI 0", "        RET"]
        R["rt_puts"] = ["rt_puts: LDAVR R3", "        BRZ rt_puts_d", "        JSR rt_putc", "        INCR R3",
                        "        BR rt_puts", "rt_puts_d: LDAI 10", "        JSR rt_putc", "        RET"]
        # recursion (2026-09-24): push / pop a static frame of R6 bytes (R6 > 0) under the return address.
        # rt_fsave: R5 = the frame's first byte, pushed first; rt_frest: R5 = its LAST byte, popped first.
        # Both keep R3 (the callee's result) and R4; they use R5-R7, ACC and TMP, and no carry.
        R["rt_fsave"] = ["rt_fsave: POPR R7", "rt_fsave_l: LDAVR R5", "        PUSH", "        INCR R5", "        DECR R6",
                         "        MVRLA R6", "        MVAT", "        MVRHA R6", "        ORT", "        BRNZ rt_fsave_l",
                         "        PUSHR R7", "        RET"]
        R["rt_frest"] = ["rt_frest: POPR R7", "rt_frest_l: POP", "        STAVR R5", "        DECR R5", "        DECR R6",
                         "        MVRLA R6", "        MVAT", "        MVRHA R6", "        ORT", "        BRNZ rt_frest_l",
                         "        PUSHR R7", "        RET"]
        if self.xisa:
            # --xisa (2026-09-24): SHL16 for the doublings whose carry nothing reads; rt_divmod keeps its remainder in
            # R5 (R6 is the page register); code that leaves compiled code reloads R6 afterwards (when the page is used)
            m = R["rt_mul"]; i = m.index("rt_mul_s: MVRLA R3"); R["rt_mul"] = m[:i] + ["rt_mul_s: SHL16 R3"] + m[i + 8:]
            R["rt_shl"] = ["rt_shl: MVRLA R4", "        BRZ rt_shl_d", "rt_shl_l: SHL16 R3",
                           "        DECR R4", "        MVRLA R4", "        BRNZ rt_shl_l", "rt_shl_d: RET"]
            R["rt_divmod"] = [l.replace("R6", "R5") for l in R["rt_divmod"] if l != "        MOVRR R6,R5"]
            if self.zused:
                z = "        MVIW R6,zpage"
                for h in ("rt_putc", "rt_getc"):
                    j = next(i for i, l in enumerate(R[h]) if "JSRUR R7" in l or l.endswith(": JSR %d" % (BIOS_CHAROUT if h == "rt_putc" else BIOS_UARTIN)))
                    R[h].insert(j + 1, z)
                for h in ("rt_fsave", "rt_frest"): R[h].insert(len(R[h]) - 2, z)
        for h in ["rt_sub", "rt_mul", "rt_divmod", "rt_shl", "rt_shr", "rt_putc", "rt_getc", "rt_puts", "rt_fsave", "rt_frest"]:
            if h in self.used:
                self.emit("; runtime " + h); self.emit(*R[h])


def compile_src(src, path, org=ORG_DEFAULT, boot=False, vector=False, brur=True, osmode=False, xisa=False, stack=0):
    g = Gen(org, boot, vector, brur, osmode, xisa, stack)
    g.gen_program(P(lex(src, path)).program(), os.path.basename(path))
    return "\n".join(g.code) + "\n", g


def main():
    a = sys.argv[1:]
    if not a or a[0].startswith("-"): sys.exit(__doc__.split("Usage:")[1].strip())
    src = a[0]; out = os.path.splitext(src)[0] + ".asm"; org = ORG_DEFAULT; boot = False
    if "-o" in a: out = a[a.index("-o") + 1]
    if "--org" in a: org = int(a[a.index("--org") + 1], 0)
    if "--boot" in a: boot = True
    stack = 0
    if "--stack" in a:
        i = a.index("--stack")
        if i + 1 >= len(a): sys.exit("y1cc: --stack needs an address")
        try: stack = int(a[i + 1], 0) & 0xFFFF
        except ValueError: sys.exit("y1cc: --stack: not a number")
        if not stack: sys.exit("y1cc: --stack: not a number")
    text, g = compile_src(open(src).read(), src, org, boot, "--vector" in a, "--no-brur" not in a, "--os" in a, "--xisa" in a,
                          stack)
    open(out, "w").write(text)
    if "-l" in a:
        print("y1cc: %s -> %s: %d lines; functions: %s" % (src, out, len(text.splitlines()),
              ", ".join("%s %d" % kv for kv in g.stats.items())))


if __name__ == "__main__":
    main()
