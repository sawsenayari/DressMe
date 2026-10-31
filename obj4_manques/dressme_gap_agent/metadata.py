"""Normalize Colab embedding metadata paths to local wardrobe-relative paths."""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
import sys
import tempfile
from typing import Any


class MetadataError(ValueError):
    """Raised when embedding metadata cannot be mapped safely to local images."""


def rewrite_image_paths(
    metadata_csv: str | Path,
    wardrobe_root: str | Path,
    project_root: str | Path = ".",
) -> dict[str, Any]:
    """Replace exported Colab image paths using category/filename local mapping.

    All rows are validated before the CSV is atomically replaced. Other columns
    and row order are preserved so embedding row indices remain aligned.
    """
    metadata_path = Path(metadata_csv)
    wardrobe_path = Path(wardrobe_root).resolve()
    project_path = Path(project_root).resolve()
    try:
        with metadata_path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            fieldnames = reader.fieldnames
            if not fieldnames or not {"image_path", "filename", "category"}.issubset(fieldnames):
                raise MetadataError("Metadata CSV requires image_path, filename, and category columns.")
            rows = list(reader)
    except OSError as exc:
        raise MetadataError("Could not read the embedding metadata CSV.") from exc

    rewritten: list[dict[str, str]] = []
    mapped_paths: set[str] = set()
    for index, row in enumerate(rows):
        filename = row.get("filename", "")
        category = row.get("category", "")
        if not filename or Path(filename).name != filename or not category or Path(category).name != category:
            raise MetadataError(f"Metadata row {index} has an unsafe category or filename.")
        local_image = (wardrobe_path / category / filename).resolve()
        try:
            local_image.relative_to(wardrobe_path)
            relative_path = local_image.relative_to(project_path).as_posix()
        except ValueError as exc:
            raise MetadataError(f"Metadata row {index} maps outside the project wardrobe.") from exc
        if not local_image.is_file():
            raise MetadataError(f"Metadata row {index} does not map to a local image.")
        if relative_path in mapped_paths:
            raise MetadataError(f"Metadata row {index} duplicates a local image path.")
        mapped_paths.add(relative_path)
        row["image_path"] = relative_path
        rewritten.append(row)

    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=metadata_path.parent,
            suffix=".tmp",
            delete=False,
        ) as destination:
            temp_name = destination.name
            writer = csv.DictWriter(destination, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rewritten)
        os.replace(temp_name, metadata_path)
    except OSError as exc:
        if temp_name and Path(temp_name).exists():
            Path(temp_name).unlink(missing_ok=True)
        raise MetadataError("Could not safely update the embedding metadata CSV.") from exc

    return {"rows": len(rewritten), "metadata_path": str(metadata_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Map Colab image paths to local wardrobe files.")
    parser.add_argument("--metadata", default="wardrobe_embeddings/fashion_metadata.csv")
    parser.add_argument("--wardrobe-root", default="wardrobe/re_polyvore_sample")
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()
    try:
        result = rewrite_image_paths(args.metadata, args.wardrobe_root, args.project_root)
    except (MetadataError, OSError) as exc:
        print(f"Metadata path normalization failed: {exc}", file=sys.stderr)
        return 2
    print(f"Updated image_path for {result['rows']} rows in {result['metadata_path']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
