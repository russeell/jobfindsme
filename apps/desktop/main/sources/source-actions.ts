import {zhilianListExtractionScript} from './zhilian-page';
import {bossSearchUrl} from "./boss-page";
import { isAllowedSourceUrl, type SourceBrowserId } from "../../shared/source-browser-policy";

type BrowserSearchSourceId = "boss" | "zhilian" | "wuyou";

export type ExtractedSourceJob = {
  title: string;
  company: string;
  location: string;
  salary: string;
  url: string;
};

export type SourceActionPage = {
  collection?: {batches:number;elapsed_seconds:number;stop_reason:string;cursor:string|null;complete:boolean;failure:"risk_control"|"login_required"|null};
  records: Array<{
    external_id: string;
    source_name: string;
    source_url: string;
    payload: Record<string, unknown>;
  }>;
  next_cursor: string | null;
};

const sourceNames: Record<string, string> = {
  boss: "BOSS直聘",
  liepin: "猎聘",
  zhilian: "智联招聘",
  wuyou: "前程无忧",
};

const extractionSpecs: Record<Exclude<BrowserSearchSourceId,"zhilian">, {
  cards: string[];
  title: string[];
  company: string[];
  location: string[];
  salary: string[];
  link: string[];
  next: string[];
}> = {
  boss: {
    cards: [".job-card-wrapper", ".job-list-box li", "[class*='job-card']"],
    title: [".job-name", "[class*='job-title']", "h3"],
    company: [".company-name", "[class*='company-name']"],
    location: [".job-area", "[class*='job-area']"],
    salary: [".salary", "[class*='salary']"],
    link: ["a[href*='/job_detail/']", "a[href]"],
    next: [".options-pages a.next", "[class*='pagination'] [class*='next']"],
  },
  wuyou: {
    cards: [".joblist-item", "[class*='joblist-item']", ".joblist li"],
    title: [".jname", "[class*='job-name']", "h3"],
    company: [".cname", ".company-name"],
    location: [".joblist-item-jobinfo .area", "[class*='workarea']", "[class*='location']"],
    salary: [".sal", "[class*='salary']"],
    link: ["a[href*='/job/']", "a[href*='jobs.51job.com']:not([href*='/co'])"],
    next: [".el-pagination .btn-next", "[class*='pagination'] [class*='next']", "li.next"],
  },
};

export function buildSourceSearchUrl(
  sourceId: BrowserSearchSourceId,
  keyword: string,
  city: string,
  page: number,
): string {
  if (!keyword.trim() || keyword.length > 120) throw new Error("invalid search keyword");
  if (!Number.isInteger(page) || page < 1 || page > 20) throw new Error("invalid source page");
  if(sourceId==="boss"){if(page!==1)throw Error("BOSS uses scroll continuation, not page numbers");return bossSearchUrl(keyword,city);}
  const targets = {
    boss: new URL("https://www.zhipin.com/web/geek/job"),
    zhilian: new URL("https://www.zhaopin.com/jobs/"),
    wuyou: new URL("https://we.51job.com/pc/search"),
  };
  const target = targets[sourceId];
  if (sourceId === "zhilian") {
    target.searchParams.set("kw", keyword.trim());
    target.searchParams.set("pageMode", "search");
    target.searchParams.set("jl", zhilianCityCode(city));
    target.searchParams.set("p", String(page));
  } else {
    target.searchParams.set("keyword", keyword.trim());
    if (/^\d+$/.test(city.trim())) target.searchParams.set("jobArea", city.trim());
    target.searchParams.set("pageNum", String(page));
  }
  return target.toString();
}

