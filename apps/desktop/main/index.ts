import {foregroundZhilianVerification} from "./sources/source-actions";
import {checkForUpdates,releasesUrl} from "./updates";
import {normalizeDiscoveryFilters} from "../shared/discovery-filters";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { randomUUID } from "node:crypto";
import path from "node:path";

import { app, BrowserWindow, dialog, ipcMain, shell } from "electron";

import type { DesktopApiClient } from "./backend/api-client";
import { saveModelConnectionWithSecret } from "./backend/model-connection-service";
import { PythonService, type ServiceStatus } from "./backend/python-service";
import { SecureSecretStore } from "./security/secure-secret-store";
import { SourceBrowserManager } from "./browser/source-browser";
import {runSourceCheckQueue} from "./sources/source-check-queue";
import {executeBoundedSourceSearch} from "./sources/source-search-execution";
import {readIsolatedResearchPage} from "./research/browser-page";
import {ResearchRunController} from "./research/run-controller";
import {explicitReportRequest,validResearchChatInput} from "../shared/research-chat-ipc";
import { isAllowedSourceUrl, sourceBrowserSpecs, isSourceBrowserId, requiresElectronSourceSearch, summarizeSourceVerification, type SourceBrowserBounds } from "../shared/source-browser-policy";
import type {
  ModelConnectionInput, ResumeConfirmation, ResumeEditInput, ResumeExportInput,
  PromptPatchDecision, PromptSessionInput, PromptTurnInput, SourceSearchInput,
  BrowserSourcePage, ResearchRunInput, ScheduledTaskInput, SourceCapability,
  ResearchChatInput,
} from "../shared/contracts";

