import assert from 'node:assert/strict';
import test from 'node:test';
import {readFile,writeFile,access} from 'node:fs/promises';
import {BossApplicationController} from '../dist-electron/main/applications/boss-application.js';
import {applicationFile} from '../dist-electron/main/applications/material-file.js';

function fixture({attachment=false,gateAt='',failAt='',cancelAt='',reloadFails=false,onStep=()=>{}}={}){
 const url='https://www.zhipin.com/job_detail/fictional.html',message='您好，我有真实的 Python 工程实践，想了解示例岗位。';
 const draft={workspace_id:'ws',job_id:'job',record_id:'draft',resume_version_id:attachment?'old-version':null,message,status:'prepared',updated_at:'saved'};
 const calls=[],updates=[],receipts={message:0,resume:0};let chat=false,upload=false,input='',disposed,attempt,uploadedBytes;
 const snapshot=target=>({url:chat?'https://www.zhipin.com/web/geek/chat?id=recruiter':url,gate:null,jobId:'fictional',title:'示例工程师',company:'虚构公司',account:'188****0000',chatUrl:'https://www.zhipin.com/web/geek/chat?id=recruiter',targetMatched:true,contactable:true,alreadyContacted:false,contactEstablished:false,chatReady:chat,messageCount:receipts.message,resumeCount:receipts.resume,uploaded:upload,resumeReady:upload,uploadSelector:'input[data-jfm-resume-input="fictional"]',inputText:input});
 let controller;
 const page={
  async read(operation,target){calls.push(operation);if(operation===gateAt)throw Error('平台安全验证');if(operation===failAt)throw Error('发送结果不明');
   if(operation==='contact')chat=true;
   if(operation==='fill_message')input=target.message;
   if(operation==='send_message'){assert.equal(input,message);input='';receipts.message++;}
   if(operation==='send_resume'){assert.ok(uploadedBytes);receipts.resume++;}
   onStep(operation,controller);
   if(operation===cancelAt)await controller.cancel(controllerId);
   return snapshot(target);
  },
  async upload(selector,file){calls.push('upload');assert.match(selector,/data-jfm-resume-input/);uploadedBytes=await readFile(file);upload=true;},
  async navigate(){calls.push('navigate');},async reload(){calls.push('reload');if(reloadFails)throw Error('会话重读失败');},dispose(keep){disposed=keep;},
 };
 const api={
  async bootstrap(){return {sources:[]};},async recordSourceRuntimeFailure(_source,reason){calls.push(`pause:${reason}`);},
  async getJobPreparation(){return {job:{title:'示例工程师',company:'虚构公司',source:{source_name:'BOSS直聘'},apply_url:url}};},
  async listApplicationRecords(){return [draft];},async listApplicationAttempts(){return [];},
  async getResumeVersion(ws,id){assert.equal(id,'old-version');return {version_id:id,original_file:true,source_document_id:'source-old',created_at:'2026-10-12'};},
  async resumeSource(){return {file_name:'原始彩色简历.pdf',content_base64:Buffer.from('%PDF-1.7 exact original bytes').toString('base64')};},
  async beginApplicationAttempt(input){calls.push('reserve');attempt={...draft,...input,attempt_id:'attempt',record_id:'snapshot',state:'running',write_started:false,message_confirmed:false,resume_confirmed:false};return {...attempt};},
  async updateApplicationAttempt(id,input){assert.equal(id,'attempt');updates.push(input);attempt={...attempt,...input};if(input.state&&input.state!=='completed'&&attempt.write_started)attempt.state='uncertain';return {...attempt};},
 };
 controller=new BossApplicationController(api,async()=>page);let controllerId;
 return {controller,api,calls,updates,draft,receipts,get disposed(){return disposed;},get uploadedBytes(){return uploadedBytes;},
  async preview(){const value=await controller.prepare({workspace_id:'ws',job_id:'job',record_id:'draft'});controllerId=value.preview_id;return value;}};
}

