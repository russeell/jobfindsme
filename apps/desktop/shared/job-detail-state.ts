import type {DesktopBridge, SearchResultItem} from "./contracts";

export type JobDetail = Awaited<ReturnType<DesktopBridge["readSourceDetail"]>>;

export function jobDetailKey(workspace: string, job: SearchResultItem["job"]): string {
  return JSON.stringify([workspace, job.job_id, job.source.source_name, job.apply_url]);
}

/** Merge into the latest row so a late JD cannot undo a save/read action. */
export function mergeJobDetail(current: SearchResultItem, requested: SearchResultItem["job"], detail: JobDetail): SearchResultItem {
  if (jobDetailKey("", current.job) !== jobDetailKey("", requested)) return current;
  if (detail.job && detail.job.job_id !== requested.job_id) return current;
  return {
    ...current,
    job: detail.job || {...current.job, title: detail.title || current.job.title,
      company: detail.company || current.job.company,
      locations: detail.location ? [detail.location] : current.job.locations,
      description: detail.description, source: {...current.job.source, detail_level: "detail_page"}},
    score: null, details: undefined, components: {}, model_match: undefined,
    query_relevance: undefined, information_coverage: undefined, score_basis_outdated: true,
  };
}
