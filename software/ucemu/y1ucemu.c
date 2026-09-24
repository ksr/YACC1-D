/*
 * y1ucemu.c - a microcode-level emulator of the YACC1 (2026-09-22).
 *
 * The other emulator (software/emulator) interprets instructions: it knows what ADDI does. This one does not. It
 * loads the same control-store image the sequencer card holds (firmware/microcode/ucode-generator2/test.hex,
 * 256 opcodes x 64 steps x 64 control bits) and steps the same control words the hardware does, driving a model of
 * the cards on the bus: the sequencer (step counter, instruction/operand/branch registers, branch-taken latch,
 * pipeline), two register cards (R0-R7 as 74LS192 counters with byte-lane read buffers and the swap transceiver),
 * the ALU card (function blocks, accumulator, carry and shift-out flip-flops, 74LS194 shifter, the branch-condition
 * mux), the memory card (RAM/EEPROM with the FORCE-ROM boot remap, TMP0/TMP1) and the I/O card (control latch on P0,
 * data on P1: a 16550 UART, switches/LEDs). ADDI happens because record $B0 says so. The model is the one
 * established in docs/isa/MICROCODE-REVIEW-NOTES.md section 1 (which latch acts on which edge, what drives the
 * 16-bit data bus, what -REG-FUNC-RD alone does), so it reproduces the hardware's quirks: R2 is the operand-address
 * register of LDA/STA/LDR/STR, BRVR is an indirect jump, BRDEV always branches, SUB and every shift load the carry
 * flip-flop, loads of R0 are gated by the branch-taken latch, and every step where two sources drive a data lane
 * with different values is a BUS FIGHT that is counted and can be listed (-w).
 *
 * Timing: a step is two clock periods (the one carrying UCODE-COUNT-RESET lasts one). Leading-edge latches (IR,
 * operand, branch and INT vector registers, TMP0/1, accumulator, shift register) take the bus and function-block
 * values as they were at the end of the PREVIOUS step; trailing-edge actions (memory and I/O writes, register loads,
 * register counts) use the values at the end of the step that asserts the strobe. A count on -REG-UP/-REG-DN
 * happens when the strobe goes away or the selection changes (the OR with the register select on the card).
 *
 * usage: y1ucemu [-u test.hex] [-m] [-f image.hex ...] [-c disk.img] [-x] [-t] [-T] [-w] [-F and|src] [-s NN] [-l N]
 *   -c   attach a CompactFlash image (software/cfmodel.h: P4 = register select, P5 = data; created if missing)
 *   -u   control store (default: firmware/microcode/ucode-generator2/test.hex relative to the executable)
 *   -m   load firmware/basic/basic.img + firmware/monitor/monitor.img (the ROM), as the other emulator does
 *   -f   load an Intel-hex image (repeatable; later files overwrite earlier ones)
 *   -x   scripted: quiet, stdout flushed, SOFT-HALT exits; a status line on stderr
 *   -t   one line per instruction fetch on stderr; -T every step with the signals asserted
 *   -w   list bus fights (opcode, step, the drivers) as they first occur; the summary is always printed with -x
 *   -F   how a bus fight resolves: "and" (default) = a low output wins, the lane is the AND of its drivers (the
 *        usual TTL outcome, and what makes review finding H-2 fatal: a taken BRZ lands on offset $00); "src" = the
 *        ALU's -AC-RD drive loses to any other driver (what the hardware must be doing if the monitor ever ran)
 *   -s   the byte the I/O card's switches read as (default 0); -i 0|1 the level of the input-switch line that
 *        BRINH/BRINL test (default 0), -R 1|2 the index-register cards fitted (default 2; with 1, R4..R7 are absent:
 *        a read of them leaves the bus to its pull-ups = $FF, loads and counts are lost, as on the 2026-09-22 bench),
 *        -E ADDR (hex) stops the run when an instruction is fetched from ADDR (e.g. the monitor's `stop` loop);
 *        -I N flips that line every N steps (a bench hand on the switch); -L report writes to the LED board, the TIL311 displays and the ON/OFF LED on
 *        stderr as they change; -l N stop after N steps
 * Console: the I/O card's UART (P0 = UARTCS|register, P1 = data) is stdin/stdout, as on the machine; reading with
 * nothing left returns 0 with "data ready" set so a program's EOF test sees 0. Port 2 is also a console (the old
 * emulator's shortcut), so hand-written programs that OUTA P2 still print.
 * Reset is the real one: registers and IR cleared, FORCE-ROM set, so the first fetch at $0000 reads ROM[$F000].
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>
#include <poll.h>
#include <libgen.h>
#include <termios.h>
#ifdef __APPLE__
#include <mach-o/dyld.h>
#endif

struct signal { char *name; int chip; int port; int bit; };
#include "../../firmware/microcode/yaccsignaldata2.h"
#include "../cfmodel.h"          /* the CompactFlash card on ports P4 (select) / P5 (data), -c image */

/* ---- control store ------------------------------------------------------------------------------------------ */
static uint8_t ucode[256][64][8];
static int have_record[256];

