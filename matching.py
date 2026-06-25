"""The matchmaking brain (backstage, async — runs on your Mac).

Two stages:
  1. Hard filter — mutual orientation + same location. Cheap, deterministic,
     no model. This is what keeps matches sane.
  2. Hermes — for each surviving candidate pair, score 0-100 + a warm
     'why you two' + an icebreaker. Latency-tolerant, so local hosting is fine.

Run it from the admin page button, on a timer, or `python -c "import matching;matching.run()"`.
"""
import json
import os
import time
import uuid

import psycopg2
import psycopg2.extras
from openai import OpenAI
import config

_client = OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)


def _db():
    conn = psycopg2.connect(os.environ["DATABASE_URL"], sslmode="require")
    conn.autocommit = False
    return conn


def _orientation_ok(a, b) -> bool:
    """Does each person want to meet the other's gender?"""
    def wants(seeker, target_gender):
        s = seeker["seeking"]
        if s == "anyone":
            return True
        return (s == "women" and target_gender == "woman") or \
               (s == "men" and target_gender == "man")
    return wants(a, b["gender"]) and wants(b, a["gender"])


def _same_area(a, b) -> bool:
    la, lb = (a["location"] or "").lower().strip(), (b["location"] or "").lower().strip()
    return bool(la) and (la in lb or lb in la)


def _hermes_pair(a, b) -> dict:
    """Ask Hermes for score + why + icebreaker. Returns dict; degrades gracefully."""
    prompt = f"""You are a warm, witty professional matchmaker. Two people opted in.

Person A: LinkedIn {a['linkedin']} | based {a['location']}
Person B: LinkedIn {b['linkedin']} | based {b['location']}

Reply with ONLY compact JSON, no markdown:
{{"score": <0-100 compatibility>, "why": "<one charming sentence on why they might click>", "icebreaker": "<one playful opening line the matchmaker can send>"}}"""
    try:
        r = _client.chat.completions.create(
            model=config.LLM_MODEL, max_tokens=220,
            messages=[{"role": "user", "content": prompt}],
        )
        txt = r.choices[0].message.content.strip()
        txt = txt[txt.find("{"): txt.rfind("}") + 1]
        d = json.loads(txt)
        return {"score": int(d.get("score", 60)),
                "why": str(d.get("why", "")), "icebreaker": str(d.get("icebreaker", ""))}
    except Exception as e:
        return {"score": 60, "why": "Both opted in and are in the same city.",
                "icebreaker": f"You two might just get on — shall I make the introduction? ({e.__class__.__name__})"}


def run() -> dict:
    """Match every unmatched signup to its best available candidate."""
    conn = _db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM signups WHERE status='NEW' ORDER BY created_at")
            people = [dict(r) for r in cur.fetchall()]
            cur.execute("SELECT a, b FROM matches")
            already = set()
            for m in cur.fetchall():
                already.add(m["a"]); already.add(m["b"])

        made = 0
        used = set(already)
        for a in people:
            if a["id"] in used:
                continue
            cands = [b for b in people
                     if b["id"] != a["id"] and b["id"] not in used
                     and _orientation_ok(a, b) and _same_area(a, b)]
            if not cands:
                continue
            best, best_meta = None, None
            for b in cands:
                meta = _hermes_pair(a, b)
                if best is None or meta["score"] > best_meta["score"]:
                    best, best_meta = b, meta
            mid = "m_" + uuid.uuid4().hex[:12]
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO matches VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (mid, a["id"], best["id"], best_meta["score"], best_meta["why"],
                     best_meta["icebreaker"], "PENDING_UNLOCK", time.time()))
                cur.execute(
                    "UPDATE signups SET status='MATCHED' WHERE id IN (%s,%s)",
                    (a["id"], best["id"]))
            conn.commit()
            used.add(a["id"]); used.add(best["id"]); made += 1
    finally:
        conn.close()
    return {"matches_made": made}


def seed_demo(n: int = 6) -> dict:
    """Drop a few plausible profiles so you can demo matching before real signups land."""
    conn = _db()
    samples = [
        ("https://linkedin.com/in/maya-founder", "woman", "men", "London"),
        ("https://linkedin.com/in/tomdev", "man", "women", "London"),
        ("https://linkedin.com/in/priya-pm", "woman", "anyone", "London"),
        ("https://linkedin.com/in/james-sales", "man", "women", "London"),
        ("https://linkedin.com/in/alex-design", "other", "anyone", "London"),
        ("https://linkedin.com/in/sofia-growth", "woman", "men", "London"),
    ]
    try:
        for li, g, s, loc in samples[:n]:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO signups VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    ("u_" + uuid.uuid4().hex[:12], uuid.uuid4().hex[:6].upper(),
                     li, g, s, loc, "NEW", time.time()))
        conn.commit()
    finally:
        conn.close()
    return {"seeded": min(n, len(samples))}
