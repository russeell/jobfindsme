import {ResumeProposal} from "../research/ResumeProposal";
import {useEffect,useRef,useState} from "react";
import type {ResumeDraft,ResumeState,ResumeVersion,ResumeContent,ApplicationRecord,PromptSession,TrackedJob,SearchResultItem} from "../../../shared/contracts";
import {userError} from "../../../shared/user-errors";
import {Icon} from "../shared/Icon";

const factLabels:Record<string,string>={skill:"专业技能",project:"项目经历",experience:"工作经历",education:"教育经历"};

export function ResumePage({onChanged,embedded=false,active=true,onPrepare}:{onChanged?:(state:ResumeState)=>void;embedded?:boolean;active?:boolean;onPrepare?:(job:SearchResultItem["job"])=>void}={}){
  const [state,setState]=useState<ResumeState>();
  const [current,setCurrent]=useState<ResumeVersion>();
  const [versions,setVersions]=useState<ResumeVersion[]>([]);
  const [sessions,setSessions]=useState<PromptSession[]>([]);
  const [applications,setApplications]=useState<ApplicationRecord[]>([]);
  const [jobs,setJobs]=useState<TrackedJob[]>([]);
  const [preview,setPreview]=useState<ResumeVersion>();
  const [editing,setEditing]=useState<{base:string;content:ResumeContent}>();
  const [restore,setRestore]=useState<ResumeVersion>();
  const [template,setTemplate]=useState<'classic'|'compact'>('classic');
  const labels:Record<keyof ResumeContent,string>={basic_information:'基本信息',experience:'工作经历',projects:'项目经历',education:'教育经历',skills:'专业技能'};
  const [accepted,setAccepted]=useState<Set<string>>(new Set());
  const [corrections,setCorrections]=useState<Record<string,string>>({});
  const [busy,setBusy]=useState(false),[message,setMessage]=useState(""),[error,setError]=useState(""),[confirmClear,setConfirmClear]=useState(false);
  const draft:ResumeDraft|null|undefined=state?.active_draft;
  const reviewedDraft=useRef<string|null>(null);
  const factGroups=draft?[...new Set(draft.facts.map(fact=>fact.fact_type))]:[];
  async function reload(){
    const next=await window.jobfindsme!.getResumeState();
    const workspace=next.workspace_id;
    const versions=workspace?await window.jobfindsme!.listResumeVersions(workspace):[];
    if(workspace&&!embedded){const [proposals,rows,records]=await Promise.all([window.jobfindsme!.listPromptSessions(workspace),window.jobfindsme!.listJobTracking(workspace),window.jobfindsme!.listApplicationRecords(workspace)]);setSessions(proposals.filter(p=>p.target_job_id));setJobs(rows);setApplications(records);}
    setVersions(versions);setState(next);onChanged?.(next);
    setCurrent(versions.find(version=>version.is_current));
    const draftKey=next.active_draft?`${workspace}:${next.active_draft.profile_id}`:null;
    if(next.active_draft&&draftKey!==reviewedDraft.current){setAccepted(new Set(next.active_draft.facts.map(f=>f.fact_id)));setCorrections(Object.fromEntries(next.active_draft.facts.map(f=>[f.fact_id,f.value])));}
    reviewedDraft.current=draftKey;
  }
  useEffect(()=>{if(!active)return;const refresh=()=>void reload().catch(reason=>setError(userError(reason).message));refresh();window.addEventListener('jfm:job-updated',refresh);return()=>window.removeEventListener('jfm:job-updated',refresh);},[active]);
  async function exportVersion(version:ResumeVersion,format:'pdf'|'docx'){if(!state?.workspace_id)return;await run(async()=>{const exported=await window.jobfindsme!.exportResume({workspace_id:state.workspace_id!,version_id:version.version_id,format,template});if(exported)setMessage('已导出到所选位置。');});}
  async function saveEdit(){if(!editing||!state?.workspace_id)return;await run(async()=>{await window.jobfindsme!.saveResumeVersion({workspace_id:state.workspace_id!,base_version_id:editing.base,content:editing.content});setEditing(undefined);await reload();window.dispatchEvent(new Event('jfm:job-updated'));setMessage('已保存为新的基础版本，旧版本保留。');});}
  const tailoredIds=new Set(sessions.map(p=>p.saved_version_id).filter(Boolean));
  const history=versions.filter(v=>!v.is_current&&!tailoredIds.has(v.version_id));
  async function run(action:()=>Promise<void>){setBusy(true);setError("");setMessage("");try{await action();}catch(reason){setError(userError(reason).message);}finally{setBusy(false);}}
  async function importResume(){await run(async()=>{const value=await window.jobfindsme!.chooseAndImportResume();if(value){await reload();setMessage("请核对解析内容。确认前，新导入内容不会参与检索。");}});}
  async function confirm(){if(!draft)return;await run(async()=>{await window.jobfindsme!.confirmResume({workspace_id:draft.workspace_id,profile_id:draft.profile_id,accepted_fact_ids:[...accepted],corrections:Object.fromEntries([...accepted].map(id=>[id,corrections[id]??""]))});await reload();setMessage("简历已确认，下一次检索可使用其中的技能和经历。");});}
  async function abandon(){if(!draft)return;await run(async()=>{await window.jobfindsme!.abandonResume(draft.workspace_id,draft.profile_id);await reload();setMessage("本次导入已放弃。");});}
  async function clearResume(){if(!state?.workspace_id)return;await run(async()=>{await window.jobfindsme!.clearCurrentResume(state.workspace_id!);await reload();setConfirmClear(false);setMessage("当前简历已清除；现在可不使用简历搜索。已有检索和研究快照保留。");});}
  return <div className={`resume-page resume-maintenance simple-profile${embedded?' embedded':''}`}>
    {!embedded&&<div className="heading-row resume-heading"><div><h1>我的简历</h1><p>导入一次，核对后即可用于岗位匹配和求职准备。</p></div></div>}
    {error&&<p className="notice" role="alert">{error} <button type="button" disabled={busy} onClick={()=>void run(reload)}>重新读取</button></p>}{message&&<p className="resume-feedback" role="status">{message}</p>}
    {!state&&!error?<p className="note" role="status">正在读取本地简历…</p>:<>
    {(current||draft)&&<div className="resume-context"><span><i className={draft?'pending':''}/>{draft?'待核对':`已确认 · v${current!.version_number}`}</span><button type="button" disabled={busy||!!editing} onClick={()=>void importResume()}>{busy?'处理中…':'替换文件'}</button></div>}
    {draft&&<section className="resume-confirm resume-review">
      <h3>核对解析内容</h3><p className="note">{draft.file_name} · 已选择 {accepted.size} / {draft.facts.length} 条。取消勾选不准确的内容，也可直接修改。</p>
      <div className="resume-review-tools"><button type="button" disabled={busy} onClick={()=>setAccepted(new Set(draft.facts.map(fact=>fact.fact_id)))}>全选</button><button type="button" disabled={busy} onClick={()=>setAccepted(new Set())}>取消全选</button></div>
      <div className="fact-list">{factGroups.map(type=>{const facts=draft.facts.filter(fact=>fact.fact_type===type);const label=factLabels[type]??'简历信息';return <section className="fact-group" key={type} aria-label={label}><h3>{label}<small>{facts.length} 条</small></h3>{facts.map((fact,index)=><div className="fact-row" key={fact.fact_id}><input type="checkbox" disabled={busy} aria-label={`${label} ${index+1}`} checked={accepted.has(fact.fact_id)} onChange={event=>setAccepted(previous=>{const next=new Set(previous);event.target.checked?next.add(fact.fact_id):next.delete(fact.fact_id);return next;})}/><textarea aria-label={`${label} ${index+1} 内容`} value={corrections[fact.fact_id]??fact.value} disabled={!accepted.has(fact.fact_id)||busy} onChange={event=>setCorrections(previous=>({...previous,[fact.fact_id]:event.target.value}))}/></div>)}</section>;})}</div>
      <div className="resume-review-footer"><span>{current?'确认后更新当前简历；原版本仍保留。':'确认前不会用于岗位匹配。'}</span><div><button type="button" disabled={busy} onClick={()=>void abandon()}>暂不使用</button><button type="button" className="primary-button" disabled={busy||!accepted.size} onClick={()=>void confirm()}>{busy?'处理中…':'确认并使用'}</button></div></div>
    </section>}
    {current&&!draft&&!embedded&&<div className="resume-library-toolbar"><strong>基础简历 · v{current.version_number}</strong><div><button disabled={busy||!!editing} onClick={()=>setEditing({base:current.version_id,content:structuredClone(current.content)})}>编辑经历</button><button disabled={busy} onClick={()=>setPreview(current)}>预览与导出</button></div></div>}
    {editing&&<section className="resume-editor"><h3>编辑基础简历</h3><p className="note">每行一条经历。只填写真实信息，保存后保留原版本。</p>{Object.entries(labels).map(([key,label])=><label key={key}>{label}<textarea aria-label={label} disabled={busy} value={editing.content[key as keyof ResumeContent].join('\n')} onChange={e=>setEditing({...editing,content:{...editing.content,[key]:e.target.value.split('\n')}})}/></label>)}<div className="button-row"><button disabled={busy} onClick={()=>setEditing(undefined)}>放弃修改</button><button className="primary-button" disabled={busy||!Object.values(editing.content).some(lines=>lines.some(line=>line.trim()))} onClick={()=>void saveEdit()}>保存新版本</button></div></section>}
    {current&&!draft&&!editing&&<section className="resume-current resume-ready"><p className="note">技能与经历可用于本地匹配；发送求职助手消息时才交给所选模型。</p><div className="resume-summary">{([['skills','专业技能'],['experience','工作经历'],['projects','项目经历'],['education','教育经历']] as const).filter(([key])=>current.content[key]?.some(line=>line.trim())).map(([key,label])=><section key={key}><h3>{label}</h3>{current.content[key].map((line,index)=><p key={index}>{line}</p>)}</section>)}</div><details className="resume-manage"><summary>管理当前简历</summary><p className="note">已有岗位、简历版本和研究记录会保留。</p><button type="button" disabled={busy} onClick={()=>setConfirmClear(value=>!value)}>清除当前简历</button>{confirmClear&&<div className="history-confirm" role="alert"><p>清除当前简历？之后可不使用简历搜索；已有检索和报告快照保留。</p><div className="button-row"><button autoFocus disabled={busy} onClick={()=>void clearResume()}>确认清除</button><button disabled={busy} onClick={()=>setConfirmClear(false)}>取消</button></div></div>}</details></section>}
    {!current&&!draft&&state&&<section className="resume-import">
      <span className="resume-import-icon"><Icon name="resume"/></span><h3>让岗位更贴合你的经历</h3><p>导入并确认简历，找岗位和求职准备就能复用已有材料。</p>
      <div className="resume-import-steps" aria-label="简历导入步骤"><span><b>1</b> 导入文件</span><span aria-hidden="true">→</span><span><b>2</b> 核对内容</span><span aria-hidden="true">→</span><span><b>3</b> 确认使用</span></div>
      <button type="button" className="primary-button" disabled={busy||!!editing} onClick={()=>void importResume()}>{busy?'正在解析…':'选择简历文件'}</button><small>PDF、DOCX、Markdown、TXT</small>
      <details className="resume-file-help"><summary>文件要求与隐私</summary><p>{state.capabilities.detail}</p><p>文件保存在本机；公开检索词不包含简历正文和联系方式。不导入也能直接按关键词找岗位。</p></details>
    </section>}
    </>}
    {!embedded&&state&&<section className="resume-library-section"><div className="heading-row"><div><h2>岗位专属简历</h2><p className="note">每个岗位保留独立稿，基础简历不受影响。</p></div></div>{sessions.length?sessions.map(session=>{const version=versions.find(v=>v.version_id===session.saved_version_id);const job=jobs.find(j=>j.job.job_id===session.target_job_id)?.job;return <article className="resume-library-card" key={session.session_id}><div><strong>{job?.company||'目标岗位'} · {job?.title||session.target_title||'岗位专属稿'}</strong><p className="note">{version?`v${version.version_number} · ${new Date(version.created_at).toLocaleDateString()} · ${applications.some(a=>a.resume_version_id===version.version_id&&a.status==='resume_sent')?'已用于投递（本人确认）':'未记录投递'}`:'待审阅修改稿'}</p></div><div className="button-row">{job&&onPrepare&&<button onClick={()=>onPrepare(job)}>查看岗位</button>}{version&&<button onClick={()=>setPreview(version)}>预览与导出</button>}</div>{!version&&state.workspace_id&&<details><summary>审阅修改</summary><ResumeProposal workspaceId={state.workspace_id} sessionId={session.session_id}/></details>}</article>;}):<p className="resume-library-empty">从岗位的“修改简历”开始，审阅后保存的专属稿会出现在这里。</p>}</section>}
    {!embedded&&history.length>0&&<details className="resume-manage"><summary>更多 · 历史版本（{history.length}）</summary>{history.map(version=><div className="resume-history-row" key={version.version_id}><span>v{version.version_number} · {new Date(version.created_at).toLocaleString()}</span><button disabled={busy} onClick={()=>setPreview(version)}>预览</button><button disabled={busy||!!editing||!!draft} onClick={()=>setRestore(version)}>恢复此版本</button></div>)}</details>}
    {restore&&<div className="history-confirm" role="alert"><p>将 v{restore.version_number} 恢复为新的基础简历？现有版本会保留。</p><button disabled={busy} onClick={()=>setRestore(undefined)}>取消</button><button disabled={busy} onClick={()=>void run(async()=>{await window.jobfindsme!.restoreResumeVersion(state!.workspace_id!,restore.version_id);setRestore(undefined);await reload();window.dispatchEvent(new Event('jfm:job-updated'));setMessage('已恢复为新的基础版本。');})}>确认恢复</button></div>}
    {preview&&<section className="resume-preview" aria-label="简历内容预览"><div className="heading-row"><h2>简历预览 · v{preview.version_number}</h2><button onClick={()=>setPreview(undefined)}>收起预览</button></div><p className="note">核对内容后导出。PDF / Word 使用下方所选模板排版。</p><div className="button-row"><select aria-label="导出模板" value={template} onChange={e=>setTemplate(e.target.value as typeof template)}><option value="classic">经典</option><option value="compact">紧凑</option></select><button disabled={busy} onClick={()=>void exportVersion(preview,'pdf')}>导出 PDF</button><button disabled={busy} onClick={()=>void exportVersion(preview,'docx')}>导出 Word</button></div>{Object.entries(labels).map(([key,label])=>preview.content[key as keyof ResumeContent].length>0&&<section key={key}><h3>{label}</h3>{preview.content[key as keyof ResumeContent].map((line,i)=><p key={i}>{line}</p>)}</section>)}</section>}
  </div>;
}
