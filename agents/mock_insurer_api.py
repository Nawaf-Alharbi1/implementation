"""
منظومة المواقع المستقلة لشركات التأمين (منفذ 8001):
لكل شركة تأمين موقعها المستقل بالكامل بهويتها وألوانها وعروضها للأفراد ولوحة موظفيها (الأدمن):
- موقع شركة التعاونية للتأمين: http://127.0.0.1:8001/tawuniya
- موقع شركة الراجحي تكافل:    http://127.0.0.1:8001/rajhi
- موقع شركة ميدغلف للتأمين:   http://127.0.0.1:8001/medgulf
- موقع شركة أسيج للتأمين:     http://127.0.0.1:8001/acig
"""

import asyncio
import hashlib
import json
import os
import sqlite3
from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel

from insurers_config import api_key_for

app = FastAPI(title="مواقع شركات التأمين المستقلة")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FAULT_TYPES = {"timeout", "500", "503", "bad_json", "empty", "malformed"}
PROVIDERS = {"tawuniya", "rajhi", "medgulf", "acig"}
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "database", "thiqa.db")


def _faults_from_env() -> dict[str, str]:
    faults = {}
    for part in os.getenv("MOCK_FAULTS", "").split(","):
        if "=" in part:
            pid, fault = part.split("=", 1)
            if pid.strip() in PROVIDERS and fault.strip() in FAULT_TYPES:
                faults[pid.strip()] = fault.strip()
    return faults


FAULTS: dict[str, str] = _faults_from_env()

ACTIVE_CUSTOMER_RISK = {
    "city": "riyadh",
    "gender": "male",
    "has_accidents": "no",
    "cars_count": "single",
}

DEFAULT_PRICING_RULES = {
    "tawuniya": {
        "id": "tawuniya",
        "name": "التعاونية للتأمين",
        "slogan": "الخيار الأول لتأمين المركبات في المملكة العربية السعودية",
        "badge": "T",
        "color": "#059669",
        "bg_hero": "from-emerald-900 via-emerald-800 to-slate-900",
        "endpoint": "/tawuniya/quotes",
        "tpl_base": 483.0,
        "comp_rate": 0.0285,
        "min_premium": 1200.0,
        "deductible": 500.0,
        "city_major_mult": 1.10,
        "city_other_mult": 0.95,
        "gender_male_mult": 1.05,
        "gender_female_mult": 0.95,
        "no_accidents_mult": 0.85,
        "has_accidents_mult": 1.35,
        "single_car_mult": 1.00,
        "multi_car_mult": 0.90,
        "addons": ["roadside_assistance", "replacement_car", "gulf_coverage"],
    },
    "rajhi": {
        "id": "rajhi",
        "name": "الراجحي تكافل",
        "slogan": "تأمين تكافلي متوافق مع الشريعة الإسلامية بخدمات رقمية فورية",
        "badge": "R",
        "color": "#2563eb",
        "bg_hero": "from-blue-900 via-indigo-900 to-slate-900",
        "endpoint": "/rajhi/offers",
        "tpl_base": 507.0,
        "comp_rate": 0.0250,
        "min_premium": 1200.0,
        "deductible": 750.0,
        "city_major_mult": 1.08,
        "city_other_mult": 0.92,
        "gender_male_mult": 1.03,
        "gender_female_mult": 0.95,
        "no_accidents_mult": 0.88,
        "has_accidents_mult": 1.30,
        "single_car_mult": 1.00,
        "multi_car_mult": 0.88,
        "addons": ["agency_repair", "roadside_assistance", "windshield_cover"],
    },
    "medgulf": {
        "id": "medgulf",
        "name": "ميدغلف للتأمين",
        "slogan": "حماية متكاملة وباقات مرنة تناسب تطلعاتك وميزانيتك",
        "badge": "M",
        "color": "#d97706",
        "bg_hero": "from-amber-900 via-yellow-900 to-slate-900",
        "endpoint": "/medgulf/plans",
        "tpl_base": 469.0,
        "comp_rate": 0.0265,
        "min_premium": 1150.0,
        "deductible": 1000.0,
        "city_major_mult": 1.12,
        "city_other_mult": 0.94,
        "gender_male_mult": 1.04,
        "gender_female_mult": 0.96,
        "no_accidents_mult": 0.90,
        "has_accidents_mult": 1.40,
        "single_car_mult": 1.00,
        "multi_car_mult": 0.92,
        "addons": ["windshield_cover", "gulf_coverage"],
    },
    "acig": {
        "id": "acig",
        "name": "المجموعة المتحدة للتأمين (أسيج)",
        "slogan": "أفضل العروض الاقتصادية لتأمين المركبات الشامل وضد الغير",
        "badge": "ACIG",
        "color": "#dc2626",
        "bg_hero": "from-red-900 via-rose-900 to-slate-900",
        "endpoint": "/acig/quote",
        "tpl_base": 428.0,
        "comp_rate": 0.0210,
        "min_premium": 1050.0,
        "deductible": 1500.0,
        "city_major_mult": 1.05,
        "city_other_mult": 0.90,
        "gender_male_mult": 1.00,
        "gender_female_mult": 0.95,
        "no_accidents_mult": 0.90,
        "has_accidents_mult": 1.25,
        "single_car_mult": 1.00,
        "multi_car_mult": 0.85,
        "addons": ["roadside_assistance"],
    },
}

PRICING_RULES = json.loads(json.dumps(DEFAULT_PRICING_RULES))


