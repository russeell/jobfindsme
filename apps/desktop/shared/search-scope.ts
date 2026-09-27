import type {SourceSearchResponse} from './contracts';

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