export function sourceListExtractionScript(
  sourceId: BrowserSearchSourceId,
): string {
  if(sourceId==="zhilian")return zhilianListExtractionScript();
  const spec = JSON.stringify(extractionSpecs[sourceId]);
  return `(() => {
    const spec = ${spec};
    const text = (document.body?.innerText || "").slice(0, 5000);
    const blocked = ["滑动验证", "安全验证", "访问过于频繁", "captcha", "请完成验证"]
      .find((marker) => text.toLowerCase().includes(marker.toLowerCase()));
    const visible=node=>{const rect=node.getBoundingClientRect?.();const style=getComputedStyle(node);return !!rect&&rect.width>0&&rect.height>0&&style.display!=='none'&&style.visibility!=='hidden'&&Number(style.opacity)!==0;};
    const loginHost=/passport\\.zhaopin\\.com|login\\.51job\\.com/.test(location.hostname);
    const loginForm=Array.from(document.querySelectorAll('input[type="password"],input[autocomplete="current-password"],input[placeholder*="验证码"]')).some(visible);
    const pick = (root, selectors) => {
      for (const selector of selectors) {
        const node = root.querySelector(selector);
        const value = (node?.textContent || "").replace(/\\s+/g, " ").trim();
        if (value) return value;
      }
      return "";
    };
    const href = (root) => {
      if (root.matches?.('a[href]')) return root.href;
      for (const selector of spec.link) {
        const node = root.querySelector(selector);
        if (node?.href) return node.href;
      }
      if (${JSON.stringify(sourceId)} === 'wuyou' && !blocked && !loginHost && !loginForm) {
        // Observed 51job code: window.open('_blank'); child.location.href=jobHref.
        // Capture only a title click's destination; never click application controls.
        const title = root.querySelector('.jname');
        if (title) {
          const original = window.open; let destination = '';
          const destinationObject = {get href(){return destination;},set href(value){destination=String(value);}};
          try {
            window.open = (url) => ({get location(){return destinationObject;},set location(value){destination=String(value);}});
            title.click();
          } finally {window.open = original;}
          if (destination) return destination;
        }
      }
      return "";
    };
    let cards = [];
    for (const selector of spec.cards) {
      cards = Array.from(document.querySelectorAll(selector));
      if (cards.length) break;
    }
    const jobs = cards.filter(visible).slice(0, 60).map((card) => ({
      title: pick(card, spec.title) || (card.matches?.('a[href]') ? (card.textContent||'').trim() : ''), company: pick(card, spec.company),
      location: pick(card, spec.location), salary: pick(card, spec.salary),
      url: href(card),
    })).filter((item) => item.title && item.url);
    let hasNext = false;
    for (const selector of spec.next) {
      const next = document.querySelector(selector);
      if (next && !next.matches("[disabled], .disabled, [aria-disabled='true']")) {
        hasNext = true; break;
      }
    }
    const searchKeyword=undefined;
    return { jobs, hasNext, searchKeyword, diagnostics:{readyState:document.readyState,visibility:document.visibilityState,cards:cards.length,visibleCards:cards.filter(visible).length}, empty:/暂无相关职位|没有找到相关职位|没有符合条件的职位/.test(text), blocked: blocked || null, loginRequired: Boolean(loginHost||loginForm) };
  })()`;
}

export function sourceDetailExtractionScript(): string {
  return `(() => {
    const selectors = ["[class*='job-detail']", "[class*='job-desc']", "[class*='job-intro']", "article", "main"];
    let best = "";
    for (const selector of selectors) {
      for (const node of document.querySelectorAll(selector)) {
        const value = (node.textContent || "").replace(/\\s+/g, " ").trim();
        if (value.length >= 80 && value.length <= 12000 && value.length > best.length) best = value;
      }
    }
    return best.slice(0, 12000);
  })()`;
}

