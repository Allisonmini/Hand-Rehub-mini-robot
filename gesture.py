import math

import cv2
import mediapipe as mp

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

hands = mp_hands.Hands(
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

def get_finger_states(landmarks):
    """Returns which fingers are up [thumb, index, middle, ring, pinky]"""
    fingers = []
    
    # Thumb (compares x position since thumb goes sideways)
    if landmarks[4].x < landmarks[3].x:
        fingers.append(1)  # up
    else:
        fingers.append(0)  # down
    
    # Index, Middle, Ring, Pinky
    # Tip landmark is higher (smaller y) than base = finger is up
    tip_ids = [8, 12, 16, 20]
    base_ids = [6, 10, 14, 18]
    
    for tip, base in zip(tip_ids, base_ids):
        if landmarks[tip].y < landmarks[base].y:
            fingers.append(1)  # up
        else:
            fingers.append(0)  # down
    
    return fingers  # [thumb, index, middle, ring, pinky]


def classify_gesture(fingers):
    """Classify Rock, Paper, Scissors from finger states"""
    
    # Rock = all fingers down
    if fingers == [0, 0, 0, 0, 0]:
        return "Rock"
    
    # Paper = all fingers up
    elif fingers == [1, 1, 1, 1, 1]:
        return "Paper"
    
    # Scissors = index and middle up only
    elif fingers[1] == 1 and fingers[2] == 1 and fingers[3] == 0 and fingers[4] == 0:
        return "Scissors"
    
    else:
        return "Unknown"


def classify_control(landmarks):
    """Detect the thumbs-up / thumbs-down control gestures.

    Returns "ThumbsUp", "ThumbsDown", or None. These start and quit the game.
    Both need the four fingers curled into a fist with the thumb sticking
    clearly up or down, so they don't clash with Rock/Paper/Scissors. The
    thumb must be well past the index knuckle (by a fraction of hand size) so
    an ordinary fist (Rock) isn't mistaken for a thumbs gesture.
    """
    tips = [8, 12, 16, 20]
    pips = [6, 10, 14, 18]
    fingers_curled = all(landmarks[t].y > landmarks[p].y for t, p in zip(tips, pips))
    if not fingers_curled:
        return None

    scale = _dist(landmarks[0], landmarks[9]) or 1e-6   # wrist -> middle knuckle
    thumb_tip = landmarks[4]
    thumb_mcp = landmarks[2]
    index_mcp = landmarks[5]
    margin = 0.35 * scale

    if thumb_tip.y < thumb_mcp.y and (index_mcp.y - thumb_tip.y) > margin:
        return "ThumbsUp"
    if thumb_tip.y > thumb_mcp.y and (thumb_tip.y - index_mcp.y) > margin:
        return "ThumbsDown"
    return None


# --- Range-of-motion metrics (the rehab signal) --------------------------
# MediaPipe hand landmarks we care about: the wrist, each fingertip, and the
# middle-finger MCP (base) knuckle, which we use to scale everything so the
# numbers don't depend on how far the hand is from the camera.
_WRIST = 0
_MIDDLE_MCP = 9
_TIP_IDS = [4, 8, 12, 16, 20]        # thumb, index, middle, ring, pinky tips


def _dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def hand_metrics(landmarks):
    """How fully the hand is opened, from MediaPipe landmarks.

    For a hand-injury patient the key thing to measure is range of motion:
    how far each fingertip is from the wrist (extended vs. curled). We divide
    by hand size (wrist -> middle knuckle) so the value is the same whether
    the hand is near or far from the webcam.

    Returns:
      finger_ext : list of 5 extension ratios [thumb, index, middle, ring, pinky]
                   (higher = more extended)
      openness   : mean extension of the four fingers (ignores thumb)
      spread     : thumb-to-index-tip distance / hand size (thumb abduction)
    """
    scale = _dist(landmarks[_WRIST], landmarks[_MIDDLE_MCP]) or 1e-6
    ext = [_dist(landmarks[tip], landmarks[_WRIST]) / scale for tip in _TIP_IDS]
    openness = sum(ext[1:]) / 4.0                    # index..pinky only
    spread = _dist(landmarks[4], landmarks[8]) / scale
    return {
        "finger_ext": [round(e, 3) for e in ext],
        "openness": round(openness, 3),
        "spread": round(spread, 3),
    }


if __name__ == "__main__":
    cap = cv2.VideoCapture(0)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb)

        gesture = "No Hand"

        if result.multi_hand_landmarks:
            for hand in result.multi_hand_landmarks:
                mp_draw.draw_landmarks(frame, hand, mp_hands.HAND_CONNECTIONS)

                landmarks = hand.landmark
                fingers = get_finger_states(landmarks)
                gesture = classify_gesture(fingers)

        # Display gesture on screen
        cv2.putText(frame, f"Gesture: {gesture}", (10, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)

        cv2.imshow("Gesture Detection", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()