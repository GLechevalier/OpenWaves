#!/usr/bin/env python3
"""
Radar Material Classification - Model Architecture

Single source of truth for the neural network architecture.
Both training and evaluation scripts import from here.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

# ============================================================
# Constants
# ============================================================
INPUT_SIZE = 5120
HIDDEN1_SIZE = 64
HIDDEN2_SIZE = 32
NUM_CLASSES = 2  # Update this to match your actual number of classes
OUTLIER_THRESHOLD = 1e11

BASE_MODEL_CONSTS = {
    "INPUT_SIZE":INPUT_SIZE,
    "HIDDEN1_SIZE":HIDDEN1_SIZE,
    "HIDDEN2_SIZE":HIDDEN2_SIZE,
    "NUM_CLASSES":NUM_CLASSES,
    "OUTLIER_THRESHOLD":OUTLIER_THRESHOLD
}

# ============================================================
# Model
# ============================================================
class BaseModel(nn.Module):
    """
    Neural Network for multi-class radar material classification.

    Architecture:
        Input (5120) -> BatchNorm -> Dense(64) + ReLU -> Dense(32) + ReLU -> Dense(num_classes)
    """
    consts = BASE_MODEL_CONSTS

    def __init__(
        self,
        input_size=INPUT_SIZE,
        hidden1_size=HIDDEN1_SIZE,
        hidden2_size=HIDDEN2_SIZE,
        num_classes=NUM_CLASSES,
    ):
        super().__init__()

        # Input normalization / bias layer
        self.input_bias = nn.Parameter(torch.randn(input_size) * 0.1)

        self.bn_input = nn.BatchNorm1d(input_size)
        self.bn2 = nn.BatchNorm1d(hidden1_size)
        self.bn3 = nn.BatchNorm1d(hidden2_size)

        # Hidden layers
        self.fc1 = nn.Linear(input_size, hidden1_size)
        self.fc1_bias_add = nn.Parameter(torch.randn(hidden1_size) * 0.1)

        self.fc2 = nn.Linear(hidden1_size, hidden2_size)
        self.fc2_bias_add = nn.Parameter(torch.randn(hidden2_size) * 0.1)

        # Output layer (no activation — CrossEntropyLoss applies softmax internally)
        if num_classes==2:
            self.fc3 = nn.Linear(hidden2_size, 1)
        else:
            self.fc3 = nn.Linear(hidden2_size, num_classes)

        self._init_weights()

    def _init_weights(self):
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                nn.init.constant_(module.bias, 0.0)

    def forward(self, x):
        x = self.bn_input(x)
        x = x + self.input_bias

        x = self.fc1(x)
        x = self.bn2(x)
        x = F.relu(x)
        x = x + self.fc1_bias_add

        x = self.fc2(x)
        x = self.bn3(x)
        x = F.relu(x)
        x = x + self.fc2_bias_add

        x = self.fc3(x)
        return x  # (batch_size, num_classes)

    @staticmethod
    def save_checkpoint(model, scaler, filepath):
        """Save model checkpoint with architecture metadata and scaler."""
        import joblib

        torch.save(
            {
                "model_state_dict": model.state_dict(),
                "model_class":type(model).__name__,
                "model_architecture": {
                    "input_size": INPUT_SIZE,
                    "hidden1_size": HIDDEN1_SIZE,
                    "hidden2_size": HIDDEN2_SIZE,
                    "num_classes": NUM_CLASSES,
                },
            },
            filepath,
        )

        scaler_path = filepath.parent / "scaler.pkl"
        joblib.dump(scaler, scaler_path)

        return filepath, scaler_path

    @staticmethod
    def load_checkpoint(filepath, device="cpu"):
        """Load model from checkpoint. Returns (model, architecture_dict)."""
        checkpoint = torch.load(filepath, map_location=device, weights_only=False)
        arch = checkpoint["model_architecture"]

        model = BaseModel(
            input_size=arch["input_size"],
            hidden1_size=arch["hidden1_size"],
            hidden2_size=arch["hidden2_size"],
            num_classes=arch["num_classes"],
        ).to(device)

        model.load_state_dict(checkpoint["model_state_dict"])
        return model, arch