static int sig_byte[128], sig_bit[128], sig_low[128], nsig;
static int S(const char *name) {            /* index of a signal by name, resolved once */
    for (int i = 0; i < nsig; i++) if (strcmp(signals[i].name, name) == 0) return i;
    fprintf(stderr, "y1ucemu: no signal %s in the table\n", name); exit(2);
}
static int s_reg_func_rd, s_reg_func_ld, s_rd_id[4], s_ld_id[4], s_reg_rd_lo, s_reg_ld_lo, s_reg_rd_hi, s_reg_ld_hi,
    s_reg_dn, s_reg_up, s_mem_rd, s_mem_wr, s_io_rd, s_io_wr, s_tmp_rd0, s_tmp_ld0, s_tmp_rd1, s_tmp_ld1, s_addr_id[4],
    s_ioaddr[4], s_vma, s_alu_func, s_alu[4], s_ac_ld_inv, s_ac_rd, s_ac_ld, s_sr_ld, s_br_test, s_hl_swap, s_soft_halt,
    s_out_off, s_out_on, s_int_ld_hi, s_int_start, s_int_en, s_ld_ins_reg, s_count_reset, s_operand_clk, s_branch_rd,
    s_branch_ld_lo, s_branch_ld_hi, s_int_jmp, s_int_ld_lo, s_two_byte;

static void resolve_signals(void) {
    for (nsig = 0; signals[nsig].name && signals[nsig].name[0]; nsig++) {
        sig_byte[nsig] = (signals[nsig].chip - 1) * 2 + signals[nsig].port;
        sig_bit[nsig] = signals[nsig].bit;
        sig_low[nsig] = signals[nsig].name[0] == '-';
    }
    s_reg_func_rd = S("-REG-FUNC-RD"); s_reg_func_ld = S("-REG-FUNC-LD");
    for (int i = 0; i < 4; i++) {
        char b[24];
        sprintf(b, "REG-RD-ID%d", i); s_rd_id[i] = S(b);
        sprintf(b, "REG-LD-ID%d", i); s_ld_id[i] = S(b);
        sprintf(b, "ADDR-REG-ID%d", i); s_addr_id[i] = S(b);
        sprintf(b, "IOADDR%d", i); s_ioaddr[i] = S(b);
        sprintf(b, "ALU%d", i); s_alu[i] = S(b);
    }
    s_reg_rd_lo = S("-REG-RD-LO"); s_reg_ld_lo = S("REG-LD-LO"); s_reg_rd_hi = S("-REG-RD-HI"); s_reg_ld_hi = S("REG-LD-HI");
    s_reg_dn = S("-REG-DN"); s_reg_up = S("-REG-UP");
    s_mem_rd = S("-MEM-RD"); s_mem_wr = S("-MEM-WR"); s_io_rd = S("-IO-RD"); s_io_wr = S("-IO-WR");
    s_tmp_rd0 = S("-TMP-REG-RD0"); s_tmp_ld0 = S("-TMP-REG-LD0"); s_tmp_rd1 = S("-TMP-REG-RD1"); s_tmp_ld1 = S("-TMP-REG-LD1");
    s_vma = S("-VMA"); s_alu_func = S("-ALU-FUNC"); s_ac_ld_inv = S("-AC-LD-INV"); s_ac_rd = S("-AC-RD"); s_ac_ld = S("-AC-LD");
    s_sr_ld = S("-SR-LD"); s_br_test = S("BR-TEST"); s_hl_swap = S("-HL-SWAP"); s_soft_halt = S("SOFT-HALT");
    s_out_off = S("OUT-OFF"); s_out_on = S("OUT-ON"); s_int_ld_hi = S("INT-LD-HI"); s_int_start = S("INT-START");
    s_int_en = S("INT-EN"); s_ld_ins_reg = S("LD-INS-REG"); s_count_reset = S("UCODE-COUNT-RESET");
    s_operand_clk = S("OPERAND-CLK"); s_branch_rd = S("-BRANCH-RD"); s_branch_ld_lo = S("BRANCH-LD-LO");
    s_branch_ld_hi = S("BRANCH-LD-HI"); s_int_jmp = S("-INT-JMP"); s_int_ld_lo = S("INT-LD-LO"); s_two_byte = S("-2-BYTE-OPERAND-SEL");
}

static int on(const uint8_t *w, int s) {   /* is signal s asserted in control word w? */
    int v = (w[sig_byte[s]] >> sig_bit[s]) & 1;
    return sig_low[s] ? !v : v;
}
static int field(const uint8_t *w, int *s4) {
    int v = 0;
    for (int i = 0; i < 4; i++) v |= ((w[sig_byte[s4[i]]] >> sig_bit[s4[i]]) & 1) << i;
    return v;
}

static int load_ucode(const char *path) {
    FILE *f = fopen(path, "r");
    if (!f) { fprintf(stderr, "y1ucemu: cannot open control store %s\n", path); return 0; }
    fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
    char *buf = malloc(n + 1); if (fread(buf, 1, n, f) != (size_t)n) { fclose(f); return 0; }
    buf[n] = 0; fclose(f);
    int recs = 0;
    for (char *tok = strchr(buf, '%'); tok; tok = strchr(tok + 1, '%')) {          /* %LLOO<1024 hex>Z or ! */
        char *p = tok + 1;
        if (strlen(p) < 4) break;
        int op = (int)strtol((char[]){p[2], p[3], 0}, NULL, 16);
        p += 4;
        for (int i = 0; i < 512 && p[0] && p[1] && p[0] != 'Z' && p[0] != '!' && p[0] != '%'; i++, p += 2)
            ucode[op][i / 8][i % 8] = (uint8_t)strtol((char[]){p[0], p[1], 0}, NULL, 16);
        have_record[op] = 1; recs++;
    }
    free(buf);
    return recs;
}

