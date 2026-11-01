"""Cohérence entre la SEGMENTATION (ce que le crop croit avoir découpé) et la RECONNAISSANCE (ce que l'agent voit dans le crop).

Pourquoi ce module : SegFormer est un modèle de « parsing » de vêtements occidentaux (classes : upper-clothes, pants, skirt, dress, shoes, bag, hat…).
Il n'a pas de classe « veste » (les vestes sont dans upper-clothes) ni de classe pour une jebba ou une farmla : une longue pièce traditionnelle est
souvent coupée en plusieurs morceaux (haut + bas + « chaussures » + « écharpe »…), et chaque morceau, vu seul, est reconnu comme la MÊME pièce longue.

Règle : on compare la classe de segmentation (`hint`) au slot reconnu.
  * compatible  -> rien à signaler (ex. « upper-clothes » reconnu comme veste ou comme robe : normal) ;
  * PETITE pièce (chaussures, sac, accessoire) reconnue comme tout autre chose -> c'est un FRAGMENT d'un autre vêtement : on l'ignore ;
  * GRANDE pièce (haut, bas, robe) incompatible -> on garde la fiche mais elle est marquée `slot_disagrees_with_segmentation` (revue).
La table COMPATIBLE est un choix de conception (non validé statistiquement) : à ajuster d'après les résultats."""
from __future__ import annotations

COMPATIBLE = {
    "top": {"top", "outer", "onepiece"},          # upper-clothes contient aussi vestes/gilets ; une robe ou une tunique longue commence au haut du corps
    "bottom": {"bottom", "onepiece"},             # le bas d'une robe / jebba est « skirt » ou « pants » pour SegFormer
    "onepiece": {"onepiece", "top", "outer"},
    "footwear": {"footwear"},
    "bag": {"bag", "accessory"},
    "accessory": {"accessory", "bag"},
}
SMALL_HINTS = {"footwear", "bag", "accessory"}


def judge_piece(hint: str | None, slot: str | None) -> str:
    """'ok' | 'inconsistent' (grande pièce, à revoir) | 'fragment' (petite pièce reconnue comme autre chose : à ignorer)."""
    if not hint or not slot or slot in COMPATIBLE.get(hint, {slot}): return "ok"
    return "fragment" if hint in SMALL_HINTS else "inconsistent"
