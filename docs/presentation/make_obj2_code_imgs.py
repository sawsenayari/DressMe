"""Captures fidèles du code de l'Obj2 (extraits réels des fichiers, numéros de ligne réels) + vraie trace JSONL."""
import json, sys, textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from pygments import lex
from pygments.lexers import PythonLexer
from pygments.token import Token

REPO = Path(r"C:\Users\MSI\dressme")
ST = REPO / "obj2_compat" / "stylist"
DEST = Path(sys.argv[1]); DEST.mkdir(parents=True, exist_ok=True)
FS = 24
FONT = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", FS)
FONT_B = ImageFont.truetype(r"C:\Windows\Fonts\consolab.ttf", FS)
TITLE = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 24)
BG, BAR, FG, DIM, HL = (30, 26, 36), (52, 44, 60), (232, 228, 236), (120, 112, 130), (70, 40, 66)
COL = {Token.Keyword: (231, 154, 192), Token.Name.Builtin: (240, 190, 110), Token.Literal.String: (152, 214, 168),
       Token.Literal.Number: (240, 190, 110), Token.Comment: (150, 142, 160), Token.Name.Function: (140, 200, 240),
       Token.Name.Class: (140, 200, 240), Token.Operator: (232, 228, 236), Token.Name.Decorator: (240, 190, 110)}
LH = 34


def colour(tok):
    while tok is not Token:
        if tok in COL:
            return COL[tok]
        tok = tok.parent
    return FG


def py_lines(src):
    """Coloration ligne par ligne (le lexer travaille sur le bloc entier pour les chaînes multilignes)."""
    lines, cur = [], []
    for tok, val in lex(src, PythonLexer()):
        parts = val.split("\n")
        for i, p in enumerate(parts):
            if i:
                lines.append(cur); cur = []
            if p:
                cur.append((p, colour(tok)))
    lines.append(cur)
    return lines


def wrap_segs(segs, maxc):
    """Coupe une ligne colorée trop longue en plusieurs lignes visuelles."""
    out, cur, n = [], [], 0
    for t, c in segs:
        while n + len(t) > maxc:
            k = maxc - n
            sp = t.rfind(" ", 0, k)          # coupe sur un espace, pas au milieu d'un mot
            k = sp + 1 if sp > 0 else k
            cur.append((t[:k], c)); out.append(cur); cur, n, t = [], 8, t[k:]
            cur.append(("        ", c))
        cur.append((t, c)); n += len(t)
    out.append(cur)
    return out


def card(name, title, numbered, width=1500, highlight=()):
    """numbered : liste de (numéro de ligne ou None, segments)."""
    maxc = (width - 130) // int(FONT.getlength("x"))
    rows = []
    for no, segs in numbered:
        for j, w in enumerate(wrap_segs(segs, maxc)):
            rows.append((no if j == 0 else None, w, no in highlight))
    h = 64 + 24 + LH * len(rows) + 24
    im = Image.new("RGB", (width, h), BG); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, width, 64], fill=BAR)
    for i, c in enumerate([(240, 110, 110), (240, 190, 90), (120, 200, 120)]):
        d.ellipse([24 + i * 30, 23, 42 + i * 30, 41], fill=c)
    d.text((130, 16), title, font=TITLE, fill=FG)
    y = 88
    for no, segs, hl in rows:
        if hl:
            d.rectangle([0, y - 3, width, y + LH - 5], fill=HL)
        if no is not None:
            d.text((14, y), f"{no:>3}", font=FONT, fill=DIM)
        x = 80
        for t, c in segs:
            d.text((x, y), t, font=FONT, fill=c); x += d.textlength(t, font=FONT)
        y += LH
    im.save(DEST / f"{name}.png"); print(name, im.size)


def excerpt(path, a, b, skip=()):
    src = path.read_text(encoding="utf-8").split("\n")
    block = "\n".join(src[a - 1:b])
    out = [(a + i, segs) for i, segs in enumerate(py_lines(block)) if a + i not in skip]
    while out and not out[-1][1]:
        out.pop()                     # pas de ligne vide en fin d'extrait
    return out


# 1. prompt v2 : rôle système + étapes + contraintes
card("obj2_code_prompt", "obj2_compat/stylist/prompts.py  ·  compat-conseil-v2 (system + user)",
     excerpt(ST / "prompts.py", 66, 87), highlight={67, 68, 75, 81, 87})

# 2. hyperparamètres
card("obj2_code_config", "obj2_compat/stylist/config.py  ·  generation hyperparameters",
     excerpt(ST / "config.py", 17, 33), highlight={23, 24, 26, 29})

# 3. garde-fous
card("obj2_code_guard", "obj2_compat/stylist/guard.py  ·  ground(): output checked against the facts",
     excerpt(ST / "guard.py", 43, 66), width=1300, highlight={48, 50, 59, 61})

# 4. vraie trace : dernière ligne de users_data/traces/stylist.jsonl, sortie brute dépliée
t = json.loads((REPO / "gateway" / "users_data" / "traces" / "stylist.jsonl").read_text(encoding="utf-8").strip().split("\n")[-1])
raw = json.loads(t.pop("raw"))
KEY, STR, NUM = (231, 154, 192), (152, 214, 168), (240, 190, 110)


def kv(k, v, ind=2, last=False):
    js = json.dumps(v, ensure_ascii=False)
    col = STR if isinstance(v, str) else NUM
    return [(" " * ind + f'"{k}": ', KEY), (js, col)] + ([] if last else [(",", FG)])


order = ["ts", "prompt_version", "model", "temperature", "verdict", "suspect_names", "attempts", "latency_ms",
         "prompt_tokens", "completion_tokens"]
rows = [(None, [("{", FG)])] + [(None, kv(k, t[k])) for k in order]
rows.append((None, [('  "raw": {', KEY)]))
rows += [(None, kv(k, raw[k], 4, k == "a_eviter")) for k in ("observation", "conseil", "tenue", "a_eviter")]
rows.append((None, [("  },", FG)]))
rows += [(None, kv(k, t[k], last=k == "ok")) for k in ("schema_ok", "invented_ids", "invented_numbers", "truncated", "ok")]
rows.append((None, [("}", FG)]))
when = f"{t['ts'][8:10]}/{t['ts'][5:7]}/{t['ts'][:4]} {t['ts'][11:16]}"
card("obj2_trace", f"gateway/users_data/traces/stylist.jsonl  ·  one real call ({when})", rows, width=1500,
     highlight={"hl"})
