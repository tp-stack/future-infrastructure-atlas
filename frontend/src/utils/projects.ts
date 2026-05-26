import type { CandidateSite } from "../api/siteSelectionApi";

const STORAGE_KEY = "future-intelligence-projects";

export interface SavedProject {
  id: string;
  name: string;
  region: string;
  computeProfile: string;
  scoringProfile: string;
  candidates: CandidateSite[];
  mapBounds: [number, number, number, number] | null;
  createdAt: string;
  updatedAt: string;
  notes: string;
}

function generateId(): string {
  return `proj_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

export function loadProjects(): SavedProject[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as SavedProject[];
  } catch {
    return [];
  }
}

export function saveProject(project: SavedProject): void {
  const projects = loadProjects();
  const idx = projects.findIndex((p) => p.id === project.id);
  if (idx >= 0) {
    projects[idx] = { ...project, updatedAt: new Date().toISOString() };
  } else {
    projects.unshift({ ...project, id: generateId(), createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() });
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(projects));
}

export function deleteProject(id: string): void {
  const projects = loadProjects().filter((p) => p.id !== id);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(projects));
}

export function createProjectFromCandidates(
  name: string,
  candidates: CandidateSite[],
  computeProfile: string,
  scoringProfile: string,
  region: string,
  mapBounds: [number, number, number, number] | null,
): SavedProject {
  return {
    id: generateId(),
    name,
    region,
    computeProfile,
    scoringProfile,
    candidates,
    mapBounds,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    notes: "",
  };
}

export function renameProject(id: string, name: string): void {
  const projects = loadProjects();
  const project = projects.find((p) => p.id === id);
  if (project) {
    project.name = name;
    project.updatedAt = new Date().toISOString();
    localStorage.setItem(STORAGE_KEY, JSON.stringify(projects));
  }
}
