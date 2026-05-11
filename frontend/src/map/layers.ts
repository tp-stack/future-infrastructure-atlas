export const FUEL_COLORS: Record<string, string> = {
  "Hydro": "#4fc3f7",
  "Solar": "#ffd54f",
  "Wind": "#81c784",
  "Nuclear": "#ce93d8",
  "Coal": "#ef5350",
  "Natural Gas": "#ffb74d",
  "Oil": "#ff8a65",
  "Biomass": "#a5d6a7",
  "Geothermal": "#ffab91",
  "Waste": "#bcaaa4",
  "Cogeneration": "#90caf9",
  "Wave and Tidal": "#4dd0e1",
  "Other": "#bdbdbd",
};

export const LAYER_IDS = {
  POWER_PLANTS: "power-plants",
  POWER_CLUSTERS: "power-plants-clusters",
  POWER_CLUSTER_COUNT: "power-plants-cluster-count",
  CABLES: "submarine-cables",
  DATA_CENTERS: "data-centers",
} as const;

export const CLUSTER_PAINT = {
  "circle-color": "#f59e0b",
  "circle-radius": ["step", ["get", "point_count"], 20, 50, 30, 200, 40],
  "circle-opacity": 0.7,
  "circle-stroke-width": 2,
  "circle-stroke-color": "#fbbf24",
};

export const CLUSTER_COUNT_PAINT = {
  "text-field": ["get", "point_count_abbreviated"],
  "text-size": 12,
  "text-color": "#0a0a0f",
  "text-font": ["Open Sans Bold", "Arial Unicode MS Bold"],
};

export const POWER_PAINT = {
  "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 3, 8, 6, 12, 10],
  "circle-color": ["case", ["has", "f"], ["coalesce", ["get", "f"], "#bdbdbd"], "#bdbdbd"],
  "circle-opacity": 0.8,
  "circle-stroke-width": 1,
  "circle-stroke-color": "rgba(0,0,0,0.3)",
};

export const DATA_CENTER_PAINT = {
  "circle-radius": 8,
  "circle-color": "#e0e0e0",
  "circle-opacity": 0.9,
  "circle-stroke-width": 2,
  "circle-stroke-color": "#ffffff",
};

export const CABLE_PAINT = {
  "line-color": "#4dd0e1",
  "line-width": 2,
  "line-opacity": 0.8,
};
