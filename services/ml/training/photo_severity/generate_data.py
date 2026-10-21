"""Synthetic image generator for the photo-severity classifier (same honesty
as training/prank/generate_data.py and training/triage/'s synthetic set: no
real clinical wound-photo dataset was available in the time this was built,
so this is a documented, labeled proxy task -- visual pattern classes that
are genuinely learnable from pixels (blotchy red regions, dark charred
patches, diffuse bruising, a clean/calm frame) stand in for
bleeding/burn/bruise-fracture/none. A model trained on this learns the real
underlying skill (classify a photo by its dominant visual pattern) on
synthetic images, same spirit as the prank model's synthetic caller logs.
Swap in a real labeled clinical dataset post-hackathon without changing
train.py or the serving code -- only this generator changes."""

import os
import random

from PIL import Image, ImageDraw, ImageFilter

OUT_DIR = "services/ml/data/photo_severity"
CLASSES = ["bleeding", "burn", "bruise_fracture", "none_minor"]
IMAGES_PER_CLASS = 150
SIZE = 128


def _skin_base(rng: random.Random) -> Image.Image:
    # A rough skin-tone base in a plausible real-world range, plus per-image
    # texture noise so the model can't just key off a flat background color.
    base = (rng.randint(150, 225), rng.randint(110, 180), rng.randint(90, 150))
    img = Image.new("RGB", (SIZE, SIZE), base)
    noise = Image.effect_noise((SIZE, SIZE), 18).convert("RGB")
    return Image.blend(img, noise, 0.08)


def _make_bleeding(rng: random.Random) -> Image.Image:
    img = _skin_base(rng)
    draw = ImageDraw.Draw(img)
    for _ in range(rng.randint(3, 7)):
        cx, cy = rng.randint(20, SIZE - 20), rng.randint(20, SIZE - 20)
        r = rng.randint(8, 26)
        red = (rng.randint(140, 200), rng.randint(0, 20), rng.randint(0, 20))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=red)
    return img.filter(ImageFilter.GaussianBlur(1.2))


def _make_burn(rng: random.Random) -> Image.Image:
    img = _skin_base(rng)
    draw = ImageDraw.Draw(img)
    for _ in range(rng.randint(2, 4)):
        x0, y0 = rng.randint(10, SIZE - 60), rng.randint(10, SIZE - 60)
        w, h = rng.randint(30, 60), rng.randint(30, 60)
        dark = (rng.randint(20, 60), rng.randint(10, 30), rng.randint(5, 20))
        draw.rectangle([x0, y0, x0 + w, y0 + h], fill=dark)
        # a reddened edge ring around the charred patch
        draw.rectangle([x0 - 4, y0 - 4, x0 + w + 4, y0 + h + 4], outline=(200, 60, 40), width=3)
    return img.filter(ImageFilter.GaussianBlur(1.0))


def _make_bruise_fracture(rng: random.Random) -> Image.Image:
    img = _skin_base(rng)
    draw = ImageDraw.Draw(img)
    for _ in range(rng.randint(2, 5)):
        cx, cy = rng.randint(20, SIZE - 20), rng.randint(20, SIZE - 20)
        rx, ry = rng.randint(15, 35), rng.randint(10, 25)
        purple = (rng.randint(60, 110), rng.randint(20, 60), rng.randint(90, 140))
        draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=purple)
    return img.filter(ImageFilter.GaussianBlur(2.0))


def _make_none_minor(rng: random.Random) -> Image.Image:
    img = _skin_base(rng)
    if rng.random() < 0.3:
        draw = ImageDraw.Draw(img)
        cx, cy = rng.randint(30, SIZE - 30), rng.randint(30, SIZE - 30)
        r = rng.randint(4, 10)
        pink = (min(255, int(_avg(img)[0]) + 30), 120, 110)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=pink)
    return img.filter(ImageFilter.GaussianBlur(0.5))


def _avg(img: Image.Image):
    return img.resize((1, 1)).getpixel((0, 0))


MAKERS = {
    "bleeding": _make_bleeding, "burn": _make_burn,
    "bruise_fracture": _make_bruise_fracture, "none_minor": _make_none_minor,
}


def main() -> None:
    rng = random.Random(42)
    rows = []
    for cls in CLASSES:
        cls_dir = os.path.join(OUT_DIR, cls)
        os.makedirs(cls_dir, exist_ok=True)
        for i in range(IMAGES_PER_CLASS):
            img = MAKERS[cls](rng)
            path = os.path.join(cls_dir, f"{i:04d}.png")
            img.save(path)
            rows.append((path, cls))
    print(f"generated {len(rows)} synthetic images across {len(CLASSES)} classes in {OUT_DIR}")


if __name__ == "__main__":
    main()
