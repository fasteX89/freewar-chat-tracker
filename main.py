import requests
import time
import os
from bs4 import BeautifulSoup
from datetime import datetime
from flask import Flask, send_from_directory, request, render_template_string
import threading

# -------------------------------
# Chat-Tracking-Konfiguration
# -------------------------------
WELTEN = [f"https://welt{i}.freewar.de/freewar/internal/chattext.php" for i in range(1, 15)]
LAST_LINES = {i: set() for i in range(1, 15)}
LAST_GLOBAL_LINES = set()

GLOBAL_PATTERNS = [
    f"(Welt {i}):" for i in range(1, 15)
] + ["(Chaos-Welt)", "(Welt AF):", "(Welt RP):"]

def extract_chat_lines(html):
    soup = BeautifulSoup(html, "html.parser")
    p_tags = soup.find_all("p")
    return [p.get_text(separator=" ", strip=True) for p in p_tags if p.get_text(strip=True)]

def is_global_chat(line):
    return any(p in line for p in GLOBAL_PATTERNS)

def format_message(message):
    if "schreit:" in message:
        return f'<span style="color: #4dabf7;">{message}</span>'
    return message

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
        print(f"[Welt {welt_nummer}] {len(new_local_lines)} neue lokale Zeile(n) gespeichert.")
        LAST_LINES[welt_nummer].update(new_local_lines)

    if welt_nummer == 1 and new_global_lines:
        filename = "global_chatlog.txt"
        with open(filename, "a", encoding="utf-8") as f:
            f.write(f"--- {timestamp} ---\n")
            for line in new_global_lines:
                f.write(f"{line}\n")
            f.write("\n")
        print(f"[GLOBAL] {len(new_global_lines)} neue globale Zeile(n) gespeichert.")
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

# -------------------------------
# Flask Webserver
# -------------------------------
app = Flask(__name__)

@app.route("/")
def index():
    welt_param = request.args.get("welt")
    logs = ""

    if welt_param:
        if welt_param == "global":
            try:
                with open("global_chatlog.txt", "r", encoding="utf-8") as f:
                    logs = f.read()
            except FileNotFoundError:
                logs = "Keine globalen Nachrichten gefunden."
        else:
            try:
                with open(f"welt{welt_param}_chatlog.txt", "r", encoding="utf-8") as f:
                    logs = f.read()
            except FileNotFoundError:
                logs = f"Keine Nachrichten für Welt {welt_param} gefunden."

    return render_template_string("""
        <html>
        <head>
            <title>Freewar Chat Tracker</title>
            <style>
                body {
                    background-color: #1e1e1e;
                    color: #e0e0e0;
                    font-family: Arial, sans-serif;
                    padding: 20px;
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
                textarea {
                    width: 100%;
                    height: 600px;
                    background-color: #121212;
                    color: #f0f0f0;
                    padding: 10px;
                    border: 1px solid #333;
                    font-family: monospace;
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
            </div>
            <textarea id="chatBox" readonly>{{ logs }}</textarea>

            <script>
                const input = document.getElementById("searchInput");
                const chatBox = document.getElementById("chatBox");
                input.addEventListener("input", function() {
                    const lines = chatBox.value.split("\\n");
                    const filtered = lines.filter(l => l.toLowerCase().includes(input.value.toLowerCase()));
                    chatBox.value = filtered.join("\\n");
                });
            </script>
        </body>
        </html>
    """, logs=logs)

@app.route("/delete_all", methods=["POST"])
def delete_all_logs():
    password = request.form.get("pw")
    if password != "FSw356t&":
        return "❌ Falsches Passwort. <a href='/'>Zurück</a>", 403

    errors = []
    for i in range(1, 15):
        try:
            os.remove(f"welt{i}_chatlog.txt")
        except FileNotFoundError:
            pass
        except Exception as e:
            errors.append(str(e))
    try:
        os.remove("global_chatlog.txt")
    except FileNotFoundError:
        pass
    except Exception as e:
        errors.append(str(e))

    if errors:
        return f"Einige Dateien konnten nicht gelöscht werden: {errors} <a href='/'>Zurück</a>", 500
    return "✅ Alle Chatlogs wurden gelöscht. <a href='/'>Zurück</a>"

# -------------------------------
# Startpunkt
# -------------------------------
if __name__ == "__main__":
    def loop_fetch():
        print("Starte Freewar Chat Tracker (5-Minuten-Takt)...")
        while True:
            fetch_all_worlds()
            time.sleep(300)  # 5 Minuten

    tracking_thread = threading.Thread(target=loop_fetch, daemon=True)
    tracking_thread.start()
    app.run(host="0.0.0.0", port=8080)
