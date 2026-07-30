#!/usr/bin/env python3
"""Prepare the supplied portrait for high-contrast ASCII conversion."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "assets" / "source-photo.webp"
DEFAULT_OUTPUT = ROOT / "assets" / "source-prepped.png"
TARGET_SIZE = (500, 560)


def _center_crop(image: Image.Image, aspect: float = 0.89) -> Image.Image:
    width, height = image.size
    current = width / height
    if current < aspect:
        new_height = int(width / aspect)
        top = max(0, int((height - new_height) * 0.02))
        bottom = min(height, top + new_height)
        top = bottom - new_height
        return image.crop((0, top, width, bottom))
    new_width = int(height * aspect)
    left = (width - new_width) // 2
    return image.crop((left, 0, left + new_width, height))


def _remove_background(rgb: np.ndarray) -> tuple[np.ndarray, str]:
    try:
        from rembg import remove  # type: ignore

        cutout = remove(Image.fromarray(rgb).convert("RGBA"))
        alpha = np.asarray(cutout.getchannel("A"), dtype=np.float32) / 255.0
        foreground = np.asarray(cutout.convert("RGB"), dtype=np.uint8)
        return np.dstack((foreground, alpha)), "rembg"
    except (ImportError, RuntimeError, OSError):
        mask = np.zeros(rgb.shape[:2], dtype=np.uint8)
        background_model = np.zeros((1, 65), np.float64)
        foreground_model = np.zeros((1, 65), np.float64)
        height, width = rgb.shape[:2]
        rectangle = (max(2, width // 30), max(2, height // 80), width - width // 15, height - height // 35)
        cv2.grabCut(rgb, mask, rectangle, background_model, foreground_model, 7, cv2.GC_INIT_WITH_RECT)
        alpha = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 1.0, 0.0).astype(np.float32)
        alpha = cv2.GaussianBlur(alpha, (0, 0), 2.2)
        return np.dstack((rgb, alpha)), "opencv-grabcut"


def prepare_portrait(source: Path, output: Path, remove_background: bool = True) -> Path:
    if not source.is_file():
        raise FileNotFoundError(f"portrait source not found: {source}")
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
    image = _center_crop(image).resize(TARGET_SIZE, Image.Resampling.LANCZOS)
    rgb = np.asarray(image, dtype=np.uint8)

    if remove_background:
        layered, method = _remove_background(rgb)
        foreground = layered[:, :, :3].astype(np.float32)
        alpha = layered[:, :, 3].astype(np.float32)
    else:
        foreground = rgb.astype(np.float32)
        alpha = np.ones(rgb.shape[:2], dtype=np.float32)
        method = "disabled"

    gray = cv2.cvtColor(foreground.astype(np.uint8), cv2.COLOR_RGB2GRAY)
    gray = cv2.createCLAHE(clipLimit=2.25, tileGridSize=(8, 8)).apply(gray)
    gray = cv2.GaussianBlur(gray, (0, 0), 0.45)
    gray = cv2.convertScaleAbs(gray, alpha=1.04, beta=7)
    composed = gray.astype(np.float32) * alpha + 255.0 * (1.0 - alpha)
    composed = np.clip(composed, 0, 255).astype(np.uint8)

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp.png")
    Image.fromarray(composed, mode="L").save(temporary, format="PNG", optimize=True)
    temporary.replace(output)
    print(f"wrote {output}: {TARGET_SIZE[0]}x{TARGET_SIZE[1]} via {method}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("output", nargs="?", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--keep-background", action="store_true")
    args = parser.parse_args()
    prepare_portrait(args.source, args.output, remove_background=not args.keep_background)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
