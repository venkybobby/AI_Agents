# Production Architecture

This project should evolve as a governed agent runtime, not a toy prompt wrapper.

## Core boundaries

- Behavior policy lives in external rule packs under `rules/`.
- Python code loads, validates, and executes rules; it should not hide product policy in conditionals.
- Providers are adapters. The default remains `dry-run`; OpenAI is optional and configured through environment variables.
- Tools start read-only. Any future write-capable tool must have explicit approval gates and tests.
- End-to-end behavior is tested through the CLI, not only through unit-level functions.

## Runtime flow

```text
User goal
  -> Rule pack loaded and validated
  -> Planner builds rule-driven plan
  -> Optional read-only workspace inspection
  -> Provider generates normalized response
  -> Implementer proposes actions
  -> Reviewer evaluates actions against rule pack
  -> CLI returns approved / needs_input JSON
```

## Rule-pack contract

Current schema version: `1`.

The active rule pack controls:

- planner step titles and templates;
- reviewer blocked terms;
- finding message templates;
- approval and blocked summaries.

Rule packs must be validated before execution. Unknown template fields fail fast.

## End-to-end test target

The minimum production E2E test executes:

```powershell
python -m ai_agents "Prepare a production rollout plan" --workflow --rules rules/agent_rules.yaml
```

Expected behavior:

- process exits successfully;
- response is valid JSON;
- plan comes from the external rule pack;
- reviewer event is present;
- final status is deterministic.

## Domain packs

Domain-specific behavior belongs outside the core engine. A domain pack owns:

- its rule YAML;
- its reference/config schema;
- seed fixtures for local and CI tests;
- domain tool adapters;
- E2E tests for representative flows.

The first domain pack is `claims_anomaly`. Its business routing rules live in:

```text
domains/claims_anomaly/rules/claims_anomaly.yaml
```

Runtime thresholds and reference data are read from SQLite in local/CI mode. A production deployment can replace this adapter with a managed database while preserving the same rule-pack contract.
