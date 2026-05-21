const STORAGE_KEY = "atlas-theme";

export function getTheme(): string {
  return localStorage.getItem(STORAGE_KEY) || "dark";
}

export function setTheme(theme: string): void {
  localStorage.setItem(STORAGE_KEY, theme);
  document.documentElement.dataset.theme = theme;
}

export function toggleTheme(): string {
  const current = getTheme();
  const next = current === "dark" ? "light" : "dark";
  setTheme(next);
  return next;
}
