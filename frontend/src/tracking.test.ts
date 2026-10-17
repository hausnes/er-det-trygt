import { describe, expect, it } from "vitest";
import { buildRouteLine, distance, locateOnRoute, type LonLat } from "./tracking";

// Ei rute rett austover, ca. 1 km lang, på 62° nord
const west: LonLat = [7.8, 62.0];
const middle: LonLat = [7.8095, 62.0];
const east: LonLat = [7.819, 62.0];

describe("buildRouteLine", () => {
  it("slår saman segment med felles endepunkt og reknar ut lengda", () => {
    const route = buildRouteLine([[west, middle], [middle, east]]);
    expect(route.coords).toEqual([west, middle, east]);
    expect(route.cumulative.at(-1)).toBeCloseTo(distance(west, east), 3);
    expect(distance(west, east)).toBeGreaterThan(990);
    expect(distance(west, east)).toBeLessThan(1000);
  });
});

describe("locateOnRoute", () => {
  const route = buildRouteLine([[west, middle], [middle, east]]);
  const total = route.cumulative.at(-1)!;

  it("gjev 0 m frå ruta når ein står på ho", () => {
    const pos = locateOnRoute(route, middle);
    expect(pos.distanceFromRoute).toBeLessThan(0.01);
    expect(pos.remaining).toBeCloseTo(total / 2, 0);
  });

  it("måler avstanden vinkelrett ut frå ruta", () => {
    const north: LonLat = [7.805, 62.0 + 50 / 111_195]; // ca. 50 m nord for ruta
    const pos = locateOnRoute(route, north);
    expect(pos.distanceFromRoute).toBeCloseTo(50, 0);
    expect(pos.nearest[1]).toBeCloseTo(62.0, 6);
  });

  it("brukar endepunktet når ein er forbi målet", () => {
    const beyond: LonLat = [7.825, 62.0];
    const pos = locateOnRoute(route, beyond);
    expect(pos.remaining).toBeCloseTo(0, 3);
    expect(pos.nearest).toEqual(east);
  });
});
