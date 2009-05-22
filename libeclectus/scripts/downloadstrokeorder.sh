#!/bin/bash

if [ ! -d "bw.png" ]
then
  mkdir bw.png
fi
cd bw.png
downcommons.py "Bw.png stroke order images"
cd ..

if [ ! -d "tbw.png" ]
then
  mkdir tbw.png
fi
cd tbw.png
downcommons.py "Tbw.png stroke order images"
cd ..

if [ ! -d "jbw.png" ]
then
  mkdir jbw.png
fi
cd jbw.png
downcommons.py "Jbw.png stroke order images"
cd ..

if [ ! -d "order.gif" ]
then
  mkdir order.gif
fi
cd order.gif
downcommons.py "Order.gif stroke order images"
cd ..

if [ ! -d "torder.gif" ]
then
  mkdir torder.gif
fi
cd torder.gif
downcommons.py "Torder.gif stroke order images"
cd ..

if [ ! -d "jorder.gif" ]
then
  mkdir jorder.gif
fi
cd jorder.gif
downcommons.py "Jorder.gif stroke order images"
cd ..

if [ ! -d "red.png" ]
then
  mkdir red.png
fi
cd red.png
downcommons.py "Red.png stroke order images"
cd ..
#if [ ! -d "tred.png" ]
#then
#  mkdir tred.png
#fi
#cd tred.png
#downcommons.py "Tred.png stroke order images"
#cd ..
#
#if [ ! -d "jred.png" ]
#then
#  mkdir jred.png
#fi
#cd jred.png
#downcommons.py "Jred.png stroke order images"
#cd ..
