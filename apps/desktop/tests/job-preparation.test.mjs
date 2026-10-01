import test from 'node:test';
import assert from 'node:assert/strict';
import {proposalMatchesJob,preparationDraft} from '../dist-electron/shared/job-preparation.js';
import {resolveResearchSession} from '../dist-electron/shared/research-session.js';

test('preparation proposals use job identity and legacy exact URL only',()=>{
 const job={job_id:'selected',apply_url:'https://www.liepin.com/job/901.html',company:'虚构公司',title:'Python 工程师'};
 assert.equal(proposalMatchesJob({target_job_id:'other',target_url:job.apply_url},job),false);
 assert.equal(proposalMatchesJob({target_job_id:'selected'},job),true);
 assert.equal(proposalMatchesJob({target_url:job.apply_url},job),true);
 assert.equal(proposalMatchesJob({target_title:job.title,target_url:'https://www.liepin.com/job/902.html'},job),false);
 for(const skill of ['resume-tailor','interview-prep','deep-research']){
   const draft=preparationDraft(skill,job);
   assert.equal(resolveResearchSession(draft,undefined,job,{}).activeJobId,'selected');
 }
});
