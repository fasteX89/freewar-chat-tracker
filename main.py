import requests
import time
import os
from bs4 import BeautifulSoup
from datetime import datetime
from flask import Flask, request, render_template_string, redirect, url_for
import threading

WELTEN = [f"https://welt{i}.freewar.de/freewar/internal/chattext.php" for i in range(1, 15)]
LAST_LINES = {i: set() for i in range(1, 15)}
LAST_GLOBAL_LINES = set()

def extract_chat_lines(html):
    soup = BeautifulSoup(html, "html.parser")
    p_tags = soup.find_all("p")
    return [p.get_text(separator=" ", strip=True) for p in p_tags if p.get_text(strip=True)]

def is_global_chat(line):
    return any(f"(Welt {i})" in line for i in range(2, 15))

def save_new_lines(welt_nummer, lines):
    global LAST_GLOBAL_LINES
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_lines = [line for line in lines if line not in LAST_LINES[welt_nummer]]
    new_global_lines = [line for line in new_lines if is_global_chat(line)]
    new_local_lines = [line for line in new_lines if line not in new_global_lines]

    if new_local_lines:
        filename = f"welt{welt_nummer}_chatlog.txt"
        with open(filename, "a", encoding="utf-8") as f:
            f.write(f"--- {timestamp} ---\n")
            for line in new_local_lines:
                f.write(f"{line}\n")
            f.write("\n")
        print(f"[Welt {welt_nummer}] {len(new_local_lines)} neue lokale Zeile(n) gespeichert.")
        LAST_LINES[welt_nummer].update(new_local_lines)

    if welt_nummer == 1 and new_global_lines:
        filename = "global_chatlog.txt"
        with open(filename, "a", encoding="utf-8") as f:
            f.write(f"--- {timestamp} ---\n")
            for line in new_global_lines:
                f.write(f"{line}\n")
            f.write("\n")
        print(f"[GLOBAL] {len(new_global_lines)} neue Zeile(n) gespeichert.")
        LAST_GLOBAL_LINES.update(new_global_lines)

def fetch_all_worlds():
    for i, url in enumerate(WELTEN, start=1):
        try:
            response = requests.get(url, timeout=10)
            response.encoding = 'utf-8'
            if response.status_code == 200:
                chat_lines = extract_chat_lines(response.text)
                if chat_lines:
                    save_new_lines(i, chat_lines)
            else:
                print(f"[Welt {i}] Fehler: HTTP {response.status_code}")
        except Exception as e:
            print(f"[Welt {i}] Fehler beim Abruf: {e}")

app = Flask(__name__)

@app.route("/")
def index():
    selected_world = request.args.get("welt", "Globaler Chat")
    filename = "global_chatlog.txt" if selected_world == "Globaler Chat" else f"{selected_world}_chatlog.txt"

    logs = {f"Welt{i}": f"welt{i}_chatlog.txt" for i in range(1, 15)}
    logs["Globaler Chat"] = "global_chatlog.txt"

    try:
        with open(filename, encoding="utf-8") as f:
            lines = f.readlines()
    except:
        lines = ["Fehler: Datei konnte nicht geladen werden."]

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Freewar Chat Tracker</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #f4f4f4;
                padding: 20px;
            }
            .chatbox {
                background: #fff;
                border: 1px solid #ccc;
                padding: 15px;
                height: 500px;
                overflow-y: scroll;
                white-space: pre-wrap;
                font-size: 14px;
            }
            .schreit {
                color: blue;
                font-weight: bold;
            }
            .buttons {
                margin-bottom: 10px;
            }
            .buttons form {
                display: inline;
                margin-right: 5px;
            }
            .buttons button {
                padding: 5px 10px;
            }
            .active {
                font-weight: bold;
                background-color: #ddd;
            }
            .search-container {
                margin-bottom: 10px;
            }
            input[type="text"] {
                padding: 5px;
                width: 300px;
            }
        </style>
        <script>
            function toggleRefresh(checkbox) {
                if (checkbox.checked) {
                    localStorage.setItem("refresh", "on");
                    startRefresh();
                } else {
                    localStorage.setItem("refresh", "off");
                    stopRefresh();
                }
            }

            let intervalId;
            function startRefresh() {
                intervalId = setInterval(() => {
                    location.reload();
                }, 10000);
            }

            function stopRefresh() {
                clearInterval(intervalId);
            }

            function searchChat() {
                const query = document.getElementById("search").value.toLowerCase();
                const lines = document.querySelectorAll(".chatline");
                lines.forEach(line => {
                    if (line.textContent.toLowerCase().includes(query)) {
                        line.style.display = "block";
                    } else {
                        line.style.display = "none";
                    }
                });
            }

            window.onload = function() {
                const refreshState = localStorage.getItem("refresh");
                const checkbox = document.getElementById("autorefresh");
                if (refreshState === "on") {
                    checkbox.checked = true;
                    startRefresh();
                }
            }
        </script>
    </head>
    <body>
        <div class="buttons">
            {% for name, file in logs.items() %}
                <form method="get" style="display:inline;">
                    <input type="hidden" name="welt" value="{{ name }}">
                    <button type="submit" class="{% if selected_world == name %}active{% endif %}">{{ name }}</button>
                </form>
                <form method="post" action="/delete/{{ file }}" style="display:inline;">
                    <button title="Löschen" onclick="return confirm('Datei wirklich löschen?')">🗑️</button>
                </form>
            {% endfor %}
            <label style="margin-left: 20px;">
                <input type="checkbox" id="autorefresh" onchange="toggleRefresh(this)">
                Auto-Refresh (10s)
            </label>
        </div>
        <div class="search-container">
            <input type="text" id="search" placeholder="Nachricht durchsuchen..." onkeyup="searchChat()">
        </div>
        <div class="chatbox">
            {% for line in lines %}
                <div class="chatline {% if 'schreit:' in line %}schreit{% endif %}">{{ line.strip() }}</div>
            {% endfor %}
        </div>
    </body>
    </html>
    """
    return render_template_string(html, logs=logs, lines=lines, selected_world=selected_world)

@app.route("/delete/<filename>", methods=["POST"])
def delete_file(filename):
    allowed_files = [f"welt{i}_chatlog.txt" for i in range(1, 15)] + ["global_chatlog.txt"]
    if filename not in allowed_files:
        return "Nicht erlaubt", 403
    try:
        os.remove(filename)
        return redirect(url_for("index"))
    except Exception as e:
        return f"Fehler beim Löschen: {e}", 500

if __name__ == "__main__":
    def start_tracker():
        print("Starte Freewar Chat Tracker (5-Minuten-Takt)...")
        while True:
            fetch_all_worlds()
            time.sleep(300)

    thread = threading.Thread(target=start_tracker, daemon=True)
    thread.start()

    app.run(host="0.0.0.0", port=8080)
