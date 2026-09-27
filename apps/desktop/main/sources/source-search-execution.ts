import {randomUUID} from "node:crypto";
import type {DesktopApiClient} from "../backend/api-client";
import type {SourceBrowserManager} from "../browser/source-browser";
import type {BrowserSourcePage,SourceSearchInput,SourceSearchResponse,SourceSearchRun} from "../../shared/contracts";
import {collectBrowserSourcePages} from "./source-search-coordinator";
import {requiresElectronSourceSearch,summarizeSourceVerification} from "../../shared/source-browser-policy";

export type SourceBatchFailure={source_id:string;stage:"save"|"source_status";message:string};
const messageOf=(error:unknown)=>error instanceof Error?error.message:String(error);

/** Keep source collection concurrent while committing each validated batch in order. */
export async function executeBoundedSourceSearch(
  input:SourceSearchInput,
  deps:{client:DesktopApiClient;manager?:SourceBrowserManager;getCancellationEpoch:()=>number;onProgress?:(value:unknown)=>void;onSourceStatusChanged?:()=>void},
):Promise<SourceSearchResponse>{
  const {client,manager,getCancellationEpoch,onProgress,onSourceStatusChanged}=deps;
  const epoch=getCancellationEpoch();
  const isCancelled=()=>epoch!==getCancellationEpoch();
  if(isCancelled())throw Error("cancelled:检索已停止");
  const runStarted=Date.now();
  const preflight=await client.searchPreflight({...input,attempt_unverified_login:true});
  if(isCancelled())throw Error("cancelled:预检期间已停止检索");
  const clientRunId=input.client_run_id||randomUUID();
  let runId=input.existing_run_id;
  const responses:SourceSearchResponse[]=[];
  const failures:SourceBatchFailure[]=[];
  let firstUsableMs:number|null=null;
  let saveQueue=Promise.resolve();
  const saveOne=async(sourceId:string,pages:BrowserSourcePage[],error?:string)=>{
    if(isCancelled()&&!pages.length)return;
    const {boss_cursor:_boss,source_cursor:_source,client_run_id:_client,existing_run_id:_existing,...executionInput}=input;
    let response:SourceSearchResponse;
    try{
      response=await client.runSourceSearch({...executionInput,attempt_unverified_login:true,source_ids:[sourceId],existing_run_id:runId,
        resume_version_id:preflight.resume_version_id||undefined,
        browser_pages:pages.length?{[sourceId]:pages}:{},browser_errors:error?{[sourceId]:error}:{}});
    }catch(saveError){failures.push({source_id:sourceId,stage:"save",message:messageOf(saveError).slice(0,300)});return;}
    runId=response.result_page.run_id;
    responses.push(response);
    if(firstUsableMs===null&&response.result_page.total>0)firstUsableMs=Date.now()-runStarted;
    try{onProgress?.({stage:"listing",count:response.result_page.total,
      message:`${sourceId} 已保存并筛选 ${response.result_page.total} 条候选`,workspace_id:input.workspace_id,client_run_id:clientRunId,
      run_id:runId,source_id:sourceId,batch_id:`${sourceId}:${responses.length}`,response});}catch{/* A notification failure must not mark a saved batch as failed. */}
    const pageFailure=pages.find(page=>page.collection?.failure)?.collection?.failure;
    const failure=pageFailure|| (error&&/login_required:/.test(error)?"login_required":error&&/risk_control:/.test(error)?"risk_control":null);
    if(failure)try{await client.recordSourceRuntimeFailure(sourceId,failure,error||`${failure}:有界检索被来源阻断`);}
      catch(statusError){failures.push({source_id:sourceId,stage:"source_status",message:messageOf(statusError).slice(0,300)});}
    if(!error&&requiresElectronSourceSearch(sourceId)&&response.jobs.some(job=>job.source_id===sourceId)&&!pages.some(page=>page.collection?.failure)&&response.source_runs.some(run=>run.source_id===sourceId&&run.status!=="failed")){
      try{const summary=summarizeSourceVerification(pages);await client.recordSourceVerification(sourceId,{...summary,
        detail_status:"unverified",pagination_status:"partial",notes:`本次用户检索读取 ${pages.flatMap(page=>page.records).length} 条；详情与网站续页仍单独待验。`});}
      catch(statusError){failures.push({source_id:sourceId,stage:"source_status",message:messageOf(statusError).slice(0,300)});}
    }
  };
  const browser=await collectBrowserSourcePages(input,preflight,{client,manager,isCancelled,
    onProgress:value=>onProgress?.({...(value as object),workspace_id:input.workspace_id,client_run_id:clientRunId}),
    onSourceCompleted:(sourceId,pages,error)=>{
      saveQueue=saveQueue.then(()=>saveOne(sourceId,pages,error)).catch(saveError=>{
        failures.push({source_id:sourceId,stage:"save",message:messageOf(saveError).slice(0,300)});
      });
      return saveQueue;
    }});
  await saveQueue;
  if(isCancelled()&&!responses.length)throw Error("cancelled:检索已停止");
  let response=responses.at(-1);
  if(!response){
    if(failures.length)throw Error(`本次岗位保存失败：${failures.map(item=>item.source_id).join("、")}`);
    const {boss_cursor:_boss,source_cursor:_source,client_run_id:_client,existing_run_id:_existing,...executionInput}=input;
    response=await client.runSourceSearch({...executionInput,attempt_unverified_login:true,source_ids:[],existing_run_id:runId,resume_version_id:preflight.resume_version_id||undefined});
  }
  onSourceStatusChanged?.();
  const query={keyword:preflight.keywords[0],city:input.city||input.filters?.cities?.[0]||""};
  const failedRuns:SourceSearchRun[]=failures.filter(item=>item.stage==="save").map(item=>({source_id:item.source_id,
    status:"failed",pages_fetched:browser.pages[item.source_id]?.length||0,elapsed_seconds:0,coverage_status:"failed",
    can_continue:false,next_cursor:null,stop_reason:"save_failed",error:item.message}));
  for(const item of failures){const diagnostic=browser.diagnostics.sources[item.source_id];if(diagnostic)diagnostic.status=item.stage==="save"?"save_failed":"source_status_failed";}
  const runOrder=new Map(preflight.allowed_source_ids.map((sourceId,index)=>[sourceId,index]));
  const sourceRuns=[...responses.flatMap(batch=>batch.source_runs),...failedRuns]
    .sort((a,b)=>(runOrder.get(a.source_id)??Infinity)-(runOrder.get(b.source_id)??Infinity));
  return {...response,allowed_source_ids:preflight.allowed_source_ids,blocked_sources:preflight.blocked_sources,
    source_runs:sourceRuns,batch_failures:failures,
    source_diagnostics:{...browser.diagnostics,first_usable_ms:firstUsableMs},
    planned_queries:preflight.allowed_source_ids.map(source_id=>({source_id,...query})),
    executed_queries:preflight.allowed_source_ids.filter(source_id=>{
      const source=browser.diagnostics.sources[source_id];return !!source&&
        (source.site_pages>0||!/(cancelled|time_budget|browser_session_error|unsupported_cursor)/.test(browser.errors[source_id]||""));
    }).map(source_id=>({source_id,...query})),local_filters:input.filters};
}
