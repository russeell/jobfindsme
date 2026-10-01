import {readSelectedSources} from "../../shared/discovery-filters";
import {reportMatchesJob} from "../../shared/research-reports";
import type {ResearchReport} from "../../shared/contracts";
import {userError} from "../../shared/user-errors";
import {JobActions} from "./search/JobActions";
import { Icon } from "./shared/Icon";
import { ModelsPage } from "./settings/ModelsPage";
import { ResearchPage } from "./research/ResearchPage";
import { sourceBrowserSpecs, isAllowedSourceUrl, type SourceBrowserId } from "../../shared/source-browser-policy";
import { Discovery } from "./search/Discovery";
import {formatSalary} from "./search/salary";
import { Workbench, useOriginalBrowser } from "./shared/Workbench";
import {presentSourceStatus,sourceCheckFailureOutcome} from "../../shared/source-presentation";
import { FormEvent, useEffect, useRef, useState } from "react";
import buildInfo from "../../build-info.json";

import type {
  BootstrapData, SourceCheckResult,
  ServiceStatus,
  SearchResultItem, TrackedJob,
} from "../../shared/contracts";

type WorkPage = "discover" | "research" | "records";
type Page = WorkPage | "settings";
type SettingsTab = "sources" | "models" | "about" | "archive";
const navItems: Array<[string, WorkPage]> = [["找工作", "discover"], ["我的岗位", "records"]];
const settingsItems: Array<[string, SettingsTab]> = [["岗位来源", "sources"], ["对话归档", "archive"], ["模型设置", "models"], ["版本更新", "about"]];
export function App() {
  const [chosenSources,setChosenSources] = useState<string[]>(()=>readSelectedSources(localStorage.getItem("jfm.sources.selected")));
  const hadSourcePreference=useRef(localStorage.getItem("jfm.sources.selected")!==null);
  useEffect(()=>localStorage.setItem("jfm.sources.selected",JSON.stringify(chosenSources)),[chosenSources]);
  const [reports,setReports]=useState<ResearchReport[]>([]);
  function chooseSource(id:string, selected:boolean) {setChosenSources(current => {const previous=current;const next=selected ? [...new Set([...previous,id])] : previous.filter(s=>s!==id);localStorage.setItem("jfm.sources.selected",JSON.stringify(next));return next;});}
  function chooseAllSources(selected:boolean) {setChosenSources(selected?(data?.sources.map(source=>source.source_id)??[]):[]);}
  const [page, setPage] = useState<Page>("discover");
  const [settingsTab,setSettingsTab]=useState<SettingsTab>("sources");
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
  const [data, setData] = useState<BootstrapData>();
  useEffect(()=>{if(!data)return;const allowed=new Set(data.sources.map(source=>source.source_id));setChosenSources(current=>current.filter(id=>allowed.has(id)));},[data]);
  useEffect(()=>{if(!data||hadSourcePreference.current)return;hadSourcePreference.current=true;
    const first=data.sources.find(source=>source.source_id==="liepin"&&source.live_search_enabled)||data.sources.find(source=>source.live_search_enabled);
    if(first)setChosenSources([first.source_id]);
  },[data]);
  const [error, setError] = useState<string>();
  useEffect(()=>{const workspace=data?.workspaces[0]?.workspace_id;if(!workspace)return;let cancelled=false;void window.jobfindsme!.listResearchReports(workspace).then(value=>{if(!cancelled)setReports(value);}).catch(e=>setError(messageOf(e)));return()=>{cancelled=true;};},[data?.workspaces[0]?.workspace_id,page]);
  const [researchTarget,setResearchTarget]=useState<SearchResultItem["job"]>();
  const [researchBusy,setResearchBusy]=useState(false);
  const [newChatNonce,setNewChatNonce]=useState(0);
  function openNewChat(){setResearchTarget(undefined);setNewChatNonce(value=>value+1);setPage("research");}
  const [suggestedSearch,setSuggestedSearch]=useState<{query:string;nonce:number}>();
  useEffect(() => { if (page === "discover") void window.jobfindsme?.getServiceStatus().then(status => { if (status.connected) void window.jobfindsme!.getBootstrap().then(setData).catch(e => setError(messageOf(e))); }); }, [page]);
  const [serviceStatus, setServiceStatus] = useState<ServiceStatus>({ connected: false, message: "本地服务正在启动" });
  useEffect(() => {
    if (!window.jobfindsme) { setError("仅可在 JobFindsMe 桌面容器中读取本地数据。"); return; }
    let loadingBootstrap = false;
    let cancelled = false;
    const loadBootstrap = async () => {
      if (loadingBootstrap || cancelled) return;
      loadingBootstrap = true;
      try {
        const value = await window.jobfindsme!.getBootstrap();
        if (!cancelled) { setData(value); setServiceStatus({ connected: true }); }
      } catch (bootstrapError) {
        const message = messageOf(bootstrapError);
        if (!cancelled && !message.includes("desktop API is not ready")) setError(message);
      } finally {
        loadingBootstrap = false;
      }
    };
    const handleStatus = (status: ServiceStatus) => {
      if (cancelled) return;
      setServiceStatus(status);
      if (status.connected) void loadBootstrap();
      else if (status.message && status.message !== "本地服务正在启动") setError(status.message);
    };
    const unsubscribe = window.jobfindsme.onServiceStatus(handleStatus);
    const unsubscribeSources = window.jobfindsme.onSourceStatusChanged(()=>void loadBootstrap());
    void window.jobfindsme.getServiceStatus().then(handleStatus).catch((statusError: unknown) => setError(messageOf(statusError)));
    return () => { cancelled = true; unsubscribe(); unsubscribeSources(); };
  }, []);
  return <Workbench onError={setError} sidebar={<>
    <div className="brand"><img className="brandmark" src="./brand.svg" alt="j" /><span className="brand-name">JobFindsMe</span></div>
    <div className="nav-group"><nav aria-label="工作区">{navItems.map(([label,target])=><button key={target} className={page===target?"active":""} disabled={!serviceStatus.connected} title={label} aria-label={label} aria-current={page===target?"page":undefined} onClick={()=>setPage(target)}><span className="nav-icon"><Icon name={target}/></span><span className="nav-label">{label}</span></button>)}
    <button className="sidebar-new-chat" type="button" disabled={!serviceStatus.connected} title="求职助手" aria-label="求职助手" onClick={openNewChat}><span className="nav-icon"><Icon name="newChat"/></span><span className="nav-label">求职助手</span>{researchBusy&&<span className="sidebar-chat-busy" aria-hidden="true">进行中</span>}</button></nav></div>
    <div id="research-sidebar-history" className="sidebar-history-slot"/>
    <div className="sidebar-bottom"><button className={page==="settings"?"sidebar-settings active":"sidebar-settings"} disabled={!serviceStatus.connected} title="设置" aria-label={availableUpdate?"设置，有新版本":"设置"} aria-current={page==="settings"?"page":undefined} onClick={()=>openSettings(availableUpdate?"about":settingsTab)}><span className="nav-icon"><Icon name="settings"/></span><span className="nav-label">设置</span>{availableUpdate&&<span className="update-indicator" aria-hidden="true"/>}</button></div>
  </>}>
    <section className="main"><header className={page==="settings"?"topbar settings-topbar":"topbar"}>{page==="settings"?<nav className="settings-tabs" aria-label="设置分类">{settingsItems.map(([label,tab])=><button key={tab} type="button" className={settingsTab===tab?"active":""} aria-current={settingsTab===tab?"page":undefined} onClick={()=>setSettingsTab(tab)}>{label}</button>)}</nav>:<span className="workspace-name" title={data?.workspaces[0]?.name||"本地工作区"}>{data?.workspaces[0]?.name||"本地工作区"}</span>}<div id="research-topbar-actions" className="research-topbar-actions"/></header><div className={page==="research"?"content research-content":"content"}>
      {availableUpdate&&page!=="settings"&&<div className="update-notice" role="status"><span>JobFindsMe {availableUpdate.tag} 已发布</span><button type="button" onClick={()=>openSettings("about")}>查看更新</button><button type="button" aria-label="不再提示此版本" onClick={dismissUpdate}>暂不提示</button></div>}
      {error&&<div className="error-message banner" role="alert">{userError(error).message} <button onClick={()=>setError(undefined)}>关闭提示</button></div>}
      <div className="discovery-mount" hidden={page!=="discover"}><Discovery active={page==="discover"} suggestedIntent={suggestedSearch} onResearch={job=>{setResearchTarget(job);setPage("research");}} data={data} selectedSources={chosenSources} onSelectSource={chooseSource} onSelectAllSources={chooseAllSources} reports={reports} onError={setError}/></div>
      <div className="research-mount" hidden={page!=="research"}><ResearchPage selectedSources={chosenSources} onReports={setReports} onBusyChange={setResearchBusy} active={page==="research"} archiveVisible={page==="settings"&&settingsTab==="archive"} newChatNonce={newChatNonce} onOpenChat={()=>{setResearchTarget(undefined);setPage("research");}} data={data} target={researchTarget} onSearchJobs={query=>{setSuggestedSearch({query,nonce:Date.now()});setPage("discover");}} onError={setError}/></div>
      {page==="records"&&<RecordsPage reports={reports} data={data} onResearch={job=>{setResearchTarget(job);setPage("research");}} onError={setError}/>}
      {page==="settings"&&<section className="settings-page"><div className="settings-panel">{settingsTab==="sources"?<SourcesPage selected={chosenSources} onSelect={chooseSource} data={data} onRefresh={setData} onError={setError}/>:settingsTab==="models"?<ModelsPage workspaceId={data?.workspaces[0]?.workspace_id} onError={setError}/>:settingsTab==="archive"?<div id="research-archive-settings"/>:<UpdatesPage availableUpdate={availableUpdate}/>}</div></section>}
    </div></section>
  </Workbench>;
}

