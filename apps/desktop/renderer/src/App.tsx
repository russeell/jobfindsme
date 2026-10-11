import {ResumePage,type ResumeOpenRequest} from "./resume/ResumePage";
import {RecordsPage} from "./preparation/RecordsPage";
import {JobPreparation} from "./preparation/JobPreparation";
import type {AssistantSkillId} from "../../shared/assistant-skills";
import {readSelectedSources} from "../../shared/discovery-filters";
import type {ResearchReport} from "../../shared/contracts";
import {userError} from "../../shared/user-errors";
import { Icon } from "./shared/Icon";
import { ModelsPage } from "./settings/ModelsPage";
import { ResearchPage } from "./research/ResearchPage";
import { sourceBrowserSpecs, isAllowedSourceUrl, type SourceBrowserId } from "../../shared/source-browser-policy";
import { Discovery } from "./search/Discovery";
import { Workbench, useOriginalBrowser } from "./shared/Workbench";
import {sourceStatusRows,mergeSourceChecks,sourceCheckFailureOutcome} from "../../shared/source-presentation";
import { FormEvent, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import buildInfo from "../../build-info.json";

import type {
  BootstrapData, SourceCheckResult,
  ServiceStatus,
  SearchResultItem,
} from "../../shared/contracts";

type WorkPage = "discover" | "research" | "records" | "resume";
type Page = WorkPage | "settings";
type SettingsTab = "sources" | "models" | "about" | "archive";
const navItems: Array<[string, WorkPage]> = [["找工作", "discover"], ["岗位管理", "records"], ["我的简历", "resume"]];
const settingsItems: Array<[string, SettingsTab]> = [["岗位来源", "sources"], ["对话归档", "archive"], ["模型设置", "models"], ["版本更新", "about"]];
export function App() {
  const [chosenSources,setChosenSources] = useState<string[]>(()=>readSelectedSources(localStorage.getItem("jfm.sources.selected")));
  const hadSourcePreference=useRef(localStorage.getItem("jfm.sources.selected")!==null);
  useEffect(()=>localStorage.setItem("jfm.sources.selected",JSON.stringify(chosenSources)),[chosenSources]);
  const [reports,setReports]=useState<ResearchReport[]>([]);
  const [sourceChecks,setSourceChecks]=useState<SourceCheckResult[]>([]);
  function chooseSource(id:string, selected:boolean) {setChosenSources(current => {const previous=current;const next=selected ? [...new Set([...previous,id])] : previous.filter(s=>s!==id);localStorage.setItem("jfm.sources.selected",JSON.stringify(next));return next;});}
  function chooseAllSources(selected:boolean) {setChosenSources(selected?(data?.sources.map(source=>source.source_id)??[]):[]);}
  const [page, setPage] = useState<Page>("discover");
  const contentRef=useRef<HTMLDivElement>(null);
  const scrollPositions=useRef(new Map<string,number>());
  const [settingsTab,setSettingsTab]=useState<SettingsTab>("sources");
  const [data, setData] = useState<BootstrapData>();
  const routeKey=`${data?.workspaces[0]?.workspace_id ?? 'local'}:${page}:${page==='settings'?settingsTab:''}`;
  useLayoutEffect(()=>{const node=contentRef.current;if(node)node.scrollTop=scrollPositions.current.get(routeKey)??0;},[routeKey]);
  function openSettings(tab:SettingsTab){setSettingsTab(tab);setPage("settings");}
  const [availableUpdate,setAvailableUpdate]=useState<{tag:string;message:string}>();
  useEffect(()=>{
    const key=`jfm.update.last-check:${buildInfo.label}`;
    const last=Number(localStorage.getItem(key)||0);
    if(Date.now()-last<24*60*60*1000)return;
    let cancelled=false;
    const timer=window.setTimeout(()=>{void window.jobfindsme?.checkForUpdates().then(result=>{
      if(cancelled)return;
      localStorage.setItem(key,String(Date.now()));
      if(result.status==="available"&&result.tag&&localStorage.getItem("jfm.update.dismissed-tag")!==result.tag)setAvailableUpdate({tag:result.tag,message:result.message});
    }).catch(()=>{localStorage.setItem(key,String(Date.now()));});},5000);
    return()=>{cancelled=true;window.clearTimeout(timer);};
  },[]);
  function dismissUpdate(){if(availableUpdate)localStorage.setItem("jfm.update.dismissed-tag",availableUpdate.tag);setAvailableUpdate(undefined);}
  useEffect(()=>{const show=()=>openSettings("sources");window.addEventListener("jfm:show-sources",show);return()=>window.removeEventListener("jfm:show-sources",show);},[page]);
  useEffect(()=>{if(!data)return;const allowed=new Set(data.sources.map(source=>source.source_id));setChosenSources(current=>current.filter(id=>allowed.has(id)));},[data]);
  useEffect(()=>{if(!data||hadSourcePreference.current)return;hadSourcePreference.current=true;
    const first=data.sources.find(source=>source.source_id==="liepin"&&source.live_search_enabled)||data.sources.find(source=>source.live_search_enabled);
    if(first)setChosenSources([first.source_id]);
  },[data]);
  const [failure,setFailure]=useState<{message:string;route:string}>();
  const setError=useCallback((message?:string)=>setFailure(previous=>message?{message,route:routeKey}:previous?.route===routeKey||previous?.route==='*'?undefined:previous),[routeKey]);
  const error=failure&&(failure.route===routeKey||failure.route==='*')?failure.message:undefined;
  const [checkingService,setCheckingService]=useState(false);
  async function checkService(){setCheckingService(true);try{const status=await window.jobfindsme!.getServiceStatus();setServiceStatus(status);if(status.connected){setData(await window.jobfindsme!.getBootstrap());setError('本地服务已连接，请重试刚才的操作。');}else setError('本地服务尚未连接，请重新打开应用后重试。');}catch{setError('无法连接本地服务，请重新打开应用后重试。');}finally{setCheckingService(false);}}
  useEffect(()=>{const workspace=data?.workspaces[0]?.workspace_id;if(!workspace)return;let cancelled=false;void window.jobfindsme!.listResearchReports(workspace).then(value=>{if(!cancelled)setReports(value);}).catch(()=>{if(!cancelled)setFailure({message:"研究记录暂时无法读取，请稍后重试。",route:`${workspace}:research:`});});return()=>{cancelled=true;};},[data?.workspaces[0]?.workspace_id]);
  const [preparationJob,setPreparationJob]=useState<SearchResultItem["job"]>();
  const [preparationApply,setPreparationApply]=useState(false);
  const [applicationView,setApplicationView]=useState<'materials'|'records'>('materials');
  function openPreparation(job:SearchResultItem["job"],apply=false,view:'materials'|'records'='materials'){setApplicationView(view);setPreparationApply(apply);setPreparationJob(job);}
  const [preparationRequest,setPreparationRequest]=useState<{job?:SearchResultItem["job"];skill:AssistantSkillId;nonce:number;chatId?:string;draft?:string}>();
  const [resumeRequest,setResumeRequest]=useState<ResumeOpenRequest>();
  function openResume(job?:SearchResultItem["job"],sessionId?:string,instruction?:string){setResumeRequest({job,sessionId,instruction,nonce:Date.now()});setPage("resume");}
  function startPreparation(job:SearchResultItem["job"],skill:AssistantSkillId,chatId?:string){setPreparationJob(undefined);if(skill==="resume-tailor"){openResume(job);return;}setResearchTarget(undefined);setPreparationRequest({job,skill,nonce:Date.now(),chatId});setPage("research");}
  const [researchTarget,setResearchTarget]=useState<SearchResultItem["job"]>();
  const [researchBusy,setResearchBusy]=useState(false);
  const [newChatNonce,setNewChatNonce]=useState(0);
  function openNewChat(){setResearchTarget(undefined);setNewChatNonce(value=>value+1);setPage("research");}
  const [suggestedSearch,setSuggestedSearch]=useState<{query:string;nonce:number}>();
  useEffect(() => { if (page === "discover") void window.jobfindsme?.getServiceStatus().then(status => { if (status.connected) void window.jobfindsme!.getBootstrap().then(setData).catch(e => setError(messageOf(e))); }).catch(e=>setError(messageOf(e))); }, [page]);
  const [serviceStatus, setServiceStatus] = useState<ServiceStatus>({ connected: false, message: "本地服务正在启动" });
  useEffect(() => {
    if (!window.jobfindsme) { setFailure({message:"仅可在 JobFindsMe 桌面容器中读取本地数据。",route:"*"}); return; }
    let loadingBootstrap = false;
    let cancelled = false;
    const loadBootstrap = async () => {
      if (loadingBootstrap || cancelled) return;
      loadingBootstrap = true;
      try {
        const value = await window.jobfindsme!.getBootstrap();
        if (!cancelled) { setData(value); setServiceStatus({ connected: true }); setFailure(previous=>previous?.route==="*"?undefined:previous); }
      } catch (bootstrapError) {
        const message = messageOf(bootstrapError);
        if (!cancelled && !message.includes("desktop API is not ready")) setFailure({message,route:"*"});
      } finally {
        loadingBootstrap = false;
      }
    };
    const handleStatus = (status: ServiceStatus) => {
      if (cancelled) return;
      setServiceStatus(status);
      if (status.connected) void loadBootstrap();
      else if (status.message && status.message !== "本地服务正在启动") setFailure({message:status.message,route:"*"});
    };
    const unsubscribe = window.jobfindsme.onServiceStatus(handleStatus);
    const unsubscribeSources = window.jobfindsme.onSourceStatusChanged(()=>void loadBootstrap());
    void window.jobfindsme.getServiceStatus().then(handleStatus).catch((statusError: unknown) => setFailure({message:messageOf(statusError),route:"*"}));
    return () => { cancelled = true; unsubscribe(); unsubscribeSources(); };
  }, []);
  return <Workbench onError={setError} sidebar={<>
    <div className="brand"><img className="brandmark" src="./brand.svg" alt="j" /><span className="brand-name">JobFindsMe</span></div>
    <div className="nav-group"><nav aria-label="工作区">{navItems.map(([label,target])=><button key={target} className={page===target?"active":""} disabled={!serviceStatus.connected} title={label} aria-label={label} aria-current={page===target?"page":undefined} onClick={()=>setPage(target)}><span className="nav-icon"><Icon name={target}/></span><span className="nav-label">{label}</span></button>)}
    <button className={`sidebar-new-chat${page==="research"?" active":""}`} aria-current={page==="research"?"page":undefined} type="button" disabled={!serviceStatus.connected} title="求职助手" aria-label="求职助手" onClick={()=>setPage("research")}><span className="nav-icon"><Icon name="newChat"/></span><span className="nav-label">求职助手</span>{researchBusy&&<span className="sidebar-chat-busy" aria-hidden="true">进行中</span>}</button></nav></div>
    <div id="research-sidebar-history" className="sidebar-history-slot"/>
    <div className="sidebar-bottom"><button className={page==="settings"?"sidebar-settings active":"sidebar-settings"} disabled={!serviceStatus.connected} title="设置" aria-label={availableUpdate?"设置，有新版本":"设置"} aria-current={page==="settings"?"page":undefined} onClick={()=>openSettings(availableUpdate?"about":settingsTab)}><span className="nav-icon"><Icon name="settings"/></span><span className="nav-label">设置</span>{availableUpdate&&<span className="update-indicator" aria-hidden="true"/>}</button></div>
  </>}>
    <section className="main"><header className={page==="settings"?"topbar settings-topbar":"topbar"}>{page==="settings"?<nav className="settings-tabs" aria-label="设置分类">{settingsItems.map(([label,tab])=><button key={tab} type="button" className={settingsTab===tab?"active":""} aria-current={settingsTab===tab?"page":undefined} onClick={()=>setSettingsTab(tab)}>{label}</button>)}</nav>:<span className="workspace-name" title={data?.workspaces[0]?.name||"本地工作区"}><strong>{{discover:"找工作",records:"岗位管理",resume:"我的简历",research:"求职助手"}[page as WorkPage]}</strong><span className="workspace-divider" aria-hidden="true">/</span>{data?.workspaces[0]?.name||"本地工作区"}</span>}<div className="topbar-actions"><div id="research-topbar-actions" className="research-topbar-actions"/>{page==="research"&&<button className="new-conversation-button" onClick={openNewChat}><Icon name="newChat"/>新建对话</button>}</div></header><div ref={contentRef} onScroll={event=>scrollPositions.current.set(routeKey,event.currentTarget.scrollTop)} className={page==="research"?"content research-content":page==="resume"?"content resume-content":"content"}>
      {availableUpdate&&page!=="settings"&&<div className="update-notice" role="status"><span>JobFindsMe {availableUpdate.tag} 已发布</span><button type="button" onClick={()=>openSettings("about")}>查看更新</button><button type="button" aria-label="不再提示此版本" onClick={dismissUpdate}>暂不提示</button></div>}
      {error&&<div className="operation-notice" role="alert"><span>{userError(error).message}</span>{userError(error).action==='source'?<button onClick={()=>{setError(undefined);openSettings('sources');}}>查看来源</button>:userError(error).message.includes('本地服务')&&<button disabled={checkingService} onClick={()=>void checkService()}>{checkingService?'正在检查…':'检查服务'}</button>}<button aria-label="关闭操作提示" onClick={()=>setError(undefined)}>×</button></div>}
      <div className="discovery-mount" hidden={page!=="discover"}><Discovery onOpenResume={()=>setPage("resume")} active={page==="discover"} suggestedIntent={suggestedSearch} onResearch={openPreparation} data={data} selectedSources={chosenSources} onSelectSource={chooseSource} onSelectAllSources={chooseAllSources} reports={reports}/></div>
      <div className="research-mount" hidden={page!=="research"}><ResearchPage onEditResume={openResume} preparationRequest={preparationRequest} selectedSources={chosenSources} onReports={setReports} onBusyChange={setResearchBusy} active={page==="research"} archiveVisible={page==="settings"&&settingsTab==="archive"} newChatNonce={newChatNonce} onOpenChat={()=>{setResearchTarget(undefined);setPage("research");}} data={data} target={researchTarget} onSearchJobs={query=>{setSuggestedSearch({query,nonce:Date.now()});setPage("discover");}} onError={setError}/></div>
      <div hidden={page!=="records"}><RecordsPage active={page==="records"} data={data} onPrepare={openPreparation} onDiscover={()=>setPage("discover")}/></div>
      <div hidden={page!=="resume"}><ResumePage active={page==="resume"} onPrepare={openPreparation} openRequest={resumeRequest}/></div>
      {page==="settings"&&<section className="settings-page"><div className="settings-panel">{settingsTab==="sources"?<SourcesPage checks={sourceChecks} onChecks={rows=>setSourceChecks(current=>mergeSourceChecks(current,rows))} onSelectAll={chooseAllSources} selected={chosenSources} onSelect={chooseSource} data={data} onRefresh={setData} onError={setError}/>:settingsTab==="models"?<ModelsPage workspaceId={data?.workspaces[0]?.workspace_id} onError={setError}/>:settingsTab==="archive"?<div id="research-archive-settings"/>:<UpdatesPage availableUpdate={availableUpdate}/>}</div></section>}
    </div></section>
    {preparationJob&&data?.workspaces[0]&&<JobPreparation initialApplicationView={applicationView} initialApplicationOpen={preparationApply} key={preparationJob.job_id} workspaceId={data.workspaces[0].workspace_id} job={preparationJob} onClose={()=>setPreparationJob(undefined)} onStart={startPreparation}/>}
  </Workbench>;
}

function SourcesPage({ checks, onChecks, data, selected, onSelect, onSelectAll, onRefresh, onError }: { checks:SourceCheckResult[]; onChecks(rows:SourceCheckResult[]):void; onSelectAll(selected:boolean):void; selected:string[]; onSelect(id:string, selected:boolean):void; data?: BootstrapData; onRefresh(data: BootstrapData): void; onError(message?: string): void }) {
  const capabilityLabel=(status:string)=>({verified:"已验证",partial:"部分可用",blocked:"受阻",unverified:"待验证"})[status]??status;
  const [verifying, setVerifying] = useState<string[]>([]);
  const [audit,setAudit]=useState<{done:number;total:number;running:boolean;cancelled:boolean;rows:SourceCheckResult[];startedAt:string}>();
  const auditRunId=useRef("");
  const onChecksRef=useRef(onChecks);onChecksRef.current=onChecks;
  useEffect(()=>{const unsubscribe=window.jobfindsme?.onSourceCheckProgress(value=>{if(value.runId!==auditRunId.current)return;onChecksRef.current([value.result]);setAudit(current=>current?.running?({...current,done:value.done,total:value.total,rows:[...current.rows,value.result]}):current);});return()=>{unsubscribe?.();if(auditRunId.current)void window.jobfindsme?.cancelAllSourceChecks();};},[]);
  const openBrowser = useOriginalBrowser();
  const platforms = data?.sources.filter(source => source.source_type === "platform") ?? [];
  async function verify(sourceId: string) {
    const source=platforms.find(item=>item.source_id===sourceId);
    if(!source)return;
    setVerifying(current=>current.includes(sourceId)?current:[...current,sourceId]);
    onError(undefined);
    const started=Date.now();
    try {
      try {
        const checked=await window.jobfindsme!.verifySource(sourceId);
        onChecks([{source:checked,outcome:checked.live_search_enabled?"verified_now":"unverified",evidence:"live",attempted_at:new Date().toISOString(),detail:checked.detail,duration_ms:Date.now()-started}]);
      } catch(error) {
        const detail=messageOf(error),outcome=sourceCheckFailureOutcome(detail);
        onChecks([{source,outcome,evidence:outcome==="skipped_cooldown"?"history":"live",attempted_at:new Date().toISOString(),detail:userError(error).message,duration_ms:Date.now()-started}]);
        if(userError(error).kind==="service")onError(detail);
      }
      try{onRefresh(await window.jobfindsme!.getBootstrap());}catch(error){onError(messageOf(error));}
    } finally {
      setVerifying(current=>current.filter(id=>id!==sourceId));
    }
  }
  async function inspectAll() {
    if(audit?.running)return;
    const count=data?.sources.length??0;
    if(!count)return;
    const runId=crypto.randomUUID();auditRunId.current=runId;
    const startedAt=new Date().toISOString();
    setAudit({done:0,total:count,running:true,cancelled:false,rows:[],startedAt});
    onError(undefined);
    try {
      const results=await window.jobfindsme!.checkAllSources(runId);
      if(auditRunId.current!==runId)return;
      auditRunId.current="";
      onChecks(results);
      setAudit({done:results.length,total:results.length,running:false,cancelled:results.some(result=>result.outcome==="cancelled"),rows:results,startedAt});
      onRefresh(await window.jobfindsme!.getBootstrap());
    } catch(error){
      if(auditRunId.current===runId)setAudit(current=>current&&({...current,running:false,cancelled:true}));
      onError(messageOf(error));
    }finally{if(auditRunId.current===runId)auditRunId.current="";}
  }
  function cancelInspect(){setAudit(current=>current&&({...current,cancelled:true}));void window.jobfindsme!.cancelAllSourceChecks().catch(error=>onError(messageOf(error)));}
  const rows = sourceStatusRows(platforms,checks);
  const availableCount=rows.filter(row=>selected.includes(row.source.source_id)&&row.presented.available).length;
  return <>
    <div className="heading-row settings-heading"><div><h1>岗位来源</h1><p>选择参与检索的平台，管理登录与读取状态。</p></div><span className="settings-count">{platforms.length} 个平台</span></div>
    <div className="source-toolbar"><p className="source-selection-summary" role="status">已选 {selected.length} 个平台 · 当前可检索 {availableCount} 个{!selected.length&&" · 请至少选择一个平台"}</p><div className="source-toolbar-actions"><div className="button-row"><button disabled={!platforms.length} onClick={()=>onSelectAll(!platforms.every(s=>selected.includes(s.source_id)))}>{platforms.length>0&&platforms.every(s=>selected.includes(s.source_id))?"取消全选":"全选平台"}</button><button disabled={!!audit?.running||verifying.length>0||!data?.sources.length} onClick={()=>void inspectAll()}>检查全部平台</button>{audit?.running&&<button onClick={cancelInspect}>{audit.cancelled?"停止中…":"取消"}</button>}</div></div></div>
    {audit&&<div className="source-audit-progress" role="status"><span>{audit.running?audit.cancelled?"正在停止":"检查中":audit.cancelled?"部分完成":"检查结束"} · 已评估 {audit.done}/{audit.total} 个来源{!audit.running&&` · 本次实际探测 ${audit.rows.filter(row=>row.evidence==="live").length} 个，通过 ${audit.rows.filter(row=>row.outcome==="verified_now").length} 个 · 复用缓存 ${audit.rows.filter(row=>row.evidence==="cache").length} 个 · 登录/风控跳过 ${audit.rows.filter(row=>row.evidence!=="live"&&["login_required","risk_control","skipped_cooldown"].includes(row.outcome)).length} 个 · 未检查 ${audit.rows.filter(row=>["not_checked_budget","cancelled"].includes(row.outcome)&&row.evidence!=="live").length} 个`}</span>{audit.running&&<progress value={audit.done} max={audit.total} aria-label="来源检查进度"/>}</div>}
    <section className="source-grid source-catalog">{rows.map(({source,checked,presented}) => {
      return <article className="panel source-card" key={source.source_id}>
        <div className="source-card-head"><label className="source-choice"><input type="checkbox" aria-label={`加入搜索范围：${source.name}`} checked={selected.includes(source.source_id)} onChange={event=>onSelect(source.source_id,event.target.checked)}/><strong>{source.name}</strong></label><span className={presented.available?"ready":"muted"}>{presented.title}</span></div>
        <p className="source-card-status">{presented.detail}</p>
        <div className="button-row source-card-actions">{presented.action==="login"?<button onClick={()=>openBrowser({sourceId:source.source_id,title:source.name})}>登录 / 验证</button>:presented.action==="check"?<button disabled={verifying.includes(source.source_id)||!!audit?.running} onClick={()=>void verify(source.source_id)}>{verifying.includes(source.source_id)?"检查中…":"检查"}</button>:null}{presented.action!=="check"&&<button disabled={verifying.includes(source.source_id)||!!audit?.running} onClick={()=>void verify(source.source_id)}>{verifying.includes(source.source_id)?"检查中…":"检查"}</button>}{presented.action!=="login"&&<button onClick={()=>openBrowser({sourceId:source.source_id,title:source.name})}>打开官网</button>}</div>
        {checked?.outcome==="login_required"&&<p className="note source-login-help">请在应用内完成登录，再重试检查。</p>}
        <details><summary>能力与限制</summary><p className="note">登录：{source.session_status==="verified"?"此前记录已登录":source.session_status==="anonymous"?"匿名使用":source.session_status==="expired"?"需要重新确认":source.session_status==="blocked"?"需要验证":"未确认"} · 列表：{capabilityLabel(source.list_status)} · 详情：{capabilityLabel(source.detail_status)} · 字段：{capabilityLabel(source.fields_status)} · 网站续页：{capabilityLabel(source.pagination_status)}</p><p className="note">{checked?.outcome==="failed"?userError(checked.detail).message:checked?.detail||source.detail}</p>{source.last_verified_at&&<p className="note">上次验证：{new Date(source.last_verified_at).toLocaleString()}</p>}</details>
      </article>;
    })}</section><details className="source-guidance"><summary>登录与检查说明</summary><p className="note">平台登录与检索能力分别核对；智联在应用内使用官方登录页，Chrome 登录状态不会同步。全部检查按原有单源和总预算执行，未轮到的来源不算本次通过；风险验证立即停源。关闭原页不清除已保存的会话，登录仍可能过期。</p></details>
  </>;
}


function messageOf(reason: unknown): string { return reason instanceof Error ? reason.message : "本地服务不可用"; }

function UpdatesPage({availableUpdate}:{availableUpdate?:{tag:string;message:string}}){
 const [busy,setBusy]=useState(false);
 const [result,setResult]=useState<{message:string;tag?:string}|undefined>(availableUpdate);
 async function check(){setBusy(true);setResult(undefined);try{setResult(await window.jobfindsme!.checkForUpdates());}catch(error){setResult({message:messageOf(error)});}finally{setBusy(false);}}
 return <section className="section updates-page"><h2>关于与更新</h2><p>当前版本：{buildInfo.label.split("+")[0]}</p><p>检查 GitHub 正式发布的桌面版本。下载安装不会在后台自动执行。</p><div className="button-row"><button className="primary-button" disabled={busy} onClick={()=>void check()}>{busy?"正在检查…":"检查更新"}</button><button onClick={()=>void window.jobfindsme!.openReleases().catch(error=>setResult({message:messageOf(error)}))}>查看发布与下载</button></div>{result&&<p role="status">{result.tag&&`发布版本：${result.tag} · `}{result.message}</p>}<details><summary>构建信息</summary><p>{buildInfo.label}</p></details></section>;
}
