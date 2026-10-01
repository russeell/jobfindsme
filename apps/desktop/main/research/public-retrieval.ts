import {isPublicWebUrl} from "../../shared/source-browser-policy";
import type {Discovery} from "./pi-research-agent.mjs" with {"resolution-mode":"import"};

const ENDPOINT="https://mcp.exa.ai/mcp";
export const retrievalSites:Record<string,string>={web:"",github:"github.com",papers:"arxiv.org OR site:doi.org OR site:aclanthology.org",cninfo:"cninfo.com.cn",sse:"sse.com.cn",szse:"szse.cn",hkex:"hkexnews.hk",maimai:"maimai.cn",kanzhun:"kanzhun.com",zhihu:"zhihu.com",offershow:"offershow.cn"};
type Input={workspace?:string;company:string;query:string;site:string;originalQuestion:string};
type Fallback=(input:Input,signal:AbortSignal,timeoutMs:number)=>Promise<Discovery[]>;

export function parseExaDiscovery(body:string,site:string):Discovery[]{
  const messages=body.trim().startsWith("{")?[body]:body.split(/\r?\n\r?\n/).map(event=>event.split(/\r?\n/).filter(line=>line.startsWith("data:")).map(line=>line.slice(5).trimStart()).join("\n")).filter(Boolean);
  let response:unknown;
  for(const message of messages){try{const value=JSON.parse(message);if(value?.id===1)response=value;}catch{/* Incomplete or unrelated SSE events are never evidence. */}}
  const data=response as {error?:unknown;result?:{isError?:boolean;content?:Array<{type?:string;text?:string}>}}|undefined;
  if(data?.result?.isError&&data.result.content?.some(block=>/\b429\b|rate.?limit|captcha|verification required/i.test(block.text||"")))throw Error("retrieval:rate_limited");
  if(data?.error||data?.result?.isError||!Array.isArray(data?.result?.content))throw Error("retrieval:invalid_response");
  const rows:Discovery[]=[];const seen=new Set<string>();
  for(const block of data.result.content){
    if(block.type!=="text"||typeof block.text!=="string")continue;
    let title="";
    for(const line of block.text.split(/\r?\n/)){
      if(line.startsWith("Title: "))title=line.slice(7).trim().slice(0,300);
      if(!line.startsWith("URL: "))continue;
      const value=line.slice(5).trim();
      if(!isPublicWebUrl(value))continue;
      const url=new URL(value);if(url.protocol!=="https:"||url.port&&url.port!=="443")continue;
      if(site==="github"&&url.hostname!=="github.com")continue;
      if(site==="papers"&&!["arxiv.org","doi.org","aclanthology.org"].some(host=>url.hostname===host||url.hostname.endsWith("."+host)))continue;
      const domain=retrievalSites[site];
      if(domain&&site!=="papers"&&url.hostname!==domain&&!url.hostname.endsWith("."+domain))continue;
      url.hash="";if(seen.has(url.href))continue;seen.add(url.href);
      rows.push({url:url.href,site,title:title||url.hostname,status:"search_hint_only",provider:"exa_public",source_type:"public_web"});
      if(rows.length>=6)return rows;
    }
  }
  return rows;
}

async function boundedBody(response:Response):Promise<string>{
  if(!response.body)throw Error("retrieval:invalid_response");
  const reader=response.body.getReader();const parts:Uint8Array[]=[];let size=0;
  try{for(;;){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>1_000_000)throw Error("retrieval:response_too_large");parts.push(value);}}
  finally{await reader.cancel().catch(()=>{});reader.releaseLock();}
  return Buffer.concat(parts).toString("utf8");
}