const packageInfo=JSON.parse(readFileSync(path.join(app.getAppPath(),"package.json"),"utf8"));
const buildLabel=String(packageInfo.build || "development");
const previewBuild=packageInfo.jobfindsmePreview===true;
const qa=previewBuild&&packageInfo.qa&&typeof packageInfo.qa==="object"?packageInfo.qa as {width:number;height:number;userData:string;captures:string}:undefined;
if(previewBuild){
  const profile = typeof packageInfo.previewUserData === "string" && /^jobfindsme-preview-[a-zA-Z0-9_-]+$/.test(packageInfo.previewUserData) ? packageInfo.previewUserData : `jobfindsme-preview-${buildLabel.split("-")[0]}`;
  if(!app.commandLine.hasSwitch("user-data-dir"))app.setPath("userData",path.join(app.getPath("appData"),profile));
  if(qa&&path.isAbsolute(qa.userData)){mkdirSync(qa.userData,{recursive:true,mode:0o700});app.setPath("userData",qa.userData);}
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
let sourceVerifyActive=false;
const sourceAutoCheckAt=new Map<string,number>();
const sourceAutoCheckPending=new Set<string>();
let researchController: AbortController | undefined;
let researchRequestId: string | undefined;
let researchWorkspaceId: string | undefined;
const chatRuns=new ResearchRunController();
let isQuitting = false;

function shutdownAndExit(): Promise<void> {
  if (shutdownPromise) return shutdownPromise;
  chatRuns.cancelCurrent();
  apiClient = undefined;
  serviceStatus = { connected: false, message: "本地服务正在退出" };
  isQuitting = true;
  shutdownPromise = Promise.allSettled([
    pythonService.stop(),
    sourceBrowserManager?.flushSessions() ?? Promise.resolve(),
  ]).then(results => {
    for (const result of results) if (result.status === "rejected") console.error("JobFindsMe shutdown failed", result.reason);
    app.exit(0);
  });
  return shutdownPromise;
}

async function createWindow(): Promise<void> {
  mainWindow = new BrowserWindow({
    title:`JobFindsMe · ${buildLabel}${isolatedProfile?" · 隔离测试":""}`,
    width: qa?.width??1240,
    height: qa?.height??820,
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

  if(qa&&path.isAbsolute(qa.captures)){
    let captureNumber=0;
    mainWindow.webContents.on("before-input-event",(event,input)=>{
      if(input.type!=="keyDown"||input.key!=="F12"||!mainWindow)return;
      event.preventDefault();
      const destination=path.join(qa.captures,`native-${String(++captureNumber).padStart(2,"0")}-${qa.width}x${qa.height}.png`);
      void mainWindow.webContents.capturePage().then(image=>{mkdirSync(qa.captures,{recursive:true,mode:0o700});writeFileSync(destination,image.toPNG());}).catch(error=>console.error("QA capture failed",error));
    });
  }

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
  sourceBrowserManager = new SourceBrowserManager(mainWindow, async (page,explicit,revisit,probeOnly) => {
    if(!apiClient)return;
    let state = page.blocked ? "risk_control" : page.loginRequired ? "login_required" : page.authenticated && page.readable ? "ready" : page.authenticated ? "logged_in" : "";
    if(!state)return;
    const current=(await apiClient.bootstrap()).sources.find(source=>source.source_id==="boss");
    const recent=current?.live_search_enabled&&current.last_verified_at&&Date.now()-Date.parse(current.last_verified_at)<600000;
    if(state===lastBossState&&!explicit&&!revisit)return;
    if(state==="ready"||state==="logged_in") {
      if(current?.session_status==="blocked" || sourceBrowserManager?.boss.paused==="risk_control")return;
      sourceBrowserManager?.boss.resume();
      if(current?.session_status!=="blocked"&&(current?.session_status!=="verified"||current.list_status!=="verified"))await apiClient.recordSourceVerification("boss",{session_status:"verified",list_status:"partial",detail_status:current?.detail_status||"unverified",fields_status:current?.fields_status||"unverified",pagination_status:current?.pagination_status||"unverified",enabled:false,notes:"当前平台页显示已登录；岗位列表和自动检索仍待单独检查。"});
      const last=sourceAutoCheckAt.get("boss")||0;
      if(!probeOnly&&!recent&&!sourceAutoCheckPending.has("boss")&&Date.now()-last>600000){
        sourceAutoCheckAt.set("boss",Date.now());sourceAutoCheckPending.add("boss");
        void (async()=>{try{
          const result=await sourceBrowserManager!.boss.collect({keyword:"工程师",city:"",maxBatches:1,seconds:10});
          if(result.collection?.failure)throw Error(`${result.collection.failure}:BOSS 有界检索未通过`);
          if(!result.records.length)throw Error("no_matching:本次未读到岗位列表");
          const summary=summarizeSourceVerification([result]);
          const latest=(await apiClient!.bootstrap()).sources.find(source=>source.source_id==="boss");
          if(latest?.session_status==="expired"||latest?.session_status==="blocked")return;
          await apiClient!.recordSourceVerification("boss",{...summary,detail_status:"unverified",pagination_status:"partial",notes:`登录后一次有界检索：${result.records.length} 条；完整 JD 与续页未验证。`});
        }catch(error){const failure=String(error);if(/risk_control:|login_required:/.test(failure))await apiClient!.recordSourceRuntimeFailure("boss",failure.includes("risk_control:")?"risk_control":"login_required",failure.slice(0,500));
          else await apiClient!.recordSourceVerification("boss",{session_status:"verified",list_status:"partial",detail_status:"unverified",fields_status:"partial",pagination_status:"unverified",enabled:false,notes:`后台有界检索未通过：${failure.slice(0,350)}`});}
        finally{sourceAutoCheckPending.delete("boss");mainWindow?.webContents.send("desktop:source-status-changed");}})();
      }
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
    } else if(page.kind==="login") {
      if(current.session_status==="blocked")return;
      if(current.session_status==="verified")await apiClient.recordSourceRuntimeFailure(sourceId,"login_required","当前平台页显示登录表单；会话可能已失效，请重新登录。");
      else await apiClient.recordSourceVerification(sourceId,{session_status:"unverified",list_status:current.list_status,detail_status:current.detail_status,fields_status:current.fields_status,pagination_status:current.pagination_status,enabled:false,notes:"当前页面显示登录表单；会话有效性与检索能力仍需分别确认。"});
    } else if(sourceId==="zhilian"&&(page.kind==="list"||page.kind==="account")) {
      // Observing an already rendered page never starts an unrelated search.
      if(current.session_status!=="blocked"&&current.list_status!=="blocked")
        await apiClient.recordSourceVerification(sourceId,foregroundZhilianVerification(current,page));
    } else if(page.kind==="list"||page.kind==="account") {
      if(current.session_status==="blocked"||current.list_status==="blocked"){
        mainWindow?.webContents.send("desktop:source-status-changed");return;
      }
      if(!page.authenticated){
        if(page.kind==="list")await apiClient.recordSourceVerification(sourceId,{session_status:"unverified",list_status:"partial",detail_status:current.detail_status,fields_status:"partial",pagination_status:"unverified",enabled:false,notes:`原页可见 ${page.cardCount} 个岗位卡片，但未确认登录身份；自动检索仍待验证。`});
        mainWindow?.webContents.send("desktop:source-status-changed");return;
      }
      const recent=current.live_search_enabled&&current.session_status==="verified"&&current.list_status==="verified"&&current.last_verified_at && Date.now()-Date.parse(current.last_verified_at)<600000;
      const verified=current.session_status==="verified"&&current.list_status==="verified";
      if(!verified)await apiClient.recordSourceVerification(sourceId,{session_status:"verified",list_status:"partial",detail_status:current.detail_status,fields_status:"partial",pagination_status:"unverified",enabled:false,notes:page.kind==="list"?`原页可见 ${page.cardCount} 个岗位卡片；自动检索尚待有界验证。`:"当前平台页显示已登录；自动检索尚待有界验证。"});
      const last=sourceAutoCheckAt.get(sourceId)||0;
      if(!sourceAutoCheckPending.has(sourceId)&&!recent&&Date.now()-last>600000){
        sourceAutoCheckAt.set(sourceId,Date.now());sourceAutoCheckPending.add(sourceId);
        void (async()=>{try{
          const result=await sourceBrowserManager!.searchPage(sourceId,{keyword:"工程师",city:"",page:1});
          const summary=summarizeSourceVerification([result]);
          const latest=(await apiClient!.bootstrap()).sources.find(source=>source.source_id===sourceId);
          if(latest?.session_status==="expired"||latest?.session_status==="blocked")return;
          await apiClient!.recordSourceVerification(sourceId,{...summary,session_status:"verified",detail_status:current.detail_status==="verified"?"verified":"unverified",pagination_status:"partial",notes:`登录后一次有界检索：${result.records.length} 条、1 个网站页。详情与网站续页仍单独待验。`});
        }catch(error){const failure=String(error);
          if(/risk_control:|login_required:/.test(failure))await apiClient!.recordSourceRuntimeFailure(sourceId,failure.includes("risk_control:")?"risk_control":"login_required",failure.slice(0,500));
          else {const latest=(await apiClient!.bootstrap()).sources.find(source=>source.source_id===sourceId);
            if(latest?.session_status!=="blocked"&&latest?.session_status!=="expired")await apiClient!.recordSourceVerification(sourceId,{session_status:"verified",list_status:"partial",detail_status:current.detail_status,fields_status:"partial",pagination_status:"unverified",enabled:false,notes:`原页有列表，后台有界检索未通过：${failure.slice(0,350)}`});}
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
  if(sourceVerifyActive)throw Error("单个平台检查进行中，请结束后再检索岗位");
  if(sourceSearchActive)throw Error("岗位检索进行中，请先停止当前检索。");
  sourceSearchActive++;
  try{
  input={...input,filters:normalizeDiscoveryFilters(input.filters)};
  return await executeBoundedSourceSearch(input,{client:apiClient,manager:sourceBrowserManager,
    getCancellationEpoch:()=>sourceSearchEpoch,
    onProgress:value=>mainWindow?.webContents.send("desktop:source-collection-progress",value),
    onSourceStatusChanged:()=>mainWindow?.webContents.send("desktop:source-status-changed")});
  }finally{sourceSearchActive--;}
});

let sourceSearchEpoch=0;
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
  if(sourceId==="zhilian")sourceBrowserManager.prepareZhilianCheck(bounds);
  else await sourceBrowserManager.show(sourceId, bounds);
});
async function probeSourceForBulk(source:SourceCapability,signal:AbortSignal,ignorePending=false):Promise<SourceCapability>{
  if(!sourceBrowserManager||!apiClient||!isSourceBrowserId(source.source_id))throw Error("source_contract_error:来源不可检查");
  const sourceId=source.source_id;
  if(!ignorePending&&sourceAutoCheckPending.has(sourceId))throw Error("source_backoff:登录后自动检查正在运行，本次不重复访问来源");
  const stop=()=>{if(sourceId==="zhilian"||sourceId==="wuyou")sourceBrowserManager?.cancelCareerSearch(sourceId);};
  if(sourceId==="boss"){
    const abort=()=>sourceBrowserManager?.boss.cancel();
    signal.addEventListener("abort",abort,{once:true});
    try{
    const page=await sourceBrowserManager.observeBoss(true,false,true);
    if(page?.blocked)throw Error("risk_control:请在应用内 BOSS 页面完成平台验证");
    if(page?.loginRequired)throw Error("login_required:请在应用内 BOSS 页面完成登录");
    // A foreground tab is optional: the bounded collector uses the same persistent session.
    const result=await sourceBrowserManager.boss.collect({keyword:"工程师",city:"",maxBatches:1,seconds:10});
    if(signal.aborted)throw Error("source_check_cancelled");
    if(result.collection?.failure)throw Error(`${result.collection.failure}:BOSS 有界检索未通过`);
    if(!result.records.length)throw Error("no_matching:本次未读取到 BOSS 岗位列表");
    const summary=summarizeSourceVerification([result]);
    return apiClient.recordSourceVerification(sourceId,{...summary,session_status:"verified",detail_status:"unverified",pagination_status:"partial",notes:`本次有界检索读取 ${result.records.length} 条；完整 JD 与续页仍待验证。`},signal);
    }catch(error){const message=String(error);
      if(!signal.aborted&&/risk_control:|login_required:/.test(message))await apiClient.recordSourceRuntimeFailure(sourceId,message.includes("risk_control:")?"risk_control":"login_required",message.slice(0,500)).catch(()=>{});
      throw error;
    }finally{signal.removeEventListener("abort",abort);}
  }
  signal.addEventListener("abort",stop,{once:true});
  try{
    let pages:BrowserSourcePage[];
    if(sourceId==="zhilian"){
      const visible=await sourceBrowserManager.waitForVisibleZhilian(signal);
      if(signal.aborted)throw Error("source_check_cancelled");
      if(!visible)throw Error("source_visible_page_required:请打开智联岗位列表；检查只读取当前页面，输入关键词后可直接尝试搜索");
      if(visible.kind==="challenge")throw Error("risk_control:当前页要求平台验证");
      if(visible.kind==="login")throw Error("login_required:当前页显示登录表单");
      return apiClient.recordSourceVerification(sourceId,foregroundZhilianVerification(source,visible),signal);
    }else if(sourceId==="wuyou"){
      const page=await sourceBrowserManager.searchPage(sourceId,{keyword:"工程师",city:"",page:1,forceRefresh:true});
      pages=[page];
    }else if(sourceId==="liepin"){
      pages=await apiClient.publicSourcePages(sourceId,{keyword:"工程师",city:"",max_pages:1,seconds:8,force_refresh:true},signal);
    }else throw Error("source_contract_error:未知招聘平台");
    if(signal.aborted)throw Error("source_check_cancelled");
    if(pages.some(page=>page.collection?.failure==="risk_control"))throw Error("risk_control:来源要求安全验证");
    if(pages.some(page=>page.collection?.failure==="login_required"))throw Error("login_required:来源要求重新登录");
    const first=pages.flatMap(page=>page.records)[0];
    if(!first)throw Error("no_matching:本次没有读取到匹配岗位；不能判定来源不可用");
    const summary=summarizeSourceVerification(pages);
    summary.session_status=source.login_required?"verified":"anonymous";
    summary.pagination_status="unverified";
    summary.notes=`本次检查仅验证 1 个列表页；JD 与网站续页未在本次重查。${summary.notes}`;
    return apiClient.recordSourceVerification(sourceId,summary,signal);
  }catch(error){
    const message=String(error);
    if(!signal.aborted&&/risk_control:|login_required:/.test(message)){
      await apiClient.recordSourceRuntimeFailure(sourceId,message.includes("risk_control:")?"risk_control":"login_required",message.slice(0,500)).catch(()=>{});
    }
    throw error;
  }finally{signal.removeEventListener("abort",stop);}
}
async function recheckPersistedSessions():Promise<void>{
  if(!apiClient||!sourceBrowserManager||isQuitting)return;
  const sources=(await apiClient.bootstrap()).sources.filter(source=>source.source_id!=="zhilian"&&requiresElectronSourceSearch(source.source_id)&&
    source.session_status==="verified"&&source.list_status!=="blocked"&&
    (!source.live_search_enabled||!source.last_verified_at||Date.now()-Date.parse(source.last_verified_at)>600000));
  for(const source of sources){
    if(!apiClient||!sourceBrowserManager||isQuitting||sourceSearchActive||sourceCheckController||sourceVerifyActive)break;
    if(sourceAutoCheckPending.has(source.source_id))continue;
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);
    sourceAutoCheckPending.add(source.source_id);sourceAutoCheckAt.set(source.source_id,Date.now());
    try{await probeSourceForBulk(source,controller.signal,true);}
    catch(error){const message=String(error);
      if(!controller.signal.aborted&&/risk_control:|login_required:/.test(message))await apiClient.recordSourceRuntimeFailure(source.source_id,message.includes("risk_control:")?"risk_control":"login_required",message.slice(0,500)).catch(()=>{});
    }finally{clearTimeout(timer);sourceAutoCheckPending.delete(source.source_id);mainWindow?.webContents.send("desktop:source-status-changed");}
  }
}
ipcMain.handle("desktop:check-all-sources",async(event,runId:string)=>{
  if(event.sender!==mainWindow?.webContents||!apiClient||!sourceBrowserManager||!/^[-a-zA-Z0-9]{8,80}$/.test(runId))throw Error("source verification is not available");
  if(sourceCheckController)throw Error("全部来源检查已在运行");
  if(sourceVerifyActive)throw Error("单个平台检查进行中，请结束后检查全部来源");
  if(sourceSearchActive)throw Error("岗位检索进行中，请结束后检查全部来源");
  const controller=new AbortController();sourceCheckController=controller;
  try{
    const sources=(await apiClient.bootstrap()).sources;
    const results=await runSourceCheckQueue({sources,signal:controller.signal,probe:probeSourceForBulk,probeUnverifiedLogin:true,
      // Only automated QA is capped; an isolated user profile is not a test run.
      maxLiveProbes:qa?1:undefined,
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
  if(sourceSearchActive)throw Error('岗位检索进行中，请结束后再检查来源');
  if(sourceVerifyActive)throw Error('单个平台检查正在运行，请稍后重试');
  sourceVerifyActive=true;
  try{
  if(sourceId==="boss"){
    const page=await sourceBrowserManager.observeBoss(true,false,true);
    if(!page?.authenticated||page.blocked||page.loginRequired)throw Error("请在应用内 BOSS 页面完成登录或平台验证后重试。");
    sourceBrowserManager.boss.resume();
    const result=await sourceBrowserManager.boss.collect({keyword:"工程师",city:"",maxBatches:1,seconds:10});
    if(result.collection?.failure){await apiClient.recordSourceRuntimeFailure("boss",result.collection.failure,result.collection.failure);throw Error(`${result.collection.failure}:BOSS 有界检索未通过`);}
    if(!result.records.length)throw Error("本次未读取到 BOSS 岗位列表；检索能力仍待验证。");
    const summary=summarizeSourceVerification([result]);
    const updated=await apiClient.recordSourceVerification("boss",{...summary,session_status:"verified",detail_status:"unverified",pagination_status:"partial",notes:`手动有界检索读取 ${result.records.length} 条；完整 JD 与续页仍待验证。`});
    mainWindow?.webContents.send("desktop:source-status-changed");
    return updated;
  }
  const current=(await apiClient.bootstrap()).sources.find(source=>source.source_id===sourceId);
  if(!current)throw Error("source_contract_error:来源记录不存在");
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8000);
  try{return await probeSourceForBulk(current,controller.signal);}
  catch(error){if(controller.signal.aborted)throw Error('source_check_timeout:单个平台检查超过 8 秒');throw error;}
  finally{clearTimeout(timer);mainWindow?.webContents.send("desktop:source-status-changed");}
  }finally{sourceVerifyActive=false;}
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
  }
  researchController?.abort();
  researchController = new AbortController();
  requestId = `research-${randomUUID()}`;
  researchRequestId = requestId;
  researchWorkspaceId = input.workspace_id;
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
ipcMain.handle("desktop:run-research-chat",async(event,input:ResearchChatInput)=>{
  if(event.sender!==mainWindow?.webContents||!apiClient)throw Error("research unavailable");
  if(!validResearchChatInput(input))throw Error("invalid research chat input");
  const run=chatRuns.begin({runId:input.request_id,sessionId:input.session_id,workspaceId:input.workspace_id},90_000);
  try{
    const workspaces=(await apiClient.bootstrap()).workspaces;
    if(run.signal.aborted)throw Error("cancelled");
    if(!workspaces.some(item=>item.workspace_id===input.workspace_id))throw Error("workspace unavailable");
    const connection=await apiClient.modelConnection(input.connection_id);
    if(run.signal.aborted)throw Error("cancelled");
    const apiKey=connection.credential_ref?secretStore.get(connection.credential_ref)||"":"";
    const {runPiResearchAgent}=await import("./research/pi-research-agent.mjs");
    if(run.signal.aborted)throw Error("cancelled");
    return await runPiResearchAgent({workspaceId:input.workspace_id,sessionId:input.session_id,requestId:input.request_id,question:input.question,research:input.research,reportRequested:explicitReportRequest(input.question),jobId:input.job_id,company:input.company,title:input.title,history:input.history},connection,apiKey,
      {
        readResume:()=>apiClient!.previewAnalysisCopy({workspace_id:input.workspace_id,privacy_mode:"redact"}),
        listSavedJobs:()=>apiClient!.listJobTracking(input.workspace_id),
        findEvidence:(company,signal,timeoutMs)=>apiClient!.findAgentEvidence(input.workspace_id,company,signal,timeoutMs),
        searchWeb:(company,searchQuery,site,originalQuestion,signal,timeoutMs)=>apiClient!.searchAgentSources({workspace_id:input.workspace_id,company,original_question:originalQuestion,search_query:searchQuery,site,timeout_ms:timeoutMs},signal,timeoutMs),
        readPage:(company,site,url,signal,timeoutMs,question)=>apiClient!.readAgentPage({workspace_id:input.workspace_id,company,site,url,question,timeout_ms:timeoutMs},signal,timeoutMs),
        readJob:(jobId,signal,timeoutMs)=>apiClient!.readAgentJob(input.workspace_id,jobId,signal,timeoutMs),
        readBrowserPage:(company,site,url,signal,timeoutMs)=>readIsolatedResearchPage(company,site,url,signal,timeoutMs),
        saveExecution:state=>apiClient!.saveAgentExecution(state),
        saveReport:state=>apiClient!.saveAgentReport(state),
      },
      delta=>{if(!run.signal.aborted&&chatRuns.current===run)event.sender.send("desktop:research-chat-delta",{request_id:input.request_id,session_id:input.session_id,workspace_id:input.workspace_id,delta});},run.signal,
      progress=>{if(!run.signal.aborted&&chatRuns.current===run)event.sender.send("desktop:research-chat-delta",{request_id:input.request_id,session_id:input.session_id,workspace_id:input.workspace_id,progress});});
  }finally{chatRuns.finish(run);}
});
ipcMain.handle("desktop:list-research-chats",async(event,workspaceId:string)=>{
  if(event.sender!==mainWindow?.webContents||!apiClient||typeof workspaceId!=="string")throw Error("research unavailable");
  return apiClient.listAgentConversations(workspaceId);
});
ipcMain.handle("desktop:list-archived-research-chats",async(event,workspaceId:string)=>{
  if(event.sender!==mainWindow?.webContents||!apiClient||typeof workspaceId!=="string")throw Error("research unavailable");
  return apiClient.listAgentConversations(workspaceId,true);
});
ipcMain.handle("desktop:save-research-chat",async(event,input:Record<string,unknown>)=>{
  if(event.sender!==mainWindow?.webContents||!apiClient||!input||typeof input.workspace_id!=="string")throw Error("research unavailable");
  await apiClient.saveAgentConversation(input);
});
for(const [channel,action] of [["archive",(workspaceId:string,id:string)=>apiClient!.archiveAgentConversation(workspaceId,id)],["restore",(workspaceId:string,id:string)=>apiClient!.restoreAgentConversation(workspaceId,id)],["delete-archived",(workspaceId:string,id:string)=>apiClient!.deleteArchivedAgentConversation(workspaceId,id)]] as const){
  ipcMain.handle(`desktop:${channel}-research-chat`,async(event,workspaceId:string,id:string)=>{
    if(event.sender!==mainWindow?.webContents||!apiClient||typeof workspaceId!=="string"||typeof id!=="string")throw Error("research unavailable");
    if(chatRuns.current?.sessionId===id&&chatRuns.current.workspaceId===workspaceId)throw Error("当前对话运行中，请先停止再整理历史");
    await action(workspaceId,id);
  });
}
ipcMain.handle("desktop:cancel-research-chat",async(event,requestId:string)=>{
  if(event.sender!==mainWindow?.webContents)throw Error("unauthorized caller");
  if(requestId)chatRuns.cancel(requestId);
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
    // One bounded check after restart for a previously verified but stale session.
    // It uses each source's persisted partition and does not run periodically.
    void recheckPersistedSessions().catch(error=>console.error("Persisted source check failed",error));
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

ipcMain.handle("desktop:check-updates",event=>{
 if(event.sender!==mainWindow?.webContents)throw Error("unauthorized caller");
 return checkForUpdates(String(packageInfo.releaseTag??""),process.platform);
});
ipcMain.handle("desktop:open-releases",async event=>{
 if(event.sender!==mainWindow?.webContents)throw Error("unauthorized caller");
 await shell.openExternal(releasesUrl);
});
