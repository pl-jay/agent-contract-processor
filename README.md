# Vendor Contract Compliance Agent

Production-ready backend for processing vendor contract emails with PDF attachments, extracting structured contract data with an LLM, validating against policy documents using RAG, and routing outcomes for auto-approval or human review.

## Architecture

### High-level flow

1. Email webhook receives metadata + PDF (`POST /email-webhook`) with `X-API-KEY` auth and returns a structured processing response.
2. File is persisted temporarily and processed asynchronously by a LangGraph workflow.
3. PDF text is extracted and normalized (PyMuPDF).
4. LLM extracts strict structured contract JSON.
5. A data-cleaning phase normalizes noisy values (dates, numbers, currency-like strings, nullish text) before schema validation.
6. RAG retriever pulls relevant internal policies from Chroma.
7. LLM validation agent checks policy violations and risk.
8. Deterministic router sends contract to review queue or auto-approval.
9. Results, decisions, and logs are persisted to database.

### LangGraph state machine

The orchestrator uses these states in sequence:

- `ingest`
- `extract`
- `validate`
- `route`
- `persist`

## Why RAG improves decision quality

Without retrieval, validation relies on model priors and can miss organization-specific policy rules. This system embeds internal policy docs and retrieves only the most relevant chunks per contract, grounding validation decisions in current policy text and reducing hallucinated compliance reasoning.

## Failure handling strategy

- Invalid/non-PDF uploads are rejected at API boundary (extension/content-type/PDF signature checks).
- Uploads above configured size are rejected.
- Corrupted or unreadable PDFs raise structured processing errors.
- Extraction/validation enforce strict JSON schema and retry malformed outputs.
- Pipeline failures are logged into `processing_logs` with error context.
- Routing is deterministic and conservative (`review_queue`) when confidence is low or critical fields are missing.
- Pipeline execution uses a bounded worker pool with idempotency-key support and timeout-based deferred response fallback.

## Project structure

```text
agent-contract-processor/
│
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── errors.py
│   │   ├── schemas.py
│   │   ├── security.py
│   ├── logging/
│   │   ├── logging_config.py
│   ├── processing/
│   │   ├── document_processor.py
│   │   ├── pdf_utils.py
│   ├── agents/
│   │   ├── extraction_agent.py
│   │   ├── validation_agent.py
│   ├── routing/
│   │   ├── router.py
│   ├── orchestration/
│   │   ├── orchestrator.py
│   ├── routers/
│   │   ├── email_router.py
│   │   ├── review_router.py
│   ├── services/
│   │   ├── persistence_service.py
│   │   ├── pipeline_executor.py
│   │   ├── structured_llm.py
│   │   ├── webhook_service.py
│   ├── providers/
│   │   ├── factory.py
│   ├── rag/
│   │   ├── indexer.py
│   │   ├── retriever.py
│   │   ├── chroma_settings.py
│   │   ├── chroma_telemetry.py
│   ├── db/
│   │   ├── models.py
│   │   ├── session.py
│
├── data/policies/
├── docker/
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── README.md
```

## Database schema

Tables:

- `processed_contracts`
- `review_queue`
- `processing_logs`

Models are SQLAlchemy 2.x with naming conventions to stay migration-friendly (Alembic-ready).

Alembic scaffolding is included:

- `alembic.ini`
- `migrations/env.py`
- `migrations/versions/`

## Local run

### 1) Install dependencies

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Configure environment

Set at minimum:

```bash
export ANTHROPIC_API_KEY="your_anthropic_key"
export WEBHOOK_SECRET="set_a_long_random_webhook_secret"
# Optional (required only for review/admin endpoints):
export ADMIN_API_KEY="set_a_different_long_random_admin_key"
export ALLOWED_ORIGINS="http://localhost:5678,http://localhost:3000,http://127.0.0.1:3000"

# Must be model ids enabled for your Anthropic account.
export EXTRACTION_MODEL="your_available_anthropic_model_id"
export VALIDATION_MODEL="your_available_anthropic_model_id"

# Local embedding model (no external embedding API)
export EMBEDDING_MODEL="sentence-transformers/all-MiniLM-L6-v2"
export EMBEDDING_DEVICE="cpu"
export EMBEDDING_CACHE_DIR="./.cache/huggingface"
export EMBEDDING_LOCAL_FILES_ONLY="false"
export ANONYMIZED_TELEMETRY="FALSE"

export POSTGRES_USER="contracts_app"
export POSTGRES_PASSWORD="set_a_strong_database_password"
export POSTGRES_DB="contracts"
export DATABASE_URL="postgresql+psycopg2://contracts_app:set_a_strong_database_password@localhost:5432/contracts"
export MAX_UPLOAD_SIZE_BYTES="10485760"
export WEBHOOK_SYNC_TIMEOUT_SECONDS="30"
export PIPELINE_WORKERS="4"
export WEBHOOK_IDEMPOTENCY_ENABLED="true"
export EXTRACTION_MAX_INPUT_CHARS="24000"
```

### 3) Build policy index (real embeddings + Chroma)

```bash
python -m app.rag.indexer
```

### 4) Run API

```bash
uvicorn app.main:app --reload --port 8000
```

### Optional: run DB migrations

```bash
alembic revision --autogenerate -m "init"
alembic upgrade head
```

## Docker run

```bash
docker compose up --build
```

If you see package download timeouts during build, retry with larger pip timeout/retries:

```bash
docker compose build --no-cache \
  --build-arg PIP_DEFAULT_TIMEOUT=300 \
  --build-arg PIP_RETRIES=25
docker compose up
```

## API usage

### Email webhook

`POST /email-webhook` (multipart/form-data)

Fields:

- `sender` (string)
- `subject` (string)
- `attachment` (PDF file)

Example with `curl`:

```bash
curl -X POST http://localhost:8000/email-webhook \
  -H "X-API-KEY: set_a_long_random_webhook_secret" \
  -H "X-Idempotency-Key: msa-2026-001" \
  -F "sender=contracts@vendor.com" \
  -F "subject=Vendor MSA - Renewal" \
  -F "attachment=@./sample_contract.pdf;type=application/pdf"
```

Response shape:

```json
{
  "status": "processed",
  "decision": "approved",
  "risk_level": "low",
  "requires_review": false,
  "contract_id": "123",
  "processing_time_ms": 420
}
```

Deferred response (when processing exceeds sync timeout):

```json
{
  "status": "accepted",
  "decision": "review",
  "risk_level": "high",
  "requires_review": true,
  "contract_id": "request_id",
  "processing_time_ms": 30012
}
```

### Human review endpoints

- Require `X-API-KEY` with `ADMIN_API_KEY`.
- `GET /approved-contracts?limit=50&offset=0`
- `GET /review-queue?limit=100&offset=0`
- `POST /approve/{id}`
- `POST /reject/{id}`

## Tests

```bash
pytest -q
```

## Notes

- Extraction and validation use temperature `0`.
- LLM calls are Anthropic-only through `app/providers/factory.py`.
- RAG embeddings use a local HuggingFace model (`EMBEDDING_MODEL`) and do not call an external embedding API.
- If Docker cannot resolve `huggingface.co`, pre-download/cache the embedding model and set `EMBEDDING_LOCAL_FILES_ONLY=true`.
- Structured JSON output is strictly validated with Pydantic.
- Routing rules:
  - confidence `< 0.8`
  - OR `requires_human_review == true`
  - OR missing critical fields
  - => `review_queue`; otherwise auto-approve.
