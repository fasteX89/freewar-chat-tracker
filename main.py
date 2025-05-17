import os, time, threading, html, re, requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from flask import Flask, request, render_template_string, send_from_directory
from supabase import create_client

# ── Supabase ­Creds  (jetzt aus Environment) ────────────────────
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
sb = create_client(SUPABASE_URL, SUPABASE_KEY)
TABLE = "chat_logs"

# ── Crawler-Konfiguration ────────────────────────────────────────
WELTEN_URLS = [f"https://welt{i}.freewar.de/freewar/internal/chattext.php" for i in range(1, 15)]
LAST_LINES   = {i: set() for i in range(1, 15)}
LAST_GLOBAL  = set()

GLOBAL_MARKER = (
    [f"(Welt {i}):" for i in range(2, 15)] +
    ["(Chaos-Welt)", "(Welt AF):", "(Welt RP):"]
)

# ── Hilfsfunktionen ──────────────────────────────────────────────
def extract_lines(html_text: str):
    soup = BeautifulSoup(html_text, "html.parser")
    lines = [p.get_text(" ", strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
    # Filter : Automatische Mitteilung (case-insensitive, ohne führende Leerzeichen)
    return [l for l in lines if not l.strip().lower().startswith("automatische mitteilung:")]

def is_global(line:str) -> bool:
    return any(k in line for k in GLOBAL_MARKER)

def store_lines(welt:int, lines:list[str]):
    if not lines: return
    data=[{"welt":welt,"timestamp":datetime.utcnow().isoformat(),"message":l} for l in lines]
    sb.table(TABLE).insert(data).execute()

def clean_old():
    cutoff=(datetime.utcnow()-timedelta(hours=48)).isoformat()
    sb.table(TABLE).delete().lt("timestamp",cutoff).execute()

def crawl_world(welt:int,url:str):
    try:
        r=requests.get(url,timeout=10); r.encoding="utf-8"
        if r.status_code!=200: return
        lines=extract_lines(r.text)
        new=[l for l in lines if l not in LAST_LINES[welt]]
        if not new: return
        gl=[l for l in new if is_global(l)]
        lc=[l for l in new if l not in gl]
        if lc: store_lines(welt,lc); LAST_LINES[welt].update(lc)
        if welt==1 and gl: store_lines(0,gl); LAST_GLOBAL.update(gl)
    except Exception as e: print(f"[Welt {welt}] Fehler: {e}")

# ── Flask Frontend ───────────────────────────────────────────────
app=Flask(__name__)

def fmt(msg:str):
    safe=html.escape(msg)
    return f"<span class='shout'>{safe}</span><br>" if "schreit:" in safe else f"{safe}<br>"

def fetch_from_db(welt:int):
    rows=(sb.table(TABLE).select("timestamp,message").eq("welt",welt).order("timestamp").execute().data)
    out,cur="",""
    for r in rows:
        ts=datetime.fromisoformat(r["timestamp"]); d=ts.strftime("%d.%m.%Y")
        if d!=cur: out+=f"<span class='datestamp'>📅 {d}</span><br>"; cur=d
        out+=fmt(r["message"])
    return out

@app.route("/")
def index():
    welt=request.args.get("welt")
    logs=fetch_from_db(0 if welt=="global" else int(welt)) if welt else ""
    tpl=open("template.html",encoding="utf-8").read()
    return render_template_string(tpl,logs=logs)

@app.route("/<path:filename>")
def static_files(filename): return send_from_directory(".",filename)

# ── Hintergrund-Worker ───────────────────────────────────────────
def worker():
    while True:
        for i,u in enumerate(WELTEN_URLS,1): crawl_world(i,u)
        clean_old(); time.sleep(300)

if __name__=="__main__":
    threading.Thread(target=worker,daemon=True).start()
    app.run(host="0.0.0.0",port=8080)
