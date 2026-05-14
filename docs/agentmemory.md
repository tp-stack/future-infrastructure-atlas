# Agentmemory Integration

This repository is prepared for local agent memory through [rohitg00/agentmemory](https://github.com/rohitg00/agentmemory). It is an agent tooling integration only. It is not part of the Atlas frontend runtime, data pipeline, or deployment artifact.

## Current Setup

On this machine, Codex MCP is configured globally with:

```powershell
codex mcp add agentmemory --env AGENTMEMORY_URL=http://localhost:3111 --env AGENTMEMORY_TOOLS=all -- npx -y @agentmemory/mcp
```

Verify the MCP entry:

```powershell
codex mcp get agentmemory
```

Start or verify the local memory server from this repo:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_agentmemory.ps1
```

The API health endpoint is:

```text
http://localhost:3111/agentmemory/health
```

The local viewer is:

```text
http://localhost:3113
```

## Runtime Notes

- `agentmemory` version verified during setup: `0.9.12`.
- The installed Codex binary exposes `codex mcp`, but not the README's `codex plugin install` command, so this repo uses the MCP integration path.
- On this Windows machine, `agentmemory` uses Docker Desktop to run the `iii` engine. Docker Desktop must be running, or a native `iii-engine` installation must be available.
- The helper script attempts to start Docker Desktop if needed, launches `npx -y @agentmemory/agentmemory`, waits for health, and writes logs under the user temp directory.

## Safety Policy

Use memory for durable project lessons and validated engineering facts. Do not save raw infrastructure data, restricted dataset content, secrets, local credentials, or bulk file contents. Current repository validation and user instructions always override recalled memory.
