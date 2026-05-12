import type { PowerPlant, DataCenter, Cable } from "./types";

export type InteractableType = "power_plant" | "data_center" | "submarine_cable";

export interface InteractableAsset {
  id: string;
  type: InteractableType;
  name: string;
  asset: PowerPlant | DataCenter | Cable;
  screenX: number;
  screenY: number;
  radius: number;
}

export interface PickIndex {
  powerPlants: InteractableAsset[];
  dataCenters: InteractableAsset[];
  cables: InteractableAsset[];
}

export function buildPickIndex(
  powerPlants: PowerPlant[],
  dataCenters: DataCenter[],
  cables: Cable[],
  projectFn: (lon: number, lat: number) => [number, number],
  viewW: number,
  viewH: number,
): PickIndex {
  const pp: InteractableAsset[] = [];
  for (const p of powerPlants) {
    const [x, y] = projectFn(p.lon, p.lat);
    if (x < -10 || x > viewW + 10 || y < -10 || y > viewH + 10) continue;
    pp.push({ id: `pp-${p.n}-${p.lat}-${p.lon}`, type: "power_plant", name: p.n, screenX: x, screenY: y, radius: 8, asset: p });
  }

  const dc: InteractableAsset[] = [];
  for (const d of dataCenters) {
    if (d.lat == null || d.lon == null) continue;
    const [x, y] = projectFn(d.lon, d.lat);
    if (x < -10 || x > viewW + 10 || y < -10 || y > viewH + 10) continue;
    dc.push({ id: `dc-${d.n}-${d.lat}-${d.lon}`, type: "data_center", name: d.n, screenX: x, screenY: y, radius: 14, asset: d });
  }

  const cb: InteractableAsset[] = [];
  for (const c of cables) {
    if (!c.geometry || c.geometry.length < 2) continue;
    const isMulti = Array.isArray(c.geometry[0]) && Array.isArray(c.geometry[0][0]);
    const lines = isMulti ? (c.geometry as number[][][]) : [c.geometry as number[][]];
    for (const line of lines) {
      for (let i = 0; i < line.length; i++) {
        const [px, py] = line[i];
        if (px == null || py == null) continue;
        const [x, y] = projectFn(px, py);
        if (x >= -10 && x <= viewW + 10 && y >= -10 && y <= viewH + 10) {
          cb.push({ id: `cable-${c.n}-${i}`, type: "submarine_cable", name: c.n, screenX: x, screenY: y, radius: 6, asset: c });
          break;
        }
      }
    }
  }

  return { powerPlants: pp, dataCenters: dc, cables: cb };
}

function dist(x1: number, y1: number, x2: number, y2: number): number {
  return Math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2);
}

export function findNearest(
  x: number, y: number, pickIndex: PickIndex, maxDistPx: number = 12,
): InteractableAsset | null {
  let best: InteractableAsset | null = null;
  let bestDist = maxDistPx;

  for (const a of pickIndex.powerPlants) {
    const d = dist(x, y, a.screenX, a.screenY);
    if (d < bestDist) { bestDist = d; best = a; }
  }
  for (const a of pickIndex.dataCenters) {
    const d = dist(x, y, a.screenX, a.screenY);
    if (d < bestDist) { bestDist = d; best = a; }
  }
  for (const a of pickIndex.cables) {
    const d = dist(x, y, a.screenX, a.screenY);
    if (d < bestDist) { bestDist = d; best = a; }
  }

  return best;
}

export function formatAssetType(type: InteractableType): string {
  switch (type) {
    case "power_plant": return "Power Plant";
    case "data_center": return "Data Center / Facility";
    case "submarine_cable": return "Submarine Cable";
  }
}
