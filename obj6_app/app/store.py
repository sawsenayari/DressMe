"""Mémoire utilisateur (SQLite) : feedback, préférences par article, rotation des tenues portées."""
import json, os, sqlite3
from datetime import datetime, timedelta
from pathlib import Path

def _db():
    path = os.getenv("DRESSME_DB", "data/feedback.db"); Path(path).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE IF NOT EXISTS feedback(ts TEXT DEFAULT CURRENT_TIMESTAMP, features TEXT, accepted INT)")
    cols = {r[1] for r in c.execute("PRAGMA table_info(feedback)")}
    for col, typ in (("uid", "TEXT"), ("reason", "TEXT"), ("item_ids", "TEXT")):
        if col not in cols: c.execute(f"ALTER TABLE feedback ADD COLUMN {col} {typ}")  # migration depuis la v1
    c.execute("CREATE TABLE IF NOT EXISTS item_pref(uid TEXT, item_id TEXT, score REAL, last_worn TEXT, PRIMARY KEY(uid, item_id))")
    return c

def save_feedback(uid, features, accepted, reason=None, item_ids=()):
    # 👍 : pièces favorisées + "portée aujourd'hui" (rotation) ; 👎 « pas mon style » : pièces pénalisées ;
    # 👎 « trop chaud / trop habillé… » : erreur de contexte, loguée pour le réentraînement, sans punir les pièces.
    delta = 1.0 if accepted else (-1.0 if reason in (None, "style") else 0.0)
    now = datetime.now().isoformat()
    with _db() as c:
        c.execute("INSERT INTO feedback(uid,features,accepted,reason,item_ids) VALUES (?,?,?,?,?)",
                  (uid, json.dumps(features), int(accepted), reason, json.dumps(list(item_ids))))
        for i in item_ids:
            c.execute("INSERT OR IGNORE INTO item_pref VALUES (?,?,0,NULL)", (uid, i))
            c.execute("UPDATE item_pref SET score=MAX(-5,MIN(5,score+?)), last_worn=COALESCE(?,last_worn) WHERE uid=? AND item_id=?",
                      (delta, now if accepted else None, uid, i))

def prefs(uid):
    with _db() as c: return dict(c.execute("SELECT item_id, score FROM item_pref WHERE uid=?", (uid,)).fetchall())

def recent_worn(uid, days=3):
    lim = (datetime.now() - timedelta(days=days)).isoformat()
    with _db() as c: return {r[0] for r in c.execute("SELECT item_id FROM item_pref WHERE uid=? AND last_worn>?", (uid, lim))}

def stats(uid):
    with _db() as c:
        n, ok = c.execute("SELECT COUNT(*), COALESCE(SUM(accepted),0) FROM feedback WHERE uid=?", (uid,)).fetchone()
        reasons = dict(c.execute("SELECT reason, COUNT(*) FROM feedback WHERE uid=? AND accepted=0 AND reason IS NOT NULL GROUP BY reason", (uid,)).fetchall())
    return {"feedback": n, "accepted": ok, "acceptance_rate": round(ok / n, 3) if n else None, "rejection_reasons": reasons}
