import {readSelectedSources} from "../../shared/discovery-filters";
import {reportMatchesJob} from "../../shared/research-reports";
import type {ResearchReport} from "../../shared/contracts";
import {ResumePage} from "./components/ResumePage";
import {userError} from "../../shared/user-errors";
import {JobActions} from "./components/JobActions";
import { MatchingRulesPage, defaultWeights } from "./components/MatchingRulesPage";
import { Icon } from "./components/Icon";
import { modelPresets, protocolNames } from "./components/model-presets";
import { ResearchPage } from "./components/ResearchPage";
import { sourceBrowserSpecs, isAllowedSourceUrl, type SourceBrowserId } from "../../main/source-browser-policy";
import { Discovery } from "./components/Discovery";
import {formatSalary} from "./components/salary";
import { Workbench, BrowserToggle, useOriginalBrowser } from "./components/Workbench";
import { FormEvent, useEffect, useRef, useState } from "react";
import buildInfo from "../../build-info.json";

import type {
  BootstrapData, ModelConnection, ModelConnectionInput, SourceCheckResult,
  ModelProtocol, ServiceStatus,
  SearchResultItem, TrackedJob, MatchingWeights,
} from "../../shared/contracts";

type Page = "discover" | "research" | "records" | "resume" | "scores" | "sources" | "models";

