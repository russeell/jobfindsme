import {isAllowedSourceUrl,type SourceBrowserId} from '../../shared/source-browser-policy';
import type {SourceActionPage} from './source-actions';
import {browserSiteNames} from '../../shared/browser-search';
import {canonicalJobUrl} from '../../shared/research-reports';

export type CareerPage = {jobs:Array<{title:string;url:string;location:string;company:string;salary:string;description?:string}>;next:boolean;entry?:string;blocked?:string;empty:boolean;loading:boolean};
/** Read only visible DOM and real links; never invent an ATS route or a job ID. */
export function careerPageScript():string{return `(${readCareerPage.toString()})()`;}
function readCareerPage():CareerPage {
 const visible=(e:Element)=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(e).visibility!=='hidden';};
 const text=(e:Element|null)=>((e as HTMLElement)?.innerText||e?.textContent||'').trim();
 const pick=(e:Element,s:string)=>Array.from(e.querySelectorAll(s)).filter(visible).map(text).find(Boolean)||'';
 const body=(document.body?.innerText||'').slice(0,20000);
 const blocked=['访问过于频繁','请完成验证','滑动验证','安全验证','Access Denied'].find(s=>body.includes(s));
 const jobs:CareerPage['jobs']=[],seen=new Set<string>();
 // JD's public home_index.js binds observed requirement IDs to this exact detail route.
 if(location.hostname==='zhaopin.jd.com')for(const row of Array.from(document.querySelectorAll('.table-main .line')).filter(visible)){
  const id=(row.querySelector('input[id="requemtId"]') as HTMLInputElement)?.value;
  const title=row.querySelector('.post[title]')?.getAttribute('title')||'';
  if(!/^\d+$/.test(id||'')||!title)continue;
  jobs.push({title,url:new URL('/web/job-info-detail?requementId='+id,location.origin).href,company:text(row.querySelector('.info .sel')),location:text(row.querySelectorAll('.info .sel')[2]),salary:'',description:Array.from(row.querySelectorAll('.detail .par')).map(text).join('\n')});
 }
 for(const a of Array.from(document.querySelectorAll<HTMLAnchorElement>('a[href]')).filter(visible)){
  const u=new URL(a.href,location.href);
  if(!/(?:\/job(?:s)?\/[^/?#]+|\/position\/\w+\/detail|\/job_detail\/|\/jobdesc|#\/job\/|\/jobs\/detail\?|postId=|jobId=)/i.test(u.href))continue;
  if(/\/jobs\/(?:social|campus|social-list|campus-list|search|index|list)(?:[/?#]|$)/i.test(u.href)||/\/job\/job_info_list\//.test(u.href))continue;
  if(a.closest('[class*="latest-job"]'))continue;
  const card=a.closest('li,article,[class*="job-card"],[class*="position-item"],[class*="job-item"]')||a;
  const title=pick(card,'.job-title')||pick(card,'h3,h2,[class*="job-title"],[class*="job-name"],[class*="position-name"],.positionItem-title-text,[class*="title-u"],.target-color-container')||text(a).split('\n')[0];
  if(!title||title.length>250||/^(申请|投递|详情|查看|Apply|申请职位|立即申请)$/i.test(title)||seen.has(u.href))continue;
  seen.add(u.href);jobs.push({title,url:u.href,company:pick(card,'[class*="company-name"]'),location:pick(card,'[class*="location"],[class*="city"],[class*="workplace"],.job-tags,.positionItem-subTitle > span:first-child')||Array.from(card.querySelectorAll('.no-adaptive-tooltip')).filter(visible).map(text).filter(t=>/市|北京|上海|深圳|杭州|美国|新加坡/.test(t)).join(' '),salary:pick(card,'[class*="salary"]')});
  if(jobs.length>=100)break;
 }
 const next=Array.from(document.querySelectorAll('button,a,li[role="button"],li[title="下一页"]')).filter(visible).some(e=>!e.matches('[disabled],[aria-disabled="true"],.disabled,.is-disabled')&&(/^(下一页|下一批|Next|›|>)$/i.test(text(e))||/^下一页/.test(e.getAttribute('aria-label')||'')||/pagination.*next|next.*pagination|Pagination-forward/i.test(e.className)));
 const entry=Array.from(document.querySelectorAll<HTMLAnchorElement>('a[href]')).filter(visible).find(a=>/^(社会招聘|招聘职位|查看所有职位|全部职位|所有职位|查看工作岗位|搜索职位|加入我们|职位列表|所有岗位|职位|应届招聘)$/.test(text(a)))?.href;
 return {jobs,next,entry,blocked,loading:/数据读取中|正在加载/.test(body),empty:/暂无(?:相关)?职位|没有找到.*职位|No jobs found/i.test(body)};
}
export function careerAdvanceScript():string{return `(()=>{const visible=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0;};const n=Array.from(document.querySelectorAll('button,a,li[role="button"],li[title="下一页"]')).filter(visible).find(e=>!e.matches('[disabled],[aria-disabled="true"],.disabled,.is-disabled')&&(/^(下一页|下一批|Next|›|>)$/i.test((e.innerText||'').trim())||/^下一页/.test(e.getAttribute('aria-label')||'')||/pagination.*next|next.*pagination|Pagination-forward/i.test(e.className)));if(n){n.click();return true;}return false;})()`;}
export function careerKeywordScript(keyword:string):string{return `(${setCareerKeyword.toString()})(${JSON.stringify(keyword)})`;}
async function setCareerKeyword(keyword:string):Promise<boolean>{
 const visible=(e:Element)=>e.getBoundingClientRect().width>0;
 const input=Array.from(document.querySelectorAll<HTMLInputElement>('input')).find(e=>/职位|岗位|关键|搜索|search|keyword/i.test(e.placeholder||'')&&visible(e))
  ||(location.hostname==='talent.baidu.com'?document.querySelector<HTMLInputElement>('[class*="input-wrap"] input'):null)
  ||(location.hostname==='zhaopin.jd.com'?document.querySelector<HTMLInputElement>('#search-key'):null);
 if(!input)return false;
 Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(input,keyword);
 input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));
 await new Promise(r=>setTimeout(r,150));
 let button:HTMLElement|null=null;
 if(location.hostname==='talent.baidu.com')button=document.querySelector('[class*="search-btn"]');
 if(location.hostname==='career.meituan.com')button=input.closest('.zp_search')?.querySelector('.zp_search_btn')||null;
 if(location.hostname==='zhaopin.jd.com')button=document.querySelector('.search-btn');
 button ||= Array.from(document.querySelectorAll<HTMLElement>('button')).find(e=>visible(e)&&/^(搜索|搜索职位|查询|Search)$/i.test((e.innerText||'').replace(/\s/g,'')))||null;
 if(button)button.click();
 else input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true}));
 return true;
}
export function careerRecords(sourceId:SourceBrowserId,url:string,raw:CareerPage,keyword:string,city:string):SourceActionPage {
 const seen=new Set<string>();
 raw={...raw,jobs:raw.jobs.map(job=>({...job,url:canonicalJobUrl(job.url)}))};
 const records=raw.jobs.filter(j=>isAllowedSourceUrl(sourceId,j.url)&&!seen.has(j.url)&&!!seen.add(j.url)).filter(j=>!keyword||j.title.toLowerCase().includes(keyword.toLowerCase())).filter(j=>!city||!j.location||j.location.includes(city)).map(j=>({external_id:j.url,source_name:browserSiteNames[sourceId],source_url:url,payload:{title:j.title,company:j.company||browserSiteNames[sourceId],location:j.location,salary:j.salary,description:j.description||j.title,url:j.url,apply_url:j.url,detail_level:j.description&&j.description.length>=80?'detail_page':'list_card'}}));
 return {records,next_cursor:null};
}

