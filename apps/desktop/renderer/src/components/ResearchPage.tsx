import {reportMatchesJob,reportStatus,reportJob} from "../../../shared/research-reports";
import { ReputationEvidence, researchDirections } from "./ReputationEvidence";
import {userError} from "../../../shared/user-errors";
import { sourceBrowserSpecs, isSourceBrowserId, isAllowedSourceUrl } from "../../../main/source-browser-policy";
import { useEffect, useRef, useState } from "react";
import type { BootstrapData, SearchResultItem, ResearchReport, ResearchDirection } from "../../../shared/contracts";
import { useOriginalBrowser } from "./Workbench";
type Props = {onReports(value:ResearchReport[]):void;active:boolean; data?: BootstrapData; target?: SearchResultItem["job"]; onEditResume(job:SearchResultItem["job"]):void; onBack():void; onError(message?:string):void};
export function ResearchPage({active,data,target,onEditResume,onBack,onError,onReports}:Props) {
  const workspaceId = data?.workspaces[0]?.workspace_id;
  const [job,setJob] = useState(target);
  const [contextCompany,setContextCompany]=useState("");const [contextDescription,setContextDescription]=useState("");
  const [report,setReport] = useState<ResearchReport>();
  const [reports,setReports] = useState<ResearchReport[]>([]);
  const [allHistory,setAllHistory]=useState(false);
  const lastOpened=useRef<string|undefined>(undefined);
  function keepReports(value:ResearchReport[]){setReports(value);onReports(value);}
  function openSaved(value:ResearchReport){lastOpened.current=value.report_id;readSequence.current++;setJob(reportJob(value));setReport(value);setCandidate(undefined);setInputOpen(false);setTab("reputation");setContextCompany("");setContextDescription("");setMessage("");setBusy(false);}
  const [tab,setTab] = useState("reputation");
  const [url,setUrl] = useState("");
  const [candidate,setCandidate] = useState<Awaited<ReturnType<NonNullable<typeof window.jobfindsme>["resolveResearchLink"]>>>();
  const readSequence=useRef(0);
  const [inputOpen,setInputOpen] = useState(!target); const [message,setMessage] = useState("");
  const [directions,setDirections] = useState<ResearchDirection[]>(Object.keys(researchDirections) as ResearchDirection[]); const [busy,setBusy] = useState(false);
  const openBrowser = useOriginalBrowser();
  useEffect(() => { lastOpened.current=undefined;setTab("reputation"); setContextCompany("");setContextDescription("");setJob(target); setCandidate(undefined); setReport(undefined); setInputOpen(!target); setMessage(""); setBusy(false); readSequence.current++; }, [target]);
  useEffect(() => { if (!workspaceId || !active) return; let cancelled=false;void window.jobfindsme!.listResearchReports(workspaceId).then(values=>{if(cancelled)return;keepReports(values);const previous=values.find(r=>r.report_id===lastOpened.current);if(previous){openSaved(previous);return;}if(target){const latest=values.filter(r=>reportMatchesJob(r,target)).sort((a,b)=>(b.version_number??1)-(a.version_number??1)||b.created_at.localeCompare(a.created_at))[0];if(latest){lastOpened.current=latest.report_id;setJob(reportJob(latest));setReport(latest);setInputOpen(false);}}}).catch(e => onError(String(e)));return()=>{cancelled=true;}; },[workspaceId,active,target]);
  async function readLink(value=url.trim()) {
    const sequence=++readSequence.current;setBusy(true);onError(undefined);setCandidate(undefined);setInputOpen(true);setReport(undefined);setMessage("正在自动解析岗位信息…");
    try {const result=await window.jobfindsme!.resolveResearchLink(value);if(sequence!==readSequence.current)return;setCandidate(result);setMessage(result.message);}
    catch(e){if(sequence===readSequence.current)setMessage(`解析未完成：${e instanceof Error ? e.message : String(e)}`);}
    finally{if(sequence===readSequence.current)setBusy(false);}
  }
  async function run() {
    if (!workspaceId || (!job && !candidate)) return;
    const sequence=++readSequence.current;setBusy(true);onError(undefined);
    try {
      let current=job;
      if(candidate) {
        current=await window.jobfindsme!.prepareResearchJob({workspace_id:workspaceId,url:candidate.url,title:candidate.title,company:candidate.company,description:candidate.description});
        setJob(current);setCandidate(undefined);setInputOpen(false);
      }
      if(!current)return;
      const value=await window.jobfindsme!.createResearchReport({workspace_id:workspaceId,job_id:current.job_id,source_ids:tab === "reputation" ? ["maimai","offershow","kanzhun"] : [],user_evidence:[],directions,context_company:contextCompany||undefined,context_description:contextDescription||undefined});
      const values=await window.jobfindsme!.listResearchReports(workspaceId);keepReports(values);
      if(sequence!==readSequence.current)return;
      lastOpened.current=value.report_id;setJob(reportJob(value));setReport(value);setInputOpen(false);setMessage(value.outcome==="failed"?"本次检索失败，失败记录已保存在本机。":"研究报告已自动保存在本机。");
    }catch(e){if(sequence===readSequence.current)onError(String(e));}finally{if(sequence===readSequence.current)setBusy(false);}
  }
  function openLink(value:string) {const sourceId=Object.keys(sourceBrowserSpecs).find(id=>isSourceBrowserId(id) && isAllowedSourceUrl(id,value));if(sourceId)openBrowser({sourceId,url:value,title:"岗位原页"});else setMessage("请使用已登记招聘来源的岗位详情链接。");}
  function original() {if(job)openLink(job.apply_url);}

  const history=reports.filter(r=>allHistory||!job||reportMatchesJob(r,job));
  return <div className={`research-page ${job ? "has-research-job" : "empty-research"}`}><div className="heading-row"><div><h1>岗位研究</h1><p>{job ? `${job.company} · ${job.title}` : "粘贴岗位链接，自动解析 JD 后开始研究。"}</p></div><div className="button-row"><button onClick={onBack}>← 返回列表</button>{job && <button className="primary-button" onClick={original}>打开岗位链接 ↗</button>}</div></div>
  {!!reports.length&&<details className="research-history" open={!job||undefined}><summary>历史研究报告 · {history.length}</summary>{job&&<label><input type="checkbox" checked={allHistory} onChange={e=>setAllHistory(e.target.checked)}/> 查看所有岗位</label>}<div className="research-history-list">{history.map(r=><button key={r.report_id} disabled={busy} aria-pressed={report?.report_id===r.report_id} onClick={()=>openSaved(r)}>{r.job_context?.company||"公司未知"} · {r.job_context?.title||"历史岗位"}<br/>v{r.version_number??1} · {new Date(r.created_at).toLocaleString()} · {reportStatus(r)}</button>)}</div></details>}
  <div className="research-context"><span>{job?.source.source_name || "添加一个岗位链接"}</span><button onClick={()=>setInputOpen(!inputOpen)}>{inputOpen ? "收起输入" : "输入其他岗位链接"}</button></div>
  {inputOpen && <section className="research-input"><div className="searchbar"><input aria-label="岗位链接" value={url} disabled={busy} onChange={e=>{setUrl(e.target.value);setCandidate(undefined);setMessage("");}} onPaste={e=>{const value=e.clipboardData.getData("text").trim();if(value){e.preventDefault();setUrl(value);void readLink(value);}}} placeholder="粘贴岗位详情链接，自动解析岗位信息"/><button disabled={busy || !url.trim()} onClick={()=>void readLink()}>{busy ? "解析中…" : "解析岗位"}</button></div>{message && <p className="notice">{userError(message).message}</p>}{url && !candidate && !busy && <button onClick={()=>openLink(url.trim())}>打开原页 / 登录后重试</button>}{candidate && <div className="panel section"><h3>{candidate.title}</h3><p>{candidate.company}</p><details><summary>已解析岗位 JD</summary><p className="job-description">{candidate.description}</p></details><button className="primary-button" disabled={busy} onClick={()=>void run()}>{busy ? "研究中…" : "确认并研究"}</button></div>}</section>}
  {job && !inputOpen && !report && <details className="research-jd"><summary>查看岗位 JD</summary><p className="job-description">{job.description || "此来源暂未提供完整 JD，请先读取详情。"}</p></details>}
  <div className="research-tabs" role="tablist" aria-label="研究模块">{[["reputation","口碑调查"],["resume","针对 JD 修改简历"]].map(([key,label])=><button role="tab" aria-selected={tab===key} key={key} className={tab===key?"active":""} onClick={()=>setTab(key)}>{label}</button>)}</div>
  <div className="research-body" role="tabpanel">
  {!job ? (!candidate && <div className="empty"><strong>先选择一个岗位</strong><p>从发现岗位、已看过进入，或直接粘贴岗位链接。</p></div>) : <>
  {tab==="reputation" && <>{report&&<section className="report-saved" role="status"><strong>研究报告 v{report.version_number??1} · {reportStatus(report)}</strong><p>{new Date(report.created_at).toLocaleString()} · 已保存在本机</p><p className="note">当前展示保存时的岗位信息和证据。再次研究会生成新报告，不覆盖历史。</p><details><summary>报告岗位快照</summary><p>{report.job_context?.company||"公司未知"} · {report.job_context?.title||"历史岗位"}</p><p className="job-description">{report.job_context?.description||"保存时未读取到完整职位描述"}</p><p>{report.job_context?.url||"原链接未知"}</p></details></section>}<section className="research-subject"><h2>调查对象</h2><p><strong>{report?.job_context?.company||contextCompany||job.company}</strong> · {report?.job_context?.title||job.title}</p><p className="muted">岗位名称、公司、JD 与原链接已带入，仅用于定位调查对象，不作为员工口碑证据。</p>{(!job.description||job.description.length<80)&&<p className="notice">当前 JD 不完整，可读取原页补全，或展开补充信息。</p>}{["公司未知","未知","BOSS直聘"].includes(job.company)&&!contextCompany&&<p className="notice">公司名称未知，请先读取原页或补充名称后调查。</p>}<div className="button-row"><button disabled={busy} onClick={()=>void readLink(job.apply_url)}>读取原页补全</button><button onClick={original}>查看原始链接 ↗</button></div><details><summary>调查上下文 / 补充信息</summary><p>原链接：{report?.job_context?.url||job.apply_url}</p><p>明确标注的团队：{report?.job_context?.team||"未知；不会根据岗位名称猜测"}</p><label>补充公司名称（可选）<input aria-label="补充公司名称" value={contextCompany} maxLength={300} onChange={e=>setContextCompany(e.target.value)}/></label><label>补充 JD（可选）<textarea aria-label="补充 JD" value={contextDescription} maxLength={30000} onChange={e=>setContextDescription(e.target.value)}/></label><p className="job-description">{report?.job_context?.description||contextDescription||job.description||"JD 未知"}</p></details></section><fieldset className="research-directions"><legend>调查方向</legend>{(Object.entries(researchDirections) as Array<[ResearchDirection,string]>).map(([key,label])=><label key={key}><input type="checkbox" checked={directions.includes(key)} disabled={busy} onChange={e=>setDirections(current=>e.target.checked?[...current,key]:current.filter(item=>item!==key))}/>{label}</label>)}</fieldset><div className="research-actions"><p className="muted">读取公开来源，不调用模型作公司评价。</p><button className="primary-button" disabled={busy||!directions.length||(["公司未知","未知","BOSS直聘"].includes(job.company)&&!contextCompany.trim())} onClick={()=>void run()}>{busy?"检索中…":report?"再次研究 · 保存新报告":"确认并研究"}</button></div><ReputationEvidence report={report} workspaceId={workspaceId!} onReport={value=>{setReport(value);keepReports(reports.map(item=>item.report_id===value.report_id?value:item));}}/></>}

  {tab==="resume" && <><h2>针对这个 JD，调整表达</h2><p className="muted">把真实经历与岗位需求对应，保留原版，逐段决定是否采纳。</p><ReportSection title="改写方向" items={report?.project_rewrites ?? ["直接将当前岗位 JD 带入简历编辑器，基于真实经历调整表达。"]}/><details><summary>将带入编辑器的 JD</summary><p className="job-description">{job.description}</p></details><button className="primary-button" onClick={()=>onEditResume(job)}>带入 JD，进入简历编辑 →</button></>}

  </>}
  </div>
  </div>;
}
function ReportSection({title,items}:{title:string;items:string[]}) { return <section className="report-section"><h3>{title}</h3>{items.map((text,index)=><p key={index}>{text.replace(/（resume_version_[^）]*）/g, "")}</p>)}</section>; }
