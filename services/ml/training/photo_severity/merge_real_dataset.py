"""Merges the real wound-photo dataset (Kaggle: yasinpratomo/wound-dataset,
downloaded to data/wound_dataset_raw/) into the photo_severity training set
alongside the synthetic images. Closes the actual gap a real test photo
exposed: a classifier trained only on synthetic PIL-drawn shapes called a
real bleeding wound "none_minor" at 95% confidence (and the vision LLM
moondream got it wrong too on a real photo) -- neither model had ever seen
a real wound photo before this. Real photos stay real photos; no synthetic
transform is applied to them, only a resize to match the training pipeline.

Source dataset has 7 classes with no "no injury" class at all (it's a wound
dataset, by definition every image shows one) -- mapped onto our 4-class
taxonomy as follows. Abrasions/Cut/Laceration/Stab_wound/Ingrown_nails all
map to "bleeding" (open-wound-with-blood-visible is the closest real match
in our taxonomy; a finer real taxonomy is future work, not try-to-guess-it
tonight work). Bruises -> bruise_fracture. Burns -> burn. none_minor has NO
real source (nothing in a wound dataset is "no visible injury") and stays
entirely synthetic -- run generate_data.py first, this only adds to it."""

import os
import shutil

from PIL import Image

RAW_DIR = "services/ml/data/wound_dataset_raw/Wound_dataset"
OUT_DIR = "services/ml/data/photo_severity"
SIZE = 128

CLASS_MAP = {
    "Abrasions": "bleeding", "Cut": "bleeding", "Laceration": "bleeding",
    "Stab_wound": "bleeding", "Ingrown_nails": "bleeding",
    "Bruises": "bruise_fracture",
    "Burns": "burn",
}


def main() -> None:
    if not os.path.isdir(RAW_DIR):
        raise SystemExit(f"{RAW_DIR} not found -- run `kaggle datasets download -d yasinpratomo/wound-dataset "
                          f"-p services/ml/data/wound_dataset_raw --unzip` first")

    counts: dict[str, int] = {}
    for src_class, dst_class in CLASS_MAP.items():
        src_dir = os.path.join(RAW_DIR, src_class)
        if not os.path.isdir(src_dir):
            print(f"skip {src_class}: not found in dataset")
            continue
        dst_dir = os.path.join(OUT_DIR, dst_class)
        os.makedirs(dst_dir, exist_ok=True)
        n = 0
        for fname in sorted(os.listdir(src_dir)):
            src_path = os.path.join(src_dir, fname)
            try:
                img = Image.open(src_path).convert("RGB")
            except Exception as exc:
                print(f"  skip unreadable file {src_path}: {exc}")
                continue
            img = img.resize((SIZE, SIZE))
            dst_path = os.path.join(dst_dir, f"real_{src_class.lower()}_{n:04d}.jpg")
            img.save(dst_path, quality=90)
            n += 1
        counts[f"{src_class} -> {dst_class}"] = n
        print(f"{src_class} ({n} images) -> {dst_class}/")

    print("\nmerged real images:", counts)
    print("none_minor has no real source -- stays synthetic-only, as documented above")


if __name__ == "__main__":
    main()
