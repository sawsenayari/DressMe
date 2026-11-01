"""Compare plusieurs LLM pour l'agent agenda (même jeu étiqueté, mêmes conditions) afin de choisir le modèle sur des mesures.
python -m training.eval_models [--models a,b,c] [--n 20]"""
import argparse, asyncio, os, time
from app import agent
from .eval_agent import GOLD, clean, run, summarize
from .evalkit import save

DEFAULT = "openai/gpt-oss-20b,openai/gpt-oss-120b,qwen/qwen3.8-27b,allam-2-7b"

async def amain(models, n=None):
    gold = clean(GOLD)[:n] if n else clean(GOLD); out = {"n": len(gold), "models": {}}; old = os.environ.get("LLM_MODEL_AGENDA")
    for m in models:
        os.environ["LLM_MODEL_AGENDA"] = m; agent._CACHE.clear(); t0 = time.time()
        rows = await run("rag", gold); out["models"][m] = summarize(rows) | {"seconds_per_phrase": round((time.time() - t0) / len(gold), 1)}
        print(m, {k: out["models"][m][k] for k in ("occasion_accuracy", "formality_mae", "answered_by_llm", "seconds_per_phrase")})
    if old is None: os.environ.pop("LLM_MODEL_AGENDA", None)
    else: os.environ["LLM_MODEL_AGENDA"] = old
    def key(m):   # on exige que le modèle réponde (≥ 90 % sans repli), puis la meilleure exactitude, puis la vitesse
        r = out["models"][m]; k, nn = r["answered_by_llm"].split("/"); return (int(k) / int(nn) >= .9, float(r["occasion_accuracy"].split()[0]), -r["seconds_per_phrase"])
    out["recommended_for_agenda"] = max(out["models"], key=key); save("models", out); print("recommandé :", out["recommended_for_agenda"]); return out

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--models", default=DEFAULT); ap.add_argument("--n", type=int, default=0); a = ap.parse_args(argv)
    return asyncio.run(amain([m.strip() for m in a.models.split(",") if m.strip()], a.n or None))

if __name__ == "__main__": main()
