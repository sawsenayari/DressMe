from __future__ import annotations
import json
from pathlib import Path
from .prompts import SYSTEM


class VisionLLM:
    def __init__(self, model_id: str, load_4bit: bool = True, max_new_tokens: int = 200):
        import torch
        from transformers import AutoProcessor, AutoModelForImageTextToText, BitsAndBytesConfig
        self.max_new_tokens = max_new_tokens; kw = dict(device_map="auto")
        if load_4bit: kw["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16, bnb_4bit_quant_type="nf4")
        else: kw["dtype"] = torch.float16
        try: self.model = AutoModelForImageTextToText.from_pretrained(model_id, **kw).eval()
        except (TypeError, ValueError):
            if "dtype" in kw: kw["torch_dtype"] = kw.pop("dtype")
            self.model = AutoModelForImageTextToText.from_pretrained(model_id, **kw).eval()
        self.processor = AutoProcessor.from_pretrained(model_id, min_pixels=128 * 28 * 28, max_pixels=512 * 28 * 28)
        self.torch = torch

    def generate(self, image, prompt, system=SYSTEM):
        err = None
        for use_system in (True, False):                      # certains modèles n'acceptent pas le rôle « system »
            try:
                msgs = [{"role": "system", "content": [{"type": "text", "text": system}]}] if use_system else []
                msgs.append({"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt if use_system else system + "\n\n" + prompt}]})
                text = self.processor.apply_chat_template(msgs, add_generation_prompt=True)
                inp = self.processor(text=[text], images=[image], return_tensors="pt").to(self.model.device, dtype=self.model.dtype)
                with self.torch.no_grad(): out = self.model.generate(**inp, max_new_tokens=self.max_new_tokens, do_sample=False)
                return self.processor.batch_decode(out[:, inp["input_ids"].shape[1]:], skip_special_tokens=True)[0]
            except Exception as e: err = e
        raise err


class JsonlCache:
    """Cache disque des appels LLM (génération déterministe) ; une erreur n'est jamais mise en cache."""
    def __init__(self, path):
        self.path = Path(path); self.d = {}
        if self.path.exists():
            for line in open(self.path, encoding="utf-8"):
                try:
                    r = json.loads(line)
                    if not str(r.get("raw", "")).startswith("ERROR"): self.d[r["key"]] = r
                except Exception: pass
    def __contains__(self, k): return k in self.d
    def __getitem__(self, k): return self.d[k]
    def put(self, k, **v):
        r = dict(key=k, **v); self.d[k] = r
        with open(self.path, "a", encoding="utf-8") as f: f.write(json.dumps(r, ensure_ascii=False) + "\n")
