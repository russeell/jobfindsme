import type {DesktopApiClient} from "../backend/api-client";
import type {SourceBrowserManager} from "../browser/source-browser";
import {browserSiteNames} from "../../shared/browser-search";
import {isSourceBrowserId,requiresElectronSourceSearch} from "../../shared/source-browser-policy";
import type {BrowserSourcePage,SourceSearchInput,SourceSearchPreflight} from "../../shared/contracts";

export async function collectBrowserSourcePages(
  input: SourceSearchInput,
  preflight: SourceSearchPreflight,
  deps: {client:DesktopApiClient;manager?:SourceBrowserManager;isCancelled:()=>boolean;onProgress?:(value:unknown)=>void},
): Promise<{
  pages: Record<string, BrowserSourcePage[]>;
  errors: Record<string, string>;
  diagnostics: {started_at:string;first_source_ms:number|null;sources:Record<string,{elapsed_ms:number;records:number;site_pages:number;read_at:string;status:string}>};
}> {
  const {client,manager,isCancelled,onProgress}=deps;
  const started=Date.now();
  const diagnostics:{started_at:string;first_source_ms:number|null;sources:Record<string,{elapsed_ms:number;records:number;site_pages:number;read_at:string;status:string}>}={started_at:new Date(started).toISOString(),first_source_ms:null,sources:{}};
  const browserPages: Record<string, BrowserSourcePage[]> = {};
  const browserErrors: Record<string, string> = {};
  const collectOne=async (sourceId:string):Promise<void> => {
    if(isCancelled()){browserErrors[sourceId]="cancelled:已停止后续来源，保留已读取结果";return;}
    onProgress?.({stage:"loading",count:0,message:`正在读取 ${isSourceBrowserId(sourceId)?browserSiteNames[sourceId]:"岗位来源"}`});
    if (!requiresElectronSourceSearch(sourceId)) {
      if(!isSourceBrowserId(sourceId))return;
      try { browserPages[sourceId]=await client.publicSourcePages(sourceId,{keyword:preflight.keywords[0],city:input.city||input.filters?.cities?.[0]||'',max_pages:Math.min(3,preflight.max_pages),seconds:Math.min(60,preflight.time_budget_seconds)}); }
      catch(primaryError){
        if(/429|risk_control|访问过于频繁|captcha/i.test(String(primaryError))){browserErrors[sourceId]=String(primaryError);return;}
        if(!manager){browserErrors[sourceId]=String(primaryError);return;}
        try {browserPages[sourceId]=[await manager.collectCareer(sourceId,{keyword:preflight.keywords[0],city:input.city||input.filters?.cities?.[0]||'',maxPages:preflight.max_pages,seconds:preflight.time_budget_seconds})];}
        catch(fallbackError){browserErrors[sourceId]=`首选通道：${String(primaryError).slice(0,300)}；内嵌浏览器：${String(fallbackError).slice(0,400)}`;}
      }
      return;
    }
    if (!manager) {
      browserErrors[sourceId] = "browser_session_error:来源后台会话不可用";
      return;
    }
    if(sourceId==="boss"){
      try {browserPages.boss=[await manager.boss.collect({keyword:preflight.keywords[0],city:input.city||input.filters?.cities?.[0]||"",maxBatches:preflight.max_pages,seconds:preflight.time_budget_seconds,cursor:input.boss_cursor},progress=>{onProgress?.(progress);})];}
      catch(error){const message=error instanceof Error?error.message:String(error),failure=message.startsWith("risk_control:")?"risk_control":message.startsWith("login_required:")?"login_required":null;
        browserPages.boss=[{records:[],next_cursor:null,collection:{batches:0,elapsed_seconds:0,stop_reason:failure||(message.startsWith("unsupported_city:")?"unsupported_city":"source_contract_error"),cursor:null,complete:false,failure}}];
      }
      const collection=browserPages.boss[0]?.collection;
      if((input.filters?.cities?.length||0)>1 && collection?.complete){collection.complete=false;collection.stop_reason="city_scope";}
      return;
    }
    const pages: BrowserSourcePage[] = [];
    let page = 1;
    try {
      while (page <= preflight.max_pages) {
        if(isCancelled())throw Error('cancelled:已停止后续翻页，保留已读取结果');
        const result = await manager.searchPage(
          sourceId,
          { keyword: preflight.keywords[0], city: input.city || input.filters?.cities?.[0] || "", page },
        );
        pages.push(result);
        if (!result.next_cursor) break;
        const nextPage = Number(result.next_cursor);
        if (!Number.isInteger(nextPage) || nextPage <= page) break;
        page = nextPage;
      }
      browserPages[sourceId] = pages;
    } catch (error) {
      if (pages.length) browserPages[sourceId] = pages;
      const message = error instanceof Error ? error.message : String(error);
      browserErrors[sourceId] = message.slice(0, 1000);
      const failure = message.startsWith("login_required:")
        ? "login_required"
        : message.startsWith("risk_control:")
          ? "risk_control"
          : undefined;
      if (failure) {
        await client.recordSourceRuntimeFailure(sourceId, failure, message);
      }
    }
  };
  // Different sources have independent views; a small worker pool limits load.
  const sourceIds=[...preflight.allowed_source_ids];let nextSource=0;
  await Promise.all(Array.from({length:Math.min(2,sourceIds.length)},async()=>{
    while(nextSource<sourceIds.length){
      const sourceId=sourceIds[nextSource++],start=Date.now();
      try{await collectOne(sourceId);}catch(error){browserErrors[sourceId]=`source_contract_error:${String(error).slice(0,500)}`;}
      const pages=browserPages[sourceId]||[],records=pages.reduce((count,page)=>count+page.records.length,0);
      diagnostics.sources[sourceId]={elapsed_ms:Date.now()-start,records,site_pages:pages.length,read_at:new Date().toISOString(),status:browserErrors[sourceId]?"partial_or_failed":"completed"};
      if(records&&diagnostics.first_source_ms===null)diagnostics.first_source_ms=Date.now()-started;
      if(records)onProgress?.({stage:"listing",count:records,message:`${browserSiteNames[sourceId as keyof typeof browserSiteNames]||sourceId} 已读取 ${records} 条；其他来源继续检索`,titles:pages.flatMap(page=>page.records).slice(0,3).map(record=>String(record.payload.title||""))});
    }
  }));
  return { pages: browserPages, errors: browserErrors, diagnostics };
}
