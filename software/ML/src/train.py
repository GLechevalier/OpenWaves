#!/usr/bin/env python3
"""
Radar Material Classification - Training Script

Usage:
    python train.py --data data_rice.csv --epochs 100 --lr 1e-4
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import pandas as pd
import numpy as np
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import argparse
import logging


import sys
import os

sys.path.append(os.getcwd())


from src.models import (
    ConvNeXtT,
)

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Model chose : 
model = ConvNeXtT

# ============================================================
# Dataset
# ============================================================
class SimpleDataset(Dataset):
    def __init__(self, features, targets):
        self.features = features.astype(np.float32)
        self.targets = targets

    def __len__(self):
        return len(self.features)

    def __getitem__(self, idx):
        return torch.tensor(self.features[idx]), torch.tensor(self.targets[idx])


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

    outliers_mask = np.abs(features) > model.consts["OUTLIER_THRESHOLD"]
    outliers_count = outliers_mask.sum()
    if outliers_count > 0:
        logger.warning(
            f"Found {outliers_count} outlier values (|x| > {model.consts["OUTLIER_THRESHOLD"]:.0e}) — replacing with 0"
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


def create_data_loaders(csv_file, train_ratio=0.7, val_ratio=0.15, test_ratio=0.15, batch_size=32):
    """
    Create train / val / test DataLoaders with StandardScaler fitted on training data only.
    """
    assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-6, "Ratios must sum to 1.0"

    # Load raw data
    data = pd.read_csv(csv_file)
    feature_cols = [f"{i}" for i in range(model.consts["INPUT_SIZE"])]
    features = data[feature_cols].values.astype(np.float32)
    targets = data["classification"].values.astype(np.int64)

    # Clean
    features = clean_features(features)
    log_class_distribution(targets, label="Full dataset")

    # Shuffle and split indices
    indices = np.arange(len(features))
    np.random.shuffle(indices)

    train_end = int(train_ratio * len(features))
    val_end = train_end + int(val_ratio * len(features))

    train_idx = indices[:train_end]
    val_idx = indices[train_end:val_end]
    test_idx = indices[val_end:]

    X_train, y_train = features[train_idx], targets[train_idx]
    X_val, y_val = features[val_idx], targets[val_idx]
    X_test, y_test = features[test_idx], targets[test_idx]

    # Fit scaler on training data only
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_val = scaler.transform(X_val)
    X_test = scaler.transform(X_test)

    logger.info(f"Split — Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")

    train_loader = DataLoader(SimpleDataset(X_train, y_train), batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(SimpleDataset(X_val, y_val), batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(SimpleDataset(X_test, y_test), batch_size=batch_size, shuffle=False)

    return train_loader, val_loader, test_loader, scaler


# ============================================================
# Training / Validation
# ============================================================
def train_epoch(model, loader, criterion, optimizer, device):
    model.train()
    total_loss, correct, total = 0.0, 0, 0

    for features, targets in loader:
        features, targets = features.to(device), targets.to(device)

        optimizer.zero_grad()
        outputs = model(features)
        loss = criterion(outputs, targets)

        if torch.isnan(loss):
            raise ValueError("NaN loss detected during training!")

        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()

        total_loss += loss.item()
        _, predicted = torch.max(outputs, 1)
        correct += (predicted == targets).sum().item()
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


def train_model(model, train_loader, val_loader, num_epochs, learning_rate, device):
    """Full training loop with early stopping and LR scheduling."""
    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    optimizer = optim.Adam(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, "min", patience=10, factor=0.5)

    # Initial eval
    train_acc_init, _, _ = evaluate(model, train_loader, device)
    val_acc_init, _, _ = evaluate(model, val_loader, device)

    history = {
        "train_losses": [],
        "val_losses": [],
        "train_accuracies": [train_acc_init],
        "val_accuracies": [val_acc_init],
    }

    best_val_acc = 0.0
    best_state = None
    patience_counter = 0
    early_stop_patience = 20

    logger.info(f"Training for {num_epochs} epochs on {device}")
    logger.info(f"Initial — Train Acc: {train_acc_init:.4f}, Val Acc: {val_acc_init:.4f}")

    for epoch in range(num_epochs):
        train_loss, train_acc = train_epoch(model, train_loader, criterion, optimizer, device)
        val_loss, val_acc = validate_epoch(model, val_loader, criterion, device)
        scheduler.step(val_loss)

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            patience_counter = 0
        else:
            patience_counter += 1

        history["train_losses"].append(train_loss)
        history["val_losses"].append(val_loss)
        history["train_accuracies"].append(train_acc)
        history["val_accuracies"].append(val_acc)

        if (epoch + 1) % 10 == 0:
            lr = optimizer.param_groups[0]["lr"]
            logger.info(
                f"Epoch [{epoch+1}/{num_epochs}] "
                f"Train Loss: {train_loss:.4f} Acc: {train_acc:.4f} | "
                f"Val Loss: {val_loss:.4f} Acc: {val_acc:.4f} | "
                f"Best: {best_val_acc:.4f} | LR: {lr:.6f}"
            )

        if patience_counter >= early_stop_patience:
            logger.info(f"Early stopping at epoch {epoch + 1}")
            break

    if best_state is not None:
        model.load_state_dict(best_state)

    history["best_val_accuracy"] = best_val_acc
    return history


# ============================================================
# Plotting
# ============================================================
def plot_training_history(history, save_path=None):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

    epochs = range(1, len(history["train_losses"]) + 1)
    ax1.plot(epochs, history["train_losses"], label="Train", color="blue")
    ax1.plot(epochs, history["val_losses"], label="Val", color="red")
    ax1.set(title="Loss", xlabel="Epoch", ylabel="Loss")
    ax1.legend()
    ax1.grid(True)

    ax2.plot(history["train_accuracies"], label="Train", color="blue")
    ax2.plot(history["val_accuracies"], label="Val", color="red")
    ax2.set(title="Accuracy", xlabel="Epoch", ylabel="Accuracy")
    ax2.legend()
    ax2.grid(True)

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        logger.info(f"Training history saved to {save_path}")
    plt.show()


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
    plt.show()


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="Train Radar Material Classifier")
    parser.add_argument("--data", type=str, default="data/rice/gold/csv/data_train_rice.csv", help="Path to CSV data file")
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--batch_size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=0.1e-4)
    parser.add_argument("--device", type=str, default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--output_dir", type=str, default="./outputs")
    args = parser.parse_args()

    device = (
        torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if args.device == "auto"
        else torch.device(args.device)
    )
    logger.info(f"Using device: {device}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    # Data
    train_loader, val_loader, test_loader, scaler = create_data_loaders(
        args.data, batch_size=args.batch_size
    )

    # Model
    model = ConvNeXtT().to(device)
    total_params = sum(p.numel() for p in model.parameters())
    logger.info(f"Model parameters: {total_params}")

    # Train
    history = train_model(model, train_loader, val_loader, args.epochs, args.lr, device)

    # Evaluate on test set
    test_acc, test_report, cm = evaluate(model, test_loader, device)
    logger.info(f"Test Accuracy: {test_acc:.4f}")
    logger.info(f"Classification Report:\n{test_report}")

    # Save
    model_path = output_dir / "radar_material_classifier.pth"
    ConvNeXtT.save_checkpoint(model=model, filepath=model_path, scaler=scaler)
    logger.info(f"Model saved to {model_path}")

    # Plots
    plot_training_history(history, output_dir / "training_history.png")
    plot_confusion_matrix(cm, output_dir / "confusion_matrix.png")

    # Results file
    with open(output_dir / "results.txt", "w") as f:
        f.write(f"Test Accuracy: {test_acc:.4f}\n")
        f.write(f"Best Validation Accuracy: {history['best_val_accuracy']:.4f}\n\n")
        f.write(f"Classification Report:\n{test_report}\n")

    logger.info(f"Training complete! Results saved in {output_dir}")


if __name__ == "__main__":
    main()
    # filepath="outputs/radar_material_classifier.pth"
    # checkpoint = torch.load(filepath, map_location="cuda", weights_only=False)
    # model_class = checkpoint["model_class"]
    # arch = checkpoint["model_architecture"]
    # print(model_class)
    # print(arch)