function RecordsPage({ data, onError, onResearch,reports }: {reports:ResearchReport[]; onResearch(job:SearchResultItem["job"]):void; data?: BootstrapData; onError(message?: string): void }) {
  const [items, setItems] = useState<TrackedJob[]>([]);
  const openBrowser = useOriginalBrowser();
  const [filter, setFilter] = useState("read");
  const visibleItems = items.filter(item => filter === "read" ? item.tracking.read : filter === "saved" ? item.tracking.saved : item.tracking.applied);
  const workspaceId = data?.workspaces[0]?.workspace_id;
  async function update(item: TrackedJob, event_type: "read" | "saved" | "applied" | "apply_opened", enabled = true) {
    if (!workspaceId) return;
    const sourceId = (Object.keys(sourceBrowserSpecs) as SourceBrowserId[]).find(id => isAllowedSourceUrl(id, item.job.apply_url)) || "web";
    onError(undefined);
    try {
      const tracking = await window.jobfindsme!.setJobTracking({workspace_id:workspaceId,job_id:item.job.job_id,event_type,enabled});
      setItems(current => current.map(row => row.job.job_id === item.job.job_id ? {...row,tracking} : row));
      if (event_type === "apply_opened" && sourceId) openBrowser({sourceId,url:item.job.apply_url,title:item.job.title});
    } catch (error) { onError(messageOf(error)); }
  }
  useEffect(() => { if (workspaceId) void window.jobfindsme!.listJobTracking(workspaceId).then(setItems).catch((error) => onError(messageOf(error))); }, [workspaceId, onError]);
  return <><div className="heading-row"><div><h1>我的岗位</h1><p>回到你认真看过的机会。</p></div><span className="pill">{visibleItems.length} 条岗位</span></div>
    <div className="source-tabs">{[["read","已看过"],["saved","收藏"],["applied","已投递"]].map(([key,label])=><button key={key} className={filter===key?"active":""} onClick={()=>setFilter(key)}>{label}</button>)}</div>
    <div className="job-list section">{visibleItems.length?visibleItems.map(item=><article key={item.job.job_id}>
      <div><strong>{item.job.title}</strong><span>{item.job.source.source_name}</span></div>
      <p>{item.job.company} · {item.job.locations.join("/")||"地点未知"} · {formatSalary(item.job)}</p>
      <JobActions hasReport={reports.some(report=>reportMatchesJob(report,item.job))} tracking={item.tracking} onTrack={(event,enabled)=>update(item,event,enabled)} onOpen={()=>update(item,"apply_opened")} onResearch={()=>onResearch(item.job)} onError={onError}/>
    </article>):<div className="empty"><strong>暂无记录</strong><p>阅读过的岗位会留在这里；收藏和投递状态分别保存。</p></div>}</div></>;
}

