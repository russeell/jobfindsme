import type {DesktopApiClient} from "../backend/api-client";
import type {SourceBrowserManager} from "../browser/source-browser";
import {browserSiteNames} from "../../shared/browser-search";
import {isSourceBrowserId,requiresElectronSourceSearch} from "../../shared/source-browser-policy";
import type {BrowserSourcePage,SourceSearchInput,SourceSearchPreflight} from "../../shared/contracts";

export const SOURCE_SEARCH_CONCURRENCY = 4;
export async function collectBrowserSourcePages(
  input: SourceSearchInput,
  preflight: SourceSearchPreflight,
  deps: {concurrency?:number;client:DesktopApiClient;manager?:SourceBrowserManager;isCancelled:()=>boolean;onProgress?:(value:unknown)=>void;signal?:AbortSignal;onPage?:(sourceId:string,page:BrowserSourcePage)=>Promise<void>;onSourceCompleted?:(sourceId:string,pages:BrowserSourcePage[],error?:string)=>Promise<void>},
): Promise<{
  pages: Record<string, BrowserSourcePage[]>;
  errors: Record<string, string>;
  continuations:Record<string,string|null>;planned_queries:Array<{source_id:string;keyword:string;city:string}>;executed_queries:Array<{source_id:string;keyword:string;city:string}>;diagnostics: {started_at:string;first_source_ms:number|null;sources:Record<string,{elapsed_ms:number;records:number;site_pages:number;read_at:string;status:string}>};
}> {
  const {client,manager,isCancelled,onProgress,onSourceCompleted}=deps;
  const started=Date.now();
  const deadline=started+preflight.time_budget_seconds*1000;
  const remaining=()=>Math.max(0,(deadline-Date.now())/1000);
  const diagnostics:{started_at:string;first_source_ms:number|null;sources:Record<string,{elapsed_ms:number;records:number;site_pages:number;read_at:string;status:string}>}={started_at:new Date(started).toISOString(),first_source_ms:null,sources:{}};
  const browserPages: Record<string, BrowserSourcePage[]> = {};
  const browserErrors: Record<string, string> = {};
  const cities=[...new Set(input.city?[input.city]:input.filters?.cities?.length?input.filters.cities:[""])];
  if(cities.length>1)throw Error("每次只能选择一个城市；也可以选择城市不限");
  const city=cities[0],scope=JSON.stringify([input.workspace_id,preflight.keywords[0],city]);
  const continuations:Record<string,string|null>={},planned_queries=preflight.allowed_source_ids.flatMap(source_id=>cities.map(city=>({source_id,keyword:preflight.keywords[0],city}))),executed_queries:typeof planned_queries=[];
  const collectOne=async(sourceId:string):Promise<void>=>{
    const supplied=input.source_cursors?.[sourceId]??(sourceId==="boss"?input.boss_cursor:input.source_cursor);
    let cursor:string|null|undefined=supplied;
    if(supplied?.startsWith("source-v1:")){
      try{const decoded=JSON.parse(Buffer.from(supplied.slice(10),"base64url").toString());
        if(decoded.scope!==scope||decoded.source!==sourceId||decoded.cursor!==null&&decoded.cursor!==undefined&&typeof decoded.cursor!=="string")throw Error();
        cursor=decoded.cursor;
      }catch{browserErrors[sourceId]="unsupported_cursor:检索条件与续页不一致，请开始新搜索";return;}
    }else if(supplied?.startsWith("cities-v1:")){browserErrors[sourceId]="unsupported_cursor:旧版多城市检索请开始新搜索";return;}
    const pages:BrowserSourcePage[]=[];browserPages[sourceId]=pages;
    collect: for(let round=0;round<preflight.max_pages;round++){
      if(cursor===null)break;
      if(isCancelled()){browserErrors[sourceId]="cancelled:已停止后续来源，保留已读取结果";break collect;}
      if(remaining()<0.1){browserErrors[sourceId]="time_budget:本次总时间预算已用完";break collect;}
      onProgress?.({stage:"loading",count:pages.reduce((n,p)=>n+p.records.length,0),message:`正在读取 ${isSourceBrowserId(sourceId)?browserSiteNames[sourceId]:sourceId}${city?" · "+city:""}`});
      if(!isSourceBrowserId(sourceId))continue;
      try{
        const nativeCursor=cursor??undefined;let batch:BrowserSourcePage[];
        executed_queries.push({source_id:sourceId,keyword:preflight.keywords[0],city});
        if(!requiresElectronSourceSearch(sourceId))batch=await client.publicSourcePages(sourceId,{keyword:preflight.keywords[0],city,max_pages:1,seconds:Math.max(1,Math.min(60,remaining())),cursor:nativeCursor},deps.signal);
        else if(!manager)throw Error("browser_session_error:来源后台会话不可用");
        else if(sourceId==="boss")batch=[await (manager.bossForSearch?.(city)||manager.boss).collect({keyword:preflight.keywords[0],city,maxBatches:1,seconds:remaining(),cursor:nativeCursor},onProgress)];
        else{
          const page=nativeCursor?Number(nativeCursor):1;
          if(!Number.isInteger(page)||page<1)throw Error("unsupported_cursor:来源未提供可用页码");
          batch=[await manager.searchPage(sourceId,{keyword:preflight.keywords[0],city,page,deadline})];
        }
        for(const page of batch){
          pages.push(page);const nextCursor=sourceId==="boss"?page.collection?.cursor??page.next_cursor:page.next_cursor;
          if(page.collection?.failure){browserErrors[sourceId]=`${page.collection.failure}:请在平台原页处理后重试`;}
          if(diagnostics.first_source_ms===null&&page.records.length)diagnostics.first_source_ms=Date.now()-started;
          await deps.onPage?.(sourceId,page);cursor=nextCursor;
        }
        if(!batch.length)cursor=null;
        if(browserErrors[sourceId])break collect;
      }catch(error){browserErrors[sourceId]=String(error instanceof Error?error.message:error).slice(0,1000);break collect;}
    }
    if(!pages.length)delete browserPages[sourceId];
    // A source cursor binds the original query and workspace. Undefined means
    // an unstarted first page; only a saved page advances the native cursor.
    continuations[sourceId]=cursor===null?null:"source-v1:"+Buffer.from(JSON.stringify({scope,source:sourceId,cursor})).toString("base64url");
  };
  // Different sources have independent views; a small worker pool limits load.
  const sourceIds=[...preflight.allowed_source_ids];let nextSource=0;
  await Promise.all(Array.from({length:Math.min(Math.max(1,Math.min(SOURCE_SEARCH_CONCURRENCY,deps.concurrency??SOURCE_SEARCH_CONCURRENCY)),sourceIds.length)},async()=>{
    while(nextSource<sourceIds.length){
      const sourceId=sourceIds[nextSource++],start=Date.now();
      try{await collectOne(sourceId);}catch(error){browserErrors[sourceId]=`source_contract_error:${String(error).slice(0,500)}`;}
      const pages=browserPages[sourceId]||[],records=pages.reduce((count,page)=>count+page.records.length,0);
      diagnostics.sources[sourceId]={elapsed_ms:Date.now()-start,records,site_pages:pages.length,read_at:new Date().toISOString(),status:browserErrors[sourceId]||pages.some(page=>page.collection?.failure||["risk_control","login_required","source_contract_error","unsupported_city"].includes(page.collection?.stop_reason||""))?"partial_or_failed":"completed"};
      if(records&&diagnostics.first_source_ms===null)diagnostics.first_source_ms=Date.now()-started;
      if(onSourceCompleted)try{await onSourceCompleted(sourceId,pages,browserErrors[sourceId]);}
      catch(error){browserErrors[sourceId]=`save_failed:${String(error).slice(0,500)}`;}
      if(records)onProgress?.({stage:"listing",count:records,message:`${browserSiteNames[sourceId as keyof typeof browserSiteNames]||sourceId} 已读取 ${records} 条；其他来源继续检索`,titles:pages.flatMap(page=>page.records).slice(0,3).map(record=>String(record.payload.title||""))});
    }
  }));
  return { pages: browserPages, errors: browserErrors, diagnostics,continuations,planned_queries,executed_queries };
}
