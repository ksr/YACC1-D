/* help.c - the Y1/OS command reference: the shell's built-ins and the /BIN programs, one line each.
     help       the list (man NAME for the page of any of them)
   Ported from P8X os/commands/help.c 2026-09-23, changes: the text is rewritten for Y1/OS (no /d1, graphics,
   kermit, make, sh; the built-ins are Y1/OS's; redirection and pipes since the same evening: man shell; pack added 2026-09-23;
   asm 2026-09-25). Keep it
   in step with os/README.md. */
#include "y1lib.c"

void main() {
    puts("Y1/OS commands (man NAME for more; a /BIN program wins over a built-in of the same name)");
    puts("built into the shell:");
    puts("  cd path        change directory (/abs, rel, ., ..)");
    puts("  load path      read a program to its load address");
    puts("  run path args  load and call a program with an argument tail");
    puts("  save p a l     write memory a..a+l (hex) to a new file");
    puts("  ren path name  rename a file or directory in place");
    puts("  mkdir / rmdir  make / remove (an empty) directory");
    puts("  type path      print a file (the built-in cat)");
    puts("  exit           back to the ROM monitor");
    puts("  cmd < in  > out  >> out  a | b | c   redirection and pipes (man shell)");
    puts("in /BIN:");
    puts("  asm  assemble: asm [-h] SRC [OUT]  (-h: Intel hex)");
    puts("  awk  one-rule awk: fields, /re/ {print $N ...}, NR NF");
    puts("  cat  print files (globs, - = console)   cmp  first differing byte");
    puts("  cp   copy files, -r a tree               del  delete files (globs)");
    puts("  dep  deposit hex bytes into memory       diff line differences");
    puts("  dir  list, sorted; -R -S, globs          dump hex dump, a page a key");
    puts("  echo print the arguments                 examine view/change memory");
    puts("  find names matching a pattern (tree)     grep lines matching a regex; -r");
    puts("  head first lines                         help this list");
    puts("  ls   plain directory list                man  a manual page (/MAN)");
    puts("  md   render Markdown (/DOCS)             more page a file");
    puts("  mv   move/rename files                   pack compact the disk: reclaim dead sectors");
    puts("  pwd  the working directory               sed  s/re/new/[g]");
    puts("  sort sort lines                          tail last lines");
    puts("  touch create empty files                 tree the directory tree");
    puts("  uniq drop adjacent repeats               vi   the screen editor");
    puts("  wc   lines words bytes");
}
