"""DressMe objectif 2 : coeur du score de compatibilité (sans API, sans LLM).

Entrées : embeddings FashionCLIP (512, L2-normalisés) + catégorie Polyvore (11 valeurs).
Modèle : ensemble de 3 PairMLP (image seule, perte FITB), comme dans l'étude.
"""
import os
import numpy as np
import torch
import torch.nn as nn

HERE = os.path.dirname(os.path.abspath(__file__))
SLOT_TO_CAT = {  # défaut ; une catégorie explicite (champ "category") l'emporte
    "top": "tops", "bottom": "bottoms", "onepiece": "all-body", "outer": "outerwear",
    "footwear": "shoes", "bag": "bags", "accessory": "accessories",
}
THRESH_COMPATIBLE, THRESH_MOYENNE = 70, 40        # fixés à l'avance (garde-robes)
PAIR_GOOD, PAIR_BAD = 0.75, 0.35                 # seuils /pairs calibrés sur 8 000 paires de validation Polyvore (31/10/2026)
CHUNK_REFS = 25                                   # références évaluées par paquet (mémoire bornée)
DUP_PCT = 90                                      # doublon si >= 90e centile des paires aléatoires
MODEL_NAME = "pairmlp-image-fitb-3seeds"


class Enc(nn.Module):
    def __init__(s, d, n_cats, h=256):
        super().__init__()
        s.proj = nn.Sequential(nn.Linear(d, h), nn.GELU(), nn.Dropout(0.1), nn.Linear(h, h))
        s.cat = nn.Embedding(n_cats + 1, h)
    def forward(s, f, c): return s.proj(f) + s.cat(c)


class PairMLP(nn.Module):
    def __init__(s, d, n_cats, h=256):
        super().__init__(); s.enc = Enc(d, n_cats, h)
        s.pair = nn.Sequential(nn.Linear(2 * h, h), nn.GELU(), nn.Dropout(0.1), nn.Linear(h, 1))
    def pair_from_z(s, zi, zj):
        return s.pair(torch.cat([zi * zj, (zi - zj).abs()], -1)).squeeze(-1)
    def forward(s, f, c, m):
        z = s.enc(f, c); L = z.size(1); zi, zj = z.unsqueeze(2), z.unsqueeze(1)
        p = s.pair_from_z(zi.expand(-1, -1, L, -1), zj.expand(-1, L, -1, -1))
        pm = (m.unsqueeze(2) & m.unsqueeze(1)) & ~torch.eye(L, dtype=torch.bool, device=m.device)
        return (p * pm).sum((1, 2)) / pm.sum((1, 2)).clamp(min=1)


def pair_verdict(score01):
    return "va bien" if score01 >= PAIR_GOOD else ("moyen" if score01 >= PAIR_BAD else "peu probable")


def verdict(rank):
    return "compatible" if rank >= THRESH_COMPATIBLE else ("moyenne" if rank >= THRESH_MOYENNE else "peu compatible")


class CardStore:
    """Dossier de fiches article (un JSON par article, contrat ItemCard) et de leurs embeddings (.npy).
    Racine : variable d'environnement DRESSME_STORE ; le champ `embedding` d'une fiche est un chemin relatif à cette racine."""
    def __init__(self, root=None):
        self.root = root or os.environ.get("DRESSME_STORE")
        self.cards = {}
        if self.root and os.path.isdir(self.root):
            import glob, json
            for p in sorted(glob.glob(os.path.join(self.root, "**", "*.json"), recursive=True)):
                try:
                    c = json.load(open(p, encoding="utf-8"))
                except Exception:
                    continue
                if isinstance(c, dict) and "id" in c and "slot" in c:
                    self.cards[c["id"]] = c

    def get(self, item_id):
        if item_id not in self.cards:
            raise ValueError(f"article inconnu : {item_id!r} (dossier de fiches : {self.root or 'DRESSME_STORE non défini'})")
        return self.cards[item_id]

    def load_vec(self, path):
        full = path if os.path.isabs(path) else os.path.join(self.root or "", path)
        if not os.path.exists(full):
            raise ValueError(f"fichier d'embedding introuvable : {full}")
        return np.load(full).astype(np.float32).reshape(-1)


