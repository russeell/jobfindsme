import {useEffect,useRef,useState} from "react";
import type {BootstrapData,ResearchReport,SearchResultItem} from "../../../shared/contracts";
import {reportJob,reportMatchesJob,reportStatus} from "../../../shared/research-reports";
import {isAllowedSourceUrl,isSourceBrowserId,sourceBrowserSpecs} from "../../../shared/source-browser-policy";
import {userError} from "../../../shared/user-errors";
import {useOriginalBrowser} from "../shared/Workbench";
import {ReputationEvidence} from "./ReputationEvidence";

type Job=SearchResultItem["job"];
type Topic="company"|"job";
type Props={onReports(value:ResearchReport[]):void;active:boolean;data?:BootstrapData;target?:Job;onBack():void;onError(message?:string):void};
const unknownCompanies=new Set(["公司未知","未知","BOSS直聘"]);
const researchSources=["official","maimai","kanzhun","zhihu","offershow"];

export function ResearchPage({active,data,target,onBack,onError,onReports}:Props){
  const workspaceId=data?.workspaces[0]?.workspace_id;
  const [job,setJob]=useState<Job|undefined>(target);
  const [report,setReport]=useState<ResearchReport>();
  const [reports,setReports]=useState<ResearchReport[]>([]);
  const [mode,setMode]=useState<"start"|"report">("start");
  const [historyOpen,setHistoryOpen]=useState(false);
  const [allHistory,setAllHistory]=useState(false);
  const [hideId,setHideId]=useState("");
  const [url,setUrl]=useState("");
  const [candidate,setCandidate]=useState<Awaited<ReturnType<NonNullable<typeof window.jobfindsme>["resolveResearchLink"]>>>();
  const [linkOpen,setLinkOpen]=useState(!target);
  const [contextCompany,setContextCompany]=useState("");
  const [topics,setTopics]=useState<Topic[]>(["company","job"]);
  const [question,setQuestion]=useState("");
  const [busy,setBusy]=useState<"link"|"prepare"|"research"|"history"|null>(null);
  const [message,setMessage]=useState("");
  const sequence=useRef(0);
  const lastOpened=useRef<string|undefined>(undefined);
  const openBrowser=useOriginalBrowser();
  function keepReports(values:ResearchReport[]){setReports(values);onReports(values);}
  function openSaved(value:ResearchReport){sequence.current++;lastOpened.current=value.report_id;setJob(reportJob(value));setReport(value);setMode("report");setLinkOpen(false);setCandidate(undefined);setContextCompany("");setTopics(value.job_context?.research_topics?.length?value.job_context.research_topics:["company","job"]);setQuestion("");setMessage("");setBusy(null);}
  useEffect(()=>{sequence.current++;lastOpened.current=undefined;setJob(target);setReport(undefined);setMode("start");setLinkOpen(!target);setCandidate(undefined);setContextCompany("");setUrl("");setHistoryOpen(false);setTopics(["company","job"]);setQuestion("");setMessage("");setBusy(null);},[target]);
  useEffect(()=>{if(!workspaceId||!active)return;let cancelled=false;void window.jobfindsme!.listResearchReports(workspaceId).then(values=>{if(cancelled)return;keepReports(values);if(lastOpened.current){const previous=values.find(item=>item.report_id===lastOpened.current);if(previous)return;}if(target){const latest=values.filter(item=>reportMatchesJob(item,target)&&item.outcome!=="failed").sort((a,b)=>(b.version_number??1)-(a.version_number??1)||b.created_at.localeCompare(a.created_at))[0];if(latest)openSaved(latest);}}).catch(error=>onError(userError(error).message));return()=>{cancelled=true;};},[workspaceId,active,target]);
  async function readLink(value=url.trim()){
    if(!value)return;const id=++sequence.current;setBusy("link");setCandidate(undefined);setMessage("正在读取岗位原页…");
    try{const next=await window.jobfindsme!.resolveResearchLink(value);if(id!==sequence.current)return;setCandidate(next);setMessage(next.message);}
    catch(error){if(id===sequence.current)setMessage(`岗位信息未读取：${userError(error).message}`);}
    finally{if(id===sequence.current)setBusy(null);}
  }
  async function confirmCandidate(){
    if(!workspaceId||!candidate)return;const id=++sequence.current;setBusy("prepare");setMessage("正在保存岗位上下文…");
    try{const next=await window.jobfindsme!.prepareResearchJob({workspace_id:workspaceId,url:candidate.url,title:candidate.title,company:candidate.company,description:candidate.description});if(id!==sequence.current)return;setJob(next);setCandidate(undefined);setLinkOpen(false);setContextCompany("");setReport(undefined);setMode("start");lastOpened.current=undefined;setMessage("");}
    catch(error){if(id===sequence.current)setMessage(userError(error).message);}
    finally{if(id===sequence.current)setBusy(null);}
  }
  async function run(){
    if(!workspaceId||!job||!topics.length||busy)return;
    if(unknownCompanies.has(job.company)&&!contextCompany.trim()){setMessage("请先补充公司全称，再开始研究。");return;}
    const id=++sequence.current;setBusy("research");setMessage("正在检索公开材料并核对原页；每次请求最多等待 4 秒。当前报告仍可保留。");
    try{
      const next=await window.jobfindsme!.createResearchReport({workspace_id:workspaceId,job_id:job.job_id,source_ids:researchSources,user_evidence:[],topics,directions:topics.includes("job")?["role","workload","leave","care"]:[],context_company:contextCompany.trim()||undefined,interest_question:question.trim()||undefined});
      const values=await window.jobfindsme!.listResearchReports(workspaceId);
      if(id!==sequence.current)return;
      keepReports(values);
      if(next.outcome==="failed"){setMessage("本次公开来源读取失败，原报告仍在。可稍后重试；失败记录可从历史报告查看。");return;}
      lastOpened.current=next.report_id;setReport(next);setJob(reportJob(next));setMode("report");setLinkOpen(false);setQuestion("");setMessage(next.evidence.length?"已保存新报告。材料按来源与时间列出。":"已保存本次研究；没有取得可核对的公开原文，相关结论保持未知。");
    }catch(error){if(id===sequence.current)setMessage(`本次研究未完成：${userError(error).message} 原报告仍在。`);}
    finally{if(id===sequence.current)setBusy(null);}
  }
  async function cancel(){
    if(busy!=="research")return;sequence.current++;setBusy(null);setMessage("已请求取消。进行中的单次网页读取最多再等待 4 秒；原报告仍在。");
    try{await window.jobfindsme!.cancelResearch();}catch(error){setMessage(`取消请求未完成：${userError(error).message} 原报告仍在。`);}
  }
  async function hideReport(value:ResearchReport){
    if(!workspaceId)return;setBusy("history");setMessage("");
    try{await window.jobfindsme!.hideResearchReport(workspaceId,value.report_id);const next=await window.jobfindsme!.listResearchReports(workspaceId);keepReports(next);if(report?.report_id===value.report_id){const previous=next.find(item=>job&&reportMatchesJob(item,job)&&item.outcome!=="failed");if(previous)openSaved(previous);else{setReport(undefined);setMode("start");lastOpened.current=undefined;}}setHideId("");setMessage("已从历史列表移除，原始证据快照仍保存在本机。");}
    catch(error){setMessage(userError(error).message);}finally{setBusy(null);}
  }
  function openOriginal(value:string){const id=Object.keys(sourceBrowserSpecs).find(key=>isSourceBrowserId(key)&&isAllowedSourceUrl(key,value));if(id)openBrowser({sourceId:id,url:value,title:job?.title||"岗位原页"});else setMessage("请使用已登记招聘来源的岗位详情链接。");}
  const history=reports.filter(item=>allHistory||!job||reportMatchesJob(item,job));
  const showingReport=mode==="report"&&!!report;
  const title=job?`${job.company} · ${job.title}`:"尚未选择岗位";
  return <div className="research-page research-workbench">
    <header className="research-header"><div><span className="research-eyebrow">岗位研究</span><h1>{showingReport?job?.title:"这个机会，你想了解什么？"}</h1><p>{showingReport?`${job?.company} · ${report&&new Date(report.created_at).toLocaleString()} · ${report&&reportStatus(report)}`:job?"选择方向，补充你关心的问题。":"从找工作或已看过选择岗位，也可粘贴岗位详情链接。"}</p></div><div className="button-row">{showingReport&&<button onClick={()=>{setMode("start");setMessage("");}}>← 返回研究首页</button>}<button aria-expanded={historyOpen} onClick={()=>setHistoryOpen(value=>!value)}>历史报告{history.length?` · ${history.length}`:""}</button><button onClick={onBack}>返回找工作</button>{job&&<button onClick={()=>openOriginal(job.apply_url)}>岗位原页 ↗</button>}</div></header>
    {historyOpen&&<section className="research-history-panel" aria-label="历史报告"><div className="research-history-title"><strong>历史报告</strong>{job&&<label><input type="checkbox" checked={allHistory} onChange={event=>setAllHistory(event.target.checked)}/> 查看所有岗位</label>}</div>{history.length?<div className="research-history-list">{history.map(item=><div className="research-history-row" key={item.report_id}><button disabled={!!busy} aria-pressed={report?.report_id===item.report_id&&showingReport} onClick={()=>{openSaved(item);setHistoryOpen(false);}}><strong>{item.job_context?.company||"公司未知"} · {item.job_context?.title||"岗位未知"}</strong><small>{new Date(item.created_at).toLocaleString()} · {reportStatus(item)}{item.job_context?.interest_question?` · 问：${item.job_context.interest_question}`:""}</small></button><button disabled={!!busy} onClick={()=>setHideId(item.report_id)}>移除</button>{hideId===item.report_id&&<div className="history-confirm" role="alert"><p>从列表移除这份报告？本机证据快照保留。</p><div className="button-row"><button disabled={!!busy} onClick={()=>void hideReport(item)}>确认移除</button><button onClick={()=>setHideId("")}>取消</button></div></div>}</div>)}</div>:<p className="research-empty-note">这里还没有报告。选择岗位后可直接研究。</p>}</section>}
    {message&&<p className="research-message" role="status">{message}</p>}
    {!job&&<><section className="research-link-entry"><label htmlFor="research-url">岗位详情链接</label><div className="searchbar"><input id="research-url" value={url} disabled={!!busy} onChange={event=>{setUrl(event.target.value);setCandidate(undefined);}} onPaste={event=>{const value=event.clipboardData.getData("text").trim();if(value){event.preventDefault();setUrl(value);void readLink(value);}}} placeholder="粘贴 BOSS、智联、猎聘等岗位原页链接"/><button disabled={!!busy||!url.trim()} onClick={()=>void readLink()}>{busy==="link"?"读取中…":"读取岗位"}</button></div>{candidate&&<div className="research-candidate"><strong>{candidate.company} · {candidate.title}</strong><p>{candidate.description?`${candidate.description.slice(0,180)}${candidate.description.length>180?"…":""}`:"暂未读取到完整 JD"}</p><button className="primary-button" disabled={!!busy} onClick={()=>void confirmCandidate()}>确认这个岗位</button></div>}</section><section className="research-composer research-composer-pending" aria-label="研究输入框"><div className="research-composer-context">先选择一个岗位<span>公司与岗位主题已准备好</span></div><textarea aria-label="研究问题" disabled placeholder="确认岗位后，可在这里补充问题或直接开始"/><div className="research-composer-actions"><div className="research-topic-chips" aria-label="默认研究主题"><button type="button" aria-pressed="true" disabled>✓ 公司情况</button><button type="button" aria-pressed="true" disabled>✓ 岗位情况</button></div><button type="button" className="primary-button" disabled>开始研究 ↑</button></div></section></>}
    {job&&<>
      {!showingReport&&<div className="research-start"><p className="research-context-label">研究对象 · {title}</p>{report&&<button className="research-last-report" onClick={()=>setMode("report")}>继续阅读上次报告 ↗</button>}{unknownCompanies.has(job.company)&&<label className="research-company-supplement">公司全称<input value={contextCompany} maxLength={300} onChange={event=>setContextCompany(event.target.value)} placeholder="填写可核对的公司全称"/></label>}{!job.description&&<p className="research-empty-note">尚未取得完整岗位 JD；岗位职责与发展将保留未知。</p>}</div>}
      {showingReport&&report&&<><div className="research-report-meta"><span>本地保存的研究报告 · 第 {report.version_number??1} 版</span><span>{report.evidence.length} 条材料</span></div><ReputationEvidence report={report} workspaceId={workspaceId!} onReport={value=>{setReport(value);keepReports(reports.map(item=>item.report_id===value.report_id?value:item));}} onSource={value=>openBrowser({sourceId:"web",url:value,title:"研究来源"})}/></>}
      <form className="research-composer" onSubmit={event=>{event.preventDefault();void run();}}><div className="research-composer-context"><strong>{showingReport?"继续研究":"研究问题"}</strong><span>基于已选岗位与 JD</span></div><textarea aria-label="研究问题" value={question} maxLength={300} disabled={!!busy} onChange={event=>setQuestion(event.target.value)} placeholder={showingReport?"继续追问，例如：这个团队的工作强度有原文依据吗？":"补充你关心的问题；也可以留空直接研究"}/><div className="research-composer-actions"><div className="research-topic-chips" role="group" aria-label="研究主题"><button type="button" aria-pressed={topics.includes("company")} disabled={!!busy} onClick={()=>setTopics(current=>current.includes("company")?current.filter(item=>item!=="company"):[...current,"company"])}>{topics.includes("company")?"✓ ":""}公司情况</button><button type="button" aria-pressed={topics.includes("job")} disabled={!!busy} onClick={()=>setTopics(current=>current.includes("job")?current.filter(item=>item!=="job"):[...current,"job"])}>{topics.includes("job")?"✓ ":""}岗位情况</button></div><div className="button-row">{busy==="research"&&<button type="button" onClick={()=>void cancel()}>取消研究</button>}<button type="submit" className="primary-button" disabled={!!busy||!topics.length}>{busy==="research"?"研究中…":showingReport?"继续追问 / 更新报告 ↑":"开始研究 ↑"}</button></div></div><p className="research-composer-help">{showingReport?"追问会检索问题相关原文并保存新版本；无可核对材料时会说明未知。":"问题可留空，默认包含公司与岗位。"} 请勿填写隐私信息。</p></form>
      {job&&!showingReport&&<button className="research-switch-job" onClick={()=>{setLinkOpen(value=>!value);setCandidate(undefined);}}>换一个岗位链接</button>}
      {linkOpen&&job&&<section className="research-link-entry"><div className="searchbar"><input aria-label="新岗位链接" value={url} disabled={!!busy} onChange={event=>{setUrl(event.target.value);setCandidate(undefined);}} placeholder="粘贴另一个岗位详情链接"/><button disabled={!!busy||!url.trim()} onClick={()=>void readLink()}>读取岗位</button></div>{candidate&&<div className="research-candidate"><strong>{candidate.company} · {candidate.title}</strong><button onClick={()=>void confirmCandidate()}>确认这个岗位</button></div>}</section>}
    </>}
  </div>;
}
