"""Outils appelables par le LLM (function calling JSON-schema). Les mêmes fonctions sont exposées via MCP (app/mcp_server.py)."""
from .features import OCCASIONS
from .rag import retrieve

TOOL_SPECS = [
 {"type": "function", "function": {"name": "get_weather", "description": "Météo du jour (température ressentie °C, probabilité de pluie 0-1, vent) pour une ville tunisienne.",
   "parameters": {"type": "object", "properties": {"city": {"type": "string", "description": "ex. Tunis, Sfax, Sousse"}}, "required": ["city"]}}},
 {"type": "function", "function": {"name": "search_dress_code", "description": "Cherche dans la base de connaissances locale des usages vestimentaires tunisiens (mariage, aïd, soutenance, chaleur, pluie…).",
   "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
 {"type": "function", "function": {"name": "recommend_outfits", "description": "Propose des tenues complètes (avec accessoires et alertes) depuis la garde-robe de l'utilisateur pour un contexte donné.",
   "parameters": {"type": "object", "properties": {"occasion": {"type": "string", "enum": OCCASIONS}, "feels_like": {"type": "number", "description": "température ressentie en °C"},
     "rain_prob": {"type": "number"}, "gender": {"type": "string", "enum": ["Men", "Women"]}, "k": {"type": "integer"}}, "required": ["occasion", "feels_like", "gender"]}}},
]

async def get_weather(city: str = "Tunis"):
    from .context import get_weather as w
    r = await w(city); return {k: r[k] for k in ("feels_like", "rain_prob", "wind", "source")}

async def search_dress_code(query: str):
    return [{"title": d["title"], "text": d["text"]} for d in retrieve(query)]

async def recommend_outfits(occasion: str, feels_like: float, gender: str = "Women", rain_prob: float = 0.0, k: int = 3, wardrobe=None, uid="anon"):
    from .main import RecommendRequest, recommend   # import tardif : évite l'import circulaire
    r = await recommend(RecommendRequest(occasion=occasion, gender=gender, weather={"feels_like": feels_like, "rain_prob": rain_prob}, k=k, uid=uid, wardrobe=wardrobe))
    return {"contexte": {k2: r["context"][k2] for k2 in ("occasion", "formality", "feels_like", "rain_prob")}, "message": r.get("message"),
            "tenues": [{"articles": [i["name"] for i in o["items"]], "accessoires": [a["name"] for a in o["accessories"]], "alertes": o["warnings"], "score": o["score"]} for o in r["outfits"]]}

DISPATCH = {"get_weather": get_weather, "search_dress_code": search_dress_code, "recommend_outfits": recommend_outfits}
