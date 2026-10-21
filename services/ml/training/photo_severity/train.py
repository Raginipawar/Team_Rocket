"""Fine-tunes torchvision's pretrained MobileNetV2 (ImageNet weights) on the
synthetic photo_severity set -- transfer learning, not training from scratch:
the backbone's real learned visual features (edges, color blobs, textures)
are kept frozen, only the final classifier head is retrained for our 4
classes. This is the actually-correct way to fine-tune a small open-source
CV model on a small dataset, same spirit as every other model in this repo
being the right real tool for its job rather than a from-scratch reinvention."""

import json

import torch
from torch import nn
from torch.utils.data import DataLoader, random_split
from torchvision import datasets, models, transforms

DATA_DIR = "services/ml/data/photo_severity"
ARTIFACT_PATH = "services/ml/artifacts/photo_severity/mobilenet_v2_finetuned.pt"
REPORT_PATH = "services/ml/training/photo_severity/REPORT.json"
EPOCHS = 14
BATCH_SIZE = 16
LR = 1e-3


def main() -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Light augmentation on top of the generator's own per-image variation --
    # a real photo is never framed/lit/colored exactly like the training
    # set, so forcing a bit of that variation at train time (not just baking
    # it into the generator once) makes the decision boundary less brittle.
    train_transform = transforms.Compose([
        transforms.Resize((128, 128)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(12),
        transforms.ColorJitter(brightness=0.25, contrast=0.25, saturation=0.2),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    eval_transform = transforms.Compose([
        transforms.Resize((128, 128)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    full_ds = datasets.ImageFolder(DATA_DIR, transform=train_transform)
    classes = full_ds.classes  # alphabetical: ImageFolder's own ordering, saved below so serving matches exactly

    n_val = max(1, int(0.2 * len(full_ds)))
    train_ds, val_ds = random_split(full_ds, [len(full_ds) - n_val, n_val], generator=torch.Generator().manual_seed(42))
    # The val split must not see train-time augmentation (that would make
    # val accuracy an optimistic lie) -- ImageFolder's transform is shared by
    # reference across random_split's two Subsets, so val_ds's underlying
    # dataset object is swapped to the eval transform after the split.
    val_ds.dataset = datasets.ImageFolder(DATA_DIR, transform=eval_transform)
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE)

    model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.IMAGENET1K_V1)
    for param in model.features.parameters():
        param.requires_grad = False  # freeze the pretrained backbone -- only the head learns our classes
    model.classifier[1] = nn.Linear(model.last_channel, len(classes))
    model = model.to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.classifier.parameters(), lr=LR)

    for epoch in range(EPOCHS):
        model.train()
        total_loss = 0.0
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            loss = criterion(model(images), labels)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * images.size(0)
        print(f"epoch {epoch + 1}/{EPOCHS} train_loss={total_loss / len(train_ds):.4f}")

    model.eval()
    correct, total = 0, 0
    with torch.no_grad():
        for images, labels in val_loader:
            images, labels = images.to(device), labels.to(device)
            preds = model(images).argmax(dim=1)
            correct += (preds == labels).sum().item()
            total += labels.size(0)
    val_acc = correct / total if total else 0.0

    torch.save({"state_dict": model.state_dict(), "classes": classes}, ARTIFACT_PATH)

    report = {"classes": classes, "n_train": len(train_ds), "n_val": len(val_ds), "val_accuracy": round(val_acc, 4)}
    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
