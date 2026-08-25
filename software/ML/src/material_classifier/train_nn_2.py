#!/usr/bin/env python3
"""
Neural Network Training Script for Radar Material Classification
Multi-class classification (6 classes: 0-5)
"""

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader, random_split
import pandas as pd
import numpy as np
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import argparse
import logging
import joblib

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RadarDataset(Dataset):
    """Dataset class for radar material classification data"""
    
    def __init__(self, csv_file, scaler=None, fit_scaler=False):
        """
        Args:
            csv_file (str): Path to the CSV file with radar data
            scaler (StandardScaler): Pre-fitted scaler for normalization
            fit_scaler (bool): Whether to fit the scaler on this data
        """
        self.data = pd.read_csv(csv_file)
        
        # Extract features (bin1 to bin20) and targets (classification)
        feature_cols = [f'{i}' for i in range(5120)]
        self.features = self.data[feature_cols].values.astype(np.float32)
        self.targets = self.data['classification'].values.astype(np.int64)  # Changed to int64 for multi-class
        
        # Normalize features using StandardScaler
        if fit_scaler:
            self.scaler = StandardScaler()
            self.features = self.scaler.fit_transform(self.features)
            logger.info("StandardScaler fitted on data")
        elif scaler is not None:
            self.scaler = scaler
            self.features = self.scaler.transform(self.features)
            logger.info("Using provided StandardScaler")
        else:
            self.scaler = None
            logger.warning("No scaler provided - data not normalized!")
        
        self.features = self.features.astype(np.float32)
        
        logger.info(f"Dataset loaded: {len(self.features)} samples, {self.features.shape[1]} features")
        logger.info(f"Classes found: {np.unique(self.targets)}")
        logger.info(f"Feature statistics - Mean: {self.features.mean():.4f}, Std: {self.features.std():.4f}")
    
    def __len__(self):
        return len(self.features)
    
    def __getitem__(self, idx):
        return torch.tensor(self.features[idx]), torch.tensor(self.targets[idx])

class RadarMaterialClassifier(nn.Module):
    """
    Neural Network for multi-class radar material classification
    
    Architecture:
    Input (5120) -> BatchNorm -> Dense(64) + ReLU -> Dense(32) + ReLU -> Dense(6) 
    Output: 6 classes (0-5)
    """
    
    def __init__(self, input_size=5120, hidden1_size=64, hidden2_size=32, num_classes=6):
        super(RadarMaterialClassifier, self).__init__()
        
        # Input normalization/bias layer
        self.input_bias = nn.Parameter(torch.randn(input_size) * 0.1)
        
        self.bn_input = nn.BatchNorm1d(input_size)
        self.bn2 = nn.BatchNorm1d(hidden1_size)
        self.bn3 = nn.BatchNorm1d(hidden2_size)

        # First dense layer with ReLU
        self.fc1 = nn.Linear(input_size, hidden1_size)
        self.fc1_bias_add = nn.Parameter(torch.randn(hidden1_size) * 0.1)
        
        # Second dense layer with ReLU
        self.fc2 = nn.Linear(hidden1_size, hidden2_size)
        self.fc2_bias_add = nn.Parameter(torch.randn(hidden2_size) * 0.1)
        
        # Output layer: 6 classes (no activation, we'll use CrossEntropyLoss)
        self.fc3 = nn.Linear(hidden2_size, num_classes)
        
        # Initialize weights
        self._init_weights()
    
    def _init_weights(self):
        """Initialize weights similar to TVM model"""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                nn.init.constant_(module.bias, 0.0)
    
    def forward(self, x):
        # Input layer with bias addition
        x = self.bn_input(x)
        x = x + self.input_bias
        
        # First hidden layer: Dense -> BatchNorm -> ReLU -> Bias Add
        x = self.fc1(x)
        x = self.bn2(x)
        x = F.relu(x)
        x = x + self.fc1_bias_add
        
        # Second hidden layer: Dense -> BatchNorm -> ReLU -> Bias Add  
        x = self.fc2(x)
        x = self.bn3(x)
        x = F.relu(x)
        x = x + self.fc2_bias_add
        
        # Output layer: Dense (no activation, CrossEntropyLoss applies softmax internally)
        x = self.fc3(x)
        
        return x  # Shape: (batch_size, 6)