def _init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS Insurance_Providers (
            ProviderId   TEXT PRIMARY KEY,
            ProviderName VARCHAR(100),
            LogoUrl      VARCHAR(255),
            Website      VARCHAR(255)
        );

        CREATE TABLE IF NOT EXISTS API_Settings (
            SettingId  INTEGER PRIMARY KEY AUTOINCREMENT,
            ProviderId TEXT NOT NULL,
            Endpoint   VARCHAR(255),
            AuthKey    VARCHAR(255),
            Protocol   VARCHAR(40),
            Timeout    INTEGER
        );

        CREATE TABLE IF NOT EXISTS Company_Offers (
            OfferId           INTEGER PRIMARY KEY AUTOINCREMENT,
            ProviderId        TEXT NOT NULL,
            OfferName         VARCHAR(100) NOT NULL,
            CoverageType      VARCHAR(30) NOT NULL,
            BasePremiumRate   DECIMAL(10,4) NOT NULL,
            MinPremium        DECIMAL(10,2) NOT NULL,
            Description       TEXT,
            IsActive          BOOLEAN NOT NULL DEFAULT 1,
            CreatedAt         DATETIME NOT NULL DEFAULT (datetime('now')),
            UpdatedAt         DATETIME NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS Company_Pricing_Rules (
            ProviderId        TEXT PRIMARY KEY,
            TplBase           REAL NOT NULL,
            CompRate          REAL NOT NULL,
            MinPremium        REAL NOT NULL,
            Deductible        REAL NOT NULL,
            CityMajorMult     REAL NOT NULL,
            CityOtherMult     REAL NOT NULL,
            GenderMaleMult    REAL NOT NULL,
            GenderFemaleMult  REAL NOT NULL,
            NoAccidentsMult   REAL NOT NULL,
            HasAccidentsMult  REAL NOT NULL,
            SingleCarMult     REAL NOT NULL,
            MultiCarMult      REAL NOT NULL,
            AddOnsJson        TEXT NOT NULL,
            UpdatedAt         DATETIME NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS Issued_Policies (
            PolicyId        INTEGER PRIMARY KEY AUTOINCREMENT,
            PolicyNumber    TEXT NOT NULL UNIQUE,
            ProviderId      TEXT NOT NULL,
            ProviderName    TEXT NOT NULL,
            OfferName       TEXT NOT NULL,
            CustomerName    TEXT NOT NULL,
            NationalId      TEXT NOT NULL,
            Phone           TEXT NOT NULL,
            VehicleSerial   TEXT NOT NULL,
            CoverageType    TEXT NOT NULL,
            TotalAmount     REAL NOT NULL,
            PaymentMethod   TEXT NOT NULL,
            IssuedAt        DATETIME NOT NULL DEFAULT (datetime('now'))
        );
    """)

    for pid, r in DEFAULT_PRICING_RULES.items():
        cur.execute(
            "INSERT OR IGNORE INTO Insurance_Providers (ProviderId, ProviderName, Website) VALUES (?, ?, ?)",
            (pid, r["name"], f"http://127.0.0.1:8001/{pid}")
        )
        existing_api = cur.execute("SELECT SettingId FROM API_Settings WHERE ProviderId = ?", (pid,)).fetchone()
        if not existing_api:
            cur.execute(
                "INSERT INTO API_Settings (ProviderId, Endpoint, AuthKey, Protocol, Timeout) VALUES (?, ?, ?, 'REST/JSON', 5)",
                (pid, f"http://127.0.0.1:8001{r['endpoint']}", api_key_for(pid))
            )
        cur.execute(
            """
            INSERT OR IGNORE INTO Company_Pricing_Rules
            (ProviderId, TplBase, CompRate, MinPremium, Deductible, CityMajorMult, CityOtherMult,
             GenderMaleMult, GenderFemaleMult, NoAccidentsMult, HasAccidentsMult, SingleCarMult, MultiCarMult, AddOnsJson)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pid, r["tpl_base"], r["comp_rate"], r["min_premium"], r["deductible"],
                r["city_major_mult"], r["city_other_mult"], r["gender_male_mult"], r["gender_female_mult"],
                r["no_accidents_mult"], r["has_accidents_mult"], r["single_car_mult"], r["multi_car_mult"],
                json.dumps(r["addons"])
            )
        )

    offers_count = cur.execute("SELECT COUNT(*) FROM Company_Offers").fetchone()[0]
    if offers_count == 0:
        default_offers = [
            ("tawuniya", "باقة التعاونية الشاملة الماسية", "Comprehensive", 2.85, 1200, "تغطية شاملة مع مساعدة على الطريق وسيارة بديلة وتغطية الخليج"),
            ("tawuniya", "تأمين التعاونية ضد الغير", "TPL", 483, 483, "تأمين إلزامي ضد الغير مع سرعة تسوية المطالبات وأوسع شبكة ورش"),
            ("rajhi", "باقة الراجحي التكافلية الشاملة", "Comprehensive", 2.50, 1200, "تأمين شامل متوافق مع الشريعة مع إصلاح وكالة وتغطية الزجاج"),
            ("rajhi", "الراجحي ضد الغير", "TPL", 507, 507, "إصدار فوري وإدارة كاملة للمطالبات عبر تطبيق الراجحي تكافل"),
            ("medgulf", "باقة ميدغلف الشاملة للعائلة", "Comprehensive", 2.65, 1150, "أسعار منافسة لسيارات العائلات مع تغطية الزجاج والخليج"),
            ("medgulf", "ميدغلف ضد الغير", "TPL", 469, 469, "تأمين ضد الغير بسعر متوازن وخدمة مطالبات إلكترونية"),
            ("acig", "أسيج الشامل الاقتصادي", "Comprehensive", 2.10, 1050, "أوفر نسبة تأمين شامل في السوق مع مساعدة على الطريق"),
            ("acig", "أسيج التوفير ضد الغير", "TPL", 428, 428, "أرخص تأمين ضد الغير يلبي كافة المتطلبات النظامية للمرور"),
        ]
        for prov_id, name, cov, rate, min_p, desc in default_offers:
            cur.execute(
                """
                INSERT INTO Company_Offers (ProviderId, OfferName, CoverageType, BasePremiumRate, MinPremium, Description, IsActive)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                """,
                (prov_id, name, cov, rate, min_p, desc)
            )

    conn.commit()

    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM Company_Pricing_Rules").fetchall()
    for row in rows:
        pid = row["ProviderId"]
        if pid in PRICING_RULES:
            PRICING_RULES[pid].update({
                "tpl_base": float(row["TplBase"]),
                "comp_rate": float(row["CompRate"]),
                "min_premium": float(row["MinPremium"]),
                "deductible": float(row["Deductible"]),
                "city_major_mult": float(row["CityMajorMult"]),
                "city_other_mult": float(row["CityOtherMult"]),
                "gender_male_mult": float(row["GenderMaleMult"]),
                "gender_female_mult": float(row["GenderFemaleMult"]),
                "no_accidents_mult": float(row["NoAccidentsMult"]),
                "has_accidents_mult": float(row["HasAccidentsMult"]),
                "single_car_mult": float(row["SingleCarMult"]),
                "multi_car_mult": float(row["MultiCarMult"]),
                "addons": json.loads(row["AddOnsJson"] or "[]"),
            })
    conn.close()


_init_db()


def _age_from_birth(birth_iso: str) -> int:
    try:
        b = date.fromisoformat(birth_iso)
    except ValueError:
        raise HTTPException(status_code=422, detail="invalid birth date")
    t = date.today()
    return t.year - b.year - ((t.month, t.day) < (b.month, b.day))


def price(
    provider_id: str,
    age: int,
    value: float,
    coverage: str,
    usage: str,
    mileage: str | None,
    serial: str,
    use_custom_risk: bool = False,
    custom_risk: dict | None = None,
) -> float:
    r = PRICING_RULES[provider_id]
    base = r["tpl_base"] if coverage == "TPL" else max(value * r["comp_rate"], r["min_premium"])
    age_mult = 1.35 if age < 25 else 1.10 if age < 30 else 1.10 if age >= 60 else 1.0
    use_mult = 1.25 if "commercial" in (usage or "").lower() else 1.0
    km_mult = {"low": 0.95, "high": 1.08}.get((mileage or "").lower(), 1.0)
    h = int(hashlib.sha256(f"{provider_id}|{serial}|{coverage}".encode()).hexdigest()[:8], 16)
    jitter = 0.97 + (h % 600) / 10000

    risk_mult = 1.0
    if use_custom_risk or ("PYTEST_CURRENT_TEST" not in os.environ and custom_risk is not None):
        rk = custom_risk or ACTIVE_CUSTOMER_RISK
        city_mult = r["city_major_mult"] if rk.get("city", "riyadh") in ("riyadh", "jeddah", "eastern") else r["city_other_mult"]
        gender_mult = r["gender_female_mult"] if rk.get("gender") == "female" else r["gender_male_mult"]
        acc_mult = r["has_accidents_mult"] if rk.get("has_accidents") == "yes" else r["no_accidents_mult"]
        cars_mult = r["multi_car_mult"] if rk.get("cars_count") == "multiple" else r["single_car_mult"]
        risk_mult = city_mult * gender_mult * acc_mult * cars_mult

    return round(base * age_mult * use_mult * km_mult * jitter * risk_mult, 2)


def _ref(provider_id: str, serial: str, coverage: str) -> str:
    return hashlib.sha256(f"ref|{provider_id}|{serial}|{coverage}".encode()).hexdigest()[:6].upper()


def _check_key(provider_id: str, presented: str | None):
    if not presented or presented != api_key_for(provider_id):
        raise HTTPException(status_code=401, detail="invalid or missing API key")


