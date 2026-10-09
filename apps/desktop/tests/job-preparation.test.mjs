import test from 'node:test';
import assert from 'node:assert/strict';
import {proposalMatchesJob,preparationDraft,preparationHasChanges,mergePreparation} from '../dist-electron/shared/job-preparation.js';
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

test('background application confirmation keeps server stage while preserving local notes',()=>{
 const saved={workspace_id:'test',job_id:'test-job',stage:'considering',next_action:'',due_date:null,note:'',resume_version_id:null,updated_at:null};
 const fresh={...saved,stage:'applied',resume_version_id:'tailored',updated_at:'2026-10-10'};
 const merged=mergePreparation({...saved,next_action:'准备项目介绍',note:'待核对'},saved,fresh);
 assert.equal(merged.stage,'applied');
 assert.equal(merged.next_action,'准备项目介绍');
 assert.equal(merged.note,'待核对');
 assert.equal(merged.resume_version_id,'tailored');
 assert.equal(mergePreparation({...saved,stage:'interview'},saved,fresh).stage,'interview');
 assert.match(preparationDraft('interview-prep',{company:'虚构公司',title:'工程师'}),/请读取并结合这个岗位的专属简历/);
});


test('unsaved preparation protection covers editable fields but ignores background document updates',()=>{
 const saved={workspace_id:'test',job_id:'test-job',stage:'considering',next_action:'',due_date:null,note:'',resume_version_id:null,updated_at:null};
 assert.equal(preparationHasChanges(undefined,saved),false);
 assert.equal(preparationHasChanges(saved,undefined),false);
 assert.equal(preparationHasChanges({...saved,resume_version_id:'new-document',updated_at:'2026-10-02'},saved),false);
 for(const [key,value] of [['stage','interview'],['next_action','练习项目介绍'],['due_date','2026-10-03'],['note','待核对']]){
  const edited={...saved,[key]:value};
  assert.equal(preparationHasChanges(edited,saved),true);
  assert.equal(preparationHasChanges(edited,{...edited}),false);
 }
 assert.equal(saved.stage,'considering');
});
