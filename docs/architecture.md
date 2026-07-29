# Architecture

The AI Support Evaluation Suite separates evaluation contracts, provider behavior, grading, and run
storage so each can change without hiding the evidence used for release
decisions.

```text
versioned dataset ──► candidate adapter ──► structured output
                                                │
                                                ▼
                                    deterministic task graders
                                                │
                            ┌───────────────────┴──────────────────┐
                            ▼                                      ▼
                      run + result ledger                  baseline comparison
```

## Invariants

- Dataset IDs are unique and every case validates before a run starts.
- Live-provider execution requires explicit API key and model configuration.
- Candidate output is sanitized before it is graded or persisted.
- High-risk human-review misses are a first-class metric.
- Comparisons identify both aggregate deltas and individual regressed cases.
