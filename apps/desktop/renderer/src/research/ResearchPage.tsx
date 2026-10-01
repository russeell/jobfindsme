import {ResumeProposal} from "./ResumeProposal";
import {attachmentLimits,type ChatAttachment} from "../../../shared/chat-attachments";
import {assistantSkills,assistantSkill,skillDraft,isAssistantSkillId,type AssistantSkillId} from "../../../shared/assistant-skills";
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
import {acceptsResearchDelta,branchChat,beginChat,retryChatAttachments,failChat,finishChat,finishJobSearchChat,fromStoredResearchChat,researchChatsForRecovery,pendingResearchChats,stageResearchChat,acknowledgeResearchChat,removeResearchChatRecovery,mergeResearchChats,loadResearchChats,migrateResearchChats,reportIdsByTurn,saveResearchChats,saveResearchChatWithRetry,stopChat,toStoredResearchChat,type ActiveResearchRequest,type SavedResearchChat} from "../../../shared/research-chat-history";

type Job=SearchResultItem["job"];
type Props={selectedSources:string[];onReports(value:ResearchReport[]):void;onBusyChange(value:boolean):void;active:boolean;archiveVisible:boolean;newChatNonce:number;onOpenChat():void;data?:BootstrapData;target?:Job;onSearchJobs(query:string):void;onError(message?:string):void};

