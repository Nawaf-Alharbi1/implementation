"""
إعدادات الاتصال بشركات التأمين (Insurance APIs).

تقابل جدول API_Settings في التقرير (القسم 3.6.2):
    Endpoint  -> base_url + path
    AuthKey   -> api_key_for(provider_id)
    Protocol  -> protocol
    Timeout   -> timeout (بالثواني)

الحقول reliability / workshop_network / digital_score هي بيانات تعريفية عن الشركة
(ليست جزءاً من رد الـ API) يحتاجها Agent 2 لاحقاً عند التقييم.

للتحويل إلى APIs حقيقية: غيّر INSURERS_BASE_URL (أو الـ endpoint لكل شركة) ومفاتيح
<PROVIDER>_API_KEY في متغيرات البيئة — ولا يتغير أي كود آخر.
"""

import os

DEFAULT_BASE_URL = "http://127.0.0.1:8001"  # خدمة Mock Insurance API

# الإضافات المعتمدة داخل النظام (الصيغة الموحدة)
CANONICAL_ADDONS = (
    "agency_repair",
    "roadside_assistance",
    "replacement_car",
    "windshield_cover",
    "gulf_coverage",
)

_INSURER_DEFS = [
    {
        "provider_id": "tawuniya",
        "name": "التعاونية للتأمين",
        "adapter": "tawuniya",
        "path": "/tawuniya/quotes",
        "auth_scheme": "x-api-key",
        "protocol": "REST/JSON",
        "reliability": 0.95,
        "workshop_network": "واسع جداً",
        "digital_score": 0.82,
    },
    {
        "provider_id": "rajhi",
        "name": "الراجحي تكافل",
        "adapter": "rajhi",
        "path": "/rajhi/offers",
        "auth_scheme": "bearer",
        "protocol": "REST/JSON",
        "reliability": 0.90,
        "workshop_network": "متوسط",
        "digital_score": 0.96,
    },
    {
        "provider_id": "medgulf",
        "name": "ميدغلف للتأمين",
        "adapter": "medgulf",
        "path": "/medgulf/plans",
        "auth_scheme": "x-api-key",
        "protocol": "REST/JSON",
        "reliability": 0.85,
        "workshop_network": "متوسط",
        "digital_score": 0.88,
    },
    {
        "provider_id": "acig",
        "name": "المجموعة المتحدة للتأمين (ACIG)",
        "adapter": "acig",
        "path": "/acig/quote",
        "auth_scheme": "x-api-key",
        "protocol": "REST/JSON",
        "reliability": 0.78,
        "workshop_network": "محدود",
        "digital_score": 0.78,
    },
]


def api_key_for(provider_id: str) -> str:
    """مفتاح المصادقة لكل شركة (من البيئة، وإلا قيمة تجريبية للتطوير)."""
    return os.getenv(f"{provider_id.upper()}_API_KEY", f"{provider_id}-test-key")


def load_insurers(base_url: str | None = None, timeout: float | None = None) -> list[dict]:
    """يرجع قائمة الشركات المتصل بها مع إعدادات كل واحدة."""
    base = (base_url or os.getenv("INSURERS_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    t = timeout if timeout is not None else float(os.getenv("INSURER_TIMEOUT", "5"))
    insurers = []
    for d in _INSURER_DEFS:
        insurers.append({
            **d,
            "base_url": base,
            "timeout": t,
            "api_key": api_key_for(d["provider_id"]),
        })
    return insurers
