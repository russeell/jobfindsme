import type {SearchFilters,SourceCapability} from './contracts';
export function defaultDiscoveryFilters():SearchFilters{return {unknown_policy:'include',read:'any',salary_mode:'overlap'};}
// Interactive searches use fixed defaults; frozen scheduled snapshots are separate.
export function normalizeDiscoveryFilters(filters:SearchFilters={}):SearchFilters{return {...filters,unknown_policy:filters.unknown_policy??'include',salary_mode:'overlap'};}
export function selectedSearchSources(sources:SourceCapability[],selected:string[]):SourceCapability[]{return sources.filter(s=>selected.includes(s.source_id)&&s.live_search_enabled);}
export function readSelectedSources(raw:string|null):string[]{try{const value=JSON.parse(raw??'[]');return Array.isArray(value)&&value.every(id=>typeof id==='string')?[...new Set<string>(value)]:[];}catch{return [];}}
export function hasDiscoveryFilters(filters:SearchFilters,sourceId=''):boolean {
 const defaults=defaultDiscoveryFilters();
 return !!sourceId||Object.entries(normalizeDiscoveryFilters(filters)).some(([key,value])=>value!=null&&(!Array.isArray(value)||value.length>0)&&value!==defaults[key as keyof SearchFilters]);
}

export function applySearchPreferences(intent:string,filters:SearchFilters,preferences:import('./contracts').SearchPreferences):{intent:string;filters:SearchFilters}{
 const constrained=preferences.cities.length>0||preferences.salary_min_k!=null||preferences.salary_max_k!=null;
 return {intent:intent.trim()?intent:preferences.target_role,filters:{...filters,cities:[...preferences.cities],salary_min_k:preferences.salary_min_k??undefined,salary_max_k:preferences.salary_max_k??undefined,unknown_policy:constrained?'exclude':'include'}};
}