export function ResearchPage({selectedSources,active,archiveVisible,newChatNonce,onOpenChat,data,target,onSearchJobs,onError,onReports,onBusyChange}:Props){
  const workspaceId=data?.workspaces[0]?.workspace_id;
  const [job,setJob]=useState<Job|undefined>(target);
  const [report,setReport]=useState<ResearchReport>();
  const [reports,setReports]=useState<ResearchReport[]>([]);
  const [mode,setMode]=useState<"start"|"report">("start");
  const [archivedChats,setArchivedChats]=useState<SavedResearchChat[]>([]);
  const [deleteId,setDeleteId]=useState("");
  const [historyMenu,setHistoryMenu]=useState<"sort"|null>(null);
  const [historySort,setHistorySort]=useState<"recent"|"oldest"|"title">(()=>{const saved=localStorage.getItem("jobfindsme:chat-sort");return saved==="oldest"||saved==="title"?saved:"recent";});
  const [historySearchOpen,setHistorySearchOpen]=useState(false);
  const [historyQuery,setHistoryQuery]=useState("");
  useEffect(()=>{
    if(!historyMenu&&!historySearchOpen)return;
    const dismiss=(event:PointerEvent)=>{
      if(event.target instanceof Element&&event.target.closest(".research-history-menu, .research-history-toolbar, .research-history-search"))return;
      setHistoryMenu(null);setHistorySearchOpen(false);
    };
    const escape=(event:KeyboardEvent)=>{if(event.key==="Escape"){setHistoryMenu(null);setHistorySearchOpen(false);}};
    document.addEventListener("pointerdown",dismiss);
    document.addEventListener("keydown",escape);
    return()=>{document.removeEventListener("pointerdown",dismiss);document.removeEventListener("keydown",escape);};
  },[historyMenu,historySearchOpen]);
  useEffect(()=>{localStorage.setItem("jobfindsme:chat-sort",historySort);},[historySort]);
  const [candidate,setCandidate]=useState<Awaited<ReturnType<NonNullable<typeof window.jobfindsme>["resolveResearchLink"]>>>();
  const [topbarTarget,setTopbarTarget]=useState<HTMLElement|null>(null);
  const [sidebarTarget,setSidebarTarget]=useState<HTMLElement|null>(null);
  const [archiveTarget,setArchiveTarget]=useState<HTMLElement|null>(null);
  const [contextCompany,setContextCompany]=useState("");
  const [contextTitle,setContextTitle]=useState("");
  const [question,setQuestion]=useState("");
  const [connections,setConnections]=useState<ModelConnection[]>([]);
  const [modelId,setModelId]=useState<string|null>(null);
  const [chats,setChats]=useState<SavedResearchChat[]>([]);
  const [loadedWorkspace,setLoadedWorkspace]=useState<string|null>(null);
  const [chatId,setChatIdState]=useState<string|null>(null);
  const chatIdRef=useRef<string|null>(null);
  function setChatId(id:string|null){chatIdRef.current=id;setChatIdState(id);}
  const [skillId,setSkillId]=useState<AssistantSkillId>();
  const [addMenu,setAddMenu]=useState(false);
  const [attachments,setAttachments]=useState<ChatAttachment[]>([]);
  const [attachmentBusy,setAttachmentBusy]=useState(false);
  function chooseSkill(id:AssistantSkillId|undefined){setSkillId(id);setAddMenu(false);setQuestion(skillDraft(id,question,target&&job?.job_id===target.job_id?job:undefined));inputRef.current?.focus();}
  async function pickAttachments(kind:"files"|"folder"|"mixed"){
    if(attachmentBusy||chatBusy)return;const selectionSequence=sequence.current;setAddMenu(false);setMessage("");setAttachmentBusy(true);
    try{const selected=await window.jobfindsme!.pickChatAttachments(kind);if(selectionSequence!==sequence.current)return;setAttachments(current=>{const combined=[...current];let total=combined.reduce((sum,item)=>sum+item.text.length,0),imageChars=combined.reduce((sum,item)=>sum+(item.image?.data.length||0),0);for(const item of selected.attachments){if(combined.length>=attachmentLimits.files||total+item.text.length>attachmentLimits.totalChars||imageChars+(item.image?.data.length||0)>8_000_000){setMessage("已达到附件数量或文本限制，部分新文件未添加。请移除一些附件后再添加。");break;}combined.push(item);total+=item.text.length;imageChars+=item.image?.data.length||0;}return combined;});if(selected.warnings.length)setMessage(selected.warnings.join("；"));}
    catch(error){setMessage(userError(error).message);}finally{setAttachmentBusy(false);}
  }
  type RunningChat=ActiveResearchRequest&{text:string;contentStatus?:"direct"|"checked";process:string};
  const requestsRef=useRef(new Map<string,RunningChat>());
  const [,refreshRequests]=useState(0);
  const activeRun=chatId?requestsRef.current.get(chatId):undefined;
  const chatBusy=!!activeRun,streaming=activeRun?.text||"",liveProcess=activeRun?.process||"";
  const runningCount=requestsRef.current.size;
  const [focusedCitation,setFocusedCitation]=useState<{turn:number;number:number}|null>(null);
  const [copiedMessage,setCopiedMessage]=useState<string|null>(null);
  const [branchSelection,setBranchSelection]=useState<{chatId:string;turnIndex:number}|null>(null);
  const branchDialog=useRef<HTMLDialogElement>(null);
  const branchTrigger=useRef<HTMLElement|null>(null);
  useEffect(()=>{
    if(!branchSelection)return;
    const dialog=branchDialog.current;if(!dialog)return;
    dialog.showModal();dialog.querySelector<HTMLButtonElement>(".research-branch-option")?.focus();
    return()=>{dialog.close();if(branchTrigger.current?.isConnected)branchTrigger.current.focus();};
  },[branchSelection]);
  useEffect(()=>setBranchSelection(null),[workspaceId,chatId,active]);
  const draftsRef=useRef(new Map<string,{text:string;attachments:ChatAttachment[];skillId?:AssistantSkillId}>());
  function rememberDraft(){if(chatIdRef.current&&!requestsRef.current.has(chatIdRef.current))draftsRef.current.set(chatIdRef.current,{text:question,attachments,skillId});}
  const workspaceRef=useRef(workspaceId);
  workspaceRef.current=workspaceId;
  const inputRef=useRef<HTMLTextAreaElement>(null);
  const scrollRef=useRef<HTMLDivElement>(null);
  const saveQueue=useRef<Promise<unknown>>(Promise.resolve());
  const saveRevision=useRef(0);
  const [savePending,setSavePending]=useState(false);
  const savedChats=useRef(new Map<string,string>());
  const [busy,setBusy]=useState<"link"|"prepare"|"history"|null>(null);
  useEffect(()=>onBusyChange(runningCount>0||!!busy||savePending||attachmentBusy),[runningCount,busy,savePending,attachmentBusy,onBusyChange]);
  const [message,setMessage]=useState("");
  const sequence=useRef(0);
  const lastOpened=useRef<string|undefined>(undefined);
  const openBrowser=useOriginalBrowser();
  function keepReports(values:ResearchReport[]){setReports(values);onReports(values);}
  function openSaved(value:ResearchReport){sequence.current++;lastOpened.current=value.report_id;scrollRef.current?.scrollTo({top:0});setChatId(null);setSkillId(undefined);setAttachments([]);setAddMenu(false);setJob(value.job_id?reportJob(value):undefined);setReport(value);setMode("report");setCandidate(undefined);setContextCompany(value.job_id?"":value.job_context?.company||"");setContextTitle(value.job_id?"":value.job_context?.title||"");setQuestion("");setMessage("");setBusy(null);}
  useEffect(()=>{setTopbarTarget(document.getElementById("research-topbar-actions"));setSidebarTarget(document.getElementById("research-sidebar-history"));},[]);
  useEffect(()=>{setArchiveTarget(archiveVisible?document.getElementById("research-archive-settings"):null);},[archiveVisible]);
  useEffect(()=>{
    if(!workspaceId)return;
    let cancelled=false;
    const cached=loadResearchChats(workspaceId);
    const migrationKey=`jobfindsme:research-chat-migrated:${workspaceId}`;
    const alreadyMigrated=localStorage.getItem(migrationKey)==="1";
    savedChats.current.clear();setLoadedWorkspace(null);setChats(alreadyMigrated?[]:cached);setArchivedChats([]);setReports([]);setChatId(null);setSkillId(undefined);setAttachments([]);requestsRef.current.clear();draftsRef.current.clear();refreshRequests(value=>value+1);setModelId(getCurrentModel(workspaceId));
    void Promise.all([window.jobfindsme!.listResearchChats(workspaceId),window.jobfindsme!.listArchivedResearchChats(workspaceId)]).then(async([rows,archivedRows])=>{
      if(cancelled)return;
      const remote=rows.map(fromStoredResearchChat),archived=archivedRows.map(fromStoredResearchChat);
      const archivedIds=new Set(archived.map(item=>item.id));
      const legacy=researchChatsForRecovery(workspaceId,cached,remote,archivedIds,alreadyMigrated);
      try{
        const verified=await migrateResearchChats(workspaceId,legacy,remote,item=>window.jobfindsme!.saveResearchChat(item),()=>window.jobfindsme!.listResearchChats(workspaceId));
        if(cancelled)return;
        localStorage.setItem(migrationKey,"1");
        for(const chat of verified)acknowledgeResearchChat(workspaceId,chat);
        for(const chat of verified)savedChats.current.set(chat.id,JSON.stringify(toStoredResearchChat(workspaceId,chat)));
        setChats(verified);setArchivedChats(archived);setLoadedWorkspace(workspaceId);
      }catch(error){if(!cancelled){for(const chat of remote)savedChats.current.set(chat.id,JSON.stringify(toStoredResearchChat(workspaceId,chat)));setChats(mergeResearchChats(legacy,remote));setArchivedChats(archived);setLoadedWorkspace(workspaceId);setMessage(`历史恢复未完成，待保存版本仍保留：${userError(error).message}`);}}
    }).catch(error=>{if(!cancelled)setMessage(`对话记录暂未从本地服务加载：${userError(error).message}`);});
    return()=>{cancelled=true;for(const [id,running] of requestsRef.current){if(running.workspaceId!==workspaceId)continue;requestsRef.current.delete(id);void(running.kind==="model"?window.jobfindsme!.cancelResearchChat(running.id):window.jobfindsme!.cancelResearch());}};
  },[workspaceId]);
  useEffect(()=>{if(!workspaceId||loadedWorkspace!==workspaceId)return;if(!saveResearchChats(workspaceId,chats))setMessage("历史对话未能写入设备缓存，请检查可用空间。");for(const chat of chats){const stored=toStoredResearchChat(workspaceId,chat),serialized=JSON.stringify(stored);if(savedChats.current.get(chat.id)===serialized)continue;const recoveryStaged=stageResearchChat(workspaceId,chat);if(!recoveryStaged)setMessage("对话的待恢复版本未能写入设备缓存，请检查可用空间。");savedChats.current.set(chat.id,serialized);const revision=++saveRevision.current;setSavePending(true);saveQueue.current=saveQueue.current.catch(()=>undefined).then(async()=>{await saveResearchChatWithRetry(stored,item=>window.jobfindsme!.saveResearchChat(item));acknowledgeResearchChat(workspaceId,chat);}).catch(error=>{if(savedChats.current.get(chat.id)===serialized)savedChats.current.delete(chat.id);setMessage(`对话记录未能写入本地服务：${userError(error).message}。${recoveryStaged?"待恢复版本仍保留，请重试。":"设备缓存也未写入，请保留当前窗口中的内容。"}`);}).finally(()=>{if(saveRevision.current===revision)setSavePending(false);});}},[workspaceId,loadedWorkspace,chats]);
  useEffect(()=>{if(!active)return;void window.jobfindsme!.listModelConnections().then(values=>{setConnections(values);const saved=getCurrentModel(workspaceId);setModelId(saved&&values.some(value=>value.connection_id===saved&&value.status==="verified")?saved:null);}).catch(error=>onError(userError(error).message));},[active,workspaceId]);
  useEffect(()=>window.jobfindsme!.onResearchChatDelta(event=>{
    const running=requestsRef.current.get(event.session_id);
    if(!running||!acceptsResearchDelta(running,event,workspaceRef.current))return;
    if(event.progress){const label=({find_evidence:"核对已存材料",search_web:"搜索公开来源",read_page:"读取原页",read_browser_page:"浏览器读取原页",read_job:"读取岗位详情",search_jobs:"正在搜索岗位",browser_open:"阅读原文",browser_snapshot:"核对页面结构",browser_search:"正在搜索",browser_click:"阅读原文",browser_next:"读取下一页"} as Record<string,string>)[event.progress.tool]||"处理来源";running.process=event.progress.status==="started"?`${label}中…`:event.progress.status==="failed"?`${label}失败，正在整理已获取内容…`:`${label}结束，正在继续处理…`;}
    if(event.delta){running.contentStatus=event.content_status;running.text+=event.delta;}
    refreshRequests(value=>value+1);
  }),[]);
  useEffect(()=>{if(!target)return;rememberDraft();sequence.current++;lastOpened.current=undefined;setChatId(null);setSkillId(undefined);setAttachments([]);setAddMenu(false);setJob(target);setReport(undefined);setMode("start");setCandidate(undefined);setContextCompany("");setContextTitle("");setQuestion("");setMessage("");setBusy(null);},[target?.job_id]);
  const lastNewChatNonce=useRef(newChatNonce);
  useEffect(()=>{if(lastNewChatNonce.current===newChatNonce)return;lastNewChatNonce.current=newChatNonce;rememberDraft();scrollRef.current?.scrollTo({top:0});sequence.current++;lastOpened.current=undefined;setChatId(null);setSkillId(undefined);setAttachments([]);setAddMenu(false);setJob(undefined);setReport(undefined);setMode("start");setCandidate(undefined);setContextCompany("");setContextTitle("");setQuestion("");setMessage("");setBusy(null);requestAnimationFrame(()=>inputRef.current?.focus());},[newChatNonce]);
  useEffect(()=>{const input=inputRef.current;if(!input)return;input.style.height="auto";input.style.height=`${Math.min(input.scrollHeight,window.innerHeight<650?74:112)}px`;},[question,active]);
  useEffect(()=>{if(!workspaceId||(!active&&!archiveVisible))return;let cancelled=false;void window.jobfindsme!.listResearchReports(workspaceId).then(values=>{if(cancelled)return;keepReports(values);if(!active||chatIdRef.current)return;if(lastOpened.current){const previous=values.find(item=>item.report_id===lastOpened.current);if(previous)return;}if(target){const latest=values.filter(item=>reportMatchesJob(item,target)&&item.outcome!=="failed").sort((a,b)=>(b.version_number??1)-(a.version_number??1)||b.created_at.localeCompare(a.created_at))[0];if(latest)openSaved(latest);}}).catch(error=>onError(userError(error).message));return()=>{cancelled=true;};},[workspaceId,active,archiveVisible,target]);
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
    started.chat.turns=started.chat.turns.map((turn,index)=>index===started.chat.turns.length-1?{...turn,skillId,attachments:attachments.length?attachments:undefined}:turn);
    if((skillId||decision.kind!=="job_search")&&!modelId){setMessage("请先在模型设置中选择一个已测试模型。提问已保留。");return;}
    setChatId(id);
    if(!modelId&&!skillId&&!attachments.length&&decision.kind==="job_search"){
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
    const requestId=crypto.randomUUID();
    const running:RunningChat={id:requestId,workspaceId,sessionId:id,kind:"model",text:"",process:""};
    requestsRef.current.set(id,running);draftsRef.current.delete(id);refreshRequests(value=>value+1);
    const companyHint=decision.kind==="research"?decision.company:decision.kind==="clarify"&&"company" in decision.pending?decision.pending.company:currentCompany;
    const startedChat={...started.chat,subjectCompany:companyHint||current?.subjectCompany,subjectTitle:decision.kind==="research"?decision.title:current?.subjectTitle,jobId:activeJobId,researchMode:skillId?skillId==="deep-research":decision.kind!=="chat"};
    setChats(items=>[startedChat,...items.filter(item=>item.id!==id)]);
    setQuestion("");setMessage("");
    try{
      const result=await window.jobfindsme!.runResearchChat({source_ids:selectedSources,interview_state:current?.turns.slice().reverse().find(turn=>turn.interviewState)?.interviewState,attachments,skill_id:skillId,request_id:requestId,session_id:id,workspace_id:workspaceId,connection_id:selected.connection_id,question:!skillId&&decision.kind==="research"?decision.question:value,research:skillId?skillId==="deep-research":decision.kind==="research",job_id:activeJobId,company:companyHint,title:decision.kind==="research"?decision.title:undefined,history:modelHistoryWithinBudget(started.history)});
      if(requestsRef.current.get(id)?.id!==requestId||workspaceRef.current!==workspaceId)return;
      setChats(items=>items.map(item=>{if(item.id!==id)return item;const finished=finishChat(item,result.text,result.report?.report_id,new Date().toISOString(),{jobs:result.jobs,resumeProposalId:result.resumeProposalId,interviewState:result.interviewState,evidence:result.evidence,process:result.process});return {...finished,subjectCompany:result.company||finished.subjectCompany,researchMode:!!result.researched||finished.researchMode,pendingResearch:!skillId&&decision.kind==="clarify"&&!result.researched?decision.pending:undefined};}));
      if(result.report){const values=await window.jobfindsme!.listResearchReports(workspaceId);if(requestsRef.current.get(id)?.id===requestId&&workspaceRef.current===workspaceId){keepReports(values);if(chatIdRef.current===id){lastOpened.current=result.report.report_id;setReport(result.report);}}}
      if(chatIdRef.current===id)setAttachments([]);
    }catch(error){if(requestsRef.current.get(id)?.id===requestId&&workspaceRef.current===workspaceId){setChats(items=>items.map(item=>item.id===id?failChat(item,userError(error).message,new Date().toISOString()):item));if(chatIdRef.current===id){setQuestion(value);setMessage(`本次对话未完成：${userError(error).message}。提问已保留，可直接重试。`);}try{keepReports(await window.jobfindsme!.listResearchReports(workspaceId));}catch{}}}
    finally{if(requestsRef.current.get(id)?.id===requestId){requestsRef.current.delete(id);refreshRequests(value=>value+1);}}
  }
  async function cancelChat(){const running=chatId?requestsRef.current.get(chatId):undefined;if(!running)return;
    const current=chats.find(item=>item.id===running.sessionId),stopped=current?stopChat(current,running.text,running.contentStatus,new Date().toISOString()):undefined;
    const retained=!!stopped&&stopped!==current;requestsRef.current.delete(running.sessionId);refreshRequests(value=>value+1);
    if(stopped)setChats(items=>items.map(item=>item.id===stopped.id?stopped:item));setQuestion(retained?"":stopped?.draft||"");
    try{if(running.kind==="model")await window.jobfindsme!.cancelResearchChat(running.id);else await window.jobfindsme!.cancelResearch();if(chatIdRef.current===running.sessionId)setMessage(retained?"已停止；已生成的回复已保留，内容未完成。":"已停止；当前提问会保留。");}catch(error){if(chatIdRef.current===running.sessionId)setMessage(userError(error).message);}
  }
  async function refreshChatHistory(id:string){
    const [activeRows,archivedRows]=await Promise.all([window.jobfindsme!.listResearchChats(id),window.jobfindsme!.listArchivedResearchChats(id)]);
    if(workspaceRef.current!==id)return;
    const remote=activeRows.map(fromStoredResearchChat);
    const activeChats=mergeResearchChats(researchChatsForRecovery(id,[],remote,new Set(archivedRows.map(item=>String(item.id))),true),remote);
    const archived=archivedRows.map(fromStoredResearchChat);
    savedChats.current=new Map(remote.map(item=>[item.id,JSON.stringify(toStoredResearchChat(id,item))]));
    setChats(current=>mergeResearchChats(current.filter(chat=>requestsRef.current.has(chat.id)),activeChats));setArchivedChats(archived);
  }
  async function changeChatHistory(item:SavedResearchChat,action:"archive"|"restore"|"delete"){
    if(!workspaceId||loadedWorkspace!==workspaceId||requestsRef.current.has(item.id)||busy||savePending)return;
    setBusy("history");setMessage("");
    try{
      await saveQueue.current;
      if(action!=="restore"){
        if(pendingResearchChats(workspaceId).some(chat=>chat.id===item.id))throw Error("该对话仍有未保存更新，请先保存成功后再归档或删除。");
        removeResearchChatRecovery(workspaceId,item.id);
      }
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
  const historyBusy=!!busy||savePending;
  const visibleChats=chats.filter(item=>item.title.toLocaleLowerCase().includes(historyQuery.trim().toLocaleLowerCase())).sort((a,b)=>historySort==="title"?a.title.localeCompare(b.title,"zh-CN"):historySort==="oldest"?a.updatedAt.localeCompare(b.updatedAt):b.updatedAt.localeCompare(a.updatedAt));
  const showingReport=mode==="report"&&!!report;
  function submitInput(){
    if(busy||chatBusy||attachmentBusy)return;
    const parsed=splitResearchInput(question);
    if(parsed.error){setCandidate(undefined);setMessage(parsed.error);return;}
    if(parsed.url){if(Object.keys(sourceBrowserSpecs).some(key=>isSourceBrowserId(key)&&isAllowedSourceUrl(key,parsed.url!)))void readLink(parsed.url);else void sendChat(question.trim());return;}
    if(candidate){setMessage("请先确认读取到的岗位，再开始研究。");return;}
    if(!parsed.question&&!attachments.length){setMessage("请输入消息，或粘贴岗位链接。");return;}
    void sendChat(parsed.question||"请阅读我附上的材料。");
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
    if(busy)return;rememberDraft();setCopiedMessage(null);setFocusedCitation(null);
    onOpenChat();const draft=draftsRef.current.get(item.id);setAttachments(draft?.attachments||retryChatAttachments(item));setAddMenu(false);
    scrollRef.current?.scrollTo({top:0});setChatId(item.id);
    const lastUser=[...item.turns].reverse().find(turn=>turn.role==="user");setSkillId(draft?draft.skillId:(isAssistantSkillId(lastUser?.skillId)?lastUser.skillId:undefined));
    const latest=[...item.reportIds].reverse().map(id=>reportsById.get(id)).find(Boolean);
    setReport(latest);setMode(latest?"report":"start");setJob(latest?.job_id?reportJob(latest):undefined);
    setContextCompany(item.subjectCompany||"");setContextTitle(item.subjectTitle||"");setQuestion(requestsRef.current.has(item.id)?"":draft?.text??item.draft??"");
    setMessage(item.failure||"");requestAnimationFrame(()=>scrollRef.current?.focus());
  }
  async function copyMessage(chat:SavedResearchChat,index:number){
    try{await window.jobfindsme!.copyChatText(chat.turns[index].text);if(chatIdRef.current===chat.id)setCopiedMessage(`${chat.id}-${index}`);}catch(error){setMessage(userError(error).message);}
  }
  function forkMessage(chat:SavedResearchChat,index:number){
    if(busy)return;
    const fork=branchChat(chat,index,crypto.randomUUID(),new Date().toISOString(),reports);
    setBranchSelection(null);setChats(items=>[fork,...items]);selectHistoryChat(fork);setMessage("");
    requestAnimationFrame(()=>inputRef.current?.focus());
  }
  return <div className="research-page research-workbench">
    {branchSelection&&createPortal(<dialog ref={branchDialog} className="research-branch-dialog" aria-labelledby="research-branch-title" aria-describedby="research-branch-description" onCancel={event=>{event.preventDefault();setBranchSelection(null);}} onClick={event=>{if(event.target!==event.currentTarget)return;const bounds=event.currentTarget.getBoundingClientRect();if(event.clientX<bounds.left||event.clientX>bounds.right||event.clientY<bounds.top||event.clientY>bounds.bottom)setBranchSelection(null);}}>
      <header><h2 id="research-branch-title">从这里创建聊天分支</h2><button type="button" aria-label="关闭分支选择" onClick={()=>setBranchSelection(null)}>×</button></header>
      <p id="research-branch-description">保留截至这条回复的消息，原聊天不变。</p>
      <button type="button" className="research-branch-option" onClick={()=>{const parent=chats.find(chat=>chat.id===branchSelection.chatId);if(parent)forkMessage(parent,branchSelection.turnIndex);else setBranchSelection(null);}}><Icon name="chatBranch"/><span><strong>在此工作区中创建分支</strong><small>从这条消息继续，在新聊天中探索</small></span></button>
    </dialog>,document.body)}
    {active&&topbarTarget&&job&&createPortal(<div className="button-row" aria-label="岗位操作"><button onClick={()=>openOriginal(job.apply_url)}>岗位原页 ↗</button></div>,topbarTarget)}
    <div ref={scrollRef} className={`research-scroll-region${centeredEmpty?" research-empty-state":""}${activeChat&&!showingReport?" research-conversation":""}`} role="region" aria-label="求职助手对话" tabIndex={0}><div className="research-reading-column">
      {(!activeChat||showingReport)&&<header className={job&&!showingReport?"research-header research-header-job":"research-header"}><div>{job&&!showingReport?<><strong>{job.title}</strong><p>{job.company} · 围绕这个岗位继续聊</p></>:<><h1>{showingReport?(job?.title||report?.job_context?.company||"公司研究"):"有什么求职问题？"}</h1><p>{showingReport?`${job?job.company+" · ":"公司研究 · "}${report&&new Date(report.created_at).toLocaleString()} · ${report&&reportStatus(report)}`:"可以聊岗位、简历、面试，也可以了解公司。"}</p></>}</div></header>}
      {activeChat&&<section className="research-chat-messages" aria-label="对话内容">
        {activeChat.branchOf&&<div className="research-branch-origin"><Icon name="branch"/><span>聊天分支</span>{chats.find(chat=>chat.id===activeChat.branchOf?.chatId)&&<button type="button" onClick={()=>selectHistoryChat(chats.find(chat=>chat.id===activeChat.branchOf!.chatId)!)}>返回原聊天</button>}</div>}
        {activeChat.researchMode&&activeChat.subjectCompany&&<p className="research-subject-caption">{activeChat.subjectCompany}{activeChat.subjectTitle?` · ${activeChat.subjectTitle}`:""}</p>}
        {activeChat.turns.map((item,index)=>{
          const attached=chatReportIds.get(index);
          const attachedReport=attached?reportsById.get(attached):undefined;
          return <article className={`research-chat-turn ${item.role}`} aria-label={item.role==="user"?"你":"求职助手"} key={`${activeChat.id}-${index}`}>
            {item.role==="assistant"&&!!item.jobs?.length&&<div className="agent-job-results" aria-label="实时岗位结果">{item.jobs.map(candidate=><div key={candidate.job_id} className="agent-job-card"><strong>{candidate.title}</strong><p>{candidate.company} · {candidate.locations.join(" / ")||"地点未知"} · {candidate.source.source_name}</p><div className="button-row"><button onClick={()=>openOriginal(candidate.apply_url)}>查看原页 ↗</button><button onClick={()=>{if(workspaceId)void window.jobfindsme!.setJobTracking({workspace_id:workspaceId,job_id:candidate.job_id,event_type:"saved",enabled:true}).then(()=>setMessage("已收藏岗位")).catch(error=>setMessage(userError(error).message));}}>收藏</button><button onClick={()=>{setJob(candidate);setContextCompany(candidate.company);setContextTitle(candidate.title);setChats(items=>items.map(chat=>chat.id===chatId?{...chat,jobId:candidate.job_id,subjectCompany:candidate.company,subjectTitle:candidate.title}:chat));inputRef.current?.focus();}}>继续分析</button></div></div>)}</div>}
            {item.role==="user"&&!!item.attachments?.length&&<div className="research-attachment-list">{item.attachments.map(file=><span key={file.id}>{file.image?<img src={`data:${file.image.mimeType};base64,${file.image.data}`} alt="图片附件"/>:<Icon name="attachment"/>}<span>{file.name}</span>{file.truncated?" · 部分文本":""}</span>)}</div>}
            {item.role==="user"&&assistantSkill(item.skillId)&&<small className="research-skill-badge">{assistantSkill(item.skillId)!.title}</small>}
            {item.resumeProposalId&&workspaceId&&<ResumeProposal workspaceId={workspaceId} sessionId={item.resumeProposalId}/>}
            {item.role==="assistant"?<MessageContent text={item.text} sources={attachedReport?.evidence||item.evidence} onCitation={number=>showCitation(index,number)}/>:<p>{item.text}</p>}
            {item.interrupted&&<small className="note" role="status">已停止 · 内容未完成</small>}
            {attachedReport?<details id={`research-sources-${index}`}><summary>来源与核验详情（{attachedReport.evidence.length}）</summary><ReputationEvidence report={attachedReport} workspaceId={workspaceId!} onReport={updateShownReport} onSource={value=>openBrowser({sourceId:"web",url:value,title:"研究来源"})} focusedEvidenceId={focusedCitation?.turn===index?attachedReport.evidence[focusedCitation.number-1]?.evidence_id:undefined}/></details>:item.evidence?.length?<details id={`research-sources-${index}`}><summary>来源片段（{item.evidence.length}）</summary>{item.evidence.map((source,sourceIndex)=><article id={`research-source-${index}-${sourceIndex+1}`} tabIndex={-1} className={`evidence-card${focusedCitation?.turn===index&&focusedCitation.number===sourceIndex+1?" research-source-focused":""}`} key={source.evidence_id}><strong>原文片段 [{sourceIndex+1}] · {source.platform}</strong><small>{source.context?.page?`第 ${source.context.page} 页 · `:""}{source.published_at||"发布时间未知"}</small><blockquote>{source.excerpt}</blockquote><p className="note">{source.limitations} · 读取于 {source.retrieved_at}</p>{source.url&&<button type="button" onClick={()=>openBrowser({sourceId:"web",url:source.url!,title:"研究来源"})}>查看原页 ↗</button>}</article>)}</details>:null}
            {!!item.process?.length&&<details className="research-diagnostics"><summary>检索与阅读过程（{item.process.length}）</summary><ol>{item.process.map((step,stepIndex)=><li key={stepIndex}>{({find_evidence:"核对已存材料",search_web:"发现网页",read_page:"读取原页",read_browser_page:"浏览器读取原页",answer_check:"核对陈述",completion_check:"补查缺口"} as Record<string,string>)[step.tool]||step.tool}{step.site?` · ${step.site}`:""} · {step.status}{typeof step.count==="number"?` · ${step.count} 条`:""}</li>)}</ol></details>}
            <div className="research-message-actions" aria-label="消息操作"><button type="button" aria-label={copiedMessage===`${activeChat.id}-${index}`?"已复制消息":"复制消息"} data-tooltip={copiedMessage===`${activeChat.id}-${index}`?"已复制":"复制"} onClick={()=>void copyMessage(activeChat,index)}><Icon name={copiedMessage===`${activeChat.id}-${index}`?"check":"copy"}/></button>{item.role==="assistant"&&<button type="button" data-tooltip="分支到新聊天" aria-label="分支到新聊天" aria-haspopup="dialog" onClick={event=>{branchTrigger.current=event.currentTarget;setBranchSelection({chatId:activeChat.id,turnIndex:index});}}><Icon name="chatBranch"/></button>}</div>
            {item.searchQuery&&<button type="button" className="research-search-action" onClick={()=>onSearchJobs(item.searchQuery!)}>去找工作 · {item.searchQuery}</button>}
          </article>;
        })}
        {chatBusy&&<article className="research-chat-turn assistant" aria-label="求职助手" aria-live="polite"><MessageContent text={streaming||liveProcess||"正在处理…"}/>{streaming&&liveProcess&&<small className="note">{liveProcess}</small>}</article>}
        {activeChat.failure&&!chatBusy&&<p className="research-chat-failure" role="status">{activeChat.failure} · 输入框已保留提问，可重试。</p>}
      </section>}
      {!activeChat&&showingReport&&report&&<ReputationEvidence report={report} workspaceId={workspaceId!} onReport={updateShownReport} onSource={value=>openBrowser({sourceId:"web",url:value,title:"研究来源"})}/>}
    </div></div>
    {sidebarTarget&&createPortal(<aside id="research-history-panel" className="research-history-sidebar" aria-label="最近对话">
      <div className="research-history-toolbar"><button className="research-history-sort-trigger" type="button" aria-label="聊天排序方式" aria-expanded={historyMenu==="sort"} onClick={()=>{setHistoryMenu(value=>value==="sort"?null:"sort");setHistorySearchOpen(false);}}>{historySort==="recent"?"最近":historySort==="oldest"?"最早":"名称"}<span aria-hidden="true">⌄</span></button><div><button type="button" aria-label="搜索聊天" title="搜索聊天" aria-expanded={historySearchOpen} onClick={()=>{setHistorySearchOpen(value=>!value);setHistoryQuery("");setHistoryMenu(null);}}><Icon name="discover"/></button></div></div>
      {historySearchOpen&&<input className="research-history-search" type="search" aria-label="搜索聊天名称" value={historyQuery} onChange={event=>setHistoryQuery(event.target.value)} placeholder="搜索聊天"/>}
      {historyMenu&&<div className="research-history-menu research-history-menu-sort" role="group" aria-label="聊天排序方式">{([ ["recent","最近更新"],["oldest","最早更新"],["title","名称"] ] as const).map(([value,label])=><button key={value} type="button" aria-pressed={historySort===value} onClick={()=>{setHistorySort(value);setHistoryMenu(null);}}>{label}{historySort===value&&" ✓"}</button>)}</div>}
      <div className="research-history-body">
        {visibleChats.length?<div className="research-history-list">{visibleChats.map((item,index)=><div key={item.id}>{historySort!=="title"&&(index===0||historyGroup(visibleChats[index-1].updatedAt)!==historyGroup(item.updatedAt))&&<p className="history-day">{historyGroup(item.updatedAt)}</p>}<div className="research-history-row"><button className="research-history-item" title={item.title} aria-current={active&&chatId===item.id?"true":undefined} onClick={()=>selectHistoryChat(item)}>{item.branchOf&&<span className="research-history-branch-icon"><Icon name="branch"/></span>}{item.title}{requestsRef.current.has(item.id)&&<span className="research-history-running" aria-label="正在运行"> ···</span>}</button><button className="research-history-archive" type="button" title="归档聊天" disabled={historyBusy||requestsRef.current.has(item.id)} aria-label={`归档聊天：${item.title}`} onClick={()=>void changeChatHistory(item,"archive")}><Icon name="archive"/></button></div></div>)}</div>:<p className="research-empty-note">{historyQuery?"没有匹配的聊天。":"还没有对话。"}</p>}
      </div>
    </aside>,sidebarTarget)}
    {archiveVisible&&archiveTarget&&createPortal(<div className="research-archive-settings"><div className="heading-row settings-heading"><div><h1>对话归档</h1><p>在这里恢复或删除已归档的对话。</p></div><span className="settings-count">{archivedChats.length} 条对话</span></div>{archivedChats.length?<div className="research-archive-list">{archivedChats.map(item=><div className="research-archive-item" key={item.id}><div className="research-archive-info"><strong title={item.title}>{item.title}</strong><time dateTime={item.updatedAt}>{Number.isFinite(Date.parse(item.updatedAt))?new Date(item.updatedAt).toLocaleString("zh-CN",{year:"numeric",month:"long",day:"numeric",hour:"2-digit",minute:"2-digit"}):"时间未知"}</time></div><div className="button-row research-archive-actions"><button disabled={!!busy} onClick={()=>void changeChatHistory(item,"restore")}>恢复对话</button><button className="archive-delete" title="删除归档对话" aria-label={`删除归档对话：${item.title}`} disabled={!!busy} onClick={()=>setDeleteId(item.id)}><Icon name="trash"/></button></div>{deleteId===item.id&&<div className="history-confirm" role="alert"><p>永久删除这条归档对话？</p><div className="button-row"><button disabled={!!busy} onClick={()=>void changeChatHistory(item,"delete")}>确认删除</button><button onClick={()=>setDeleteId("")}>取消</button></div></div>}</div>)}</div>:<p className="research-empty-note">还没有归档对话。</p>}</div>,archiveTarget)}
    {message&&<p className="research-inline-status" role="status">{message}</p>}
    <form className="research-composer" aria-label="求职助手输入框" onSubmit={event=>{event.preventDefault();submitInput();}}>
      {!!attachments.length&&<div className="research-attachment-list" aria-label="待发送附件">{attachments.map(file=><span key={file.id} title={file.name}>{file.image?<img src={`data:${file.image.mimeType};base64,${file.image.data}`} alt="图片附件"/>:<Icon name="attachment"/>}<span>{file.name}</span>{file.truncated?" · 部分文本":""}<button type="button" aria-label={`移除附件：${file.name}`} disabled={chatBusy} onClick={()=>setAttachments(items=>items.filter(item=>item.id!==file.id))}>×</button></span>)}</div>}
      <textarea ref={inputRef} rows={1} aria-label="向求职助手提问" value={question} maxLength={12000} disabled={!!busy||chatBusy} onChange={event=>{setQuestion(event.target.value);setCandidate(undefined);setMessage("");}} onKeyDown={event=>{if(event.key==="Enter"&&!event.shiftKey&&!event.nativeEvent.isComposing){event.preventDefault();submitInput();}}} placeholder={job?"继续聊这个岗位、公司或求职准备":"输入问题，或粘贴岗位链接、JD…"}/>
      {candidate&&<div className="research-candidate"><strong>{candidate.company} · {candidate.title}</strong><span title={candidate.description}>{candidate.description?candidate.description.slice(0,120):"岗位原文不完整"}</span><button type="button" disabled={!!busy} onClick={()=>void confirmCandidate()}>确认岗位</button></div>}
      <div className="research-composer-actions"><div className="research-add-control">
        <button className="research-add-button" type="button" aria-label="添加文件和技能" title="添加文件和技能" aria-expanded={addMenu} disabled={!!busy||chatBusy||attachmentBusy} onClick={()=>setAddMenu(value=>!value)}>{attachmentBusy?"…":<Icon name="add"/>}</button>
        {addMenu&&<><button className="research-menu-dismiss" type="button" aria-label="关闭添加菜单" onClick={()=>setAddMenu(false)}/><div className="research-add-menu" role="group" aria-label="添加文件和技能" onKeyDown={event=>{if(event.key==="Escape"){setAddMenu(false);inputRef.current?.focus();}}}><small>添加资料</small><div className="research-file-actions"><button type="button" onClick={()=>void pickAttachments("mixed")}><Icon name="attachment"/><div>添加文件、文件夹或图片<span>PDF、Word、文本、JPG、PNG、WebP</span></div></button></div><small>求职技能</small>{assistantSkills.map(skill=><button key={skill.id} type="button" aria-pressed={skillId===skill.id} onClick={()=>chooseSkill(skill.id)}><Icon name={skill.id==="resume-tailor"?"resume":skill.id==="interview-prep"?"interview":"research"}/><div>{skill.title}<span>{skill.description}</span></div>{skillId===skill.id&&<span className="research-selected-check">✓</span>}</button>)}</div></>}
      </div>{skillId&&<div className="research-active-skill"><strong>{assistantSkill(skillId)!.title}</strong><button type="button" aria-label="取消技能，切回普通聊天" disabled={!!busy||chatBusy} onClick={()=>setSkillId(undefined)}>×</button></div>}<div className="button-row research-send-actions"><select aria-label="当前使用模型" disabled={chatBusy} value={modelId||""} onChange={event=>{const value=event.target.value;setModelId(value||null);if(value)setCurrentModel(workspaceId,value);}}><option value="">选择模型</option>{connections.filter(item=>item.status==="verified").map(item=><option key={item.connection_id} value={item.connection_id}>{item.provider} · {item.model_id}</option>)}</select>{chatBusy&&<button type="button" onClick={()=>void cancelChat()}>停止</button>}<button type="submit" className="primary-button" aria-label={chatBusy?"正在处理":busy==="link"?"正在读取":"发送消息"} disabled={!!busy||chatBusy||!!candidate||attachmentBusy}>{chatBusy||busy==="link"?"…":"↑"}</button></div></div>
      {!!attachments.length&&<small className="research-attachment-note">资料内容将在发送后交给所选模型，并保存在本机对话中。每个文件最多 5MB；图片需使用支持视觉的模型，附件不会自动覆盖简历。</small>}
    </form>

  </div>;
}