// Observed click-only list titles, scoped per first-party site. No application buttons.
export function careerClickableScript(sourceId:SourceBrowserId,index=-1):string {
 const selectors:Partial<Record<SourceBrowserId,string>>={company_03:'._1RRlPtjyYmeDGCWt9lrk2P',company_04:'.position_list_item .postion_name .title',company_05:'[class*="post-title-content__"]',company_06:'a.link-tag[id]',company_07:'.list-card-content .f-title',company_08:'.item .name[title]',company_10:'.cursor-pointer.break-all'};
 const selector=selectors[sourceId];if(!selector)return '[]';
 return `(()=>{const nodes=Array.from(document.querySelectorAll(${JSON.stringify(selector)})).filter(e=>e.getBoundingClientRect().width>0);if(${index}>=0){nodes[${index}]?.click();return [];}return nodes.slice(0,20).map(e=>({title:(e.getAttribute('title')||e.innerText||'').trim(),location:(e.closest('.position_list_item')?.querySelector('.position_city')?.textContent||'').trim()}));})()`;
}
export function careerEntryClickScript(sourceId:SourceBrowserId):string {
 if(!['company_01','company_03'].includes(sourceId))return 'false';
 return `(()=>{const nodes=Array.from(document.querySelectorAll('a,button,span,div')).filter(e=>e.getBoundingClientRect().width>0&&(e.innerText||'').trim()==='社会招聘');const n=nodes.sort((a,b)=>a.querySelectorAll('*').length-b.querySelectorAll('*').length)[0];n?.click();if(location.hostname==='talent-holding.alibaba.com'){const all=Array.from(document.querySelectorAll('div,button,a')).filter(e=>e.getBoundingClientRect().width>0&&(e.innerText||'').trim()==='查看全部职位').sort((a,b)=>a.querySelectorAll('*').length-b.querySelectorAll('*').length)[0];all?.click();}return !!n;})()`;
}
