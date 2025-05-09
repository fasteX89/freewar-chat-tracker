import requests
import time
import os
from bs4 import BeautifulSoup
from datetime import datetime
from flask import Flask, request, render_template_string
import threading

WELTEN = [f"https://welt{i}.freewar.de/freewar/internal/chattext.php" for i in range(1, 15)]
LAST_LINES = {i: set() for i in range(1, 15)}
LAST_GLOBAL_LINES = set()

GLOBAL_MARKERS = [f"(Welt {i}):" for i in range(1, 15)] + ["(Chaos-Welt)", "(AF):", "(RP):"]

def extract_chat_lines(html):
    soup = BeautifulSoup(html, "html.parser")
    return [p.get_text(separator=" ", strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]

def is_global_chat(line):
    return any(marker in line for marker in GLOBAL_MARKERS)

def format_message(message):
    if "schreit:" in message:
        return f'<span style="color: #4da6ff;">{message}</span>'
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
        LAST_LINES[welt_nummer].update(new_local_lines)

    if welt_nummer == 1 and new_global_lines:
        with open("global_chatlog.txt", "a", encoding="utf-8") as f:
            f.write(f"--- {timestamp} ---\n")
            for line in new_global_lines:
                f.write(f"{line}\n")
            f.write("\n")
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
        except Exception as e:
            print(f"[Welt {i}] Fehler beim Abruf: {e}")

# Flask App
app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    selected = request.args.get("welt", "global")

    logs = ""
    filename = "global_chatlog.txt" if selected == "global" else f"welt{selected}_chatlog.txt"

    try:
        with open(filename, "r", encoding="utf-8") as f:
            for line in f:
                logs += format_message(line)
    except FileNotFoundError:
        logs = "<i>Noch keine Daten.</i>"

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
            h1 {
                color: #f0db4f;
            }
            .button {
                background-color: #4d4dff;
                color: white;
                padding: 5px 10px;
                margin: 5px 2px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
            }
            .button:hover {
                background-color: #3333cc;
            }
            .delete-button {
                background-color: #ff4d4d;
                margin-top: 10px;
            }
            .delete-button:hover {
                background-color: #cc0000;
            }
            pre {
                background-color: #2e2e2e;
                border: 1px solid #444;
                padding: 10px;
                border-radius: 8px;
                max-height: 70vh;
                overflow-y: scroll;
                white-space: pre-wrap;
            }
        </style>
    </head>
    <body>
        <h1>Freewar Chat Tracker</h1>
        <div>
            <a href="/?welt=global"><button class="button">Global</button></a>
            {% for i in range(1, 15) %}
                <a href="/?welt={{i}}"><button class="button">Welt {{i}}</button></a>
            {% endfor %}
        </div>
        <form method="POST" action="/delete?welt={{selected}}">
            <button type="submit" class="button delete-button">Löschen</button>
        </form>
        <hr>
        <pre>{{ logs|safe }}</pre>
    </body>
    </html>
    """, logs=logs, selected=selected)

@app.route("/delete", methods=["POST"])
def delete_log():
    selected = request.args.get("welt")
    if selected == "global":
        filename = "global_chatlog.txt"
    elif selected.isdigit() and 1 <= int(selected) <= 14:
        filename = f"welt{selected}_chatlog.txt"
    else:
        return "Ungültige Welt", 400

    try:
        os.remove(filename)
        return f"Datei {filename} gelöscht. <a href='/'>Zurück</a>"
    except Exception as e:
        return f"Fehler: {e}", 500

if __name__ == "__main__":
    def loop_fetch():
        print("Starte Freewar Chat Tracker...")
        while True:
            fetch_all_worlds()
            time.sleep(300)

    threading.Thread(target=loop_fetch, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)
