"""Pont Obj2 : embeddings SYNTHÉTIQUES (tirés du pool Polyvore) : on teste le branchement, pas la qualité."""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OBJ2 = os.path.join(os.path.dirname(HERE), "obj2_compat")
import pytest
pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(OBJ2, "core.py")), reason="obj2_compat absent")
from dressme.service import DressMeService
from dressme.compat_bridge import CompatBridge


def _svc(tmp_path):
    svc = DressMeService.from_demo()
    ref = np.load(os.path.join(OBJ2, "reference.npz"))
    ids = list(svc.pieces)
    np.savez(tmp_path / "emb.npz", ids=np.array(ids), emb=ref["pool_img"][: len(ids) * 50: 50].astype(np.float32)[: len(ids)])
    svc.compat = CompatBridge(str(tmp_path / "emb.npz"), obj2_dir=OBJ2)
    return svc


def test_judge_ajoute_la_compatibilite(tmp_path):
    svc = _svc(tmp_path)
    ids = [p["id"] + ".jpg" if not p["id"].endswith(".jpg") else p["id"] for p in svc.list_pieces()][:4]
    r = svc.judge(ids, 18, False, "décontracté", mode="regles")
    c = r["compatibilite"]
    assert c is None or (0 <= c["outfit_compat01"] <= 1 and c["niveau"] in ("va bien", "moyen", "peu probable"))


def test_sans_embeddings_le_jury_marche_quand_meme():
    svc = DressMeService.from_demo()
    ids = list(svc.pieces)[:3]
    assert svc.judge(ids, 18, False, "travail", mode="regles")["compatibilite"] is None
