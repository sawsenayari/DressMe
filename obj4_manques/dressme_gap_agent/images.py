"""Bounded, privacy-conscious preparation of wardrobe images for vision models."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageOps, UnidentifiedImageError


MAX_IMAGES_PER_REQUEST = 3
MAX_IMAGE_FILE_BYTES = 12 * 1024 * 1024
MAX_IMAGE_PIXELS = 24_000_000
MAX_IMAGE_DIMENSION = 1600
MAX_TOTAL_ENCODED_BYTES = 12 * 1024 * 1024
SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP"}


class ImageInputError(ValueError):
    """Raised when an image is missing, unsupported, unsafe, or too large."""


def collect_wardrobe_images(directory: str | Path) -> list[Path]:
    """Collect top-level wardrobe photos in stable order, enforcing the model limit."""
    folder = Path(directory)
    if not folder.is_dir():
        raise ImageInputError("Wardrobe directory does not exist or is not a directory.")
    supported_suffixes = {".jpg", ".jpeg", ".png", ".webp"}
    paths = sorted(
        (path for path in folder.rglob("*") if path.is_file() and path.suffix.casefold() in supported_suffixes),
        key=lambda path: path.relative_to(folder).as_posix().casefold(),
    )
    if not paths:
        raise ImageInputError("Wardrobe directory contains no JPEG, PNG, or WebP images.")
    if len(paths) > MAX_IMAGES_PER_REQUEST:
        raise ImageInputError(
            f"This vision route accepts at most {MAX_IMAGES_PER_REQUEST} wardrobe images per request; "
            f"found {len(paths)}."
        )
    return paths


@dataclass(frozen=True)
class PreparedImage:
    """Image data prepared for the OpenAI-compatible multimodal message format."""

    data_url: str
    byte_size: int
    width: int
    height: int

    def message_part(self) -> dict[str, object]:
        return {"type": "image_url", "image_url": {"url": self.data_url}}


def prepare_images(paths: Iterable[str | Path]) -> list[PreparedImage]:
    """Validate, orient, downscale, and re-encode local images as JPEG data URLs.

    Local paths and source metadata are intentionally not returned or sent to the
    model. Re-encoding strips EXIF metadata, including GPS fields.
    """
    image_paths = list(paths)
    if len(image_paths) > MAX_IMAGES_PER_REQUEST:
        raise ImageInputError(f"At most {MAX_IMAGES_PER_REQUEST} images are allowed per request.")

    prepared: list[PreparedImage] = []
    total_bytes = 0
    for image_path in image_paths:
        path = Path(image_path)
        try:
            if not path.is_file():
                raise ImageInputError("An image path does not point to a regular file.")
            if path.stat().st_size > MAX_IMAGE_FILE_BYTES:
                raise ImageInputError("An image exceeds the 12 MiB file-size limit.")
            raw = path.read_bytes()
            with Image.open(BytesIO(raw)) as source:
                if source.format not in SUPPORTED_FORMATS:
                    raise ImageInputError("Use JPEG, PNG, or WebP wardrobe images.")
                width, height = source.size
                if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS:
                    raise ImageInputError("An image has invalid or excessive pixel dimensions.")
                source.load()
                normalized = ImageOps.exif_transpose(source).convert("RGB")
                normalized.thumbnail(
                    (MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION),
                    Image.Resampling.LANCZOS,
                )
                output = BytesIO()
                normalized.save(output, format="JPEG", quality=82, optimize=True)
        except ImageInputError:
            raise
        except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
            raise ImageInputError("An image could not be safely decoded.") from exc

        encoded = output.getvalue()
        total_bytes += len(encoded)
        if total_bytes > MAX_TOTAL_ENCODED_BYTES:
            raise ImageInputError("The prepared images exceed the 12 MiB total-size limit.")
        data_url = "data:image/jpeg;base64," + base64.b64encode(encoded).decode("ascii")
        prepared.append(
            PreparedImage(
                data_url=data_url,
                byte_size=len(encoded),
                width=normalized.width,
                height=normalized.height,
            )
        )
    return prepared
