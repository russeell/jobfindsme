import test from 'node:test';
import assert from 'node:assert/strict';
import {ResearchRunController} from '../dist-electron/main/research/run-controller.js';
const input=(runId,sessionId=runId)=>({runId,sessionId,workspaceId:'workspace'});
test('parallel sessions isolate cancellation and reject duplicate work within a session',()=>{
 const runs=new ResearchRunController();const a=runs.begin(input('a'),90000),b=runs.begin(input('b'),90000);
 try{
  assert.throws(()=>runs.begin(input('duplicate','a'),90000),/正在生成/);
  assert.equal(runs.cancel('wrong'),false);runs.cancel('a');assert.equal(a.signal.aborted,true);assert.equal(b.signal.aborted,false);
  const retry=runs.begin(input('a'),90000);runs.finish(a);assert.equal(runs.has(retry),true);
  runs.finish(b);assert.equal(runs.has(retry),true);runs.finish(retry);assert.equal(runs.current,undefined);
 }finally{runs.cancelCurrent();}
});
test('finite concurrency and shutdown abort every independent run',()=>{
 const runs=new ResearchRunController();const active=Array.from({length:4},(_,i)=>runs.begin(input(String(i)),90000));
 assert.throws(()=>runs.begin(input('fifth'),90000),/chat_concurrency_limit/);
 assert.equal(runs.cancelCurrent(),true);assert(active.every(run=>run.signal.aborted));assert.equal(runs.current,undefined);assert.equal(runs.cancelCurrent(),false);
});
test('one timeout never aborts a different session',async()=>{
 const runs=new ResearchRunController();const a=runs.begin(input('short'),5),b=runs.begin(input('long'),90000);
 try{await new Promise(resolve=>setTimeout(resolve,20));assert.equal(a.signal.aborted,true);assert.equal(a.signal.reason,"timeout");assert.equal(b.signal.aborted,false);assert.equal(runs.has(b),true);}finally{runs.cancelCurrent();}
});
