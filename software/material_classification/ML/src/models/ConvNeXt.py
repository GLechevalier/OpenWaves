#!/usr/bin/env python3
"""
Radar Material Classification - ConvNeXt-T Model Architecture

Inspired by "A ConvNet for the 2020s" (Liu et al., CVPR 2022):
a pure convolutional architecture that modernizes ResNet with design
choices borrowed from Vision Transformers.

Adapted from 2D image classification to 1D radar signal classification.
Key borrowed ideas:
  - Patchify stem (non-overlapping convolution, like ViT)
  - Inverted bottleneck with depthwise separable convolutions
  - Large kernel (7) depthwise convolutions for wide receptive fields
  - LayerNorm instead of BatchNorm
  - GELU activation, fewer activation/norm layers
  - Layer Scale and Stochastic Depth for training stability
"""

import torch
import torch.nn as nn
from software.material_classification.ML.src.models.abstract_module import AbstractModule

# ============================================================
# Constants
# ============================================================
INPUT_SIZE = 5120
NUM_CLASSES = 2
DROPOUT_RATE = 0.3
OUTLIER_THRESHOLD = 1e11

# ConvNeXt-T configuration: C=96, blocks=(3, 3, 9, 3)
EMBED_DIM = 96
DEPTHS = (3, 3, 9, 3)
DIMS = (48, 96, 192, 384)


CONV_NEXT_CONSTS = {
    "INPUT_SIZE":INPUT_SIZE,
    "NUM_CLASSES":NUM_CLASSES,
    "DROPOUT_RATE":DROPOUT_RATE,
    "OUTLIER_THRESHOLD":OUTLIER_THRESHOLD,
    "EMBED_DIM":EMBED_DIM,
    "DEPTHS":DEPTHS,
    "DIMS":DIMS
}


# ============================================================
# Building Blocks
# ============================================================
class LayerNorm1d(nn.Module):
    """
    Channel-first LayerNorm for 1D convolutions.

    Standard LayerNorm expects (B, L, C) but conv layers produce (B, C, L).
    This wrapper handles the transpose so we can use LayerNorm in a conv
    pipeline without manual permutation at every layer.
    """

    def __init__(self, channels, eps=1e-6):
        super().__init__()
        self.norm = nn.LayerNorm(channels, eps=eps)

    def forward(self, x):
        # x: (B, C, L) -> transpose -> norm -> transpose back
        x = x.transpose(1, 2)   # (B, L, C)
        x = self.norm(x)
        x = x.transpose(1, 2)   # (B, C, L)
        return x


class DropPath(nn.Module):
    """
    Stochastic Depth (Huang et al., 2016).

    Randomly drops entire residual branches during training.
    Used in ConvNeXt (and many modern architectures) to regularize
    deep networks and improve generalization in low-data regimes.
    """

    def __init__(self, drop_prob=0.0):
        super().__init__()
        self.drop_prob = drop_prob

    def forward(self, x):
        if not self.training or self.drop_prob == 0.0:
            return x
        keep_prob = 1.0 - self.drop_prob
        # Binary mask: (B, 1, 1) for broadcasting over (B, C, L)
        shape = (x.shape[0],) + (1,) * (x.ndim - 1)
        mask = torch.rand(shape, device=x.device, dtype=x.dtype).floor_() + keep_prob
        return x * mask / keep_prob


