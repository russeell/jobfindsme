import {reportMatchesJob,hasFullDescription} from "../../../shared/research-reports";
import type {ResearchReport} from "../../../shared/contracts";
import {defaultDiscoveryFilters,normalizeDiscoveryFilters,selectedSearchSources,selectedAttemptableSources} from "../../../shared/discovery-filters";
import {userError} from "../../../shared/user-errors";
import {JobActions} from "./JobActions";
import {useEffect, useMemo,useState,useRef,type FormEvent} from "react";
import type {BootstrapData,SearchFilters,SourceSearchResponse,SearchResultPage,SearchResultItem,SourceCollectionProgress,ResumeState} from "../../../shared/contracts";
import {useOriginalBrowser} from "../shared/Workbench";
import {SearchFilters as FilterControls} from "./SearchFilters";
import {sourceBrowserIdForSourceName} from "../../../shared/source-browser-policy";
import {formatSalary} from "./salary";
import {ResumePage} from "../resume/ResumePage";
import {remoteSearchScopeChanged,searchPageForCurrentFilters,mergeSearchCoverage,unstartedSourceIds,keepVisibleSearchPage,keepSelectedSearchJob,sourceRunNeedsAttention,progressBelongsToRun} from "../../../shared/search-scope";

const messageOf = (e:unknown) => e instanceof Error ? e.message : String(e);
const blockedReason=(value:string)=>/login|登录/i.test(value)?"需登录后重试":/risk|captcha|验证/i.test(value)?"需完成网站验证":"暂不可检索，请到岗位来源检查";
const runReason=(value:string)=>/^invalid_cards:\d+$/.test(value)?`已跳过 ${value.split(":")[1]} 张异常或不属于本次搜索的卡片，正常岗位已保留`:({complete:"本次范围已读完",time_budget:"本轮时间已用完",cancelled:"已停止",page_budget:"可继续读取",batch_budget:"可继续读取",record_budget:"可继续读取",no_growth:"暂无新增",risk_control:"需完成网站验证",login_required:"需重新登录",save_failed:"保存失败",browser_session_error:"浏览器读取失败，可重试",source_contract_error:"读取未完成",unsupported_city:"该城市编码尚未核验",city_scope:"本次仅检索首个城市"} as Record<string,string>)[value]||"读取未完成，可检查来源";

