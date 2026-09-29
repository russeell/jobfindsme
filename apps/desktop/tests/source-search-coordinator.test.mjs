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

test('a failed public continuation never falls back to a first-page browser search',async()=>{
 let browserCalls=0;
 const result=await collectBrowserSourcePages({source_ids:['liepin'],workspace_id:'w1',intent:'Python',source_cursor:'2'},
   {allowed_source_ids:['liepin'],keywords:['Python'],max_pages:1,time_budget_seconds:10},
   {client:{publicSourcePages:async()=>{throw Error('source_timeout:public page');}},manager:{collectCareer:async()=>{browserCalls++;return {records:[],next_cursor:null};}},isCancelled:()=>false});
 assert.equal(browserCalls,0);
 assert.match(result.errors.liepin,/source_timeout|unsupported_cursor/);
 assert.equal(result.pages.liepin,undefined);
});

test('four explicitly selected sources start together even with a short budget',async()=>{
 const ids=['boss','liepin','zhilian','wuyou'],seen=[];
 const result=await collectBrowserSourcePages({source_ids:ids,workspace_id:'w1',intent:'Agent'},
   {allowed_source_ids:ids,keywords:['Agent'],max_pages:1,time_budget_seconds:.15},
   {manager:{boss:{collect:async()=>{seen.push("boss");await new Promise(resolve=>setTimeout(resolve,250));return {records:[],next_cursor:null};}},searchPage:async id=>{seen.push(id);await new Promise(resolve=>setTimeout(resolve,250));return {records:[],next_cursor:null};}},client:{publicSourcePages:async id=>{seen.push(id);await new Promise(resolve=>setTimeout(resolve,250));return [{records:[],next_cursor:null}];}},isCancelled:()=>false});
 assert.deepEqual(seen,ids);
 assert.deepEqual(result.errors,{});
 assert.deepEqual(Object.keys(result.diagnostics.sources).sort(),[...ids].sort());
});

test('selected platforms use their own continuation cursor while a newly selected platform starts once',async()=>{
 const seen={};
 await collectBrowserSourcePages({source_ids:['boss','liepin','zhilian','wuyou'],workspace_id:'w',intent:'Java',source_cursors:{boss:'boss-next',liepin:'2',zhilian:'3'}},
  {allowed_source_ids:['boss','liepin','zhilian','wuyou'],keywords:['Java'],max_pages:1,time_budget_seconds:10},
  {isCancelled:()=>false,client:{publicSourcePages:async(id,input)=>{seen[id]=input.cursor;return [{records:[],next_cursor:null}];}},manager:{boss:{collect:async input=>{seen.boss=input.cursor;return {records:[],next_cursor:null};}},searchPage:async(id,input)=>{seen[id]=input.page;return {records:[],next_cursor:null};}}});
 assert.deepEqual(seen,{boss:'boss-next',liepin:'2',zhilian:3,wuyou:1});
});

test('same platform pages stay sequential while four sources start independently',async()=>{
 const active=new Set(),starts=[];let overlap=false;
 const page=async(id,input)=>{if(active.has(id))overlap=true;active.add(id);starts.push([id,input.page]);await new Promise(r=>setTimeout(r,8));active.delete(id);return {records:[],next_cursor:input.page===1?'2':null};};
 await collectBrowserSourcePages({workspace_id:'w',intent:'Agent',source_ids:['boss','liepin','zhilian','wuyou']},{allowed_source_ids:['boss','liepin','zhilian','wuyou'],keywords:['Agent'],max_pages:2,time_budget_seconds:5},{client:{publicSourcePages:async()=>[]},manager:{boss:{collect:async()=>({records:[],next_cursor:null})},searchPage:page},isCancelled:()=>false});
 assert.equal(overlap,false);assert.deepEqual(starts.filter(([id])=>id==='zhilian').map(([,p])=>p),[1,2]);assert.deepEqual(starts.filter(([id])=>id==='wuyou').map(([,p])=>p),[1,2]);
});