const navGroups: Array<[string, Array<[string, Page | undefined]>]> = [
  ["开始", [
    ["找工作", "discover"], ["口碑调查", "research"],
    ["已看过", "records"],
  ]],
  ["设置与资料", [
    ["我的简历", "resume"], ["匹配规则", "scores"],
    ["岗位来源", "sources"], ["模型设置", "models"],
  ]],
];
const navItems = navGroups.flatMap(([, items]) => items);
export function App() {
  const [chosenSources,setChosenSources] = useState<string[]>(()=>readSelectedSources(localStorage.getItem("jfm.sources.selected")));
  useEffect(()=>localStorage.setItem("jfm.sources.selected",JSON.stringify(chosenSources)),[chosenSources]);
  const [reports,setReports]=useState<ResearchReport[]>([]);
  function chooseSource(id:string, selected:boolean) {setChosenSources(current => {const previous=current;const next=selected ? [...new Set([...previous,id])] : previous.filter(s=>s!==id);localStorage.setItem("jfm.sources.selected",JSON.stringify(next));return next;});}
  function chooseAllSources(selected:boolean) {setChosenSources(selected?(data?.sources.map(source=>source.source_id)??[]):[]);}
  const [page, setPage] = useState<Page>("discover");
  useEffect(()=>{const show=()=>setPage("sources");window.addEventListener("jfm:show-sources",show);return()=>window.removeEventListener("jfm:show-sources",show);},[]);
  const [data, setData] = useState<BootstrapData>();
  const [error, setError] = useState<string>();
  useEffect(()=>{const workspace=data?.workspaces[0]?.workspace_id;if(!workspace)return;let cancelled=false;void window.jobfindsme!.listResearchReports(workspace).then(value=>{if(!cancelled)setReports(value);}).catch(e=>setError(messageOf(e)));return()=>{cancelled=true;};},[data?.workspaces[0]?.workspace_id,page]);
  const [researchTarget,setResearchTarget]=useState<SearchResultItem["job"]>();
  const [weights, setWeights] = useState<MatchingWeights>(()=>{try {const w=JSON.parse(localStorage.getItem("jfm.matching.v2")||"null");return w && Object.keys(w).sort().join()===Object.keys(defaultWeights).sort().join() && Object.values(w).every(v=>Number.isInteger(v)&&Number(v)>=0) && Object.values(w).reduce<number>((a,v)=>a+Number(v),0)===100 ? w : defaultWeights;}catch{return defaultWeights;}});
  useEffect(()=>{if(Object.values(weights).every(v=>Number.isInteger(v)&&v>=0)&&Object.values(weights).reduce((a,b)=>a+b,0)===100)localStorage.setItem("jfm.matching.v2",JSON.stringify(weights));},[weights]);
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
        if (!cancelled) { setData(value); setError(undefined); setServiceStatus({ connected: true }); }
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
      {navGroups.map(([group, items]) => <div className="nav-group" key={group}>
        <p className="eyebrow">{group}</p><nav>{items.map(([label, target]) =>
          <button key={label} className={page === target ? "active" : ""} disabled={!target || !serviceStatus.connected} title={label} aria-label={label} aria-current={page === target ? "page" : undefined} onClick={() => target && setPage(target)}><span className="nav-icon"><Icon name={target ?? "discover"} /></span><span className="nav-label">{label}</span>{!target && <span>待接入</span>}</button>
        )}</nav>
      </div>)}
      <div className="local-status"><span className={!serviceStatus.connected ? "dot error" : "dot"} />{serviceStatus.connected ? "个人工作空间 · 本地优先" : serviceStatus.message}</div>
    </>}>
  <section className="main"><header className="topbar"><span>工作空间 / {navItems.find(([, target]) => target === page)?.[0]}</span><span className="pill">本地数据 · {data?.workspaces.length ?? 0} 个工作空间</span><BrowserToggle /></header><div className="content">{error && <div className="error-message banner" role="alert">{userError(error).message} <button onClick={()=>{setError(undefined);setPage("sources");}}>查看来源状态</button><button onClick={()=>setError(undefined)}>关闭提示</button></div>}<div className="discovery-mount" hidden={page !== "discover"}><Discovery active={page === "discover"} onResearch={job=>{setResearchTarget(job);setPage("research");}} onResume={()=>setPage("resume")} data={data} selectedSources={chosenSources} onSelectSource={chooseSource} onSelectAllSources={chooseAllSources} reports={reports} weights={weights} onWeightsChange={setWeights} onError={setError} /></div><div hidden={page !== "research"}><ResearchPage onReports={setReports} active={page === "research"} data={data} target={researchTarget} onBack={()=>setPage("discover")} onError={setError}/></div>{page === "records" && <RecordsPage reports={reports} data={data} onResearch={job=>{setResearchTarget(job);setPage("research");}} onError={setError} />}{page === "resume" && <ResumePage />}{page === "scores" && <MatchingRulesPage workspaceId={data?.workspaces[0]?.workspace_id} weights={weights} onApply={setWeights} />}{page === "sources" && <SourcesPage selected={chosenSources} onSelect={chooseSource} data={data} onRefresh={setData} onError={setError} />}{page === "models" && <ModelsPage onError={setError} />}</div><footer className="footer">本地优先 · 手动投递 · 完全退出后不调度 · {buildInfo.label}</footer></section>
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
  return <><div className="heading-row"><div><h1>已看过</h1><p>回到你认真看过的机会。</p></div><span className="pill">{visibleItems.length} 条岗位</span></div>
    <div className="source-tabs">{[["read","已看过"],["saved","收藏"],["applied","已投递"]].map(([key,label])=><button key={key} className={filter===key?"active":""} onClick={()=>setFilter(key)}>{label}</button>)}</div>
    <div className="job-list section">{visibleItems.length?visibleItems.map(item=><article key={item.job.job_id}>
      <div><strong>{item.job.title}</strong><span>{item.job.source.source_name}</span></div>
      <p>{item.job.company} · {item.job.locations.join("/")||"地点未知"} · {formatSalary(item.job)}</p>
      <JobActions hasReport={reports.some(report=>reportMatchesJob(report,item.job))} tracking={item.tracking} onTrack={(event,enabled)=>update(item,event,enabled)} onOpen={()=>update(item,"apply_opened")} onResearch={()=>onResearch(item.job)} onError={onError}/>
    </article>):<div className="empty"><strong>暂无记录</strong><p>阅读过的岗位会留在这里；收藏和投递状态分别保存。</p></div>}</div></>;
}

