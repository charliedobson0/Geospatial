from typing import Annotated, List, Optional
from fastapi import FastAPI, Query, HTTPException, Response
from pydantic import BaseModel, Field
from pystac_client import Client
from service import calculate_bbox_ndvi
from visualization import generate_heatmap



app = FastAPI(title="STAC API Client Example", description="A simple FastAPI app to query STAC API for Sentinel-2 imagery.", version="1.0.0")

STAC_API_URL = "https://earth-search.aws.element84.com/v1"
TIME_RANGE = "2026-06-01/2026-08-31"      


client = Client.open(STAC_API_URL)

# Define a Pydantic model for the bounding box to validate input parameters
class BoundingBox(BaseModel):
    min_lon: float = Field(..., ge=-180, le=180, description="Minimum longitude of the bounding box.")
    min_lat: float = Field(..., ge=-90, le=90, description="Minimum latitude of the bounding box.")
    max_lon: float = Field(..., ge=-180, le=180, description="Maximum longitude of the bounding box.")
    max_lat: float = Field(..., ge=-90, le=90, description="Maximum latitude of the bounding box.")

    def to_list(self) -> List[float]:
        return [self.min_lon, self.min_lat, self.max_lon, self.max_lat]

class SceneMetadata(BaseModel):
    id: str
    datetime: str
    cloud_cover: float
    grid_code: Optional[str] = None
    red_band_url: str
    nir_band_url: str

def fetch_latest_scene(bbox: List[float], collection: str = "sentinel-2-c1-l2a") -> SceneMetadata:
    """
    Connects to STAC, finds scenes, and extracts metadata + COG URLs for the newest image.    
    """
    try: 
        client = Client.open(STAC_API_URL)
        search = client.search(
            collections=[collection],
            bbox=bbox,
            max_items=1,
            sortby=[{
                "field": "properties.datetime", 
                "direction": "desc"
            }],
            query=["eo:cloud_cover<10"]
        )

        items = list(search.items())
        if not items:
            return None

        latest_item = items[0]

        red_asset = latest_item.assets.get("red") or latest_item.assets.get("BO4")
        nir_asset = latest_item.assets.get("nir") or latest_item.assets.get("BO8")

        if not red_asset or not nir_asset:
            raise ValueError("Selected scene is missing required Red or NIR spectral assets.")

        return SceneMetadata(
            id=latest_item.id,
            datetime=str(latest_item.datetime),
            cloud_cover=round(latest_item.properties.get("eo:cloud_cover", 0.0), 2),
            grid_code=latest_item.properties.get("grid:code"),
            red_band_url=red_asset.href,
            nir_band_url=nir_asset.href
        )

    except Exception as e:
        raise RuntimeError(f"STAC API query failed: {str(e)}")

# Define my fastAPI endpoint
@app.get("/stac/latest-scene", response_model=SceneMetadata)
async def get_latest_scene(
    min_lon: float = Query(..., ge=-180.0, le=180.0, example=-77.12),
    min_lat: float = Query(..., ge=-90.0, le=90.0, example=38.80),
    max_lon: float = Query(..., ge=-180.0, le=180.0, example=-76.90),
    max_lat: float = Query(..., ge=-90.0, le=90.0, example=38.99),
    max_cloud_cover: float = Query(10.0, ge=0.0, le=100.0, description="Max cloud cover percentage")
):
    """
    Accepts bounding box coordinates via query parameters and returns total 
    matching Sentinel-2 scenes from Earth Search.
    """
    if min_lon >= max_lon or min_lat >= max_lat:
        raise HTTPException(
            status_code=400,
            detaul="Invalid bounding box"
        )

    bbox = BoundingBox(
        min_lon=min_lon,
        min_lat=min_lat,
        max_lon=max_lon,
        max_lat=max_lat
    )

    try:
        scene = fetch_latest_scene(bbox=bbox.to_list())
        if not scene:
            raise HTTPException(status_code=444, detail="No matching scenes found for bounding box")

        print(scene.id)
        return scene
    except Exception as err:
        raise HTTPException(status_code=502, detail=f"STAC API service error: {str(err)}")

@app.get("/stac/ndvi")
async def get_bounding_box_ndvi(
    min_lon: float = Query(-77.12, ge=-180.0, le=180.0),
    min_lat: float = Query(38.80, ge=-90.0, le=90.0),
    max_lon: float = Query(-76.90, ge=-180.0, le=180.0),
    max_lat: float = Query(38.99, ge=-90.0, le=90.0),
    max_cloud_cover: float = Query(10.0, ge=0.0, le=100.0)
):
    bbox = [min_lon, min_lat, max_lon, max_lat]

    # Use helper to fetch scene metadata
    scene = fetch_latest_scene(bbox)

    if not scene:
        raise HTTPException(status_code=404, detail="No low-cloud scene found.")

    ndvi_results = calculate_bbox_ndvi(scene.red_band_url, scene.nir_band_url, bbox)

    return {
        "scene_id": scene.id,
        "capture_date": scene.datetime,
        "cloud_cover_pct": scene.cloud_cover,
        "metrics": ndvi_results
    }

@app.get("/stac/ndvi/heatmap")
async def get_ndvi_heatmap(
    min_lon: float = Query(-78.0, ge=-180.0, le=180.0),
    min_lat: float = Query(38.7, ge=-90.0, le=90.0),
    max_lon: float = Query(-76.0, ge=-180.0, le=180.0),
    max_lat: float = Query(39.4, ge=-90.0, le=90.0),
    max_cloud_cover: float = Query(10.0, ge=0.0, le=100.0),
    colormap: str = Query("RdYlGn", description="Build in Matplotlib colormap")
):
    bbox = [min_lon, min_lat, max_lon, max_lat]

    # Use helper to fetch scene metadata
    scene = fetch_latest_scene(bbox)

    ndvi_results = calculate_bbox_ndvi(scene.red_band_url, scene.nir_band_url, bbox)


    png_bytes = generate_heatmap(ndvi_results.get("data"), colormap=colormap)

    return Response(content=png_bytes, media_type="image/png")
    





# Bounding box format: [min_lon, min_lat, max_lon, max_lat]
# bbox_dc = [-77.12, 38.80, -76.90, 38.99]  # Arlington / DC area
# time_range = "2026-06-01/2026-08-31"      # Summer 2026

# # 3. Execute the STAC Item Search
# search = client.search(
#     collections=["sentinel-2-c1-l2a"],    # Sentinel-2 Collection
#     bbox=bbox_dc,
#     datetime=time_range,
#     query=["eo:cloud_cover<10"],          # Filter scenes with <10% clouds
#     max_items=5                           # Limit results for testing
# )

# # Check total matched items
# print(f"Total matching scenes found: {search.matched()}")


# red_asset = item.assets.get("red") or item.assets.get("B04")
#     nir_asset = item.assets.get("nir") or item.assets.get("B08")
    
#     if red_asset and nir_asset:
#         print("\nDirect COG Asset URLs:")
#         print(f" -> Red Band (B04) : {red_asset.href}")
#         print(f" -> NIR Band (B08) : {nir_asset.href}")