/* cc2_parse.c - pass 2 of the multi-pass y1cc (2026-09-24): the parser, from W.tok to the AST. y1cc.c's parser
   (y1cc.py's class P) and its constant folding, unchanged in what they accept and in their messages.

     cc2 W          reads W.tok (and W.nam / W.lit for the text of a message); writes W.ast, W.typ

   W.ast is one record per top-level declaration (a toplevel() call), with node ids local to the record:
     1(1) n(2) h(2) ncalls(2) ndecls(2) blen(2) ne(2) entry(2)...
     nodes 1..h;  ncalls x [name(2) nargs(2) kind(1) arg(2)];  ndecls x [name(2) type(2)];  nodes h+1..n (blen bytes)
   n nodes; the entries are the nodes y1cc.c's prog_add() collected (several for "int a, b;"); for a function
   definition h is the N_FUNC node and h+1..n its body. A function's record also lists its calls in the order
   y1cc.c's walk() meets them (the callee's name, the argument count, and the kind and name of the first argument,
   for funcaddr()) and its local declarations in the order of y1cc.c's collect_decls() (duplicates included), so
   the call graph (cc4) and the layout (cc5) never load a body. A node: kind(1) mask(1), then the fields a b c d x
   (x = the next in a list) whose mask bit (1 2 4 8 16) is set, 2 bytes each (the rest are 0). A 0 byte or the end
   of the file ends W.ast.
   W.typ: count(2), then base(2) ptr(1) count(2) per type id 1.. */
#include "pcommon.c"

char *optext[] = {"", "<<=", ">>=", "==", "!=", "<=", ">=", "<<", ">>", "&&", "||", "->", "++", "--",
                  "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "{", "}", "(", ")", "[", "]", ";", ",", "=",
                  ".", "?", ":", "+", "-", "*", "/", "%", "<", ">", "!", "&", "|", "^", "~"};

/* types (base name, pointer depth, array count), interned: id 1.. */
int ty_b[TYPES_MAX];
int ty_p[TYPES_MAX];
int ty_c[TYPES_MAX];
int ntypes;

/* the nodes of the current top-level declaration: node 0 is "none"; nx links the elements of a list */
char nk[NODES_MAX];
int na[NODES_MAX];
int nb[NODES_MAX];
int nc[NODES_MAX];
int nd[NODES_MAX];
int nx[NODES_MAX];
int nn;
int ent[ENTRIES_MAX];
int nent;

/* the token ring: the parser looks at most 2 tokens ahead and 1 back */
int tk_kind[8];
int tk_val[8];
int tk_line[8];
int tk_have;
int ti;
int tokh;                       /* W.tok */
int tline;                      /* the line of the next token read */
int fv;                         /* fold() */
int bp_base;                    /* base_and_ptr() */
int bp_ptr;
char nmbuf[ID_MAX];

void need_tok(int i);
int tk(int d);
int tv(int d);
int is_op(int d, int op);
int is_kw(int d, int kw);
void perr(char *msg);
void perr_tok(char *pre, int d);
void e_tok(int d);
void eat(int op);
int accept(int op);
int accept_kw(int kw);
int is_type_start(void);
void program(void);
void base_and_ptr(void);
int tok_name(int d);
int struct_def(void);
int const_expr(void);
void toplevel(void);
int initializer(void);
int param(void);
int block(void);
int stmt(void);
int expr(void);
int assign_op(int op);
int assign(void);
int logic_or(void);
int logic_and(void);
int in_level(int lvl, int op);
int binary(int lvl);
int unary(void);
int postfix(void);
int primary(void);
int fold(int e);
int fold_bin(int op, int l, int r);
int size_of(int base, int ptr);
int type_id(int base, int ptr, int cnt);
int new_node(int k, int a, int b, int c, int d);
void prog_add(int n);
void write_record(void);
int node_bytes(int i);
void write_node(int i);
void lwalk(int n);
void lwalk_list(int n);
void ldecls(int s);
int lmode;                      /* write_record(): 0 count the calls / declarations, 1 write them */
int lcount;

