export type BossJob = { title:string; company:string; location:string; salary:string; url:string };
export type BossPage = { authenticated:boolean; loginRequired:boolean; blocked:string|null; readable:boolean; empty:boolean; ended:boolean; jobs:BossJob[]; detail?:{title:string;company:string;location?:string;salary?:string;description:string;url:string} };
const cities:Record<string,string>={北京:'101010100',上海:'101020100',重庆:'101040100',广州:'101280100',深圳:'101280600',杭州:'101210100',南京:'101190100',苏州:'101190400',武汉:'101200100',成都:'101270100',西安:'101110100'};
export function bossSearchUrl(keyword:string,city:string) {
  if(!keyword.trim()||keyword.length>120)throw Error('请输入有效岗位关键词');
  const name=city.trim().replace(/市$/,'');
  const code=!name?'100010000':cities[name] || (Object.values(cities).includes(name)?name:'');
  if(!code)throw Error('unsupported_city:尚未核验该城市的 BOSS 编码，请选择已支持城市');
  const url=new URL('https://www.zhipin.com/web/geek/jobs');url.searchParams.set('query',keyword.trim());url.searchParams.set('city',code);return url.href;
}
export function canonicalBossJob(value:string):string|null {
  try{const u=new URL(value);if(u.protocol==='https:'&&u.hostname==='www.zhipin.com'&&!u.username&&!u.password&&!u.port&&/^\/job_detail\/[\w-]+\.html$/.test(u.pathname))return u.origin+u.pathname;}catch{}return null;
}
// Runs only in a project-owned BOSS WebContentsView. Reads the already-loaded DOM;
// never accesses cookies, storage, private network endpoints or recruiter identities.
export function bossPageScript() { return `(${readBossPage.toString()})()`; }
function readBossPage():BossPage {
  const visible=(e:Element)=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden';};
  const text=(e:Element|null)=>((e as HTMLElement)?.innerText||e?.textContent||'').trim();
  const pick=(e:Element,selectors:string)=>Array.from(e.querySelectorAll(selectors)).filter(visible).map(text).find(Boolean)||'';
  const body=(document.body?.innerText||'').slice(0,30000);
  const blocked=['滑动验证','请完成验证','访问过于频繁','账号异常','账号已被限制','安全验证'].find(t=>body.includes(t))||(Array.from(document.querySelectorAll('iframe[src*="captcha"],iframe[src*="verify"]')).some(visible)?'平台验证':null);
  const has=(s:string)=>Array.from(document.querySelectorAll(s)).some(visible);
  const loginForm=has('input[type="password"],input[type="tel"]');
  const signIn=Array.from(document.querySelectorAll('.btn-sign,a[href*="/web/user"]')).some(e=>visible(e)&&/登录|注册/.test(text(e)));
  const authenticated=!loginForm&&!signIn&&has('a[href*="/web/geek/chat"]')&&has('a[href*="/web/geek/resume"]');
  const loginRequired=!authenticated&&(loginForm||signIn||(/\/web\/user/.test(location.pathname)&&/登录|验证码/.test(body)));
  const jobs:BossJob[]=[];const seen=new Set<string>();
  for(const a of Array.from(document.querySelectorAll<HTMLAnchorElement>('a[href*="/job_detail/"]'))){
    if(!visible(a))continue;
    const u=new URL(a.href,location.href);if(u.hostname!=='www.zhipin.com'||!/^\/job_detail\/[\w-]+\.html$/.test(u.pathname))continue;
    const url=u.origin+u.pathname;if(seen.has(url))continue;
    const card=a.closest('.job-card-wrapper,li.job-card-box,li')||a.closest('.job-card-box');if(!card)continue;
    // A job link often contains salary and tags. Only dedicated title nodes qualify.
    const titleNode=['.job-name','.job-title','.job-info h3'].map(selector=>Array.from(card.querySelectorAll(selector)).find(visible)).find(Boolean);
    const titleCopy=titleNode?.cloneNode(true) as HTMLElement|undefined;
    titleCopy?.querySelectorAll('.salary,[class*="salary"],[class*="tag"],.job-area').forEach(e=>e.remove());
    const title=(titleCopy?.textContent||'').trim();
    const company=pick(card,'.company-name,.company-info h3,.company-info h4,a[href*="/gongsi/"]');
    if(!title||title.length>300||/[\uE000-\uF8FF]/.test(title))continue;
    const salary=pick(card,'.salary,[class*="salary"]');
    jobs.push({title,company:company.slice(0,300),location:pick(card,'.job-area,[class*="job-area"]').slice(0,200),salary:/[\uE000-\uF8FF]/.test(salary)?'':salary.slice(0,100),url});seen.add(url);if(jobs.length>=100)break;
  }
  const empty=has('.job-empty,.search-empty,.empty-result')&&/暂无|没有找到|未找到/.test(body);
  const ended=has('.no-more,.no-more-data,.job-list-bottom')&&/没有更多|暂无更多|已到底|到底了/.test(body);
  let detail:BossPage['detail'];
  const description=Array.from(document.querySelectorAll('.job-sec-text,.job-detail .text,.job-description')).filter(visible).map(text).find(t=>t.length>=80&&t.length<=30000);
  const title=pick(document.body,'.job-name h1,.name h1,.job-detail-header h1,h1');
  const company=pick(document.body,'.sider-company .company-info a[href*="/gongsi/"],.company-info .company-name,.job-company-name,.sider-company a[href*="/gongsi/"]');
  const detailLocation=pick(document.body,'.job-banner .text-city,.job-banner a[href*="/city/"],.job-banner .job-area,.job-banner .text-desc a');
  const detailSalary=pick(document.body,'.job-banner .salary,.job-detail-header .salary');
  // A split-list panel must be linked to its selected job, never inferred from first card.
  const detailUrl=/^\/job_detail\/[\w-]+\.html$/.test(location.pathname)?location.origin+location.pathname:'';
  const folded=Array.from(document.querySelectorAll('.job-sec button,.job-description button,.job-sec a')).some(e=>visible(e)&&/展开全部|展开更多|查看完整/.test(text(e)));
  if(description&&title&&detailUrl&&!folded&&!/展开全部|展开更多/.test(description))detail={title,company,location:detailLocation,salary:/[\uE000-\uF8FF]/.test(detailSalary)?'':detailSalary,description,url:detailUrl};
  return {authenticated,loginRequired,blocked,readable:jobs.length>0||empty,empty,ended,jobs,detail};
}
export function bossScrollScript(){return `(()=>{const card=document.querySelector('.job-card-wrapper,.job-card-box,.job-list-box li');let node=card?.parentElement;while(node){const s=getComputedStyle(node);if(/auto|scroll/.test(s.overflowY)&&node.scrollHeight>node.clientHeight+4){const before=node.scrollTop;node.scrollBy(0,Math.max(240,node.clientHeight*.8));return {moved:node.scrollTop!==before};}node=node.parentElement;}const before=window.scrollY;window.scrollBy(0,Math.max(240,innerHeight*.8));return {moved:window.scrollY!==before};})()`;}
