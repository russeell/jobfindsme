import {ResumeProposal} from "../research/ResumeProposal";
import {ResumePage} from '../resume/ResumePage';
import {useEffect,useRef,useState} from 'react';
import type {AssistantSkillId} from '../../../shared/assistant-skills';
import type {JobPreparationData,JobPreparationInput,MatchingPreview,PromptSession,ResumeState,SearchResultItem} from '../../../shared/contracts';
import {preparationHasChanges,preparationStages,proposalMatchesJob} from '../../../shared/job-preparation';
import {fromStoredResearchChat,type SavedResearchChat} from '../../../shared/research-chat-history';
import {hasFullDescription} from '../../../shared/research-reports';
import {sourceBrowserIdForSourceName} from '../../../shared/source-browser-policy';
import {userError} from '../../../shared/user-errors';
import {Icon} from '../shared/Icon';
import {useOriginalBrowser} from '../shared/Workbench';
import {formatSalary} from '../search/salary';

type Job=SearchResultItem['job'];
type Props={workspaceId:string;job:Job;onClose():void;onStart(job:Job,skill:AssistantSkillId,chatId?:string):void};
export function JobPreparation({workspaceId,job:initialJob,onClose,onStart}:Props){
 const dialog=useRef<HTMLDialogElement>(null);
 const progress=useRef<HTMLDetailsElement>(null);
 const leavePrompt=useRef<HTMLDivElement>(null);
 const [editingResume,setEditingResume]=useState(false);
 const [data,setData]=useState<JobPreparationData>();
 const [saved,setSaved]=useState<JobPreparationInput>();
 const [leaving,setLeaving]=useState<{run():void}>();
 const dirty=preparationHasChanges(data?.preparation,saved);
 function proceed(run:()=>void){if(busy||reading)return;if(dirty)setLeaving({run});else run();}
 useEffect(()=>{if(leaving){leavePrompt.current?.scrollIntoView({block:'nearest'});leavePrompt.current?.querySelector<HTMLButtonElement>('button')?.focus();}},[leaving]);
 useEffect(()=>{if(!dirty)setLeaving(undefined);},[dirty]);
 const [resume,setResume]=useState<ResumeState>();
 const [sessions,setSessions]=useState<PromptSession[]>([]);
 const [chats,setChats]=useState<SavedResearchChat[]>([]);
 const [match,setMatch]=useState<MatchingPreview>();
 const [busy,setBusy]=useState(false),[reading,setReading]=useState(false);
 const [matchMessage,setMatchMessage]=useState('');
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
 useEffect(()=>{let cancelled=false;setMatch(undefined);setMatchMessage('');
  if(!data||resume?.search_profile_state!=='ready')return;
  const bridge=window.jobfindsme!;
  void bridge.matchingRules(workspaceId).then(rules=>{const active=rules.versions.find(item=>item.rule_version_id===rules.active_rule_id);return bridge.previewMatching({workspace_id:workspaceId,job_id:job.job_id,weights:active?.weights||{skills:35,projects:30,education:15,experience:20}});}).then(result=>{if(!cancelled)setMatch(result);}).catch(()=>{if(!cancelled)setMatchMessage('本地匹配暂未算出，可继续准备。');});
  return()=>{cancelled=true;};
 },[workspaceId,data?.job.job_id,data?.job.description,resume?.current_version_id,resume?.search_profile_state]);
 useEffect(()=>{let cancelled=false;const refresh=()=>{void window.jobfindsme!.getJobPreparation(workspaceId,initialJob.job_id).then(value=>{if(!cancelled)setData(current=>current?{job:value.job,preparation:{...current.preparation,resume_version_id:value.preparation.resume_version_id}}:value);}).catch(()=>{});};window.addEventListener('jfm:job-updated',refresh);return()=>{cancelled=true;window.removeEventListener('jfm:job-updated',refresh);};},[workspaceId,initialJob.job_id]);
 async function readJd(){
  const source=sourceBrowserIdForSourceName(job.source.source_name);if(!source)return;
  setReading(true);setError('');
  try{await (source==='boss'?window.jobfindsme!.readBossDetail(job.apply_url,workspaceId,job.job_id):window.jobfindsme!.readSourceDetail(source,job.apply_url,workspaceId,job.job_id));setMatch(undefined);const fresh=await window.jobfindsme!.getJobPreparation(workspaceId,job.job_id);setData(current=>current?{...current,job:fresh.job}:fresh);setNotice('岗位原文已补齐并保存在本机。');window.dispatchEvent(new Event('jfm:job-updated'));}
  catch(e){setError(userError(e).message);}finally{setReading(false);}
 }
 async function saveProgress(){if(!data||busy)return false;setBusy(true);setError('');setNotice('');
  try{const value=await window.jobfindsme!.saveJobPreparation(data.preparation);setData(value);setSaved(value.preparation);setNotice('进度和下一步已保存。');window.dispatchEvent(new Event('jfm:job-updated'));return true;}
  catch(e){setError(userError(e).message);return false;}finally{setBusy(false);}
 }
 async function save(event:React.FormEvent){event.preventDefault();await saveProgress();}
 async function saveAndContinue(){const action=leaving;if(await saveProgress()){setLeaving(undefined);action?.run();}}
 async function exportResume(){if(!data?.preparation.resume_version_id)return;setBusy(true);setError('');
  try{await window.jobfindsme!.exportResume({workspace_id:workspaceId,version_id:data.preparation.resume_version_id,format:'pdf',template:'classic'});}catch(e){setError(userError(e).message);}finally{setBusy(false);}
 }
 const tiles=[{id:'resume-tailor',icon:'resume',title:'修改简历',description:'保留基础简历，准备岗位专属副本。'},{id:'interview-prep',icon:'interview',title:'模拟面试',description:'准备重点、逐题练习和回答点评。'},{id:'deep-research',icon:'research',title:'深度研究',description:'核对公司与岗位原文，保留来源。'}] as const;
 return <dialog ref={dialog} className="preparation-dialog" aria-labelledby="preparation-title" onCancel={event=>{event.preventDefault();proceed(onClose);}} onClick={event=>{if(event.target===event.currentTarget)proceed(onClose);}}>
  <div className="preparation-shell">
   <header className="preparation-header"><div><span className="preparation-eyebrow">岗位准备</span><h2 id="preparation-title">{job.title}</h2><p>{job.company} · {job.locations.join(' / ')||'地点未知'} · {formatSalary(job)}</p></div><button className="preparation-close" type="button" aria-label="关闭岗位准备" onClick={()=>proceed(onClose)} disabled={busy||reading}>×</button></header>
   <div className="preparation-body">{editingResume?<><button type="button" className="preparation-back" onClick={()=>setEditingResume(false)}>← 返回岗位准备</button><ResumePage onChanged={setResume}/></>:<>
    <div className="preparation-source"><span><i className={hasFullDescription(job)?'ready':''}/>{hasFullDescription(job)?'完整 JD 已保存':'JD 尚不完整'} · {job.source.source_name}</span><div>{!hasFullDescription(job)&&sourceBrowserIdForSourceName(job.source.source_name)&&<button type="button" disabled={reading} onClick={()=>void readJd()}>{reading?'正在读取…':'补全 JD'}</button>}<button type="button" disabled={!job.apply_url||busy||reading} onClick={()=>proceed(()=>{onClose();openBrowser({sourceId:sourceBrowserIdForSourceName(job.source.source_name)||'web',url:job.apply_url,title:job.title});})}>核对原页 ↗</button></div></div>
    <section className="preparation-section"><div className="preparation-section-heading"><h3>为这个机会做好准备</h3><span>{resume?.search_profile_state==='ready'?'已确认简历可复用':'面试和研究可直接开始'}</span></div><div className="preparation-tiles">{tiles.map(tile=>{
     const previous=[...chats].sort((a,b)=>b.updatedAt.localeCompare(a.updatedAt)).find(chat=>chat.turns.some(turn=>turn.skillId===tile.id));
     return <div className="preparation-tile" key={tile.id}><Icon name={tile.icon}/><h4>{tile.title}</h4><p>{tile.description}</p><div className="preparation-tile-footer"><button type="button" disabled={!data||!resume||busy||reading} onClick={()=>tile.id==='resume-tailor'&&resume?.search_profile_state!=='ready'?setEditingResume(true):proceed(()=>onStart(job,tile.id,previous?.id))}>{tile.id==='resume-tailor'&&resume?.search_profile_state!=='ready'?'添加简历':previous?'继续上次':'开始准备'}<span aria-hidden="true"> →</span></button>{previous&&<button type="button" className="preparation-continue" disabled={!data||!resume||busy||reading} onClick={()=>proceed(()=>onStart(job,tile.id))}>重新开始</button>}</div></div>;
    })}</div></section>
    {data?.preparation.resume_version_id&&<div className="preparation-document"><div><Icon name="resume"/><span><strong>岗位专属简历已保存</strong><small>与这个岗位关联，基础简历保持不变。</small></span></div><button type="button" disabled={busy} onClick={()=>void exportResume()}>导出 PDF</button></div>}
    {!data?.preparation.resume_version_id&&sessions.length>0&&<details className="preparation-evidence"><summary>查看岗位修改提案（{sessions.length}）</summary>{sessions.map(session=><ResumeProposal key={session.session_id} workspaceId={workspaceId} sessionId={session.session_id}/>)}</details>}
    <details className="preparation-evidence"><summary>岗位要求与已有材料</summary>{match?<><p className="note">本地匹配线索，依据已确认简历和当前 JD；不是录用概率。</p>{Object.entries(match.details).map(([key,value])=><div key={key} className="preparation-match"><strong>{{skills:'专业技能',projects:'项目经历',education:'教育经历',experience:'工作经历'}[key]||key}</strong><span>{value.explanation||'依据不足'}</span></div>)}</>:<p className="note">{resume?.search_profile_state==='ready'?(matchMessage||'正在核对本地材料。'):'尚无已确认简历，不推测你的个人匹配度。'}</p>}<h4>岗位原文</h4><div className="preparation-jd">{job.description||'暂无可读取的岗位正文，可以先核对原页。'}</div></details>
    <details ref={progress} className="preparation-progress"><summary><strong>进度与下一步</strong><span>{data?preparationStages[data.preparation.stage]:'正在读取…'}{data?.preparation.next_action&&` · ${data.preparation.next_action}`}{dirty&&' · 未保存'}</span></summary>{data?<form className="preparation-form" onSubmit={save}><div className="preparation-progress-fields"><label>当前进度<select value={data.preparation.stage} disabled={busy} onChange={event=>setData({...data,preparation:{...data.preparation,stage:event.target.value as typeof data.preparation.stage}})}>{Object.entries(preparationStages).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label><label>下一步<input maxLength={200} placeholder="例如：准备项目介绍" value={data.preparation.next_action} disabled={busy} onChange={event=>setData({...data,preparation:{...data.preparation,next_action:event.target.value}})}/></label><label>日期（可选）<input type="date" value={data.preparation.due_date||''} disabled={busy} onChange={event=>setData({...data,preparation:{...data.preparation,due_date:event.target.value||null}})}/></label></div><details><summary>添加备注</summary><textarea aria-label="岗位备注" maxLength={2000} value={data.preparation.note} disabled={busy} onChange={event=>setData({...data,preparation:{...data.preparation,note:event.target.value}})}/></details><div className="preparation-save-row"><span className="note">{dirty?'有修改尚未保存':'修改后再保存，打开原页不代表投递。'}</span><button type="submit" className="primary-button" disabled={busy||!dirty}>{busy?'保存中…':'保存修改'}</button></div></form>:<p className="note">正在读取本地记录…</p>}</details>
    {error&&<p className="preparation-error" role="alert">{error}</p>}{notice&&<p className="preparation-notice" role="status">{notice}</p>}
   </>}{leaving&&<div ref={leavePrompt} className="preparation-leave" role="alert"><div><strong>还有未保存的进度</strong><p>保存后继续，或放弃本次修改。</p></div><div><button type="button" disabled={busy} onClick={()=>{setLeaving(undefined);if(progress.current){progress.current.open=true;progress.current.querySelector<HTMLSelectElement>('select')?.focus();}}}>继续编辑</button><button type="button" disabled={busy} onClick={()=>{const action=leaving;setLeaving(undefined);action.run();}}>放弃修改</button><button type="button" className="primary-button" disabled={busy} onClick={()=>void saveAndContinue()}>{busy?'保存中…':'保存并继续'}</button></div></div>}</div>
  </div>
 </dialog>;
}
