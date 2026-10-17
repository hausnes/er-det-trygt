import asyncio
import math
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pyproj import Transformer

from .ratelimit import RateLimiter
from .routing import NoRouteError, find_route, slope_class
from .terrain import CRS, Grid, TerrainError, fetch_dem
from .water import WaterError, fetch_water_mask

# Lengste tillatne avstand i luftline mellom start og mål.
MAX_DISTANCE_M = 15_000
# Høgdemodellen blir henta med maks så mange celler langs lengste side.
MAX_GRID_CELLS = 1000
MIN_CELL_SIZE_M = 2.0

# Grenser som vernar NAS-en og Kartverket sine tenester. Kan overstyrast med miljøvariablar.
RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", 10))
RATE_LIMIT_PER_HOUR = int(os.environ.get("RATE_LIMIT_PER_HOUR", 60))
MAX_CONCURRENT_ROUTES = int(os.environ.get("MAX_CONCURRENT_ROUTES", 3))
# Kor lenge ein førespurnad ventar i kø på ledig kapasitet før han blir avvist.
QUEUE_TIMEOUT_S = 30

rate_limiter = RateLimiter([(RATE_LIMIT_PER_MINUTE, 60), (RATE_LIMIT_PER_HOUR, 3600)])
route_slots = asyncio.Semaphore(MAX_CONCURRENT_ROUTES)

to_utm = Transformer.from_crs("EPSG:4326", CRS, always_xy=True)
to_wgs = Transformer.from_crs(CRS, "EPSG:4326", always_xy=True)

app = FastAPI(title="Er det trygt?")


class Point(BaseModel):
    lat: float = Field(ge=57, le=72)
    lon: float = Field(ge=-2, le=34)


class RouteRequest(BaseModel):
    start: Point
    end: Point


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/route")
async def route(req: RouteRequest, request: Request):
    # Bak reverse proxy er dette den verkelege klient-IP-en (uvicorn --proxy-headers)
    client = request.client.host if request.client else "ukjend"
    retry_after = rate_limiter.check(client)
    if retry_after is not None:
        minutes = math.ceil(retry_after / 60)
        raise HTTPException(
            429,
            f"Du har søkt etter mange ruter på kort tid. Prøv igjen om {minutes} min.",
            headers={"Retry-After": str(math.ceil(retry_after))},
        )

    try:
        await asyncio.wait_for(route_slots.acquire(), QUEUE_TIMEOUT_S)
    except TimeoutError:
        raise HTTPException(503, "Tenesta er travel akkurat no. Prøv igjen om litt.", headers={"Retry-After": "10"})
    try:
        return await _compute_route(req)
    finally:
        route_slots.release()


async def _compute_route(req: RouteRequest) -> dict:
    sx, sy = to_utm.transform(req.start.lon, req.start.lat)
    ex, ey = to_utm.transform(req.end.lon, req.end.lat)
    distance = math.dist((sx, sy), (ex, ey))
    if distance > MAX_DISTANCE_M:
        raise HTTPException(422, f"Punkta ligg for langt frå kvarandre (maks {MAX_DISTANCE_M / 1000:.0f} km).")
    if distance < 10:
        raise HTTPException(422, "Start og mål ligg for nær kvarandre.")

    # Ta med terreng rundt punkta, slik at ruta kan gå ein omveg.
    margin = max(300.0, 0.4 * distance)
    minx, maxx = min(sx, ex) - margin, max(sx, ex) + margin
    miny, maxy = min(sy, ey) - margin, max(sy, ey) + margin
    cell_size = max(MIN_CELL_SIZE_M, math.ceil(max(maxx - minx, maxy - miny) / MAX_GRID_CELLS))

    grid = Grid.covering(minx, miny, maxx, maxy, cell_size)
    warnings: list[str] = []
    try:
        dem, water = await asyncio.gather(fetch_dem(grid), _fetch_water_or_none(grid, warnings))
    except TerrainError as e:
        raise HTTPException(502, str(e))

    try:
        # Ruteberekninga er tung reknejobb; i ein eigen tråd blokkerer ho ikkje andre førespurnader
        result = await asyncio.to_thread(find_route, dem, (sx, sy), (ex, ey), water)
    except NoRouteError as e:
        raise HTTPException(422, str(e))

    return {
        "segments": to_segments(result["points"]),
        "summary": {**result["summary"], "cell_size_m": cell_size},
        "warnings": warnings,
    }


async def _fetch_water_or_none(grid: Grid, warnings: list[str]):
    """Utan vassdata kan vi framleis rekne ut ei rute, men brukaren må få vite det."""
    try:
        return await fetch_water_mask(grid)
    except WaterError:
        warnings.append("Fekk ikkje henta vassdata, så ruta kan gå gjennom vatn.")
        return None


def to_segments(points: list[tuple[float, float, float, float]]) -> dict:
    """Deler ruta i GeoJSON-linjer der kvar linje har same hellingsklasse."""
    features = []
    current_class = None
    coords: list[list[float]] = []
    for (x0, y0, z0, s0), (x1, y1, z1, s1) in zip(points, points[1:]):
        cls = slope_class(max(s0, s1))
        lon0, lat0 = to_wgs.transform(x0, y0)
        lon1, lat1 = to_wgs.transform(x1, y1)
        if cls != current_class:
            if coords:
                features.append(_feature(coords, current_class))
            coords = [[lon0, lat0, round(z0, 1)]]
            current_class = cls
        coords.append([lon1, lat1, round(z1, 1)])
    if coords:
        features.append(_feature(coords, current_class))
    return {"type": "FeatureCollection", "features": features}


def _feature(coords: list[list[float]], cls: str) -> dict:
    return {
        "type": "Feature",
        "properties": {"slope_class": cls},
        "geometry": {"type": "LineString", "coordinates": coords},
    }


# I Docker-imaget serverer backend-en òg den ferdigbygde frontend-en. Må monterast
# etter API-rutene, elles fangar ho opp /api-kalla.
if static_dir := os.environ.get("STATIC_DIR"):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