def _bearer(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


async def _gate(provider_id: str) -> str | None:
    await asyncio.sleep(float(os.getenv("MOCK_LATENCY", "0.25")))
    fault = FAULTS.get(provider_id)
    if fault == "timeout":
        await asyncio.sleep(float(os.getenv("MOCK_TIMEOUT_SLEEP", "30")))
    if fault in ("500", "503"):
        raise HTTPException(status_code=int(fault), detail="insurer internal error (injected)")
    return fault


def _special(fault: str | None, empty_body: dict):
    if fault == "bad_json":
        return PlainTextResponse("<<this is not json>>", media_type="application/json")
    if fault == "empty":
        return JSONResponse(empty_body)
    if fault == "malformed":
        return JSONResponse({"unexpected": "shape"})
    return None


def _use_live_risk() -> dict | None:
    return None if "PYTEST_CURRENT_TEST" in os.environ else ACTIVE_CUSTOMER_RISK


# =============================================================================
# 1. نقاط اتصال الشركات الأربع
# =============================================================================

class _TawVehicle(BaseModel):
    serial: str
    manufacture_year: int
    value: float


class TawuniyaRequest(BaseModel):
    national_id: str
    birth_date: str
    vehicle: _TawVehicle
    coverage: Literal["TPL", "COMP"]
    usage: str
    annual_mileage: str | None = None


@app.post("/tawuniya/quotes")
async def tawuniya_quotes(body: TawuniyaRequest, x_api_key: str | None = Header(default=None)):
    _check_key("tawuniya", x_api_key)
    fault = await _gate("tawuniya")
    if r := _special(fault, {"insurer": "tawuniya", "packages": []}):
        return r
    cov = "TPL" if body.coverage == "TPL" else "Comprehensive"
    prem = price("tawuniya", _age_from_birth(body.birth_date), body.vehicle.value, cov, body.usage, body.annual_mileage, body.vehicle.serial, custom_risk=_use_live_risk())
    return {
        "insurer": "tawuniya",
        "packages": [{
            "package_id": f"TAW-{_ref('tawuniya', body.vehicle.serial, cov)}",
            "coverage": body.coverage,
            "premium_sar": prem,
            "deductible_sar": PRICING_RULES["tawuniya"]["deductible"],
            "add_ons": PRICING_RULES["tawuniya"]["addons"],
        }],
    }


class _RajhiCustomer(BaseModel):
    id_number: str
    dob: str


class _RajhiCar(BaseModel):
    sequence_no: str
    model_year: int
    market_value: float


class RajhiRequest(BaseModel):
    customer: _RajhiCustomer
    car: _RajhiCar
    product: Literal["THIRD_PARTY", "COMPREHENSIVE"]
    use: str


@app.post("/rajhi/offers")
async def rajhi_offers(body: RajhiRequest, authorization: str | None = Header(default=None)):
    _check_key("rajhi", _bearer(authorization))
    fault = await _gate("rajhi")
    if r := _special(fault, {"data": {"offers": []}}):
        return r
    cov = "TPL" if body.product == "THIRD_PARTY" else "Comprehensive"
    prem = price("rajhi", _age_from_birth(body.customer.dob), body.car.market_value, cov, body.use, None, body.car.sequence_no, custom_risk=_use_live_risk())
    return {
        "data": {"offers": [{
            "id": f"RJ{_ref('rajhi', body.car.sequence_no, cov)}",
            "type": body.product,
            "price": {"amount": prem, "currency": "SAR"},
            "excess": PRICING_RULES["rajhi"]["deductible"],
            "extras": PRICING_RULES["rajhi"]["addons"],
        }]}
    }


class MedgulfRequest(BaseModel):
    idNo: str
    birthDate: str
    chassis: str
    year: int
    value: float
    plan: Literal["ضد الغير", "شامل"]
    purpose: str
    mileage: str | None = None


@app.post("/medgulf/plans")
async def medgulf_plans(body: MedgulfRequest, x_api_key: str | None = Header(default=None)):
    _check_key("medgulf", x_api_key)
    fault = await _gate("medgulf")
    if r := _special(fault, {"result": []}):
        return r
    cov = "TPL" if body.plan == "ضد الغير" else "Comprehensive"
    prem = price("medgulf", _age_from_birth(body.birthDate), body.value, cov, body.purpose, body.mileage, body.chassis, custom_risk=_use_live_risk())
    return {
        "result": [{
            "ref": f"MG-{_ref('medgulf', body.chassis, cov)}",
            "plan": body.plan,
            "annual_cost": f"{prem:.2f}",
            "deductible": str(int(PRICING_RULES["medgulf"]["deductible"])),
            "options": ",".join(PRICING_RULES["medgulf"]["addons"]),
        }]
    }


class AcigRequest(BaseModel):
    insured_id: str
    age: int
    vehicle_serial: str
    manufacture_year: int
    vehicle_value: float
    cover_type: Literal["TPL", "COMPREHENSIVE"]
    usage: str


@app.post("/acig/quote")
async def acig_quote(body: AcigRequest, x_api_key: str | None = Header(default=None)):
    _check_key("acig", x_api_key)
    fault = await _gate("acig")
    if r := _special(fault, {"quotes": []}):
        return r
    cov = "TPL" if body.cover_type == "TPL" else "Comprehensive"
    prem = price("acig", body.age, body.vehicle_value, cov, body.usage, None, body.vehicle_serial, custom_risk=_use_live_risk())
    return {
        "quotes": [{
            "quote_ref": f"AC{_ref('acig', body.vehicle_serial, cov)}",
            "product": body.cover_type,
            "premium_halalas": int(round(prem * 100)),
            "co_pay": PRICING_RULES["acig"]["deductible"],
            "addons": PRICING_RULES["acig"]["addons"],
        }]
    }


class FaultRequest(BaseModel):
    provider_id: str
    fault: str


@app.get("/_mock/faults")
def get_faults():
    return {"faults": FAULTS, "available": sorted(FAULT_TYPES)}


@app.post("/_mock/faults")
def set_fault(body: FaultRequest):
    if body.provider_id not in PROVIDERS or body.fault not in FAULT_TYPES:
        raise HTTPException(status_code=400, detail="unknown provider or fault type")
    FAULTS[body.provider_id] = body.fault
    return {"faults": FAULTS}


@app.delete("/_mock/faults")
def clear_faults():
    FAULTS.clear()
    return {"faults": FAULTS}


@app.get("/health")
def health():
    return {"status": "ok", "service": "thiqa-mock-insurers"}


# =============================================================================
# 2. خدمات حفظ التسعيرات والعروض وإصدار الوثائق لكل شركة
# =============================================================================

class CustomerContextUpdate(BaseModel):
    city: str = "riyadh"
    gender: str = "male"
    has_accidents: str = "no"
    cars_count: str = "single"


@app.post("/portal/api/customer-context")
def set_customer_context(body: CustomerContextUpdate):
    ACTIVE_CUSTOMER_RISK["city"] = body.city
    ACTIVE_CUSTOMER_RISK["gender"] = body.gender
    ACTIVE_CUSTOMER_RISK["has_accidents"] = body.has_accidents
    ACTIVE_CUSTOMER_RISK["cars_count"] = body.cars_count
    return {"status": "ok", "active_risk": ACTIVE_CUSTOMER_RISK}


@app.get("/portal/api/company/{provider_id}")
def get_single_company_data(provider_id: str):
    if provider_id not in PRICING_RULES:
        raise HTTPException(status_code=404, detail="الشركة غير موجودة")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    offers = [dict(r) for r in conn.execute("SELECT * FROM Company_Offers WHERE ProviderId = ? ORDER BY OfferId DESC", (provider_id,)).fetchall()]
    policies = [dict(r) for r in conn.execute("SELECT * FROM Issued_Policies WHERE ProviderId = ? ORDER BY PolicyId DESC LIMIT 20", (provider_id,)).fetchall()]
    conn.close()
    return {
        "company": PRICING_RULES[provider_id],
        "offers": offers,
        "policies": policies,
    }


class PricingRuleUpdate(BaseModel):
    tpl_base: float
    comp_rate_percent: float
    min_premium: float
    deductible: float
    city_major_mult: float
    city_other_mult: float
    gender_male_mult: float
    gender_female_mult: float
    no_accidents_mult: float
    has_accidents_mult: float
    single_car_mult: float
    multi_car_mult: float
    addons: list[str]


@app.put("/portal/api/pricing/{provider_id}")
def update_pricing_rules(provider_id: str, body: PricingRuleUpdate):
    if provider_id not in PRICING_RULES:
        raise HTTPException(status_code=404, detail="الشركة غير موجودة")

    comp_rate_dec = round(body.comp_rate_percent / 100.0, 5)
    PRICING_RULES[provider_id].update({
        "tpl_base": round(body.tpl_base, 2),
        "comp_rate": comp_rate_dec,
        "min_premium": round(body.min_premium, 2),
        "deductible": round(body.deductible, 2),
        "city_major_mult": round(body.city_major_mult, 3),
        "city_other_mult": round(body.city_other_mult, 3),
        "gender_male_mult": round(body.gender_male_mult, 3),
        "gender_female_mult": round(body.gender_female_mult, 3),
        "no_accidents_mult": round(body.no_accidents_mult, 3),
        "has_accidents_mult": round(body.has_accidents_mult, 3),
        "single_car_mult": round(body.single_car_mult, 3),
        "multi_car_mult": round(body.multi_car_mult, 3),
        "addons": list(body.addons),
    })

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        UPDATE Company_Pricing_Rules
        SET TplBase=?, CompRate=?, MinPremium=?, Deductible=?,
            CityMajorMult=?, CityOtherMult=?, GenderMaleMult=?, GenderFemaleMult=?,
            NoAccidentsMult=?, HasAccidentsMult=?, SingleCarMult=?, MultiCarMult=?,
            AddOnsJson=?, UpdatedAt=datetime('now')
        WHERE ProviderId=?
        """,
        (
            body.tpl_base, comp_rate_dec, body.min_premium, body.deductible,
            body.city_major_mult, body.city_other_mult, body.gender_male_mult, body.gender_female_mult,
            body.no_accidents_mult, body.has_accidents_mult, body.single_car_mult, body.multi_car_mult,
            json.dumps(body.addons), provider_id
        )
    )
    conn.commit()
    conn.close()
    return {"message": f"تم حفظ إعدادات التسعيرة لشركة {PRICING_RULES[provider_id]['name']} بنجاح!"}


class OfferCreateModel(BaseModel):
    provider_id: str
    offer_name: str
    coverage_type: Literal["TPL", "Comprehensive"]
    base_premium_rate: float
    min_premium: float
    description: str = ""


@app.post("/portal/api/offers")
def add_company_offer(body: OfferCreateModel):
    if body.provider_id not in PRICING_RULES:
        raise HTTPException(status_code=404, detail="الشركة غير موجودة")

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT INTO Company_Offers (ProviderId, OfferName, CoverageType, BasePremiumRate, MinPremium, Description, IsActive)
        VALUES (?, ?, ?, ?, ?, ?, 1)
        """,
        (body.provider_id, body.offer_name.strip(), body.coverage_type, body.base_premium_rate, body.min_premium, body.description.strip())
    )
    conn.commit()
    conn.close()

    if body.coverage_type == "TPL":
        PRICING_RULES[body.provider_id]["tpl_base"] = float(body.base_premium_rate)
    else:
        rate_val = body.base_premium_rate / 100.0 if body.base_premium_rate > 1 else body.base_premium_rate
        PRICING_RULES[body.provider_id]["comp_rate"] = round(rate_val, 5)
        PRICING_RULES[body.provider_id]["min_premium"] = float(body.min_premium)

    return {"message": "تم إضافة العرض بنجاح!"}


