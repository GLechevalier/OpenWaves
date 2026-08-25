#!/usr/bin/env python3
"""
Radar Material Classification - Evaluation Script

Evaluates a pre-trained model on a new test dataset.

Usage:
    python evaluate.py --data data_test_rice.csv --model ./outputs/radar_material_classifier.pth
"""

import torch
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import pandas as pd
import numpy as np
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import argparse
import logging
import joblib

import sys
import os

sys.path.append(os.getcwd())

from src.models import BaseModel

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

ModelClass = BaseModel
INPUT_SIZE = 5120
OUTLIER_THRESHOLD = 1e11
NUM_CLASSES = 2

# ============================================================
# Dataset
# ============================================================
class TestDataset(Dataset):
    def __init__(self, features, targets):
        self.features = features.astype(np.float32)
        self.targets = targets

    def __len__(self):
        return len(self.features)

    def __getitem__(self, idx):
        return torch.tensor(self.features[idx]), torch.tensor(self.targets[idx])


# ============================================================
# Evaluation
# ============================================================
def evaluate_model(model, loader, device):
    """Run inference, return metrics and per-sample probabilities."""
    model.eval()
    all_preds, all_targets, all_probs = [], [], []

    with torch.no_grad():
        for features, targets in loader:
            features = features.to(device)
            outputs = model(features)
            probs = F.softmax(outputs, dim=1)
            _, predicted = torch.max(outputs, 1)

            all_preds.extend(predicted.cpu().numpy())
            all_targets.extend(targets.numpy())
            all_probs.extend(probs.cpu().numpy())

    all_targets = np.array(all_targets)
    all_preds = np.array(all_preds)
    all_probs = np.array(all_probs)

    accuracy = accuracy_score(all_targets, all_preds)
    report = classification_report(all_targets, all_preds, zero_division=0)
    cm = confusion_matrix(all_targets, all_preds)

    return accuracy, report, cm, all_targets, all_preds, all_probs

def evaluate_binary(model, loader, device):
    """Run inference, return metrics and per-sample probabilities."""
    model.eval()
    all_preds, all_targets, all_probs = [], [], []

    with torch.no_grad():
        for features, targets in loader:
            features = features.to(device)
            outputs = model(features).squeeze(1)
            predicted = (torch.sigmoid(outputs) > 0.5).long()

            all_preds.extend(predicted.cpu().numpy())
            all_targets.extend(targets.numpy())

    all_targets = np.array(all_targets)
    all_preds = np.array(all_preds)

    accuracy = accuracy_score(all_targets, all_preds)
    report = classification_report(all_targets, all_preds, zero_division=0)
    cm = confusion_matrix(all_targets, all_preds)

    return accuracy, report, cm, all_targets, all_preds


# ============================================================
# Plotting
# ============================================================
def plot_confusion_matrix(cm, save_path=None):
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues")
    plt.title("Confusion Matrix — Test Set")
    plt.ylabel("True Label")
    plt.xlabel("Predicted Label")
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        logger.info(f"Confusion matrix saved to {save_path}")
    plt.show()