function SourcesPage({ data, selected, onSelect, onRefresh, onError }: { selected:string[]; onSelect(id:string, selected:boolean):void; data?: BootstrapData; onRefresh(data: BootstrapData): void; onError(message?: string): void }) {
  const capabilityLabel=(status:string)=>({verified:"已验证",partial:"部分可用",blocked:"受阻",unverified:"待验证"})[status]??status;
  const [verifying, setVerifying] = useState<string[]>([]);
  const [audit,setAudit]=useState<{done:number;total:number;running:boolean;cancelled:boolean;rows:SourceCheckResult[];startedAt:string}>();
  const auditRunId=useRef("");
  useEffect(()=>{const unsubscribe=window.jobfindsme?.onSourceCheckProgress(value=>{if(value.runId!==auditRunId.current)return;setAudit(current=>current?.running?({...current,done:value.done,total:value.total,rows:[...current.rows,value.result]}):current);});return()=>{unsubscribe?.();if(auditRunId.current)void window.jobfindsme?.cancelAllSourceChecks();};},[]);
  const openBrowser = useOriginalBrowser();
  const platforms = data?.sources.filter(source => source.source_type === "platform") ?? [];
  async function verify(sourceId: string) {
    setVerifying(current=>current.includes(sourceId)?current:[...current,sourceId]);
    onError(undefined);
    try {
      const checked=await window.jobfindsme!.verifySource(sourceId);
      setAudit(current=>current&&!current.running?{...current,rows:current.rows.map(row=>row.source.source_id===sourceId?{source:checked,outcome:checked.live_search_enabled?"verified_now":"unverified",evidence:"live",attempted_at:new Date().toISOString(),detail:checked.detail,duration_ms:0}:row)}:current);
      onRefresh(await window.jobfindsme!.getBootstrap());
    } catch (error) {
      const detail=messageOf(error);
      const safe=userError(error).message;
      setAudit(current=>current&&!current.running?{...current,rows:current.rows.map(row=>row.source.source_id===sourceId?{...row,outcome:sourceCheckFailureOutcome(detail),evidence:"live",attempted_at:new Date().toISOString(),detail:safe}:row)}:current);
      onError(detail);
      try{onRefresh(await window.jobfindsme!.getBootstrap());}catch{/* Keep the current view if status refresh also fails. */}
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
      setAudit({done:results.length,total:results.length,running:false,cancelled:results.some(result=>result.outcome==="cancelled"),rows:results,startedAt});
      onRefresh(await window.jobfindsme!.getBootstrap());
    } catch(error){
      if(auditRunId.current===runId)setAudit(current=>current&&({...current,running:false,cancelled:true}));
      onError(messageOf(error));
    }finally{if(auditRunId.current===runId)auditRunId.current="";}
  }
  function cancelInspect(){setAudit(current=>current&&({...current,cancelled:true}));void window.jobfindsme!.cancelAllSourceChecks().catch(error=>onError(messageOf(error)));}
  const rows = platforms;
  return <>
    <div className="heading-row settings-heading"><div><h1>岗位来源</h1><p>选择参与检索的平台，管理登录与读取状态。</p></div><span className="settings-count">{platforms.length} 个平台</span></div>
    <div className="source-toolbar"><p className="source-selection-summary" role="status">已选 {selected.length} 个平台 · 当前可检索 {data?.sources.filter(s=>selected.includes(s.source_id)&&s.live_search_enabled).length??0} 个{!selected.length&&" · 请至少选择一个平台"}</p><div className="source-toolbar-actions"><div className="button-row"><button disabled={!!audit?.running||verifying.length>0||!data?.sources.length} onClick={()=>void inspectAll()}>检查全部平台</button>{audit?.running&&<button onClick={cancelInspect}>{audit.cancelled?"停止中…":"取消"}</button>}</div></div></div>
    {audit&&<div className="source-audit-progress" role="status"><span>{audit.running?audit.cancelled?"正在停止":"检查中":audit.cancelled?"部分完成":"检查结束"} · 已评估 {audit.done}/{audit.total} 个来源{!audit.running&&` · 本次实际探测 ${audit.rows.filter(row=>row.evidence==="live").length} 个，通过 ${audit.rows.filter(row=>row.outcome==="verified_now").length} 个 · 复用缓存 ${audit.rows.filter(row=>row.evidence==="cache").length} 个 · 登录/风控跳过 ${audit.rows.filter(row=>row.evidence!=="live"&&["login_required","risk_control","skipped_cooldown"].includes(row.outcome)).length} 个 · 未检查 ${audit.rows.filter(row=>["not_checked_budget","cancelled"].includes(row.outcome)&&row.evidence!=="live").length} 个`}</span>{audit.running&&<progress value={audit.done} max={audit.total} aria-label="来源检查进度"/>}</div>}
    <section className="source-grid source-catalog">{rows.map(source => {
      const recorded=audit?.rows.find(result=>result.source.source_id===source.source_id);
      const checked=recorded?.attempted_at&&source.last_verified_at&&Date.parse(source.last_verified_at)>Date.parse(recorded.attempted_at)?undefined:recorded;
      const presented=presentSourceStatus(source,checked);
      return <article className="panel source-card" key={source.source_id}>
        <div className="source-card-head"><label className="source-choice"><input type="checkbox" aria-label={`加入搜索范围：${source.name}`} checked={selected.includes(source.source_id)} onChange={event=>onSelect(source.source_id,event.target.checked)}/><strong>{source.name}</strong></label><span className={presented.available?"ready":"muted"}>{presented.title}</span></div>
        <p className="source-card-status">{presented.detail}</p>
        <div className="button-row source-card-actions">{presented.action==="login"?<button onClick={()=>openBrowser({sourceId:source.source_id,title:source.name})}>登录 / 验证</button>:presented.action==="check"?<button disabled={verifying.includes(source.source_id)||!!audit?.running} onClick={()=>void verify(source.source_id)}>{verifying.includes(source.source_id)?"检查中…":"检查"}</button>:null}{presented.action!=="check"&&<button disabled={verifying.includes(source.source_id)||!!audit?.running} onClick={()=>void verify(source.source_id)}>{verifying.includes(source.source_id)?"检查中…":"检查"}</button>}{presented.action!=="login"&&<button onClick={()=>openBrowser({sourceId:source.source_id,title:source.name})}>打开官网</button>}</div>
        {checked?.outcome==="login_required"&&<p className="note source-login-help">请在应用内完成登录，再重试检查。</p>}
        <details><summary>能力与限制</summary><p className="note">登录：{source.session_status==="verified"?"此前记录已登录":source.session_status==="anonymous"?"匿名使用":source.session_status==="expired"?"需要重新确认":source.session_status==="blocked"?"平台验证中":"未确认"} · 列表：{capabilityLabel(source.list_status)} · 详情：{capabilityLabel(source.detail_status)} · 字段：{capabilityLabel(source.fields_status)} · 网站续页：{capabilityLabel(source.pagination_status)}</p><p className="note">{checked?.detail||source.detail}</p>{source.last_verified_at&&<p className="note">上次验证：{new Date(source.last_verified_at).toLocaleString()}</p>}</details>
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