def create_data_loaders_with_scaler(csv_file, train_ratio=0.7, val_ratio=0.15, test_ratio=0.15, batch_size=32):
    """
    Create train, validation, and test data loaders with proper StandardScaler usage
    
    IMPORTANT: Scaler is fitted ONLY on training data, then applied to val/test
    """
    assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-6, "Ratios must sum to 1.0"
    
    # Load raw data
    data = pd.read_csv(csv_file)
    feature_cols = [f'{i}' for i in range(5120)]
    features = data[feature_cols].values.astype(np.float32)
    targets = data['classification'].values.astype(np.int64)  # int64 for multi-class
    
    # ========== NETTOYAGE DES NaN ==========
    nan_count = np.isnan(features).sum()
    inf_count = np.isinf(features).sum()
    
    if nan_count > 0:
        logger.warning(f"Found {nan_count} NaN values in features - replacing with 0")
        features = np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)
    
    if inf_count > 0:
        logger.warning(f"Found {inf_count} Inf values in features - replacing with 0")
        features = np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)
    
    logger.info(f"After cleaning - Min: {features.min():.4f}, Max: {features.max():.4f}")
    
    # ========== GESTION DES VALEURS ABERRANTES ==========
    threshold = 1e11
    outliers_mask = np.abs(features) > threshold
    outliers_count = outliers_mask.sum()
    
    if outliers_count > 0:
        logger.warning(f"Found {outliers_count} outlier values (|x| > {threshold:.0e}) ({100*outliers_count/features.size:.2f}%)")
        logger.warning(f"Min before clipping: {features.min():.2e}, Max before clipping: {features.max():.2e}")
        features[outliers_mask] = 0.0
        logger.info(f"Outliers replaced with 0")
        logger.info(f"After cleaning - Min: {features.min():.4f}, Max: {features.max():.4f}, Mean: {features.mean():.4f}")
    else:
        logger.info(f"No outliers detected - Min: {features.min():.4f}, Max: {features.max():.4f}")
    
    # ========== DIAGNOSTIC ==========
    print("\n=== DIAGNOSTIC DES DONNÉES ===")
    print(f"Shape des features: {features.shape}")
    print(f"Nombre de NaN dans features: {np.isnan(features).sum()}")
    print(f"Nombre de Inf dans features: {np.isinf(features).sum()}")
    print(f"Min des features: {np.nanmin(features)}")
    print(f"Max des features: {np.nanmax(features)}")
    print(f"\nDistribution des classes:")
    unique, counts = np.unique(targets, return_counts=True)
    for cls, count in zip(unique, counts):
        print(f"  Classe {cls}: {count} samples ({100*count/len(targets):.1f}%)")
    print("=" * 40 + "\n")

    # Split indices
    dataset_size = len(features)
    indices = np.arange(dataset_size)
    np.random.shuffle(indices)
    
    train_size = int(train_ratio * dataset_size)
    val_size = int(val_ratio * dataset_size)
    
    train_idx = indices[:train_size]
    val_idx = indices[train_size:train_size + val_size]
    test_idx = indices[train_size + val_size:]
    
    # Split data
    X_train, y_train = features[train_idx], targets[train_idx]
    X_val, y_val = features[val_idx], targets[val_idx]
    X_test, y_test = features[test_idx], targets[test_idx]
    
    # Fit scaler on TRAIN data only
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    X_test_scaled = scaler.transform(X_test)
    
    logger.info(f"Data split - Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")
    logger.info(f"Scaler fitted on training data")
    logger.info(f"Train data - Mean: {X_train_scaled.mean():.6f}, Std: {X_train_scaled.std():.6f}")
    logger.info(f"Val data - Mean: {X_val_scaled.mean():.6f}, Std: {X_val_scaled.std():.6f}")
    
    # Create datasets
    class SimpleDataset(Dataset):
        def __init__(self, features, targets):
            self.features = features.astype(np.float32)
            self.targets = targets
        
        def __len__(self):
            return len(self.features)
        
        def __getitem__(self, idx):
            return torch.tensor(self.features[idx]), torch.tensor(self.targets[idx])
    
    train_dataset = SimpleDataset(X_train_scaled, y_train)
    val_dataset = SimpleDataset(X_val_scaled, y_val)
    test_dataset = SimpleDataset(X_test_scaled, y_test)
    
    # Create data loaders
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)
    
    return train_loader, val_loader, test_loader, scaler

