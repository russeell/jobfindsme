import test from 'node:test';
import assert from 'node:assert/strict';
import {executeBoundedSourceSearch} from '../dist-electron/main/sources/source-search-execution.js';

const input={workspace_id:'w1',intent:'Python',source_ids:['zhilian','wuyou'],max_pages:1,time_budget_seconds:10,filters:{},page_size:10};
const preflight={workspace_id:'w1',resume_version_id:null,keywords:['Python'],allowed_source_ids:['zhilian','wuyou'],blocked_sources:{},max_pages:1,time_budget_seconds:10};
const record=id=>({external_id:id,source_name:id,source_url:'https://example.org',payload:{title:'Python 工程师'}});
const response=(sourceId,runId,total,status='success')=>({workspace_id:'w1',resume_version_id:null,keywords:['Python'],allowed_source_ids:[sourceId],blocked_sources:{},max_pages:1,time_budget_seconds:10,jobs:[],source_runs:[{source_id:sourceId,status,pages_fetched:1,elapsed_seconds:0.01,coverage_status:'partial',can_continue:false,next_cursor:null,stop_reason:'page_budget',error:null}],result_page:{run_id:runId,page:1,page_size:10,total,page_count:1,items:[]}});
const manager=()=>({searchPage:async id=>({records:[record(id)],next_cursor:null})});

test('cancelling while preflight waits prevents all source requests and snapshot writes',async()=>{
 let release,started,epoch=0,sourceCalls=0,writes=0;
 const gate=new Promise(resolve=>{release=resolve;});
 const preflightStarted=new Promise(resolve=>{started=resolve;});
 const work=executeBoundedSourceSearch(input,{client:{searchPreflight:async()=>{started();await gate;return preflight;},runSourceSearch:async()=>{writes++;}},manager:{searchPage:async()=>{sourceCalls++;return {records:[],next_cursor:null};}},getCancellationEpoch:()=>epoch});
 await preflightStarted;
 epoch++;release();
 await assert.rejects(work,/cancelled|已停止/);
 assert.equal(sourceCalls,0);assert.equal(writes,0);
});

test('selected unverified source uses the user search once and verifies only after save',async()=>{
 const calls=[];
 const client={searchPreflight:async request=>{calls.push(['preflight',request.attempt_unverified_login]);return {...preflight,allowed_source_ids:['zhilian']};},
  runSourceSearch:async request=>{calls.push(['save',request.attempt_unverified_login]);return {...response('zhilian','run-verify',1),jobs:[{...record('zhilian'),source_id:'zhilian'}]};},
  bootstrap:async()=>({sources:[{source_id:'zhilian',login_required:true,session_status:'unverified'}]}),
  recordSourceVerification:async(id,summary)=>{calls.push(['verify',id,summary.list_status,summary.session_status,summary.enabled]);}};
 await executeBoundedSourceSearch({...input,source_ids:['zhilian']},{client,manager:{searchPage:async()=>{calls.push(['search']);return {records:[record('zhilian')],next_cursor:null};}},getCancellationEpoch:()=>0});
 assert.deepEqual(calls,[['preflight',true],['search'],['save',true],['verify','zhilian','verified','unverified',false]]);
});

test('readable anonymous 51job results never become a verified login',async()=>{
 const statuses=[];
 const client={searchPreflight:async()=>({...preflight,allowed_source_ids:['wuyou']}),
  runSourceSearch:async()=>({...response('wuyou','run-public',1),jobs:[{...record('wuyou'),source_id:'wuyou'}]}),
  bootstrap:async()=>({sources:[{source_id:'wuyou',login_required:true,session_status:'unverified'}]}),
  recordSourceVerification:async(_id,summary)=>{statuses.push(summary);}};
 const result=await executeBoundedSourceSearch({...input,source_ids:['wuyou']},{client,manager:{searchPage:async()=>({records:[{...record('wuyou'),payload:{title:'Python 工程师',company:'示例公司',url:'https://jobs.51job.com/example'}}],next_cursor:null})},getCancellationEpoch:()=>0});
 assert.equal(result.result_page.total,1);assert.equal(statuses[0].list_status,'verified');
 assert.equal(statuses[0].session_status,'unverified');assert.equal(statuses[0].enabled,false);
});

test('a failed batch save does not poison the next valid source',async()=>{
 const writes=[];
 const client={searchPreflight:async()=>preflight,runSourceSearch:async request=>{writes.push(request.source_ids[0]);if(request.source_ids[0]==='zhilian')throw Error('disk full');return response('wuyou','run_b',1);},recordSourceVerification:async()=>{}};
 const result=await executeBoundedSourceSearch(input,{client,manager:manager(),getCancellationEpoch:()=>0});
 assert.deepEqual(writes,['zhilian','wuyou']);
 assert.equal(result.result_page.run_id,'run_b');
 assert.equal(result.source_runs.find(run=>run.source_id==='zhilian')?.status,'failed');
 assert.equal(result.source_runs.find(run=>run.source_id==='wuyou')?.status,'success');
 assert.deepEqual(result.batch_failures.map(item=>[item.source_id,item.stage]),[['zhilian','save']]);
});

