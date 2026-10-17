import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, LngLat } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import "./style.css";
import { fetchRoute, type RouteResponse, type SlopeClass } from "./api";

type Target = "start" | "end";

const SLOPE_COLORS: Record<SlopeClass, string> = {
  slakt: "#2e9e4f",
  moderat: "#e3b505",
  bratt: "#ef7d1a",
  "svært bratt": "#d62828",
};
const SLOPE_LABELS: Record<SlopeClass, string> = {
  slakt: "Slakt (under 20°)",
  moderat: "Moderat (20–30°)",
  bratt: "Bratt (30–35°)",
  "svært bratt": "Svært bratt (over 35°)",
};

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const pickStart = $<HTMLButtonElement>("pick-start");
const pickEnd = $<HTMLButtonElement>("pick-end");
const useGps = $<HTMLButtonElement>("use-gps");
const findRouteBtn = $<HTMLButtonElement>("find-route");
const resetBtn = $<HTMLButtonElement>("reset");
const statusEl = $<HTMLParagraphElement>("status");
const summaryEl = $<HTMLDivElement>("summary");

// MapLibre finn elles workeren relativt til si eiga fil, men Vite flyttar MapLibre ved
// pakking utan å ta med workeren. Utan worker blir GeoJSON (ruta) aldri teikna.
maplibregl.setWorkerUrl(maplibreWorkerUrl);

const map = new maplibregl.Map({
  container: "map",
  center: [8.5, 61.6],
  zoom: 6,
  style: {
    version: 8,
    sources: {
      topo: {
        type: "raster",
        tiles: ["https://cache.kartverket.no/v1/wmts/1.0.0/topo/default/webmercator/{z}/{y}/{x}.png"],
        tileSize: 256,
        maxzoom: 18,
        attribution: '© <a href="https://www.kartverket.no/">Kartverket</a>',
      },
    },
    layers: [{ id: "topo", type: "raster", source: "topo" }],
  },
});
map.addControl(new maplibregl.NavigationControl(), "top-right");
map.addControl(
  new maplibregl.GeolocateControl({ positionOptions: { enableHighAccuracy: true }, trackUserLocation: true }),
  "top-right",
);
map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");

map.on("load", () => {
  map.addSource("route", { type: "geojson", data: emptyRoute() });
  map.addLayer({
    id: "route-casing",
    type: "line",
    source: "route",
    layout: { "line-join": "round", "line-cap": "round" },
    paint: { "line-color": "#ffffff", "line-width": 8 },
  });
  map.addLayer({
    id: "route",
    type: "line",
    source: "route",
    layout: { "line-join": "round", "line-cap": "round" },
    paint: {
      "line-width": 5,
      "line-color": [
        "match",
        ["get", "slope_class"],
        "slakt", SLOPE_COLORS.slakt,
        "moderat", SLOPE_COLORS.moderat,
        "bratt", SLOPE_COLORS.bratt,
        "svært bratt", SLOPE_COLORS["svært bratt"],
        "#555555",
      ],
    },
  });
});

// --- Start- og målpunkt ---

const markers: Record<Target, maplibregl.Marker | null> = { start: null, end: null };
let picking: Target | null = "start";

function setPoint(target: Target, lngLat: LngLat | [number, number]) {
  if (!markers[target]) {
    const el = document.createElement("div");
    el.className = `marker ${target}`;
    const marker = new maplibregl.Marker({ element: el, draggable: true }).setLngLat(lngLat).addTo(map);
    marker.on("dragend", clearRoute);
    markers[target] = marker;
  } else {
    markers[target]!.setLngLat(lngLat);
  }
  clearRoute();
  // Etter at start er sett, går vi automatisk vidare til å velje mål
  setPicking(target === "start" && !markers.end ? "end" : null);
  updateButtons();
}

function setPicking(target: Target | null) {
  picking = target;
  pickStart.classList.toggle("active", picking === "start");
  pickEnd.classList.toggle("active", picking === "end");
  map.getCanvas().style.cursor = picking ? "crosshair" : "";
  if (picking) setStatus(picking === "start" ? "Trykk på kartet der du startar." : "Trykk på kartet der du vil ende opp.");
}

function updateButtons() {
  pickStart.querySelector(".label")!.textContent = markers.start ? "Flytt start" : "Vel start";
  pickEnd.querySelector(".label")!.textContent = markers.end ? "Flytt mål" : "Vel mål";
  findRouteBtn.disabled = !(markers.start && markers.end);
}