function SourcesPage({ data, selected, onSelect, onRefresh, onError }: { selected:string[]; onSelect(id:string, selected:boolean):void; data?: BootstrapData; onRefresh(data: BootstrapData): void; onError(message?: string): void }) {
  const capabilityLabel=(status:string)=>({verified:"已验证",partial:"部分可用",blocked:"受阻",unverified:"待验证"})[status]??status;
  const outcomeLabel=(result:SourceCheckResult)=>({verified_now:"本次探测通过",cached_recent:"最近验证缓存",skipped_cooldown:"冷却中跳过",login_required:"需在应用内登录",risk_control:"平台验证 / 风控",unverified:"本次未确认",failed:"本次检查失败",not_checked_budget:"预算未轮到",cancelled:"取消未检查"})[result.outcome];
  const [tab, setTab] = useState<"platform" | "company">("platform");
  const [verifying, setVerifying] = useState<string>();
  const [audit,setAudit]=useState<{done:number;total:number;running:boolean;cancelled:boolean;rows:SourceCheckResult[];startedAt:string}>();
  const auditRunId=useRef("");
  useEffect(()=>{const unsubscribe=window.jobfindsme?.onSourceCheckProgress(value=>{if(value.runId!==auditRunId.current)return;setAudit(current=>current?.running?({...current,done:value.done,total:value.total,rows:[...current.rows,value.result]}):current);});return()=>{unsubscribe?.();if(auditRunId.current)void window.jobfindsme?.cancelAllSourceChecks();};},[]);
  const openBrowser = useOriginalBrowser();
  const platforms = data?.sources.filter(source => source.source_type === "platform") ?? [];
  const companies = data?.sources.filter(source => source.source_type === "company") ?? [];
  async function verify(sourceId: string) {
    setVerifying(sourceId);
    onError(undefined);
    try {
      await window.jobfindsme!.verifySource(sourceId);
      onRefresh(await window.jobfindsme!.getBootstrap());
    } catch (error) {
      onError(messageOf(error));
    } finally {
      setVerifying(undefined);
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
  const rows = tab === "platform" ? platforms : companies;
  return <>
    <div className="heading-row"><div><h1>岗位来源</h1><p>多选下次想检索的平台或公司官网，与发现岗位同步。已创建的定时任务不受影响。</p></div></div>
    <section className="panel source-audit"><div className="source-audit-heading"><div><h2>检查全部来源</h2><p className="note">按队列检查 4 个平台和 16 个公司官网；每源最多 8 秒、合计最多 45 秒，只探测一个岗位列表页。未登录、冷却或超预算的来源明确标为未检查，不把历史可用写成本次通过。</p></div><div className="button-row"><button disabled={!!audit?.running||!data?.sources.length} onClick={()=>void inspectAll()}>开始检查全部</button>{audit?.running&&<button onClick={cancelInspect}>{audit.cancelled?"停止中…":"取消"}</button>}</div></div>
      {audit&&<><p role="status">{audit.running?audit.cancelled?"正在停止":"检查中":audit.cancelled?"部分完成":"本次队列结束"} · 已处理 {audit.done}/{audit.total} · 本次通过 {audit.rows.filter(row=>row.outcome==="verified_now").length} · {new Date(audit.startedAt).toLocaleString()}</p><progress value={audit.done} max={audit.total} aria-label="来源检查进度"/><details className="source-audit-details"><summary>查看逐源结果 · {audit.rows.length} 条</summary><div className="source-audit-rows">{audit.rows.map(result=><div key={result.source.source_id}><strong>{result.source.name}</strong><span>{outcomeLabel(result)}<small>{result.evidence==="live"?"本次探测":result.evidence==="cache"?"最近缓存":result.evidence==="history"?"历史状态":"未探测"}</small></span><span>列表 {capabilityLabel(result.source.list_status)} · 详情 {capabilityLabel(result.source.detail_status)} · 字段 {capabilityLabel(result.source.fields_status)} · 网站续页 {capabilityLabel(result.source.pagination_status)}</span><span>{result.detail}{result.attempted_at?` · 处理 ${new Date(result.attempted_at).toLocaleTimeString()}`:""}{result.source.last_verified_at?` · 上次验证 ${new Date(result.source.last_verified_at).toLocaleString()}`:""}</span></div>)}</div></details></>}
    </section>
    <p className="source-selection-summary" role="status">已选 {selected.length} 个来源 · 当前可检索 {data?.sources.filter(s=>selected.includes(s.source_id)&&s.live_search_enabled).length??0} 个{!selected.length&&" · 请至少选择一个来源"}</p><div className="source-tabs"><button className={tab === "platform" ? "active" : ""} onClick={() => setTab("platform")}>招聘平台 · {platforms.length}</button><button className={tab === "company" ? "active" : ""} onClick={() => setTab("company")}>公司官网 · {companies.length}</button></div>
    <section className="source-grid source-catalog">{rows.map(source => {
      const stale=!!source.last_verified_at && Date.now()-Date.parse(source.last_verified_at)>24*60*60*1000;
      const login=source.session_status==="verified"?"当前已确认":source.session_status==="expired"?"已失效":source.session_status==="blocked"?"平台验证中":source.login_required?"未确认":"公开浏览";
      const ability=source.live_search_enabled?(stale?"历史可检索 · 待复查":source.fields_status!=="verified"||source.pagination_status!=="verified"?"可检索 · 部分覆盖":"可检索"):source.list_status==="partial"?"列表可见 · 自动检索待验":source.list_status==="blocked"?"检索暂停":"自动检索待验证";
      return <article className="panel source-card" key={source.source_id}>
        <div className="source-card-head"><label className="source-choice"><input type="checkbox" checked={selected.includes(source.source_id)} onChange={event=>onSelect(source.source_id,event.target.checked)}/><strong>{source.name}</strong></label><span className={source.live_search_enabled&&!stale?"ready":"muted"}>{ability}</span></div>
        <div className="source-card-status"><span>登录：{login}</span></div>
        <div className="button-row source-card-actions"><button className="primary-button" onClick={()=>openBrowser({sourceId:source.source_id,title:source.name})}>{source.login_required?"打开来源 / 登录":"打开官网"}</button><button disabled={Boolean(verifying)||!!audit?.running} onClick={()=>void verify(source.source_id)}>{verifying===source.source_id?"检查中…":"重试检查"}</button></div>
        <p className="note">{source.last_verified_at?`最近检查 ${new Date(source.last_verified_at).toLocaleString()} · `:"尚未检查 · "}{source.live_search_enabled?"实际搜索前仍会核对会话与页面；列表、详情和网站续页可能只覆盖部分结果。":"请先在来源原页确认页面可用；可浏览不代表自动检索成功。"}</p>
        <details><summary>能力与限制</summary><p className="note">列表：{capabilityLabel(source.list_status)} · 详情：{capabilityLabel(source.detail_status)} · 字段：{capabilityLabel(source.fields_status)} · 网站续页：{capabilityLabel(source.pagination_status)}</p><p className="note">{source.detail}</p></details>
      </article>;
    })}</section><p className="note">平台登录与实际检索分别核对。智联在应用内打开您提供的 passport.zhaopin.com 登录页；Chrome 登录不会自动同步到应用的独立会话。打开来源后会观察已加载页面；只有看到可读列表才做一次有冷却期的限额检查。风险验证立即停源；手动检查仅用于重试。关闭原页不清除平台允许保存的会话，登录仍可能过期。</p>
  </>;
}

function ModelsPage({ onError }: { onError(message?: string): void }) {
  const [connections, setConnections] = useState<ModelConnection[]>([]); const [secure, setSecure] = useState(false); const [testing, setTesting] = useState<string>();
  const [form, setForm] = useState<ModelConnectionInput>({ provider: "DeepSeek", protocol: "openai_compatible", endpoint: "https://api.deepseek.com", model_id: "", api_key: "", auth_mode: "api_key" });
  useEffect(() => { void Promise.all([window.jobfindsme!.listModelConnections(), window.jobfindsme!.secureStorageAvailable()]).then(([items, available]) => { setConnections(items); setSecure(available); }).catch((e) => onError(messageOf(e))); }, [onError]);
  async function save(event: FormEvent) { event.preventDefault(); onError(undefined); try { const saved = await window.jobfindsme!.saveModelConnection(form); setConnections((items) => [saved, ...items.filter((item) => item.connection_id !== saved.connection_id)]); setForm((value) => ({ ...value, connection_id: saved.connection_id, api_key: "" })); } catch (e) { onError(messageOf(e)); } }
  async function test(connectionId: string) { setTesting(connectionId); onError(undefined); try { const tested = await window.jobfindsme!.testModelConnection(connectionId); setConnections((items) => items.map((item) => item.connection_id === connectionId ? { ...tested, has_api_key: item.has_api_key } : item)); } catch (e) { const latest = await window.jobfindsme!.listModelConnections(); setConnections(latest); onError(messageOf(e)); } finally { setTesting(undefined); } }
  return <><div className="heading-row"><div><h1>模型设置</h1><p>非秘密配置保存在本地数据库，API Key 仅进入系统加密存储。</p></div><span className={secure ? "pill ready" : "pill blocked"}>{secure ? "安全存储可用" : "安全存储不可用"}</span></div><div className="settingssplit"><form className="panel model-form" onSubmit={(event) => void save(event)}><label>服务商<select value={modelPresets.some(p => p.name === form.provider) ? form.provider : "自定义"} onChange={e => { const p = modelPresets.find(p => p.name === e.target.value)!; setForm({provider:p.name,protocol:p.protocol,endpoint:p.endpoint,model_id:"",api_key:"",auth_mode:p.local ? "none" : "api_key"}); }}>{modelPresets.map(p => <option key={p.name}>{p.name}</option>)}</select></label>{modelPresets.find(p => p.name === form.provider)?.note && <p className="note">{modelPresets.find(p => p.name === form.provider)?.note}</p>}<label>协议<select value={form.protocol} onChange={(e) => setForm({ ...form, protocol: e.target.value as ModelProtocol })}><option value="openai_compatible">OpenAI 兼容</option><option value="anthropic">Anthropic 原生</option><option value="gemini">Gemini 原生</option></select></label><label>API 基础地址（不含请求路径）<input type="url" value={form.endpoint} onChange={(e) => setForm({ ...form, endpoint: e.target.value })} required /></label><label>模型 ID（按服务商控制台或本机模型列表填写）<input value={form.model_id} onChange={(e) => setForm({ ...form, model_id: e.target.value })} required /></label><label>认证方式<select value={form.auth_mode ?? "api_key"} onChange={e => setForm({...form,auth_mode:e.target.value as "api_key" | "none",api_key:""})}><option value="api_key">API Key</option><option value="none">本机免密</option></select></label>{form.auth_mode !== "none" && <label>API Key<input type="password" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} placeholder={form.connection_id ? "留空则保留已存密钥" : "仅保存到系统安全存储"} /></label>}<button className="primary-button" disabled={!secure && Boolean(form.api_key)}>保存配置</button><p className="note">保存不会发起请求；新配置保持“未验证”。</p></form><aside className="panel"><h3>已保存连接</h3>{connections.length === 0 && <p className="muted">尚无配置。基础检索不依赖模型。</p>}{connections.map((connection) => <article key={connection.connection_id}><div><strong>{connection.provider} · {connection.model_id}</strong><span className={connection.status === "verified" ? "ready" : "blocked"}>{{unverified:"待测试",testing:"测试中",verified:"可用",failed:"连接失败",cancelled:"已取消"}[connection.status]}</span></div><p>{protocolNames[connection.protocol]} · {connection.endpoint}<br />认证：{connection.auth_mode === "none" ? "本机免密" : connection.has_api_key ? "密钥已安全保存" : "密钥未保存"}{connection.last_error ? ` · ${connection.last_error}` : ""}</p><div className="button-row"><button onClick={() => setForm({connection_id:connection.connection_id,provider:connection.provider,protocol:connection.protocol,endpoint:connection.endpoint,model_id:connection.model_id,auth_mode:connection.auth_mode ?? "api_key",api_key:""})}>编辑</button><button disabled={(!connection.has_api_key && connection.auth_mode !== "none") || Boolean(testing)} onClick={() => void test(connection.connection_id)}>{testing === connection.connection_id ? "测试中…" : "测试连接"}</button>{testing === connection.connection_id && <button onClick={() => void window.jobfindsme!.cancelModelTest()}>取消</button>}</div>{connection.last_tested_at && <p className="note">最近测试 {new Date(connection.last_tested_at).toLocaleString()} · 用量 {connection.input_tokens ?? "?"}/{connection.output_tokens ?? "?"} tokens</p>}</article>)}</aside></div></>;
}

function messageOf(reason: unknown): string { return reason instanceof Error ? reason.message : "本地服务不可用"; }
