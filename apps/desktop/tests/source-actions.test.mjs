import assert from "node:assert/strict";
import test from "node:test";

import {
  buildSourceSearchUrl,
  sanitizeSourceActionPage,
  sourceListExtractionScript, passiveSourceObservationScript,
} from "../dist-electron/main/sources/source-actions.js";

test("browser source actions build only fixed allowlisted search targets", () => {
  const boss = new URL(buildSourceSearchUrl("boss", "AI 工程师", "上海", 1));
  assert.equal(boss.hostname, "www.zhipin.com");
  assert.equal(boss.searchParams.get("query"), "AI 工程师");
  assert.equal(boss.searchParams.get("city"), "101020100");
  assert.equal(boss.searchParams.has("page"), false);
  assert.throws(()=>buildSourceSearchUrl("boss","AI","上海",2),/scroll/);
  assert.throws(() => buildSourceSearchUrl("boss", "", "上海", 1), /keyword/);
  assert.throws(() => buildSourceSearchUrl("boss", "AI", "上海", 21), /page/);
  assert.match(sourceListExtractionScript("zhilian"), /joblist/);
});

test("browser source results reject cross-origin URLs and bound fields", () => {
  const page = sanitizeSourceActionPage(
    "boss",
    "https://www.zhipin.com/web/geek/job?query=AI",
    1,
    {
      hasNext: true,
      jobs: [
        {
          title: "AI 工程师",
          company: "示例公司",
          location: "上海",
          salary: "20-30K",
          url: "https://www.zhipin.com/job_detail/abc.html",
        },
        {
          title: "恶意结果",
          company: "伪造",
          location: "",
          salary: "",
          url: "https://evil.example/job/1",
        },
      ],
    },
    new Map([["https://www.zhipin.com/job_detail/abc.html", "岗位职责与任职要求".repeat(20)]]),
  );
  assert.equal(page.records.length, 1);
  assert.equal(page.records[0].payload.detail_level, "detail_page");
  assert.equal(page.next_cursor, "2");
});

test('named cities are never sent as opaque platform city codes',()=>{
 for(const id of ['zhilian','wuyou']){
 const url=new URL(buildSourceSearchUrl(id,'工程师','上海',1));
 assert.equal(url.searchParams.get(id==='zhilian'?'jl':'jobArea'),id==='zhilian'?'538':null);
 }
});


test('passive source observation separates splash, login form, and readable list without searches',async()=>{
 const {runInNewContext}=await import('node:vm');
 const script=passiveSourceObservationScript('zhilian');
 function observe(text,inputs,cards,account=false){const node=(shown=true)=>({textContent:'我的简历',getAttribute:()=>'',querySelector:()=>null,matches:()=>false,getBoundingClientRect:()=>({width:shown?10:0,height:shown?10:0})});return runInNewContext(script,{location:{href:'https://www.zhaopin.com/',hostname:'www.zhaopin.com'},getComputedStyle:()=>({display:'block',visibility:'visible',opacity:1}),document:{body:{innerText:text},querySelector:()=>null,querySelectorAll(selector){if(selector.startsWith('.c-login'))return [];if(selector.startsWith('input'))return Array.from({length:inputs==='hidden'?1:inputs},()=>node(inputs!=='hidden'));if(selector.startsWith('a[href*="/resume"]'))return account?[node(account==='hidden'?false:true)]:[];return Array.from({length:cards},()=>node(true));}}});}
 assert.equal(observe('找风口工作，就上智联招聘',0,0).kind,'splash');
 assert.equal(observe('求职者登录',2,0).kind,'login');
 assert.equal(observe('搜索岗位',0,3).kind,'list');
 assert.equal(observe('搜索岗位',0,3).authenticated,false);
 assert.equal(observe('欢迎回来',0,0,true).kind,'account');
 assert.equal(observe('欢迎回来',0,0,'hidden').authenticated,false);
 assert.equal(observe('欢迎回来','hidden',0,true).authenticated,true);
});

