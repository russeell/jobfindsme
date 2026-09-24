import type {MatchingRuleState,MatchingRuleInput,MatchingRule,MatchingInput,RerankResult} from "../../shared/contracts";
import type {
  AnalysisPreview,
  AnalysisPreviewInput,
  BootstrapData,
  BrowserSourcePage,
  ModelConnection,
  ModelConnectionInput,
  ResumeConfirmation,
  ResumeDraft,
  ResumeEditInput,
  ResumeExport,
  ResumeExportInput,
  ResumeState,
  ResumeVersion,
  PromptPatchDecision,
  PromptSession,
  PromptSessionInput,
  PromptTurnInput,
  SourceSearchExecutionInput,
  SourceSearchPreflight,
  SourceSearchResponse,
  SourceCapability,
  SearchResultPage,
  JobTrackingInput,
  JobTrackingState,
  TrackedJob,
  ResearchReport,
  ResearchRunInput,
  ScheduledTask,
  ScheduledTaskInput,
  LegacyTaskStatus,
  TaskNotification,
} from "../../shared/contracts";

export class DesktopApiClient {
  matchingRules(workspaceId:string):Promise<MatchingRuleState> { return this.json(`/v1/matching-rules?${new URLSearchParams({workspace_id:workspaceId})}`); }
  saveMatchingRule(input:MatchingRuleInput):Promise<MatchingRule> { return this.json("/v1/matching-rules",{method:"POST",body:JSON.stringify(input)}); }
  async deleteMatchingRule(workspaceId:string,ruleVersionId:string):Promise<void> { await this.json(`/v1/matching-rules/${encodeURIComponent(ruleVersionId)}?${new URLSearchParams({workspace_id:workspaceId})}`,{method:"DELETE"}); }
  matchingTrial(input:{workspace_id:string;job_id:string;rule_version_id:string}):Promise<SearchResultPage> { return this.json("/v1/matching-trials",{method:"POST",body:JSON.stringify(input)}); }
  matchingInput(workspaceId:string,runId:string):Promise<MatchingInput> { return this.json(`/v1/matching-input?${new URLSearchParams({workspace_id:workspaceId,run_id:runId})}`); }
  rerankMatching(input:{workspace_id:string;run_id:string;request_id:string;api_key:string}):Promise<RerankResult> { return this.json("/v1/matching-rerank",{method:"POST",body:JSON.stringify(input)},75000); }
  cancelMatching(workspaceId:string,requestId:string):Promise<void> { return this.json(`/v1/matching-cancel?${new URLSearchParams({workspace_id:workspaceId,request_id:requestId})}`,{method:"POST"}); }

  previewMatching(input:unknown) { return this.json("/v1/matching-preview",{method:"POST",body:JSON.stringify(input)}); }
  constructor(
    private readonly baseUrl: string,
    private readonly token: string,
  ) {}

  enrichBossJob(workspaceId:string,jobId:string,detail:import("../sources/boss-collector").BossDetail):Promise<import("../../shared/contracts").SearchResultItem["job"]> {
    return this.json(`/v1/jobs/${encodeURIComponent(jobId)}/boss-detail`,{method:"POST",body:JSON.stringify({workspace_id:workspaceId,...detail})});
  }
  enrichSourceJob(workspaceId:string,jobId:string,detail:import("../sources/boss-collector").BossDetail):Promise<import("../../shared/contracts").SearchResultItem["job"]> {return this.json(`/v1/jobs/${encodeURIComponent(jobId)}/source-detail`,{method:'POST',body:JSON.stringify({workspace_id:workspaceId,...detail})});}
  prepareResearchJob(input: {workspace_id:string; url:string; title:string; company:string; description:string}) {
    return this.json("/v1/research-jobs", {method:"POST",body:JSON.stringify(input)});
  }

  async health(): Promise<boolean> {
    const response = await this.request("/health");
    return response.ok;
  }

  async bootstrap(): Promise<BootstrapData> {
    const response = await this.request("/v1/bootstrap");
    if (!response.ok) {
      throw new Error(`desktop API bootstrap failed (${response.status})`);
    }
    return (await response.json()) as BootstrapData;
  }

  recordSourceRuntimeFailure(
    sourceId: string,
    failure: "login_required" | "risk_control",
    notes: string,
  ): Promise<void> {
    return this.json(`/v1/sources/${sourceId}/runtime-failure`, {
      method: "POST",
      body: JSON.stringify({ failure, notes }),
    });
  }

