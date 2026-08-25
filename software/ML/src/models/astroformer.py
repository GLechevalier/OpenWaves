#!/usr/bin/env python3
"""
Radar Material Classification - Attention-based Model Architecture

Inspired by Astroformer (Dagli, ICLR 2023): hybrid transformer-convolutional
architecture designed for low-data regime classification.

Adapted from 2D image classification to 1D radar signal classification.
Key borrowed ideas:
  - Conv stem for local feature extraction (translational equivariance)
  - Squeeze-Excitation blocks for channel attention
  - Multi-head Self-Attention with relative positional bias
  - Hybrid C-C-T-T stack ordering (conv early, attention late)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import math

# ============================================================
# Constants
# ============================================================
INPUT_SIZE = 5120
NUM_CLASSES = 2
DROPOUT_RATE = 0.3
OUTLIER_THRESHOLD = 1e11


# ============================================================
# Building Blocks
# ============================================================
class SqueezeExcitation1D(nn.Module):
    """
    Channel attention mechanism (Hu et al., 2018).
    Used in Astroformer's inverted residual blocks.
    Learns to re-weight channels based on global signal statistics.
    """

    def __init__(self, channels, reduction=4):
        super().__init__()
        mid = max(channels // reduction, 8)
        self.pool = nn.AdaptiveAvgPool1d(1)
        self.fc = nn.Sequential(
            nn.Linear(channels, mid),
            nn.ReLU(inplace=True),
            nn.Linear(mid, channels),
            nn.Sigmoid(),
        )

    def forward(self, x):
        # x: (B, C, L)
        b, c, _ = x.shape
        w = self.pool(x).view(b, c)
        w = self.fc(w).view(b, c, 1)
        return x * w


class ConvBlock1D(nn.Module):
    """
    1D convolutional block with inverted residual structure + SE attention.
    Mirrors the C-stages of Astroformer / CoAtNet.
    
    Inverted residual: expand channels -> depthwise conv -> SE -> project back
    """

    def __init__(self, channels, expand_ratio=2, kernel_size=7, dropout=0.1):
        super().__init__()
        mid = channels * expand_ratio
        self.block = nn.Sequential(
            # Pointwise expansion
            nn.Conv1d(channels, mid, 1, bias=False),
            nn.BatchNorm1d(mid),
            nn.GELU(),
            # Depthwise convolution (local feature extraction)
            nn.Conv1d(mid, mid, kernel_size, padding=kernel_size // 2, groups=mid, bias=False),
            nn.BatchNorm1d(mid),
            nn.GELU(),
            # Squeeze-Excitation
            SqueezeExcitation1D(mid),
            # Pointwise projection
            nn.Conv1d(mid, channels, 1, bias=False),
            nn.BatchNorm1d(channels),
            nn.Dropout(dropout),
        )

    def forward(self, x):
        return x + self.block(x)  # residual connection


class RelativeMultiHeadAttention1D(nn.Module):
    """
    Multi-head self-attention with learnable relative positional bias.
    
    Astroformer's key contribution: relative attention preserves translational
    equivariance (Theorem 1 in the paper), making the attention layer
    compatible with the conv layers' inductive bias.
    """

    def __init__(self, dim, num_heads=4, dropout=0.1, max_len=512):
        super().__init__()
        self.num_heads = num_heads
        self.head_dim = dim // num_heads
        self.scale = self.head_dim ** -0.5

        self.qkv = nn.Linear(dim, dim * 3, bias=False)
        self.proj = nn.Linear(dim, dim)
        self.attn_drop = nn.Dropout(dropout)
        self.proj_drop = nn.Dropout(dropout)

        # Learnable relative positional bias (Astroformer-style)
        self.rel_pos_bias = nn.Parameter(torch.zeros(num_heads, 2 * max_len - 1))
        nn.init.trunc_normal_(self.rel_pos_bias, std=0.02)
        self.max_len = max_len

    def _get_rel_pos(self, seq_len):
        """Build relative position bias matrix from the parameter table."""
        coords = torch.arange(seq_len, device=self.rel_pos_bias.device)
        relative = coords.unsqueeze(0) - coords.unsqueeze(1)  # (L, L)
        relative = relative + self.max_len - 1  # shift to positive indices
        return self.rel_pos_bias[:, relative]  # (heads, L, L)

    def forward(self, x):
        B, L, C = x.shape
        qkv = self.qkv(x).reshape(B, L, 3, self.num_heads, self.head_dim)
        qkv = qkv.permute(2, 0, 3, 1, 4)  # (3, B, heads, L, head_dim)
        q, k, v = qkv.unbind(0)

        attn = (q @ k.transpose(-2, -1)) * self.scale

        # Add relative positional bias
        if L <= self.max_len:
            attn = attn + self._get_rel_pos(L).unsqueeze(0)

        attn = attn.softmax(dim=-1)
        attn = self.attn_drop(attn)

        x = (attn @ v).transpose(1, 2).reshape(B, L, C)
        x = self.proj(x)
        x = self.proj_drop(x)
        return x


class TransformerBlock1D(nn.Module):
    """
    Transformer block: Attention + FFN with pre-norm (like Astroformer).
    
    Uses GELU activation and relatively wide FFN (4x expansion)
    as in the original transformer and Astroformer.
    """

    def __init__(self, dim, num_heads=4, ffn_ratio=4, dropout=0.1, max_len=512):
        super().__init__()
        self.norm1 = nn.LayerNorm(dim)
        self.attn = RelativeMultiHeadAttention1D(dim, num_heads, dropout, max_len)
        self.norm2 = nn.LayerNorm(dim)
        self.ffn = nn.Sequential(
            nn.Linear(dim, dim * ffn_ratio),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(dim * ffn_ratio, dim),
            nn.Dropout(dropout),
        )

    def forward(self, x):
        x = x + self.attn(self.norm1(x))  # pre-norm + residual
        x = x + self.ffn(self.norm2(x))   # pre-norm + residual
        return x


# ============================================================
# Main Model
# ============================================================
class AstroFormer(nn.Module):
    """
    Hybrid Conv-Transformer for radar material classification.

    Follows Astroformer's C-C-T-T stack philosophy:
      Stage 0 (Stem):  Raw 5120 -> reshape to 1D sequence -> Conv projection
      Stage 1 (Conv):  Local feature extraction with SE-augmented inverted residuals
      Stage 2 (Conv):  Deeper local features, channel expansion
      Stage 3 (Trans): Self-attention over the sequence (global reasoning)
      Stage 4 (Trans): Final attention + classification head

    The conv stages capture local patterns in the radar signal (e.g., peaks,
    frequency-local features). The transformer stages then learn global
    relationships between those features (e.g., how patterns at different
    parts of the spectrum interact to determine material class).
    """

    def __init__(
        self,
        input_size=INPUT_SIZE,
        num_classes=NUM_CLASSES,
        dropout_rate=DROPOUT_RATE,
        # Stem
        patch_size=16,
        embed_dim=64,
        # Conv stages
        num_conv_blocks=2,
        conv_expand_ratio=2,
        conv_kernel_size=7,
        # Transformer stages
        num_attn_blocks=2,
        num_heads=4,
        ffn_ratio=4,
    ):
        super().__init__()

        self.input_size = input_size
        self.patch_size = patch_size
        seq_len = input_size // patch_size  # 5120 / 16 = 320 tokens

        # ---- Stage 0: Stem (patchify + project) ----
        self.stem = nn.Sequential(
            nn.BatchNorm1d(1),  # normalize raw input
            nn.Conv1d(1, embed_dim, kernel_size=patch_size, stride=patch_size, bias=False),
            nn.BatchNorm1d(embed_dim),
            nn.GELU(),
        )

        # ---- Stage 1-2: Conv blocks (local features + SE attention) ----
        self.conv_stages = nn.Sequential(
            *[ConvBlock1D(embed_dim, conv_expand_ratio, conv_kernel_size, dropout_rate)
              for _ in range(num_conv_blocks)]
        )

        # ---- Stage 3-4: Transformer blocks (global attention) ----
        self.to_transformer = nn.Sequential(
            # Conv1d -> (B, L, C) for transformer
        )
        self.attn_stages = nn.Sequential(
            *[TransformerBlock1D(embed_dim, num_heads, ffn_ratio, dropout_rate, max_len=seq_len)
              for _ in range(num_attn_blocks)]
        )
        self.final_norm = nn.LayerNorm(embed_dim)

        # ---- Classification head ----
        self.head = nn.Sequential(
            nn.Dropout(dropout_rate),
            nn.Linear(embed_dim, num_classes),
        )

        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.trunc_normal_(m.weight, std=0.02)
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.Conv1d):
                nn.init.kaiming_normal_(m.weight, mode="fan_out", nonlinearity="relu")
            elif isinstance(m, (nn.BatchNorm1d, nn.LayerNorm)):
                nn.init.constant_(m.weight, 1.0)
                nn.init.constant_(m.bias, 0.0)

    def forward(self, x):
        # x: (B, 5120) flat radar vector
        B = x.shape[0]

        # Reshape to 1D signal: (B, 1, 5120)
        x = x.unsqueeze(1)

        # Stem: patchify -> (B, embed_dim, seq_len)
        x = self.stem(x)

        # Conv stages: local feature extraction (B, C, L)
        x = self.conv_stages(x)

        # Transpose for transformer: (B, L, C)
        x = x.transpose(1, 2)

        # Attention stages: global reasoning
        x = self.attn_stages(x)
        x = self.final_norm(x)

        # Global average pooling over sequence -> (B, C)
        x = x.mean(dim=1)

        # Classification
        x = self.head(x)
        return x  # (B, num_classes)


# ============================================================
# Checkpoint utilities
# ============================================================
def save_checkpoint(model, scaler, filepath):
    """Save model checkpoint with architecture metadata and scaler."""
    import joblib

    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "model_class":type(model).__name__,
            "model_architecture": {
                "input_size":INPUT_SIZE,
                "num_classes":NUM_CLASSES,
                "dropout_rate":DROPOUT_RATE,
                "patch_size":16,
                "embed_dim":64,
                "num_conv_blocks":2,
                "conv_expand_ratio":2,
                "conv_kernel_size":7,
                "num_attn_blocks":2,
                "num_heads":4,
                "ffn_ratio":4
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

    model = AstroFormer(
        input_size=arch["input_size"],
        num_classes=arch["num_classes"],
        dropout_rate=arch.get("dropout_rate", DROPOUT_RATE),
    ).to(device)

    model.load_state_dict(checkpoint["model_state_dict"])
    return model, arch