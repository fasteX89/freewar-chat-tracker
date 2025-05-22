import os, time, threading, re, requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from flask import Flask, request, render_template_string, send_from_directory
from supabase import create_client, Client
from zoneinfo import ZoneInfo
import html

# ─────────────────────────────
# Supabase Initialisierung
# ─────────────────────────────
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
TABLE = "chat_logs"

# ─────────────────────────────
# Chat-Crawler Setup
# ─────────────────────────────
WELTEN_URLS = [f"https://welt{i}.freewar.de/freewar/internal/chattext.php" for i in range(1, 15)]
LAST_LINES = {i: set() for i in range(1, 15)}
LAST_GLOBAL = set()

def extract_lines(html_text: str):
    soup = BeautifulSoup(html_text, "html.parser")
    lines = [p.get_text(" ", strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
    return [l for l in lines if "Automatische Mitteilung:" not in l]

def is_global(line: str) -> bool:
    pat = [f"(Welt {i}):" for i in range(1, 15)] + ["(Welt AF):", "(Chaos-Welt):"]
    return any(k in line for k in pat)

def get_berlin_timestamp(line: str, fetch_time_utc: datetime) -> str:
    match = re.match(r"^(\d{2}:\d{2}:\d{2})", line)
    if not match:
        return fetch_time_utc.astimezone(ZoneInfo("Europe/Berlin")).isoformat()

    time_str = match.group(1)
    line_time = datetime.strptime(time_str, "%H:%M:%S").time()

    fetch_berlin = fetch_time_utc.astimezone(ZoneInfo("Europe/Berlin"))
    line_dt = datetime.combine(fetch_berlin.date(), line_time, tzinfo=ZoneInfo("Europe/Berlin"))

    if line_dt > fetch_berlin:
        line_dt -= timedelta(days=1)

    return line_dt.isoformat()

def store_lines(welt: int, lines: list[str], fetch_time_utc: datetime):
    data = [{
        "welt": welt,
        "timestamp": get_berlin_timestamp(l, fetch_time_utc),
        "message": l
    } for l in lines]
    if data:
        sb.table(TABLE).insert(data).execute()

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

        fetch_time_utc = datetime.utcnow()
        globals_ = [l for l in new if is_global(l)]
        locals_ = [l for l in new if l not in globals_]

        if locals_:
            store_lines(welt_num, locals_, fetch_time_utc)
            LAST_LINES[welt_num].update(locals_)

        if welt_num == 1 and globals_:
            store_lines(0, globals_, fetch_time_utc)
            LAST_LINES[welt_num].update(globals_)  # <-- hinzufügen!
            LAST_GLOBAL.update(globals_)

    except Exception as e:
        print(f"[Welt {welt_num}] Fehler: {e}")

# ─────────────────────────────
# Flask Web-Interface
# ─────────────────────────────
app = Flask(__name__)

def format_msg(msg: str):
    msg = html.escape(msg)  # sicher und ohne Backslashes
    if "schreit:" in msg:
        return f"<span class='shout'>{msg}</span><br>"
    return f"{msg}<br>"

def fetch_from_db(welt: int):
    q = (sb.table(TABLE)
           .select("timestamp,message")
           .eq("welt", welt)
           .order("timestamp"))
    rows = q.execute().data

    seen = set()
    out, cur_date = [], ""
    for r in rows:
        ts = datetime.fromisoformat(r["timestamp"]).astimezone(ZoneInfo("Europe/Berlin"))
        d = ts.strftime("%d.%m.%Y")
        key = (ts.isoformat(), r["message"])
        if key in seen:
            continue
        seen.add(key)

        if d != cur_date:
            out.append(f"<span class='datestamp'>📅 {d}</span><br>")
            cur_date = d
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
    tpl = open("template.html", encoding="utf-8").read()
    return render_template_string(tpl, logs=logs)

@app.route("/<path:filename>")
def statics(filename):
    return send_from_directory(".", filename)

# ─────────────────────────────
# Hintergrund-Worker
# ─────────────────────────────
def worker():
    while True:
        for idx, url in enumerate(WELTEN_URLS, 1):
            crawl_world(idx, url)
        clean_old()
        time.sleep(240)  # alle 4 Minuten

if __name__ == "__main__":
    threading.Thread(target=worker, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)