class CompatEngine:
    def __init__(self, base=HERE, device="cpu", store=None):
        self.store = store or CardStore()
        ref = np.load(os.path.join(base, "reference.npz"))
        self.cats = [str(c) for c in ref["cats"]]; self.cid = {c: k for k, c in enumerate(self.cats)}
        self.n_cats = len(self.cats); self.pad_cat = self.n_cats
        self.pool_img = torch.tensor(ref["pool_img"], dtype=torch.float32, device=device)
        self.pool_cat = torch.tensor(ref["pool_cat"], dtype=torch.long, device=device)
        self.ref_sims = ref["ref_sims"]; self.dev = device
        self.models = []
        for s in range(3):
            ck = torch.load(os.path.join(base, "models", f"final_image_s{s}.pt"), map_location=device)
            m = PairMLP(ck["d"], self.n_cats).to(device); m.load_state_dict(ck["state"]); self.models.append(m.eval())
        self.pools = {c: self.pool_img[self.pool_cat == k] for k, c in enumerate(self.cats)}
        with torch.no_grad():  # encodage des références, une fois par modèle
            self.pool_z = [{c: m.enc(self.pools[c], torch.full((len(self.pools[c]),), self.cid[c], device=device))
                            for c in self.cats} for m in self.models]

    # ---- utilitaires
    def category_of(self, item):
        c = item.get("category") or SLOT_TO_CAT.get(item.get("slot", ""), None)
        if c not in self.cid:
            raise ValueError(f"catégorie inconnue pour l'article {item.get('id')!r} : {c!r} (attendu : {self.cats})")
        return c

    def resolve(self, item):
        """Un article peut être : un identifiant (str, cherché dans le dossier de fiches) ou une fiche (dict)."""
        return self.store.get(item) if isinstance(item, str) else item

    def _emb(self, item):
        raw = item.get("embedding")
        if raw is None or (isinstance(raw, str) and not raw):
            raise ValueError(f"fiche {item.get('id')!r} sans embedding FashionCLIP (le calculer avec embed_cards.py, objectif 1)")
        e = self.store.load_vec(raw) if isinstance(raw, str) else np.asarray(raw, dtype=np.float32)
        if e.shape != (512,): raise ValueError(f"embedding de taille {e.shape} (attendu 512) pour {item.get('id')!r}")
        n = float(np.linalg.norm(e))
        if n < 1e-6: raise ValueError(f"embedding nul pour {item.get('id')!r}")
        return e / n

    @torch.no_grad()
    def set_scores(self, feats, cats):
        """feats (B,L,512), cats (B,L) -> score moyen des 3 modèles (B,), tous éléments présents."""
        m = torch.ones(cats.shape, dtype=torch.bool, device=self.dev)
        return torch.stack([mod(feats, cats, m) for mod in self.models]).mean(0)

    # ---- /compat
    @torch.no_grad()
    def compat(self, candidate, wardrobe):
        candidate = self.resolve(candidate); wardrobe = [self.resolve(w) for w in wardrobe]
        if len(wardrobe) < 2:
            return {"error": "garde-robe trop petite (minimum 2 articles)"}
        cc = self.category_of(candidate); ec = torch.tensor(self._emb(candidate), device=self.dev)
        W = [(torch.tensor(self._emb(w), device=self.dev), self.category_of(w)) for w in wardrobe]
        fw = torch.stack([e for e, _ in W]); cw = torch.tensor([self.cid[c] for _, c in W], device=self.dev)
        refs = self.pools[cc]; R = len(refs)
        # ensembles W+[candidat] puis W+[référence r], évalués par paquets (mémoire bornée même pour une grande garde-robe)
        base = torch.cat([fw, ec[None]]); cb = torch.cat([cw, torch.tensor([self.cid[cc]], device=self.dev)])
        def run(extra):
            n = len(extra); f = base[None].repeat(n, 1, 1); f[:, -1] = extra
            return self.set_scores(f, cb[None].repeat(n, 1))
        s_c = run(ec[None])[0]
        s_r = torch.cat([run(refs[i:i + CHUNK_REFS]) for i in range(0, R, CHUNK_REFS)])
        rank = int(round(100 * float((s_r < s_c).float().mean())))
        # partenaires : paires (candidat, article) de catégorie différente
        ks = [i for i, (_, c) in enumerate(W) if c != cc]
        partners = []
        if ks:
            pf = torch.stack([torch.stack([ec, W[i][0]]) for i in ks])
            pc = torch.stack([torch.tensor([self.cid[cc], self.cid[W[i][1]]], device=self.dev) for i in ks])
            ps = self.set_scores(pf, pc).cpu().numpy()
            for j in np.argsort(-ps)[:2]:
                i = ks[int(j)]
                p01 = 0.5 * (self._pair_pct(ec, cc, W[i][0], W[i][1]) + self._pair_pct(W[i][0], W[i][1], ec, cc))
                partners.append({"id": wardrobe[i].get("id", f"W{i+1}"), "category": W[i][1], "pair_score01": round(float(p01), 2)})
        # doublon : article de la garde-robe le plus semblable
        sims = (fw @ ec).cpu().numpy(); j = int(np.argmax(sims))
        pct = int(round(100 * float(np.searchsorted(self.ref_sims, float(sims[j])) / len(self.ref_sims))))
        return {"rank100": rank, "score01": round(rank / 100, 2), "verdict": verdict(rank), "partners": partners,
                "duplicate": {"id": wardrobe[j].get("id", f"W{j+1}"), "similarity": round(float(sims[j]), 3),
                              "pct": pct, "is_duplicate": pct >= DUP_PCT},
                "model": MODEL_NAME}

    # ---- /pairs : score01 d'une paire = centile du score de la paire parmi (a, 300 références de la catégorie de b),
    #               moyenné dans les deux sens
    @torch.no_grad()
    def pairs(self, A, B):
        A = [self.resolve(a) for a in A]; B = [self.resolve(b) for b in B]
        ea = torch.stack([torch.tensor(self._emb(a), device=self.dev) for a in A]); ca = [self.category_of(a) for a in A]
        eb = torch.stack([torch.tensor(self._emb(b), device=self.dev) for b in B]); cb = [self.category_of(b) for b in B]
        ia = torch.tensor([self.cid[c] for c in ca], device=self.dev); ib = torch.tensor([self.cid[c] for c in cb], device=self.dev)
        za = [m.enc(ea, ia) for m in self.models]; zb = [m.enc(eb, ib) for m in self.models]   # encodés une seule fois
        out = np.zeros((len(A), len(B)), dtype=np.float32)
        for i in range(len(A)):
            for j in range(len(B)):
                out[i, j] = 0.5 * (self._pct_z(za, i, ca[i], zb, j, cb[j]) + self._pct_z(zb, j, cb[j], za, i, ca[i]))
        return np.round(out, 2).tolist()

    def _pct_z(self, zx, i, cx, zy, j, cy):
        """Centile de s(x_i, y_j) parmi s(x_i, r) pour r dans les références de la catégorie de y."""
        s, sr = 0.0, 0.0
        for m, pz, zxm, zym in zip(self.models, self.pool_z, zx, zy):
            z1 = zxm[i:i + 1]; zr = pz[cy]
            s = s + m.pair_from_z(z1, zym[j:j + 1]) / len(self.models)
            sr = sr + m.pair_from_z(z1.expand(len(zr), -1), zr) / len(self.models)
        return float((sr < s).float().mean())

    def _pair_pct(self, e1, c1, e2, c2):
        """Centile de s(1,2) parmi s(1, r) pour r dans les références de la catégorie de 2."""
        vals = []
        for m, pz in zip(self.models, self.pool_z):
            z1 = m.enc(e1[None], torch.tensor([self.cid[c1]], device=self.dev))
            z2 = m.enc(e2[None], torch.tensor([self.cid[c2]], device=self.dev))
            s = m.pair_from_z(z1, z2)
            zr = pz[c2]; sr = m.pair_from_z(z1.expand(len(zr), -1), zr)
            vals.append((s, sr))
        s = torch.stack([v[0] for v in vals]).mean(0); sr = torch.stack([v[1] for v in vals]).mean(0)
        return float((sr < s).float().mean())
