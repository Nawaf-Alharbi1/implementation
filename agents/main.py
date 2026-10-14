"""
خدمة الوكلاء الذكية (Python / FastAPI)
تشكل الطبقة 2 من معمارية Thiqa: الوكلاء الثلاثة يعملون كخط أنابيب واحد
(Agent1 -> Agent2 -> Agent3) خلف endpoint واحد: POST /recommend
"""

from fastapi import Body, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agent1_receiver import DataReceiverAgent, InvalidCustomerData, NoOffersAvailable
from agent2_recommender import RecommendationAgentV2
from agent3_explainer import ExplainerAgent
from orchestrator import NoEligibleOffers, coordinate_recommendation

app = FastAPI(title="Thiqa Agents Service")

# يسمح لسيرفر Node.js (على بورت مختلف) بالاتصال بهذه الخدمة
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

agent1 = DataReceiverAgent()
agent2 = RecommendationAgentV2()
agent3 = ExplainerAgent()


def _error(status: int, message: str, **extra):
    return JSONResponse(status_code=status, content={"error": message, **extra})


@app.get("/health")
def health():
    return {"status": "ok", "service": "thiqa-agents"}


@app.post("/agent1/retrieve")
async def agent1_retrieve(payload: dict = Body(...)):
    """تشغيل Agent 1 وحده (للاختبار المستقل): يرجع العروض الموحدة وحالة كل شركة."""
    try:
        return await agent1.run(payload)
    except InvalidCustomerData as e:
        return _error(422, "بيانات غير صالحة", errors=e.errors)
    except NoOffersAvailable as e:
        return _error(503, str(e), provider_status=e.provider_status)


@app.post("/recommend")
async def recommend(payload: dict = Body(...)):
    try:
        # Agent 1: استلام البيانات والتحقق وجلب العروض من الشركات وتوحيدها
        step1 = await agent1.run(payload)
    except InvalidCustomerData as e:
        return _error(422, "بيانات غير صالحة: " + "، ".join(x["message"] for x in e.errors), errors=e.errors)
    except NoOffersAvailable as e:
        return _error(503, str(e), provider_status=e.provider_status)

    try:
        # Run the agent pipeline to get the recommendation
        result = coordinate_recommendation(step1, agent2, agent3)

        # Database persistence is intentionally not attempted here yet.
        # The current schema requires linked Customer_Profiles, Vehicles, Retrieved_Quotes
        # and a non-null Recommendations.SelectedQuoteId. The UI currently has no
        # authenticated account/profile workflow, so inserting partial records here
        # would violate foreign-key/NOT NULL constraints or create misleading records.
        # The recommendation pipeline returns its result independently; persistence
        # must be implemented together with the profile/vehicle/quote write sequence.
        return result
    except NoEligibleOffers as e:
        return _error(503, str(e), provider_status=e.provider_status)