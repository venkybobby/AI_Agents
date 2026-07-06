# AI_Agents

Standalone workspace for AI agent experiments and implementations.

This repository is intentionally separate from the SARO / ClaimsAnomolyAgent project so the histories and codebases do not mix.

## MVP 1: Local Task Agent

The first MVP is a dependency-light command-line agent that turns a user goal into a small execution plan. It does not call external AI providers yet; the point is to establish the repo structure, test loop, and clean extension points before adding model integrations.

Run it locally:

```powershell
python -m pip install -e ".[dev]"
python -m ai_agents "Plan a research workflow for market analysis" --provider dry-run
```

Provider selection defaults to `AI_AGENTS_PROVIDER`, falling back to `dry-run`.

Inspect a workspace in read-only mode:

```powershell
python -m ai_agents "Review this repo shape" --inspect .
```

Run tests:

```powershell
python -m pytest
```

## Roadmap

See [docs/MVP_ROADMAP.md](docs/MVP_ROADMAP.md).
