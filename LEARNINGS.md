# Learnings

## 2026-05-14 - Ingestion Fixture Validation Baseline

- Issue fixed: `run_fixture_ingestion` fixture tests failed on canonical output fields and Windows path assertions.
- Root cause: the fixture wrapper returned legacy `run_ingestion` JSONL records while newer fixture tests expected canonical layer records; tests also checked POSIX path substrings.
- Solution: convert fixture-wrapper JSONL output to canonical asset fields and make path assertions platform-neutral.
- Validation: `python scripts/init_storage.py`; `python scripts/check_registry.py`; `python scripts/build_web_map_data.py --max-public-mb 5`; `python scripts/check_frontend_data.py`; `pytest -q`; `python -m atlas.storage .`; `cd frontend && npm.cmd install && npm.cmd run build`.
- Deployment: skipped; this was a backend/test baseline fix, not a frontend rendering change.
- Remaining risk: `atlas_core.json` can still drift from regenerated `atlas_web_data.json` cable counts.
