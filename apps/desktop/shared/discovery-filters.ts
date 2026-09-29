import type {SearchFilters,SourceCapability} from './contracts';
export function defaultDiscoveryFilters():SearchFilters{return {unknown_policy:'include',read:'any',salary_mode:'overlap'};}
// Interactive searches use fixed defaults; frozen scheduled snapshots are separate.
export function normalizeDiscoveryFilters(filters:SearchFilters={}):SearchFilters{return {...filters,unknown_policy:filters.unknown_policy??'include',salary_mode:filters.salary_mode??'overlap'};}
export function selectedSearchSources(sources:SourceCapability[],selected:string[]):SourceCapability[]{return sources.filter(s=>selected.includes(s.source_id)&&s.live_search_enabled);}
export function selectedAttemptableSources(sources:SourceCapability[],selected:string[]):SourceCapability[]{return sources.filter(s=>selected.includes(s.source_id)&&(
  s.live_search_enabled||(["boss","zhilian","wuyou"].includes(s.source_id)&&s.session_status!=="blocked"&&s.list_status!=="blocked")
));}
const platformSourceIds=new Set(["boss","liepin","zhilian","wuyou"]);
export function readSelectedSources(raw:string|null):string[]{try{const value=JSON.parse(raw??'[]');return Array.isArray(value)&&value.every(id=>typeof id==='string')?[...new Set<string>(value)].filter(id=>platformSourceIds.has(id)):[];}catch{return [];}}
export function hasDiscoveryFilters(filters:SearchFilters,sourceId=''):boolean {
 const defaults=defaultDiscoveryFilters();
 return !!sourceId||Object.entries(normalizeDiscoveryFilters(filters)).some(([key,value])=>value!=null&&(!Array.isArray(value)||value.length>0)&&value!==defaults[key as keyof SearchFilters]);
}
