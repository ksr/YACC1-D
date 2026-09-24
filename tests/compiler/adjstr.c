/* adjstr.c - adjacent string literals are not concatenated in the y1cc subset: a compile error (adjstr.err). Until
   2026-09-24 this crashed y1cc.py with a Python TypeError (a string token looked up in the op= table). */
void main() { puts("one" "two"); }
