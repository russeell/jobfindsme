import test from 'node:test';
import assert from 'node:assert/strict';
import {collectBrowserSourcePages} from '../dist-electron/main/sources/source-search-coordinator.js';

test('first valid page remains when second Electron source page fails',async()=>{
 let calls=0;const record={external_id:'one',source_name:'智联招聘',source_url:'https://www.zhaopin.com/',payload:{title:'Python',company:'样例',description:'Python',url:'https://www.zhaopin.com/job/one'}};
 const manager={searchPage:async()=>{calls++;if(calls===1)return {records:[record],next_cursor:'2'};throw Error('risk_control:verification required');}};
 const failures=[];const client={recordSourceRuntimeFailure:async(...args)=>failures.push(args)};
 const result=await collectBrowserSourcePages({source_ids:['zhilian'],workspace_id:'w1',intent:'Python'}, {allowed_source_ids:['zhilian'],keywords:['Python'],max_pages:3,time_budget_seconds:10}, {client,manager,isCancelled:()=>false});
 assert.equal(calls,2);assert.equal(result.pages.zhilian.length,1);assert.equal(result.pages.zhilian[0].records[0].external_id,'one');
 assert.match(result.errors.zhilian,/risk_control/);assert.deepEqual(failures[0].slice(0,2),['zhilian','risk_control']);
});
