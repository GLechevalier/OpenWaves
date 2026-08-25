import torch.nn as nn

class AbstractModule(nn.Module):
    def __init__(self):
        super().__init__()
        return
     
    def save_checkpoint(self):
        raise NotImplementedError
    
    @staticmethod
    def _get_checkpoint(filepath, device='cpu'):
        raise NotImplementedError
    
    @staticmethod
    def _load_model(arch, device='cpu'):
        raise NotImplementedError
    
    @staticmethod
    def load_checkpoint(filepath, device="cpu"):
        """Load model from checkpoint. Returns (model, architecture_dict)."""
        checkpoint = AbstractModule._get_checkpoint(filepath=filepath, device=device)
        arch = checkpoint["model_architecture"]
        model = AbstractModule._load_model(arch=arch, device=device)
        model.load_state_dict(checkpoint["model_state_dict"])
        return model, arch