test('current Zhaopin jobs template keeps footer login prompts separate from session evidence',async()=>{
 const {runInNewContext}=await import('node:vm');
 const visible={textContent:'',innerText:'',getAttribute:()=>'',querySelector:()=>null,matches:()=>false,getBoundingClientRect:()=>({width:20,height:20})};
 const avatar={...visible};
 const header=(avatarVisible=true)=>({...visible,innerText:'职位 消息 我要招人 账户',querySelectorAll:selector=>selector.includes('alt*="头像"')?avatarVisible?[avatar]:[{...avatar,getBoundingClientRect:()=>({width:0,height:0})}]:[]});
 const anonymousHeader={...visible,innerText:'职位 消息 我要招人',querySelectorAll:()=>[]};
 const card={...visible,querySelector(selector){if(selector==='h3')return {textContent:'工程师'};if(selector.includes('/jobdetail/'))return {href:'https://www.zhaopin.com/jobdetail/example.htm'};return null;}};
 const context=(authenticated,loginHost=false,options={})=>({
  location:{href:loginHost?'https://passport.zhaopin.com/login':'https://www.zhaopin.com/jobs',hostname:loginHost?'passport.zhaopin.com':'www.zhaopin.com'},
  getComputedStyle:()=>({display:'block',visibility:'visible',opacity:1}),
  document:{body:{innerText:'热门职位 登录查看更多相关职位 立即登录'},querySelector:()=>null,querySelectorAll(selector){
   if(selector.startsWith('header,'))return [authenticated?header(!options.hiddenAvatar):anonymousHeader];
   if(selector.startsWith('input'))return options.phoneInput&&!selector.includes('type="password"')?[visible]:[];
   if(selector.includes('job-list'))return options.cards===false?[]:[card,card];
   return [];
  }}
 });
 const observed=runInNewContext(passiveSourceObservationScript('zhilian'),context(true));
 assert.equal(observed.kind,'list');assert.equal(observed.authenticated,true);assert.equal(observed.cardCount,2);
 const publicObserved=runInNewContext(passiveSourceObservationScript('zhilian'),context(false));
 assert.equal(publicObserved.authenticated,false);assert.notEqual(publicObserved.kind,'login');
 const hidden=runInNewContext(passiveSourceObservationScript('zhilian'),context(true,false,{hiddenAvatar:true}));
 assert.equal(hidden.authenticated,false);
 const phone=runInNewContext(passiveSourceObservationScript('zhilian'),context(false,false,{phoneInput:true}));
 assert.equal(phone.authenticated,false);assert.notEqual(phone.kind,'login');
 const phoneWithAccount=runInNewContext(passiveSourceObservationScript('zhilian'),context(true,false,{phoneInput:true}));
 assert.equal(phoneWithAccount.authenticated,true);
 const extracted=runInNewContext(sourceListExtractionScript('zhilian'),context(false));
 assert.equal(extracted.loginRequired,false);assert.equal(extracted.jobs.length,2);
 const login=runInNewContext(sourceListExtractionScript('zhilian'),context(false,true,{cards:false}));
 assert.equal(login.loginRequired,true);
});

test('foreground Zhaopin standardization is distinct from authenticated search capability',async()=>{
 const {foregroundZhilianVerification,validateZhilianSearchScope}=await import('../dist-electron/main/sources/source-actions.js');
 const job={title:'大模型应用研发',company:'示例科技',location:'上海',salary:'20-30K',url:'https://www.zhaopin.com/jobdetail/123.htm'};
 const page=sanitizeSourceActionPage('zhilian','https://www.zhaopin.com/jobs',1,{jobs:[job,job,{...job,url:'https://www.zhaopin.com/resume'},{...job,company:'',url:'https://www.zhaopin.com/jobdetail/456.htm'}]});
 assert.equal(page.records.length,1);assert.equal(page.records[0].payload.company,'示例科技');
 const current={session_status:'unverified',list_status:'unverified',detail_status:'unverified',fields_status:'unverified',pagination_status:'unverified',live_search_enabled:false};
 const observed=foregroundZhilianVerification(current,{authenticated:true,records:page.records});
 assert.equal(observed.session_status,'verified');assert.equal(observed.list_status,'partial');assert.equal(observed.fields_status,'verified');assert.equal(observed.enabled,false);
 assert.match(observed.notes,/1 条岗位/);
 const anonymous=foregroundZhilianVerification(current,{authenticated:false,records:page.records});assert.equal(anonymous.session_status,'unverified');
 const prior=foregroundZhilianVerification({...current,session_status:'verified',list_status:'verified',live_search_enabled:true},{authenticated:false,records:[]});assert.equal(prior.enabled,true);assert.equal(prior.list_status,'verified');
 assert.doesNotThrow(()=>validateZhilianSearchScope('https://www.zhaopin.com/jobs/?pageMode=search&kw=AI%20Agent&jl=538&p=1','AI Agent','538',1));
 for(const url of ['https://www.zhaopin.com/jobs','https://sou.zhaopin.com/?kw=工程师','https://sou.zhaopin.com/?kw=AI%20Agent&jl=530'])assert.throws(()=>validateZhilianSearchScope(url,'AI Agent','538',1),/source_scope_mismatch/);
});