export function sanitizeSourceActionPage(
  sourceId: BrowserSearchSourceId,
  searchUrl: string,
  page: number,
  raw: { jobs?: ExtractedSourceJob[]; hasNext?: boolean },
  details: Map<string, string> = new Map(),
): SourceActionPage {
  const records = [];
  const seen = new Set<string>();
  for (const item of raw.jobs || []) {
    if (!item || typeof item.title !== "string" || typeof item.url !== "string") continue;
    const candidateUrl=sourceId==="zhilian"?normalizeZhilianJobUrl(item.url):item.url;
    if (!candidateUrl||!isAllowedSourceUrl(sourceId, candidateUrl)) continue;
    const title = item.title.trim().slice(0, 300);
    if (!title) continue;
    const url = new URL(candidateUrl).toString();
    if(sourceId==="zhilian" && (!isZhilianJobUrl(url) || !String(item.company||"").trim()))continue;
    if(seen.has(url))continue;
    seen.add(url);
    const description = (details.get(url) || title).trim().slice(0, 12_000);
    records.push({
      external_id: `${new URL(url).pathname}:${title}`.slice(0, 500),
      source_name: sourceNames[sourceId],
      source_url: searchUrl,
      payload: {
        title,
        company: String(item.company || "").trim().slice(0, 300),
        description,
        location: String(item.location || "").trim().slice(0, 200),
        salary: String(item.salary || "").trim().slice(0, 100),
        url,
        apply_url: url,
        detail_level: details.has(url) ? "detail_page" : "list_card",
        description_source_url: details.has(url) ? url : undefined,
        description_fetched_at: details.has(url) ? new Date().toISOString() : undefined,
      },
    });
  }
  return {
    records: records.slice(0, 60),
    next_cursor: raw.hasNext ? String(page + 1) : null,
  };
}


export type PassiveSourceObservation = {
  records?:SourceActionPage["records"]; jobs?:ExtractedSourceJob[]; url:string; kind:"list"|"account"|"login"|"challenge"|"splash"|"unknown"; cardCount:number; formCount:number; authenticated:boolean;
};

// Reads the already loaded foreground document. It never clicks, navigates or searches.
export function passiveSourceObservationScript(sourceId:"zhilian"|"wuyou"):string {
  return `(() => {
    const text=(document.body?.innerText||'').slice(0,4000);
    const visible=node=>{const rect=node.getBoundingClientRect?.();const style=getComputedStyle(node);return !!rect&&rect.width>0&&rect.height>0&&style.display!=='none'&&style.visibility!=='hidden'&&Number(style.opacity)!==0;};
    let cardCount=Array.from(document.querySelectorAll(${JSON.stringify(sourceId)}==='wuyou'
      ? '.joblist-item,[class*="joblist-item"]'
      : '.job-list-panel .job-card,.joblist-box__item,.positionlist__item,[class*="joblist"] article,[class*="job-list"] [class*="item"],[class*="position-list"] [class*="item"]')).filter(visible).length;
    const extracted=${sourceId === "zhilian" ? sourceListExtractionScript("zhilian") : "null"};
    if(extracted)cardCount=Math.max(cardCount,extracted.jobs.length);
    const formCount=Array.from(document.querySelectorAll('input[type="password"],input[type="tel"],input[autocomplete="tel"],input[placeholder*="手机号"],input[placeholder*="验证码"]')).filter(visible).length;
    const challenge=/滑动验证|安全验证|访问过于频繁|captcha|请完成验证/i.test(text);
    const accountLink=Array.from(document.querySelectorAll('a[href*="/resume"],a[href*="/personal"],a[href*="/my/"],[class*="user-avatar"],[class*="userAvatar"]')).filter(visible)
      .some(node=>/我的简历|个人中心|我的投递|消息|用户|头像/.test((node.textContent||'')+' '+(node.getAttribute('aria-label')||'')) || node.matches('[class*="user-avatar"],[class*="userAvatar"]'));
    const accountHeader=Array.from(document.querySelectorAll('header,[role="banner"],nav,[class*="header"],[class*="Header"]')).filter(visible).slice(0,20)
      .some(node=>{const label=(node.innerText||'').slice(0,1000);return /消息/.test(label)&&!/登录\\s*\\/?\\s*注册|立即登录/.test(label)&&Array.from(node.querySelectorAll('img[alt*="头像"],img[class*="avatar"],img[class*="Avatar"],[class*="avatar"] img,[class*="Avatar"] img,[aria-label*="个人"],[title*="个人"]')).some(visible);});
    const account=accountLink||accountHeader||(${JSON.stringify(sourceId)}==='zhilian'&&Array.from(document.querySelectorAll('.c-login__top .c-login__top__img[alt="avatar"]')).some(visible));
    const loginHost=/passport\\.zhaopin\\.com|login\\.51job\\.com/.test(location.hostname);
    const login=loginHost || (formCount>0&&!cardCount&&!account) || Boolean(extracted?.loginRequired);
    const splash=!cardCount&&!formCount&&/找风口工作|登录|招聘/.test(text)&&text.length<1200;
    const authenticated=!challenge&&!login&&account;
    return {url:location.href,jobs:extracted?.jobs,kind:challenge?'challenge':login?'login':cardCount?'list':authenticated?'account':splash?'splash':'unknown',cardCount,formCount,authenticated};
  })()`;
}

