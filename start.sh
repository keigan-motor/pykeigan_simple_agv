#!/bin/sh
cd /home/pi/Desktop/pykeigan_simple_agv/
lxterminal -e python3 picam_line_tracer_hsv.py
lxterminal -e python3 shutdown.py