  recordSourceVerification(
    sourceId: string,
    input: {
      session_status: string; list_status: string; detail_status: string;
      fields_status: string; pagination_status: string; enabled: boolean; notes: string;
    },
    signal?:AbortSignal,
  ): Promise<SourceCapability> {
    return this.json(`/v1/sources/${sourceId}/verification`, {
      method: "PUT",
      body: JSON.stringify(input),
      signal,
    });
  }

  publicSourcePages(sourceId:string,input:{keyword:string;city:string;max_pages:number;seconds:number;force_refresh?:boolean},signal?:AbortSignal):Promise<BrowserSourcePage[]>{return this.json(`/v1/sources/${sourceId}/public-pages`,{method:'POST',body:JSON.stringify(input),signal},65000);}

  searchPreflight(input: SourceSearchExecutionInput): Promise<SourceSearchPreflight> {
    return this.json("/v1/search-preflight", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  runSourceSearch(input: SourceSearchExecutionInput): Promise<SourceSearchResponse> {
    return this.json("/v1/source-searches", {
      method: "POST",
      body: JSON.stringify(input),
    }, 125_000);
  }

  refilterSearch(workspaceId:string,runId:string,filters:unknown,pageSize:number):Promise<SearchResultPage>{return this.json(`/v1/search-runs/${runId}/refilter`,{method:"POST",body:JSON.stringify({workspace_id:workspaceId,filters,page_size:pageSize})});}
  getSearchPage(workspaceId: string, runId: string, page: number, pageSize: number): Promise<SearchResultPage> {
    const query = new URLSearchParams({ workspace_id: workspaceId, page: String(page), page_size: String(pageSize) });
    return this.json(`/v1/search-runs/${runId}/jobs?${query}`);
  }

  setJobTracking(input: JobTrackingInput): Promise<JobTrackingState> {
    return this.json(`/v1/jobs/${input.job_id}/events`, {
      method: "POST",
      body: JSON.stringify({ workspace_id: input.workspace_id, event_type: input.event_type, enabled: input.enabled ?? true }),
    });
  }

  listJobTracking(workspaceId: string): Promise<TrackedJob[]> {
    const query = new URLSearchParams({ workspace_id: workspaceId });
    return this.json(`/v1/job-tracking?${query}`);
  }

  async resumeState(): Promise<ResumeState> {
    return this.json("/v1/resumes/state");
  }

  async importResume(sourcePath: string): Promise<ResumeDraft> {
    const draft = await this.json<ResumeDraft>("/v1/resumes/import", {
      method: "POST",
      body: JSON.stringify({ source_path: sourcePath, mode: "managed" }),
    });
    const state = await this.resumeState();
    if (!state.workspace_id) throw new Error("简历工作区初始化失败");
    return { ...draft, workspace_id: state.workspace_id };
  }

  confirmResume(input: ResumeConfirmation): Promise<ResumeState> {
    return this.json(`/v1/resumes/${input.profile_id}/confirm`, {
      method: "POST",
      body: JSON.stringify({
        workspace_id: input.workspace_id,
        accepted_fact_ids: input.accepted_fact_ids,
        corrections: input.corrections,
      }),
    });
  }

  abandonResume(workspaceId: string, profileId: string): Promise<ResumeState> {
    const query = new URLSearchParams({ workspace_id: workspaceId });
    return this.json(`/v1/resumes/${profileId}/abandon?${query}`, {
      method: "POST",
      body: "{}",
    });
  }

  previewAnalysisCopy(input: AnalysisPreviewInput): Promise<AnalysisPreview> {
    return this.json("/v1/resumes/analysis-preview", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  clearCurrentResume(workspaceId:string):Promise<ResumeState> {return this.json("/v1/resumes/clear-current",{method:"POST",body:JSON.stringify({workspace_id:workspaceId})});}
  getSearchPreferences(workspaceId:string):Promise<import("../../shared/contracts").SearchPreferences> {return this.json(`/v1/search-preferences?${new URLSearchParams({workspace_id:workspaceId})}`);}
  saveSearchPreferences(input:import("../../shared/contracts").SearchPreferences):Promise<import("../../shared/contracts").SearchPreferences> {return this.json("/v1/search-preferences",{method:"PUT",body:JSON.stringify(input)});}

  listResumeVersions(workspaceId: string): Promise<ResumeVersion[]> {
    const query = new URLSearchParams({ workspace_id: workspaceId });
    return this.json(`/v1/resume-versions?${query}`);
  }

  hideResumeVersion(workspaceId:string,versionId:string):Promise<void> {
    const query=new URLSearchParams({workspace_id:workspaceId});
    return this.json(`/v1/resume-versions/${encodeURIComponent(versionId)}?${query}`,{method:"DELETE"});
  }

  saveResumeVersion(input: ResumeEditInput): Promise<ResumeVersion> {
    return this.json("/v1/resume-versions", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  restoreResumeVersion(workspaceId: string, versionId: string): Promise<ResumeVersion> {
    return this.json(`/v1/resume-versions/${versionId}/restore`, {
      method: "POST",
      body: JSON.stringify({ workspace_id: workspaceId }),
    });
  }

  exportResume(input: ResumeExportInput, destination: string): Promise<ResumeExport> {
    return this.json(`/v1/resume-versions/${input.version_id}/export`, {
      method: "POST",
      // version_id is a path parameter and the API rejects unknown body fields.
      body: JSON.stringify({
        workspace_id: input.workspace_id,
        destination,
        format: input.format,
        template: input.template,
      }),
    }, 20_000);
  }

  listPromptSessions(workspaceId:string):Promise<PromptSession[]> {return this.json(`/v1/resume-edit-sessions?${new URLSearchParams({workspace_id:workspaceId})}`);}
  createPromptSession(input: PromptSessionInput): Promise<PromptSession> {
    return this.json("/v1/resume-edit-sessions", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  getPromptSession(sessionId: string): Promise<PromptSession> {
    return this.json(`/v1/resume-edit-sessions/${sessionId}`);
  }

  generatePromptTurn(
    input: PromptTurnInput,
    requestId: string,
    apiKey: string,
    signal: AbortSignal,
  ): Promise<PromptSession> {
    return this.json(`/v1/resume-edit-sessions/${input.session_id}/turns`, {
      method: "POST",
      body: JSON.stringify({
        request_id: requestId,
        api_key: apiKey,
        prompt: input.prompt,
        project_facts: input.project_facts,
        optional_jd: input.optional_jd,
        redacted_fields: input.redacted_fields,
      }),
      signal,
    }, 65_000);
  }

  cancelPromptTurn(sessionId: string, requestId: string): Promise<PromptSession> {
    return this.json(`/v1/resume-edit-sessions/${sessionId}/requests/${requestId}/cancel`, {
      method: "POST",
      body: "{}",
    });
  }

  decidePromptPatch(
    sessionId: string,
    patchId: string,
    decision: PromptPatchDecision,
  ): Promise<PromptSession> {
    return this.json(`/v1/resume-edit-sessions/${sessionId}/patches/${patchId}`, {
      method: "POST",
      body: JSON.stringify({ decision }),
    });
  }

  savePromptSession(sessionId: string): Promise<ResumeVersion> {
    return this.json(`/v1/resume-edit-sessions/${sessionId}/save`, {
      method: "POST",
      body: "{}",
    });
  }

  listModelConnections(): Promise<ModelConnection[]> {
    return this.json("/v1/model-connections");
  }

  async modelConnection(connectionId: string): Promise<ModelConnection> {
    const connections = await this.listModelConnections();
    const connection = connections.find((item) => item.connection_id === connectionId);
    if (!connection) throw new Error("模型连接不存在。");
    return connection;
  }

  saveModelConnection(input: Omit<ModelConnectionInput, "api_key">): Promise<ModelConnection> {
    return this.json("/v1/model-connections", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  testModelConnection(
    connectionId: string,
    testId: string,
    apiKey: string,
    signal: AbortSignal,
  ): Promise<ModelConnection> {
    return this.json(`/v1/model-connections/${connectionId}/test`, {
      method: "POST",
      body: JSON.stringify({ test_id: testId, api_key: apiKey, timeout_seconds: 15 }),
      signal,
    }, 18_000);
  }

  cancelModelConnectionTest(connectionId: string, testId: string): Promise<ModelConnection> {
    return this.json(`/v1/model-connections/${connectionId}/tests/${testId}/cancel`, {
      method: "POST",
      body: "{}",
    });
  }

  correctResearch(reportId:string,input:import("../../shared/contracts").ResearchCorrectionInput):Promise<ResearchReport> {
    return this.json(`/v1/research-runs/${encodeURIComponent(reportId)}/corrections`,{method:"POST",body:JSON.stringify(input)});
  }
  listResearchReports(workspaceId: string): Promise<ResearchReport[]> {
    const query = new URLSearchParams({ workspace_id: workspaceId });
    return this.json(`/v1/research-runs?${query}`);
  }

  hideResearchReport(workspaceId:string,reportId:string):Promise<void> {
    const query=new URLSearchParams({workspace_id:workspaceId});
    return this.json(`/v1/research-runs/${encodeURIComponent(reportId)}?${query}`,{method:"DELETE"});
  }

  createResearchReport(
    input: ResearchRunInput,
    requestId?: string,
    apiKey?: string,
    signal?: AbortSignal,
  ): Promise<ResearchReport> {
    return this.json("/v1/research-runs", {
      method: "POST",
      body: JSON.stringify({ ...input, request_id: requestId, api_key: apiKey }),
      signal,
    }, 60_000);
  }

  cancelResearch(requestId: string, workspaceId: string): Promise<ResearchReport> {
    const query = new URLSearchParams({ workspace_id: workspaceId });
    return this.json(`/v1/research-requests/${requestId}/cancel?${query}`, {
      method: "POST",
      body: "{}",
    });
  }

  listScheduledTasks(workspaceId: string): Promise<ScheduledTask[]> {
    const query = new URLSearchParams({ workspace_id: workspaceId });
    return this.json(`/v1/tasks?${query}`);
  }

  listDueTasks(): Promise<ScheduledTask[]> {
    return this.json("/v1/tasks/due");
  }

  createScheduledTask(input: ScheduledTaskInput): Promise<ScheduledTask> {
    return this.json("/v1/tasks", { method: "POST", body: JSON.stringify(input) });
  }

  setScheduledTaskPaused(taskId: string, paused: boolean): Promise<ScheduledTask> {
    return this.json(`/v1/tasks/${taskId}/${paused ? "pause" : "resume"}`, {
      method: "POST",
      body: "{}",
    });
  }

  legacyTaskStatus(workspaceId: string): Promise<LegacyTaskStatus> {
    const query = new URLSearchParams({ workspace_id: workspaceId });
    return this.json(`/v1/tasks/legacy-status?${query}`);
  }

  runDueTasks(input: {
    matching_keys_by_task?:Record<string,string>;
    browser_pages_by_task?: Record<string, Record<string, BrowserSourcePage[]>>;
    browser_errors_by_task?: Record<string, Record<string, string>>;
  } = {}): Promise<{ runs: unknown[]; notifications: TaskNotification[] }> {
    return this.json("/v1/tasks/run-due", {
      method: "POST",
      body: JSON.stringify(input),
    }, 125_000);
  }

  markTaskNotificationDelivered(notificationId: string): Promise<void> {
    return this.json(`/v1/task-notifications/${notificationId}/delivered`, {
      method: "POST",
      body: "{}",
    });
  }

  private async json<T>(
    path: string,
    init: RequestInit = {},
    timeoutMs = 5_000,
  ): Promise<T> {
    const response = await this.request(path, init, timeoutMs);
    if (!response.ok) {
      const payload = await response.json().catch(() => ({})) as { detail?: unknown };
      throw new Error(apiErrorMessage(payload.detail, response.status));
    }
    return await response.json() as T;
  }

  private request(path: string, init: RequestInit = {}, timeoutMs = 2_000): Promise<Response> {
    const timeout = AbortSignal.timeout(timeoutMs);
    const signal = init.signal ? AbortSignal.any([init.signal, timeout]) : timeout;
    return fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.token}`,
        ...init.headers,
      },
      signal,
    });
  }
}

function apiErrorMessage(detail: unknown, status: number): string {
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail.flatMap((item) => {
      if (!item || typeof item !== "object") return [];
      const record = item as { loc?: unknown; msg?: unknown };
      if (typeof record.msg !== "string") return [];
      const location = Array.isArray(record.loc)
        ? record.loc.filter((part) => typeof part === "string" || typeof part === "number").join(".")
        : "";
      return [location ? `${location}: ${record.msg}` : record.msg];
    });
    if (messages.length) return messages.join("；");
  }
  return `desktop API request failed (${status})`;
}