test('preview is read only; an explicit token and confirmation are mandatory',async()=>{
 const f=fixture(),p=await f.preview();assert.deepEqual(f.calls,['snapshot']);
 assert.throws(()=>f.controller.execute({preview_id:p.preview_id,confirmed:false}),/确认/);
 assert.throws(()=>f.controller.execute({preview_id:'other',confirmed:true}),/确认/);
 await f.controller.cancel(p.preview_id);assert.equal(f.disposed,false);assert.equal(f.updates.length,0);
});
test('one confirmation sends no attachment when the saved material says none',async()=>{
 const f=fixture(),p=await f.preview();const result=await f.controller.execute({preview_id:p.preview_id,confirmed:true});
 assert.equal(result.state,'completed');assert.equal(result.resume_version_id,null);assert.equal(result.message_confirmed,true);assert.equal(result.resume_confirmed,false);
 assert.equal(f.calls.filter(x=>x==='send_message').length,1);assert.ok(!f.calls.includes('upload'));assert.ok(!f.calls.includes('send_resume'));assert.equal(f.calls.filter(x=>x==='reload').length,1);
});
test('chosen original file is byte exact and attachment verified after reload',async()=>{
 const f=fixture({attachment:true}),p=await f.preview();assert.equal(p.original_file_name,'原始彩色简历.pdf');assert.match(p.file_name,/^简历-[a-f0-9]{16}\.pdf$/);
 const result=await f.controller.execute({preview_id:p.preview_id,confirmed:true});
 assert.equal(f.uploadedBytes.toString(),'%PDF-1.7 exact original bytes');assert.equal(result.resume_version_id,'old-version');assert.equal(result.resume_confirmed,true);
 assert.equal(f.calls.filter(x=>x==='reload').length,2);assert.ok(f.updates.findIndex(x=>x.message_confirmed)<f.updates.findIndex(x=>x.phase==='resume'));
});
test('concurrent confirms coalesce and never send twice',async()=>{
 const f=fixture(),p=await f.preview(),input={preview_id:p.preview_id,confirmed:true};
 const a=f.controller.execute(input),b=f.controller.execute(input);assert.equal(a,b);await a;
 assert.equal(f.calls.filter(x=>x==='contact').length,1);assert.equal(f.calls.filter(x=>x==='reserve').length,1);
});
test('verification or cancellation after a write preserves uncertain and stops following writes',async()=>{
 for(const option of [{gateAt:'send_message'},{cancelAt:'fill_message'}]){
  const f=fixture({...option,attachment:true}),p=await f.preview();const result=await f.controller.execute({preview_id:p.preview_id,confirmed:true});
  assert.equal(result.state,'uncertain');assert.equal(result.message_confirmed,false);assert.ok(!f.calls.includes('send_resume'));assert.equal(f.disposed,true);
 }
});
test('unconfirmed attachment keeps confirmed greeting without claiming application success',async()=>{
 const f=fixture({attachment:true,failAt:'send_resume'}),p=await f.preview();const result=await f.controller.execute({preview_id:p.preview_id,confirmed:true});
 assert.equal(result.state,'uncertain');assert.equal(result.message_confirmed,true);assert.equal(result.resume_confirmed,false);
 assert.equal(f.calls.filter(x=>x==='send_resume').length,1);
});
test('material copy is removed and cannot substitute an archived chosen version',async()=>{
 const f=fixture({attachment:true}),file=await applicationFile(f.api,'ws','old-version');assert.match(file.hash,/^[a-f0-9]{64}$/);await access(file.path);await file.dispose();await assert.rejects(access(file.path));
});
test('persistent platform block stops before accessing BOSS',async()=>{
 const f=fixture();f.api.bootstrap=async()=>({sources:[{source_id:'boss',session_status:'blocked'}]});
 await assert.rejects(f.preview(),/没有访问平台/);assert.deepEqual(f.calls,[]);
});
test('optimistic message bubble is not confirmed when server reread fails',async()=>{
 const f=fixture({attachment:true,reloadFails:true}),p=await f.preview();const result=await f.controller.execute({preview_id:p.preview_id,confirmed:true});
 assert.equal(result.state,'uncertain');assert.equal(result.message_confirmed,false);assert.equal(result.resume_confirmed,false);assert.ok(!f.calls.includes('send_resume'));
});
