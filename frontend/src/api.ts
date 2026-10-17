export type SlopeClass = "slakt" | "moderat" | "bratt" | "svært bratt";

export interface LatLon {
  lat: number;
  lon: number;
}

export interface RouteResponse {
  segments: GeoJSON.FeatureCollection<GeoJSON.LineString, { slope_class: SlopeClass }>;
  summary: {
    length_m: number;
    ascent_m: number;
    descent_m: number;
    max_slope_deg: number;
    length_by_slope_class_m: Record<SlopeClass, number>;
    cell_size_m: number;
  };
}

export async function fetchRoute(start: LatLon, end: LatLon): Promise<RouteResponse> {
  let resp: Response;
  try {
    resp = await fetch("/api/route", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ start, end }),
    });
  } catch {
    throw new Error("Fekk ikkje kontakt med tenesta. Har du nettdekning?");
  }
  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    const detail = typeof body?.detail === "string" ? body.detail : "Noko gjekk gale ved ruteberekninga.";
    throw new Error(detail);
  }
  return resp.json();
}
