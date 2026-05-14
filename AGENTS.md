# Agent Instructions

This repository can use `agentmemory` as an optional local Codex MCP memory layer.

## Memory Use

- At the start of substantial work, use agentmemory recall if MCP tools are available, especially for Atlas map rendering, data safety, PMTiles, deployment, and validation history.
- After a validated fix, save a concise memory with the issue, root cause, changed files, validation commands, deployment result, and remaining risk.
- Store summaries only. Do not store secrets, API keys, local credentials, raw dataset rows, raw CSV/GeoJSON/KMZ/JSON contents, or restricted source material.
- Treat memory as advisory context. Current user instructions, repository code, tests, registry validation, and storage safety checks override memory.

## Atlas Safety Invariants

- Do not download new datasets unless explicitly asked.
- Do not invent coordinates or infer submarine cable routes.
- Do not silently geocode data centers as exact coordinates.
- Do not commit raw source files or anything under `data/raw`, `data/cache`, `data/processed`, `data/tiles`, `data/logs`, or `data/reports`.
- Keep `frontend/tsconfig.tsbuildinfo` untracked.
- Preserve source/license warnings and provenance guardrails.
- Keep PeeringDB facilities labeled as public facilities/interconnection data, not as every data center in the world.

