import asyncio
from datetime import datetime, timezone

import httpx
import pytest

import main
import mock_insurer_api
from agent1_receiver import DataReceiverAgent
from agent2_recommender import RecommendationAgentV2
from agent3_explainer import ExplainerAgent
from insurers_config import load_insurers


VALID = {
    "national_id": "1098765432",
    "birth_date": "1995-06-15",
    "vehicle_serial": "1HGCM82633A004352",
    "manufacture_year": 2021,
    "vehicle_value": 85000,
    "purpose_of_use": "personal",
    "annual_mileage": "medium",
    "coverage_type": "TPL",
    "priority": "Budget",
}
PATHS = {"tawuniya": "/tawuniya/quotes", "rajhi": "/rajhi/offers",
         "medgulf": "/medgulf/plans", "acig": "/acig/quote"}


class FaultTransport(httpx.AsyncBaseTransport):
    def __init__(self, failures=()):
        self.inner = httpx.ASGITransport(app=mock_insurer_api.app)
        self.failures = set(failures)

    async def handle_async_request(self, request):
        if request.url.path in self.failures:
            return httpx.Response(503, json={"detail": "isolated test failure"})
        return await self.inner.handle_async_request(request)


def real_receiver(failures=()):
    insurers = load_insurers(base_url="http://mock")
    return DataReceiverAgent(insurers=insurers, transport=FaultTransport(failures),
                             max_attempts=1, retry_backoff=0)


async def post_recommend(monkeypatch, receiver, payload=None):
    monkeypatch.setattr(main, "agent1", receiver)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as client:
        return await client.post("/recommend", json=VALID if payload is None else payload)


def test_actual_recommend_path_uses_v2_and_explains_score_criteria(monkeypatch):
    assert isinstance(main.agent2, RecommendationAgentV2), "main path still binds legacy recommender"
    response = asyncio.run(post_recommend(monkeypatch, real_receiver()))
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"recommended_package", "all_offers_ranked", "explanation", "provider_status"}
    selected = body["recommended_package"]
    assert selected["score_breakdown"] and selected["weighted_contributions"]
    assert len(selected["score_breakdown"]) == 9
    assert body["explanation"]["criteria_explanations"]


def test_partial_provider_failure_preserves_success_and_priority(monkeypatch):
    class PrioritySpy(RecommendationAgentV2):
        forwarded = None

        def run_from_agent1_output(self, agent1_output, priority=None):
            self.forwarded = priority
            return super().run_from_agent1_output(agent1_output, priority=priority)

    recommender = PrioritySpy()
    monkeypatch.setattr(main, "agent2", recommender)
    response = asyncio.run(post_recommend(monkeypatch, real_receiver([PATHS["acig"]]),
                                          {**VALID, "priority": "Service"}))
    assert response.status_code == 200
    body = response.json()
    assert body["recommended_package"]["suitability_score"] > 0
    assert {s["provider_id"] for s in body["provider_status"] if s["ok"]} == {"tawuniya", "rajhi", "medgulf"}
    failed = next(s for s in body["provider_status"] if s["provider_id"] == "acig")
    assert failed["ok"] is False
    assert body["recommended_package"]["score_breakdown"]
    assert recommender.forwarded == "Service"


def test_all_provider_failures_are_503(monkeypatch):
    response = asyncio.run(post_recommend(monkeypatch, real_receiver(PATHS.values())))
    assert response.status_code == 503
    assert response.json()["provider_status"]


def test_no_eligible_quotes_are_friendly_503_without_explainer(monkeypatch):
    class NoEligibleReceiver:
        """Explicitly fault-injects only the V2 eligibility case; normal flows use real insurers."""
        async def run(self, payload):
            return {"customer_profile": {"coverage_type": "TPL", "priority": "Budget"},
                    "unified_quote_set": [{"quote_id": "filtered", "coverage_type": "Comprehensive",
                                            "premium": 100, "retrieved_at": datetime.now(timezone.utc).isoformat()}],
                    "provider_status": [{"provider_id": "fixture", "ok": True, "offers_count": 1}]}

    class ExplainerSpy(ExplainerAgent):
        called = False
        def run(self, *args, **kwargs):
            self.called = True
            return super().run(*args, **kwargs)

    spy = ExplainerSpy()
    monkeypatch.setattr(main, "agent3", spy)
    response = asyncio.run(post_recommend(monkeypatch, NoEligibleReceiver()))
    assert response.status_code == 503
    assert "error" in response.json() and response.json()["provider_status"]
    assert spy.called is False


def test_invalid_input_keeps_422_contract(monkeypatch):
    response = asyncio.run(post_recommend(monkeypatch, real_receiver(), {**VALID, "national_id": "bad"}))
    assert response.status_code == 422
    assert response.json()["errors"]


def test_agent1_retrieve_remains_independent(monkeypatch):
    monkeypatch.setattr(main, "agent1", real_receiver())
    async def send():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as client:
            return await client.post("/agent1/retrieve", json=VALID)
    response = asyncio.run(send())
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"customer_profile", "unified_quote_set", "provider_status"}
    assert body["unified_quote_set"] and all("suitability_score" not in q for q in body["unified_quote_set"])
