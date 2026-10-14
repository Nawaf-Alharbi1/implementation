"""
خدمة الوكلاء الذكية (Python / FastAPI)
تشكل الطبقة 2 من معمارية Thiqa: الوكلاء الثلاثة يعملون كخط أنابيب واحد
(Agent1 -> Agent2 -> Agent3) خلف endpoint واحد: POST /recommend
"""

import sqlite3
import json
from fastapi import Body, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agent1_receiver import DataReceiverAgent, InvalidCustomerData, NoOffersAvailable
from agent2_recommender import RecommendationAgentV2
from agent3_explainer import ExplainerAgent
from orchestrator import NoEligibleOffers, coordinate_recommendation

def get_db_connection():
    """Create a database connection."""
    conn = sqlite3.connect("../database/thiqa.db")
    conn.row_factory = sqlite3.Row
    return conn

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

        # Save recommendation to database and get RecId
        recommended_package = result["recommended_package"]
        explanation = result["explanation"]

        conn = get_db_connection()
        cursor = conn.cursor()

        # Extract customer information from payload to get UserId
        national_id = payload.get("national_id")
        if not national_id:
            # If we can't determine the user, we'll still save but without user linkage
            user_id = None
        else:
            # Find the user by national_id
            cursor.execute("SELECT UserId FROM Users WHERE NationalId = ?", (national_id,))
            user_row = cursor.fetchone()
            user_id = user_row["UserId"] if user_row else None

        # Create quote request record
        cursor.execute("""
            INSERT INTO Quote_Requests (ProfileId, VehicleId, CoverageType, RequestedAddOns, Timestamp)
            VALUES (
                (SELECT ProfileId FROM Customer_Profiles WHERE UserId = ? LIMIT 1),
                (SELECT VehicleId FROM Vehicles WHERE ProfileId =
                  (SELECT ProfileId FROM Customer_Profiles WHERE UserId = ? LIMIT 1) LIMIT 1),
                ?,
                ?,
                datetime('now')
            )
        """, [
            user_id or 0,  # Use 0 as fallback if user not found
            user_id or 0,
            recommended_package.get("coverage_type", "Comprehensive"),
            json.dumps(recommended_package.get("add_ons", []))
        ])

        request_id = cursor.lastrowid

        # Save recommendation to database
        cursor.execute("""
            INSERT INTO Recommendations (RequestId, SelectedQuoteId, SuitabilityScore, CreatedAt)
            VALUES (?, ?, ?, datetime('now'))
        """, [
            request_id,
            None,  # SelectedQuoteId - we'll leave as None for now since we don't have direct mapping
            recommended_package.get("suitability_score", 0)
        ])

        rec_id = cursor.lastrowid

        # Save explanation to database
        if rec_id and explanation:
            cursor.execute("""
                INSERT INTO Explanations (RecId, MainReasons, CriteriaBreakdown, ComparisonText)
                VALUES (?, ?, ?, ?)
            """, [
                rec_id,
                explanation.get("main_reasons", ""),
                json.dumps(explanation.get("criteria_explanations", []), ensure_ascii=False),
                explanation.get("comparison", "")
            ])

        conn.commit()
        conn.close()

        # Add RecId to the result for the frontend
        result["recId"] = rec_id

        return result
    except NoEligibleOffers as e:
        return _error(503, str(e), provider_status=e.provider_status)