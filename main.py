import os, time, threading, re, requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from flask import Flask, request, render_template_string, send_from_directory
from supabase import create_client, Client
import html  # ganz oben ergänzen

# ───────────────────────────────────────────────
# Supabase-Initialisierung
# ───────────────────────────────────────────────
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

TABLE = "chat_logs"

# ───────────────────────────────────────────────
# Chat-Crawler-Konfiguration
# ───────────────────────────────────────────────
WELTEN_URLS = [f"https://welt{i}.freewar.de/freewar/internal/chattext.php" for i in range(1, 15)]
LAST_LINES = {i: set() for i in range(1, 15)}
LAST_GLOBAL = set()

def extract_lines(html_text: str):
    soup = BeautifulSoup(html_text, "html.parser")
    lines = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    # Ausschluss: Alles mit "Automatische Mitteilung:" im Text
    return [l for l in lines if "Automatische Mitteilung:" not in l]

def is_global(line: str) -> bool:
    global_keys = [f"(Welt {i}):" for i in range(1, 15)] + ["(Chaos-Welt):", "(Welt AF):", "(Welt RP):"]
    return any(k in line for k in global_keys)

def store_lines(welt: int, lines: list[str]):
    now = datetime.utcnow().isoformat()
    data = [{"welt": welt, "timestamp": now, "message": l} for l in lines]
    if data:
        try:
            sb.table(TABLE).insert(data).execute()
        except Exception as e:
            if "duplicate key" not in str(e).lower():
                print(f"[store_lines] Fehler: {e}")

def clean_old():
    cutoff = (datetime.utcnow() - timedelta(hours=48)).isoformat()
    sb.table(TABLE).delete().lt("timestamp", cutoff).execute()

def crawl_world(welt_num: int, url: str):
    try:
        res = requests.get(url, timeout=10)
        res.encoding = "utf-8"
        if res.status_code != 200:
            return
        lines = extract_lines(res.text)
        if not lines:
            return

        new = [l for l in lines if l not in LAST_LINES[welt_num]]
        if not new:
            return

        globals_ = [l for l in new if is_global(l)]
        locals_ = [l for l in new if l not in globals_]

        if locals_:
            store_lines(welt_num, locals_)
            LAST_LINES[welt_num].update(locals_)

        if welt_num == 1 and globals_:
            new_global = [l for l in globals_ if l not in LAST_GLOBAL]
            if new_global:
                store_lines(0, new_global)
                LAST_GLOBAL.update(new_global)

    except Exception as e:
        print(f"[Welt {welt_num}] Fehler: {e}")

# ───────────────────────────────────────────────
# Flask Frontend
# ───────────────────────────────────────────────
app = Flask(__name__)


def format_msg(msg: str):
    msg = html.escape(msg)  # korrektes HTML-Escaping
    if "schreit:" in msg:
        return f"<span class='shout'>{msg}</span><br>"
    return f"{msg}<br>"

def fetch_from_db(welt: int):
    q = (sb.table(TABLE)
           .select("timestamp,message")
           .eq("welt", welt)
           .order("timestamp"))
    rows = q.execute().data

    # Gruppiere nach Datum → fette Überschrift
    out, cur_date = [], ""
    for r in rows:
        ts = datetime.fromisoformat(r["timestamp"])
        d = (ts + timedelta(hours=2)).strftime("%d.%m.%Y")  # UTC+2
        if d != cur_date:
            out.append(f"<span class='datestamp'>📅 {d}</span><br>")
            cur_date = d

        # Nur die Nachricht selbst – ohne Zeitstempel
        out.append(format_msg(r["message"]))
    return "".join(out)

@app.route("/")
def index():
    welt = request.args.get("welt")
    logs = ""
    if welt == "global":
        logs = fetch_from_db(0)
    elif welt and welt.isdigit() and 1 <= int(welt) <= 14:
        logs = fetch_from_db(int(welt))
    page = open("template.html", encoding="utf-8").read()
    return render_template_string(page, logs=logs)

@app.route("/<path:filename>")
def statics(filename):
    return send_from_directory(".", filename)

# ───────────────────────────────────────────────
# Hintergrund-Thread
# ───────────────────────────────────────────────
def worker():
    while True:
        for idx, url in enumerate(WELTEN_URLS, 1):
            crawl_world(idx, url)
        clean_old()
        time.sleep(240)  # Alle 4 Minuten

if __name__ == "__main__":
    threading.Thread(target=worker, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)
