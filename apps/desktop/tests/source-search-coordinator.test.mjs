import test from 'node:test';
import assert from 'node:assert/strict';
import {collectBrowserSourcePages} from '../dist-electron/main/sources/source-search-coordinator.js';

test('first valid page remains when second Electron source page fails',async()=>{
 let calls=0;const record={external_id:'one',source_name:'智联招聘',source_url:'https://www.zhaopin.com/',payload:{title:'Python',company:'样例',description:'Python',url:'https://www.zhaopin.com/job/one'}};
 const manager={searchPage:async()=>{calls++;if(calls===1)return {records:[record],next_cursor:'2'};throw Error('risk_control:verification required');}};
 const failures=[];const client={recordSourceRuntimeFailure:async(...args)=>failures.push(args)};
 const result=await collectBrowserSourcePages({source_ids:['zhilian'],workspace_id:'w1',intent:'Python'}, {allowed_source_ids:['zhilian'],keywords:['Python'],max_pages:3,time_budget_seconds:10}, {client,manager,isCancelled:()=>false});
 assert.equal(calls,2);assert.equal(result.pages.zhilian.length,1);assert.equal(result.pages.zhilian[0].records[0].external_id,'one');
 assert.match(result.errors.zhilian,/risk_control/);assert.equal(failures.length,0);
});

test('fast source is committed while the second source is still loading',async()=>{
 let releaseSlow;const slow=new Promise(resolve=>{releaseSlow=resolve;});
 const committed=[];let cursorSeen;
 const manager={searchPage:async(sourceId,input)=>{
   if(sourceId==='wuyou')await slow;
   if(sourceId==='zhilian')cursorSeen=input.page;
   return {records:[{external_id:sourceId,source_name:sourceId,source_url:'https://example.com',payload:{title:'Python'}}],next_cursor:null};
 }};
 const run=collectBrowserSourcePages({source_ids:['zhilian','wuyou'],workspace_id:'w1',intent:'Python',source_cursor:'3'},
   {allowed_source_ids:['zhilian','wuyou'],keywords:['Python'],max_pages:1,time_budget_seconds:10},
   {client:{},manager,isCancelled:()=>false,onSourceCompleted:async id=>{committed.push(id);}});
 await new Promise(resolve=>setTimeout(resolve,15));
 assert.deepEqual(committed,['zhilian']);
 assert.equal(cursorSeen,3);
 releaseSlow();await run;
 assert.deepEqual(committed,['zhilian','wuyou']);
});

test('Alibaba uses its existing browser collector without a known unsupported local adapter call',async()=>{
 let publicCalls=0,careerCalls=0;
 const result=await collectBrowserSourcePages({source_ids:['company_03'],workspace_id:'w1',intent:'AI Infra'},
   {allowed_source_ids:['company_03'],keywords:['AI Infra'],max_pages:1,time_budget_seconds:10},
   {client:{publicSourcePages:async()=>{publicCalls++;throw Error('no_public_adapter');}},
    manager:{collectCareer:async()=>{careerCalls++;return {records:[],next_cursor:null};}},isCancelled:()=>false});
 assert.equal(publicCalls,0);assert.equal(careerCalls,1);assert.equal(result.pages.company_03.length,1);
});

test('a failed public continuation never falls back to a first-page browser search',async()=>{
 let browserCalls=0;
 const result=await collectBrowserSourcePages({source_ids:['liepin'],workspace_id:'w1',intent:'Python',source_cursor:'2'},
   {allowed_source_ids:['liepin'],keywords:['Python'],max_pages:1,time_budget_seconds:10},
   {client:{publicSourcePages:async()=>{throw Error('source_timeout:public page');}},manager:{collectCareer:async()=>{browserCalls++;return {records:[],next_cursor:null};}},isCancelled:()=>false});
 assert.equal(browserCalls,0);
 assert.match(result.errors.liepin,/source_timeout|unsupported_cursor/);
 assert.equal(result.pages.liepin,undefined);
});

test('Alibaba passes an observed page cursor to its browser collector',async()=>{
 let pageSeen=0;
 const result=await collectBrowserSourcePages({source_ids:['company_03'],workspace_id:'w1',intent:'Agent',source_cursor:'2'},
   {allowed_source_ids:['company_03'],keywords:['Agent'],max_pages:1,time_budget_seconds:10},
   {client:{},manager:{collectCareer:async(_source,input)=>{pageSeen=input.page;return {records:[],next_cursor:'3'};}},isCancelled:()=>false});
 assert.equal(pageSeen,2);
 assert.equal(result.pages.company_03[0].next_cursor,'3');
});

test('other browser-only sources reject a continuation cursor they cannot honor',async()=>{
 let browserCalls=0;
 const result=await collectBrowserSourcePages({source_ids:['company_04'],workspace_id:'w1',intent:'Python',source_cursor:'2'},
   {allowed_source_ids:['company_04'],keywords:['Python'],max_pages:1,time_budget_seconds:10},
   {client:{},manager:{collectCareer:async()=>{browserCalls++;return {records:[],next_cursor:null};}},isCancelled:()=>false});
 assert.equal(browserCalls,0);
 assert.match(result.errors.company_04,/unsupported_cursor/);
});

test('four explicitly selected sources retain budget-unstarted identities after two slow readers',async()=>{
 const ids=['company_04','company_05','company_06','company_07'],seen=[];
 const result=await collectBrowserSourcePages({source_ids:ids,workspace_id:'w1',intent:'Agent'},
   {allowed_source_ids:ids,keywords:['Agent'],max_pages:1,time_budget_seconds:.15},
   {client:{},manager:{collectCareer:async id=>{seen.push(id);await new Promise(resolve=>setTimeout(resolve,250));return {records:[],next_cursor:null};}},isCancelled:()=>false});
 assert.deepEqual(seen,ids.slice(0,2));
 assert.deepEqual(ids.slice(2).map(id=>result.errors[id]),['time_budget:本次总时间预算已用完','time_budget:本次总时间预算已用完']);
 assert.deepEqual(Object.keys(result.diagnostics.sources).sort(),[...ids].sort());
});
