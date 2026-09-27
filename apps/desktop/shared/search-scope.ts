import type {SearchResultItem,SearchResultPage,SourceCollectionProgress,SourceSearchResponse,SourceSearchRun} from './contracts';

export function progressBelongsToRun(progress:SourceCollectionProgress,clientRunId:string|undefined,workspaceId:string|undefined):boolean{
  return !!clientRunId&&!!workspaceId&&progress.client_run_id===clientRunId&&progress.workspace_id===workspaceId;
}

export function sourceRunNeedsAttention(run:SourceSearchRun):boolean{
  return run.status==='failed'||['risk_control','login_required','source_contract_error','save_failed','browser_session_error','cancelled','time_budget'].includes(run.stop_reason);
}

export function keepVisibleSearchPage(previous:SearchResultPage|undefined,next:SearchResultPage):SearchResultPage{
  return previous?.run_id===next.run_id&&previous.page>1
    ?{...previous,total:next.total,page_count:next.page_count}:next;
}

export function keepSelectedSearchJob(previous:SearchResultItem|undefined,shownRunId:string|undefined,next:SearchResultPage):SearchResultItem|undefined{
  return shownRunId===next.run_id&&previous?previous:next.items[0];
}

export function unstartedSourceIds(response:SourceSearchResponse):string[]{
  const executed=new Set(response.executed_queries?.map(query=>query.source_id)||[]);
  return [...new Set(response.planned_queries?.map(query=>query.source_id)||[])].filter(id=>!executed.has(id)&&!Object.hasOwn(response.blocked_sources,id));
}

export function mergeSearchCoverage(previous:SourceSearchResponse|undefined,next:SourceSearchResponse):SourceSearchResponse{
  if(!previous||previous.result_page.run_id!==next.result_page.run_id)return next;
  const unique=<T extends {source_id:string}>(items:T[])=>[...new Map(items.map(item=>[item.source_id,item])).values()];
  const blocked={...previous.blocked_sources};
  for(const id of next.allowed_source_ids||[])delete blocked[id];
  return {...next,
    source_runs:unique([...previous.source_runs,...next.source_runs]),
    planned_queries:unique([...(previous.planned_queries||[]),...(next.planned_queries||[])]),
    executed_queries:unique([...(previous.executed_queries||[]),...(next.executed_queries||[])]),
    blocked_sources:{...blocked,...next.blocked_sources},
    source_diagnostics:next.source_diagnostics?{...next.source_diagnostics,sources:{...previous.source_diagnostics?.sources,...next.source_diagnostics.sources}}:previous.source_diagnostics,
  };
}
