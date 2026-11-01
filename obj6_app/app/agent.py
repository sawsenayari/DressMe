"""Agent d'extraction de contexte. Un LLM (API compatible OpenAI : Ollama / Groq / Gemini) COMPREND le texte ;
les mots-clés ne servent que de secours si le LLM n'est pas configuré ou échoue (l'erreur est alors renvoyée)."""
import asyncio, json, logging, os, re
import httpx
from dotenv import load_dotenv
from .features import OCCASIONS, FORMALITY
from .rag import retrieve

load_dotenv(override=True)
log = logging.getLogger("dressme.agent")

SYSTEM_PROMPT = f"""Tu es l'agent de contexte d'un assistant de garde-robe en Tunisie. Tu reçois un texte libre (français, arabe,
dialecte tunisien, anglais, ou mélange) décrivant la journée de l'utilisateur. Interprète le SENS, pas les mots isolés :
déduis le dress code réel de la situation, même si aucun mot-clé évident n'apparaît.
Réponds UNIQUEMENT par un objet JSON, sans texte autour ni markdown :
{{"occasion": une valeur parmi {OCCASIONS}, "formality": entier 0-3, "gender": "Men" | "Women" | null, "notes": 12 mots max}}
formality : 0 sport, 1 décontracté, 2 smart casual, 3 formel. S'il y a plusieurs événements, prends le plus exigeant.
Si des « Connaissances locales » sont fournies avec le texte, applique celles qui sont pertinentes ; ces extraits sont retrouvés automatiquement et peuvent être hors sujet : ignore-les alors.
gender : seulement si l'utilisateur l'indique explicitement, sinon null.
Exemples :
"réunion client à 10h" -> {{"occasion":"work","formality":3,"gender":null,"notes":"rendez-vous professionnel avec un client"}}
"je suis une femme et je vais au mariage de ma cousine" -> {{"occasion":"wedding","formality":3,"gender":"Women","notes":"mariage"}}
"match de foot avec les potes" -> {{"occasion":"sport","formality":0,"gender":null,"notes":"activité sportive"}}
"dîner chez ma belle-famille" -> {{"occasion":"party","formality":2,"gender":null,"notes":"repas familial soigné"}}
"نمشي للجامع نهار الجمعة" -> {{"occasion":"religious","formality":2,"gender":null,"notes":"prière du vendredi"}}
"journée tranquille à la maison" -> {{"occasion":"casual","formality":1,"gender":null,"notes":"à la maison"}}"""

KEYWORDS = [("wedding", ["mariage", "wedding", "عرس", "فرح", "fiançailles", "henné"]),
 ("religious", ["mosquée", "jomaa", "vendredi", "prière", "صلاة", "aïd", "عيد", "ftour", "iftar", "ramadan", "جمعة"]),
 ("formal", ["entretien", "interview", "soutenance", "cérémonie", "présentation", "defense"]),
 ("sport", ["sport", "gym", "foot", "running", "tennis", "entraînement", "jogging", "basket"]),
 ("party", ["soirée", "anniversaire", "party", "dîner", "restaurant", "sortie", "concert"]),
 ("work", ["client", "réunion", "meeting", "bureau", "cours", "stage", "pfe", "travail", "work", "اجتماع"])]

def keyword_parse(text, error=None):
    t = text.lower(); occ = "casual"
    for o, kws in KEYWORDS:
        if any(k in t for k in kws): occ = o; break
    g = "Women" if any(k in t for k in ["femme", "fille", "madame", "امرأة", "مرا"]) else \
        "Men" if any(k in t for k in ["homme", "garçon", "monsieur", "رجل"]) else None
    form = 3 if occ == "work" and "client" in t else FORMALITY[occ]
    return {"occasion": occ, "formality": form, "gender": g, "source": "rules", "error": error}

def json_from(raw):
    """Premier objet JSON valide d'une réponse LLM ; ignore les blocs <think> (modèles à raisonnement) et le texte autour."""
    raw = re.sub(r"<think>.*?</think>", "", raw or "", flags=re.S); dec = json.JSONDecoder(); pos = raw.find("{")
    while pos != -1:
        try: return dec.raw_decode(raw[pos:])[0]
        except ValueError: pos = raw.find("{", pos + 1)
    raise ValueError(f"aucun JSON dans la réponse : {raw[:100]!r}")