/* ---- opcode names (for traces and the fight report) --------------------------------------------------------- */
static const char *opname[256];
static void load_opnames(const char *exe_dir) {
    static char names[256][16];
    char path[4096]; snprintf(path, sizeof path, "%s/../../firmware/opcodes.h", exe_dir);
    FILE *f = fopen(path, "r"); if (!f) return;
    char line[256];
    while (fgets(line, sizeof line, f)) {
        char nm[64]; unsigned v;
        if (sscanf(line, " #define %63s 0%*[xX]%x", nm, &v) == 2 && v < 256 && strncmp(nm, "OPCODE_", 7) && !opname[v]) {
            strncpy(names[v], nm, 15); opname[v] = names[v];
        }
    }
    fclose(f);
    for (int b = 0; b < 256; b++) if (!opname[b] && (b & 7) && opname[b & ~7]) {   /* Rn families */
        strncpy(names[b], opname[b & ~7], 15); opname[b] = names[b];
    }
    for (int b = 0; b < 256; b++) if (!opname[b] && (b & 15) && opname[b & ~15] && (b & 0xF0) >= 0x60 && (b & 0xF0) <= 0x90) {
        strncpy(names[b], opname[b & ~15], 15); opname[b] = names[b];              /* Pn families */
    }
}

/* ---- machine state ------------------------------------------------------------------------------------------ */
static uint8_t mem[65536];
static uint16_t reg[8];
static int reg_cards = 2;                          /* -R: card 0 = R0..R3, card 1 = R4..R7 */
#define REG_PRESENT(r) (((r) >> 2) < reg_cards)
static uint8_t acc, sreg, ir, operand;
static uint16_t tmp0, tmp1, branch, intvec;
static int carry, shift_out, cond_latch, force_rom = 1, out_led, in_line, int_enabled, int_pending, halted;
static int step;
static uint8_t port[16];
static int switches, show_leds, stale_so = 1;   /* 2026-09-23: the ALU as built (CO/BO OR SHIFT-OUT); -K = the old model */ static long exit_pc = -1; static unsigned long in_flip;

/* the combinational state of a step (what the latches see at the next leading edge) */
struct comb {
    uint16_t addr; uint16_t data; int data_lo_driven, data_hi_driven;
    uint16_t adata; int adata_valid;             /* the register card's internal bus */
    uint8_t inv_in; uint8_t ac_input; int co_bo; int fn_addsub, fn_shift; int br_cond;
    int rd_id, ld_id, alu;
};
static struct comb prev, cur;

/* ---- I/O card ----------------------------------------------------------------------------------------------- */
static int scripted, trace, trace_steps, warn_fights, fight_src;
static int io_rd_hold = -1;     /* an I/O read is sampled once, at the leading edge of -IO-RD, and held while it stays asserted */
static uint8_t uart_lcr, uart_ier, uart_fcr, uart_mcr, uart_scr, uart_dll, uart_dlm;
static int in_buf = -1;   /* one byte of look-ahead from stdin, -1 = none */
static int in_eof;

/* 2026-09-23: the UART's data-ready bit (LSR) is a NON-blocking poll. It used to call a blocking read(), so every
   LSR read - including the transmit-empty check before each output character - stalled the emulator until the next
   input byte arrived: invisible with a scripted input file (all input present, then end of input), but a live
   sender (tools/monload.py through a pty, tests/monload) saw no answer until it sent more. The data read (RBR, port
   2) still blocks. After a long run of empty polls with no output either, each poll waits 1 ms, so a monitor idling
   at its prompt does not spin the host CPU; any input or output resets that. */
static long idle_polls;
static int stdin_fill(int wait_ms) {              /* try to buffer one byte; 1 = something buffered or end of input */
    struct pollfd pf = { STDIN_FILENO, POLLIN, 0 };
    if (poll(&pf, 1, wait_ms) <= 0) return 0;
    unsigned char c;
    ssize_t n = read(STDIN_FILENO, &c, 1);
    if (n == 1) { in_buf = c; if (c == 0x0d) in_buf = 0x0a; idle_polls = 0; return 1; }
    in_eof = 1; return 1;
}
static int input_ready(void) {
    if (in_buf >= 0) return 1;
    if (in_eof) return 1;                         /* "ready" with 0: programs see end of input as 0 */
    return stdin_fill(++idle_polls > 20000 ? 1 : 0);
}
static int input_byte(void) {
    if (in_buf < 0 && !in_eof) stdin_fill(-1);    /* a data read waits for the byte */
    if (in_buf >= 0) { int c = in_buf; in_buf = -1; return c; }
    return 0;
}
static void console_out(int c) { char ch = (char)c; idle_polls = 0; if (write(STDOUT_FILENO, &ch, 1) < 0) exit(3); }

