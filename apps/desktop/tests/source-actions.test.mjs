import assert from "node:assert/strict";
import test from "node:test";

import {
  buildSourceSearchUrl,
  sanitizeSourceActionPage,
  sourceListExtractionScript, passiveSourceObservationScript,
} from "../dist-electron/main/source-actions.js";

test("browser source actions build only fixed allowlisted search targets", () => {
  const boss = new URL(buildSourceSearchUrl("boss", "AI 工程师", "上海", 1));
  assert.equal(boss.hostname, "www.zhipin.com");
  assert.equal(boss.searchParams.get("query"), "AI 工程师");
  assert.equal(boss.searchParams.get("city"), "101020100");
  assert.equal(boss.searchParams.has("page"), false);
  assert.throws(()=>buildSourceSearchUrl("boss","AI","上海",2),/scroll/);
  assert.throws(() => buildSourceSearchUrl("boss", "", "上海", 1), /keyword/);
  assert.throws(() => buildSourceSearchUrl("boss", "AI", "上海", 21), /page/);
  assert.match(sourceListExtractionScript("zhilian"), /joblist/);
});

test("browser source results reject cross-origin URLs and bound fields", () => {
  const page = sanitizeSourceActionPage(
    "boss",
    "https://www.zhipin.com/web/geek/job?query=AI",
    1,
    {
      hasNext: true,
      jobs: [
        {
          title: "AI 工程师",
          company: "示例公司",
          location: "上海",
          salary: "20-30K",
          url: "https://www.zhipin.com/job_detail/abc.html",
        },
        {
          title: "恶意结果",
          company: "伪造",
          location: "",
          salary: "",
          url: "https://evil.example/job/1",
        },
      ],
    },
    new Map([["https://www.zhipin.com/job_detail/abc.html", "岗位职责与任职要求".repeat(20)]]),
  );
  assert.equal(page.records.length, 1);
  assert.equal(page.records[0].payload.detail_level, "detail_page");
  assert.equal(page.next_cursor, "2");
});

test('named cities are never sent as opaque platform city codes',()=>{
 for(const id of ['zhilian','wuyou']){
 const url=new URL(buildSourceSearchUrl(id,'工程师','上海',1));
 assert.equal(url.searchParams.has(id==='zhilian'?'jl':'jobArea'),false);
 }
});


test('passive source observation separates splash, login form, and readable list without searches',async()=>{
 const {runInNewContext}=await import('node:vm');
 const script=passiveSourceObservationScript('zhilian');
 function observe(text,inputs,cards){return runInNewContext(script,{location:{href:'https://www.zhaopin.com/',hostname:'www.zhaopin.com'},document:{body:{innerText:text},querySelectorAll(selector){return Array.from({length:selector.startsWith('input')?inputs:cards},()=>({}));}}});}
 assert.equal(observe('找风口工作，就上智联招聘',0,0).kind,'splash');
 assert.equal(observe('求职者登录',2,0).kind,'login');
 assert.equal(observe('搜索岗位',0,3).kind,'list');
});
