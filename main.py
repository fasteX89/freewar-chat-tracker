import os, time, threading, re, requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from flask import Flask, request, render_template_string, send_from_directory
from supabase import create_client, Client

# ───────────────────────────────────────────────
# Supabase-Initialisierung
# ───────────────────────────────────────────────
SUPABASE_URL = os.environ["https://rkrlvvhdzqtrhsvtcjwf.supabase.co"]
SUPABASE_KEY = os.environ["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJrcmx2dmhkenF0cmhzdnRjandmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDc1MTI4MzMsImV4cCI6MjA2MzA4ODgzM30.aayJqyQYfHdsv56NDX1Ybp5snhm3orE6gWViUqcp6DE"]
sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

TABLE = "chat_logs"           # Name aus Vorbereitung

# ───────────────────────────────────────────────
# Chat-Crawler-Konfiguration
# ───────────────────────────────────────────────
WELTEN_URLS = [f"https://welt{i}.freewar.de/freewar/internal/chattext.php" for i in range(1, 15)]
LAST_LINES  = {i: set() for i in range(1, 15)}   # Duplikat-Vermeidung
LAST_GLOBAL = set()

def extract_lines(html_text: str):
    soup = BeautifulSoup(html_text, "html.parser")
    lines = [p.get_text(" ", strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
    # Filter : Automatische Mitteilung
    return [l for l in lines if not l.startswith("Automatische Mitteilung:")]

def is_global(line:str) -> bool:
    pat = [f"(Welt {i}):" for i in range(1,15)] + ["(Chaos-Welt)", "(Welt AF):", "(Welt RP):"]
    return any(k in line for k in pat)

def store_lines(welt:int, lines:list[str]):
    # Einfügen als Batch
    data = [{
        "welt": welt,
        "timestamp": datetime.utcnow().isoformat(),
        "message": l
    } for l in lines]
    if data:
        sb.table(TABLE).insert(data).execute()

def clean_old():
    cutoff = (datetime.utcnow() - timedelta(hours=48)).isoformat()
    sb.table(TABLE).delete().lt("timestamp", cutoff).execute()

def crawl_world(welt_num:int, url:str):
    try:
        res = requests.get(url, timeout=10)
        res.encoding = "utf-8"
        if res.status_code != 200:
            return
        lines = extract_lines(res.text)
        if not lines: return

        new = [l for l in lines if l not in LAST_LINES[welt_num]]
        if not new: return

        globals_ = [l for l in new if is_global(l)]
        locals_  = [l for l in new if l not in globals_]

        if locals_:
            store_lines(welt_num, locals_)
            LAST_LINES[welt_num].update(locals_)

        if welt_num == 1 and globals_:
            store_lines(0, globals_)          # welt==0 → global
            LAST_GLOBAL.update(globals_)

    except Exception as e:
        print(f"[Welt {welt_num}] Fehler: {e}")

# ───────────────────────────────────────────────
# Flask Frontend
# ───────────────────────────────────────────────
app = Flask(__name__)

def format_msg(msg:str):
    msg = re.escape(msg)         # HTML escapen
    msg = msg.replace("\\ ", " ")  # Rück-escape spaces
    if "schreit:" in msg:
        return f"<span class='shout'>{msg}</span><br>"
    return f"{msg}<br>"

def fetch_from_db(welt:int):
    q = (sb.table(TABLE)
           .select("timestamp,message")
           .eq("welt", welt)
           .order("timestamp"))
    rows = q.execute().data
    # gruppiere nach Datum → fette Überschrift
    out, cur_date = [], ""
    for r in rows:
        ts = datetime.fromisoformat(r["timestamp"])
        d  = ts.strftime("%d.%m.%Y")
        if d != cur_date:
            out.append(f"<span class='datestamp'>📅 {d}</span><br>")
            cur_date = d
        out.append(format_msg(r["message"]))
    return "".join(out)

@app.route("/")
def index():
    welt = request.args.get("welt")  # None→leer
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
        time.sleep(300)          # 5 Minuten

if __name__ == "__main__":
    threading.Thread(target=worker, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)
