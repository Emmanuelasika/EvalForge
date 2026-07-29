"""AI support evaluation API: runs, regression evidence, and comparisons."""
from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .core import (
    EvalCase,
    ModelOutput,
    aggregate,
    deterministic_output,
    grade,
    load_dataset,
    sanitize_output,
    serialize_case,
    serialize_grade,
)
from .store import RunStore

ROOT = Path(__file__).parent.parent
DATASET = Path(
    os.getenv(
        "EVALFORGE_DATASET",
        str(Path(__file__).parent / "data" / "support_triage.json"),
    )
)
DATABASE = Path(os.getenv("EVALFORGE_DATABASE", str(ROOT / "evalforge.sqlite3")))
store = RunStore(DATABASE)
app = FastAPI(title="AI Support Evaluation Suite", version="2.0.0")


class RunRequest(BaseModel):
    name: str = Field(default="Support triage regression", min_length=3, max_length=120)
    mode: Literal["deterministic", "openai"] = "deterministic"
    candidate: Literal["reference", "unsafe", "misrouted"] = "reference"
    model: str | None = Field(default=None, max_length=120)
    prompt: str = Field(
        default="Classify the request, identify missing information, and propose a safe next action.",
        min_length=10,
        max_length=4_000,
    )


def cases() -> list[EvalCase]:
    return load_dataset(DATASET)


async def openai_output(case: EvalCase, request: RunRequest) -> ModelOutput:
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(400, "OPENAI_API_KEY is required for mode=openai.")
    model = request.model or os.getenv("OPENAI_MODEL")
    if not model:
        raise HTTPException(400, "Set model in the request or OPENAI_MODEL in the environment.")
    from openai import AsyncOpenAI

    client = AsyncOpenAI()
    schema = {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": ["billing", "access", "security", "technical"]},
            "human_review": {"type": "boolean"},
            "next_action": {"type": "string"},
            "rationale": {"type": "string"},
        },
        "required": ["category", "human_review", "next_action", "rationale"],
        "additionalProperties": False,
    }
    response = await client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": request.prompt},
            {"role": "user", "content": case.input},
        ],
        text={"format": {"type": "json_schema", "name": "triage", "strict": True, "schema": schema}},
    )
    return ModelOutput.model_validate_json(response.output_text)


@app.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok", "dataset_cases": len(cases()), "persistence": "sqlite-wal", "live_provider_configured": bool(os.getenv("OPENAI_API_KEY"))}


@app.get("/api/cases")
def list_cases() -> dict[str, object]:
    return {"cases": [serialize_case(case) for case in cases()]}


@app.get("/api/runs")
def list_runs(limit: int = Query(default=20, ge=1, le=100)) -> dict[str, object]:
    return {"runs": store.list_runs(limit)}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict[str, object]:
    run = store.get(run_id)
    if not run:
        raise HTTPException(404, "Evaluation run not found")
    return run


@app.post("/api/runs", status_code=201)
async def create_run(request: RunRequest) -> dict[str, object]:
    results: list[dict[str, object]] = []
    for case in cases():
        started = time.perf_counter()
        raw_output = deterministic_output(case, request.candidate) if request.mode == "deterministic" else await openai_output(case, request)
        output = sanitize_output(raw_output)
        result_grade = grade(case, output)
        results.append(
            {
                "case_id": case.id,
                "input": case.input,
                "severity": case.severity,
                "requires_human": case.requires_human,
                "output": output.model_dump(),
                **serialize_grade(result_grade),
                "latency_ms": round((time.perf_counter() - started) * 1_000, 2),
                "review_status": "pending" if case.requires_human else "not_required",
            }
        )
    model = request.model or (os.getenv("OPENAI_MODEL") if request.mode == "openai" else f"deterministic/{request.candidate}")
    run = {
        "id": f"run_{uuid4().hex[:12]}",
        "name": request.name,
        "candidate": request.candidate,
        "mode": request.mode,
        "model": model,
        "created_at": datetime.now(UTC).isoformat(),
        "metrics": aggregate(results),
    }
    store.save(run, results)
    return {**run, "results": results}


@app.get("/api/compare")
def compare(baseline: str, candidate: str) -> dict[str, object]:
    first, second = store.get(baseline), store.get(candidate)
    if not first or not second:
        raise HTTPException(404, "Both evaluation runs must exist")
    keys = ("pass_rate", "average_score", "critical_pass_rate", "human_review_misses", "average_latency_ms")
    delta = {key: round(second["metrics"][key] - first["metrics"][key], 3) for key in keys}
    regressions = [
        result["case_id"]
        for result in second["results"]
        if not result["passed"] and any(item["case_id"] == result["case_id"] and item["passed"] for item in first["results"])
    ]
    return {"baseline": first["id"], "candidate": second["id"], "delta": delta, "regressed_cases": regressions}


@app.get("/")
def home() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "index.html")
