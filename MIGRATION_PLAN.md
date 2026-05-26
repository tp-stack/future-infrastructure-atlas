# FUTURE Infrastructure Atlas → Infrastructure Intelligence
## Migration Plan: Critique → Code

Maps every item from the product critique to specific files, features, and implementation steps.

---

## How to use this plan

Each section maps a critique theme to:
- **What exists today** (current state)
- **Files to modify** (exact paths)
- **What to change** (specific edits)
- **Priority** (P0=immediate, P1=next, P2=later)

---

## 1. Positioning: Atlas → Intelligence Product

**Critique:** The app presents as "Global Infrastructure Atlas" (passive browsing) instead of "compute infrastructure intelligence" (decision support).

### 1.1 Rename the product throughout the UI

| Current text | New text | Files |
|---|---|---|
| `Global Infrastructure Atlas` | `FUTURE Infrastructure Intelligence` | `frontend/src/App.tsx:540,615` |
| `Energy, internet & compute intelligence` | `AI compute, energy & data-center site intelligence` | `frontend/src/App.tsx:545` |
| `Loading infrastructure atlas...` | `Loading infrastructure intelligence...` | `frontend/src/App.tsx:439` |
| `<title>` in index.html | `FUTURE Infrastructure Intelligence` | `frontend/index.html` |
| `package.json` name | `future-infrastructure-intelligence` | `frontend/package.json` |

### 1.2 Add decision-mode entry points to the sidebar header

**File:** `frontend/src/App.tsx` (panel-header section, ~line 538)

Replace passive title with action-oriented buttons:
- "Run Site Selection" (primary CTA)
- "Explore Infrastructure" (secondary)
- "Compare Regions" (future)
- "Generate Report" (future)

These should sit prominently in the sidebar header, not buried in a toolbar.

### 1.3 Add product tagline to loading screen and error states

**File:** `frontend/src/App.tsx:440`

Update `loading-sub` text from generic to:
> "The decision layer for AI compute, energy, and data-center infrastructure."

### Priority: P0 — 3 edits

---

## 2. UX Hierarchy: Three-Level Intelligence System

**Critique:** The app lacks hierarchy between raw data, interpreted intelligence, risk warnings, and business decisions. Everything is at the same level.

### 2.1 Level 1 — Executive Answer (new component)

**Create:** `frontend/src/components/site_selection/ExecutiveSummary.tsx`

A top-of-sidebar card when a candidate site is selected showing:
- Overall suitability score (large, prominent)
- Confidence level with evidence quality badge
- Top 3 advantages (best scores)
- Top 3 risks (lowest scores + missing flags)
- Missing data register summary
- Recommended next action

**Props needed:** `CandidateSite` (already available in `siteSelectionApi.ts`)

### 2.2 Level 2 — Evidence (enhance existing)

**Modify:** `frontend/src/components/site_selection/EvidenceDrawer.tsx`

Currently shows all scores as equal bars. Restructure to:

```
┌─────────────────────────────────┐
│ EVIDENCE REPORT                 │
│                                 │
│ Grid proximity: 72/100          │
│   Evidence: Derived / OSM proxy │
│   Warning: Grid capacity unknown│
│                                 │
│ Fiber proximity: 61/100         │
│   Evidence: Proxy (PeeringDB)   │
│   Warning: Not fiber-confirmed  │
│ ...                             │
└─────────────────────────────────┘
```

### 2.3 Level 3 — Raw Map (already exists)

The map continues to be the canvas. No changes needed — but it should *support* Levels 1 and 2, not dominate.

### 2.4 Reorder the sidebar to reflect hierarchy

**File:** `frontend/src/App.tsx` (sidebar content, lines 537-604)

Reorder sidebar sections:
1. **Header** with decision-mode buttons (new)
2. **Executive Summary** (when candidate selected)
3. **Site Selection Panel** (when active)
4. **Layer & Filter controls** (de-emphasized)
5. **Stats / Legend / Sources** (scroll, bottom)

**Priority:** P0 for evidence quality labels, P1 for ExecutiveSummary

---

## 3. Trust: Evidence Quality System

**Critique:** Proxy data looks too certain. The app needs visible evidence grades everywhere.

### 3.1 Add evidence quality grades to SuitabilityScore

**File:** `frontend/src/components/site_selection/SuitabilityScore.tsx`

Add an `evidenceQuality` prop with values: `observed | derived | proxy | missing | unverified`

