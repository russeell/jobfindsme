export type SourceBrowserId = "boss" | "liepin" | "zhilian" | "wuyou";

export type SourceBrowserBounds = {
  x: number;
  y: number;
  width: number;
  height: number;

};

export const sourceBrowserSpecs: Record<SourceBrowserId, {
  loginUrl: string;
  homeUrl?: string;
  allowedHosts: string[];
  partition: string;
  allowedPaths?: string[];
}> = {
  boss: {
    loginUrl: "https://www.zhipin.com/web/user/?ka=header-login",
    allowedHosts: ["zhipin.com"],
    partition: "persist:jobfindsme-source-boss",
  },
  liepin: {
    loginUrl: "https://www.liepin.com/login/",
    homeUrl: "https://www.liepin.com/",
    allowedHosts: ["liepin.com"],
    partition: "persist:jobfindsme-source-liepin",
  },
  zhilian: {
    homeUrl: "https://www.zhaopin.com/jobs/",
    loginUrl: "https://passport.zhaopin.com/login?bkUrl=https%3A%2F%2Fi.zhaopin.com%2Fblank%3Fhttps%3A%2F%2Fwww.zhaopin.com%2Findex%3FvalidateCampus%3D",
    allowedHosts: ["zhaopin.com"],
    partition: "persist:jobfindsme-source-zhilian",
  },
  wuyou: {
    loginUrl: "https://login.51job.com/login.php",
    homeUrl: "https://www.51job.com/",
    allowedHosts: ["51job.com"],
    partition: "persist:jobfindsme-source-wuyou",
  },

};

const sourceBrowserNames: Record<string, SourceBrowserId> = {
  "BOSS直聘": "boss",
  "猎聘": "liepin",
  "智联招聘": "zhilian",
  "前程无忧": "wuyou",


};

export function sourceBrowserIdForSourceName(name: string): SourceBrowserId | undefined {
  return sourceBrowserNames[name];
}

export function requiresElectronSourceSearch(sourceId: string): sourceId is "boss" | "zhilian" | "wuyou" {
  return sourceId === "boss" || sourceId === "zhilian" || sourceId === "wuyou";
}

export function summarizeSourceVerification(pages: Array<{ records: Array<{ payload: Record<string, unknown> }>; next_cursor: string | null;collection?:{batches:number} }>) {
  const records = pages.flatMap((page) => page.records);
  if (!records.length) throw new Error("source_contract_error:验证检索没有返回岗位");
  const hasDetail = records.some((record) =>
    record.payload.detail_level === "detail_page" && String(record.payload.description || "").length >= 80,
  );
  const coreFields = records.every((record) =>
    Boolean(String(record.payload.title || "").trim()) &&
    Boolean(String(record.payload.company || "").trim()) &&
    Boolean(String(record.payload.url || "").trim()),
  );
  const sitePages=pages.reduce((count,page)=>count+Math.max(1,page.collection?.batches||1),0);
  const paginationVerified = sitePages > 1 || pages[0]?.next_cursor === null;
  return {
    session_status: "verified", list_status: "verified",
    detail_status: hasDetail ? "verified" : "partial",
    fields_status: coreFields ? "verified" : "partial",
    pagination_status: paginationVerified ? "verified" : "partial",
    enabled: true,
    notes: `桌面隔离会话人工触发验证：${sitePages} 页、${records.length} 条；完整详情=${hasDetail ? "是" : "否"}。`,
  };
}

// A readable result page proves list extraction, not the identity of the browser session.
export function sourceSearchVerification(
  source: {login_required:boolean;session_status:string},
  pages: Parameters<typeof summarizeSourceVerification>[0],
  authenticated=false,
) {
  const summary=summarizeSourceVerification(pages);
  const session_status=authenticated||source.session_status==="verified"?"verified":source.login_required?"unverified":"anonymous";
  return {...summary,session_status,enabled:!source.login_required||session_status==="verified"};
}

export function isSourceBrowserId(value: string): value is SourceBrowserId {
  return Object.hasOwn(sourceBrowserSpecs, value);
}