void pass_fail(char *msg) { io_fail(msg); }

int type_id(int base, int ptr, int cnt) {
    int i;
    for (i = 1; i <= ntypes; i++) if (ty_b[i] == base && ty_p[i] == ptr && ty_c[i] == cnt) return i;
    if (ntypes + 1 >= TYPES_MAX) fail("y1cc: too many types (TYPES_MAX)");
    ntypes++;
    ty_b[ntypes] = base; ty_p[ntypes] = ptr; ty_c[ntypes] = cnt;
    return ntypes;
}
int new_node(int k, int a, int b, int c, int d) {
    if (nn + 1 >= NODES_MAX) fail("y1cc: declaration too big (NODES_MAX)");
    nn++;
    nk[nn] = k; na[nn] = a; nb[nn] = b; nc[nn] = c; nd[nn] = d; nx[nn] = 0;
    return nn;
}
void prog_add(int n) {
    if (nent >= ENTRIES_MAX) fail("y1cc: too many declarators (ENTRIES_MAX)");
    ent[nent] = n; nent++;
}

/* ---- the tokens ------------------------------------------------------------------------------------------------ */
void need_tok(int i) {
    int c; int s;
    while (tk_have <= i) {
        c = rb(tokh);
        if (c == T_LINE) { tline = ri(tokh); continue; }
        s = tk_have & 7;
        if (c == 256) { tk_kind[s] = T_EOF; tk_val[s] = 0; }             /* past the end: more T_EOF */
        else { tk_kind[s] = c; tk_val[s] = ri(tokh); }
        tk_line[s] = tline;
        tk_have++;
    }
}
int tk(int d) { need_tok(ti + d); return tk_kind[(ti + d) & 7]; }
int tv(int d) { need_tok(ti + d); return tk_val[(ti + d) & 7]; }
int is_op(int d, int op) { return tk(d) == T_OP && tv(d) == op; }
int is_kw(int d, int kw) { return tk(d) == T_KW && tv(d) == kw; }
void perr(char *msg) {                              /* "y1cc: line N: msg" */
    need_tok(ti);
    e_start("y1cc: line "); e_n(tk_line[ti & 7]); e_s(": "); e_s(msg); e_go();
}
void e_tok(int d) {                                 /* Python's repr() of a token's value */
    int k; int v; int i; int h; int n;
    k = tk(d); v = tv(d);
    if (k == T_EOF) { e_s("None"); return; }
    if (k == T_NUM) { e_n(v); return; }
    if (k == T_OP) { e_q(optext[v]); return; }
    if (k == T_STR) {                               /* the literal's bytes, from W.lit */
        h = ropen(".lit");
        ri(h);
        for (i = 1; i < v; i++) { n = ri(h); while (n) { rb(h); n--; } }
        n = ri(h);
        e_s("[");
        for (i = 0; i < n; i++) { if (i) e_s(", "); e_n(rb(h)); }
        e_s("]");
        io_close(h);
        return;
    }
    nm_fetch(v, nmbuf);
    e_q(nmbuf);
}
void perr_tok(char *pre, int d) {
    need_tok(ti);
    e_start("y1cc: line "); e_n(tk_line[ti & 7]); e_s(": "); e_s(pre); e_tok(d); e_go();
}
void eat(int op) {
    if (!is_op(0, op)) {
        need_tok(ti);
        e_start("y1cc: line "); e_n(tk_line[ti & 7]); e_s(": expected "); e_q(optext[op]); e_s(", got ");
        e_tok(0); e_go();
    }
    ti++;
}
int accept(int op) { if (is_op(0, op)) { ti++; return 1; } return 0; }
int accept_kw(int kw) { if (is_kw(0, kw)) { ti++; return 1; } return 0; }
int is_type_start(void) {
    int v;
    if (tk(0) != T_KW) return 0;
    v = tv(0);
    return v == K_INT || v == K_CHAR || v == K_VOID || v == K_STRUCT || v == K_UNION || v == K_UNSIGNED ||
           v == K_CONST || v == K_STATIC;
}

