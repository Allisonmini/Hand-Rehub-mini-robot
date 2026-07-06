# dashboard.py
# ---------------------------------------------------------------
# A small local web dashboard for the RPS rehab game. It answers one
# question for a hand-injury patient: "is my hand getting better?"
#
# Three simple tabs:
#   My Progress  - a big "am I improving?" number + hand-movement trend
#   My Games     - totals, wins/losses, difficulty, recent games
#   Coach Report - a plain-English recovery summary written by Claude
#
# Run:  double-click "Open Dashboard.command"   (or:  python dashboard.py)
#       The dashboard opens automatically at http://127.0.0.1:8000
# ---------------------------------------------------------------
import socket
import threading
import time
import webbrowser

from flask import Flask, jsonify, render_template_string

import rehab_api
import rehab_data

app = Flask(__name__)

PAGE = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Hand Rehab Tracker</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Press+Start+2P&family=VT323&display=swap" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
  <style>
    :root {
      --bg:#160726; --panel:#241043; --panel2:#2f1657;
      --purple:#a855f7; --purple-lt:#c9a4ff; --ink:#ece3ff; --muted:#a68fd0;
      --shadow:#0c0418; --green:#3ddc84; --red:#ff5b6e;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0; background: var(--bg); color: var(--ink);
      font-family: 'VT323', monospace; font-size: 20px;
      background-image:
        linear-gradient(rgba(168,85,247,.06) 1px, transparent 1px),
        linear-gradient(90deg, rgba(168,85,247,.06) 1px, transparent 1px);
      background-size: 24px 24px;
    }
    header { background: var(--purple); color: #12061f; padding: 16px 20px;
             border-bottom: 4px solid var(--shadow);
             display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    header h1 { margin: 0; font-family: 'Press Start 2P', monospace; font-size: 15px;
                letter-spacing: 1px; text-shadow: 2px 2px 0 var(--shadow); }
    header .sub { font-size: 16px; color: #3a1063; margin-top: 6px; letter-spacing: 1px; }
    .reset { font-family: 'Press Start 2P', monospace; font-size: 9px; cursor: pointer;
             background: #12061f; color: #ff6b81; border: 3px solid #ff6b81;
             border-bottom-width: 4px; padding: 9px 11px; }
    .reset:active { transform: translateY(2px); border-bottom-width: 3px; }

    /* Purpose banner: says what this page is for, in plain words. */
    .intro { max-width: 900px; margin: 16px auto 0; padding: 0 20px;
             color: var(--muted); font-size: 18px; line-height: 1.5; }

    .tab-btn.active::before { content: "> "; }
    main { max-width: 900px; margin: 0 auto; padding: 20px; }
    .card { background: var(--panel); border: 4px solid var(--purple);
            box-shadow: 6px 6px 0 var(--shadow); padding: 16px 18px; margin-bottom: 22px; }
    h2 { font-family: 'Press Start 2P', monospace; font-size: 12px; color: var(--purple-lt);
         margin: 0 0 14px; letter-spacing: 1px; }

    /* "Am I improving?" hero. */
    .hero { text-align: center; }
    .big { font-family: 'Press Start 2P', monospace; font-size: 34px; line-height: 1.2;
           margin: 10px 0; color: var(--purple-lt); text-shadow: 0 0 12px rgba(201,164,255,.5); }

    .stats { display: flex; gap: 20px; flex-wrap: wrap; }
    .stat { text-align: center; flex: 1; min-width: 120px; }
    .stat .n { font-family: 'Press Start 2P', monospace; font-size: 18px; color: var(--purple-lt);
               text-shadow: 0 0 8px rgba(201,164,255,.5); }
    .stat .l { font-size: 16px; color: var(--muted); margin-top: 6px; text-transform: uppercase; }
    .pies { display: flex; gap: 20px; flex-wrap: wrap; }
    .pie { flex: 1; min-width: 220px; max-width: 320px; text-align: center; }
    .pie h3 { font-family: 'Press Start 2P', monospace; font-size: 9px; color: var(--muted);
              margin: 0 0 10px; line-height: 1.5; }
    button { font-family: 'Press Start 2P', monospace; font-size: 11px; cursor: pointer;
             background: var(--purple); color: #12061f; border: 0;
             border-bottom: 4px solid var(--shadow); padding: 12px 16px; }
    button:active { transform: translateY(2px); border-bottom-width: 2px; }
    button:disabled { background: #6b4a9a; color: #3a2a55; cursor: default; }
    table { width: 100%; border-collapse: collapse; font-size: 18px; }
    th, td { padding: 7px 8px; border-bottom: 2px solid #3a2360; text-align: left; }
    th { font-family: 'Press Start 2P', monospace; font-size: 9px; color: var(--purple-lt);
         text-transform: uppercase; }
    .report h3 { font-family: 'Press Start 2P', monospace; font-size: 10px; color: var(--purple-lt);
                 margin: 16px 0 6px; }
    .report p { margin: 6px 0; }
    .report ul { margin: 4px 0; }
    .hint { color: var(--muted); font-size: 16px; line-height: 1.5; margin: 10px 0 0; }
    .err { color: #ff6b81; }

    /* Tab bar */
    .tabs { max-width: 900px; margin: 8px auto 0; padding: 14px 20px 0; display: flex;
            gap: 8px; flex-wrap: wrap; }
    .tab-btn { font-family: 'Press Start 2P', monospace; font-size: 10px; cursor: pointer;
               background: var(--panel2); color: var(--muted);
               border: 3px solid var(--purple); border-bottom: none; padding: 12px; }
    .tab-btn.active { background: var(--purple); color: #12061f; }
    .panel { display: none; }
    .panel.active { display: block; }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>HAND REHAB TRACKER</h1>
      <div class="sub">Rock . Paper . Scissors recovery game</div>
    </div>
    <button class="reset" onclick="resetData()">Clear data</button>
  </header>

  <div class="intro">
    Play Rock-Paper-Scissors with your camera. Every round measures how far your hand can
    open and close. This page shows whether your hand movement is improving over time.
  </div>

  <nav class="tabs" id="tabs">
    <button class="tab-btn active" data-tab="progress" onclick="showTab('progress')">My Progress</button>
    <button class="tab-btn" data-tab="games" onclick="showTab('games')">My Games</button>
    <button class="tab-btn" data-tab="report" onclick="showTab('report')">Coach Report</button>
  </nav>

  <main>
    <!-- My Progress: the one thing that matters - am I getting better? -->
    <section class="panel active" id="tab-progress">
      <div class="card hero">
        <h2>Am I improving?</h2>
        <div class="big" id="recoveryBig">-</div>
        <div class="hint" id="recoveryText"></div>
      </div>
      <div class="card">
        <h2>Hand movement over time</h2>
        <canvas id="romChart" height="120"></canvas>
        <p class="hint">Each point is one session. Higher means your hand opens and closes
           more fully - a line that climbs means you are recovering.</p>
      </div>
    </section>

    <!-- My Games: how much you played and how it went. -->
    <section class="panel" id="tab-games">
      <div class="card"><div class="stats" id="stats"></div></div>
      <div class="card">
        <h2>Wins, losses and difficulty</h2>
        <div class="pies">
          <div class="pie"><h3>Results</h3><canvas id="resultsPie"></canvas></div>
          <div class="pie"><h3>Difficulty played</h3><canvas id="modePie"></canvas></div>
        </div>
      </div>
      <div class="card">
        <h2>How open your hand was each round</h2>
        <canvas id="openChart" height="120"></canvas>
        <p class="hint">Green = Paper (open hand), red = Rock (fist), orange = Scissors.</p>
      </div>
      <div class="card">
        <h2>Recent games</h2>
        <div id="history"></div>
      </div>
    </section>

    <!-- Coach Report: plain-English summary written by Claude. -->
    <section class="panel" id="tab-report">
      <div class="card report">
        <h2>Your progress report</h2>
        <p class="hint">A short, friendly summary of your hand recovery - with encouragement
           and simple exercises to try - written for you from your play history.</p>
        <button id="genBtn" onclick="genReport()">Get my report</button>
        <div id="report"></div>
      </div>
    </section>
  </main>

<script>
const WORD = {R: "Rock", P: "Paper", S: "Scissors"};
const MODE_COLOR = {EASY: "#3ddc84", MEDIUM: "#ffb300", HARD: "#ff5b6e"};
const CHARTS = [];   // keep chart instances so we can resize them when a tab opens

// Retro theming applied to every chart.
Chart.defaults.color = "#ece3ff";
Chart.defaults.font.family = "'VT323', monospace";
Chart.defaults.font.size = 16;
Chart.defaults.borderColor = "rgba(168,85,247,.20)";

function showTab(name) {
  document.querySelectorAll(".panel").forEach(p =>
    p.classList.toggle("active", p.id === "tab-" + name));
  document.querySelectorAll(".tab-btn").forEach(b =>
    b.classList.toggle("active", b.dataset.tab === name));
  // Charts created inside a hidden tab render at zero size; fix them on show.
  CHARTS.forEach(c => c.resize());
}

async function resetData() {
  if (!confirm("Erase ALL recorded games? This cannot be undone.")) return;
  await fetch("/api/reset", { method: "POST" });
  location.reload();   // reload with the now-empty data
}

async function load() {
  const res = await fetch("/api/history");
  const data = await res.json();
  renderProgress(data.stats);
  renderStats(data.stats, data.history);
  renderCharts(data.stats, data.history);
  renderPies(data.history);
  renderHistory(data.history);
}

// "Am I improving?" headline: one big number in plain words.
function renderProgress(stats) {
  const chg = stats.range_of_motion_change_pct;
  const big = document.getElementById("recoveryBig");
  const txt = document.getElementById("recoveryText");
  if (chg === null || chg === undefined) {
    big.textContent = "-";
    big.style.color = "var(--muted)";
    txt.textContent = stats.total_sessions >= 2
      ? "Not enough clear hand data yet. Play a few rounds making full fists and fully open hands."
      : "Play at least two sessions (for example on two different days) to see how much your hand movement has improved.";
    return;
  }
  big.textContent = (chg > 0 ? "+" : "") + chg + "%";
  big.style.color = chg > 0 ? "var(--green)" : (chg < 0 ? "var(--red)" : "var(--purple-lt)");
  txt.textContent = chg > 0
    ? "Your hand opens and closes " + chg + "% more fully than your first session. Great progress - keep it up!"
    : chg < 0
    ? "A little lower than your first session. That is normal from day to day - keep playing and watch the overall trend."
    : "About the same as your first session. Keep playing to build up your range of motion.";
}

function renderStats(stats, history) {
  const mode = history.length ? history[history.length - 1].mode : "-";
  const color = MODE_COLOR[mode] || "#888";
  let wins = 0;
  for (const r of history) if (r.result === "WIN") wins++;
  document.getElementById("stats").innerHTML = `
    <div class="stat"><div class="n">${stats.total_rounds}</div><div class="l">rounds played</div></div>
    <div class="stat"><div class="n">${stats.total_sessions}</div><div class="l">sessions</div></div>
    <div class="stat"><div class="n">${wins}</div><div class="l">wins</div></div>
    <div class="stat"><div class="n" style="color:${color}">${mode}</div><div class="l">current difficulty</div></div>`;
}

function tally(history, key) {
  const counts = {};
  for (const r of history) { const k = r[key] || "?"; counts[k] = (counts[k] || 0) + 1; }
  return counts;
}

function renderPies(history) {
  const pieOpts = { plugins: { legend: { position: "bottom", labels: { boxWidth: 14 } } } };

  const res = tally(history, "result");
  CHARTS.push(new Chart(document.getElementById("resultsPie"), {
    type: "pie",
    data: { labels: ["Win", "Lose", "Tie"], datasets: [{
      data: [res.WIN || 0, res.LOSE || 0, res.TIE || 0],
      backgroundColor: ["#3ddc84", "#ff5b6e", "#8b7fb0"] }] },
    options: pieOpts
  }));

  const modes = tally(history, "mode");
  CHARTS.push(new Chart(document.getElementById("modePie"), {
    type: "pie",
    data: { labels: ["Easy", "Medium", "Hard"], datasets: [{
      data: [modes.EASY || 0, modes.MEDIUM || 0, modes.HARD || 0],
      backgroundColor: [MODE_COLOR.EASY, MODE_COLOR.MEDIUM, MODE_COLOR.HARD] }] },
    options: pieOpts
  }));
}

function renderCharts(stats, history) {
  const labels = stats.sessions.map((s, i) => "Session " + (i + 1));
  CHARTS.push(new Chart(document.getElementById("romChart"), {
    type: "line",
    data: { labels, datasets: [{
      label: "Hand movement", data: stats.sessions.map(s => s.range_of_motion),
      borderColor: "#c9a4ff", backgroundColor: "rgba(168,85,247,.20)", tension: .3, fill: true }] },
    options: { plugins: { legend: { display: false } } }
  }));

  const idx = history.map((_, i) => i + 1);
  CHARTS.push(new Chart(document.getElementById("openChart"), {
    type: "line",
    data: { labels: idx, datasets: [{
      label: "Openness", data: history.map(r => r.openness),
      borderColor: "#3ddc84", backgroundColor: "rgba(61,220,132,.14)", tension: .2,
      pointBackgroundColor: history.map(r => r.gesture === "Rock" ? "#ff5b6e"
        : r.gesture === "Paper" ? "#3ddc84" : "#ffb300") }] },
    options: { plugins: { legend: { display: false } },
               scales: { x: { title: { display: true, text: "round" } } } }
  }));
}

function renderHistory(history) {
  const box = document.getElementById("history");
  if (!history.length) {
    box.innerHTML = '<p class="hint">No games yet. Open the RPS game, turn on your camera, ' +
      'and play a few rounds - they will show up here.</p>';
    return;
  }
  const rows = history.slice().reverse().slice(0, 40).map(r => `
    <tr><td>${r.time.replace("T", " ")}</td>
    <td style="color:${MODE_COLOR[r.mode] || '#888'}">${r.mode}</td>
    <td>${WORD[r.player] || r.gesture}</td>
    <td>${WORD[r.ai] || r.ai}</td>
    <td>${r.result}</td></tr>`).join("");
  box.innerHTML = `<table>
    <tr><th>Time</th><th>Difficulty</th><th>You</th><th>Robot</th><th>Result</th></tr>
    ${rows}</table>`;
}

async function genReport() {
  const btn = document.getElementById("genBtn");
  const out = document.getElementById("report");
  btn.disabled = true; out.innerHTML = '<p class="hint">Writing your report&hellip;</p>';
  try {
    const res = await fetch("/api/report", { method: "POST" });
    const data = await res.json();
    if (!data.ok) { out.innerHTML = '<p class="err">' + data.error + '</p>'; return; }
    const r = data.report;
    out.innerHTML = `
      <h3>How you're doing</h3><p>${r.summary}</p>
      <h3>Your improvement (${r.improvement_percent > 0 ? "+" : ""}${r.improvement_percent}%)</h3>
      <p>${r.improvement}</p>
      <h3>Keep going</h3><p>${r.encouragement}</p>
      <h3>Exercises to try</h3>
      <ul>${r.exercises.map(e => "<li>" + e + "</li>").join("")}</ul>`;
  } catch (e) {
    out.innerHTML = '<p class="err">' + e + '</p>';
  } finally { btn.disabled = false; }
}

load();
</script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(PAGE)


@app.route("/api/history")
def api_history():
    return jsonify({
        "history": rehab_data.load_history(),
        "stats": rehab_data.build_stats(),
    })


@app.route("/api/reset", methods=["POST"])
def api_reset():
    rehab_data.clear_history()
    return jsonify({"ok": True})


@app.route("/api/report", methods=["POST"])
def api_report():
    try:
        return jsonify({"ok": True, "report": rehab_api.generate_report()})
    except Exception as exc:  # surface auth / no-data errors to the page
        return jsonify({"ok": False, "error": str(exc)}), 500


# Port 8000 (not 5000): macOS AirPlay Receiver occupies 5000 and returns 403.
PORT = 8000
URL = "http://127.0.0.1:{}".format(PORT)


def _port_in_use(port):
    """True if something is already listening on the port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def _open_browser():
    """Open the dashboard once the server is accepting connections."""
    for _ in range(40):                 # wait up to ~8s for Flask to come up
        if _port_in_use(PORT):
            break
        time.sleep(0.2)
    webbrowser.open(URL)


if __name__ == "__main__":
    if _port_in_use(PORT):
        # Already running (e.g. launcher double-clicked twice) - just open it.
        print("Dashboard already running - opening", URL)
        webbrowser.open(URL)
    else:
        print("=" * 46)
        print("  HAND REHAB TRACKER")
        print("  Opening in your browser:", URL)
        print("  Keep this window open. Press Ctrl-C to stop.")
        print("=" * 46)
        # Open the browser from a side thread so it fires after the server is up.
        threading.Thread(target=_open_browser, daemon=True).start()
        app.run(port=PORT, use_reloader=False)
