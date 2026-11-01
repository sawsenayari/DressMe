"""Vérifie que chaque agent joint bien son modèle (et que l'assistant sait appeler des outils). python -m training.check_llm"""
import asyncio, time
from app.agent import ROLES, _post, json_from, model_for
from app.tools import TOOL_SPECS

async def one(agent):
    model = model_for(agent); t0 = time.time()
    if not model: return {"agent": agent, "model": None, "statut": "NON DÉFINI (variable LLM_MODEL_" + agent.upper() + ")"}
    try:
        j = await _post([{"role": "user", "content": 'Réponds uniquement par ce JSON : {"ok": true}'}], agent, model=model)
        ok = json_from(j["choices"][0]["message"]["content"]).get("ok") is True; res = {"agent": agent, "model": model, "statut": "OK" if ok else "réponse inattendue"}
        if agent == "assistant":   # l'assistant doit savoir appeler un outil
            j = await _post([{"role": "user", "content": "Quel temps fait-il à Tunis ? Utilise un outil."}], agent, TOOL_SPECS[:1], model=model)
            res["appel_d_outils"] = "OK" if j["choices"][0]["message"].get("tool_calls") else "NON : choisis un autre modèle pour l'assistant"
    except Exception as e: res = {"agent": agent, "model": model, "statut": "ERREUR " + repr(e)[:160]}
    return res | {"secondes": round(time.time() - t0, 1)}

async def amain():
    rows = [await one(a) for a in ROLES]
    for r in rows: print(r)
    return rows

if __name__ == "__main__": asyncio.run(amain())
