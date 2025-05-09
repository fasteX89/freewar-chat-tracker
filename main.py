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

# Globale Marker
GLOBAL_MARKERS = [f"(Welt {i}):" for i in range(1, 15)] + ["(Chaos-Welt)", "(AF):", "(RP):"]

def extract_chat_lines(html):
    soup = BeautifulSoup(html, "html.parser")
    p_tags = soup.find_all("p")
    return [p.get_text(separator=" ", strip=True) for p in p_tags if p.get_text(strip=True)]

def is_global_chat(line):
    return any(marker in line for marker in GLOBAL_MARKERS)

def format_message(message):
    """ Hebt 'schreit:' hervor """
    if "schreit:" in message:
        return f'<span style="color: #4da6ff;">{message}</span>'
    return message

def save_new_lines(welt_nummer, lines):
    global LAST_GLOBAL_LINES
    new_lines = [line for line in lines if line not in LAST_LINES[welt_nummer]]
    new_global_lines = [line for line in new_lines if is_global_chat(line)]
    new_local_lines = [line for line in new_lines if line not in new_global_lines]

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Lokale Logs
    if new_local_lines:
        filename = f"welt{welt_nummer}_chatlog.txt"
        with open(filename, "a", encoding="utf-8") as f:
            f.write(f"--- {timestamp} ---\n")
            for line in new_local_lines:
                f.write(f"{line}\n")
            f.write("\n")
        LAST_LINES[welt_nummer].update(new_local_lines)
        print(f"[Welt {welt_nummer}] {len(new_local_lines)} neue lokale Zeile(n) gespeichert.")

    # Global nur in Welt 1
    if welt_nummer == 1 and new_global_lines:
        filename = "global_chatlog.txt"
        with open(filename, "a", encoding="utf-8") as f:
            f.write(f"--- {timestamp} ---\n")
            for line in new_global_lines:
                f.write(f"{line}\n")
            f.write("\n")
        LAST_GLOBAL_LINES.update(new_global_lines)
        print(f"[GLOBAL] {len(new_global_lines)} neue Zeile(n) gespeichert.")

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
    logs = {}
    for i in range(1, 15):
        try:
            with open(f"welt{i}_chatlog.txt", "r", encoding="utf-8") as file:
                logs[f"Welt {i}"] = file.read()
        except FileNotFoundError:
            logs[f"Welt {i}"] = ""

    try:
        with open("global_chatlog.txt", "r", encoding="utf-8") as file:
            logs["Global"] = file.read()
    except FileNotFoundError:
        logs["Global"] = ""

    return render_template_string("""
    <html>
    <head>
        <title>Freewar Chat Tracker</title>
        <style>
            body {
                background-color: #1e1e1e;
                color: #f0f0f0;
                font-family: monospace;
                padding: 20px;
            }
            h1, h2 {
                color: #f0db4f;
            }
            .welt {
                margin-bottom: 30px;
                border: 1px solid #333;
                padding: 10px;
                background-color: #2e2e2e;
                border-radius: 8px;
            }
            .button {
                background-color: #ff4d4d;
                color: white;
                padding: 5px 10px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                margin-top: 5px;
            }
            .button:hover {
                background-color: #e60000;
            }
            pre {
                white-space: pre-wrap;
                word-wrap: break-word;
            }
        </style>
    </head>
    <body>
        <h1>Freewar Chat Tracker</h1>
        {% for welt, content in logs.items() %}
            <div class="welt">
                <h2>{{ welt }}</h2>
                <form method="POST" action="/delete/{{ 'global_chatlog.txt' if welt == 'Global' else 'welt' + welt.split(' ')[1] + '_chatlog.txt' }}">
                    <button class="button" type="submit">Löschen</button>
                </form>
                <pre>{{ content | safe }}</pre>
            </div>
        {% endfor %}
    </body>
    </html>
    """, logs=logs)

@app.route("/delete/<filename>", methods=["POST"])
def delete_log(filename):
    safe_files = [f"welt{i}_chatlog.txt" for i in range(1, 15)] + ["global_chatlog.txt"]
    if filename not in safe_files:
        return "Nicht erlaubt", 403
    try:
        os.remove(filename)
        return f"Datei {filename} gelöscht. <a href='/'>Zurück</a>"
    except Exception as e:
        return f"Fehler: {e}", 500

# -------------------------------
# Startpunkt
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
