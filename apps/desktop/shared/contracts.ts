export type MatchingRuleInput = {workspace_id:string;name:string;prompt:string;template_id:string;mode:"local"|"model";connection_id?:string|null;candidate_limit:number;weights:MatchingWeights};
export type MatchingRule = MatchingRuleInput & {rule_version_id:string;created_at:string;model_snapshot?:{model_id:string;endpoint:string;protocol:string;credential_ref?:string|null;auth_mode:string}};
export type MatchingRuleState = {templates:Array<{id:string;name:string;prompt:string}>;active_rule_id:string|null;versions:MatchingRule[]};
export type MatchingInput = {rule:MatchingRule;payload:{instructions:string;resume:string;candidates:Array<{job_id:string;title:string;jd:string}>}};
export type RerankResult = {status:"complete"|"skipped"|"cancelled"|"failed";message:string;page?:SearchResultPage};
export type MatchingWeights = Record<"skills" | "projects" | "education" | "experience", number>;
export type ScoreDetails = Record<string,{weight:number;ratio:number;points:number;status:"known" | "unknown";explanation:string}>;
export type MatchingPreview = {job_id:string;resume_version_id:string|null;score:number;coverage:number;components:Record<string,number>;details:ScoreDetails;scoring_version:string};
export type SourceCapability = {
  source_id: string;
  source_type: "platform" | "company";
  name: string;
  login_required: boolean;
  live_search_enabled: boolean;
  session_status: string;
  list_status: string;
  detail_status: string;
  fields_status: string;
  pagination_status: string;
  status: string;
  detail: string;
  last_verified_at: string | null;
};

export type SourceCheckResult = {
  source: SourceCapability;
  outcome: "verified_now" | "cached_recent" | "skipped_cooldown" | "login_required" | "risk_control" | "unverified" | "failed" | "not_checked_budget" | "cancelled";
  evidence: "live" | "cache" | "history" | "none";
  attempted_at: string | null;
  detail: string;
  duration_ms: number;
};

export type BootstrapData = {
  product: string;
  workspaces: Array<{ workspace_id: string; name: string }>;
  sources: SourceCapability[];
};

