"""Images « preuves techniques » pour la présentation : vraies sorties JSON et terminaux, rendues en cartes de code."""
import json, re, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

REPO = Path(r"C:\Users\MSI\dressme")
STORE = REPO / "gateway" / "users_data" / "stores" / "u_80e80c68e255"
OUTS = Path(sys.argv[1])          # sorties capturées (compat.json, judge_cold.json…)
TESTS = Path(sys.argv[2])         # sorties pytest
DEST = Path(sys.argv[3]); DEST.mkdir(parents=True, exist_ok=True)

FONT = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 31)
FONT_B = ImageFont.truetype(r"C:\Windows\Fonts\consolab.ttf", 31)
TITLE = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 30)
BG, BAR, FG, DIM = (30, 26, 36), (52, 44, 60), (232, 228, 236), (150, 142, 160)
KEY, STR, NUM, OK, BAD = (231, 154, 192), (152, 214, 168), (240, 190, 110), (120, 220, 150), (240, 120, 120)
LH = 42


def colour_json_line(line):
    """Segments (texte, couleur) pour une ligne de JSON indenté."""
    segs, pos = [], 0
    for m in re.finditer(r'"(?:[^"\\]|\\.)*"(\s*:)?|-?\d+(?:\.\d+)?|\b(?:true|false|null)\b', line):
        if m.start() > pos: segs.append((line[pos:m.start()], FG))
        tok = m.group(0)
        if m.group(1): segs.append((tok, KEY))
        elif tok.startswith('"'): segs.append((tok, STR))
        else: segs.append((tok, NUM))
        pos = m.end()
    segs.append((line[pos:], FG))
    return segs


def card(name, title, lines, width=1250):
    """lines : liste de listes de segments (texte, couleur[, gras])."""
    h = 70 + 30 + LH * len(lines) + 30
    im = Image.new("RGB", (width, h), BG)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, width, 70], fill=BAR)
    for i, c in enumerate([(240, 110, 110), (240, 190, 90), (120, 200, 120)]):
        d.ellipse([28 + i * 34, 25, 48 + i * 34, 45], fill=c)
    d.text((150, 18), title, font=TITLE, fill=FG)
    y = 100
    for segs in lines:
        x = 40
        for seg in segs:
            t, col = seg[0], seg[1]
            f = FONT_B if len(seg) > 2 and seg[2] else FONT
            d.text((x, y), t, font=f, fill=col)
            x += d.textlength(t, font=f)
        y += LH
    im.save(DEST / f"{name}.png")
    print(name, im.size)


def compact(obj, ind=0, maxw=66):
    """JSON indenté, mais tout objet ou liste court tient sur une ligne."""
    one = json.dumps(obj, ensure_ascii=False)
    if not isinstance(obj, (dict, list)) or len(one) + ind <= maxw:
        return one
    pad = " " * (ind + 2)
    if isinstance(obj, dict):
        body = [f"{pad}{json.dumps(k, ensure_ascii=False)}: {compact(v, ind + 2, maxw)}" for k, v in obj.items()]
        return "{\n" + ",\n".join(body) + "\n" + " " * ind + "}"
    body = [f"{pad}{compact(v, ind + 2, maxw)}" for v in obj]
    return "[\n" + ",\n".join(body) + "\n" + " " * ind + "]"


def json_lines(obj, maxw=68):
    out = []
    for line in compact(obj).split("\n"):
        while len(line) > maxw:   # coupe les lignes trop longues
            out.append(colour_json_line(line[:maxw])); line = "    " + line[maxw:]
        out.append(colour_json_line(line))
    return out


def comment(t, col=DIM):
    return [(t, col)]


# ---------------------------------------------------------------- DSO1 : fiche produite par l'agent + rapport
c = json.load(open(REPO / "obj1_reconnaissance" / "data" / "store" / "items" / "it_0002.json", encoding="utf-8"))
card8 = {k: c[k] for k in ("id", "slot", "type", "colour", "usage", "gender", "season", "confidence", "source", "embedding")}
card8["confidence"] = {k: round(v, 2) for k, v in card8["confidence"].items()}
rep = json.load(open(REPO / "obj1_reconnaissance" / "data" / "store" / "recognition_report.json", encoding="utf-8"))["items"][1]
rep = {k: rep[k] for k in ("id", "category", "status", "source", "H", "reasons")}
card("01_tech_recognition", "DSO1 · ItemCard v1 produced by the recognition agent",
     [comment("// store/items/it_0002.json  (photo -> agent -> validated card)")] + json_lines(card8)
     + [comment(""), comment("// store/recognition_report.json  (same item: decision trace)")] + json_lines(rep))