Render a colored badge below each score bar.

**Colors:**
- Observed: green `#22c55e`
- Derived: gold `#d69a13`
- Proxy: orange `#f59e0b`
- Missing: red `#ef4444`
- Unverified: gray `#6a6a72`

### 3.2 Add evidence quality to CandidateLocationCard

**File:** `frontend/src/components/site_selection/CandidateLocationCard.tsx`

Add a compact evidence-grade indicator next to each sub-score letter.

### 3.3 Add evidence quality to the backend evidence generator

**File:** `atlas/site_selection/evidence.py`

Every evidence sentence should include a quality label. Already partially done (lines distinguish substation vs HV line vs power plant proxy). Extend this to include explicit `[Observed]`, `[Derived]`, `[Proxy]`, `[Missing]`, `[Unverified]` tags in the generated text.

### 3.4 Add evidence quality to the CandidateSite model

**File:** `atlas/site_selection/models.py`

Add an `evidence_quality` field per dimension. We need a new data structure:

```python
class EvidenceQuality(str, enum.Enum):
    OBSERVED = "observed"
    DERIVED = "derived"
    PROXY = "proxy"
    MISSING = "missing"
    UNVERIFIED = "unverified"
```

Add to `ScoreBreakdown` or create `EvidenceQualityBreakdown` with a quality grade for each dimension.

### 3.5 Surface evidence quality in the API

**File:** `atlas/site_selection/schemas.py`
**File:** `atlas/site_selection/api.py`

Include `evidence_quality` in the API response for each candidate.

### 3.6 Surface evidence quality in the frontend API types

**File:** `frontend/src/api/siteSelectionApi.ts`

Add `evidenceQuality` field to `CandidateSite` interface, and `EvidenceQualityBreakdown` if needed.

**Priority:** P0 — this is the single most important trust fix

---

## 4. Killer Workflow: Compute Site Selection

**Critique:** The app needs one flagship workflow that makes people understand the value immediately.

### What exists today
- `SiteSelectionPanel.tsx` — form with profile dropdown, limit slider, generate button
- `CandidateLocationCard.tsx` — compact candidate card
- `EvidenceDrawer.tsx` — detail overlay
- Backend: `candidate_generator.py`, `scoring.py`, `confidence.py`, `evidence.py`, `report_builder.py`
- 4 compute profiles, 2 scoring profiles
- Export: JSON/CSV

### 4.1 Make Site Selection the primary CTA

**File:** `frontend/src/App.tsx`

- Move the "Analyze area" button to be always visible on the map (not only at zoom >= 8)
- Rename it from "Analyze visible area for data center locations" to **"Run Compute Site Selection"** (gold button, prominent)
- Auto-open the SiteSelectionPanel when this is clicked
- Add a "Site Selection" tab to the sidebar header as the primary action

### 4.2 Add a quick-start wizard

**Create:** `frontend/src/components/site_selection/SiteSelectionWizard.tsx`

A 3-step wizard overlay:
1. **Select region** — draw box, search country, or use current viewport
2. **Choose compute profile** — visual cards for each profile (not just dropdown). Show MW, use case, required area
3. **Run analysis** — single button, shows progress

### 4.3 Add candidate comparison

**Create:** `frontend/src/components/site_selection/CandidateComparison.tsx`

A side-by-side comparison view when user selects 2+ candidates:
- Table rows for each score dimension
- Color-coded cells
- Evidence quality badges
- Export comparison as CSV/PDF

### 4.4 Improve the "report export"

**File:** `atlas/site_selection/report_builder.py`

The report builder exists but only outputs JSON/CSV. Add:
- A sample downloadable HTML report in `frontend/public/sample-report.html`
- PDF-ready output format

### 4.5 Add a "run for current region" auto-flow

**File:** `frontend/src/App.tsx` (site selection trigger logic, lines 817-833)

Currently only triggers at zoom >= 8. Change to:
- Show "Run Compute Site Selection" at any zoom > 2
- When clicked, use current map bounds + auto-select "regional_compute_5mw" as default profile
- Show one-click flow

**Priority:** P0 — the killer workflow

---

## 5. Visual Identity: Institutional Intelligence

**Critique:** The UI is too technical/dashboard-like, not enough "strategic intelligence system."

### What exists today
- Dark theme: near-black background, gold accent, teal secondary
- CSS custom properties for all tokens
- Compact, data-dense layout

