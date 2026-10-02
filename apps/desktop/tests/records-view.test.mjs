import test from 'node:test';
import assert from 'node:assert/strict';
import {followsRecord,matchesRecordFilter,selectRecords} from '../dist-electron/shared/records-view.js';
const row=(id,tracking={},preparation)=>({job:{job_id:id,title:'Python 工程师',company:'示例公司',locations:['上海'],source:{source_name:'测试来源',fetched_at:'2026-10-01T08:00:00Z'}},tracking:{read:true,saved:false,applied:false,...tracking},preparation});

test('following excludes casual browsing and closed opportunities without losing history',()=>{
 const browsed=row('read'),saved=row('saved',{saved:true}),applied=row('applied',{applied:true});
 const prepared=row('prepared',{}, {stage:'considering'}),closed=row('closed',{saved:true,applied:true},{stage:'closed'});
 const items=[browsed,saved,applied,prepared,closed];
 assert.deepEqual(selectRecords(items,'following','','','recent').map(item=>item.job.job_id),['saved','applied','prepared']);
 assert.equal(selectRecords(items,'all','','','recent').length,5);
 assert.equal(matchesRecordFilter(closed,'all'),true);
 assert.equal(followsRecord(closed),false);
 assert.deepEqual(selectRecords(items,'all','','applied','recent').map(item=>item.job.job_id),['applied']);
});
test('local filtering finds companies and cities across the entire list, including later pages',()=>{
 const items=Array.from({length:47},(_,i)=>row(String(i)));
 items[46].job.company='目标示例';items[46].job.title='AI Agent 工程师';items[46].job.locations=['北京'];
 const before=structuredClone(items);
 assert.deepEqual(selectRecords(items,'all','目标示例 北京 agent','','recent').map(item=>item.job.job_id),['46']);
 assert.equal(selectRecords(items,'all','上海 agent','','recent').length,0);
 assert.deepEqual(items,before);
});
test('next dates precede undated actions and empty rows; legacy applied flags retain stage',()=>{
 const noAction=row('none'),undated=row('undated',{}, {stage:'considering',next_action:'练习',due_date:null});
 const later=row('later',{}, {stage:'interview',next_action:'练习',due_date:'2026-10-05'});
 const first=row('first',{applied:true},{stage:'applied',next_action:'准备',due_date:'2026-10-03'});
 assert.deepEqual(selectRecords([noAction,undated,later,first],'all','','','next').map(item=>item.job.job_id),['first','later','undated','none']);
 assert.equal(selectRecords([row('legacy',{applied:true})],'all','','applied','recent').length,1);
});

test('saved and applied entrances keep independent flags and closed saved jobs discoverable',()=>{
 const saved=row('saved',{saved:true}), closed=row('closed',{saved:true},{stage:'closed'});
 const interview=row('interview',{}, {stage:'interview'}), applied=row('applied',{applied:true});
 const items=[saved,closed,interview,applied,row('browsed')];
 assert.deepEqual(selectRecords(items,'saved','','','recent').map(x=>x.job.job_id),['saved','closed']);
 assert.deepEqual(selectRecords(items,'applied','','','recent').map(x=>x.job.job_id),['interview','applied']);
 assert.equal(selectRecords(items,'all','','','recent').length,5);
 assert.equal(selectRecords(items,'saved','无匹配','','recent').length,0);
});
