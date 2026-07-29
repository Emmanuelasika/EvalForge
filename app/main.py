"""EvalForge: a small, inspectable LLM evaluation workbench.

The app deliberately keeps the evaluation contract in code: expected behavior,
failure categories, latency, cost estimates, and reviewer decisions are all
visible rather than hidden behind a chat interface.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

app = FastAPI(title="EvalForge", version="1.0.0")
DATASET = Path(__file__).parent.parent / "data" / "support_triage.json"


class RunRequest(BaseModel):
    model: str = Field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-5.6-terra"))
    prompt: str = "Classify the request, identify missing information, and propose a safe next action."
    mode: Literal["demo", "openai"] = "demo"


def load_cases() -> list[dict]:
    return json.loads(DATASET.read_text())


def grade(case: dict, output: dict) -> tuple[bool, list[str]]:
    failures = []
    if output["category"] != case["expected_category"]:
        failures.append("wrong_category")
    if case["requires_human"] and not output["human_review"]:
        failures.append("missed_human_review")
    if not output["next_action"]:
        failures.append("no_next_action")
    return not failures, failures


def demo_response(case: dict) -> dict:
    # A deterministic baseline makes the repository runnable without credentials.
    return {
        "category": case["expected_category"],
        "human_review": case["requires_human"],
        "next_action": case["expected_action"],
        "rationale": "Deterministic local baseline for repeatable evaluation.",
    }


async def openai_response(case: dict, request: RunRequest) -> dict:
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(400, "OPENAI_API_KEY is required for mode=openai. Use demo mode otherwise.")
    from openai import AsyncOpenAI
    client = AsyncOpenAI()
    schema = {"type": "object", "properties": {
        "category": {"type": "string", "enum": ["billing", "access", "security", "technical"]},
        "human_review": {"type": "boolean"},
        "next_action": {"type": "string"},
        "rationale": {"type": "string"}
    }, "required": ["category", "human_review", "next_action", "rationale"], "additionalProperties": False}
    response = await client.responses.create(
        model=request.model,
        input=[{"role": "system", "content": request.prompt}, {"role": "user", "content": case["input"]}],
        text={"format": {"type": "json_schema", "name": "triage", "strict": True, "schema": schema}},
    )
    return json.loads(response.output_text)


@app.get("/health")
def health():
    return {"status": "ok", "dataset_cases": len(load_cases())}


@app.get("/api/cases")
def cases():
    return load_cases()


@app.post("/api/runs")
async def run(request: RunRequest):
    results = []
    for case in load_cases():
        started = time.perf_counter()
        output = demo_response(case) if request.mode == "demo" else await openai_response(case, request)
        passed, failures = grade(case, output)
        results.append({"id": case["id"], "input": case["input"], "output": output, "passed": passed,
                        "failures": failures, "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                        "review_status": "pending" if case["requires_human"] else "not_required"})
    return {"model": request.model, "mode": request.mode, "pass_rate": sum(x["passed"] for x in results) / len(results), "results": results}


@app.get("/")
def home():
    return FileResponse(Path(__file__).parent / "static" / "index.html")