### 5.1 Strengthen the color system

**File:** `frontend/src/styles.css`

Add new CSS custom properties:
```css
--intel-panel: rgba(8, 10, 16, 0.92);  /* darker panels */
--intel-border: rgba(255, 255, 255, 0.06); /* subtler borders */
--intel-gold-dim: rgba(214, 154, 19, 0.08); /* barely-there gold */
--intel-ivory: #f0ebe0; /* light theme report panel */
```

### 5.2 Add report-card styling for evidence panels

**File:** `frontend/src/styles.css`

Add report-card styles:
```css
.report-card { ... }  /* ivory/dark panel, subtle border, structured layout */
.report-card-header { ... }  /* small caps, muted */
.report-card-section { ... }  /* separated sections */
```

These should be used by EvidenceDrawer, ExecutiveSummary, and any "report" views.

### 5.3 Reduce debug UI visibility

**File:** `frontend/src/App.tsx` (diagnostics panel, toolbar buttons)

The diagnostics panel, canvas overlay toggle, and test mode should be hidden by default and only show when:
- URL param `?debug=1` is present
- Or a hidden key combo is pressed (e.g., Ctrl+Shift+D)

Remove the "diagnostics" toolbar button from the default top bar.

### 5.4 Add the diagnostics toggle to a hidden Easter egg

**File:** `frontend/src/App.tsx`

Add `Ctrl+Shift+D` listener to toggle diagnostics visibility. This keeps the diagnostic power available without showing it to normal users.

### 5.5 Premium typographic hierarchy

**File:** `frontend/src/styles.css`

Add type scale tokens:
```css
--type-display: 18px;  /* for scores */
--type-title: 13px;    /* section headers */
--type-body: 11px;     /* body text */
--type-caption: 9px;   /* labels, metadata */
--type-micro: 8px;     /* badges, footnotes */
```

Apply consistently across all components. The current CSS uses ad-hoc font sizes everywhere.

**Priority:** P1 (except 5.3/5.4 which are P0 — hide debug UI now)

---

## 6. Missing Data as a Feature

**Critique:** Missing datasets should become a professional risk signal, not an apology.

### What exists today
- `MissingDataFlags.tsx` — maps flag keys to human-readable labels
- `EvidenceDrawer.tsx` — shows flags in the evidence overlay
- Backend: `MissingDataFlag` enum with 13 flags in `models.py`
- `confidence.py` — penalizes scores for missing flags

### 6.1 Add Due Diligence Gap Register (new component)

**Create:** `frontend/src/components/site_selection/DueDiligenceGapRegister.tsx`

A structured table component showing:

| Category | Status | Impact | Risk | Action Required |
|---|---|---|---|---|
| Grid capacity | Unknown (proxy) | Score -15 | High | Utility data required |
| Zoning | Not verified | Score -10 | High | Local permitting check |
| Flood risk | Dataset missing | Confidence -5 | Medium | FEMA/local data |
| ... | ... | ... | ... | ... |

**Props:** `missingDataFlags: string[]`, `candidate: CandidateSite`

### 6.2 Upgrade missing data flag text from neutral to risk-aware

**File:** `frontend/src/components/site_selection/MissingDataFlags.tsx`

Current mapping (line 13+): `GRID_CAPACITY_UNKNOWN` → "Grid capacity unknown"

New mapping: add severity + recommendation:
```typescript
const FLAG_METADATA: Record<string, { label: string; severity: 'high' | 'medium' | 'low'; recommendation: string }> = {
  GRID_CAPACITY_UNKNOWN: {
    label: 'Grid capacity unknown',
    severity: 'high',
    recommendation: 'Utility interconnection study required before site commitment',
  },
  ...
};
```

### 6.3 Update backend evidence to include risk language

**File:** `atlas/site_selection/evidence.py`

Each evidence function should end with a risk-level note. For example, replace:
> "Flood risk assessment is based on proxy data only — no flood hazard dataset available."

With:
> "**Material due-diligence gap.** Flood risk data missing for this region. Independent flood-risk assessment required before investment, permitting, or site commitment."

### 6.4 Add the gap register to the API response

**File:** `atlas/site_selection/schemas.py`
**File:** `atlas/site_selection/api.py`

Add `due_diligence_gaps` field to the candidate response — a structured array of gap objects with category, status, risk level, and action items.

