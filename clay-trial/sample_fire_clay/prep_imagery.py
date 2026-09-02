import rasterio
import torch
import numpy as np
import pandas as pd
import math
from torchvision.transforms import v2
import yaml
from box import Box


class ImageryPreprocessor:
    def __init__(self, tif_path, metadata_path, lat, lon, platform="sentinel-2-l2a", device="cpu"):
        self.tif_path = tif_path
        self.metadata_path = metadata_path
        self.lat = lat
        self.lon = lon
        self.platform = platform
        self.device = device
        self.dates = None
        
    def normalize_timestamp(self, date):
        date = pd.Timestamp(date)
        week = date.isocalendar().week * 2 * np.pi / 52
        hour = date.hour * 2 * np.pi / 24
        return (math.sin(week), math.cos(week)), (math.sin(hour), math.cos(hour))
    
    def normalize_latlon(self, lat, lon):
        lat = lat * np.pi / 180
        lon = lon * np.pi / 180
        return (math.sin(lat), math.cos(lat)), (math.sin(lon), math.cos(lon))
    
    def get_dates(self):
        with rasterio.open(self.tif_path) as dataset:
            descriptions = dataset.descriptions
            dates = sorted(list(set([description.rsplit("_", 1)[0] for description in descriptions])))
        return [np.datetime64(date) for date in dates]
    
    def get_datacube(self):
        with rasterio.open(self.tif_path) as dataset:
            descriptions = dataset.descriptions
            band_names = [description.rsplit("_", 1)[1] for description in descriptions[:4]]
            dates = sorted(list(set([description.rsplit("_", 1)[0] for description in descriptions])))
            pixels_data = dataset.read().astype(np.float32)
            gsd = dataset.res[0]
        
        self.dates = [np.datetime64(date) for date in dates]
        
        metadata = Box(yaml.safe_load(open(self.metadata_path)))
        mean = [metadata[self.platform].bands.mean[str(band)] for band in band_names]
        std = [metadata[self.platform].bands.std[str(band)] for band in band_names]
        waves = [metadata[self.platform].bands.wavelength[str(band)] for band in band_names]
        
        transform = v2.Compose([v2.Normalize(mean=mean, std=std)])
        
        datetimes = self.dates
        times = [self.normalize_timestamp(dat) for dat in datetimes]
        week_norm = [dat[0] for dat in times]
        hour_norm = [dat[1] for dat in times]
        
        latlons = [self.normalize_latlon(self.lat, self.lon)] * len(times)
        lat_norm = [dat[0] for dat in latlons]
        lon_norm = [dat[1] for dat in latlons]
        
        num_bands = len(band_names)
        num_times = len(dates)
        pixels_data = pixels_data.reshape(num_times, num_bands, *pixels_data.shape[1:])
        pixels = torch.from_numpy(pixels_data)
        pixels = torch.stack([transform(pixels[i]) for i in range(num_times)])
        
        return {
            "platform": self.platform,
            "time": torch.tensor(np.hstack((week_norm, hour_norm)), dtype=torch.float32, device=self.device),
            "latlon": torch.tensor(np.hstack((lat_norm, lon_norm)), dtype=torch.float32, device=self.device),
            "pixels": pixels.to(self.device),
            "gsd": torch.tensor(gsd, dtype=torch.float32, device=self.device),
            "waves": torch.tensor(waves, dtype=torch.float32, device=self.device),
        }