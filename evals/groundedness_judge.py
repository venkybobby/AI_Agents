"""Opt-in LLM judge check for medical necessity reasoning groundedness."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

from evals.claims_eval_harness import (
    build_domain,
    em_requirement_context,
    load_golden_records,
    medical_necessity_records,
    run_record,
)

JUDGE_MODEL = "gemini-2.5-flash"
JUDGE_TEMPERATURE = 0.0
PACE_SECONDS = float(os.getenv("SARO_EVAL_JUDGE_SLEEP_SECONDS", "10"))


@dataclass(frozen=True)
class GroundednessRow:
    record_id: str
    score: float
    verdict: str
    boundary_warning: bool
    reason: str | None


def judge_enabled() -> bool:
    """Return True only when the Vertex judge is explicitly enabled."""

    return os.getenv("SARO_EVAL_JUDGE", "").strip().lower() == "vertex"


def metric_says_grounded(metric_name: str, metric: Any) -> bool:
    """Port of Week 1 boundary-band score handling.

    True means the metric thinks the answer is clean. Scores in 0.4-0.6 are
    printed as low confidence and should be routed to human review rather than
    silently passed or failed.
    """

    if 0.4 <= metric.score <= 0.6:
        print(
            f"      ⚠ boundary score {metric.score} on {metric_name} "
            "— low confidence, flag for human review"
        )
    if metric_name == "hallucination":
        return metric.score <= 0.5
    return metric.score >= 0.5


def is_boundary_score(score: float) -> bool:
    return 0.4 <= score <= 0.6


def build_context(claim_data: dict[str, Any], requirement: dict[str, Any] | None) -> str:
    """Build the only source context allowed for reasoning claims."""

    requirement_text = "No E/M requirement row found."
    if requirement is not None:
        requirement_text = (
            f"cpt_code={requirement['cpt_code']}; "
            f"min_time_minutes={requirement['min_time_minutes']}; "
            f"max_time_minutes={requirement['max_time_minutes']}; "
            f"mdm_level={requirement['mdm_level']}"
        )
    return "\n".join(
        [
            f"clinical_notes={claim_data.get('clinical_notes', '')}",
            f"em_requirement={requirement_text}",
        ]
    )


def make_geval_metric(judge: Any) -> Any:
    """Create the strict G-Eval metric lazily to avoid default CI model imports."""

    from deepeval.metrics import GEval
    from deepeval.test_case import LLMTestCaseParams

    return GEval(
        name="StrictGroundedness",
        criteria=(
            "Every claim in the reasoning must be explicitly supported by the "
            "context (clinical notes + EM requirement). Any added fact, cause, "
            "clinical judgment, or policy detail not present in the context "
            "means FAIL, even if plausible."
        ),
        evaluation_params=[
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.CONTEXT,
        ],
        model=judge,
        async_mode=False,
    )


def build_case(reasoning: str, context: str) -> Any:
    """Build a DeepEval case lazily to keep the skip path dependency-free."""

    from deepeval.test_case import LLMTestCase

    return LLMTestCase(
        input="Evaluate whether the medical necessity reasoning is grounded.",
        actual_output=reasoning,
        context=[context],
    )


def build_vertex_judge() -> Any:
    """Build the Vertex Gemini judge only for explicit judge runs."""

    from deepeval.models.base_model import DeepEvalBaseLLM
    from google import genai
    from google.genai import types

    class VertexGeminiJudge(DeepEvalBaseLLM):
        """Minimal Vertex judge via google-genai. No LangChain layer."""

        def __init__(self) -> None:
            self.client = genai.Client()

        def load_model(self) -> Any:
            return self.client

        def generate(self, prompt: str) -> str:
            response = self.client.models.generate_content(
                model=JUDGE_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=JUDGE_TEMPERATURE),
            )
            return response.text or ""

        async def a_generate(self, prompt: str) -> str:
            response = await self.client.aio.models.generate_content(
                model=JUDGE_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=JUDGE_TEMPERATURE),
            )
            return response.text or ""

        def get_model_name(self) -> str:
            return f"vertex:{JUDGE_MODEL}@t={JUDGE_TEMPERATURE}"

    return VertexGeminiJudge()


def evaluate_groundedness() -> list[GroundednessRow]:
    """Run strict groundedness checks for medical necessity reasoning."""

    domain = build_domain()
    judge = build_vertex_judge()
    metric_name = "geval-strict"
    rows: list[GroundednessRow] = []

    print(f"judge={judge.get_model_name()} metric={metric_name}")
    for record in medical_necessity_records(load_golden_records()):
        result = run_record(record, domain)
        medical_output = result.tool_outputs.get("medical_necessity_check")
        if not isinstance(medical_output, dict):
            continue
        reasoning = str(medical_output.get("reasoning", ""))
        context = build_context(record.claim_data, em_requirement_context(record, domain))
        case = build_case(reasoning, context)
        metric = make_geval_metric(judge)
        metric.measure(case)
        time.sleep(PACE_SECONDS)

        grounded = metric_says_grounded(metric_name, metric)
        boundary = is_boundary_score(float(metric.score))
        verdict = "GROUNDED" if grounded else "FAIL"
        if boundary:
            verdict = "HUMAN_REVIEW"
        rows.append(
            GroundednessRow(
                record_id=record.record_id,
                score=float(metric.score),
                verdict=verdict,
                boundary_warning=boundary,
                reason=getattr(metric, "reason", None),
            )
        )
        print(
            f"{record.record_id}: score={metric.score} verdict={verdict} "
            f"boundary={boundary}"
        )
        print(f"  reason: {getattr(metric, 'reason', None)}")
    return rows


def print_summary(rows: list[GroundednessRow]) -> None:
    grounded = sum(1 for row in rows if row.verdict == "GROUNDED")
    flagged = sum(1 for row in rows if row.verdict == "HUMAN_REVIEW")
    failed = sum(1 for row in rows if row.verdict == "FAIL")
    print(f"summary: {grounded} grounded / {flagged} flagged for review / {failed} failed")


def main() -> int:
    if not judge_enabled():
        print("judge not configured, skipping groundedness check")
        return 0

    rows = evaluate_groundedness()
    print_summary(rows)
    return 1 if any(row.verdict == "FAIL" for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
