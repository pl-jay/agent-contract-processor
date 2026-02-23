# Report 01: End-to-End Success (Auto-Approve Path)

## Goal
Demonstrate the full workflow succeeds for a clean, low-risk contract and gets auto-approved.

## Input
- File: `/Users/pathum/Dev/flatrock_codex_2/agent-contract-processor/data/demo_contracts/demo_01_auto_approve.pdf`
- Expected decision: `approved`

## Why this report matters
1. End-to-end execution: proves webhook -> extraction -> RAG/validation -> routing -> persistence works.
2. Extraction quality: checks vendor/date/value are structured and usable.
3. RAG value: confirms no threshold violation for a low-value contract.
4. Reliability: confirms no unexpected failure path for normal input.

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
- `/Users/pathum/Dev/flatrock_codex_2/agent-contract-processor/docs/reports/report_01_success_auto_approve.md`

Look for:
- HTTP status 200/202 on `/email-webhook`
- response `decision=approved`
- approved contract appears in `/approved-contracts`
- extracted fields present (`vendor_name`, `total_value`, dates)