export type DesktopBridge = {
  matchingRules(workspaceId:string):Promise<MatchingRuleState>;
  saveMatchingRule(input:MatchingRuleInput):Promise<MatchingRule>;
  deleteMatchingRule(workspaceId:string,ruleVersionId:string):Promise<void>;
  matchingTrial(input:{workspace_id:string;job_id:string;rule_version_id:string}):Promise<SearchResultPage>;
  matchingInput(workspaceId:string,runId:string):Promise<MatchingInput>;
  rerankMatching(workspaceId:string,runId:string):Promise<RerankResult>;
  cancelMatching():Promise<void>;

  previewMatching(input:{workspace_id:string;job_id:string;weights:MatchingWeights}):Promise<MatchingPreview>;
  getBootstrap(): Promise<BootstrapData>;
  runSourceSearch(input: SourceSearchInput): Promise<SourceSearchResponse>;
  refilterSearch(workspaceId:string,runId:string,filters:SearchFilters,pageSize:number):Promise<SearchResultPage>;
  getSearchPage(workspaceId: string, runId: string, page: number, pageSize: number): Promise<SearchResultPage>;
  setJobTracking(input: JobTrackingInput): Promise<JobTrackingState>;
  listJobTracking(workspaceId: string): Promise<TrackedJob[]>;
  openSourceBrowser(sourceId: string, bounds: SourceBrowserBounds): Promise<void>;
  onSourceStatusChanged(listener: () => void): () => void;
  onSourceCollectionProgress(listener: (progress:SourceCollectionProgress) => void): () => void;
  cancelSourceSearch():Promise<void>;
  readBossDetail(url:string,workspaceId?:string,jobId?:string):Promise<{title:string;company:string;location?:string;salary?:string;description:string;url:string;fetched_at:string;job?:SearchResultItem["job"]}>;
  readSourceDetail(sourceId:string,url:string,workspaceId?:string,jobId?:string):Promise<{title:string;company:string;location?:string;salary?:string;description:string;url:string;fetched_at:string;job?:SearchResultItem["job"]}>;
  verifySource(sourceId: string): Promise<SourceCapability>;
  checkAllSources(runId:string):Promise<SourceCheckResult[]>;
  cancelAllSourceChecks():Promise<void>;
  onSourceCheckProgress(listener:(value:{runId:string;result:SourceCheckResult;done:number;total:number})=>void):()=>void;
  openJobOriginal(sourceId: string, url: string, bounds: SourceBrowserBounds): Promise<void>;
  selectBrowserTab(id:string):Promise<SourceBrowserState>;
  navigateBrowserTab(id:string,url:string):Promise<SourceBrowserState>;
  closeBrowserTab(id:string):Promise<SourceBrowserState>;
  closeSourceBrowser(): Promise<void>;
  layoutSourceBrowser(bounds: SourceBrowserBounds | null): Promise<void>;
  sourceBrowserCommand(command: "back" | "forward" | "reload" | "state" | "zoom-in" | "zoom-out" | "zoom-reset" | "fit-width"): Promise<SourceBrowserState>;
  getResumeState(): Promise<ResumeState>;
  chooseAndImportResume(): Promise<ResumeDraft | undefined>;
  confirmResume(input: ResumeConfirmation): Promise<ResumeState>;
  abandonResume(workspaceId: string, profileId: string): Promise<ResumeState>;
  previewAnalysisCopy(input: AnalysisPreviewInput): Promise<AnalysisPreview>;
  listResumeVersions(workspaceId: string): Promise<ResumeVersion[]>;
  hideResumeVersion(workspaceId:string,versionId:string):Promise<void>;
  saveResumeVersion(input: ResumeEditInput): Promise<ResumeVersion>;
  restoreResumeVersion(workspaceId: string, versionId: string): Promise<ResumeVersion>;
  exportResume(input: ResumeExportInput): Promise<ResumeExport | undefined>;
  listPromptSessions(workspaceId:string):Promise<PromptSession[]>;
  createPromptSession(input: PromptSessionInput): Promise<PromptSession>;
  generatePromptTurn(input: PromptTurnInput): Promise<PromptSession>;
  cancelPromptTurn(): Promise<PromptSession | undefined>;
  decidePromptPatch(sessionId: string, patchId: string, decision: PromptPatchDecision): Promise<PromptSession>;
  savePromptSession(sessionId: string): Promise<ResumeVersion>;
  listModelConnections(): Promise<ModelConnection[]>;
  saveModelConnection(input: ModelConnectionInput): Promise<ModelConnection>;
  testModelConnection(connectionId: string): Promise<ModelConnection>;
  cancelModelTest(): Promise<ModelConnection | undefined>;
  resolveResearchLink(url: string): Promise<{title:string;company:string;description: string;url:string; message: string}>;
  prepareResearchJob(input: {workspace_id:string; url:string; title:string; company:string; description:string}): Promise<SearchResultItem["job"]>;
  correctResearch(reportId:string,input:ResearchCorrectionInput):Promise<ResearchReport>;
  listResearchReports(workspaceId: string): Promise<ResearchReport[]>;
  hideResearchReport(workspaceId:string,reportId:string):Promise<void>;
  createResearchReport(input: ResearchRunInput): Promise<ResearchReport>;
  cancelResearch(): Promise<ResearchReport | undefined>;
  listScheduledTasks(workspaceId: string): Promise<ScheduledTask[]>;
  createScheduledTask(input: ScheduledTaskInput): Promise<ScheduledTask>;
  setScheduledTaskPaused(taskId: string, paused: boolean): Promise<ScheduledTask>;
  legacyTaskStatus(workspaceId: string): Promise<LegacyTaskStatus>;
  secureStorageAvailable(): Promise<boolean>;
  getServiceStatus(): Promise<ServiceStatus>;
  onSourceBrowserFocus(listener:()=>void):()=>void;
  onServiceStatus(listener: (status: ServiceStatus) => void): () => void;
};

