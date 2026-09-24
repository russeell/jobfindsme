import {test} from "node:test";
import assert from "node:assert/strict";
import {researchTopicsForQuestion} from "../dist-electron/shared/research-intent.js";

test("自由提问按对象和意图选择范围，已有岗位空问包含公司与岗位",()=>{
  assert.deepEqual(researchTopicsForQuestion("",true,false),["company","job"]);
  assert.deepEqual(researchTopicsForQuestion("公司的经营和福利如何？",true,false),["company"]);
  assert.deepEqual(researchTopicsForQuestion("岗位职责和发展如何？",true,false),["company","job"]);
  assert.deepEqual(researchTopicsForQuestion("经营和福利如何？",false,false),["company"]);
  assert.deepEqual(researchTopicsForQuestion("AI 工程师岗位职责如何？",false,true),["company","job"]);
});
