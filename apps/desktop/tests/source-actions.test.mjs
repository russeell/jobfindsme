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
 assert.equal(url.searchParams.has(id==='zhilian'?'jl':'jobArea'),false);
 }
});


test('passive source observation separates splash, login form, and readable list without searches',async()=>{
 const {runInNewContext}=await import('node:vm');
 const script=passiveSourceObservationScript('zhilian');
 function observe(text,inputs,cards,account=false){const node=(shown=true)=>({textContent:'我的简历',getAttribute:()=>'',matches:()=>false,getBoundingClientRect:()=>({width:shown?10:0,height:shown?10:0})});return runInNewContext(script,{location:{href:'https://www.zhaopin.com/',hostname:'www.zhaopin.com'},getComputedStyle:()=>({display:'block',visibility:'visible',opacity:1}),document:{body:{innerText:text},querySelectorAll(selector){if(selector.startsWith('input'))return Array.from({length:inputs==='hidden'?1:inputs},()=>node(inputs!=='hidden'));if(selector.startsWith('a[href*="/resume"]'))return account?[node(account==='hidden'?false:true)]:[];return Array.from({length:cards},()=>node(true));}}});}
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
 const visible={textContent:'',innerText:'',getAttribute:()=>'',matches:()=>false,getBoundingClientRect:()=>({width:20,height:20})};
 const avatar={...visible};
 const header=(avatarVisible=true)=>({...visible,innerText:'职位 消息 我要招人 账户',querySelectorAll:selector=>selector.includes('alt*="头像"')?avatarVisible?[avatar]:[{...avatar,getBoundingClientRect:()=>({width:0,height:0})}]:[]});
 const anonymousHeader={...visible,innerText:'职位 消息 我要招人',querySelectorAll:()=>[]};
 const card={...visible,querySelector(selector){if(selector==='h3')return {textContent:'工程师'};if(selector.includes('/jobdetail/'))return {href:'https://www.zhaopin.com/jobdetail/example.htm'};return null;}};
 const context=(authenticated,loginHost=false,options={})=>({
  location:{href:loginHost?'https://passport.zhaopin.com/login':'https://www.zhaopin.com/jobs',hostname:loginHost?'passport.zhaopin.com':'www.zhaopin.com'},
  getComputedStyle:()=>({display:'block',visibility:'visible',opacity:1}),
  document:{body:{innerText:'热门职位 登录查看更多相关职位 立即登录'},querySelector:()=>null,querySelectorAll(selector){
   if(selector.startsWith('header,'))return [authenticated?header(!options.hiddenAvatar):anonymousHeader];
   if(selector.startsWith('input'))return options.phoneInput?[visible]:[];
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
