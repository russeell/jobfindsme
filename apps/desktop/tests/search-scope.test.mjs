import test from 'node:test';
import assert from 'node:assert/strict';
import {unstartedSourceIds,mergeSearchCoverage,keepVisibleSearchPage,keepSelectedSearchJob,sourceRunNeedsAttention,progressBelongsToRun} from '../dist-electron/shared/search-scope.js';

const response=(id,planned,executed,runs=[])=>({result_page:{run_id:id},source_runs:runs,planned_queries:planned.map(source_id=>({source_id,keyword:'Agent',city:''})),executed_queries:executed.map(source_id=>({source_id,keyword:'Agent',city:''})),blocked_sources:{},source_diagnostics:{sources:{}}});
test('explicit multi-source scope keeps budget-unstarted sources for bounded continuation',()=>{
  const first=response('run-1',['a','b','c','d'],['a','b'],[{source_id:'a',can_continue:true,next_cursor:'2'}]);
  assert.deepEqual(unstartedSourceIds(first),['c','d']);
  const merged=mergeSearchCoverage(first,response('run-1',['c','d'],['c'],[{source_id:'c',can_continue:false,next_cursor:null}]));
  assert.deepEqual(unstartedSourceIds(merged),['d']);
  assert.deepEqual(merged.source_runs.map(run=>run.source_id),['a','c']);
});
test('new run never inherits old continuation or coverage',()=>{
  const old=response('old',['a','b'],['a'],[{source_id:'a',can_continue:true,next_cursor:'2'}]);
  const fresh=response('new',['c'],['c']);
  assert.deepEqual(mergeSearchCoverage(old,fresh),fresh);
});
test('a source unblocked in a later batch loses its stale rejection reason',()=>{
 const old={...response('same',['a'],[],[]),blocked_sources:{b:'需登录',c:'待检查'}};
 const next={...response('same',['b'],['b'],[]),allowed_source_ids:['b']};
 assert.deepEqual(mergeSearchCoverage(old,next).blocked_sources,{c:'待检查'});
});
test('a source blocked after waiting for budget no longer offers endless continuation',()=>{
 const old=response('same',['a','b'],['a']);
 const next={...response('same',[],[]),blocked_sources:{b:'登录已过期'}};
 const merged=mergeSearchCoverage(old,next);
 assert.deepEqual(unstartedSourceIds(merged),[]);
 assert.equal(merged.blocked_sources.b,'登录已过期');
});
test('a later saved batch and final response keep the job being read in the same run',()=>{
 const first={run_id:'run-1',page:1,page_count:1,total:1,items:[{job:{job_id:'a'}}]};
 const later={run_id:'run-1',page:1,page_count:2,total:2,items:[{job:{job_id:'b'}},{job:{job_id:'a'}}]};
 assert.equal(keepSelectedSearchJob(first.items[0],'run-1',later).job.job_id,'a');
 assert.equal(keepVisibleSearchPage(first,later).total,2);
 const pageTwo={...later,page:2,items:[{job:{job_id:'c'}}]};
 assert.deepEqual(keepVisibleSearchPage(pageTwo,{...later,total:3,page_count:3}),{...pageTwo,total:3,page_count:3});
 assert.equal(keepSelectedSearchJob(first.items[0],'old-run',{...later,run_id:'new-run'}).job.job_id,'b');
});
test('normal site pagination stays out of warning status while real failures remain visible',()=>{
 assert.equal(sourceRunNeedsAttention({status:'partial',stop_reason:'page_budget'}),false);
 assert.equal(sourceRunNeedsAttention({status:'partial',stop_reason:'risk_control'}),true);
 assert.equal(sourceRunNeedsAttention({status:'failed',stop_reason:'connector_error'}),true);
});
test('late progress from an older client run cannot replace the visible search',()=>{
 assert.equal(progressBelongsToRun({client_run_id:'old',workspace_id:'w1'},'new','w1'),false);
 assert.equal(progressBelongsToRun({client_run_id:'new',workspace_id:'w2'},'new','w1'),false);
 assert.equal(progressBelongsToRun({client_run_id:'new',workspace_id:'w1'},'new','w1'),true);
});
