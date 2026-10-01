import type {PreparationStage,TrackedJob} from './contracts';

export type RecordsFilter='following'|'saved'|'applied'|'read'|'all';
export type RecordsSort='recent'|'next';
export const recordsPageSize=20;

export function recordStage(item:TrackedJob):PreparationStage|undefined {
  return item.preparation?.stage || (item.tracking.applied?'applied':undefined);
}
export function followsRecord(item:TrackedJob):boolean {
  return recordStage(item)!=='closed' && (item.tracking.saved||item.tracking.applied||!!item.preparation);
}
export function matchesRecordFilter(item:TrackedJob,filter:RecordsFilter):boolean {
  return filter==='all'||(filter==='following'?followsRecord(item):item.tracking[filter]);
}
function recordedAt(item:TrackedJob):number {
  return Date.parse(item.preparation?.updated_at||item.job.source.fetched_at||'')||0;
}
export function selectRecords(items:TrackedJob[],filter:RecordsFilter,query:string,stage:PreparationStage|'',sort:RecordsSort):TrackedJob[] {
  const terms=query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  return items.filter(item=>{
    const text=[item.job.title,item.job.company,...item.job.locations,item.job.source.source_name].join(' ').toLocaleLowerCase();
    return matchesRecordFilter(item,filter)&&(!stage||recordStage(item)===stage)&&terms.every(term=>text.includes(term));
  }).sort((a,b)=>{
    if(sort==='next'){
      const key=(item:TrackedJob)=>item.preparation?.next_action&&recordStage(item)!=='closed'?(item.preparation.due_date||'9998'):'9999';
      const difference=key(a).localeCompare(key(b));if(difference)return difference;
    }
    return recordedAt(b)-recordedAt(a);
  });
}
