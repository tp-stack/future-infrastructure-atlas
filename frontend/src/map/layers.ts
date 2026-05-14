export const FUEL_COLORS: Record<string, string> = {
  "Hydro": "#4fc3f7",
  "Solar": "#d69a13",
  "Wind": "#5cb88a",
  "Nuclear": "#a87bc7",
  "Coal": "#d45050",
  "Natural Gas": "#d4956a",
  "Oil": "#c47555",
  "Biomass": "#7ab87a",
  "Geothermal": "#d48a6a",
  "Waste": "#8a8a8a",
  "Cogeneration": "#6a9fd4",
  "Wave and Tidal": "#4dd0e1",
  "Other": "#8d93a1",
};

export const CABLE_COLOR = "#087ea4";
export const CABLE_HOVER_COLOR = "#0b94bd";
export const DATA_CENTER_COLOR = "#173f5f";
export const DATA_CENTER_STROKE_COLOR = "#ffffff";

export const LAYER_IDS = {
  POWER_PLANTS: "power-plants",
  POWER_CLUSTERS: "power-plants-clusters",
  POWER_CLUSTER_COUNT: "power-plants-cluster-count",
  CABLES: "submarine-cables",
  DATA_CENTERS: "data-centers",
} as const;

export const CLUSTER_PAINT = {
  "circle-color": "#d69a13",
  "circle-radius": ["step", ["get", "point_count"], 20, 50, 28, 200, 36],
  "circle-opacity": 0.85,
  "circle-stroke-width": 2,
  "circle-stroke-color": "#fce488",
};

export const CLUSTER_COUNT_PAINT = {
  "text-field": ["get", "point_count_abbreviated"],
  "text-size": 10,
  "text-color": "#0a0a0f",
  "text-font": ["Open Sans Bold", "Arial Unicode MS Bold"],
};

export const POWER_PAINT = {
  "circle-radius": [
    "interpolate", ["linear"], ["zoom"],
    2, 3,
    5, 4.5,
    8, 6,
    12, 10,
    16, 14,
  ],
  "circle-color": [
    "case",
    ["has", "f"],
    ["coalesce", ["get", "f"], "#8d93a1"],
    "#8d93a1",
  ],
  "circle-opacity": [
    "interpolate", ["linear"], ["zoom"],
    2, 0.5,
    8, 0.6,
    14, 0.75,
  ],
  "circle-stroke-width": [
    "interpolate", ["linear"], ["zoom"],
    2, 0.5,
    8, 0.7,
    14, 1,
  ],
  "circle-stroke-color": "rgba(255,255,255,0.2)",
};

export const DATA_CENTER_PAINT = {
  "circle-radius": [
    "interpolate", ["linear"], ["zoom"],
    3, 3,
    8, 5,
    12, 8,
  ],
  "circle-color": DATA_CENTER_COLOR,
  "circle-opacity": 0.85,
  "circle-stroke-width": 1.5,
  "circle-stroke-color": DATA_CENTER_STROKE_COLOR,
};

export const CABLE_PAINT = {
  "line-color": CABLE_COLOR,
  "line-width": [
    "interpolate", ["linear"], ["zoom"],
    2, 0.8,
    8, 1.5,
    12, 2.5,
  ],
  "line-opacity": [
    "interpolate", ["linear"], ["zoom"],
    2, 0.4,
    8, 0.6,
    12, 0.8,
  ],
};