**Priority:** P0

---

## 7. Commercial Category Framing

**Critique:** The app needs to state what business it is in.

### 7.1 Add product statement to the app

**File:** `frontend/src/App.tsx` (sidebar header or top bar)

Add above the map:
> **"FUTURE Infrastructure Intelligence — the decision layer for AI compute, energy, and data-center site selection."**

### 7.2 Add proof pillars

**File:** `frontend/src/App.tsx` (sidebar header, below title)

Add three pillar indicators (as compact badges or icons):
1. **Infrastructure proximity** (power plant icon)
2. **Constraint intelligence** (shield icon)  
3. **Evidence-based reporting** (document icon)

Each with a brief label. These should be visible in the sidebar header.

### 7.3 Rename the API from "API Dashboard" to "Data & API"

**File:** `frontend/src/App.tsx` (sidebar header, line 546-549)

Change "API Dashboard" button label and description to be product-forward:
- Button text: "Enterprise Data & API"
- Description: "Pricing, keys, exports & institutional access"

**Priority:** P0

---

## 8. Workspace Architecture

**Critique:** The app is a viewer, not a workspace. Missing: saved sites, comparison, report history, project folders.

### 8.1 Saved candidate sites (localStorage MVP)

**Create:** `frontend/src/utils/projects.ts`

Lightweight localStorage-based project system:
```typescript
interface SavedProject {
  id: string;
  name: string;
  region: string;
  computeProfile: string;
  candidates: CandidateSite[];
  createdAt: string;
  notes: string;
}
```

Functions: `saveProject`, `loadProjects`, `deleteProject`, `exportProject`

### 8.2 Project sidebar panel

**Create:** `frontend/src/components/ProjectsPanel.tsx`

Left-side panel (or tab within sidebar) showing saved projects:
- List of projects with name, date, candidate count
- Click to load project (restore candidates)
- Delete / rename
- Export all

### 8.3 Candidate comparison (see 4.3)

### 8.4 Report history

**Create:** `frontend/src/components/ReportHistory.tsx`

Track export history in localStorage:
- Timestamp, region, profile, candidate count
- Link to re-export
- Auto-generated report names

### 8.5 Dataset versioning indicator

**File:** `frontend/src/components/SourcePanel.tsx`

Add dataset generation timestamp and version info from `atlas_core.json`. This already exists in `metadata.generated_at` — surface it more prominently.

**Priority:** P2 (except 8.1 which is P1)

---

## 9. Backend Evidence Quality System

**Critique:** The evidence system needs to explicitly tag proxy vs observed data.

### 9.1 Add EvidenceQuality enum

**File:** `atlas/site_selection/models.py`

```python
class EvidenceQuality(str, enum.Enum):
    OBSERVED = "observed"          # Directly measured / authoritative
    DERIVED = "derived"            # Computed from observed data
    PROXY = "proxy"                # Inferred from related data
    MISSING = "missing"            # Not available
    UNVERIFIED = "unverified"      # Exists but not reviewed
```

### 9.2 Add per-dimension evidence quality to CandidateSite

**File:** `atlas/site_selection/models.py`

Add to `CandidateSite`:
```python
# Per-dimension evidence quality
grid_evidence_quality: EvidenceQuality | None = None
fiber_evidence_quality: EvidenceQuality | None = None
land_evidence_quality: EvidenceQuality | None = None
climate_evidence_quality: EvidenceQuality | None = None
water_evidence_quality: EvidenceQuality | None = None
regulatory_evidence_quality: EvidenceQuality | None = None
market_evidence_quality: EvidenceQuality | None = None
```

### 9.3 Populate evidence quality in scoring functions

**File:** `atlas/site_selection/scoring.py`

Each `compute_*_score` function should determine the evidence quality for its dimension:
- Grid: `PROXY` if using power plant or HV line proxy, `DERIVED` if using substation proximity, `OBSERVED` if actual grid capacity data available
- Fiber: `PROXY` if using PeeringDB/data center proximity, `DERIVED` if using IXP data, `OBSERVED` if fiber route data
- Etc.

### 9.4 Add evidence quality to the evidence generator

**File:** `atlas/site_selection/evidence.py`

Each sentence should include an explicit `[Observed]`, `[Derived]`, `[Proxy]`, `[Missing]`, or `[Unverified]` tag.

### 9.5 Add evidence quality to schema and API response

