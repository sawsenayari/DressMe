"""Traitement par lots : un dossier de PHOTOS (ou de crops) -> fiches JSON + .npy + fichiers récapitulatifs, dans le dossier `store`.

    store/
      items/it_0001.json        une fiche ItemCard v1 par article (le « résultat JSON » de chaque photo)
      items/it_0001_crop.png    crop 512 px fond blanc      items/it_0001_raw.jpg   photo d'origine
      emb/it_0001.npy           embedding FashionCLIP 512-d, norme 1
      wardrobe.json             LISTE de toutes les fiches (contrat pur) -> à donner aux objectifs 2-6
      recognition_report.json   une ligne par pièce : statut, raisons, source, H ; les pièces IGNORÉES y figurent (status « discarded »)

Les identifiants sont stables : relancer sur la même image réutilise son id ; une nouvelle image reçoit le numéro suivant.
`fresh=True` repart d'un store vide (ids it_0001…). Pièces ignorées (jamais dans wardrobe.json) :
  * fragments : petite pièce (chaussures, sac, accessoire) que la reconnaissance identifie comme un autre vêtement (voir outfit.py) ;
  * doublons : plusieurs pièces d'une même photo reconnues comme une pièce unique (robe, jebba…) -> on garde la plus grande."""
from __future__ import annotations
import json, re, shutil, time
from collections import Counter
from pathlib import Path

EXT = {".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif"}


def _next_id(store: Path, used: set[str]) -> str:
    nums = [int(m.group(1)) for p in (store / "items").glob("it_*.json") if (m := re.fullmatch(r"it_(\d+)", p.stem))]
    nums += [int(m.group(1)) for i in used if (m := re.fullmatch(r"it_(\d+)", i))]
    return f"it_{(max(nums) + 1 if nums else 1):04d}"


def reset_store(store: str | Path, archive: bool = False) -> str:
    """Vide le store (items/, emb/, _tmp/, wardrobe.json, recognition_report.json). archive=True : déplace l'ancien contenu
    dans `<store>_archive_<date>` au lieu de le supprimer. Les autres dossiers (agent_final, tunisian_dataset…) ne sont JAMAIS touchés."""
    store = Path(store); store.mkdir(parents=True, exist_ok=True); names = ["items", "emb", "_tmp", "wardrobe.json", "recognition_report.json"]
    present = [n for n in names if (store / n).exists()]; msg = "store déjà propre"
    if present:
        if archive:
            dst = store.parent / f"{store.name}_archive_{time.strftime('%Y%m%d_%H%M%S')}"; dst.mkdir(parents=True)
            for n in present: shutil.move(str(store / n), str(dst / n))
            msg = f"ancien contenu archivé dans {dst}"
        else:
            for n in present:
                p = store / n; shutil.rmtree(p) if p.is_dir() else p.unlink()
            msg = f"{len(present)} élément(s) supprimé(s) : {present}"
    (store / "items").mkdir(parents=True, exist_ok=True); (store / "emb").mkdir(parents=True, exist_ok=True); return msg


def _discard(store: Path, item_id: str) -> None:
    for rel in (f"items/{item_id}.json", f"items/{item_id}_crop.png", f"items/{item_id}_raw.jpg", f"emb/{item_id}.npy"):
        (store / rel).unlink(missing_ok=True)


