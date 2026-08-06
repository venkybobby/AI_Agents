"""Opt-in LLM judge check for medical necessity reasoning groundedness."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
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
BOUNDARY_MIN = 0.4
BOUNDARY_MAX = 0.6
PASS_MIN = 0.6
SYNTHETIC = Path(__file__).resolve().parent / "golden" / "groundedness_synthetic.jsonl"

PASS_GROUNDED = "PASS_GROUNDED"
FLAG_BOUNDARY_REVIEW = "FLAG_BOUNDARY_REVIEW"
FAIL_UNGROUNDED = "FAIL_UNGROUNDED"


@dataclass(frozen=True)
class GroundednessSyntheticCase:
    case_id: str
    source_record_id: str
    reasoning: str
    expectation: str
    rationale: str


@dataclass(frozen=True)
class GroundednessRow:
    record_id: str
    score: float
    verdict: str
    boundary_warning: bool
    reason: str | None


@dataclass(frozen=True)
class GroundednessRun:
    synthetic_rows: list[GroundednessRow]
    real_rows: list[GroundednessRow]
    classification: str


def judge_enabled() -> bool:
    """Return True only when the Vertex judge is explicitly enabled."""

    return os.getenv("SARO_EVAL_JUDGE", "").strip().lower() == "vertex"


def groundedness_verdict(score: float) -> str:
    """Classify the strict G-Eval score without hiding boundary uncertainty."""

    if BOUNDARY_MIN <= score <= BOUNDARY_MAX:
        return FLAG_BOUNDARY_REVIEW
    if score > PASS_MIN:
        return PASS_GROUNDED
    return FAIL_UNGROUNDED


def is_boundary_score(score: float) -> bool:
    return BOUNDARY_MIN <= score <= BOUNDARY_MAX


def classification_exit_code(classification: str) -> int:
    """Return CI exit code for the groundedness judge classification."""

    return 1 if classification == FAIL_UNGROUNDED else 0


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
    from deepeval.test_case import SingleTurnParams

    return GEval(
        name="StrictGroundedness",
        criteria=(
            "Every claim in the reasoning must be explicitly supported by the "
            "context (clinical notes + EM requirement). Any added fact, cause, "
            "clinical judgment, policy detail, payer action, patient condition, "
            "or corrective assumption not present in the context means FAIL, "
            "even if plausible. Do not give credit for likely, reasonable, "
            "common, or inferred facts unless the context states them explicitly."
        ),
        evaluation_params=[
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.CONTEXT,
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


def load_synthetic_cases(path: str | Path = SYNTHETIC) -> list[GroundednessSyntheticCase]:
    """Load permanent synthetic judge-validation fixtures."""

    cases: list[GroundednessSyntheticCase] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            raw = json.loads(line)
            cases.append(
                GroundednessSyntheticCase(
                    case_id=str(raw["case_id"]),
                    source_record_id=str(raw["source_record_id"]),
                    reasoning=str(raw["reasoning"]),
                    expectation=str(raw["expectation"]),
                    rationale=str(raw.get("rationale", "")),
                )
            )
    return cases


def evaluate_case(
    *,
    metric_name: str,
    judge: Any,
    record_id: str,
    reasoning: str,
    context: str,
) -> GroundednessRow:
    """Evaluate one reasoning/context pair."""

    case = build_case(reasoning, context)
    metric = make_geval_metric(judge)
    metric.measure(case)
    time.sleep(PACE_SECONDS)

    score = float(metric.score)
    verdict = groundedness_verdict(score)
    boundary = is_boundary_score(score)
    if boundary:
        print(
            f"      boundary score {score} on {metric_name}: "
            f"{FLAG_BOUNDARY_REVIEW}"
        )
    return GroundednessRow(
        record_id=record_id,
        score=score,
        verdict=verdict,
        boundary_warning=boundary,
        reason=getattr(metric, "reason", None),
    )


def evaluate_synthetic_fixtures(
    *,
    judge: Any,
    domain: Any,
    records_by_id: dict[str, Any],
) -> list[GroundednessRow]:
    """Run synthetic bad reasoning first to prove the judge can catch fabrication."""

    metric_name = "geval-strict"
    rows: list[GroundednessRow] = []
    print("phase=synthetic_judge_validation")
    for fixture in load_synthetic_cases():
        record = records_by_id[fixture.source_record_id]
        context = build_context(record.claim_data, em_requirement_context(record, domain))
        row = evaluate_case(
            metric_name=metric_name,
            judge=judge,
            record_id=fixture.case_id,
            reasoning=fixture.reasoning,
            context=context,
        )
        rows.append(row)
        print(
            f"{fixture.case_id}: score={row.score} verdict={row.verdict} "
            f"expectation={fixture.expectation}"
        )
        print(f"  rationale: {fixture.rationale}")
        print(f"  reason: {row.reason}")
    return rows


def rerun_boundary_or_failure(
    *,
    metric_name: str,
    judge: Any,
    record_id: str,
    reasoning: str,
    context: str,
) -> list[GroundednessRow]:
    """Repeat unstable-looking cases before trusting a single judge score."""

    reruns = int(os.getenv("SARO_EVAL_JUDGE_RERUNS", "3"))
    if reruns <= 1:
        return []

    rows: list[GroundednessRow] = []
    for index in range(reruns - 1):
        rows.append(
            evaluate_case(
                metric_name=metric_name,
                judge=judge,
                record_id=f"{record_id}#rerun-{index + 2}",
                reasoning=reasoning,
                context=context,
            )
        )
    return rows


def evaluate_real_golden_groundedness(
    *,
    judge: Any,
    domain: Any,
    records: list[Any],
) -> list[GroundednessRow]:
    """Run strict groundedness checks for real golden medical necessity reasoning."""

    metric_name = "geval-strict"
    rows: list[GroundednessRow] = []

    print("phase=real_golden_reasoning")
    for record in medical_necessity_records(records):
        result = run_record(record, domain)
        medical_output = result.tool_outputs.get("medical_necessity_check")
        if not isinstance(medical_output, dict):
            continue
        reasoning = str(medical_output.get("reasoning", ""))
        context = build_context(record.claim_data, em_requirement_context(record, domain))
        row = evaluate_case(
            metric_name=metric_name,
            judge=judge,
            record_id=record.record_id,
            reasoning=reasoning,
            context=context,
        )
        print(
            f"{record.record_id}: score={row.score} verdict={row.verdict} "
            f"boundary={row.boundary_warning}"
        )
        print(f"  reason: {row.reason}")

        if row.verdict != PASS_GROUNDED:
            consistency_rows = rerun_boundary_or_failure(
                metric_name=metric_name,
                judge=judge,
                record_id=record.record_id,
                reasoning=reasoning,
                context=context,
            )
            if consistency_rows:
                scores = ", ".join(str(item.score) for item in consistency_rows)
                verdicts = ", ".join(item.verdict for item in consistency_rows)
                print(
                    f"  consistency_reruns: scores=[{scores}] verdicts=[{verdicts}]"
                )

        rows.append(row)
    return rows


def synthetic_validation_passed(rows: list[GroundednessRow]) -> bool:
    """Require obvious fabrication to be caught before trusting real results."""

    by_id = {row.record_id: row for row in rows}
    obvious = by_id.get("SYN-OBVIOUS-GC01")
    return obvious is not None and obvious.verdict == FAIL_UNGROUNDED


def classify_groundedness_run(
    synthetic_rows: list[GroundednessRow],
    real_rows: list[GroundednessRow],
) -> str:
    """Classify the judge run for CI."""

    if not synthetic_validation_passed(synthetic_rows):
        return FAIL_UNGROUNDED
    if any(row.verdict == FAIL_UNGROUNDED for row in real_rows):
        return FAIL_UNGROUNDED
    if any(row.verdict == FLAG_BOUNDARY_REVIEW for row in real_rows + synthetic_rows):
        return FLAG_BOUNDARY_REVIEW
    return PASS_GROUNDED


def evaluate_groundedness() -> GroundednessRun:
    """Run synthetic judge validation first, then real golden reasoning."""

    domain = build_domain()
    records = load_golden_records()
    records_by_id = {record.record_id: record for record in records}
    judge = build_vertex_judge()
    print(f"judge={judge.get_model_name()} metric=geval-strict")
    print("scope=medical_necessity_check.reasoning is deterministic template text")

    synthetic_rows = evaluate_synthetic_fixtures(
        judge=judge,
        domain=domain,
        records_by_id=records_by_id,
    )
    if not synthetic_validation_passed(synthetic_rows):
        return GroundednessRun(synthetic_rows, [], FAIL_UNGROUNDED)

    real_rows = evaluate_real_golden_groundedness(
        judge=judge,
        domain=domain,
        records=records,
    )
    classification = classify_groundedness_run(synthetic_rows, real_rows)
    return GroundednessRun(synthetic_rows, real_rows, classification)


def print_summary(run: GroundednessRun) -> None:
    synthetic_caught = sum(
        1 for row in run.synthetic_rows if row.verdict == FAIL_UNGROUNDED
    )
    synthetic_flagged = sum(
        1 for row in run.synthetic_rows if row.verdict == FLAG_BOUNDARY_REVIEW
    )
    real_grounded = sum(1 for row in run.real_rows if row.verdict == PASS_GROUNDED)
    real_flagged = sum(
        1 for row in run.real_rows if row.verdict == FLAG_BOUNDARY_REVIEW
    )
    real_failed = sum(1 for row in run.real_rows if row.verdict == FAIL_UNGROUNDED)
    print(
        f"summary: classification={run.classification} "
        f"synthetic_caught={synthetic_caught} "
        f"synthetic_flagged={synthetic_flagged} "
        f"real_grounded={real_grounded} "
        f"real_flagged={real_flagged} "
        f"real_failed={real_failed}"
    )


def main() -> int:
    if not judge_enabled():
        print("judge not configured, skipping groundedness check")
        return 0

    run = evaluate_groundedness()
    print_summary(run)
    return classification_exit_code(run.classification)


if __name__ == "__main__":
    raise SystemExit(main())
