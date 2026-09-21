export type SourceBrowserId = "boss" | "liepin" | "zhilian" | "wuyou" | "company_01" | "company_02" | "company_03" | "company_04" | "company_05" | "company_06" | "company_07" | "company_08" | "company_09" | "company_10" | "company_11" | "company_12" | "company_13" | "company_14" | "company_15" | "company_16";

export type SourceBrowserBounds = {
  x: number;
  y: number;
  width: number;
  height: number;

};

export const sourceBrowserSpecs: Record<SourceBrowserId, {
  loginUrl: string;
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
    allowedHosts: ["liepin.com"],
    partition: "persist:jobfindsme-source-liepin",
  },
  zhilian: {
    loginUrl: "https://passport.zhaopin.com/login",
    allowedHosts: ["zhaopin.com"],
    partition: "persist:jobfindsme-source-zhilian",
  },
  wuyou: {
    loginUrl: "https://login.51job.com/login.php",
    allowedHosts: ["51job.com"],
    partition: "persist:jobfindsme-source-wuyou",
  },
  company_01: {
    loginUrl: "https://careers.tencent.com/",
    allowedHosts: ["careers.tencent.com"],
    partition: "persist:jobfindsme-source-company-01",
  },
  company_02: {loginUrl:"https://jobs.bytedance.com/", allowedHosts:["jobs.bytedance.com", "seed.bytedance.com"], partition:"persist:jobfindsme-source-company-02"},
  company_03: {loginUrl:"https://talent-holding.alibaba.com/?lang=zh", allowedHosts:["talent.alibaba.com", "campus-talent.alibaba.com", "talent-holding.alibaba.com"], partition:"persist:jobfindsme-source-company-03"},
  company_04: {loginUrl:"https://career.meituan.com/", allowedHosts:["career.meituan.com"], partition:"persist:jobfindsme-source-company-04"},
  company_05: {loginUrl:"https://talent.baidu.com/", allowedHosts:["talent.baidu.com"], partition:"persist:jobfindsme-source-company-05"},
  company_06: {loginUrl:"https://zhaopin.jd.com/home", allowedHosts:["zhaopin.jd.com"], partition:"persist:jobfindsme-source-company-06"},
  company_07: {loginUrl:"https://hr.163.com/", allowedHosts:["hr.163.com", "campus.163.com"], partition:"persist:jobfindsme-source-company-07"},
  company_08: {loginUrl:"https://campus.kuaishou.cn/", allowedHosts:["campus.kuaishou.cn", "zhaopin.kuaishou.cn"], partition:"persist:jobfindsme-source-company-08"},
  company_09: {loginUrl:"https://hr.xiaomi.com/website/opportunities.html", allowedHosts:["hr.xiaomi.com", "career.mi.com", "xiaomi.jobs.f.mioffice.cn"], partition:"persist:jobfindsme-source-company-09"},
  company_10: {loginUrl:"https://talent.didiglobal.com/", allowedHosts:["talent.didiglobal.com"], partition:"persist:jobfindsme-source-company-10"},
  company_11: {loginUrl:"https://careers.pddglobalhr.com/jobs", allowedHosts:["careers.pddglobalhr.com"], partition:"persist:jobfindsme-source-company-11"},
  company_12: {"loginUrl": "https://talent.deepseek.com/", "allowedHosts": ["talent.deepseek.com"], "allowedPaths": ["/social-recruitment/high-flyer/140576"], "partition": "persist:jobfindsme-source-company-12"},
  company_13: {"loginUrl": "https://vrfi1sk8a0.jobs.feishu.cn/index/", "allowedHosts": ["vrfi1sk8a0.jobs.feishu.cn", "www.minimax.cn"], "allowedPaths": [], "partition": "persist:jobfindsme-source-company-13"},
  company_14: {"loginUrl": "https://app.mokahr.com/social-recruitment/zphz/148983?locale=zh-CN#/", "allowedHosts": ["www.zhipuai.cn"], "allowedPaths": ["/social-recruitment/zphz/148983", "/campus-recruitment/zphz/148984"], "partition": "persist:jobfindsme-source-company-14"},
  company_15: {"loginUrl": "https://app.mokahr.com/apply/moonshot/148506#/jobs", "allowedHosts": ["careers.kimi.com", "careers.kimi.ai"], "allowedPaths": ["/apply/moonshot/148506"], "partition": "persist:jobfindsme-source-company-15"},
  company_16: {"loginUrl": "https://app.mokahr.com/social-recruitment/step/94904#/", "allowedHosts": ["www.stepfun.com"], "allowedPaths": ["/social-recruitment/step/94904", "/campus-recruitment/step/94905"], "partition": "persist:jobfindsme-source-company-16"},
};