**File:** `atlas/site_selection/schemas.py`

Add to `SiteSelectionCandidate` schema.

**Priority:** P0 (core trust fix)

---

## 10. CSS Architecture: Institutional Look

**Critique:** The CSS needs to support a premium, institutional visual language.

### 10.1 Add report-card, evidence-panel, and gap-register styles

**File:** `frontend/src/styles.css` (new section, ~line 3700+)

New CSS sections:
- `.report-card` — structured white/ivory card for evidence
- `.evidence-quality-badge` — colored badge for observed/derived/proxy/missing/unverified
- `.gap-register` — due diligence gap table
- `.executive-summary` — large score display, top advantages/risks
- `.intel-header` — product statement section

### 10.2 Add institutional color tokens

**File:** `frontend/src/styles.css:7-22`

New CSS custom properties:
```css
--intel-highlight: #d69a13;
--intel-success: #22c55e;
--intel-warning: #f59e0b;
--intel-danger: #ef4444;
--intel-observed: #22c55e;
--intel-derived: #d69a13;
--intel-proxy: #f59e0b;
--intel-missing: #ef4444;
--intel-unverified: #6a6a72;
--intel-panel-bg: rgba(8, 10, 16, 0.95);
--intel-report-bg: rgba(245, 240, 230, 0.04);
```

### 10.3 Add type scale

**File:** `frontend/src/styles.css`

```css
--type-display: 18px;
--type-title: 13px;
--type-body: 11px;
--type-caption: 9px;
--type-micro: 8px;
```

### 10.4 Current CSS audit for consistency

**File:** `frontend/src/styles.css`

Many components use ad-hoc font sizes. Audit and replace with type scale tokens:
- Search `font-size: 1[0-4]px` and `font-size: 9px` — most should become `var(--type-body)` or `var(--type-caption)`

**Priority:** P1

---

## 11. Concrete Implementation Order

### Phase 1: Trust & Positioning (Week 1) — P0

| Step | File(s) | Change | Estimated effort |
|---|---|---|---|
| 1 | `App.tsx:540,615,439` | Rename "Global Infrastructure Atlas" → "FUTURE Infrastructure Intelligence" | 15 min |
| 2 | `App.tsx:439-440` | Update loading text with decision-layer tagline | 5 min |
| 3 | `App.tsx:817-833` | Make "Run Compute Site Selection" always visible (not just zoom >= 8) | 10 min |
| 4 | `App.tsx:537-550` | Add decision-mode buttons to sidebar header | 30 min |
| 5 | `App.tsx:644-693` | Hide diagnostics/canvas/test toggles from default toolbar (behind `?debug=1` or Ctrl+Shift+D) | 20 min |
| 6 | `App.tsx:546-549` | Rename "API Dashboard" → "Enterprise Data & API" | 5 min |
| 7 | `SuitabilityScore.tsx` | Add `evidenceQuality` prop + colored badge | 30 min |
| 8 | `CandidateLocationCard.tsx` | Add mini evidence-quality indicators | 20 min |
| 9 | `MissingDataFlags.tsx` | Upgrade with severity levels and recommendations | 30 min |
| 10 | `DueDiligenceGapRegister.tsx` NEW | Create the gap register component | 45 min |
| 11 | `EvidenceDrawer.tsx` | Restructure with evidence quality badges + gap register | 30 min |
| 12 | `models.py` | Add `EvidenceQuality` enum + per-dimension fields | 20 min |
| 13 | `scoring.py` | Populate evidence quality in each scoring function | 30 min |
| 14 | `evidence.py` | Add `[Observed/Derived/Proxy/Missing/Unverified]` tags | 20 min |
| 15 | `schemas.py`, `api.py` | Surface evidence quality in API response | 15 min |
| 16 | `siteSelectionApi.ts` | Update TypeScript interfaces for evidence quality | 10 min |

### Phase 2: Killer Workflow (Week 2) — P0/P1

| Step | File(s) | Change | Estimated effort |
|---|---|---|---|
| 17 | `SiteSelectionPanel.tsx` | Add quick-start wizard mode (3-step: region → profile → run) | 2 h |
| 18 | `SiteSelectionPanel.tsx` | Add "run for current region" one-click flow | 30 min |
| 19 | `CandidateComparison.tsx` NEW | Side-by-side candidate comparison table | 2 h |
| 20 | `ExecutiveSummary.tsx` NEW | Top-level decision card showing score, confidence, top risks, next action | 1.5 h |
| 21 | `report_builder.py` | Add sample HTML report generation | 1 h |
| 22 | `public/sample-report.html` NEW | Beautiful downloadable sample report | 1 h |