// Read-only, fixed official endpoint. No local MCP server, command execution,
// global Agent Reach configuration, OAuth token or user model key is involved.
export function createPublicRetrieval(fetcher:typeof fetch=fetch,clock=Date.now){
  const cache=new Map<string,{at:number;rows:Discovery[]}>();
  const remember=(key:string,rows:Discovery[])=>{if(rows.length){cache.set(key,{at:clock(),rows:structuredClone(rows)});if(cache.size>100)cache.delete(cache.keys().next().value!);}return rows;};
  let cooldownUntil=0;let lastStatus="not_probed";let fallbackStatus="not_probed";
  const status=()=>({skill:"web-retrieval",providers:[{id:"exa_public",configured:true,status:clock()<cooldownUntil?"cooldown":lastStatus},{id:"public_search",configured:true,status:fallbackStatus}],privacy:"仅发送公开查询词；摘要不能作为原文证据"});
  async function search(input:Input,fallback:Fallback,signal:AbortSignal,timeoutMs:number):Promise<Discovery[]>{
    if(!Object.hasOwn(retrievalSites,input.site)||!input.query.trim()||input.query.length>700||input.company.length>100)throw Error("invalid retrieval request");
    if(/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|\b(?:sk-|AIza)[A-Za-z0-9_-]{12,}|\b1[3-9]\d{9}\b|\/Users\/[^\s]+|[A-Z]:\\Users\\/i.test(input.company+" "+input.query))throw Error("公开检索词不能包含邮箱、手机号、密钥或私人文件路径。");
    if(signal.aborted)throw Error("cancelled");
    const key=JSON.stringify([input.workspace||"app",input.company,input.query,input.site]),cached=cache.get(key);if(cached&&clock()-cached.at<60000)return structuredClone(cached.rows);
    const deadline=clock()+Math.min(10000,Math.max(100,timeoutMs));
    const remaining=()=>Math.max(0,deadline-clock());
    let primaryFailure="";
    if(signal.aborted)throw Error("cancelled");
    if(clock()>=cooldownUntil){
      const requestSignal=AbortSignal.any([signal,AbortSignal.timeout(Math.max(100,Math.min(5500,remaining())))]);
      try{
        const domain=retrievalSites[input.site];const query=(input.company?input.company+" ":"")+input.query+(domain?` (site:${domain})`:"");
        const response=await fetcher(ENDPOINT,{method:"POST",redirect:"error",headers:{"Content-Type":"application/json","Accept":"application/json, text/event-stream"},body:JSON.stringify({jsonrpc:"2.0",id:1,method:"tools/call",params:{name:"web_search_exa",arguments:{query,numResults:6}}}),signal:requestSignal});
        if(!response.ok){
          if([401,403,429].includes(response.status)){cooldownUntil=clock()+180_000;lastStatus="restricted";}
          throw Error(`retrieval:HTTP ${response.status}`);
        }
        const rows=parseExaDiscovery(await boundedBody(response),input.site);
        lastStatus=rows.length?"candidates":"no_results";
        if(rows.length)return remember(key,rows);
      }catch(error){
        if(signal.aborted)throw Error("cancelled");
        primaryFailure=error instanceof Error?error.message:"retrieval:unavailable";
        if(primaryFailure==="retrieval:rate_limited"){cooldownUntil=clock()+180_000;lastStatus="restricted";}
        if(clock()>=cooldownUntil)lastStatus="unavailable";
      }
    }else primaryFailure="retrieval:cooldown";
    if(signal.aborted)throw Error("cancelled");
    if(remaining()<100)throw Error("公开检索服务响应超时");
    // The remaining original budget, not a new timer, goes to the independent
    // existing search service. Never retry the restricted Exa endpoint.
    try{
      fallbackStatus="running";const rows=await fallback(input,signal,remaining());
      fallbackStatus=rows.length?"candidates":"no_results";
      if(!rows.length&&primaryFailure)throw Error("主检索不可用，备用检索没有取得候选");
      return remember(key,rows);
    }
    catch(error){if(signal.aborted)throw Error("cancelled");if(fallbackStatus!=="no_results")fallbackStatus="unavailable";if(primaryFailure)throw Error(`公开检索服务未能完成（${primaryFailure.startsWith("retrieval:HTTP")?primaryFailure:"主检索不可用"}；备用检索不可用）`);throw error;}
  }
  return {search,status};
}
