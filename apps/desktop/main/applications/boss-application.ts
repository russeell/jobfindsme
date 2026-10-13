import {randomUUID,createHash} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import type {ApplicationAttempt,ApplicationRecord,BossApplicationPreview} from '../../shared/contracts';
import type {DesktopApiClient} from '../backend/api-client';
import {applicationFile,type ApplicationFile} from './material-file';
import type {BossSnapshot,BossTarget,BossOperation} from './boss-dom';
import {isSourceVerificationBlocked} from '../../shared/source-presentation';

export interface BossApplicationPage{
  read(operation:BossOperation,target:BossTarget):Promise<BossSnapshot>;
  upload(selector:string,filePath:string):Promise<void>;
  navigate(url:string):Promise<void>;
  reload():Promise<void>;
  dispose(keep:boolean):void;
}
type Api=Pick<DesktopApiClient,'bootstrap'|'recordSourceRuntimeFailure'|'getJobPreparation'|'listApplicationRecords'|'listApplicationAttempts'|'beginApplicationAttempt'|'updateApplicationAttempt'|'getResumeVersion'|'resumeSource'|'exportResume'>;
type Preview={value:BossApplicationPreview;record:ApplicationRecord;target:BossTarget;page:BossApplicationPage;file?:ApplicationFile;controller:AbortController;timer?:ReturnType<typeof setTimeout>;executing:boolean;promise?:Promise<ApplicationAttempt>};
export const applicationPhases:Record<string,string>={reserved:'正在核对岗位与材料',upload:'正在上传所选简历',contact:'正在发起沟通',message:'正在发送招呼语',verify_message:'正在核实招呼语',resume:'正在发送所选简历',verify_resume:'正在核实简历',finished:'已完成',stopped:'已停止'};

