"""ÉVALUATION 3 — Assistant à outils : bons outils, bon ordre, arguments valides et cohérents avec la météo, réponse fidèle (juge).
python -m training.eval_tools [--mcp]"""
import argparse, asyncio, json, time
from app.assistant import run_assistant
from app.features import OCCASIONS
from .evalkit import fmt, judge_json, save

SC = [("Que mettre pour un match de foot avec mes amis demain à Sousse ?", "Women", {"sport"}), ("J'ai un entretien d'embauche à Tunis cet après-midi, que porter ?", "Men", {"formal", "work"}),
      ("Je vais à un mariage samedi soir à Sfax", "Women", {"wedding"}), ("Journée de cours à l'université, quel temps fait-il à Tunis ?", "Women", {"casual", "work"}),
      ("Prière du vendredi à Nabeul, une tenue ?", "Men", {"religious"}), ("Dîner au restaurant avec des amis ce soir à Bizerte", "Men", {"party", "casual"}),
      ("Réunion client à Tunis, je veux faire bonne impression", "Women", {"work", "formal"}), ("Sortie à la plage à Djerba", "Men", {"casual"})]
NEED = {"get_weather", "search_dress_code", "recommend_outfits"}
GROUND = """Tu vérifies le respect des faits (groundedness). On te donne le RÉSULTAT d'un outil (tenues avec leurs articles) et la RÉPONSE finale d'un assistant.
Liste les vêtements ou accessoires cités dans la réponse qui ne figurent PAS dans le résultat (synonymes proches acceptés, ex. « pantalon » pour « Trousers »).
Réponds uniquement par un JSON : {"ungrounded": ["..."], "grounded": true ou false}"""

def last(trace, name): return next((t for t in reversed(trace) if t["tool"] == name), None)

async def check(q, gender, occs, mcp):
    t0 = time.time(); r = await run_assistant(q, gender, uid="eval", use_mcp=mcp, keep_raw=True); tr = r["trace"]; names = [t["tool"] for t in tr]
    rec, wx = last(tr, "recommend_outfits"), last(tr, "get_weather"); res = {"all_tools": NEED <= set(names), "seconds": round(time.time() - t0, 1)}
    res["order_ok"] = bool(wx and rec and names.index("get_weather") < names.index("recommend_outfits"))
    a = rec["args"] if rec else {}
    res["args_valid"] = a.get("occasion") in OCCASIONS and isinstance(a.get("feels_like"), (int, float)) and a.get("gender") in ("Men", "Women")
    res["occasion_ok"] = a.get("occasion") in occs
    try: res["weather_consistent"] = abs(float(a["feels_like"]) - json.loads(wx["raw"])["feels_like"]) <= 1.5   # le LLM doit reprendre la météo reçue, pas l'inventer
    except Exception: res["weather_consistent"] = False
    try: res["grounded"] = bool((await judge_json(GROUND, {"resultat_outil": rec["raw"], "reponse": r["answer"]}))["grounded"]) if rec else False
    except Exception: res["grounded"] = None
    return res

async def amain(mcp=False):
    rows = []
    for q, g, o in SC:
        try: rows.append(await check(q, g, o, mcp))
        except Exception as e: print("échec :", q, repr(e)[:120]); rows.append({"error": repr(e)[:120]})
    n = len(rows); out = {"mode": "MCP" if mcp else "function calling local", "scenarios": n, "run_errors": sum("error" in r for r in rows)}
    for k in ("all_tools", "order_ok", "args_valid", "occasion_ok", "weather_consistent", "grounded"):
        v = [r[k] for r in rows if k in r and r[k] is not None]; out[k] = fmt(sum(v), len(v))
    out["mean_seconds"] = round(sum(r.get("seconds", 0) for r in rows) / n, 1); save("tools_mcp" if mcp else "tools", out); print(json.dumps(out, indent=2, ensure_ascii=False)); return out

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--mcp", action="store_true"); return asyncio.run(amain(ap.parse_args(argv).mcp))

if __name__ == "__main__": main()