def recognize_folder(svc, folder: str | Path, store: str | Path, mode: str | None = None, verbose: bool = True,
                     crop: bool | str = False, fresh: bool = False, limit: int | None = None, archive: bool = False) -> dict:
    """crop=False : chaque image est DÉJÀ un crop (livré par le module crop).
       crop=True / "auto" / "worn" / "flat" : chaque image est une PHOTO ; svc.cropper la découpe (réglages : CFG.crop_*).
       fresh=True : repart d'un store propre.   limit=N : ne traite que les N premières images (démo)."""
    folder, store = Path(folder), Path(store)
    if fresh: print("🧹", reset_store(store, archive))
    store.mkdir(parents=True, exist_ok=True); (store / "items").mkdir(exist_ok=True)
    rep_path = store / "recognition_report.json"
    report = {e["source_key"]: e for e in json.loads(rep_path.read_text(encoding="utf-8"))["items"]} if rep_path.exists() else {}
    images = sorted(p for p in folder.iterdir() if p.suffix.lower() in EXT and not p.name.startswith("."))
    if not images: raise FileNotFoundError(f"Aucune image (png/jpg/jpeg/webp) dans {folder}")
    if limit: images = images[:limit]
    tmp = store / "_tmp"; tmp.mkdir(exist_ok=True); crop_mode = None if crop is False else ("auto" if crop is True else crop)
    if crop_mode is not None and getattr(svc, "cropper", None) is not None and hasattr(svc.cropper, "apply_config"): svc.cropper.apply_config(svc.cfg)
    for p in images:
        pieces = [(None, None, None, None, None)] if crop_mode is None else [(c.name, c.slot_hint, c.image, c.quality, c.area_frac) for c in svc.cropper.crop(p, crop_mode)]
        onepieces = []                                                       # (clé, aire) des pièces « robe / pièce unique » de CETTE photo
        for name, hint, img, q, area in pieces:
            key = p.name if name is None else f"{p.name}#{name}"; used = {e["id"] for e in report.values()}
            item_id = report[key]["id"] if key in report else _next_id(store, used); src = p
            if img is not None: src = tmp / f"{item_id}_piece.png"; img.save(src)
            r = svc.recognize(src, item_id=item_id, raw_path=str(p), out_dir=store, mode=mode, crop_reasons=(q or {}).get("reasons"), slot_hint=hint)
            base = dict(source_key=key, source_file=p.name, crop_piece=name, id=item_id, category=r.category, hint=hint, area=None if area is None else round(float(area), 4))
            if r.debug.get("fragment"):                                      # petite pièce reconnue comme autre chose : fragment -> ignorée
                _discard(store, item_id); report[key] = dict(base, status="discarded", reasons=r.reasons, json=None, discard_reason="fragment")
                if verbose: print(f"{key:34s} → ignorée (fragment) | {r.category:20s} | {r.reasons[-1]}")
                continue
            report[key] = dict(base, status=r.status, reasons=r.reasons, json=f"items/{item_id}.json" if r.card else None, source=r.debug.get("source"),
                               H=r.debug.get("H"), confidence_calibrated=r.debug.get("confidence_calibrated", False))
            if r.card is not None and r.card.slot == "onepiece" and area is not None: onepieces.append((key, area))
            if verbose: print(f"{key:34s} → {item_id} | {r.status:12s} | {r.category:20s} | {r.reasons}")
        if len(onepieces) > 1:                                               # plusieurs « pièces uniques » sur une photo = morceaux d'un même vêtement
            keep = max(onepieces, key=lambda t: t[1])[0]
            for key, _ in onepieces:
                if key == keep: continue
                e = report[key]; _discard(store, e["id"]); report[key] = dict(e, status="discarded", json=None, discard_reason="duplicate", reasons=e["reasons"] + [f"duplicate_of:{report[keep]['id']}"])
                if verbose: print(f"{key:34s} → ignorée (doublon de {report[keep]['id']})")
    rep_path.write_text(json.dumps(dict(version="itemcard_v1", items=list(report.values())), indent=2, ensure_ascii=False), encoding="utf-8")
    cards = [json.loads(Path(store / e["json"]).read_text(encoding="utf-8")) for e in report.values() if e["json"] and (store / e["json"]).exists()]
    (store / "wardrobe.json").write_text(json.dumps(cards, indent=2, ensure_ascii=False), encoding="utf-8")
    kept = [e for e in report.values() if e["status"] != "discarded"]
    summary = dict(photos=len(images), cards=len(cards), ignorees=sum(e["status"] == "discarded" for e in report.values()),
                   needs_review=sum(e["status"] == "needs_review" for e in kept), unsupported=sum(e["status"] == "unsupported" for e in kept),
                   wardrobe_json=str(store / "wardrobe.json"))
    if verbose: print(summary)
    return summary


