"""Command-line entry point for the local task agent."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from .agent import run_agent
from .providers import ProviderError, provider_from_env, provider_from_name
from .tools import ToolError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-agents",
        description="Create a deterministic starter plan for a goal.",
    )
    parser.add_argument("goal", help="Goal for the agent to plan.")
    parser.add_argument(
        "--provider",
        help="Provider to use. Defaults to AI_AGENTS_PROVIDER or dry-run.",
    )
    parser.add_argument(
        "--inspect",
        metavar="PATH",
        help="Read-only inspect a workspace directory and include a summary.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        provider = (
            provider_from_name(args.provider)
            if args.provider is not None
            else provider_from_env()
        )
        result = run_agent(args.goal, provider, inspect_path=args.inspect)
    except (ProviderError, ToolError, ValueError) as exc:
        parser.error(str(exc))

    print(json.dumps(result.to_dict(), indent=2))
    return 0
