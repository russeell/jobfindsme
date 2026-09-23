import {reportMatchesJob,hasFullDescription} from "../../../shared/research-reports";
import type {ResearchReport} from "../../../shared/contracts";
import {defaultDiscoveryFilters,normalizeDiscoveryFilters,selectedSearchSources} from "../../../shared/discovery-filters";
import {userError} from "../../../shared/user-errors";
import {JobActions} from "./JobActions";
import {useEffect, useMemo,useState,useRef,type FormEvent} from "react";
import type {BootstrapData,SearchFilters,SourceSearchResponse,SearchResultPage,SearchResultItem,MatchingWeights,SourceCollectionProgress,ResumeState} from "../../../shared/contracts";
import {useOriginalBrowser} from "./Workbench";
import {SearchFilters as FilterControls} from "./SearchFilters";
import {TasksPage} from "./TasksPage";
import {sourceBrowserIdForSourceName} from "../../../main/source-browser-policy";
import {createPortal} from "react-dom";
import {formatSalary} from "./salary";

const messageOf = (e:unknown) => e instanceof Error ? e.message : String(e);
const weightLabels:Record<string,string>={skills:"技能",projects:"项目经历",education:"学历",experience:"工作经验",responsibilities:"职责（旧版）",bonus:"加分项（旧版）"};

