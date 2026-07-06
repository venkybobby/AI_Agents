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

Status: in progress.

## MVP 3 — Tool-using Agent

Goal: let the agent inspect local files and propose changes.

- Read-only workspace inspection tools first.
- Explicit write boundary before file edits.
- Structured action log.
- Tests for tool routing and refusal paths.

Status: queued.

## MVP 4 — Multi-agent Workflow

Goal: coordinate planner, implementer, and reviewer roles.

- Shared task state.
- Role-specific prompts/providers.
- Reviewer gate before writing or publishing.
- Run summary generated at the end.

Status: queued.