/* ---- the parser -> AST (y1cc.c) ---------------------------------------------------------------------------------- */
void program(void) {
    while (tk(0) != T_EOF) { toplevel(); write_record(); }
}
void base_and_ptr(void) {                           /* -> bp_base, bp_ptr */
    int base; int ptr;
    while (is_kw(0, K_CONST) || is_kw(0, K_STATIC) || is_kw(0, K_UNSIGNED)) ti++;
    if (is_kw(0, K_STRUCT) || is_kw(0, K_UNION)) {
        ti++;
        base = tv(0); ti++;
        if (tk_kind[(ti + 7) & 7] != T_ID) perr("expected struct/union tag");
    } else if (is_kw(0, K_INT) || is_kw(0, K_CHAR) || is_kw(0, K_VOID)) {
        base = tv(0); ti++;
    } else if (tk_kind[(ti + 7) & 7] == T_KW && tk_val[(ti + 7) & 7] == K_UNSIGNED && ti > 0) {
        base = K_INT;                                /* bare `unsigned` */
    } else {
        perr("expected a type");
        base = 0;
    }
    ptr = 0;
    for (;;) {
        if (accept(O_STAR)) ptr++;
        else if (is_kw(0, K_CONST)) ti++;
        else break;
    }
    bp_base = base; bp_ptr = ptr;
}
int tok_name(int d) {                               /* the name id of an id/keyword token (y1cc.py: next()[1]) */
    if (tk(d) == T_ID || tk(d) == T_KW) return tv(d);
    return 0;
}
int struct_def(void) {                              /* struct/union T { ... }; */
    int kind; int tag; int first; int last; int m; int base; int ptr; int nm; int count;
    kind = is_kw(0, K_UNION) ? 2 : 1; ti++;
    tag = tok_name(0); ti++;
    eat(O_LBRACE);
    first = 0; last = 0;
    while (!is_op(0, O_RBRACE)) {
        base_and_ptr(); base = bp_base; ptr = bp_ptr;
        nm = tok_name(0); ti++;
        count = 0;
        if (accept(O_LBRACK)) { count = const_expr(); eat(O_RBRACK); }
        eat(O_SEMI);
        m = new_node(N_MEMBERDEF, type_id(base, ptr, count), nm, 0, 0);
        if (last) nx[last] = m; else first = m;
        last = m;
    }
    eat(O_RBRACE); eat(O_SEMI);
    return new_node(N_STRUCTDEF, kind, tag, first, 0);
}
int const_expr(void) {
    int e;
    e = expr();
    if (!fold(e)) perr("constant expression expected");
    return fv;
}
void toplevel(void) {
    int base; int ptr; int name; int first; int last; int p; int arr; int count; int init; int flags;
    if ((is_kw(0, K_STRUCT) || is_kw(0, K_UNION)) && is_op(2, O_LBRACE)) { prog_add(struct_def()); return; }
    base_and_ptr(); base = bp_base; ptr = bp_ptr;
    name = tv(0); ti++;
    if (tk_kind[(ti + 7) & 7] != T_ID) perr("expected name");
    if (accept(O_LPAREN)) {
        first = 0; last = 0;
        if (is_kw(0, K_VOID) && is_op(1, O_RPAREN)) ti++;
        else if (!is_op(0, O_RPAREN)) {
            first = param(); last = first;
            while (accept(O_COMMA)) { p = param(); nx[last] = p; last = p; }
        }
        eat(O_RPAREN);
        if (accept(O_SEMI)) { prog_add(new_node(N_PROTO, type_id(base, ptr, 0), name, first, 0)); return; }
        p = new_node(N_FUNC, type_id(base, ptr, 0), name, first, 0);
        nd[p] = block();
        prog_add(p);
        return;
    }
    for (;;) {                                      /* int a, *b, c[3]; */
        arr = 0; count = 0; flags = 0;
        if (accept(O_LBRACK)) {
            arr = 1;
            if (is_op(0, O_RBRACK)) flags = 2; else count = const_expr();
            eat(O_RBRACK);
        }
        init = 0;
        if (accept(O_ASSIGN)) init = initializer();
        prog_add(new_node(N_GVAR, type_id(base, ptr, count), name, init, arr | flags));
        if (!accept(O_COMMA)) break;
        ptr = 0;                                    /* a new declarator starts from the base type (int *p, q) */
        while (accept(O_STAR)) ptr++;
        name = tok_name(0); ti++;
    }
    eat(O_SEMI);
}
int initializer(void) {                             /* constant global initializer */
    int first; int last; int it; int nm;
    if (accept(O_LBRACE)) {
        first = 0; last = 0;
        if (!is_op(0, O_RBRACE)) {
            first = initializer(); last = first;
            while (accept(O_COMMA)) {
                if (is_op(0, O_RBRACE)) break;
                it = initializer(); nx[last] = it; last = it;
            }
        }
        eat(O_RBRACE);
        return new_node(N_INITLIST, first, 0, 0, 0);
    }
    if (tk(0) == T_STR) { it = tv(0); ti++; return new_node(N_INITSTR, it, 0, 0, 0); }
    if (accept(O_AMP)) {
        nm = tv(0); ti++;
        if (tk_kind[(ti + 7) & 7] != T_ID) perr("expected a name after &");
        return new_node(N_INITADDR, nm, 0, 0, 0);
    }
    if (tk(0) == T_ID && (is_op(1, O_COMMA) || is_op(1, O_SEMI) || is_op(1, O_RBRACE))) {
        nm = tv(0); ti++;                           /* an array's address */
        return new_node(N_INITADDR, nm, 0, 0, 0);
    }
    it = expr();
    if (!fold(it)) perr("non-constant global initializer");
    return new_node(N_INITNUM, fv, 0, 0, 0);
}
int param(void) {
    int base; int ptr; int nm;
    base_and_ptr(); base = bp_base; ptr = bp_ptr;
    nm = tv(0); ti++;
    if (tk_kind[(ti + 7) & 7] != T_ID) perr("expected parameter name");
    if (accept(O_LBRACK)) { eat(O_RBRACK); ptr++; }  /* T a[] as a parameter = pointer */
    return new_node(N_PARAM, type_id(base, ptr, 0), nm, 0, 0);
}
int block(void) {
    int first; int last; int s;
    eat(O_LBRACE);
    first = 0; last = 0;
    while (!is_op(0, O_RBRACE)) {
        s = stmt();
        if (last) nx[last] = s; else first = s;
        last = s;
    }
    eat(O_RBRACE);
    return new_node(N_BLOCK, first, 0, 0, 0);
}
int stmt(void) {
    int base; int ptr; int p; int name; int count; int init; int first; int last; int d; int c; int t; int e;
    int i; int post;
    if (is_op(0, O_LBRACE)) return block();
    if (is_type_start()) {
        base_and_ptr(); base = bp_base; ptr = bp_ptr;   /* the stars consumed here belong to the FIRST declarator */
        first = 0; last = 0;
        for (;;) {
            p = ptr; ptr = 0;                       /* later declarators start from the base type (int *p, q) */
            while (accept(O_STAR)) p++;
            name = tok_name(0); ti++;
            count = 0;
            if (accept(O_LBRACK)) { count = const_expr(); eat(O_RBRACK); }
            init = 0;
            if (accept(O_ASSIGN)) init = expr();
            d = new_node(N_DECL, type_id(base, p, count), name, init, 0);
            if (last) nx[last] = d; else first = d;
            last = d;
            if (!accept(O_COMMA)) break;
        }
        eat(O_SEMI);
        if (first == last) return first;
        return new_node(N_BLOCK, first, 0, 0, 0);
    }
    if (is_kw(0, K_IF)) {
        ti++; eat(O_LPAREN); c = expr(); eat(O_RPAREN);
        t = stmt(); e = 0;
        if (accept_kw(K_ELSE)) e = stmt();
        return new_node(N_IF, c, t, e, 0);
    }
    if (is_kw(0, K_WHILE)) {
        ti++; eat(O_LPAREN); c = expr(); eat(O_RPAREN);
        return new_node(N_WHILE, c, stmt(), 0, 0);
    }
    if (is_kw(0, K_FOR)) {
        ti++; eat(O_LPAREN);
        i = 0; if (!is_op(0, O_SEMI)) i = expr();
        eat(O_SEMI);
        c = 0; if (!is_op(0, O_SEMI)) c = expr();
        eat(O_SEMI);
        post = 0; if (!is_op(0, O_RPAREN)) post = expr();
        eat(O_RPAREN);
        t = stmt();
        return new_node(N_FOR, i, c, post, t);
    }
    if (is_kw(0, K_RETURN)) {
        ti++; e = 0;
        if (!is_op(0, O_SEMI)) e = expr();
        eat(O_SEMI);
        return new_node(N_RETURN, e, 0, 0, 0);
    }
    if (is_kw(0, K_SWITCH)) {
        ti++; eat(O_LPAREN); e = expr(); eat(O_RPAREN);
        if (!is_op(0, O_LBRACE)) perr("switch body must be a { block }");
        return new_node(N_SWITCH, e, block(), 0, 0);
    }
    if (is_kw(0, K_CASE)) { ti++; c = const_expr(); eat(O_COLON); return new_node(N_CASE, c, 0, 0, 0); }
    if (is_kw(0, K_DEFAULT)) { ti++; eat(O_COLON); return new_node(N_DEFAULT, 0, 0, 0, 0); }
    if (is_kw(0, K_BREAK)) { ti++; eat(O_SEMI); return new_node(N_BREAK, 0, 0, 0, 0); }
    if (is_kw(0, K_CONTINUE)) { ti++; eat(O_SEMI); return new_node(N_CONTINUE, 0, 0, 0, 0); }
    if (is_op(0, O_SEMI)) { ti++; return new_node(N_EMPTY, 0, 0, 0, 0); }
    e = expr(); eat(O_SEMI);
    return new_node(N_EXPR, e, 0, 0, 0);
}
int expr(void) { return assign(); }
int assign_op(int op) {                             /* x op= e  ->  the binary operator */
    if (op == O_ADDEQ) return O_PLUS;
    if (op == O_SUBEQ) return O_MINUS;
    if (op == O_MULEQ) return O_STAR;
    if (op == O_DIVEQ) return O_SLASH;
    if (op == O_MODEQ) return O_PERCENT;
    if (op == O_ANDEQ) return O_AMP;
    if (op == O_OREQ) return O_BAR;
    if (op == O_XOREQ) return O_CARET;
    if (op == O_SHLEQ) return O_SHL;
    if (op == O_SHREQ) return O_SHR;
    return 0;
}
int assign(void) {
    int left; int a; int b; int op;
    left = logic_or();
    if (is_op(0, O_QUEST)) {                        /* c ? a : b */
        ti++; a = assign(); eat(O_COLON); b = assign();
        return new_node(N_COND, left, a, b, 0);
    }
    if (is_op(0, O_ASSIGN)) { ti++; a = assign(); return new_node(N_ASSIGN, left, a, 0, 0); }
    if (tk(0) == T_OP && assign_op(tv(0))) {        /* x op= e  ->  x = x op e (lvalue evaluated twice) */
        op = assign_op(tv(0)); ti++;
        a = assign();
        return new_node(N_ASSIGN, left, new_node(N_BIN, op, left, a, 0), 0, 0);
    }
    return left;
}
int logic_or(void) {
    int left; int r;
    left = logic_and();
    while (is_op(0, O_OROR)) { ti++; r = logic_and(); left = new_node(N_LOGOR, left, r, 0, 0); }
    return left;
}
int logic_and(void) {
    int left; int r;
    left = binary(0);
    while (is_op(0, O_ANDAND)) { ti++; r = binary(0); left = new_node(N_LOGAND, left, r, 0, 0); }
    return left;
}
int in_level(int lvl, int op) {                     /* y1cc.py's LEVELS */
    if (lvl == 0) return op == O_BAR;
    if (lvl == 1) return op == O_CARET;
    if (lvl == 2) return op == O_AMP;
    if (lvl == 3) return op == O_EQ || op == O_NE;
    if (lvl == 4) return op == O_LT || op == O_GT || op == O_LE || op == O_GE;
    if (lvl == 5) return op == O_SHL || op == O_SHR;
    if (lvl == 6) return op == O_PLUS || op == O_MINUS;
    return op == O_STAR || op == O_SLASH || op == O_PERCENT;
}
int binary(int lvl) {
    int left; int op; int r;
    if (lvl >= 8) return unary();
    left = binary(lvl + 1);
    while (tk(0) == T_OP && in_level(lvl, tv(0))) {
        op = tv(0); ti++;
        r = binary(lvl + 1);
        left = new_node(N_BIN, op, left, r, 0);
    }
    return left;
}
int unary(void) {
    int op; int e; int v;
    if (tk(0) == T_OP) {
        op = tv(0);
        if (op == O_MINUS || op == O_NOT || op == O_AMP || op == O_STAR || op == O_TILDE) {
            ti++; e = unary(); return new_node(N_UNARY, op, e, 0, 0);
        }
        if (op == O_INC || op == O_DEC) { ti++; e = unary(); return new_node(N_PREINC, op, e, 0, 0); }
    }
    if (is_kw(0, K_SIZEOF)) {
        ti++;
        if (is_op(0, O_LPAREN) && tk(1) == T_KW) {
            v = tv(1);
            if (v == K_INT || v == K_CHAR || v == K_STRUCT || v == K_UNION || v == K_UNSIGNED) {
                ti++; base_and_ptr(); eat(O_RPAREN);
                return new_node(N_SIZEOFT, bp_base, bp_ptr, 0, 0);
            }
        }
        e = unary();
        return new_node(N_SIZEOFE, e, 0, 0, 0);
    }
    return postfix();
}
int postfix(void) {
    int e; int first; int last; int a; int n; int m;
    e = primary();
    for (;;) {
        if (is_op(0, O_LPAREN)) {
            ti++; first = 0; last = 0; n = 0;
            if (!is_op(0, O_RPAREN)) {
                first = expr(); last = first; n = 1;
                while (accept(O_COMMA)) { a = expr(); nx[last] = a; last = a; n++; }
            }
            eat(O_RPAREN);
            if (nk[e] != N_ID) perr("call of non-function");
            e = new_node(N_CALL, na[e], first, n, 0);
        } else if (is_op(0, O_LBRACK)) {
            ti++; a = expr(); eat(O_RBRACK);
            e = new_node(N_INDEX, e, a, 0, 0);
        } else if (is_op(0, O_DOT)) {
            ti++; m = tok_name(0); ti++;
            e = new_node(N_MEMBER, e, m, 0, 0);
        } else if (is_op(0, O_ARROW)) {
            ti++; m = tok_name(0); ti++;
            e = new_node(N_ARROW, e, m, 0, 0);
        } else if (is_op(0, O_INC) || is_op(0, O_DEC)) {
            m = tv(0); ti++;
            e = new_node(N_POSTINC, m, e, 0, 0);
        } else {
            return e;
        }
    }
    return e;
}
int primary(void) {
    int k; int v; int e;
    k = tk(0); v = tv(0);
    if (k == T_NUM) { ti++; return new_node(N_NUM, v, 0, 0, 0); }
    if (k == T_STR) { ti++; return new_node(N_STR, v, 0, 0, 0); }
    if (k == T_ID) { ti++; return new_node(N_ID, v, 0, 0, 0); }
    if (k == T_OP && v == O_LPAREN) { ti++; e = expr(); eat(O_RPAREN); return e; }
    perr_tok("unexpected ", 0);
    return 0;
}

