# game.py
# ---------------------------------------------------------------
# Rock-Paper-Scissors: you vs. the micro:bit.
#
#   1. The webcam + MediaPipe detect your hand gesture.
#   2. Watch the 3-2-1 countdown, then throw rock/paper/scissors on THROW!.
#   3. The laptop picks the AI's move based on the difficulty mode, then
#      sends "<you>:<ai>" to the micro:bit, which scores it and shows the
#      result on the OLED. The result is sent back and printed here.
#   4. Difficulty: press E = Easy, M = Medium, H = Hard. Press Q to quit.
#
# Difficulty:
#   Easy   - AI plays randomly.
#   Medium - AI counters its prediction of your next move ~50% of the time.
#   Hard   - AI always counters its prediction (Markov model of your history).
#
# Before running: flash microbit_rps.py onto the micro:bit and plug it
# in by USB. Install deps with:  pip install -r requirements.txt
# ---------------------------------------------------------------
import random
import time

import cv2
import serial
import serial.tools.list_ports

import gesture       # reuse the detection functions + the mediapipe "hands" object
import rehab_data    # persist play history + hand-movement metrics

# micro:bit's USB vendor id (ARM mbed). Used to auto-find the serial port.
MICROBIT_VID = 0x0D28

GESTURE_TO_LETTER = {"Rock": "R", "Paper": "P", "Scissors": "S"}
MOVES = ["R", "P", "S"]
COUNTER = {"R": "P", "P": "S", "S": "R"}   # COUNTER[x] beats x
BEATS = {"R": "S", "P": "R", "S": "P"}     # BEATS[x] is the move x defeats
MODES = ["EASY", "MEDIUM", "HARD"]

# In HARD mode the AI counters your ACTUAL move this fraction of the time (the
# rest it plays randomly), so winning is possible but rare — "barely winnable".
HARD_WIN_BLOCK = 0.9


class Predictor:
    """Order-1 Markov model: learns which move tends to follow which."""

    def __init__(self):
        self.history = []
        self.trans = {m: {"R": 0, "P": 0, "S": 0} for m in MOVES}
        self.freq = {"R": 0, "P": 0, "S": 0}

    def record(self, move):
        if self.history:
            self.trans[self.history[-1]][move] += 1
        self.freq[move] += 1
        self.history.append(move)

    def predict_next(self):
        # Most likely move after the last one the player made.
        if self.history:
            row = self.trans[self.history[-1]]
            best = max(row, key=row.get)
            if row[best] > 0:
                return best
        # Fall back to the player's overall favourite, else random.
        if sum(self.freq.values()) > 0:
            return max(self.freq, key=self.freq.get)
        return random.choice(MOVES)

    def ai_move(self, mode, player=None):
        """Choose the AI's move for the given difficulty.

        EASY   - random.
        MEDIUM - counters its prediction of your next move ~half the time.
        HARD   - nearly unbeatable: usually counters your ACTUAL move, with a
                 small chance of a random move so a win is still possible.
        """
        if mode == "EASY":
            return random.choice(MOVES)
        if mode == "HARD":
            if player is not None and random.random() < HARD_WIN_BLOCK:
                return COUNTER[player]          # beats your move -> you lose
            return random.choice(MOVES)
        # MEDIUM
        counter = COUNTER[self.predict_next()]
        if random.random() < 0.5:
            return random.choice(MOVES)
        return counter


def find_microbit_port():
    """Return the serial device path for the connected micro:bit, or None."""
    for port in serial.tools.list_ports.comports():
        if port.vid == MICROBIT_VID:
            return port.device
    return None


def open_camera(retries=80, delay=0.25):
    """Open the webcam, retrying so macOS has time to grant camera permission.

    On the first launch (especially from the RPS Game app) macOS shows an
    "allow camera access" prompt, and the first open fails while it is still
    pending. Retrying for ~20s lets the game start the moment you click Allow.
    """
    for _ in range(retries):
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            ok, _ = cap.read()
            if ok:
                return cap
        cap.release()
        time.sleep(delay)
    return None


