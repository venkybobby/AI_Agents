# MVP Roadmap

This repo is for AI agent work only. It should not contain SARO / ClaimsAnomolyAgent source code, compliance artifacts, or project history.

## MVP 1 — Local Task Agent

Goal: prove the base developer loop.

- CLI entry point accepts a natural-language goal.
- Planner converts the goal into deterministic steps.
- Output is JSON so future tools can consume it.
- Unit tests pin the behavior.
- No external model calls or secrets required.

Status: complete.

## MVP 2 — Provider-backed Agent

Goal: add a real model provider behind a clean interface.

- Define provider protocol.
- Add environment-based configuration.
- Keep model calls isolated behind one adapter.
- Add dry-run mode for local development.
- Add basic safety controls: timeout, max retries, and redaction hooks.

Status: complete.

## MVP 3 — Tool-using Agent

Goal: let the agent inspect local files and propose changes.

- Read-only workspace inspection tools first.
- Explicit write boundary before file edits.
- Structured action log.
- Tests for tool routing and refusal paths.

Status: complete.

## MVP 4 — Multi-agent Workflow

Goal: coordinate planner, implementer, and reviewer roles.

- Shared task state.
- Role-specific prompts/providers.
- Reviewer gate before writing or publishing.
- Run summary generated at the end.

Status: complete.

## MVP 5 — OpenAI Provider + CI

Goal: make the agent useful with a real provider path while preserving local dry-run development.

- Add environment-backed provider settings.
- Add optional OpenAI provider adapter.
- Keep dry-run as the default provider.
- Mock provider tests; no live API calls in CI.
- Add GitHub Actions test workflow.

Status: complete.

## MVP 6 — Production Rule Packs + E2E

Goal: remove hardcoded planning/reviewer policy and make behavior governed by validated rule packs.

- External YAML rule pack under `rules/`.
- Loader validates schema, required fields, and templates.
- Planner steps come from the active rule pack.
- Reviewer gates come from the active rule pack.
- CLI supports `--rules`.
- E2E tests execute the real CLI.

Status: complete.

## MVP 7 — Claims Anomaly Domain Pack

Goal: convert claims anomaly planning, tools, reviewer gates, and thresholds into a production-style domain pack.

- Claims rules are YAML, not Python conditionals.
- Runtime thresholds/reference data are database-backed.
- Domain tool adapters read from reference data.
- E2E tests exercise seeded claims scenarios.
- Core engine remains generic.

Status: complete.

## MVP 8 — 837 Claim Transaction Demo Ingest

Goal: receive a demo 837P transaction and execute the claims anomaly flow end to end.

- Parse supported 837P demo segments into normalized claim data.
- Execute OIG, NCCI, medical necessity, and synthesis/routing steps.
- Use configurable claims rules and DB-backed thresholds/reference data.
- Add clean, NCCI violation, and OIG exclusion fixtures.
- Add E2E tests for 837-to-routing outcomes.

Status: complete.