export type SourceBrowserTab = {id:string;sourceId:string;url:string;title:string;loading:boolean;error?:string};
export type SourceBrowserState = {fitting?:boolean;url:string;canGoBack:boolean;canGoForward:boolean;loading:boolean;activeTabId:string|null;tabs:SourceBrowserTab[];notice:string;zoom:number};
export type SourceBrowserBounds = { x: number; y: number; width: number; height: number };

export type SourceCollectionProgress = {stage:"queued"|"loading"|"listing"|"details"|"cached"|"done";count:number;message:string;titles?:string[]};
export type SourceSearchInput = {
  boss_cursor?:string;
  workspace_id: string;
  intent: string;
  source_ids: string[];
  city?: string;
  max_pages?: number;
  time_budget_seconds?: number;
  filters?: SearchFilters;
  weights?: MatchingWeights;
  page_size?: 10 | 20 | 50;
};

export type BrowserSourcePage = {
  collection?: {batches:number;elapsed_seconds:number;stop_reason:string;cursor:string|null;complete:boolean;failure:"risk_control"|"login_required"|null};
  records: Array<{
    external_id: string;
    source_name: string;
    source_url: string;
    payload: Record<string, unknown>;
  }>;
  next_cursor: string | null;
};

export type SourceSearchExecutionInput = SourceSearchInput & {
  resume_version_id?: string;
  rule_version_id?: string;
  browser_pages?: Record<string, BrowserSourcePage[]>;
  browser_errors?: Record<string, string>;
};

export type SourceSearchPreflight = {
  workspace_id: string;
  resume_version_id: string | null;
  keywords: string[];
  allowed_source_ids: string[];
  blocked_sources: Record<string, string>;
  max_pages: number;
  time_budget_seconds: number;
};

export type SearchFilters = {
  cities?: string[];
  salary_min_k?: number;
  salary_max_k?: number;
  salary_mode?: "overlap" | "contained";
  recruitment_track?: "campus" | "social";
  employment_type?: "full_time" | "internship" | "part_time" | "contract";
  experience_min_years?: number;
  experience_max_years?: number;
  source_names?: string[];
  read?: "any" | "read" | "unread";
  unknown_policy?: "include" | "exclude" | "only";
};

export type JobTrackingState = { read: boolean; saved: boolean; applied: boolean };
export type JobTrackingInput = {
  workspace_id: string;
  job_id: string;
  event_type: "read" | "saved" | "applied" | "apply_opened";
  enabled?: boolean;
};
export type TrackedJob = { job: SearchResultItem["job"]; tracking: JobTrackingState };

export type SearchResultItem = {
  job: {
    job_id: string; title: string; company: string; description: string;
    locations: string[]; salary_min_k: number | null; salary_max_k: number | null;
    experience_min_years: number | null; experience_max_years: number | null;
    recruitment_track: string; employment_type: string; apply_url: string;
    source: { source_name: string; liveness: string; detail_level?:string };
  };
  model_match?:{score:number|null;evidence:Array<{resume_quote:string;jd_quote:string}>;unknowns:string[]};
  local_score?:number;
  score: number;
  components: Record<string, number>;
  details?: ScoreDetails;
  scoring_version?: string;
  coverage: number;
  tracking: JobTrackingState;
};

export type SearchResultPage = {
  rerank?:{candidate_count:number;scored_count:number;total:number;model:string}|null;
  run_id: string;
  resume_version_id: string | null;
  rule_version_id: string;
  page: number;
  page_size: 10 | 20 | 50;
  total: number;
  page_count: number;
  items: SearchResultItem[];
};