class ConvNeXtBlock1D(nn.Module):
    """
    Core ConvNeXt block adapted to 1D signals.

    Follows the inverted bottleneck design from the paper:
      1. Depthwise conv 7×1 (spatial mixing, large receptive field)
      2. LayerNorm
      3. Pointwise conv 1×1 expanding channels 4× (channel mixing)
      4. GELU
      5. Pointwise conv 1×1 projecting back (channel mixing)
      6. Layer Scale + residual connection

    This mirrors a Transformer block: depthwise conv ≈ self-attention
    (spatial), and the two pointwise convs ≈ the FFN (channel).

    Key differences from Astroformer's ConvBlock1D:
      - Depthwise conv comes FIRST (not sandwiched in expansion)
      - LayerNorm replaces BatchNorm
      - Fewer activations (only one GELU, not two)
      - Layer Scale for training stability
      - No Squeeze-Excitation (simplicity over explicit channel attention)
    """

    def __init__(self, dim, expand_ratio=4, kernel_size=7,
                 drop_path=0.0, layer_scale_init=1e-6):
        super().__init__()
        mid = dim * expand_ratio

        # Depthwise convolution: spatial mixing with large kernel
        self.dwconv = nn.Conv1d(
            dim, dim, kernel_size=kernel_size,
            padding=kernel_size // 2, groups=dim, bias=True,
        )
        # LayerNorm (channel-first wrapper)
        self.norm = LayerNorm1d(dim)
        # Pointwise expansion -> GELU -> pointwise projection
        self.pwconv1 = nn.Conv1d(dim, mid, kernel_size=1, bias=True)
        self.act = nn.GELU()
        self.pwconv2 = nn.Conv1d(mid, dim, kernel_size=1, bias=True)

        # Layer Scale: learnable per-channel scaling (ConvNeXt contribution)
        # Initialized to a small value so residual branch starts near-identity
        self.layer_scale = nn.Parameter(
            layer_scale_init * torch.ones(1, dim, 1)
        ) if layer_scale_init > 0 else None

        self.drop_path = DropPath(drop_path) if drop_path > 0.0 else nn.Identity()

    def forward(self, x):
        # x: (B, C, L)
        residual = x

        x = self.dwconv(x)      # spatial mixing
        x = self.norm(x)         # normalize
        x = self.pwconv1(x)      # expand channels
        x = self.act(x)          # single GELU
        x = self.pwconv2(x)      # project back

        # Layer Scale
        if self.layer_scale is not None:
            x = x * self.layer_scale

        x = residual + self.drop_path(x)  # residual + stochastic depth
        return x


class Downsampling1D(nn.Module):
    """
    Spatial downsampling between ConvNeXt stages.

    Uses LayerNorm followed by a strided convolution (stride=2)
    to halve sequence length and increase channels.
    Replaces the max-pooling / strided-conv approach in ResNets.
    """

    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.norm = LayerNorm1d(in_channels)
        self.conv = nn.Conv1d(
            in_channels, out_channels,
            kernel_size=2, stride=2, bias=True,
        )

    def forward(self, x):
        # x: (B, C_in, L) -> (B, C_out, L//2)
        x = self.norm(x)
        x = self.conv(x)
        return x


