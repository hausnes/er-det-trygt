"""Ruteberekning: finn vegen med lågast «kostnad», der bratt terreng kostar mykje."""

import math

import numpy as np
from scipy import ndimage
from skimage.graph import MCP_Geometric

from .terrain import Dem

# Terreng brattare enn dette (grader) blir rekna som ufarbart.
MAX_SLOPE_DEG = 45.0
# Ligg start eller mål i ufarbart terreng, blir det flytta til næraste farbare punkt innanfor denne avstanden.
SNAP_RADIUS_M = 30.0

# Hellingsklassar for visning, inspirert av NVE sine bratthetskart.
SLOPE_CLASSES = [
    (20.0, "slakt"),
    (30.0, "moderat"),
    (35.0, "bratt"),
    (math.inf, "svært bratt"),
]


class NoRouteError(Exception):
    pass


def slope_degrees(dem: Dem) -> np.ndarray:
    """Helling i grader for kvar celle."""
    filled = np.where(np.isnan(dem.elevation), np.nanmean(dem.elevation), dem.elevation)
    dy, dx = np.gradient(filled, dem.cell_size)
    slope = np.degrees(np.arctan(np.hypot(dx, dy)))
    slope[np.isnan(dem.elevation)] = np.nan
    return slope


def cost_surface(slope: np.ndarray, water: np.ndarray | None = None) -> np.ndarray:
    """Kostnad per meter for å gå gjennom kvar celle.

    Kostnaden veks kraftig med hellinga (1 på flatmark, ~6 ved 30°, ~17 ved 40°).
    Celler brattare enn MAX_SLOPE_DEG, og nabocellene deira, er ufarbare – det
    held ruta unna stupkantar. Vatn er ufarbart, men ein kan gå langs strandkanten.
    """
    surface = 1.0 / np.cos(np.radians(np.nan_to_num(slope)))
    penalty = 1.0 + (np.nan_to_num(slope) / 20.0) ** 4
    cost = surface * penalty

    impassable = np.isnan(slope) | (slope > MAX_SLOPE_DEG)
    impassable = ndimage.binary_dilation(impassable, iterations=1)
    if water is not None:
        impassable |= water
    cost[impassable] = np.inf
    return cost


def slope_class(deg: float) -> str:
    for limit, name in SLOPE_CLASSES:
        if deg < limit:
            return name
    return SLOPE_CLASSES[-1][1]


def find_route(
    dem: Dem,
    start_xy: tuple[float, float],
    end_xy: tuple[float, float],
    water: np.ndarray | None = None,
) -> dict:
    """Returnerer ruta som liste med punkt (x, y, høgd, helling) og ei oppsummering.

    `water` er ei boolsk maske i same rutenett som `dem`, der True er vatn.
    """
    slope = slope_degrees(dem)
    cost = cost_surface(slope, water)

    start = _nearest_passable(cost, dem.to_cell(*start_xy), dem.cell_size, "Startpunktet")
    end = _nearest_passable(cost, dem.to_cell(*end_xy), dem.cell_size, "Sluttpunktet")

    mcp = MCP_Geometric(cost, fully_connected=True)
    cumulative, _ = mcp.find_costs([start], [end])
    if not np.isfinite(cumulative[end]):
        raise NoRouteError(
            f"Fann inga rute mellom punkta utan å krysse vatn eller terreng brattare enn {MAX_SLOPE_DEG:.0f}°."
        )
    cells = mcp.traceback(end)

    points = []
    for row, col in cells:
        x, y = dem.to_xy(row, col)
        points.append((x, y, float(dem.elevation[row, col]), float(slope[row, col])))

    return {"points": points, "summary": summarize(points)}


def _nearest_passable(cost: np.ndarray, cell: tuple[int, int], cell_size: float, name: str) -> tuple[int, int]:
    """Flyttar punktet til næraste farbare celle, slik at t.d. ein spiss topp ikkje blir avvist."""
    if np.isfinite(cost[cell]):
        return cell
    radius = math.ceil(SNAP_RADIUS_M / cell_size)
    row, col = cell
    r0, c0 = max(row - radius, 0), max(col - radius, 0)
    window = cost[r0 : row + radius + 1, c0 : col + radius + 1]
    rows, cols = np.nonzero(np.isfinite(window))
    if len(rows) == 0:
        raise NoRouteError(
            f"{name} ligg i vatn, i terreng som er for bratt (over {MAX_SLOPE_DEG:.0f}°) "
            "eller utan høgdedata. Prøv å flytte det litt."
        )
    i = np.argmin((rows + r0 - row) ** 2 + (cols + c0 - col) ** 2)
    return int(rows[i] + r0), int(cols[i] + c0)


def summarize(points: list[tuple[float, float, float, float]]) -> dict:
    length = ascent = descent = 0.0
    length_by_class = {name: 0.0 for _, name in SLOPE_CLASSES}
    for (x0, y0, z0, s0), (x1, y1, z1, s1) in zip(points, points[1:]):
        seg = math.dist((x0, y0, z0), (x1, y1, z1))
        length += seg
        dz = z1 - z0
        ascent += max(dz, 0)
        descent += max(-dz, 0)
        length_by_class[slope_class(max(s0, s1))] += seg

    return {
        "length_m": round(length),
        "ascent_m": round(ascent),
        "descent_m": round(descent),
        "max_slope_deg": round(max(p[3] for p in points), 1),
        "length_by_slope_class_m": {k: round(v) for k, v in length_by_class.items()},
    }
