import test from 'node:test';
import assert from 'node:assert/strict';
import {presentSourceStatus} from '../dist-electron/shared/source-presentation.js';

const source={source_id:'sample',source_type:'platform',name:'示例',login_required:false,live_search_enabled:true,session_status:'public',list_status:'verified',detail_status:'verified',fields_status:'verified',pagination_status:'verified',status:'ok',detail:'',last_verified_at:null};
test('source presentation keeps search capability separate from session and check outcome',()=>{
 assert.deepEqual(presentSourceStatus(source),{title:'可检索',detail:'可加入本次搜索范围',action:'use',available:true});
 assert.equal(presentSourceStatus({...source,last_verified_at:'2020-01-01T00:00:00Z'}).available,true);
 assert.equal(presentSourceStatus({...source,login_required:true,session_status:'expired'}).title,'会话待复查');
 assert.equal(presentSourceStatus({...source,live_search_enabled:false,list_status:'partial'}).action,'check');
 assert.equal(presentSourceStatus({...source,login_required:true,session_status:'verified',live_search_enabled:false,list_status:'partial',detail:'当前平台页显示已登录'}).title,'已登录，检索待验');
 assert.equal(presentSourceStatus({...source,login_required:true,session_status:'blocked',list_status:'blocked'}).title,'平台验证中');
 assert.equal(presentSourceStatus(source,{outcome:'failed',detail:'本次读取失败'}).title,'本次未确认');
 assert.equal(presentSourceStatus({...source,login_required:true,session_status:'unverified',live_search_enabled:false}, {outcome:'failed',detail:'source_contract_error'}).title,'本次未确认');
 assert.equal(presentSourceStatus({...source,login_required:true,session_status:'unverified',live_search_enabled:false}).title,'登录状态待确认');
});
