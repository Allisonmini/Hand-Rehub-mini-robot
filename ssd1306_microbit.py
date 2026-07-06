# ssd1306_microbit.py
# ---------------------------------------------------------------
# Tiny SSD1306 (128x64 I2C OLED) text driver for the BBC micro:bit.
# No framebuf needed. Add this file to your micro:bit project ALONGSIDE
# microbit_rps.py (in python.microbit.org use the "Project files" panel
# to add a second file with this exact name).
#
# Wiring (use the micro:bit's real I2C pins):
#     OLED VCC -> 3V
#     OLED GND -> GND
#     OLED SDA -> P20
#     OLED SCL -> P19
#
# If you insist on SDA->P19 / SCL->P20, change the init() call below.
# ---------------------------------------------------------------
from microbit import i2c, pin19, pin20, sleep

ADDR = 0x3C          # most 0.96" OLEDs; some are 0x3D
WIDTH = 128
HEIGHT = 64
PAGES = HEIGHT // 8

_buf = bytearray(WIDTH * PAGES)

# 5x7 font, 1 byte per column, bit0 = top row.
FONT = {
    " ": b"\x00\x00\x00\x00\x00",
    "!": b"\x00\x00\x5f\x00\x00",
    "-": b"\x08\x08\x08\x08\x08",
    ":": b"\x00\x36\x36\x00\x00",
    "0": b"\x3e\x51\x49\x45\x3e",
    "1": b"\x00\x42\x7f\x40\x00",
    "2": b"\x42\x61\x51\x49\x46",
    "3": b"\x21\x41\x45\x4b\x31",
    "4": b"\x18\x14\x12\x7f\x10",
    "5": b"\x27\x45\x45\x45\x39",
    "6": b"\x3c\x4a\x49\x49\x30",
    "7": b"\x01\x71\x09\x05\x03",
    "8": b"\x36\x49\x49\x49\x36",
    "9": b"\x06\x49\x49\x29\x1e",
    "A": b"\x7c\x12\x11\x12\x7c",
    "B": b"\x7f\x49\x49\x49\x36",
    "C": b"\x3e\x41\x41\x41\x22",
    "D": b"\x7f\x41\x41\x22\x1c",
    "E": b"\x7f\x49\x49\x49\x41",
    "F": b"\x7f\x09\x09\x09\x01",
    "G": b"\x3e\x41\x49\x49\x7a",
    "H": b"\x7f\x08\x08\x08\x7f",
    "I": b"\x00\x41\x7f\x41\x00",
    "J": b"\x20\x40\x41\x3f\x01",
    "K": b"\x7f\x08\x14\x22\x41",
    "L": b"\x7f\x40\x40\x40\x40",
    "M": b"\x7f\x02\x0c\x02\x7f",
    "N": b"\x7f\x04\x08\x10\x7f",
    "O": b"\x3e\x41\x41\x41\x3e",
    "P": b"\x7f\x09\x09\x09\x06",
    "Q": b"\x3e\x41\x51\x21\x5e",
    "R": b"\x7f\x09\x19\x29\x46",
    "S": b"\x46\x49\x49\x49\x31",
    "T": b"\x01\x01\x7f\x01\x01",
    "U": b"\x3f\x40\x40\x40\x3f",
    "V": b"\x1f\x20\x40\x20\x1f",
    "W": b"\x7f\x20\x18\x20\x7f",
    "X": b"\x63\x14\x08\x14\x63",
    "Y": b"\x07\x08\x70\x08\x07",
    "Z": b"\x61\x51\x49\x45\x43",
}

_INIT = (
    0xAE, 0x20, 0x00, 0xB0, 0xC8, 0x00, 0x10, 0x40,
    0x81, 0x7F, 0xA1, 0xA6, 0xA8, 0x3F, 0xA4, 0xD3,
    0x00, 0xD5, 0x80, 0xD9, 0xF1, 0xDA, 0x12, 0xDB,
    0x40, 0x8D, 0x14, 0xAF,
)


def _cmd(c):
    i2c.write(ADDR, bytes([0x00, c]))


def init():
    # Wired SDA->P20, SCL->P19 (standard micro:bit I2C).
    i2c.init(freq=100000, sda=pin20, scl=pin19)
    sleep(300)                       # let the 2.42" panel power up after reset
    # The bigger OLED sometimes isn't ready on the first try (ENODEV).
    # Retry the init sequence a few times before giving up.
    for _ in range(15):
        try:
            for c in _INIT:
                _cmd(c)
            clear()
            show()
            return
        except OSError:
            sleep(200)


def clear():
    for i in range(len(_buf)):
        _buf[i] = 0


def text(s, x, page):
    """Draw a string at column x, on the given 8-pixel page (0..7)."""
    for ch in s:
        glyph = FONT.get(ch, FONT[" "])
        for col in range(5):
            if 0 <= x < WIDTH:
                _buf[page * WIDTH + x] = glyph[col]
            x += 1
        x += 1  # 1px gap between characters
        if x >= WIDTH:
            break


def text_center(s, page):
    """Draw a string horizontally centered on the given page."""
    x = (WIDTH - len(s) * 6) // 2
    if x < 0:
        x = 0
    text(s, x, page)


# --- simple shape drawing (for the rock / paper / scissors icons) ---
def pixel(x, y, on=1):
    if 0 <= x < WIDTH and 0 <= y < HEIGHT:
        i = (y >> 3) * WIDTH + x
        bit = 1 << (y & 7)
        if on:
            _buf[i] |= bit
        else:
            _buf[i] &= ~bit & 0xFF


def fill_rect(x, y, w, h, on=1):
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            pixel(xx, yy, on)


def rect(x, y, w, h, on=1):
    for xx in range(x, x + w):
        pixel(xx, y, on)
        pixel(xx, y + h - 1, on)
    for yy in range(y, y + h):
        pixel(x, yy, on)
        pixel(x + w - 1, yy, on)


def fill_circle(cx, cy, r, on=1):
    r2 = r * r
    for yy in range(-r, r + 1):
        for xx in range(-r, r + 1):
            if xx * xx + yy * yy <= r2:
                pixel(cx + xx, cy + yy, on)


def circle(cx, cy, r, on=1):
    x = r
    y = 0
    err = 0
    while x >= y:
        for px, py in ((x, y), (y, x), (-x, y), (-y, x),
                       (-x, -y), (-y, -x), (x, -y), (y, -x)):
            pixel(cx + px, cy + py, on)
        y += 1
        if err <= 0:
            err += 2 * y + 1
        else:
            x -= 1
            err -= 2 * x + 1


def line(x0, y0, x1, y1, on=1):
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        pixel(x0, y0, on)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def thick_line(x0, y0, x1, y1, on=1):
    """A 3px-wide line so the scissors blades are visible."""
    line(x0, y0, x1, y1, on)
    line(x0, y0 + 1, x1, y1 + 1, on)
    line(x0, y0 - 1, x1, y1 - 1, on)


def show():
    _cmd(0x21)            # set column address...
    _cmd(0x00)
    _cmd(0x7F)            # ...0 to 127
    _cmd(0x22)            # set page address...
    _cmd(0x00)
    _cmd(PAGES - 1)       # ...0 to 7
    for i in range(0, len(_buf), 16):
        i2c.write(ADDR, bytes([0x40]) + _buf[i:i + 16])
