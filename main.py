import requests
import time
import os
from bs4 import BeautifulSoup
from datetime import datetime
from flask import Flask, send_from_directory, request, render_template_string
import threading
import html

WELTEN = [f"https://welt{i}.freewar.de/freewar/internal/chattext.php" for i in range(1, 15)]
LAST_LINES = {i: set() for i in range(1, 15)}
LAST_GLOBAL_LINES = set()

GLOBAL_PATTERNS = [
    f"(Welt {i}):" for i in range(1, 15)
] + ["(Chaos-Welt)", "(Welt AF):", "(Welt RP):"]

def extract_chat_lines(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    p_tags = soup.find_all("p")
    return [p.get_text(separator=" ", strip=True) for p in p_tags if p.get_text(strip=True)]

def is_global_chat(line):
    return any(p in line for p in GLOBAL_PATTERNS)

def save_new_lines(welt_nummer, lines):
    global LAST_GLOBAL_LINES
    new_lines = [line for line in lines if line not in LAST_LINES[welt_nummer]]
    new_global_lines = [line for line in new_lines if is_global_chat(line)]
    new_local_lines = [line for line in new_lines if line not in new_global_lines]

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if new_local_lines:
        filename = f"welt{welt_nummer}_chatlog.txt"
        with open(filename, "a", encoding="utf-8") as f:
            f.write(f"--- {timestamp} ---\n")
            for line in new_local_lines:
                f.write(f"{line}\n")
            f.write("\n")
        LAST_LINES[welt_nummer].update(new_local_lines)

    if welt_nummer == 1 and new_global_lines:
        filename = "global_chatlog.txt"
        with open(filename, "a", encoding="utf-8") as f:
            f.write(f"--- {timestamp} ---\n")
            for line in new_global_lines:
                f.write(f"{line}\n")
            f.write("\n")
        LAST_GLOBAL_LINES.update(new_global_lines)

app = Flask(__name__)

@app.route("/")
def index():
    welt_param = request.args.get("welt")
    raw_logs = ""

    if welt_param:
        if welt_param == "global":
            try:
                with open("global_chatlog.txt", "r", encoding="utf-8") as f:
                    raw_logs = f.read()
            except FileNotFoundError:
                raw_logs = "Keine globalen Nachrichten gefunden."
        else:
            try:
                with open(f"welt{welt_param}_chatlog.txt", "r", encoding="utf-8") as f:
                    raw_logs = f.read()
            except FileNotFoundError:
                raw_logs = f"Keine Nachrichten für Welt {welt_param} gefunden."

    # HTML Escaping und Markierung für "schreit:"
    lines = raw_logs.splitlines()
    lines_html = []
    for line in lines:
        safe_line = html.escape(line)
        if "schreit:" in safe_line:
            safe_line = f'<span class="shout">{safe_line}</span>'
        lines_html.append(safe_line)
    logs_html = "<br>".join(lines_html)

    return render_template_string("""
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
                .delete-button {
                    background-color: #d9534f;
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

            <br>
            <form method="POST" action="/delete_all">
                <input type="password" name="pw" placeholder="Passwort zum Löschen" required>
                <button type="submit" class="button delete-button">Alle Chats löschen</button>
            </form>

            <div class="search-box">
                <input type="text" id="searchInput" class="button" placeholder="Suche...">
                <button class="button" onclick="toggleDarkMode()">🌗 Dark Mode umschalten</button>
            </div>

            <div id="chatDisplay">{{ logs|safe }}</div>

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
    """, logs=logs_html)

@app.route("/delete_all", methods=["POST"])
def delete_all_logs():
    password = request.form.get("pw")
    if password != "FSw356t&":
        return "❌ Falsches Passwort. <a href='/'>Zurück</a>", 403

    for i in range(1, 15):
        try:
            os.remove(f"welt{i}_chatlog.txt")
        except FileNotFoundError:
            pass
    try:
        os.remove("global_chatlog.txt")
    except FileNotFoundError:
        pass

    return "✅ Alle Chatlogs wurden gelöscht. <a href='/'>Zurück</a>"

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
            print(f"[Welt {i}] Fehler: {e}")

if __name__ == "__main__":
    def background_loop():
        while True:
            fetch_all_worlds()
            time.sleep(300)

    threading.Thread(target=background_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)
