import numpy as np
import rasterio
from rasterio.windows import from_bounds
from pyproj import Transformer
from typing import Dict, List



def calculate_bbox_ndvi(
        red_url: str,
        nir_url: str,
        bbox: List[float]
) -> Dict[str, float]:
    """
    Streams bounding box pixels from remote Red and NIR COGs over HTTP,
    calculates NDVI array, and returns summary metrics.
    
    bbox format: [min_lon, min_lat, max_lon, max_lat] (EPSG:4326)
    """
    min_lon, min_lat, max_lon, max_lat = bbox

    # Reporject lat/lon bbox to CRS coordinates
    with rasterio.open(red_url) as red_data:
        transformer = Transformer.from_crs("EPSG:4326", red_data.crs, always_xy=True)
        utm_min_x, utm_min_y = transformer.transform(min_lon, min_lat)
        utm_max_x, utm_max_y = transformer.transform(max_lon, max_lat)

        # Build a pixel window corresponding to bounding box coordinates
        pixel_window = from_bounds(
            utm_min_x, utm_min_y, utm_max_x, utm_max_y, 
            transform=red_data.transform
        )

        # Stream pixel sub-region array into memory
        red_array = red_data.read(1, window=pixel_window).astype(np.float32)

        with rasterio.open(nir_url) as nir_data:
            nir_array = nir_data.read(1, window=pixel_window).astype(np.float32)

        # 5. Handle zero division and calculate NDVI array
        # NDVI = (NIR - Red) / (NIR + Red)
        numerator = nir_array - red_array
        denominator = nir_array + red_array

        # Prevent division by zero for invalid/masked pixels
        with np.errstate(divide='ignore', invalid='ignore'):
            ndvi_array = np.where(denominator == 0, np.nan, numerator / denominator)

        valid_ndvi = ndvi_array[~np.isnan(ndvi_array)]

        if valid_ndvi.size == 0:
            raise ValueError("No valid pixel data found within target bounding box.")

        return {
            "mean_ndvi": round(float(np.mean(valid_ndvi)), 3),
            "max_ndvi": round(float(np.max(valid_ndvi)), 3),
            "min_ndvi": round(float(np.min(valid_ndvi)), 3),
            "pixel_count": int(valid_ndvi.size),
            "data": ndvi_array
        }