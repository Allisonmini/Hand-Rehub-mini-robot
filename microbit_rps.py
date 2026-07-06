# microbit_rps.py
# ---------------------------------------------------------------
# Flash THIS file onto the micro:bit as the MAIN program, and add
# ssd1306_microbit.py as a second project file (same name).
#
# Easiest way: open https://python.microbit.org, paste this as main.py,
# use "Project files" to add ssd1306_microbit.py, connect by USB, then
# "Send to micro:bit". 
#
# What it does each round:
#   - Reads "<you>:<ai>" from the laptop over USB serial (e.g. "P:R"),
#     where the laptop has already chosen the AI move for the difficulty.
#   - Decides win / lose / tie and keeps a running score.
#   - Shows the AI's move as a big icon, then YOU WIN / YOU LOSE / TIE + score.
#   - Shows a happy/sad/meh face on the LED grid too.
#   - Plays arcade sounds: a start jingle, and win/lose effects (built with loops).
#   - Sends the result text back to the laptop.
#
# Wiring:
#   OLED       VCC->3V, GND->GND, SDA->P20, SCL->P19
#   HC-SR04    VCC->5V (see notes), GND->GND, TRIG->P0, ECHO->P1
#   Green LED  P8  -> 220ohm resistor -> LED(+),  LED(-) -> GND   (win)
#   Red LED    P16 -> 220ohm resistor -> LED(+),  LED(-) -> GND   (lose)
#   Sound      P2 -> headphones or a buzzer -> GND   (micro:bit V2 speaker also plays)
# ---------------------------------------------------------------
from microbit import *
from machine import time_pulse_us
import utime
import music
import ssd1306_microbit as oled

uart.init(baudrate=115200)
oled.init()

MOVES = ["R", "P", "S"]
WORD = {"R": "ROCK", "P": "PAPER", "S": "SCISSORS"}
RESULT_TEXT = {"WIN": "YOU WIN", "LOSE": "YOU LOSE", "TIE": "TIE"}

# --- Ultrasonic trigger (HC-SR04) ---
TRIG = pin0
ECHO = pin1
TRIGGER_CM = 12.7    # 5 inches; hand this close starts a round
REARM_CM = 20        # hand must move back past this before it can trigger again
armed = True         # ready to detect a new approach

# --- Win/Lose LEDs (each via a ~220ohm resistor to GND) ---
GREEN_LED = pin8     # lights up when you win
RED_LED = pin16      # lights up when you lose
GREEN_LED.write_digital(0)
RED_LED.write_digital(0)


# --- Arcade sound (built from loops) ---
# Sound plays on P2 (attach headphones or a buzzer to P2 + GND). On the
# micro:bit V2 the built-in speaker plays it too, so you may hear it with
# nothing attached. P0 is left free for the ultrasonic sensor's TRIG.
AUDIO = pin2
START_REPEATS = 2       # nested loop: how many times to play the whole start tune


def play_start_music():
    """Cheerful arcade start jingle, built from count-controlled loops."""
    music.set_tempo(bpm=180)
    rise = ['c5:2', 'e5:2', 'g5:2']          # a climbing phrase
    tag = ['g5:1', 'c6:3']                   # a little flourish
    for _ in range(START_REPEATS):           # nested loop: play the whole tune twice
        for _ in range(2):                   # count-controlled: play the rise twice
            music.play(rise, pin=AUDIO, wait=True)
        music.play(tag, pin=AUDIO, wait=True)
    music.set_tempo(bpm=120)                 # back to normal for the win/lose sounds


def play_win():
    """Rising 'you win!' arcade sound."""
    for note in ['g5:1', 'c6:1', 'e6:2']:    # notes climb up = happy
        music.play(note, pin=AUDIO, wait=True)


def play_lose():
    """Falling 'aww' arcade sound."""
    for note in ['e5:1', 'c5:1', 'g4:3']:    # notes fall down = sad
        music.play(note, pin=AUDIO, wait=True)


def play_tie():
    """Flat 'meh' arcade sound for a tie (neither up nor down)."""
    for note in ['c5:2', 'c5:2']:            # same pitch = neutral
        music.play(note, pin=AUDIO, wait=True)


def distance_cm():
    """Distance to the nearest object in cm, or 999 if nothing/too far."""
    TRIG.write_digital(0)
    utime.sleep_us(2)
    TRIG.write_digital(1)
    utime.sleep_us(10)
    TRIG.write_digital(0)
    dur = time_pulse_us(ECHO, 1, 30000)   # echo high time, 30ms timeout
    if dur < 0:
        return 999.0
    return dur / 58.0


wins = 0
losses = 0
ties = 0
current_mode = "EASY"     # difficulty sent from the laptop; shown on the OLED


