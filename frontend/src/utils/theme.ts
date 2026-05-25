const STORAGE_KEY = "atlas-theme";

export type AtlasTheme = "dark" | "light";

function normalizeTheme(theme: string | null): AtlasTheme {
  return theme === "light" ? "light" : "dark";
}

export function getTheme(): AtlasTheme {
  if (typeof localStorage === "undefined") return "dark";
  return normalizeTheme(localStorage.getItem(STORAGE_KEY));
}

export function setTheme(theme: AtlasTheme): void {
  localStorage.setItem(STORAGE_KEY, theme);
  document.documentElement.dataset.theme = theme;
}

export function toggleTheme(): AtlasTheme {
  const current = getTheme();
  const next = current === "dark" ? "light" : "dark";
  setTheme(next);
  return next;
}
