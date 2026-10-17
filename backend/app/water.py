"""Vassmaske (innsjøar, tjørner og breie elvar) frå Kartverket sitt N50-kart."""

import io

import httpx
import numpy as np
from skimage import io as skio

from .terrain import CRS, Grid

WMS_URL = "https://wms.geonorge.no/skwms1/wms.topo"
LAYER = "N50Vannflate"

# WMS-en teiknar berre N50-laget mellom målestokk 1:12 000 og 1:50 000. Med
# standard pikselstorleik 0,28 mm svarar det til ca. 3,4–14 m per piksel, så vi
# hentar biletet innanfor det intervallet og skalerer det til høgdemodellen.
STANDARD_PIXEL_M = 0.00028
MIN_PIXEL_M = 12_000 * STANDARD_PIXEL_M * 1.05
MAX_PIXEL_M = 50_000 * STANDARD_PIXEL_M * 0.95

# Ein piksel er vatn når han er minst halvt dekt (kantane er kantutjamna).
ALPHA_THRESHOLD = 128


class WaterError(Exception):
    pass


async def fetch_water_mask(grid: Grid) -> np.ndarray:
    """Returnerer ei boolsk maske for rutenettet, der True er vatn."""
    rows, cols = grid.rows, grid.cols
    width_m = cols * grid.cell_size
    height_m = rows * grid.cell_size
    pixel_m = min(max(grid.cell_size, MIN_PIXEL_M), MAX_PIXEL_M)
    width_px = max(1, round(width_m / pixel_m))
    height_px = max(1, round(height_m / pixel_m))

    params = {
        "service": "WMS",
        "request": "GetMap",
        "version": "1.3.0",
        "layers": LAYER,
        "styles": "",
        "crs": CRS,
        "bbox": grid.bbox,
        "width": width_px,
        "height": height_px,
        "format": "image/png",
        "transparent": "true",
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(WMS_URL, params=params)
    except httpx.HTTPError as e:
        raise WaterError(f"Fekk ikkje kontakt med Kartverket (vassdata): {e}") from e

    if resp.status_code != 200 or not resp.headers.get("content-type", "").startswith("image/png"):
        raise WaterError(f"Klarte ikkje hente vassdata frå Kartverket: {resp.text[:300]}")

    image = skio.imread(io.BytesIO(resp.content))
    if image.ndim != 3 or image.shape[2] != 4:
        raise WaterError("Uventa biletformat frå Kartverket sin vass-teneste.")
    mask = image[..., 3] >= ALPHA_THRESHOLD

    # Næraste piksel for midten av kvar celle i rutenettet
    row_idx = ((np.arange(rows) + 0.5) * height_px / rows).astype(int)
    col_idx = ((np.arange(cols) + 0.5) * width_px / cols).astype(int)
    return mask[np.ix_(row_idx, col_idx)]