def player_beats_ai(player, ai):
    """True if the player's move beats the micro:bit's move."""
    return (
        (player == "R" and ai == "S")
        or (player == "P" and ai == "R")
        or (player == "S" and ai == "P")
    )


def icon_rock():
    # A closed fist = rock.
    oled.fill_rect(48, 26, 36, 24)                   # hand
    for kx in (54, 63, 72, 81):
        oled.fill_circle(kx, 26, 5)                  # knuckles
    oled.fill_rect(44, 34, 12, 9)                    # thumb
    oled.fill_circle(45, 38, 5)                      # thumb tip
    for cx in (60, 69, 78):
        oled.line(cx, 30, cx, 49, 0)                 # finger creases


def icon_paper():
    # An open hand with five fingers = paper.
    oled.fill_rect(48, 32, 34, 18)                   # palm
    for fx, ftop in ((49, 18), (57, 14), (65, 16), (73, 22)):
        oled.fill_rect(fx, ftop, 7, 36 - ftop)       # finger
        oled.fill_circle(fx + 3, ftop, 3)            # rounded fingertip
    oled.fill_rect(40, 36, 10, 8)                    # thumb
    oled.fill_circle(40, 40, 4)                      # thumb tip
    oled.fill_rect(54, 50, 22, 4)                    # wrist


def icon_scissors():
    # Two ring handles on the left, two blades crossing to the right.
    oled.circle(40, 20, 8)
    oled.circle(40, 44, 8)
    oled.thick_line(47, 24, 92, 44)
    oled.thick_line(47, 40, 92, 20)
    oled.fill_circle(68, 32, 3)        # pivot screw


ICON = {"R": icon_rock, "P": icon_paper, "S": icon_scissors}


def draw(ai, result, mode):
    # 1) Show the AI's move on its own first: title, big icon, and the word.
    oled.clear()
    oled.text_center("AI PLAYED", 0)
    ICON[ai]()                                       # big picture of AI's move
    oled.text_center(WORD[ai], 7)                    # ...and its name (ROCK/PAPER/SCISSORS)
    oled.show()
    sleep(2500)

    # 2) Then reveal the result + running score, still showing what the AI played.
    oled.clear()
    oled.text_center("AI: " + WORD[ai], 0)           # reminder of the AI's move
    oled.text_center(RESULT_TEXT[result], 3)         # YOU WIN / YOU LOSE / TIE
    oled.text_center("MODE: " + mode, 5)             # difficulty
    oled.text_center("W:{} L:{} T:{}".format(wins, losses, ties), 7)
    oled.show()
    # Light the LED and play the arcade sound the moment the WIN/LOSE screen shows.
    GREEN_LED.write_digital(1 if result == "WIN" else 0)
    RED_LED.write_digital(1 if result == "LOSE" else 0)
    if result == "WIN":
        play_win()
    elif result == "LOSE":
        play_lose()
    else:
        play_tie()
    sleep(1300)                                      # keep the result up to read it
    GREEN_LED.write_digital(0)
    RED_LED.write_digital(0)


def play(player, ai, mode):
    """Score one round using the AI move chosen by the laptop, and show it."""
    global wins, losses, ties, current_mode
    current_mode = mode
    if player == ai:
        ties += 1
        result = "TIE"
        face = Image.MEH
    elif player_beats_ai(player, ai):
        wins += 1
        result = "WIN"
        face = Image.HAPPY
    else:
        losses += 1
        result = "LOSE"
        face = Image.SAD

    draw(ai, result, mode)       # draw() lights the win/lose LED with the result
    display.show(face)
    uart.write("{} (AI={}) W{} L{} T{}\n".format(result, ai, wins, losses, ties))
    eyes_react()                 # bring the eyes back after the AI move + result


def draw_eyes(look=0, closed=False):
    """Robot eyes: 'look' shifts both pupils (negative = left); closed = blink."""
    oled.clear()
    for cx in (40, 88):
        if closed:
            oled.fill_rect(cx - 15, 30, 30, 4)   # closed eyelid (blink)
        else:
            oled.circle(cx, 32, 15)              # eye outline
            oled.fill_circle(cx + look, 32, 6)   # pupil, shifted to look around
    oled.show()


def blink_eyes(look):
    """Quick blink: shut the eyes for a moment, then reopen at 'look'."""
    draw_eyes(look, closed=True)
    sleep(120)
    draw_eyes(look, closed=False)


def eyes_react():
    """A quick glance + blink to bring the eyes back after a round result."""
    draw_eyes(-7)                # glance left
    sleep(160)
    draw_eyes(7)                 # glance right
    sleep(160)
    draw_eyes(0)                 # center
    sleep(120)
    blink_eyes(0)               # ...then a blink before revealing the round