export function isAllowedSourceUrl(sourceId: SourceBrowserId, value: string): boolean {
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" || url.username || url.password || (url.port && url.port !== "443")) return false;
    if(url.hostname === "app.mokahr.com") return (sourceBrowserSpecs[sourceId].allowedPaths || []).some(path => url.pathname === path || url.pathname.startsWith(path + "/"));
    return sourceBrowserSpecs[sourceId].allowedHosts.some(
      (host) => url.hostname === host || url.hostname.endsWith(`.${host}`),
    );
  } catch {
    return false;
  }
}

export function sourceBrowserIdForUrl(value:string):SourceBrowserId|undefined {
  return (Object.keys(sourceBrowserSpecs) as SourceBrowserId[]).find(id=>isAllowedSourceUrl(id,value));
}

export function isAllowedNavigationAbort(
  sourceId: SourceBrowserId,
  targetUrl: string,
  error: unknown,
): boolean {
  const code = error && typeof error === "object" && "code" in error
    ? String((error as { code: unknown }).code)
    : "";
  return code === "ERR_ABORTED" && isAllowedSourceUrl(sourceId, targetUrl);
}

export async function confirmAllowedNavigationAfterAbort(
  sourceId: SourceBrowserId,
  targetUrl: string,
  error: unknown,
  observe: () => { url: string; loading: boolean },
  wait: () => Promise<void> = () => new Promise((resolve) => setTimeout(resolve, 100)),
  maxAttempts = 80,
): Promise<boolean> {
  if (!isAllowedNavigationAbort(sourceId, targetUrl, error)) return false;
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const state = observe();
    if (!state.loading && isAllowedSourceUrl(sourceId, state.url)) return true;
    await wait();
  }
  return false;
}

export function resolveSourceBrowserTarget(
  sourceId: SourceBrowserId,
  currentUrl: string,
  requestedUrl?: string,
): { targetUrl: string; shouldLoad: boolean } {
  if (requestedUrl && !isAllowedSourceUrl(sourceId, requestedUrl)) {
    throw new Error("job URL is outside the selected source allowlist");
  }
  const targetUrl = requestedUrl ?? sourceBrowserSpecs[sourceId].loginUrl;
  return {
    targetUrl,
    shouldLoad:
      !currentUrl ||
      !isAllowedSourceUrl(sourceId, currentUrl) ||
      Boolean(requestedUrl && currentUrl !== targetUrl),
  };
}

export function clampSourceBrowserBounds(
  requested: SourceBrowserBounds,
  windowSize: { width: number; height: number },
): SourceBrowserBounds {
  if (!Object.values(requested).every(Number.isFinite)) throw new Error("invalid browser bounds");
  const x = Math.max(0, Math.min(Math.round(requested.x), windowSize.width));
  const y = Math.max(0, Math.min(Math.round(requested.y), windowSize.height));
  return { x, y, width: Math.max(0, Math.min(Math.round(requested.width), windowSize.width - x)), height: Math.max(0, Math.min(Math.round(requested.height), windowSize.height - y)) };
}

// Foreground browsing is independent of the automation source contract above.
export type ForegroundBrowserId = SourceBrowserId | "web";
export function isPublicWebUrl(value:string):boolean {
  try {
    const url=new URL(value),host=url.hostname.toLowerCase().replace(/\.$/,"");
    if(!["http:","https:"].includes(url.protocol)||url.username||url.password)return false;
    if(host==="localhost"||host.endsWith(".localhost")||host.endsWith(".local")||host==="[::1]"||host==="[::]"||host.startsWith("[::ffff:")||host.startsWith("[ff")||/^\[(?:fc|fd|fe[89ab])/i.test(host))return false;
    const ip=host.split(".").map(Number);
    if(ip.length===4&&ip.every(n=>Number.isInteger(n)&&n>=0&&n<=255)) {
      if(ip[0]===0||ip[0]===10||ip[0]===127||ip[0]>=224||ip[0]===169&&ip[1]===254||ip[0]===172&&ip[1]>=16&&ip[1]<=31||ip[0]===192&&ip[1]===168||ip[0]===100&&ip[1]>=64&&ip[1]<=127||ip[0]===198&&[18,19].includes(ip[1])||ip[0]===192&&ip[1]===0||ip[0]===198&&ip[1]===51&&ip[2]===100||ip[0]===203&&ip[1]===0&&ip[2]===113)return false;
    }
    return !!host;
  } catch{return false;}
}
