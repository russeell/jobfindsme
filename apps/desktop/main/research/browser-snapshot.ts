import {createHash} from 'node:crypto';
import type {ResearchEvidence} from '../../shared/contracts';
export type RetrievalSnapshot={tab_id:string;snapshot_id:string;url:string;title:string;text:string;status:string;elements:Array<{ref:string;role:string;name:string;url?:string;query_name?:string;next?:boolean}>};
// Our DOM snapshot runs in an isolated world. References belong to this exact
// snapshot/document; page scripts cannot replace the reference table.
export function retrievalSnapshotScript(id:string){return `(${snapshotDocument.toString()})(${JSON.stringify(id)})`;}
function snapshotDocument(id:string){
  const clean=(value:string)=>value.replace(/\s+/g,' ').trim();
  const visible=(node:Element)=>{const box=node.getBoundingClientRect(),style=getComputedStyle(node);return box.width>0&&box.height>0&&style.display!=='none'&&style.visibility!=='hidden';};
  const root=(document.querySelector('article.markdown-body,.markdown-body')||document.querySelector('[id="readme"],article')||document.querySelector('main,[role="main"]')||document.body)?.cloneNode(true) as Element|undefined;
  root?.querySelectorAll('script,style,noscript,nav,footer,aside,form,[hidden],[aria-hidden="true"],[role="navigation"]').forEach(node=>node.remove());
  const text=clean(root?.textContent||'').slice(0,30000),title=document.title.slice(0,300),prefix=(title+' '+text.slice(0,1200)).toLowerCase();
  const password=Array.from(document.querySelectorAll('input[type="password"]')).some(visible);
  const challenge=/please verify you are a human|checking your browser before accessing|enable javascript and cookies to continue|attention required! \| cloudflare|人机验证|安全验证|访问过于频繁/.test(prefix)&&text.length<5000;
  const status=challenge?'verification_required':password||/\/(login|signin)(\/|$)/.test(location.pathname)?'login_required':text.length<50?'empty_body':text.includes('\uFFFD')&&text.split('\uFFFD').length>text.length/100||text.includes('\u0000')?'unreadable_body':'readable';
  const elements:Array<{ref:string;role:string;name:string;url?:string;query_name?:string;next?:boolean}>=[];
  for(const node of Array.from(document.querySelectorAll('h1,h2,h3,a[href],input[type="search"],input[name="q"],input[name="query"],input[name="keyword"],[role="searchbox"]')).filter(visible).slice(0,180)){
    const role=node.tagName==='A'?'link':node.tagName==='INPUT'?'searchbox':'heading';
    const ref=id+':e'+elements.length;const input=node as HTMLInputElement,link=node as HTMLAnchorElement;
    const name=clean(node.getAttribute('aria-label')||node.textContent||input.placeholder||'').slice(0,240);
    elements.push({ref,role,name,...(role==='link'?{url:link.href,next:node.getAttribute('rel')==='next'||/^(next|下一页|下页|›|»|→)$/i.test(name)}:{}),...(role==='searchbox'?{query_name:input.name||'q'}:{})});
  }
  return {snapshot_id:id,url:location.href,title,text,status,elements};
}
export function snapshotEvidence(page:RetrievalSnapshot,company:string,site:string,focus=''):ResearchEvidence&{status:string}{
  if(page.status!=='readable')return {status:page.status,url:page.url,limitations:'请在应用内处理登录或验证后继续；未将页面作为原文。'} as ResearchEvidence&{status:string};
  if(company&&!page.text.toLocaleLowerCase().includes(company.toLocaleLowerCase()))return {status:'entity_mismatch',url:page.url} as ResearchEvidence&{status:string};
  const terms=focus.toLowerCase().match(/[a-z][a-z0-9_-]{2,}/g)||[];
  const positions=[0,...terms.map(term=>Math.max(0,page.text.toLowerCase().indexOf(term)-600))];
  const start=positions.sort((a,b)=>terms.reduce((n,t)=>n+(page.text.slice(b,b+4000).toLowerCase().includes(t)?1:0)-(page.text.slice(a,a+4000).toLowerCase().includes(t)?1:0),0))[0];
  const excerpt=page.text.slice(start,start+4000),content_hash=createHash('sha256').update(page.text.replace(/\s+/g,'').toLowerCase()).digest('hex');
  return {status:'read_original',evidence_id:'ev_'+createHash('sha256').update(page.url+'\0'+excerpt).digest('hex').slice(0,24),url:page.url,platform:site,published_at:null,retrieved_at:new Date().toISOString(),company,team:null,excerpt,evidence_kind:'public_source',verification_status:'independently_retrieved',relevance:company?'company':'role',limitations:'应用浏览器读取了正文；发布时间与实体范围需另行核对。',context:{source_type:'public_web',reader:'browser',tab_id:page.tab_id,start_char:start,end_char:start+excerpt.length,content_hash,source_id:createHash('sha256').update(page.url).digest('hex').slice(0,20),link_status:'reachable'}};
}
