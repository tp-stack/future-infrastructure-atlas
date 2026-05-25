export interface UrlParams {
  fuelType?: string;
  country?: string;
  minMw?: number;
  searchQuery?: string;
  layers?: string;
  sidebar?: string;
}

export function readUrlParams(): UrlParams {
  const params = new URLSearchParams(window.location.search);
  return {
    fuelType: params.get("fuel") || undefined,
    country: params.get("country") || undefined,
    minMw: params.get("mw") ? Number(params.get("mw")) : undefined,
    searchQuery: params.get("q") || undefined,
    layers: params.get("layers") || undefined,
    sidebar: params.get("sidebar") || undefined,
  };
}

export function writeUrlParams(updates: Record<string, string | number | boolean | null>): void {
  const url = new URL(window.location.href);
  for (const [key, value] of Object.entries(updates)) {
    if (value === null || value === false || value === "") {
      url.searchParams.delete(key);
    } else {
      url.searchParams.set(key, String(value));
    }
  }
  window.history.replaceState({}, "", url.toString());
}

export function layersToParam(layers: Record<string, boolean>): string | null {
  const active: string[] = [];
  if (layers.power_plants) active.push("pp");
  if (layers.cables) active.push("cb");
  if (layers.data_centers) active.push("dc");
  if (layers.power_lines) active.push("pl");
  if (layers.substations) active.push("ss");
  if (layers.heatmap) active.push("hm");
  const defaultActive = ["pp", "cb", "dc", "pl", "ss"];
  if (active.length === defaultActive.length && defaultActive.every((key, index) => active[index] === key)) return null;
  return active.length === 0 ? "none" : active.join(",");
}

export function paramToLayers(param: string | undefined): Record<string, boolean> | null {
  if (!param) return null;
  if (param === "none") {
    return {
      power_plants: false,
      cables: false,
      data_centers: false,
      power_lines: false,
      substations: false,
      heatmap: false,
    };
  }
  const active = param.split(",");
  return {
    power_plants: active.includes("pp"),
    cables: active.includes("cb"),
    data_centers: active.includes("dc"),
    power_lines: active.includes("pl"),
    substations: active.includes("ss"),
    heatmap: active.includes("hm"),
  };
}