# ---------------------------------------------------------------- DSO2 : score réel
r = json.load(open(OUTS / "compat.json", encoding="utf-8"))
compat = {"category": r["category"], "score": r["score"], "verdict": r["verdict"], "newOutfits": r["newOutfits"],
          "partners": r["partners"][:2], "clashing": r["clashing"][:1], "duplicate": r["duplicate"], "compared": r["compared"]}
card("02_tech_compat", "DSO2 · POST /compatibility/score   (cream-trousers.jpg)",
     [comment("// FashionCLIP embedding -> 3 PairMLP -> percentile vs 300 references")] + json_lines(compat))

# ---------------------------------------------------------------- DSO3 : jury réel (3 °C, travail)
j = json.load(open(OUTS / "judge_cold.json", encoding="utf-8"))
jury = {"request": {"item_ids": ["it_0008", "it_0003", "it_0021"], "occasion": "work", "temperatureC": 3},
        "score": j["score"], "verdictLabel": j["verdictLabel"],
        "judges": {"rules": j["judges"]["rules"], "llm": j["judges"]["llm"]},
        "levels": {"weather": j["judges"]["context"]["weatherLevel"], "occasion": j["judges"]["context"]["occasionLevel"]},
        "compatibility": j["judges"]["compatibility"]["score01"]}
card("03_tech_jury", "DSO3 · POST /outfits/judge   (rules + LLM + hybrid -> arbiter)",
     [comment("// shirt + track pants + sneakers, at work, 3 °C")] + json_lines(jury))

# ---------------------------------------------------------------- DSO4 : évaluation LLM réelle
e = json.load(open(REPO / "obj4_manques" / "llm_eval_results_final.json", encoding="utf-8"))["summary"]
ev = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in e.items()
      if k in ("dataset_version", "prompt_version", "cases", "successful_cases", "tool_correct_rate", "tool_argument_correct_rate",
               "recommendation_match_rate", "security_cases", "security_pass_rate", "mean_latency_ms")}
card("04_tech_gaps", "DSO4 · llm_eval_results_final.json   (fixed live LLM evaluation)",
     [comment("// gap agent: tool choice, arguments, injection case")] + json_lines(ev))

# ---------------------------------------------------------------- DSO6 : LLM-as-a-judge réel
jd = json.load(open(REPO / "obj6_app" / "reports" / "eval_judge.json", encoding="utf-8"))
q = jd["judges"]["qwen/qwen3.8-27b"]
judge6 = {"cases": jd["cases"], "judge": "qwen/qwen3.8-27b",
          "overall_score_by_variant": {k: v["overall"] for k, v in q["by_variant"].items()},
          "detection_rate": q["detection_rate"], "false_alarm_on_good": q["false_alarm_on_good"],
          "agreement_between_judges_spearman": jd["agreement_between_judges_spearman"], "within_25_words": jd["within_25_words"]}
card("06_tech_outfit_day", "DSO6 · reports/eval_judge.json   (LLM-as-a-judge with negative controls)",
     [comment("// good explanation vs other-context and invented controls, scored 1-5")] + json_lines(judge6))

# ---------------------------------------------------------------- tests : vraies sorties pytest
rows = []
for name, f, cmd in [("gateway", "gateway.txt", "pytest -q tests"), ("obj1_reconnaissance", "obj1.txt", "pytest -q"),
                     ("obj2_compat", "obj2.txt", "pytest -q tests"), ("obj3_jury", "obj3.txt", "pytest -q"),
                     ("obj4_manques", "obj4.txt", "pytest -q"), ("obj5_profil", "obj5.txt", "pytest -q tests"),
                     ("obj6_app", "obj6.txt", "pytest -q")]:
    p = TESTS / f
    last = [l for l in p.read_text(encoding="utf-8", errors="replace").splitlines() if re.search(r"\d+ (passed|failed)", l)] if p.exists() else []
    res = last[-1].strip("= ").strip() if last else "not run"
    rows.append([(f"{name}> ", KEY, True), (f"python -m {cmd}", FG)])
    rows.append([("  " + res, OK if "failed" not in res and "passed" in res else BAD)])
recette = (TESTS / "obj2_recette.txt").read_text(encoding="utf-8", errors="replace") if (TESTS / "obj2_recette.txt").exists() else ""
m = re.search(r"\d+\s*PASS.*", recette)
if m:
    rows.append([("obj2_compat> ", KEY, True), ("python recette.py", FG)])
    rows.append([("  " + m.group(0).strip()[:70], OK)])
card("07_tech_tests", "Automated tests — real runs (fake LLMs, no keys used)", rows, width=1250)
