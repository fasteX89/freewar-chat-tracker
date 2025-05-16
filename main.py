import requests
import time
import os
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from flask import Flask, send_from_directory, render_template_string
import threading

app = Flask(__name__)

WELTEN = [f"https://welt{i}.freewar.de/freewar/internal/chattext.php" for i in range(1, 15)]
LAST_LINES = {i: set() for i in range(1, 15)}
LAST_GLOBAL_LINES = set()
LAST_DATES = {i: "" for i in range(1, 15)}
LAST_GLOBAL_DATE = ""

def extract_chat_lines(html):
    soup = BeautifulSoup(html, "html.parser")
    p_tags = soup.find_all("p")
    lines = [p.get_text(separator=" ", strip=True) for p in p_tags if p.get_text(strip=True)]
    return [line for line in lines if not line.startswith("Automatische Mitteilung:")]

def is_global_chat(line):
    global_keys = [f"(Welt {i}):" for i in range(1, 15)] + ["(Chaos-Welt)", "(Welt AF):", "(Welt RP):"]
    return any(key in line for key in global_keys)

def format_message(message):
    if "schreit:" in message:
        return f'<span style="color: #4ea3ff;">{message}</span>'
    return message

def write_line_with_date_check(file_path, welt_nummer, line, is_global=False):
    global LAST_DATES, LAST_GLOBAL_DATE
    now = datetime.now()
    date_str = now.strftime("%d.%m.%Y")
    line_out = f"{now.strftime('%Y-%m-%d %H:%M:%S')}||{format_message(line)}\n"

    if is_global:
        if LAST_GLOBAL_DATE != date_str:
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(f"DATE||{date_str}\n")
            LAST_GLOBAL_DATE = date_str
    else:
        if LAST_DATES[welt_nummer] != date_str:
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(f"DATE||{date_str}\n")
            LAST_DATES[welt_nummer] = date_str

    with open(file_path, "a", encoding="utf-8") as f:
        f.write(line_out)

def save_new_lines(welt_nummer, lines):
    global LAST_GLOBAL_LINES
    new_lines = [line for line in lines if line not in LAST_LINES[welt_nummer]]
    new_global_lines = [line for line in new_lines if is_global_chat(line)]
    new_local_lines = [line for line in new_lines if line not in new_global_lines]

    if new_local_lines:
        file_path = f"welt{welt_nummer}_chatlog.txt"
        for line in new_local_lines:
            write_line_with_date_check(file_path, welt_nummer, line)
        LAST_LINES[welt_nummer].update(new_local_lines)

    if welt_nummer == 1 and new_global_lines:
        file_path = "global_chatlog.txt"
        for line in new_global_lines:
            write_line_with_date_check(file_path, None, line, is_global=True)
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
    all_files = [f"welt{i}_chatlog.txt" for i in range(1, 15)] + ["global_chatlog.txt"]

    for file in all_files:
        if not os.path.exists(file):
            continue

        new_lines = []
        with open(file, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("DATE||"):
                    new_lines.append(line)
                elif "||" in line:
                    ts_str, msg = line.split("||", 1)
                    try:
                        ts = datetime.strptime(ts_str.strip(), "%Y-%m-%d %H:%M:%S")
                        if ts > cutoff:
                            new_lines.append(line)
                    except:
                        continue

        with open(file, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

@app.route("/")
def index():
    logs_by_world = {}

    for i in range(1, 15):
        filename = f"welt{i}_chatlog.txt"
        logs_by_world[f"Welt {i}"] = []
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                logs_by_world[f"Welt {i}"] = f.readlines()

    if os.path.exists("global_chatlog.txt"):
        with open("global_chatlog.txt", "r", encoding="utf-8") as f:
            logs_by_world["Global"] = f.readlines()
    else:
        logs_by_world["Global"] = []

    with open("logs.html", "r", encoding="utf-8") as f:
        html_template = f.read()

    return render_template_string(html_template, logs_by_world=logs_by_world)

@app.route("/<path:filename>")
def serve_log(filename):
    return send_from_directory('.', filename)

if __name__ == "__main__":
    def loop():
        print("Starte Chat-Tracker mit Auto-Cleanup...")
        while True:
            fetch_all_worlds()
            clean_old_logs()
            time.sleep(300)  # 5 Minuten

    threading.Thread(target=loop, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)