export function isZhilianJobUrl(value:string):boolean {
  try{const url=new URL(value);return isAllowedSourceUrl("zhilian",value)&&
    (url.hostname==="jobs.zhaopin.com"&&/^\/[^/]+\.htm[l]?$/.test(url.pathname)||url.hostname==="www.zhaopin.com"&&/^\/jobdetail\/[^/]+/.test(url.pathname));}catch{return false;}
}

/** A visible list verifies extraction only. Preserve previous search evidence. */
export function foregroundZhilianVerification(current:{session_status:string;list_status:string;detail_status:string;fields_status:string;pagination_status:string;live_search_enabled:boolean},page:PassiveSourceObservation){
  const count=page.records?.length||0;
  const priorSearch=current.live_search_enabled&&current.list_status==="verified";
  return {session_status:page.authenticated?"verified":current.session_status,
    list_status:priorSearch?"verified":"partial",detail_status:current.detail_status,
    fields_status:count?"verified":current.fields_status,pagination_status:current.pagination_status,
    enabled:priorSearch,notes:`${page.authenticated?"当前平台页显示已登录；":"登录身份尚待确认；"}${count?`当前页已标准化读取 ${count} 条岗位` : "当前页尚未读到完整岗位卡片"}。仅验证当前可见列表，关键词、城市搜索及续页需在实际检索时核对。`};
}

export function validateZhilianSearchScope(url:string,keyword:string,city:string,page:number):void {
  const target=new URL(url);
  if(target.hostname!=="www.zhaopin.com"||!/^\/jobs\/?$/.test(target.pathname)||target.searchParams.get("pageMode")!=="search"||
    target.searchParams.get("kw")!==keyword.trim() || Number(target.searchParams.get("p")||target.searchParams.get("pageIndex")||"1")!==page ||
    target.searchParams.get("jl")!==zhilianCityCode(city))throw Error("source_scope_mismatch:站内搜索未保留本次关键词、城市或页码，不能将推荐列表当作检索结果");
}

// Existing Python connector city codes; 全国=489 also confirmed in the current site bundle.
export function zhilianCityCode(city:string):string {
  const value=city.trim();
  const codes:Record<string,string>={"":"489","全国":"489","北京":"530","上海":"538","广州":"654","深圳":"765","杭州":"736","南京":"631","苏州":"639","成都":"801","武汉":"570","西安":"535","重庆":"551"};
  if(/^\d+$/.test(value))return value;
  if(codes[value])return codes[value];
  throw Error("source_scope_mismatch:尚未确认该城市的站内筛选，请选择已支持的城市");
}

export function normalizeZhilianJobUrl(value:string):string|null {
  try{
    const url=new URL(value);
    if(url.protocol==="http:"&&["www.zhaopin.com","jobs.zhaopin.com"].includes(url.hostname)&&!url.port&&!url.username&&!url.password)url.protocol="https:";
    return isZhilianJobUrl(url.toString())?url.toString():null;
  }catch{return null;}
}
