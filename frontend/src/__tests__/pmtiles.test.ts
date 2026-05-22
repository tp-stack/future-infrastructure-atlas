import { describe, expect, it } from "vitest";
import { getPMTilesLayers } from "../map/pmtiles";
import type { TileStatus } from "../map/pmtiles";

const present: TileStatus = {
  power_plants: "missing",
  submarine_cables: "missing",
  data_centers: "missing",
  power_lines: "present",
  substations: "missing",
};

describe("getPMTilesLayers", () => {
  it("renders overhead lines and underground power cables as separate layers", () => {
    const layers = getPMTilesLayers(present, { power_lines: true });
    const ids = layers.map((layer) => layer.id);

    expect(ids).toContain("power_lines_tiles-layer");
    expect(ids).toContain("power_lines_cables_tiles-layer");

    const cableLayer = layers.find((layer) => layer.id === "power_lines_cables_tiles-layer");
    expect(cableLayer?.type).toBe("line");
    expect((cableLayer as { filter?: unknown } | undefined)?.filter).toEqual([
      "any",
      ["==", ["get", "power"], "cable"],
      ["==", ["get", "underground"], true],
      ["==", ["get", "underground"], "true"],
      ["==", ["get", "underground"], 1],
    ]);
    expect((cableLayer?.paint as Record<string, unknown>)["line-dasharray"]).toEqual([2, 1.2]);
  });
});
