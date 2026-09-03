import torch
import torch.nn as nn


class ClaySegmentationHead(nn.Module):
    """Simple segmentation decoder for Clay embeddings"""
    def __init__(self, embedding_dim=1024, num_classes=10, patch_size=16):
        super().__init__()
        self.patch_size = patch_size
        self.decoder = nn.Sequential(
            nn.Conv2d(embedding_dim, 512, 1),
            nn.ReLU(),
            nn.Conv2d(512, 256, 1),
            nn.ReLU(),
            nn.Conv2d(256, num_classes, 1)
        )
    
    def forward(self, embeddings):
        """
        embeddings: (B, N_patches, embedding_dim) from Clay encoder
        returns: (B, num_classes, H, W) segmentation logits
        """
        B, N, D = embeddings.shape
        H = W = int(N ** 0.5)
        
        # Reshape to spatial: (B, D, H, W)
        x = embeddings.transpose(1, 2).reshape(B, D, H, W)
        
        # Decode to classes
        logits = self.decoder(x)
        
        # Upsample to original resolution
        logits = nn.functional.interpolate(
            logits, 
            scale_factor=self.patch_size, 
            mode='bilinear', 
            align_corners=False
        )
        
        return logits


# Usage example:
# seg_head = ClaySegmentationHead(num_classes=5)
# with torch.no_grad():
#     unmsk_patch, _, _, _ = clay_model.model.encoder(datacube)
#     seg_logits = seg_head(unmsk_patch)  # (B, 5, 256, 256)
#     seg_map = seg_logits.argmax(dim=1)  # (B, 256, 256)
