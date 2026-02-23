# Report 03: Failure Handling (Corrupted PDF Path)

## Goal
Demonstrate robust handling when input is malformed/corrupted.

## Input
- File: `/Users/pathum/Dev/flatrock_codex_2/agent-contract-processor/data/demo_contracts/demo_03_failure_corrupted_pipeline.pdf`
- Expected outcome: failure path (non-success response and/or logged pipeline error)

## Why this report matters
1. End-to-end behavior: proves system does not silently succeed on broken files.
2. Extraction quality guardrails: invalid source should never produce fabricated structured output.
3. RAG relevance: retrieval/validation should not execute as normal for unreadable documents.
4. Error handling quality: checks clear failure propagation and logged diagnostics.

## Run command
```bash
cd /Users/pathum/Dev/flatrock_codex_2/agent-contract-processor
BASE_URL=http://localhost:8000 \
WEBHOOK_API_KEY="$WEBHOOK_SECRET" \
ADMIN_API_KEY="$ADMIN_API_KEY" \
python3 scripts/generate_demo_reports.py
```

## Evidence produced
Generated/updated by script:
- `/Users/pathum/Dev/flatrock_codex_2/agent-contract-processor/docs/reports/report_03_failure_bad_file.md`

Look for:
- non-success HTTP status OR explicit error response
- no false positive approval
- error details in app logs and `processing_logs` (pipeline_error)
