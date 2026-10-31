"""Client LLM v3 : texte + image, API compatible OpenAI, cache disque, gestion des quotas GRATUITS.

Fournisseurs gratuits (vérifiés fin octobre 2026 — les quotas changent, re-vérifie dans la console) :
- Google Gemini, avec vision : base_url https://generativelanguage.googleapis.com/v1beta/openai/ ;
  modèles Flash gratuits (gemini-3.8-flash, 3.7, 3.6...) ; limites affichées dans AI Studio ; en palier gratuit,
  le contenu envoyé peut servir à améliorer les produits Google (aucun souci pour des photos du dataset).
- Groq, texte seul pour gpt-oss : openai/gpt-oss-120b, openai/gpt-oss-20b, qwen/qwen3.8-27b :
  30 req/min, 8 000 tokens/min, 200 000 tokens/jour, PAR MODÈLE.
Le cache disque évite de « payer » deux fois le même appel : relancer une cellule coûte 0 token.
"""
import base64
import hashlib
import io
import json
import os
import re
import time
from collections import deque

from .llm import extract_json

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GROQ_URL = "https://api.groq.com/openai/v1"


class QuotaExhausted(RuntimeError):
    """Quota épuisé pour longtemps (jour, ou attente > max_wait) : inutile d'insister, le cache garde tout."""


class ModelUnavailable(QuotaExhausted):
    """Modèle inconnu ou retiré pour ce compte : FallbackLLM passe au suivant au lieu de réessayer."""


def to_data_url(img, max_side=1024):
    """PIL.Image ou chemin -> (data URL JPEG base64, empreinte courte pour le cache)."""
    from PIL import Image
    if isinstance(img, (str, os.PathLike)):
        img = Image.open(img)
    img = img.convert("RGB")
    if max(img.size) > max_side:
        k = max_side / max(img.size)
        img = img.resize((round(img.width * k), round(img.height * k)))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    raw = buf.getvalue()
    return "data:image/jpeg;base64," + base64.b64encode(raw).decode(), hashlib.sha256(raw).hexdigest()[:16]


def retry_after_seconds(msg):
    """Lit « try again in 1h2m3.5s » / « retry after 20s » dans un message d'erreur ; None si absent."""
    m = re.search(r"(?:try again in|retry (?:in|after)|retrydelay\W+)\s*(?:(\d+)h)?\s*(?:(\d+)m(?!s))?\s*([\d.]+)\s*s",
                  msg.lower())
    if not m:
        return None
    return int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + float(m.group(3))


def is_daily_quota(msg):
    msg = msg.lower()
    return (any(k in msg for k in ("per day", "perday", "daily")) or re.search(r"limit:\s*0\b", msg) is not None)


