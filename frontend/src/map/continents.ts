import type maplibregl from "maplibre-gl";

export type GridContinentKey = "north_america" | "south_america" | "europe" | "africa" | "asia" | "oceania";
export type GridContinentFilters = Record<GridContinentKey, boolean>;

export const GRID_CONTINENTS: Array<{ key: GridContinentKey; label: string; shortLabel: string }> = [
  { key: "north_america", label: "North America", shortLabel: "N. America" },
  { key: "south_america", label: "South America", shortLabel: "S. America" },
  { key: "europe", label: "Europe", shortLabel: "Europe" },
  { key: "africa", label: "Africa", shortLabel: "Africa" },
  { key: "asia", label: "Asia", shortLabel: "Asia" },
  { key: "oceania", label: "Oceania", shortLabel: "Oceania" },
];

export const DEFAULT_GRID_CONTINENT_FILTERS: GridContinentFilters = {
  north_america: true,
  south_america: true,
  europe: true,
  africa: true,
  asia: true,
  oceania: true,
};

type Rect = [minLon: number, minLat: number, maxLon: number, maxLat: number];

function rectToPolygon([minLon, minLat, maxLon, maxLat]: Rect): GeoJSON.Position[][] {
  return [[
    [minLon, minLat],
    [maxLon, minLat],
    [maxLon, maxLat],
    [minLon, maxLat],
    [minLon, minLat],
  ]];
}

const CONTINENT_RECTS: Record<GridContinentKey, Rect[]> = {
  north_america: [[-170, 5, -50, 85]],
  south_america: [[-90, -60, -30, 15]],
  europe: [[-25, 34, 45, 72]],
  africa: [[-20, -35, 55, 38]],
  asia: [[25, -10, 180, 82], [-180, 50, -168, 72]],
  oceania: [[110, -50, 180, 10], [-180, -30, -130, 0]],
};

export function selectedGridContinentCount(filters: GridContinentFilters): number {
  return GRID_CONTINENTS.filter((continent) => filters[continent.key]).length;
}

export function buildSelectedGridContinentGeometry(filters: GridContinentFilters): GeoJSON.MultiPolygon | null {
  const selected = GRID_CONTINENTS.filter((continent) => filters[continent.key]);
  if (selected.length === GRID_CONTINENTS.length) return null;
  if (selected.length === 0) return null;

  return {
    type: "MultiPolygon",
    coordinates: selected.flatMap((continent) => CONTINENT_RECTS[continent.key].map(rectToPolygon)),
  };
}

export function buildGridContinentFilter(
  baseFilter: maplibregl.FilterSpecification,
  filters: GridContinentFilters,
): maplibregl.FilterSpecification {
  const selectedCount = selectedGridContinentCount(filters);
  if (selectedCount === GRID_CONTINENTS.length) return baseFilter;
  if (selectedCount === 0) {
    return ["all", baseFilter, ["==", ["get", "__continent_filter_none__"], "__hidden__"]] as maplibregl.FilterSpecification;
  }

  const geometry = buildSelectedGridContinentGeometry(filters);
  return ["all", baseFilter, ["within", geometry]] as maplibregl.FilterSpecification;
}
