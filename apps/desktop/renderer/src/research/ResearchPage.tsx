import {reportMatchesJob,reportStatus,reportJob} from "../../../shared/research-reports";
import { ReputationEvidence } from "./ReputationEvidence";
import {userError} from "../../../shared/user-errors";
import { sourceBrowserSpecs, isSourceBrowserId, isAllowedSourceUrl } from "../../../shared/source-browser-policy";
import { useEffect, useRef, useState } from "react";
import type { BootstrapData, SearchResultItem, ResearchReport } from "../../../shared/contracts";
import { useOriginalBrowser } from "../shared/Workbench";
type Props = {onReports(value:ResearchReport[]):void;active:boolean; data?: BootstrapData; target?: SearchResultItem["job"];  onBack():void; onError(message?:string):void};
export function ResearchPage({active,data,target,onBack,onError,onReports}:Props) {
  const workspaceId = data?.workspaces[0]?.workspace_id;
  const [job,setJob] = useState(target);
  const [contextCompany,setContextCompany]=useState("");
  const [report,setReport] = useState<ResearchReport>();
  const [reports,setReports] = useState<ResearchReport[]>([]);
  const [allHistory,setAllHistory]=useState(false);
  const [historyOpen,setHistoryOpen]=useState(false);
  const [hideId,setHideId]=useState("");
  const lastOpened=useRef<string|undefined>(undefined);
  function keepReports(value:ResearchReport[]){setReports(value);onReports(value);}
  function openSaved(value:ResearchReport){lastOpened.current=value.report_id;readSequence.current++;setJob(reportJob(value));setReport(value);setCandidate(undefined);setInputOpen(false);setContextCompany("");setTopics(value.job_context?.research_topics?.length?value.job_context.research_topics:["company","job"]);setMessage("");setBusy(false);}
  const [url,setUrl] = useState("");
  const [candidate,setCandidate] = useState<Awaited<ReturnType<NonNullable<typeof window.jobfindsme>["resolveResearchLink"]>>>();
  const readSequence=useRef(0);
  const [inputOpen,setInputOpen] = useState(!target); const [message,setMessage] = useState("");
  const [topics,setTopics] = useState<Array<"company"|"job">>(["company","job"]);
  const [busy,setBusy] = useState(false);
  const openBrowser = useOriginalBrowser();
  useEffect(() => { lastOpened.current=undefined; setContextCompany("");setTopics(["company","job"]);setJob(target); setCandidate(undefined); setReport(undefined); setInputOpen(!target); setMessage(""); setBusy(false); readSequence.current++; }, [target]);
  useEffect(() => { if (!workspaceId || !active) return; let cancelled=false;void window.jobfindsme!.listResearchReports(workspaceId).then(values=>{if(cancelled)return;keepReports(values);const previous=values.find(r=>r.report_id===lastOpened.current);if(previous){openSaved(previous);return;}if(target){const latest=values.filter(r=>reportMatchesJob(r,target)).sort((a,b)=>(b.version_number??1)-(a.version_number??1)||b.created_at.localeCompare(a.created_at))[0];if(latest){lastOpened.current=latest.report_id;setJob(reportJob(latest));setReport(latest);setInputOpen(false);setTopics(latest.job_context?.research_topics?.length?latest.job_context.research_topics:["company","job"]);}}}).catch(e => onError(String(e)));return()=>{cancelled=true;}; },[workspaceId,active,target]);
  async function readLink(value=url.trim()) {
    const sequence=++readSequence.current;setBusy(true);onError(undefined);setCandidate(undefined);setInputOpen(true);setReport(undefined);setMessage("正在自动解析岗位信息…");
    try {const result=await window.jobfindsme!.resolveResearchLink(value);if(sequence!==readSequence.current)return;setCandidate(result);setMessage(result.message);}
    catch(e){if(sequence===readSequence.current)setMessage(`解析未完成：${e instanceof Error ? e.message : String(e)}`);}
    finally{if(sequence===readSequence.current)setBusy(false);}
  }
  async function confirmCandidate() {
    if(!workspaceId||!candidate)return;
    const sequence=++readSequence.current;setBusy(true);onError(undefined);
    try{const current=await window.jobfindsme!.prepareResearchJob({workspace_id:workspaceId,url:candidate.url,title:candidate.title,company:candidate.company,description:candidate.description});if(sequence!==readSequence.current)return;setJob(current);setCandidate(undefined);setInputOpen(false);setReport(undefined);setMessage("");}
    catch(e){if(sequence===readSequence.current)onError(String(e));}
    finally{if(sequence===readSequence.current)setBusy(false);}
  }
  async function run() {
    if (!workspaceId || !job) return;
    const sequence=++readSequence.current;setBusy(true);onError(undefined);
    try {
      const value=await window.jobfindsme!.createResearchReport({workspace_id:workspaceId,job_id:job.job_id,source_ids:["official","maimai","kanzhun","zhihu","offershow"],user_evidence:[],topics,directions:topics.includes("job")?["role","workload","leave","care"]:[],context_company:contextCompany||undefined});
      const values=await window.jobfindsme!.listResearchReports(workspaceId);keepReports(values);
      if(sequence!==readSequence.current)return;
      lastOpened.current=value.report_id;setJob(reportJob(value));setReport(value);setInputOpen(false);setMessage(value.outcome==="failed"?"本次检索失败，失败记录已保存在本机。":"研究报告已自动保存在本机。");
    }catch(e){if(sequence===readSequence.current)onError(String(e));}finally{if(sequence===readSequence.current)setBusy(false);}
  }
  async function hideReport(value:ResearchReport){if(!workspaceId)return;setBusy(true);onError(undefined);try{await window.jobfindsme!.hideResearchReport(workspaceId,value.report_id);const next=await window.jobfindsme!.listResearchReports(workspaceId);keepReports(next);if(report?.report_id===value.report_id){lastOpened.current=undefined;setReport(undefined);}setHideId("");setMessage("报告已从历史列表移除；本机证据快照保留。");}catch(error){onError(String(error));}finally{setBusy(false);}}
  function openLink(value:string) {const sourceId=Object.keys(sourceBrowserSpecs).find(id=>isSourceBrowserId(id) && isAllowedSourceUrl(id,value));if(sourceId)openBrowser({sourceId,url:value,title:"岗位原页"});else setMessage("请使用已登记招聘来源的岗位详情链接。");}
  function original() {if(job)openLink(job.apply_url);}
  function returnToTopics(){readSequence.current++;lastOpened.current=undefined;setReport(undefined);setCandidate(undefined);setInputOpen(false);setHistoryOpen(false);setMessage("");}

  const history=reports.filter(r=>allHistory||!job||reportMatchesJob(r,job));
  return <div className={`research-page ${job ? "has-research-job" : "empty-research"}`}><div className="heading-row"><div><h1>岗位研究</h1><p>{report?"已保存的岗位研究":job?`${job.company} · ${job.title}`:"从岗位列表选择对象，或粘贴岗位链接。"}</p></div><div className="button-row">{report&&job&&<button onClick={returnToTopics}>← 选择研究主题</button>}<button onClick={onBack}>← 返回找工作</button>{job && <button onClick={original}>岗位原页 ↗</button>}</div></div>
  {!!reports.length&&<section className="research-history"><button type="button" className="research-history-toggle" aria-expanded={historyOpen} onClick={()=>setHistoryOpen(value=>!value)}>{historyOpen?"▾":"▸"} 历史岗位研究 · {history.length}</button>{historyOpen&&<>{job&&<label className="research-history-filter"><input type="checkbox" checked={allHistory} onChange={e=>setAllHistory(e.target.checked)}/> 查看所有岗位</label>}<div className="research-history-list">{history.map(r=><div className="research-history-row" key={r.report_id}><button disabled={busy} aria-pressed={report?.report_id===r.report_id} onClick={()=>{openSaved(r);setHistoryOpen(false);}}><strong>{r.job_context?.company||"公司未知"} · {r.job_context?.title||"历史岗位"}</strong><small>{new Date(r.created_at).toLocaleString()} · {reportStatus(r)}</small></button><button disabled={busy} onClick={()=>setHideId(r.report_id)}>移除记录</button>{hideId===r.report_id&&<div className="history-confirm" role="alert"><p>从历史列表移除「{r.job_context?.company||"公司未知"} · {r.job_context?.title||"历史岗位"}」？本机证据与更正保留。</p><div className="button-row"><button disabled={busy} onClick={()=>void hideReport(r)}>确认移除</button><button disabled={busy} onClick={()=>setHideId("")}>取消</button></div></div>}</div>)}</div></>}</section>}
  {!report&&<div className="research-context"><span>{job?`研究对象 · ${job.company} · ${job.title}`:"研究对象"}</span><button onClick={()=>setInputOpen(!inputOpen)}>{inputOpen ? "收起链接输入" : "换一个岗位"}</button></div>}
  {inputOpen && <section className="research-input"><div className="searchbar"><input aria-label="岗位链接" value={url} disabled={busy} onChange={e=>{setUrl(e.target.value);setCandidate(undefined);setMessage("");}} onPaste={e=>{const value=e.clipboardData.getData("text").trim();if(value){e.preventDefault();setUrl(value);void readLink(value);}}} placeholder="粘贴岗位详情链接，自动解析岗位信息"/><button disabled={busy || !url.trim()} onClick={()=>void readLink()}>{busy ? "解析中…" : "解析岗位"}</button></div>{message && <p className="notice">{userError(message).message}</p>}{url && !candidate && !busy && <button onClick={()=>openLink(url.trim())}>打开原页 / 登录后重试</button>}{candidate && <div className="panel section"><h3>{candidate.title}</h3><p>{candidate.company}</p><details><summary>已解析岗位 JD</summary><p className="job-description">{candidate.description}</p></details><button className="primary-button" disabled={busy} onClick={()=>void confirmCandidate()}>{busy ? "确认中…" : "确认岗位并选择主题"}</button></div>}</section>}
  {job && !inputOpen && !report && <details className="research-jd"><summary>查看岗位 JD</summary><p className="job-description">{job.description || "此来源暂未提供完整 JD，请先读取详情。"}</p></details>}
  <div className="research-body" role="tabpanel">
  {!job ? null : <>
  <>{report&&<section className="report-saved" role="status"><div className="report-summary"><strong>{report.job_context?.company||job.company} · {report.job_context?.title||job.title}</strong><span>更新于 {new Date(report.created_at).toLocaleString()} · {reportStatus(report)}</span></div><details><summary>保存时的岗位与原链接</summary><p className="job-description">{report.job_context?.description||"保存时未读取到完整职位描述"}</p><p>{report.job_context?.url||"原链接未知"}</p></details>{!report.evidence.length&&<button className="research-again-shortcut" onClick={()=>{const next=document.querySelector<HTMLDetailsElement>(".research-new-run");if(next){next.open=true;next.scrollIntoView({behavior:"smooth",block:"center"});}}}>调整主题并再次研究 ↓</button>}</section>}{report&&<ReputationEvidence report={report} workspaceId={workspaceId!} onReport={value=>{setReport(value);keepReports(reports.map(item=>item.report_id===value.report_id?value:item));}}/>}<details className="research-new-run" key={report?.report_id||"new"} open={!report||undefined}><summary>{report?"更新研究 · 保存新报告":"选择研究主题"}</summary><section className="research-compact"><p className="note">岗位与公司自动带入。只选择想了解的主题，可以同时选两项。</p>{["公司未知","未知","BOSS直聘"].includes(job.company)&&<label>补充公司名称<input aria-label="补充公司名称" value={contextCompany} maxLength={300} onChange={e=>setContextCompany(e.target.value)} placeholder="实际公司全称"/></label>}<fieldset className="research-topic-choice"><legend>选择研究主题</legend>{([["company","公司情况","经营情况、上市状态、正负面反馈、强度与福利"],["job","岗位内容与发展","岗位职责、技能与发展线索，结合公司经营资料"]] as const).map(([key,label,description])=><label className="research-topic-card" key={key}><input type="checkbox" checked={topics.includes(key)} disabled={busy} onChange={e=>setTopics(old=>e.target.checked?[...old,key]:old.filter(item=>item!==key))}/><span><strong>{label}</strong><small>{description}</small></span></label>)}</fieldset><div className="button-row"><button className="primary-button" disabled={busy||!topics.length||(["公司未知","未知","BOSS直聘"].includes(job.company)&&!contextCompany.trim())} onClick={()=>void run()}>{busy?"研究中…":report?"更新研究 · 保存新报告":"开始研究"}</button></div>{(!job.description||job.description.length<80)&&<p className="note">完整 JD 尚未读取；岗位主题会标明未知。<button disabled={busy} onClick={()=>void readLink(job.apply_url)}>尝试读取岗位原页</button></p>}</section></details></>



  </>}
  </div>
  </div>;
}
