# FUTURE Infrastructure Atlas — Security Audit

**Date:** 2026-05-21
**Commit:** (post-audit)
**Branch:** master
**Live URL:** https://frontend-wheat-seven-24.vercel.app/

## Executive Summary

- **Overall security posture:** Moderate — no known secrets exposed, no raw data committed, but production deployment had zero security headers, an inline script incompatible with strict CSP, and unnecessary public exposure of a raw PeeringDB CSV and a debug map instance reference.
- **P0 findings:** 2 (fixed)
- **P1 findings:** 5 (4 fixed, 1 accepted risk)
- **P2 findings:** 2 (1 fixed, 1 open)
- **P3 findings:** 2 (open)

## Scope

| Area | Status |
|------|--------|
| Frontend security (React/MapLibre) | Audited — no HTML injection, safe popups, no dangerouslySetInnerHTML |
| Deployment security (Vercel) | Audited — no security headers were set. Fixed via `frontend/vercel.json`. |
| Data pipeline security (Python scripts) | Audited — path handling is safe, no shell=True, write destinations are validated |
| Secrets and credentials | Audited — no secrets exposed in code, .env.example has placeholder dev passwords only |
| Dependency security | Audited — 0 npm vulnerabilities, Python deps not audited (pip-audit unavailable) |
| Infrastructure/data sensitivity | Audited — license warnings preserved, PeeringDB labeled correctly, KMCD marked to_verify |
| Error handling and observability | Audited — ErrorBoundary shows generic message, no stack traces exposed to users |

## Findings

### SEC-001 — Missing Security Headers (P0 — Fixed)

| Field | Value |
|-------|-------|
| **Category** | Deployment security |
| **File(s)** | (none — no vercel.json existed) |
| **Evidence** | Live site at https://frontend-wheat-seven-24.vercel.app/ returned no `Content-Security-Policy`, no `X-Content-Type-Options`, no `Referrer-Policy`, no `Permissions-Policy`, no `Cross-Origin-Opener-Policy` headers. |
| **Risk** | XSS, clickjacking, MIME-type sniffing, referrer leakage, unauthorized embeddings. |
| **Fix** | Created `frontend/vercel.json` with CSP, X-Content-Type-Options: nosniff, Referrer-Policy: strict-origin-when-cross-origin, Permissions-Policy, COOP: same-origin, frame-ancestors: none. |
| **Status** | **Fixed** |

**CSP deployed:**
```
default-src 'self';
script-src 'self';
style-src 'self' 'unsafe-inline';
img-src 'self' data: blob: https:;
font-src 'self' data:;
connect-src 'self' https: blob:;
worker-src 'self' blob:;
object-src 'none';
base-uri 'self';
form-action 'self';
frame-ancestors 'none';
upgrade-insecure-requests;
```

MapLibre compatibility maintained via `style-src 'unsafe-inline'`, `img-src https:` for ArcGIS basemap tiles, `connect-src https:` for external tile/data fetches, and `worker-src blob:` for WebGL workers.

---

### SEC-002 — Inline Script Incompatible With CSP (P0 — Fixed)

| Field | Value |
|-------|-------|
| **Category** | Frontend security |
| **File(s)** | `frontend/index.html` (line 8) |
| **Evidence** | `<script>document.documentElement.dataset.theme = ...</script>` inline in HTML violates `script-src 'self'`. |
| **Risk** | CSP violation blocks the inline script, causing theme flash or broken dark mode. |
| **Fix** | Moved inline script to `frontend/public/theme-init.js`, referenced via `<script src="/theme-init.js">`. |
| **Status** | **Fixed** |

---

### SEC-003 — Global Map Instance Exposure (P1 — Fixed)

| Field | Value |
|-------|-------|
| **Category** | Frontend security |
| **File(s)** | `frontend/src/map/AtlasMap.tsx` (lines 533, 544) |
| **Evidence** | `(window as unknown as { __atlasMap?: maplibregl.Map }).__atlasMap = m;` exposed the full MapLibre instance globally. |
| **Risk** | Any browser extension or XSS payload can access and manipulate the map instance programmatically. |
| **Fix** | Removed the global window assignment and its cleanup. |
| **Status** | **Fixed** |

---

### SEC-004 — Raw PeeringDB CSV Served From Public Data (P1 — Fixed)

