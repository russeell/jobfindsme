import {bossSearchUrl} from "./boss-page";
import { isAllowedSourceUrl, type SourceBrowserId } from "./source-browser-policy";

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
  company_01: "腾讯招聘官网",
};

const extractionSpecs: Record<BrowserSearchSourceId, {
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
  zhilian: {
    cards: [".joblist-box__item", ".positionlist__item", "[class*='joblist'] article"],
    title: ["[class*='job-name']", "[class*='position-name']", "h3"],
    company: ["[class*='company-name']", "[class*='company']"],
    location: ["[class*='location']", "[class*='address']"],
    salary: ["[class*='salary']"],
    link: ["a[href*='jobs.zhaopin.com']", "a[href]"],
    next: ["[class*='pagination'] [class*='next']", "li.next"],
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
    zhilian: new URL("https://sou.zhaopin.com/"),
    wuyou: new URL("https://we.51job.com/pc/search"),
  };
  const target = targets[sourceId];
  if (sourceId === "zhilian") {
    target.searchParams.set("kw", keyword.trim());
    if (/^\d+$/.test(city.trim())) target.searchParams.set("jl", city.trim());
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
  const spec = JSON.stringify(extractionSpecs[sourceId]);
  return `(() => {
    const spec = ${spec};
    const text = (document.body?.innerText || "").slice(0, 5000);
    const blocked = ["滑动验证", "安全验证", "访问过于频繁", "captcha", "请完成验证"]
      .find((marker) => text.toLowerCase().includes(marker.toLowerCase()));
    const login = ["请登录", "登录后查看", "立即登录"]
      .find((marker) => text.includes(marker));
    const pick = (root, selectors) => {
      for (const selector of selectors) {
        const node = root.querySelector(selector);
        const value = (node?.textContent || "").replace(/\\s+/g, " ").trim();
        if (value) return value;
      }
      return "";
    };
    const href = (root) => {
      for (const selector of spec.link) {
        const node = root.querySelector(selector);
        if (node?.href) return node.href;
      }
      if (${JSON.stringify(sourceId)} === 'wuyou' && !blocked && !login) {
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
    const jobs = cards.slice(0, 60).map((card) => ({
      title: pick(card, spec.title), company: pick(card, spec.company),
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
    return { jobs, hasNext, empty:/暂无相关职位|没有找到相关职位|没有符合条件的职位/.test(text), blocked: blocked || null, loginRequired: Boolean(login && !jobs.length) };
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
  for (const item of raw.jobs || []) {
    if (!item || typeof item.title !== "string" || typeof item.url !== "string") continue;
    if (!isAllowedSourceUrl(sourceId, item.url)) continue;
    const title = item.title.trim().slice(0, 300);
    if (!title) continue;
    const url = new URL(item.url).toString();
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
  url:string; kind:"list"|"login"|"challenge"|"splash"|"unknown"; cardCount:number; formCount:number;
};

// Reads the already loaded foreground document. It never clicks, navigates or searches.
export function passiveSourceObservationScript(sourceId:"zhilian"|"wuyou"):string {
  return `(() => {
    const text=(document.body?.innerText||'').slice(0,4000);
    const cardCount=${JSON.stringify(sourceId)}==='wuyou'
      ? document.querySelectorAll('.joblist-item,[class*="joblist-item"]').length
      : document.querySelectorAll('.joblist-box__item,.positionlist__item,[class*="joblist"] article').length;
    const formCount=document.querySelectorAll('input[type="password"],input[type="tel"],input[autocomplete="tel"],input[placeholder*="手机号"],input[placeholder*="验证码"]').length;
    const challenge=/滑动验证|安全验证|访问过于频繁|captcha|请完成验证/i.test(text);
    const login=/passport\.zhaopin\.com|login\.51job\.com/.test(location.hostname) || (/请登录|登录后查看/.test(text)&&!cardCount);
    const splash=!cardCount&&!formCount&&/找风口工作|登录|招聘/.test(text)&&text.length<1200;
    return {url:location.href,kind:challenge?'challenge':cardCount?'list':formCount||login?'login':splash?'splash':'unknown',cardCount,formCount};
  })()`;
}
