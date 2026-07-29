# EvalForge

An evaluation-first LLM workflow workbench, designed as a forward-deployed engineering portfolio project.

## Why this is different

It makes the delivery decisions inspectable: test cases encode a customer workflow, graders expose failure modes, every result carries latency evidence, and high-risk cases are explicitly marked for human review. It runs fully in deterministic demo mode and can call the OpenAI Responses API with strict JSON schema output when an API key is supplied.

## Run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
pytest
```

Open http://localhost:8000. Copy `.env.example` to `.env` and export its variables before choosing `mode: openai`.

## Architecture and safety

- FastAPI boundary separates UI, evaluation dataset, grading, and model calls.
- Deterministic demo baseline makes review reproducible without leaking credentials.
- Strict structured output avoids fragile free-text parsing.
- OpenAI calls fail closed when no key exists; the API key is never served to the browser.
- Dataset includes a human-review path for access/security-sensitive work.

## Interview walkthrough

Start in demo mode, inspect case E-02, then explain how a customer-specific corpus, calibrated graders, trace persistence, and an approval workflow would replace the sample dataset in production.
