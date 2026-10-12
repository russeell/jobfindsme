import {test} from 'node:test';
import assert from 'node:assert/strict';
import {loadGreetingContext,validGreetingTarget} from '../dist-electron/main/research/greeting-context.js';
const target={workspaceId:'workspace',jobId:'job',resumeVersionId:'selected'};
test('greeting reads the explicitly selected version and bounded saved JD without changing materials',async()=>{
 const calls=[];
 const api={getJobPreparation:async(...args)=>{calls.push(['job',...args]);return {job:{title:'Agent工程师',company:'示例公司',description:'长'.repeat(4500)}};},agentResume:async(...args)=>{calls.push(['resume',...args]);return {text:'脱敏'.repeat(3500)};}};
 const context=await loadGreetingContext(api,target);
 assert.deepEqual(calls,[['job','workspace','job'],['resume','workspace',undefined,'selected']]);
 assert.equal(context.description.length,4000);assert.equal(context.resume.length,6000);
});
test('no selected resume never silently falls back to the current resume',async()=>{
 const context=await loadGreetingContext({getJobPreparation:async()=>({job:{title:'Agent工程师',company:'示例公司',description:''}}),agentResume:async()=>{throw Error('must not load');}},{...target,resumeVersionId:null});
 assert.equal(context.resume,'');
});
test('invalid selections fail closed rather than using unrelated material',async()=>{
 assert.ok(validGreetingTarget(target));assert.ok(validGreetingTarget({...target,resumeVersionId:null}));
 for(const value of [null,{}, {...target,workspaceId:''},{...target,resumeVersionId:3},{...target,jobId:'x'.repeat(201)}])assert.equal(validGreetingTarget(value),false);
 await assert.rejects(loadGreetingContext({getJobPreparation:async()=>({job:{title:'Agent工程师',company:'示例公司',description:''}}),agentResume:async()=>{throw Error('resume not found');}},target),/resume not found/);
});