static uint8_t io_read(int p) {
    if (p == CF_PORT_SEL || p == CF_PORT_DATA) return cf_io_read(p);
    if (p == 2) return (uint8_t)input_byte();
    if (p != 1) return 0xFF;
    uint8_t ctl = port[0];
    if (ctl & 0x40) {                             /* UART (16550) register (ctl & 0x38) >> 3 */
        switch ((ctl >> 3) & 7) {
            case 0: return (uart_lcr & 0x80) ? uart_dll : (uint8_t)input_byte();      /* RBR */
            case 1: return (uart_lcr & 0x80) ? uart_dlm : uart_ier;
            case 2: return 0x01;                                                       /* IIR: no interrupt */
            case 3: return uart_lcr;
            case 4: return uart_mcr;
            case 5: return 0x60 | (input_ready() ? 1 : 0);                             /* LSR: THRE+TEMT, DR */
            case 6: return 0x00;                                                       /* MSR */
            default: return uart_scr;
        }
    }
    if (ctl & 0x01) return (uint8_t)switches;    /* SWITCHLED: the switches */
    return 0xFF;
}
static void io_write(int p, uint8_t v) {
    port[p] = v;
    if (p == CF_PORT_SEL || p == CF_PORT_DATA) { cf_io_write(p, v); return; }
    if (p == 2) { console_out(v); return; }
    if (p != 1) return;
    uint8_t ctl = port[0];
    if (ctl & 0x40) {
        switch ((ctl >> 3) & 7) {
            case 0: if (uart_lcr & 0x80) uart_dll = v; else console_out(v); break;   /* THR */
            case 1: if (uart_lcr & 0x80) uart_dlm = v; else uart_ier = v; break;
            case 2: uart_fcr = v; break;
            case 3: uart_lcr = v; break;
            case 4: uart_mcr = v; break;
            case 7: uart_scr = v; break;
            default: break;
        }
    }
    if (show_leds) {                              /* the LED board / TIL311 displays: reported on stderr */
        static int led = -1, til = -1;
        if ((ctl & 0x01) && v != led) { led = v; fprintf(stderr, "LED=%02X\n", v); }
        if ((ctl & 0x80) && v != til) { til = v; fprintf(stderr, "TIL=%02X\n", v); }
    }
}

/* ---- bus fights --------------------------------------------------------------------------------------------- */
static long fights[256][64];
static long fights_total, fights_kinds, weak_drives;
static void note_fight(int lane, const char *drivers) {
    fights_total++;
    if (fights[ir][step]++ == 0) {
        fights_kinds++;
        if (warn_fights) fprintf(stderr, "bus fight: %s ($%02X) step %d, DATA%s: %s\n", opname[ir] ? opname[ir] : "?", ir, step, lane ? "8..15" : "0..7", drivers);
    }
}

/* ---- one step ----------------------------------------------------------------------------------------------- */
static unsigned long nsteps, nclocks, ninstr;
static uint16_t last_fetch_pc;

