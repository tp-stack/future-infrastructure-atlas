import type maplibregl from "maplibre-gl";
import type { AtlasTheme } from "../utils/theme";

const LIGHT_TOPO_SOURCE_ID = "basemap-light-topo";
const DARK_TOPO_SOURCE_ID = "basemap-dark-topo";
export const MAPLIBRE_GLYPHS_URL = "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf";

export const LIGHT_TOPO_ATTRIBUTION =
  'Tiles &copy; Esri &mdash; Sources: Esri, Garmin, FAO, NOAA, USGS, OpenStreetMap contributors, and the GIS User Community';
export const DARK_TOPO_ATTRIBUTION =
  'Tiles &copy; Esri &mdash; Sources: Esri, HERE, Garmin, FAO, NOAA, USGS, OpenStreetMap contributors, and the GIS User Community';

export function getLightTopoSources(): Record<string, maplibregl.SourceSpecification> {
  return {
    [LIGHT_TOPO_SOURCE_ID]: {
      type: "raster",
      tiles: ["https://services.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}"],
      tileSize: 256,
      attribution: LIGHT_TOPO_ATTRIBUTION,
    },
  };
}

export function getLightTopoLayers(): maplibregl.LayerSpecification[] {
  return [
    { id: "background", type: "background", paint: { "background-color": "#eef1ec" } },
    {
      id: "basemap-light-topo-layer",
      type: "raster",
      source: LIGHT_TOPO_SOURCE_ID,
      minzoom: 0,
      maxzoom: 20,
      paint: {
        "raster-opacity": 0.9,
        "raster-fade-duration": 100,
      },
    },
  ];
}

export function getDarkTopoSources(): Record<string, maplibregl.SourceSpecification> {
  return {
    [DARK_TOPO_SOURCE_ID]: {
      type: "raster",
      tiles: ["https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"],
      tileSize: 256,
      attribution: DARK_TOPO_ATTRIBUTION,
    },
  };
}

export function getDarkTopoLayers(): maplibregl.LayerSpecification[] {
  return [
    { id: "background", type: "background", paint: { "background-color": "#02040a" } },
    {
      id: "basemap-dark-topo-layer",
      type: "raster",
      source: DARK_TOPO_SOURCE_ID,
      minzoom: 0,
      maxzoom: 20,
      paint: {
        "raster-opacity": 0.92,
        "raster-fade-duration": 100,
      },
    },
  ];
}

export function getThemedTopoSources(theme: AtlasTheme): Record<string, maplibregl.SourceSpecification> {
  return theme === "dark" ? getDarkTopoSources() : getLightTopoSources();
}

export function getThemedTopoLayers(theme: AtlasTheme): maplibregl.LayerSpecification[] {
  return theme === "dark" ? getDarkTopoLayers() : getLightTopoLayers();
}

export function getLightTopoStyle(name = "Light Topographic Atlas"): maplibregl.StyleSpecification {
  return {
    version: 8,
    name,
    glyphs: MAPLIBRE_GLYPHS_URL,
    sources: getLightTopoSources(),
    layers: getLightTopoLayers(),
  };
}

export function getThemedTopoStyle(theme: AtlasTheme, name = "Infrastructure Atlas"): maplibregl.StyleSpecification {
  return {
    version: 8,
    name,
    glyphs: MAPLIBRE_GLYPHS_URL,
    sources: getThemedTopoSources(theme),
    layers: getThemedTopoLayers(theme),
  };
}

export function getGlobeTopoStyle(theme: AtlasTheme = "dark", name = "Infrastructure Atlas Globe"): maplibregl.StyleSpecification {
  const dark = theme === "dark";
  return {
    version: 8,
    name,
    projection: { type: "globe" },
    glyphs: MAPLIBRE_GLYPHS_URL,
    sources: getThemedTopoSources(theme),
    layers: [
      { id: "globe-space", type: "background", paint: { "background-color": dark ? "#02040a" : "#d9e4f0" } },
      {
        id: dark ? "basemap-dark-topo-layer" : "basemap-light-topo-layer",
        type: "raster",
        source: dark ? DARK_TOPO_SOURCE_ID : LIGHT_TOPO_SOURCE_ID,
        minzoom: 0,
        maxzoom: 20,
        paint: {
          "raster-opacity": dark ? 0.88 : 0.78,
          "raster-fade-duration": 120,
        },
      },
    ],
    sky: {
      "atmosphere-blend": [
        "interpolate",
        ["linear"],
        ["zoom"],
        0,
        0.9,
        5,
        0.45,
        7,
        0,
      ],
      "sky-color": dark ? "#061326" : "#b9d7ef",
      "horizon-color": dark ? "#143b5a" : "#d5ecff",
      "fog-color": dark ? "#0b1220" : "#f4f8fb",
    },
    light: {
      anchor: "map",
      position: [1.5, 90, 80],
    },
  };
}
