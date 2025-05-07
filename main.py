import requests
import time
import os
from datetime import datetime
from flask import Flask, render_template_string, Response

app = Flask(__name__)

# Deine Welt-URLs und Chatdateien
WELTEN = [f"https://welt{i}.freewar.de/freewar/internal/chattext.php" for i in range(1, 15)]
LAST_LINES = {i: set() for i in range(1, 15)}

# Pfad zur globalen Chatlog-Datei
GLOBAL_CHAT_LOG = "global_chatlog.txt"

def extract_chat_lines(html):
    """Extrahiert die Chat-Nachrichten aus dem HTML."""
    soup = BeautifulSoup(html, "html.parser")
    p_tags = soup.find_all("p")
    return [p.get_text(separator=" ", strip=True) for p in p_tags if p.get_text(strip=True)]

def save_new_lines(welt_nummer, lines):
    """Speichert neue Chat-Nachrichten in einer Datei."""
    filename = f"welt{welt_nummer}_chatlog.txt"
    new_lines = [line for line in lines if line not in LAST_LINES[welt_nummer]]

    if new_lines:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(filename, "a", encoding="utf-8") as f:
            f.write(f"--- {timestamp} ---\n")
            for line in new_lines:
                f.write(f"{line}\n")
            f.write("\n")
        LAST_LINES[welt_nummer].update(new_lines)
        print(f"[Welt {welt_nummer}] {len(new_lines)} neue Zeile(n) gespeichert.")
    else:
        print(f"[Welt {welt_nummer}] Keine neuen Zeilen.")

def fetch_all_worlds():
    """Holt alle Chat-Nachrichten von allen Welten."""
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

def fetch_global_chat():
    """Lädt den globalen Chattext und speichert ihn alle 5 Minuten."""
    while True:
        fetch_all_worlds()
        time.sleep(300)  # Alle 5 Minuten

# Starten des Hintergrundprozesses für das Abrufen der Daten
import threading
threading.Thread(target=fetch_global_chat, daemon=True).start()

@app.route('/global-chat')
def show_global_chat():
    """Zeigt den globalen Chatlog an."""
    try:
        if not os.path.exists(GLOBAL_CHAT_LOG):
            return "Fehler: Datei existiert nicht.", 404
        with open(GLOBAL_CHAT_LOG, "r", encoding="utf-8") as f:
            content = f.read()
        return render_template_string("""
            <html><head><title>Global Chatlog</title>
            <meta http-equiv="refresh" content="300"> <!-- Seite alle 5 Minuten neu laden -->
            </head><body>
            <h1>Globaler Chatlog</h1>
            <pre style="white-space: pre-wrap;">{{ content }}</pre>
            </body></html>
        """, content=content)
    except Exception as e:
        return f"Fehler: {str(e)}", 500

if __name__ == "__main__":
    print("Starte Freewar Chat Tracker...")
    app.run(host='0.0.0.0', port=8080)