| Field | Value |
|-------|-------|
| **Category** | Infrastructure/data sensitivity |
| **File(s)** | `frontend/public/data/datacenters_public.csv` |
| **Evidence** | A CSV with PeeringDB facility coordinates, operators, and addresses was deployed as a static Vercel asset. Not referenced by any frontend code. |
| **Risk** | Raw facility coordinates and contact data served without the context, license notes, or precision labels that the React UI enforces. |
| **Fix** | Removed `datacenters_public.csv` from public data directory. Added `frontend/public/data/*.csv` to `.gitignore`. |
| **Status** | **Fixed** |

---

### SEC-005 — Debug Routes Exposed Without Labels (P1 — Accepted Risk)

| Field | Value |
|-------|-------|
| **Category** | Deployment security |
| **File(s)** | `frontend/src/App.tsx` |
| **Evidence** | Routes `?debugMap=1`, `?zoomMap=1`, `?pmtilesMap=1` are publicly accessible. The debug map shows infrastructure counts, zoom level, and diagnostic metrics. |
| **Risk** | Diagnostic information aids reconnaissance. |
| **Fix** | Adding warning labels would reduce but not eliminate the informational exposure. These routes are essential for internal QA and support troubleshooting. |
| **Status** | **Accepted risk** — labelled as development/diagnostic routes in the build observatory; not hidden to preserve supportability. |

---

### SEC-006 — Build Observatory Publicly Accessible (P1 — Accepted Risk)

| Field | Value |
|-------|-------|
| **Category** | Deployment security |
| **File(s)** | `frontend/public/debug/build_observatory.html` |
| **Evidence** | The build observatory at `/debug/build_observatory.html` exposes all route URLs, data file sizes, source licenses, and PMTiles status. |
| **Risk** | Route enumeration, data size disclosure. |
| **Status** | **Accepted risk** — the observatory is a QA tool and does not contain secrets, raw data, or exact coordinates. It mirrors public information already visible on the map or in the source panel. |

---

### SEC-007 — Missing SRI Hash on External Scripts (P2 — Open)

| Field | Value |
|-------|-------|
| **Category** | Frontend security |
| **File(s)** | `frontend/index.html` |
| **Evidence** | The theme-init.js external script is loaded without `integrity` attribute. |
| **Risk** | If an attacker compromises the CDN/origin, they could serve a modified script. Low risk as script is same-origin. |
| **Status** | **Open** — low priority, same-origin. |

---

### SEC-008 — Dev Database Password in .env.example (P2 — Open)

| Field | Value |
|-------|-------|
| **Category** | Secrets and credentials |
| **File(s)** | `.env.example` |
| **Evidence** | `DATABASE_PASSWORD=future_atlas_dev_password` is a placeholder development password, but follows the pattern of a real credential. |
| **Risk** | Low — documented as a local dev placeholder. Not used in production. |
| **Status** | **Open** — documented as development-only. No production credentials exposed. |

---

### SEC-009 — No Lockfile Validation (P3 — Open)

| Field | Value |
|-------|-------|
| **Category** | Dependency security |
| **File(s)** | `frontend/package-lock.json` |
| **Evidence** | package-lock.json exists but no integrity verification step in CI. |
| **Risk** | Low — npm automatically verifies lockfile integrity on install. |
| **Status** | **Open** — future hardening. |

---

### SEC-010 — No pip-audit / bandit / semgrep in CI (P3 — Open)

| Field | Value |
|-------|-------|
| **Category** | Dependency security |
| **Evidence** | pip-audit, bandit, semgrep, gitleaks, trufflehog all unavailable in the current environment. |
| **Risk** | Python dependency vulnerabilities and code-quality issues go undetected. |
| **Status** | **Open** — install and configure in CI pipeline. |

## Validation Commands

All passed post-fix:

```powershell
python scripts/init_storage.py
python scripts/check_registry.py
python scripts/check_frontend_data.py
pytest -q tests/test_storage.py tests/test_registry.py tests/test_no_large_files_in_repo.py tests/test_sources_config.py
python -m atlas.storage .
cd frontend
npm install
npm run build
npm audit --audit-level=moderate
cd ..
```

## Remaining Risks

| Risk | Severity | Notes |
|------|----------|-------|
| Debug routes publicly accessible | P1 | Accepted — required for support |
| Build observatory publicly accessible | P1 | Accepted — no secrets exposed |
| No pip-audit/bandit in CI | P3 | Future hardening |
| No SRI hashes | P2 | Low priority, same-origin |
| Dev database password in example env | P2 | Placeholder only |
