"""Local FashionCLIP embeddings and zero-shot visual labels for wardrobe photos.

This module uses the pretrained FashionCLIP encoder only. It does not load or
use the notebook's PCA compatibility classifier, judge model, scores, or report.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError


DEFAULT_MODEL = "patrickjohncyh/fashion-clip"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_IMAGE_PIXELS = 24_000_000
DEFAULT_COLORS = (
    "black", "white", "beige", "navy blue", "grey", "brown", "red", "green",
    "blue", "pink", "purple", "yellow", "orange", "multicolor",
)
PATTERNS = (
    "solid", "striped", "plaid", "floral", "geometric print", "animal print",
    "graphic print", "polka dot", "textured",
)
STYLE_LABELS = (
    "casual", "formal", "sporty", "streetwear", "business casual", "minimalist",
    "bohemian", "eveningwear", "classic",
)

CATEGORY_TEXT = {
    "top": "top",
    "pants": "pants",
    "skirt": "skirt",
    "legwear": "legwear",
    "dress": "dress",
    "jumpsuit": "jumpsuit",
    "outwear": "outerwear",
    "shoes": "shoes",
    "bag": "bag",
    "eyewear": "eyewear",
    "earrings": "earrings",
    "necklace": "necklace",
    "neckwear": "neckwear",
    "bracelet": "bracelet",
    "rings": "rings",
    "watches": "watch",
    "hats": "hat",
    "gloves": "gloves",
    "hairwear": "hair accessory",
    "brooch": "brooch",
}

# Mirrored from the notebook's slot mapping; this is category structure, not a
# learned compatibility result.
SLOT_OF = {
    "top": "top",
    "skirt": "bottom",
    "pants": "bottom",
    "legwear": "accessory",
    "dress": "onepiece",
    "jumpsuit": "onepiece",
    "outwear": "outer",
    "shoes": "shoes",
    "bag": "bag",
}


class FashionEncoderError(RuntimeError):
    """Raised when inventory inputs or local FashionCLIP inference fail."""


def discover_images(root: str | Path) -> list[Path]:
    folder = Path(root)
    if not folder.is_dir():
        raise FashionEncoderError("Wardrobe image folder is missing or is not a directory.")
    images = sorted(
        (path for path in folder.rglob("*") if path.is_file() and path.suffix.casefold() in IMAGE_SUFFIXES),
        key=lambda path: path.relative_to(folder).as_posix().casefold(),
    )
    if not images:
        raise FashionEncoderError("No JPEG, PNG, or WebP images were found in the wardrobe folder.")
    return images


def _slot_for(category: str) -> str:
    return SLOT_OF.get(category.casefold(), "accessory")


def _safe_category(path: Path, root: Path) -> tuple[str, str]:
    relative = path.relative_to(root)
    category = relative.parts[0].casefold() if len(relative.parts) > 1 else "unknown"
    slot = _slot_for(category) if category != "unknown" else "unknown"
    return category, slot


def _load_rgb(path: Path) -> Image.Image:
    try:
        if path.stat().st_size > MAX_IMAGE_BYTES:
            raise FashionEncoderError("A wardrobe image exceeds the 12 MiB file-size limit.")
        with Image.open(path) as source:
            if source.format not in {"JPEG", "PNG", "WEBP"}:
                raise FashionEncoderError("Wardrobe images must be JPEG, PNG, or WebP.")
            width, height = source.size
            if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS:
                raise FashionEncoderError("A wardrobe image has invalid or excessive pixel dimensions.")
            source.load()
            return ImageOps.exif_transpose(source).convert("RGB")
    except FashionEncoderError:
        raise
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise FashionEncoderError("A wardrobe image could not be decoded safely.") from exc


def _normalize(features: Any) -> Any:
    import torch

    return torch.nn.functional.normalize(features.float(), p=2, dim=-1)


def _features(output: Any) -> Any:
    import torch

    if isinstance(output, torch.Tensor):
        return output
    for name in ("image_embeds", "text_embeds", "pooler_output"):
        value = getattr(output, name, None)
        if value is not None:
            return value
    if isinstance(output, (tuple, list)) and output:
        return output[0]
    raise FashionEncoderError("FashionCLIP returned an unsupported feature format.")


def build_inventory(
    wardrobe_dir: str | Path,
    output_dir: str | Path,
    model_name: str = DEFAULT_MODEL,
    batch_size: int = 8,
    max_images: int | None = None,
    colors: tuple[str, ...] = DEFAULT_COLORS,
) -> dict[str, Any]:
    """Encode each wardrobe image and write a local inventory + embeddings cache."""
    import numpy as np
    import torch
    from transformers import CLIPImageProcessor, CLIPModel, CLIPTokenizer

    root = Path(wardrobe_dir).resolve()
    images = discover_images(root)
    if not 1 <= batch_size <= 32:
        raise FashionEncoderError("batch_size must be between 1 and 32.")
    if max_images is not None:
        if max_images < 1:
            raise FashionEncoderError("max_images must be positive when specified.")
        images = images[:max_images]

    device = torch.device("cpu")
    model = CLIPModel.from_pretrained(model_name).to(device).eval()
    image_processor = CLIPImageProcessor.from_pretrained(model_name)
    tokenizer = CLIPTokenizer.from_pretrained(model_name)
    model_revision = getattr(model.config, "_commit_hash", None)
    preprocessing = {
        "processor": type(image_processor).__name__,
        "size": image_processor.size,
        "crop_size": image_processor.crop_size,
        "image_mean": image_processor.image_mean,
        "image_std": image_processor.image_std,
        "input_color_mode": "RGB",
    }

    category_slots = [_safe_category(path, root) for path in images]
    prompts: list[str] = []
    prompt_ranges: dict[tuple[str, str], tuple[tuple[str, ...], int, int]] = {}
    for category in sorted({category for category, _ in category_slots}):
        text_name = CATEGORY_TEXT.get(category)
        subject = text_name or "clothing item"
        label_sets = {
            "color_candidates": colors if text_name else ("black", "white", "beige", "red", "blue", "green"),
            "pattern_candidates": PATTERNS,
            "style_candidates": STYLE_LABELS,
        }
        for axis, labels in label_sets.items():
            start = len(prompts)
            if axis == "color_candidates":
                prompts.extend(f"a photo of a {label} {subject}" for label in labels)
            elif axis == "pattern_candidates":
                prompts.extend(f"a photo of a {subject} with a {label} pattern" for label in labels)
            else:
                prompts.extend(f"a photo of a {subject} in {label} style" for label in labels)
            prompt_ranges[(category, axis)] = (tuple(labels), start, len(prompts))

    text_vectors = []
    with torch.inference_mode():
        for offset in range(0, len(prompts), 64):
            batch = tokenizer(
                prompts[offset : offset + 64],
                padding=True,
                truncation=True,
                max_length=77,
                return_tensors="pt",
            ).to(device)
            text_vectors.append(_normalize(_features(model.get_text_features(**batch))).cpu())
    text_matrix = torch.cat(text_vectors, dim=0)

    embeddings = []
    inventory_items: list[dict[str, Any]] = []
    duplicate_first: dict[str, str] = {}
    with torch.inference_mode():
        for offset in range(0, len(images), batch_size):
            paths_batch = images[offset : offset + batch_size]
            pixel_values = image_processor(
                images=[_load_rgb(path) for path in paths_batch],
                return_tensors="pt",
            )["pixel_values"].to(device)
            vectors = _normalize(_features(model.get_image_features(pixel_values=pixel_values))).cpu()
            embeddings.extend(vectors.numpy().astype(np.float32))

    for index, (path, vector, (category, slot)) in enumerate(
        zip(images, embeddings, category_slots), start=1
    ):
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        item_id = f"wardrobe-{index:04d}"
        duplicate_of = duplicate_first.setdefault(checksum, item_id)
        attributes: dict[str, list[dict[str, Any]]] = {}
        for axis in ("color_candidates", "pattern_candidates", "style_candidates"):
            labels, start, end = prompt_ranges[(category, axis)]
            similarities = (torch.from_numpy(vector) @ text_matrix[start:end].T).tolist()
            order = sorted(range(len(labels)), key=lambda i: similarities[i], reverse=True)[:3]
            attributes[axis] = [
                {"label": labels[i], "similarity": round(float(similarities[i]), 4)}
                for i in order
            ]
        inventory_items.append(
            {
                "item_id": item_id,
                "source_path": path.relative_to(root).as_posix(),
                "category": category,
                "slot": slot,
                **attributes,
                "duplicate_of": duplicate_of if duplicate_of != item_id else None,
            }
        )

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    embedding_path = destination / "fashionclip_embeddings.npz"
    inventory_path = destination / "wardrobe_inventory.json"
    np.savez_compressed(
        embedding_path,
        item_ids=np.array([item["item_id"] for item in inventory_items]),
        embeddings=np.asarray(embeddings, dtype=np.float32),
        model_name=np.array(model_name),
    )
    duplicate_targets = {item["duplicate_of"] for item in inventory_items if item["duplicate_of"]}
    duplicate_extras = sum(item["duplicate_of"] is not None for item in inventory_items)
    payload = {
        "schema_version": "wardrobe-inventory-v1",
        "encoder": {
            "model_id": model_name,
            "revision": model_revision,
            "preprocessing": preprocessing,
        },
        "encoder_role": "pretrained visual embedding and zero-shot color shortlist only; no compatibility score",
        "item_count": len(inventory_items),
        "embedding_dimension": int(embeddings[0].shape[0]),
        "embedding_dtype": "float32",
        "embedding_normalization": "L2",
        "duplicate_image_groups": len(duplicate_targets),
        "duplicate_image_extra_records": duplicate_extras,
        "items": inventory_items,
    }
    inventory_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    manifest_path = destination / "manifest.json"
    manifest = {
        "schema_version": "dressme-fashionclip-inventory-v1",
        "source_folder": root.name,
        "encoder": payload["encoder"],
        "encoder_role": payload["encoder_role"],
        "embedding": {
            "file": embedding_path.name,
            "shape": [len(embeddings), int(embeddings[0].shape[0])],
            "dtype": "float32",
            "normalization": "L2",
        },
        "inventory": {"file": inventory_path.name, "rows": len(inventory_items)},
        "row_mapping": "wardrobe_inventory.items[i] and item_ids[i] correspond to embeddings[i]",
        "integrity": {
            "embedding_sha256": hashlib.sha256(embedding_path.read_bytes()).hexdigest(),
            "inventory_sha256": hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
        },
        "duplicate_image_groups": len(duplicate_targets),
        "duplicate_image_extra_records": duplicate_extras,
        "compatibility_model_used": False,
        "gap_report_used": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "item_count": len(inventory_items),
        "duplicate_image_groups": len(duplicate_targets),
        "duplicate_image_extra_records": duplicate_extras,
        "embedding_dimension": int(embeddings[0].shape[0]),
        "encoder_revision": model_revision,
        "inventory_path": str(inventory_path),
        "embedding_path": str(embedding_path),
        "manifest_path": str(manifest_path),
        "category_counts": dict(Counter(item["category"] for item in inventory_items)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a local FashionCLIP wardrobe inventory.")
    parser.add_argument("--wardrobe-dir", default="wardrobe")
    parser.add_argument("--output-dir", default="wardrobe/.dressme-cache")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-images", type=int, default=None, help="Optional smoke-test cap; default processes all images.")
    args = parser.parse_args()
    try:
        result = build_inventory(args.wardrobe_dir, args.output_dir, args.model, args.batch_size, args.max_images)
    except (FashionEncoderError, OSError, ImportError, ValueError) as exc:
        print(f"FashionCLIP inventory failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
