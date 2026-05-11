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
  CABLES: "submarine-cables",
  DATA_CENTERS: "data-centers",
} as const;

export const POWER_PAINT = {
  "circle-radius": [
    "interpolate",
    ["linear"],
    ["get", "mw"],
    0, 3,
    100, 6,
    500, 10,
    2000, 14,
    10000, 20,
  ],
  "circle-color": ["case",
    ["has", "f"], ["coalesce", ["get", "f"], "#bdbdbd"],
    "#bdbdbd"
  ],
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
