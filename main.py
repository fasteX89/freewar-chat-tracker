import requests
import time
import os
from bs4 import BeautifulSoup
from datetime import datetime
from flask import Flask, send_from_directory, request

# -------------------------------
# Chat-Tracking-Konfiguration
# -------------------------------
WELTEN = [f"https://welt{i}.freewar.de/freewar/internal/chattext.php" for i in range(1, 15)]
LAST_LINES = {i: set() for i in range(1, 15)}
LAST_GLOBAL_LINES = set()

def extract_chat_lines(html):
    soup = BeautifulSoup(html, "html.parser")
    p_tags = soup.find_all("p")
    return [p.get_text(separator=" ", strip=True) for p in p_tags if p.get_text(strip=True)]

def is_global_chat(line):
    return any(f"(Welt {i})" in line for i in range(2, 15))  # Welt 1 ist lokale Quelle, andere sind global

def save_new_lines(welt_nummer, lines):
    global LAST_GLOBAL_LINES
    new_lines = [line for line in lines if line not in LAST_LINES[welt_nummer]]
    new_global_lines = [line for line in new_lines if is_global_chat(line)]
    new_local_lines = [line for line in new_lines if line not in new_global_lines]

    # Lokale Welt-Logs
    if new_local_lines:
        filename = f"welt{welt_nummer}_chatlog.txt"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(filename, "a", encoding="utf-8") as f:
            f.write(f"--- {timestamp} ---\n")
            for line in new_local_lines:
                f.write(f"{line}\n")
            f.write("\n")
        print(f"[Welt {welt_nummer}] {len(new_local_lines)} neue lokale Zeile(n) gespeichert.")
        LAST_LINES[welt_nummer].update(new_local_lines)

    # Global Chat (nur aus Welt 1 extrahiert)
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

# -------------------------------
# Flask Webserver
# -------------------------------
app = Flask(__name__)

@app.route("/")
def index():
    return send_from_directory('.', 'logs.html')

@app.route("/<path:filename>")
def serve_log(filename):
    return send_from_directory('.', filename)

@app.route("/delete/<filename>", methods=["POST"])
def delete_log(filename):
    safe_files = [f"welt{i}_chatlog.txt" for i in range(1, 15)] + ["global_chatlog.txt"]
    if filename not in safe_files:
        return "Nicht erlaubt", 403
    try:
        os.remove(filename)
        return f"Datei {filename} gelöscht."
    except Exception as e:
        return f"Fehler: {e}", 500

# -------------------------------
# Startpunkt für Render oder lokal
# -------------------------------
if __name__ == "__main__":
    import threading

    def loop_fetch():
        print("Starte Freewar Chat Tracker (5-Minuten-Takt)...")
        while True:
            fetch_all_worlds()
            time.sleep(300)  # 5 Minuten

    # Tracker läuft in Thread
    tracking_thread = threading.Thread(target=loop_fetch, daemon=True)
    tracking_thread.start()

    # Starte Webserver
    app.run(host="0.0.0.0", port=8080)
