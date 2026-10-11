import {useEffect,useState} from 'react';
import type {PromptPatchDecision,PromptSession} from '../../../shared/contracts';
import {resumeReviewCounts,resumeSections} from '../../../shared/resume-library';
import {userError} from '../../../shared/user-errors';

export function ResumeProposal({workspaceId,sessionId,onChanged,onBusyChange}:{workspaceId:string;sessionId:string;onChanged?:(session:PromptSession)=>void;onBusyChange?:(busy:boolean)=>void}){
 const [session,setSession]=useState<PromptSession>();
 const [currentVersion,setCurrentVersion]=useState<string>();
 const [message,setMessage]=useState(''),[error,setError]=useState('');
 const [busy,setBusy]=useState(false),[retry,setRetry]=useState(0);
 useEffect(()=>{onBusyChange?.(busy);return()=>onBusyChange?.(false);},[busy,onBusyChange]);
 useEffect(()=>{
  let active=true;setSession(undefined);setError('');setMessage('');
  void Promise.all([window.jobfindsme!.listPromptSessions(workspaceId),window.jobfindsme!.listResumeVersions(workspaceId)]).then(([rows,versions])=>{
   if(!active)return;setCurrentVersion(versions.find(version=>version.is_current)?.version_id);
   const next=rows.find(row=>row.session_id===sessionId&&row.workspace_id===workspaceId);
   if(next)setSession(next);else setError('这份修改记录暂时找不到，请重新读取。');
  }).catch(e=>{if(active)setError(userError(e).message);});
  return()=>{active=false;};
 },[workspaceId,sessionId,retry]);
 async function decide(id:string,decision:PromptPatchDecision){
  setBusy(true);setError('');setMessage('');
  try{const next=await window.jobfindsme!.decidePromptPatch(sessionId,id,decision);setSession(next);onChanged?.(next);}
  catch(e){setError(userError(e).message);}finally{setBusy(false);}
 }
 async function save(){
  setBusy(true);setError('');setMessage('');
  try{const version=await window.jobfindsme!.savePromptSession(sessionId);setSession(current=>current&&{...current,status:'saved',saved_version_id:version.version_id});setMessage(`已保存${session?.target_job_id?'岗位专属简历':'新的基础简历'}，原稿保留。`);window.dispatchEvent(new Event('jfm:job-updated'));}
  catch(e){setError(userError(e).message);}finally{setBusy(false);}
 }
 const stale=session?.status==='active'&&session.base_version_id!==currentVersion;
 const counts=session?resumeReviewCounts(session):undefined;
 return <section className="resume-proposal resume-proposal-review">
  <div className="proposal-heading"><div><h4>简历修改提案</h4><p>{session?.target_job_id?'逐项取舍，保存为岗位专属副本。':'逐项取舍，保存为新的基础版本。'}</p></div>{counts&&<span>{counts.accepted} 项已接受</span>}</div>
  {!session&&!error&&<p className="note" role="status">正在读取修改记录…</p>}
  {stale&&<p className="notice" role="alert">基础简历已更新，这份提案仅供参考。请从“我的简历 → AI 修改”基于最新版本重新生成。</p>}
  {session?.patches.map(patch=><details className={`proposal-patch ${patch.status}`} key={patch.patch_id} open={patch.status==='proposed'}><summary><strong>{resumeSections[patch.section]||patch.section}</strong><span>{patch.status==='accepted'?'已接受':patch.status==='rejected'?'保留原文':patch.needs_user_input.length?'待补充事实':'待审阅'}</span></summary><div className="proposal-diff"><div><small>原文</small>{patch.before.length?patch.before.map((line,index)=><p key={index}>{line}</p>):<p className="note">原文无此项</p>}</div><div><small>建议修改</small>{patch.after.map((line,index)=><p key={index}>{line}</p>)}</div></div><p className="proposal-rationale">{patch.rationale}</p>{patch.needs_user_input.length>0&&<p className="proposal-fact-gap">需要先核对：{patch.needs_user_input.join('；')}。确认前不能采用。</p>}{session.status==='active'&&!stale&&<div className="proposal-decisions">{patch.status==='proposed'?<><button disabled={busy} onClick={()=>void decide(patch.patch_id,'rejected')}>保留原文</button><button className="primary-button" disabled={busy||patch.needs_user_input.length>0} onClick={()=>void decide(patch.patch_id,'accepted')}>采用修改</button></>:<button disabled={busy} onClick={()=>void decide(patch.patch_id,'proposed')}>重新审阅</button>}</div>}</details>)}
  {session?.status==='active'&&<div className="proposal-save-bar"><p>{counts?.accepted?`仅保存已接受的 ${counts.accepted} 项，其余保留原文。`:'选择值得采用的修改，再保存。'}{counts?.pending?` ${counts.pending} 项待审阅。`:''}</p><button className="primary-button" disabled={busy||stale||!counts?.accepted} onClick={()=>void save()}>{busy?'处理中…':session.target_job_id?'保存岗位专属简历':'保存新版本'}</button></div>}
  {session?.saved_version_id&&<div className="proposal-save-bar"><p>已保存，可返回简历继续编辑与导出。</p><button disabled={busy} onClick={()=>{setBusy(true);setError('');void window.jobfindsme!.exportResume({workspace_id:workspaceId,version_id:session.saved_version_id!,format:'pdf',template:'classic'}).catch(e=>setError(userError(e).message)).finally(()=>setBusy(false));}}>导出 PDF</button></div>}
  {error&&<p className="notice" role="alert">{error}{!session&&<button onClick={()=>setRetry(value=>value+1)}>重新读取</button>}</p>}{message&&<p className="resume-feedback" role="status">{message}</p>}
 </section>;
}
