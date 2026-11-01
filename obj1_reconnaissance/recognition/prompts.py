from .taxonomy import DEFINITIONS, COLORS, GENDERS, SEASONS, OCCASIONS, TUNISIAN_HINTS

SYSTEM = ("You are DressMe's vision analyst, a meticulous fashion cataloguer. You report only what is visible in the photo. "
          "You never invent brands, fabrics or details you cannot see. When you are unsure, you lower your confidence "
          "or answer 'unknown' for an attribute instead of guessing.")
RULES = '''- Classify the MAIN item: the garment or accessory the photo is about. If a person wears several items, choose the most prominent one.
- Polo shirts and knitted short-sleeve tops with a small collar -> tshirt.
- Hoodies, sweatshirts, pullovers, cardigans -> sweater.  Denim trousers -> jeans.  Leggings, chinos, track pants -> pants.
- Sneakers, sandals, heels, flats, boots -> shoes.  Watches, belts, caps, scarves, sunglasses, wallets, ties, socks -> accessory.
- Kaftans, jebbas, farmlas, kurtas and other ceremonial garments -> traditional_garment.
- Colour = dominant colour of the garment only (ignore skin, hair, background).
- gender / season / occasion: infer only from visible cues (cut, fabric look, context); otherwise answer "unknown".'''
CONFIDENCE_GUIDE = ("confidence in [0,1]: >0.85 clear and unambiguous; 0.6-0.85 plausible but a close alternative exists; "
                    "<0.6 item partly visible, unusual, or ambiguous.")
SCHEMA = ('{"evidence": "<=15 words describing the visible cues", "category": "...", "alternative": "second most likely category", '
          '"color": "...", "gender": "...", "season": "...", "occasion": "...", "confidence": 0.0}')


def _header(tunisian: bool = False):
    defs = "\n".join(f"- {c}: {d}" for c, d in DEFINITIONS.items())
    rules = RULES + ("\n" + TUNISIAN_HINTS if tunisian else "")
    return (f"CATEGORIES (choose exactly one):\n{defs}\n\nRULES:\n{rules}\n\n"
            f"ALLOWED VALUES:\ncolor: {COLORS}\ngender: {GENDERS}\nseason: {SEASONS}\noccasion: {OCCASIONS}\n"
            f"(for gender, season, occasion you may also answer \"unknown\")\n\n{CONFIDENCE_GUIDE}\n")


def prompt_v1(tunisian: bool = False) -> str:
    return ("TASK: analyse the clothing item in the photo.\n"
             "Work in this order, silently: (1) identify the object and its visible cues (shape, neckline, sleeves, length, closure); "
             "(2) pick the category with the definitions and rules; (3) read the colour; (4) judge gender/season/occasion only from visible cues; (5) rate your confidence.\n\n"
             + _header(tunisian) + f"\nOUTPUT: one JSON object, no markdown, no text before or after, exactly these keys:\n{SCHEMA}\n\nJSON:")


PROMPT_V1 = prompt_v1(False)


def prompt_rag(neighbors, prev, kv, flags, tunisian: bool = False):
    refs = "\n".join(f'{i}. category={n["category"]}; color={n["color"] or "?"}; gender={n["gender"] or "?"}; season={n["season"] or "?"}; '
                     f'occasion={n["occasion"] or "?"}; catalogue name="{n["name"][:70]}"; similarity={n["sim"]:.2f}' for i, n in enumerate(neighbors, 1))
    cons = ", ".join(f"{c} {s:.0%}" for c, s in list(kv["dist"].items())[:3])
    first = (f'category={prev["category"]}, color={prev["color"]}, gender={prev["gender"]}, confidence={prev["confidence"]:.2f}'
             if prev["valid"] else "your first answer was not valid or used values outside the allowed lists")
    return ("TASK: re-examine the photo and correct your first analysis if needed.\n\n"
            f"VERIFIED REFERENCES: catalogue items visually similar to the photo, with expert labels. They are evidence, not the truth: this photo may differ.\n{refs}\n"
            f"Weighted vote of the references on the category: {cons}.\n\n"
            f"YOUR FIRST ANALYSIS: {first}.\nPROBLEMS DETECTED: {', '.join(flags) if flags else 'low confidence'}.\n\n"
            "REVISION RULES:\n- Look at the photo again. If it matches the references, align with them.\n"
            "- If the photo clearly contradicts the references, keep what you see and lower your confidence.\n"
            "- Never copy an attribute from a reference that you cannot see in the photo; use \"unknown\" instead.\n\n"
            + _header(tunisian) + f"\nOUTPUT: one JSON object, no markdown, exactly these keys:\n{SCHEMA}\n\nJSON:")
