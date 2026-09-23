import {reportMatchesJob,reportStatus,reportJob} from "../../../shared/research-reports";
import { ReputationEvidence } from "./ReputationEvidence";
import {userError} from "../../../shared/user-errors";
import { sourceBrowserSpecs, isSourceBrowserId, isAllowedSourceUrl } from "../../../main/source-browser-policy";
import { useEffect, useRef, useState } from "react";
import type { BootstrapData, SearchResultItem, ResearchReport } from "../../../shared/contracts";
import { useOriginalBrowser } from "./Workbench";
type Props = {onReports(value:ResearchReport[]):void;active:boolean; data?: BootstrapData; target?: SearchResultItem["job"];  onBack():void; onError(message?:string):void};
export function ResearchPage({active,data,target,onBack,onError,onReports}:Props) {
  const workspaceId = data?.workspaces[0]?.workspace_id;
  const [job,setJob] = useState(target);
  const [contextCompany,setContextCompany]=useState("");
  const [report,setReport] = useState<ResearchReport>();
  const [reports,setReports] = useState<ResearchReport[]>([]);
  const [allHistory,setAllHistory]=useState(false);
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
      const value=await window.jobfindsme!.createResearchReport({workspace_id:workspaceId,job_id:job.job_id,source_ids:["maimai","kanzhun","zhihu","offershow"],user_evidence:[],topics,directions:topics.includes("job")?["role","workload","leave","care"]:[],context_company:contextCompany||undefined});
      const values=await window.jobfindsme!.listResearchReports(workspaceId);keepReports(values);
      if(sequence!==readSequence.current)return;
      lastOpened.current=value.report_id;setJob(reportJob(value));setReport(value);setInputOpen(false);setMessage(value.outcome==="failed"?"本次检索失败，失败记录已保存在本机。":"研究报告已自动保存在本机。");
    }catch(e){if(sequence===readSequence.current)onError(String(e));}finally{if(sequence===readSequence.current)setBusy(false);}
  }
  async function hideReport(value:ResearchReport){if(!workspaceId)return;setBusy(true);onError(undefined);try{await window.jobfindsme!.hideResearchReport(workspaceId,value.report_id);const next=await window.jobfindsme!.listResearchReports(workspaceId);keepReports(next);if(report?.report_id===value.report_id){lastOpened.current=undefined;setReport(undefined);}setHideId("");setMessage("报告已从历史列表移除；本机证据快照保留。");}catch(error){onError(String(error));}finally{setBusy(false);}}
  function openLink(value:string) {const sourceId=Object.keys(sourceBrowserSpecs).find(id=>isSourceBrowserId(id) && isAllowedSourceUrl(id,value));if(sourceId)openBrowser({sourceId,url:value,title:"岗位原页"});else setMessage("请使用已登记招聘来源的岗位详情链接。");}
  function original() {if(job)openLink(job.apply_url);}

  const history=reports.filter(r=>allHistory||!job||reportMatchesJob(r,job));
  return <div className={`research-page ${job ? "has-research-job" : "empty-research"}`}><div className="heading-row"><div><h1>岗位研究</h1><p>{job ? `${job.company} · ${job.title}` : "粘贴岗位链接，自动解析 JD 后开始研究。"}</p></div><div className="button-row"><button onClick={onBack}>← 返回列表</button>{job && <button className="primary-button" onClick={original}>打开岗位链接 ↗</button>}</div></div>
  {!!reports.length&&<details className="research-history" open={!job||undefined}><summary>历史研究报告 · {history.length}</summary>{job&&<label><input type="checkbox" checked={allHistory} onChange={e=>setAllHistory(e.target.checked)}/> 查看所有岗位</label>}<div className="research-history-list">{history.map(r=><div className="research-history-row" key={r.report_id}><button disabled={busy} aria-pressed={report?.report_id===r.report_id} onClick={()=>openSaved(r)}>{r.job_context?.company||"公司未知"} · {r.job_context?.title||"历史岗位"}<br/>v{r.version_number??1} · {new Date(r.created_at).toLocaleString()} · {reportStatus(r)}</button><button disabled={busy} onClick={()=>setHideId(r.report_id)}>移除记录</button>{hideId===r.report_id&&<div className="history-confirm" role="alert"><p>从历史列表移除「{r.job_context?.company||"公司未知"} · {r.job_context?.title||"历史岗位"}」v{r.version_number??1}？本机证据与更正保留，不会物理清除。</p><div className="button-row"><button disabled={busy} onClick={()=>void hideReport(r)}>确认移除</button><button disabled={busy} onClick={()=>setHideId("")}>取消</button></div></div>}</div>)}</div></details>}
  <div className="research-context"><span>{job?.source.source_name || "添加一个岗位链接"}</span><button onClick={()=>setInputOpen(!inputOpen)}>{inputOpen ? "收起输入" : "输入其他岗位链接"}</button></div>
  {inputOpen && <section className="research-input"><div className="searchbar"><input aria-label="岗位链接" value={url} disabled={busy} onChange={e=>{setUrl(e.target.value);setCandidate(undefined);setMessage("");}} onPaste={e=>{const value=e.clipboardData.getData("text").trim();if(value){e.preventDefault();setUrl(value);void readLink(value);}}} placeholder="粘贴岗位详情链接，自动解析岗位信息"/><button disabled={busy || !url.trim()} onClick={()=>void readLink()}>{busy ? "解析中…" : "解析岗位"}</button></div>{message && <p className="notice">{userError(message).message}</p>}{url && !candidate && !busy && <button onClick={()=>openLink(url.trim())}>打开原页 / 登录后重试</button>}{candidate && <div className="panel section"><h3>{candidate.title}</h3><p>{candidate.company}</p><details><summary>已解析岗位 JD</summary><p className="job-description">{candidate.description}</p></details><button className="primary-button" disabled={busy} onClick={()=>void confirmCandidate()}>{busy ? "确认中…" : "确认岗位并选择主题"}</button></div>}</section>}
  {job && !inputOpen && !report && <details className="research-jd"><summary>查看岗位 JD</summary><p className="job-description">{job.description || "此来源暂未提供完整 JD，请先读取详情。"}</p></details>}
  <div className="research-body" role="tabpanel">
  {!job ? (!candidate && <div className="empty"><strong>先选择一个岗位</strong><p>从发现岗位、已看过进入，或直接粘贴岗位链接。</p></div>) : <>
  <>{report&&<section className="report-saved" role="status"><strong>调研报告 v{report.version_number??1} · {reportStatus(report)}</strong><p>{new Date(report.created_at).toLocaleString()} · 已保存在本机</p><p className="note">当前展示保存时的岗位信息和证据。再次研究会生成新报告，不覆盖历史。</p><details><summary>报告岗位快照</summary><p>{report.job_context?.company||"公司未知"} · {report.job_context?.title||"历史岗位"}</p><p className="job-description">{report.job_context?.description||"保存时未读取到完整职位描述"}</p><p>{report.job_context?.url||"原链接未知"}</p></details></section>}{report&&<ReputationEvidence report={report} workspaceId={workspaceId!} onReport={value=>{setReport(value);keepReports(reports.map(item=>item.report_id===value.report_id?value:item));}}/>}<section className="panel section research-compact"><h2>口碑调查</h2><p className="note">{job.company} · {job.title}。公司与岗位 JD 自动带入，仅用于定位调查对象，不作为员工口碑证据。</p>{["公司未知","未知","BOSS直聘"].includes(job.company)&&<label>补充公司名称<input aria-label="补充公司名称" value={contextCompany} maxLength={300} onChange={e=>setContextCompany(e.target.value)} placeholder="实际公司全称"/></label>}<fieldset className="research-topic-choice"><legend>选择调研主题</legend>{([["company","公司评价"],["job","岗位情况"]] as const).map(([key,label])=><label key={key}><input type="checkbox" checked={topics.includes(key)} disabled={busy} onChange={e=>setTopics(old=>e.target.checked?[...old,key]:old.filter(item=>item!==key))}/>{label}</label>)}</fieldset><p className="note">公司评价分别寻找正向与负向公开反馈；岗位情况查工作内容、工作强度、假期和员工福利。仅展示实际找到的材料。</p><div className="button-row"><button className="primary-button" disabled={busy||!topics.length||(["公司未知","未知","BOSS直聘"].includes(job.company)&&!contextCompany.trim())} onClick={()=>void run()}>{busy?"调研中…":report?"再次调研 · 保存新报告":"开始调研"}</button>{(!job.description||job.description.length<80)&&<button disabled={busy} onClick={()=>void readLink(job.apply_url)}>读取原页补全 JD</button>}</div></section></>



  </>}
  </div>
  </div>;
}