def train_epoch(model, train_loader, criterion, optimizer, device):
    """Train for one epoch"""
    model.train()
    total_loss = 0.0
    correct_predictions = 0
    total_samples = 0
    
    for batch_idx, (features, targets) in enumerate(train_loader):
        features, targets = features.to(device), targets.to(device)
        
        # targets are already int64, no need to convert to float
        
        optimizer.zero_grad()
        outputs = model(features)
        loss = criterion(outputs, targets)
        
        # Check for NaN
        if torch.isnan(loss):
            logger.error(f"NaN loss detected at batch {batch_idx}")
            logger.error(f"Outputs - min: {outputs.min():.4f}, max: {outputs.max():.4f}")
            logger.error(f"Features - min: {features.min():.4f}, max: {features.max():.4f}")
            raise ValueError("NaN loss detected!")
        
        loss.backward()
        
        # Gradient clipping to prevent explosion
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        
        optimizer.step()
        
        total_loss += loss.item()
        
        # For multi-class classification accuracy
        _, predicted = torch.max(outputs, 1)  # Get the class with highest score
        correct_predictions += (predicted == targets).sum().item()
        total_samples += targets.size(0)
    
    avg_loss = total_loss / len(train_loader)
    accuracy = correct_predictions / total_samples
    
    return avg_loss, accuracy

def validate_epoch(model, val_loader, criterion, device):
    """Validate for one epoch"""
    model.eval()
    total_loss = 0.0
    correct_predictions = 0
    total_samples = 0
    
    with torch.no_grad():
        for features, targets in val_loader:
            features, targets = features.to(device), targets.to(device)
            
            outputs = model(features)
            loss = criterion(outputs, targets)
            
            total_loss += loss.item()
            
            # Get predicted class
            _, predicted = torch.max(outputs, 1)
            correct_predictions += (predicted == targets).sum().item()
            total_samples += targets.size(0)
    
    avg_loss = total_loss / len(val_loader)
    accuracy = correct_predictions / total_samples
    
    return avg_loss, accuracy

def train_model(model, train_loader, val_loader, num_epochs=100, learning_rate=1e-4, device='cuda'):
    """Complete training loop"""
    
    # Use CrossEntropyLoss for multi-class classification
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, 'min', patience=10, factor=0.5)
    
    # Initial evaluation
    train_acc, _, _, _, _ = evaluate_model(model=model, test_loader=train_loader, device=device)
    val_acc, _, _, _, _ = evaluate_model(model=model, test_loader=val_loader, device=device)

    train_losses = []
    val_losses = []
    train_accuracies = [train_acc]
    val_accuracies = [val_acc]
    
    best_val_accuracy = 0.0
    best_model_state = None
    patience_counter = 0
    early_stop_patience = 20
    
    logger.info(f"Starting training for {num_epochs} epochs on {device}")
    logger.info(f"Initial - Train Acc: {train_acc:.4f}, Val Acc: {val_acc:.4f}")
    
    for epoch in range(num_epochs):
        # Train
        train_loss, train_acc = train_epoch(model, train_loader, criterion, optimizer, device)
        
        # Validate
        val_loss, val_acc = validate_epoch(model, val_loader, criterion, device)
        
        # Learning rate scheduling
        scheduler.step(val_loss)
        
        # Save best model
        if val_acc > best_val_accuracy:
            best_val_accuracy = val_acc
            best_model_state = model.state_dict().copy()
            patience_counter = 0
        else:
            patience_counter += 1
        
        # Record metrics
        train_losses.append(train_loss)
        val_losses.append(val_loss)
        train_accuracies.append(train_acc)
        val_accuracies.append(val_acc)
        
        # Logging
        if (epoch + 1) % 10 == 0:
            logger.info(f'Epoch [{epoch+1}/{num_epochs}]')
            logger.info(f'Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.4f}')
            logger.info(f'Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.4f}')
            logger.info(f'Best Val Acc: {best_val_accuracy:.4f}')
            logger.info(f'LR: {optimizer.param_groups[0]["lr"]:.6f}')
        
        # Early stopping
        if patience_counter >= early_stop_patience:
            logger.info(f"Early stopping at epoch {epoch+1}")
            break
    
    # Load best model
    if best_model_state is not None:
        model.load_state_dict(best_model_state)
    
    return {
        'train_losses': train_losses,
        'val_losses': val_losses,
        'train_accuracies': train_accuracies,
        'val_accuracies': val_accuracies,
        'best_val_accuracy': best_val_accuracy
    }

def evaluate_model(model, test_loader, device):
    """Evaluate model on test set"""
    model.eval()
    all_predictions = []
    all_targets = []
    
    with torch.no_grad():
        for features, targets in test_loader:
            features, targets = features.to(device), targets.to(device)
            
            outputs = model(features)
            # Get predicted class (argmax)
            _, predicted = torch.max(outputs, 1)
            
            all_predictions.extend(predicted.cpu().numpy())
            all_targets.extend(targets.cpu().numpy())
    
    accuracy = accuracy_score(all_targets, all_predictions)
    report = classification_report(all_targets, all_predictions)
    cm = confusion_matrix(all_targets, all_predictions)
    
    return accuracy, report, cm, all_targets, all_predictions

