import {useEffect,useState} from "react";
import type {ResumeDraft,ResumeState,ResumeVersion} from "../../../shared/contracts";
import {userError} from "../../../shared/user-errors";
import {Icon} from "../shared/Icon";

const factLabels:Record<string,string>={skill:"专业技能",project:"项目经历",experience:"工作经历",education:"教育经历"};

export function ResumePage({onChanged,embedded=false}:{onChanged?:(state:ResumeState)=>void;embedded?:boolean}={}){
  const [state,setState]=useState<ResumeState>();
  const [current,setCurrent]=useState<ResumeVersion>();
  const [accepted,setAccepted]=useState<Set<string>>(new Set());
  const [corrections,setCorrections]=useState<Record<string,string>>({});
  const [busy,setBusy]=useState(false),[message,setMessage]=useState(""),[error,setError]=useState(""),[confirmClear,setConfirmClear]=useState(false);
  const draft:ResumeDraft|null|undefined=state?.active_draft;
  const factGroups=draft?[...new Set(draft.facts.map(fact=>fact.fact_type))]:[];
  async function reload(){
    const next=await window.jobfindsme!.getResumeState();
    const workspace=next.workspace_id;
    const versions=workspace?await window.jobfindsme!.listResumeVersions(workspace):[];
    setState(next);onChanged?.(next);
    setCurrent(versions.find(version=>version.is_current));
    if(next.active_draft){setAccepted(new Set(next.active_draft.facts.map(f=>f.fact_id)));setCorrections(Object.fromEntries(next.active_draft.facts.map(f=>[f.fact_id,f.value])));}
  }
  useEffect(()=>{void reload().catch(reason=>setError(userError(reason).message));},[]);
  async function run(action:()=>Promise<void>){setBusy(true);setError("");setMessage("");try{await action();}catch(reason){setError(userError(reason).message);}finally{setBusy(false);}}
  async function importResume(){await run(async()=>{const value=await window.jobfindsme!.chooseAndImportResume();if(value){await reload();setMessage("请核对解析内容。确认前，新导入内容不会参与检索。");}});}
  async function confirm(){if(!draft)return;await run(async()=>{await window.jobfindsme!.confirmResume({workspace_id:draft.workspace_id,profile_id:draft.profile_id,accepted_fact_ids:[...accepted],corrections:Object.fromEntries([...accepted].map(id=>[id,corrections[id]??""]))});await reload();setMessage("简历已确认，下一次检索可使用其中的技能和经历。");});}
  async function abandon(){if(!draft)return;await run(async()=>{await window.jobfindsme!.abandonResume(draft.workspace_id,draft.profile_id);await reload();setMessage("本次导入已放弃。");});}
  async function clearResume(){if(!state?.workspace_id)return;await run(async()=>{await window.jobfindsme!.clearCurrentResume(state.workspace_id!);await reload();setConfirmClear(false);setMessage("当前简历已清除；现在可不使用简历搜索。已有检索和研究快照保留。");});}
  return <div className={`resume-page resume-maintenance simple-profile${embedded?' embedded':''}`}>
    {!embedded&&<div className="heading-row resume-heading"><div><h1>我的简历</h1><p>导入一次，核对后即可用于岗位匹配和求职准备。</p></div></div>}
    {error&&<p className="notice" role="alert">{error} <button type="button" disabled={busy} onClick={()=>void run(reload)}>重新读取</button></p>}{message&&<p className="resume-feedback" role="status">{message}</p>}
    {!state&&!error?<p className="note" role="status">正在读取本地简历…</p>:<>
    {(current||draft)&&<div className="resume-context"><span><i className={draft?'pending':''}/>{draft?'待核对':`已确认 · v${current!.version_number}`}</span><button type="button" disabled={busy} onClick={()=>void importResume()}>{busy?'处理中…':'替换文件'}</button></div>}
    {draft&&<section className="resume-confirm resume-review">
      <h3>核对解析内容</h3><p className="note">{draft.file_name} · 已选择 {accepted.size} / {draft.facts.length} 条。取消勾选不准确的内容，也可直接修改。</p>
      <div className="resume-review-tools"><button type="button" disabled={busy} onClick={()=>setAccepted(new Set(draft.facts.map(fact=>fact.fact_id)))}>全选</button><button type="button" disabled={busy} onClick={()=>setAccepted(new Set())}>取消全选</button></div>
      <div className="fact-list">{factGroups.map(type=>{const facts=draft.facts.filter(fact=>fact.fact_type===type);const label=factLabels[type]??'简历信息';return <section className="fact-group" key={type} aria-label={label}><h3>{label}<small>{facts.length} 条</small></h3>{facts.map((fact,index)=><div className="fact-row" key={fact.fact_id}><input type="checkbox" disabled={busy} aria-label={`${label} ${index+1}`} checked={accepted.has(fact.fact_id)} onChange={event=>setAccepted(previous=>{const next=new Set(previous);event.target.checked?next.add(fact.fact_id):next.delete(fact.fact_id);return next;})}/><textarea aria-label={`${label} ${index+1} 内容`} value={corrections[fact.fact_id]??fact.value} disabled={!accepted.has(fact.fact_id)||busy} onChange={event=>setCorrections(previous=>({...previous,[fact.fact_id]:event.target.value}))}/></div>)}</section>;})}</div>
      <div className="resume-review-footer"><span>{current?'确认后更新当前简历；原版本仍保留。':'确认前不会用于岗位匹配。'}</span><div><button type="button" disabled={busy} onClick={()=>void abandon()}>暂不使用</button><button type="button" className="primary-button" disabled={busy||!accepted.size} onClick={()=>void confirm()}>{busy?'处理中…':'确认并使用'}</button></div></div>
    </section>}
    {current&&!draft&&<section className="resume-current resume-ready"><p className="note">技能与经历可用于本地匹配；发送求职助手消息时才交给所选模型。</p><div className="resume-summary">{([['skills','专业技能'],['experience','工作经历'],['projects','项目经历'],['education','教育经历']] as const).filter(([key])=>current.content[key]?.some(line=>line.trim())).map(([key,label])=><section key={key}><h3>{label}</h3>{current.content[key].map((line,index)=><p key={index}>{line}</p>)}</section>)}</div><details className="resume-manage"><summary>管理当前简历</summary><p className="note">已有岗位、简历版本和研究记录会保留。</p><button type="button" disabled={busy} onClick={()=>setConfirmClear(value=>!value)}>清除当前简历</button>{confirmClear&&<div className="history-confirm" role="alert"><p>清除当前简历？之后可不使用简历搜索；已有检索和报告快照保留。</p><div className="button-row"><button autoFocus disabled={busy} onClick={()=>void clearResume()}>确认清除</button><button disabled={busy} onClick={()=>setConfirmClear(false)}>取消</button></div></div>}</details></section>}
    {!current&&!draft&&state&&<section className="resume-import">
      <span className="resume-import-icon"><Icon name="resume"/></span><h3>让岗位更贴合你的经历</h3><p>导入并确认简历，找岗位和求职准备就能复用已有材料。</p>
      <div className="resume-import-steps" aria-label="简历导入步骤"><span><b>1</b> 导入文件</span><span aria-hidden="true">→</span><span><b>2</b> 核对内容</span><span aria-hidden="true">→</span><span><b>3</b> 确认使用</span></div>
      <button type="button" className="primary-button" disabled={busy} onClick={()=>void importResume()}>{busy?'正在解析…':'选择简历文件'}</button><small>PDF、DOCX、Markdown、TXT</small>
      <details className="resume-file-help"><summary>文件要求与隐私</summary><p>{state.capabilities.detail}</p><p>文件保存在本机；公开检索词不包含简历正文和联系方式。不导入也能直接按关键词找岗位。</p></details>
    </section>}
    </>}
  </div>;
}
