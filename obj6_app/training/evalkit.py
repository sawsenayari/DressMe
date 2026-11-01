"""Outils communs aux évaluations : intervalle de confiance, appel du LLM juge, sauvegarde des rapports."""
import json, math, os, re
from pathlib import Path
from app.agent import _post, json_from

def wilson(k, n, z=1.96):
    if n == 0: return 0.0, 0.0
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - m) / d, (c + m) / d

def fmt(k, n):
    lo, hi = wilson(k, n); return f"{(k / n if n else 0):.2f} [IC95 {lo:.2f}-{hi:.2f}] ({k}/{n})"

async def judge_json(system, payload, model=None):
    """Appelle un LLM juge (température 0). `model` impose le modèle ; sinon LLM_MODEL_JUDGE."""
    user = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    j = await _post([{"role": "system", "content": system}, {"role": "user", "content": user}], "judge", model=model)
    return json_from(j["choices"][0]["message"]["content"])

def save(name, data):
    p = Path(os.getenv("DRESSME_REPORTS", "reports")); p.mkdir(parents=True, exist_ok=True)
    (p / f"eval_{name}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False)); return p
