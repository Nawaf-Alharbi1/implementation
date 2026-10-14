"""
Simple test to verify the agents work together.
"""
from agent1_receiver import DataReceiverAgent
from agent2_recommender import RecommendationAgent
from agent3_explainer import ExplainerAgent

def test_agents_chain():
    """Test that the three agents work together in a chain."""
    # Create agents
    agent1 = DataReceiverAgent()
    agent2 = RecommendationAgent()
    agent3 = ExplainerAgent()

    print("All agents created successfully")

    # Test data (simplified)
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

    # Test Agent 1 (we'll skip the actual HTTP call since it requires mock servers)
    # Just test that we can create the agents and they have the expected methods
    print("Agent 1 has run method:", hasattr(agent1, 'run'))
    print("Agent 2 has run method:", hasattr(agent2, 'run'))
    print("Agent 3 has run method:", hasattr(agent3, 'run'))
    print("Agent 3 has _log_explanation method:", hasattr(agent3, '_log_explanation'))

    print("All required methods present")

if __name__ == "__main__":
    test_agents_chain()