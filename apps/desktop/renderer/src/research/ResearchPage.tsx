import {useEffect,useRef,useState} from "react";
import {createPortal} from "react-dom";
import type {BootstrapData,ModelConnection,ResearchReport,SearchResultItem} from "../../../shared/contracts";
import {reportJob,reportMatchesJob,reportStatus} from "../../../shared/research-reports";
import {isAllowedSourceUrl,isSourceBrowserId,sourceBrowserSpecs} from "../../../shared/source-browser-policy";
import {userError} from "../../../shared/user-errors";
import {splitResearchInput} from "../../../shared/research-input";
import {resolveResearchSession} from "../../../shared/research-session";
import {modelHistoryWithinBudget} from "../../../shared/research-chat-ipc";
import {useOriginalBrowser} from "../shared/Workbench";
import {ReputationEvidence} from "./ReputationEvidence";
import {getCurrentModel,setCurrentModel} from "../settings/current-model";
import {acceptsResearchDelta,beginChat,failChat,finishChat,fromStoredResearchChat,loadResearchChats,mergeResearchChats,migrateResearchChats,reportIdsByTurn,saveResearchChats,toStoredResearchChat,type ActiveResearchRequest,type SavedResearchChat} from "../../../shared/research-chat-history";

type Job=SearchResultItem["job"];
type Props={onReports(value:ResearchReport[]):void;active:boolean;data?:BootstrapData;target?:Job;onBack():void;onError(message?:string):void};

