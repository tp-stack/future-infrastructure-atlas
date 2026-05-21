import { describe, it, expect } from "vitest";
import { buildFuelCircleColorExpression } from "../map/fuelMatch";
import { FUEL_COLORS } from "../map/layers";

describe("buildFuelCircleColorExpression", () => {
  it("returns an array starting with 'match' and 'get'", () => {
    const expr = buildFuelCircleColorExpression();
    expect(Array.isArray(expr)).toBe(true);
    expect(expr[0]).toBe("match");
    expect(expr[1]).toEqual(["get", "fuel"]);
  });

  it("includes all fuel types except Other", () => {
    const expr = buildFuelCircleColorExpression();
    const fuelKeys = Object.keys(FUEL_COLORS).filter((k) => k !== "Other");
    for (const fuel of fuelKeys) {
      expect(expr).toContain(fuel);
      expect(expr).toContain(FUEL_COLORS[fuel]);
    }
  });

  it("ends with the Other color as fallback", () => {
    const expr = buildFuelCircleColorExpression();
    const last = expr[expr.length - 1] as string;
    expect(last).toBe(FUEL_COLORS["Other"]);
  });

  it("has the correct structure length", () => {
    const expr = buildFuelCircleColorExpression();
    const fuelKeys = Object.keys(FUEL_COLORS).filter((k) => k !== "Other");
    // [match, [get, fuel], fuel1, color1, fuel2, color2, ..., fallbackColor]
    expect(expr.length).toBe(3 + fuelKeys.length * 2);
  });

  it("returns a valid MapLibre expression structure", () => {
    const expr = buildFuelCircleColorExpression() as unknown[];
    expect(expr[0]).toBe("match");
    expect(Array.isArray(expr[1])).toBe(true);
    const getExpr = expr[1] as unknown[];
    expect(getExpr[0]).toBe("get");
    expect(getExpr[1]).toBe("fuel");
  });
});
