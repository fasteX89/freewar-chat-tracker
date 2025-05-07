import requests
import time
import os
from bs4 import BeautifulSoup
from datetime import datetime
from flask import Flask, send_from_directory, request, jsonify

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

# Flask-Setup
app = Flask(__name__)

@app.route("/")
def index():
    return send_from_directory('.', 'logs.html')

@app.route("/api/chat/<welt>")
def get_chat(welt):
    filename = f"{welt}_chatlog.txt" if welt != "global" else "global_chatlog.txt"
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return jsonify({"lines": f.readlines()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/<path:filename>")
def serve_log(filename):
    return send_from_directory('.', filename)

# Hintergrund-Thread für regelmäßiges Abrufen
if __name__ == "__main__":
    import threading
    def loop_fetch():
        while True:
            fetch_all_worlds()
            time.sleep(60)

    threading.Thread(target=loop_fetch, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)
