"""
Mock / Test Insurance API — خدمة مستقلة تحاكي APIs شركات التأمين الحقيقية.

تعمل كخدمة HTTP منفصلة (بورت 8001) حتى يتصل بها Agent 1 عبر شبكة فعلية تماماً كما
سيتصل بالشركات الحقيقية. كل شركة لها:
    - endpoint خاص بها
    - طريقة مصادقة (X-API-Key أو Bearer)
    - صيغة طلب ورد مختلفة (لذلك نحتاج التوحيد في Agent 1)

الأسعار ثابتة (deterministic) لنفس المدخلات، فلا تتغير بين طلب وآخر.

حقن الأعطال (للاختبار):
    متغير بيئة:  MOCK_FAULTS="acig=timeout,medgulf=500"
    أو أثناء التشغيل:  POST /_mock/faults  {"provider_id": "acig", "fault": "timeout"}
    الأنواع: timeout | 500 | 503 | bad_json | empty | malformed

للتشغيل:
    uvicorn mock_insurer_api:app --port 8001
"""

import asyncio
import hashlib
import os
from datetime import date
from typing import Literal

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel

from insurers_config import api_key_for

app = FastAPI(title="Thiqa Mock Insurance APIs")

FAULT_TYPES = {"timeout", "500", "503", "bad_json", "empty", "malformed"}
PROVIDERS = {"tawuniya", "rajhi", "medgulf", "acig"}


def _faults_from_env() -> dict[str, str]:
    faults = {}
    for part in os.getenv("MOCK_FAULTS", "").split(","):
        if "=" in part:
            pid, fault = part.split("=", 1)
            if pid.strip() in PROVIDERS and fault.strip() in FAULT_TYPES:
                faults[pid.strip()] = fault.strip()
    return faults


FAULTS: dict[str, str] = _faults_from_env()

# ----------------------------------------------------------------------------- بيانات التسعير
TPL_BASE = {"tawuniya": 483, "rajhi": 507, "medgulf": 469, "acig": 428}
COMP_RATE = {"tawuniya": 0.0285, "rajhi": 0.0250, "medgulf": 0.0265, "acig": 0.0210}
DEDUCTIBLE = {"tawuniya": 500, "rajhi": 750, "medgulf": 1000, "acig": 1500}
ADDONS = {
    "tawuniya": ["roadside_assistance", "replacement_car", "gulf_coverage"],
    "rajhi": ["agency_repair", "roadside_assistance", "windshield_cover"],
    "medgulf": ["windshield_cover", "gulf_coverage"],
    "acig": ["roadside_assistance"],
}


def _age_from_birth(birth_iso: str) -> int:
    try:
        b = date.fromisoformat(birth_iso)
    except ValueError:
        raise HTTPException(status_code=422, detail="invalid birth date")
    t = date.today()
    return t.year - b.year - ((t.month, t.day) < (b.month, b.day))


def price(provider_id: str, age: int, value: float, coverage: str, usage: str, mileage: str | None, serial: str) -> float:
    """تسعير تقريبي (للعرض فقط) وثابت لنفس المدخلات."""
    base = TPL_BASE[provider_id] if coverage == "TPL" else max(value * COMP_RATE[provider_id], 1200)
    age_mult = 1.35 if age < 25 else 1.10 if age < 30 else 1.10 if age >= 60 else 1.0
    use_mult = 1.25 if "commercial" in (usage or "").lower() else 1.0
    km_mult = {"low": 0.95, "high": 1.08}.get((mileage or "").lower(), 1.0)
    h = int(hashlib.sha256(f"{provider_id}|{serial}|{coverage}".encode()).hexdigest()[:8], 16)
    jitter = 0.97 + (h % 600) / 10000  # بين 0.97 و 1.03، ثابت لنفس السيارة
    return round(base * age_mult * use_mult * km_mult * jitter, 2)


def _ref(provider_id: str, serial: str, coverage: str) -> str:
    return hashlib.sha256(f"ref|{provider_id}|{serial}|{coverage}".encode()).hexdigest()[:6].upper()


# ----------------------------------------------------------------------------- المصادقة والأعطال
def _check_key(provider_id: str, presented: str | None):
    if not presented or presented != api_key_for(provider_id):
        raise HTTPException(status_code=401, detail="invalid or missing API key")


def _bearer(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


async def _gate(provider_id: str) -> str | None:
    """يحاكي زمن الاستجابة، ثم يطبق العطل المحقون (إن وجد)."""
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


# ----------------------------------------------------------------------------- التعاونية
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
    prem = price("tawuniya", _age_from_birth(body.birth_date), body.vehicle.value, cov, body.usage, body.annual_mileage, body.vehicle.serial)
    return {
        "insurer": "tawuniya",
        "packages": [{
            "package_id": f"TAW-{_ref('tawuniya', body.vehicle.serial, cov)}",
            "coverage": body.coverage,
            "premium_sar": prem,
            "deductible_sar": DEDUCTIBLE["tawuniya"],
            "add_ons": ADDONS["tawuniya"],
        }],
    }


# ----------------------------------------------------------------------------- الراجحي تكافل
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
    prem = price("rajhi", _age_from_birth(body.customer.dob), body.car.market_value, cov, body.use, None, body.car.sequence_no)
    return {
        "data": {"offers": [{
            "id": f"RJ{_ref('rajhi', body.car.sequence_no, cov)}",
            "type": body.product,
            "price": {"amount": prem, "currency": "SAR"},
            "excess": DEDUCTIBLE["rajhi"],
            "extras": ADDONS["rajhi"],
        }]}
    }


# ----------------------------------------------------------------------------- ميدغلف
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
    prem = price("medgulf", _age_from_birth(body.birthDate), body.value, cov, body.purpose, body.mileage, body.chassis)
    return {
        "result": [{
            "ref": f"MG-{_ref('medgulf', body.chassis, cov)}",
            "plan": body.plan,
            "annual_cost": f"{prem:.2f}",                       # نص وليس رقماً
            "deductible": str(DEDUCTIBLE["medgulf"]),           # نص وليس رقماً
            "options": ",".join(ADDONS["medgulf"]),             # نص مفصول بفواصل
        }]
    }


# ----------------------------------------------------------------------------- ACIG
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
    prem = price("acig", body.age, body.vehicle_value, cov, body.usage, None, body.vehicle_serial)
    return {
        "quotes": [{
            "quote_ref": f"AC{_ref('acig', body.vehicle_serial, cov)}",
            "product": body.cover_type,
            "premium_halalas": int(round(prem * 100)),          # بالهللات
            "co_pay": DEDUCTIBLE["acig"],
            "addons": ADDONS["acig"],
        }]
    }


# ----------------------------------------------------------------------------- التحكم بالأعطال (للاختبار)
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
