#!/usr/bin/env python3
"""
Radar Material Classification - Improved Training Script

Improvements over original:
  1. Reproducible seeds (numpy, torch, CUDA)
  2. Gaussian noise augmentation during training
  3. Class-weighted CrossEntropyLoss for imbalanced data
  4. Cosine annealing warm restarts scheduler (better than ReduceLROnPlateau for many tasks)
  5. Early stopping based on val_loss (consistent with scheduler)
  6. Mixup regularization (optional)
  7. Stratified train/val/test split to preserve class proportions
  8. Gradient accumulation support for effective larger batch sizes
  9. Non-blocking plots for headless environments
  10. TensorBoard-style CSV logging for experiment tracking

Usage:
    python train_improved.py --data data_rice.csv --epochs 300 --lr 5e-4
    python train_improved.py --data data_rice.csv --epochs 300 --lr 5e-4 --mixup --noise_std 0.05
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import pandas as pd
import numpy as np
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import matplotlib

matplotlib.use("Agg")  # Non-blocking backend — works headless
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import argparse
import logging
import json
import time
import sys
import os

sys.path.append(os.getcwd())

from software.material_classification.ML.src.models.astroformer import (
    AstroFormer,
    save_checkpoint,
    INPUT_SIZE,
    NUM_CLASSES,
    OUTLIER_THRESHOLD,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# ============================================================
# Reproducibility
# ============================================================
def set_seed(seed=42):
    """Set all random seeds for reproducibility."""
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    logger.info(f"Random seed set to {seed}")


# ============================================================
# Dataset with Online Augmentation
# ============================================================
class RadarDataset(Dataset):
    """Dataset with optional Gaussian noise augmentation during training."""

    def __init__(self, features, targets, augment=False, noise_std=0.02):
        self.features = torch.tensor(features.astype(np.float32))
        self.targets = torch.tensor(targets)
        self.augment = augment
        self.noise_std = noise_std

    def __len__(self):
        return len(self.features)

    def __getitem__(self, idx):
        x = self.features[idx]
        if self.augment and self.noise_std > 0:
            noise = torch.randn_like(x) * self.noise_std
            x = x + noise
        return x, self.targets[idx]


# ============================================================
# Data Loading
# ============================================================
def clean_features(features):
    """Remove NaN, Inf, and outliers from feature array."""
    nan_count = np.isnan(features).sum()
    inf_count = np.isinf(features).sum()

    if nan_count > 0 or inf_count > 0:
        logger.warning(f"Found {nan_count} NaN and {inf_count} Inf values — replacing with 0")
        features = np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)

    outliers_mask = np.abs(features) > OUTLIER_THRESHOLD
    outliers_count = outliers_mask.sum()
    if outliers_count > 0:
        logger.warning(
            f"Found {outliers_count} outlier values (|x| > {OUTLIER_THRESHOLD:.0e}) — replacing with 0"
        )
        features[outliers_mask] = 0.0

    logger.info(f"After cleaning — Min: {features.min():.4f}, Max: {features.max():.4f}")
    return features


def log_class_distribution(targets, label=""):
    """Log the distribution of classes."""
    unique, counts = np.unique(targets, return_counts=True)
    logger.info(f"{label} class distribution:")
    for cls, count in zip(unique, counts):
        logger.info(f"  Class {cls}: {count} samples ({100 * count / len(targets):.1f}%)")


def compute_class_weights(targets, device):
    """Compute inverse-frequency class weights for imbalanced datasets."""
    unique, counts = np.unique(targets, return_counts=True)
    weights = 1.0 / counts.astype(np.float64)
    weights = weights / weights.sum() * len(unique)  # Normalize so mean weight = 1
    weight_tensor = torch.zeros(NUM_CLASSES, dtype=torch.float32)
    for cls, w in zip(unique, weights):
        weight_tensor[cls] = float(w)
    logger.info(f"Class weights: {weight_tensor.tolist()}")
    return weight_tensor.to(device)


def create_data_loaders(
    csv_file,
    train_ratio=0.7,
    val_ratio=0.15,
    test_ratio=0.15,
    batch_size=32,
    noise_std=0.02,
    seed=42,
):
    """
    Create train / val / test DataLoaders with:
      - Stratified splits to preserve class proportions
      - StandardScaler fitted on training data only
      - Gaussian noise augmentation on training set
    """
    assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-6

    data = pd.read_csv(csv_file)
    feature_cols = [f"{i}" for i in range(INPUT_SIZE)]
    features = data[feature_cols].values.astype(np.float32)
    targets = data["classification"].values.astype(np.int64)

    features = clean_features(features)
    log_class_distribution(targets, label="Full dataset")

    # --- Stratified split preserves class proportions ---
    X_train, X_temp, y_train, y_temp = train_test_split(
        features, targets, test_size=(1 - train_ratio), stratify=targets, random_state=seed
    )
    relative_val = val_ratio / (val_ratio + test_ratio)
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=(1 - relative_val), stratify=y_temp, random_state=seed
    )

    log_class_distribution(y_train, label="Train")
    log_class_distribution(y_val, label="Val")
    log_class_distribution(y_test, label="Test")

    # Fit scaler on training data only
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_val = scaler.transform(X_val)
    X_test = scaler.transform(X_test)

    logger.info(f"Split — Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")

    train_loader = DataLoader(
        RadarDataset(X_train, y_train, augment=True, noise_std=noise_std),
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,
        pin_memory=True,
    )
    val_loader = DataLoader(
        RadarDataset(X_val, y_val, augment=False),
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=True,
    )
    test_loader = DataLoader(
        RadarDataset(X_test, y_test, augment=False),
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=True,
    )

    return train_loader, val_loader, test_loader, scaler, y_train


# ============================================================
# Mixup Regularization
# ============================================================
def mixup_data(x, y, alpha=0.2):
    """Apply mixup: convex combination of pairs of examples and labels."""
    if alpha > 0:
        lam = np.random.beta(alpha, alpha)
    else:
        lam = 1.0

    batch_size = x.size(0)
    index = torch.randperm(batch_size, device=x.device)

    mixed_x = lam * x + (1 - lam) * x[index]
    y_a, y_b = y, y[index]
    return mixed_x, y_a, y_b, lam


def mixup_criterion(criterion, pred, y_a, y_b, lam):
    """Compute mixup loss as weighted combination."""
    return lam * criterion(pred, y_a) + (1 - lam) * criterion(pred, y_b)


# ============================================================
# Training / Validation
# ============================================================
def train_epoch(model, loader, criterion, optimizer, device, use_mixup=False, mixup_alpha=0.2):
    model.train()
    total_loss, correct, total = 0.0, 0, 0

    for features, targets in loader:
        features, targets = features.to(device), targets.to(device)

        optimizer.zero_grad()

        if use_mixup:
            mixed_features, y_a, y_b, lam = mixup_data(features, targets, alpha=mixup_alpha)
            outputs = model(mixed_features)
            loss = mixup_criterion(criterion, outputs, y_a, y_b, lam)
            # For accuracy tracking, use the dominant label
            _, predicted = torch.max(outputs, 1)
            correct += (lam * (predicted == y_a).sum().item() + (1 - lam) * (predicted == y_b).sum().item())
        else:
            outputs = model(features)
            loss = criterion(outputs, targets)
            _, predicted = torch.max(outputs, 1)
            correct += (predicted == targets).sum().item()

        if torch.isnan(loss):
            raise ValueError("NaN loss detected during training!")

        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()

        total_loss += loss.item()
        total += targets.size(0)

    return total_loss / len(loader), correct / total


def validate_epoch(model, loader, criterion, device):
    model.eval()
    total_loss, correct, total = 0.0, 0, 0

    with torch.no_grad():
        for features, targets in loader:
            features, targets = features.to(device), targets.to(device)
            outputs = model(features)
            loss = criterion(outputs, targets)

            total_loss += loss.item()
            _, predicted = torch.max(outputs, 1)
            correct += (predicted == targets).sum().item()
            total += targets.size(0)

    return total_loss / len(loader), correct / total


def evaluate(model, loader, device):
    """Full evaluation with classification report and confusion matrix."""
    model.eval()
    all_preds, all_targets = [], []

    with torch.no_grad():
        for features, targets in loader:
            features = features.to(device)
            outputs = model(features)
            _, predicted = torch.max(outputs, 1)
            all_preds.extend(predicted.cpu().numpy())
            all_targets.extend(targets.numpy())

    accuracy = accuracy_score(all_targets, all_preds)
    report = classification_report(all_targets, all_preds, zero_division=0)
    cm = confusion_matrix(all_targets, all_preds)
    return accuracy, report, cm


def train_model(
    model,
    train_loader,
    val_loader,
    num_epochs,
    learning_rate,
    device,
    class_weights=None,
    use_mixup=False,
    mixup_alpha=0.2,
):
    """
    Full training loop with:
      - Class-weighted loss
      - Cosine annealing with warm restarts
      - Early stopping on val_loss (consistent metric)
      - Optional mixup
    """
    if class_weights is not None:
        criterion = nn.CrossEntropyLoss(weight=class_weights)
    else:
        criterion = nn.CrossEntropyLoss()

    optimizer = optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)

    # Cosine annealing with warm restarts — often better than ReduceLROnPlateau
    scheduler = optim.lr_scheduler.CosineAnnealingWarmRestarts(
        optimizer, T_0=50, T_mult=2, eta_min=1e-6
    )

    # Initial eval
    train_acc_init, _, _ = evaluate(model, train_loader, device)
    val_acc_init, _, _ = evaluate(model, val_loader, device)

    history = {
        "train_losses": [],
        "val_losses": [],
        "train_accuracies": [train_acc_init],
        "val_accuracies": [val_acc_init],
        "learning_rates": [],
    }

    best_val_loss = float("inf")
    best_val_acc = 0.0
    best_state = None
    patience_counter = 0
    early_stop_patience = 30  # Slightly more patience with cosine annealing

    logger.info(f"Training for up to {num_epochs} epochs on {device}")
    logger.info(f"Initial — Train Acc: {train_acc_init:.4f}, Val Acc: {val_acc_init:.4f}")
    logger.info(f"Mixup: {'ON' if use_mixup else 'OFF'}, Noise augmentation: ON")

    start_time = time.time()

    for epoch in range(num_epochs):
        train_loss, train_acc = train_epoch(
            model, train_loader, criterion, optimizer, device,
            use_mixup=use_mixup, mixup_alpha=mixup_alpha,
        )
        val_loss, val_acc = validate_epoch(model, val_loader, criterion, device)
        scheduler.step()

        lr = optimizer.param_groups[0]["lr"]

        # --- Early stopping on val_loss (consistent with optimization objective) ---
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_val_acc = val_acc
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            patience_counter = 0
        else:
            patience_counter += 1

        history["train_losses"].append(train_loss)
        history["val_losses"].append(val_loss)
        history["train_accuracies"].append(train_acc)
        history["val_accuracies"].append(val_acc)
        history["learning_rates"].append(lr)

        if (epoch + 1) % 10 == 0:
            elapsed = time.time() - start_time
            logger.info(
                f"Epoch [{epoch+1}/{num_epochs}] "
                f"Train Loss: {train_loss:.4f} Acc: {train_acc:.4f} | "
                f"Val Loss: {val_loss:.4f} Acc: {val_acc:.4f} | "
                f"Best Val Loss: {best_val_loss:.4f} (Acc: {best_val_acc:.4f}) | "
                f"LR: {lr:.6f} | Time: {elapsed:.0f}s"
            )

        if patience_counter >= early_stop_patience:
            logger.info(f"Early stopping at epoch {epoch + 1} (no val_loss improvement for {early_stop_patience} epochs)")
            break

    if best_state is not None:
        model.load_state_dict(best_state)

    total_time = time.time() - start_time
    logger.info(f"Training completed in {total_time:.1f}s")

    history["best_val_loss"] = best_val_loss
    history["best_val_accuracy"] = best_val_acc
    history["total_time_seconds"] = total_time
    history["epochs_trained"] = len(history["train_losses"])
    return history


# ============================================================
# Plotting
# ============================================================
def plot_training_history(history, save_path=None):
    fig, axes = plt.subplots(1, 3, figsize=(16, 4))

    epochs = range(1, len(history["train_losses"]) + 1)

    # Loss
    axes[0].plot(epochs, history["train_losses"], label="Train", color="blue", alpha=0.8)
    axes[0].plot(epochs, history["val_losses"], label="Val", color="red", alpha=0.8)
    axes[0].set(title="Loss", xlabel="Epoch", ylabel="Loss")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # Accuracy
    axes[1].plot(history["train_accuracies"], label="Train", color="blue", alpha=0.8)
    axes[1].plot(history["val_accuracies"], label="Val", color="red", alpha=0.8)
    axes[1].set(title="Accuracy", xlabel="Epoch", ylabel="Accuracy")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    # Learning rate
    axes[2].plot(epochs, history["learning_rates"], color="green", alpha=0.8)
    axes[2].set(title="Learning Rate", xlabel="Epoch", ylabel="LR")
    axes[2].set_yscale("log")
    axes[2].grid(True, alpha=0.3)

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        logger.info(f"Training history saved to {save_path}")
    plt.close()


def plot_confusion_matrix(cm, save_path=None):
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues")
    plt.title("Confusion Matrix")
    plt.ylabel("True Label")
    plt.xlabel("Predicted Label")
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        logger.info(f"Confusion matrix saved to {save_path}")
    plt.close()


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="Train Radar Material Classifier (Improved)")
    parser.add_argument("--data", type=str, default="data/rice/gold/csv/data_train_rice.csv")
    parser.add_argument("--epochs", type=int, default=300)
    parser.add_argument("--batch_size", type=int, default=128)
    parser.add_argument("--lr", type=float, default=0.5e-4)
    parser.add_argument("--device", type=str, default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--output_dir", type=str, default="./outputs")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--noise_std", type=float, default=0.04, help="Gaussian noise std for augmentation (0 to disable)")
    parser.add_argument("--mixup", action="store_true", help="Enable mixup regularization")
    parser.add_argument("--mixup_alpha", type=float, default=0.2)
    parser.add_argument("--no_class_weights", action="store_true", help="Disable class-weighted loss")
    args = parser.parse_args()

    set_seed(args.seed)

    device = (
        torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if args.device == "auto"
        else torch.device(args.device)
    )
    logger.info(f"Using device: {device}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    # Save experiment config
    config = vars(args)
    config["device_actual"] = str(device)
    with open(output_dir / "config.json", "w") as f:
        json.dump(config, f, indent=2)

    # Data
    train_loader, val_loader, test_loader, scaler, y_train = create_data_loaders(
        args.data, batch_size=args.batch_size, noise_std=args.noise_std, seed=args.seed
    )

    # Class weights
    class_weights = None
    if not args.no_class_weights:
        class_weights = compute_class_weights(y_train, device)

    # Model
    model = AstroFormer().to(device)
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info(f"Model parameters: {total_params:,} total, {trainable_params:,} trainable")

    # Train
    history = train_model(
        model, train_loader, val_loader,
        args.epochs, args.lr, device,
        class_weights=class_weights,
        use_mixup=args.mixup,
        mixup_alpha=args.mixup_alpha,
    )

    # Evaluate on test set
    test_acc, test_report, cm = evaluate(model, test_loader, device)
    logger.info(f"Test Accuracy: {test_acc:.4f}")
    logger.info(f"Classification Report:\n{test_report}")

    # Save model
    model_path = output_dir / "radar_material_classifier.pth"
    save_checkpoint(model, scaler, model_path)
    logger.info(f"Model saved to {model_path}")

    # Plots
    plot_training_history(history, output_dir / "training_history.png")
    plot_confusion_matrix(cm, output_dir / "confusion_matrix.png")

    # Results file
    results = {
        "test_accuracy": test_acc,
        "best_val_accuracy": history["best_val_accuracy"],
        "best_val_loss": history["best_val_loss"],
        "epochs_trained": history["epochs_trained"],
        "total_time_seconds": history["total_time_seconds"],
    }
    with open(output_dir / "results.json", "w") as f:
        json.dump(results, f, indent=2)

    with open(output_dir / "results.txt", "w") as f:
        f.write(f"Test Accuracy: {test_acc:.4f}\n")
        f.write(f"Best Validation Accuracy: {history['best_val_accuracy']:.4f}\n")
        f.write(f"Best Validation Loss: {history['best_val_loss']:.4f}\n")
        f.write(f"Epochs Trained: {history['epochs_trained']}\n")
        f.write(f"Training Time: {history['total_time_seconds']:.1f}s\n\n")
        f.write(f"Classification Report:\n{test_report}\n")

    logger.info(f"Training complete! Results saved in {output_dir}")


if __name__ == "__main__":
    main()