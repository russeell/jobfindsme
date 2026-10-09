import {ResumeProposal} from "../research/ResumeProposal";
import {useEffect,useRef,useState} from "react";
import type {ResumeDraft,ResumeState,ResumeVersion,ResumeContent,ApplicationRecord,PromptSession,TrackedJob,SearchResultItem} from "../../../shared/contracts";
import {userError} from "../../../shared/user-errors";
import {Icon} from "../shared/Icon";
import {resumeContentChanged,resumeSections,resumeReviewCounts} from "../../../shared/resume-library";
import {ResumeImproveDialog,ResumeModal,ResumePreview} from "./ResumeDialogs";

const factLabels:Record<string,string>={basic_information:"基本信息（仅本机保存）",skill_detail:"技能描述",skill:"识别到的技能",project:"项目经历",experience:"工作经历",education:"教育经历"};

export function ResumePage({onChanged,embedded=false,active=true,onPrepare,onImprove}:{onChanged?:(state:ResumeState)=>void;embedded?:boolean;active?:boolean;onPrepare?:(job:SearchResultItem["job"])=>void;onImprove?:(job:SearchResultItem["job"]|undefined,instruction:string)=>void}={}){
  const [state,setState]=useState<ResumeState>();
  const [current,setCurrent]=useState<ResumeVersion>();
  const [versions,setVersions]=useState<ResumeVersion[]>([]);
  const [sessions,setSessions]=useState<PromptSession[]>([]);
  const [applications,setApplications]=useState<ApplicationRecord[]>([]);
  const [jobs,setJobs]=useState<TrackedJob[]>([]);
  const [preview,setPreview]=useState<ResumeVersion>();
  const [editing,setEditing]=useState<{base:string;content:ResumeContent}>();
  const [reviewSection,setReviewSection]=useState('');
  const [restore,setRestore]=useState<ResumeVersion>();
  const [tab,setTab]=useState<"base"|"tailored">("base");
  const [section,setSection]=useState<keyof ResumeContent>("experience");
  const [reviewBusy,setReviewBusy]=useState(false);
  const [improve,setImprove]=useState(false),[review,setReview]=useState<PromptSession>();
  const loadSequence=useRef(0);
  const labels=resumeSections;
  const [accepted,setAccepted]=useState<Set<string>>(new Set());
  const [corrections,setCorrections]=useState<Record<string,string>>({});
  const [busy,setBusy]=useState(false),[message,setMessage]=useState(""),[error,setError]=useState(""),[confirmClear,setConfirmClear]=useState(false);
  const draft:ResumeDraft|null|undefined=state?.active_draft;
  const reviewedDraft=useRef<string|null>(null);
  const factGroups=['basic_information','experience','project','education','skill_detail','skill'].filter(type=>draft?.facts.some(fact=>fact.fact_type===type));
  const activeReviewSection=factGroups.includes(reviewSection)?reviewSection:factGroups[0];
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
    const draftKey=next.active_draft?`${workspace}:${next.active_draft.profile_id}`:null;
    if(next.active_draft&&draftKey!==reviewedDraft.current){setReviewSection('');setAccepted(new Set(next.active_draft.facts.map(f=>f.fact_id)));setCorrections(Object.fromEntries(next.active_draft.facts.map(f=>[f.fact_id,f.value])));}
    reviewedDraft.current=draftKey;
  }
  useEffect(()=>{if(!active){setPreview(undefined);setImprove(false);setReview(undefined);return;}const refresh=()=>void reload().catch(reason=>setError(userError(reason).message));refresh();window.addEventListener('jfm:job-updated',refresh);return()=>{loadSequence.current++;window.removeEventListener('jfm:job-updated',refresh);};},[active]);
  async function saveEdit(){if(!editing||!state?.workspace_id)return;await run(async()=>{await window.jobfindsme!.saveResumeVersion({workspace_id:state.workspace_id!,base_version_id:editing.base,content:editing.content});setEditing(undefined);await reload();window.dispatchEvent(new Event('jfm:job-updated'));setMessage('已保存为新的基础版本，旧版本保留。');});}
  const tailored=sessions.filter(p=>p.target_job_id);
  const pending=sessions.filter(p=>!p.target_job_id&&p.status==="active");
  const editStale=!!editing&&editing.base!==current?.version_id;
  const editChanged=!!editing&&!!current&&resumeContentChanged(current.content,editing.content);
  const tailoredIds=new Set(tailored.map(p=>p.saved_version_id).filter(Boolean));
  const history=versions.filter(v=>!v.is_current&&!tailoredIds.has(v.version_id));
  async function run(action:()=>Promise<void>){setBusy(true);setError("");setMessage("");try{await action();}catch(reason){setError(userError(reason).message);}finally{setBusy(false);}}
  async function importResume(){await run(async()=>{const value=await window.jobfindsme!.chooseAndImportResume();if(value){await reload();setMessage(value.status==='confirmed'?"此文件已确认过，没有重复导入。可编辑当前简历，或在历史版本中预览、恢复原稿。":"请核对解析内容。确认前，新导入内容不会参与检索。");}});}
  async function confirm(){if(!draft)return;await run(async()=>{await window.jobfindsme!.confirmResume({workspace_id:draft.workspace_id,profile_id:draft.profile_id,accepted_fact_ids:[...accepted],corrections:Object.fromEntries([...accepted].map(id=>[id,corrections[id]??""]))});await reload();setMessage("简历已确认，下一次检索可使用其中的技能和经历。");});}
  async function abandon(){if(!draft)return;await run(async()=>{await window.jobfindsme!.abandonResume(draft.workspace_id,draft.profile_id);await reload();setMessage("本次导入已放弃。");});}
  async function clearResume(){if(!state?.workspace_id)return;await run(async()=>{await window.jobfindsme!.clearCurrentResume(state.workspace_id!);await reload();setConfirmClear(false);setMessage("当前简历已清除；现在可不使用简历搜索。已有检索和研究快照保留。");});}
  return <div className={`resume-page resume-maintenance simple-profile${embedded?' embedded':''}`}>
    {!embedded&&<div className="heading-row resume-heading"><div><h1>我的简历</h1><p>维护真实经历，为每个机会准备合适的表达。</p></div></div>}
    {error&&<p className="notice" role="alert">{error} <button type="button" disabled={busy} onClick={()=>void run(reload)}>重新读取</button></p>}{message&&<p className="resume-feedback" role="status">{message}</p>}
    {!state&&!error?<p className="note" role="status">正在读取本地简历…</p>:<>
    {(draft||(embedded&&current))&&<div className="resume-context"><span><i className={draft?'pending':''}/>{draft?'待核对':`已确认 · v${current!.version_number}`}</span><button type="button" disabled={busy||!!editing} onClick={()=>void importResume()}>{busy?'处理中…':'替换文件'}</button></div>}
    {draft&&<section className="resume-confirm resume-review">
      <h3>核对解析内容</h3><p className="note">{draft.file_name} · 已选择 {accepted.size} / {draft.facts.length} 条。取消勾选不准确的内容，也可直接修改。</p>
      <div className="resume-review-tools"><button type="button" disabled={busy} onClick={()=>setAccepted(new Set(draft.facts.map(fact=>fact.fact_id)))}>全选</button><button type="button" disabled={busy} onClick={()=>setAccepted(new Set())}>取消全选</button></div>
      <nav className="resume-review-sections" aria-label="核对章节">{factGroups.map(type=><button key={type} aria-pressed={activeReviewSection===type} onClick={()=>setReviewSection(type)}>{factLabels[type]}<small>{draft.facts.filter(fact=>fact.fact_type===type).length}</small></button>)}</nav><div className="fact-list resume-fact-scroll">{factGroups.filter(type=>type===activeReviewSection).map(type=>{const facts=draft.facts.filter(fact=>fact.fact_type===type);const label=factLabels[type]??'简历信息';return <section className="fact-group" key={type} aria-label={label}><h3>{label}<small>{facts.length} 条</small></h3>{facts.map((fact,index)=><div className="fact-row" key={fact.fact_id}><input type="checkbox" disabled={busy} aria-label={`${label} ${index+1}`} checked={accepted.has(fact.fact_id)} onChange={event=>setAccepted(previous=>{const next=new Set(previous);event.target.checked?next.add(fact.fact_id):next.delete(fact.fact_id);return next;})}/><textarea aria-label={`${label} ${index+1} 内容`} value={corrections[fact.fact_id]??fact.value} disabled={!accepted.has(fact.fact_id)||busy} onChange={event=>setCorrections(previous=>({...previous,[fact.fact_id]:event.target.value}))}/></div>)}</section>;})}</div>
      <div className="resume-review-footer"><span>{current?'确认后更新当前简历；原版本仍保留。':'确认前不会用于岗位匹配。'}</span><div><button type="button" disabled={busy} onClick={()=>void abandon()}>暂不使用</button><button type="button" className="primary-button" disabled={busy||!accepted.size} onClick={()=>void confirm()}>{busy?'处理中…':'确认并使用'}</button>{factGroups.indexOf(activeReviewSection)<factGroups.length-1&&<button disabled={busy} onClick={()=>setReviewSection(factGroups[factGroups.indexOf(activeReviewSection)+1])}>核对下一项 →</button>}</div></div>
    </section>}
    {!embedded&&!draft&&<nav className="resume-library-tabs" aria-label="简历分类"><button aria-current={tab==='base'?'page':undefined} disabled={!!editing} onClick={()=>setTab('base')}>基础简历</button><button aria-current={tab==='tailored'?'page':undefined} disabled={!!editing} onClick={()=>setTab('tailored')}>岗位专属{tailored.length>0&&<span>{tailored.length}</span>}</button></nav>}
    {current&&!draft&&!embedded&&tab==='base'&&!editing&&<div className="resume-document-bar"><div><strong>基础简历</strong><small>v{current.version_number} · {new Date(current.created_at).toLocaleDateString()} · 已确认</small></div><div className="button-row"><button disabled={busy} onClick={()=>{setSection(current.content.experience.length?'experience':'projects');setEditing({base:current.version_id,content:structuredClone(current.content)});}}>编辑</button><button disabled={busy} onClick={()=>setPreview(current)}>预览与导出</button>{onImprove&&<button className="primary-button" disabled={busy} onClick={()=>setImprove(true)}>AI 修改</button>}</div></div>}
    {editing&&<section className="resume-edit-workspace">{editStale&&<p className="notice" role="alert">基础简历已在其他操作中更新。当前输入仍保留；请复制需要的内容，取消编辑后从最新版本继续。</p>}<div className="resume-edit-heading"><div><h2>编辑基础简历</h2><p>保存为新版本，原版本仍可恢复。</p></div><span>{editChanged?'有未保存的修改':'尚未修改'}</span></div><div className="resume-edit-grid"><nav aria-label="简历编辑章节">{Object.entries(labels).map(([key,label])=><button key={key} aria-pressed={section===key} onClick={()=>setSection(key as keyof ResumeContent)}>{label}<small>{editing.content[key as keyof ResumeContent].filter(line=>line.trim()).length}</small></button>)}</nav><label><strong>{labels[section]}</strong><small>每行一条，只填写真实信息。</small><textarea aria-label={labels[section]} disabled={busy} value={editing.content[section].join('\n')} onChange={e=>setEditing({...editing,content:{...editing.content,[section]:e.target.value.split('\n')}})}/></label></div><footer><span>切换页面会保留当前编辑。</span><div><button disabled={busy} onClick={()=>setEditing(undefined)}>取消编辑</button><button className="primary-button" disabled={busy||editStale||!editChanged||!Object.values(editing.content).some(lines=>lines.some(line=>line.trim()))} onClick={()=>void saveEdit()}>{busy?'保存中…':'保存新版本'}</button></div></footer></section>}
    {current&&!draft&&!editing&&(embedded||tab==='base')&&<section className="resume-current resume-ready"><div className="resume-summary">{Object.entries(labels).filter(([key])=>current.content[key as keyof ResumeContent]?.some(line=>line.trim())).map(([key,label])=><section key={key}><h3>{label}</h3>{current.content[key as keyof ResumeContent].filter(line=>line.trim()).map((line,index)=><p key={index}>{line}</p>)}</section>)}</div><p className="note resume-local-note">已确认的经历可复用到岗位匹配、修改简历和模拟面试。</p><details className="resume-manage"><summary>更多操作</summary><div className="button-row"><button disabled={busy} onClick={()=>void importResume()}>替换文件</button><button type="button" disabled={busy} onClick={()=>setConfirmClear(value=>!value)}>清除当前简历</button></div>{confirmClear&&<div className="history-confirm" role="alert"><p>清除当前简历？历史版本和岗位材料会保留。</p><div className="button-row"><button disabled={busy} onClick={()=>void clearResume()}>确认清除</button><button disabled={busy} onClick={()=>setConfirmClear(false)}>取消</button></div></div>}</details></section>}
    {!current&&!draft&&state&&(embedded||tab==='base')&&<section className="resume-import">
      <span className="resume-import-icon"><Icon name="resume"/></span><h3>让岗位更贴合你的经历</h3><p>导入并确认简历，找岗位和求职准备就能复用已有材料。</p>
      <div className="resume-import-steps" aria-label="简历导入步骤"><span><b>1</b> 导入文件</span><span aria-hidden="true">→</span><span><b>2</b> 核对内容</span><span aria-hidden="true">→</span><span><b>3</b> 确认使用</span></div>
      <button type="button" className="primary-button" disabled={busy||!!editing} onClick={()=>void importResume()}>{busy?'正在解析…':'选择简历文件'}</button><small>PDF、DOCX、Markdown、TXT</small>
      <details className="resume-file-help"><summary>文件要求与隐私</summary><p>{state.capabilities.detail}</p><p>文件保存在本机；公开检索词不包含简历正文和联系方式。不导入也能直接按关键词找岗位。</p></details>
    </section>}
    </>}
    {!embedded&&state&&!editing&&!draft&&tab==='base'&&pending.length>0&&<section className="resume-library-section"><h2>待审阅的 AI 修改 <span>{pending.length}</span></h2>{pending.map(session=><article className="resume-library-card" key={session.session_id}><div><strong>基础简历 · v{versions.find(v=>v.version_id===session.base_version_id)?.version_number||'历史版本'}</strong><p className="note">{resumeReviewCounts(session).accepted} 项已接受 · {resumeReviewCounts(session).pending} 项待审阅</p></div><button onClick={()=>setReview(session)}>审阅修改 →</button></article>)}</section>}
    {!embedded&&state&&!editing&&!draft&&tab==='tailored'&&<section className="resume-tailored-list"><div className="resume-document-bar"><div><strong>岗位专属简历</strong><small>针对岗位修改，基础简历保持不变。</small></div>{current&&onImprove&&<button className="primary-button" onClick={()=>setImprove(true)}>AI 修改</button>}</div>{tailored.length?tailored.map(session=>{const version=versions.find(v=>v.version_id===session.saved_version_id);const job=jobs.find(j=>j.job.job_id===session.target_job_id)?.job;const counts=resumeReviewCounts(session);const status=version?`v${version.version_number} · ${new Date(version.created_at).toLocaleDateString()} · ${applications.some(a=>a.resume_version_id===version.version_id&&a.status==='resume_sent')?'已用于投递（本人确认）':'未记录投递'}`:session.saved_version_id?'已保存，版本已归档':counts.pending?`${counts.pending} 项待审阅`:counts.accepted?`${counts.accepted} 项已接受，待保存`:'已保留原文';return <article className="resume-library-card" key={session.session_id}><div><small>{job?.company||'目标岗位'}</small><strong>{job?.title||session.target_title||'岗位专属稿'}</strong><p className="note">{status}</p></div><div className="button-row">{job&&onPrepare&&<button onClick={()=>onPrepare(job)}>查看岗位</button>}{version?<button onClick={()=>setPreview(version)}>预览与导出</button>:session.status==='active'&&<button onClick={()=>setReview(session)}>审阅修改 →</button>}</div></article>;}):<div className="resume-library-empty"><Icon name="resume"/><h3>给目标岗位一份专属表达</h3><p>{current?'选择一个岗位，AI 会根据真实经历提出修改，由你决定采用哪些。':'先导入并确认基础简历，再为目标岗位准备独立稿。'}</p>{current&&onImprove?<button onClick={()=>setImprove(true)}>开始 AI 修改 →</button>:<button onClick={()=>setTab('base')}>去完善基础简历 →</button>}</div>}</section>}
    {!embedded&&!editing&&!draft&&tab==='base'&&history.length>0&&<details className="resume-manage"><summary>历史版本（{history.length}）</summary>{history.map(version=><div className="resume-history-row" key={version.version_id}><span>v{version.version_number} · {new Date(version.created_at).toLocaleString()}</span><button disabled={busy} onClick={()=>setPreview(version)}>预览</button><button disabled={busy} onClick={()=>setRestore(version)}>恢复</button></div>)}</details>}
    {restore&&<ResumeModal title="恢复历史版本" onClose={()=>setRestore(undefined)} busy={busy}><div className="resume-improve-body"><p>将 v{restore.version_number} 恢复为新的基础简历？现有版本会保留。</p></div><footer><button disabled={busy} onClick={()=>setRestore(undefined)}>取消</button><button className="primary-button" disabled={busy} onClick={()=>void run(async()=>{await window.jobfindsme!.restoreResumeVersion(state!.workspace_id!,restore.version_id);setRestore(undefined);await reload();window.dispatchEvent(new Event('jfm:job-updated'));setMessage('已恢复为新的基础版本。');})}>确认恢复</button></footer></ResumeModal>}
    {preview&&state?.workspace_id&&<ResumePreview workspaceId={state.workspace_id} version={preview} onClose={()=>setPreview(undefined)}/>}
    {improve&&onImprove&&<ResumeImproveDialog initialTarget={tab==='tailored'?'job':'general'} jobs={jobs.map(row=>row.job)} onClose={()=>setImprove(false)} onStart={(job,instruction)=>{setImprove(false);onImprove(job,instruction);}}/>}
    {review&&state?.workspace_id&&<ResumeModal busy={reviewBusy} title="审阅 AI 修改" onClose={()=>setReview(undefined)} wide><div className="resume-review-scroll"><ResumeProposal workspaceId={state.workspace_id} sessionId={review.session_id} onBusyChange={setReviewBusy} onChanged={next=>setSessions(rows=>rows.map(row=>row.session_id===next.session_id?next:row))}/></div></ResumeModal>}

  </div>;
}
