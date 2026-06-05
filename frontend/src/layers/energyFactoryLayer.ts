export const ENERGY_LAYER_ID = "energy-factory-points";
export const ENERGY_GLOW_ID = "energy-factory-glow";
export const ENERGY_SELECTED_ID = "energy-factory-selected";
export const ENERGY_FLOW_SOURCE_ID = "energy-flow-source";
export const ENERGY_FLOW_LAYER_ID = "energy-flow-lines";
export const ENERGY_FLOW_DESTINATION_ID = "energy-flow-destinations";

export const ENERGY_COLOR = "#d69a13";
export const ENERGY_UNKNOWN_COLOR = "#5a5a62";

export function getEnergyCirclePaint(color: string): maplibregl.CircleLayerSpecification["paint"] {
  return {
    "circle-radius": [
      "interpolate", ["linear"], ["coalesce", ["get", "mw"], 0],
      0, 3,
      1, 3,
      5, 4,
      10, 5,
      25, 6,
      50, 7,
      100, 8,
      250, 9,
      500, 10,
      1000, 12,
      5000, 13,
      10000, 14,
      22500, 14,
    ],
    "circle-color": color,
    "circle-opacity": 0.25,
    "circle-stroke-width": 1.2,
    "circle-stroke-color": color,
    "circle-stroke-opacity": 0.7,
    "circle-blur": 0.5,
  };
}

export const ENERGY_SELECTED_PAINT: maplibregl.CircleLayerSpecification["paint"] = {
  "circle-radius": [
    "interpolate", ["linear"], ["coalesce", ["get", "mw"], 0],
    0, 6,
    1, 6,
    10, 8,
    100, 11,
    500, 14,
    1000, 16,
    5000, 18,
    22500, 20,
  ],
  "circle-color": "#f4efe6",
  "circle-opacity": 0.6,
  "circle-stroke-width": 2,
  "circle-stroke-color": "#d69a13",
  "circle-stroke-opacity": 0.9,
};

export const FLOW_LINE_PAINT: maplibregl.LineLayerSpecification["paint"] = {
  "line-color": "#d69a13",
  "line-width": 1.2,
  "line-opacity": 0.35,
  "line-dasharray": [3, 2],
};

export const FLOW_DESTINATION_PAINT: maplibregl.CircleLayerSpecification["paint"] = {
  "circle-radius": 3,
  "circle-color": "#d69a13",
  "circle-opacity": 0.5,
  "circle-stroke-width": 0.5,
  "circle-stroke-color": "rgba(255,255,255,0.3)",
};
