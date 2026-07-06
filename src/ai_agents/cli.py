"""Command-line entry point for the local task agent."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from .planner import create_plan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-agents",
        description="Create a deterministic starter plan for a goal.",
    )
    parser.add_argument("goal", help="Goal for the agent to plan.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    plan = create_plan(args.goal)
    print(json.dumps(plan.to_dict(), indent=2))
    return 0
