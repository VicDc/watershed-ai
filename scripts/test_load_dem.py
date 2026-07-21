import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ingestion.public_dem import load_dem_from_geotiff

dem = load_dem_from_geotiff("data/dem/copernicus_glo30_test.tif")
print(dem.elevation.shape)
print(dem.elevation.min(), dem.elevation.max())
print(dem.cell_size_m)
print(dem.quality_flags)