def screen(lines):
    """Show up to three centered lines of text (game state screens)."""
    oled.clear()
    for text, row in zip(lines, (1, 3, 5)):
        oled.text_center(text, row)
    oled.show()


def big_center(text, scale=6):
    """Draw text large and centered (used for the big countdown digits)."""
    oled.clear()
    cw = 6 * scale
    x0 = max(0, (128 - len(text) * cw) // 2)
    y0 = max(0, (64 - 7 * scale) // 2)
    for ch in text:
        glyph = oled.FONT.get(ch, oled.FONT[" "])
        for col in range(5):
            bits = glyph[col]
            for row in range(7):
                if bits & (1 << row):
                    oled.fill_rect(x0 + col * scale, y0 + row * scale, scale, scale)
        x0 += cw
    oled.show()


def show_count(text):
    """One countdown step from the laptop: big for a digit, centered for a word,
    with an arcade beep (a higher 'go' tone on THROW!)."""
    if len(text) == 1:
        big_center(text, 6)
    else:
        oled.clear()
        oled.text_center(text, 3)
        oled.show()
    # Beep: same tone for 3 / 2 / 1, a higher and longer tone on THROW!.
    if text == "THROW!":
        music.pitch(1320, 350, pin=AUDIO, wait=True)
    elif text in ("3", "2", "1"):
        music.pitch(660, 150, pin=AUDIO, wait=True)


# Waiting state: alternate the text prompt with animated robot eyes until the
# laptop sends START (which the thumbs-up gesture triggers).
LOOK = (0, -7, -7, 0, 7, 7)     # pupil offsets: center, look left, look right...
PHASE = 2500                    # ms to show text, then ms to show eyes, in WAITING
STEP = 650                      # ms between eye movements
BLINK_EVERY = 5000              # ms between blinks while the eyes are showing

playing = False
prompt = ["GAME", "THUMBS UP TO", "START"]
waiting_text = True             # in WAITING: showing text (True) or the eyes (False)?
eye_idx = 0
next_toggle = running_time() + PHASE
next_anim = running_time()
next_blink = running_time() + BLINK_EVERY
screen(prompt)
display.clear()

buf = ""

while True:
    now = running_time()

    # While WAITING, animate the prompt + robot eyes. While PLAYING, the laptop
    # drives the display (the 3-2-1 countdown and the round results), so we just
    # show whatever it sends.
    if not playing:
        if now >= next_toggle:
            waiting_text = not waiting_text
            next_toggle = now + PHASE
            if waiting_text:
                screen(prompt)
            else:
                next_anim = now
        if not waiting_text and now >= next_anim:
            eye_idx = (eye_idx + 1) % len(LOOK)
            draw_eyes(LOOK[eye_idx])
            next_anim = now + STEP
        if not waiting_text and now >= next_blink:
            blink_eyes(LOOK[eye_idx])
            next_blink = now + BLINK_EVERY

    # Commands from the laptop: state changes, difficulty, and rounds.
    if uart.any():
        buf += str(uart.read(), "utf-8")
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            cmd = line.strip()
            parts = cmd.split(":")
            if cmd == "READY":
                playing = False
                prompt = ["GAME", "THUMBS UP TO", "START"]
                waiting_text = True
                screen(prompt)
                next_toggle = now + PHASE
            elif cmd == "START":
                playing = True
                screen(["GAME", "START"])
                play_start_music()           # arcade start jingle (loops)
            elif cmd == "QUIT":
                playing = False
                prompt = ["GAME QUIT", "THUMBS UP", "TO RESTART"]
                waiting_text = True
                screen(prompt)
                next_toggle = now + PHASE
            elif cmd == "OFF":
                playing = False
                prompt = ["GAME QUIT", "GOODBYE!"]
                waiting_text = True
                screen(prompt)
                next_toggle = now + 3600000  # freeze on goodbye; program has closed
            elif parts[0] == "CD" and len(parts) >= 2:
                show_count(parts[1])             # 3 / 2 / 1 / THROW! from the laptop
            elif parts[0] == "MODE" and len(parts) >= 2:
                current_mode = parts[1]
                screen(["MODE", current_mode])   # confirm the new difficulty
                sleep(1000)
                next_anim = running_time()       # resume eyes promptly
                next_blink = running_time() + BLINK_EVERY
                if not playing:                  # back to the waiting prompt
                    waiting_text = True
                    screen(prompt)
                    next_toggle = running_time() + PHASE
            elif len(parts) >= 2 and parts[0] in MOVES and parts[1] in MOVES:
                m = parts[2] if len(parts) >= 3 else current_mode
                play(parts[0], parts[1], m)

    sleep(50)
