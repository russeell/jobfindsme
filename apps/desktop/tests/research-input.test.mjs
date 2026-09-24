import {test} from "node:test";
import assert from "node:assert/strict";
import {splitResearchInput} from "../dist-electron/shared/research-input.js";

test("岗位链接与自然语言问题分离，保留后续追问",()=>{
  assert.deepEqual(splitResearchInput("https://www.zhipin.com/job_detail/abc.html 这个岗位加班有依据吗？"),{url:"https://www.zhipin.com/job_detail/abc.html",question:"这个岗位加班有依据吗？"});
  assert.deepEqual(splitResearchInput("这个团队如何？ https://www.zhipin.com/job_detail/abc.html。"),{url:"https://www.zhipin.com/job_detail/abc.html",question:"这个团队如何？"});
  assert.deepEqual(splitResearchInput("团队如何？"),{question:"团队如何？"});
});

test("模糊和多个链接不允许落到当前岗位研究",()=>{
  assert.match(splitResearchInput("www.zhipin.com/job_detail/abc.html").error,/https:\/\//);
  assert.match(splitResearchInput("zhipin.com/job_detail/abc.html 这个岗位如何？").error,/https:\/\//);
  assert.match(splitResearchInput("https://a.example/job https://b.example/job").error,/一个岗位链接/);
});
