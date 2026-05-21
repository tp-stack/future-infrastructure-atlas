import { describe, it, expect } from "vitest";
import { parseCoord, getLon, getLat, isValidLonLat, validPointFromRecord, toValidPoint } from "../map/coords";

describe("parseCoord", () => {
  it("returns a valid number as-is", () => {
    expect(parseCoord(42)).toBe(42);
    expect(parseCoord(-13.5)).toBe(-13.5);
    expect(parseCoord(0)).toBe(0);
  });

  it("parses numeric strings", () => {
    expect(parseCoord("42")).toBe(42);
    expect(parseCoord("-13.5")).toBe(-13.5);
    expect(parseCoord("0")).toBe(0);
  });

  it("returns null for non-numeric strings", () => {
    expect(parseCoord("abc")).toBeNull();
    expect(parseCoord("")).toBeNull();
    expect(parseCoord("  ")).toBeNull();
  });

  it("returns null for NaN and Infinity", () => {
    expect(parseCoord(NaN)).toBeNull();
    expect(parseCoord(Infinity)).toBeNull();
    expect(parseCoord(-Infinity)).toBeNull();
  });

  it("returns null for null/undefined", () => {
    expect(parseCoord(null)).toBeNull();
    expect(parseCoord(undefined)).toBeNull();
  });

  it("returns null for non-number non-string types", () => {
    expect(parseCoord({})).toBeNull();
    expect(parseCoord([])).toBeNull();
    expect(parseCoord(true)).toBeNull();
  });
});

describe("getLon", () => {
  it("extracts lon field", () => {
    expect(getLon({ lon: 12.5 })).toBe(12.5);
  });

  it("extracts longitude field", () => {
    expect(getLon({ longitude: -73.9 })).toBe(-73.9);
  });

  it("extracts lng field", () => {
    expect(getLon({ lng: 103.8 })).toBe(103.8);
  });

  it("prefers lon over other fields", () => {
    expect(getLon({ lon: 1, longitude: 2, lng: 3 })).toBe(1);
  });

  it("returns null when no field exists", () => {
    expect(getLon({})).toBeNull();
  });

  it("parses string values", () => {
    expect(getLon({ lon: "12.5" })).toBe(12.5);
  });
});

describe("getLat", () => {
  it("extracts lat field", () => {
    expect(getLat({ lat: 51.5 })).toBe(51.5);
  });

  it("extracts latitude field", () => {
    expect(getLat({ latitude: -23.5 })).toBe(-23.5);
  });

  it("prefers lat over latitude", () => {
    expect(getLat({ lat: 1, latitude: 2 })).toBe(1);
  });

  it("returns null when no field exists", () => {
    expect(getLat({})).toBeNull();
  });
});

describe("isValidLonLat", () => {
  it("accepts valid coordinates", () => {
    expect(isValidLonLat(0, 0)).toBe(true);
    expect(isValidLonLat(-180, -90)).toBe(true);
    expect(isValidLonLat(180, 90)).toBe(true);
    expect(isValidLonLat(12.5, 51.5)).toBe(true);
  });

  it("rejects out-of-range longitude", () => {
    expect(isValidLonLat(-181, 0)).toBe(false);
    expect(isValidLonLat(181, 0)).toBe(false);
  });

  it("rejects out-of-range latitude", () => {
    expect(isValidLonLat(0, -91)).toBe(false);
    expect(isValidLonLat(0, 91)).toBe(false);
  });

  it("rejects non-finite values", () => {
    expect(isValidLonLat(NaN, 0)).toBe(false);
    expect(isValidLonLat(0, Infinity)).toBe(false);
  });
});

describe("validPointFromRecord", () => {
  it("returns point for valid record", () => {
    expect(validPointFromRecord({ lon: 12.5, lat: 51.5 })).toEqual([12.5, 51.5]);
  });

  it("returns null for missing coordinates", () => {
    expect(validPointFromRecord({})).toBeNull();
  });

  it("returns null for out-of-range coordinates", () => {
    expect(validPointFromRecord({ lon: 200, lat: 0 })).toBeNull();
    expect(validPointFromRecord({ lon: 0, lat: 100 })).toBeNull();
  });

  it("reads string coordinate values", () => {
    expect(validPointFromRecord({ lon: "12.5", lat: "51.5" })).toEqual([12.5, 51.5]);
  });
});

describe("toValidPoint", () => {
  it("converts valid coordinate pair", () => {
    expect(toValidPoint([12.5, 51.5])).toEqual([12.5, 51.5]);
  });

  it("returns null for short array", () => {
    expect(toValidPoint([12.5])).toBeNull();
  });

  it("returns null for non-array input", () => {
    expect(toValidPoint(null)).toBeNull();
    expect(toValidPoint(undefined)).toBeNull();
    expect(toValidPoint("foo")).toBeNull();
  });

  it("rejects invalid coordinates", () => {
    expect(toValidPoint([200, 0])).toBeNull();
    expect(toValidPoint([0, 100])).toBeNull();
  });
});
