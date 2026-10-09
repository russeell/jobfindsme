import test from 'node:test';
import assert from 'node:assert/strict';
import {dueJobs,interviewReview} from '../dist-electron/shared/job-follow-up.js';
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
