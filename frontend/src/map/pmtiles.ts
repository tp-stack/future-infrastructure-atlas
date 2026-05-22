import { Protocol } from "pmtiles";
import maplibregl from "maplibre-gl";
import { getLightTopoLayers, getLightTopoSources, MAPLIBRE_GLYPHS_URL } from "./basemaps";
import { CABLE_COLOR, DATA_CENTER_COLOR, DATA_CENTER_STROKE_COLOR, FUEL_COLORS, POWER_CABLE_COLOR, POWER_CABLE_HVDC_COLOR, POWER_LINE_DEFAULT_COLOR, POWER_LINE_HVDC_COLOR, SUBSTATION_COLOR, SUBSTATION_STROKE_COLOR } from "./layers";

let registered = false;

export function registerPMTilesProtocol(): void {
  if (registered) return;
  const protocol = new Protocol();
  maplibregl.addProtocol("pmtiles", protocol.tile);
  registered = true;
}

export interface TileStatus {
  power_plants: "present" | "missing" | "unknown";
  submarine_cables: "present" | "missing" | "unknown";
  data_centers: "present" | "missing" | "unknown";
  power_lines: "present" | "missing" | "unknown";
  substations: "present" | "missing" | "unknown";
}

export type TileRegistry = Record<string, { url?: string; status?: string; layer_name?: string } | undefined>;

const FALLBACK_TILE_URLS: Record<keyof TileStatus, string> = {
  power_plants: "pmtiles:///tiles/power_plants.pmtiles",
  submarine_cables: "pmtiles:///tiles/submarine_cables.pmtiles",
  data_centers: "pmtiles:///tiles/data_centers.pmtiles",
  power_lines: "pmtiles:///tiles/power_lines.pmtiles",
  substations: "pmtiles:///tiles/substations.pmtiles",
};

function normalizePMTilesUrl(url: string | undefined, fallback: string): string {
  const raw = (url || fallback).trim();
  if (!raw) return "";
  if (raw.startsWith("pmtiles://")) return raw;
  if (raw.startsWith("https://")) return `pmtiles://${raw}`;
  if (raw.startsWith("/")) return `pmtiles://${raw}`;
  return raw;
}

function sourceSpecFor(
  key: keyof TileStatus,
  tileStatus: TileStatus,
  tileRegistry?: TileRegistry
): maplibregl.SourceSpecification | null {
  if (tileStatus[key] !== "present") return null;
  const url = normalizePMTilesUrl(tileRegistry?.[key]?.url, FALLBACK_TILE_URLS[key]);
  if (!url) return null;
  return { type: "vector", url };
}

function powerLineColorExpression(): maplibregl.ExpressionSpecification {
  return [
    "case",
    ["==", ["get", "type"], "HVDC"],
    POWER_LINE_HVDC_COLOR,
    [">=", ["coalesce", ["get", "voltage"], 0], 380],
    "#d45050",
    [">=", ["coalesce", ["get", "voltage"], 0], 220],
    "#d69a13",
    [">=", ["coalesce", ["get", "voltage"], 0], 110],
    "#2f6b4f",
    [">=", ["coalesce", ["get", "voltage"], 0], 45],
    "#087ea4",
    [">", ["coalesce", ["get", "voltage"], 0], 0],
    "#8d93a1",
    POWER_LINE_DEFAULT_COLOR,
  ] as maplibregl.ExpressionSpecification;
}

export const POWER_CABLE_FILTER: maplibregl.FilterSpecification = [
  "any",
  ["==", ["get", "power"], "cable"],
  ["==", ["get", "underground"], true],
  ["==", ["get", "underground"], "true"],
  ["==", ["get", "underground"], 1],
];

export const POWER_OVERHEAD_FILTER: maplibregl.FilterSpecification = ["!", POWER_CABLE_FILTER];

function powerCableColorExpression(): maplibregl.ExpressionSpecification {
  return [
    "case",
    ["==", ["get", "type"], "HVDC"],
    POWER_CABLE_HVDC_COLOR,
    POWER_CABLE_COLOR,
  ] as maplibregl.ExpressionSpecification;
}

export function getPMTilesSources(
  tileStatus: TileStatus,
  tileRegistry?: TileRegistry
): Record<string, maplibregl.SourceSpecification> {
  const sources: Record<string, maplibregl.SourceSpecification> = {};
  const powerPlants = sourceSpecFor("power_plants", tileStatus, tileRegistry);
  const submarineCables = sourceSpecFor("submarine_cables", tileStatus, tileRegistry);
  const dataCenters = sourceSpecFor("data_centers", tileStatus, tileRegistry);
  const powerLines = sourceSpecFor("power_lines", tileStatus, tileRegistry);
  const substations = sourceSpecFor("substations", tileStatus, tileRegistry);

  if (powerPlants) sources["power_plants_tiles"] = powerPlants;
  if (submarineCables) sources["submarine_cables_tiles"] = submarineCables;
  if (dataCenters) sources["data_centers_tiles"] = dataCenters;
  if (powerLines) sources["power_lines_tiles"] = powerLines;
  if (substations) sources["substations_tiles"] = substations;
  return sources;
}

