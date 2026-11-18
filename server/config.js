/** Central runtime defaults for the Node gateway. */
module.exports = {
  agentsUrl: process.env.AGENTS_SERVICE_URL || "http://127.0.0.1:8000",
  bodyLimit: "64kb",
  agentsTimeoutMs: 20_000,
  // الرابط العام للموقع: يُستخدم لبناء رابط "إعادة تعيين كلمة المرور" في البريد.
  // لا نعتمد على ترويسة Host القادمة من المتصفح حتى لا يُزوَّر الرابط.
  publicBaseUrl: (
    process.env.PUBLIC_BASE_URL || `http://localhost:${process.env.PORT || 3000}`
  ).replace(/\/+$/, ""),
  // مدة صلاحية رابط إعادة التعيين بالدقائق
  resetTokenTtlMinutes: Number(process.env.RESET_TOKEN_TTL_MINUTES || 30),
};
