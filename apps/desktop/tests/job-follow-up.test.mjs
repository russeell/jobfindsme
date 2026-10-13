import test from 'node:test';
import assert from 'node:assert/strict';
import {dueJobs,interviewReview,reminderDay} from '../dist-electron/shared/job-follow-up.js';
test('quick dates use local calendar days across month, year and daylight-saving boundaries',()=>{
 const original=process.env.TZ;process.env.TZ='America/New_York';
 try{
  assert.equal(reminderDay(1,new Date(2026,11,31,23,50)),'2027-01-01');
  assert.equal(reminderDay(3,new Date(2026,9,30,0,5)),'2026-11-02');
  assert.equal(reminderDay(1,new Date(2026,2,7,23,50)),'2026-03-08');
 }finally{if(original===undefined)delete process.env.TZ;else process.env.TZ=original;}
});
test('today includes overdue work, omits future, closed and undated actions',()=>{
 const item=(id,due_date,stage='considering',next_action='跟进')=>({job:{job_id:id},preparation:{due_date,stage,next_action}});
 const rows=[item('future','2026-10-12'),item('today','2026-10-10'),item('old','2026-10-09'),item('closed','2026-10-01','closed'),item('none',null),item('empty','2026-10-01','considering','')];
 assert.deepEqual(dueJobs(rows,'2026-10-10').map(row=>row.job.job_id),['old','today']);
});
test('review uses latest completed feedback, deduplicates and does not invent weaknesses',()=>{
 const turn=(weaknesses,interrupted=false)=>({role:'assistant',interrupted,interviewState:{weaknesses}});
 assert.deepEqual(interviewReview([turn(['旧薄弱点']),turn(['任务拆解','任务拆解','']),turn(['未完成反馈'],true)]),['任务拆解']);
 assert.deepEqual(interviewReview([turn(['旧薄弱点']),turn([])]),[]);
 assert.deepEqual(interviewReview([{role:'user',text:'练习agent'}]),[]);
});
