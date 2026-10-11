import {ResumeOriginal} from "./ResumeOriginal";
import {ResumeEditorBoundary} from "./ResumeEditorBoundary";
import {lazy,Suspense} from "react";
const ResumeWordEditor=lazy(()=>import("./ResumeWordEditor").then(module=>({default:module.ResumeWordEditor})));
import {ResumeDocument} from "./ResumeDocument";
import {ResumeProposal} from "../research/ResumeProposal";
import {useEffect,useRef,useState} from "react";
import type {ResumeDraft,ResumeState,ResumeVersion,ResumeContent,ApplicationRecord,PromptSession,TrackedJob,SearchResultItem} from "../../../shared/contracts";
import {userError} from "../../../shared/user-errors";
import {Icon} from "../shared/Icon";
import {resumeContentChanged,resumeSections,resumeReviewCounts,moveResumeEntry,resumeImprovementDraft} from "../../../shared/resume-library";
import {ResumeImproveDialog,ResumeModal,ResumePreview} from "./ResumeDialogs";



export type ResumeOpenRequest={nonce:number;job?:SearchResultItem["job"];sessionId?:string;instruction?:string};
export function ResumePage({onChanged,embedded=false,active=true,onPrepare,openRequest}:{onChanged?:(state:ResumeState)=>void;embedded?:boolean;active?:boolean;onPrepare?:(job:SearchResultItem["job"])=>void;openRequest?:ResumeOpenRequest}={}){
  const [wordDirty,setWordDirty]=useState(false);
  const [editingOriginal,setEditingOriginal]=useState(false);
  const [state,setState]=useState<ResumeState>();
  const [current,setCurrent]=useState<ResumeVersion>();
  useEffect(()=>setEditingOriginal(false),[current?.version_id]);
  const [versions,setVersions]=useState<ResumeVersion[]>([]);
  const [sessions,setSessions]=useState<PromptSession[]>([]);
  const [applications,setApplications]=useState<ApplicationRecord[]>([]);
  const [jobs,setJobs]=useState<TrackedJob[]>([]);
  const [preview,setPreview]=useState<ResumeVersion>();
  const [editing,setEditing]=useState<{base:string;content:ResumeContent}>();
  const [discardEdit,setDiscardEdit]=useState(false);
  const [tab,setTab]=useState<"base"|"tailored">("base");
  const [section,setSection]=useState<keyof ResumeContent>("experience");
  const [reviewBusy,setReviewBusy]=useState(false);
  const [improveInstruction,setImproveInstruction]=useState('');
  const [improve,setImprove]=useState(false),[review,setReview]=useState<PromptSession>();
  const [improveJob,setImproveJob]=useState<SearchResultItem["job"]>();
  const [generating,setGenerating]=useState(false),[generationMessage,setGenerationMessage]=useState('');
  const generation=useRef<string|undefined>(undefined);
  const openedRequest=useRef<number|undefined>(undefined);
  const reviewAnchor=useRef<HTMLElement>(null);
  function stopGeneration(){const id=generation.current;if(!id)return;generation.current=undefined;setGenerating(false);setGenerationMessage('已停止，原简历未改动。可以调整要求后重新生成。');void window.jobfindsme!.cancelResearchChat(id).catch(reason=>setError(userError(reason).message));}
  useEffect(()=>()=>{const id=generation.current;generation.current=undefined;if(id)void window.jobfindsme!.cancelResearchChat(id).catch(()=>{});},[]);
  useEffect(()=>{if(!active)stopGeneration();},[active]);
  useEffect(()=>{if(generating||review)requestAnimationFrame(()=>reviewAnchor.current?.scrollIntoView({block:'start'}));},[generating,review?.session_id]);
  useEffect(()=>{
    if(!active||!state||!openRequest||openedRequest.current===openRequest.nonce)return;
    if(generating||reviewBusy)return;
    openedRequest.current=openRequest.nonce;setGenerationMessage('');setMessage('');
    if(wordDirty||editing){setMessage('请先保存当前草稿，再进行 AI 修改；已有输入仍保留。');return;}
    const existing=openRequest.sessionId?sessions.find(row=>row.session_id===openRequest.sessionId):openRequest.job?sessions.find(row=>row.target_job_id===openRequest.job!.job_id&&row.status==='active'):undefined;
    if(openRequest.sessionId&&!existing){setMessage('未找到这份修改记录，原简历与其他提案仍保留。');return;}
    setTab(existing?.target_job_id||openRequest.job?'tailored':'base');setImproveJob(existing?jobs.find(row=>row.job.job_id===existing.target_job_id)?.job:openRequest.job);setImproveInstruction(openRequest.instruction||'');
    if(existing){setReview(existing);return;}
    setReview(undefined);
    if(current&&!draft)setImprove(true);else setMessage('先导入简历，再生成修改稿。');
  },[active,state,openRequest,generating,reviewBusy]);
  async function generate(job:SearchResultItem["job"]|undefined,instruction:string,connectionId?:string){
    if(!state?.workspace_id||!current||!connectionId||generation.current||wordDirty)return;
    const workspace=state.workspace_id,id=crypto.randomUUID();generation.current=id;
    setImprove(false);setImproveJob(job);setImproveInstruction(instruction);setReview(undefined);setGenerating(true);setGenerationMessage('正在根据简历经历生成修改建议…');setError('');
    try{
      const result=await window.jobfindsme!.runResearchChat({request_id:id,session_id:`resume-${id}`,workspace_id:workspace,connection_id:connectionId,skill_id:'resume-tailor',research:false,job_id:job?.job_id,question:resumeImprovementDraft(instruction,job),history:[],source_ids:[]});
      if(generation.current!==id)return;
      if(!result.resumeProposalId)throw Error('本次没有生成可审阅的修改稿。原简历未改动，请调整要求后重试。');
      const rows=await window.jobfindsme!.listPromptSessions(workspace);
      if(generation.current!==id)return;
      const proposal=rows.find(row=>row.session_id===result.resumeProposalId&&row.workspace_id===workspace);
      if(!proposal)throw Error('修改稿暂时无法读取，请从本页的待审阅记录中重新打开。');
      setReview(proposal);setGenerationMessage('');await reload();
    }catch(reason){if(generation.current===id)setGenerationMessage(userError(reason).message);}
    finally{if(generation.current===id){generation.current=undefined;setGenerating(false);}}
  }
  const loadSequence=useRef(0);
  const labels=resumeSections;
  const [busy,setBusy]=useState(false),[message,setMessage]=useState(""),[error,setError]=useState(""),[confirmClear,setConfirmClear]=useState(false);
  const draft:ResumeDraft|null|undefined=state?.active_draft;
  async function reload(){
    const sequence=++loadSequence.current;
    const next=await window.jobfindsme!.getResumeState();
    const workspace=next.workspace_id;
    const [versions,proposals,rows,records]=workspace?await Promise.all([
      window.jobfindsme!.listResumeVersions(workspace),
      embedded?Promise.resolve([]):window.jobfindsme!.listPromptSessions(workspace),
      embedded?Promise.resolve([]):window.jobfindsme!.listJobTracking(workspace),
      embedded?Promise.resolve([]):window.jobfindsme!.listApplicationRecords(workspace),
    ]):[[],[],[],[]];
    if(sequence!==loadSequence.current)return;
    setVersions(versions);setState(next);onChanged?.(next);setError("");
    setSessions(proposals.filter(p=>p.status!=="cancelled"&&(p.patches.length>0||p.saved_version_id)));
    setJobs(rows);setApplications(records);setCurrent(versions.find(version=>version.is_current));

  }
  useEffect(()=>{if(!active){setPreview(undefined);setImprove(false);setReview(undefined);return;}const refresh=()=>void reload().catch(reason=>setError(userError(reason).message));refresh();window.addEventListener('jfm:job-updated',refresh);return()=>{loadSequence.current++;window.removeEventListener('jfm:job-updated',refresh);};},[active]);
  function closeEdit(){if(editChanged)setDiscardEdit(true);else setEditing(undefined);}
  async function saveEdit(){if(!editing||!state?.workspace_id)return;await run(async()=>{await window.jobfindsme!.saveResumeVersion({workspace_id:state.workspace_id!,base_version_id:editing.base,content:editing.content});setEditing(undefined);setDiscardEdit(false);await reload();window.dispatchEvent(new Event('jfm:job-updated'));setMessage('已保存为新的基础版本，旧版本保留。');});}
  const tailored=sessions.filter(p=>p.target_job_id);
  const pending=sessions.filter(p=>!p.target_job_id&&p.status==="active");
  const editStale=!!editing&&editing.base!==current?.version_id;
  const editChanged=!!editing&&!!current&&resumeContentChanged(current.content,editing.content);
  async function run(action:()=>Promise<void>){setBusy(true);setError("");setMessage("");try{await action();}catch(reason){setError(userError(reason).message);}finally{setBusy(false);}}
  async function importResume(){await run(async()=>{const value=await window.jobfindsme!.chooseAndImportResume();if(value){await reload();setMessage("文件已在本机保留；提取结果用于匹配，不改动原文件。重复文件不会覆盖当前版本。");}});}
  async function confirm(){if(!draft)return;await run(async()=>{await window.jobfindsme!.useOriginalResume(draft.workspace_id,draft.profile_id);await reload();setMessage("已使用原文件。后续修改会保存为独立版本。");});}
  async function abandon(){if(!draft)return;await run(async()=>{await window.jobfindsme!.abandonResume(draft.workspace_id,draft.profile_id);await reload();setMessage("本次导入已放弃。");});}
  async function clearResume(){if(!state?.workspace_id)return;await run(async()=>{await window.jobfindsme!.clearCurrentResume(state.workspace_id!);await reload();setConfirmClear(false);setMessage("已停止使用当前简历，历史版本和岗位材料保留。");});}
  return <div className={`resume-page resume-maintenance simple-profile${current&&!draft?' resume-has-document':''}${embedded?' embedded':''}`}>
    {!embedded&&<div className="heading-row resume-heading"><div><h1>我的简历</h1><p>维护真实经历，为每个机会准备合适的表达。</p></div></div>}
    {error&&<p className="notice" role="alert">{error} <button type="button" disabled={busy} onClick={()=>void run(reload)}>重新读取</button></p>}{message&&!draft&&<p className="resume-feedback" role="status">{message}</p>}
    {!state&&!error?<p className="note" role="status">正在读取本地简历…</p>:<>
    {(!draft&&embedded&&current)&&<div className="resume-context"><span><i className={draft?'pending':''}/>{draft?'待核对':'已保存'}</span><button type="button" disabled={busy||!!editing} onClick={()=>void importResume()}>{busy?'处理中…':'替换文件'}</button></div>}
    {draft&&<><div className="resume-document-bar"><div><strong>此前导入的文件</strong><small>选择使用后，本机提取的文字将用于匹配。</small></div><div className="button-row"><button disabled={busy} onClick={()=>void abandon()}>暂不使用</button><button disabled={busy} onClick={()=>void importResume()}>替换文件</button><button className="primary-button" disabled={busy} onClick={()=>void confirm()}>使用这份简历</button></div></div><ResumeOriginal workspaceId={draft.workspace_id} documentId={draft.document_id}/></>}

    {!embedded&&!draft&&<nav className="resume-library-tabs" aria-label="简历分类"><button aria-current={tab==='base'?'page':undefined} disabled={!!editing||generating||reviewBusy} onClick={()=>{setReview(undefined);setGenerationMessage('');setTab('base');}}>基础简历</button><button aria-current={tab==='tailored'?'page':undefined} disabled={!!editing||generating||reviewBusy} onClick={()=>{setReview(undefined);setGenerationMessage('');setTab('tailored');}}>岗位专属{tailored.length>0&&<span>{tailored.length}</span>}</button></nav>}

    {!embedded&&(generating||generationMessage||review)&&<section ref={reviewAnchor} className="resume-ai-workspace" aria-label="AI 修改工作区">
      <header><div><strong>AI 修改</strong><p>{review?.target_title||improveJob?.title||'基础简历'} · 原稿保留，采用后保存修改</p></div><div className="button-row">{generating?<button onClick={stopGeneration}>停止生成</button>:<><button disabled={reviewBusy||wordDirty} onClick={()=>setImprove(true)}>调整要求</button><button disabled={reviewBusy} onClick={()=>{setReview(undefined);setGenerationMessage('');}}>返回简历</button></>}</div></header>
      {generationMessage&&<p className="resume-ai-status" role="status">{generating&&<span className="resume-ai-pulse"/>}{generationMessage}</p>}
      {review&&state?.workspace_id&&<ResumeProposal key={review.session_id} workspaceId={state.workspace_id} sessionId={review.session_id} onBusyChange={setReviewBusy} onChanged={next=>{setReview(next);setSessions(rows=>rows.map(row=>row.session_id===next.session_id?next:row));}}/>}
    </section>}
    {editing&&<ResumeModal title="编辑基础简历" busy={busy} wide onClose={closeEdit}><section className="resume-edit-workspace">{editStale&&<p className="notice" role="alert">基础简历已在其他操作中更新。当前输入仍保留；请复制需要的内容，取消编辑后从最新版本继续。</p>}<div className="resume-edit-heading"><div><h2>编辑基础简历</h2><p>保存为新版本，原稿保留。</p></div><span>{editChanged?'有未保存的修改':'尚未修改'}</span></div><div className="resume-edit-grid"><nav aria-label="简历编辑章节">{Object.entries(labels).map(([key,label])=><button key={key} aria-pressed={section===key} onClick={()=>setSection(key as keyof ResumeContent)}>{label}<small>{editing.content[key as keyof ResumeContent].filter(line=>line.trim()).length}</small></button>)}</nav><div className="resume-entry-editor"><p className="note">保留真实内容；分区不对时，可将整条内容移到正确章节。</p>{editing.content[section].map((value,index)=><div className="resume-entry-edit" key={`${section}:${index}`}><label><span>{labels[section]} · {index+1}</span><textarea aria-label={`${labels[section]} ${index+1} 内容`} disabled={busy} value={value} onChange={e=>setEditing({...editing,content:{...editing.content,[section]:editing.content[section].map((line,i)=>i===index?e.target.value:line)}})}/></label><label className="resume-move-entry">移动到<select disabled={busy} aria-label={`移动第 ${index+1} 条内容`} value={section} onChange={e=>setEditing({...editing,content:moveResumeEntry(editing.content,section,index,e.target.value as keyof ResumeContent)})}>{Object.entries(labels).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label></div>)}<button disabled={busy} onClick={()=>setEditing({...editing,content:{...editing.content,[section]:[...editing.content[section],'']}})}>＋ 添加内容</button></div></div><footer>{discardEdit?<span role="alert">放弃未保存的修改？ <button onClick={()=>setDiscardEdit(false)}>继续编辑</button><button onClick={()=>{setDiscardEdit(false);setEditing(undefined);}}>放弃修改</button></span>:<span>保存为新版本，原稿保留。</span>}<div><button disabled={busy} onClick={closeEdit}>取消编辑</button><button className="primary-button" disabled={busy||editStale||!editChanged||!Object.values(editing.content).some(lines=>lines.some(line=>line.trim()))} onClick={()=>void saveEdit()}>{busy?'保存中…':'保存修改'}</button></div></footer></section></ResumeModal>}
    {editingOriginal&&current?.original_file&&<div className="resume-document-bar"><span className="note">正在编辑文字副本，保存会生成新版本。</span><button disabled={wordDirty} title={wordDirty?'请先保存或撤销文档修改':undefined} onClick={()=>setEditingOriginal(false)}>返回原文件</button></div>}
    {current&&!draft&&(embedded||tab==='base')&&<section hidden={!embedded&&(generating||!!generationMessage||!!review)} className="resume-current resume-ready"><>{current.original_file&&current.source_document_id&&state?.workspace_id&&!editingOriginal?<ResumeOriginal workspaceId={state.workspace_id} documentId={current.source_document_id} version={current} onEdit={()=>setEditingOriginal(true)} onImprove={()=>{setImproveJob(undefined);setImproveInstruction('');setImprove(true);}}/>:!embedded&&state?.workspace_id?<ResumeEditorBoundary fallback={<ResumeDocument workspaceId={state.workspace_id} version={current}/>}><Suspense fallback={<p role="status">正在打开文档…</p>}><ResumeWordEditor key={state.workspace_id} workspaceId={state.workspace_id} version={current} active={active} onSaved={reload} onDirty={setWordDirty} onOrganize={()=>{setSection(current.content.experience.length?"experience":"projects");setEditing({base:current.version_id,content:structuredClone(current.content)});}} onImprove={!embedded?(instruction)=>{setImproveJob(undefined);setImproveInstruction(instruction||'');setImprove(true);}:undefined}/></Suspense></ResumeEditorBoundary>:<div className="resume-summary">{Object.entries(labels).filter(([key])=>current.content[key as keyof ResumeContent]?.some(line=>line.trim())).map(([key,label])=><section key={key}><h3>{label}</h3>{current.content[key as keyof ResumeContent].filter(line=>line.trim()).map((line,index)=><p key={index}>{line}</p>)}</section>)}</div>}</><p className="note resume-local-note">保存的简历与岗位材料可复用到匹配、修改建议和面试。</p><details className="resume-manage"><summary>更多操作</summary><div className="button-row"><button disabled={busy||wordDirty} onClick={()=>void importResume()}>替换文件</button><button type="button" disabled={busy||wordDirty} onClick={()=>setConfirmClear(value=>!value)}>清除当前简历</button></div>{confirmClear&&<div className="history-confirm" role="alert"><p>清除当前简历？历史版本和岗位材料会保留。</p><div className="button-row"><button disabled={busy} onClick={()=>void clearResume()}>确认清除</button><button disabled={busy||wordDirty} onClick={()=>setConfirmClear(false)}>取消</button></div></div>}</details></section>}
    {!current&&!draft&&state&&(embedded||tab==='base')&&<section className="resume-import">
      <span className="resume-import-icon"><Icon name="resume"/></span><h3>让岗位更贴合你的经历</h3><p>导入 PDF 或 Word，原文件直接保留；需要修改时再编辑副本。</p>

      <button type="button" className="primary-button" disabled={busy||!!editing} onClick={()=>void importResume()}>{busy?'正在解析…':'选择简历文件'}</button><small>PDF、DOCX、Markdown、TXT</small>
      <details className="resume-file-help"><summary>文件要求与隐私</summary><p>{state.capabilities.detail}</p><p>原文件保存在本机，后台提取不改变版式；主动编辑时生成副本，复杂 PDF 转为文字后可能需要调整。公开检索词不包含简历正文和联系方式。不导入也能直接按关键词找岗位。</p></details>
    </section>}
    </>}
    {!embedded&&!generating&&!generationMessage&&!review&&state&&!editing&&!draft&&tab==='base'&&pending.length>0&&<section className="resume-library-section"><h2>待审阅的 AI 修改 <span>{pending.length}</span></h2>{pending.map(session=><article className="resume-library-card" key={session.session_id}><div><strong>基础简历</strong><p className="note">{resumeReviewCounts(session).accepted} 项已接受 · {resumeReviewCounts(session).pending} 项待审阅</p></div><button disabled={generating||reviewBusy||wordDirty} onClick={()=>{setGenerationMessage('');setImproveJob(jobs.find(row=>row.job.job_id===session.target_job_id)?.job);setImproveInstruction('');setReview(session);}}>审阅修改 →</button></article>)}</section>}
    {!embedded&&!generating&&!generationMessage&&!review&&state&&!editing&&!draft&&tab==='tailored'&&<section className="resume-tailored-list"><div className="resume-document-bar"><div><strong>岗位专属简历</strong><small>针对岗位修改，基础简历保持不变。</small></div>{current&&!embedded&&<button className="primary-button" disabled={wordDirty||generating||reviewBusy} onClick={()=>{setImproveInstruction('');setImproveJob(undefined);setImprove(true);}}>AI 修改</button>}</div>{tailored.length?tailored.map(session=>{const version=versions.find(v=>v.version_id===session.saved_version_id);const job=jobs.find(j=>j.job.job_id===session.target_job_id)?.job;const counts=resumeReviewCounts(session);const status=version?`修改于 ${new Date(version.created_at).toLocaleDateString()} · ${applications.some(a=>a.resume_version_id===version.version_id&&a.status==='resume_sent')?'已用于投递（本人确认）':'未记录投递'}`:session.saved_version_id?'已保存，版本已归档':counts.pending?`${counts.pending} 项待审阅`:counts.accepted?`${counts.accepted} 项已接受，待保存`:'已保留原文';return <article className="resume-library-card" key={session.session_id}><div><small>{job?.company||'目标岗位'}</small><strong>{job?.title||session.target_title||'岗位专属稿'}</strong><p className="note">{status}</p></div><div className="button-row">{job&&onPrepare&&<button onClick={()=>onPrepare(job)}>查看岗位</button>}{version?<button onClick={()=>setPreview(version)}>预览与导出</button>:session.status==='active'&&<button disabled={generating||reviewBusy||wordDirty} onClick={()=>{setGenerationMessage('');setImproveJob(jobs.find(row=>row.job.job_id===session.target_job_id)?.job);setImproveInstruction('');setReview(session);}}>审阅修改 →</button>}</div></article>;}):<div className="resume-library-empty"><Icon name="resume"/><h3>给目标岗位一份专属表达</h3><p>{current?'选择一个岗位，AI 会根据真实经历提出修改，由你决定采用哪些。':'先导入基础简历，再为目标岗位准备独立稿。'}</p>{current&&!embedded?<button disabled={wordDirty||generating||reviewBusy} onClick={()=>{setImproveInstruction('');setImproveJob(undefined);setImprove(true);}}>开始 AI 修改 →</button>:<button onClick={()=>setTab('base')}>去完善基础简历 →</button>}</div>}</section>}
    {preview&&state?.workspace_id&&<ResumePreview workspaceId={state.workspace_id} version={preview} onClose={()=>setPreview(undefined)}/>}
    {improve&&!embedded&&<ResumeImproveDialog initialJob={improveJob} workspaceId={state!.workspace_id!} initialInstruction={improveInstruction} initialTarget={improveJob||review?.target_job_id||tab==='tailored'?'job':'general'} jobs={jobs.map(row=>row.job)} onClose={()=>setImprove(false)} onStart={(job,instruction,connectionId)=>void generate(job,instruction,connectionId)}/>}


  </div>;
}
