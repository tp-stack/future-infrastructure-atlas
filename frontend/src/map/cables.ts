import type maplibregl from "maplibre-gl";
import type { Cable, CableGeometry } from "./types";

export type CableViewMode = "all" | "company" | "selected";

export interface CableFilterState {
  operator: string;
  mode: CableViewMode;
  selectedCableName: string;
}

export interface CableCompanyStat {
  operator: string;
  key: string;
  count: number;
  color: string;
}

export interface CableCompanyMeta {
  operators: string[];
  primaryOperator: string;
  operatorGroup: string;
  operatorColor: string;
  operatorCount: number;
  isCompanyMatch: boolean;
  isSelected: boolean;
  isDimmed: boolean;
}

export const DEFAULT_CABLE_FILTERS: CableFilterState = {
  operator: "",
  mode: "all",
  selectedCableName: "",
};

export const OTHER_CABLE_OPERATOR = "Other operators";
export const UNKNOWN_CABLE_OPERATOR = "Unknown operator";

export const CABLE_OPERATOR_PALETTE = [
  "#087ea4",
  "#d69a13",
  "#2f6b4f",
  "#a855f7",
  "#d45050",
  "#3b82f6",
  "#f97316",
  "#14b8a6",
  "#e11d48",
  "#64748b",
];

const OPERATOR_ALIASES: Record<string, string> = {
  "meta platforms": "Meta",
  "facebook": "Meta",
  "google llc": "Google",
  "google cloud": "Google",
  "alphabet": "Google",
  "vodafone carrier services": "Vodafone",
  "softbank corp": "SoftBank",
  "orange s.a.": "Orange",
  "china mobile international": "China Mobile",
  "china telecom global": "China Telecom",
  "china unicom global": "China Unicom",
  "ntt communications": "NTT",
  "tata communications limited": "Tata Communications",
};

function normalizeOperatorName(operator: string): string {
  const cleaned = operator.replace(/\s+/g, " ").trim();
  if (!cleaned) return "";
  const alias = OPERATOR_ALIASES[cleaned.toLowerCase()];
  return alias || cleaned;
}

function statKey(operator: string): string {
  return operator.toLowerCase();
}

export function splitCableOperators(raw: string | undefined | null): string[] {
  if (!raw) return [];
  const seen = new Set<string>();
  const operators: string[] = [];

  for (const part of raw.split(/[,;|]/)) {
    const operator = normalizeOperatorName(part);
    const key = statKey(operator);
    if (!operator || seen.has(key)) continue;
    seen.add(key);
    operators.push(operator);
  }

  return operators;
}

export function buildCableCompanyStats(cables: Cable[], limit = 8): CableCompanyStat[] {
  const counts = new Map<string, { operator: string; count: number }>();

  for (const cable of cables) {
    if (cable.mapped_status !== "mapped") continue;
    for (const operator of splitCableOperators(cable.operators)) {
      const key = statKey(operator);
      const current = counts.get(key);
      if (current) current.count += 1;
      else counts.set(key, { operator, count: 1 });
    }
  }

  return Array.from(counts.values())
    .sort((a, b) => b.count - a.count || a.operator.localeCompare(b.operator))
    .slice(0, limit)
    .map((stat, index) => ({
      operator: stat.operator,
      key: statKey(stat.operator),
      count: stat.count,
      color: CABLE_OPERATOR_PALETTE[index % CABLE_OPERATOR_PALETTE.length],
    }));
}

