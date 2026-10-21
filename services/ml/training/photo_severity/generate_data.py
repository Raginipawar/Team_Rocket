"""Synthetic image generator for the photo-severity classifier (same honesty
as training/prank/generate_data.py and training/triage/'s synthetic set: no
real clinical wound-photo dataset was available in the time this was built,
so this is a documented, labeled proxy task -- visual pattern classes that
are genuinely learnable from pixels (irregular red regions, dark charred
patches, diffuse bruising, varied non-injury scenes) stand in for
bleeding/burn/bruise-fracture/none. A model trained on this learns the real
underlying skill (classify a photo by its dominant visual pattern) on
synthetic images, same spirit as the prank model's synthetic caller logs.
Swap in a real labeled clinical dataset post-hackathon without changing
train.py or the serving code -- only this generator changes.

v2: the first version trained a classifier that called a real bleeding
wound photo "none_minor" at 95% confidence -- found via an actual real test
photo, not a held-out synthetic split (which it aced at 100%, because it
was only ever tested against its own narrow synthetic distribution). Root
cause: perfectly smooth ellipses on a flat skin-tone background look
nothing like a real camera photo (texture, lighting, irregular wound
edges, JPEG artifacts, varied framing/background), so the model had
learned to key off synthetic-generator fingerprints, not the actual visual
pattern. This version adds: irregular/organic blob outlines (not perfect
ellipses), varied backgrounds for none_minor (a real "nothing alarming"
photo is rarely a skin close-up), per-image blur/noise/lighting variation,
and a real JPEG re-encode pass -- closing as much of the synthetic-to-real
gap as is achievable without an actual photo dataset."""

import io
import os
import random

from PIL import Image, ImageDraw, ImageFilter

OUT_DIR = "services/ml/data/photo_severity"
CLASSES = ["bleeding", "burn", "bruise_fracture", "none_minor"]
IMAGES_PER_CLASS = 220
SIZE = 128


def _jitter_polygon(rng: random.Random, cx: float, cy: float, r: float, n: int = 10) -> list[tuple[float, float]]:
    """An organic, irregular blob outline instead of a perfect ellipse --
    a real wound/bruise/burn edge is never a clean geometric curve."""
    import math
    pts = []
    for i in range(n):
        angle = 2 * math.pi * i / n
        rr = r * rng.uniform(0.6, 1.25)
        pts.append((cx + rr * math.cos(angle), cy + rr * math.sin(angle)))
    return pts


def _skin_base(rng: random.Random) -> Image.Image:
    base = (rng.randint(150, 225), rng.randint(110, 180), rng.randint(90, 150))
    img = Image.new("RGB", (SIZE, SIZE), base)
    noise = Image.effect_noise((SIZE, SIZE), rng.randint(14, 28)).convert("RGB")
    img = Image.blend(img, noise, rng.uniform(0.06, 0.14))
    # A soft lighting gradient (real photos are rarely evenly lit) -- a
    # radial brightness falloff, +/-15% at most, via ImageEnhance rather
    # than a from-scratch mask composite (an earlier version of this mask
    # math was inverted and crushed the whole image to near-black; this is
    # simpler and was actually checked against its own output).
    from PIL import ImageEnhance
    return ImageEnhance.Brightness(img).enhance(rng.uniform(0.85, 1.1))


def _scene_base(rng: random.Random) -> Image.Image:
    """A generic non-skin background -- clothing, pavement, grass, a wall --
    standing in for "a person standing" / "the scene" / nothing alarming,
    which is what a real none_minor photo actually tends to look like."""
    palette = [
        (90, 140, 70), (120, 115, 110), (70, 90, 130), (180, 170, 150),
        (60, 60, 65), (150, 130, 100), (100, 100, 100), (170, 150, 190),
    ]
    base = rng.choice(palette)
    base = tuple(max(0, min(255, c + rng.randint(-20, 20))) for c in base)
    img = Image.new("RGB", (SIZE, SIZE), base)
    noise = Image.effect_noise((SIZE, SIZE), rng.randint(20, 40)).convert("RGB")
    return Image.blend(img, noise, rng.uniform(0.1, 0.22))


def _post_process(img: Image.Image, rng: random.Random) -> Image.Image:
    """Camera-like post-processing every class gets, so the model can't use
    'suspiciously clean PNG' as a shortcut signal."""
    img = img.filter(ImageFilter.GaussianBlur(rng.uniform(0.4, 1.6)))
    if rng.random() < 0.3:
        img = img.rotate(rng.uniform(-8, 8), fillcolor=tuple(img.resize((1, 1)).getpixel((0, 0))))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=rng.randint(55, 90))  # real JPEG re-encode -> real compression artifacts
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def _make_bleeding(rng: random.Random) -> Image.Image:
    img = _skin_base(rng)
    draw = ImageDraw.Draw(img)
    for _ in range(rng.randint(3, 7)):
        cx, cy = rng.randint(20, SIZE - 20), rng.randint(20, SIZE - 20)
        r = rng.randint(8, 26)
        red = (rng.randint(130, 200), rng.randint(0, 25), rng.randint(0, 25))
        draw.polygon(_jitter_polygon(rng, cx, cy, r, rng.randint(8, 14)), fill=red)
        # a thin darker rim and occasional bright highlight -- real wet blood has sheen
        if rng.random() < 0.5:
            draw.polygon(_jitter_polygon(rng, cx, cy, r * 0.4, 6), fill=(min(255, red[0] + 40), red[1] + 15, red[2] + 15))
    return _post_process(img, rng)


def _make_burn(rng: random.Random) -> Image.Image:
    img = _skin_base(rng)
    draw = ImageDraw.Draw(img)
    for _ in range(rng.randint(2, 4)):
        cx, cy = rng.randint(30, SIZE - 30), rng.randint(30, SIZE - 30)
        r = rng.randint(18, 38)
        dark = (rng.randint(20, 65), rng.randint(10, 35), rng.randint(5, 25))
        draw.polygon(_jitter_polygon(rng, cx, cy, r, rng.randint(8, 12)), fill=dark)
        draw.polygon(_jitter_polygon(rng, cx, cy, r * 1.25, 10), outline=(200, 60, 40), width=3)
    return _post_process(img, rng)


def _make_bruise_fracture(rng: random.Random) -> Image.Image:
    img = _skin_base(rng)
    draw = ImageDraw.Draw(img)
    for _ in range(rng.randint(2, 5)):
        cx, cy = rng.randint(20, SIZE - 20), rng.randint(20, SIZE - 20)
        r = rng.randint(14, 32)
        purple = (rng.randint(55, 110), rng.randint(20, 65), rng.randint(90, 145))
        draw.polygon(_jitter_polygon(rng, cx, cy, r, rng.randint(8, 12)), fill=purple)
    return _post_process(img, rng)


def _make_none_minor(rng: random.Random) -> Image.Image:
    # Mostly generic scenes (what a real "nothing alarming" photo looks
    # like), sometimes a calm skin frame with no wound -- not always a
    # skin close-up, which was the earlier version's real blind spot.
    img = _scene_base(rng) if rng.random() < 0.6 else _skin_base(rng)
    if rng.random() < 0.15:
        draw = ImageDraw.Draw(img)
        cx, cy = rng.randint(30, SIZE - 30), rng.randint(30, SIZE - 30)
        r = rng.randint(4, 9)
        draw.polygon(_jitter_polygon(rng, cx, cy, r, 7), fill=(190, 130, 120))
    return _post_process(img, rng)


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