def main():
    port = find_microbit_port()
    if port is None:
        # No micro:bit? Run webcam-only: you still play (hold a gesture or press
        # SPACE), rounds are scored + recorded, just without the OLED display.
        print("micro:bit not found - running in webcam-only mode.")
        print("Hold a gesture or press SPACE to play; press Q to quit.")
        ser = None
    else:
        print("Connecting to micro:bit on", port)
        ser = serial.Serial(port, 115200, timeout=0.1)

    cap = open_camera()
    if cap is None:
        print("Could not open the camera.")
        print("Allow camera access in System Settings > Privacy & Security > Camera")
        print("(turn on 'RPS Game' or 'Terminal'), then start the game again.")
        if ser:
            ser.close()
        return
    last_result = ""
    predictor = Predictor()
    mode = "EASY"

    # Seed the predictor with moves from past sessions so it keeps learning
    # the player's habits across runs, not just within this one.
    for past in rehab_data.load_history():
        if past.get("player") in MOVES:
            predictor.record(past["player"])

    # 3-2-1-THROW countdown (arcade rounds). The laptop drives the timing, so the
    # count shows on the camera window, and each step is mirrored to the OLED.
    COUNT_STEPS = [("GET READY", 0.9), ("3", 0.8), ("2", 0.8), ("1", 0.8), ("THROW!", 1.6)]
    START_PAUSE = 3.2           # let the START jingle finish before the first countdown
    RESULT_PAUSE = 5.5          # let the micro:bit show the AI move + result
    counting = False            # True while a 3-2-1 countdown is running
    cd_step = 0                 # index into COUNT_STEPS
    cd_step_end = 0.0           # time the current step ends
    cd_captured = False         # already grabbed the throw this countdown?
    next_round_at = 0.0         # when to begin the next countdown (0 = not scheduled)
    stable_start = None         # when THROW! began (the round's reaction time)

    # Game state: WAITING (thumbs-up to start) or PLAYING. Thumbs down quits
    # back to WAITING; the camera stays on so thumbs-up can restart it.
    state = "WAITING"
    status = "THUMBS UP TO START"   # shown on the webcam window
    CONTROL_HOLD = 12               # frames (~1s) to confirm a start/quit gesture
    control_stable = None
    control_count = 0
    control_locked = False          # wait for the hand to leave before acting again

    def send(cmd):
        if ser:
            ser.write((cmd + "\n").encode())

    def set_state(new_state):
        """Switch WAITING <-> PLAYING and tell the OLED what to show."""
        nonlocal state, status, counting, cd_captured, next_round_at
        state = new_state
        counting = False
        cd_captured = False
        if new_state == "PLAYING":
            status = "PLAYING - thumbs down to quit"
            send("START")
            next_round_at = time.time() + START_PAUSE   # first countdown after the jingle
            print("GAME START")
        else:
            status = "GAME QUIT - thumbs up to restart"
            send("QUIT")
            next_round_at = 0.0
            print("GAME QUIT")

    send("READY")                   # OLED shows the start prompt

    def play_round(player_gesture, metrics):
        """Pick the AI move, send + record the round. Returns True if a clear
        move was played, False if it wasn't a clear rock/paper/scissors."""
        nonlocal last_result
        if player_gesture not in GESTURE_TO_LETTER:
            last_result = "No clear move - try again"
            return False
        player = GESTURE_TO_LETTER[player_gesture]
        ai = predictor.ai_move(mode, player)   # HARD counters your actual move
        predictor.record(player)
        if ser:
            ser.write((player + ":" + ai + ":" + mode + "\n").encode())

        # Score it here too, so we can save the result with the hand metrics.
        result = "TIE" if player == ai else ("WIN" if BEATS[player] == ai else "LOSE")
        hold = time.time() - stable_start if stable_start else 0.0
        rehab_data.record_round(player, ai, result, mode, player_gesture,
                                metrics, hold, clear=True)
        print("Round:", player, "vs", ai, "(", mode, ") ->", result)
        return True

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = gesture.hands.process(rgb)

        current = "No Hand"
        current_metrics = None
        control = None
        if result.multi_hand_landmarks:
            for hand in result.multi_hand_landmarks:
                gesture.mp_draw.draw_landmarks(
                    frame, hand, gesture.mp_hands.HAND_CONNECTIONS
                )
                # A thumbs-up/down control gesture takes priority over R/P/S.
                control = gesture.classify_control(hand.landmark)
                if control is None:
                    fingers = gesture.get_finger_states(hand.landmark)
                    current = gesture.classify_gesture(fingers)
                    current_metrics = gesture.hand_metrics(hand.landmark)

        # Thumbs up / down (held ~1s) start or quit the game.
        if control is not None and control == control_stable:
            control_count += 1
        else:
            control_stable = control
            control_count = 1 if control else 0
        if control is None:
            control_locked = False                  # hand left; ready to act again
        elif control_count >= CONTROL_HOLD and not control_locked:
            if control == "ThumbsUp" and state == "WAITING":
                set_state("PLAYING")
            elif control == "ThumbsDown" and state == "PLAYING":
                set_state("WAITING")
            control_locked = True

        # 3-2-1-THROW countdown (only while PLAYING), shown on the camera + OLED.
        countdown_text = ""
        if state == "PLAYING":
            now = time.time()
            if not counting and next_round_at and now >= next_round_at:
                # Start a new countdown.
                counting = True
                cd_step = 0
                cd_step_end = now + COUNT_STEPS[0][1]
                cd_captured = False
                next_round_at = 0.0
                send("CD:" + COUNT_STEPS[0][0])
            elif counting and now >= cd_step_end:
                cd_step += 1
                if cd_step < len(COUNT_STEPS):
                    cd_step_end = now + COUNT_STEPS[cd_step][1]
                    send("CD:" + COUNT_STEPS[cd_step][0])
                    if COUNT_STEPS[cd_step][0] == "THROW!":
                        stable_start = now          # start timing the throw
                else:
                    # THROW! window ended with no clear move: take whatever's there.
                    counting = False
                    if not cd_captured:
                        if play_round(current, current_metrics):
                            next_round_at = time.time() + RESULT_PAUSE
                        else:
                            next_round_at = time.time() + 1.2   # missed; retry soon

            if counting:
                countdown_text = COUNT_STEPS[cd_step][0]
                # As soon as a clear move shows during THROW!, grab it.
                if countdown_text == "THROW!" and not cd_captured \
                        and current in GESTURE_TO_LETTER:
                    play_round(current, current_metrics)
                    cd_captured = True
                    counting = False
                    next_round_at = time.time() + RESULT_PAUSE

        # Read messages the micro:bit echoes back (the result text).
        if ser and ser.in_waiting:
            line = ser.readline().decode(errors="ignore").strip()
            if line and line != "GO":
                last_result = line

        # On-screen overlay.
        cv2.putText(frame, status, (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
        cv2.putText(frame, f"You: {current}", (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 255, 0), 3)
        cv2.putText(frame, f"Mode: {mode}", (10, 130),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.putText(frame, "Thumbs UP=start  Thumbs DOWN=quit  E/M/H=mode  Q/Esc=exit", (10, 162),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2)
        # Thumbs up/down hold progress.
        if control and 0 < control_count < CONTROL_HOLD:
            label = "Starting" if control == "ThumbsUp" else "Quitting"
            cv2.putText(frame, label + "... " + "#" * control_count, (10, 195),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
        # Big 3-2-1-THROW countdown in the centre of the screen.
        if countdown_text:
            scale = 5.0 if countdown_text in ("1", "2", "3") else 2.2
            color = (0, 255, 0) if countdown_text == "THROW!" else (0, 215, 255)
            (tw, th), _ = cv2.getTextSize(countdown_text, cv2.FONT_HERSHEY_SIMPLEX, scale, 6)
            cx = max((frame.shape[1] - tw) // 2, 10)
            cy = (frame.shape[0] + th) // 2
            cv2.putText(frame, countdown_text, (cx, cy),
                        cv2.FONT_HERSHEY_SIMPLEX, scale, color, 6)
        if last_result:
            cv2.putText(frame, last_result, (10, 460),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 200, 255), 2)

        cv2.imshow("RPS vs micro:bit", frame)

        # Stop if the window's close (X) button was clicked.
        if cv2.getWindowProperty("RPS vs micro:bit", cv2.WND_PROP_VISIBLE) < 1:
            break

        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):        # 'q' or the Esc key
            break
        elif key == ord(" "):
            if state == "PLAYING":            # manual throw (skip the wait)
                if play_round(current, current_metrics):
                    counting = False
                    next_round_at = time.time() + RESULT_PAUSE
        elif key in (ord("e"), ord("m"), ord("h")):
            mode = {"e": "EASY", "m": "MEDIUM", "h": "HARD"}[chr(key)]
            if ser:
                ser.write(("MODE:" + mode + "\n").encode())

    if ser:
        send("OFF")          # tell the OLED the program is shutting down
        ser.flush()
        time.sleep(0.2)      # let the bytes transmit before we close the port

    cap.release()
    cv2.destroyAllWindows()
    if ser:
        ser.close()


if __name__ == "__main__":
    main()
