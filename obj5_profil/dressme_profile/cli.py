"""Ligne de commande : python -m dressme_profile <commande> ...

  train            entraîne (ou réentraîne) la taxonomie de styles sur le catalogue
  profile          calcule le profil d'une garde-robe (ids, fichier d'ids ou filtre)
  recommend        recommandations personnalisées pour une garde-robe
  export-schemas   écrit les schémas JSON du contrat dans contracts/
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import config


def _ids_from_args(svc, args):
    if args.ids:
        return [s.strip() for s in args.ids.split(",") if s.strip()]
    if args.ids_file:
        data = json.loads(Path(args.ids_file).read_text(encoding="utf-8"))
        return data if isinstance(data, list) else data["item_ids"]
    items = svc.catalog
    if args.gender:
        items = [i for i in items if i.gender in (args.gender, "Unisex")]
    return [i.id for i in items]


def _add_common(p):
    p.add_argument("--catalog", type=Path, default=config.CATALOG_PATH)
    p.add_argument("--model", type=Path, default=config.MODEL_PATH)
    p.add_argument("--assets", type=Path, default=config.ASSETS_DIR,
                   help="dossier de base des chemins emb/*.npy")


def _add_selection(p):
    p.add_argument("--user", default=None)
    p.add_argument("--ids", help="identifiants séparés par des virgules")
    p.add_argument("--ids-file", help="JSON : liste d'ids ou {\"item_ids\": [...]}")
    p.add_argument("--gender", choices=["Men", "Women"],
                   help="sans --ids : toutes les pièces de ce genre (+ Unisex)")
    p.add_argument("--out", type=Path, help="fichier JSON de sortie")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="dressme_profile", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("train"); _add_common(t)
    p = sub.add_parser("profile"); _add_common(p); _add_selection(p)
    r = sub.add_parser("recommend"); _add_common(r); _add_selection(r)
    r.add_argument("-k", type=int, default=10)
    r.add_argument("--slot", choices=config.SLOTS)
    e = sub.add_parser("export-schemas")
    e.add_argument("--dir", type=Path, default=config.ROOT_DIR / "contracts")
    args = ap.parse_args(argv)

    if args.cmd == "export-schemas":
        from .contracts import ItemCard, StyleProfile
        args.dir.mkdir(parents=True, exist_ok=True)
        for name, m in [("item_card_v1", ItemCard), ("style_profile_v1", StyleProfile)]:
            (args.dir / f"{name}.schema.json").write_text(
                json.dumps(m.model_json_schema(), indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Schémas écrits dans {args.dir}")
        return

    from .contracts import ProfileRequest, RecommendRequest
    from .service import ProfileService
    svc = ProfileService(args.catalog, args.model, args.assets, retrain=(args.cmd == "train"))
    if args.cmd == "train":
        print(f"Modèle sauvegardé : {args.model}  ({svc.model.name})")
        return

    ids = _ids_from_args(svc, args)
    if args.cmd == "profile":
        res = svc.profile(ProfileRequest(user_id=args.user, item_ids=ids))
    else:
        res = svc.recommend(RecommendRequest(user_id=args.user, wardrobe_ids=ids,
                                             k=args.k, slot=args.slot))
    txt = json.dumps(res.model_dump(), indent=2, ensure_ascii=False)
    if args.out:
        args.out.write_text(txt, encoding="utf-8")
        print(f"Écrit : {args.out}")
    else:
        print(txt)


if __name__ == "__main__":
    main()
