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
import { Workbench, BrowserToggle, useOriginalBrowser } from "./components/Workbench";
import { FormEvent, useEffect, useState } from "react";
import buildInfo from "../../build-info.json";

import type {
  BootstrapData, ModelConnection, ModelConnectionInput,
  ModelProtocol, ServiceStatus,
  SearchResultItem, TrackedJob, MatchingWeights,
} from "../../shared/contracts";

type Page = "discover" | "research" | "records" | "resume" | "scores" | "sources" | "models";

const navGroups: Array<[string, Array<[string, Page | undefined]>]> = [
  ["工作空间", [
    ["发现岗位", "discover"], ["岗位研究", "research"],
    ["已看过", "records"],
  ]],
  ["资料与设置", [
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
  const [page, setPage] = useState<Page>("discover");
  useEffect(()=>{const show=()=>setPage("sources");window.addEventListener("jfm:show-sources",show);return()=>window.removeEventListener("jfm:show-sources",show);},[]);
  const [data, setData] = useState<BootstrapData>();
  const [error, setError] = useState<string>();
  useEffect(()=>{const workspace=data?.workspaces[0]?.workspace_id;if(!workspace)return;let cancelled=false;void window.jobfindsme!.listResearchReports(workspace).then(value=>{if(!cancelled)setReports(value);}).catch(e=>setError(messageOf(e)));return()=>{cancelled=true;};},[data?.workspaces[0]?.workspace_id,page]);
  const [researchTarget,setResearchTarget]=useState<SearchResultItem["job"]>();
  const [resumeTarget,setResumeTarget]=useState<SearchResultItem["job"]>();
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
  <section className="main"><header className="topbar"><span>工作空间 / {navItems.find(([, target]) => target === page)?.[0]}</span><span className="pill">本地数据 · {data?.workspaces.length ?? 0} 个工作空间</span><BrowserToggle /></header><div className="content">{error && <div className="error-message banner" role="alert">{userError(error).message} <button onClick={()=>{setError(undefined);setPage("sources");}}>查看来源状态</button><button onClick={()=>setError(undefined)}>关闭提示</button></div>}<div className="discovery-mount" hidden={page !== "discover"}><Discovery active={page === "discover"} onResearch={job=>{setResearchTarget(job);setPage("research");}} data={data} selectedSources={chosenSources} onSelectSource={chooseSource} reports={reports} weights={weights} onWeightsChange={setWeights} onError={setError} /></div><div hidden={page !== "research"}><ResearchPage onReports={setReports} active={page === "research"} data={data} target={researchTarget} onEditResume={job=>{setResumeTarget(job);setPage("resume");}} onBack={()=>setPage("discover")} onError={setError}/></div>{page === "records" && <RecordsPage reports={reports} data={data} onResearch={job=>{setResearchTarget(job);setPage("research");}} onError={setError} />}{page === "resume" && <ResumePage target={resumeTarget} onConfigureModels={()=>setPage("models")} />}{page === "scores" && <MatchingRulesPage workspaceId={data?.workspaces[0]?.workspace_id} weights={weights} onApply={setWeights} />}{page === "sources" && <SourcesPage selected={chosenSources} onSelect={chooseSource} data={data} onRefresh={setData} onError={setError} />}{page === "models" && <ModelsPage onError={setError} />}</div><footer className="footer">本地优先 · 手动投递 · 完全退出后不调度 · {buildInfo.label}</footer></section>
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
  return <><div className="heading-row"><div><h1>已看过</h1><p>回到你认真看过的机会。</p></div><span className="pill">{visibleItems.length} 条岗位</span></div><div className="source-tabs">{[["read","已看过"],["saved","收藏"],["applied","已投递"]].map(([key,label]) => <button key={key} className={filter === key ? "active" : ""} onClick={() => setFilter(key)}>{label}</button>)}</div><div className="job-list section">{visibleItems.length ? visibleItems.map((item) => <article key={item.job.job_id}><div><strong>{item.job.title}</strong><span>{item.job.source.source_name}</span></div><p>{item.job.company} · {item.job.locations.join("/") || "地点未知"}</p><JobActions hasReport={reports.some(r=>reportMatchesJob(r,item.job))} tracking={item.tracking} onTrack={(event,enabled)=>update(item,event,enabled)} onOpen={()=>update(item,"apply_opened")} onResearch={()=>onResearch(item.job)} onError={onError}/></article>) : <div className="empty"><strong>暂无记录</strong><p>打开岗位详情后会保留阅读记录；收藏与投递状态独立保存。</p></div>}</div></>;
}

function SourcesPage({ data, selected, onSelect, onRefresh, onError }: { selected:string[]; onSelect(id:string, selected:boolean):void; data?: BootstrapData; onRefresh(data: BootstrapData): void; onError(message?: string): void }) {
  const [tab, setTab] = useState<"platform" | "company">("platform");
  const [verifying, setVerifying] = useState<string>();
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
  const rows = tab === "platform" ? platforms : companies;
  return <>
    <div className="heading-row"><div><h1>岗位来源</h1><p>多选下次想检索的平台或公司官网，与发现岗位同步。已创建的定时任务不受影响。</p></div></div>
    <p className="source-selection-summary" role="status">已选 {selected.length} 个来源 · 当前可检索 {data?.sources.filter(s=>selected.includes(s.source_id)&&s.live_search_enabled).length??0} 个{!selected.length&&" · 请至少选择一个来源"}</p><div className="source-tabs"><button className={tab === "platform" ? "active" : ""} onClick={() => setTab("platform")}>招聘平台 · {platforms.length}</button><button className={tab === "company" ? "active" : ""} onClick={() => setTab("company")}>公司官网 · {companies.length}</button></div>
    <section className="source-grid source-catalog">{rows.map(source => <article className="panel source-card" key={source.source_id}>
      <div><label className="source-choice"><input type="checkbox" checked={selected.includes(source.source_id)} onChange={e=>onSelect(source.source_id,e.target.checked)} />{source.name}</label><span className={source.live_search_enabled ? "ready" : "muted"}>{source.live_search_enabled ? (source.fields_status!=="verified"||source.pagination_status!=="verified" ? "可检索 · 部分覆盖" : "可检索") : source.login_required && source.session_status!=="verified" ? "需登录 / 检查" : "自动检索待验证"}</span></div>
      <p className="note">登录：{source.session_status === "verified" ? "已确认" : source.session_status === "expired" ? "已过期" : source.session_status === "blocked" ? "需在原页处理" : source.login_required ? "请在原页查看" : "公开浏览无需登录"}</p>
      <div className="button-row"><button onClick={() => openBrowser({sourceId:source.source_id,title:source.name})}>{source.login_required || source.source_id==="liepin" ? "打开 / 登录" : "打开官网"}</button>{(source.source_id!=="boss" || source.session_status==="blocked") && <button disabled={Boolean(verifying)} onClick={() => void verify(source.source_id)}>{verifying === source.source_id ? "检查中…" : source.source_id==="boss" ? "已处理，恢复 BOSS" : "检查检索"}</button>}</div>
      {source.source_type==="company"&&<p className="note">{source.detail}</p>}
      {source.source_id==="boss"&&<p className="note">从此处打开并完成登录，列表可读后自动启用。若在搜索引擎标签中登录，请回到此处使用平台会话。</p>}
    </article>)}</section><p className="note">收起或关闭原页不清除登录信息。应用重启后恢复平台允许持久保存的会话；临时会话或登录过期时需重新登录。应用不记录密码。官网浏览不代表已支持自动检索。</p>
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
