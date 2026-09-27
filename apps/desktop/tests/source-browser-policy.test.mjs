import assert from "node:assert/strict";
import test from "node:test";

import {
  isPublicWebUrl,
  clampSourceBrowserBounds,
  confirmAllowedNavigationAfterAbort,
  isAllowedSourceUrl,
  isAllowedNavigationAbort,
  resolveSourceBrowserTarget,
  requiresElectronSourceSearch,
  sourceBrowserSpecs,
  sourceBrowserIdForSourceName,
  summarizeSourceVerification,
} from "../dist-electron/shared/source-browser-policy.js";

test("each source has its own persistent partition", () => {
  const partitions = Object.values(sourceBrowserSpecs).map((item) => item.partition);
  assert.equal(new Set(partitions).size, 4);
  assert.ok(partitions.every((item) => item.startsWith("persist:jobfindsme-source-")));
});

test("all supported source labels resolve to their original-page browser", () => {
  assert.equal(sourceBrowserIdForSourceName("BOSS直聘"), "boss");
  assert.equal(sourceBrowserIdForSourceName("猎聘"), "liepin");
  assert.equal(sourceBrowserIdForSourceName("智联招聘"), "zhilian");
  assert.equal(sourceBrowserIdForSourceName("未知来源"), undefined);
});

test("source browser allows only https platform hosts", () => {
  assert.equal(isAllowedSourceUrl("boss", "https://www.zhipin.com/web/user/"), true);
  assert.equal(isAllowedSourceUrl("boss", "https://evil.example/zhipin.com"), false);
  assert.equal(isAllowedSourceUrl("boss", "http://www.zhipin.com/"), false);
  assert.equal(isAllowedSourceUrl("liepin", "https://sub.liepin.com/path"), true);
  assert.equal(isAllowedSourceUrl("liepin", "https://www.liepin.com/job/1.shtml"), true);
  assert.equal(isAllowedSourceUrl("liepin", "https://www.liepin.com.evil.example/job"), false);
});

test("only login-gated platform sources require the Electron search bridge", () => {
  assert.equal(requiresElectronSourceSearch("boss"), true);
  assert.equal(requiresElectronSourceSearch("liepin"), false);
  assert.equal(requiresElectronSourceSearch("liepin"), false);
});

test("an SPA abort is tolerated only for an allowlisted navigation target", () => {
  assert.equal(
    isAllowedNavigationAbort(
      "liepin",
      "https://www.liepin.com/job/123.shtml",
      { code: "ERR_ABORTED" },
    ),
    true,
  );
  assert.equal(
    isAllowedNavigationAbort("liepin", "https://evil.example/", { code: "ERR_ABORTED" }),
    false,
  );
  assert.equal(
    isAllowedNavigationAbort(
      "liepin",
      "https://www.liepin.com/job/123.shtml",
      { code: "ERR_FAILED" },
    ),
    false,
  );
});

test("an allowlisted SPA abort succeeds only after the final page is ready", async () => {
  const states = [
    { url: "", loading: true },
    { url: "https://www.liepin.com/job/123.shtml", loading: true },
    { url: "https://www.liepin.com/job/123.shtml", loading: false },
  ];
  assert.equal(await confirmAllowedNavigationAfterAbort(
    "liepin",
    "https://www.liepin.com/job/123.shtml",
    { code: "ERR_ABORTED" },
    () => states.shift() ?? states.at(-1),
    async () => {},
    3,
  ), true);
});

test("an allowlisted target that never finishes loading remains a failure", async () => {
  assert.equal(await confirmAllowedNavigationAfterAbort(
    "liepin",
    "https://www.liepin.com/job/123.shtml",
    { code: "ERR_ABORTED" },
    () => ({ url: "https://www.liepin.com/job/123.shtml", loading: true }),
    async () => {},
    2,
  ), false);
});