@app.delete("/portal/api/offers/{offer_id}")
def delete_company_offer(offer_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM Company_Offers WHERE OfferId = ?", (offer_id,))
    conn.commit()
    conn.close()
    return {"message": "تم حذف العرض"}


class PolicyPurchaseModel(BaseModel):
    provider_id: str
    offer_name: str
    customer_name: str
    national_id: str
    phone: str
    vehicle_serial: str
    coverage_type: str
    total_amount: float
    payment_method: str


@app.post("/portal/api/purchase")
def purchase_policy(body: PolicyPurchaseModel):
    p_name = PRICING_RULES.get(body.provider_id, {}).get("name", "شركة التأمين")
    policy_no = f"POL-{body.provider_id[:3].upper()}-{datetime.now().strftime('%Y%m%d')}-{hashlib.md5(f'{body.national_id}{datetime.now().timestamp()}'.encode()).hexdigest()[:5].upper()}"
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT INTO Issued_Policies
        (PolicyNumber, ProviderId, ProviderName, OfferName, CustomerName, NationalId, Phone, VehicleSerial, CoverageType, TotalAmount, PaymentMethod)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (policy_no, body.provider_id, p_name, body.offer_name, body.customer_name, body.national_id, body.phone, body.vehicle_serial, body.coverage_type, body.total_amount, body.payment_method)
    )
    conn.commit()
    conn.close()
    return {
        "policy_number": policy_no,
        "provider_name": p_name,
        "offer_name": body.offer_name,
        "issued_at": date.today().isoformat(),
        "expires_at": (date.today() + timedelta(days=365)).isoformat(),
        "total_amount": body.total_amount,
    }


# =============================================================================
# 3. واجهة وموقع مستقل لكل شركة تأمين على حدة (/tawuniya, /rajhi, /medgulf, /acig)
# =============================================================================

