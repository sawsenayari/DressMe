"""Clients LLM. GeminiClient pour la vraie exécution, MockLLM pour les tests hors ligne.
Les deux exposent la même méthode : json_call(prompt, images=None) -> dict."""
import json
import os
import re
import time

from .config import GEMINI_MODEL


def extract_json(text):
    """Extrait un objet JSON d'une réponse, même entourée de ```json ... ```."""
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if m:
            return json.loads(m.group(0))
        raise


class GeminiClient:
    def __init__(self, api_key=None, model=None, retries=3):
        from google import genai   # pip install google-genai
        key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("Clé API Gemini manquante (GEMINI_API_KEY).")
        self.client = genai.Client(api_key=key)
        self.model = model or GEMINI_MODEL
        self.retries = retries

    def json_call(self, prompt, images=None):
        contents = list(images or []) + [prompt]
        last = None
        for k in range(self.retries):
            try:
                r = self.client.models.generate_content(
                    model=self.model, contents=contents,
                    config={"response_mime_type": "application/json", "temperature": 0})
                return extract_json(r.text)
            except Exception as e:   # réseau, quota, JSON invalide...
                last = e
                time.sleep(2 ** k)
        raise RuntimeError(f"Appel Gemini échoué après {self.retries} essais : {last}")


class MockLLM:
    """Renvoie des réponses préparées (dict, ou fonction prompt -> dict). Pour les tests."""
    def __init__(self, responder):
        self.responder = responder
        self.calls = []

    def json_call(self, prompt, images=None):
        self.calls.append(prompt)
        return self.responder(prompt) if callable(self.responder) else self.responder
