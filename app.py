"""Launch-critical funnel.

  GET  /            the landing page
  POST /signup      capture a lead, return the WhatsApp handoff link
  GET  /admin       live signup + match feed (watch your launch)
  POST /match/run   backstage: run the matchmaking brain over current pool
  GET  /health

Signup does NOT take payment — the £1 unlock happens later, in the WhatsApp
flow, once a match exists. That keeps signup a 15-second, zero-friction step.
"""
import json
import sqlite3
import time
import uuid
import urllib.parse
import pathlib

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

import config

HERE = pathlib.Path(__file__).parent
app = FastAPI(title=f"{config.BRAND}")


def db():
    c = sqlite3.connect(config.DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS signups(
        id TEXT PRIMARY KEY, ref TEXT, linkedin TEXT, gender TEXT, seeking TEXT,
        location TEXT, status TEXT, created_at REAL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS matches(
        id TEXT PRIMARY KEY, a TEXT, b TEXT, score INTEGER, why TEXT,
        icebreaker TEXT, status TEXT, created_at REAL)""")
    c.commit()
    return c


@app.get("/", response_class=HTMLResponse)
async def home():
    return (HERE / "index.html").read_text()


@app.post("/signup")
async def signup(req: Request):
    b = await req.json()
    linkedin = (b.get("linkedin") or "").strip()
    if "linkedin.com/" not in linkedin.lower():
        return JSONResponse({"error": "valid LinkedIn URL required"}, status_code=400)
    ref = uuid.uuid4().hex[:6].upper()
    row = {
        "id": "u_" + uuid.uuid4().hex[:12], "ref": ref, "linkedin": linkedin,
        "gender": b.get("gender"), "seeking": b.get("seeking"),
        "location": (b.get("location") or "").strip(),
        "status": "NEW", "created_at": time.time(),
    }
    c = db()
    c.execute("INSERT INTO signups VALUES (:id,:ref,:linkedin,:gender,:seeking,"
              ":location,:status,:created_at)", row)
    c.commit(); c.close()

    text = f"Hi! I'm ready to meet someone ❤ My code is {ref}"
    wa_link = (f"https://wa.me/{config.CONCIERGE_WA_NUMBER}"
               f"?text={urllib.parse.quote(text)}")
    return {"ok": True, "ref": ref, "wa_link": wa_link}


@app.post("/match/run")
async def match_run():
    import matching
    return matching.run()


@app.get("/health")
async def health():
    return {"ok": True, "brand": config.BRAND}


@app.get("/admin", response_class=HTMLResponse)
async def admin():
    c = db()
    su = c.execute("SELECT * FROM signups ORDER BY created_at DESC").fetchall()
    ms = c.execute("SELECT * FROM matches ORDER BY created_at DESC").fetchall()
    c.close()
    rows = "".join(
        f"<tr><td>{s['ref']}</td><td><a href='{s['linkedin']}' target='_blank'>link</a></td>"
        f"<td>{s['gender']}&rarr;{s['seeking']}</td><td>{s['location']}</td>"
        f"<td>{s['status']}</td></tr>" for s in su)
    mrows = "".join(
        f"<tr><td>{m['score']}</td><td>{m['why']}</td><td>{m['icebreaker']}</td>"
        f"<td>{m['status']}</td></tr>" for m in ms)
    return f"""<html><head><meta charset=utf-8><title>admin</title>
    <style>body{{font:14px system-ui;margin:24px;color:#222}}
    h2{{margin-top:28px}} table{{border-collapse:collapse;width:100%}}
    td,th{{border-bottom:1px solid #eee;padding:7px 10px;text-align:left;vertical-align:top}}
    button{{padding:8px 14px;font-size:14px}}</style></head><body>
    <h1>{config.BRAND} — control</h1>
    <button onclick="fetch('/match/run',{{method:'POST'}}).then(()=>location.reload())">
      Run matchmaking</button>
    <h2>Signups ({len(su)})</h2>
    <table><tr><th>ref</th><th>li</th><th>pref</th><th>where</th><th>status</th></tr>{rows}</table>
    <h2>Matches ({len(ms)})</h2>
    <table><tr><th>score</th><th>why</th><th>icebreaker</th><th>status</th></tr>{mrows}</table>
    </body></html>"""
