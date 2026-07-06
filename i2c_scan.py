# i2c_scan.py  -- diagnostic only
# Flash this ALONE (no other files). It checks both wire orders and shows
# ONE big letter on the red LED grid so it's easy to read:
#   A = OLED answers with SDA->P20, SCL->P19
#   B = OLED answers with SDA->P19, SCL->P20
#   X = nothing answered (power / ground / loose wire / RES held low)
from microbit import *


def found_on(sda, scl):
    i2c.init(freq=100000, sda=sda, scl=scl)
    for addr in range(0x08, 0x78):
        try:
            i2c.write(addr, b"\x00")
            return True
        except OSError:
            pass
    return False


while True:
    if found_on(pin20, pin19):
        display.show("A")
    elif found_on(pin19, pin20):
        display.show("B")
    else:
        display.show("X")
    sleep(800)
