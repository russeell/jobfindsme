import {applicationDraft} from '../../../shared/application-materials';
import {BossApplicationReview} from './BossApplicationReview';
import {GreetingPolish} from "./GreetingPolish";
import {defaultGreeting,greetingKey,renderGreeting} from '../../../shared/application-greeting';
import {useEffect,useRef,useState} from 'react';
import type {ApplicationAttempt,BossApplicationPreview,ApplicationRecord,ApplicationRecordInput,ResumeVersion,SearchResultItem} from '../../../shared/contracts';
import {userError} from '../../../shared/user-errors';
export type ApplicationGuard={dirty:boolean;busy:boolean;reveal():void;save():Promise<boolean>};
export const applicationLabels={prepared:'材料已准备',opened:'已发起打开原页',contacted:'已发起沟通（本人确认）',resume_sent:'简历已发送（本人确认）',uncertain:'结果待确认'};
export function ApplicationPreparation({workspaceId,job,resumeId,onGuard,onOpenOriginal,initialView='materials'}:{initialView?:'materials'|'records';workspaceId:string;job:SearchResultItem['job'];resumeId?:string|null;onGuard(value:ApplicationGuard):void;onOpenOriginal():void}){
 const [versions,setVersions]=useState<ResumeVersion[]>([]),[records,setRecords]=useState<ApplicationRecord[]>([]);
 const [draft,setDraft]=useState<ApplicationRecordInput>();
 const [saved,setSaved]=useState<ApplicationRecordInput>();
 const [error,setError]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false);
 const [greeting,setGreeting]=useState(()=>localStorage.getItem(greetingKey(workspaceId))||defaultGreeting);
 const [polishing,setPolishing]=useState(false),[templateOpen,setTemplateOpen]=useState(false);
 const [savedGreeting,setSavedGreeting]=useState(greeting);
 const [view,setView]=useState<'materials'|'records'>(initialView),[showDeleted,setShowDeleted]=useState(false),[deletedRecords,setDeletedRecords]=useState<ApplicationRecord[]>([]),[deleteTarget,setDeleteTarget]=useState<ApplicationRecord>();
 const [confirm,setConfirm]=useState<ApplicationRecordInput['status']>();
 const [preview,setPreview]=useState<BossApplicationPreview>(),[applying,setApplying]=useState(false),[attempts,setAttempts]=useState<ApplicationAttempt[]>([]);
 const previewRef=useRef<string|undefined>(undefined);previewRef.current=preview?.preview_id;
 const boss=job.source.source_name==='BOSS直聘';
 useEffect(()=>()=>{if(previewRef.current)void window.jobfindsme!.cancelBossApplication(previewRef.current);},[]);
 useEffect(()=>{let alive=true;void window.jobfindsme!.listApplicationAttempts(workspaceId,job.job_id).then(rows=>{if(alive)setAttempts(rows);}).catch(e=>{if(alive)setError(userError(e).message);});return()=>{alive=false;};},[workspaceId,job.job_id]);
 const dirty=greeting!==savedGreeting||!!draft&&JSON.stringify(draft)!==JSON.stringify(saved);
 useEffect(()=>{let alive=true;void Promise.all([window.jobfindsme!.listResumeVersions(workspaceId),window.jobfindsme!.listApplicationRecords(workspaceId,job.job_id),window.jobfindsme!.listApplicationAttempts(workspaceId,job.job_id)]).then(([v,r,a])=>{if(!alive)return;setVersions(v);setRecords(r);setAttempts(a);const value=applicationDraft({workspaceId,job,resumeId,versions:v,records:r.filter(row=>!a.some(attempt=>attempt.record_id===row.record_id)),greeting:localStorage.getItem(greetingKey(workspaceId))||defaultGreeting,recordId:crypto.randomUUID()});setDraft(value);setSaved(value);}).catch(e=>{if(alive)setError(userError(e).message);});return()=>{alive=false;};},[workspaceId,job.job_id]);
 async function exportSelected(){const selected=versions.find(v=>v.version_id===draft?.resume_version_id);if(!draft?.resume_version_id)return;if(selected?.original_file&&selected.source_document_id)await window.jobfindsme!.exportResumeSource({workspace_id:workspaceId,document_id:selected.source_document_id});else await window.jobfindsme!.exportResume({workspace_id:workspaceId,version_id:draft.resume_version_id,format:'pdf',template:'professional'});}
 async function save(status:ApplicationRecordInput['status']='prepared'){
  if(!draft||busy||polishing)return false;if(greeting!==savedGreeting&&!greeting.trim()){setError('请填写常用招呼语，或保留原模板。');return false;}setBusy(true);setError('');setNotice('');
  try{const value=await window.jobfindsme!.saveApplicationRecord({...draft,status});if(greeting!==savedGreeting){localStorage.setItem(greetingKey(workspaceId),greeting.trim());setSavedGreeting(greeting);}
setRecords(current=>[value,...current.filter(x=>x.record_id!==value.record_id)]);const next={...draft,status};setSaved(next);setDraft(next);setNotice(draft.resume_version_id?'材料已保存；面试将复用这份简历与岗位 JD。':'已保存，投递材料不附简历。');window.dispatchEvent(new Event('jfm:job-updated'));return true;}catch(e){setError(userError(e).message);return false;}finally{setBusy(false);}
 }
 useEffect(()=>onGuard({dirty,busy:busy||polishing||applying,reveal:()=>setView('materials'),save:()=>save(draft?.status==='opened'?'opened':'prepared')}),[dirty,busy,polishing,applying,draft,greeting]);
 const completed=draft&&['contacted','resume_sent','uncertain'].includes(draft.status);
 async function open(){if(busy||polishing||!draft)return;setError('');try{await window.jobfindsme!.copyChatText(draft.message);if(await save('opened'))onOpenOriginal();}catch(e){setError(userError(e).message);}}
 async function reviewBoss(){if(busy||polishing||applying||!draft)return;if(!await save(draft.status))return;setBusy(true);setNotice('');try{setPreview(await window.jobfindsme!.previewBossApplication({workspace_id:workspaceId,job_id:job.job_id,record_id:draft.record_id}));}catch(e){setError(userError(e).message);}finally{setBusy(false);}}
 function applicationResult(result:ApplicationAttempt){setPreview(undefined);setAttempts(rows=>[result,...rows.filter(r=>r.attempt_id!==result.attempt_id)]);setView('records');setNotice('');void window.jobfindsme!.listApplicationRecords(workspaceId,job.job_id).then(setRecords).catch(e=>setError(userError(e).message));window.dispatchEvent(new Event('jfm:job-updated'));}
 const attempted=attempts.some(a=>a.write_started||['running','completed','uncertain'].includes(a.state));
 function saveGreeting(){if(!greeting.trim())return false;try{localStorage.setItem(greetingKey(workspaceId),greeting.trim());setSavedGreeting(greeting);setNotice('常用招呼语已保存。');return true;}catch(e){setError(userError(e).message);return false;}}

 async function changeDeleted(row:ApplicationRecord,deleted:boolean){
  if(busy||polishing)return;setBusy(true);setError('');
  try{await window.jobfindsme!.setApplicationDeleted(workspaceId,job.job_id,row.record_id,deleted);
   setRecords(rows=>deleted?rows.filter(r=>r.record_id!==row.record_id):[row,...rows]);
   setDeletedRecords(rows=>deleted?[row,...rows]:rows.filter(r=>r.record_id!==row.record_id));
   if(deleted&&draft?.record_id===row.record_id){const next={...draft,record_id:crypto.randomUUID(),status:'prepared' as const};setDraft(next);setSaved(dirty?undefined:next);}
   setDeleteTarget(undefined);setNotice(deleted?'记录已删除，可在“已删除”中恢复。':'记录已恢复。');window.dispatchEvent(new Event('jfm:job-updated'));
  }catch(e){setError(userError(e).message);}finally{setBusy(false);}
 }
 async function toggleDeleted(){if(!showDeleted){setBusy(true);try{setDeletedRecords(await window.jobfindsme!.listApplicationRecords(workspaceId,job.job_id,true));setShowDeleted(true);}catch(e){setError(userError(e).message);}finally{setBusy(false);}}else setShowDeleted(false);}
 return <section className="application-preparation application-clean">
  <nav className="application-tabs" aria-label="投递工作台"><button disabled={applying} aria-pressed={view==='materials'} onClick={()=>setView('materials')}>投递材料</button><button disabled={applying} aria-pressed={view==='records'} onClick={()=>setView('records')}>记录{records.length?` · ${records.length}`:''}</button></nav>
  <div className="application-content" hidden={view!=='materials'}>
  {preview?<BossApplicationReview preview={preview} onBusy={setApplying} onResult={applicationResult} onBack={()=>{void window.jobfindsme!.cancelBossApplication(preview.preview_id);setPreview(undefined);}}/>:draft&&!completed?<>
   <div className="application-material-tools"><label>使用的简历<select aria-label="投递使用的简历" value={draft.resume_version_id||''} disabled={busy||polishing} onChange={e=>setDraft({...draft,resume_version_id:e.target.value||null})}><option value="">暂不附简历</option>{draft.resume_version_id&&!versions.some(v=>v.version_id===draft.resume_version_id)&&<option value={draft.resume_version_id}>上次选用的简历 · 已归档</option>}{versions.map(v=><option value={v.version_id} key={v.version_id}>{v.version_id===saved?.resume_version_id&&records.some(r=>r.record_id===draft.record_id)?'上次选用的简历':v.is_current?'基础简历':v.version_id===resumeId?'此岗位简历':'历史简历'} · {new Date(v.created_at).toLocaleDateString()}</option>)}</select></label><button disabled={busy||polishing||!draft.resume_version_id} onClick={()=>{setBusy(true);void exportSelected().catch(e=>setError(userError(e).message)).finally(()=>setBusy(false));}}>导出简历</button><button type="button" aria-expanded={templateOpen} disabled={busy||polishing} onClick={()=>setTemplateOpen(v=>!v)}>常用话术</button></div>
   {templateOpen&&<div className="application-template"><label>常用招呼语<textarea aria-label="常用招呼语模板" rows={3} maxLength={2500} value={greeting} disabled={busy||polishing} onChange={e=>setGreeting(e.target.value)}/></label><p className="note">{'{公司}'}、{'{岗位}'} 自动填入当前岗位。</p><GreetingPolish workspaceId={workspaceId} value={greeting} disabled={busy||polishing} onBusy={setPolishing} onAccept={setGreeting}/><div className="button-row"><button disabled={busy||polishing||!greeting.trim()} onClick={()=>{if(!saveGreeting())return;setDraft({...draft,message:renderGreeting(greeting,job)});setTemplateOpen(false);}}>保存并用于本次</button><button disabled={busy||polishing} onClick={()=>setTemplateOpen(false)}>收起</button></div></div>}
   <label className="application-message-label">招呼语<span>{draft.message.length} 字</span><textarea aria-label="投递开场白" rows={4} maxLength={3000} disabled={busy||polishing} value={draft.message} onChange={e=>setDraft({...draft,message:e.target.value})}/></label>
   <GreetingPolish workspaceId={workspaceId} value={draft.message} target={{workspaceId,jobId:job.job_id,resumeVersionId:draft.resume_version_id||null}} disabled={busy||polishing} onBusy={setPolishing} onAccept={message=>setDraft({...draft,message})}/>
   <div className="application-result-line"><span>已在平台操作？</span><select aria-label="记录投递结果" value="" disabled={busy||polishing} onChange={e=>setConfirm(e.target.value as ApplicationRecordInput['status'])}><option value="">记录结果…</option><option value="contacted">已发起沟通</option><option value="resume_sent" disabled={!draft.resume_version_id}>简历已发送</option><option value="uncertain">结果待确认</option></select></div>
   {confirm&&<div className="history-confirm" role="alert"><p>确认记录“{applicationLabels[confirm]}”？仅记录你的操作，不会代为发送。</p><button disabled={busy||polishing} onClick={()=>setConfirm(undefined)}>取消</button><button disabled={busy||polishing} onClick={()=>void save(confirm).then(ok=>{if(ok){setConfirm(undefined);setView('records');}})}>确认记录</button></div>}
  </>:completed?<div className="application-empty"><p>本次结果已记录。</p><button onClick={()=>{const value={...draft!,record_id:crypto.randomUUID(),status:'prepared' as const};setDraft(value);setSaved(undefined);}}>准备新材料</button></div>:<p className="note">正在读取材料…</p>}
  </div>
  <div className="application-content" hidden={view!=='records'}><div className="application-record-heading"><span>{showDeleted?'已删除记录':'投递记录'}</span><button disabled={busy||polishing} onClick={()=>void toggleDeleted()}>{showDeleted?'返回记录':'已删除'}</button></div>
   {(showDeleted?deletedRecords:records).map(row=>{const attempt=attempts.find(a=>a.record_id===row.record_id);return <div className="application-record" key={row.record_id}><div className="application-record-top"><div><strong>{attempt?(attempt.state==='completed'?'BOSS 发送已核实':attempt.state==='running'?'BOSS 执行尚未结束':attempt.write_started?'BOSS 结果待确认':'BOSS 执行已停止'):applicationLabels[row.status]}</strong><small>{new Date(row.updated_at).toLocaleString()} · {row.resume_version_id?`所选简历${versions.find(v=>v.version_id===row.resume_version_id)?'':' · 已归档'}`:'未附简历'}</small></div><button disabled={busy||polishing||attempt?.state==='running'} onClick={()=>showDeleted?void changeDeleted(row,false):setDeleteTarget(row)}>{showDeleted?'恢复':'删除'}</button></div>{attempt&&<div className="application-receipts" role="status"><span>{attempt.message_confirmed?'✓ 招呼语已核实':'招呼语未核实'}</span>{attempt.resume_version_id&&<span>{attempt.resume_confirmed?'✓ 所选简历已核实':'所选简历未核实'}</span>}<p>{attempt.detail}</p>{attempt.file_name&&<small>{attempt.file_name}</small>}</div>}<details><summary>查看招呼语</summary><p>{row.message}</p></details></div>;})}
   {!(showDeleted?deletedRecords:records).length&&<p className="application-empty">{showDeleted?'没有已删除记录':initialView==='records'?'此岗位已标记投递，尚未记录具体发送材料。可在“投递材料”中补充记录。':'暂无记录，保存材料后会显示在这里。'}</p>}
   {deleteTarget&&<div role="alert" className="history-confirm"><p>删除这条记录？可从“已删除”恢复，不影响简历和岗位投递状态。{deleteTarget.record_id===draft?.record_id?'当前材料会保留为一份新草稿。':''}</p><button onClick={()=>setDeleteTarget(undefined)}>取消</button><button className="danger-button" disabled={busy||polishing} onClick={()=>void changeDeleted(deleteTarget,true)}>删除记录</button></div>}
  </div>
  {error&&<p role="alert" className="preparation-error application-feedback">{error}</p>}{notice&&<p role="status" className="note application-feedback">{notice}</p>}
  {view==='materials'&&draft&&!completed&&!preview&&<footer className="application-actions"><button disabled={busy||polishing||!dirty&&records.some(r=>r.record_id===draft.record_id)} onClick={()=>void save(draft.status)}>保存材料</button><button className={boss?'':'primary-button'} disabled={busy||polishing||!job.apply_url||!draft.message.trim()} onClick={()=>void open()}>复制并打开 ↗</button>{boss&&<button className="primary-button" disabled={busy||polishing||!attempted&&!draft.message.trim()} onClick={()=>attempted?setView('records'):void reviewBoss()}>{busy?'正在准备…':attempted?'查看投递记录':'一键投递'}</button>}</footer>}
 </section>;
}
