import {normalizeDiscoveryFilters} from "../shared/discovery-filters";
import { readFileSync } from "node:fs";
import { randomUUID } from "node:crypto";
import path from "node:path";

import { app, BrowserWindow, dialog, ipcMain, shell } from "electron";

import type { DesktopApiClient } from "./backend/api-client";
import { saveModelConnectionWithSecret } from "./backend/model-connection-service";
import { PythonService, type ServiceStatus } from "./backend/python-service";
import { SecureSecretStore } from "./security/secure-secret-store";
import { SourceBrowserManager } from "./browser/source-browser";
import {runSourceCheckQueue} from "./sources/source-check-queue";
import {browserSiteNames} from "../shared/browser-search";
import { isAllowedSourceUrl, sourceBrowserSpecs, isSourceBrowserId, requiresElectronSourceSearch, summarizeSourceVerification, type SourceBrowserBounds } from "../shared/source-browser-policy";
import type {
  ModelConnectionInput, ResumeConfirmation, ResumeEditInput, ResumeExportInput,
  PromptPatchDecision, PromptSessionInput, PromptTurnInput, SourceSearchInput,
  BrowserSourcePage, ResearchRunInput, ScheduledTaskInput, SourceSearchPreflight, SourceCapability,
} from "../shared/contracts";

const packageInfo=JSON.parse(readFileSync(path.join(app.getAppPath(),"package.json"),"utf8"));
const buildLabel=String(packageInfo.build || "development");
const previewBuild=packageInfo.jobfindsmePreview===true;
if(previewBuild){
  const profile = typeof packageInfo.previewUserData === "string" && /^jobfindsme-preview-[a-zA-Z0-9_-]+$/.test(packageInfo.previewUserData) ? packageInfo.previewUserData : `jobfindsme-preview-${buildLabel.split("-")[0]}`;
  if(!app.commandLine.hasSwitch("user-data-dir"))app.setPath("userData",path.join(app.getPath("appData"),profile));
  app.setName(`JobFindsMe ${buildLabel.split("-")[0]} 测试版`);
}
const isolatedProfile=previewBuild || app.commandLine.hasSwitch("user-data-dir");
// Electron scopes this lock to userData, before Python, SQLite or scheduler startup.
const ownsInstance=app.requestSingleInstanceLock();
if(!ownsInstance)app.exit(0);
let apiClient: DesktopApiClient | undefined;
let mainWindow: BrowserWindow | undefined;
app.on("second-instance",()=>{if(mainWindow){if(mainWindow.isMinimized())mainWindow.restore();mainWindow.show();mainWindow.focus();}});
let serviceStatus: ServiceStatus = {
  connected: false,
  message: "本地服务正在启动",
};
let shutdownPromise: Promise<void> | undefined;
const projectRoot = path.resolve(__dirname, "../../../..");
const pythonService = new PythonService({
  projectRoot,
  userDataPath: app.getPath("userData"),
  packaged: app.isPackaged,
  resourcesPath: process.resourcesPath,
  onStatus: (status) => {
    if (status.connected) return; // Publish ready only after apiClient is assigned.
    serviceStatus = status;
    if (!status.connected) apiClient = undefined;
    mainWindow?.webContents.send("desktop:service-status", status);
  },
});
const secretStore = new SecureSecretStore(app.getPath("userData"));
let modelTestController: AbortController | undefined;
let modelTestConnectionId: string | undefined;
let modelTestRunId: string | undefined;
let promptController: AbortController | undefined;
let promptSessionId: string | undefined;
let promptRequestId: string | undefined;
let sourceBrowserManager: SourceBrowserManager | undefined;
let sourceCheckController:AbortController|undefined;
const sourceAutoCheckAt=new Map<string,number>();
const sourceAutoCheckPending=new Set<string>();
let researchController: AbortController | undefined;
let researchRequestId: string | undefined;
let researchWorkspaceId: string | undefined;
let isQuitting = false;

function shutdownAndExit(): Promise<void> {
  if (shutdownPromise) return shutdownPromise;
  apiClient = undefined;
  serviceStatus = { connected: false, message: "本地服务正在退出" };
  isQuitting = true;
  shutdownPromise = pythonService
    .stop()
    .catch((error) => console.error("JobFindsMe failed to stop cleanly", error))
    .then(() => app.exit(0));
  return shutdownPromise;
}

