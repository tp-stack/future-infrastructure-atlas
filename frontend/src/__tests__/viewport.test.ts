import { describe, it, expect } from "vitest";
import {
  expandBounds,
  getDefaultGlobalBounds,
  boundsToFitBounds,
  isZoomPathological,
  describeZoomLevel,
  computeLonLatBounds,
  FIT_WORLD_MIN_LON,
  FIT_WORLD_MAX_LON,
} from "../map/viewport";

describe("expandBounds", () => {
  it("pads bounds by the given degrees", () => {
    const result = expandBounds({ minLon: 10, minLat: 20, maxLon: 30, maxLat: 40 }, 5);
    expect(result.minLon).toBe(5);
    expect(result.minLat).toBe(15);
    expect(result.maxLon).toBe(35);
    expect(result.maxLat).toBe(45);
  });

  it("clamps to world bounds", () => {
    const result = expandBounds({ minLon: -178, minLat: -83, maxLon: 178, maxLat: 83 }, 10);
    expect(result.minLon).toBeGreaterThanOrEqual(FIT_WORLD_MIN_LON);
    expect(result.minLat).toBeGreaterThanOrEqual(-85);
    expect(result.maxLon).toBeLessThanOrEqual(FIT_WORLD_MAX_LON);
    expect(result.maxLat).toBeLessThanOrEqual(85);
  });
});

describe("getDefaultGlobalBounds", () => {
  it("returns a LonLatBounds", () => {
    const b = getDefaultGlobalBounds();
    expect(b.minLon).toBe(FIT_WORLD_MIN_LON);
    expect(b.maxLon).toBe(FIT_WORLD_MAX_LON);
    expect(b.minLat).toBe(-60);
    expect(b.maxLat).toBe(85);
  });
});

describe("boundsToFitBounds", () => {
  it("converts LonLatBounds to MapLibre fitBounds array", () => {
    const result = boundsToFitBounds({ minLon: 10, minLat: 20, maxLon: 30, maxLat: 40 });
    expect(result).toEqual([[10, 20], [30, 40]]);
  });

  it("expands to world bounds if span >= 359 degrees", () => {
    const result = boundsToFitBounds({ minLon: -180, minLat: -60, maxLon: 179, maxLat: 85 });
    expect(result[0][0]).toBe(FIT_WORLD_MIN_LON);
    expect(result[1][0]).toBe(FIT_WORLD_MAX_LON);
  });
});

describe("isZoomPathological", () => {
  it("returns false for global and continental zoom levels", () => {
    expect(isZoomPathological(1)).toBe(false);
    expect(isZoomPathological(3)).toBe(false);
    expect(isZoomPathological(5)).toBe(false);
    expect(isZoomPathological(8)).toBe(false);
  });

  it("returns true for zoom > 8", () => {
    expect(isZoomPathological(8.1)).toBe(true);
    expect(isZoomPathological(9)).toBe(true);
    expect(isZoomPathological(15)).toBe(true);
  });
});

describe("describeZoomLevel", () => {
  it("describes global zoom (<=2)", () => {
    expect(describeZoomLevel(1)).toBe("global");
    expect(describeZoomLevel(2)).toBe("global");
  });

  it("describes continental zoom (2-5)", () => {
    expect(describeZoomLevel(3)).toBe("continental");
    expect(describeZoomLevel(5)).toBe("continental");
  });

  it("describes regional zoom (5-8)", () => {
    expect(describeZoomLevel(6)).toBe("regional");
    expect(describeZoomLevel(8)).toBe("regional");
  });

  it("describes zoomed-in pathological (>8)", () => {
    expect(describeZoomLevel(9)).toBe("zoomed in (pathological)");
    expect(describeZoomLevel(12)).toBe("zoomed in (pathological)");
  });

  it("describes street pathological (>12)", () => {
    expect(describeZoomLevel(13)).toBe("street (pathological)");
    expect(describeZoomLevel(20)).toBe("street (pathological)");
  });
});

describe("computeLonLatBounds", () => {
  it("computes bounds from coordinate list", () => {
    const result = computeLonLatBounds([[10, 20], [30, 40], [15, 25]]);
    expect(result).toEqual({ minLon: 10, minLat: 20, maxLon: 30, maxLat: 40 });
  });

  it("returns null for empty list", () => {
    expect(computeLonLatBounds([])).toBeNull();
  });

  it("handles a single coordinate", () => {
    const result = computeLonLatBounds([[42, 17]]);
    expect(result).toEqual({ minLon: 42, minLat: 17, maxLon: 42, maxLat: 17 });
  });
});