### Phase 3: Visual Polish (Week 3) — P1

| Step | File(s) | Change | Estimated effort |
|---|---|---|---|
| 23 | `styles.css` | Add institutional color tokens, type scale, report-card styles | 1 h |
| 24 | `styles.css` | Apply type scale tokens throughout | 2 h |
| 25 | `App.tsx` | Update sidebar layout order: decisions → evidence → layers | 30 min |
| 26 | All components | Apply report-card styling to evidence panels | 1 h |
| 27 | `styles.css` + `App.tsx` | Add product statement + proof pillars | 20 min |

### Phase 4: Workspace (Week 4) — P2

| Step | File(s) | Change | Estimated effort |
|---|---|---|---|
| 28 | `projects.ts` NEW | localStorage-based project system | 1 h |
| 29 | `ProjectsPanel.tsx` NEW | Project management sidebar panel | 1.5 h |
| 30 | `App.tsx` | Hook projects into sidebar | 30 min |
| 31 | `ReportHistory.tsx` NEW | Export history tracking | 30 min |
| 32 | `SourcePanel.tsx` | Surface dataset version/date more prominently | 15 min |

---

## 12. File Change Summary

### New files to create (12)

| File | Purpose |
|---|---|
| `frontend/src/components/site_selection/ExecutiveSummary.tsx` | Level 1 — executive decision card |
| `frontend/src/components/site_selection/DueDiligenceGapRegister.tsx` | Structured due diligence gap table |
| `frontend/src/components/site_selection/SiteSelectionWizard.tsx` | 3-step quick-start wizard |
| `frontend/src/components/site_selection/CandidateComparison.tsx` | Side-by-side candidate comparison |
| `frontend/src/components/ProjectsPanel.tsx` | Project management sidebar |
| `frontend/src/components/ReportHistory.tsx` | Export history tracking |
| `frontend/src/utils/projects.ts` | localStorage project system |
| `frontend/public/sample-report.html` | Sample downloadable report |

### Existing files to modify (17)

| File | Changes |
|---|---|
| `frontend/index.html` | Page title |
| `frontend/package.json` | Package name |
| `frontend/src/App.tsx` | Product renaming, decision-mode header, reordered sidebar, hide debug UI, trigger logic |
| `frontend/src/styles.css` | Color tokens, type scale, report-card styles, evidence quality badges, gap register |
| `frontend/src/api/siteSelectionApi.ts` | Evidence quality + gap register types |
| `frontend/src/components/site_selection/SuitabilityScore.tsx` | Evidence quality prop + badge |
| `frontend/src/components/site_selection/CandidateLocationCard.tsx` | Mini evidence indicators |
| `frontend/src/components/site_selection/EvidenceDrawer.tsx` | Restructured with quality + gap register |
| `frontend/src/components/site_selection/MissingDataFlags.tsx` | Severity + recommendations |
| `frontend/src/components/site_selection/SiteSelectionPanel.tsx` | Wizard mode, one-click flow |
| `frontend/src/components/SourcePanel.tsx` | Dataset version prominence |
| `atlas/site_selection/models.py` | EvidenceQuality enum, per-dimension quality fields |
| `atlas/site_selection/scoring.py` | Populate evidence quality in scores |
| `atlas/site_selection/evidence.py` | Evidence quality tags in text |
| `atlas/site_selection/schemas.py` | Evidence quality + gap register in schemas |
| `atlas/site_selection/api.py` | Surface new fields in response |
| `atlas/site_selection/report_builder.py` | HTML report output |

---

## 13. Risk Register for Migration

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Sidebar becomes too long with new sections | High | Medium | Use collapsible sections + tabs; keep executive summary always visible |
| Evidence quality reveals too many "proxy" labels | Medium | Medium | This is actually the goal — it builds trust through transparency |
| New component volume degrades load time | Low | Medium | All new components should be lazy-loaded via `Suspense` |
| Backend evidence quality changes break frontend | Low | High | Keep the API response backward-compatible; add fields without changing existing ones |
| Users confused by "decision mode" vs "explore mode" | Medium | Low | Clear toggle between modes; default to explore mode for returning users |
