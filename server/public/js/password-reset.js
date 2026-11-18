/**
 * صفحتا "نسيت كلمة المرور" و"تعيين كلمة مرور جديدة".
 * التحقق في المتصفح لتجربة أسرع فقط؛ الخادم يعيد التحقق دائماً.
 */
(() => {
  const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const forgotForm = document.getElementById("forgot-form");
  const resetForm = document.getElementById("reset-form");
  const form = forgotForm || resetForm;
  if (!form) return;
  const formError = document.getElementById("form-error");

  const show = (id) => document.getElementById(id).classList.remove("hidden");
  const hide = (id) => document.getElementById(id).classList.add("hidden");

  function setFieldError(field, message) {
    const box = form.querySelector(`[data-error="${field}"]`);
    const input = form.querySelector(`[name="${field}"]`);
    if (box) box.textContent = message || "";
    if (input) input.classList.toggle("border-red-400", Boolean(message));
  }
  function clearErrors() {
    form
      .querySelectorAll("[data-error]")
      .forEach((box) => setFieldError(box.dataset.error, ""));
    formError.classList.add("hidden");
  }
  function showFormError(message) {
    formError.textContent = message;
    formError.classList.remove("hidden");
  }
  function showServerErrors(error) {
    const fieldErrors = error.data?.errors || [];
    fieldErrors.forEach((item) => setFieldError(item.field, item.message));
    if (!fieldErrors.length) showFormError(error.message);
  }

  // ------------------------------------------------ 1) نسيت كلمة المرور
  if (forgotForm) {
    forgotForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      clearErrors();
      const email = forgotForm.email.value.trim();
      if (!EMAIL_RE.test(email))
        return setFieldError("email", "البريد الإلكتروني غير صحيح");

      const button = forgotForm.querySelector('button[type="submit"]');
      TH.setLoading(button, true, "جارٍ الإرسال…");
      try {
        const data = await TH.api("/api/auth/forgot-password", {
          method: "POST",
          body: { email },
        });
        document.getElementById("sent-message").textContent = data.message;
        hide("request-step");
        show("sent-step");
      } catch (error) {
        showServerErrors(error);
      } finally {
        TH.setLoading(button, false);
      }
    });

    document.getElementById("try-again").addEventListener("click", () => {
      hide("sent-step");
      show("request-step");
    });
    return;
  }

  // ------------------------------------------------ 2) تعيين كلمة مرور جديدة
  const token = new URLSearchParams(location.search).get("token") || "";
  // نزيل الرمز من شريط العنوان والسجل بعد قراءته
  history.replaceState(null, "", location.pathname);

  const rules = {
    length: (p) => p.length >= 8,
    letter: (p) => /[A-Za-z]/.test(p),
    digit: (p) => /\d/.test(p),
  };
  resetForm.password.addEventListener("input", () => {
    const value = resetForm.password.value;
    Object.entries(rules).forEach(([rule, test]) => {
      const item = document.querySelector(`[data-rule="${rule}"]`);
      item.classList.toggle("text-brand-600", test(value));
      item.classList.toggle("text-slate-400", !test(value));
    });
  });
  resetForm.querySelectorAll("[data-toggle-password]").forEach((button) => {
    button.addEventListener("click", () => {
      const input = document.getElementById(button.dataset.togglePassword);
      const hidden = input.type === "password";
      input.type = hidden ? "text" : "password";
      button.innerHTML = `<i class="fa-solid ${hidden ? "fa-eye-slash" : "fa-eye"}"></i>`;
    });
  });

  (async () => {
    let valid = false;
    if (/^[a-f0-9]{64}$/.test(token)) {
      try {
        const data = await TH.api(
          `/api/auth/reset-password/verify?token=${encodeURIComponent(token)}`,
        );
        valid = data.valid;
      } catch {
        valid = false;
      }
    }
    hide("checking-step");
    show(valid ? "reset-step" : "invalid-step");
  })();

  resetForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearErrors();
    const password = resetForm.password.value;
    const confirm_password = resetForm.confirm_password.value;
    let bad = false;
    if (!Object.values(rules).every((test) => test(password))) {
      setFieldError(
        "password",
        "كلمة المرور 8 أحرف على الأقل وتحتوي حرفاً ورقماً",
      );
      bad = true;
    }
    if (password !== confirm_password) {
      setFieldError("confirm_password", "كلمتا المرور غير متطابقتين");
      bad = true;
    }
    if (bad) return;

    const button = resetForm.querySelector('button[type="submit"]');
    TH.setLoading(button, true, "جارٍ الحفظ…");
    try {
      await TH.api("/api/auth/reset-password", {
        method: "POST",
        body: { token, password, confirm_password },
      });
      location.replace("/login.html?reset=1");
    } catch (error) {
      if (error.status === 400) {
        hide("reset-step");
        show("invalid-step");
      } else showServerErrors(error);
      TH.setLoading(button, false);
    }
  });
})();
