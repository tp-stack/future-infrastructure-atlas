import { FUEL_COLORS } from "./layers";

const OTHER_COLOR = FUEL_COLORS["Other"];

export function buildFuelCircleColorExpression(): maplibregl.ExpressionSpecification {
  const entries: unknown[] = ["match", ["get", "fuel"]];
  for (const [fuel, color] of Object.entries(FUEL_COLORS)) {
    if (fuel === "Other") continue;
    entries.push(fuel, color);
  }
  entries.push(OTHER_COLOR);
  return entries as maplibregl.ExpressionSpecification;
}
