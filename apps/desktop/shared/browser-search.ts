import {isAllowedSourceUrl,isPublicWebUrl,sourceBrowserSpecs,type ForegroundBrowserId,type SourceBrowserId} from "./source-browser-policy";

export type SearchEngine = "bing" | "baidu" | "google";
export const searchEngineNames:Record<SearchEngine,string>={bing:"Bing",baidu:"百度",google:"Google"};
export function normalizeSearchEngine(value:string|null):SearchEngine {return value==="baidu"||value==="google"?value:"bing";}
export const browserSiteNames:Record<SourceBrowserId,string>={boss:"BOSS直聘",liepin:"猎聘",zhilian:"智联招聘",wuyou:"前程无忧",company_01:"腾讯",company_02:"字节跳动",company_03:"阿里巴巴",company_04:"美团",company_05:"百度",company_06:"京东",company_07:"网易",company_08:"快手",company_09:"小米",company_10:"滴滴",company_11:"拼多多",company_12:"DeepSeek",company_13:"MiniMax",company_14:"智谱",company_15:"月之暗面",company_16:"阶跃星辰"};
const platformHome:Partial<Record<SourceBrowserId,string>>={boss:"https://www.zhipin.com/",liepin:"https://www.liepin.com/",zhilian:"https://www.zhaopin.com/",wuyou:"https://www.51job.com/"};
export type BrowserDestination = {kind:"empty"|"invalid";summary:string} | {kind:"homepage"|"url"|"search";url:string;sourceId:ForegroundBrowserId;summary:string};

/** One form submission resolves to exactly one URL. This does not invoke job search. */
export function resolveBrowserDestination(input:string,engine:SearchEngine):BrowserDestination {
  const value=input.trim();
  if(!value)return {kind:"empty",summary:"输入关键词或网址。"};
  const invalid=():BrowserDestination=>({kind:"invalid",summary:"网址格式不正确，或不是可打开的公共 HTTP/HTTPS 地址。"});
  if(/[\u0000-\u001f\u007f]/.test(value))return invalid();
  const explicit=/^https?:/i.test(value);
  const domain=/^(?:[\p{L}\d](?:[\p{L}\d-]*[\p{L}\d])?\.)+[\p{L}\d-]+(?::\d+)?(?:[/?#]|$)/u.test(value);
  const local=/^(?:localhost|\[[^\]]+\])(?::\d+)?(?:[/?#]|$)/i.test(value);
  if(explicit || domain || local){
    if(explicit&&!/^https?:\/\/[^/\s]/i.test(value))return invalid();
    const candidate=explicit?value:`https://${value}`;
    if(!isPublicWebUrl(candidate)||/\s/.test(new URL(candidate).host))return invalid();
    const url=new URL(candidate).href;
    // A new address-bar tab uses the target URL to choose its session partition.
    const sourceId=(Object.keys(sourceBrowserSpecs) as SourceBrowserId[]).find(id=>isAllowedSourceUrl(id,url))??"web";
    return {kind:"url",url,sourceId,summary:`将打开输入网址：${url}`};
  }
  if(/^(?:javascript|data|file|about|chrome|devtools|vbscript|mailto|ftp|https?)\s*:/i.test(value)||/^[a-z][a-z\d+.-]*:\S/i.test(value)||value.includes("://")||/^[\/\\]/.test(value))return invalid();
  return searchDestination(value,engine);
}

function searchDestination(value:string,engine:SearchEngine):BrowserDestination {
  const url=new URL(engine==="baidu"?"https://www.baidu.com/s":engine==="google"?"https://www.google.com/search":"https://www.bing.com/search");
  url.search=new URLSearchParams({[engine==="baidu"?"wd":"q"]:value}).toString();
  return {kind:"search",url:url.href,sourceId:"web",summary:`${searchEngineNames[engine]} 全网搜索：${value}`};
}

export function resolveWebsiteHomepage(site:SourceBrowserId|""):BrowserDestination {
  if(!site)return {kind:"empty",summary:"选择招聘网站。"};
  return {kind:"homepage",url:platformHome[site]??sourceBrowserSpecs[site].loginUrl,sourceId:site,summary:`将打开${browserSiteNames[site]}首页`};
}

export function resolveWebSearch(input:string,engine:SearchEngine):BrowserDestination {
  const result=resolveBrowserDestination(input,engine);
  if(result.kind==="empty")return {kind:"empty",summary:"输入搜索关键词。"};
  if(result.kind==="invalid")return result;
  return searchDestination(input.trim(),engine);
}