test('canonical-link fallback reads company fields and rejects visible login overlay even with cards',async()=>{
 const {runInNewContext}=await import('node:vm');
 const shown={getBoundingClientRect:()=>({width:20,height:20}),matches:()=>false};
 const link={...shown,href:'https://www.zhaopin.com/jobdetail/abc.htm',textContent:'大模型应用研发'};
 const card={...shown,querySelector(selector){if(selector==='.jobinfo__name')return link;if(selector==='.companyinfo__name')return {textContent:'示例科技'};if(selector==='.jobinfo__other-info-item')return {textContent:'上海'};if(selector.includes('/jobdetail/'))return link;return null;}};
 link.closest=()=>card;
 let overlay=false;
 const context={location:{hostname:'www.zhaopin.com',href:'https://www.zhaopin.com/jobs'},getComputedStyle:()=>({display:'block',visibility:'visible',opacity:1}),document:{body:{innerText:'登录查看更多相关职位'},querySelector:()=>null,querySelectorAll(selector){if(selector.startsWith('input'))return overlay?[shown]:[];if(selector==='a[href*="/jobdetail/"],a[href*="jobs.zhaopin.com/"]')return [link];return [];}}};
 const raw=runInNewContext(sourceListExtractionScript('zhilian'),context);assert.equal(raw.jobs.length,1);assert.equal(raw.jobs[0].company,'示例科技');assert.equal(raw.loginRequired,false);
 assert.equal(sanitizeSourceActionPage('zhilian',context.location.href,1,raw).records.length,1);
 overlay=true;assert.equal(runInNewContext(passiveSourceObservationScript('zhilian'),context).kind,'login');
 context.document.body.innerText='请完成验证';assert.equal(runInNewContext(passiveSourceObservationScript('zhilian'),context).kind,'challenge');
});


test('observed split-layout JobCard uses only its matched public job prop for the canonical URL',async()=>{
 const {runInNewContext}=await import('node:vm');
 const title='AI agent BD',company='进迭时空(杭州)科技有限公司';
 const job={name:title,companyName:company,positionUrl:'http://www.zhaopin.com/jobdetail/CCL1378359190J000000001.htm'};
 const vue={$props:{job}};
 for(const key of ['$data','$store','user','cookiesData'])Object.defineProperty(vue,key,{get(){throw Error('must not read private Vue state');}});
 const card={__vue__:vue,matches:s=>s==='.job-card',getBoundingClientRect:()=>({width:300,height:200}),querySelector(s){
  if(s==='.job-card__title-clamp .vue-clamp__text')return {textContent:title};
  if(s==='.job-card__company-name')return {textContent:company};
  if(s==='.job-card__location')return {textContent:'深圳 宝安 新安'};
  if(s.includes('salary'))return {textContent:'1.5-3万'};
  return null;
 }};
 const ctx={location:{hostname:'www.zhaopin.com',href:'https://www.zhaopin.com/jobs/?pageMode=search&jl=765&kw=AI+Agent'},getComputedStyle:()=>({display:'block',visibility:'visible',opacity:1}),document:{body:{innerText:'职位 消息 AI Agent'},querySelector:s=>s.startsWith('input')?{value:'AI Agent'}:null,querySelectorAll:s=>s==='.job-list-panel .job-card'?[card]:[]}};
 const raw=runInNewContext(sourceListExtractionScript('zhilian'),ctx);assert.equal(raw.jobs.length,1);assert.equal(raw.jobs[0].url,job.positionUrl);assert.equal(raw.searchKeyword,'AI Agent');
 const normalized=sanitizeSourceActionPage('zhilian',ctx.location.href,1,raw);assert.equal(normalized.records.length,1);assert.equal(normalized.records[0].payload.url,job.positionUrl.replace('http:','https:'));
 job.name='另一个岗位';assert.equal(runInNewContext(sourceListExtractionScript('zhilian'),ctx).jobs.length,0);
});

test('Zhaopin uses the observed site search route and explicit city scope',()=>{
 const url=new URL(buildSourceSearchUrl('zhilian','AI Agent','深圳',1));
 assert.equal(url.origin+url.pathname,'https://www.zhaopin.com/jobs/');assert.equal(url.searchParams.get('pageMode'),'search');assert.equal(url.searchParams.get('jl'),'765');
 assert.equal(new URL(buildSourceSearchUrl('zhilian','AI','',1)).searchParams.get('jl'),'489');
 assert.throws(()=>buildSourceSearchUrl('zhilian','AI','未核对城市',1),/source_scope_mismatch/);
});


test('observed HTTP official detail links upgrade only their transport, never an unknown host',async()=>{
 const {normalizeZhilianJobUrl}=await import('../dist-electron/main/sources/source-actions.js');
 assert.equal(normalizeZhilianJobUrl('http://www.zhaopin.com/jobdetail/CC000374740J40791423406.htm'),'https://www.zhaopin.com/jobdetail/CC000374740J40791423406.htm');
 for(const url of ['http://evil.example/jobdetail/1.htm','http://www.zhaopin.com/companydetail/1.htm','http://www.zhaopin.com:8080/jobdetail/1.htm','http://user@www.zhaopin.com/jobdetail/1.htm'])assert.equal(normalizeZhilianJobUrl(url),null);
});
