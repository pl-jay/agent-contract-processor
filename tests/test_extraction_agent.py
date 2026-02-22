from app.agents.extraction_agent import ExtractionAgent


def test_bounded_input_text_keeps_short_text() -> None:
    agent = ExtractionAgent(llm=object(), max_retries=1, max_input_chars=4000)
    text = "Short contract text"
    assert agent._build_bounded_input_text(text) == text


def test_bounded_input_text_truncates_long_text() -> None:
    agent = ExtractionAgent(llm=object(), max_retries=1, max_input_chars=4000)
    long_text = (
        "Vendor Agreement\n\n"
        + ("This section describes the vendor name, term and total value in USD 5000.\n\n" * 600)
    )
    bounded = agent._build_bounded_input_text(long_text)
    assert len(bounded) <= 4000
    assert "TRUNCATED FOR TOKEN LIMIT" in bounded


def test_normalize_payload_derives_confidence_from_cleaned_payload() -> None:
    payload = {
        "vendor_name": "ACME Inc",
        "contract_start_date": "2026-01-01",
        "contract_end_date": "2027-01-01",
        "total_value": 70000.0,
    }
    normalized = ExtractionAgent._normalize_payload(payload)
    assert normalized["total_value"] == 70000.0
    assert normalized["confidence_score"] == 1.0
