"""Crop (découpe du vêtement) : photo de téléphone  ->  une ou plusieurs images « vêtement seul, fond blanc, 512 px ».

Méthode du document d'orchestration :
  * photo PORTÉE (une personne)  : SegFormer B2 (parsing de vêtements) -> un masque par pièce (haut, bas, robe, chaussures, sac, écharpe…)
  * photo À PLAT                 : rembg retire le fond
  * contrôle qualité             : masque trop petit / vêtement coupé par le cadre -> `quality.ok = False` (la fiche sera needs_review)

!! Le crop est proposé à Amir (app/segment.py).  Ce module est le REPLI : si Amir livre son code, branche-le avec
   DRESSME_CROP_HOOK='module:function'  (function(PIL.Image) -> list[(name, slot_hint, PIL.Image 512x512)]) — rien d'autre à changer.
!! Le modèle SegFormer ci-dessous est celui que je connais pour le parsing de vêtements ; son identifiant (cfg.seg_model_id) et le
   numéro des classes sont à vérifier à la première exécution (la cellule de test du notebook affiche les classes trouvées)."""
from __future__ import annotations
import importlib, os
from dataclasses import dataclass, field
import numpy as np
from PIL import Image
from .imaging import normalise_crop, open_rgb

# classes du modèle mattmdjaga/segformer_b2_clothes (ordre de sa carte de modèle ; vérifié par `describe_labels` au chargement)
SEG_LABELS = {0: "background", 1: "hat", 2: "hair", 3: "sunglasses", 4: "upper", 5: "skirt", 6: "pants", 7: "dress", 8: "belt", 9: "left_shoe",
              10: "right_shoe", 11: "face", 12: "left_leg", 13: "right_leg", 14: "left_arm", 15: "right_arm", 16: "bag", 17: "scarf"}
# (nom de la pièce, classes fusionnées, slot probable)
PIECES = [("top", [4], "top"), ("bottom", [5, 6], "bottom"), ("onepiece", [7], "onepiece"), ("shoes", [9, 10], "footwear"),
          ("bag", [16], "bag"), ("hat", [1], "accessory"), ("scarf", [17], "accessory"), ("belt", [8], "accessory")]
MAJOR = {"top", "bottom", "onepiece"}      # grandes pièces ; les autres (chaussures, sac, accessoires) sont « petites »
PERSON = [2, 11, 12, 13, 14, 15]          # cheveux, visage, jambes, bras : indices qu'une personne est dans la photo


@dataclass
class CropPiece:
    name: str
    slot_hint: str | None
    image: Image.Image
    area_frac: float = 1.0
    quality: dict = field(default_factory=lambda: dict(ok=True, reasons=[]))


class SegformerClothes:
    def __init__(self, model_id: str = "mattmdjaga/segformer_b2_clothes", device: str | None = None):
        import torch
        from transformers import SegformerImageProcessor, AutoModelForSemanticSegmentation
        self.torch = torch; self.dev = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.proc = SegformerImageProcessor.from_pretrained(model_id); self.model = AutoModelForSemanticSegmentation.from_pretrained(model_id).eval().to(self.dev)
        self.id2label = {int(k): v for k, v in self.model.config.id2label.items()}

    def describe_labels(self) -> str:
        norm = lambda v: {"upper_clothes": "upper"}.get(str(v).lower().replace("-", "_").replace(" ", "_"), str(v).lower().replace("-", "_").replace(" ", "_"))
        diff = {k: (SEG_LABELS.get(k), v) for k, v in self.id2label.items() if SEG_LABELS.get(k, "").lower() != norm(v)}
        return "classes SegFormer cohérentes avec le code" if not diff else f"⚠️ classes différentes de celles attendues (à corriger dans SEG_LABELS) : {diff}"

    def __call__(self, image: Image.Image) -> np.ndarray:
        torch = self.torch
        with torch.no_grad():
            lg = self.model(**self.proc(images=image, return_tensors="pt").to(self.dev)).logits
            up = torch.nn.functional.interpolate(lg, size=image.size[::-1], mode="bilinear", align_corners=False)
        return up.argmax(1)[0].cpu().numpy()


_SESSIONS: dict = {}


def rembg_remove(image: Image.Image, model: str = "u2net") -> Image.Image:
    """RGBA (fond transparent). Repli sans rembg : seuil sur le blanc (valable seulement pour une photo déjà sur fond clair)."""
    try:
        from rembg import remove, new_session
        if model not in _SESSIONS: _SESSIONS[model] = new_session(model)
        return remove(image, session=_SESSIONS[model]).convert("RGBA")
    except Exception as e:                                                 # rembg absent / modèle non téléchargeable
        print("⚠️ rembg indisponible (", repr(e)[:80], ") -> repli par seuil de blanc")
        a = np.asarray(image.convert("RGB")); m = ~(a >= 235).all(-1); out = image.convert("RGBA"); out.putalpha(Image.fromarray((m * 255).astype("uint8"))); return out


