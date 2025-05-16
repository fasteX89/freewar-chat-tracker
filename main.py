import requests
import time
import os
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from flask import Flask, send_from_directory, render_template_string, request
import threading

# -------------------------------
# Chat-Tracking-Konfiguration
# -------------------------------
WELTEN = [f"https://welt{i}.freewar.de/freewar/internal/chattext.php" for i in range(1, 15)]
LAST_LINES = {i: set() for i in range(1, 15)}
LAST_GLOBAL_LINES = set()

LOG_DIR = "."

def extract_chat_lines(html):
    soup = BeautifulSoup(html, "html.parser")
    p_tags = soup.find_all("p")
    lines = [p.get_text(separator=" ", strip=True) for p in p_tags if p.get_text(strip=True)]
    # Filtere "Automatische Mitteilung:"
    return [line for line in lines if not line.startswith("Automatische Mitteilung:")]

def is_global_chat(line):
    global_keywords = [
        "(Welt ", "(Chaos-Welt)", "(Welt AF):", "(Welt RP):"
    ]
    return any(k in line for k in global_keywords)

def format_message(message):
    if "schreit:" in message:
        return f'<span style="color: #4ea3ff;">{message}</span>'
    return message

def save_new_lines(welt_nummer, lines):
    global LAST_GLOBAL_LINES
    new_lines = [line for line in lines if line not in LAST_LINES[welt_nummer]]
    new_global_lines = [line for line in new_lines if is_global_chat(line)]
    new_local_lines = [line for line in new_lines if line not in new_global_lines]

    # Lokale Welt-Logs
    if new_local_lines:
        filename = os.path.join(LOG_DIR, f"welt{welt_nummer}_chatlog.txt")
        with open(filename, "a", encoding="utf-8") as f:
            for line in new_local_lines:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"{timestamp}||{format_message(line)}\n")
        LAST_LINES[welt_nummer].update(new_local_lines)

    # Global Chat (nur aus Welt 1 extrahiert)
    if welt_nummer == 1 and new_global_lines:
        filename = os.path.join(LOG_DIR, "global_chatlog.txt")
        with open(filename, "a", encoding="utf-8") as f:
            for line in new_global_lines:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"{timestamp}||{format_message(line)}\n")
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

def clean_old_logs():
    cutoff = datetime.now() - timedelta(hours=48)
    for filename in [f"welt{i}_chatlog.txt" for i in range(1, 15)] + ["global_chatlog.txt"]:
        full_path = os.path.join(LOG_DIR, filename)
        if not os.path.exists(full_path):
            continue
        lines = []
        with open(full_path, "r", encoding="utf-8") as f:
            for line in f:
                if "||" in line:
                    timestamp_str, content = line.split("||", 1)
                    try:
                        ts = datetime.strptime(timestamp_str.strip(), "%Y-%m-%d %H:%M:%S")
                        if ts > cutoff:
                            lines.append(line)
                    except:
                        continue
        with open(full_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

# -------------------------------
# Flask Webserver
# -------------------------------
app = Flask(__name__)

@app.route("/")
def index():
    logs_by_world = {}
    for i in range(1, 15):
        filename = os.path.join(LOG_DIR, f"welt{i}_chatlog.txt")
        logs_by_world[f"Welt {i}"] = []
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                logs_by_world[f"Welt {i}"] = f.readlines()

    # Global Chat
    global_logs = []
    if os.path.exists("global_chatlog.txt"):
        with open("global_chatlog.txt", "r", encoding="utf-8") as f:
            global_logs = f.readlines()
    logs_by_world["Global"] = global_logs

    return render_template_string(open("logs.html", encoding="utf-8").read(), logs_by_world=logs_by_world)

@app.route("/<path:filename>")
def serve_static(filename):
    return send_from_directory(".", filename)

# -------------------------------
# Hintergrundtasks
# -------------------------------
if __name__ == "__main__":
    def background_task():
        print("Starte Tracker mit Auto-Cleanup (48h)...")
        while True:
            fetch_all_worlds()
            clean_old_logs()
            time.sleep(300)

    threading.Thread(target=background_task, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)
