import requests
import time
import os
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from flask import Flask, request, render_template_string, send_from_directory
import threading
import re

# -------------------------------
# Chat-Tracking-Konfiguration
# -------------------------------
WELTEN = [f"https://welt{i}.freewar.de/freewar/internal/chattext.php" for i in range(1, 15)]
LAST_LINES = {i: set() for i in range(1, 15)}
LAST_GLOBAL_LINES = set()

def extract_chat_lines(html):
    soup = BeautifulSoup(html, "html.parser")
    p_tags = soup.find_all("p")
    lines = [p.get_text(separator=" ", strip=True) for p in p_tags if p.get_text(strip=True)]
    return [line for line in lines if not line.startswith("Automatische Mitteilung:")]

def is_global_chat(line):
    return any(keyword in line for keyword in [
        "(Welt 1):", "(Welt 2):", "(Welt 3):", "(Welt 4):", "(Welt 5):",
        "(Welt 6):", "(Welt 7):", "(Welt 8):", "(Welt 9):", "(Welt 10):",
        "(Welt 11):", "(Welt 12):", "(Welt 13):", "(Welt 14):",
        "(Chaos-Welt)", "(AF):", "(RP):"
    ])

def format_message(message):
    if "schreit:" in message:
        return f"<span class='shout'>{message}</span><br>"
    return f"{message}<br>"

def save_lines(filename, lines):
    today_str = datetime.now().strftime("%d.%m.%Y")
    date_header = f"<span class='datestamp'>📅 {today_str}</span><br>\n"
    need_date_header = True

    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            content = f.read()
            if date_header.strip() in content:
                need_date_header = False

    with open(filename, "a", encoding="utf-8") as f:
        if need_date_header:
            f.write(date_header)
        for line in lines:
            f.write(format_message(line))