export function getCableCompanyMeta(
  cable: Pick<Cable, "n" | "operators">,
  stats: CableCompanyStat[],
  filters: CableFilterState = DEFAULT_CABLE_FILTERS,
): CableCompanyMeta {
  const operators = splitCableOperators(cable.operators);
  const topByKey = new Map(stats.map((stat) => [stat.key, stat]));
  const selectedKey = statKey(filters.operator);
  const selectedStat = selectedKey ? topByKey.get(selectedKey) : undefined;
  const primaryOperator = operators[0] || UNKNOWN_CABLE_OPERATOR;
  const matchingTopOperator = operators.map((op) => topByKey.get(statKey(op))).find(Boolean);
  const selectedOperatorMatch = selectedKey
    ? operators.some((operator) => statKey(operator) === selectedKey)
    : false;
  const isSelected = Boolean(filters.selectedCableName && cable.n === filters.selectedCableName);

  let operatorGroup = matchingTopOperator?.operator || OTHER_CABLE_OPERATOR;
  let operatorColor = matchingTopOperator?.color || "#6b7280";

  if (selectedStat && selectedOperatorMatch) {
    operatorGroup = selectedStat.operator;
    operatorColor = selectedStat.color;
  } else if (primaryOperator === UNKNOWN_CABLE_OPERATOR) {
    operatorGroup = UNKNOWN_CABLE_OPERATOR;
    operatorColor = "#8d93a1";
  }

  const isCompanyMatch = !filters.operator || selectedOperatorMatch;
  const isDimmed =
    (filters.mode === "company" && Boolean(filters.operator) && !selectedOperatorMatch) ||
    (filters.mode === "selected" && Boolean(filters.selectedCableName) && !isSelected) ||
    (filters.mode === "selected" && !filters.selectedCableName && Boolean(filters.operator) && !selectedOperatorMatch);

  return {
    operators,
    primaryOperator,
    operatorGroup,
    operatorColor,
    operatorCount: operators.length,
    isCompanyMatch,
    isSelected,
    isDimmed,
  };
}

export function shouldIncludeCable(
  cable: Pick<Cable, "n" | "operators">,
  stats: CableCompanyStat[],
  filters: CableFilterState = DEFAULT_CABLE_FILTERS,
): boolean {
  const meta = getCableCompanyMeta(cable, stats, filters);
  if (filters.mode !== "selected") return true;
  if (filters.selectedCableName) return meta.isSelected;
  if (filters.operator) return meta.isCompanyMatch;
  return true;
}

export function cableColorExpression(stats: CableCompanyStat[]): maplibregl.ExpressionSpecification {
  const matchParts: unknown[] = [];
  for (const stat of stats) matchParts.push(stat.operator, stat.color);
  matchParts.push(OTHER_CABLE_OPERATOR, "#6b7280", UNKNOWN_CABLE_OPERATOR, "#8d93a1", "#087ea4");
  return ["match", ["get", "operator_group"], ...matchParts] as unknown as maplibregl.ExpressionSpecification;
}

export function cableOperatorContainsExpression(operator: string): maplibregl.ExpressionSpecification {
  return [
    ">=",
    ["index-of", operator, ["coalesce", ["get", "operators"], ""]],
    0,
  ] as maplibregl.ExpressionSpecification;
}

export function pmtilesCableColorExpression(stats: CableCompanyStat[]): maplibregl.ExpressionSpecification {
  const cases: unknown[] = [];
  for (const stat of stats) {
    cases.push(cableOperatorContainsExpression(stat.operator), stat.color);
  }
  cases.push("#087ea4");
  return ["case", ...cases] as maplibregl.ExpressionSpecification;
}

export function cableBounds(geometry: CableGeometry | undefined | null): {
  minLon: number;
  minLat: number;
  maxLon: number;
  maxLat: number;
} | null {
  if (!geometry || geometry.length === 0) return null;
  const isMultiLine = Array.isArray(geometry[0]) && Array.isArray((geometry[0] as unknown[])[0]);
  const lines = isMultiLine ? (geometry as number[][][]) : [geometry as number[][]];
  let minLon = Infinity;
  let minLat = Infinity;
  let maxLon = -Infinity;
  let maxLat = -Infinity;

  for (const line of lines) {
    for (const coord of line) {
      const lon = Number(coord[0]);
      const lat = Number(coord[1]);
      if (!Number.isFinite(lon) || !Number.isFinite(lat)) continue;
      minLon = Math.min(minLon, lon);
      minLat = Math.min(minLat, lat);
      maxLon = Math.max(maxLon, lon);
      maxLat = Math.max(maxLat, lat);
    }
  }

  if (!Number.isFinite(minLon) || !Number.isFinite(minLat)) return null;
  return { minLon, minLat, maxLon, maxLat };
}
