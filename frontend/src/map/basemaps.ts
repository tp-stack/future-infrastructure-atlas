import type maplibregl from "maplibre-gl";

const LIGHT_TOPO_SOURCE_ID = "basemap-light-topo";
export const MAPLIBRE_GLYPHS_URL = "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf";

export const LIGHT_TOPO_ATTRIBUTION =
  'Tiles &copy; Esri &mdash; Sources: Esri, Garmin, FAO, NOAA, USGS, OpenStreetMap contributors, and the GIS User Community';

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

export function getLightTopoStyle(name = "Light Topographic Atlas"): maplibregl.StyleSpecification {
  return {
    version: 8,
    name,
    glyphs: MAPLIBRE_GLYPHS_URL,
    sources: getLightTopoSources(),
    layers: getLightTopoLayers(),
  };
}
