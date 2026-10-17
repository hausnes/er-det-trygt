import numpy as np
import pytest

from app.routing import NoRouteError, find_route
from app.terrain import Dem


def make_dem(elevation: np.ndarray, cell_size: float = 5.0) -> Dem:
    return Dem(elevation=elevation.astype(np.float32), left=0.0, top=elevation.shape[0] * cell_size, cell_size=cell_size)


def xy(dem: Dem, row: int, col: int) -> tuple[float, float]:
    return dem.to_xy(row, col)


def test_flat_terrain_gives_straight_route():
    dem = make_dem(np.full((50, 50), 100.0))
    result = find_route(dem, xy(dem, 25, 5), xy(dem, 25, 45))
    assert result["summary"]["length_m"] == pytest.approx(200, abs=1)
    assert result["summary"]["max_slope_deg"] == 0


def test_route_goes_around_cliff_through_gap():
    # Eit 50 m høgt stup tvers over området, med ei renne (ca. 27°) ved kolonne 38–47
    elevation = np.full((60, 60), 100.0)
    elevation[:30, :] = 150.0
    for i, row in enumerate(range(20, 40)):
        elevation[row, 38:48] = 150.0 - i * 2.5
    dem = make_dem(elevation)

    result = find_route(dem, xy(dem, 5, 10), xy(dem, 55, 10))
    assert result["summary"]["max_slope_deg"] < 45
    cells = [dem.to_cell(x, y) for x, y, *_ in result["points"]]
    assert all(38 <= col < 48 for row, col in cells if row == 30)


def test_no_route_when_cliff_blocks_everything():
    elevation = np.full((60, 60), 100.0)
    elevation[:30, :] = 150.0
    dem = make_dem(elevation)
    with pytest.raises(NoRouteError):
        find_route(dem, xy(dem, 5, 10), xy(dem, 55, 10))


def test_start_on_steep_cell_snaps_to_nearby_passable_cell():
    elevation = np.full((50, 50), 100.0)
    elevation[24:27, 4:7] = 130.0  # liten, bratt knaus der startpunktet ligg
    dem = make_dem(elevation)
    result = find_route(dem, xy(dem, 25, 5), xy(dem, 25, 45))
    assert result["points"]


def test_route_goes_around_lake():
    dem = make_dem(np.full((60, 60), 100.0))
    water = np.zeros((60, 60), dtype=bool)
    water[10:50, 20:40] = True  # flatt vatn rett mellom start og mål
    result = find_route(dem, xy(dem, 30, 5), xy(dem, 30, 55), water)

    cells = [dem.to_cell(x, y) for x, y, *_ in result["points"]]
    assert not any(water[cell] for cell in cells)
    # Omvegen rundt vatnet er lengre enn luftlina på 250 m
    assert result["summary"]["length_m"] > 300


def test_end_point_far_out_in_lake_gives_error():
    dem = make_dem(np.full((60, 60), 100.0))
    water = np.zeros((60, 60), dtype=bool)
    water[10:50, 20:50] = True
    with pytest.raises(NoRouteError, match="vatn"):
        find_route(dem, xy(dem, 30, 5), xy(dem, 30, 35), water)
