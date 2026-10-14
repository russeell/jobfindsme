/** Resume wire contracts; re-exported by contracts.ts for existing callers. */
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

export type ResumeDocumentNode = {type:string; text?:string; attrs?:Record<string,unknown>; marks?:Array<{type:string;attrs?:Record<string,unknown>}>; content?:ResumeDocumentNode[]};

export type ResumeSourceInput = {workspace_id:string;document_id:string};

export type ResumeSource = {file_name:string;media_type:string;content_base64:string;text:string};

export type ResumeVersion = {
  source_document_id?: string;
  original_file?: boolean;
  version_id: string;
  parent_version_id: string | null;
  version_number: number;
  content: ResumeContent;
  document?: ResumeDocumentNode | null;
  is_current: boolean;
  created_at: string;
};

export type ResumeEditInput = {
  workspace_id: string;
  base_version_id: string;
  content: ResumeContent;
  document?: ResumeDocumentNode | null;
};

export type ResumeExportInput = {
  workspace_id: string;
  version_id: string;
  format: "pdf" | "docx" | "md";
  template?: "classic" | "compact" | "campus" | "professional";
};

export type ResumeExport = ResumeExportInput & { path: string; template: "classic" | "compact" | "campus" | "professional" };

export type ResumeAnalysisMaterial={source_version_id:string;text:string;limitations:string};