static void compute(const uint8_t *w, struct comb *c) {
    memset(c, 0, sizeof *c);
    c->rd_id = field(w, s_rd_id); c->ld_id = field(w, s_ld_id);
    if (on(w, s_two_byte)) { c->rd_id = operand & 0x0F; c->ld_id = operand >> 4; }   /* sequencer IC5 */
    c->alu = field(w, s_alu);
    int addr_id = field(w, s_addr_id) & 7;
    int vma = on(w, s_vma);
    uint16_t a = REG_PRESENT(addr_id) ? reg[addr_id] : 0xFFFF;
    c->addr = force_rom ? (a | 0xF000) : a;                                     /* FORCE-ROM: BADDR12..15 high */
    if (vma && (a & 0x8000)) force_rom = 0;
    /* data bus: collect the drivers of each byte lane */
    /* a lane's value is the AND of its drivers (a low wins a TTL fight); a "fight" is two drivers that disagree,
       except the register card's pull-up value ($FF with no read strobe, review finding M-1: 327 steps, the machine
       lives with it) which is counted separately as weak */
    uint16_t lo_val = 0xFF, hi_val = 0xFF; int lo_n = 0, hi_n = 0, lo_dis = 0, hi_dis = 0;
    char lo_d[160] = "", hi_d[160] = "";
#define DRIVE_LO(v, nm) do { uint8_t _v = (v); if (lo_n && _v != (lo_val & 0xFF)) lo_dis = 1; lo_val = lo_n ? (lo_val & _v) : _v; lo_n++; strcat(lo_d, nm); strcat(lo_d, " "); } while (0)
#define DRIVE_HI(v, nm) do { uint8_t _v = (v); if (hi_n && _v != (hi_val & 0xFF)) hi_dis = 1; hi_val = hi_n ? (hi_val & _v) : _v; hi_n++; strcat(hi_d, nm); strcat(hi_d, " "); } while (0)
    if (on(w, s_mem_rd) && vma) DRIVE_LO(mem[c->addr], "MEM");
    if (on(w, s_io_rd)) { if (io_rd_hold < 0) io_rd_hold = io_read(field(w, s_ioaddr)); DRIVE_LO(io_rd_hold, "IO"); }
    else io_rd_hold = -1;
    if (on(w, s_tmp_rd0)) { DRIVE_LO(tmp0 & 0xFF, "TMP0"); DRIVE_HI(tmp0 >> 8, "TMP0"); }
    if (on(w, s_tmp_rd1)) { DRIVE_LO(tmp1 & 0xFF, "TMP1"); DRIVE_HI(tmp1 >> 8, "TMP1"); }
    if (on(w, s_branch_rd)) { DRIVE_LO(branch & 0xFF, "BRANCH"); DRIVE_HI(branch >> 8, "BRANCH"); }
    if (on(w, s_int_jmp)) { DRIVE_LO(intvec & 0xFF, "INTVEC"); DRIVE_HI(intvec >> 8, "INTVEC"); }
    int alu_func = on(w, s_alu_func), ac_rd = on(w, s_ac_rd);
    int alu_drives = alu_func && ac_rd;
    int others_lo = lo_n, others_hi = hi_n;     /* drivers seen so far on each lane (the register card is added below) */
    /* register cards: internal bus ADATA = pull-ups unless a read buffer is enabled; transceivers open when exactly
       one of RDSEL/LDSEL selects the card (straight, or swapped with -HL-SWAP) */
    int func_rd = on(w, s_reg_func_rd), func_ld = on(w, s_reg_func_ld), swap = on(w, s_hl_swap);
    int rd_card = c->rd_id >> 2, ld_card = c->ld_id >> 2;
    uint16_t adata = 0xFFFF;
    if (func_rd && !REG_PRESENT(c->rd_id & 7)) { c->adata = 0xFFFF; c->adata_valid = 1; }   /* no card: nothing drives */
    else if (func_rd) {
        int r = c->rd_id & 7;
        if (on(w, s_reg_rd_lo)) adata = (adata & 0xFF00) | (reg[r] & 0xFF);
        if (on(w, s_reg_rd_hi)) adata = (adata & 0x00FF) | (reg[r] & 0xFF00);
        c->adata = adata; c->adata_valid = 1;
        if (!(func_ld && ld_card == rd_card)) {                              /* not an internal same-card copy */
            int strobed = on(w, s_reg_rd_lo) || on(w, s_reg_rd_hi);
            if (!strobed) weak_drives++;                                      /* pull-ups through the transceivers */
            else if (!swap) { DRIVE_LO(adata & 0xFF, "REG"); DRIVE_HI(adata >> 8, "REG"); }
            else DRIVE_LO(adata >> 8, "REG(swap)");
        }
    }
    others_lo = lo_n; others_hi = hi_n;
    if (alu_drives) {                                                          /* the ALU: AC on DATA0..7, pull-ups on DATA8..15 */
        if (fight_src && others_lo) { fights_total++; if (fights[ir][step]++ == 0) { fights_kinds++; if (warn_fights) fprintf(stderr, "bus fight (ALU drive ignored, -F src): %s ($%02X) step %d\n", opname[ir] ? opname[ir] : "?", ir, step); } }
        else { DRIVE_LO(acc, "ACC"); if (!(fight_src && others_hi)) DRIVE_HI(0xFF, "ACC(FF)"); }
    }
    c->data = (uint16_t)((hi_val << 8) | (lo_val & 0xFF));
    c->data_lo_driven = lo_n; c->data_hi_driven = hi_n;
    if (lo_dis) note_fight(0, lo_d);
    if (hi_dis) note_fight(1, hi_d);
    /* the register card as a receiver: ADATA from the bus (straight) or the swap path */
    if (func_ld && !(func_rd && ld_card == rd_card)) {
        c->adata = swap ? (uint16_t)((c->data & 0xFF) << 8 | 0x00FF) : c->data;   /* swap: DATA0..7 -> ADATA8..15 */
        c->adata_valid = 1;
    }
    /* ALU function blocks: BDATA = the bus when receiving, AC (+$FF) when -AC-RD */
    uint16_t bdata = (alu_func && ac_rd) ? (uint16_t)(0xFF00 | acc) : c->data;
    uint8_t b = bdata & 0xFF;
    int fn = c->alu & 7, alu3 = (c->alu >> 3) & 1;
    unsigned sum; uint8_t out = 0;
    c->fn_addsub = (fn == 7 || fn == 1); c->fn_shift = (fn == 5);
    switch (fn) {
        case 0: out = b; break;                                                   /* DATA */
        case 1: sum = acc + (uint8_t)~b + (((alu3 & carry) ^ 1) & 1); out = sum & 0xFF; c->co_bo = ((sum >> 8) & 1) ^ 1; break;   /* SUB: CO/BO = carry XOR SUB */
        case 2: out = acc & b; break;
        case 3: out = acc | b; break;
        case 4: out = acc ^ b; break;
        case 5: out = sreg; break;                                                /* SHIFT register */
        case 6: out = 0; break;                                                   /* ZERO */
        case 7: sum = acc + b + (alu3 ? carry : 0); out = sum & 0xFF; c->co_bo = (sum >> 8) & 1; break;
    }
    c->inv_in = out;
    c->ac_input = on(w, s_ac_ld_inv) ? (uint8_t)~out : out;
    /* branch-condition mux (74LS251): D0 always, D1 BDATA<AC, D2 =, D3 BDATA>AC, D4 low byte zero, D5 IN, D6 16-bit zero, D7 carry */
    int d;
    switch (fn) {
        case 0: d = 1; break;
        case 1: d = b < acc; break;
        case 2: d = b == acc; break;
        case 3: d = b > acc; break;
        case 4: d = b == 0; break;
        case 5: d = in_line; break;
        case 6: d = bdata == 0; break;
        default: d = carry; break;
    }
    c->br_cond = d ^ on(w, s_ac_ld_inv);
}

