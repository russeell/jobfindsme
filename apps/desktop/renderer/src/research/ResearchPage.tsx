import {useEffect,useRef,useState} from "react";
import {createPortal} from "react-dom";
import type {BootstrapData,ResearchReport,SearchResultItem} from "../../../shared/contracts";
import {reportJob,reportMatchesJob,reportStatus} from "../../../shared/research-reports";
import {isAllowedSourceUrl,isSourceBrowserId,sourceBrowserSpecs} from "../../../shared/source-browser-policy";
import {userError} from "../../../shared/user-errors";
import {splitResearchInput} from "../../../shared/research-input";
import {researchScopeFromQuestion} from "../../../shared/research-scope";
import {researchTopicsForQuestion,type ResearchTopic} from "../../../shared/research-intent";
import {useOriginalBrowser} from "../shared/Workbench";
import {ReputationEvidence} from "./ReputationEvidence";

type Job=SearchResultItem["job"];
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
  const [candidate,setCandidate]=useState<Awaited<ReturnType<NonNullable<typeof window.jobfindsme>["resolveResearchLink"]>>>();
  const [topbarTarget,setTopbarTarget]=useState<HTMLElement|null>(null);
  const [contextCompany,setContextCompany]=useState("");
  const [contextTitle,setContextTitle]=useState("");
  const [clarify,setClarify]=useState<"company"|"role"|null>(null);
  const [question,setQuestion]=useState("");
  const inputRef=useRef<HTMLTextAreaElement>(null);
  const [busy,setBusy]=useState<"link"|"prepare"|"research"|"history"|null>(null);
  const [message,setMessage]=useState("");
  const sequence=useRef(0);
  const lastOpened=useRef<string|undefined>(undefined);
  const openBrowser=useOriginalBrowser();
  function keepReports(values:ResearchReport[]){setReports(values);onReports(values);}
  function openSaved(value:ResearchReport){sequence.current++;lastOpened.current=value.report_id;setJob(value.job_id?reportJob(value):undefined);setReport(value);setMode("report");setCandidate(undefined);setContextCompany(value.job_id?"":value.job_context?.company||"");setContextTitle(value.job_id?"":value.job_context?.title||"");setClarify(null);setQuestion("");setMessage("");setBusy(null);}
  useEffect(()=>setTopbarTarget(document.getElementById("research-topbar-actions")),[]);
  useEffect(()=>{sequence.current++;lastOpened.current=undefined;setJob(target);setReport(undefined);setMode("start");setCandidate(undefined);setContextCompany("");setContextTitle("");setClarify(null);setHistoryOpen(false);setQuestion("");setMessage("");setBusy(null);},[target]);
  useEffect(()=>{const input=inputRef.current;if(!input)return;input.style.height="auto";input.style.height=`${Math.min(input.scrollHeight,window.innerHeight<650?74:112)}px`;},[question,active]);
  useEffect(()=>{if(!workspaceId||!active)return;let cancelled=false;void window.jobfindsme!.listResearchReports(workspaceId).then(values=>{if(cancelled)return;keepReports(values);if(lastOpened.current){const previous=values.find(item=>item.report_id===lastOpened.current);if(previous)return;}if(target){const latest=values.filter(item=>reportMatchesJob(item,target)&&item.outcome!=="failed").sort((a,b)=>(b.version_number??1)-(a.version_number??1)||b.created_at.localeCompare(a.created_at))[0];if(latest)openSaved(latest);}}).catch(error=>onError(userError(error).message));return()=>{cancelled=true;};},[workspaceId,active,target]);
  async function readLink(value:string){
    if(!value)return;
    if(!Object.keys(sourceBrowserSpecs).some(key=>isSourceBrowserId(key)&&isAllowedSourceUrl(key,value))){setCandidate(undefined);setMessage("仅支持已接入招聘来源的 HTTPS 岗位链接，请检查网址后重试。");return;}
    const id=++sequence.current;setBusy("link");setCandidate(undefined);setMessage("正在读取岗位原页…");
    try{const next=await window.jobfindsme!.resolveResearchLink(value);if(id!==sequence.current)return;setCandidate(next);setMessage(next.message);}
    catch(error){if(id===sequence.current)setMessage(`岗位信息未读取：${userError(error).message}`);}
    finally{if(id===sequence.current)setBusy(null);}
  }
  async function confirmCandidate(){
    if(!workspaceId||!candidate)return;const id=++sequence.current;setBusy("prepare");setMessage("正在保存岗位上下文…");
    try{const next=await window.jobfindsme!.prepareResearchJob({workspace_id:workspaceId,url:candidate.url,title:candidate.title,company:candidate.company,description:candidate.description});if(id!==sequence.current)return;setJob(next);setCandidate(undefined);setContextCompany("");setContextTitle("");setClarify(null);setReport(undefined);setMode("start");lastOpened.current=undefined;setQuestion(splitResearchInput(question).question);setMessage("岗位已确认，可以继续提问。");}
    catch(error){if(id===sequence.current)setMessage(userError(error).message);}
    finally{if(id===sequence.current)setBusy(null);}
  }
  async function run(interestQuestion:string,topics:ResearchTopic[],company?:string,title?:string){
    if(!workspaceId||busy)return;
    if(job&&unknownCompanies.has(job.company)&&!contextCompany.trim()){setMessage("请先补充公司全称，再开始研究。");return;}
    const id=++sequence.current;setBusy("research");setMessage("正在检索公开材料并核对原页；每次请求最多等待 4 秒。当前报告仍可保留。");
    try{
      const next=await window.jobfindsme!.createResearchReport({workspace_id:workspaceId,job_id:job?.job_id??null,source_ids:researchSources,user_evidence:[],topics,directions:job&&topics.includes("job")?["role","workload","leave","care"]:[],context_company:company||contextCompany.trim()||undefined,context_title:job?undefined:title,interest_question:interestQuestion||undefined});
      const values=await window.jobfindsme!.listResearchReports(workspaceId);
      if(id!==sequence.current)return;
      keepReports(values);
      if(next.outcome==="failed"){setMessage("本次公开来源读取失败，原报告仍在。可稍后重试；失败记录可从历史报告查看。");return;}
      lastOpened.current=next.report_id;setReport(next);setJob(next.job_id?reportJob(next):undefined);setContextCompany(next.job_id?"":next.job_context?.company||"");setContextTitle(next.job_id?"":next.job_context?.title||"");setClarify(null);setMode("report");setQuestion("");setMessage("");
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
  const title=job?`${job.company} · ${job.title}`:contextCompany||"未选择研究对象";
  function submitInput(){
    if(busy)return;
    const parsed=splitResearchInput(question);
    if(parsed.error){setCandidate(undefined);setMessage(parsed.error);return;}
    if(parsed.url){void readLink(parsed.url);return;}
    if(candidate){setMessage("请先确认读取到的岗位，再开始研究。");return;}
    if(job){void run(parsed.question,researchTopicsForQuestion(parsed.question,true,false));return;}
    if(!parsed.question){setMessage("请输入要研究的问题，或粘贴岗位链接。");return;}
    const scope=researchScopeFromQuestion(parsed.question);
    const company=scope.company||contextCompany.trim();
    if(!company){setClarify("company");setMessage("请补充要研究的公司名称，问题会保留。");return;}
    const role=scope.title||(company===contextCompany.trim()?contextTitle.trim():"");
    if(!role&&/(?:岗位|职位|招聘|职责|任职|JD)/iu.test(parsed.question)){setClarify("role");setMessage("请补充要研究的岗位名称，问题会保留。");return;}
    setClarify(null);setContextCompany(company);setContextTitle(role);
    void run(parsed.question,researchTopicsForQuestion(parsed.question,false,!!role),company,role);
  }
  const contextLabel=job?`${job.company} · ${job.title}`:contextCompany?`${contextCompany}${contextTitle?` · ${contextTitle}`:""}`:"";
  const centeredEmpty=!showingReport&&!job&&!contextCompany&&!historyOpen&&!message&&!clarify;
  return <div className="research-page research-workbench">
    {active&&topbarTarget&&createPortal(<div className="button-row" aria-label="研究操作">
      {showingReport?<button onClick={()=>{setMode("start");setMessage("");}}>← 研究首页</button>:<button onClick={onBack}>← 找工作</button>}
      <button aria-expanded={historyOpen} onClick={()=>setHistoryOpen(value=>!value)}>历史报告{history.length?` · ${history.length}`:""}</button>
      {(showingReport||job)&&<details className="research-more"><summary>更多</summary><div className="research-more-menu"><button onClick={onBack}>返回找工作</button>{job&&<button onClick={()=>openOriginal(job.apply_url)}>岗位原页 ↗</button>}</div></details>}
    </div>,topbarTarget)}
    <div className={`research-scroll-region${centeredEmpty?" research-empty-state":""}`} role="region" aria-label="研究报告正文" tabIndex={0}><div className="research-reading-column">
      <header className="research-header"><div><h1>{showingReport?(job?.title||report?.job_context?.company||"公司研究"):"想了解哪家公司或岗位？"}</h1><p>{showingReport?`${job?job.company+" · ":"公司研究 · "}${report&&new Date(report.created_at).toLocaleString()} · ${report&&reportStatus(report)}`:job?`${job.company} · ${job.title}`:"直接输入公司问题；岗位链接是可选资料。"}</p></div></header>
      {historyOpen&&<section className="research-history-panel" aria-label="历史报告"><div className="research-history-title"><strong>历史报告</strong>{job&&<label><input type="checkbox" checked={allHistory} onChange={event=>setAllHistory(event.target.checked)}/> 查看所有岗位</label>}</div>{history.length?<div className="research-history-list">{history.map(item=><div className="research-history-row" key={item.report_id}><button disabled={!!busy} aria-pressed={report?.report_id===item.report_id&&showingReport} onClick={()=>{openSaved(item);setHistoryOpen(false);}}><strong>{item.job_id?`${item.job_context?.company||"公司未知"} · ${item.job_context?.title||"岗位未知"}`:`${item.job_context?.company||"公司未知"} · 公司研究`}</strong><small>{new Date(item.created_at).toLocaleString()} · {reportStatus(item)}{item.job_context?.interest_question?` · 问：${item.job_context.interest_question}`:""}</small></button><button disabled={!!busy} onClick={()=>setHideId(item.report_id)}>移除</button>{hideId===item.report_id&&<div className="history-confirm" role="alert"><p>从列表移除这份报告？本机证据快照保留。</p><div className="button-row"><button disabled={!!busy} onClick={()=>void hideReport(item)}>确认移除</button><button onClick={()=>setHideId("")}>取消</button></div></div>}</div>)}</div>:<p className="research-empty-note">这里还没有报告。提出公司问题即可开始。</p>}</section>}
      {job&&!showingReport&&unknownCompanies.has(job.company)&&<label className="research-company-supplement">公司全称<input value={contextCompany} maxLength={300} onChange={event=>setContextCompany(event.target.value)} placeholder="填写可核对的公司全称"/></label>}
      {showingReport&&report&&<ReputationEvidence report={report} workspaceId={workspaceId!} onReport={value=>{setReport(value);keepReports(reports.map(item=>item.report_id===value.report_id?value:item));}} onSource={value=>openBrowser({sourceId:"web",url:value,title:"研究来源"})}/>}
    </div></div>
    {message&&<p className="research-inline-status" role="status">{message}</p>}
    <form className="research-composer" aria-label="研究输入框" onSubmit={event=>{event.preventDefault();submitInput();}}>
      <div className="research-composer-context"><strong>{showingReport?"继续提问":"提问"}</strong>{contextLabel&&<span title={contextLabel}>{contextLabel}</span>}</div>
      <textarea ref={inputRef} rows={2} aria-label="岗位链接与研究问题" value={question} maxLength={700} disabled={!!busy} onChange={event=>{setQuestion(event.target.value);setCandidate(undefined);setMessage("");}} onKeyDown={event=>{if(event.key==="Enter"&&!event.shiftKey&&!event.nativeEvent.isComposing){event.preventDefault();submitInput();}}} placeholder={job?"继续问这个岗位或公司，也可贴链接":"问一家公司，或粘贴岗位链接"}/>
      {clarify==="company"&&<label className="research-clarify">公司名称<input aria-label="研究公司名称" value={contextCompany} maxLength={80} onChange={event=>{setContextCompany(event.target.value);setMessage("");}} placeholder="例如：合成科技"/></label>}
      {clarify==="role"&&<label className="research-clarify">岗位名称<input aria-label="研究岗位名称" value={contextTitle} maxLength={100} onChange={event=>{setContextTitle(event.target.value);setMessage("");}} placeholder="例如：AI 工程师"/></label>}
      {candidate&&<div className="research-candidate"><strong>{candidate.company} · {candidate.title}</strong><span title={candidate.description}>{candidate.description?candidate.description.slice(0,120):"岗位原文不完整"}</span><button type="button" disabled={!!busy} onClick={()=>void confirmCandidate()}>确认岗位</button></div>}
      <div className="research-composer-actions"><div className="button-row">{busy==="research"&&<button type="button" onClick={()=>void cancel()}>取消</button>}<button type="submit" className="primary-button" disabled={!!busy||!!candidate}>{busy==="link"?"读取中…":busy==="research"?"研究中…":"发送 ↑"}</button></div></div>
    </form>
  </div>;
}
