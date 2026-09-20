#!/bin/bash
j=(3 2 1 0 7 6 5 4 11 10 9 8 15 14 13 12)
for i in {0..15} 
do
   sed "s/R0D$i\"/SP-${j[$i]}\"/" <SP:PC-2.sch >tmp
   mv tmp SP:PC-2.sch
done
for i in {0..15} 
do
   sed "s/R1D$i\"/PC-${j[$i]}\"/" <SP:PC-2.sch >tmp
   mv tmp SP:PC-2.sch
done
for i in {0..15} 
do
   sed "s/R2D$i\"/IA-${j[$i]}\"/" <SP:PC-2.sch >tmp
   mv tmp SP:PC-2.sch
done
for i in {0..15} 
do
   sed "s/R3D$i\"/IB-${j[$i]}\"/" <SP:PC-2.sch >tmp
   mv tmp SP:PC-2.sch
done