export function Discovery({ active, data, weights, onWeightsChange, onError, onResearch,onResume,selectedSources,onSelectSource,onSelectAllSources,reports }: {selectedSources:string[];onSelectSource(id:string,selected:boolean):void;onSelectAllSources(selected:boolean):void;reports:ResearchReport[]; active:boolean; data?: BootstrapData; weights: MatchingWeights; onWeightsChange(weights: MatchingWeights): void; onError(message?: string): void; onResearch(job:SearchResultItem["job"]):void;onResume():void }) {
  const sources = useMemo(() => data?.sources ?? [], [data]);
  const enabled = selectedSearchSources(sources,selectedSources);
  const unavailable=sources.filter(s=>selectedSources.includes(s.source_id)&&!s.live_search_enabled);
  const [intent, setIntent] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchError,setSearchError]=useState<ReturnType<typeof userError>>();
  const [collection,setCollection]=useState<SourceCollectionProgress>();
  const [readingDetail,setReadingDetail]=useState(false);
  const [resumeState,setResumeState]=useState<ResumeState>();
  const [detailTimes,setDetailTimes]=useState<Record<string,string>>({});
  useEffect(()=>window.jobfindsme?.onSourceCollectionProgress(setCollection),[]);
  const [reranking,setReranking]=useState(false),[matchingMessage,setMatchingMessage]=useState("");
  const searchEpoch=useRef(0);
  const [result, setResult] = useState<SourceSearchResponse>();
  const [page, setPage] = useState<SearchResultPage>();
  const [pageSize, setPageSize] = useState<10 | 20 | 50>(10);
  const [selected, setSelected] = useState<SearchResultItem>();
  const [mobileView, setMobileView] = useState<"list" | "detail">("list");
  const [filters, setFilters] = useState<SearchFilters>(defaultDiscoveryFilters);
  const [filterKey,setFilterKey]=useState(0);
  const filterEpoch=useRef(0);
  const filterBaseRun=useRef<string|undefined>(undefined);
  async function updateFilters(next:SearchFilters) {
    if(reranking){searchEpoch.current++;setReranking(false);void window.jobfindsme!.cancelMatching();}
    next=normalizeDiscoveryFilters(next);setFilters(next);const epoch=++filterEpoch.current;
    if(!result||!workspaceId||searching)return;
    try {const nextPage=await window.jobfindsme!.refilterSearch(workspaceId,filterBaseRun.current||result.result_page.run_id,next,pageSize);
      if(epoch!==filterEpoch.current)return;setPage(nextPage);setSelected(nextPage.items[0]);setMatchingMessage("已按当前筛选更新本地候选；未重新请求招聘网站。");
    }catch(error){setSearchError(userError(error));}
  }
  function resetFilters(){setFilterKey(key=>key+1);void updateFilters(defaultDiscoveryFilters());}
  const openBrowser = useOriginalBrowser();
  const [showTasks, setShowTasks] = useState(false);
  const scheduleTrigger=useRef<HTMLButtonElement>(null);
  useEffect(()=>{if(!showTasks)return;
    const key=(event:KeyboardEvent)=>{
      if(event.key==="Escape"){event.preventDefault();setShowTasks(false);}
      if(event.key==="Tab") {const nodes=Array.from(document.querySelectorAll<HTMLElement>('.schedule-dialog button:not(:disabled),.schedule-dialog input:not(:disabled),.schedule-dialog select:not(:disabled)')).filter(n=>n.getClientRects().length);
        const first=nodes[0],last=nodes.at(-1);if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}}
    };window.addEventListener("keydown",key);return()=>{window.removeEventListener("keydown",key);scheduleTrigger.current?.focus();};
  },[showTasks]);
  const workspaceId = data?.workspaces[0]?.workspace_id;
  useEffect(()=>{if(!active||!workspaceId)return;let cancelled=false;void window.jobfindsme!.getResumeState().then(value=>{if(!cancelled)setResumeState(value);}).catch(()=>{});return()=>{cancelled=true;};},[active,workspaceId]);
  useEffect(()=>{
    if(!active || !workspaceId)return;let cancelled=false;
    void window.jobfindsme!.listJobTracking(workspaceId).then(rows=>{if(cancelled)return;const byId=new Map(rows.map(row=>[row.job.job_id,row.tracking]));const fresh=(item:SearchResultItem)=>({...item,tracking:byId.get(item.job.job_id) ?? item.tracking});setPage(current=>current && {...current,items:current.items.map(fresh)});setSelected(current=>current && fresh(current));}).catch(error=>onError(messageOf(error)));
    return()=>{cancelled=true;};
  },[active,workspaceId]);
  async function search(event?: FormEvent, cursor?:string) {
    event?.preventDefault();
    if (!workspaceId || !intent.trim()) return;
    if (!enabled.length || (cursor&&!enabled.some(s=>s.source_id==="boss"))) {onError("请先选择至少一个当前可检索的来源。");return;}
    if (filters.salary_min_k != null && filters.salary_max_k != null && filters.salary_min_k > filters.salary_max_k) { onError("最低薪资不能高于最高薪资。"); return; }
    const epoch=++searchEpoch.current;filterEpoch.current++;
    setSearching(true); setSearchError(undefined); setCollection(undefined); setMatchingMessage(""); onError(undefined);
    try {
      const response = await window.jobfindsme!.runSourceSearch({ workspace_id: workspaceId, boss_cursor:cursor, intent: intent.trim(), source_ids: cursor ? ["boss"] : enabled.map((source) => source.source_id), max_pages: 3, time_budget_seconds: 15, filters:normalizeDiscoveryFilters(filters), page_size: pageSize });
      if(epoch!==searchEpoch.current)return;
      filterBaseRun.current=response.result_page.run_id;setResult(response);
      const failed=response.source_runs.filter(run=>run.status!=="success");
      const blocked=Object.values(response.blocked_sources);
      if(failed.length||blocked.length)setSearchError(userError(failed.find(run=>["risk_control","login_required"].includes(run.stop_reason))?.stop_reason || (blocked.length?blocked[0]:failed.length===response.source_runs.length&&!response.result_page.total?"source_contract_error":"partial")));
      if(response.result_page.total || (!failed.length&&!blocked.length)){setPage(response.result_page);setSelected(response.result_page.items[0]);setMobileView("list");}
      const rules=await window.jobfindsme!.matchingRules(workspaceId);
      const rule=rules.versions.find(r=>r.rule_version_id===response.result_page.rule_version_id);
      if(rule?.mode==="model" && response.result_page.resume_version_id && response.result_page.total){
        setReranking(true);setMatchingMessage(`本地结果已就绪；正在按已保存提示词检查前 ${Math.min(rule.candidate_limit,response.result_page.total)} 个候选…`);
        void window.jobfindsme!.rerankMatching(workspaceId,response.result_page.run_id).then(async value=>{
          if(epoch!==searchEpoch.current)return;setMatchingMessage(value.message);
          if(value.status==="complete"&&value.page){const next=await window.jobfindsme!.getSearchPage(workspaceId,value.page.run_id,1,pageSize);if(epoch!==searchEpoch.current)return;filterBaseRun.current=next.run_id;setPage(next);setSelected(next.items[0]);}
        }).catch(e=>{if(epoch===searchEpoch.current)setMatchingMessage(`模型重排未完成，保留本地结果：${messageOf(e)}`);}).finally(()=>{if(epoch===searchEpoch.current)setReranking(false);});
      } else setMatchingMessage(response.result_page.resume_version_id?"本地规则结果；自由提示词未参与评分。":"尚未评分：请先确认简历。");
    } catch (error) { setSearchError(userError(error)); } finally { setSearching(false); }
  }
  async function completeDetail() {
    if(!selected)return;const item=selected;setReadingDetail(true);onError(undefined);
    try {const sourceId=sourceBrowserIdForSourceName(item.job.source.source_name);if(!sourceId)throw Error("来源尚未接入详情读取");const detail=sourceId==="boss"?await window.jobfindsme!.readBossDetail(item.job.apply_url,workspaceId,item.job.job_id):await window.jobfindsme!.readSourceDetail(sourceId,item.job.apply_url,workspaceId,item.job.job_id);
      const updated={...item,job:detail.job||{...item.job,title:detail.title||item.job.title,company:detail.company||item.job.company,locations:detail.location?[detail.location]:item.job.locations,description:detail.description,source:{...item.job.source,detail_level:"detail_page"}}};
      setSelected(current=>current?.job.job_id===item.job.job_id?updated:current);
      setPage(current=>current&&({...current,items:current.items.map(row=>row.job.job_id===item.job.job_id?updated:row)}));
      setDetailTimes(current=>({...current,[item.job.apply_url]:detail.fetched_at}));
    }catch(error){onError(messageOf(error));}finally{setReadingDetail(false);}
  }
  async function changePage(next: number) {
    if (!workspaceId || !page) return;
    try { const value = await window.jobfindsme!.getSearchPage(workspaceId, page.run_id, next, pageSize); setPage(value); setSelected(value.items[0]); } catch (error) { onError(messageOf(error)); }
  }
  async function changePageSize(value: 10 | 20 | 50) {
    setPageSize(value);
    if (!workspaceId || !page) return;
    try { const next = await window.jobfindsme!.getSearchPage(workspaceId, page.run_id, 1, value); setPage(next); setSelected(next.items[0]); } catch (error) { onError(messageOf(error)); }
  }
  async function track(eventType: "read" | "saved" | "applied" | "apply_opened", enabledValue = true) {
    if (!workspaceId || !selected) return;
    const tracking = await window.jobfindsme!.setJobTracking({ workspace_id: workspaceId, job_id: selected.job.job_id, event_type: eventType, enabled: enabledValue });
    const updated = { ...selected, tracking }; setSelected(current=>current?.job.job_id===updated.job.job_id?updated:current);
    setPage((value) => value && ({ ...value, items: value.items.map((item) => item.job.job_id === updated.job.job_id ? updated : item) }));
  }
  async function openOriginal() { if (!selected) return; const sourceId = sourceBrowserIdForSourceName(selected.job.source.source_name) || "web"; try { await track("apply_opened"); openBrowser({ sourceId, url: selected.job.apply_url, title: selected.job.title }); } catch (e) { onError(messageOf(e)); } }
  function selectItem(item:SearchResultItem){
    setSelected(item);setMobileView("detail");
    if(!workspaceId)return;
    void window.jobfindsme!.setJobTracking({workspace_id:workspaceId,job_id:item.job.job_id,event_type:"read",enabled:true}).then(tracking=>{
      setSelected(current=>current?.job.job_id===item.job.job_id?{...current,tracking}:current);
      setPage(current=>current&&({...current,items:current.items.map(row=>row.job.job_id===item.job.job_id?{...row,tracking}:row)}));
    }).catch(error=>onError(messageOf(error)));
  }
  return <div className="discovery-page"><div className="discovery-controls"><div className="heading-row"><div><h1>找工作</h1><p className="discovery-resume-state">{!resumeState?"正在读取简历状态":resumeState.search_profile_state==="ready"?`简历 v${resumeState.current_version_number} 已参与岗位匹配`:resumeState.search_profile_state==="pending_confirmation"?"简历待确认，当前检索不会使用它":"当前未使用简历，可先搜索岗位"} {resumeState&&<button type="button" onClick={onResume}>{resumeState.search_profile_state==="ready"?"维护简历":"设置简历"}</button>}</p></div><button ref={scheduleTrigger} className="quiet-button" onClick={() => setShowTasks(!showTasks)}>◷ 定时检索</button></div>
    <form className="searchbar" onSubmit={(event) => void search(event)}><input aria-label="岗位关键词" placeholder="输入岗位或方向，例如 AI 应用工程师" value={intent} onChange={(event) => setIntent(event.target.value)} /><button className="primary-button" disabled={!intent.trim() || searching || reranking || !workspaceId || enabled.length === 0}>{searching ? "检索中…" : "找岗位"}</button></form>
    <FilterControls key={filterKey} value={filters} onChange={next=>void updateFilters(next)} sources={sources} selectedSources={selectedSources} onSource={onSelectSource} onSelectAllSources={onSelectAllSources} onReset={resetFilters} />
    {!selectedSources.length&&<p className="discovery-next-step" role="status">选择至少一个可检索来源，再输入岗位关键词。<button onClick={()=>window.dispatchEvent(new Event("jfm:show-sources"))}>选择来源</button></p>}
    {!!unavailable.length&&<p className="note source-unavailable">已选但暂不可检索：{unavailable.map(s=>`${s.name}（${s.login_required&&s.session_status!=="verified"?"需登录 / 检查":"能力待验证"}）`).join("、")}。<button onClick={()=>window.dispatchEvent(new Event("jfm:show-sources"))}>查看来源</button></p>}
    {(searchError||collection||matchingMessage) && <div className="discovery-feedback"><details><summary title={searchError?.message||collection?.message||matchingMessage}>{searchError?.message||collection?.message||matchingMessage||"来源状态"}</summary><div className="discovery-feedback-details">
    {searchError&&<div className="notice" role="alert">{searchError.message} <button disabled={searching} onClick={()=>void search()}>重试检索</button><button onClick={()=>window.dispatchEvent(new Event("jfm:show-sources"))}>查看来源状态</button></div>}
    {collection&&<div className="matching-progress" role="status">{collection.message}{searching&&collection.titles?.length ? <p className="note">已读到：{collection.titles.join(" · ")}</p>:null}</div>}
    {matchingMessage&&<p className="matching-progress" role="status">{matchingMessage}{reranking&&<button onClick={()=>void window.jobfindsme!.cancelMatching()}>取消重排</button>}{page?.rerank&&` · 模型评分 ${page.rerank.scored_count}/${page.rerank.total} 条`}</p>}
    {filters.cities&&filters.cities.length>1&&selectedSources.includes("boss")&&<p className="note">BOSS 本次检索首个城市「{filters.cities[0]}」；其他城市请分别检索。其他条件在已采集岗位中筛选。</p>}

    </div></details>{searching&&collection&&<button type="button" onClick={()=>void window.jobfindsme!.cancelSourceSearch()}>停止采集</button>}{!searching&&enabled.some(s=>s.source_id==="boss")&&result?.source_runs.find(run=>run.source_id==="boss"&&run.can_continue)?.next_cursor&&<button type="button" onClick={()=>void search(undefined,result.source_runs.find(run=>run.source_id==="boss")!.next_cursor!)}>继续读取 BOSS 下一批</button>}</div>}
    {showTasks && createPortal(<div className="modal-backdrop" onClick={()=>setShowTasks(false)}><section className="schedule-dialog" role="dialog" aria-modal="true" aria-label="定时检索" onClick={e=>e.stopPropagation()}><button className="dialog-close" autoFocus aria-label="关闭定时检索" onClick={()=>setShowTasks(false)}>×</button><TasksPage data={data} onError={onError} snapshot={{ intent, filters, weights, source_ids: [...selectedSources] }} /></section></div>,document.body)}

    </div><div className="mobile-switch"><button className={mobileView === "list" ? "selected" : ""} onClick={() => setMobileView("list")}>列表</button><button className={mobileView === "detail" ? "selected" : ""} disabled={!selected} onClick={() => setMobileView("detail")}>详情</button></div>
    <div className={`workspace ${selected?"":"no-selection"}`}><section className={`list-pane ${mobileView === "detail" ? "mobile-hidden" : ""}`}>
      <div className="section-title"><strong>岗位结果</strong><span>{page?.total ?? 0} 条</span></div>
      {page?.items.length ? <div className="job-list">{page.items.map(item=><article className={selected?.job.job_id===item.job.job_id?"job-card selected":"job-card"} key={item.job.job_id} role="button" tabIndex={0} aria-pressed={selected?.job.job_id===item.job.job_id} onClick={()=>selectItem(item)} onKeyDown={event=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();selectItem(item);}}}>
        <div><strong>{item.job.title}</strong>{page?.resume_version_id&&<span className="job-score">{item.score.toFixed(0)} 分</span>}</div>
        <p>{item.job.company} · {item.job.locations.join("/")||"地点未知"} · {formatSalary(item.job)}</p>
        <small>{item.job.source.source_name}{item.tracking.saved?" · 已收藏":""}{item.tracking.applied?" · 已投递":""}</small>
      </article>)}</div> : <div className="empty"><strong>{result?"本次没有可展示的岗位":"先输入岗位关键词"}</strong><p>{result?"可调整条件再搜索；来源失败不代表没有岗位。":"选择来源后搜索，结果会显示在这里。"}</p></div>}
      <div className="pagination"><button disabled={!page||page.page<=1} onClick={()=>void changePage((page?.page??1)-1)}>上一页</button><span>{page?.page??0} / {page?.page_count??0}</span><button disabled={!page||page.page>=page.page_count} onClick={()=>void changePage((page?.page??1)+1)}>下一页</button><select value={pageSize} onChange={event=>void changePageSize(Number(event.target.value) as 10|20|50)}><option value="10">10/页</option><option value="20">20/页</option><option value="50">50/页</option></select></div>
    </section>
      <aside className={`detail-pane ${mobileView==="list"?"mobile-detail":""}`}><div className="detail-heading">岗位详情</div>{selected?<div className="job-detail">
        <div className="job-detail-top"><div className="heading-row"><div><h3>{selected.job.title}</h3><p>{selected.job.company} · {selected.job.locations.join("/")||"地点未知"} · {formatSalary(selected.job)}</p><small>{selected.job.source.source_name}</small></div>{page?.resume_version_id&&<span className="pill">匹配 {selected.score.toFixed(0)} 分</span>}</div>
          <JobActions hasReport={reports.some(r=>reportMatchesJob(r,selected.job))} tracking={selected.tracking} onTrack={(event,enabled)=>track(event,enabled)} onOpen={openOriginal} researchDisabledReason={!selected.job.apply_url?"该岗位没有可研究的来源链接":undefined} onResearch={()=>onResearch(selected.job)} onError={onError}/>
        </div>
        {hasFullDescription(selected.job)?<section className="job-jd"><h4>岗位职责</h4><p className="job-description">{selected.job.description}</p></section>:<section className="job-jd"><p className="note">完整岗位职责尚未读取；可查看岗位原页。{sourceBrowserIdForSourceName(selected.job.source.source_name)&&<button type="button" disabled={readingDetail||searching} onClick={()=>void completeDetail()}>{readingDetail?"读取中…":"尝试补全 JD"}</button>}</p></section>}
        {page?.resume_version_id&&<details className="scoring-details"><summary>本地匹配依据 · {selected.scoring_version==="desktop-v2"?"四维规则":"历史规则"}</summary>{Object.entries(selected.components).map(([key,value])=><p key={key}>{weightLabels[key]||key}：{value}分{selected.details?.[key]&&` · ${selected.details[key].explanation}`}</p>)}</details>}
        {selected.model_match&&<details className="model-evidence"><summary>模型匹配依据</summary>{selected.model_match.evidence.map((entry,index)=><p className="note" key={index}>简历：{entry.resume_quote}<br/>JD：{entry.jd_quote}</p>)}<p className="note">未知：{selected.model_match.unknowns.join("；")||"未列出"}</p></details>}
      </div>:<div className="empty"><strong>选择一个岗位</strong><p>从左侧列表查看岗位职责与原页。</p></div>}
      {result && <details className="source-coverage"><summary>来源覆盖与实际检索词</summary><p>{result.keywords.join(" · ")}</p>{result.source_diagnostics&&<p>首个来源读取完成：{result.source_diagnostics.first_source_ms===null?"未读到结果":`${(result.source_diagnostics.first_source_ms/1000).toFixed(1)} 秒`} · 本次开始于 {new Date(result.source_diagnostics.started_at).toLocaleString()}</p>}{sources.map((source) => { const run = result.source_runs.find((item) => item.source_id === source.source_id); return <p key={source.source_id}>{source.name}：{run ? `${run.status==="success"?"已完成":run.status==="partial"?"部分结果":"未完成"} · ${result.source_diagnostics?.sources[source.source_id]?`${(result.source_diagnostics.sources[source.source_id].elapsed_ms/1000).toFixed(1)} 秒 · ${result.source_diagnostics.sources[source.source_id].records} 条候选 · `:""}${run.pages_fetched} ${source.source_id==="boss"?"采集批次":"页"} · ${run.coverage_status==="complete"?"本次范围已读完":"未覆盖全部岗位"} · ${({complete:"已读完",batch_budget:"达到批次上限",record_budget:"达到数量上限",time_budget:"达到时间上限",cancelled:"已停止",no_growth:"暂未发现新增",risk_control:"平台要求验证",login_required:"需要登录",unsupported_city:"该城市编码尚未核验",city_scope:"本次仅检索首个城市"} as Record<string,string>)[run.stop_reason]||"来源暂不可读取"}` : result.blocked_sources[source.source_id] ?? "未执行"}</p>; })}</details>}</aside></div></div>;
}