class OpenAICompatClient2:
    """json_call(prompt, images=None) -> dict. Même interface que llm.GeminiClient / llm.MockLLM."""

    def __init__(self, api_key=None, model="gemini-3.8-flash", base_url=GEMINI_URL, *, vision=True,
                 reasoning_effort=None, temperature=None, retries=6, cache_dir=None, tpm_limit=None,
                 max_wait=120, client=None, sleep=time.sleep, now=time.time, name=None):
        if client is None:
            from openai import OpenAI          # !pip install openai
            client = OpenAI(api_key=api_key, base_url=base_url)
        self.client, self.model, self.vision = client, model, vision
        self.reasoning_effort, self.temperature = reasoning_effort, temperature
        self.retries, self.max_wait, self.tpm_limit = retries, max_wait, tpm_limit
        self.cache_dir, self.sleep, self.now = cache_dir, sleep, now
        self.name = name or model
        self.json_mode = True
        self.usage = {"appels": 0, "cache": 0, "tokens_entree": 0, "tokens_sortie": 0}
        self._window = deque()                 # (instant, tokens) sur les 60 dernières secondes
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)

    # ---- cache disque ----
    def _key(self, prompt, img_hashes):
        raw = json.dumps([self.model, self.reasoning_effort, self.temperature, prompt, img_hashes], ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def _cache_get(self, key):
        if not self.cache_dir:
            return None
        path = os.path.join(self.cache_dir, key + ".json")
        if os.path.exists(path):
            try:
                return json.load(open(path, encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return None
        return None

    def _cache_put(self, key, out):
        if self.cache_dir:
            with open(os.path.join(self.cache_dir, key + ".json"), "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False)

    # ---- plafond de tokens par minute (Groq gratuit : 8 000) ----
    def _throttle(self, estimate):
        if not self.tpm_limit:
            return
        while True:
            t = self.now()
            while self._window and t - self._window[0][0] >= 60:
                self._window.popleft()
            used = sum(n for _, n in self._window)
            if not self._window or used + estimate <= self.tpm_limit:
                return
            self.sleep(max(0.5, 60 - (t - self._window[0][0]) + 0.5))

    def json_call(self, prompt, images=None):
        urls = [to_data_url(i) for i in (images or [])]
        if urls and not self.vision:
            raise ValueError(f"{self.name} : ce client est configuré sans vision (vision=False).")
        key = self._key(prompt, [h for _, h in urls])
        hit = self._cache_get(key)
        if hit is not None:
            self.usage["cache"] += 1
            return hit
        content = prompt if not urls else [{"type": "text", "text": prompt}] + [
            {"type": "image_url", "image_url": {"url": u}} for u, _ in urls]
        messages = [{"role": "user", "content": content}]
        last, parse_errors = None, 0
        for k in range(self.retries):
            try:
                self._throttle(len(prompt) // 3 + 900)
                kw = {}
                if self.temperature is not None:       # par défaut on n'impose rien : Google déconseille de baisser la
                    kw["temperature"] = self.temperature   # température sur Gemini 3 ; le cache fige de toute façon la réponse
                if self.json_mode:
                    kw["response_format"] = {"type": "json_object"}
                if self.reasoning_effort:
                    kw["reasoning_effort"] = self.reasoning_effort
                r = self.client.chat.completions.create(model=self.model, messages=messages, **kw)
                out = extract_json(r.choices[0].message.content)
                if not isinstance(out, dict):
                    raise ValueError("réponse JSON qui n'est pas un objet")
                u = getattr(r, "usage", None)
                tin = getattr(u, "prompt_tokens", 0) or 0
                tout = getattr(u, "completion_tokens", 0) or 0
                self.usage["appels"] += 1
                self.usage["tokens_entree"] += tin
                self.usage["tokens_sortie"] += tout
                self._window.append((self.now(), tin + tout))
                out["_modele"] = self.model
                self._cache_put(key, out)
                return out
            except QuotaExhausted:
                raise
            except Exception as e:             # réseau, quota, JSON invalide...
                last = e
                msg = str(e).lower()
                status = getattr(e, "status_code", None)
                if self.json_mode and ("response_format" in msg or (status == 400 and "json" in msg)):
                    self.json_mode = False     # ce modèle n'a pas le mode JSON : on s'en passe
                    continue
                if is_daily_quota(msg):
                    raise QuotaExhausted(f"{self.name} : quota journalier épuisé ({str(e)[:160]})") from e
                if status in (401, 403) or "invalid api key" in msg or "api key not valid" in msg:
                    raise RuntimeError(f"{self.name} : clé API refusée ({str(e)[:120]}). "
                                       f"Vérifie le secret Colab.") from e
                if status == 404 or ("model" in msg and any(w in msg for w in (
                        "not found", "does not exist", "decommissioned", "no longer supported"))):
                    raise ModelUnavailable(f"{self.name} : modèle indisponible pour ce compte ({str(e)[:120]})") from e
                if status == 429 or "429" in msg or "rate limit" in msg or "resource_exhausted" in msg or "quota" in msg:
                    wait = retry_after_seconds(msg)
                    if wait is not None and wait > self.max_wait:
                        raise QuotaExhausted(f"{self.name} : quota épuisé, réessayer dans {wait / 60:.0f} min") from e
                    self.sleep(min(self.max_wait, (wait or 30) + 2))
                elif isinstance(e, ValueError):    # réponse non JSON : un seul nouvel essai (température 0 = même sortie)
                    parse_errors += 1
                    if parse_errors >= 2:
                        break
                    self.sleep(1)
                elif status in (400, 413, 422):
                    raise RuntimeError(f"{self.name} : requête refusée ({status}) : {str(e)[:200]}") from e
                else:
                    self.sleep(min(self.max_wait, 2 ** k))
        raise RuntimeError(f"{self.name} : appel échoué après {self.retries} essais : {last}")


class FallbackLLM:
    """Essaie les clients dans l'ordre ; quand l'un a épuisé son quota gratuit, passe au suivant.
    Les quotas gratuits sont PAR MODÈLE : enchaîner plusieurs modèles multiplie la capacité du jour.
    Chaque réponse porte `_modele` : n'enchaîne pas de modèles différents dans une même comparaison finale."""

    def __init__(self, clients):
        self.clients = list(clients)
        self.vision = any(c.vision for c in self.clients)
        self.name = " > ".join(c.name for c in self.clients)
        self.dead = set()

    def json_call(self, prompt, images=None):
        errs = []
        for i, c in enumerate(self.clients):
            if i in self.dead or (images and not c.vision):
                continue
            try:
                return c.json_call(prompt, images=images)
            except QuotaExhausted as e:
                self.dead.add(i)
                errs.append(str(e)[:110])
        raise QuotaExhausted(" | ".join(errs) or "aucun client disponible pour cette requête")

    @property
    def usage(self):
        tot = {"appels": 0, "cache": 0, "tokens_entree": 0, "tokens_sortie": 0}
        for c in self.clients:
            for k in tot:
                tot[k] += c.usage[k]
        return tot
