#!/bin/sh
# sizecmp.sh - the same C source through the P8X toolchain (p8cc.py + p8xasm.py) and the YACC1 one (y1cc.py + asm):
# binary size of each (code + data + uninitialised variables, so both count the same things), the YACC1 emulator's
# instruction count, and whether the YACC1 output equals the host C compiler's (tests/compiler/host_shim.h).
# The programs stay inside the subset BOTH compilers accept (no ++ += ?: switch #include, one declarator per line).
#   sh software/compiler/bench/sizecmp.sh [p8x-tree]      (default ~/Developer/p8x)
set -e
here=$(cd "$(dirname "$0")" && pwd); root=$(cd "$here/../../.." && pwd); p8x=${1:-$HOME/Developer/p8x}
[ -f "$p8x/compiler/p8cc.py" ] || { echo "no P8X tree at $p8x"; exit 1; }
build=$(mktemp -d); cp "$root/software/assembler/yacc1.def" "$build/"; echo "-h" > "$build/rcasm.rc"
printf '%-9s %8s %8s %6s   %s\n' program p8x yacc1 ratio "yacc1 instructions / output = host?"
for src in "$here"/*.c; do
  t=$(basename "$src" .c); cp "$src" "$build/"; cd "$build"
  python3 "$p8x/compiler/p8cc.py" $t.c -o p8_$t.asm > /dev/null && python3 "$p8x/assembler/p8xasm.py" p8_$t.asm -o p8_$t.bin --base 0x5900 > /dev/null 2>&1
  p8=$(wc -c < p8_$t.bin | tr -d ' ')
  python3 "$root/software/compiler/y1cc.py" $t.c -o $t.asm --boot && "$root/software/assembler/asm" $t -d=yacc1 > $t.lst
  obj=$(grep -o "Object Code:[0-9]*" $t.lst | grep -o "[0-9]*"); ds=$(awk '/ DS /{s+=$NF} END{print s+0}' $t.asm)
  y1=$((obj - 8 + ds))      # minus the 8-byte --boot stub, plus the DS bytes (p8xasm's .fill is inside its .bin)
  out=$("$root/software/emulator/emulator" -x -f $t.img < /dev/null 2> err.txt | md5); inst=$(grep -o "after [0-9]* instructions" err.txt)
  host=$(cc -w -funsigned-char -include "$root/tests/compiler/host_shim.h" -o host_$t $t.c && ./host_$t | md5)
  printf '%-9s %8s %8s %6.2f   %s  %s\n' $t $p8 $y1 $(echo "$y1 / $p8" | bc -l) "$inst" "$([ "$out" = "$host" ] && echo yes || echo NO)"
done
rm -rf "$build"
