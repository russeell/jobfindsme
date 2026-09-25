import {createHash,randomUUID} from "node:crypto";
import {BrowserWindow} from "electron";
import type {ResearchEvidence} from "../../shared/contracts.js";

const DOMAINS:Record<string,string>={cninfo:"cninfo.com.cn",sse:"sse.com.cn",szse:"szse.cn",hkex:"hkexnews.hk",maimai:"maimai.cn",kanzhun:"kanzhun.com",zhihu:"zhihu.com",offershow:"offershow.cn"};
function allowed(site:string,value:string){try{const url=new URL(value),domain=DOMAINS[site];return !!domain&&url.protocol==="https:"&&!url.username&&!url.password&&(!url.port||url.port==="443")&&(url.hostname===domain||url.hostname.endsWith("."+domain));}catch{return false;}}
export async function readIsolatedResearchPage(company:string,site:string,url:string,signal:AbortSignal,timeoutMs=8000):Promise<ResearchEvidence&{status:string}>{
  if(!allowed(site,url)||!company.trim()||company.length>100)throw Error("unsupported research URL");
  const origin=new URL(url).origin;
  const view=new BrowserWindow({show:false,width:1024,height:900,webPreferences:{partition:`research-${randomUUID()}`,nodeIntegration:false,contextIsolation:true,sandbox:true,webSecurity:true,allowRunningInsecureContent:false}});
  const wc=view.webContents,isolatedSession=wc.session;let timer:ReturnType<typeof setTimeout>|undefined;
  wc.setWindowOpenHandler(()=>({action:"deny"}));
  const safe=(candidate:string)=>allowed(site,candidate)&&new URL(candidate).origin===origin;
  wc.on("will-navigate",(event,next)=>{if(!safe(next))event.preventDefault();});
  wc.on("will-redirect",(event,next)=>{if(!safe(next))event.preventDefault();});
  wc.session.setPermissionRequestHandler((_contents,_permission,callback)=>callback(false));
  wc.session.webRequest.onBeforeRequest({urls:["*://*/*"]},(request,callback)=>callback({cancel:!safe(request.url)}));
  const abort=()=>{wc.stop();};signal.addEventListener("abort",abort,{once:true});
  try{
    await Promise.race([wc.loadURL(url),new Promise<never>((_,reject)=>{timer=setTimeout(()=>{wc.stop();reject(Error("browser read timeout"));},Math.max(100,Math.min(8000,timeoutMs)));})]);
    if(signal.aborted)throw Error("cancelled");
    if(!safe(wc.getURL()))throw Error("source redirect blocked");
    const page=await wc.executeJavaScript(`({title:document.title.slice(0,300),text:(document.querySelector('article,main')?.innerText||document.body?.innerText||'').slice(0,30000),url:location.href})`) as {title:string;text:string;url:string};
    if(!safe(page.url))throw Error("source redirect blocked");
    const text=page.text.replace(/\s+/g," ").trim();
    if(text.length<50||!text.includes(company)||!(page.title.includes(company)||text.slice(0,2000).includes(company)))return {status:"entity_mismatch",url:page.url,limitations:"浏览器原文未能核对公司主体。"} as ResearchEvidence&{status:string};
    const position=text.indexOf(company),excerpt=text.slice(Math.max(0,position-150),Math.min(text.length,position+1000));
    const evidenceId="ev_"+createHash("sha256").update(`${page.url}\0${excerpt}`).digest("hex").slice(0,24);
    return {status:"read_original",evidence_id:evidenceId,url:page.url,platform:site,published_at:null,retrieved_at:new Date().toISOString(),company,team:null,excerpt,evidence_kind:"public_source",verification_status:"independently_retrieved",relevance:"company",limitations:"隔离浏览器读取了原页正文；发布日期、法律主体和团队范围未核实。",context:{source_type:["cninfo","sse","szse","hkex"].includes(site)?"official_disclosure":"personal_account",link_status:"reachable",company_match:"name_in_article",research_topic:"company"}};
  }catch(error){return {status:"read_failed",url,limitations:String(error).slice(0,160)} as ResearchEvidence&{status:string};}
  finally{if(timer)clearTimeout(timer);signal.removeEventListener("abort",abort);view.destroy();try{await isolatedSession.clearStorageData();}catch{}}
}
