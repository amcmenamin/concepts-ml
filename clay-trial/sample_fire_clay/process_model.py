import torch
import numpy as np
import rasterio
from matplotlib import pyplot as plt
from sklearn import decomposition, svm
from claymodel.module import ClayMAEModule
from prep_imagery import ImageryPreprocessor

preprocessor = ImageryPreprocessor(
    tif_path="data/monchique_sentinel2.tif",
    metadata_path="configs/metadata.yaml",
    lat=37.30939,
    lon=-8.57207,
    device="cuda"  # or "cpu"
)
datacube = preprocessor.get_datacube()


device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
ckpt = "clay-v1.5.ckpt"
torch.set_default_device(device)

model = ClayMAEModule.load_from_checkpoint(
    ckpt,
    model_size="large",
    metadata_path="configs/metadata.yaml",
    dolls=[16, 32, 64, 128, 256, 768, 1024],
    doll_weights=[1, 1, 1, 1, 1, 1, 1],
    mask_ratio=0.0,
    shuffle=False,
)
model.eval()

model = model.to(device)

print(f"Model loaded on {device} with {sum(p.numel() for p in model.parameters())} parameters.")


# Run the model
with torch.no_grad():
    # Process each timestep separately
    all_embeddings = []
    for i in range(datacube["pixels"].shape[0]):
        single_datacube = {
            "platform": datacube["platform"],
            "time": datacube["time"][i:i+1],
            "latlon": datacube["latlon"][i:i+1],
            "pixels": datacube["pixels"][i:i+1],
            "gsd": datacube["gsd"],
            "waves": datacube["waves"],
        }
        print(f"Processing timestep {i+1}/{datacube['pixels'].shape[0]}")
        unmsk_patch, unmsk_idx, msk_idx, msk_matrix = model.model.encoder(single_datacube)
        all_embeddings.append(unmsk_patch[:, 0, :].cpu().numpy())

# The first embedding is the class token, which is the
# overall single embedding. We extract that for PCA below.
embeddings = np.vstack(all_embeddings)

# Write embeddings to GeoTIFF
with rasterio.open("data/monchique_sentinel2.tif") as src:
    profile = src.profile.copy()
    profile.update({
        'count': embeddings.shape[1],
        'dtype': 'float32'
    })
    
    with rasterio.open("data/embeddings.tif", "w", **profile) as dst:
        for i in range(embeddings.shape[1]):
            band_data = np.full((src.height, src.width), embeddings[0, i], dtype=np.float32)
            dst.write(band_data, i + 1)

print(f"Embeddings saved to data/embeddings.tif with shape {embeddings.shape}")

# Get dates for plotting
dates = preprocessor.dates

# Play with results
# Run PCA
pca = decomposition.PCA(n_components=1)
pca_result = pca.fit_transform(embeddings)

plt.figure(figsize=(10, 6))
plt.xticks(rotation=-45)

# Plot all points in blue first
plt.scatter(dates, pca_result, color="blue", label="Normal")

# Re-plot cloudy images in green
plt.scatter(dates[0], pca_result[0], color="green", label="Cloud")
plt.scatter(dates[2], pca_result[2], color="green")

# Color all images after fire in red
plt.scatter(dates[-5:], pca_result[-5:], color="red", label="Fire")

plt.xlabel("Date")
plt.ylabel("PCA Component 1")
plt.title("Temporal Analysis of Embeddings")
plt.legend()
plt.tight_layout()
plt.savefig("data/pca_plot.png", dpi=300)
print("PCA plot saved to data/pca_plot.png")


#fine-tune
# Label the images we downloaded
# 0 = Cloud
# 1 = Forest
# 2 = Fire
labels = np.array([0, 1, 0, 1, 1, 1, 1, 2, 2, 2, 2, 2])

# Split into fit and test manually, ensuring we have all 3 classes in both sets
fit = [0, 1, 3, 4, 7, 8, 9]
test = [2, 5, 6, 10, 11]

# Train a Support Vector Machine model
clf = svm.SVC()
clf.fit(embeddings[fit] + 100, labels[fit])

# Predict classes on test set
prediction = clf.predict(embeddings[test] + 100)

# Perfect match for SVM
match = np.sum(labels[test] == prediction)
print(f"Matched {match} out of {len(test)} correctly")

# Predict all timesteps
all_predictions = clf.predict(embeddings + 100)

# Write predictions to GeoTIFF
with rasterio.open("data/monchique_sentinel2.tif") as src:
    profile = src.profile.copy()
    profile.update({'count': len(all_predictions), 'dtype': 'uint8'})
    
    with rasterio.open("data/predictions.tif", "w", **profile) as dst:
        for i, pred in enumerate(all_predictions):
            band_data = np.full((src.height, src.width), pred, dtype=np.uint8)
            dst.write(band_data, i + 1)
            dst.set_band_description(i + 1, f"{dates[i]}_class_{pred}")

print(f"Predictions saved to data/predictions.tif")