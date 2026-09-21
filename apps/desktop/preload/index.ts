import { contextBridge, ipcRenderer } from "electron";
import type { DesktopBridge } from "../shared/contracts";

const bridge: DesktopBridge = Object.freeze({
  matchingRules: workspaceId => ipcRenderer.invoke("desktop:matching-rules",workspaceId),
  saveMatchingRule: input => ipcRenderer.invoke("desktop:save-matching-rule",input),
  matchingTrial: input => ipcRenderer.invoke("desktop:matching-trial",input),
  matchingInput: (workspaceId,runId) => ipcRenderer.invoke("desktop:matching-input",workspaceId,runId),
  rerankMatching: (workspaceId,runId) => ipcRenderer.invoke("desktop:rerank-matching",workspaceId,runId),
  cancelMatching: () => ipcRenderer.invoke("desktop:cancel-matching"),
  previewMatching: (input) => ipcRenderer.invoke("desktop:preview-matching",input),
  getBootstrap: () => ipcRenderer.invoke("desktop:get-bootstrap"),
  runSourceSearch: (input) => ipcRenderer.invoke("desktop:run-source-search", input),
  refilterSearch:(workspaceId,runId,filters,pageSize)=>ipcRenderer.invoke("desktop:refilter-search",workspaceId,runId,filters,pageSize),
  getSearchPage: (workspaceId, runId, page, pageSize) => ipcRenderer.invoke("desktop:get-search-page", workspaceId, runId, page, pageSize),
  setJobTracking: (input) => ipcRenderer.invoke("desktop:set-job-tracking", input),
  listJobTracking: (workspaceId) => ipcRenderer.invoke("desktop:list-job-tracking", workspaceId),
  openSourceBrowser: (sourceId, bounds) => ipcRenderer.invoke("desktop:open-source-browser", sourceId, bounds),
  onSourceStatusChanged: listener => {const handler=()=>listener();ipcRenderer.on("desktop:source-status-changed",handler);return ()=>ipcRenderer.removeListener("desktop:source-status-changed",handler);},
  onSourceCollectionProgress: listener => {const handler=(_event:Electron.IpcRendererEvent,progress:Parameters<typeof listener>[0])=>listener(progress);ipcRenderer.on("desktop:source-collection-progress",handler);return ()=>ipcRenderer.removeListener("desktop:source-collection-progress",handler);},
  cancelSourceSearch:()=>ipcRenderer.invoke("desktop:cancel-source-search"),
  readSourceDetail:(sourceId,url,workspaceId,jobId)=>ipcRenderer.invoke("desktop:read-source-detail",sourceId,url,workspaceId,jobId),
  readBossDetail:(url,workspaceId,jobId)=>ipcRenderer.invoke("desktop:read-boss-detail",url,workspaceId,jobId),
  verifySource: (sourceId) => ipcRenderer.invoke("desktop:verify-source", sourceId),
  openJobOriginal: (sourceId, url, bounds) => ipcRenderer.invoke("desktop:open-job-original", sourceId, url, bounds),
  layoutSourceBrowser: (bounds) => ipcRenderer.invoke("desktop:layout-source-browser", bounds),
  sourceBrowserCommand: (command) => ipcRenderer.invoke("desktop:source-browser-command", command),
  selectBrowserTab: (id) => ipcRenderer.invoke("desktop:select-browser-tab",id),
  navigateBrowserTab: (id,url) => ipcRenderer.invoke("desktop:navigate-browser-tab",id,url),
  closeBrowserTab: (id) => ipcRenderer.invoke("desktop:close-browser-tab",id),
  closeSourceBrowser: () => ipcRenderer.invoke("desktop:close-source-browser"),
  getResumeState: () => ipcRenderer.invoke("desktop:get-resume-state"),
  chooseAndImportResume: () => ipcRenderer.invoke("desktop:import-resume"),
  confirmResume: (input) => ipcRenderer.invoke("desktop:confirm-resume", input),
  abandonResume: (workspaceId, profileId) => ipcRenderer.invoke("desktop:abandon-resume", workspaceId, profileId),
  previewAnalysisCopy: (input) => ipcRenderer.invoke("desktop:analysis-preview", input),
  listResumeVersions: (workspaceId) => ipcRenderer.invoke("desktop:list-resume-versions", workspaceId),
  saveResumeVersion: (input) => ipcRenderer.invoke("desktop:save-resume-version", input),
  restoreResumeVersion: (workspaceId, versionId) => ipcRenderer.invoke("desktop:restore-resume-version", workspaceId, versionId),
  exportResume: (input) => ipcRenderer.invoke("desktop:export-resume", input),
  listPromptSessions:workspaceId=>ipcRenderer.invoke("desktop:list-prompt-sessions",workspaceId),
  createPromptSession: (input) => ipcRenderer.invoke("desktop:create-prompt-session", input),
  generatePromptTurn: (input) => ipcRenderer.invoke("desktop:generate-prompt-turn", input),
  cancelPromptTurn: () => ipcRenderer.invoke("desktop:cancel-prompt-turn"),
  decidePromptPatch: (sessionId, patchId, decision) => ipcRenderer.invoke("desktop:decide-prompt-patch", sessionId, patchId, decision),
  savePromptSession: (sessionId) => ipcRenderer.invoke("desktop:save-prompt-session", sessionId),
  listModelConnections: () => ipcRenderer.invoke("desktop:list-model-connections"),
  saveModelConnection: (input) => ipcRenderer.invoke("desktop:save-model-connection", input),
  testModelConnection: (connectionId) => ipcRenderer.invoke("desktop:test-model-connection", connectionId),
  cancelModelTest: () => ipcRenderer.invoke("desktop:cancel-model-test"),
  resolveResearchLink: (url) => ipcRenderer.invoke("desktop:resolve-research-link", url),
  prepareResearchJob: (input) => ipcRenderer.invoke("desktop:prepare-research-job", input),
  correctResearch:(reportId,input)=>ipcRenderer.invoke("desktop:correct-research",reportId,input),
  listResearchReports: (workspaceId) => ipcRenderer.invoke("desktop:list-research-reports", workspaceId),
  createResearchReport: (input) => ipcRenderer.invoke("desktop:create-research-report", input),
  cancelResearch: () => ipcRenderer.invoke("desktop:cancel-research"),
  listScheduledTasks: (workspaceId) => ipcRenderer.invoke("desktop:list-scheduled-tasks", workspaceId),
  createScheduledTask: (input) => ipcRenderer.invoke("desktop:create-scheduled-task", input),
  setScheduledTaskPaused: (taskId, paused) => ipcRenderer.invoke("desktop:set-scheduled-task-paused", taskId, paused),
  legacyTaskStatus: (workspaceId) => ipcRenderer.invoke("desktop:legacy-task-status", workspaceId),
  secureStorageAvailable: () => ipcRenderer.invoke("desktop:secure-storage-available"),
  getServiceStatus: () => ipcRenderer.invoke("desktop:get-service-status"),
  onSourceBrowserFocus: listener => {
    const handler=()=>listener();
    ipcRenderer.on("desktop:source-browser-focused",handler);
    return ()=>ipcRenderer.removeListener("desktop:source-browser-focused",handler);
  },
  onServiceStatus: (listener) => {
    const handler = (
      _event: Electron.IpcRendererEvent,
      status: Parameters<typeof listener>[0],
    ) => listener(status);
    ipcRenderer.on("desktop:service-status", handler);
    return () => ipcRenderer.removeListener("desktop:service-status", handler);
  },
});

contextBridge.exposeInMainWorld("jobfindsme", bridge);