const sourceBrowserNames: Record<string, SourceBrowserId> = {
  "BOSS直聘": "boss",
  "猎聘": "liepin",
  "智联招聘": "zhilian",
  "前程无忧": "wuyou",
  "腾讯": "company_01",
  "腾讯招聘官网": "company_01",
  "字节跳动": "company_02",
  "阿里巴巴": "company_03",
  "美团": "company_04",
  "百度": "company_05",
  "京东": "company_06",
  "网易": "company_07",
  "快手": "company_08",
  "小米": "company_09",
  "滴滴": "company_10",
  "拼多多": "company_11",
  "DeepSeek": "company_12",
  "MiniMax": "company_13",
  "智谱": "company_14",
  "月之暗面": "company_15",
  "阶跃星辰": "company_16",

};

export function sourceBrowserIdForSourceName(name: string): SourceBrowserId | undefined {
  return sourceBrowserNames[name];
}

export function requiresElectronSourceSearch(sourceId: string): sourceId is "boss" | "zhilian" | "wuyou" {
  return sourceId === "boss" || sourceId === "zhilian" || sourceId === "wuyou";
}

export function summarizeSourceVerification(pages: Array<{ records: Array<{ payload: Record<string, unknown> }>; next_cursor: string | null }>) {
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
  const paginationVerified = pages.length > 1 || pages[0]?.next_cursor === null;
  return {
    session_status: "verified", list_status: "verified",
    detail_status: hasDetail ? "verified" : "partial",
    fields_status: coreFields ? "verified" : "partial",
    pagination_status: paginationVerified ? "verified" : "partial",
    enabled: true,
    notes: `桌面隔离会话人工触发验证：${pages.length} 页、${records.length} 条；完整详情=${hasDetail ? "是" : "否"}。`,
  };
}

export function isSourceBrowserId(value: string): value is SourceBrowserId {
  return Object.hasOwn(sourceBrowserSpecs, value);
}

export function isAllowedSourceUrl(sourceId: SourceBrowserId, value: string): boolean {
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" || url.username || url.password || (url.port && url.port !== "443")) return false;
    // Tencent's own job detail page redirects international roles to this tenant.
    if (sourceId === "company_01" && url.hostname === "tencent.wd1.myworkdayjobs.com") return true;
    if(url.hostname === "app.mokahr.com") return (sourceBrowserSpecs[sourceId].allowedPaths || []).some(path => url.pathname === path || url.pathname.startsWith(path + "/"));
    return sourceBrowserSpecs[sourceId].allowedHosts.some(
      (host) => url.hostname === host || url.hostname.endsWith(`.${host}`),
    );
  } catch {
    return false;
  }
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
    if(host==="localhost"||host.endsWith(".localhost")||host.endsWith(".local")||host==="[::1]"||host==="[::]"||host.startsWith("[::ffff:")||/^\[(?:fc|fd|fe[89ab])/i.test(host))return false;
    const ip=host.split(".").map(Number);
    if(ip.length===4&&ip.every(n=>Number.isInteger(n)&&n>=0&&n<=255)) {
      if(ip[0]===0||ip[0]===10||ip[0]===127||ip[0]>=224||ip[0]===169&&ip[1]===254||ip[0]===172&&ip[1]>=16&&ip[1]<=31||ip[0]===192&&ip[1]===168)return false;
    }
    return !!host;
  } catch{return false;}
}
