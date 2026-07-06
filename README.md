# Hand-Rehab Mini Robot — Rock, Paper, Scissors

A Rock-Paper-Scissors game you play against a **micro:bit robot** using only your
hand in front of a webcam — designed to make **hand-injury physical therapy** fun.

Every round quietly measures how fully you can open and close your hand
(your *range of motion*), saves it, and turns it into an encouraging, AI-written
progress report so you can watch your recovery improve over time.

---

## 🎥 Demo & Presentation

- **Product demo video:** 
- **Presentation slides:**[Presentation for Capstone project (PRIME)-2.pdf](https://github.com/user-attachments/files/29715768/Presentation.for.Capstone.project.PRIME.-2.pdf)


<!-- Tip: drag a video file into a GitHub issue/README edit box to get a hosted link,
     or paste a YouTube / Google Drive / Canva link above. -->

---

## ✨ What it does

- 👋 **Play with your hand** — a webcam + MediaPipe read your gesture; no controller.
- 🤖 **The micro:bit is your opponent** — it shows the AI's move, a happy/sad face,
  win/lose LEDs, a running score, and arcade sound effects on an OLED screen.
- ⏱️ **3-2-1-THROW countdown** so a round is only captured on "THROW!", not while
  your hand is just resting.
- 🎚️ **Three difficulty modes** — Easy (random), Medium (predicts you ~half the time),
  Hard (a Markov model that's nearly unbeatable).
- 🩺 **Rehab tracking** — each round records how far you extended/curled your hand.
- 📊 **Dashboard** — charts of your progress across sessions.
- 🧠 **AI coach** — Claude reads your history and writes a warm, specific progress report.

---

## 🕹️ How to play

1. Hold a **thumbs-up** to the camera (~1 second) to start the game.
2. Watch the **3 · 2 · 1 · THROW!** countdown.
3. On **THROW!**, make **Rock** (fist), **Paper** (open hand), or **Scissors**.
4. The micro:bit reveals its move, scores the round, and shows the result.
5. Hold a **thumbs-down** to quit back to the start screen.

**Keyboard shortcuts** (on the camera window): `E` = Easy · `M` = Medium ·
`H` = Hard · `SPACE` = throw now · `Q` / `Esc` = quit.

> 💡 Keep your **whole hand — including your wrist — inside the camera frame** for
> the most accurate reading.

---

## 🧩 How it works

```
  Your hand ──► Webcam + MediaPipe ──► game.py ──► picks the AI move
                                          │
                        USB serial "P:R"  ▼
                                     micro:bit (OLED, LEDs, sound, score)
                                          │
              each round's hand metrics   ▼
                                     rehab_data.py ──► data/history.json
                                          │
                        ┌─────────────────┴─────────────────┐
                        ▼                                     ▼
                   dashboard.py (charts)            rehab_api.py ──► Claude ──► progress report
```

| File | Role |
|------|------|
| `game.py` | Main laptop program: webcam, countdown, AI opponent, talks to the micro:bit |
| `gesture.py` | MediaPipe hand detection + range-of-motion metrics |
| `microbit_rps.py` | Runs **on the micro:bit**: OLED display, LEDs, sounds, scoring |
| `ssd1306_microbit.py` | OLED display driver (second file on the micro:bit) |
| `rehab_data.py` | Saves every round and computes progress stats |
| `rehab_api.py` | Sends stats to Claude and gets back a plain-English rehab report |
| `dashboard.py` | Flask web dashboard with charts and the AI report button |

---

## 🔌 Hardware

- BBC **micro:bit** (V2 recommended — it has a built-in speaker)
- **SSD1306 OLED** display (I²C)
- 2 × LEDs (green = win, red = lose) with ~220 Ω resistors
- **HC-SR04** ultrasonic sensor (optional gesture trigger)
- A webcam (your laptop's built-in camera is fine)

**Wiring (micro:bit pins):**

| Part | Connection |
|------|-----------|
| OLED | VCC→3V, GND→GND, SDA→P20, SCL→P19 |
| HC-SR04 | VCC→5V, GND→GND, TRIG→P0, ECHO→P1 |
| Green LED (win) | P8 → 220 Ω → LED → GND |
| Red LED (lose) | P16 → 220 Ω → LED → GND |
| Sound | P2 → buzzer/headphones → GND |

---

## 🚀 Setup

### 1. Flash the micro:bit
Open **https://python.microbit.org**, paste in `microbit_rps.py` as the main file,
add `ssd1306_microbit.py` as a second project file, connect by USB, and click
**Send to micro:bit**.

### 2. Install the laptop dependencies
```bash
pip install -r requirements.txt
```

### 3. Add your Anthropic API key (only needed for the AI report)
```bash
cp .env.example .env
# then edit .env and paste your key from https://console.anthropic.com
```

### 4. Run the game
```bash
python game.py
```
> No micro:bit? It still runs in **webcam-only mode** — you play, rounds are scored
> and recorded, just without the OLED display.

### 5. Open the dashboard
```bash
python dashboard.py
```
Then visit **http://localhost:8000** to see your charts and generate an AI progress report.

---

## 🛠️ Built with

Python · OpenCV · MediaPipe · MicroPython · Flask · Chart.js · Anthropic Claude API

---

## 📄 Notes

- This project is a motivational rehab aid, **not** a medical device, and the AI coach
  does not give medical diagnoses.




