#!/usr/bin/env python3
"""
Radar Material Classification - Main Entry Point

Orchestrates training on data_rice.csv and evaluation on data_test_rice.csv.

Usage:
    python main.py
    python main.py --epochs 200 --lr 5e-4 --batch_size 64
    python main.py --skip_train --model ./outputs/radar_material_classifier.pth
"""

import argparse
import logging
from pathlib import Path

import torch

import sys
import os

sys.path.append(os.getcwd())

from software.material_classification.ML.src.models import ConvNeXtT
from software.material_classification.ML.src.train import create_data_loaders, train_model, evaluate, plot_training_history, plot_confusion_matrix
from software.material_classification.ML.src.evaluate import evaluate_model, plot_per_class_accuracy, TestDataset

import numpy as np
import pandas as pd
import joblib
from torch.utils.data import DataLoader
from software.material_classification.ML.src.models.model import INPUT_SIZE, OUTLIER_THRESHOLD

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

ModelClass = ConvNeXtT

def main():
    parser = argparse.ArgumentParser(description="Radar Material Classification — Train & Evaluate")
    # Data
    parser.add_argument("--train_data", type=str, default="data/rice/gold/csv/data_train_rice.csv", help="Training CSV file")
    parser.add_argument("--test_data", type=str, default="data/rice/gold/csv/data_test_rice.csv", help="Test CSV file")
    # Training
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-5)
    # Paths
    parser.add_argument("--output_dir", type=str, default="./outputs")
    parser.add_argument("--eval_dir", type=str, default="./eval_results")
    # Options
    parser.add_argument("--device", type=str, default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--skip_train", action="store_true", help="Skip training, only evaluate")
    parser.add_argument("--model", type=str, default=None, help="Path to pretrained model (used with --skip_train)")
    args = parser.parse_args()

    # Device
    device = (
        torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if args.device == "auto"
        else torch.device(args.device)
    )
    logger.info(f"Using device: {device}")

    output_dir = Path(args.output_dir)
    eval_dir = Path(args.eval_dir)
    output_dir.mkdir(exist_ok=True)
    eval_dir.mkdir(exist_ok=True)

    model_path = output_dir / "radar_material_classifier.pth"
    scaler_path = output_dir / "scaler.pkl"

    # ==================================================================
    # PHASE 1 — TRAINING
    # ==================================================================
    if not args.skip_train:
        logger.info("=" * 60)
        logger.info("PHASE 1: TRAINING on %s", args.train_data)
        logger.info("=" * 60)

        train_loader, val_loader, test_loader, scaler = create_data_loaders(
            args.train_data, batch_size=args.batch_size
        )

        model = ModelClass().to(device)
        total_params = sum(p.numel() for p in model.parameters())
        logger.info(f"Model parameters: {total_params}")

        history = train_model(model, train_loader, val_loader, args.epochs, args.lr, device)

        # Evaluate on the train-split test set
        test_acc, test_report, cm = evaluate(model, test_loader, device)
        logger.info(f"Train-split test accuracy: {test_acc:.4f}")
        logger.info(f"Classification Report:\n{test_report}")

        # Save model + scaler
        ModelClass.save_checkpoint(model=model, scaler=scaler, filepath=model_path)
        logger.info(f"Model saved to {model_path}")

        # Plots
        plot_training_history(history, output_dir / "training_history.png")
        plot_confusion_matrix(cm, output_dir / "confusion_matrix_train_split.png")

        # Results file
        with open(output_dir / "results.txt", "w") as f:
            f.write(f"Test Accuracy (train split): {test_acc:.4f}\n")
            f.write(f"Best Validation Accuracy: {history['best_val_accuracy']:.4f}\n\n")
            f.write(f"Classification Report:\n{test_report}\n")
    else:
        logger.info("Skipping training (--skip_train)")
        if args.model:
            model_path = Path(args.model)
            scaler_path = model_path.parent / "scaler.pkl"

    # ==================================================================
    # PHASE 2 — EVALUATION on external test set
    # ==================================================================
    logger.info("=" * 60)
    logger.info("PHASE 2: EVALUATION on %s", args.test_data)
    logger.info("=" * 60)

    # Load model
    model, arch = ModelClass.load_checkpoint(model_path, device)
    logger.info(f"Model loaded — architecture: {arch}")

    # Load scaler
    scaler = joblib.load(scaler_path)

    # Load and preprocess test data
    data = pd.read_csv(args.test_data)
    feature_cols = [f"{i}" for i in range(INPUT_SIZE)]
    features = data[feature_cols].values.astype(np.float32)
    targets = data["classification"].values.astype(np.int64)

    # Clean
    features = np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)
    features[np.abs(features) > OUTLIER_THRESHOLD] = 0.0

    # Scale
    features_scaled = scaler.transform(features)

    # Log distribution
    unique, counts = np.unique(targets, return_counts=True)
    logger.info(f"External test set: {len(features)} samples")
    for cls, count in zip(unique, counts):
        logger.info(f"  Class {cls}: {count} ({100 * count / len(targets):.1f}%)")

    # Evaluate
    test_loader = DataLoader(TestDataset(features_scaled, targets), batch_size=args.batch_size, shuffle=False)
    accuracy, report, cm, all_targets, all_preds, all_probs = evaluate_model(model, test_loader, device)

    # Print
    print("\n" + "=" * 60)
    print("EXTERNAL TEST SET RESULTS")
    print("=" * 60)
    print(f"\nAccuracy: {accuracy:.4f} ({accuracy:.2%})")
    print(f"\nClassification Report:\n{report}")
    print(f"Confusion Matrix:\n{cm}")

    per_class_acc = cm.diagonal() / cm.sum(axis=1).clip(min=1)
    for i, acc in enumerate(per_class_acc):
        print(f"  Class {i}: {acc:.4f} ({acc:.2%})")
    print("=" * 60)

    # Save
    with open(eval_dir / "evaluation_results.txt", "w") as f:
        f.write(f"Model: {model_path}\nTest Data: {args.test_data}\nDevice: {device}\n")
        f.write(f"Samples: {len(features)}\n\n")
        f.write(f"Accuracy: {accuracy:.4f} ({accuracy:.2%})\n\n")
        f.write(f"Classification Report:\n{report}\n\nConfusion Matrix:\n{cm}\n\n")
        f.write("Per-class accuracy:\n")
        for i, acc in enumerate(per_class_acc):
            f.write(f"  Class {i}: {acc:.4f}\n")

    # Predictions CSV
    predictions_df = pd.DataFrame(
        {"true_label": all_targets, "predicted_label": all_preds, "correct": all_targets == all_preds}
    )
    for c in range(all_probs.shape[1]):
        predictions_df[f"prob_class_{c}"] = all_probs[:, c]
    predictions_df.to_csv(eval_dir / "predictions.csv", index=False)

    # Plots
    plot_confusion_matrix(cm, eval_dir / "confusion_matrix_test.png")
    plot_per_class_accuracy(cm, eval_dir / "per_class_accuracy.png")

    logger.info(f"All done! Training results in {output_dir}, evaluation results in {eval_dir}")


if __name__ == "__main__":
    main()