export function Discovery({ active, data, onError, onResearch,selectedSources,onSelectSource,onSelectAllSources,reports,suggestedIntent }: {selectedSources:string[];onSelectSource(id:string,selected:boolean):void;onSelectAllSources(selected:boolean):void;reports:ResearchReport[];suggestedIntent?:{query:string;nonce:number}; active:boolean; data?: BootstrapData; onError(message?: string): void; onResearch(job:SearchResultItem["job"]):void }) {
  const sources = useMemo(() => data?.sources ?? [], [data]);
  const workspaceId = data?.workspaces[0]?.workspace_id;
  const enabled = selectedSearchSources(sources,selectedSources);
  const attemptable = selectedAttemptableSources(sources,selectedSources);
  const unavailable=sources.filter(s=>selectedSources.includes(s.source_id)&&!s.live_search_enabled);
  const [intent, setIntent] = useState("");
  useEffect(()=>{if(suggestedIntent)setIntent(suggestedIntent.query);},[suggestedIntent?.nonce]);
  const [searching, setSearching] = useState(false);
  const [showingPrevious,setShowingPrevious]=useState(false);
  const [searchError,setSearchError]=useState<ReturnType<typeof userError>>();
  const [collection,setCollection]=useState<SourceCollectionProgress>();
  const [processedSourceIds,setProcessedSourceIds]=useState<string[]>([]);
  const [currentFound,setCurrentFound]=useState(0);
  const statusMenuRef=useRef<HTMLDetailsElement>(null);
  const continueMenuRef=useRef<HTMLDetailsElement>(null);
  const closeSearchMenus=()=>{statusMenuRef.current?.removeAttribute("open");continueMenuRef.current?.removeAttribute("open");};
  useEffect(()=>{const outside=(event:PointerEvent)=>{if(!statusMenuRef.current?.contains(event.target as Node))statusMenuRef.current?.removeAttribute("open");if(!continueMenuRef.current?.contains(event.target as Node))continueMenuRef.current?.removeAttribute("open");};const escape=(event:KeyboardEvent)=>{if(event.key==="Escape")closeSearchMenus();};document.addEventListener("pointerdown",outside);document.addEventListener("keydown",escape);return()=>{document.removeEventListener("pointerdown",outside);document.removeEventListener("keydown",escape);};},[]);
  const [resultRequest,setResultRequest]=useState<{sourceIds:string[];intent:string;filters:SearchFilters}>();
  const activeRequest=useRef<{sourceIds:string[];intent:string;filters:SearchFilters}|undefined>(undefined);
  const [readingDetail,setReadingDetail]=useState(false);
  const [resumeState,setResumeState]=useState<ResumeState>();
  const [resumeOpen,setResumeOpen]=useState(false);
  const resumeTrigger=useRef<HTMLButtonElement>(null);
  const resumeClose=useRef<HTMLButtonElement>(null);
  const resumeDialog=useRef<HTMLDivElement>(null);
  function closeResume(){setResumeOpen(false);resumeTrigger.current?.focus();}
  useEffect(()=>{if(!active)setResumeOpen(false);},[active]);
  useEffect(()=>{if(!resumeOpen||!active)return;resumeClose.current?.focus();const onKey=(event:KeyboardEvent)=>{
    if(event.key==="Escape"){event.preventDefault();closeResume();return;}
    if(event.key!=="Tab"||!resumeDialog.current)return;
    const focusable=Array.from(resumeDialog.current.querySelectorAll<HTMLElement>("button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),a[href],summary")).filter(element=>element.getClientRects().length>0);
    if(!focusable.length)return;
    const first=focusable[0],last=focusable[focusable.length-1];
    if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
    else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
  };window.addEventListener("keydown",onKey);return()=>window.removeEventListener("keydown",onKey);},[resumeOpen,active]);
  const [detailTimes,setDetailTimes]=useState<Record<string,string>>({});
  const activeClientRun=useRef<string|undefined>(undefined);
  const activeResultRun=useRef<string|undefined>(undefined);
  const displayedRun=useRef<string|undefined>(undefined);
  const preserveSelection=useRef(false);
  useEffect(()=>window.jobfindsme?.onSourceCollectionProgress(progress=>{
    if(!progressBelongsToRun(progress,activeClientRun.current,workspaceId))return;
    setCollection(progress);
    if(!progress.response)return;
    const batch=progress.response;
    setCurrentFound(batch.result_page.total);
    if(progress.source_id)setProcessedSourceIds(previous=>previous.includes(progress.source_id!)?previous:[...previous,progress.source_id!]);
    if(!batch.result_page.total&&!preserveSelection.current)return;
    const sameRun=activeResultRun.current===batch.result_page.run_id;
    activeResultRun.current=batch.result_page.run_id;
    setResult(previous=>preserveSelection.current||sameRun?mergeSearchCoverage(previous,batch):batch);
    if(!batch.result_page.total)return;
    const sameDisplayedRun=displayedRun.current===batch.result_page.run_id;
    displayedRun.current=batch.result_page.run_id;
    if(activeRequest.current&&!preserveSelection.current)setResultRequest(activeRequest.current);
    setShowingPrevious(false);
    void displaySearchPage(batch.result_page,activeRequest.current?.filters||defaultDiscoveryFilters(),sameDisplayedRun?batch.result_page.run_id:undefined).catch(error=>setSearchError(userError(error)));
  }),[workspaceId]);
  const [matchingMessage,setMatchingMessage]=useState("");
  const searchEpoch=useRef(0);
  const [result, setResult] = useState<SourceSearchResponse>();
  const [latestAttempt,setLatestAttempt]=useState<SourceSearchResponse>();
  const feedbackResult=showingPrevious?latestAttempt:result;
  const [page, setPage] = useState<SearchResultPage>();
  const [pageSize, setPageSize] = useState<10 | 20 | 50>(10);
  const [selected, setSelected] = useState<SearchResultItem>();
  const [mobileView, setMobileView] = useState<"list" | "detail">("list");
  const [filters, setFilters] = useState<SearchFilters>(defaultDiscoveryFilters);
  const filtersRef=useRef(filters);filtersRef.current=filters;
  const pageSizeRef=useRef(pageSize);pageSizeRef.current=pageSize;
  const pendingSources=result?unstartedSourceIds(result):[];
  const coveredSources=resultRequest?.sourceIds||[];
  const selectionChanged=!!resultRequest&&([...selectedSources].sort().join('|')!==[...coveredSources].sort().join('|'));
  const continueRuns=result?.source_runs.filter(run=>run.can_continue&&run.next_cursor)||[];
  const canExpand=!!result&&sources.some(source=>source.live_search_enabled&&!coveredSources.includes(source.source_id));
  const issueCount=result?(result.batch_failures?.length||0)+result.source_runs.filter(sourceRunNeedsAttention).length:0;
  const statusText=searching?`正在查找 · 已找到 ${currentFound} 条岗位，已处理 ${processedSourceIds.length} 个来源`:showingPrevious?`本次未完成 · 保留上次找到的 ${page?.total??0} 条岗位`:result?`已找到 ${page?.total??0} 条岗位 · ${result.executed_queries?.length||0} 个来源已检索${Object.keys(result.blocked_sources).length?` · ${Object.keys(result.blocked_sources).length} 个需处理`:""}${pendingSources.length?` · ${pendingSources.length} 个未轮到`:""}${issueCount?" · 部分读取失败":""}${selectionChanged?" · 勾选变更下次生效":""}`:searchError?"本次未完成，已保留上次结果":selectedSources.length?`已选 ${selectedSources.length} 个来源 · ${enabled.length} 个可尝试检索${attemptable.length-enabled.length?` · ${attemptable.length-enabled.length} 个本次可尝试验证`:""}${selectedSources.length-attemptable.length?` · ${selectedSources.length-attemptable.length} 个需处理`:""}`:"请选择岗位来源";
  const [filterKey,setFilterKey]=useState(0);
  const filterEpoch=useRef(0);
  const filterBaseRun=useRef<string|undefined>(undefined);
  async function displaySearchPage(incoming:SearchResultPage,originalFilters:SearchFilters,shownRunId:string|undefined){
    if(!workspaceId)return;
    filterBaseRun.current=incoming.run_id;
    const epoch=++filterEpoch.current;
    const next=await searchPageForCurrentFilters(incoming,originalFilters,filtersRef.current,pageSizeRef.current,(runId,current,size)=>window.jobfindsme!.refilterSearch(workspaceId,runId,current,size));
    if(epoch!==filterEpoch.current)return;
    setPage(previous=>keepVisibleSearchPage(previous,next));
    setSelected(previous=>keepSelectedSearchJob(previous,shownRunId,next));
  }
  async function updateFilters(next:SearchFilters) {
    next=normalizeDiscoveryFilters(next);filtersRef.current=next;setFilters(next);const epoch=++filterEpoch.current;
    if(!result||!workspaceId)return;
    try {const nextPage=await window.jobfindsme!.refilterSearch(workspaceId,filterBaseRun.current||result.result_page.run_id,next,pageSize);
      if(epoch!==filterEpoch.current)return;setPage(nextPage);setSelected(nextPage.items[0]);setMatchingMessage(resultRequest&&remoteSearchScopeChanged(intent,next,resultRequest.intent,resultRequest.filters)?"已筛选本地候选；关键词或城市已改变，请点击找岗位开始新搜索。":"已按当前筛选更新本地候选；未重新请求招聘网站。");
    }catch(error){setSearchError(userError(error));}
  }
  function resetFilters(){setFilterKey(key=>key+1);void updateFilters(defaultDiscoveryFilters());}
  const openBrowser = useOriginalBrowser();
  useEffect(()=>{if(!active||!workspaceId)return;let cancelled=false;
    void window.jobfindsme!.getResumeState().then(resume=>{if(!cancelled)setResumeState(resume);}).catch(()=>{});
    return()=>{cancelled=true;};},[active,workspaceId]);
  useEffect(()=>{
    if(!active || !workspaceId)return;let cancelled=false;
    void window.jobfindsme!.listJobTracking(workspaceId).then(rows=>{if(cancelled)return;const byId=new Map(rows.map(row=>[row.job.job_id,row.tracking]));const fresh=(item:SearchResultItem)=>({...item,tracking:byId.get(item.job.job_id) ?? item.tracking});setPage(current=>current && {...current,items:current.items.map(fresh)});setSelected(current=>current && fresh(current));}).catch(error=>onError(messageOf(error)));
    return()=>{cancelled=true;};
  },[active,workspaceId]);
  async function search(event?: FormEvent, continuation?:{sourceId:string;cursor:string}, expand=false, useResume=false, pending=false) {
    event?.preventDefault();
    if (!workspaceId) return;
    const preserve=!!(continuation||expand||pending)&&!!result;
    if(preserve&&resultRequest&&remoteSearchScopeChanged(intent,filtersRef.current,resultRequest.intent,resultRequest.filters)){onError("关键词或城市已改变，请点击找岗位开始新搜索。");return;}
    if(useResume&&!preserve)setIntent("");
    const requestIntent=preserve?resultRequest?.intent??intent.trim():useResume?"":intent.trim();
    const requestFilters=preserve?resultRequest?.filters??normalizeDiscoveryFilters(filters):normalizeDiscoveryFilters(filters);
    if (!preserve&&!requestIntent && resumeState?.search_profile_state!=="ready") {onError("请输入岗位关键词，或先确认一份简历。");return;}
    if (!preserve&&!attemptable.length) {onError("请先选择至少一个可检索或可尝试验证的来源。");return;}
    if (requestFilters.salary_min_k != null && requestFilters.salary_max_k != null && requestFilters.salary_min_k > requestFilters.salary_max_k) { onError("最低薪资不能高于最高薪资。"); return; }
    const additional=sources.filter(source=>source.live_search_enabled&&!coveredSources.includes(source.source_id)).slice(0,2);
    const sourceIds=continuation?[continuation.sourceId]:pending&&result?unstartedSourceIds(result):expand?additional.map(source=>source.source_id):selectedSources;
    if(!sourceIds.length){onError("没有更多当前可检索的来源。");return;}
    activeRequest.current=preserve?{sourceIds:expand?[...(resultRequest?.sourceIds||[]),...sourceIds]:resultRequest?.sourceIds||sourceIds,intent:requestIntent,filters:requestFilters}:{sourceIds:[...sourceIds],intent:requestIntent,filters:requestFilters};
    preserveSelection.current=preserve;
    const epoch=++searchEpoch.current;filterEpoch.current++;
    const clientRunId=crypto.randomUUID();activeClientRun.current=clientRunId;
    closeSearchMenus();
    if(!preserve){activeResultRun.current=undefined;displayedRun.current=undefined;filterBaseRun.current=undefined;setMobileView("list");}
    setShowingPrevious(!preserve&&!!page?.items.length);
    setLatestAttempt(undefined);setSearching(true); setSearchError(undefined); setCollection(undefined);setProcessedSourceIds([]);setCurrentFound(0); setMatchingMessage(""); onError(undefined);
    try {
      const response = await window.jobfindsme!.runSourceSearch({ workspace_id: workspaceId,client_run_id:clientRunId,
        existing_run_id:preserve?result?.result_page.run_id:undefined,
        boss_cursor:continuation?.sourceId==="boss"?continuation.cursor:undefined,
        source_cursor:continuation?.sourceId!=="boss"?continuation?.cursor:undefined,
        intent:requestIntent, source_ids:sourceIds, max_pages:1, time_budget_seconds:15,
        filters:requestFilters, page_size: pageSize });
      if(epoch!==searchEpoch.current)return;
      setLatestAttempt(response);
      const failed=response.source_runs.filter(sourceRunNeedsAttention);
      const blocked=Object.values(response.blocked_sources);
      const keepPrevious=!preserve&&!response.result_page.total&&!!page?.items.length&&!!(failed.length||blocked.length);
      if(!keepPrevious){filterBaseRun.current=response.result_page.run_id;setResult(previous=>preserve?mergeSearchCoverage(previous,response):response);if(!preserve||expand)setResultRequest(activeRequest.current);}
      if(failed.length||blocked.length||response.batch_failures?.length){
        const base=userError(failed.find(run=>["risk_control","login_required"].includes(run.stop_reason))?.stop_reason || (blocked.length?blocked[0]:failed.length===response.source_runs.length&&!response.result_page.total?(failed[0]?.error||"source_contract_error") :"partial"));
        const batchNotice=response.batch_failures?.map(item=>`${sources.find(source=>source.source_id===item.source_id)?.name||item.source_id}${item.stage==="save"?"的读取结果保存失败":"的来源状态更新失败"}`).join("；");
        setSearchError(batchNotice?{...base,message:`${batchNotice}。已保存的岗位会保留。`}:base);
      }
      if(response.result_page.total || (!failed.length&&!blocked.length)){setShowingPrevious(false);await displaySearchPage(response.result_page,requestFilters,displayedRun.current);}
      if(epoch!==searchEpoch.current)return;
      setMatchingMessage(response.executed_queries?.length?`已检索：${response.keywords[0]}。远端仅使用首个城市与所列来源；薪资等其余筛选在本地进行。请核对岗位原文。`:`已计划检索「${response.keywords[0]}」，但本次没有完成来源请求。请查看来源状态。`);
      setCollection(undefined);
    } catch (error) { if(epoch===searchEpoch.current)setSearchError(userError(error)); } finally { if(epoch===searchEpoch.current){closeSearchMenus();setSearching(false);} }
  }
  async function completeDetail() {
    if(!selected)return;const item=selected;setReadingDetail(true);onError(undefined);
    try {const sourceId=sourceBrowserIdForSourceName(item.job.source.source_name);if(!sourceId)throw Error("来源尚未接入详情读取");const detail=sourceId==="boss"?await window.jobfindsme!.readBossDetail(item.job.apply_url,workspaceId,item.job.job_id):await window.jobfindsme!.readSourceDetail(sourceId,item.job.apply_url,workspaceId,item.job.job_id);
      const updated:SearchResultItem={...item,job:detail.job||{...item.job,title:detail.title||item.job.title,company:detail.company||item.job.company,locations:detail.location?[detail.location]:item.job.locations,description:detail.description,source:{...item.job.source,detail_level:"detail_page"}},score:null,details:undefined,components:{},model_match:undefined,score_basis_outdated:true};
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
  return <div className={`discovery-page${result||page||searching||searchError||collection?" has-results":""}`}><div className="discovery-controls"><div className="heading-row"><div><h1>{result||page||searching?"找工作":"想找什么样的工作？"}</h1><p className="discovery-resume-state">{!resumeState?"正在读取简历状态":resumeState.search_profile_state==="ready"?"已确认简历参与匹配":resumeState.search_profile_state==="pending_confirmation"?"简历待确认，当前检索不会使用它":"输入岗位方向即可开始；也可以先导入简历。"}</p></div><button ref={resumeTrigger} type="button" className="discovery-resume-button" onClick={()=>setResumeOpen(true)}>{resumeState?.search_profile_state==="ready"?"查看简历":resumeState?.search_profile_state==="pending_confirmation"?"核对简历":"导入简历"}</button></div>
    <form className="searchbar" onSubmit={(event) => void search(event)}><input aria-label="岗位关键词" placeholder="输入岗位方向，例如 AI 工程师" value={intent} onChange={(event) => setIntent(event.target.value)} />{(result||page||searching)&&<button type="button" className="discovery-resume-button compact" onClick={()=>setResumeOpen(true)}>{resumeState?.search_profile_state==="ready"?"查看简历":resumeState?.search_profile_state==="pending_confirmation"?"核对简历":"导入简历"}</button>}<button className="primary-button" disabled={searching || !workspaceId || attemptable.length === 0 || (!intent.trim() && resumeState?.search_profile_state!=="ready")}>{searching ? "检索中…" : "找岗位"}</button></form>
    {resumeState?.search_profile_state==="ready"&&<div className="resume-search-action"><button type="button" className="primary-button" disabled={searching||!workspaceId||attemptable.length===0} onClick={()=>void search(undefined,undefined,false,true)}>按我的简历找岗位</button><span>使用已确认简历中的技能词检索，并在本地匹配。</span></div>}
    <FilterControls key={filterKey} value={filters} onChange={next=>void updateFilters(next)} sources={sources} selectedSources={selectedSources} onSource={onSelectSource} onSelectAllSources={onSelectAllSources} onReset={resetFilters} />
    <div className="search-status-line" role="status"><span title={statusText}>{statusText}</span><details ref={statusMenuRef} className="search-status-menu"><summary>来源详情</summary><div className="search-menu-content">
      <p>{searching?`本轮请求 ${activeRequest.current?.sourceIds.length||0} 个来源；岗位在每个来源保存后加入结果。`:resultRequest?`${showingPrevious?"保留的上次结果":"结果"}对应「${resultRequest.intent||"简历关键词"}」和当时选择的 ${coveredSources.length} 个来源。`:"勾选会在下次检索时使用。"}</p>
      {searchError&&<p className="search-menu-warning">{searchError.message} 已保存的岗位保留。</p>}
      {matchingMessage&&<p>{matchingMessage}</p>}
      {!searching&&feedbackResult?.source_runs.map(run=><p key={run.source_id}>{sources.find(source=>source.source_id===run.source_id)?.name||run.source_id}：{run.status==="success"?"已读取":run.status==="partial"?"部分岗位已读取":"本次未完成"} · {run.error?userError(run.error).message:runReason(run.stop_reason)}</p>)}
      {!searching&&feedbackResult&&Object.entries(feedbackResult.blocked_sources).map(([id,reason])=><p key={id}>{sources.find(source=>source.source_id===id)?.name||id}：{blockedReason(reason)}</p>)}
      {!result&&unavailable.map(source=><p key={source.source_id}>{source.name}：{attemptable.some(item=>item.source_id===source.source_id)?"输入关键词即可尝试搜索，无需先检查":"请在原页完成平台验证后重试"}</p>)}
      <button type="button" onClick={()=>window.dispatchEvent(new Event("jfm:show-sources"))}>管理岗位来源</button>
    </div></details>
    {searching?<button type="button" onClick={()=>void window.jobfindsme!.cancelSourceSearch()}>停止</button>:result&&(pendingSources.length||continueRuns.length||canExpand)?<details ref={continueMenuRef} className="search-status-menu continue-menu"><summary>继续查找</summary><div className="search-menu-content"><p>关键词或城市改变后须重新搜索；续查保留岗位并应用当前本地筛选。</p>{pendingSources.length>0&&<button type="button" onClick={()=>void search(undefined,undefined,false,false,true)}>检索未轮到的 {pendingSources.length} 个来源</button>}{continueRuns.map(run=><button key={run.source_id} type="button" onClick={()=>void search(undefined,{sourceId:run.source_id,cursor:run.next_cursor!})}>读取 {sources.find(source=>source.source_id===run.source_id)?.name||run.source_id}下一页</button>)}{canExpand&&<button type="button" onClick={()=>void search(undefined,undefined,true)}>扩大到其他来源（每次最多 2 个）</button>}</div></details>:null}
    </div>

    </div><div className="mobile-switch"><button className={mobileView === "list" ? "selected" : ""} onClick={() => setMobileView("list")}>列表</button><button className={mobileView === "detail" ? "selected" : ""} disabled={!selected} onClick={() => setMobileView("detail")}>详情</button></div>
    <div className={`workspace ${selected?"":"no-selection"}`}><section className={`list-pane ${mobileView === "detail" ? "mobile-hidden" : ""}`}>
      <div className="section-title"><strong>岗位结果{showingPrevious?" · 上次成功结果":selectionChanged?" · 与当前勾选不同":""}</strong><span>{page?.total ?? 0} 条</span></div>
      {page?.items.length ? <div className="job-list">{page.items.map(item=><article className={selected?.job.job_id===item.job.job_id?"job-card selected":"job-card"} key={item.job.job_id} role="button" tabIndex={0} aria-pressed={selected?.job.job_id===item.job.job_id} onClick={()=>selectItem(item)} onKeyDown={event=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();selectItem(item);}}}>
        <div><strong>{item.job.title}</strong></div>
        <p>{item.job.company} · {item.job.locations.join("/")||"地点未知"} · {formatSalary(item.job)}</p>
        <small>{item.job.source.source_name} · 发布：{item.job.source.published_at?new Date(item.job.source.published_at).toLocaleDateString():"未知"}{item.tracking.saved?" · 已收藏":""}{item.tracking.applied?" · 已投递":""}{item.snapshot_status==="unknown"?" · 历史内容版本未知，旧评分不可用":""}</small>
      </article>)}</div> : <div className="empty" role="status"><strong>{searching?"正在检索岗位":searchError?"本次检索未完成":result?"本次没有可展示的岗位":resumeState?.search_profile_state==="ready"?"可按已确认简历搜索":"先输入岗位关键词"}</strong><p>{searching?"请稍候，来源读取情况会显示在上方。":searchError?"请查看上方错误并重试；本次失败不能视为没有岗位。":result?"可调整条件再搜索；来源失败不代表没有岗位。":"选择来源后搜索，结果会显示在这里。"}</p></div>}
      <div className="pagination"><button disabled={!page||page.page<=1} onClick={()=>void changePage((page?.page??1)-1)}>上一页</button><span>{page?.page??0} / {page?.page_count??0}</span><button disabled={!page||page.page>=page.page_count} onClick={()=>void changePage((page?.page??1)+1)}>下一页</button><select value={pageSize} onChange={event=>void changePageSize(Number(event.target.value) as 10|20|50)}><option value="10">10/页</option><option value="20">20/页</option><option value="50">50/页</option></select></div>
    </section>
      <aside className={`detail-pane ${mobileView==="list"?"mobile-detail":""}`}><div className="detail-heading">岗位详情</div>{selected?<div className="job-detail">
        <div className="job-detail-top"><div className="heading-row"><div><h3>{selected.job.title}</h3><p>{selected.job.company} · {selected.job.locations.join("/")||"地点未知"} · {formatSalary(selected.job)}</p><small>{selected.job.source.source_name} · 发布：{selected.job.source.published_at?new Date(selected.job.source.published_at).toLocaleDateString():"未知"}</small>{selected.snapshot_status==="unknown"&&<p className="note">这次历史检索的岗位版本无法恢复；下方为当前岗位内容，旧评分和重排不可用。</p>}{selected.score_basis_outdated&&<p className="note">JD 已补充；搜索时的旧评分依据仍保留在原快照，此处不再显示为新 JD 的评分。</p>}</div></div>
          <JobActions hasReport={reports.some(r=>reportMatchesJob(r,selected.job))} tracking={selected.tracking} onTrack={(event,enabled)=>track(event,enabled)} onOpen={openOriginal} researchDisabledReason={!selected.job.apply_url?"该岗位没有可研究的来源链接":undefined} onResearch={()=>onResearch(selected.job)} onError={onError}/>
        </div>
        {hasFullDescription(selected.job)?<section className="job-jd"><h4>岗位职责</h4><p className="job-description">{selected.job.description}</p></section>:<section className="job-jd"><p className="note">完整岗位职责尚未读取；可查看岗位原页。{sourceBrowserIdForSourceName(selected.job.source.source_name)&&<button type="button" disabled={readingDetail||searching} onClick={()=>void completeDetail()}>{readingDetail?"读取中…":"尝试补全 JD"}</button>}</p></section>}
        {page?.resume_version_id&&<details className="scoring-details"><summary>岗位与简历的对应线索</summary><p className="note">依据岗位描述和已确认简历；请核对原文，未知条件不视为满足。</p>{Object.entries(selected.details||{}).map(([key,value])=><p key={key}>{({skills:"技能",projects:"项目经历",education:"学历",experience:"工作经验"} as Record<string,string>)[key]||key}：{value.explanation.replaceAll("暂不计分","仍需核对").replace("，按达成比例计分","")}</p>)}</details>}
        {selected.model_match&&<details className="model-evidence"><summary>历史模型分析记录</summary>{selected.model_match.evidence.map((entry,index)=><p className="note" key={index}>简历：{entry.resume_quote}<br/>JD：{entry.jd_quote}</p>)}<p className="note">未知：{selected.model_match.unknowns.join("；")||"未列出"}</p></details>}
      </div>:<div className="empty"><strong>选择一个岗位</strong><p>从左侧列表查看岗位职责与原页。</p></div>}
      {result && <details className="source-coverage"><summary>来源覆盖与实际检索词</summary><p>计划：{(result.planned_queries||[]).map(query=>`${sources.find(s=>s.source_id===query.source_id)?.name||query.source_id} / ${query.keyword} / ${query.city||"城市不限"}`).join("；")||result.keywords.join(" · ")}</p><p>已检索：{(result.executed_queries||[]).map(query=>`${sources.find(s=>s.source_id===query.source_id)?.name||query.source_id} / ${query.keyword} / ${query.city||"城市不限"}`).join("；")||"无"}。薪资与其他条件在本地筛选。</p>{result.source_diagnostics&&<p>首批可用岗位：{result.source_diagnostics.first_usable_ms==null?"尚无":`${(result.source_diagnostics.first_usable_ms/1000).toFixed(1)} 秒`} · 本次开始于 {new Date(result.source_diagnostics.started_at).toLocaleString()}</p>}{sources.map((source) => { const run = result.source_runs.find((item) => item.source_id === source.source_id); return <p key={source.source_id}>{source.name}：{run ? `${run.status==="success"?"已完成":run.status==="partial"?"部分结果":"未完成"} · ${result.source_diagnostics?.sources[source.source_id]?`${(result.source_diagnostics.sources[source.source_id].elapsed_ms/1000).toFixed(1)} 秒 · ${result.source_diagnostics.sources[source.source_id].records} 条候选 · `:""}${run.pages_fetched} ${source.source_id==="boss"?"采集批次":"页"} · ${run.coverage_status==="complete"?"本次范围已读完":"未覆盖全部岗位"} · ${runReason(run.stop_reason)}` : result.blocked_sources[source.source_id] ?? "未执行"}</p>; })}</details>}</aside></div>
    {active&&resumeOpen&&<div className="resume-modal-backdrop" data-browser-overlay="modal" onMouseDown={event=>{if(event.target===event.currentTarget)closeResume();}}><div ref={resumeDialog} className="resume-modal" role="dialog" aria-modal="true" aria-label="简历维护"><header className="resume-modal-header"><strong>简历维护</strong><button ref={resumeClose} type="button" onClick={closeResume} aria-label="关闭简历维护">关闭 ×</button></header><ResumePage onChanged={setResumeState}/></div></div>}
    </div>;
}
