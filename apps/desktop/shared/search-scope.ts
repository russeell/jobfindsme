import {normalizeDiscoveryFilters} from "./discovery-filters.js";
import type {SearchFilters,SearchResultItem,SearchResultPage,SourceCollectionProgress,SourceSearchResponse,SourceSearchRun} from './contracts';

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
    planned_queries:[...new Map([...(previous.planned_queries||[]),...(next.planned_queries||[])].map(query=>[JSON.stringify(query),query])).values()],
    executed_queries:[...new Map([...(previous.executed_queries||[]),...(next.executed_queries||[])].map(query=>[JSON.stringify(query),query])).values()],
    blocked_sources:{...blocked,...next.blocked_sources},
    source_diagnostics:next.source_diagnostics?{...next.source_diagnostics,sources:{...previous.source_diagnostics?.sources,...next.source_diagnostics.sources}}:previous.source_diagnostics,
  };
}

export function remoteSearchScopeChanged(intent:string,filters:SearchFilters,originalIntent:string,originalFilters:SearchFilters):boolean{
  return intent.trim()!==originalIntent.trim()||JSON.stringify(filters.cities||[])!==JSON.stringify(originalFilters.cities||[]);
}
export async function searchPageForCurrentFilters(page:SearchResultPage,originalFilters:SearchFilters,currentFilters:SearchFilters,pageSize:number,refilter:(runId:string,filters:SearchFilters,pageSize:number)=>Promise<SearchResultPage>):Promise<SearchResultPage>{
  const current=normalizeDiscoveryFilters(currentFilters);
  return JSON.stringify(normalizeDiscoveryFilters(originalFilters))===JSON.stringify(current)?page:refilter(page.run_id,current,pageSize);
}

export function selectedSourceContinuation(response:SourceSearchResponse,selectedIds:string[],coveredIds:string[]):{sourceIds:string[];cursors:Record<string,string>;unavailableIds:string[]}{
  const unstarted=new Set(unstartedSourceIds(response)),covered=new Set(coveredIds);
  const runs=new Map(response.source_runs.map(run=>[run.source_id,run]));
  const sourceIds:string[]=[],cursors:Record<string,string>={},unavailableIds:string[]=[];
  for(const id of [...new Set(selectedIds)]){
    const run=runs.get(id);
    if(!covered.has(id)||unstarted.has(id))sourceIds.push(id);
    else if(run?.can_continue&&run.next_cursor){sourceIds.push(id);cursors[id]=run.next_cursor;}
    else unavailableIds.push(id);
  }
  return {sourceIds,cursors,unavailableIds};
}