test("source verification enables only evidence-backed bounded results", () => {
  const result = summarizeSourceVerification([
    { records: [{ payload: { title: "Python", company: "Acme", url: "https://www.zhipin.com/job/1", detail_level: "detail_page", description: "x".repeat(80) } }], next_cursor: "2" },
    { records: [{ payload: { title: "Backend", company: "Acme", url: "https://www.zhipin.com/job/2", detail_level: "list_card", description: "Backend" } }], next_cursor: null },
  ]);
  assert.equal(result.enabled, true);
  assert.equal(result.detail_status, "verified");
  assert.equal(result.fields_status, "verified");
  assert.equal(result.pagination_status, "verified");
  const clickOnly=summarizeSourceVerification([{records:[{payload:{title:'Agent工程师',company:'样例公司',url:'https://www.liepin.com/job/1.shtml'}}],next_cursor:'3',collection:{batches:2}}]);
  assert.match(clickOnly.notes,/2 页、1 条/);
  assert.throws(() => summarizeSourceVerification([{ records: [], next_cursor: null }]), /没有返回岗位/);
});

test("browser bounds stay inside the desktop content area", () => {
  assert.deepEqual(
    clampSourceBrowserBounds({ x: 600, y: 180, width: 900, height: 900 }, { width: 1200, height: 800 }),
    { x: 600, y: 180, width: 600, height: 620 },
  );
});

test("job original navigation stays isolated and does not imply an application", () => {
  assert.deepEqual(
    resolveSourceBrowserTarget(
      "liepin",
      "https://www.liepin.com/login/",
      "https://www.liepin.com/job/123.html",
    ),
    { targetUrl: "https://www.liepin.com/job/123.html", shouldLoad: true },
  );
  assert.deepEqual(
    resolveSourceBrowserTarget(
      "liepin",
      "https://www.liepin.com/job/123.html",
      "https://www.liepin.com/job/123.html",
    ),
    { targetUrl: "https://www.liepin.com/job/123.html", shouldLoad: false },
  );
  assert.throws(
    () => resolveSourceBrowserTarget("liepin", "", "https://evil.example/job/123"),
    /allowlist/,
  );
  assert.deepEqual(
    resolveSourceBrowserTarget(
      "liepin",
      "",
      "https://www.liepin.com/job/123.shtml",
    ),
    {
      targetUrl: "https://www.liepin.com/job/123.shtml",
      shouldLoad: true,
    },
  );
});

test("browser layout never expands a small slot over adjacent controls", () => {
  assert.deepEqual(clampSourceBrowserBounds({x:1000,y:700,width:100,height:50},{width:1100,height:750}), {x:1000,y:700,width:100,height:50});
  assert.throws(() => clampSourceBrowserBounds({x:NaN,y:0,width:100,height:100},{width:1100,height:750}), /invalid/);
  for (const url of ["https://user:pass@www.liepin.com/job/1", "https://www.liepin.com:8443/job/1", "https://127.0.0.1/job/1", "https://liepin.com.evil.test/job/1"]) assert.equal(isAllowedSourceUrl("liepin",url),false);
});

test('public browsing accepts independent sites and blocks schemes and loopback forms',()=>{
 for(const url of ['https://ats.example.org/jobs','http://recruit.example.org:8080/','https://login.example.com/sso'])assert.equal(isPublicWebUrl(url),true,url);
 for(const url of ['javascript:alert(1)','file:///etc/passwd','data:text/html,hi','http://127.1/','http://2130706433/','http://localhost:8000/','http://[::1]/','http://192.168.1.2/','https://user:pass@example.com/'])assert.equal(isPublicWebUrl(url),false,url);
});

test('job seeker entry uses the observed official login route in its persistent partition',()=>{
 assert.equal(sourceBrowserSpecs.zhilian.loginUrl,'https://passport.zhaopin.com/login?bkUrl=https%3A%2F%2Fi.zhaopin.com%2Fblank%3Fhttps%3A%2F%2Fwww.zhaopin.com%2Findex%3FvalidateCampus%3D');
 assert.equal(sourceBrowserSpecs.zhilian.partition,'persist:jobfindsme-source-zhilian');
});
