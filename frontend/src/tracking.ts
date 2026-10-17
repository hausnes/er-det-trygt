/** Geometri for å følgje med på kvar ein er i forhold til ruta. */

export type LonLat = [number, number];

export interface RouteLine {
  coords: LonLat[];
  /** Avstand langs ruta (meter) fram til kvart punkt */
  cumulative: number[];
}

export interface RoutePosition {
  /** Avstand frå posisjonen til næraste punkt på ruta (meter) */
  distanceFromRoute: number;
  /** Næraste punkt på ruta */
  nearest: LonLat;
  /** Avstand langs ruta att til mål (meter) */
  remaining: number;
}

const EARTH_RADIUS_M = 6_371_000;
const toRad = (deg: number) => (deg * Math.PI) / 180;

/** Avstand i meter mellom to punkt. Flat tilnærming, som er nøyaktig nok på nokre kilometer. */
export function distance(a: LonLat, b: LonLat): number {
  const [x, y] = toLocalMeters(b, a);
  return Math.hypot(x, y);
}

/** Punkt `p` i meter (aust, nord) relativt til `origin`. */
function toLocalMeters(p: LonLat, origin: LonLat): [number, number] {
  const x = toRad(p[0] - origin[0]) * EARTH_RADIUS_M * Math.cos(toRad(origin[1]));
  const y = toRad(p[1] - origin[1]) * EARTH_RADIUS_M;
  return [x, y];
}

/** Slår saman rutesegmenta (som deler endepunkt) til éi samanhengande line. */
export function buildRouteLine(segments: LonLat[][]): RouteLine {
  const coords: LonLat[] = [];
  for (const seg of segments) {
    for (const [lon, lat] of seg) {
      const last = coords[coords.length - 1];
      if (!last || last[0] !== lon || last[1] !== lat) coords.push([lon, lat]);
    }
  }
  const cumulative = [0];
  for (let i = 1; i < coords.length; i++) cumulative.push(cumulative[i - 1] + distance(coords[i - 1], coords[i]));
  return { coords, cumulative };
}

/** Finn næraste punkt på ruta og kor langt det er att til mål derifrå. */
export function locateOnRoute(route: RouteLine, position: LonLat): RoutePosition {
  const { coords, cumulative } = route;
  let best: RoutePosition = {
    distanceFromRoute: distance(position, coords[0]),
    nearest: coords[0],
    remaining: cumulative[cumulative.length - 1],
  };
  const total = cumulative[cumulative.length - 1];

  for (let i = 0; i < coords.length - 1; i++) {
    // Projiser posisjonen ned på linjestykket i lokale meter med `position` som origo
    const [ax, ay] = toLocalMeters(coords[i], position);
    const [bx, by] = toLocalMeters(coords[i + 1], position);
    const dx = bx - ax;
    const dy = by - ay;
    const lengthSq = dx * dx + dy * dy;
    const t = lengthSq === 0 ? 0 : Math.min(1, Math.max(0, -(ax * dx + ay * dy) / lengthSq));
    const px = ax + t * dx;
    const py = ay + t * dy;
    const d = Math.hypot(px, py);
    if (d < best.distanceFromRoute) {
      const [lon0, lat0] = coords[i];
      const [lon1, lat1] = coords[i + 1];
      best = {
        distanceFromRoute: d,
        nearest: [lon0 + t * (lon1 - lon0), lat0 + t * (lat1 - lat0)],
        remaining: total - (cumulative[i] + t * (cumulative[i + 1] - cumulative[i])),
      };
    }
  }
  return best;
}