# ---------------------------------------------------------------- explication du rapport
REASON_HELP = {
    "warmth_formality_placeholder": ("INFO", "warmth/formality : valeur neutre provisoire (le dictionnaire d'Amir n'est pas chargé). Ne déclenche PAS needs_review."),
    "slot_mapping_unconfirmed": ("REVUE (voulue)", "pièce traditionnelle : son slot (onepiece) n'est pas encore validé avec Amir -> toujours needs_review. Désactivable : CFG.confirm_traditional = False."),
    "traditional_subtype_from_neighbours": ("INFO", "sous-type (jebba, farmla…) lu chez les voisins tunisiens."),
    "traditional_subtype_unknown": ("INFO", "pas assez de voisins tunisiens avec un sous-type pour en annoncer un."),
    "slot_disagrees_with_segmentation": ("REVUE", "grande pièce : la segmentation dit A, la reconnaissance dit B, et ce n'est pas un cas normal (voir recognition/outfit.py)."),
    "crop": ("REVUE", "qualité du crop : garment_cut_by_frame = vêtement coupé par le bord de la photo ; no_garment_segmented = rien de découpé ; low_resolution = trop petit."),
    "low_confidence": ("REVUE", "confiance slot/type sous CFG.review_conf (0,60)."),
    "agent_could_not_decide": ("REVUE", "ni le LLM ni le kNN n'ont donné d'avis fiable (route REVIEW de l'agent)."),
    "agent_review_used_knn_top": ("INFO", "la fiche utilise la meilleure catégorie du kNN faute de décision de l'agent."),
    "colour_from_pixels_or_default": ("INFO", "couleur inconnue du LLM : prise dans les pixels."),
    "usage_home_mapped_to_Casual": ("INFO", "usage 'home' converti en 'Casual' (valeur non prévue par le contrat)."),
    "duplicate_of": ("IGNORÉE", "autre morceau du même vêtement dans la même photo : une seule fiche est gardée."),
    "fragment_of_other_garment": ("IGNORÉE", "petite pièce (chaussures/sac/accessoire) reconnue comme un autre vêtement : fragment, pas un article."),
    "no_slot_for_category": ("NON SUPPORTÉE", "catégorie sans slot (ex. underwear) : aucune fiche."),
}


def explain_report(store: str | Path, top: int = 12) -> dict:
    """Lit recognition_report.json et explique, chiffres à l'appui, POURQUOI des fiches sont en needs_review ou ignorées."""
    items = json.loads((Path(store) / "recognition_report.json").read_text(encoding="utf-8"))["items"]
    st = Counter(e["status"] for e in items); photos = Counter(e["source_file"] for e in items)
    print(f"{len(items)} pièces découpées sur {len(photos)} photos | statuts : {dict(st)}")
    print("pièces par photo :", dict(sorted(Counter(photos.values()).items())))
    kept = [e for e in items if e["status"] != "discarded"]
    base = lambda r: r.split(":")[0]
    rc = Counter(base(r) for e in kept for r in e["reasons"])
    print("\nRAISONS (nombre de fiches concernées) :")
    for k, v in rc.most_common(top): print(f"  {v:4d}  {k:40s} [{REASON_HELP.get(k, ('?', ''))[0]}] {REASON_HELP.get(k, ('', ''))[1]}")
    dis = Counter(r.split(":", 1)[1] for e in kept for r in e["reasons"] if r.startswith("slot_disagrees"))
    if dis: print("\nDésaccords segmentation → reconnaissance :", dict(dis.most_common(8)))
    blocking = {"slot_mapping_unconfirmed", "slot_disagrees_with_segmentation", "crop", "low_confidence", "agent_could_not_decide"}
    nr = [e for e in kept if e["status"] == "needs_review"]; only_trad = [e for e in nr if {base(r) for r in e["reasons"]} & blocking <= {"slot_mapping_unconfirmed"}]
    print(f"\nneeds_review : {len(nr)} fiche(s), dont {len(only_trad)} UNIQUEMENT parce que le slot des pièces traditionnelles n'est pas validé (revue voulue).")
    disc = Counter(e.get("discard_reason") for e in items if e["status"] == "discarded")
    if disc: print("ignorées :", dict(disc))
    return dict(statuts=dict(st), raisons=dict(rc), ignorees=dict(disc))
