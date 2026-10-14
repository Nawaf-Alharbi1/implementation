## التشغيل

**أول مرة فقط (تثبيت المكتبات):**

```
cd agents  && pip install -r requirements.txt
cd server  && npm install
```

**كل مرة:** من مجلد المشروع شغّل

```
./run-website.bat
```

ويفتح 3 خدمات: Mock Insurers (8001) + Agents (8000) + الموقع (3000)، ثم افتح http://localhost:3000

> قاعدة البيانات (SQLite) تُنشأ تلقائياً في `database/thiqa.db` عند أول تشغيل.
> في الإنتاج اضبط متغير البيئة `JWT_SECRET` بقيمة سرية طويلة.

## اختبار Agent 1 بشكل مستقل

```
cd agents
python -m pytest tests -v        # 43 اختباراً، لا تحتاج تشغيل أي سيرفر
```

أو تشغيله وحده عبر HTTP (بعد تشغيل خدمتي 8000 و 8001) من Swagger: http://localhost:8000/docs ← `POST /agent1/retrieve`

**حقن أعطال في شركات التأمين التجريبية** (لتجربة معالجة الأخطاء يدوياً):

```
curl -X POST localhost:8001/_mock/faults -H "Content-Type: application/json" -d "{\"provider_id\":\"acig\",\"fault\":\"timeout\"}"
curl -X DELETE localhost:8001/_mock/faults        # إزالة كل الأعطال
```
الأنواع: `timeout | 500 | 503 | bad_json | empty | malformed`

## هيكل المجلدات

```
implementation/
├── agents/                       # خدمة الوكلاء (Python/FastAPI) — الطبقة 2
│   ├── main.py                   # POST /recommend  و  POST /agent1/retrieve
│   ├── agent1_receiver.py        # الوكيل 1: التحقق + الاتصال بالـ APIs بالتوازي + معالجة الأخطاء
│   ├── insurer_adapters.py       # لكل شركة: بناء الطلب + توحيد الرد (Unified Quote)
│   ├── insurers_config.py        # إعدادات الاتصال (تقابل جدول API_Settings)
│   ├── mock_insurer_api.py       # Mock Insurance API (خدمة مستقلة، بورت 8001)
│   ├── agent2_recommender.py     # الوكيل 2 (لم يتغير)
│   ├── agent3_explainer.py       # الوكيل 3 (لم يتغير)
│   ├── tests/test_agent1.py      # اختبارات Agent 1
│   └── requirements.txt
├── server/                       # Node.js — الواجهة + المصادقة + البوابة
│   ├── server.js                 # Express + حماية /api/recommend
│   ├── auth.js                   # تسجيل / دخول / خروج / me
│   ├── db.js                     # اتصال SQLite وإنشاء الجداول
│   └── public/index.html         # الواجهة
├── database/
│   ├── thiqa_database.sql        # المخطط الأصلي (MySQL)
│   ├── schema.sqlite.sql         # نفس الجداول بصيغة SQLite (يُستخدم حالياً)
│   └── *.png
└── run-website.bat
```

## المصادقة (API)

| المسار | الوصف |
|---|---|
| `POST /api/auth/register` | `{username, email, password}` ← ينشئ الحساب ويسجّل الدخول |
| `POST /api/auth/login` | `{identifier, password}` (البريد أو اسم المستخدم) |
| `POST /api/auth/logout` | |
| `GET /api/auth/me` | المستخدم الحالي أو 401 |

---

### Tables
![Tables](database/show-tables&columns.png)

---

### Primary Keys
![Primary Keys](database/show-PK.png)

---

### Foreign Keys
![Foreign Keys](database/relations&FK.png)