static void trace_step(const uint8_t *w) {
    fprintf(stderr, "  %s($%02X) s%02d:", opname[ir] ? opname[ir] : "?", ir, step);
    for (int i = 0; i < nsig; i++)
        if (on(w, i) && strncmp(signals[i].name, "REG-RD-ID", 9) && strncmp(signals[i].name, "REG-LD-ID", 9) &&
            strncmp(signals[i].name, "ADDR-REG-ID", 11) && strncmp(signals[i].name, "IOADDR", 6) && strncmp(signals[i].name, "ALU", 3) &&
            strcmp(signals[i].name, "-VMA"))
            fprintf(stderr, " %s", signals[i].name);
    fprintf(stderr, "  addr=%04X data=%04X adata=%04X alu=%X ac=%02X c=%d\n", cur.addr, cur.data, cur.adata, cur.alu, acc, carry);
}

static void do_step(void) {
    const uint8_t *w = ucode[ir][step];
    /* ---- leading edge: latches take what the previous step left on the bus and in the function blocks ---- */
    if (on(w, s_ld_ins_reg)) {
        int do_int = int_pending && int_enabled;
        ir = do_int ? 0xFF : (uint8_t)(prev.data & 0xFF);
        w = ucode[ir][step];                                   /* this step's word really came from the old record; the generator makes steps 0..5 identical in every record, so the new one serves */
        ninstr++; last_fetch_pc = prev.addr;
        if (exit_pc >= 0 && last_fetch_pc == exit_pc) halted = 1;     /* -E: stop when execution reaches this address */
        if (trace) fprintf(stderr, "%04X %-6s($%02X) ACC=%02X TMP=%04X C=%d R1=%04X R2=%04X R3=%04X R4=%04X R5=%04X R6=%04X R7=%04X\n",
                           prev.addr, opname[ir] ? opname[ir] : "?", ir, acc, tmp0, carry, reg[1], reg[2], reg[3], reg[4], reg[5], reg[6], reg[7]);
    }
    if (on(w, s_operand_clk)) operand = prev.data & 0xFF;
    if (on(w, s_branch_ld_hi)) branch = (uint16_t)((branch & 0x00FF) | ((prev.data & 0xFF) << 8));   /* IC13: D = DATA0..7 */
    if (on(w, s_branch_ld_lo)) branch = (uint16_t)((branch & 0xFF00) | (prev.data & 0xFF));
    if (on(w, s_int_ld_hi)) intvec = (uint16_t)((intvec & 0x00FF) | ((prev.data & 0xFF) << 8));
    if (on(w, s_int_ld_lo)) intvec = (uint16_t)((intvec & 0xFF00) | (prev.data & 0xFF));
    if (on(w, s_tmp_ld0)) tmp0 = prev.data;
    if (on(w, s_tmp_ld1)) tmp1 = prev.data;
    if (on(w, s_ac_ld)) {
        acc = prev.ac_input;
        if (prev.fn_addsub) carry = prev.co_bo | (stale_so ? shift_out : 0);   /* IC9A: clocked with AC-LD for add/sub and shift; -S: D = CO/BO OR SHIFT-OUT as the ALU V3.2 schematic draws it */
        else if (prev.fn_shift) carry = shift_out;
    }
    if (on(w, s_sr_ld)) {                                      /* 74LS194 pair, mode S1S0 = ALU1,ALU0; serial input by ALU3,ALU2 */
        int mode = prev.alu & 3, ser_sel = (prev.alu >> 2) & 3;
        if (mode == 3) { sreg = acc; shift_out = 0; }
        else if (mode == 1) {                                  /* towards bit 7 */
            int ser = ser_sel == 0 ? 0 : ser_sel == 1 ? (sreg >> 7) & 1 : ser_sel == 2 ? (sreg >> 7) & 1 : carry;
            shift_out = (sreg >> 7) & 1; sreg = (uint8_t)((sreg << 1) | ser);
        } else if (mode == 2) {                                /* towards bit 0 */
            int ser = ser_sel == 0 ? 0 : ser_sel == 1 ? (sreg & 1) : ser_sel == 2 ? (sreg >> 7) & 1 : carry;
            shift_out = sreg & 1; sreg = (uint8_t)((sreg >> 1) | (ser << 7));
        }
    }
    if (on(w, s_int_en)) int_enabled = 1;
    if (on(w, s_int_start)) { int_enabled = 0; int_pending = 0; }
    if (on(w, s_out_on)) { if (show_leds && !out_led) fprintf(stderr, "ON\n"); out_led = 1; }
    if (on(w, s_out_off)) { if (show_leds && out_led) fprintf(stderr, "OFF\n"); out_led = 0; }
    if (on(w, s_soft_halt)) halted = 1;
    /* ---- the step itself: what drives what ---- */
    compute(w, &cur);
    if (trace_steps) trace_step(w);
    if (on(w, s_br_test) && cur.br_cond) cond_latch = 1;       /* level-sensitive SR latch */
    /* ---- trailing edge ---- */
    if (on(w, s_mem_wr) && on(w, s_vma)) {
        if (cur.addr >= 0xE000) { /* the EEPROM: ignore writes (the other emulator exits) */ }
        else mem[cur.addr] = cur.data & 0xFF;
    }
    /* -IO-WR: the I/O card's latches clock on the trailing edge, once per assertion */
    int reset = on(w, s_count_reset);
    const uint8_t *nw = reset ? ucode[ir][0] : (step < 63 ? ucode[ir][step + 1] : ucode[ir][0]);
    if (on(w, s_io_wr) && !on(nw, s_io_wr)) io_write(field(w, s_ioaddr), cur.data & 0xFF);
    if (on(w, s_reg_func_ld)) {                                /* 74LS192 LOAD, level-sensitive: value at the end of the step */
        int r = cur.ld_id & 7;
        int allowed = (cur.ld_id != 0) || cond_latch;          /* N$53: loads of R0 need the branch-taken latch */
        if (allowed && cur.adata_valid && REG_PRESENT(r)) {
            if (on(w, s_reg_ld_lo)) reg[r] = (uint16_t)((reg[r] & 0xFF00) | (cur.adata & 0xFF));
            if (on(w, s_reg_ld_hi)) reg[r] = (uint16_t)((reg[r] & 0x00FF) | (cur.adata & 0xFF00));
        }
    }
    /* counts: at the rising edge of (strobe OR select): the strobe ends, or the selection changes, in the next step */
    int next_rd = field(nw, s_rd_id); if (on(nw, s_two_byte)) next_rd = operand & 0x0F;
    if (on(w, s_reg_func_rd)) {
        int r = cur.rd_id & 7;
        int same_next = on(nw, s_reg_func_rd) && (next_rd & 7) == r;
        if (!REG_PRESENT(r)) same_next = 1;                    /* no card: nothing to count */
        if (on(w, s_reg_up) && !(same_next && on(nw, s_reg_up))) reg[r]++;
        if (on(w, s_reg_dn) && !(same_next && on(nw, s_reg_dn))) reg[r]--;
    }
    nsteps++; nclocks += reset ? 1 : 2;
    if (in_flip && nsteps % in_flip == 0) in_line ^= 1;         /* -I N: the input switch flipped every N steps */
    prev = cur;
    if (reset) { step = 0; cond_latch = 0; }
    else step = (step + 1) & 63;
    if (step == 0 && !reset) { /* a record ran off its end: the counter wraps (COUNT-FAULT would stop the clock) */
        fprintf(stderr, "y1ucemu: opcode $%02X ran to step 63 without UCODE-COUNT-RESET (COUNT-FAULT)\n", ir); halted = 2;
    }
}

