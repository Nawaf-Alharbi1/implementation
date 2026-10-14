"""
Test script to verify the database logging integration works.
"""
import json
from main import app
from fastapi.testclient import TestClient

def test_recommendation_with_logging():
    """Test the recommendation endpoint with database logging."""
    client = TestClient(app)

    # Test payload
    test_payload = {
        "customer_profile": {
            "FullName": "test customer",
            "NationalId": "1234567890",
            "DateOfBirth": "1990-01-01",
            "DriverLicenseNo": "1234567890"
        },
        "vehicle": {
            "SerialNumber": "ABC123",
            "MakeModelYear": "2020",
            "EstimatedValue": 100000,
            "PurposeOfUse": "personal"
        },
        "CoverageType": "TPL",
        "RequestedAddOns": ["roadside_assistance"]
    }

    # Make request
    response = client.post("/recommend", json=test_payload)

    # Check response
    print(f"Status code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")

    # Verify we got a successful response
    assert response.status_code == 200
    data = response.json()
    assert "recommended_package" in data
    assert "explanation" in data
    assert "all_offers_ranked" in data
    assert "provider_status" in data

    # Verify explanation has the expected fields
    explanation = data["explanation"]
    assert "main_reasons" in explanation
    assert "strengths" in explanation
    assert "criteria_explanations" in explanation
    assert "comparison" in explanation
    assert "comparison_array" in explanation

    print("✅ Test passed!")

if __name__ == "__main__":
    test_recommendation_with_logging()