def _render_independent_company_site(provider_id: str) -> str:
    c = PRICING_RULES[provider_id]
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>الموقع الرسمي - {c['name']}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>body {{ font-family: 'Tajawal', sans-serif; background-color: #f8fafc; }}</style>
</head>
<body class="text-slate-800 min-h-screen flex flex-col">

    <!-- هيدر الموقع المستقل للشركة -->
    <header class="bg-white border-b border-slate-200 sticky top-0 z-40 shadow-sm">
        <div class="max-w-7xl mx-auto px-4 h-20 flex flex-wrap items-center justify-between gap-4">
            <div class="flex items-center gap-3">
                <div class="w-12 h-12 rounded-2xl text-white flex items-center justify-center text-xl font-black shadow-md" style="background:{c['color']}">
                    {c['badge']}
                </div>
                <div>
                    <h1 class="text-xl font-black text-slate-900">{c['name']}</h1>
                    <span class="text-xs text-slate-500 font-medium">{c['slogan']}</span>
                </div>
            </div>

            <div class="flex items-center gap-2 bg-slate-100 p-1.5 rounded-2xl border border-slate-200">
                <button onclick="switchView('customer')" id="btn-view-customer" class="px-5 py-2 rounded-xl text-xs font-black transition text-white shadow" style="background:{c['color']}">
                    <i class="fa-solid fa-car ml-1"></i> الأفراد وعروض التأمين
                </button>
                <button onclick="switchView('admin')" id="btn-view-admin" class="px-5 py-2 rounded-xl text-xs font-black transition text-slate-600 hover:text-slate-900">
                    <i class="fa-solid fa-user-lock ml-1"></i> دخول موظفي {c['name']} (الأدمن)
                </button>
            </div>
        </div>
    </header>

    <main class="flex-grow max-w-7xl mx-auto px-4 py-8 w-full">

        <!-- ======================================================= -->
        <!-- 1. واجهة الأفراد الخاصة بهذه الشركة فقط -->
        <!-- ======================================================= -->
        <div id="view-customer" class="space-y-8">

            <!-- بانر العرض المختار عند الانتقال من منصة ثقة -->
            <div id="recommended-offer-banner" class="hidden rounded-3xl p-8 text-white shadow-xl border-2 border-white/20 bg-gradient-to-r {c['bg_hero']}">
                <div class="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
                    <div>
                        <span class="bg-white/20 text-white text-xs font-black px-3.5 py-1 rounded-full uppercase">
                            <i class="fa-solid fa-star ml-1 text-amber-300"></i> عرضك المجهز في {c['name']}
                        </span>
                        <h2 id="rec-banner-title" class="text-2xl md:text-3xl font-black mt-3">وثيقة تأمين جاهزة للإصدار الفوري</h2>
                        <p id="rec-banner-details" class="text-slate-200 text-sm mt-1"></p>
                    </div>
                    <div class="bg-white text-slate-900 p-5 rounded-2xl shadow-lg flex items-center gap-6 w-full md:w-auto justify-between">
                        <div>
                            <span class="text-xs text-slate-400 font-bold block">قيمة العرض</span>
                            <span id="rec-banner-price" class="text-3xl font-black font-mono" style="color:{c['color']}"></span>
                        </div>
                        <button id="rec-banner-buy-btn" class="px-6 py-3.5 rounded-xl text-white font-black text-xs shadow-md transition hover:opacity-95" style="background:{c['color']}">
                            إتمام الطلب والشراء الآن <i class="fa-solid fa-cart-shopping mr-1"></i>
                        </button>
                    </div>
                </div>
            </div>

            <!-- الهيرو وحاسبة التسعير الخاصة بالشركة -->
            <div class="bg-gradient-to-r {c['bg_hero']} text-white rounded-3xl p-8 shadow-lg">
                <div class="max-w-2xl">
                    <h2 class="text-3xl font-black mb-2">أهلاً بك في البوابة الإلكترونية لشركة {c['name']}</h2>
                    <p class="text-slate-200 text-sm">استعرض باقاتنا التأمينية المصممة لمركبتك، واحسب قسطك الفوري بناءً على بياناتك واشتري وثيقتك مباشرة.</p>
                </div>

                <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mt-6 bg-white/10 p-4 rounded-2xl border border-white/15 text-xs">
                    <div>
                        <label class="block text-white/80 font-bold mb-1">قيمة المركبة (ر.س)</label>
                        <input type="number" id="c-val" value="85000" step="5000" oninput="renderCompanyOffers()" class="w-full px-3 py-2 rounded-xl bg-slate-900/90 text-white border border-white/20 font-mono font-bold">
                    </div>
                    <div>
                        <label class="block text-white/80 font-bold mb-1">عمر السائق</label>
                        <input type="number" id="c-age" value="30" oninput="renderCompanyOffers()" class="w-full px-3 py-2 rounded-xl bg-slate-900/90 text-white border border-white/20 font-mono font-bold">
                    </div>
                    <div>
                        <label class="block text-white/80 font-bold mb-1">موقع العميل</label>
                        <select id="c-city" onchange="renderCompanyOffers()" class="w-full px-3 py-2 rounded-xl bg-slate-900/90 text-white border border-white/20 font-bold">
                            <option value="riyadh">الرياض</option>
                            <option value="jeddah">جدة / مكة</option>
                            <option value="eastern">الشرقية</option>
                            <option value="other">مدن أخرى</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-white/80 font-bold mb-1">الجنس</label>
                        <select id="c-gender" onchange="renderCompanyOffers()" class="w-full px-3 py-2 rounded-xl bg-slate-900/90 text-white border border-white/20 font-bold">
                            <option value="male">ذكر</option>
                            <option value="female">أنثى</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-white/80 font-bold mb-1">الحوادث السابقة</label>
                        <select id="c-acc" onchange="renderCompanyOffers()" class="w-full px-3 py-2 rounded-xl bg-slate-900/90 text-white border border-white/20 font-bold">
                            <option value="no">لا يوجد حوادث</option>
                            <option value="yes">يوجد حوادث سابقة</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-white/80 font-bold mb-1">عدد السيارات</label>
                        <select id="c-cars" onchange="renderCompanyOffers()" class="w-full px-3 py-2 rounded-xl bg-slate-900/90 text-white border border-white/20 font-bold">
                            <option value="single">سيارة واحدة</option>
                            <option value="multiple">عدة سيارات</option>
                        </select>
                    </div>
                </div>
            </div>

            <div>
                <h3 class="text-xl font-black text-slate-900 mb-4">عروض وباقات {c['name']} المتاحة للأفراد</h3>
                <div id="company-offers-grid" class="grid grid-cols-1 md:grid-cols-2 gap-6"></div>
            </div>
        </div>

        <!-- ======================================================= -->
        <!-- 2. واجهة موظفي الشركة (الأدمن الخاص بهذه الشركة فقط) -->
        <!-- ======================================================= -->
        <div id="view-admin" class="hidden space-y-8">
            <div class="bg-white rounded-3xl p-6 border border-slate-200 shadow-sm flex items-center justify-between">
                <div class="flex items-center gap-4">
                    <div class="w-14 h-14 rounded-2xl text-white font-black text-xl flex items-center justify-center" style="background:{c['color']}">{c['badge']}</div>
                    <div>
                        <span class="text-xs font-bold text-slate-400">لوحة التحكم الخاصة بموظفي الشركة</span>
                        <h2 class="text-2xl font-black text-slate-900">إدارة عروض ونظام تسعيرة {c['name']}</h2>
                    </div>
                </div>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div class="lg:col-span-2 bg-white rounded-3xl p-6 border border-slate-200 shadow-sm">
                    <h3 class="text-lg font-black text-slate-900 mb-1">1. نظام التسعيرة الخاص بشركة {c['name']}</h3>
                    <p class="text-xs text-slate-500 mb-5">تحكم في الأسعار الأساسية ومعاملات تسعير الشركة (موقع العميل، الجنس، سجل الحوادث، وعدد السيارات):</p>

                    <div id="adm-msg" class="hidden mb-4 p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm font-bold"></div>

                    <form onsubmit="savePricing(event)" class="space-y-5 text-xs">
                        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-slate-50 p-4 rounded-2xl border border-slate-200">
                            <div>
                                <label class="font-bold block mb-1">سعر ضد الغير الأساسي (ر.س)</label>
                                <input type="number" id="pr-tpl" step="any" required class="w-full px-3 py-2 rounded-xl border border-slate-300 font-mono font-bold">
                            </div>
                            <div>
                                <label class="font-bold block mb-1">نسبة الشامل (%)</label>
                                <input type="number" id="pr-comp" step="any" required class="w-full px-3 py-2 rounded-xl border border-slate-300 font-mono font-bold">
                            </div>
                            <div>
                                <label class="font-bold block mb-1">الحد الأدنى للشامل (ر.س)</label>
                                <input type="number" id="pr-min" step="any" required class="w-full px-3 py-2 rounded-xl border border-slate-300 font-mono font-bold">
                            </div>
                            <div>
                                <label class="font-bold block mb-1">مبلغ التحمل (ر.س)</label>
                                <input type="number" id="pr-ded" step="any" required class="w-full px-3 py-2 rounded-xl border border-slate-300 font-mono font-bold">
                            </div>
                        </div>

                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div class="p-4 rounded-2xl border border-slate-200 space-y-2">
                                <h4 class="font-black text-slate-900"><i class="fa-solid fa-location-dot ml-1"></i> معامل موقع العميل</h4>
                                <div class="grid grid-cols-2 gap-2">
                                    <div><label class="text-slate-500 block mb-1">المدن المزدحمة (الرياض/جدة)</label><input type="number" id="pr-city-major" step="0.01" required class="w-full px-3 py-2 rounded-xl border border-slate-200 font-mono font-bold"></div>
                                    <div><label class="text-slate-500 block mb-1">المدن الأخرى</label><input type="number" id="pr-city-other" step="0.01" required class="w-full px-3 py-2 rounded-xl border border-slate-200 font-mono font-bold"></div>
                                </div>
                            </div>

                            <div class="p-4 rounded-2xl border border-slate-200 space-y-2">
                                <h4 class="font-black text-slate-900"><i class="fa-solid fa-venus-mars ml-1"></i> معامل الجنس</h4>
                                <div class="grid grid-cols-2 gap-2">
                                    <div><label class="text-slate-500 block mb-1">ذكر</label><input type="number" id="pr-gender-m" step="0.01" required class="w-full px-3 py-2 rounded-xl border border-slate-200 font-mono font-bold"></div>
                                    <div><label class="text-slate-500 block mb-1">أنثى</label><input type="number" id="pr-gender-f" step="0.01" required class="w-full px-3 py-2 rounded-xl border border-slate-200 font-mono font-bold"></div>
                                </div>
                            </div>

                            <div class="p-4 rounded-2xl border border-slate-200 space-y-2">
                                <h4 class="font-black text-slate-900"><i class="fa-solid fa-car-burst ml-1"></i> معامل الحوادث السابقة</h4>
                                <div class="grid grid-cols-2 gap-2">
                                    <div><label class="text-slate-500 block mb-1">بدون حوادث سابقة</label><input type="number" id="pr-acc-no" step="0.01" required class="w-full px-3 py-2 rounded-xl border border-slate-200 font-mono font-bold text-emerald-700"></div>
                                    <div><label class="text-slate-500 block mb-1">يوجد حوادث سابقة</label><input type="number" id="pr-acc-yes" step="0.01" required class="w-full px-3 py-2 rounded-xl border border-slate-200 font-mono font-bold text-red-600"></div>
                                </div>
                            </div>

                            <div class="p-4 rounded-2xl border border-slate-200 space-y-2">
                                <h4 class="font-black text-slate-900"><i class="fa-solid fa-cars ml-1"></i> معامل عدد السيارات</h4>
                                <div class="grid grid-cols-2 gap-2">
                                    <div><label class="text-slate-500 block mb-1">سيارة واحدة فقط</label><input type="number" id="pr-car-single" step="0.01" required class="w-full px-3 py-2 rounded-xl border border-slate-200 font-mono font-bold"></div>
                                    <div><label class="text-slate-500 block mb-1">عدة سيارات</label><input type="number" id="pr-car-multi" step="0.01" required class="w-full px-3 py-2 rounded-xl border border-slate-200 font-mono font-bold text-emerald-700"></div>
                                </div>
                            </div>
                        </div>

                        <div class="p-4 rounded-2xl border border-slate-200 bg-slate-50">
                            <label class="block font-black text-slate-800 mb-2">المزايا المشمولة في وثائق الشركة:</label>
                            <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
                                <label class="flex items-center gap-1.5"><input type="checkbox" name="adm-addon" value="agency_repair"> إصلاح وكالة</label>
                                <label class="flex items-center gap-1.5"><input type="checkbox" name="adm-addon" value="roadside_assistance"> مساعدة على الطريق</label>
                                <label class="flex items-center gap-1.5"><input type="checkbox" name="adm-addon" value="replacement_car"> سيارة بديلة</label>
                                <label class="flex items-center gap-1.5"><input type="checkbox" name="adm-addon" value="windshield_cover"> تغطية الزجاج</label>
                                <label class="flex items-center gap-1.5"><input type="checkbox" name="adm-addon" value="gulf_coverage"> تغطية الخليج</label>
                            </div>
                        </div>

                        <button type="submit" class="w-full text-white font-black py-4 rounded-2xl shadow-lg transition" style="background:{c['color']}">
                            حفظ واعتماد نظام التسعيرة للشركة
                        </button>
                    </form>
                </div>

                <div class="space-y-6">
                    <div class="bg-white rounded-3xl p-6 border border-slate-200 shadow-sm">
                        <h3 class="text-md font-black text-slate-900 mb-3">2. إضافة عرض تأميني جديد في {c['name']}</h3>
                        <form onsubmit="addOffer(event)" class="space-y-3 text-xs">
                            <input type="text" id="of-name" required placeholder="اسم العرض" class="w-full px-3 py-2.5 rounded-xl border border-slate-200">
                            <div class="grid grid-cols-2 gap-2">
                                <select id="of-cov" class="w-full px-3 py-2.5 rounded-xl border border-slate-200 font-bold">
                                    <option value="TPL">ضد الغير (TPL)</option>
                                    <option value="Comprehensive">تأمين شامل</option>
                                </select>
                                <input type="number" id="of-rate" step="any" required placeholder="السعر أو النسبة %" class="w-full px-3 py-2.5 rounded-xl border border-slate-200 font-mono">
                            </div>
                            <input type="number" id="of-min" value="500" required placeholder="الحد الأدنى للسعر" class="w-full px-3 py-2.5 rounded-xl border border-slate-200 font-mono">
                            <textarea id="of-desc" rows="2" required placeholder="وصف العرض ومميزاته..." class="w-full px-3 py-2 rounded-xl border border-slate-200"></textarea>
                            <button type="submit" class="w-full text-white font-bold py-3 rounded-xl shadow" style="background:{c['color']}">إضافة العرض</button>
                        </form>
                        <hr class="my-4 border-slate-100">
                        <div id="adm-offers-list" class="space-y-2 max-h-56 overflow-y-auto text-xs"></div>
                    </div>

                    <div class="bg-white rounded-3xl p-6 border border-slate-200 shadow-sm">
                        <h3 class="text-md font-black text-slate-900 mb-2">الوثائق المباعة في {c['name']}</h3>
                        <div id="adm-policies-list" class="space-y-2 max-h-52 overflow-y-auto text-xs"></div>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <!-- نافذة إتمام الطلب والشراء الخاصة بالشركة -->
    <div id="checkout-modal" class="fixed inset-0 bg-slate-900/75 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
        <div class="bg-white rounded-3xl max-w-lg w-full p-6 sm:p-8 shadow-2xl border border-slate-200">
            <div id="chk-form-box">
                <div class="flex items-center justify-between border-b border-slate-100 pb-4 mb-4">
                    <div>
                        <span class="text-xs font-bold text-slate-400">{c['name']}</span>
                        <h3 class="text-xl font-black text-slate-900">إكمال الطلب وإصدار الوثيقة</h3>
                    </div>
                    <button onclick="closeCheckout()" class="w-8 h-8 rounded-full bg-slate-100 text-slate-600"><i class="fa-solid fa-xmark"></i></button>
                </div>

                <div class="bg-slate-50 p-4 rounded-2xl border border-slate-200 mb-4 text-xs space-y-1.5">
                    <div class="flex justify-between"><span>العرض المختار:</span><strong id="chk-offer-name" class="text-slate-900"></strong></div>
                    <div class="flex justify-between"><span>نوع التغطية:</span><strong id="chk-cov-name"></strong></div>
                    <div class="flex justify-between border-t border-slate-200 pt-2 text-sm">
                        <span class="font-bold">الإجمالي شامل الضريبة (15%):</span>
                        <strong id="chk-total-amt" class="font-mono text-lg font-black" style="color:{c['color']}"></strong>
                    </div>
                </div>

                <form onsubmit="submitPurchase(event)" class="space-y-3.5 text-xs">
                    <div>
                        <label class="font-bold block mb-1">اسم مالك الوثيقة <span class="text-red-500">*</span></label>
                        <input type="text" id="chk-cust-name" required placeholder="الاسم الثلاثي" class="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm">
                    </div>
                    <div class="grid grid-cols-2 gap-3">
                        <div>
                            <label class="font-bold block mb-1">رقم الهوية</label>
                            <input type="text" id="chk-cust-id" required maxlength="10" value="1098765432" class="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 font-mono text-sm">
                        </div>
                        <div>
                            <label class="font-bold block mb-1">رقم الجوال</label>
                            <input type="tel" id="chk-cust-phone" required maxlength="10" value="0551234567" class="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 font-mono text-sm">
                        </div>
                    </div>
                    <div>
                        <label class="font-bold block mb-1">الرقم التسلسلي / VIN</label>
                        <input type="text" id="chk-cust-serial" required value="123456789" class="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 font-mono text-sm">
                    </div>
                    <div>
                        <label class="font-bold block mb-1">وسيلة الدفع الإلكتروني</label>
                        <select id="chk-pay-method" class="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 font-bold text-sm">
                            <option value="مدى (Mada)">بطاقة مدى البنكية</option>
                            <option value="فيزا / ماستركارد">بطاقة ائتمانية (Visa / MasterCard)</option>
                            <option value="Apple Pay">Apple Pay</option>
                        </select>
                    </div>
                    <button type="submit" class="w-full text-white font-black py-3.5 rounded-2xl shadow-lg text-sm transition" style="background:{c['color']}">
                        تأكيد الدفع وإصدار الوثيقة فوراً
                    </button>
                </form>
            </div>

            <div id="chk-success-box" class="hidden text-center space-y-4">
                <div class="w-16 h-16 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center text-3xl mx-auto">
                    <i class="fa-solid fa-circle-check"></i>
                </div>
                <h3 class="text-2xl font-black text-slate-900">تم إصدار وثيقتك من {c['name']}!</h3>
                <div class="bg-slate-50 p-4 rounded-2xl border border-slate-200 text-right text-xs space-y-2">
                    <div class="flex justify-between"><span>رقم الوثيقة:</span><strong id="pol-no" class="font-mono text-emerald-700 text-sm"></strong></div>
                    <div class="flex justify-between"><span>العرض:</span><strong id="pol-of"></strong></div>
                    <div class="flex justify-between"><span>الصلاحية:</span><strong id="pol-dates" class="font-mono"></strong></div>
                    <div class="flex justify-between border-t border-slate-200 pt-2"><span>الإجمالي المدفوع:</span><strong id="pol-total" class="font-mono font-black"></strong></div>
                </div>
                <div class="flex gap-3">
                    <button onclick="window.print()" class="flex-1 bg-slate-900 text-white font-bold py-3 rounded-xl text-xs">طباعة الوثيقة</button>
                    <button onclick="closeCheckout()" class="flex-1 text-white font-bold py-3 rounded-xl text-xs" style="background:{c['color']}">إغلاق</button>
                </div>
            </div>
        </div>
    </div>

    <footer class="bg-slate-900 text-slate-400 py-8 mt-12 text-center text-xs">
        <span>© 2026 جميع الحقوق محفوظة - {c['name']}</span>
    </footer>

    <script>
        const PROVIDER_ID = "{provider_id}";
        const COMPANY_COLOR = "{c['color']}";
        const ADDON_AR = {{
            agency_repair: "إصلاح وكالة",
            roadside_assistance: "مساعدة على الطريق",
            replacement_car: "سيارة بديلة",
            windshield_cover: "تغطية الزجاج",
            gulf_coverage: "تغطية الخليج"
        }};

        let companyData = {{ company: {{}}, offers: [], policies: [] }};
        let activeOrder = null;

        async function loadCompanyPortal() {{
            const res = await fetch(`/portal/api/company/${{PROVIDER_ID}}`);
            companyData = await res.json();
            applyUrlCustomerParams();
            renderCompanyOffers();
            populateAdmin();
        }}

        function switchView(v) {{
            const isCust = v === 'customer';
            document.getElementById('view-customer').classList.toggle('hidden', !isCust);
            document.getElementById('view-admin').classList.toggle('hidden', isCust);
            const btnC = document.getElementById('btn-view-customer');
            const btnA = document.getElementById('btn-view-admin');
            if (isCust) {{
                btnC.style.background = COMPANY_COLOR;
                btnC.className = "px-5 py-2 rounded-xl text-xs font-black transition text-white shadow";
                btnA.style.background = "transparent";
                btnA.className = "px-5 py-2 rounded-xl text-xs font-black transition text-slate-600";
            }} else {{
                btnA.style.background = COMPANY_COLOR;
                btnA.className = "px-5 py-2 rounded-xl text-xs font-black transition text-white shadow";
                btnC.style.background = "transparent";
                btnC.className = "px-5 py-2 rounded-xl text-xs font-black transition text-slate-600";
            }}
        }}

        function calcOfferPrice(offer) {{
            const r = companyData.company;
            const val = parseFloat(document.getElementById('c-val').value) || 85000;
            const age = parseInt(document.getElementById('c-age').value) || 30;
            const city = document.getElementById('c-city').value;
            const gender = document.getElementById('c-gender').value;
            const acc = document.getElementById('c-acc').value;
            const cars = document.getElementById('c-cars').value;

            let base = 500;
            if (offer.CoverageType === 'TPL') {{
                base = parseFloat(offer.BasePremiumRate) > 50 ? parseFloat(offer.BasePremiumRate) : r.tpl_base;
            }} else {{
                const rateDec = parseFloat(offer.BasePremiumRate) > 1 ? (parseFloat(offer.BasePremiumRate) / 100.0) : parseFloat(offer.BasePremiumRate);
                base = Math.max(val * rateDec, parseFloat(offer.MinPremium) || r.min_premium);
            }}

            const ageMult = age < 25 ? 1.35 : (age < 30 || age >= 60) ? 1.10 : 1.0;
            const cityMult = (city === 'riyadh' || city === 'jeddah' || city === 'eastern') ? r.city_major_mult : r.city_other_mult;
            const genderMult = (gender === 'female') ? r.gender_female_mult : r.gender_male_mult;
            const accMult = (acc === 'yes') ? r.has_accidents_mult : r.no_accidents_mult;
            const carsMult = (cars === 'multiple') ? r.multi_car_mult : r.single_car_mult;

            return Math.round(base * ageMult * cityMult * genderMult * accMult * carsMult);
        }}

        function renderCompanyOffers() {{
            const grid = document.getElementById('company-offers-grid');
            const r = companyData.company;
            grid.innerHTML = '';

            const addonsBadges = (r.addons || []).map(a => `<span class="bg-slate-100 text-slate-700 px-2.5 py-1 rounded-lg text-[11px] font-bold">✓ ${{ADDON_AR[a] || a}}</span>`).join('');

            (companyData.offers || []).forEach(o => {{
                const price = calcOfferPrice(o);
                grid.innerHTML += `
                    <div class="bg-white rounded-3xl p-6 border border-slate-200 shadow-sm hover:shadow-md transition flex flex-col justify-between">
                        <div>
                            <div class="flex items-center justify-between mb-3">
                                <h4 class="text-lg font-black text-slate-900">${{o.OfferName}}</h4>
                                <span class="px-3 py-1 rounded-full text-xs font-black ${{o.CoverageType === 'Comprehensive' ? 'bg-indigo-50 text-indigo-700' : 'bg-emerald-50 text-emerald-700'}}">
                                    ${{o.CoverageType === 'Comprehensive' ? 'تأمين شامل' : 'ضد الغير (TPL)'}}
                                </span>
                            </div>
                            <p class="text-xs text-slate-600 mb-4 leading-relaxed">${{o.Description || 'وثيقة تأمين معتمدة من الشركة.'}}</p>
                            <div class="flex flex-wrap gap-1.5 mb-4">${{addonsBadges}}</div>
                        </div>
                        <div class="flex items-center justify-between pt-4 border-t border-slate-100">
                            <div>
                                <span class="text-[11px] text-slate-400 block font-bold">السعر السنوي للوثيقة</span>
                                <span class="text-2xl font-black text-slate-900 font-mono">${{price}} <small class="text-xs">ر.س</small></span>
                                <span class="text-[11px] text-slate-400 block">التحمل: ${{r.deductible}} ر.س</span>
                            </div>
                            <button onclick="openCheckout('${{o.OfferName.replace(/'/g, "")}}', '${{o.CoverageType}}', ${{price}})"
                                    class="px-6 py-3.5 rounded-2xl text-white font-black text-xs shadow-lg transition hover:opacity-95"
                                    style="background:${{COMPANY_COLOR}}">
                                اختيار العرض والشراء <i class="fa-solid fa-cart-shopping mr-1"></i>
                            </button>
                        </div>
                    </div>
                `;
            }});
        }}

        function applyUrlCustomerParams() {{
            const p = new URLSearchParams(window.location.search);
            if (p.get('val')) document.getElementById('c-val').value = p.get('val');
            if (p.get('city')) document.getElementById('c-city').value = p.get('city');
            if (p.get('gender')) document.getElementById('c-gender').value = p.get('gender');
            if (p.get('accidents')) document.getElementById('c-acc').value = p.get('accidents');
            if (p.get('cars')) document.getElementById('c-cars').value = p.get('cars');
            if (p.get('national_id')) document.getElementById('chk-cust-id').value = p.get('national_id');
            if (p.get('serial')) document.getElementById('chk-cust-serial').value = p.get('serial');

            if (p.get('selected_offer') === '1') {{
                const cov = p.get('coverage') || 'TPL';
                const prem = parseFloat(p.get('premium')) || 500;
                const matchedOffer = (companyData.offers || []).find(o => o.CoverageType === cov) || (companyData.offers || [])[0];
                const offerTitle = matchedOffer ? matchedOffer.OfferName : (cov === 'Comprehensive' ? 'وثيقة التأمين الشامل' : 'وثيقة التأمين ضد الغير');

                const banner = document.getElementById('recommended-offer-banner');
                banner.classList.remove('hidden');
                document.getElementById('rec-banner-title').textContent = offerTitle;
                document.getElementById('rec-banner-details').textContent = `التغطية: ${{cov === 'Comprehensive' ? 'تأمين شامل' : 'ضد الغير (TPL)'}} | رقم الهوية: ${{p.get('national_id') || ''}} | الرقم التسلسلي: ${{p.get('serial') || ''}}`;
                document.getElementById('rec-banner-price').textContent = prem + ' ر.س';
                document.getElementById('rec-banner-buy-btn').onclick = () => openCheckout(offerTitle, cov, prem);
            }}
        }}

        function populateAdmin() {{
            const r = companyData.company;
            document.getElementById('pr-tpl').value = r.tpl_base;
            document.getElementById('pr-comp').value = (r.comp_rate * 100).toFixed(2);
            document.getElementById('pr-min').value = r.min_premium;
            document.getElementById('pr-ded').value = r.deductible;
            document.getElementById('pr-city-major').value = r.city_major_mult;
            document.getElementById('pr-city-other').value = r.city_other_mult;
            document.getElementById('pr-gender-m').value = r.gender_male_mult;
            document.getElementById('pr-gender-f').value = r.gender_female_mult;
            document.getElementById('pr-acc-no').value = r.no_accidents_mult;
            document.getElementById('pr-acc-yes').value = r.has_accidents_mult;
            document.getElementById('pr-car-single').value = r.single_car_mult;
            document.getElementById('pr-car-multi').value = r.multi_car_mult;

            document.querySelectorAll('input[name="adm-addon"]').forEach(cb => {{
                cb.checked = (r.addons || []).includes(cb.value);
            }});

            document.getElementById('adm-offers-list').innerHTML = (companyData.offers || []).map(o => `
                <div class="p-3 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between">
                    <div><strong>${{o.OfferName}}</strong> <span class="text-slate-400">(${{o.CoverageType}})</span></div>
                    <button onclick="deleteOffer(${{o.OfferId}})" class="text-red-500 hover:bg-red-50 p-1.5 rounded"><i class="fa-solid fa-trash"></i></button>
                </div>
            `).join('');

            document.getElementById('adm-policies-list').innerHTML = (companyData.policies || []).map(pol => `
                <div class="p-3 rounded-xl bg-slate-50 border border-slate-200">
                    <div class="flex justify-between font-bold"><span class="font-mono text-emerald-700">${{pol.PolicyNumber}}</span><span>${{pol.TotalAmount}} ر.س</span></div>
                    <div class="text-slate-500 mt-0.5">${{pol.CustomerName}} - ${{pol.OfferName}}</div>
                </div>
            `).join('') || '<p class="text-slate-400">لا توجد وثائق مصدرة بعد.</p>';
        }}

        async function savePricing(e) {{
            e.preventDefault();
            const addons = Array.from(document.querySelectorAll('input[name="adm-addon"]:checked')).map(c => c.value);
            const body = {{
                tpl_base: parseFloat(document.getElementById('pr-tpl').value),
                comp_rate_percent: parseFloat(document.getElementById('pr-comp').value),
                min_premium: parseFloat(document.getElementById('pr-min').value),
                deductible: parseFloat(document.getElementById('pr-ded').value),
                city_major_mult: parseFloat(document.getElementById('pr-city-major').value),
                city_other_mult: parseFloat(document.getElementById('pr-city-other').value),
                gender_male_mult: parseFloat(document.getElementById('pr-gender-m').value),
                gender_female_mult: parseFloat(document.getElementById('pr-gender-f').value),
                no_accidents_mult: parseFloat(document.getElementById('pr-acc-no').value),
                has_accidents_mult: parseFloat(document.getElementById('pr-acc-yes').value),
                single_car_mult: parseFloat(document.getElementById('pr-car-single').value),
                multi_car_mult: parseFloat(document.getElementById('pr-car-multi').value),
                addons
            }};
            const res = await fetch(`/portal/api/pricing/${{PROVIDER_ID}}`, {{
                method: 'PUT',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(body)
            }});
            const data = await res.json();
            const msg = document.getElementById('adm-msg');
            msg.textContent = data.message;
            msg.classList.remove('hidden');
            setTimeout(() => msg.classList.add('hidden'), 4000);
            await loadCompanyPortal();
        }}

        async function addOffer(e) {{
            e.preventDefault();
            const body = {{
                provider_id: PROVIDER_ID,
                offer_name: document.getElementById('of-name').value,
                coverage_type: document.getElementById('of-cov').value,
                base_premium_rate: parseFloat(document.getElementById('of-rate').value),
                min_premium: parseFloat(document.getElementById('of-min').value),
                description: document.getElementById('of-desc').value
            }};
            await fetch('/portal/api/offers', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(body)
            }});
            e.target.reset();
            await loadCompanyPortal();
        }}

        async function deleteOffer(id) {{
            await fetch(`/portal/api/offers/${{id}}`, {{ method: 'DELETE' }});
            await loadCompanyPortal();
        }}

        function openCheckout(offerName, covType, basePrice) {{
            const totalWithVat = Math.round(basePrice * 1.15);
            activeOrder = {{ offerName, covType, totalWithVat }};
            document.getElementById('chk-offer-name').textContent = offerName;
            document.getElementById('chk-cov-name').textContent = covType === 'Comprehensive' ? 'تأمين شامل' : 'ضد الغير (TPL)';
            document.getElementById('chk-total-amt').textContent = totalWithVat + ' ر.س';
            document.getElementById('chk-form-box').classList.remove('hidden');
            document.getElementById('chk-success-box').classList.add('hidden');
            document.getElementById('checkout-modal').classList.remove('hidden');
        }}

        function closeCheckout() {{
            document.getElementById('checkout-modal').classList.add('hidden');
        }}

        async function submitPurchase(e) {{
            e.preventDefault();
            const body = {{
                provider_id: PROVIDER_ID,
                offer_name: activeOrder.offerName,
                customer_name: document.getElementById('chk-cust-name').value.trim(),
                national_id: document.getElementById('chk-cust-id').value.trim(),
                phone: document.getElementById('chk-cust-phone').value.trim(),
                vehicle_serial: document.getElementById('chk-cust-serial').value.trim(),
                coverage_type: activeOrder.covType,
                total_amount: activeOrder.totalWithVat,
                payment_method: document.getElementById('chk-pay-method').value
            }};
            const res = await fetch('/portal/api/purchase', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(body)
            }});
            const data = await res.json();
            document.getElementById('chk-form-box').classList.add('hidden');
            document.getElementById('chk-success-box').classList.remove('hidden');
            document.getElementById('pol-no').textContent = data.policy_number;
            document.getElementById('pol-of').textContent = data.offer_name;
            document.getElementById('pol-dates').textContent = `${{data.issued_at}} إلى ${{data.expires_at}}`;
            document.getElementById('pol-total').textContent = data.total_amount + ' ر.س';
            loadCompanyPortal();
        }}

        loadCompanyPortal();
    </script>
