/**
 * نسيت كلمة المرور — مساران:
 *   POST /api/auth/forgot-password   { email }
 *   GET  /api/auth/reset-password/verify?token=...
 *   POST /api/auth/reset-password    { token, password, confirm_password }
 *
 * مبادئ الأمان:
 * 1) نفس الرد دائماً سواء كان البريد مسجلاً أم لا (لا نكشف من لديه حساب).
 * 2) الرابط عشوائي 256-bit، يُخزَّن مشفّراً SHA-256، صالح 30 دقيقة ولمرة واحدة.
 * 3) بعد تغيير كلمة المرور تُلغى كل جلسات العميل المفتوحة وكل الروابط الأخرى.
 * 4) حد لعدد الطلبات من نفس الجهاز/البريد لمنع الإغراق.
 */
const crypto = require("node:crypto");
const express = require("express");
const bcrypt = require("bcryptjs");
const { hash, passwordErrors } = require("../auth");
const { transaction } = require("../services/recommendationStore");
const config = require("../config");

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const TOKEN_RE = /^[a-f0-9]{64}$/;
const GENERIC_MESSAGE =
  "إذا كان البريد مسجلاً لدينا فستصلك رسالة برابط إعادة تعيين كلمة المرور خلال دقائق.";
const INVALID_LINK =
  "رابط إعادة التعيين غير صالح أو منتهي الصلاحية. اطلب رابطاً جديداً.";
const RESEND_COOLDOWN_SECONDS = 60;

const now = () => Math.floor(Date.now() / 1000);

/** يبحث عن طلب إعادة تعيين صالح (غير مستخدم، غير منتهي، وصاحبه عميل مفعّل). */
function findValidReset(db, token) {
  if (typeof token !== "string" || !TOKEN_RE.test(token)) return null;
  return (
    db
      .prepare(
        "SELECT r.ResetId,r.UserId,u.PasswordHash FROM Password_Resets r " +
          "JOIN Users u ON u.UserId=r.UserId " +
          "WHERE r.TokenHash=? AND r.UsedAt IS NULL AND r.ExpiresAt>? " +
          "AND u.IsActive=1 AND u.IsAdmin=0",
      )
      .get(hash(token), now()) || null
  );
}

module.exports = ({ db, rate, mailer }) => {
  const r = express.Router();

  r.post("/forgot-password", (req, res) => {
    const email = String(req.body?.email || "")
      .trim()
      .toLowerCase();
    if (!EMAIL_RE.test(email))
      return res.status(422).json({
        error: "أدخل بريداً إلكترونياً صحيحاً",
        errors: [{ field: "email", message: "البريد الإلكتروني غير صحيح" }],
      });

    // حد الطلبات: 5 طلبات كل 15 دقيقة لكل (جهاز + بريد)
    const key = `reset|${req.ip}|${email}`;
    if (rate.blocked(key))
      return res.status(429).json({ error: "طلبات كثيرة، حاول لاحقاً" });
    rate.fail(key);

    const user = db
      .prepare(
        "SELECT UserId,UserName,Email FROM Users WHERE lower(Email)=? AND IsActive=1 AND IsAdmin=0",
      )
      .get(email);

    if (user) {
      const t = now();
      const recent = db
        .prepare(
          "SELECT 1 FROM Password_Resets WHERE UserId=? AND UsedAt IS NULL AND CreatedAt>?",
        )
        .get(user.UserId, t - RESEND_COOLDOWN_SECONDS);
      if (!recent) {
        const token = crypto.randomBytes(32).toString("hex");
        const ttl = config.resetTokenTtlMinutes;
        transaction(db, () => {
          // رابط واحد فعّال فقط لكل عميل: نلغي الروابط القديمة غير المستخدمة
          db.prepare(
            "DELETE FROM Password_Resets WHERE UserId=? AND UsedAt IS NULL",
          ).run(user.UserId);
          db.prepare(
            "INSERT INTO Password_Resets(UserId,TokenHash,CreatedAt,ExpiresAt,RequestIp) VALUES(?,?,?,?,?)",
          ).run(user.UserId, hash(token), t, t + ttl * 60, req.ip || null);
        });
        const link = `${config.publicBaseUrl}/reset-password.html?token=${token}`;
        // الإرسال لا يؤخر الرد (حتى لا يكشف زمن الرد وجود الحساب)
        Promise.resolve()
          .then(() =>
            mailer.sendPasswordReset({
              to: user.Email,
              username: user.UserName,
              link,
              expiresMinutes: ttl,
            }),
          )
          .catch((error) =>
            console.error("[THIQA] password reset mail:", error),
          );
      }
    }
    res.json({ ok: true, message: GENERIC_MESSAGE });
  });

  r.get("/reset-password/verify", (req, res) => {
    res.json({ valid: Boolean(findValidReset(db, req.query.token)) });
  });

  r.post("/reset-password", async (req, res) => {
    const { token, password } = req.body || {};
    const confirmPassword =
      req.body?.confirm_password ?? req.body?.confirmPassword;
    const reset = findValidReset(db, token);
    if (!reset) return res.status(400).json({ error: INVALID_LINK });

    const errors = passwordErrors(password, confirmPassword);
    if (!errors.length && (await bcrypt.compare(password, reset.PasswordHash)))
      errors.push({
        field: "password",
        message: "كلمة المرور الجديدة يجب أن تختلف عن السابقة",
      });
    if (errors.length)
      return res
        .status(422)
        .json({ error: "تحقق من البيانات المدخلة", errors });

    const newHash = await bcrypt.hash(password, 10);
    const used = transaction(db, () => {
      // UsedAt IS NULL في الشرط يمنع استخدام نفس الرابط مرتين حتى لو وصل طلبان معاً
      const mark = db
        .prepare(
          "UPDATE Password_Resets SET UsedAt=? WHERE ResetId=? AND UsedAt IS NULL",
        )
        .run(now(), reset.ResetId);
      if (!mark.changes) return false;
      db.prepare("UPDATE Users SET PasswordHash=? WHERE UserId=?").run(
        newHash,
        reset.UserId,
      );
      db.prepare(
        "DELETE FROM Password_Resets WHERE UserId=? AND UsedAt IS NULL",
      ).run(reset.UserId);
      // تسجيل خروج من كل الأجهزة: من كان يملك جلسة قديمة يفقدها
      db.prepare("DELETE FROM Sessions WHERE UserId=? AND Kind='customer'").run(
        reset.UserId,
      );
      return true;
    });
    if (!used) return res.status(400).json({ error: INVALID_LINK });
    res.json({
      ok: true,
      message: "تم تغيير كلمة المرور بنجاح. سجّل الدخول بكلمة المرور الجديدة.",
    });
  });

  return r;
};