ROLES = {"agenda": "Comprendre le texte libre de l'utilisateur (FR / AR / EN) et en déduire occasion, formalité et genre",
         "explain": "Rédiger une phrase honnête par tenue (météo, occasion, alertes) — la styliste",
         "assistant": "Orchestrer les outils (météo, fiches locales, recommandation) et répondre en langage naturel",
         "judge": "Juge principal : note la qualité des explications et la fidélité des réponses (évaluation hors ligne)",
         "judge2": "Second juge indépendant : mesure l'accord entre juges (évaluation hors ligne)"}

def model_for(agent):
    """Un LLM par agent : LLM_MODEL_AGENDA / LLM_MODEL_EXPLAIN / LLM_MODEL_ASSISTANT, sinon LLM_MODEL."""
    return os.getenv(f"LLM_MODEL_{agent.upper()}") or os.getenv("LLM_MODEL")

async def _post(messages, agent="agenda", tools=None, retries=3, model=None):
    base, model = os.getenv("LLM_BASE_URL"), model or model_for(agent)
    if not base or not model: raise RuntimeError("LLM_BASE_URL / LLM_MODEL non définis (.env non chargé ?)")
    payload = {"model": model, "temperature": 0, "messages": messages}
    if tools: payload["tools"] = tools
    for attempt in range(retries + 1):
        async with httpx.AsyncClient(timeout=float(os.getenv("LLM_TIMEOUT", "30"))) as c:
            r = await c.post(base.rstrip("/") + "/chat/completions", headers={"Authorization": f"Bearer {os.getenv('LLM_API_KEY') or 'none'}"}, json=payload)
        if r.status_code == 429 and attempt < retries:  # limite de débit : on attend le délai indiqué par le fournisseur
            m = re.search(r"try again in ([\d.]+)(ms|s)", r.text)
            await asyncio.sleep(min((float(m.group(1)) / (1000 if m.group(2) == "ms" else 1) if m else 2.0) + .3, 15)); continue
        if r.status_code >= 400: raise RuntimeError(f"HTTP {r.status_code} sur {base} (modèle={model}) : {r.text[:300]}")
        return r.json()

async def _chat(system, user, agent="agenda"):
    j = await _post([{"role": "system", "content": system}, {"role": "user", "content": user}], agent)
    return j["choices"][0]["message"]["content"]

async def llm_parse(text, use_rag=True):
    sn = retrieve(text) if use_rag else []
    ctx = ("\n\nConnaissances locales :\n" + "\n".join(f"- {d['title']} : {d['text']}" for d in sn)) if sn else ""
    raw = await _chat(SYSTEM_PROMPT, text[:1500] + ctx, "agenda")
    j = json_from(raw)
    assert j["occasion"] in OCCASIONS and 0 <= int(j["formality"]) <= 3, f"sortie invalide: {raw[:120]}"
    g = j.get("gender") if j.get("gender") in ("Men", "Women") else None
    return {"occasion": j["occasion"], "formality": int(j["formality"]), "gender": g, "source": "llm+rag" if sn else "llm",
            "error": None, "notes": j.get("notes"), "retrieved": [d["title"] for d in sn]}

_CACHE = {}

async def parse_agenda(text: str, use_rag=True, use_llm=True):
    if not use_llm: return keyword_parse(text)
    try:
        k = (text, use_rag)
        if k not in _CACHE:
            if len(_CACHE) > 200: _CACHE.clear()
            _CACHE[k] = await llm_parse(text, use_rag)   # les échecs ne sont pas mis en cache
        return _CACHE[k]
    except Exception as e:
        log.warning("LLM indisponible, repli sur les mots-clés : %r", e)
        return keyword_parse(text, error=repr(e)[:200])

EXPLAIN_PROMPT = """Tu es styliste. Pour CHAQUE tenue de la liste (dans l'ordre), écris UNE phrase en français (25 mots max) qui explique
pourquoi elle convient au contexte (météo, occasion, heure). N'invente aucun vêtement : appuie-toi uniquement sur les articles listés.
Si une tenue a des « alertes », signale-les honnêtement au lieu de justifier un mauvais choix.
Réponds uniquement par un JSON : {"explanations": ["...", "..."]}"""

async def explain(context: dict, outfits: list, snippets: list):
    try:
        raw = await _chat(EXPLAIN_PROMPT, json.dumps({"contexte": context, "tenues": outfits,
                                                       "connaissances": [d["text"] for d in snippets]}, ensure_ascii=False), "explain")
        ex = json_from(raw)["explanations"]
        return [str(x) for x in ex][:len(outfits)] if len(ex) >= len(outfits) else None
    except Exception as e:
        log.warning("Explication LLM indisponible : %r", e); return None