export function ResearchPage({active,data,target,onBack,onError,onReports}:Props){
  const workspaceId=data?.workspaces[0]?.workspace_id;
  const [job,setJob]=useState<Job|undefined>(target);
  const [report,setReport]=useState<ResearchReport>();
  const [reports,setReports]=useState<ResearchReport[]>([]);
  const [mode,setMode]=useState<"start"|"report">("start");
  const [historyOpen,setHistoryOpen]=useState(false);
  const [hideId,setHideId]=useState("");
  const [candidate,setCandidate]=useState<Awaited<ReturnType<NonNullable<typeof window.jobfindsme>["resolveResearchLink"]>>>();
  const [topbarTarget,setTopbarTarget]=useState<HTMLElement|null>(null);
  const [contextCompany,setContextCompany]=useState("");
  const [contextTitle,setContextTitle]=useState("");
  const [question,setQuestion]=useState("");
  const [connections,setConnections]=useState<ModelConnection[]>([]);
  const [modelId,setModelId]=useState<string|null>(null);
  const [chats,setChats]=useState<SavedResearchChat[]>([]);
  const [loadedWorkspace,setLoadedWorkspace]=useState<string|null>(null);
  const [chatId,setChatId]=useState<string|null>(null);
  const [chatBusy,setChatBusy]=useState(false);
  const [streaming,setStreaming]=useState("");
  const streamingRef=useRef("");
  const requestRef=useRef<ActiveResearchRequest|null>(null);
  const workspaceRef=useRef(workspaceId);
  workspaceRef.current=workspaceId;
  const inputRef=useRef<HTMLTextAreaElement>(null);
  const scrollRef=useRef<HTMLDivElement>(null);
  const historyButtonRef=useRef<HTMLButtonElement>(null);
  const historyCloseRef=useRef<HTMLButtonElement>(null);
  const saveQueue=useRef<Promise<unknown>>(Promise.resolve());
  const [busy,setBusy]=useState<"link"|"prepare"|"history"|null>(null);
  const [message,setMessage]=useState("");
  const sequence=useRef(0);
  const lastOpened=useRef<string|undefined>(undefined);
  const openBrowser=useOriginalBrowser();
  function closeHistory(restoreFocus=true){setHistoryOpen(false);if(restoreFocus)requestAnimationFrame(()=>historyButtonRef.current?.focus());}
  function keepReports(values:ResearchReport[]){setReports(values);onReports(values);}
  function openSaved(value:ResearchReport){sequence.current++;lastOpened.current=value.report_id;scrollRef.current?.scrollTo({top:0});setChatId(null);setJob(value.job_id?reportJob(value):undefined);setReport(value);setMode("report");setCandidate(undefined);setContextCompany(value.job_id?"":value.job_context?.company||"");setContextTitle(value.job_id?"":value.job_context?.title||"");setQuestion("");setMessage("");setBusy(null);}
  useEffect(()=>setTopbarTarget(document.getElementById("research-topbar-actions")),[]);
  useEffect(()=>{if(!historyOpen)return;historyCloseRef.current?.focus();const onKey=(event:KeyboardEvent)=>{if(event.key==="Escape"){event.preventDefault();closeHistory();}};window.addEventListener("keydown",onKey);return()=>window.removeEventListener("keydown",onKey);},[historyOpen]);
  useEffect(()=>{if(!workspaceId)return;let cancelled=false;const cached=loadResearchChats(workspaceId);setLoadedWorkspace(null);setChats(cached);setReports([]);setChatId(null);setChatBusy(false);setStreaming("");streamingRef.current="";setModelId(getCurrentModel(workspaceId));void window.jobfindsme!.listResearchChats(workspaceId).then(async rows=>{if(cancelled)return;const remote=rows.map(fromStoredResearchChat);try{const verified=await migrateResearchChats(workspaceId,cached,remote,item=>window.jobfindsme!.saveResearchChat(item),()=>window.jobfindsme!.listResearchChats(workspaceId));if(cancelled)return;setChats(verified);}catch(error){if(cancelled)return;setChats(mergeResearchChats(cached,remote));setMessage(`历史迁移未完成，设备缓存已保留：${userError(error).message}`);}setLoadedWorkspace(workspaceId);}).catch(error=>{if(!cancelled){setLoadedWorkspace(workspaceId);setMessage(`对话记录暂未从本地服务加载；当前显示设备缓存：${userError(error).message}`);}});return()=>{cancelled=true;const active=requestRef.current;if(active?.workspaceId===workspaceId){requestRef.current=null;void(active.kind==="model"?window.jobfindsme!.cancelResearchChat(active.id):window.jobfindsme!.cancelResearch());}};},[workspaceId]);
  useEffect(()=>{if(!workspaceId||loadedWorkspace!==workspaceId)return;if(!saveResearchChats(workspaceId,chats))setMessage("历史对话未能写入设备缓存，请检查可用空间。");for(const chat of chats){saveQueue.current=saveQueue.current.catch(()=>undefined).then(()=>window.jobfindsme!.saveResearchChat(toStoredResearchChat(workspaceId,chat))).catch(error=>{setMessage(`对话记录未能写入本地服务：${userError(error).message}。设备缓存仍保留，请重试。`);});}},[workspaceId,loadedWorkspace,chats]);
  useEffect(()=>{if(!active)return;void window.jobfindsme!.listModelConnections().then(values=>{setConnections(values);const saved=getCurrentModel(workspaceId);setModelId(saved&&values.some(value=>value.connection_id===saved&&value.status==="verified")?saved:null);}).catch(error=>onError(userError(error).message));},[active,workspaceId]);
  useEffect(()=>window.jobfindsme!.onResearchChatDelta(event=>{if(!acceptsResearchDelta(requestRef.current,event,workspaceRef.current))return;streamingRef.current+=event.delta;setStreaming(streamingRef.current);}),[]);
  useEffect(()=>{sequence.current++;lastOpened.current=undefined;setChatId(null);setJob(target);setReport(undefined);setMode("start");setCandidate(undefined);setContextCompany("");setContextTitle("");setHistoryOpen(false);setQuestion("");setMessage("");setBusy(null);},[target?.job_id]);
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
    try{const next=await window.jobfindsme!.prepareResearchJob({workspace_id:workspaceId,url:candidate.url,title:candidate.title,company:candidate.company,description:candidate.description});if(id!==sequence.current)return;setJob(next);setCandidate(undefined);setContextCompany("");setContextTitle("");setReport(undefined);setMode("start");lastOpened.current=undefined;setQuestion(splitResearchInput(question).question);setMessage("岗位已确认，可以继续提问。");}
    catch(error){if(id===sequence.current)setMessage(userError(error).message);}
    finally{if(id===sequence.current)setBusy(null);}
  }
  async function sendChat(value:string){
    if(!workspaceId||chatBusy||loadedWorkspace!==workspaceId)return;
    const prior=chats.find(item=>item.id===chatId);
    const {decision,newSubject,current,currentCompany,activeJobId,sameJob}=resolveResearchSession(value,prior,job,{company:contextCompany,title:contextTitle});
    const id=current?.id||crypto.randomUUID();
    const at=new Date().toISOString();
    const started=beginChat(current,id,value,at);
    if(decision.kind!=="clarify"&&!modelId){setMessage("请先在模型设置中选择一个已测试模型。提问已保留。");return;}
    setChatId(id);
    if(decision.kind==="clarify"){
      const clarified={...finishChat(started.chat,decision.reply,undefined,at),pendingResearch:decision.pending};
      setChats(items=>[clarified,...items.filter(item=>item.id!==id)]);setQuestion("");setMessage("");return;
    }
    if(decision.kind==="research"){
      if(newSubject)setJob(undefined);
      setContextCompany(decision.company);setContextTitle(decision.title||"");
    }
    const selected=modelId?connections.find(item=>item.connection_id===modelId&&item.status==="verified"):undefined;
    if(modelId&&!selected){setMessage("请先在模型设置中保存并测试一个模型。");return;}
    if(!selected){setMessage("请先在模型设置中选择一个已测试模型。提问已保留。");return;}
    const requestId=crypto.randomUUID();requestRef.current={id:requestId,workspaceId,sessionId:id,kind:"model"};
    const startedChat={...started.chat,subjectCompany:decision.kind==="research"?decision.company:current?.subjectCompany,subjectTitle:decision.kind==="research"?decision.title:current?.subjectTitle,jobId:activeJobId,researchMode:decision.kind==="research"};
    setChats(items=>[startedChat,...items.filter(item=>item.id!==id)]);
    setQuestion("");streamingRef.current="";setStreaming("");setMessage("");setChatBusy(true);
    try{
      const result=await window.jobfindsme!.runResearchChat({request_id:requestId,session_id:id,workspace_id:workspaceId,connection_id:selected.connection_id,question:decision.kind==="research"?decision.question:value,research:decision.kind==="research",job_id:sameJob?activeJobId:undefined,company:decision.kind==="research"?decision.company:undefined,title:decision.kind==="research"?decision.title:undefined,history:modelHistoryWithinBudget(started.history)});
      if(requestRef.current?.id!==requestId||workspaceRef.current!==workspaceId)return;
      setChats(items=>items.map(item=>item.id===id?finishChat(item,result.text,result.report?.report_id,new Date().toISOString()):item));
      if(result.report){const values=await window.jobfindsme!.listResearchReports(workspaceId);if(requestRef.current?.id===requestId&&workspaceRef.current===workspaceId){keepReports(values);lastOpened.current=result.report.report_id;setReport(result.report);setMode("report");}}
      streamingRef.current="";setStreaming("");
    }catch(error){if(requestRef.current?.id===requestId&&workspaceRef.current===workspaceId){setChats(items=>items.map(item=>item.id===id?failChat(item,userError(error).message,new Date().toISOString()):item));setQuestion(value);setMessage(`本次对话未完成：${userError(error).message}。提问已保留，可直接重试。`);try{keepReports(await window.jobfindsme!.listResearchReports(workspaceId));}catch{}}}
    finally{if(requestRef.current?.id===requestId){requestRef.current=null;setChatBusy(false);setStreaming("");streamingRef.current="";}}
  }
  async function cancelChat(){const active=requestRef.current;if(!active)return;requestRef.current=null;setChatBusy(false);setStreaming("");streamingRef.current="";setQuestion(chats.find(item=>item.id===active.sessionId)?.draft||"");try{if(active.kind==="model")await window.jobfindsme!.cancelResearchChat(active.id);else await window.jobfindsme!.cancelResearch();setMessage("已停止；当前提问会保留。");}catch(error){setMessage(userError(error).message);}}
  async function hideReport(value:ResearchReport){
    if(!workspaceId)return;setBusy("history");setMessage("");
    try{await window.jobfindsme!.hideResearchReport(workspaceId,value.report_id);const next=await window.jobfindsme!.listResearchReports(workspaceId);keepReports(next);if(report?.report_id===value.report_id){const previous=next.find(item=>job&&reportMatchesJob(item,job)&&item.outcome!=="failed");if(previous)openSaved(previous);else{setReport(undefined);setMode("start");lastOpened.current=undefined;}}setHideId("");setMessage("已从历史列表移除，原始证据快照仍保存在本机。");}
    catch(error){setMessage(userError(error).message);}finally{setBusy(null);}
  }
  function openOriginal(value:string){const id=Object.keys(sourceBrowserSpecs).find(key=>isSourceBrowserId(key)&&isAllowedSourceUrl(key,value));if(id)openBrowser({sourceId:id,url:value,title:job?.title||"岗位原页"});else setMessage("请使用已登记招聘来源的岗位详情链接。");}
  const history=reports;
  const showingReport=mode==="report"&&!!report;
  function submitInput(){
    if(busy||chatBusy)return;
    const parsed=splitResearchInput(question);
    if(parsed.error){setCandidate(undefined);setMessage(parsed.error);return;}
    if(parsed.url){void readLink(parsed.url);return;}
    if(candidate){setMessage("请先确认读取到的岗位，再开始研究。");return;}
    if(!parsed.question){setMessage("请输入消息，或粘贴岗位链接。");return;}
    void sendChat(parsed.question);
  }
  const centeredEmpty=!showingReport&&!chatId&&!job&&!contextCompany&&!message;
  const activeChat=chats.find(item=>item.id===chatId);
  const chatReportIds=activeChat?reportIdsByTurn(activeChat,reports):new Map<number,string>();
  const reportsById=new Map(reports.map(item=>[item.report_id,item]));
  function updateShownReport(value:ResearchReport){setReport(current=>current?.report_id===value.report_id?value:current);keepReports(reports.map(item=>item.report_id===value.report_id?value:item));}
  function selectHistoryChat(item:SavedResearchChat){
    scrollRef.current?.scrollTo({top:0});setChatId(item.id);
    const latest=[...item.reportIds].reverse().map(id=>reportsById.get(id)).find(Boolean);
    setReport(latest);setMode(latest?"report":"start");setJob(latest?.job_id?reportJob(latest):undefined);
    setContextCompany(item.subjectCompany||"");setContextTitle(item.subjectTitle||"");setQuestion(item.draft||"");
    closeHistory(false);setMessage(item.failure||"");requestAnimationFrame(()=>scrollRef.current?.focus());
  }
  function selectHistoryReport(item:ResearchReport){openSaved(item);closeHistory(false);requestAnimationFrame(()=>scrollRef.current?.focus());}
  return <div className="research-page research-workbench">
    {active&&topbarTarget&&createPortal(<div className="button-row" aria-label="研究操作">
      {showingReport?<button onClick={()=>{setMode("start");setMessage("");}}>← 研究首页</button>:<button onClick={onBack}>← 找工作</button>}
      <button disabled={chatBusy} onClick={()=>{closeHistory(false);scrollRef.current?.scrollTo({top:0});setChatId(null);setJob(undefined);setContextCompany("");setContextTitle("");setQuestion("");setCandidate(undefined);setReport(undefined);setMode("start");setStreaming("");setMessage("");inputRef.current?.focus();}}>新对话</button>
      <button ref={historyButtonRef} aria-expanded={historyOpen} aria-controls="research-history-panel" onClick={()=>historyOpen?closeHistory():setHistoryOpen(true)}>历史{history.length+chats.length?` · ${history.length+chats.length}`:""}</button>
      {(showingReport||job)&&<details className="research-more"><summary>更多</summary><div className="research-more-menu"><button onClick={onBack}>返回找工作</button>{job&&<button onClick={()=>openOriginal(job.apply_url)}>岗位原页 ↗</button>}</div></details>}
    </div>,topbarTarget)}
    <div ref={scrollRef} className={`research-scroll-region${centeredEmpty?" research-empty-state":""}`} role="region" aria-label="研究报告正文" tabIndex={0}><div className="research-reading-column">
      {(!activeChat||showingReport)&&<header className="research-header"><div><h1>{showingReport?(job?.title||report?.job_context?.company||"公司研究"):"想了解哪家公司或岗位？"}</h1><p>{showingReport?`${job?job.company+" · ":"公司研究 · "}${report&&new Date(report.created_at).toLocaleString()} · ${report&&reportStatus(report)}`:job?`${job.company} · ${job.title}`:"直接输入公司问题；岗位链接是可选资料。"}</p></div></header>}
      {activeChat&&<section className="research-chat-messages" aria-label="对话内容">
        {activeChat.subjectCompany&&<p className="research-empty-note">当前对话：{activeChat.subjectCompany}{activeChat.subjectTitle?` · ${activeChat.subjectTitle}`:""}</p>}
        {activeChat.turns.map((item,index)=>{
          const attached=chatReportIds.get(index);
          const attachedReport=attached?reportsById.get(attached):undefined;
          return <article className={`research-chat-turn ${item.role}`} key={`${activeChat.id}-${index}`}>
            <strong>{item.role==="user"?"你":"研究助手"}</strong>
            {attachedReport?<ReputationEvidence report={attachedReport} workspaceId={workspaceId!} onReport={updateShownReport} onSource={value=>openBrowser({sourceId:"web",url:value,title:"研究来源"})}/>:<p>{item.text}</p>}
          </article>;
        })}
        {chatBusy&&<article className="research-chat-turn assistant" aria-live="polite"><strong>研究助手</strong><p>{streaming||"正在处理…"}</p></article>}
        {activeChat.failure&&!chatBusy&&<p className="research-chat-failure" role="status">{activeChat.failure} · 输入框已保留提问，可重试。</p>}
      </section>}
      {!activeChat&&showingReport&&report&&<ReputationEvidence report={report} workspaceId={workspaceId!} onReport={updateShownReport} onSource={value=>openBrowser({sourceId:"web",url:value,title:"研究来源"})}/>}
    </div></div>
    {historyOpen&&<aside id="research-history-panel" className="research-history-panel" role="dialog" aria-label="历史对话与报告" aria-modal="false">
      <div className="research-history-heading"><strong>历史</strong><button ref={historyCloseRef} type="button" aria-label="关闭历史" onClick={()=>closeHistory()}>关闭</button></div>
      <div className="research-history-body">
        <div className="research-history-title"><strong>历史对话</strong></div>
        <div className="research-history-list">{chats.map(item=><div className="research-history-row" key={item.id}><button disabled={chatBusy} aria-pressed={chatId===item.id} onClick={()=>selectHistoryChat(item)}><strong>{item.title}</strong><small>{new Date(item.updatedAt).toLocaleString()} · {item.turns.length} 条消息</small></button></div>)}</div>
        <div className="research-history-title"><strong>历史报告</strong></div>
        {history.length?<div className="research-history-list">{history.map(item=><div className="research-history-row" key={item.report_id}><button disabled={!!busy||chatBusy} aria-pressed={report?.report_id===item.report_id&&showingReport} onClick={()=>selectHistoryReport(item)}><strong>{item.job_id?`${item.job_context?.company||"公司未知"} · ${item.job_context?.title||"岗位未知"}`:`${item.job_context?.company||"公司未知"} · 公司研究`}</strong><small>{new Date(item.created_at).toLocaleString()} · {reportStatus(item)}{item.job_context?.interest_question?` · 问：${item.job_context.interest_question}`:""}</small></button><button disabled={!!busy||chatBusy} onClick={()=>setHideId(item.report_id)}>移除</button>{hideId===item.report_id&&<div className="history-confirm" role="alert"><p>从列表移除这份报告？本机证据快照保留。</p><div className="button-row"><button disabled={!!busy} onClick={()=>void hideReport(item)}>确认移除</button><button onClick={()=>setHideId("")}>取消</button></div></div>}</div>)}</div>:<p className="research-empty-note">这里还没有报告。提出公司问题即可开始。</p>}
      </div>
    </aside>}
    {message&&<p className="research-inline-status" role="status">{message}</p>}
    <form className="research-composer" aria-label="研究输入框" onSubmit={event=>{event.preventDefault();submitInput();}}>
      <textarea ref={inputRef} rows={2} aria-label="岗位链接与研究问题" value={question} maxLength={2200} disabled={!!busy||chatBusy} onChange={event=>{setQuestion(event.target.value);setCandidate(undefined);setMessage("");}} onKeyDown={event=>{if(event.key==="Enter"&&!event.shiftKey&&!event.nativeEvent.isComposing){event.preventDefault();submitInput();}}} placeholder={job?"继续问这个岗位或公司，也可贴链接":"自由对话、研究公司，或粘贴岗位链接"}/>
      {candidate&&<div className="research-candidate"><strong>{candidate.company} · {candidate.title}</strong><span title={candidate.description}>{candidate.description?candidate.description.slice(0,120):"岗位原文不完整"}</span><button type="button" disabled={!!busy} onClick={()=>void confirmCandidate()}>确认岗位</button></div>}
      <div className="research-composer-actions"><select aria-label="当前使用模型" value={modelId||""} onChange={event=>{const value=event.target.value;setModelId(value||null);if(value)setCurrentModel(workspaceId,value);}}><option value="">选择模型</option>{connections.filter(item=>item.status==="verified").map(item=><option key={item.connection_id} value={item.connection_id}>{item.provider} · {item.model_id}</option>)}</select><div className="button-row">{chatBusy&&<button type="button" onClick={()=>void cancelChat()}>停止</button>}<button type="submit" className="primary-button" disabled={!!busy||chatBusy||!!candidate}>{busy==="link"?"读取中…":chatBusy?"处理中…":"发送 ↑"}</button></div></div>
    </form>
  </div>;
}
