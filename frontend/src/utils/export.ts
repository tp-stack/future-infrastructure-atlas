import type { AtlasData, FilterState, PowerPlant, Cable, DataCenter } from "../map/types";

function filterPowerPlants(data: AtlasData, filters: FilterState): PowerPlant[] {
  return data.power_plants.filter((p) => {
    if (filters.fuelType && p.f !== filters.fuelType) return false;
    if (filters.country && p.c !== filters.country) return false;
    if (filters.minMw > 0 && p.mw < filters.minMw) return false;
    return true;
  });
}

function toCSVRow(values: Record<string, unknown>): string {
  return Object.values(values).map((v) => {
    const s = v == null ? "" : String(v);
    return s.includes(",") || s.includes('"') || s.includes("\n") ? `"${s.replace(/"/g, '""')}"` : s;
  }).join(",");
}

export function exportCSV(data: AtlasData, filters: FilterState, type: string): void {
  let rows: string[] = [];

  if (type === "power_plants" || type === "all") {
    const plants = filterPowerPlants(data, filters);
    rows.push("name,country,fuel,capacity_mw,lat,lon");
    for (const p of plants) {
      rows.push(toCSVRow({ name: p.n, country: p.c, fuel: p.f, capacity_mw: p.mw, lat: p.lat, lon: p.lon }));
    }
  }

  if (type === "cables" || type === "all") {
    const cables = data.cables.filter((c) => c.mapped_status === "mapped");
    rows.push("name,source,length_km,operators,landing_points,confidence");
    for (const c of cables) {
      const lp = Array.isArray(c.landing_points) ? c.landing_points.join("; ") : (c.landing_points || "");
      rows.push(toCSVRow({ name: c.n, source: c.source, length_km: c.length_km, operators: c.operators, landing_points: lp, confidence: c.confidence }));
    }
  }

  if (type === "data_centers" || type === "all") {
    const dcs = data.data_centers.filter((d) => d.mapped_status === "mapped");
    rows.push("name,operator,country,city,capacity_mw,lat,lon,networks,ixps");
    for (const d of dcs) {
      rows.push(toCSVRow({ name: d.n, operator: d.op, country: d.c, city: d.city, capacity_mw: d.mw, lat: d.lat, lon: d.lon, networks: d.net_count, ixps: d.ix_count }));
    }
  }

  download(rows.join("\n"), `${type}-${Date.now()}.csv`, "text/csv");
}

export function exportGeoJSON(data: AtlasData, filters: FilterState, type: string): void {
  let features: GeoJSON.Feature[] = [];

  if (type === "power_plants" || type === "all") {
    const plants = filterPowerPlants(data, filters);
    for (const p of plants) {
      features.push({
        type: "Feature",
        geometry: { type: "Point", coordinates: [p.lon, p.lat] },
        properties: { name: p.n, country: p.c, fuel: p.f, capacity_mw: p.mw },
      });
    }
  }

  if (type === "data_centers" || type === "all") {
    const dcs = data.data_centers.filter((d) => d.mapped_status === "mapped");
    for (const d of dcs) {
      features.push({
        type: "Feature",
        geometry: { type: "Point", coordinates: [d.lon, d.lat] },
        properties: { name: d.n, operator: d.op, country: d.c, city: d.city, capacity_mw: d.mw, networks: d.net_count, ixps: d.ix_count },
      });
    }
  }

  if (type === "cables" || type === "all") {
    const cables = data.cables.filter((c) => c.mapped_status === "mapped" && c.geometry?.length);
    for (const c of cables) {
      if (!c.geometry?.length) continue;
      const isMulti = Array.isArray(c.geometry[0]) && Array.isArray(c.geometry[0][0]);
      const geometry: GeoJSON.Geometry = isMulti
        ? { type: "MultiLineString", coordinates: c.geometry as number[][][] }
        : { type: "LineString", coordinates: c.geometry as number[][] };
      features.push({
        type: "Feature",
        geometry,
        properties: { name: c.n, source: c.source, operators: c.operators, length_km: c.length_km, confidence: c.confidence },
      });
    }
  }

  const fc: GeoJSON.FeatureCollection = { type: "FeatureCollection", features };
  download(JSON.stringify(fc, null, 2), `${type}-${Date.now()}.geojson`, "application/geo+json");
}

function download(content: string, filename: string, mime: string): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
