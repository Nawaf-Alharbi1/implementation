/**
 * إرسال بريد "إعادة تعيين كلمة المرور".
 *
 * - إذا ضُبط خادم بريد (SMTP_HOST ...) يُرسل الرابط فعلياً إلى بريد العميل عبر nodemailer.
 * - بدون SMTP (بيئة التطوير والعرض): يُطبع الرابط في نافذة/سجل خادم Node فقط،
 *   ولا يظهر أبداً في المتصفح، فلا يستطيع أحد غير مشغّل الخادم استخدامه.
 *
 * المتغيرات: SMTP_HOST, SMTP_PORT (587), SMTP_SECURE (1 للمنفذ 465),
 *            SMTP_USER, SMTP_PASS, MAIL_FROM
 */
function smtpConfigured() {
  return Boolean(process.env.SMTP_HOST);
}

function buildMessage({ username, link, expiresMinutes }) {
  const subject = "ثقة — إعادة تعيين كلمة المرور";
  const text =
    `مرحباً ${username}،\n\n` +
    "وصلنا طلب لإعادة تعيين كلمة المرور لحسابك في منصة ثقة.\n" +
    `لتعيين كلمة مرور جديدة افتح الرابط التالي (صالح لمدة ${expiresMinutes} دقيقة ولمرة واحدة):\n\n` +
    `${link}\n\n` +
    "إذا لم تطلب ذلك فتجاهل هذه الرسالة، وستبقى كلمة مرورك الحالية كما هي.\n\n" +
    "منصة ثقة للتأمين الذكي";
  const html =
    `<div dir="rtl" style="font-family:Tahoma,Arial,sans-serif;line-height:1.8">` +
    `<p>مرحباً ${escapeHtml(username)}،</p>` +
    "<p>وصلنا طلب لإعادة تعيين كلمة المرور لحسابك في منصة ثقة.</p>" +
    `<p><a href="${escapeHtml(link)}" style="display:inline-block;background:#059669;color:#fff;` +
    `padding:10px 18px;border-radius:10px;text-decoration:none;font-weight:bold">تعيين كلمة مرور جديدة</a></p>` +
    `<p style="color:#64748b;font-size:13px">الرابط صالح لمدة ${expiresMinutes} دقيقة ولمرة واحدة. ` +
    "إذا لم تطلب ذلك فتجاهل هذه الرسالة.</p></div>";
  return { subject, text, html };
}

function escapeHtml(value) {
  return String(value).replace(
    /[&<>"']/g,
    (ch) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        ch
      ],
  );
}

function logToConsole(to, link, expiresMinutes) {
  console.log(
    "\n[THIQA] لا يوجد خادم بريد (SMTP) — رابط إعادة تعيين كلمة المرور:\n" +
      `  المستخدم: ${to}\n  الرابط:   ${link}\n  الصلاحية: ${expiresMinutes} دقيقة\n`,
  );
}

let transport;
function getTransport() {
  if (transport !== undefined) return transport;
  try {
    const nodemailer = require("nodemailer");
    const port = Number(process.env.SMTP_PORT || 587);
    transport = nodemailer.createTransport({
      host: process.env.SMTP_HOST,
      port,
      secure: process.env.SMTP_SECURE === "1" || port === 465,
      auth: process.env.SMTP_USER
        ? { user: process.env.SMTP_USER, pass: process.env.SMTP_PASS }
        : undefined,
    });
  } catch (error) {
    console.warn(
      "[THIQA] SMTP مضبوط لكن مكتبة nodemailer غير مثبتة (npm install). سيُطبع الرابط في السجل.",
    );
    transport = null;
  }
  return transport;
}

/** يرسل رابط إعادة التعيين، ويرجع طريقة التسليم: smtp أو console. */
async function sendPasswordReset({ to, username, link, expiresMinutes }) {
  const message = buildMessage({ username, link, expiresMinutes });
  const smtp = smtpConfigured() && getTransport();
  if (smtp) {
    try {
      await smtp.sendMail({
        from: process.env.MAIL_FROM || process.env.SMTP_USER,
        to,
        ...message,
      });
      return "smtp";
    } catch (error) {
      console.error("[THIQA] فشل إرسال بريد إعادة التعيين:", error.message);
      // Do not print a live reset token to server logs when SMTP was configured.
      throw error;
    }
  }
  if (process.env.SMTP_HOST) {
    console.error("[THIQA] إعدادات SMTP غير مكتملة؛ لم يتم إرسال رسالة الاستعادة.");
    return "unavailable";
  }
  logToConsole(to, link, expiresMinutes);
  return "console";
}

module.exports = { sendPasswordReset, buildMessage };
