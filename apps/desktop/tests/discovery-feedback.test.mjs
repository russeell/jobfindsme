import test from 'node:test';import assert from 'node:assert/strict';import http from 'node:http';
import {userError} from '../dist-electron/shared/user-errors.js';import {defaultDiscoveryFilters,hasDiscoveryFilters,normalizeDiscoveryFilters,readSelectedSources,selectedSearchSources,selectedAttemptableSources} from '../dist-electron/shared/discovery-filters.js';import {DesktopApiClient} from '../dist-electron/main/backend/api-client.js';
test('all hidden and visible filters reset to defaults; keyword is outside reset state',()=>{assert(!hasDiscoveryFilters(defaultDiscoveryFilters(),''));for(const field of [{cities:['上海']},{read:'read'},{experience_min_years:0},{employment_type:'contract'},{source_names:['BOSS直聘']}])assert(hasDiscoveryFilters({...defaultDiscoveryFilters(),...field},''));assert(hasDiscoveryFilters(defaultDiscoveryFilters(),'boss'));assert.notEqual(defaultDiscoveryFilters(),defaultDiscoveryFilters());});
test('IPC exceptions and private-looking details never become user-visible raw errors',()=>{for(const raw of ["Error invoking remote method 'desktop:run-source-search': Error: desktop API request failed (500)",'Error stack\n at f (private-file:23) token=private']){const result=userError(raw);assert(!/Error|remote|stack|private|500/.test(result.message));}assert.equal(userError('risk_control:captcha').kind,'risk');assert.equal(userError('login_required').kind,'login');assert.equal(userError('partial').kind,'partial');});
test('source check errors retain a safe concrete reason',()=>{
 assert.match(userError('source_contract_error:验证检索没有返回岗位').message,/岗位列表/);
 assert.match(userError('source_check_timeout:secret-path').message,/超时/);
 assert.match(userError('source_backoff:token=secret').message,/没有重复访问/);
 for(const raw of ['source_contract_error:secret-path','source_check_timeout:secret-path','source_backoff:token=secret'])assert.doesNotMatch(userError(raw).message,/secret|token/);
});
test('chat storage failure identifies a safe cause without showing SQL or local paths',()=>{const result=userError('Error invoking remote method: research_chat_storage:sqlite_busy');assert.equal(result.kind,'service');assert.match(result.message,/数据库繁忙/);assert.match(result.message,/sqlite_busy/);assert(!result.message.includes('remote method'));});
test('real HTTP 500 response maps to short local-service feedback',async()=>{const server=http.createServer((_req,res)=>{res.writeHead(500,{'content-type':'text/plain'});res.end('private traceback');});await new Promise(r=>server.listen(0,'127.0.0.1',r));try{const client=new DesktopApiClient(`http://127.0.0.1:${server.address().port}`,'fixture');await assert.rejects(client.runSourceSearch({workspace_id:'fixture',intent:'AI',source_ids:[]}),e=>{assert.equal(userError(e).kind,'service');assert(!userError(e).message.includes('traceback'));return true;});}finally{server.close();}});

test('interactive filters keep explicit unknown handling without mutating frozen snapshots',()=>{const frozen={unknown_policy:'exclude',salary_mode:'contained',cities:['上海'],read:'unread'};const before=JSON.stringify(frozen);assert.deepEqual(normalizeDiscoveryFilters(frozen),frozen);assert.equal(JSON.stringify(frozen),before);assert(hasDiscoveryFilters({unknown_policy:'only',salary_mode:'contained'}));});
test('explicit source selection never falls back to all and distinguishes availability',()=>{const sources=[{source_id:'liepin',live_search_enabled:true},{source_id:'boss',live_search_enabled:false},{source_id:'zhilian',live_search_enabled:true}];for(const raw of [null,'null','{}','bad','[]'])assert.deepEqual(readSelectedSources(raw),[]);assert.deepEqual(readSelectedSources('["boss","boss","liepin"]'),['boss','liepin']);assert.deepEqual(readSelectedSources('["company_01","liepin","company_16"]'),['liepin']);assert.deepEqual(selectedSearchSources(sources,[]),[]);assert.deepEqual(selectedSearchSources(sources,['boss']),[]);assert.deepEqual(selectedSearchSources(sources,['boss','zhilian']).map(s=>s.source_id),['zhilian']);});
test('an explicitly selected unverified platform can start a bounded search, while risk stays paused',()=>{
 const sources=[{source_id:'liepin',live_search_enabled:true,session_status:'anonymous',list_status:'verified'},
  {source_id:'zhilian',live_search_enabled:false,session_status:'unverified',list_status:'unverified'},
  {source_id:'wuyou',live_search_enabled:false,session_status:'blocked',list_status:'blocked'}];
 assert.deepEqual(selectedSearchSources(sources,['zhilian']).map(s=>s.source_id),[]);
 assert.deepEqual(selectedAttemptableSources(sources,['zhilian']).map(s=>s.source_id),['zhilian']);
 assert.deepEqual(selectedAttemptableSources(sources,['zhilian','wuyou']).map(s=>s.source_id),['zhilian']);
 assert.deepEqual(selectedAttemptableSources(sources,['wuyou']),[]);
});
test('browser load failure is not presented as a backend outage',()=>{
 const result=userError('Error invoking remote method: browser_navigation_failed');
 assert.equal(result.kind,'source');assert.match(result.message,/网页加载失败/);assert.doesNotMatch(result.message,/本地服务|remote/);
});
test('an unreadable JD with an optional login suggestion is not an expired session',()=>{
 const error=userError('没有读取到完整岗位信息，请打开原页确认这是岗位详情，并在需要时登录后重试。');
 assert.equal(error.kind,'source');assert.doesNotMatch(error.message,/重新登录|失效/);
 assert.equal(userError('login_required:登录状态已失效').kind,'login');
});
