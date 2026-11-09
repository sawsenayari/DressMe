"""Client LLM vision (Gemini via son API compatible OpenAI) : mode JSON, hyperparamètres, repli de modèle, mesures."""
import base64
import io
import time
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    model: str
    latency_ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0


def image_url(image, max_side):
    """Photo réduite (côté max) et encodée en data URL JPEG pour l'API."""
    img = image.convert("RGB"); img.thumbnail((max_side, max_side))
    buf = io.BytesIO(); img.save(buf, "JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


class GeminiVision:
    def __init__(self, api_key, cfg):
        from openai import OpenAI
        self.cfg = cfg
        self.client = OpenAI(api_key=api_key, base_url=cfg.base_url, max_retries=cfg.retries, timeout=cfg.timeout_s)

    def chat(self, messages):
        """Essaie chaque modèle dans l'ordre (quota gratuit par modèle) ; lève la dernière erreur si tous échouent."""
        last = None
        for m in self.cfg.models:
            t0 = time.perf_counter()
            try:
                r = self.client.chat.completions.create(
                    model=m, messages=messages, response_format={"type": "json_object"},
                    temperature=self.cfg.temperature, top_p=self.cfg.top_p, max_tokens=self.cfg.max_tokens)
            except Exception as e:   # quota du modèle, modèle indisponible : modèle suivant
                last = e
                continue
            u = getattr(r, "usage", None)
            return LLMResponse(r.choices[0].message.content or "", m, int(1000 * (time.perf_counter() - t0)),
                               getattr(u, "prompt_tokens", 0) or 0, getattr(u, "completion_tokens", 0) or 0)
        raise last or RuntimeError("aucun modèle configuré")