/* ---- terminal: raw, no echo (the monitor's uartin echoes itself, as on the machine); Ctrl-C still quits ---- */
static struct termios saved_tty; static int tty_raw;
static void tty_restore(void) { if (tty_raw) tcsetattr(STDIN_FILENO, TCSAFLUSH, &saved_tty); }
static void tty_setup(void) {
    if (scripted || !isatty(STDIN_FILENO) || tcgetattr(STDIN_FILENO, &saved_tty) != 0) return;
    struct termios raw = saved_tty;
    raw.c_lflag &= ~(ECHO | ICANON | IEXTEN);
    raw.c_iflag &= ~(ICRNL | IXON);
    raw.c_cc[VMIN] = 1; raw.c_cc[VTIME] = 0;
    if (tcsetattr(STDIN_FILENO, TCSAFLUSH, &raw) == 0) { tty_raw = 1; atexit(tty_restore); }
}

/* ---- Intel hex loader (same as the other emulator) ---------------------------------------------------------- */
static int load_hex(const char *fn) {
    FILE *f = fopen(fn, "r"); if (!f) { fprintf(stderr, "y1ucemu: cannot open %s\n", fn); return 0; }
    char line[1024]; int total = 0;
    while (fgets(line, sizeof line, f)) {
        if (line[0] != ':') continue;
        int len, addr, type; if (sscanf(line + 1, "%2x%4x%2x", &len, &addr, &type) != 3) continue;
        if (type != 0) continue;
        for (int i = 0; i < len; i++) { int b; sscanf(line + 9 + 2 * i, "%2x", &b); mem[(addr + i) & 0xFFFF] = (uint8_t)b; total++; }
    }
    fclose(f);
    if (!scripted) printf("   Loaded %d bytes from %s\n", total, fn);
    return 1;
}

static void exe_relative(char *out, size_t outlen, const char *rel, const char *argv0) {
    char exe[4096], dir[4096];
#ifdef __APPLE__
    uint32_t n = sizeof exe;
    if (_NSGetExecutablePath(exe, &n) != 0) strncpy(exe, argv0, sizeof exe - 1);
#else
    strncpy(exe, argv0, sizeof exe - 1);
#endif
    exe[sizeof exe - 1] = 0;
    if (realpath(exe, dir) == NULL) strncpy(dir, exe, sizeof dir - 1);
    snprintf(out, outlen, "%s/%s", dirname(dir), rel);
}