def piece_from_mask(image: Image.Image, mask: np.ndarray, size: int = 512, margin: float = 0.04, min_area: float = 0.01, name="item", slot_hint=None) -> CropPiece | None:
    H, W = mask.shape; area = float(mask.mean()); ys, xs = np.where(mask)
    if len(ys) == 0: return None
    reasons = []
    if area < min_area: reasons.append("mask_too_small")
    border = (mask[0].sum() + mask[-1].sum() + mask[:, 0].sum() + mask[:, -1].sum()) / max(1, mask.sum())
    if border > 0.02: reasons.append("garment_cut_by_frame")               # le vêtement touche le bord de la photo
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1; my, mx = int((y1 - y0) * margin), int((x1 - x0) * margin)
    y0, y1, x0, x1 = max(0, y0 - my), min(H, y1 + my), max(0, x0 - mx), min(W, x1 + mx)
    rgb = np.asarray(image.convert("RGB"))[y0:y1, x0:x1].copy(); m = mask[y0:y1, x0:x1]; rgb[~m] = 255             # fond blanc hors masque
    if min(y1 - y0, x1 - x0) < 64: reasons.append("crop_low_resolution")
    return CropPiece(name, slot_hint, normalise_crop(Image.fromarray(rgb), size), area, dict(ok=not reasons, reasons=reasons))


class Cropper:
    def __init__(self, size: int = 512, mode: str = "auto", seg_model_id: str = "mattmdjaga/segformer_b2_clothes", segmenter=None, remover=None,
                 hook=None, min_area: float = 0.01, rembg_model: str = "u2net", strategy: str = "outfit", min_area_main: float = 0.03,
                 min_area_small: float = 0.01, min_side: int = 96, accessories: bool = True):
        self.rembg_model, self.strategy, self.min_area_main, self.min_area_small, self.min_side, self.accessories = rembg_model, strategy, min_area_main, min_area_small, min_side, accessories
        self.size, self.mode, self.seg_model_id, self._seg, self._rem, self.hook, self.min_area = size, mode, seg_model_id, segmenter, remover, hook, min_area

    @classmethod
    def from_config(cls, cfg):
        spec = os.environ.get("DRESSME_CROP_HOOK"); hook = None
        if spec: mod, fn = spec.split(":"); hook = getattr(importlib.import_module(mod), fn)
        c = cls(cfg.crop_size, cfg.crop_mode, cfg.seg_model_id, hook=hook, rembg_model=cfg.rembg_model); c.apply_config(cfg); return c

    def apply_config(self, cfg):
        """Relit les réglages de crop dans CFG (appelé avant chaque lot : modifier CFG dans le notebook suffit)."""
        self.mode, self.strategy, self.min_area_main, self.min_area_small = cfg.crop_mode, cfg.crop_strategy, cfg.crop_min_area_main, cfg.crop_min_area_small
        self.min_side, self.accessories = cfg.crop_min_side, cfg.crop_accessories

    @property
    def segmenter(self):
        if self._seg is None: self._seg = SegformerClothes(self.seg_model_id); print(self._seg.describe_labels())
        return self._seg

    @property
    def remover(self): return self._rem or (lambda im: rembg_remove(im, self.rembg_model))

    def _flat(self, im) -> list[CropPiece]:
        rgba = np.asarray(self.remover(im).convert("RGBA")); mask = rgba[..., 3] > 127
        p = piece_from_mask(im, mask, self.size, min_area=self.min_area, name="item"); return [p] if p else []

    def _worn(self, im, labels) -> list[CropPiece]:
        """Une pièce par classe de segmentation, en IGNORANT les fragments : trop petits (part de la photo) ou boîte trop étroite (px)."""
        out = []
        for name, ids, slot in PIECES:
            if slot == "accessory" and not self.accessories: continue
            m = np.isin(labels, ids); area = float(m.mean())
            if area < (self.min_area_main if slot in MAJOR else self.min_area_small): continue
            ys, xs = np.where(m)
            if min(ys.max() - ys.min() + 1, xs.max() - xs.min() + 1) < self.min_side: continue
            p = piece_from_mask(im, m, self.size, min_area=0.0, name=name, slot_hint=slot)         # min_area=0 : le filtrage est déjà fait ci-dessus
            if p: out.append(p)
        return out

    def crop(self, photo, mode: str | None = None, strategy: str | None = None) -> list[CropPiece]:
        im = open_rgb(photo); mode = mode or self.mode; strategy = strategy or self.strategy
        if self.hook: return [CropPiece(n, s, i) for n, s, i in self.hook(im)]
        if mode == "none": return [CropPiece("whole", None, normalise_crop(im, self.size))]
        if mode == "flat": pieces = self._flat(im)
        else:
            labels = self.segmenter(im)
            if mode == "worn" or np.isin(labels, PERSON).mean() > 0.003:                                    # une personne est visible
                pieces = self._worn(im, labels) or (self._flat(im) if mode != "worn" else [])           # rien d'exploitable : on essaie rembg
            else: pieces = self._flat(im)                                                                    # sinon : photo à plat
            if strategy == "main" and len(pieces) > 1: pieces = [max(pieces, key=lambda p: p.area_frac)]  # une seule fiche par photo
        if not pieces:                                                      # rien de segmenté : on garde l'image entière, signalée
            pieces = [CropPiece("whole", None, normalise_crop(im, self.size), 1.0, dict(ok=False, reasons=["no_garment_segmented"]))]
        return pieces