async function createWindow(): Promise<void> {
  mainWindow = new BrowserWindow({
    title:`JobFindsMe · ${buildLabel}${isolatedProfile?" · 隔离测试":""}`,
    width: 1240,
    height: 820,
    minWidth: 760,
    minHeight: 600,
    backgroundColor: "#ffffff",
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "../preload/index.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  mainWindow.on("page-title-updated",event=>event.preventDefault());
  mainWindow.webContents.setWindowOpenHandler(({ url: value }) => {
    try {
      const url = new URL(value);
      if (["http:", "https:"].includes(url.protocol) && !url.username && !url.password) {
        void shell.openExternal(url.toString());
      }
    } catch {
      // Invalid or non-web destinations remain denied.
    }
    return { action: "deny" };
  });
  mainWindow.webContents.on("will-navigate", (event) => event.preventDefault());
  mainWindow.once("ready-to-show", () => mainWindow?.show());
  mainWindow.on("close", (event) => {
    if (isQuitting) return;
    event.preventDefault();
    sourceBrowserManager?.layout(null);
    mainWindow?.hide();
  });
  let lastBossState = "";
  sourceBrowserManager = new SourceBrowserManager(mainWindow, async (page,explicit) => {
    if(!apiClient)return;
    let state = page.blocked ? "risk_control" : page.loginRequired ? "login_required" : page.authenticated && page.readable ? "ready" : "";
    if(!state || (state===lastBossState&&!explicit&&sourceBrowserManager?.boss.paused!=="login_required"))return;
    if(state==="ready") {
      if(!explicit && (sourceBrowserManager?.boss.paused==="risk_control" || (await apiClient.bootstrap()).sources.find(source=>source.source_id==="boss")?.session_status==="blocked"))return;
      sourceBrowserManager?.boss.resume();
      await apiClient.recordSourceVerification("boss",{session_status:"verified",list_status:"verified",detail_status:"unverified",fields_status:"partial",pagination_status:"unverified",enabled:true,notes:"当前平台页面已登录且列表可读；完整JD及滚动覆盖由每次检索单独报告。"});
    } else {
      if(sourceBrowserManager)sourceBrowserManager.boss.pause(state as "risk_control"|"login_required");
      await apiClient.recordSourceRuntimeFailure("boss",state as "risk_control"|"login_required",state==="risk_control"?"平台要求验证，处理后点击恢复":"请在当前平台页完成登录");
    }
    lastBossState=state;mainWindow?.webContents.send("desktop:source-status-changed");
  }, async (sourceId,page) => {
    if(!apiClient)return;
    const current=(await apiClient.bootstrap()).sources.find(source=>source.source_id===sourceId);
    if(!current)return;
    if(page.kind==="challenge") {
      await apiClient.recordSourceRuntimeFailure(sourceId,"risk_control","原页要求安全验证；自动检索已停止，需用户在原页处理。");
    } else if(page.kind==="login" || page.kind==="splash") {
      const reason=page.formCount===0 ? "当前原页未呈现可操作登录表单；平台登录与自动检索仍未验证，请稍后重试。" : "当前页面显示登录表单；会话有效性与检索能力仍需分别确认。";
      await apiClient.recordSourceVerification(sourceId,{session_status:"unverified",list_status:current.list_status,detail_status:current.detail_status,fields_status:current.fields_status,pagination_status:current.pagination_status,enabled:false,notes:reason});
    } else if(page.kind==="list") {
      const recent=current.last_verified_at && Date.now()-Date.parse(current.last_verified_at)<600000;
      const verified=current.session_status==="verified"&&current.list_status==="verified";
      if(!verified)await apiClient.recordSourceVerification(sourceId,{session_status:"verified",list_status:"partial",detail_status:current.detail_status,fields_status:"partial",pagination_status:"unverified",enabled:false,notes:`原页可见 ${page.cardCount} 个岗位卡片；自动检索尚待有界验证。`});
      const last=sourceAutoCheckAt.get(sourceId)||0;
      if(!sourceAutoCheckPending.has(sourceId)&&!recent&&Date.now()-last>600000){
        sourceAutoCheckAt.set(sourceId,Date.now());sourceAutoCheckPending.add(sourceId);
        void (async()=>{try{
          const result=await sourceBrowserManager!.searchPage(sourceId,{keyword:"工程师",city:"",page:1});
          const summary=summarizeSourceVerification([result]);
          await apiClient!.recordSourceVerification(sourceId,{...summary,session_status:"verified",detail_status:current.detail_status==="verified"?"verified":"unverified",pagination_status:"partial",notes:`登录后一次有界检索：${result.records.length} 条、1 个网站页。详情与网站续页仍单独待验。`});
        }catch(error){const failure=String(error);
          if(/risk_control:|login_required:/.test(failure))await apiClient!.recordSourceRuntimeFailure(sourceId,failure.startsWith("risk_control:")?"risk_control":"login_required",failure.slice(0,500));
          else await apiClient!.recordSourceVerification(sourceId,{session_status:"verified",list_status:"partial",detail_status:current.detail_status,fields_status:"partial",pagination_status:"unverified",enabled:false,notes:`原页有列表，后台有界检索未通过：${failure.slice(0,350)}`});
        }finally{sourceAutoCheckPending.delete(sourceId);mainWindow?.webContents.send("desktop:source-status-changed");}})();
      }
    }
    mainWindow?.webContents.send("desktop:source-status-changed");
  });
  mainWindow.once("closed", () => {
    sourceBrowserManager?.destroy();
    sourceBrowserManager = undefined;
  });

  const devUrl = process.env.JFM_RENDERER_URL;
  if (devUrl) await mainWindow.loadURL(devUrl);
  else await mainWindow.loadFile(path.resolve(__dirname, "../../dist/index.html"));
}

// Matching credentials stay in the main process and are never returned to the renderer.
let matchingRequest: {workspaceId:string;requestId:string;cancelled:boolean;started:boolean} | undefined;
function matchingClient(event: Electron.IpcMainInvokeEvent) {
  if(event.sender !== mainWindow?.webContents || !apiClient) throw new Error("matching unavailable");
  return apiClient;
}
ipcMain.handle("desktop:matching-rules",(event,workspaceId:string)=>matchingClient(event).matchingRules(workspaceId));
ipcMain.handle("desktop:save-matching-rule",(event,input)=>matchingClient(event).saveMatchingRule(input));
ipcMain.handle("desktop:delete-matching-rule",(event,workspaceId:string,ruleVersionId:string)=>matchingClient(event).deleteMatchingRule(workspaceId,ruleVersionId));
ipcMain.handle("desktop:matching-trial",(event,input)=>matchingClient(event).matchingTrial(input));
ipcMain.handle("desktop:matching-input",(event,workspaceId:string,runId:string)=>matchingClient(event).matchingInput(workspaceId,runId));
ipcMain.handle("desktop:rerank-matching",async(event,workspaceId:string,runId:string)=>{
  const client=matchingClient(event);
  if(matchingRequest) throw new Error("已有匹配请求正在执行");
  const request={workspaceId,requestId:`matching-${randomUUID()}`,cancelled:false,started:false};matchingRequest=request;
  try {
    const {rule}=await client.matchingInput(workspaceId,runId);
    const snapshot=rule.model_snapshot;
    const apiKey=snapshot?.auth_mode === "none" ? "" : snapshot?.credential_ref ? secretStore.get(snapshot.credential_ref) : "";
    if(request.cancelled)return {status:"cancelled",message:"已取消，保留本地结果。"};
    request.started=true;
    return await client.rerankMatching({workspace_id:workspaceId,run_id:runId,request_id:request.requestId,api_key:apiKey || ""});
  } finally {if(matchingRequest===request)matchingRequest=undefined;}
});
ipcMain.handle("desktop:cancel-matching",async(event)=>{
  const client=matchingClient(event),request=matchingRequest;if(!request)return;
  request.cancelled=true;
  if(request.started){await client.cancelMatching(request.workspaceId,request.requestId);}
});

ipcMain.handle("desktop:preview-matching", async (_event, input) => {
  if (!apiClient) throw new Error("desktop API is not ready");
  return apiClient.previewMatching(input);
});
ipcMain.handle("desktop:get-bootstrap", async () => {
  if (!apiClient) throw new Error("desktop API is not ready");
  return apiClient.bootstrap();
});
let sourceSearchActive=0;
ipcMain.handle("desktop:run-source-search", async (event, input: SourceSearchInput) => {
  if (!mainWindow || event.sender !== mainWindow.webContents || !apiClient) {
    throw new Error("desktop API is not ready");
  }
  if(!Array.isArray(input.source_ids)||!input.source_ids.length)throw new Error("请先选择岗位来源。");
  if(sourceCheckController)throw Error("全部来源检查进行中，请先结束检查");
  sourceSearchActive++;
  try{
  input={...input,filters:normalizeDiscoveryFilters(input.filters)};
  const preflight = await apiClient.searchPreflight(input);
  const browser = await collectBrowserSourcePages(input, preflight);
  const {boss_cursor: _cursor,...executionInput}=input;
  const response=await apiClient.runSourceSearch({
    ...executionInput,
    resume_version_id: preflight.resume_version_id || undefined,
    browser_pages: browser.pages,
    browser_errors: browser.errors,
  });
  mainWindow?.webContents.send("desktop:source-status-changed");return {...response,source_diagnostics:browser.diagnostics};
  }finally{sourceSearchActive--;}
});

let sourceSearchEpoch=0;
async function collectBrowserSourcePages(
  input: SourceSearchInput,
  preflight: SourceSearchPreflight,
  reportProgress = true,
): Promise<{
  pages: Record<string, BrowserSourcePage[]>;
  errors: Record<string, string>;
  diagnostics: {started_at:string;first_source_ms:number|null;sources:Record<string,{elapsed_ms:number;records:number;site_pages:number;read_at:string;status:string}>};
}> {
  if (!apiClient) throw new Error("desktop API is not ready");
  const client=apiClient;
  const manager=sourceBrowserManager;
  const epoch=sourceSearchEpoch;
  const started=Date.now();
  const diagnostics:{started_at:string;first_source_ms:number|null;sources:Record<string,{elapsed_ms:number;records:number;site_pages:number;read_at:string;status:string}>}={started_at:new Date(started).toISOString(),first_source_ms:null,sources:{}};
  const browserPages: Record<string, BrowserSourcePage[]> = {};
  const browserErrors: Record<string, string> = {};
  const collectOne=async (sourceId:string):Promise<void> => {
    if(epoch!==sourceSearchEpoch){browserErrors[sourceId]="cancelled:已停止后续来源，保留已读取结果";return;}
    if(reportProgress)mainWindow?.webContents.send("desktop:source-collection-progress",{stage:"loading",count:0,message:`正在读取 ${isSourceBrowserId(sourceId)?browserSiteNames[sourceId]:"岗位来源"}`});
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
      try {browserPages.boss=[await manager.boss.collect({keyword:preflight.keywords[0],city:input.city||input.filters?.cities?.[0]||"",maxBatches:preflight.max_pages,seconds:preflight.time_budget_seconds,cursor:input.boss_cursor},progress=>{if(reportProgress)mainWindow?.webContents.send("desktop:source-collection-progress",progress);})];}
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
        if(epoch!==sourceSearchEpoch)throw Error('cancelled:已停止后续翻页，保留已读取结果');
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
      if(reportProgress&&records)mainWindow?.webContents.send("desktop:source-collection-progress",{stage:"listing",count:records,message:`${browserSiteNames[sourceId as keyof typeof browserSiteNames]||sourceId} 已读取 ${records} 条；其他来源继续检索`,titles:pages.flatMap(page=>page.records).slice(0,3).map(record=>String(record.payload.title||""))});
    }
  }));
  return { pages: browserPages, errors: browserErrors, diagnostics };
}
ipcMain.handle("desktop:refilter-search",(event,workspaceId:string,runId:string,filters,pageSize:number)=>{if(event.sender!==mainWindow?.webContents||!apiClient)throw Error("desktop API is not ready");return apiClient.refilterSearch(workspaceId,runId,normalizeDiscoveryFilters(filters),pageSize);});
ipcMain.handle("desktop:get-search-page", (event, workspaceId: string, runId: string, page: number, pageSize: number) => {
  if (!mainWindow || event.sender !== mainWindow.webContents || !apiClient) throw new Error("desktop API is not ready");
  return apiClient.getSearchPage(workspaceId, runId, page, pageSize);
});
ipcMain.handle("desktop:set-job-tracking", (event, input) => {
  if (!mainWindow || event.sender !== mainWindow.webContents || !apiClient) throw new Error("desktop API is not ready");
  return apiClient.setJobTracking(input);
});
ipcMain.handle("desktop:list-job-tracking", (event, workspaceId: string) => {
  if (!mainWindow || event.sender !== mainWindow.webContents || !apiClient) throw new Error("desktop API is not ready");
  return apiClient.listJobTracking(workspaceId);
});
ipcMain.handle("desktop:get-service-status", () => serviceStatus);
ipcMain.handle("desktop:open-source-browser", async (event, sourceId: string, bounds: SourceBrowserBounds) => {
  if (!mainWindow || event.sender !== mainWindow.webContents || !sourceBrowserManager) {
    throw new Error("source browser is not available");
  }
  if (!isSourceBrowserId(sourceId)) throw new Error("unknown source browser");
  await sourceBrowserManager.show(sourceId, bounds);
});
async function probeSourceForBulk(source:SourceCapability,signal:AbortSignal):Promise<SourceCapability>{
  if(!sourceBrowserManager||!apiClient||!isSourceBrowserId(source.source_id))throw Error("source_contract_error:来源不可检查");
  const sourceId=source.source_id;
  const stop=()=>sourceBrowserManager?.cancelCareerSearch();
  if(sourceId==="boss"){
    const page=await sourceBrowserManager.observeBoss(true);
    if(!page?.authenticated||!page.readable||page.blocked)throw Error("source_contract_error:请在应用内打开 BOSS 已登录的岗位列表后检查");
    return (await apiClient.bootstrap()).sources.find(item=>item.source_id===sourceId)!;
  }
  signal.addEventListener("abort",stop,{once:true});
  try{
    let pages:BrowserSourcePage[];
    if(sourceId==="zhilian"||sourceId==="wuyou"){
      const page=await sourceBrowserManager.searchPage(sourceId,{keyword:"工程师",city:"",page:1,forceRefresh:true});
      pages=[page];
    }else if(["liepin","company_01","company_12"].includes(sourceId)){
      pages=await apiClient.publicSourcePages(sourceId,{keyword:"工程师",city:"",max_pages:1,seconds:8,force_refresh:true},signal);
    }else{
      pages=[await sourceBrowserManager.collectCareer(sourceId,{keyword:"工程师",city:"",maxPages:1,seconds:8,forceRefresh:true})];
    }
    if(signal.aborted)throw Error("source_check_cancelled");
    if(pages.some(page=>page.collection?.failure==="risk_control"))throw Error("risk_control:来源要求安全验证");
    if(pages.some(page=>page.collection?.failure==="login_required"))throw Error("login_required:来源要求重新登录");
    const first=pages.flatMap(page=>page.records)[0];
    if(!first)throw Error("no_matching:本次没有读取到匹配岗位；不能判定来源不可用");
    const summary=summarizeSourceVerification(pages);
    summary.session_status=source.login_required?"verified":"anonymous";
    summary.pagination_status="unverified";
    summary.notes=`批量检查本次仅验证 1 个列表页；JD 与网站续页未在本次重查。${summary.notes}`;
    return apiClient.recordSourceVerification(sourceId,summary,signal);
  }catch(error){
    const message=String(error);
    if(!signal.aborted&&/risk_control:|login_required:/.test(message)){
      await apiClient.recordSourceRuntimeFailure(sourceId,message.includes("risk_control:")?"risk_control":"login_required",message.slice(0,500)).catch(()=>{});
    }
    throw error;
  }finally{signal.removeEventListener("abort",stop);}
}
ipcMain.handle("desktop:check-all-sources",async(event,runId:string)=>{
  if(event.sender!==mainWindow?.webContents||!apiClient||!sourceBrowserManager||!/^[-a-zA-Z0-9]{8,80}$/.test(runId))throw Error("source verification is not available");
  if(sourceCheckController)throw Error("全部来源检查已在运行");
  if(sourceSearchActive)throw Error("岗位检索进行中，请结束后检查全部来源");
  const controller=new AbortController();sourceCheckController=controller;
  try{
    const sources=(await apiClient.bootstrap()).sources;
    const results=await runSourceCheckQueue({sources,signal:controller.signal,probe:probeSourceForBulk,
      maxLiveProbes:previewBuild?1:undefined,
      onProgress:(result,done,total)=>mainWindow?.webContents.send("desktop:source-check-progress",{runId,result,done,total})});
    mainWindow?.webContents.send("desktop:source-status-changed");
    return results;
  }finally{if(sourceCheckController===controller)sourceCheckController=undefined;}
});
ipcMain.handle("desktop:cancel-all-source-checks",event=>{if(event.sender!==mainWindow?.webContents)throw Error("unauthorized caller");sourceCheckController?.abort();});
ipcMain.handle("desktop:verify-source", async (event, sourceId: string) => {
  if (!mainWindow || event.sender !== mainWindow.webContents || !sourceBrowserManager || !apiClient) {
    throw new Error("source verification is not available");
  }
  if(!isSourceBrowserId(sourceId))throw Error('unknown source');
  if(sourceCheckController)throw Error('全部来源检查进行中，请结束后再单独重试');
  if(!requiresElectronSourceSearch(sourceId)){
    let pages:BrowserSourcePage[];
    try {pages=await apiClient.publicSourcePages(sourceId,{keyword:'工程师',city:'',max_pages:2,seconds:20});}
    catch {pages=[await sourceBrowserManager.collectCareer(sourceId,{keyword:'工程师',city:'',maxPages:2,seconds:30})];}
    const first=pages.flatMap(p=>p.records)[0];
    if(!first)throw Error('未读取到匹配岗位，当前仍为待验证；可在官网手动浏览。');
    if(first.payload.detail_level!=='detail_page')try{const d=await sourceBrowserManager.readResearchJob(sourceId,String(first.payload.apply_url));first.payload={...first.payload,description:d.description,detail_level:'detail_page'};}catch{}
    const summary=summarizeSourceVerification(pages);
    summary.session_status='anonymous';summary.pagination_status='partial';
    summary.notes='有界检索已读取列表；分页/城市覆盖仍需逐项实测。'+summary.notes;
    return apiClient.recordSourceVerification(sourceId,summary);
  }
  if(sourceId==="boss"){
    const page=await sourceBrowserManager.observeBoss(true);
    if(!page?.authenticated||!page.readable||page.blocked)throw Error("请从岗位来源打开 BOSS，完成登录或验证并显示岗位列表后恢复。");
    return (await apiClient.bootstrap()).sources.find(source=>source.source_id==="boss");
  }
  const first = await sourceBrowserManager.searchPage(sourceId, { keyword: "Python", city: "", page: 1 });
  const pages = [first];
  if (first.next_cursor) {
    pages.push(await sourceBrowserManager.searchPage(sourceId, { keyword: "Python", city: "", page: Number(first.next_cursor) }));
  }
  return apiClient.recordSourceVerification(sourceId, summarizeSourceVerification(pages));
});
ipcMain.handle("desktop:cancel-source-search",event=>{if(event.sender!==mainWindow?.webContents)throw Error("unauthorized caller");sourceSearchEpoch++;sourceBrowserManager?.boss.cancel();sourceBrowserManager?.cancelCareerSearch();});
ipcMain.handle("desktop:read-source-detail",async(event,sourceId:string,url:string,workspaceId?:string,jobId?:string)=>{
  if(event.sender!==mainWindow?.webContents||!sourceBrowserManager||!apiClient||!isSourceBrowserId(sourceId)||typeof url!=="string")throw Error("unauthorized caller");
  const detail={...await sourceBrowserManager.readResearchJob(sourceId,url),fetched_at:new Date().toISOString()};
  return {...detail,job:workspaceId&&jobId?await apiClient.enrichSourceJob(workspaceId,jobId,detail):undefined};
});
ipcMain.handle("desktop:read-boss-detail",async(event,url:string,workspaceId?:string,jobId?:string)=>{
  if(event.sender!==mainWindow?.webContents||!sourceBrowserManager||!apiClient||typeof url!=="string")throw Error("unauthorized caller");
  try{const detail=await sourceBrowserManager.boss.readDetail(url);return {...detail,job:workspaceId&&jobId?await apiClient.enrichBossJob(workspaceId,jobId,detail):undefined};}catch(error){const failure=sourceBrowserManager.boss.paused;if(failure){await apiClient.recordSourceRuntimeFailure("boss",failure,"BOSS 已暂停，请在平台原页处理");mainWindow?.webContents.send("desktop:source-status-changed");}throw error;}
});
ipcMain.handle("desktop:layout-source-browser", (event, bounds: SourceBrowserBounds | null) => {
  if (event.sender !== mainWindow?.webContents) throw new Error("unauthorized caller");
  sourceBrowserManager?.layout(bounds);
});
ipcMain.handle("desktop:source-browser-command", (event, command: string) => {
  if (event.sender !== mainWindow?.webContents || !["back", "forward", "reload", "state", "zoom-in", "zoom-out", "zoom-reset", "fit-width"].includes(command)) throw new Error("unauthorized browser command");
  return sourceBrowserManager?.command(command);
});
ipcMain.handle("desktop:select-browser-tab", (event,id:string) => {
  if(event.sender!==mainWindow?.webContents || !sourceBrowserManager)throw new Error("unauthorized caller");
  return sourceBrowserManager.selectTab(id);
});
ipcMain.handle("desktop:navigate-browser-tab", (event,id:string,url:string) => {
  if(event.sender!==mainWindow?.webContents || !sourceBrowserManager || typeof id!=="string" || typeof url!=="string")throw new Error("unauthorized browser navigation");
  return sourceBrowserManager.navigateTab(id,url);
});
ipcMain.handle("desktop:close-browser-tab", (event,id:string) => {
  if(event.sender!==mainWindow?.webContents || !sourceBrowserManager)throw new Error("unauthorized caller");
  return sourceBrowserManager.closeTab(id);
});
ipcMain.handle("desktop:close-source-browser", (event) => {
  if (!mainWindow || event.sender !== mainWindow.webContents) return;
  sourceBrowserManager?.hide();
});
ipcMain.handle("desktop:open-job-original", async (event, sourceId: string, url: string, bounds: SourceBrowserBounds) => {
  if (!mainWindow || event.sender !== mainWindow.webContents || !sourceBrowserManager) throw new Error("source browser is not available");
  if (sourceId !== "web" && !isSourceBrowserId(sourceId)) throw new Error("unknown source browser");
  await sourceBrowserManager.show(sourceId, bounds, url || undefined);
});
ipcMain.handle("desktop:get-resume-state", () => {
  if (!apiClient) throw new Error("desktop API is not ready");
  return apiClient.resumeState();
});
ipcMain.handle("desktop:import-resume", async () => {
  if (!apiClient || !mainWindow) throw new Error("desktop API is not ready");
  const selection = await dialog.showOpenDialog(mainWindow, {
    title: "选择简历",
    properties: ["openFile"],
    filters: [{ name: "简历", extensions: ["pdf", "docx", "md", "txt"] }],
  });
  if (selection.canceled || !selection.filePaths[0]) return undefined;
  return apiClient.importResume(selection.filePaths[0]);
});
ipcMain.handle("desktop:confirm-resume", (_event, input: ResumeConfirmation) => {
  if (!apiClient) throw new Error("desktop API is not ready");
  return apiClient.confirmResume(input);
});
ipcMain.handle("desktop:abandon-resume", (_event, workspaceId: string, profileId: string) => {
  if (!apiClient) throw new Error("desktop API is not ready");
  return apiClient.abandonResume(workspaceId, profileId);
});
ipcMain.handle("desktop:analysis-preview", (_event, input) => {
  if (!apiClient) throw new Error("desktop API is not ready");
  return apiClient.previewAnalysisCopy(input);
});
ipcMain.handle("desktop:clear-current-resume", (_event, workspaceId:string) => {
  if (!apiClient) throw new Error("desktop API is not ready");
  return apiClient.clearCurrentResume(workspaceId);
});
ipcMain.handle("desktop:get-search-preferences", (_event, workspaceId:string) => {
  if (!apiClient) throw new Error("desktop API is not ready");
  return apiClient.getSearchPreferences(workspaceId);
});
ipcMain.handle("desktop:save-search-preferences", (_event, input:import("../shared/contracts").SearchPreferences) => {
  if (!apiClient) throw new Error("desktop API is not ready");
  return apiClient.saveSearchPreferences(input);
});
ipcMain.handle("desktop:list-resume-versions", (_event, workspaceId: string) => {
  if (!apiClient) throw new Error("desktop API is not ready");
  return apiClient.listResumeVersions(workspaceId);
});
ipcMain.handle("desktop:hide-resume-version", (event, workspaceId:string, versionId:string) => {
  if(event.sender!==mainWindow?.webContents||!apiClient)throw Error("unauthorized caller");
  return apiClient.hideResumeVersion(workspaceId,versionId);
});
ipcMain.handle("desktop:save-resume-version", (_event, input: ResumeEditInput) => {
  if (!apiClient) throw new Error("desktop API is not ready");
  return apiClient.saveResumeVersion(input);
});
ipcMain.handle("desktop:restore-resume-version", (_event, workspaceId: string, versionId: string) => {
  if (!apiClient) throw new Error("desktop API is not ready");
  return apiClient.restoreResumeVersion(workspaceId, versionId);
});
ipcMain.handle("desktop:export-resume", async (_event, input: ResumeExportInput) => {
  if (!apiClient || !mainWindow) throw new Error("desktop API is not ready");
  const extensions = { pdf: ["pdf"], docx: ["docx"], md: ["md"] } as const;
  const selection = await dialog.showSaveDialog(mainWindow, {
    title: "导出简历",
    defaultPath: `简历-v${input.version_id.slice(-6)}.${input.format}`,
    filters: [{ name: input.format.toUpperCase(), extensions: [...extensions[input.format]] }],
  });
  if (selection.canceled || !selection.filePath) return undefined;
  const destination = selection.filePath.endsWith(`.${input.format}`)
    ? selection.filePath : `${selection.filePath}.${input.format}`;
  return apiClient.exportResume(input, destination);
});
ipcMain.handle("desktop:list-prompt-sessions",(event,workspaceId:string)=>{if(event.sender!==mainWindow?.webContents||!apiClient)throw Error("unauthorized caller");return apiClient.listPromptSessions(workspaceId);});
ipcMain.handle("desktop:create-prompt-session", async (_event, input: PromptSessionInput) => {
  if (!apiClient) throw new Error("desktop API is not ready");
  const connection = await apiClient.modelConnection(input.connection_id);
  if (connection.status !== "verified") {
    throw new Error("请先在模型设置中完成连接测试，再开始 AI 修改。");
  }
  if (connection.auth_mode !== "none" && (!connection.credential_ref || !secretStore.has(connection.credential_ref))) {
    throw new Error("模型连接没有可用的本地 API Key。");
  }
  return apiClient.createPromptSession(input);
});
ipcMain.handle("desktop:generate-prompt-turn", async (_event, input: PromptTurnInput) => {
  if (!apiClient) throw new Error("desktop API is not ready");
  const connections = await apiClient.listModelConnections();
  const session = await apiClient.getPromptSession(input.session_id);
  const connection = connections.find((item) => item.connection_id === session.connection_id);
  const apiKey = connection?.credential_ref
    ? secretStore.get(connection.credential_ref)
    : undefined;
  if (!connection || connection.status !== "verified" || (!apiKey && connection.auth_mode !== "none")) {
    throw new Error("模型连接未验证或本地 API Key 不可用。");
  }
  promptController?.abort();
  const controller = new AbortController();
  const requestId = `resume-prompt-${randomUUID()}`;
  promptController = controller;
  promptSessionId = input.session_id;
  promptRequestId = requestId;
  try {
    return await apiClient.generatePromptTurn(input, requestId, apiKey ?? "", controller.signal);
  } catch (error) {
    if (controller.signal.aborted) {
      throw new Error("简历修改已取消；若请求已到服务商，仍可能产生用量。");
    }
    throw error;
  } finally {
    if (promptRequestId === requestId) {
      promptController = undefined;
      promptSessionId = undefined;
      promptRequestId = undefined;
    }
  }
});
ipcMain.handle("desktop:cancel-prompt-turn", async () => {
  if (!apiClient || !promptSessionId || !promptRequestId) return undefined;
  const cancelled = await apiClient.cancelPromptTurn(promptSessionId, promptRequestId);
  promptController?.abort();
  return cancelled;
});
ipcMain.handle("desktop:decide-prompt-patch", (_event, sessionId: string, patchId: string, decision: PromptPatchDecision) => {
  if (!apiClient) throw new Error("desktop API is not ready");
  return apiClient.decidePromptPatch(sessionId, patchId, decision);
});
ipcMain.handle("desktop:save-prompt-session", (_event, sessionId: string) => {
  if (!apiClient) throw new Error("desktop API is not ready");
  return apiClient.savePromptSession(sessionId);
});
ipcMain.handle("desktop:list-model-connections", async () => {
  if (!apiClient) throw new Error("desktop API is not ready");
  const connections = await apiClient.listModelConnections();
  return connections.map((connection) => ({
    ...connection,
    has_api_key: Boolean(
      connection.credential_ref && secretStore.has(connection.credential_ref),
    ),
  }));
});
ipcMain.handle("desktop:save-model-connection", async (_event, input: ModelConnectionInput) => {
  if (!apiClient) throw new Error("desktop API is not ready");
  if (input.api_key && !secretStore.isAvailable()) {
    throw new Error("系统安全存储不可用，未保存 API Key。");
  }
  return saveModelConnectionWithSecret(
    apiClient,
    secretStore,
    input,
    () => `model-secret-${randomUUID()}`,
  );
});
ipcMain.handle("desktop:test-model-connection", async (_event, connectionId: string) => {
  if (!apiClient) throw new Error("desktop API is not ready");
  const connection = await apiClient.modelConnection(connectionId);
  const apiKey = connection.credential_ref
    ? secretStore.get(connection.credential_ref)
    : undefined;
  if (!apiKey && connection.auth_mode !== "none") throw new Error("请先在系统安全存储中保存 API Key。");
  modelTestController?.abort();
  const controller = new AbortController();
  const testId = `model-test-${randomUUID()}`;
  modelTestController = controller;
  modelTestConnectionId = connectionId;
  modelTestRunId = testId;
  try {
    return await apiClient.testModelConnection(
      connectionId,
      testId,
      apiKey ?? "",
      controller.signal,
    );
  } catch (error) {
    if (controller.signal.aborted) {
      throw new Error(
        "连接测试已取消；如果服务商已收到请求，仍可能产生用量。",
      );
    }
    throw error;
  } finally {
    if (modelTestRunId === testId) {
      modelTestController = undefined;
      modelTestConnectionId = undefined;
      modelTestRunId = undefined;
    }
  }
});
ipcMain.handle("desktop:cancel-model-test", async () => {
  const connectionId = modelTestConnectionId;
  const testId = modelTestRunId;
  if (!apiClient || !connectionId || !testId) return undefined;
  const cancelled = await apiClient.cancelModelConnectionTest(connectionId, testId);
  modelTestController?.abort();
  return cancelled;
});
ipcMain.handle("desktop:secure-storage-available", () => secretStore.isAvailable());
ipcMain.handle("desktop:resolve-research-link", async (event, url: string) => {
  if (event.sender !== mainWindow?.webContents || typeof url !== "string" || url.length > 2000) throw new Error("invalid research link");
  const sourceId = Object.keys(sourceBrowserSpecs).find(id => isSourceBrowserId(id) && isAllowedSourceUrl(id, url));
  if (!sourceId || !isSourceBrowserId(sourceId)) throw new Error("仅支持已接入招聘来源的 HTTPS 链接，不接受内网、账号信息或非标准端口。");
  return {...await sourceBrowserManager!.readResearchJob(sourceId,url),message:"已自动读取岗位信息，请确认后开始研究。"};
});
ipcMain.handle("desktop:prepare-research-job", (event, input) => {
  if (event.sender !== mainWindow?.webContents || !apiClient) throw new Error("research unavailable");
  return apiClient.prepareResearchJob(input);
});
ipcMain.handle("desktop:correct-research",(event,reportId:string,input:import("../shared/contracts").ResearchCorrectionInput)=>{
  if(event.sender!==mainWindow?.webContents||!apiClient)throw Error("unauthorized caller");
  return apiClient.correctResearch(reportId,input);
});
ipcMain.handle("desktop:list-research-reports", (_event, workspaceId: string) => {
  if (!apiClient) throw new Error("desktop API is not ready");
  return apiClient.listResearchReports(workspaceId);
});
ipcMain.handle("desktop:hide-research-report", (event, workspaceId:string, reportId:string) => {
  if(event.sender!==mainWindow?.webContents||!apiClient)throw Error("unauthorized caller");
  return apiClient.hideResearchReport(workspaceId,reportId);
});
ipcMain.handle("desktop:create-research-report", async (_event, input: ResearchRunInput) => {
  if (!apiClient) throw new Error("desktop API is not ready");
  let apiKey: string | undefined;
  let requestId: string | undefined;
  if (input.connection_id) {
    const connection = await apiClient.modelConnection(input.connection_id);
    apiKey = connection.credential_ref
      ? secretStore.get(connection.credential_ref)
      : undefined;
    if (connection.status !== "verified" || (!apiKey && connection.auth_mode !== "none")) {
      throw new Error("模型连接未验证或本地 API Key 不可用。");
    }
    researchController?.abort();
    researchController = new AbortController();
    requestId = `research-${randomUUID()}`;
    researchRequestId = requestId;
    researchWorkspaceId = input.workspace_id;
  }
  try {
    return await apiClient.createResearchReport(
      input,
      requestId,
      apiKey ?? "",
      researchController?.signal,
    );
  } catch (error) {
    if (researchController?.signal.aborted) {
      throw new Error("岗位研究已取消；若服务商已收到请求，仍可能产生用量。");
    }
    throw error;
  } finally {
    if (researchRequestId === requestId) {
      researchController = undefined;
      researchRequestId = undefined;
      researchWorkspaceId = undefined;
    }
  }
});
ipcMain.handle("desktop:cancel-research", async () => {
  if (!apiClient || !researchRequestId || !researchWorkspaceId) return undefined;
  const cancelled = await apiClient.cancelResearch(
    researchRequestId,
    researchWorkspaceId,
  );
  researchController?.abort();
  return cancelled;
});
ipcMain.handle("desktop:list-scheduled-tasks", (_event, workspaceId: string) => {
  if (!apiClient) throw new Error("desktop API is not ready");
  return apiClient.listScheduledTasks(workspaceId);
});
ipcMain.handle("desktop:create-scheduled-task", (_event, input: ScheduledTaskInput) => {
  throw new Error("定时检索已停用；请使用手动岗位检索。");
});
ipcMain.handle("desktop:set-scheduled-task-paused", (_event, taskId: string, paused: boolean) => {
  if (!apiClient) throw new Error("desktop API is not ready");
  if (!paused) throw new Error("定时检索已停用；历史计划不能恢复。");
  return apiClient.setScheduledTaskPaused(taskId, paused);
});
ipcMain.handle("desktop:legacy-task-status", (_event, workspaceId: string) => {
  if (!apiClient) throw new Error("desktop API is not ready");
  return apiClient.legacyTaskStatus(workspaceId);
});

app.whenReady().then(async () => {
  if(!ownsInstance)return;
  try {
    await createWindow();
    if (shutdownPromise) return;
    apiClient = await pythonService.start();
    if (shutdownPromise) return;
    serviceStatus = {connected:true};
    mainWindow?.webContents.send("desktop:service-status", serviceStatus);
  } catch (error) {
    if (!shutdownPromise) {
      console.error("JobFindsMe failed to start", error);
      serviceStatus = {connected:false,message:"本地服务启动失败，请重启应用。"};
      mainWindow?.webContents.send("desktop:service-status", serviceStatus);
    }
  }
});

app.on("before-quit", (event) => {
  event.preventDefault();
  void shutdownAndExit();
});

app.on("activate", () => {
  if (mainWindow) mainWindow.show();
  // macOS can emit activate while the packaged Python runtime is still
  // warming up.  Do not create a renderer that can only race bootstrap.
  else if (!isQuitting && apiClient) void createWindow();
});

process.once("SIGINT", () => app.quit());
process.once("SIGTERM", () => app.quit());