int main(int argc, char **argv) {
    char path[4096], exe_dir[4096];
    exe_relative(exe_dir, sizeof exe_dir, ".", argv[0]);
    const char *ucode_path = NULL; int load_std = 0; unsigned long limit = 0;
    const char *images[32]; int nimages = 0;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-u") && i + 1 < argc) ucode_path = argv[++i];
        else if (!strcmp(argv[i], "-m")) load_std = 1;
        else if (!strcmp(argv[i], "-f") && i + 1 < argc) images[nimages++] = argv[++i];
        else if (!strcmp(argv[i], "-x")) scripted = 1;
        else if (!strcmp(argv[i], "-c") && i + 1 < argc) { if (!cf_attach(argv[++i])) { fprintf(stderr, "y1ucemu: cannot open CF image %s\n", argv[i]); return 2; } }
        else if (!strcmp(argv[i], "-t")) trace = 1;
        else if (!strcmp(argv[i], "-T")) trace_steps = 1;
        else if (!strcmp(argv[i], "-w")) warn_fights = 1;
        else if (!strcmp(argv[i], "-F") && i + 1 < argc) { i++; fight_src = !strcmp(argv[i], "src"); if (!fight_src && strcmp(argv[i], "and")) { fprintf(stderr, "y1ucemu: -F and|src\n"); return 1; } }
        else if (!strcmp(argv[i], "-s") && i + 1 < argc) switches = (int)strtol(argv[++i], NULL, 0);
        else if (!strcmp(argv[i], "-i") && i + 1 < argc) in_line = (int)strtol(argv[++i], NULL, 0) & 1;
        else if (!strcmp(argv[i], "-L")) show_leds = 1;
        else if (!strcmp(argv[i], "-S")) stale_so = 1;
        else if (!strcmp(argv[i], "-K")) stale_so = 0;
        else if (!strcmp(argv[i], "-E") && i + 1 < argc) exit_pc = strtol(argv[++i], NULL, 16);
        else if (!strcmp(argv[i], "-I") && i + 1 < argc) in_flip = strtoul(argv[++i], NULL, 0);
        else if (!strcmp(argv[i], "-R") && i + 1 < argc) { reg_cards = atoi(argv[++i]); if (reg_cards < 1 || reg_cards > 2) { fprintf(stderr, "y1ucemu: -R 1|2\n"); return 1; } }
        else if (!strcmp(argv[i], "-l") && i + 1 < argc) limit = strtoul(argv[++i], NULL, 0);
        else { fprintf(stderr, "usage: y1ucemu [-u test.hex] [-m] [-f image.hex ...] [-c disk.img] [-x] [-t] [-T] [-w] [-F and|src] [-s NN] [-i 0|1] [-I N] [-R 1|2] [-L] [-E ADDR] [-l N]\n"); return 1; }
    }
    resolve_signals();
    load_opnames(exe_dir);
    if (!ucode_path) { exe_relative(path, sizeof path, "../../firmware/microcode/ucode-generator2/test.hex", argv[0]); ucode_path = path; }
    int recs = load_ucode(ucode_path);
    if (!recs) return 2;
    if (!scripted) printf("   Control store: %d records from %s\n", recs, ucode_path);
    memset(mem, 0xFF, sizeof mem);           /* unprogrammed EEPROM and unwritten RAM read as $FF */
    if (load_std) {
        char img[4096];
        exe_relative(img, sizeof img, "../../firmware/basic/basic.img", argv[0]); load_hex(img);
        exe_relative(img, sizeof img, "../../firmware/monitor/monitor.img", argv[0]); load_hex(img);
    }
    for (int i = 0; i < nimages; i++) if (!load_hex(images[i])) return 2;
    if (!scripted) printf("   Interactive: the monitor's console is this terminal (raw mode, the monitor echoes); Ctrl-C quits.\n");
    fflush(stdout);
    tty_setup();
    /* reset: everything cleared, FORCE-ROM set, record 0 (START) fetches from $0000 -> ROM $F000 */
    memset(&prev, 0, sizeof prev); prev.data = 0xFFFF;
    while (!halted) {
        do_step();
        if (limit && nsteps >= limit) { fprintf(stderr, "y1ucemu: step limit reached\n"); break; }
    }
    fflush(stdout);
    tty_restore();
    if (scripted || halted) {
        fprintf(stderr, "%s at %04X after %lu instructions, %lu steps, %lu clocks, R3=%04X; bus fights: %ld in %ld (opcode,step) pairs; weak pull-up drives: %ld\n",
                halted == 2 ? "COUNT-FAULT" : "HALT", last_fetch_pc, ninstr, nsteps, nclocks, reg[3], fights_total, fights_kinds, weak_drives);
        if (fights_kinds && !warn_fights) {
            fprintf(stderr, "  fights by opcode:");
            for (int o = 0; o < 256; o++) { long n = 0; for (int s = 0; s < 64; s++) n += fights[o][s]; if (n) fprintf(stderr, " %s($%02X)x%ld", opname[o] ? opname[o] : "?", o, n); }
            fprintf(stderr, "\n");
        }
    }
    return halted == 2 ? 4 : 0;
}
