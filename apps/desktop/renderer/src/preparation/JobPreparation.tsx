import {ApplicationPreparation,type ApplicationGuard} from "./ApplicationPreparation";
import {ResumePage} from '../resume/ResumePage';
import {useEffect,useRef,useState} from 'react';
import type {AssistantSkillId} from '../../../shared/assistant-skills';
import type {JobPreparationData,JobPreparationInput,PromptSession,ResumeState,SearchResultItem} from '../../../shared/contracts';
import {mergePreparation,preparationHasChanges,preparationStages,proposalMatchesJob} from '../../../shared/job-preparation';
import {fromStoredResearchChat,type SavedResearchChat} from '../../../shared/research-chat-history';
import {hasFullDescription} from '../../../shared/research-reports';
import {sourceBrowserIdForSourceName} from '../../../shared/source-browser-policy';
import {userError} from '../../../shared/user-errors';
import {Icon} from '../shared/Icon';
import {useOriginalBrowser} from '../shared/Workbench';
import {formatSalary} from '../search/salary';

type Job=SearchResultItem['job'];
type Props={initialApplicationView?:'materials'|'records';initialApplicationOpen?:boolean;workspaceId:string;job:Job;onClose():void;onStart(job:Job,skill:AssistantSkillId,chatId?:string):void};
export function JobPreparation({workspaceId,job:initialJob,onClose,onStart,initialApplicationOpen=false,initialApplicationView='materials'}:Props){
 const dialog=useRef<HTMLDialogElement>(null);
 const progress=useRef<HTMLDetailsElement>(null);
 const leavePrompt=useRef<HTMLDivElement>(null);
 const autoRead=useRef(false);
 const mounted=useRef(true);
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
 const [editingResume,setEditingResume]=useState(false);
 const [data,setData]=useState<JobPreparationData>();
 const [saved,setSaved]=useState<JobPreparationInput>();
 const [leaving,setLeaving]=useState<{run():void}>();
 const [applicationOpen,setApplicationOpen]=useState(initialApplicationOpen);
 const [applicationGuard,setApplicationGuard]=useState<ApplicationGuard>();
 const progressDirty=preparationHasChanges(data?.preparation,saved);
 const dirty=progressDirty||!!applicationGuard?.dirty;
 const savedRef=useRef(saved);savedRef.current=saved;
 function proceed(run:()=>void){if(busy||applicationGuard?.busy)return;if(dirty)setLeaving({run});else run();}
 useEffect(()=>{if(leaving){leavePrompt.current?.scrollIntoView({block:'nearest'});leavePrompt.current?.querySelector<HTMLButtonElement>('button')?.focus();}},[leaving]);
 useEffect(()=>{if(!dirty)setLeaving(undefined);},[dirty]);
 const [resume,setResume]=useState<ResumeState>();
 const [sessions,setSessions]=useState<PromptSession[]>([]);
 const [chats,setChats]=useState<SavedResearchChat[]>([]);
 const [busy,setBusy]=useState(false),[reading,setReading]=useState(false);
 const [error,setError]=useState(''),[notice,setNotice]=useState('');
 const openBrowser=useOriginalBrowser();
 const job=data?.job||initialJob;
 useEffect(()=>{const previous=document.activeElement as HTMLElement|null;dialog.current?.showModal();return()=>{dialog.current?.close();if(previous?.isConnected)previous.focus();};},[]);
 useEffect(()=>{let cancelled=false;
  const bridge=window.jobfindsme!;
  void Promise.all([bridge.getJobPreparation(workspaceId,initialJob.job_id),bridge.getResumeState(),bridge.listPromptSessions(workspaceId),bridge.listResearchChats(workspaceId)]).then(([value,state,proposals,rows])=>{
   if(cancelled)return;setData(value);setSaved(value.preparation);setResume(state);setSessions(proposals.filter(item=>proposalMatchesJob(item,value.job)));setChats(rows.map(fromStoredResearchChat).filter(item=>item.jobId===value.job.job_id));
  }).catch(e=>{if(!cancelled)setError(userError(e).message);});
  return()=>{cancelled=true;};
 },[workspaceId,initialJob.job_id]);
 useEffect(()=>{let cancelled=false;const refresh=()=>{void window.jobfindsme!.getJobPreparation(workspaceId,initialJob.job_id).then(value=>{if(!cancelled){const baseline=savedRef.current;setData(current=>current?{job:value.job,preparation:mergePreparation(current.preparation,baseline,value.preparation)}:value);setSaved(value.preparation);}}).catch(()=>{});};window.addEventListener('jfm:job-updated',refresh);return()=>{cancelled=true;window.removeEventListener('jfm:job-updated',refresh);};},[workspaceId,initialJob.job_id]);
 useEffect(()=>{if(!data||hasFullDescription(data.job)||autoRead.current)return;autoRead.current=true;void readJd();},[data?.job.job_id,applicationOpen]);
 async function readJd(){
  const source=sourceBrowserIdForSourceName(job.source.source_name);if(!source)return;
  setReading(true);setError('');
  try{await (source==='boss'?window.jobfindsme!.readBossDetail(job.apply_url,workspaceId,job.job_id):window.jobfindsme!.readSourceDetail(source,job.apply_url,workspaceId,job.job_id));if(!mounted.current)return;const fresh=await window.jobfindsme!.getJobPreparation(workspaceId,job.job_id);if(!mounted.current)return;setData(current=>current?{...current,job:fresh.job}:fresh);setNotice('岗位原文已补齐并保存在本机。');window.dispatchEvent(new Event('jfm:job-updated'));}
  catch(e){if(mounted.current)setError(userError(e).message);}finally{if(mounted.current)setReading(false);}
 }
 async function saveProgress(){if(!data||busy)return false;setBusy(true);setError('');setNotice('');
  try{const value=await window.jobfindsme!.saveJobPreparation(data.preparation);setData(value);setSaved(value.preparation);setNotice('进度和下一步已保存。');window.dispatchEvent(new Event('jfm:job-updated'));return true;}
  catch(e){setError(userError(e).message);return false;}finally{setBusy(false);}
 }
 async function save(event:React.FormEvent){event.preventDefault();await saveProgress();}
 async function saveAndContinue(){const action=leaving;if(applicationGuard?.dirty&&!await applicationGuard.save())return;if(progressDirty&&!await saveProgress())return;setLeaving(undefined);action?.run();}
 async function exportResume(){if(!data?.preparation.resume_version_id)return;setBusy(true);setError('');
  try{const versions=await window.jobfindsme!.listResumeVersions(workspaceId);const version=versions.find(row=>row.version_id===data.preparation.resume_version_id);if(version?.original_file&&version.source_document_id)await window.jobfindsme!.exportResumeSource({workspace_id:workspaceId,document_id:version.source_document_id});else await window.jobfindsme!.exportResume({workspace_id:workspaceId,version_id:data.preparation.resume_version_id,format:'pdf'});}catch(e){setError(userError(e).message);}finally{setBusy(false);}
 }
 const tiles=[{id:'resume-tailor',icon:'resume',title:'修改简历',description:'保留基础简历，准备岗位专属副本。'},{id:'interview-prep',icon:'interview',title:'模拟面试',description:'准备重点、逐题练习和回答点评。'},{id:'deep-research',icon:'research',title:'深度研究',description:'核对公司与岗位原文，保留来源。'}] as const;
 return <dialog ref={dialog} className={`preparation-dialog${applicationOpen?' application-dialog':''}`} aria-labelledby="preparation-title" onCancel={event=>{event.preventDefault();proceed(onClose);}} onClick={event=>{if(event.target===event.currentTarget)proceed(onClose);}}>
  <div className="preparation-shell">
   <header className="preparation-header"><div><span className="preparation-eyebrow">{applicationOpen?(initialApplicationView==='records'?"投递记录":"准备投递"):"岗位准备"}</span><h2 id="preparation-title">{job.title}</h2><p>{job.company} · {job.locations.join(' / ')||'地点未知'} · {formatSalary(job)}</p></div><button className="preparation-close" type="button" aria-label="关闭岗位准备" onClick={()=>proceed(onClose)} disabled={busy||applicationGuard?.busy}>×</button></header>
   <div className="preparation-body">{editingResume?<><button type="button" className="preparation-back" onClick={()=>setEditingResume(false)}>← 返回岗位准备</button><ResumePage embedded onChanged={setResume}/></>:<>
    <div className="preparation-navigation"><div className="preparation-source" hidden={applicationOpen}><span><i className={hasFullDescription(job)?'ready':''}/>{hasFullDescription(job)?'完整 JD 已保存':'JD 尚不完整'} · {job.source.source_name}</span><div>{!hasFullDescription(job)&&sourceBrowserIdForSourceName(job.source.source_name)&&<button type="button" disabled={reading} onClick={()=>void readJd()}>{reading?'正在读取…':'补全 JD'}</button>}<button type="button" disabled={!job.apply_url||busy} onClick={()=>proceed(()=>{onClose();openBrowser({sourceId:sourceBrowserIdForSourceName(job.source.source_name)||'web',url:job.apply_url,title:job.title});})}>核对原页 ↗</button></div></div>
    <button type="button" hidden={applicationOpen&&initialApplicationOpen} className="preparation-apply" disabled={!data||!!applicationGuard?.dirty||!!applicationGuard?.busy} onClick={()=>setApplicationOpen(value=>!value)}>{applicationOpen?"← 岗位准备":initialApplicationView==='records'?"投递记录 →":"准备投递 →"}</button></div>
    {applicationOpen&&data&&<ApplicationPreparation initialView={initialApplicationView} workspaceId={workspaceId} job={job} resumeId={data.preparation.resume_version_id} onGuard={setApplicationGuard} onOpenOriginal={()=>{const run=()=>{onClose();openBrowser({sourceId:sourceBrowserIdForSourceName(job.source.source_name)||'web',url:job.apply_url,title:job.title});};if(progressDirty)setLeaving({run});else run();}}/>}
    <div hidden={applicationOpen}><section className="preparation-section"><div className="preparation-section-heading"><h3>准备这个岗位</h3><span>{resume?.search_profile_state==='ready'?(data?.preparation.resume_version_id?'面试复用此岗位选用的简历':'基础简历已就绪'):'面试和研究可直接开始'}</span></div><div className="preparation-tiles">{tiles.map(tile=>{
     const previous=[...chats].sort((a,b)=>b.updatedAt.localeCompare(a.updatedAt)).find(chat=>chat.turns.some(turn=>turn.skillId===tile.id));
     return <div className="preparation-tile" key={tile.id}><Icon name={tile.icon}/><h4>{tile.title}</h4><p>{tile.description}</p><div className="preparation-tile-footer"><button type="button" disabled={!data||!resume||busy} onClick={()=>proceed(()=>onStart(job,tile.id,previous?.id))}>{tile.id==='resume-tailor'&&resume?.search_profile_state!=='ready'?'添加简历':previous?'继续上次':'开始准备'}<span aria-hidden="true"> →</span></button>{previous&&<button type="button" className="preparation-continue" disabled={!data||!resume||busy} onClick={()=>proceed(()=>onStart(job,tile.id))}>重新开始</button>}</div></div>;
    })}</div></section>
    {data?.preparation.resume_version_id&&<div className="preparation-document"><div><Icon name="resume"/><span><strong>此岗位使用的简历</strong><small>投递与面试复用同一版本。</small></span></div><button type="button" disabled={busy} onClick={()=>void exportResume()}>导出简历</button></div>}
    {!data?.preparation.resume_version_id&&sessions.length>0&&<details className="preparation-evidence"><summary>查看岗位修改提案（{sessions.length}）</summary>{sessions.map(session=><button key={session.session_id} onClick={()=>proceed(()=>onStart(job,'resume-tailor'))}>在我的简历中审阅修改 →</button>)}</details>}
    <details className="preparation-evidence"><summary>查看完整 JD</summary><h4>岗位原文</h4><div className="preparation-jd">{job.description||'暂无可读取的岗位正文，可以先核对原页。'}</div></details>
    <details ref={progress} className="preparation-progress"><summary><strong>进度与下一步</strong><span>{data?preparationStages[data.preparation.stage]:'正在读取…'}{data?.preparation.next_action&&` · ${data.preparation.next_action}`}{progressDirty&&' · 未保存'}</span></summary>{data?<form className="preparation-form" onSubmit={save}><div className="preparation-progress-fields"><label>当前进度<select value={data.preparation.stage} disabled={busy} onChange={event=>setData({...data,preparation:{...data.preparation,stage:event.target.value as typeof data.preparation.stage}})}>{Object.entries(preparationStages).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label><label>下一步<input maxLength={200} placeholder="例如：准备项目介绍" value={data.preparation.next_action} disabled={busy} onChange={event=>setData({...data,preparation:{...data.preparation,next_action:event.target.value}})}/></label><label>日期（可选）<input type="date" value={data.preparation.due_date||''} disabled={busy} onChange={event=>setData({...data,preparation:{...data.preparation,due_date:event.target.value||null}})}/></label></div><details><summary>添加备注</summary><textarea aria-label="岗位备注" maxLength={2000} value={data.preparation.note} disabled={busy} onChange={event=>setData({...data,preparation:{...data.preparation,note:event.target.value}})}/></details><div className="preparation-save-row"><span className="note">{progressDirty?'有修改尚未保存':'修改后再保存，打开原页不代表投递。'}</span><button type="submit" className="primary-button" disabled={busy||!progressDirty}>{busy?'保存中…':'保存修改'}</button></div></form>:<p className="note">正在读取本地记录…</p>}</details>
    </div>{error&&<p className="preparation-error" role="alert">{error}</p>}{notice&&<p className="preparation-notice" role="status">{notice}</p>}
   </>}{leaving&&<div ref={leavePrompt} className="preparation-leave" role="alert"><div><strong>还有未保存的修改</strong><p>保存进度与投递材料后继续，或放弃本次修改。</p></div><div><button type="button" disabled={busy} onClick={()=>{setLeaving(undefined);if(applicationGuard?.dirty){applicationGuard.reveal();requestAnimationFrame(()=>{const input=dialog.current?.querySelector<HTMLTextAreaElement>('textarea[aria-label="投递开场白"]');input?.scrollIntoView({block:'center'});input?.focus();});}else if(progress.current){progress.current.open=true;progress.current.querySelector<HTMLSelectElement>('select')?.focus();}}}>继续编辑</button><button type="button" disabled={busy} onClick={()=>{const action=leaving;setLeaving(undefined);action.run();}}>放弃修改</button><button type="button" className="primary-button" disabled={busy} onClick={()=>void saveAndContinue()}>{busy?'保存中…':'保存并继续'}</button></div></div>}</div>
  </div>
 </dialog>;
}
