from app.core.schemas import ContractExtraction
from app.processing.data_cleaner import clean_payload_for_model


def test_clean_payload_for_model_handles_currency_date_and_noise() -> None:
    payload = {
        "vendor_name": "  ACME   Holdings  ",
        "contract_start_date": "March 1st, 2026",
        "contract_end_date": "03/31/2027",
        "total_value": "$70,000 USD",
        "confidence_score": "0.95",
        "unexpected_key": "should_be_ignored",
    }

    cleaned = clean_payload_for_model(payload, ContractExtraction)
    assert cleaned == {
        "vendor_name": "ACME Holdings",
        "contract_start_date": "2026-03-01",
        "contract_end_date": "2027-03-31",
        "total_value": 70000.0,
        "confidence_score": 0.95,
    }


def test_clean_payload_for_model_handles_magnitude_and_nullish_values() -> None:
    payload = {
        "vendor_name": "N/A",
        "contract_start_date": "unknown",
        "contract_end_date": "",
        "total_value": "1.5 million dollars",
        "confidence_score": None,
    }

    cleaned = clean_payload_for_model(payload, ContractExtraction)
    assert cleaned["vendor_name"] == ""
    assert cleaned["contract_start_date"] == ""
    assert cleaned["contract_end_date"] == ""
    assert cleaned["total_value"] == 1_500_000.0
    assert cleaned["confidence_score"] == 0.0
