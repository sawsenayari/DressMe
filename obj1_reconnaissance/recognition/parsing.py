from __future__ import annotations
import json, re
import numpy as np
from .taxonomy import CATEGORIES, CAT_SYN, ATTR_SYN, ATTR_ALLOWED


def _lab(v): return str(v).strip().lower().replace(" ", "_").replace("-", "_") if v is not None else "unknown"


def extract_json(text):
    if not isinstance(text, str): return None
    t = text.strip().replace("```json", "").replace("```", ""); i, j = t.find("{"), t.rfind("}")
    if i < 0 or j <= i: return None
    s = t[i:j + 1]
    for cand in (s, re.sub(r",\s*}", "}", s)):
        try: return json.loads(cand)
        except Exception: pass
    return None


def parse_answer(raw) -> dict:
    out = dict(valid=False, category="invalid", color="unknown", gender="unknown", season="unknown", occasion="unknown",
               confidence=0.0, evidence="", alternative="", issues=[], raw=raw, latency=0.0)
    o = extract_json(raw)
    if not isinstance(o, dict): out["issues"] = ["no_json"]; return out
    cat = _lab(o.get("category")); cat = CAT_SYN.get(cat, cat); issues = []
    for attr, allowed in ATTR_ALLOWED.items():
        v = _lab(o.get(attr)); v = ATTR_SYN[attr].get(v, v)
        if v in allowed or v == "unknown": out[attr] = v
        else: out[attr] = "unknown"; issues.append(f"{attr}={v}")
    try: conf = float(o.get("confidence", 0.0))
    except Exception: conf = 0.0
    if 1 < conf <= 100: conf /= 100
    alt = _lab(o.get("alternative")); alt = CAT_SYN.get(alt, alt)
    if cat not in CATEGORIES: issues.append(f"category={cat}")
    out.update(valid=cat in CATEGORIES, category=cat if cat in CATEGORIES else "invalid", confidence=float(np.clip(conf, 0, 1)),
               evidence=str(o.get("evidence", ""))[:160], alternative=alt if alt in CATEGORIES else "", issues=issues)
    return out
