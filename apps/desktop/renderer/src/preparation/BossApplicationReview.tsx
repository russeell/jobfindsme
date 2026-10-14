import {useEffect,useRef,useState} from 'react';
import type {ApplicationAttempt,BossApplicationPreview} from '../../../shared/contracts';
import {userError} from '../../../shared/user-errors';

export function BossApplicationReview({preview,onBack,onBusy,onResult}:{preview:BossApplicationPreview;onBack():void;onBusy(value:boolean):void;onResult(result:ApplicationAttempt):void}){
 const [running,setRunning]=useState(false),[phase,setPhase]=useState(''),[error,setError]=useState('');
 const heading=useRef<HTMLHeadingElement>(null),stop=useRef<HTMLButtonElement>(null);
 useEffect(()=>{heading.current?.focus();},[preview.preview_id]);
 useEffect(()=>{if(running)stop.current?.focus();},[running]);
 useEffect(()=>window.jobfindsme!.onApplicationProgress(value=>{if(value.preview_id===preview.preview_id)setPhase(value.phase);}),[preview.preview_id]);
 async function execute(){
  if(running)return;setRunning(true);onBusy(true);setError('');setPhase('正在核对岗位与材料');
  try{onResult(await window.jobfindsme!.executeBossApplication({preview_id:preview.preview_id,confirmed:true}));}
  catch(e){setError(userError(e).message);}
  finally{setRunning(false);onBusy(false);}
 }
 return <section className="boss-application-review" aria-label="确认 BOSS 单岗位投递">
  <h3 ref={heading} tabIndex={-1}>确认本次投递</h3>
  <p className="note">BOSS直聘 · {preview.account}</p>
  <div className="application-recipient"><strong>{preview.title}</strong><span>{preview.company}</span></div>
  <dl><dt>发送的简历</dt><dd>{preview.resume_label}{preview.file_name&&<small>{preview.original_file_name&&`${preview.original_file_name} → `}{preview.file_name}</small>}</dd><dt>招呼语</dt><dd className="application-review-message">{preview.message}</dd></dl>
  <p className="note">确认后将发起沟通、发送以上招呼语{preview.file_name?'及这份附件简历':''}。BOSS 可能同时发送平台默认招呼语或在线简历。若需额外验证，将停止并保留结果。</p>
  {running&&<p role="status" className="application-running"><i/>{phase}</p>}
  {error&&<p role="alert" className="preparation-error">{error}</p>}
  <div className="application-review-actions">{running?<button ref={stop} onClick={()=>void window.jobfindsme!.cancelBossApplication(preview.preview_id)}>停止执行</button>:<><button onClick={onBack}>返回修改</button><button className="primary-button" onClick={()=>void execute()}>确认并投递</button></>}</div>
 </section>;
}