export type SourceSearchRun = {
  source_id: string;
  status: "success" | "partial" | "failed";
  pages_fetched: number;
  elapsed_seconds: number;
  coverage_status: string;
  can_continue: boolean;
  next_cursor: string | null;
  stop_reason: string;
  error: string | null;
};

export type SourceSearchResponse = {
  source_diagnostics?: {started_at:string;first_source_ms:number|null;sources:Record<string,{elapsed_ms:number;records:number;site_pages:number;read_at:string;status:string}>};
  workspace_id: string;
  resume_version_id: string | null;
  keywords: string[];
  allowed_source_ids: string[];
  blocked_sources: Record<string, string>;
  max_pages: number;
  time_budget_seconds: number;
  jobs: Array<{
    source_id: string;
    source_name: string;
    external_id: string;
    payload: Record<string, unknown>;
  }>;
  source_runs: SourceSearchRun[];
  result_page: SearchResultPage;
};

export type ResumeFact = {
  fact_id: string;
  fact_type: string;
  value: string;
  status: string;
};

export type ResumeDraft = {
  profile_id: string;
  document_id: string;
  status: string;
  file_name: string;
  facts: ResumeFact[];
  workspace_id: string;
};

export type ResumeState = {
  workspace_id: string | null;
  pending_confirmation: boolean;
  current_version_id: string | null;
  current_version_number: number | null;
  search_profile_state: "no_resume" | "pending_confirmation" | "ready";
  search_block_reason: string | null;
  active_draft: ResumeDraft | null;
  capabilities: {
    supported_formats: string[];
    doc_status: string;
    ocr_status: string;
    detail: string;
  };
};

export type ResumeConfirmation = {
  workspace_id: string;
  profile_id: string;
  accepted_fact_ids: string[];
  corrections: Record<string, string>;
};

export type AnalysisPreviewInput = {
  workspace_id: string;
  privacy_mode?: "redact" | "keep";
  redacted_fields?: string[];
};

export type AnalysisPreview = {
  source_version_id: string;
  redacted_fields: string[];
  text: string;
  limitations: string;
};

export type ResumeContent = Record<
  "basic_information" | "education" | "experience" | "projects" | "skills",
  string[]
>;

export type ResumeVersion = {
  version_id: string;
  parent_version_id: string | null;
  version_number: number;
  content: ResumeContent;
  is_current: boolean;
  created_at: string;
};

export type ResumeEditInput = {
  workspace_id: string;
  base_version_id: string;
  content: ResumeContent;
};

export type ResumeExportInput = {
  workspace_id: string;
  version_id: string;
  format: "pdf" | "docx" | "md";
  template: "classic" | "compact";
};

export type ResumeExport = ResumeExportInput & { path: string };

export type PromptSessionInput = {
  target_title?:string;
  target_url?:string;
  target_jd?:string;
  workspace_id: string;
  base_version_id: string;
  connection_id: string;
};

export type PromptPatchDecision = "accepted" | "rejected" | "proposed";

export type PromptPatch = {
  patch_id: string;
  turn_number: number;
  section: keyof ResumeContent;
  before: string[];
  after: string[];
  rationale: string;
  evidence_ids: string[];
  needs_user_input: string[];
  status: PromptPatchDecision;
};

export type PromptSession = PromptSessionInput & {
  messages: Array<{turn_number:number;user_prompt:string;project_facts:string[];created_at:string}>;
  saved_version_id?:string|null;
  session_id: string;
  status: "active" | "saved" | "cancelled";
  patches: PromptPatch[];
};

export type PromptTurnInput = {
  session_id: string;
  prompt: string;
  project_facts: string[];
  optional_jd?: string;
  redacted_fields?: string[];
};

export type ModelProtocol = "openai_compatible" | "anthropic" | "gemini";

export type ModelConnectionInput = {
  connection_id?: string;
  provider: string;
  protocol: ModelProtocol;
  endpoint: string;
  model_id: string;
  auth_mode?: "api_key" | "none";
  api_key?: string;
  credential_ref?: string | null;
};