test('source status update failure is reported after A was saved and B still saves',async()=>{
 const writes=[],status=[];
 const client={searchPreflight:async()=>({...preflight,max_pages:2}),runSourceSearch:async request=>{const id=request.source_ids[0];writes.push(id);return response(id,'run_a',writes.length,id==='zhilian'?'partial':'success');},recordSourceRuntimeFailure:async id=>{status.push(id);throw Error('status store busy');},recordSourceVerification:async()=>{}};
 const sourceManager={searchPage:async(id,{page})=>{if(id==='zhilian'&&page===2)throw Error('risk_control:verify');return {records:[record(id)],next_cursor:id==='zhilian'?'2':null};}};
 const result=await executeBoundedSourceSearch({...input,max_pages:2},{client,manager:sourceManager,getCancellationEpoch:()=>0});
 assert.deepEqual([...writes].sort(),['wuyou','zhilian']);assert.deepEqual(status,['zhilian']);
 assert.equal(result.result_page.total,2);
 assert.deepEqual(result.batch_failures.map(item=>[item.source_id,item.stage]),[['zhilian','source_status']]);
 assert.equal(result.source_runs.find(run=>run.source_id==='zhilian')?.status,'partial');
 assert.equal(result.source_runs.find(run=>run.source_id==='wuyou')?.status,'success');
});

test('the fast source is saved and emitted before the slow source finishes',async()=>{
 let releaseSlow,notifyFast;const slow=new Promise(resolve=>{releaseSlow=resolve;});
 const fastSeen=new Promise(resolve=>{notifyFast=resolve;});const events=[],writes=[];
 const client={searchPreflight:async()=>preflight,runSourceSearch:async request=>{const id=request.source_ids[0];writes.push(id);return response(id,'run-stream',writes.length);}};
 const work=executeBoundedSourceSearch(input,{client,manager:{searchPage:async id=>{if(id==='wuyou')await slow;return {records:[record(id)],next_cursor:null};}},getCancellationEpoch:()=>0,onProgress:value=>{if(value.response){events.push(value);if(value.source_id==='zhilian')notifyFast();}}});
 await fastSeen;
 assert.deepEqual(writes,['zhilian']);
 assert.equal(events[0].response.result_page.total,1);
 assert.equal(events[0].run_id,'run-stream');
 releaseSlow();const final=await work;
 assert.deepEqual(writes,['zhilian','wuyou']);
 assert.equal(final.result_page.total,2);
 assert.deepEqual(events.map(event=>event.response.result_page.total),[1,2]);
});

test('cancel after a saved fast source retains its batch and skips queued sources',async()=>{
 let epoch=0,notifyFast,releaseSlow;const fastSeen=new Promise(resolve=>{notifyFast=resolve;});const slow=new Promise(resolve=>{releaseSlow=resolve;});
 const seen=[],saved=[];
 const ids=['zhilian','wuyou','boss'];
 const client={searchPreflight:async()=>({...preflight,allowed_source_ids:ids}),runSourceSearch:async request=>{const id=request.source_ids[0];saved.push(id);return response(id,'run-cancel',saved.length);}};
 const work=executeBoundedSourceSearch({...input,source_ids:ids},{client,manager:{searchPage:async id=>{seen.push(id);if(id==='wuyou')await slow;return {records:[record(id)],next_cursor:null};}},getCancellationEpoch:()=>epoch,onProgress:value=>{if(value.response?.source_runs[0]?.source_id==='zhilian')notifyFast();}});
 await fastSeen;epoch++;releaseSlow();
 const final=await work;
 assert.deepEqual(seen,['zhilian','wuyou']);
 assert.ok(saved.includes('zhilian'));
 assert.equal(final.result_page.run_id,'run-cancel');
});

test('one failed source cannot inject old cache into a successful run',async()=>{
 const writes=[];
 const client={searchPreflight:async()=>preflight,runSourceSearch:async request=>{writes.push(request);const id=request.source_ids[0];return response(id,'partial-run',id==='zhilian'?0:1,id==='zhilian'?'failed':'success');}};
 const result=await executeBoundedSourceSearch(input,{client,manager:{searchPage:async id=>{if(id==='zhilian')throw Error('source_contract_error:fixture');return {records:[record(id)],next_cursor:null};}},getCancellationEpoch:()=>0});
 assert.equal(writes.length,2);assert(writes.every(request=>request.allow_cache_fallback===false));assert.equal(result.result_page.total,1);
});

test('all failed sources restore local cache once after collection without repeating website requests',async()=>{
 const writes=[];let reads=0;
 const client={searchPreflight:async()=>preflight,runSourceSearch:async request=>{writes.push(request);if(request.allow_cache_fallback)return {...response('zhilian','cached-run',2,'failed'),cache_fallback_used:true};return response(request.source_ids[0],'cached-run',0,'failed');}};
 const result=await executeBoundedSourceSearch(input,{client,manager:{searchPage:async()=>{reads++;throw Error('source_contract_error:fixture');}},getCancellationEpoch:()=>0});
 assert.equal(reads,2);assert.equal(writes.length,3);assert.deepEqual(writes.at(-1).source_ids,input.source_ids);assert.equal(Object.keys(writes.at(-1).browser_errors).length,2);assert.equal(result.cache_fallback_used,true);assert.equal(result.source_runs.length,2);
});
