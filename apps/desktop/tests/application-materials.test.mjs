import test from 'node:test';
import assert from 'node:assert/strict';
import {applicationDraft} from '../dist-electron/shared/application-materials.js';

const input={workspaceId:'workspace',job:{job_id:'job',title:'AI Engineer',company:'Example'},resumeId:'job-resume',versions:[{version_id:'new-base',is_current:true}],greeting:'你好 {公司}，申请{岗位}',recordId:'new-record'};
const record=(id,resume,status,updated)=>({workspace_id:'workspace',job_id:'job',record_id:id,resume_version_id:resume,message:`saved ${id}`,status,created_at:'2026-10-01T00:00:00Z',updated_at:updated});
test('reopening saved materials preserves the exact resume and no-attachment choice',()=>{
 for(const resume of ['old-resume',null,'archived-resume']){
  const draft=applicationDraft({...input,records:[record('saved',resume,'opened','2026-10-02T00:00:00Z')]});
  assert.equal(draft.resume_version_id,resume);assert.equal(draft.record_id,'saved');assert.equal(draft.message,'saved saved');assert.equal(draft.status,'opened');
 }
});
test('latest edited draft wins over API creation order, confirmed records and other jobs',()=>{
 const rows=[record('confirmed','sent-resume','resume_sent','2026-10-10T00:00:00Z'),record('older','base','prepared','2026-10-02T00:00:00Z'),record('edited','tailored','prepared','2026-10-09T00:00:00Z'),{...record('other',null,'opened','2026-10-11T00:00:00Z'),job_id:'other-job'}];
 assert.equal(applicationDraft({...input,records:rows}).record_id,'edited');
});
test('new materials reuse the job resume, otherwise the current base, and fill the job once',()=>{
 const draft=applicationDraft({...input,records:[]});
 assert.equal(draft.resume_version_id,'job-resume');assert.equal(draft.message,'你好 Example，申请AI Engineer');
 assert.equal(applicationDraft({...input,resumeId:null,records:[]}).resume_version_id,'new-base');
 assert.equal(applicationDraft({...input,resumeId:null,versions:[],records:[]}).resume_version_id,null);
 const rows=[record('confirmed','sent-resume','resume_sent','2026-10-10T00:00:00Z')];
 assert.equal(applicationDraft({...input,records:rows}).record_id,'new-record');
 assert.equal(rows[0].record_id,'confirmed');
});
