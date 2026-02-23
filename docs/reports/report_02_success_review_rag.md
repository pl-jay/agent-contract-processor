# Report 02: End-to-End Review (RAG/Policy Threshold Path)

## Goal
Demonstrate that policy-aware validation routes a high-value contract to human review.

## Input
- File: `/Users/pathum/Dev/flatrock_codex_2/agent-contract-processor/data/demo_contracts/demo_02_review_high_value.pdf`
- Expected decision: `review`

## Why this report matters
1. End-to-end execution: proves full pipeline runs successfully on complex/high-value input.
2. Extraction quality: verifies structured extraction still works at higher amounts.
3. RAG value: validates threshold-driven compliance logic materially affects outcome.
4. Reliability: confirms risky contracts are not auto-approved.

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
- `/Users/pathum/Dev/flatrock_codex_2/agent-contract-processor/docs/reports/report_02_success_review_rag.md`

Look for:
- HTTP status 200/202 on `/email-webhook`
- response `decision=review`
- item appears in `/review-queue`
- violations list includes threshold-related evidence
