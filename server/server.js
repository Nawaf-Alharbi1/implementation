/**
 * Thiqa Node.js Server (Port 3000)
 * يعمل كبوابة لواجهة التوصية الذكية (بدون تسجيل دخول) ويتصل عبر الـ API
 * بخدمة الوكلاء (8000) ومنصة التأمين الوطنية (8001).
 */

const express = require("express");
const path = require("path");

const app = express();
const PORT = process.env.PORT || 3000;
const AGENTS_SERVICE_URL = process.env.AGENTS_SERVICE_URL || "http://127.0.0.1:8000";
const INSURER_PLATFORM_URL = process.env.INSURER_PLATFORM_URL || "http://127.0.0.1:8001";

app.use(express.json());
app.use(express.static(path.join(__dirname, "public")));

// نقطة الاتصال بين موقع ثقة وخدمة الوكلاء (التي تسحب العروض عبر الـ API من الموقع الجديد 8001)
app.post("/api/recommend", async (req, res) => {
  try {
    // 1. إرسال عوامل التسعير (الموقع، الجنس، الحوادث السابقة، عدد السيارات) إلى منصة التأمين (8001)
    await fetch(`${INSURER_PLATFORM_URL}/portal/api/customer-context`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        city: req.body.city || "riyadh",
        gender: req.body.gender || "male",
        has_accidents: req.body.has_accidents || "no",
        cars_count: req.body.cars_count || "single",
      }),
    }).catch(() => {});

    // 2. تشغيل خط أنابيب الوكلاء الثلاثة (Agent 1 -> Agent 2 -> Agent 3)
    const response = await fetch(`${AGENTS_SERVICE_URL}/recommend`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req.body),
    });

    const data = await response.json();
    if (!response.ok) {
      return res.status(response.status).json(data);
    }

    return res.json(data);
  } catch (err) {
    console.error("Agents service error:", err.message);
    return res.status(502).json({
      error: "تعذر الاتصال بخدمة الوكلاء (Python). تأكد أنها تعمل على المنفذ 8000.",
    });
  }
});

app.get("/api/health", (req, res) => {
  res.json({ status: "ok", service: "thiqa-node-server" });
});
// مسار يزود الواجهة الأمامية برابط منصة شركات التأمين (سواء محلياً أو على Render)
app.get("/api/config", (req, res) => {
  res.json({
    insurerPlatformUrl: process.env.INSURER_PLATFORM_URL || "http://127.0.0.1:8001"
  });
});
app.listen(PORT, () => {
  console.log(`✅ 1. موقع ثقة للتوصية الذكية يعمل على: http://localhost:${PORT}`);
  console.log(`✅ 2. الموقع الجديد المستقل (منصة التأمين 8001): http://127.0.0.1:8001`);
});