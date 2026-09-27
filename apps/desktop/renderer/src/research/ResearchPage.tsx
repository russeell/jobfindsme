import {useEffect,useRef,useState} from "react";
import {createPortal} from "react-dom";
import type {BootstrapData,ModelConnection,ResearchReport,SearchResultItem} from "../../../shared/contracts";
import {reportJob,reportMatchesJob,reportStatus} from "../../../shared/research-reports";
import {isAllowedSourceUrl,isPublicWebUrl,isSourceBrowserId,sourceBrowserSpecs} from "../../../shared/source-browser-policy";
import {userError} from "../../../shared/user-errors";
import {splitResearchInput} from "../../../shared/research-input";
import {resolveResearchSession} from "../../../shared/research-session";
import {modelHistoryWithinBudget} from "../../../shared/research-chat-ipc";
import {useOriginalBrowser} from "../shared/Workbench";
import {Icon} from "../shared/Icon";
import {ReputationEvidence} from "./ReputationEvidence";
import {MessageContent} from "./MessageContent";
import {getCurrentModel,setCurrentModel} from "../settings/current-model";
import {acceptsResearchDelta,beginChat,failChat,finishChat,finishJobSearchChat,fromStoredResearchChat,legacyChatsForMigration,loadResearchChats,migrateResearchChats,reportIdsByTurn,saveResearchChats,saveResearchChatWithRetry,toStoredResearchChat,type ActiveResearchRequest,type SavedResearchChat} from "../../../shared/research-chat-history";

type Job=SearchResultItem["job"];
type Props={onReports(value:ResearchReport[]):void;active:boolean;data?:BootstrapData;target?:Job;onSearchJobs(query:string):void;onError(message?:string):void};

