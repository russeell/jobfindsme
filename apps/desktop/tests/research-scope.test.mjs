import {test} from "node:test";
import assert from "node:assert/strict";
import {researchScopeFromQuestion} from "../dist-electron/shared/research-scope.js";

test("明确公司问题提取研究对象，含糊对象保持未指定",()=>{
  assert.equal(researchScopeFromQuestion("研究合成科技的经营及福利").company,"合成科技");
  assert.equal(researchScopeFromQuestion("合成科技怎么样？").company,"合成科技");
  assert.equal(researchScopeFromQuestion("公司：合成科技，岗位：AI 工程师；福利如何？").company,"合成科技");
  assert.equal(researchScopeFromQuestion("公司：合成科技，岗位：AI 工程师；福利如何？").title,"AI 工程师");
  assert.equal(researchScopeFromQuestion("研究某公司经营及福利").company,undefined);
  assert.equal(researchScopeFromQuestion("这家公司福利如何？").company,undefined);
  assert.equal(researchScopeFromQuestion("研究清华大学的 AI 工程师岗位").company,"清华大学");
  assert.equal(researchScopeFromQuestion("研究合成科技AI工程师岗位").company,undefined);
});