def plot_training_history(history, save_path=None):
    """Plot training history"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
    
    # Loss plot
    ax1.plot(list(range(1, len(history['train_losses'])+1)), history['train_losses'], label='Train Loss', color='blue')
    ax1.plot(list(range(1, len(history['val_losses'])+1)), history['val_losses'], label='Val Loss', color='red')
    ax1.set_title('Training and Validation Loss')
    ax1.set_xlabel('Epoch')
    ax1.set_ylabel('Loss')
    ax1.legend()
    ax1.grid(True)
    
    # Accuracy plot
    ax2.plot(history['train_accuracies'], label='Train Accuracy', color='blue')
    ax2.plot(history['val_accuracies'], label='Val Accuracy', color='red')
    ax2.set_title('Training and Validation Accuracy')
    ax2.set_xlabel('Epoch')
    ax2.set_ylabel('Accuracy')
    ax2.legend()
    ax2.grid(True)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"Training history saved to {save_path}")
    
    plt.show()

def plot_confusion_matrix(cm, save_path=None):
    """Plot confusion matrix for multi-class classification"""
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', cbar=True)
    plt.title('Confusion Matrix (6 Classes)')
    plt.ylabel('True Label')
    plt.xlabel('Predicted Label')
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"Confusion matrix saved to {save_path}")
    
    plt.show()

def save_model(model, scaler, filepath):
    """Save trained model and scaler"""
    torch.save({
        'model_state_dict': model.state_dict(),
        'model_architecture': {
            'input_size': 5120,
            'hidden1_size': 64,
            'hidden2_size': 32,
            'num_classes': 6  # Updated to 6 classes
        }
    }, filepath)
    logger.info(f"Model saved to {filepath}")
    
    # Save scaler separately
    scaler_path = filepath.parent / 'scaler.pkl'
    joblib.dump(scaler, scaler_path)
    logger.info(f"Scaler saved to {scaler_path}")

def main():
    parser = argparse.ArgumentParser(description='Train Radar Material Classification Neural Network (6 classes)')
    parser.add_argument('--data', type=str, default='data.csv', 
                       help='Path to CSV data file')
    parser.add_argument('--epochs', type=int, default=100, help='Number of training epochs')
    parser.add_argument('--batch_size', type=int, default=32, help='Batch size')
    parser.add_argument('--lr', type=float, default=1e-4, help='Learning rate')
    parser.add_argument('--device', type=str, default='auto', 
                       choices=['auto', 'cpu', 'cuda'], help='Device to use')
    parser.add_argument('--output_dir', type=str, default='./outputs', 
                       help='Output directory for results')
    
    args = parser.parse_args()
    
    # Setup device
    if args.device == 'auto':
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    else:
        device = torch.device(args.device)
    
    logger.info(f"Using device: {device}")
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Load dataset with StandardScaler
    logger.info("Loading dataset with StandardScaler...")
    train_loader, val_loader, test_loader, scaler = create_data_loaders_with_scaler(
        args.data, batch_size=args.batch_size
    )
    
    # Initialize model
    model = RadarMaterialClassifier().to(device)
    logger.info(f"Model architecture:\n{model}")
    
    # Count parameters
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info(f"Total parameters: {total_params}, Trainable: {trainable_params}")
    
    # Train model
    logger.info("Starting training...")
    history = train_model(
        model, train_loader, val_loader, 
        num_epochs=args.epochs, 
        learning_rate=args.lr,
        device=device
    )
    
    # Evaluate on test set
    logger.info("Evaluating on test set...")
    test_accuracy, test_report, confusion_matrix_result, targets, predictions = evaluate_model(
        model, test_loader, device
    )
    
    logger.info(f"Test Accuracy: {test_accuracy:.4f}")
    logger.info(f"Classification Report:\n{test_report}")
    
    # Save results
    model_path = output_dir / 'radar_material_classifier.pth'
    save_model(model, scaler, model_path)
    
    # Plot results
    plot_training_history(history, output_dir / 'training_history.png')
    plot_confusion_matrix(confusion_matrix_result, output_dir / 'confusion_matrix.png')
    
    # Save metrics
    results = {
        'test_accuracy': test_accuracy,
        'best_val_accuracy': history['best_val_accuracy'],
        'classification_report': test_report
    }
    
    with open(output_dir / 'results.txt', 'w') as f:
        f.write(f"Test Accuracy: {results['test_accuracy']:.4f}\n")
        f.write(f"Best Validation Accuracy: {results['best_val_accuracy']:.4f}\n")
        f.write(f"\nClassification Report:\n{results['classification_report']}")
    
    logger.info(f"Training completed! Results saved in {output_dir}")
    
    return model, history, results

if __name__ == "__main__":
    main()