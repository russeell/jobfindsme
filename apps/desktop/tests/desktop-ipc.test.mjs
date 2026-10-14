import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,readFileSync,existsSync,rmSync} from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {createDesktopHandlerRegistrar} from '../dist-electron/main/ipc/register.js';
import {registerResumeHandlers} from '../dist-electron/main/ipc/resumes.js';
import {registerPreparationHandlers} from '../dist-electron/main/ipc/preparation.js';

function harness(){
 const handlers=new Map(),frame={},owner={mainFrame:frame,isDestroyed:()=>false};let current=owner;
 const register=createDesktopHandlerRegistrar({handle:(name,callback)=>handlers.set(name,callback)},()=>current);
 return {register,handlers,event:{sender:owner,senderFrame:frame},setOwner:value=>current=value};
}
test('every registered request rejects other windows, subframes and destroyed owners before side effects',()=>{
 const h=harness();let calls=0;h.register('example',()=>++calls);
 const invoke=h.handlers.get('example');
 for(const event of [{sender:{},senderFrame:h.event.senderFrame},{...h.event,senderFrame:{}},{...h.event,senderFrame:null}])assert.throws(()=>invoke(event),/unauthorized caller/);
 assert.equal(calls,0);assert.equal(invoke(h.event),1);
 h.setOwner(undefined);assert.throws(()=>invoke(h.event),/unauthorized caller/);
 h.setOwner({isDestroyed:()=>true});assert.throws(()=>invoke(h.event),/unauthorized caller/);
 assert.equal(calls,1);
});
test('resume IPC preserves exact archived reads, original bytes and cancellation without writing',async()=>{
 const directory=mkdtempSync(path.join(os.tmpdir(),'jfm-ipc-'));const original=Buffer.from('%PDF-1.7\nFictional original only.\n');
 try{
  const h=harness();let cancelled=true,imported=false,exported=false;
  const client={getResumeVersion:async(workspace,id)=>({workspace,id,original_file:true}),resumeSource:async()=>({file_name:'Original.PDF',content_base64:original.toString('base64')}),importResume:async()=>{imported=true;},exportResume:async()=>{exported=true;}};
  registerResumeHandlers(h.register,{client:()=>client,window:()=>({}),dialog:{showOpenDialog:async()=>({canceled:true,filePaths:[]}),showSaveDialog:async()=>({canceled:cancelled,filePath:path.join(directory,'exact.PDF')})}});
  const read=h.handlers.get('desktop:get-resume-version');assert.deepEqual(await read(h.event,'workspace','archived'),{workspace:'workspace',id:'archived',original_file:true});
  assert.throws(()=>read(h.event,'',null),/invalid resume version/);
  await h.handlers.get('desktop:import-resume')(h.event);assert.equal(imported,false);
  const source=h.handlers.get('desktop:export-resume-source');assert.equal(await source(h.event,{workspace_id:'workspace',document_id:'source'}),false);
  assert.equal(existsSync(path.join(directory,'exact.PDF')),false);
  assert.equal(await h.handlers.get('desktop:export-resume')(h.event,{workspace_id:'workspace',version_id:'old',format:'pdf'}),undefined);assert.equal(exported,false);
  cancelled=false;assert.equal(await source(h.event,{workspace_id:'workspace',document_id:'source'}),true);
  assert.deepEqual(readFileSync(path.join(directory,'exact.PDF')),original);
  await assert.rejects(h.handlers.get('desktop:export-resume')(h.event,{version_id:'old',format:'exe'}),/invalid resume export/);
 }finally{rmSync(directory,{recursive:true,force:true});}
});
test('preparation IPC passes explicit no attachment unchanged and refuses malformed deletion',async()=>{
 const h=harness();let saved;
 registerPreparationHandlers(h.register,()=>({saveApplicationRecord:async input=>(saved=input),setApplicationDeleted:async()=>{throw Error('must not call');}}));
 const input={workspace_id:'workspace',job_id:'job',resume_version_id:null,message:'Original greeting',status:'prepared'};
 assert.equal(await h.handlers.get('desktop:save-application-record')(h.event,input),input);assert.equal(saved.resume_version_id,null);
 assert.throws(()=>h.handlers.get('desktop:set-application-deleted')(h.event,'workspace','job','record','false'),/invalid record action/);
});
