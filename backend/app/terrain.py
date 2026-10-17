"""Henting av terrengmodell (DTM) frå Kartverket sine høgdedata (hoydedata.no)."""

from dataclasses import dataclass
import io

import httpx
import numpy as np
import tifffile

WCS_URL = "https://wcs.geonorge.no/skwms1/wcs.hoyde-dtm-nhm-25833"
COVERAGE = "nhm_dtm_topo_25833"
CRS = "EPSG:25833"  # UTM sone 33N, som Kartverket brukar for heile landet

# Høgder under dette (moh.) blir rekna som hav, der WCS-en returnerer ~0.
SEA_LEVEL_THRESHOLD = 0.5


@dataclass
class Dem:
    """Eit utsnitt av terrengmodellen i EPSG:25833."""

    elevation: np.ndarray  # [rad, kolonne], NaN der det manglar data
    left: float  # x for venstre kant
    top: float  # y for øvre kant
    cell_size: float  # meter per celle

    def to_cell(self, x: float, y: float) -> tuple[int, int]:
        col = int((x - self.left) / self.cell_size)
        row = int((self.top - y) / self.cell_size)
        return row, col

    def to_xy(self, row: int, col: int) -> tuple[float, float]:
        x = self.left + (col + 0.5) * self.cell_size
        y = self.top - (row + 0.5) * self.cell_size
        return x, y


@dataclass
class Grid:
    """Eit rutenett med kvadratiske celler i EPSG:25833, som alle datalag blir henta i."""

    left: float
    top: float
    cell_size: float
    rows: int
    cols: int

    @classmethod
    def covering(cls, minx: float, miny: float, maxx: float, maxy: float, cell_size: float) -> "Grid":
        cols = max(1, round((maxx - minx) / cell_size))
        rows = max(1, round((maxy - miny) / cell_size))
        return cls(left=minx, top=miny + rows * cell_size, cell_size=cell_size, rows=rows, cols=cols)

    @property
    def bbox(self) -> str:
        bottom = self.top - self.rows * self.cell_size
        right = self.left + self.cols * self.cell_size
        return f"{self.left},{bottom},{right},{self.top}"


class TerrainError(Exception):
    pass


async def fetch_dem(grid: Grid) -> Dem:
    """Hentar DTM for rutenettet."""
    params = {
        "service": "WCS",
        "request": "GetCoverage",
        "version": "1.0.0",
        "coverage": COVERAGE,
        "crs": CRS,
        "bbox": grid.bbox,
        "width": grid.cols,
        "height": grid.rows,
        "format": "GeoTIFF",
        "interpolation": "bilinear",
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(WCS_URL, params=params)
    except httpx.HTTPError as e:
        raise TerrainError(f"Fekk ikkje kontakt med Kartverket (høgdedata): {e}") from e

    if resp.status_code != 200 or "tiff" not in resp.headers.get("content-type", ""):
        raise TerrainError(f"Klarte ikkje hente høgdedata frå Kartverket: {resp.text[:300]}")

    elevation = tifffile.imread(io.BytesIO(resp.content)).astype(np.float32)
    elevation[elevation < SEA_LEVEL_THRESHOLD] = np.nan
    return Dem(elevation=elevation, left=grid.left, top=grid.top, cell_size=grid.cell_size)
