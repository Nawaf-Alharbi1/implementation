const { test } = require("node:test");
const assert = require("node:assert/strict");
const { makeHarness, register, recommendation } = require("./helpers");

test("history numbers each customer's requests from 1, independent of other customers", async (t) => {
  const h = await makeHarness();
  t.after(() => h.close());
  const first = await register(h, "firstuser");
  const second = await register(h, "seconduser");

  // المستخدم الأول: طلبان، ثم المستخدم الثاني: طلبان، ثم طلب ثالث للأول (تداخل)
  const send = async (cookie) =>
    (await (await h.call("/api/recommend", "POST", recommendation, cookie)).json())
      .request_id;
  const a1 = await send(first.cookie);
  const a2 = await send(first.cookie);
  const b1 = await send(second.cookie);
  const b2 = await send(second.cookie);
  const a3 = await send(first.cookie);
  assert.deepEqual([a1, a2, b1, b2, a3], [1, 2, 3, 4, 5]); // الأرقام الداخلية عامة

  const list = async (cookie, q = "") =>
    (await (await h.call(`/api/history${q}`, "GET", undefined, cookie)).json())
      .items;

  const secondItems = await list(second.cookie);
  assert.deepEqual(
    secondItems.map((x) => x.UserSeq),
    [2, 1],
    "second user's first two requests must be #1 and #2, not #3 and #4",
  );
  assert.deepEqual(
    secondItems.map((x) => x.RequestId),
    [b2, b1],
  );
  const firstItems = await list(first.cookie);
  assert.deepEqual(
    firstItems.map((x) => x.UserSeq),
    [3, 2, 1],
  );

  // الترقيم صحيح أيضاً في الصفحة الثانية
  const page2 = await list(first.cookie, "?page=2&pageSize=2");
  assert.deepEqual(
    page2.map((x) => x.UserSeq),
    [1],
  );

  // صفحة التفاصيل تعرض نفس الرقم الخاص بالعميل
  const detail = await (
    await h.call(`/api/history/${b2}`, "GET", undefined, second.cookie)
  ).json();
  assert.equal(detail.request.UserSeq, 2);
});