export function ResearchPage({active,data,target,onSearchJobs,onError,onReports}:Props){
  const workspaceId=data?.workspaces[0]?.workspace_id;
  const [job,setJob]=useState<Job|undefined>(target);
  const [report,setReport]=useState<ResearchReport>();
  const [reports,setReports]=useState<ResearchReport[]>([]);
  const [mode,setMode]=useState<"start"|"report">("start");
  const [historySection,setHistorySection]=useState<"chats"|"archived"|"reports">("chats");
  const [archivedChats,setArchivedChats]=useState<SavedResearchChat[]>([]);
  const [deleteId,setDeleteId]=useState("");
  const [hideId,setHideId]=useState("");
  const [candidate,setCandidate]=useState<Awaited<ReturnType<NonNullable<typeof window.jobfindsme>["resolveResearchLink"]>>>();
  const [topbarTarget,setTopbarTarget]=useState<HTMLElement|null>(null);
  const [sidebarTarget,setSidebarTarget]=useState<HTMLElement|null>(null);
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
  const [liveProcess,setLiveProcess]=useState("");
  const [focusedCitation,setFocusedCitation]=useState<{turn:number;number:number}|null>(null);
  const streamingRef=useRef("");
  const requestRef=useRef<ActiveResearchRequest|null>(null);
  const workspaceRef=useRef(workspaceId);
  workspaceRef.current=workspaceId;
  const inputRef=useRef<HTMLTextAreaElement>(null);
  const scrollRef=useRef<HTMLDivElement>(null);
  const saveQueue=useRef<Promise<unknown>>(Promise.resolve());
  const savedChats=useRef(new Map<string,string>());
  const [busy,setBusy]=useState<"link"|"prepare"|"history"|null>(null);
  const [message,setMessage]=useState("");
  const sequence=useRef(0);
  const lastOpened=useRef<string|undefined>(undefined);
  const openBrowser=useOriginalBrowser();
  function keepReports(values:ResearchReport[]){setReports(values);onReports(values);}
  function openSaved(value:ResearchReport){sequence.current++;lastOpened.current=value.report_id;scrollRef.current?.scrollTo({top:0});setChatId(null);setJob(value.job_id?reportJob(value):undefined);setReport(value);setMode("report");setCandidate(undefined);setContextCompany(value.job_id?"":value.job_context?.company||"");setContextTitle(value.job_id?"":value.job_context?.title||"");setQuestion("");setMessage("");setBusy(null);}
  useEffect(()=>{setTopbarTarget(document.getElementById("research-topbar-actions"));setSidebarTarget(document.getElementById("research-sidebar-history"));},[]);
  useEffect(()=>{
    if(!workspaceId)return;
    let cancelled=false;
    const cached=loadResearchChats(workspaceId);
    const migrationKey=`jobfindsme:research-chat-migrated:${workspaceId}`;
    const alreadyMigrated=localStorage.getItem(migrationKey)==="1";
    savedChats.current.clear();setLoadedWorkspace(null);setChats(alreadyMigrated?[]:cached);setArchivedChats([]);setReports([]);setChatId(null);setChatBusy(false);setStreaming("");streamingRef.current="";setModelId(getCurrentModel(workspaceId));
    void Promise.all([window.jobfindsme!.listResearchChats(workspaceId),window.jobfindsme!.listArchivedResearchChats(workspaceId)]).then(async([rows,archivedRows])=>{
      if(cancelled)return;
      const remote=rows.map(fromStoredResearchChat),archived=archivedRows.map(fromStoredResearchChat);
      const archivedIds=new Set(archived.map(item=>item.id));
      const legacy=legacyChatsForMigration(cached,archivedIds,alreadyMigrated);
      try{
        const verified=await migrateResearchChats(workspaceId,legacy,remote,item=>window.jobfindsme!.saveResearchChat(item),()=>window.jobfindsme!.listResearchChats(workspaceId));
        if(cancelled)return;
        localStorage.setItem(migrationKey,"1");
        for(const chat of verified)savedChats.current.set(chat.id,JSON.stringify(toStoredResearchChat(workspaceId,chat)));
        setChats(verified);setArchivedChats(archived);setLoadedWorkspace(workspaceId);
      }catch(error){if(!cancelled){setChats(alreadyMigrated?[]:cached);setArchivedChats(archived);setMessage(`历史迁移未完成，设备缓存已保留：${userError(error).message}`);}}
    }).catch(error=>{if(!cancelled)setMessage(`对话记录暂未从本地服务加载：${userError(error).message}`);});
    return()=>{cancelled=true;const running=requestRef.current;if(running?.workspaceId===workspaceId){requestRef.current=null;void(running.kind==="model"?window.jobfindsme!.cancelResearchChat(running.id):window.jobfindsme!.cancelResearch());}};
  },[workspaceId]);
  useEffect(()=>{if(!workspaceId||loadedWorkspace!==workspaceId)return;if(!saveResearchChats(workspaceId,chats))setMessage("历史对话未能写入设备缓存，请检查可用空间。");for(const chat of chats){const stored=toStoredResearchChat(workspaceId,chat),serialized=JSON.stringify(stored);if(savedChats.current.get(chat.id)===serialized)continue;savedChats.current.set(chat.id,serialized);saveQueue.current=saveQueue.current.catch(()=>undefined).then(()=>saveResearchChatWithRetry(stored,item=>window.jobfindsme!.saveResearchChat(item))).catch(error=>{if(savedChats.current.get(chat.id)===serialized)savedChats.current.delete(chat.id);setMessage(`对话记录未能写入本地服务：${userError(error).message}。设备缓存仍保留，请重试。`);});}},[workspaceId,loadedWorkspace,chats]);
  useEffect(()=>{if(!active)return;void window.jobfindsme!.listModelConnections().then(values=>{setConnections(values);const saved=getCurrentModel(workspaceId);setModelId(saved&&values.some(value=>value.connection_id===saved&&value.status==="verified")?saved:null);}).catch(error=>onError(userError(error).message));},[active,workspaceId]);
  useEffect(()=>window.jobfindsme!.onResearchChatDelta(event=>{if(!acceptsResearchDelta(requestRef.current,event,workspaceRef.current))return;
    if(event.progress){const label=({find_evidence:"核对已存材料",search_web:"搜索公开来源",read_page:"读取原页",read_browser_page:"浏览器读取原页",read_job:"读取已存岗位"} as Record<string,string>)[event.progress.tool]||"处理来源";setLiveProcess(`${label}${event.progress.status==="started"?"中…":event.progress.status==="failed"?"失败":"完成"}`);return;}
    if(event.delta){streamingRef.current+=event.delta;setStreaming(streamingRef.current);}
  }),[]);
  useEffect(()=>{sequence.current++;lastOpened.current=undefined;setChatId(null);setJob(target);setReport(undefined);setMode("start");setCandidate(undefined);setContextCompany("");setContextTitle("");setQuestion("");setMessage("");setBusy(null);},[target?.job_id]);
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
    const {decision,newSubject,current,currentCompany,activeJobId}=resolveResearchSession(value,prior,job,{company:contextCompany,title:contextTitle});
    const id=current?.id||crypto.randomUUID();
    const at=new Date().toISOString();
    const started=beginChat(current,id,value,at);
    if(decision.kind!=="job_search"&&!modelId){setMessage("请先在模型设置中选择一个已测试模型。提问已保留。");return;}
    setChatId(id);
    if(decision.kind==="job_search"){
      const guided=finishJobSearchChat(started.chat,decision.reply,decision.query,decision.pending,at);
      if(decision.company)setContextCompany(decision.company);
      setChats(items=>[{...guided,subjectCompany:decision.company||current?.subjectCompany},...items.filter(item=>item.id!==id)]);
      setQuestion("");setMessage("");return;
    }
    if(decision.kind==="research"){
      if(newSubject)setJob(undefined);
      setContextCompany(decision.company);setContextTitle(decision.title||"");
    }
    const selected=modelId?connections.find(item=>item.connection_id===modelId&&item.status==="verified"):undefined;
    if(modelId&&!selected){setMessage("请先在模型设置中保存并测试一个模型。");return;}
    if(!selected){setMessage("请先在模型设置中选择一个已测试模型。提问已保留。");return;}
    const requestId=crypto.randomUUID();requestRef.current={id:requestId,workspaceId,sessionId:id,kind:"model"};
    const companyHint=decision.kind==="research"?decision.company:decision.kind==="clarify"&&"company" in decision.pending?decision.pending.company:currentCompany;
    const startedChat={...started.chat,subjectCompany:companyHint||current?.subjectCompany,subjectTitle:decision.kind==="research"?decision.title:current?.subjectTitle,jobId:activeJobId,researchMode:decision.kind!=="chat"};
    setChats(items=>[startedChat,...items.filter(item=>item.id!==id)]);
    setQuestion("");streamingRef.current="";setStreaming("");setLiveProcess("");setMessage("");setChatBusy(true);
    try{
      const result=await window.jobfindsme!.runResearchChat({request_id:requestId,session_id:id,workspace_id:workspaceId,connection_id:selected.connection_id,question:decision.kind==="research"?decision.question:value,research:decision.kind==="research",job_id:activeJobId,company:companyHint,title:decision.kind==="research"?decision.title:undefined,history:modelHistoryWithinBudget(started.history)});
      if(requestRef.current?.id!==requestId||workspaceRef.current!==workspaceId)return;
      setChats(items=>items.map(item=>{if(item.id!==id)return item;const finished=finishChat(item,result.text,result.report?.report_id,new Date().toISOString(),{evidence:result.evidence,process:result.process});return {...finished,subjectCompany:result.company||finished.subjectCompany,researchMode:!!result.researched||finished.researchMode,pendingResearch:decision.kind==="clarify"&&!result.researched?decision.pending:undefined};}));
      if(result.report){const values=await window.jobfindsme!.listResearchReports(workspaceId);if(requestRef.current?.id===requestId&&workspaceRef.current===workspaceId){keepReports(values);lastOpened.current=result.report.report_id;setReport(result.report);}}
      streamingRef.current="";setStreaming("");setLiveProcess("");
    }catch(error){if(requestRef.current?.id===requestId&&workspaceRef.current===workspaceId){setChats(items=>items.map(item=>item.id===id?failChat(item,userError(error).message,new Date().toISOString()):item));setQuestion(value);setMessage(`本次对话未完成：${userError(error).message}。提问已保留，可直接重试。`);try{keepReports(await window.jobfindsme!.listResearchReports(workspaceId));}catch{}}}
    finally{if(requestRef.current?.id===requestId){requestRef.current=null;setChatBusy(false);setStreaming("");setLiveProcess("");streamingRef.current="";}}
  }
  async function cancelChat(){const active=requestRef.current;if(!active)return;requestRef.current=null;setChatBusy(false);setStreaming("");setLiveProcess("");streamingRef.current="";setQuestion(chats.find(item=>item.id===active.sessionId)?.draft||"");try{if(active.kind==="model")await window.jobfindsme!.cancelResearchChat(active.id);else await window.jobfindsme!.cancelResearch();setMessage("已停止；当前提问会保留。");}catch(error){setMessage(userError(error).message);}}
  async function hideReport(value:ResearchReport){
    if(!workspaceId)return;setBusy("history");setMessage("");
    try{await window.jobfindsme!.hideResearchReport(workspaceId,value.report_id);const next=await window.jobfindsme!.listResearchReports(workspaceId);keepReports(next);if(report?.report_id===value.report_id){const previous=next.find(item=>job&&reportMatchesJob(item,job)&&item.outcome!=="failed");if(previous)openSaved(previous);else{setReport(undefined);setMode("start");lastOpened.current=undefined;}}setHideId("");setMessage("已从历史列表移除，原始证据快照仍保存在本机。");}
    catch(error){setMessage(userError(error).message);}finally{setBusy(null);}
  }
  async function refreshChatHistory(id:string){
    const [activeRows,archivedRows]=await Promise.all([window.jobfindsme!.listResearchChats(id),window.jobfindsme!.listArchivedResearchChats(id)]);
    if(workspaceRef.current!==id)return;
    const activeChats=activeRows.map(fromStoredResearchChat);
    const archived=archivedRows.map(fromStoredResearchChat);
    savedChats.current=new Map(activeChats.map(item=>[item.id,JSON.stringify(toStoredResearchChat(id,item))]));
    setChats(activeChats);setArchivedChats(archived);
  }
  async function changeChatHistory(item:SavedResearchChat,action:"archive"|"restore"|"delete"){
    if(!workspaceId||loadedWorkspace!==workspaceId||chatBusy||busy)return;
    setBusy("history");setMessage("");
    try{
      await saveQueue.current;
      if(action==="archive")await window.jobfindsme!.archiveResearchChat(workspaceId,item.id);
      else if(action==="restore")await window.jobfindsme!.restoreResearchChat(workspaceId,item.id);
      else await window.jobfindsme!.deleteArchivedResearchChat(workspaceId,item.id);
      if(workspaceRef.current!==workspaceId)return;
      await refreshChatHistory(workspaceId);
      if(action==="archive"&&chatId===item.id){setChatId(null);setReport(undefined);setMode("start");}
      if(action==="delete")setDeleteId("");
      setMessage(action==="archive"?"对话已归档。":action==="restore"?"对话已恢复。":"归档对话已删除。");
    }catch(error){if(workspaceRef.current===workspaceId)setMessage(userError(error).message);}finally{if(workspaceRef.current===workspaceId)setBusy(null);}
  }
  function openOriginal(value:string){const id=Object.keys(sourceBrowserSpecs).find(key=>isSourceBrowserId(key)&&isAllowedSourceUrl(key,value));if(isPublicWebUrl(value))openBrowser({sourceId:id||"web",url:value,title:job?.title||"岗位原页"});else setMessage("该岗位原页链接不是可打开的公共网页。");}
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
  function showCitation(turn:number,number:number){
    setFocusedCitation({turn,number});
    const details=document.getElementById(`research-sources-${turn}`) as HTMLDetailsElement|null;
    if(details)details.open=true;
    requestAnimationFrame(()=>document.getElementById(`research-source-${turn}-${number}`)?.focus());
  }
  const historyGroup=(date:string)=>{const day=new Date(date).toDateString(),today=new Date(),yesterday=new Date(today);yesterday.setDate(today.getDate()-1);return day===today.toDateString()?"今天":day===yesterday.toDateString()?"昨天":"更早";};
  function updateShownReport(value:ResearchReport){setReport(current=>current?.report_id===value.report_id?value:current);keepReports(reports.map(item=>item.report_id===value.report_id?value:item));}
  function selectHistoryChat(item:SavedResearchChat){
    scrollRef.current?.scrollTo({top:0});setChatId(item.id);
    const latest=[...item.reportIds].reverse().map(id=>reportsById.get(id)).find(Boolean);
    setReport(latest);setMode(latest?"report":"start");setJob(latest?.job_id?reportJob(latest):undefined);
    setContextCompany(item.subjectCompany||"");setContextTitle(item.subjectTitle||"");setQuestion(item.draft||"");
    setMessage(item.failure||"");requestAnimationFrame(()=>scrollRef.current?.focus());
  }
  function selectHistoryReport(item:ResearchReport){openSaved(item);requestAnimationFrame(()=>scrollRef.current?.focus());}
  return <div className="research-page research-workbench">
    {active&&topbarTarget&&createPortal(<div className="button-row" aria-label="研究操作">
      <button disabled={chatBusy} onClick={()=>{scrollRef.current?.scrollTo({top:0});setChatId(null);setJob(undefined);setContextCompany("");setContextTitle("");setQuestion("");setCandidate(undefined);setReport(undefined);setMode("start");setStreaming("");setMessage("");inputRef.current?.focus();}}>新对话</button>
      {job&&<button onClick={()=>openOriginal(job.apply_url)}>岗位原页 ↗</button>}
    </div>,topbarTarget)}
    <div ref={scrollRef} className={`research-scroll-region${centeredEmpty?" research-empty-state":""}`} role="region" aria-label="求职助手对话" tabIndex={0}><div className="research-reading-column">
      {(!activeChat||showingReport)&&<header className="research-header"><div><h1>{showingReport?(job?.title||report?.job_context?.company||"公司研究"):"有什么求职问题？"}</h1><p>{showingReport?`${job?job.company+" · ":"公司研究 · "}${report&&new Date(report.created_at).toLocaleString()} · ${report&&reportStatus(report)}`:job?`${job.company} · ${job.title}`:"可以聊岗位、简历、面试，也可以了解公司。"}</p></div></header>}
      {activeChat&&<section className="research-chat-messages" aria-label="对话内容">
        {activeChat.researchMode&&activeChat.subjectCompany&&<p className="research-subject-caption">{activeChat.subjectCompany}{activeChat.subjectTitle?` · ${activeChat.subjectTitle}`:""}</p>}
        {activeChat.turns.map((item,index)=>{
          const attached=chatReportIds.get(index);
          const attachedReport=attached?reportsById.get(attached):undefined;
          return <article className={`research-chat-turn ${item.role}`} aria-label={item.role==="user"?"你":"求职助手"} key={`${activeChat.id}-${index}`}>
            {item.role==="assistant"?<MessageContent text={item.text} sources={attachedReport?.evidence||item.evidence} onCitation={number=>showCitation(index,number)}/>:<p>{item.text}</p>}
            {attachedReport?<details id={`research-sources-${index}`}><summary>来源与核验详情（{attachedReport.evidence.length}）</summary><ReputationEvidence report={attachedReport} workspaceId={workspaceId!} onReport={updateShownReport} onSource={value=>openBrowser({sourceId:"web",url:value,title:"研究来源"})} focusedEvidenceId={focusedCitation?.turn===index?attachedReport.evidence[focusedCitation.number-1]?.evidence_id:undefined}/></details>:item.evidence?.length?<details id={`research-sources-${index}`}><summary>来源片段（{item.evidence.length}）</summary>{item.evidence.map((source,sourceIndex)=><article id={`research-source-${index}-${sourceIndex+1}`} tabIndex={-1} className={`evidence-card${focusedCitation?.turn===index&&focusedCitation.number===sourceIndex+1?" research-source-focused":""}`} key={source.evidence_id}><strong>原文片段 [{sourceIndex+1}] · {source.platform}</strong><small>{source.context?.page?`第 ${source.context.page} 页 · `:""}{source.published_at||"发布时间未知"}</small><blockquote>{source.excerpt}</blockquote><p className="note">{source.limitations} · 读取于 {source.retrieved_at}</p>{source.url&&<button type="button" onClick={()=>openBrowser({sourceId:"web",url:source.url!,title:"研究来源"})}>查看原页 ↗</button>}</article>)}</details>:null}
            {!!item.process?.length&&<details className="research-diagnostics"><summary>检索与阅读过程（{item.process.length}）</summary><ol>{item.process.map((step,stepIndex)=><li key={stepIndex}>{({find_evidence:"核对已存材料",search_web:"发现网页",read_page:"读取原页",read_browser_page:"浏览器读取原页",answer_check:"核对陈述",completion_check:"补查缺口"} as Record<string,string>)[step.tool]||step.tool}{step.site?` · ${step.site}`:""} · {step.status}{typeof step.count==="number"?` · ${step.count} 条`:""}</li>)}</ol></details>}
            {item.searchQuery&&<button type="button" className="research-search-action" onClick={()=>onSearchJobs(item.searchQuery!)}>去找工作 · {item.searchQuery}</button>}
          </article>;
        })}
        {chatBusy&&<article className="research-chat-turn assistant" aria-label="求职助手" aria-live="polite"><MessageContent text={streaming||liveProcess||"正在处理…"}/>{streaming&&liveProcess&&<small className="note">{liveProcess}</small>}</article>}
        {activeChat.failure&&!chatBusy&&<p className="research-chat-failure" role="status">{activeChat.failure} · 输入框已保留提问，可重试。</p>}
      </section>}
      {!activeChat&&showingReport&&report&&<ReputationEvidence report={report} workspaceId={workspaceId!} onReport={updateShownReport} onSource={value=>openBrowser({sourceId:"web",url:value,title:"研究来源"})}/>}
    </div></div>
    {active&&sidebarTarget&&createPortal(<aside id="research-history-panel" className="research-history-sidebar" aria-label="历史对话与报告">
      <div className="research-history-heading">{historySection==="chats"?<strong>最近对话</strong>:<><button type="button" className="research-history-back" onClick={()=>setHistorySection("chats")}>← 最近</button><strong>{historySection==="archived"?"已归档":"历史报告"}</strong></>}</div>
      <div className="research-history-body">
        {historySection==="chats"&&(chats.length?<div className="research-history-list">{chats.map((item,index)=><div key={item.id}>{(index===0||historyGroup(chats[index-1].updatedAt)!==historyGroup(item.updatedAt))&&<p className="history-day">{historyGroup(item.updatedAt)}</p>}<div className="research-history-row"><button className="research-history-item" title={item.title} disabled={chatBusy||!!busy} aria-current={chatId===item.id?"true":undefined} onClick={()=>selectHistoryChat(item)}>{item.title}</button><button className="research-history-archive" type="button" title="归档" disabled={chatBusy||!!busy} aria-label={`归档${item.title}`} onClick={()=>void changeChatHistory(item,"archive")}><Icon name="archive"/></button></div></div>)}</div>:<p className="research-empty-note">还没有对话。</p>)}
        {historySection==="archived"&&(archivedChats.length?<div className="research-history-list">{archivedChats.map(item=><div className="research-history-row research-history-archived-row" key={item.id}><span className="research-history-archived-title" title={item.title}>{item.title}</span><div className="research-history-archived-actions"><button disabled={chatBusy||!!busy} onClick={()=>void changeChatHistory(item,"restore")}>恢复</button><button disabled={chatBusy||!!busy} onClick={()=>setDeleteId(item.id)}>删除</button></div>{deleteId===item.id&&<div className="history-confirm" role="alert"><p>永久删除这条归档对话？</p><div className="button-row"><button disabled={!!busy} onClick={()=>void changeChatHistory(item,"delete")}>确认删除</button><button onClick={()=>setDeleteId("")}>取消</button></div></div>}</div>)}</div>:<p className="research-empty-note">还没有归档对话。</p>)}
        {historySection==="reports"&&(history.length?<div className="research-history-list">{history.map(item=><div className="research-history-row" key={item.report_id}><button className="research-history-item" title={`${item.job_context?.company||"公司未知"} · ${item.job_context?.title||"公司研究"}`} disabled={!!busy||chatBusy} aria-current={report?.report_id===item.report_id&&showingReport?"true":undefined} onClick={()=>selectHistoryReport(item)}>{item.job_id?`${item.job_context?.company||"公司未知"} · ${item.job_context?.title||"岗位未知"}`:`${item.job_context?.company||"公司未知"} · 公司研究`}</button><button className="research-history-remove" disabled={!!busy||chatBusy} onClick={()=>setHideId(item.report_id)}>移除</button>{hideId===item.report_id&&<div className="history-confirm" role="alert"><p>从列表移除这份报告？本机证据快照保留。</p><div className="button-row"><button disabled={!!busy} onClick={()=>void hideReport(item)}>确认移除</button><button onClick={()=>setHideId("")}>取消</button></div></div>}</div>)}</div>:<p className="research-empty-note">这里还没有报告。</p>)}
      </div>
      {historySection==="chats"&&<div className="research-history-links"><button type="button" onClick={()=>setHistorySection("archived")}>归档<span>{archivedChats.length}</span></button><button type="button" onClick={()=>setHistorySection("reports")}>报告<span>{history.length}</span></button></div>}
    </aside>,sidebarTarget)}
    {message&&<p className="research-inline-status" role="status">{message}</p>}
    <form className="research-composer" aria-label="求职助手输入框" onSubmit={event=>{event.preventDefault();submitInput();}}>
      <textarea ref={inputRef} rows={1} aria-label="向求职助手提问" value={question} maxLength={12000} disabled={!!busy||chatBusy} onChange={event=>{setQuestion(event.target.value);setCandidate(undefined);setMessage("");}} onKeyDown={event=>{if(event.key==="Enter"&&!event.shiftKey&&!event.nativeEvent.isComposing){event.preventDefault();submitInput();}}} placeholder={job?"继续聊这个岗位、公司或求职准备":"问求职助手，也可以粘贴 JD 或岗位链接"}/>
      {candidate&&<div className="research-candidate"><strong>{candidate.company} · {candidate.title}</strong><span title={candidate.description}>{candidate.description?candidate.description.slice(0,120):"岗位原文不完整"}</span><button type="button" disabled={!!busy} onClick={()=>void confirmCandidate()}>确认岗位</button></div>}
      <div className="research-composer-actions"><select aria-label="当前使用模型" value={modelId||""} onChange={event=>{const value=event.target.value;setModelId(value||null);if(value)setCurrentModel(workspaceId,value);}}><option value="">选择模型</option>{connections.filter(item=>item.status==="verified").map(item=><option key={item.connection_id} value={item.connection_id}>{item.provider} · {item.model_id}</option>)}</select><div className="button-row">{chatBusy&&<button type="button" onClick={()=>void cancelChat()}>停止</button>}<button type="submit" className="primary-button" disabled={!!busy||chatBusy||!!candidate}>{busy==="link"?"读取中…":chatBusy?"处理中…":"发送 ↑"}</button></div></div>
    </form>
    {centeredEmpty&&<div className="research-examples" aria-label="示例问题">{["帮我分析一份 JD","如何准备技术面试？","调研一家目标公司"].map(example=><button key={example} type="button" onClick={()=>{setQuestion(example);inputRef.current?.focus();}}>{example}</button>)}</div>}
  </div>;
}
