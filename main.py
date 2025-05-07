import os
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from flask import Flask, send_from_directory

# Flask-App initialisieren
app = Flask(__name__)

# URLs der Freewar-Welten
WELTEN = [f"https://welt{i}.freewar.de/freewar/internal/chattext.php" for i in range(1, 15)]
LAST_LINES = {i: set() for i in range(1, 15)}
LAST_GLOBAL_LINES = set()

def extract_chat_lines(html):
    soup = BeautifulSoup(html, "html.parser")
    p_tags = soup.find_all("p")
    return [p.get_text(separator=" ", strip=True) for p in p_tags if p.get_text(strip=True)]

def save_new_lines(welt_nummer, lines):
    filename = f"welt{welt_nummer}_chatlog.txt"
    new_lines = [line for line in lines if line not in LAST_LINES[welt_nummer]]

    # Global-Chat herausfiltern
    global_lines = [line for line in new_lines if "(Welt " in line and ")" in line]
    new_lines = [line for line in new_lines if line not in global_lines]

    # Speichern globaler Chat in extra Datei
    global_new = [line for line in global_lines if line not in LAST_GLOBAL_LINES]
    if global_new:
        with open("global_chatlog.txt", "a", encoding="utf-8") as gf:
            gf.write(f"--- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            for line in global_new:
                gf.write(f"{line}\n")
            gf.write("\n")
        LAST_GLOBAL_LINES.update(global_new)

    # Speichern Welt-spezifischer Chat
    if new_lines:
        with open(filename, "a", encoding="utf-8") as f:
            f.write(f"--- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            for line in new_lines:
                f.write(f"{line}\n")
            f.write("\n")
        LAST_LINES[welt_nummer].update(new_lines)
        print(f"[Welt {welt_nummer}] {len(new_lines)} neue Zeile(n) gespeichert.")
    else:
        print(f"[Welt {welt_nummer}] Keine neuen Zeilen.")

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

# Flask-Routen
@app.route("/")
def index():
    return "Freewar Chat Tracker läuft!"

@app.route("/logs")
def serve_logs():
    return send_from_directory('.', 'logs.html')

@app.route("/global")
def serve_global_log():
    return send_from_directory('.', 'global_chatlog.txt')

# Startlogik
if __name__ == "__main__":
    import threading

    # Hintergrund-Thread für das Abrufen der Chats
    def chat_loop():
        while True:
            fetch_all_worlds()
            time.sleep(300)  # alle 5 Minuten

    threading.Thread(target=chat_loop, daemon=True).start()

    # Flask-Server starten
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
