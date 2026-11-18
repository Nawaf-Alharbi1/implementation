const { test } = require("node:test");
const assert = require("node:assert/strict");
const { makeHarness, register } = require("./helpers");

/** بريد وهمي يلتقط الرسائل بدل إرسالها. */
function fakeMailer() {
  const sent = [];
  return {
    sent,
    async sendPasswordReset(message) {
      sent.push(message);
      return "test";
    },
  };
}
const tokenFrom = (link) => new URL(link).searchParams.get("token");
const tick = () => new Promise((r) => setTimeout(r, 20));

test("forgot password: same answer for unknown email, link only for real account", async (t) => {
  const mailer = fakeMailer();
  const h = await makeHarness({ mailer });
  t.after(() => h.close());
  await register(h, "resetuser");

  const unknown = await h.call("/api/auth/forgot-password", "POST", {
    email: "nobody@example.test",
  });
  const known = await h.call("/api/auth/forgot-password", "POST", {
    email: "ResetUser@Example.test",
  });
  assert.equal(unknown.status, 200);
  assert.equal(known.status, 200);
  assert.deepEqual(await unknown.json(), await known.json());
  await tick();
  assert.equal(mailer.sent.length, 1);
  assert.equal(mailer.sent[0].to, "resetuser@example.test");
  assert.match(tokenFrom(mailer.sent[0].link), /^[a-f0-9]{64}$/);
  // الرمز لا يُخزَّن كنص في قاعدة البيانات
  const row = h.db.prepare("SELECT TokenHash FROM Password_Resets").get();
  assert.notEqual(row.TokenHash, tokenFrom(mailer.sent[0].link));

  const bad = await h.call("/api/auth/forgot-password", "POST", {
    email: "not-an-email",
  });
  assert.equal(bad.status, 422);
});

test("reset password: changes password, single use, logs out old sessions", async (t) => {
  const mailer = fakeMailer();
  const h = await makeHarness({ mailer });
  t.after(() => h.close());
  const { cookie: oldSession } = await register(h, "changer");

  await h.call("/api/auth/forgot-password", "POST", {
    email: "changer@example.test",
  });
  await tick();
  const token = tokenFrom(mailer.sent[0].link);

  const verify = await (
    await h.call(`/api/auth/reset-password/verify?token=${token}`)
  ).json();
  assert.equal(verify.valid, true);

  const weak = await h.call("/api/auth/reset-password", "POST", {
    token,
    password: "short",
    confirm_password: "short",
  });
  assert.equal(weak.status, 422);
  const same = await h.call("/api/auth/reset-password", "POST", {
    token,
    password: "Passw0rd1",
    confirm_password: "Passw0rd1",
  });
  assert.equal(same.status, 422, "new password must differ from the old one");

  const ok = await h.call("/api/auth/reset-password", "POST", {
    token,
    password: "NewPassw0rd2",
    confirm_password: "NewPassw0rd2",
  });
  assert.equal(ok.status, 200);

  // الرابط لا يعمل مرة ثانية
  const reuse = await h.call("/api/auth/reset-password", "POST", {
    token,
    password: "Another3pass",
    confirm_password: "Another3pass",
  });
  assert.equal(reuse.status, 400);
  assert.equal(
    (await (await h.call(`/api/auth/reset-password/verify?token=${token}`)).json())
      .valid,
    false,
  );

  // الجلسة القديمة أُلغيت
  assert.equal(
    (await h.call("/api/auth/me", "GET", undefined, oldSession)).status,
    401,
  );
  // كلمة المرور القديمة لا تعمل والجديدة تعمل
  const oldLogin = await h.call("/api/auth/login", "POST", {
    identifier: "changer",
    password: "Passw0rd1",
  });
  assert.equal(oldLogin.status, 401);
  const newLogin = await h.call("/api/auth/login", "POST", {
    identifier: "changer",
    password: "NewPassw0rd2",
  });
  assert.equal(newLogin.status, 200);
});

test("reset password: expired, tampered and superseded links are rejected", async (t) => {
  const mailer = fakeMailer();
  const h = await makeHarness({ mailer });
  t.after(() => h.close());
  await register(h, "expiry");

  await h.call("/api/auth/forgot-password", "POST", {
    email: "expiry@example.test",
  });
  await tick();
  const token = tokenFrom(mailer.sent[0].link);
  h.db.prepare("UPDATE Password_Resets SET ExpiresAt=0").run();
  const expired = await h.call("/api/auth/reset-password", "POST", {
    token,
    password: "NewPassw0rd2",
    confirm_password: "NewPassw0rd2",
  });
  assert.equal(expired.status, 400);

  const tampered = await h.call("/api/auth/reset-password", "POST", {
    token: "f".repeat(64),
    password: "NewPassw0rd2",
    confirm_password: "NewPassw0rd2",
  });
  assert.equal(tampered.status, 400);

  // طلب جديد يلغي الرابط السابق (رابط فعّال واحد فقط)
  h.db.prepare("UPDATE Password_Resets SET CreatedAt=0").run();
  await h.call("/api/auth/forgot-password", "POST", {
    email: "expiry@example.test",
  });
  await tick();
  assert.equal(mailer.sent.length, 2);
  assert.equal(
    h.db
      .prepare("SELECT count(*) n FROM Password_Resets WHERE UsedAt IS NULL")
      .get().n,
    1,
  );
});

test("forgot password is rate limited", async (t) => {
  const mailer = fakeMailer();
  const h = await makeHarness({ mailer });
  t.after(() => h.close());
  const statuses = [];
  for (let i = 0; i < 6; i++)
    statuses.push(
      (
        await h.call("/api/auth/forgot-password", "POST", {
          email: "flood@example.test",
        })
      ).status,
    );
  assert.deepEqual(statuses, [200, 200, 200, 200, 200, 429]);
});