/* ---- constant folding (y1cc.c; at parse time no struct is registered, so sizeof(struct) does not fold) --------- */
int fold(int e) {                                   /* 1 with the value (mod 2^16) in fv, or 0 */
    int k; int v; int op;
    k = nk[e];
    if (k == N_NUM) { fv = na[e] & 65535; return 1; }
    if (k == N_UNARY) {
        op = na[e];
        if (op != O_MINUS && op != O_TILDE && op != O_NOT) return 0;
        if (!fold(nb[e])) return 0;
        v = fv;
        if (op == O_MINUS) fv = (65535 - v + 1) & 65535;
        else if (op == O_TILDE) fv = 65535 - v;
        else fv = v == 0;
        return 1;
    }
    if (k == N_BIN) return fold_bin(na[e], nb[e], nc[e]);
    if (k == N_SIZEOFT) { fv = size_of(na[e], nb[e]); return 1; }
    if (k == N_COND) {
        if (!fold(na[e])) return 0;
        if (fv) return fold(nb[e]);
        return fold(nc[e]);
    }
    return 0;
}
int fold_bin(int op, int l, int r) {
    int a; int b; int oka; int okb; int x;
    oka = fold(l); a = fv;
    okb = fold(r); b = fv;
    if (!oka || !okb) return 0;
    if ((op == O_SLASH || op == O_PERCENT) && b == 0) return 0;
    x = 0;
    if (op == O_PLUS) x = a + b;
    else if (op == O_MINUS) x = a + 65535 - b + 1;
    else if (op == O_STAR) x = mul16(a, b);
    else if (op == O_SLASH) x = a / b;
    else if (op == O_PERCENT) x = a % b;
    else if (op == O_AMP) x = a & b;
    else if (op == O_BAR) x = a | b;
    else if (op == O_CARET) x = a ^ b;
    else if (op == O_SHL) x = (a << (b & 15)) & 65535;
    else if (op == O_SHR) x = a >> (b & 15);
    else if (op == O_EQ) x = a == b;
    else if (op == O_NE) x = a != b;
    else if (op == O_LT) x = a < b;
    else if (op == O_GT) x = a > b;
    else if (op == O_LE) x = a <= b;
    else if (op == O_GE) x = a >= b;
    fv = x & 65535;
    return 1;
}
int size_of(int base, int ptr) {
    if (ptr > 0 || base == K_INT) return 2;
    if (base == K_CHAR) return 1;
    nm_fetch(base, nmbuf);
    e_start("y1cc: unknown type "); e_q(nmbuf); e_go();
    return 0;
}

