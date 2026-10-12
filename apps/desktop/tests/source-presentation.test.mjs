import test from 'node:test';
import assert from 'node:assert/strict';
import {presentSourceStatus,sourceCheckFailureOutcome,sourceStatusRows,mergeSourceChecks} from '../dist-electron/shared/source-presentation.js';

const source={source_id:'sample',source_type:'platform',name:'示例',login_required:false,live_search_enabled:true,session_status:'public',list_status:'verified',detail_status:'verified',fields_status:'verified',pagination_status:'verified',status:'ok',detail:'',last_verified_at:null};
test('source presentation keeps search capability separate from session and check outcome',()=>{
 assert.deepEqual(presentSourceStatus(source),{title:'可检索',detail:'可加入本次搜索范围',action:'use',available:true});
 assert.equal(presentSourceStatus({...source,last_verified_at:'2020-01-01T00:00:00Z'}).available,true);
 assert.equal(presentSourceStatus({...source,login_required:true,session_status:'expired'}).title,'会话待复查');
 assert.equal(presentSourceStatus({...source,live_search_enabled:false,list_status:'partial'}).action,'check');
 assert.equal(presentSourceStatus({...source,login_required:true,session_status:'verified',live_search_enabled:false,list_status:'partial',detail:'当前平台页显示已登录'}).title,'已登录，检索待验');
 assert.equal(presentSourceStatus({...source,login_required:true,session_status:'blocked',list_status:'blocked'}).title,'需要验证');
 assert.equal(presentSourceStatus(source,{outcome:'failed',detail:'本次读取失败'}).title,'检查未通过');
 assert.equal(presentSourceStatus({...source,login_required:true,session_status:'unverified',live_search_enabled:false}, {outcome:'failed',detail:'source_contract_error'}).title,'检查未通过');
 assert.equal(presentSourceStatus({...source,login_required:true,session_status:'unverified',live_search_enabled:false,list_status:'unverified'}).title,'登录状态待确认');
 assert.equal(presentSourceStatus({...source,login_required:true,session_status:'unverified',live_search_enabled:false,list_status:'verified'}).title,'列表可读，登录未确认');
});
test('a list parse error is never presented as login or risk',()=>{
 assert.equal(sourceCheckFailureOutcome('source_contract_error:验证检索没有返回岗位'),'failed');
 assert.equal(sourceCheckFailureOutcome('source_check_timeout:单个平台检查超过 8 秒'),'failed');
 assert.equal(sourceCheckFailureOutcome('login_required:登录页'),'login_required');
 assert.equal(sourceCheckFailureOutcome('risk_control:安全验证'),'risk_control');
});

test('current foreground evidence supersedes an older failed check without claiming search success',()=>{
 const visible={...source,source_id:'zhilian',session_status:'verified',list_status:'partial',fields_status:'verified',live_search_enabled:false,detail:'当前页已标准化读取 2 条岗位',last_verified_at:'2026-09-28T10:00:02Z'};
 const status=presentSourceStatus(visible,{outcome:'failed',detail:'超时',attempted_at:'2026-09-28T10:00:00Z'});
 assert.equal(status.title,'已登录，列表可读');assert.equal(status.available,false);assert.match(status.detail,/2 条/);
});
test('a confirmed login with a failed background search stays distinct from login failure',()=>{
 const result=presentSourceStatus({...source,source_id:'zhilian',session_status:'verified',live_search_enabled:false,list_status:'partial',detail:'后台有界检索未通过：source_timeout [source_stage=extract]'});
 assert.equal(result.title,'已登录，后台检索待修复');assert.equal(result.action,'check');assert.equal(result.available,false);
});

test('available count and source labels use the same current evidence',()=>{
 const liepin={...source,source_id:'liepin'},zhilian={...source,source_id:'zhilian',session_status:'blocked'},wuyou={...source,source_id:'wuyou'};
 const checks=[{source:liepin,outcome:'failed',evidence:'live',attempted_at:'2026-10-11T01:00:00Z',detail:'source_unavailable:503',duration_ms:3}];
 const rows=sourceStatusRows([liepin,zhilian,wuyou],checks);
 assert.deepEqual(rows.map(row=>row.presented.title),['连接失败','需要验证','可检索']);
 assert.equal(rows.filter(row=>row.presented.available).length,1);
 assert.equal(presentSourceStatus(liepin,{...checks[0],detail:'source_check_timeout'}).title,'检查超时');
});
test('current login observation overrides old blocked status; foreground check is an actionable request',()=>{
 const blocked={...source,source_id:'zhilian',session_status:'blocked',list_status:'blocked'};
 assert.equal(presentSourceStatus(blocked,{outcome:'login_required'}).title,'需要登录');
 const result=presentSourceStatus(blocked,{outcome:'failed',detail:'source_visible_page_required:please open'});
 assert.equal(result.title,'需核对登录');assert.equal(result.action,'login');assert.equal(result.available,false);
});
test('individual retry works without bulk audit, skips cannot erase failure, and fresh success recovers',()=>{
 const failed={source,outcome:'failed',evidence:'live',attempted_at:'2026-10-11T01:00:00Z',detail:'source_unavailable:503'};
 const first=mergeSourceChecks([],[failed]);assert.equal(first.length,1);
 for(const outcome of ['cached_recent','skipped_cooldown','cancelled','not_checked_budget']){
  assert.equal(mergeSourceChecks(first,[{...failed,outcome,evidence:'none'}])[0].outcome,'failed');
 }
 const recovered=mergeSourceChecks(first,[{...failed,outcome:'verified_now',attempted_at:'2026-10-11T02:00:00Z'}]);
 assert.equal(sourceStatusRows([source],recovered)[0].presented.available,true);
 assert.equal(first[0].outcome,'failed');
});


test('persisted login failures do not become captcha prompts on reopening settings',()=>{
 assert.equal(presentSourceStatus({...source,login_required:true,session_status:'expired',list_status:'blocked'}).title,'会话待复查');
 assert.equal(presentSourceStatus({...source,login_required:true,session_status:'unverified',list_status:'blocked'}).title,'登录状态待确认');
 assert.equal(presentSourceStatus({...source,session_status:'blocked',list_status:'blocked'}).title,'需要验证');
});


test('failure persistence time cannot hide the login or challenge result that produced it',()=>{
 for(const [session_status,outcome,title] of [['expired','login_required','需要登录'],['blocked','risk_control','需要验证']]){
  const before={...source,source_id:'boss',login_required:true,session_status:'verified',last_verified_at:'2026-10-12T01:00:00Z'};
  const check={source:before,outcome,evidence:'live',attempted_at:'2026-10-12T01:01:00Z'};
  const after={...before,session_status,list_status:'blocked',live_search_enabled:false,last_verified_at:'2026-10-12T01:01:02Z'};
  assert.equal(presentSourceStatus(after,check).title,title);
  const [row]=sourceStatusRows([after],[check]);
  assert.equal(row.checked,check);assert.equal(row.presented.title,title);assert.equal(row.presented.action,'login');
  const recovered={...after,session_status:'verified',list_status:'verified',live_search_enabled:true,last_verified_at:'2026-10-12T01:02:00Z'};
  assert.equal(sourceStatusRows([recovered],[check])[0].checked,undefined);
  assert.equal(presentSourceStatus(recovered,check).available,true);
 }
});
