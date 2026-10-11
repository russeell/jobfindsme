import test from 'node:test';
import assert from 'node:assert/strict';
import {jobDecision} from '../dist-electron/shared/job-decision.js';
const job={locations:['上海'],salary_min_k:20,salary_max_k:30,description:'要求 Python 开发',source:{liveness:'unknown',detail_level:'detail_page'}};
const details={skills:{status:'known',ratio:1,explanation:'Python 有对应经历。'},experience:{status:'known',ratio:.5,explanation:'可确认工作年限1年 / JD最低2年，按达成比例计分。'},education:{status:'unknown',ratio:1,explanation:'学历未知，暂不计分。'}};
test('unknown and partial evidence never appear as fulfilled matching signals',()=>{
 const result=jobDecision(job,details,false,true);
 assert.deepEqual(result.signals,['技能：Python 有对应经历。']);
 assert(result.gaps.some(text=>text.includes('JD最低2年')));
 assert(result.gaps.some(text=>text.includes('学历未知')));
 assert(result.gaps.some(text=>text.includes('原页')));
 assert(!JSON.stringify(result).includes('计分'));
});
test('changed originals, list snippets and missing resumes suppress old personal matches',()=>{
 for(const result of [jobDecision(job,details,true,true),jobDecision({...job,source:{...job.source,detail_level:'list_snippet'}},details,false,true),jobDecision(job,details,false,false)])assert.deepEqual(result.signals,[]);
 assert(jobDecision(job,details,true,true).gaps.some(text=>text.includes('旧匹配')));
});
test('closed or stale sources and unknown fields stay explicit',()=>{
 const result=jobDecision({...job,locations:[],salary_min_k:null,salary_max_k:null,source:{liveness:'closed'}},undefined,false,false);
 assert(result.gaps.some(text=>text.includes('已关闭')));
 assert(result.gaps.some(text=>text.includes('地点未注明')));
 assert(result.gaps.some(text=>text.includes('薪资未注明')));
 assert(result.gaps.some(text=>text.includes('完整 JD')));
 assert(jobDecision({...job,source:{liveness:'stale'}}).gaps.some(text=>text.includes('过期')));
 assert(!jobDecision({...job,salary_min_k:null,salary_max_k:null,salary:{raw_text:'面议'}}).gaps.some(text=>text.includes('薪资未注明')));
});