/* ---- W.ast ---------------------------------------------------------------------------------------------------------- */
int node_bytes(int i) {
    int n;
    n = 2;
    if (na[i]) n = n + 2;
    if (nb[i]) n = n + 2;
    if (nc[i]) n = n + 2;
    if (nd[i]) n = n + 2;
    if (nx[i]) n = n + 2;
    return n;
}
void write_node(int i) {
    int m;
    m = 0;
    if (na[i]) m = m | 1;
    if (nb[i]) m = m | 2;
    if (nc[i]) m = m | 4;
    if (nd[i]) m = m | 8;
    if (nx[i]) m = m | 16;
    wb(nk[i]); wb(m);
    if (na[i]) wi(na[i]);
    if (nb[i]) wi(nb[i]);
    if (nc[i]) wi(nc[i]);
    if (nd[i]) wi(nd[i]);
    if (nx[i]) wi(nx[i]);
}
/* a function's calls, in y1cc.c walk()'s order (lmode 0: count them, 1: write them) */
void lwalk_list(int n) { while (n) { lwalk(n); n = nx[n]; } }
void lwalk(int n) {
    int k; int a;
    if (!n) return;
    k = nk[n];
    if (k == N_CALL) {
        if (lmode) { a = nb[n]; wi(na[n]); wi(nc[n]); wb(nk[a]); wi(na[a]); } else lcount++;
        lwalk_list(nb[n]);
        return;
    }
    if (k == N_UNARY || k == N_PREINC || k == N_POSTINC) { lwalk(nb[n]); return; }
    if (k == N_SIZEOFE || k == N_MEMBER || k == N_ARROW || k == N_RETURN || k == N_EXPR) { lwalk(na[n]); return; }
    if (k == N_INDEX || k == N_ASSIGN || k == N_LOGOR || k == N_LOGAND || k == N_WHILE || k == N_SWITCH) {
        lwalk(na[n]); lwalk(nb[n]); return;
    }
    if (k == N_COND || k == N_IF) { lwalk(na[n]); lwalk(nb[n]); lwalk(nc[n]); return; }
    if (k == N_BIN) { lwalk(nb[n]); lwalk(nc[n]); return; }
    if (k == N_BLOCK) { lwalk_list(na[n]); return; }
    if (k == N_DECL) { lwalk(nc[n]); return; }
    if (k == N_FOR) { lwalk(na[n]); lwalk(nb[n]); lwalk(nc[n]); lwalk(nd[n]); return; }
}
/* its declarations, in y1cc.c collect_decls()'s order (the duplicates too: cc5 keeps the first) */
void ldecls(int s) {
    int k; int m;
    if (!s) return;
    k = nk[s];
    if (k == N_DECL) { if (lmode) { wi(nb[s]); wi(na[s]); } else lcount++; return; }
    if (k == N_BLOCK) { for (m = na[s]; m; m = nx[m]) ldecls(m); return; }
    if (k == N_IF) { ldecls(nb[s]); ldecls(nc[s]); return; }
    if (k == N_WHILE) { ldecls(nb[s]); return; }
    if (k == N_FOR) { ldecls(nd[s]); return; }
}
void write_record(void) {                           /* the nodes of one toplevel(), then start afresh */
    int h; int i; int blen; int nca; int nde; int f;
    h = nn; f = 0; nca = 0; nde = 0;
    if (nent == 1 && nk[ent[0]] == N_FUNC) {
        h = ent[0]; f = nd[h];
        lmode = 0; lcount = 0; lwalk(f); nca = lcount;
        lcount = 0; ldecls(f); nde = lcount;
    }
    blen = 0;
    for (i = h + 1; i <= nn; i++) blen = blen + node_bytes(i);
    wb(1); wi(nn); wi(h); wi(nca); wi(nde); wi(blen); wi(nent);
    for (i = 0; i < nent; i++) wi(ent[i]);
    for (i = 1; i <= h; i++) write_node(i);
    lmode = 1;
    if (f) { lwalk(f); ldecls(f); }
    for (i = h + 1; i <= nn; i++) write_node(i);
    nn = 0; nent = 0;
}

void y1cc_main(void) {
    int i;
    p_args();
    tokh = ropen(".tok");
    wopen(".ast");
    program();
    wb(0);
    wclose();
    io_close(tokh);
    wopen(".typ");
    wi(ntypes);
    for (i = 1; i <= ntypes; i++) { wi(ty_b[i]); wb(ty_p[i]); wi(ty_c[i]); }
    wclose();
}
