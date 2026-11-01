"""Prédictions de l'agent  ->  ItemCard v1 (+ confiances par attribut, statut, raisons).

CONFIANCES : le contrat exige confidence.slot/colour/type.  Les valeurs ci-dessous sont des HEURISTIQUES non calibrées
(combinaison de la confiance du LLM, du vote kNN et, pour la couleur, du témoin de pixels). À calibrer sur les 30 photos réelles
(eval/eval_real.py imprime la table précision-par-tranche-de-confiance).  Ne jamais les présenter comme des probabilités."""
from __future__ import annotations
from contracts import (ItemCard, Confidence, slot_of, default_type, usage_out, gender_out, season_out, warmth_formality,
                       OPEN_TOE_TYPES, WATERPROOF_TYPES, SLOT_UNCONFIRMED, TRADITIONAL_SUBTYPE_TO_SLOT)
from .retrieval import attr_share


def clamp01(x) -> float:
    """Ramène une confiance dans [0, 1] : des sommes en float32 donnent parfois 1.0000000149 et Pydantic (le=1) refuse la fiche."""
    return float(min(1.0, max(0.0, float(x))))


def fine_type(category: str, nb: list[dict]) -> tuple[str, float]:
    """Type fin = articleType majoritaire (pondéré) parmi les voisins de la même catégorie ; repli : table par défaut."""
    same = [n for n in nb if n["category"] == category and n.get("article_type")]; tot = sum(n["w"] for n in same)
    if not same: return default_type(category), 1.0
    d = {}
    for n in same: d[n["article_type"]] = d.get(n["article_type"], 0.0) + n["w"]
    t = max(d, key=d.get); return t, d[t] / tot


def traditional_subtype(nb: list[dict], min_share: float = 0.5):
    """Sous-type (jebba, farmla…) majoritaire parmi les voisins traditionnels qui en ont un ; (None, 0) sinon."""
    same = [n for n in nb if n["category"] == "traditional_garment" and n.get("subtype")]; tot = sum(n["w"] for n in same)
    if not same: return None, 0.0
    d = {}
    for n in same: d[n["subtype"]] = d.get(n["subtype"], 0.0) + n["w"]
    t = max(d, key=d.get); return (t, d[t] / tot) if d[t] / tot >= min_share else (None, d[t] / tot)


def slot_confidence(category, llm_cat, knn_dist, type_conf) -> float:
    slot = slot_of(category); mass = sum(w for c, w in knn_dist.items() if slot_of(c) == slot)
    if llm_cat and slot_of(llm_cat) == slot: return float(min(1.0, max(type_conf, mass)))   # LLM et kNN d'accord sur le slot
    return float(min(type_conf, mass)) if mass > 0 else float(type_conf * 0.5)


def colour_confidence(colour, llm_conf, nb, category, pixel_cols) -> float:
    if colour == "unknown": return 0.0
    same = [n for n in nb if n["category"] == category] or nb
    share = attr_share(same, "color", colour)
    if pixel_cols:
        names = [c for c, _ in pixel_cols]; pix = 1.0 if names[0] == colour else (0.5 if colour in names else 0.0)
        return float(0.4 * llm_conf + 0.3 * share + 0.3 * pix)
    return float(0.5 * llm_conf + 0.5 * share)


def build_card(item_id: str, res: dict, *, image: str, image_crop: str, embedding: str, pixel_cols=None,
               crop_quality: dict | None = None, review_conf: float = 0.60, second_colour: bool = False,
               subtype_min_share: float = 0.5, confirm_traditional: bool = True):
    """Renvoie (card|None, status, reasons)."""
    cat = res["category"]; reasons = []; nb = res["neighbors"]
    if cat == "unknown": cat = res["knn"]["category"]; reasons.append("agent_review_used_knn_top")
    slot = slot_of(cat)
    if slot is None: return None, "unsupported", [f"no_slot_for_category:{cat}"]
    type_, tshare = fine_type(cat, nb)
    base = float(res["confidence"]) if res["status"] == "OK" else 0.0
    type_conf = float(min(1.0, base * tshare)); slot_conf = slot_confidence(cat, res.get("candidate") or None, res["knn"]["dist"], base)
    if cat == "traditional_garment":                                         # sous-type lu chez les voisins tunisiens (si le jeu en contient)
        sub, sshare = traditional_subtype(nb, subtype_min_share)
        if sub:
            slot = TRADITIONAL_SUBTYPE_TO_SLOT.get(sub, "onepiece"); type_ = sub.title(); type_conf = float(min(1.0, base * sshare))
            slot_conf = float(min(slot_conf, sshare)); reasons.append(f"traditional_subtype_from_neighbours:{sub}")
        else: reasons.append("traditional_subtype_unknown")
    colour = res["color"] if res["color"] != "unknown" else (pixel_cols[0][0] if pixel_cols else "multicolor")
    if res["color"] == "unknown": reasons.append("colour_from_pixels_or_default")
    col_conf = colour_confidence(res["color"], float(res.get("llm_conf", 0.0)), nb, cat, pixel_cols)
    colours = [colour]
    if second_colour and pixel_cols and len(pixel_cols) > 1 and pixel_cols[1][1] >= 0.25 and pixel_cols[1][0] != colour: colours.append(pixel_cols[1][0])
    w, f, official = warmth_formality(cat, type_)
    if not official: reasons.append("warmth_formality_placeholder")
    if cat in SLOT_UNCONFIRMED: reasons.append(f"slot_mapping_unconfirmed:{cat}")
    if res["occasion"] == "home": reasons.append("usage_home_mapped_to_Casual")
    if crop_quality and not crop_quality["ok"]: reasons += [f"crop:{r}" for r in crop_quality["reasons"]]
    tl = type_.lower()
    card = ItemCard(id=item_id, name=f"{colour.title()} {cat.replace('_', ' ')}", slot=slot, type=type_, colour=colours, usage=usage_out(res["occasion"]),
                    warmth=w, formality=f, waterproof=tl in WATERPROOF_TYPES, open_toe=tl in OPEN_TOE_TYPES, gender=gender_out(res["gender"]),
                    image=image, image_crop=image_crop, embedding=embedding, season=season_out(res["season"]), pattern="plain",
                    confidence=Confidence(slot=clamp01(slot_conf), colour=clamp01(col_conf), type=clamp01(type_conf)),
                    source="obj1.knn" if "knn" in res["source"] else "obj1.llm", traditional=(cat == "traditional_garment"))
    if res["status"] != "OK": reasons.append("agent_could_not_decide")
    if min(slot_conf, type_conf) < review_conf: reasons.append("low_confidence")
    review = (res["status"] != "OK" or min(slot_conf, type_conf) < review_conf or (cat in SLOT_UNCONFIRMED and confirm_traditional)
              or bool(crop_quality and not crop_quality["ok"]))
    return card, ("needs_review" if review else "ok"), reasons


def apply_correction(card: ItemCard, *, slot=None, type_=None, colour=None, usage=None) -> ItemCard:
    """Correction utilisateur : source='user_corrected', confiance 1.0 sur les champs corrigés (contrat v1)."""
    d = card.model_dump(); conf = d["confidence"]
    if slot: d["slot"] = slot; conf["slot"] = 1.0
    if type_: d["type"] = type_; conf["type"] = 1.0
    if colour: d["colour"] = [colour] if isinstance(colour, str) else list(colour); conf["colour"] = 1.0
    if usage: d["usage"] = usage
    d["source"] = "user_corrected"; return ItemCard(**d)
