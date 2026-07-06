# ultrasonic_test.py  -- diagnostic only
# Flash this as the MAIN file by itself (no OLED needed) to test the HC-SR04.
#
# Wiring:  VCC->5V (or 3V for HC-SR04P), GND->GND, TRIG->P0, ECHO->P1
#
# What you should see on the LED grid:
#   - Numbers that change as you move your hand closer/farther = sensor WORKS.
#   - Always "X" (or always the same big number) = sensor NOT responding
#     (check power, wiring, or TRIG/ECHO swapped).
from microbit import *
from machine import time_pulse_us
import utime

TRIG = pin0
ECHO = pin1


def distance_cm():
    TRIG.write_digital(0)
    utime.sleep_us(2)
    TRIG.write_digital(1)
    utime.sleep_us(10)
    TRIG.write_digital(0)
    dur = time_pulse_us(ECHO, 1, 30000)
    if dur < 0:
        return -1
    return dur / 58.0


while True:
    d = distance_cm()
    print(d)                 # shows in the serial panel
    if d < 0:
        display.show("X")    # no echo received
    else:
        display.scroll(str(int(d)))   # distance in cm
    sleep(300)