def cleanup_old_lines(filename):
    if not os.path.exists(filename):
        return
    cutoff = datetime.now() - timedelta(days=2)
    pattern = re.compile(r"^(\d{2}\.\d{2}\.\d{4})")

    new_lines = []
    current_date = None

    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            match = re.search(r"(\d{2}\.\d{2}\.\d{4})", line)
            if match:
                current_date = datetime.strptime(match.group(1), "%d.%m.%Y")
                if current_date >= cutoff:
                    new_lines.append(line)
            elif current_date and current_date >= cutoff:
                new_lines.append(line)

    with open(filename, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

def save_new_lines(welt_nummer, lines):
    global LAST_GLOBAL_LINES
    new_lines = [line for line in lines if line not in LAST_LINES[welt_nummer]]
    new_global_lines = [line for line in new_lines if is_global_chat(line)]
    new_local_lines = [line for line in new_lines if not is_global_chat(line)]

    if new_local_lines:
        filename = f"welt{welt_nummer}_chatlog.txt"
        save_lines(filename, new_local_lines)
        LAST_LINES[welt_nummer].update(new_local_lines)

    if welt_nummer == 1 and new_global_lines:
        filename = "global_chatlog.txt"
        save_lines(filename, new_global_lines)
        LAST_GLOBAL_LINES.update(new_global_lines)

    # Reinigung der Logdateien älterer Einträge
    cleanup_old_lines(f"welt{welt_nummer}_chatlog.txt")
    if welt_nummer == 1:
        cleanup_old_lines("global_chatlog.txt")

def fetch_all_worlds():
    for i, url in enumerate(WELTEN, start=1):
        try:
            response = requests.get(url, timeout=10)
            response.encoding = 'utf-8'
            if response.status_code == 200:
                chat_lines = extract_chat_lines(response.text)
                if chat_lines:
                    save_new_lines(i, chat_lines)
        except Exception as e:
            print(f"[Welt {i}] Fehler beim Abruf: {e}")

# -------------------------------
# Flask Webserver
# -------------------------------
app = Flask(__name__)

@app.route("/")
def index():
    welt = request.args.get("welt")
    logs = ""

    if welt == "global":
        try:
            with open("global_chatlog.txt", "r", encoding="utf-8") as file:
                logs = file.read()
        except FileNotFoundError:
            logs = "Kein globaler Chatverlauf vorhanden."
    elif welt and welt.isdigit() and 1 <= int(welt) <= 14:
        try:
            with open(f"welt{welt}_chatlog.txt", "r", encoding="utf-8") as file:
                logs = file.read()
        except FileNotFoundError:
            logs = f"Kein Chatverlauf für Welt {welt} vorhanden."

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Freewar Chat Tracker</title>
        <style>
            body {
                background-color: var(--bg);
                color: var(--fg);
                font-family: Arial, sans-serif;
                padding: 20px;
            }
            :root {
                --bg: #1e1e1e;
                --fg: #e0e0e0;
                --input-bg: #2a2a2a;
                --input-fg: #ffffff;
            }
            .light-mode {
                --bg: #ffffff;
                --fg: #000000;
                --input-bg: #f0f0f0;
                --input-fg: #000000;
            }
            .button {
                padding: 10px 15px;
                margin: 5px;
                border: none;
                background-color: #444;
                color: white;
                cursor: pointer;
                border-radius: 5px;
            }
            .button:hover {
                background-color: #666;
            }
            .search-box {
                margin: 10px 0;
            }
            #chatDisplay {
                background-color: var(--input-bg);
                color: var(--input-fg);
                padding: 10px;
                border: 1px solid #333;
                font-family: monospace;
                white-space: pre-wrap;
                height: 600px;
                overflow-y: scroll;
            }
            .shout {
                color: #3399ff;
                font-weight: bold;
            }
            .datestamp {
                font-size: 2em;
                font-weight: bold;
                display: block;
                margin: 10px 0;
            }
            .donate-link {
                margin-top: 20px;
                display: inline-block;
                font-size: 1.2em;
            }
        </style>
    </head>
    <body>
        <h1>Freewar Chat Tracker</h1>

        <div>
            {% for i in range(1, 15) %}
                <a href="/?welt={{i}}"><button class="button">Welt {{i}}</button></a>
            {% endfor %}
            <a href="/?welt=global"><button class="button">🌐 Global</button></a>
        </div>

        <div class="search-box">
            <input type="text" id="searchInput" class="button" placeholder="Suche...">
            <button class="button" onclick="toggleDarkMode()">🌗 Dark Mode umschalten</button>
        </div>

        <div id="chatDisplay">{{ logs|safe }}</div>

        <a class="donate-link" href="https://paypal.me/FabianSchmitt89" target="_blank">💖 Spende</a>

        <script>
            const searchInput = document.getElementById("searchInput");
            const chatDisplay = document.getElementById("chatDisplay");
            const originalContent = chatDisplay.innerHTML;

            searchInput.addEventListener("input", function () {
                const term = this.value.toLowerCase();
                if (!term) {
                    chatDisplay.innerHTML = originalContent;
                    return;
                }
                const filtered = originalContent.split("<br>").filter(line =>
                    line.toLowerCase().includes(term)
                );
                chatDisplay.innerHTML = filtered.join("<br>");
            });

            function toggleDarkMode() {
                const isLight = document.body.classList.toggle("light-mode");
                localStorage.setItem("theme", isLight ? "light" : "dark");
            }

            if (localStorage.getItem("theme") === "light") {
                document.body.classList.add("light-mode");
            }
        </script>
    </body>
    </html>
    """, logs=logs)

@app.route("/<path:filename>")
def serve_log(filename):
    return send_from_directory('.', filename)

# -------------------------------
# Hintergrund-Tracking-Thread
# -------------------------------
if __name__ == "__main__":
    def loop_fetch():
        print("Starte Freewar Chat Tracker (5-Minuten-Takt)...")
        while True:
            fetch_all_worlds()
            time.sleep(300)

    tracking_thread = threading.Thread(target=loop_fetch, daemon=True)
    tracking_thread.start()

    app.run(host="0.0.0.0", port=8080)
