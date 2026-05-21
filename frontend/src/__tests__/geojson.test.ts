import { describe, it, expect } from "vitest";
import {
  buildPowerPlantGeoJSON,
  buildDataCenterGeoJSON,
  buildCableGeoJSON,
  buildGraticuleGeoJSON,
  computeFeatureCollectionBounds,
  computeCombinedBounds,
} from "../map/geojson";
import type { AtlasData, FilterState } from "../map/types";

function makeTestData(): AtlasData {
  return {
    metadata: {
      generated_at: "2024-01-01T00:00:00Z",
      sources: [],
      disclaimer: "",
      counts: {
        power_plants_mapped: 3,
        power_plants_total: 3,
        power_plants_rejected: 0,
        submarine_cables_total: 1,
        submarine_cables_mapped: 1,
        submarine_cables_unmapped: 0,
        data_centers_total: 1,
        data_centers_mapped: 1,
        data_centers_unmapped: 0,
      },
      unmapped: { submarine_cables: [], data_centers: [] },
    },
    power_plants: [
      { kind: "power_plant", n: "Plant A", c: "US", f: "Hydro", mw: 100, lat: 40, lon: -100 },
      { kind: "power_plant", n: "Plant B", c: "DE", f: "Solar", mw: 50, lat: 52, lon: 13 },
      { kind: "power_plant", n: "Plant C", c: "US", f: "Coal", mw: 500, lat: 35, lon: -80 },
    ],
    cables: [
      {
        kind: "submarine_cable",
        n: "Cable-1",
        source: "SourceA",
        geometry: [[[-70, 40], [-60, 35], [-50, 30]]],
        mapped_status: "mapped",
      },
    ],
    data_centers: [
      {
        kind: "data_center", n: "DC-1", op: "OpCo", c: "US", city: "NYC",
        lat: 40.7, lon: -74.0, source: "PeeringDB", mapped_status: "mapped",
        coordinate_precision: "exact",
      },
    ],
  };
}

describe("buildPowerPlantGeoJSON", () => {
  it("returns all power plants with no filters", () => {
    const data = makeTestData();
    const result = buildPowerPlantGeoJSON(data);
    expect(result.type).toBe("FeatureCollection");
    expect(result.features).toHaveLength(3);
  });

  it("filters by fuel type", () => {
    const data = makeTestData();
    const result = buildPowerPlantGeoJSON(data, { fuelType: "Solar", country: "", minMw: 0 });
    expect(result.features).toHaveLength(1);
    expect(result.features[0].properties!.name).toBe("Plant B");
  });

  it("filters by country", () => {
    const data = makeTestData();
    const result = buildPowerPlantGeoJSON(data, { fuelType: "", country: "US", minMw: 0 });
    expect(result.features).toHaveLength(2);
  });

  it("filters by minimum capacity", () => {
    const data = makeTestData();
    const result = buildPowerPlantGeoJSON(data, { fuelType: "", country: "", minMw: 200 });
    expect(result.features).toHaveLength(1);
    expect(result.features[0].properties!.name).toBe("Plant C");
  });

  it("combines multiple filters", () => {
    const data = makeTestData();
    const result = buildPowerPlantGeoJSON(data, { fuelType: "Hydro", country: "US", minMw: 50 });
    expect(result.features).toHaveLength(1);
    expect(result.features[0].properties!.name).toBe("Plant A");
  });

  it("returns no features when all filtered out", () => {
    const data = makeTestData();
    const result = buildPowerPlantGeoJSON(data, { fuelType: "Nuclear", country: "", minMw: 0 });
    expect(result.features).toHaveLength(0);
  });

  it("includes _idx in properties", () => {
    const data = makeTestData();
    const result = buildPowerPlantGeoJSON(data);
    expect(result.features[0].properties!._idx).toBe(0);
    expect(result.features[1].properties!._idx).toBe(1);
    expect(result.features[2].properties!._idx).toBe(2);
  });
});

describe("buildDataCenterGeoJSON", () => {
  it("returns mapped data centers", () => {
    const data = makeTestData();
    const result = buildDataCenterGeoJSON(data);
    expect(result.features).toHaveLength(1);
    expect(result.features[0].properties!.name).toBe("DC-1");
  });

  it("excludes unmapped data centers", () => {
    const data = makeTestData();
    data.data_centers[0].mapped_status = "unmapped";
    const result = buildDataCenterGeoJSON(data);
    expect(result.features).toHaveLength(0);
  });

  it("excludes data centers without valid coordinates", () => {
    const data = makeTestData();
    data.data_centers.push({
      kind: "data_center", n: "Bad", op: "", c: "", city: "",
      lat: 999, lon: 0, source: "", mapped_status: "mapped",
    });
    const result = buildDataCenterGeoJSON(data);
    expect(result.features).toHaveLength(1);
  });
});

describe("buildCableGeoJSON", () => {
  it("returns mapped cables", () => {
    const data = makeTestData();
    const result = buildCableGeoJSON(data);
    expect(result.features).toHaveLength(1);
    expect(result.features[0].properties!.name).toBe("Cable-1");
  });

  it("excludes unmapped cables", () => {
    const data = makeTestData();
    data.cables[0].mapped_status = "unmapped";
    const result = buildCableGeoJSON(data);
    expect(result.features).toHaveLength(0);
  });

  it("creates LineString for single-line geometry", () => {
    const data = makeTestData();
    const result = buildCableGeoJSON(data);
    expect(result.features[0].geometry.type).toBe("LineString");
  });

  it("creates MultiLineString for multi-line geometry", () => {
    const data = makeTestData();
    data.cables[0].geometry = [[[0, 0], [1, 1]], [[2, 2], [3, 3]]];
    const result = buildCableGeoJSON(data);
    expect(result.features[0].geometry.type).toBe("MultiLineString");
  });
});

describe("buildGraticuleGeoJSON", () => {
  it("returns a FeatureCollection", () => {
    const result = buildGraticuleGeoJSON();
    expect(result.type).toBe("FeatureCollection");
    expect(result.features.length).toBeGreaterThan(0);
  });

  it("contains meridians and parallels", () => {
    const result = buildGraticuleGeoJSON();
    const kinds = new Set(result.features.map((f) => f.properties?.kind));
    expect(kinds.has("meridian")).toBe(true);
    expect(kinds.has("parallel")).toBe(true);
  });
});

describe("computeFeatureCollectionBounds", () => {
  it("computes bounds for power plants", () => {
    const data = makeTestData();
    const fc = buildPowerPlantGeoJSON(data);
    const bounds = computeFeatureCollectionBounds(fc);
    expect(bounds).not.toBeNull();
    const b = bounds!;
    expect(b.minLon).toBe(-100);
    expect(b.maxLon).toBe(13);
    expect(b.minLat).toBe(35);
    expect(b.maxLat).toBe(52);
  });

  it("computes bounds for cables", () => {
    const data = makeTestData();
    const fc = buildCableGeoJSON(data);
    const bounds = computeFeatureCollectionBounds(fc);
    expect(bounds).not.toBeNull();
  });
});

describe("computeCombinedBounds", () => {
  it("merges bounds from multiple collections", () => {
    const data = makeTestData();
    const combined = computeCombinedBounds([
      buildPowerPlantGeoJSON(data),
      buildDataCenterGeoJSON(data),
      buildCableGeoJSON(data),
    ]);
    expect(combined).not.toBeNull();
    const c = combined!;
    expect(c.minLon).toBe(-100);
    expect(c.maxLat).toBe(52);
  });

  it("returns null for all-empty input", () => {
    expect(computeCombinedBounds([null, undefined])).toBeNull();
  });
});