export class BossApplicationController{
  private preview?:Preview;
  private preparing=false;
  private lastPreviewAt=0;
  constructor(private api:Api,private open:(owner:string,url:string)=>Promise<BossApplicationPage>,private progress:(value:{preview_id:string;phase:string})=>void=()=>{},private pause:(reason:'risk_control'|'login_required')=>void=()=>{}){}
  async prepare(input:{workspace_id:string;job_id:string;record_id:string}):Promise<BossApplicationPreview>{
    if(this.preparing||this.preview?.executing)throw Error('已有投递正在准备或执行，请等待完成');
    if(Date.now()-this.lastPreviewAt<30000)throw Error('请稍等片刻再核对 BOSS，避免频繁访问');
    this.preparing=true;this.lastPreviewAt=Date.now();
    let page:BossApplicationPage|undefined,file:ApplicationFile|undefined;
    try{
      await this.cancel(this.preview?.value.preview_id||'');
      const source=(await this.api.bootstrap()).sources.find(s=>s.source_id==='boss');
      if(source&&isSourceVerificationBlocked(source))throw Error('BOSS 已暂停，请在原页处理验证并重新检查；本次没有访问平台');
      const [jobData,records,attempts]=await Promise.all([this.api.getJobPreparation(input.workspace_id,input.job_id),this.api.listApplicationRecords(input.workspace_id,input.job_id),this.api.listApplicationAttempts(input.workspace_id,input.job_id)]);
      const record=records.find(r=>r.record_id===input.record_id),job=jobData.job;
      if(!record||!['prepared','opened'].includes(record.status)||!record.message.trim()||/\{(?:公司|岗位)\}/.test(record.message))throw Error('请保存完整招呼语后再投递');
      if(attempts.some(a=>a.write_started||['running','completed','uncertain'].includes(a.state))||records.some(r=>['contacted','resume_sent','uncertain'].includes(r.status)))throw Error('此岗位已有沟通或待确认记录，请先核对原页；不会重复发送');
      const url=new URL(job.apply_url),jobId=url.pathname.match(/^\/job_detail\/([\w-]+)\.html$/)?.[1];
      if(job.source.source_name!=='BOSS直聘'||url.origin!=='https://www.zhipin.com'||!jobId)throw Error('首版仅支持 BOSS 单岗位详情页');
      file=record.resume_version_id?await applicationFile(this.api,input.workspace_id,record.resume_version_id):undefined;
      const id=randomUUID();page=await this.open(`application:${id}`,job.apply_url);
      const observed=await this.wait(page,{jobId,title:job.title,company:job.company},s=>!!s.title&&!!s.company&&!!s.account,10000);
      if(observed.gate)throw Error(observed.gate);
      if(observed.jobId!==jobId||observed.title.replace(/\s/g,'')!==job.title.replace(/\s/g,''))throw Error('岗位标题与原页不一致，请核对原页');
      if(observed.alreadyContacted||!observed.contactable||!observed.chatUrl)throw Error('BOSS 沟通入口不可核对或已有沟通，请在原页确认');
      const expires_at=new Date(Date.now()+120000).toISOString();
      const value:BossApplicationPreview={preview_id:id,expires_at,title:observed.title,company:observed.company,account:observed.account,message:record.message,resume_version_id:record.resume_version_id,resume_label:file?.label||'暂不附简历',file_name:file?.name||null,original_file_name:file?.originalName||null};
      this.preview={value,record,target:{jobId,title:observed.title,company:observed.company,account:observed.account,chatUrl:observed.chatUrl,message:record.message,fileName:file?.name},page,file,controller:new AbortController(),executing:false};
      this.preview.timer=setTimeout(()=>void this.cancel(id),120000);
      return value;
    }catch(error){await this.pauseFor(error);page?.dispose(false);await file?.dispose();throw error;}finally{this.preparing=false;}
  }
  private async pauseFor(error:unknown){
    const detail=error instanceof Error?error.message:String(error);
    if(detail.includes('BOSS 已暂停'))return;
    const reason=/安全验证|限流|滑块|验证码/.test(detail)?'risk_control':/完成登录|必要资料/.test(detail)?'login_required':undefined;
    if(reason){try{this.pause(reason);}catch{/* Window may close while stopping. */}await this.api.recordSourceRuntimeFailure('boss',reason,'BOSS 单岗位投递已停止，请在原页处理后重新检查').catch(()=>{});}
  }
  execute(input:{preview_id:string;confirmed:true}):Promise<ApplicationAttempt>{
    const preview=this.preview;
    if(input.confirmed!==true||!preview||preview.value.preview_id!==input.preview_id)throw Error('请先核对本次岗位和材料，再明确确认');
    if(preview.promise)return preview.promise; // double clicks share the same side effect.
    if(Date.now()>=Date.parse(preview.value.expires_at))throw Error('确认页已过期，请重新核对');
    preview.executing=true;clearTimeout(preview.timer);
    return preview.promise=this.run(preview);
  }
  async cancel(id:string):Promise<void>{
    const preview=this.preview;if(!preview||preview.value.preview_id!==id)return;
    preview.controller.abort();clearTimeout(preview.timer);
    if(preview.executing)return;this.preview=undefined;preview.page.dispose(false);await preview.file?.dispose();
  }
  async shutdown():Promise<void>{const p=this.preview;if(!p)return;await this.cancel(p.value.preview_id);if(p.promise)await bounded(p.promise,3000).catch(()=>{});}
  private async wait(page:BossApplicationPage,target:BossTarget,accept:(s:BossSnapshot)=>boolean,ms=7000,signal?:AbortSignal):Promise<BossSnapshot>{
    const deadline=Date.now()+ms;
    do{
      if(signal?.aborted)throw Error('已停止执行');
      const snapshot=await bounded(page.read('snapshot',target),Math.min(3000,deadline-Date.now()),signal);
      if(snapshot.gate)throw Error(snapshot.gate);
      if(accept(snapshot))return snapshot;
      await bounded(new Promise(r=>setTimeout(r,250)),Math.max(1,deadline-Date.now()),signal);
    }while(Date.now()<deadline);
    throw Error('未取得可核对的 BOSS 结果，请在原页确认；不会自动重发');
  }
  private async run(p:Preview):Promise<ApplicationAttempt>{
    let attempt:ApplicationAttempt|undefined;
    const signal=p.controller.signal;
    const checkpoint=()=>{if(signal.aborted)throw Error('已停止执行');};
    const update=async(phase:string,values:Record<string,unknown>={})=>{
      checkpoint();attempt=await this.api.updateApplicationAttempt(attempt!.attempt_id,{phase,...values});this.progress({preview_id:p.value.preview_id,phase:applicationPhases[phase]||phase});
    };
    const action=async(operation:BossOperation)=>{checkpoint();return bounded(p.page.read(operation,p.target),4000,signal);};
    try{
      checkpoint();const snapshot=await action('snapshot');
      if(snapshot.gate||!snapshot.targetMatched||snapshot.alreadyContacted)throw Error(snapshot.gate||'岗位、账号或沟通状态已变化，请重新核对');
      if(p.file&&createHash('sha256').update(await readFile(p.file.path)).digest('hex')!==p.file.hash)throw Error('所选简历文件已变化，请重新核对');
      checkpoint();
      attempt=await this.api.beginApplicationAttempt({workspace_id:p.record.workspace_id,job_id:p.record.job_id,record_id:p.record.record_id,expected_updated_at:p.record.updated_at,target_url:snapshot.url,title:p.target.title,company:p.target.company,file_name:p.file?.name||null,file_sha256:p.file?.hash||null});
      if(p.file){
        await update('upload');
        await action('open_upload');
        const upload=await this.wait(p.page,p.target,s=>s.uploaded||!!s.uploadSelector,5000,signal);
        if(!upload.uploaded){await update('upload',{write_started:true});checkpoint();await bounded(p.page.upload(upload.uploadSelector!,p.file.path),5000,signal);await this.wait(p.page,p.target,s=>s.uploaded,12000,signal);}
        await action('close_upload');
      }
      await update('contact',{write_started:true});await action('contact');
      const connected=await this.wait(p.page,p.target,s=>s.chatReady||s.contactEstablished,10000,signal);
      if(!connected.chatReady){checkpoint();await bounded(p.page.navigate(p.target.chatUrl!),10000,signal);}
      const chat=await this.wait(p.page,p.target,s=>s.chatReady,10000,signal);
      if(chat.messageCount||chat.resumeCount)throw Error('相同材料已有发送记录，不会重复发送');
      await update('message');await action('fill_message');checkpoint();await action('send_message');
      await this.wait(p.page,p.target,s=>s.chatReady&&s.messageCount>0&&s.inputText==='',8000,signal);
      await update('verify_message');checkpoint();await bounded(p.page.reload(),10000,signal);
      // A bubble surviving a normal server reload is stronger than an optimistic DOM update.
      await this.wait(p.page,p.target,s=>s.chatReady&&s.messageCount>0,10000,signal);
      await update('verify_message',{message_confirmed:true});
      if(p.file){
        await update('resume');await action('open_resume');
        await this.wait(p.page,p.target,s=>s.resumeReady,5000,signal);await action('select_resume');checkpoint();await action('send_resume');
        await this.wait(p.page,p.target,s=>s.chatReady&&s.resumeCount>0,8000,signal);
        await update('verify_resume');checkpoint();await bounded(p.page.reload(),10000,signal);
        await this.wait(p.page,p.target,s=>s.chatReady&&s.messageCount>0&&s.resumeCount>0,10000,signal);
        await update('verify_resume',{resume_confirmed:true});
      }
      return await this.api.updateApplicationAttempt(attempt.attempt_id,{state:'completed',phase:'finished',detail:p.file?'招呼语和所选简历在重新读取的会话中已核实。':'招呼语在重新读取的会话中已核实；本次不附简历。'});
    }catch(error){
      await this.pauseFor(error);
      if(!attempt)throw error;
      const detail=String(error instanceof Error?error.message:error).slice(0,500);
      // Persist before releasing the browser. Do not retry an uncertain action.
      return await this.api.updateApplicationAttempt(attempt.attempt_id,{state:signal.aborted?'cancelled':/登录|验证|限流|资料/.test(detail)?'blocked':'failed',phase:'stopped',detail});
    }finally{clearTimeout(p.timer);p.page.dispose(!!attempt?.write_started);await p.file?.dispose();if(this.preview===p)this.preview=undefined;}
  }
}
async function bounded<T>(work:Promise<T>,ms:number,signal?:AbortSignal):Promise<T>{
  let timer:ReturnType<typeof setTimeout>|undefined;
  let abort=()=>{};
  try{if(signal?.aborted)throw Error('已停止执行');return await Promise.race([work,new Promise<T>((_,reject)=>{timer=setTimeout(()=>reject(Error('BOSS 操作超时，结果需在原页核对；不会重发')),Math.max(1,ms));abort=()=>reject(Error('已停止执行'));signal?.addEventListener('abort',abort,{once:true});})]);}
  finally{clearTimeout(timer);signal?.removeEventListener('abort',abort);}
}