export type ModelConnection = Omit<ModelConnectionInput, "api_key"> & {
  connection_id: string;
  status: "unverified" | "testing" | "verified" | "failed" | "cancelled";
  last_error: string | null;
  last_tested_at: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  has_api_key?: boolean;
};

export type ServiceStatus = {
  connected: boolean;
  message?: string;
};

export type ResearchDirection = "role" | "workload" | "salary" | "leave" | "care";
export type ResearchCorrectionInput = {workspace_id:string;evidence_id:string;kind:"wrong_entity"|"broken_link"|"wrong_team"|"other";note:string};
export type ResearchEvidence = {
  context?: {link_status?:"reachable"|"broken"|"unavailable"|"unknown";role?:string|null;level?:string|null;region?:string|null;company_match?:string;research_topic?:"company"|"job"|null;search_angle?:"positive"|"negative"|null};
  evidence_id: string;
  url: string | null;
  platform: string;
  published_at: string | null;
  retrieved_at: string;
  company: string;
  team: string | null;
  excerpt: string;
  evidence_kind: "public_source" | "user_excerpt";
  verification_status: "independently_retrieved" | "user_supplied_unverified";
  relevance: "company" | "team" | "role";
  limitations: string;
};

export type ResearchReport = {
  version_number?:number;
  canonical_url?:string;
  outcome?:"complete"|"partial"|"failed"|"no_evidence";
  job_snapshot?:SearchResultItem["job"];
  job_context?: {title?:string;company?:string;description?:string;interest_question?:string|null;research_topics?:Array<"company"|"job">;url?:string;team?:string|null;locations?:string[];supplemented_by_user?:boolean};
  directions?: ResearchDirection[];
  disclaimer?: string;
  corrections?: Array<ResearchCorrectionInput & {correction_id:string;created_at:string}>;
  report_id: string;
  workspace_id: string;
  job_id: string;
  resume_version_id: string | null;
  status: "complete" | "limited";
  jd_facts: string[];
  resume_observations: string[];
  project_rewrites: string[];
  interview_topics: string[];
  model_connection_id: string | null;
  model_status: "not_requested" | "complete" | "failed" | "cancelled";
  limitations: string[];
  evidence: ResearchEvidence[];
  created_at: string;
};

export type ResearchRunInput = {
  topics?:Array<"company"|"job">;
  context_company?:string;
  context_description?:string;
  interest_question?:string;
  directions?: ResearchDirection[];
  workspace_id: string;
  job_id: string;
  resume_version_id?: string;
  team?: string;
  source_ids: string[];
  user_evidence?: Array<{
    url?: string;
    platform?: string;
    published_at?: string;
    excerpt: string;
    relevance?: "company" | "team" | "role";
  }>;
  connection_id?: string;
};

export type ScheduledTask = {
  task_id: string;
  workspace_id: string;
  name: string;
  intent: string;
  source_ids: string[];
  filters: SearchFilters;
  resume_version_id: string;
  rule_version_id: string;
  frequency: "interval" | "daily" | "weekly";
  local_time: string | null;
  weekday: number | null;
  interval_minutes: number | null;
  timezone: string;
  catch_up_policy: "once" | "skip";
  status: "active" | "paused";
  next_run_at: string;
  last_error: string | null;
};

export type ScheduledTaskInput = {
  workspace_id: string;
  name: string;
  intent: string;
  source_ids: string[];
  filters?: SearchFilters;
  weights?: MatchingWeights;
  frequency: "interval" | "daily" | "weekly";
  local_time?: string;
  weekday?: number;
  interval_minutes?: number;
  timezone: string;
  catch_up_policy: "once" | "skip";
};

export type LegacyTaskStatus = {
  legacy_monitor_count: number;
  migration_status: "none" | "requires_reconfiguration";
  detail: string;
};

export type TaskNotification = {
  notification_id: string;
  title: string;
  body: string;
};