export function getPMTilesLayers(
  tileStatus: TileStatus,
  visibleLayers: Record<string, boolean>
): maplibregl.LayerSpecification[] {
  const layers: maplibregl.LayerSpecification[] = [];

  if (tileStatus.power_plants === "present" && visibleLayers.power_plants) {
    layers.push({
      id: "power_plants_tiles-layer",
      type: "circle",
      source: "power_plants_tiles",
      "source-layer": "power_plants",
      paint: {
        "circle-radius": 2,
        "circle-color": ["match", ["get", "f"], "Hydro", FUEL_COLORS["Hydro"], "Solar", FUEL_COLORS["Solar"], "Wind", FUEL_COLORS["Wind"], "Natural Gas", FUEL_COLORS["Natural Gas"], "Nuclear", FUEL_COLORS["Nuclear"], "Coal", FUEL_COLORS["Coal"], FUEL_COLORS["Other"]],
        "circle-opacity": 0.85,
      },
    });
  }

  if (tileStatus.submarine_cables === "present" && visibleLayers.cables) {
    layers.push({
      id: "submarine_cables_tiles-layer",
      type: "line",
      source: "submarine_cables_tiles",
      "source-layer": "submarine_cables",
      paint: {
        "line-color": CABLE_COLOR,
        "line-width": 2,
        "line-opacity": 0.85,
      },
    });
  }

  if (tileStatus.data_centers === "present" && visibleLayers.data_centers) {
    layers.push({
      id: "data_centers_tiles-layer",
      type: "circle",
      source: "data_centers_tiles",
      "source-layer": "data_centers",
      paint: {
        "circle-radius": 6,
        "circle-color": DATA_CENTER_COLOR,
        "circle-opacity": 0.9,
        "circle-stroke-color": DATA_CENTER_STROKE_COLOR,
        "circle-stroke-width": 1.5,
      },
    });
  }

  if (tileStatus.power_lines === "present" && visibleLayers.power_lines) {
    layers.push({
      id: "power_lines_tiles-layer",
      type: "line",
      source: "power_lines_tiles",
      "source-layer": "power_lines",
      filter: POWER_OVERHEAD_FILTER,
      paint: {
        "line-color": powerLineColorExpression(),
        "line-width": [
          "interpolate", ["linear"], ["zoom"],
          2, 0.6,
          6, 1.2,
          10, 2.5,
        ],
        "line-opacity": 0.7,
      },
    });
    layers.push({
      id: "power_lines_cables_tiles-layer",
      type: "line",
      source: "power_lines_tiles",
      "source-layer": "power_lines",
      filter: POWER_CABLE_FILTER,
      paint: {
        "line-color": powerCableColorExpression(),
        "line-width": [
          "interpolate", ["linear"], ["zoom"],
          2, 0.9,
          6, 1.7,
          10, 3.2,
        ],
        "line-opacity": 0.9,
        "line-dasharray": [2, 1.2],
      },
    });
  }

  if (tileStatus.substations === "present" && visibleLayers.substations) {
    layers.push({
      id: "substations_tiles-layer",
      type: "circle",
      source: "substations_tiles",
      "source-layer": "substations",
      paint: {
        "circle-radius": [
          "interpolate", ["linear"], ["zoom"],
          2, 2,
          6, 4,
          10, 7,
        ],
        "circle-color": SUBSTATION_COLOR,
        "circle-opacity": 0.85,
        "circle-stroke-color": SUBSTATION_STROKE_COLOR,
        "circle-stroke-width": 1,
      },
    });
  }

  return layers;
}

export function getPMTilesStyle(
  tileStatus: TileStatus,
  visibleLayers: Record<string, boolean>,
  tileRegistry?: TileRegistry
): maplibregl.StyleSpecification {
  return {
    version: 8,
    name: "Light Topographic Atlas + PMTiles",
    glyphs: MAPLIBRE_GLYPHS_URL,
    sources: {
      ...getLightTopoSources(),
      ...getPMTilesSources(tileStatus, tileRegistry),
    },
    layers: [
      ...getLightTopoLayers(),
      ...getPMTilesLayers(tileStatus, visibleLayers),
    ],
  };
}
