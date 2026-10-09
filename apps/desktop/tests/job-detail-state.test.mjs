import test from 'node:test';
import assert from 'node:assert/strict';
import {jobDetailKey,mergeJobDetail} from '../dist-electron/shared/job-detail-state.js';

const row=(id='a')=>({job:{job_id:id,apply_url:`https://jobs.example/${id}`,title:'AI Agent',company:'Example',description:'摘要',locations:[],source:{source_name:'猎聘',detail_level:'list'}},tracking:{saved:false,read:false},query_relevance:{score:100},information_coverage:{ratio:0.5},score:80,components:{skills:80}});
const detail={title:'AI Agent Engineer',company:'Example',description:'完整岗位原文',url:'https://jobs.example/a',fetched_at:'2026-10-10'};

test('JD completing after a favorite/read update retains the latest tracking state',async()=>{
  let release;
  const pending=new Promise(resolve=>{release=resolve;});
  const requested=row();
  let current={...requested,tracking:{saved:true,read:true}};
  const completion=pending.then(value=>{current=mergeJobDetail(current,requested.job,value);});
  release(detail);await completion;
  assert.deepEqual(current.tracking,{saved:true,read:true});
  assert.equal(current.job.description,detail.description);
  assert.equal(current.job.source.detail_level,'detail_page');
  assert.equal(current.query_relevance,undefined);
  assert.equal(current.information_coverage,undefined);
  assert.equal(current.score,null);
  assert.equal(current.score_basis_outdated,true);
});

test('late response for A cannot change selected B or a replaced source URL',()=>{
  const selected=row('b');
  assert.equal(mergeJobDetail(selected,row().job,detail),selected);
  const replaced=row();replaced.job.apply_url='https://jobs.example/new';
  assert.equal(mergeJobDetail(replaced,row().job,detail),replaced);
  const current=row();
  assert.equal(mergeJobDetail(current,current.job,{...detail,job:row('b').job}),current);
});

test('detail scope separates workspaces and sources, while enriched fields use persisted job',()=>{
  const current=row();
  assert.notEqual(jobDetailKey('one',current.job),jobDetailKey('two',current.job));
  assert.notEqual(jobDetailKey('one',current.job),jobDetailKey('one',{...current.job,source:{source_name:'智联招聘'}}));
  const job={...current.job,description:'已保存完整JD',source:{...current.job.source,detail_level:'detail_page'}};
  assert.deepEqual(mergeJobDetail(current,current.job,{...detail,job}).job,job);
});