# ============================================================
# Main Model
# ============================================================
class ConvNeXtT(AbstractModule):
    """
    ConvNeXt-Tiny for 1D radar material classification.

    Hierarchical 4-stage pure ConvNet architecture:
      Stage 0 (Stem):   Raw 5120 -> patchify with non-overlapping conv
      Stage 1 (C=96):   3 ConvNeXt blocks at resolution L/4
      Stage 2 (C=192):  3 ConvNeXt blocks at resolution L/8
      Stage 3 (C=384):  9 ConvNeXt blocks at resolution L/16
      Stage 4 (C=768):  3 ConvNeXt blocks at resolution L/32

    Stage 3 is the heaviest (9 blocks) following the 1:1:3:1 compute
    ratio from Swin Transformer, which the ConvNeXt paper found
    superior to ResNet's original 1:1:2:1 ratio.

    The early stages capture local spectral patterns in the radar
    signal. The deeper stages, with progressively larger effective
    receptive fields from stacked 7-kernel depthwise convolutions,
    learn increasingly global relationships across the spectrum.
    """

    consts = CONV_NEXT_CONSTS

    def __init__(
        self,
        input_size=INPUT_SIZE,
        num_classes=NUM_CLASSES,
        dropout_rate=DROPOUT_RATE,
        # Stem
        patch_size=4,
        # Architecture (ConvNeXt-T defaults)
        dims=DIMS,
        depths=DEPTHS,
        # Block config
        expand_ratio=4,
        kernel_size=7,
        layer_scale_init=1e-6,
        drop_path_rate=0.1,
    ):
        super().__init__()

        self.input_size = input_size
        self.num_classes = num_classes
        self.dropout_rate = dropout_rate
        
        self.patch_size = patch_size
        self.dims = dims
        self.depths = depths

        # ---- Stage 0: Patchify stem ----
        # Non-overlapping convolution mimicking ViT's patch embedding.
        # Maps raw 1D signal to initial feature sequence.
        self.stem = nn.Sequential(
            nn.Conv1d(1, dims[0], kernel_size=patch_size, stride=patch_size, bias=True),
            LayerNorm1d(dims[0]),
        )

        # ---- Stochastic depth schedule ----
        # Linearly increasing drop rate across all blocks (deepest blocks
        # are dropped most often, following standard practice).
        total_blocks = sum(depths)
        dp_rates = [
            drop_path_rate * i / (total_blocks - 1)
            for i in range(total_blocks)
        ]

        # ---- Stages 1-4: ConvNeXt blocks with downsampling ----
        self.stages = nn.ModuleList()
        self.downsamples = nn.ModuleList()

        block_idx = 0
        for i in range(4):
            # Downsampling layer between stages (skip for stage 0)
            if i > 0:
                self.downsamples.append(
                    Downsampling1D(dims[i - 1], dims[i])
                )
            else:
                self.downsamples.append(nn.Identity())

            # Stack of ConvNeXt blocks for this stage
            stage_blocks = nn.Sequential(
                *[
                    ConvNeXtBlock1D(
                        dim=dims[i],
                        expand_ratio=expand_ratio,
                        kernel_size=kernel_size,
                        drop_path=dp_rates[block_idx + j],
                        layer_scale_init=layer_scale_init,
                    )
                    for j in range(depths[i])
                ]
            )
            self.stages.append(stage_blocks)
            block_idx += depths[i]

        # ---- Classification head ----
        # Global average pooling -> LayerNorm -> Linear
        if num_classes==2:
            num_classes=1
        self.final_norm = LayerNorm1d(dims[-1])
        self.head = nn.Sequential(
            nn.Dropout(dropout_rate),
            nn.Linear(dims[-1], num_classes),
        )

        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.trunc_normal_(m.weight, std=0.02)
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.Conv1d):
                nn.init.trunc_normal_(m.weight, std=0.02)
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)

    def forward(self, x):
        # x: (B, 5120) flat radar vector
        B = x.shape[0]

        # Reshape to 1D signal: (B, 1, 5120)
        x = x.unsqueeze(1)

        # Stem: patchify -> (B, dims[0], L)
        x = self.stem(x)

        # Hierarchical stages: conv blocks + downsampling
        for i in range(4):
            x = self.downsamples[i](x)   # spatial downsampling (identity for stage 0)
            x = self.stages[i](x)        # ConvNeXt blocks

        # Final norm
        x = self.final_norm(x)

        # Global average pooling over sequence -> (B, C)
        x = x.mean(dim=2)

        # Classification
        x = self.head(x)
        return x  # (B, num_classes)

    @staticmethod
    def _get_checkpoint(filepath, device='cpu'):
        checkpoint = torch.load(filepath, map_location=device, weights_only=False)
        return checkpoint

    @staticmethod
    def _load_model(arch, device='cpu'):
        model = ConvNeXtT(
            input_size=arch["input_size"],
            num_classes=arch["num_classes"],
            dropout_rate=arch.get("dropout_rate", CONV_NEXT_CONSTS["DROPOUT_RATE"]),
            patch_size=arch.get("patch_size", 4),
            dims=tuple(arch.get("dims", CONV_NEXT_CONSTS["DIMS"])),
            depths=tuple(arch.get("depths", CONV_NEXT_CONSTS["DEPTHS"])),
            expand_ratio=arch.get("expand_ratio", 4),
            kernel_size=arch.get("kernel_size", 7),
            layer_scale_init=arch.get("layer_scale_init", 1e-6),
            drop_path_rate=arch.get("drop_path_rate", 0.1),
        ).to(device)
        return model
    
    @staticmethod
    def save_checkpoint(model, filepath, scaler):
        """Save model checkpoint with architecture metadata and scaler."""
        import joblib

        torch.save(
            {
                "model_state_dict": model.state_dict(),
                "model_class": type(model).__name__,
                "model_architecture": {
                    "input_size": model.input_size,
                    "num_classes": model.num_classes,
                    "dropout_rate": model.dropout_rate,
                    "patch_size": 4,
                    "dims": list(model.dims),
                    "depths": list(model.depths),
                    "expand_ratio": 4,
                    "kernel_size": 7,
                    "layer_scale_init": 1e-6,
                    "drop_path_rate": 0.1,
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
        checkpoint = ConvNeXtT._get_checkpoint(filepath=filepath, device=device)
        arch = checkpoint["model_architecture"]
        model = ConvNeXtT._load_model(arch=arch, device=device)
        model.load_state_dict(checkpoint["model_state_dict"])
        return model, arch