map.on("click", (e) => {
  if (picking) setPoint(picking, e.lngLat);
});

pickStart.addEventListener("click", () => setPicking(picking === "start" ? null : "start"));
pickEnd.addEventListener("click", () => setPicking(picking === "end" ? null : "end"));

useGps.addEventListener("click", () => {
  if (!("geolocation" in navigator)) return setStatus("Nettlesaren din støttar ikkje GPS-posisjon.", true);
  setStatus("Hentar posisjonen din …");
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const lngLat: [number, number] = [pos.coords.longitude, pos.coords.latitude];
      setPoint("start", lngLat);
      map.flyTo({ center: lngLat, zoom: Math.max(map.getZoom(), 14) });
      if (pos.coords.accuracy > 50) setStatus(`Posisjonen er unøyaktig (±${Math.round(pos.coords.accuracy)} m).`, true);
    },
    (err) => setStatus(`Fekk ikkje tak i posisjonen: ${err.message}`, true),
    { enableHighAccuracy: true, timeout: 15000 },
  );
});

resetBtn.addEventListener("click", () => {
  markers.start?.remove();
  markers.end?.remove();
  markers.start = markers.end = null;
  clearRoute();
  updateButtons();
  setPicking("start");
});

// --- Ruteberekning ---

findRouteBtn.addEventListener("click", async () => {
  if (!markers.start || !markers.end) return;
  const start = markers.start.getLngLat();
  const end = markers.end.getLngLat();
  findRouteBtn.disabled = true;
  setPicking(null);
  setStatus("Hentar høgdedata og reknar ut rute …");
  try {
    const route = await fetchRoute({ lat: start.lat, lon: start.lng }, { lat: end.lat, lon: end.lng });
    (map.getSource("route") as GeoJSONSource).setData(route.segments);
    fitToRoute(route);
    showSummary(route);
    setStatus("");
  } catch (e) {
    setStatus((e as Error).message, true);
  } finally {
    updateButtons();
  }
});

function fitToRoute(route: RouteResponse) {
  const bounds = new maplibregl.LngLatBounds();
  for (const f of route.segments.features) for (const [lon, lat] of f.geometry.coordinates) bounds.extend([lon, lat]);
  map.fitBounds(bounds, { padding: { top: 60, bottom: 60 + summaryOverlap(), left: 40, right: 40 }, maxZoom: 16 });
}

function summaryOverlap() {
  // På mobil ligg panelet over nedre del av kartet
  return window.matchMedia("(max-width: 700px)").matches ? $("panel").offsetHeight : 0;
}

function showSummary(route: RouteResponse) {
  const s = route.summary;
  const rows = (Object.keys(SLOPE_LABELS) as SlopeClass[])
    .filter((c) => s.length_by_slope_class_m[c] > 0)
    .map(
      (c) =>
        `<li><span class="swatch" style="background:${SLOPE_COLORS[c]}"></span>${SLOPE_LABELS[c]}<span class="num">${formatDistance(s.length_by_slope_class_m[c])}</span></li>`,
    )
    .join("");
  summaryEl.innerHTML = `
    <dl>
      <div><dt>Lengd</dt><dd>${formatDistance(s.length_m)}</dd></div>
      <div><dt>Opp</dt><dd>${s.ascent_m} m</dd></div>
      <div><dt>Ned</dt><dd>${s.descent_m} m</dd></div>
      <div><dt>Brattast</dt><dd>${s.max_slope_deg}°</dd></div>
    </dl>
    <ul class="slopes">${rows}</ul>
    <p class="note">Rekna ut med høgdedata i ${s.cell_size_m} × ${s.cell_size_m} m rutenett.</p>`;
  summaryEl.hidden = false;
}

function clearRoute() {
  (map.getSource("route") as GeoJSONSource | undefined)?.setData(emptyRoute());
  summaryEl.hidden = true;
}

function emptyRoute(): GeoJSON.FeatureCollection {
  return { type: "FeatureCollection", features: [] };
}

function formatDistance(m: number) {
  return m >= 1000 ? `${(m / 1000).toFixed(1).replace(".", ",")} km` : `${m} m`;
}

function setStatus(text: string, isError = false) {
  statusEl.textContent = text;
  statusEl.classList.toggle("error", isError);
}

setPicking("start");
updateButtons();
