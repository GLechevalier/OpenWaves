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
HIDDEN1_SIZE = 128
HIDDEN2_SIZE = 64
HIDDEN3_SIZE = 32
NUM_CLASSES = 2
DROPOUT_RATE = 0.5
OUTLIER_THRESHOLD = 1e11


# ============================================================
# Model
# ============================================================
class RobustModel(nn.Module):
    """
    Neural Network for multi-class radar material classification.

    Architecture:
        Input (5120) -> BatchNorm -> Dense(128) -> BN -> ReLU -> Dropout(0.5)
                     -> Dense(64)  -> BN -> ReLU -> Dropout(0.5)
                     -> Dense(32)  -> BN -> ReLU -> Dropout(0.3)
                     -> Dense(num_classes)

    Key changes vs. original:
        - Added aggressive Dropout after every hidden layer to fight overfitting
        - Removed learnable bias-add parameters (unnecessary extra capacity)
        - Added a third hidden layer with lighter dropout for smoother feature compression
        - Wider first layer (128) to give the model room to learn before dropout kills neurons
    """

    def __init__(
        self,
        input_size=INPUT_SIZE,
        hidden1_size=HIDDEN1_SIZE,
        hidden2_size=HIDDEN2_SIZE,
        hidden3_size=HIDDEN3_SIZE,
        num_classes=NUM_CLASSES,
        dropout_rate=DROPOUT_RATE,
    ):
        super().__init__()

        self.bn_input = nn.BatchNorm1d(input_size)

        self.fc1 = nn.Linear(input_size, hidden1_size)
        self.bn1 = nn.BatchNorm1d(hidden1_size)
        self.drop1 = nn.Dropout(dropout_rate)

        self.fc2 = nn.Linear(hidden1_size, hidden2_size)
        self.bn2 = nn.BatchNorm1d(hidden2_size)
        self.drop2 = nn.Dropout(dropout_rate)

        self.fc3 = nn.Linear(hidden2_size, hidden3_size)
        self.bn3 = nn.BatchNorm1d(hidden3_size)
        self.drop3 = nn.Dropout(dropout_rate * 0.6)  # lighter dropout before output

        self.fc_out = nn.Linear(hidden3_size, num_classes)

        self._init_weights()

    def _init_weights(self):
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.kaiming_normal_(module.weight, nonlinearity="relu")
                nn.init.constant_(module.bias, 0.0)

    def forward(self, x):
        x = self.bn_input(x)

        x = self.fc1(x)
        x = self.bn1(x)
        x = F.relu(x)
        x = self.drop1(x)

        x = self.fc2(x)
        x = self.bn2(x)
        x = F.relu(x)
        x = self.drop2(x)

        x = self.fc3(x)
        x = self.bn3(x)
        x = F.relu(x)
        x = self.drop3(x)

        x = self.fc_out(x)
        return x  # (batch_size, num_classes)


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
                "hidden3_size": HIDDEN3_SIZE,
                "num_classes": NUM_CLASSES,
                "dropout_rate": DROPOUT_RATE,
            },
        },
        filepath,
    )

    scaler_path = filepath.parent / "scaler.pkl"
    joblib.dump(scaler, scaler_path)

    return filepath, scaler_path


def load_checkpoint(filepath, device="cpu"):
    """Load model from checkpoint. Returns (model, architecture_dict)."""
    checkpoint = torch.load(filepath, map_location=device, weights_only=False)
    arch = checkpoint["model_architecture"]

    model = RobustModel(
        input_size=arch["input_size"],
        hidden1_size=arch["hidden1_size"],
        hidden2_size=arch["hidden2_size"],
        hidden3_size=arch["hidden3_size"],
        num_classes=arch["num_classes"],
        dropout_rate=arch.get("dropout_rate", DROPOUT_RATE),
    ).to(device)

    model.load_state_dict(checkpoint["model_state_dict"])
    return model, arch