def plot_per_class_accuracy(cm, save_path=None):
    per_class_acc = cm.diagonal() / cm.sum(axis=1).clip(min=1)
    classes = list(range(len(per_class_acc)))

    plt.figure(figsize=(8, 5))
    bars = plt.bar(classes, per_class_acc, color="steelblue", edgecolor="black")
    for bar, acc in zip(bars, per_class_acc):
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.01,
            f"{acc:.2%}",
            ha="center",
            va="bottom",
        )
    plt.xlabel("Class")
    plt.ylabel("Accuracy")
    plt.title("Per-Class Accuracy")
    plt.ylim(0, 1.1)
    plt.xticks(classes)
    plt.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        logger.info(f"Per-class accuracy saved to {save_path}")
    plt.show()


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="Evaluate Radar Material Classifier")
    parser.add_argument("--data", type=str, default="data/rice/gold/csv/data_test_rice.csv", help="Path to test CSV")
    parser.add_argument("--model", type=str, default="./outputs/radar_material_classifier.pth")
    parser.add_argument("--scaler", type=str, default="./outputs/scaler.pkl")
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--device", type=str, default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--output_dir", type=str, default="./eval_results")
    args = parser.parse_args()

    device = (
        torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if args.device == "auto"
        else torch.device(args.device)
    )
    logger.info(f"Using device: {device}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    # ---- Load model (architecture read from checkpoint) ----
    logger.info(f"Loading model from {args.model}")
    model, arch = ModelClass.load_checkpoint(filepath=args.model, device=device)
    logger.info(f"Model loaded — architecture: {arch}")

    # ---- Load scaler ----
    logger.info(f"Loading scaler from {args.scaler}")
    scaler = joblib.load(args.scaler)

    # ---- Load & preprocess test data ----
    logger.info(f"Loading test data from {args.data}")
    data = pd.read_csv(args.data)
    feature_cols = [f"{i}" for i in range(INPUT_SIZE)]
    features = data[feature_cols].values.astype(np.float32)
    targets = data["classification"].values.astype(np.int64)

    # Clean
    nan_count = np.isnan(features).sum()
    inf_count = np.isinf(features).sum()
    if nan_count > 0 or inf_count > 0:
        logger.warning(f"Found {nan_count} NaN and {inf_count} Inf — replacing with 0")
        features = np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)

    outliers_mask = np.abs(features) > OUTLIER_THRESHOLD
    if outliers_mask.sum() > 0:
        logger.warning(f"Clipping {outliers_mask.sum()} outlier values")
        features[outliers_mask] = 0.0

    # Scale
    features_scaled = scaler.transform(features)

    # Log class distribution
    unique, counts = np.unique(targets, return_counts=True)
    logger.info(f"Test set: {len(features)} samples")
    for cls, count in zip(unique, counts):
        logger.info(f"  Class {cls}: {count} ({100 * count / len(targets):.1f}%)")

    # ---- Evaluate ----
    test_loader = DataLoader(TestDataset(features_scaled, targets), batch_size=args.batch_size, shuffle=False)
    if NUM_CLASSES>2:
        accuracy, report, cm, all_targets, all_preds, all_probs = evaluate_model(model, test_loader, device)
    else:
        accuracy, report, cm, all_targets, all_preds = evaluate_binary(model, test_loader, device)

    # ---- Print results ----
    print("\n" + "=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)
    print(f"\nOverall Test Accuracy: {accuracy:.4f} ({accuracy:.2%})")
    print(f"\nClassification Report:\n{report}")
    print(f"Confusion Matrix:\n{cm}")

    per_class_acc = cm.diagonal() / cm.sum(axis=1).clip(min=1)
    for i, acc in enumerate(per_class_acc):
        print(f"  Class {i}: {acc:.4f} ({acc:.2%})")
    print("=" * 60)

    # ---- Save results ----
    with open(output_dir / "evaluation_results.txt", "w") as f:
        f.write(f"Model: {args.model}\nTest Data: {args.data}\nDevice: {device}\n")
        f.write(f"Samples: {len(features)}\n\n")
        f.write(f"Overall Accuracy: {accuracy:.4f} ({accuracy:.2%})\n\n")
        f.write(f"Classification Report:\n{report}\n\n")
        f.write(f"Confusion Matrix:\n{cm}\n\n")
        f.write("Per-class accuracy:\n")
        for i, acc in enumerate(per_class_acc):
            f.write(f"  Class {i}: {acc:.4f}\n")

    # Save predictions CSV
    predictions_df = pd.DataFrame(
        {"true_label": all_targets, "predicted_label": all_preds, "correct": all_targets == all_preds}
    )
    if NUM_CLASSES>2:
        for c in range(all_probs.shape[1]):
            predictions_df[f"prob_class_{c}"] = all_probs[:, c]
    predictions_df.to_csv(output_dir / "predictions.csv", index=False)

    # Plots
    plot_confusion_matrix(cm, output_dir / "confusion_matrix_test.png")
    plot_per_class_accuracy(cm, output_dir / "per_class_accuracy.png")

    logger.info(f"Evaluation complete! Results saved in {output_dir}")


if __name__ == "__main__":
    main()