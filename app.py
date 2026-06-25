"""Liaison funnel.

  GET  /                        landing page (Stripe PK injected)
  POST /signup                  capture lead → return signup_id + wa_link
  POST /create-payment-intent   Stripe PaymentIntent for 50p
  POST /payment-complete        mark signup as paid/active
  GET  /admin                   live feed
  POST /match/run               backstage matchmaking
  GET  /health
"""
import os
import time
import uuid
import urllib.parse
import pathlib

import psycopg2
import psycopg2.extras
import stripe
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

import config

stripe.api_key = config.STRIPE_SECRET_KEY

HERE = pathlib.Path(__file__).parent
app = FastAPI(title=config.BRAND)


def db():
    conn = psycopg2.connect(os.environ["DATABASE_URL"], sslmode="require")
    conn.autocommit = False
    return conn


def ensure_tables(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS signups (
                id TEXT PRIMARY KEY,
                ref TEXT,
                linkedin TEXT,
                gender TEXT,
                seeking TEXT,
                location TEXT,
                status TEXT,
                created_at DOUBLE PRECISION
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                id TEXT PRIMARY KEY,
                a TEXT,
                b TEXT,
                score INTEGER,
                why TEXT,
                icebreaker TEXT,
                status TEXT,
                created_at DOUBLE PRECISION
            )
        """)
    conn.commit()


@app.on_event("startup")
async def startup():
    conn = db()
    ensure_tables(conn)
    conn.close()


@app.get("/", response_class=HTMLResponse)
async def home():
    html = (HERE / "index.html").read_text()
    return html.replace("__STRIPE_PK__", config.STRIPE_PUBLISHABLE_KEY)


@app.post("/signup")
async def signup(req: Request):
    b = await req.json()
    linkedin = (b.get("linkedin") or "").strip()
    if "linkedin.com/" not in linkedin.lower():
        return JSONResponse({"error": "valid LinkedIn URL required"}, status_code=400)

    ref = uuid.uuid4().hex[:6].upper()
    signup_id = "u_" + uuid.uuid4().hex[:12]

    conn = db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO signups VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (signup_id, ref, linkedin, b.get("gender"), b.get("seeking"),
                 (b.get("location") or "").strip(), "PENDING_PAYMENT", time.time())
            )
        conn.commit()
    finally:
        conn.close()

    text = f"Hi! I'm ready to meet someone ❤ My code is {ref}"
    wa_link = (f"https://wa.me/{config.CONCIERGE_WA_NUMBER}"
               f"?text={urllib.parse.quote(text)}")
    return {"ok": True, "ref": ref, "signup_id": signup_id, "wa_link": wa_link}


@app.post("/create-payment-intent")
async def create_payment_intent(req: Request):
    b = await req.json()
    signup_id = b.get("signup_id", "")
    try:
        intent = stripe.PaymentIntent.create(
            amount=config.UNLOCK_PRICE_PENCE,
            currency=config.UNLOCK_CURRENCY,
            metadata={"signup_id": signup_id},
            automatic_payment_methods={"enabled": True},
            description="Liaison — date unlock (refunded if no date within 7 days)",
        )
        conn = db()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE signups SET status='PAYMENT_INITIATED' WHERE id=%s", (signup_id,))
            conn.commit()
        finally:
            conn.close()
        return {"client_secret": intent.client_secret}
    except stripe.StripeError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.post("/payment-complete")
async def payment_complete(req: Request):
    b = await req.json()
    signup_id = b.get("signup_id", "")
    conn = db()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE signups SET status='NEW' WHERE id=%s", (signup_id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@app.post("/match/run")
async def match_run():
    import matching
    return matching.run()


@app.get("/health")
async def health():
    return {"ok": True, "brand": config.BRAND}


@app.get("/admin", response_class=HTMLResponse)
async def admin():
    conn = db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM signups ORDER BY created_at DESC")
            su = cur.fetchall()
            cur.execute("SELECT * FROM matches ORDER BY created_at DESC")
            ms = cur.fetchall()
    finally:
        conn.close()

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