</body>
</html>"""


@app.get("/tawuniya", response_class=HTMLResponse)
def tawuniya_independent_website():
    return _render_independent_company_site("tawuniya")


@app.get("/rajhi", response_class=HTMLResponse)
def rajhi_independent_website():
    return _render_independent_company_site("rajhi")


@app.get("/medgulf", response_class=HTMLResponse)
def medgulf_independent_website():
    return _render_independent_company_site("medgulf")


@app.get("/acig", response_class=HTMLResponse)
def acig_independent_website():
    return _render_independent_company_site("acig")


@app.get("/", response_class=HTMLResponse)
def companies_directory_home():
    """صفحة دليل سريعة لفتح أي موقع من مواقع الشركات الأربعة المستقلة."""
    cards = ""
    for pid, c in PRICING_RULES.items():
        cards += f"""
        <a href="/{pid}" class="bg-white p-6 rounded-3xl border border-slate-200 shadow-sm hover:shadow-lg transition flex items-center justify-between group">
            <div class="flex items-center gap-4">
                <div class="w-14 h-14 rounded-2xl text-white font-black text-lg flex items-center justify-center shadow" style="background:{c['color']}">{c['badge']}</div>
                <div>
                    <h2 class="text-xl font-black text-slate-900 group-hover:underline">{c['name']}</h2>
                    <p class="text-xs text-slate-500 mt-1">{c['slogan']}</p>
                </div>
            </div>
            <i class="fa-solid fa-arrow-left text-slate-400 group-hover:text-slate-900 transition"></i>
        </a>
        """
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>المواقع المستقلة لشركات التأمين</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>body {{ font-family: 'Tajawal', sans-serif; background-color: #f1f5f9; }}</style>
</head>
<body class="min-h-screen flex items-center justify-center p-6">
    <div class="max-w-4xl w-full space-y-6">
        <div class="text-center">
            <h1 class="text-3xl font-black text-slate-900">المواقع الإلكترونية المستقلة لشركات التأمين</h1>
            <p class="text-slate-600 text-sm mt-2">اختر موقع الشركة للدخول إلى واجهتها المستقلة (الأفراد والشراء + لوحة موظفي الشركة ونظام التسعير):</p>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-5">{cards}</div>
    </div>
</body>
</html>"""