import assert from "node:assert/strict";
import test from "node:test";
import {runSourceCheckQueue} from "../dist-electron/main/sources/source-check-queue.js";

const source=(id,changes={})=>({source_id:id,source_type:id.startsWith("company_")?"company":"platform",name:id,
  login_required:["boss","zhilian","wuyou"].includes(id),live_search_enabled:false,session_status:"unverified",
  list_status:"unverified",detail_status:"unverified",fields_status:"unverified",pagination_status:"unverified",
  status:"unverified",detail:"",last_verified_at:null,...changes});
const catalog=["boss","liepin","zhilian","wuyou"].map(source);

test("all four platforms enter the queue; only eligible sources call the live adapter",async()=>{
  const calls=[],progress=[],selected=["liepin"];
  const before=structuredClone(catalog);
  const results=await runSourceCheckQueue({sources:catalog,signal:new AbortController().signal,
    probe:async item=>{calls.push(item.source_id);return {...item,live_search_enabled:true,list_status:"verified",last_verified_at:new Date().toISOString()};},
    onProgress:(item,done,total)=>progress.push([item.source.source_id,done,total]),totalMs:10000});
  assert.equal(results.length,4);
  assert.equal(calls.length,1);
  assert.deepEqual(results.filter(item=>item.outcome==="login_required").map(item=>item.source.source_id),["boss","zhilian","wuyou"]);
  assert.equal(results.filter(item=>item.outcome==="verified_now").length,1);
  assert.deepEqual(progress.at(-1),["wuyou",4,4]);
  assert.deepEqual(catalog,before);
  assert.deepEqual(selected,["liepin"]);
});

test("recent cache and risk control do not retry a source or claim a fresh pass",async()=>{
  const calls=[];
  const recent=source("liepin",{live_search_enabled:true,list_status:"verified",last_verified_at:new Date().toISOString()});
  const results=await runSourceCheckQueue({sources:[recent,source("sample_1"),source("sample_2")],signal:new AbortController().signal,
    probe:async item=>{calls.push(item.source_id);if(item.source_id==="sample_1")throw Error("risk_control:验证码");return item;}});
  assert.deepEqual(calls,["sample_1","sample_2"]);
  assert.deepEqual(results.map(item=>item.outcome),["cached_recent","risk_control","verified_now"]);
  assert.equal(results[0].evidence,"cache");
  assert.equal(results[0].attempted_at,null);
});

test("cancel stops the active check and marks every unvisited source",async()=>{
  const controller=new AbortController();let calls=0;
  const results=await runSourceCheckQueue({sources:[source("liepin"),source("sample_1"),source("sample_2")],signal:controller.signal,
    probe:async()=>{calls++;controller.abort();return new Promise(()=>{});}});
  assert.equal(calls,1);
  assert.deepEqual(results.map(item=>item.outcome),["cancelled","cancelled","cancelled"]);
  assert.equal(results[2].attempted_at,null);
});

test("source timeout leaves a partial result and never starts the next network check",async()=>{
  let calls=0;
  const results=await runSourceCheckQueue({sources:[source("liepin"),source("sample_1")],signal:new AbortController().signal,
    perSourceMs:20,totalMs:1000,probe:async()=>{calls++;return new Promise(()=>{});}});
  assert.equal(calls,1);
  assert.deepEqual(results.map(item=>item.outcome),["failed","not_checked_budget"]);
});

test("total budget marks unvisited sources without probing them",async()=>{
  let clock=0,calls=0;
  const results=await runSourceCheckQueue({sources:[source("liepin"),source("sample_1"),source("sample_2")],signal:new AbortController().signal,
    now:()=>clock,totalMs:10,probe:async item=>{calls++;clock+=11;return item;}});
  assert.equal(calls,1);
  assert.deepEqual(results.map(item=>item.outcome),["verified_now","not_checked_budget","not_checked_budget"]);
});

test("QA probe cap checks one eligible source while reporting the rest",async()=>{
  let calls=0;
  const results=await runSourceCheckQueue({sources:catalog,signal:new AbortController().signal,maxLiveProbes:1,
    probe:async item=>{calls++;return item;}});
  assert.equal(calls,1);
  assert.equal(results.length,4);
  assert.equal(results[1].outcome,"verified_now");
  assert.equal(results.filter(item=>item.outcome==="not_checked_budget").length,0);
});

test("explicit all-source check probes an old unverified login state while retaining risk pause",async()=>{
  const calls=[];
  const results=await runSourceCheckQueue({sources:[source("zhilian"),source("wuyou",{session_status:"blocked",list_status:"blocked"})],
    signal:new AbortController().signal,probeUnverifiedLogin:true,probe:async item=>{calls.push(item.source_id);throw Error("login_required:session expired");}});
  assert.deepEqual(calls,["zhilian"]);
  assert.deepEqual(results.map(item=>item.outcome),["login_required","skipped_cooldown"]);
  assert.deepEqual(results.map(item=>item.evidence),["live","history"]);
});
