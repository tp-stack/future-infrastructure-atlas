import { Protocol } from "pmtiles";
import maplibregl from "maplibre-gl";
import { getLightTopoLayers, getLightTopoSources, MAPLIBRE_GLYPHS_URL } from "./basemaps";
import { CABLE_COLOR, DATA_CENTER_COLOR, DATA_CENTER_STROKE_COLOR, FUEL_COLORS } from "./layers";

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
}

export function getPMTilesSources(tileStatus: TileStatus): Record<string, maplibregl.SourceSpecification> {
  const sources: Record<string, maplibregl.SourceSpecification> = {};
  if (tileStatus.power_plants === "present") {
    sources["power_plants_tiles"] = {
      type: "vector",
      url: "pmtiles:///tiles/power_plants.pmtiles",
    };
  }
  if (tileStatus.submarine_cables === "present") {
    sources["submarine_cables_tiles"] = {
      type: "vector",
      url: "pmtiles:///tiles/submarine_cables.pmtiles",
    };
  }
  if (tileStatus.data_centers === "present") {
    sources["data_centers_tiles"] = {
      type: "vector",
      url: "pmtiles:///tiles/data_centers.pmtiles",
    };
  }
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

  return layers;
}

export function getPMTilesStyle(
  tileStatus: TileStatus,
  visibleLayers: Record<string, boolean>
): maplibregl.StyleSpecification {
  return {
    version: 8,
    name: "Light Topographic Atlas + PMTiles",
    glyphs: MAPLIBRE_GLYPHS_URL,
    sources: {
      ...getLightTopoSources(),
      ...getPMTilesSources(tileStatus),
    },
    layers: [
      ...getLightTopoLayers(),
      ...getPMTilesLayers(tileStatus, visibleLayers),
    ],
  };
}
