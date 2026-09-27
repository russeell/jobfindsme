import test from 'node:test';
import assert from 'node:assert/strict';
import {EventEmitter} from 'node:events';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import vm from 'node:vm';
const file=new URL('../dist-electron/main/browser/source-browser.js',import.meta.url);
const nativeRequire=createRequire(file);
class FakeView {
  constructor(options){this.options=options;this.visible=false;const wc=new EventEmitter();this.webContents=wc;let urls=[],index=-1,closed=false;wc.getURL=()=>urls[index]||'';wc.getTitle=()=>wc.getURL();wc.isLoading=wc.isLoadingMainFrame=()=>false;wc.isDestroyed=()=>closed;wc.close=()=>{closed=true;};wc.setWindowOpenHandler=handler=>{wc.popup=handler;};wc.loadURL=async url=>{urls=urls.slice(0,index+1);urls.push(url);index++;};wc.reload=()=>{};let zoom=1;wc.setZoomFactor=v=>{zoom=v;};wc.getZoomFactor=()=>zoom;wc.getUserAgent=()=>wc.userAgent||'Mozilla/5.0 Chrome/152';wc.setUserAgent=value=>{wc.userAgent=value;};wc.executeJavaScript=async()=>({width:Math.max(1280,640/zoom),viewport:640/zoom});wc.navigationHistory={canGoBack:()=>index>0,canGoForward:()=>index<urls.length-1,goBack:()=>index--,goForward:()=>index++};FakeView.onCreate?.(this);}
  setVisible(value){this.visible=value;}setBounds(bounds){this.bounds=bounds;}
}
const module={exports:{}};
vm.runInThisContext(`(function(require,module,exports){${readFileSync(file,'utf8')}\n})`)((id)=>id==='electron'?{WebContentsView:FakeView}:nativeRequire(id),module,module.exports);
const {SourceBrowserManager}=module.exports;
function setup(onBossPage,onSourcePage){const w=new EventEmitter();w.children=[];w.contentView={addChildView:v=>w.children.push(v),removeChildView:v=>{w.children=w.children.filter(x=>x!==v);}};w.getContentSize=()=>[1240,800];w.isDestroyed=()=>false;return {w,m:new SourceBrowserManager(w,onBossPage,onSourcePage)};}
const bounds={x:650,y:100,width:590,height:700};
const a='https://www.liepin.com/job/1.shtml';const b='https://www.liepin.com/job/2.shtml';
test('source buttons reopen public homepages without forcing sign-in pages',async()=>{
 const {m}=setup();
 await m.show('liepin',bounds);assert.equal(m.state().url,'https://www.liepin.com/');
 await m.show('wuyou',bounds);assert.equal(m.state().url,'https://www.51job.com/');
 m.destroy();
});
test('shutdown flushes each opened persistent source session once',async()=>{
 const sessions=new Map(),flushed=[];
 FakeView.onCreate=view=>{
  const partition=view.options.webPreferences.partition;
  if(!sessions.has(partition)){
   const session=new EventEmitter();session.cookies={flushStore:async()=>{flushed.push(partition);}};
   session.setPermissionCheckHandler=()=>{};session.setPermissionRequestHandler=()=>{};
   session.webRequest={onBeforeRequest:()=>{}};sessions.set(partition,session);
  }
  view.webContents.session=sessions.get(partition);
 };
 const {m}=setup();
 try{
  await m.show('liepin',bounds);await m.show('liepin',bounds,'https://www.liepin.com/job/1');
  await m.show('wuyou',bounds);await m.flushSessions();
  assert.deepEqual(flushed.sort(),['persist:jobfindsme-source-liepin','persist:jobfindsme-source-wuyou']);
 }finally{FakeView.onCreate=undefined;m.destroy();}
});
test('zoom is bounded and restored per tab; fit width reads the document without rewriting it',async()=>{const {w,m}=setup();await m.show('liepin',bounds,a);const one=m.state().activeTabId;await m.command('fit-width');assert.equal(m.state().zoom,.5);await m.show('liepin',bounds,b);assert.equal(m.state().zoom,1);await m.command('zoom-in');assert.equal(m.state().zoom,1.1);m.selectTab(one);assert.equal(w.children[0].webContents.getZoomFactor(),.5);for(let i=0;i<10;i++)await m.command('zoom-out');assert.equal(m.state().zoom,.3);await m.command('zoom-reset');assert.equal(m.state().zoom,1);m.destroy();});
test('blocked navigation stays with its tab and removes query secrets from notices',async()=>{const {w,m}=setup();await m.show('liepin',bounds,a);const one=m.state().activeTabId;let prevented=false;w.children[0].webContents.emit('will-redirect',{preventDefault(){prevented=true;}},'file:///private/path?token=private',false,true);assert.equal(prevented,true);assert.match(m.state().notice,/重定向.*private\/path/);assert.doesNotMatch(m.state().notice,/token=private/);await m.show('liepin',bounds,b);assert.equal(m.state().notice,'');m.selectTab(one);assert.match(m.state().notice,/此协议/);await m.command('reload');assert.equal(m.state().notice,'');m.destroy();});
test('tabs preserve per-page history, reuse URL, share source partition and isolate background',async()=>{const {w,m}=setup();await m.show('liepin',bounds,a);m.layout(bounds);const one=m.state().activeTabId;const view=w.children[0];await view.webContents.loadURL(a+'&detail=1');await m.show('liepin',bounds,b);const two=m.state().activeTabId;const second=w.children[0];assert.equal(m.state().tabs.length,2);assert.equal(view.options.webPreferences.partition,second.options.webPreferences.partition);assert.equal(view.visible,false);assert.equal(w.children.length,1);assert.equal(m.state().canGoBack,false);m.selectTab(one);assert.equal(m.state().canGoBack,true);m.command('back');assert.equal(m.state().url,a);m.selectTab(two);assert.equal(m.state().url,b);await m.show('liepin',bounds,b);assert.equal(m.state().tabs.length,2);const background=m.backgroundView('liepin');await background.webContents.loadURL(a);assert.equal(m.state().url,b);assert.notEqual(background,second);m.layout(null);assert.equal(second.visible,false);m.selectTab(one);assert.equal(view.visible,false);m.layout(bounds);assert.equal(view.visible,true);m.closeTab(one);assert.equal(m.state().activeTabId,two);assert.equal(view.webContents.isDestroyed(),true);m.destroy();assert.equal(m.state().tabs.length,0);assert.equal(background.webContents.isDestroyed(),true);});
test('cross-site popups retain WindowProxy and secure opener partition while bounding resources',async()=>{
 const {w,m}=setup();await m.show('liepin',bounds,a);const handler=w.children[0].webContents.popup;
 const popup=handler({url:'about:blank'});assert.equal(popup.action,'allow');
 const adopted=new EventEmitter();adopted.getURL=()=>'';adopted.getTitle=()=>'';adopted.isLoading=adopted.isLoadingMainFrame=()=>false;adopted.isDestroyed=()=>false;adopted.close=()=>{};adopted.setWindowOpenHandler=()=>{};adopted.setZoomFactor=()=>{};adopted.getZoomFactor=()=>1;adopted.loadURL=async()=>{};adopted.executeJavaScript=async()=>({});adopted.navigationHistory={canGoBack:()=>false,canGoForward:()=>false};
 const options={webContents:adopted,webPreferences:{partition:'untrusted',preload:'/bad',nodeIntegration:true,sandbox:false}};const child=popup.createWindow(options);
 assert.equal(child,w.children[0].webContents);assert.equal(m.state().tabs.length,2);
 assert.equal(w.children[0].options,options);assert.equal(w.children[0].options.webContents,adopted);assert.equal(child,w.children[0].webContents);
 assert.equal(handler({url:'javascript:alert(1)'}).action,'deny');assert.equal(handler({url:'http://127.0.0.1/'}).action,'deny');
 for(let i=2;i<12;i++)await m.show('liepin',bounds,`https://www.liepin.com/job/${i+10}.shtml`);
 assert.equal(handler({url:'about:blank'}).action,'deny');assert.equal(m.state().tabs.length,12);m.destroy();
});
test('teardown after native window destruction closes contents without reading native layout',async()=>{const {w,m}=setup();await m.show('liepin',bounds,a);const view=w.children[0];const background=m.backgroundView('liepin');w.isDestroyed=()=>true;w.getContentSize=()=>{throw Error('window destroyed');};w.contentView.removeChildView=()=>{throw Error('native view destroyed');};assert.doesNotThrow(()=>m.destroy());assert.equal(view.webContents.isDestroyed(),true);assert.equal(background.webContents.isDestroyed(),true);assert.equal(m.state().tabs.length,0);});

test('research extraction follows an allowed SPA abort and always releases its temporary view',async()=>{const {m}=setup();let temporary;FakeView.onCreate=view=>{temporary=view;view.webContents.loadURL=async()=>{view.webContents.getURL=()=> 'https://www.liepin.com/job/example.shtml';throw Object.assign(new Error('redirect'),{code:'ERR_ABORTED'});};view.webContents.executeJavaScript=async()=>({title:'Test role',company:'Tencent',description:'Verified page text '.repeat(10)});};try{const result=await m.readResearchJob('liepin',a);assert.equal(result.title,'Test role');assert.match(result.url,/liepin.com/);assert.equal(temporary.webContents.isDestroyed(),true);assert.equal(m.state().tabs.length,0);}finally{FakeView.onCreate=undefined;m.destroy();}});

test('foreground permits arbitrary HTTP(S) but background remains source-scoped',async()=>{const {w,m}=setup();await m.show('web',bounds,'http://jobs.example.org/');assert.equal(w.children[0].options.webPreferences.partition,'persist:jobfindsme-web');const view=w.children[0];let prevented=false;view.webContents.emit('will-redirect',{preventDefault(){prevented=true;}},'https://sso.example.net/',false,true);assert.equal(prevented,false);const bg=m.backgroundView('liepin');bg.webContents.emit('will-redirect',{preventDefault(){prevented=true;}},'https://sso.example.net/',false,true);assert.equal(prevented,true);assert.deepEqual(view.options.webPreferences,{partition:'persist:jobfindsme-web',nodeIntegration:false,contextIsolation:true,sandbox:true,webSecurity:true,allowRunningInsecureContent:false});await assert.rejects(m.readResearchJob('liepin','https://sso.example.net/'),/未支持/);m.destroy();});

test('fit width is capped at 100 percent and idempotent from manual zoom levels',async()=>{const {w,m}=setup();await m.show('liepin',bounds,a);for(const start of [1.2,1,.6]){await m.command('zoom-reset');const command=start>1?'zoom-in':'zoom-out';for(let n=0;n<Math.round(Math.abs(start-1)*10);n++)await m.command(command);await m.command('fit-width');const fit=m.state().zoom;assert.equal(fit,.5);await m.command('fit-width');assert.equal(m.state().zoom,fit);}w.children[0].webContents.executeJavaScript=async()=>({width:640,viewport:640});await m.command('fit-width');assert.equal(m.state().zoom,1);m.destroy();});

test('address navigation reuses its tab and session, supports back/forward, and rejects unsafe URLs',async()=>{
 const {w,m}=setup();await m.show('web',bounds,'https://example.com/');m.layout(bounds);const id=m.state().activeTabId,view=w.children[0];const other='https://docs.example.org/page';
 await m.navigateTab(id,other);assert.equal(m.state().tabs.length,1);assert.equal(m.state().activeTabId,id);assert.equal(w.children[0],view);assert.equal(m.state().url,other);assert.equal(m.state().canGoBack,true);
 await m.command('back');assert.equal(m.state().url,'https://example.com/');assert.equal(m.state().canGoForward,true);await m.command('forward');assert.equal(m.state().url,other);
 for(const url of ['file:///etc/passwd','javascript:alert(1)','http://localhost:8000'])await assert.rejects(m.navigateTab(id,url),/HTTP|本地/);
 await assert.rejects(m.navigateTab('closed',a),/关闭/);assert.equal(m.state().url,other);assert.equal(m.state().tabs.length,1);m.destroy();
});

test('BOSS observation never revives an expired session from a stale foreground DOM',async()=>{
 const ready={authenticated:true,readable:true,loginRequired:false,blocked:null,empty:false,ended:false,jobs:[]};let snapshot=ready,seen=0;
 const {w,m}=setup(async page=>{seen++;if(page.authenticated&&m.boss.paused!=='risk_control')m.boss.resume();});
 FakeView.onCreate=view=>{view.webContents.executeJavaScript=async()=>snapshot;};
 try{await m.show('boss',bounds,'https://www.zhipin.com/web/geek/jobs');m.layout(bounds);await m.observeBoss();assert.equal(seen,1);m.boss.pause('login_required');await m.observeBoss();assert.equal(seen,1);assert.equal(m.boss.paused,'login_required');
 snapshot={...ready,authenticated:false,loginRequired:true};await m.observeBoss();snapshot=ready;await m.observeBoss();assert.equal(m.boss.paused,undefined);
 m.boss.pause('risk_control');await m.observeBoss();assert.equal(m.boss.paused,'risk_control');await m.observeBoss(true);assert.equal(m.boss.paused,'risk_control');
 const bg=m.backgroundView('boss');assert.equal(bg.options.webPreferences.partition,w.children[0].options.webPreferences.partition);assert.equal(bg.options.webPreferences.partition,'persist:jobfindsme-source-boss');
 }finally{FakeView.onCreate=undefined;m.destroy();}
});

test('returning to BOSS refreshes local observation without explicit risk recovery',async()=>{
 const flags=[];const {m}=setup(async(_page,explicit,revisit)=>{flags.push({explicit,revisit});});
 FakeView.onCreate=view=>{view.webContents.executeJavaScript=async()=>({authenticated:true,readable:true,loginRequired:false,blocked:null,jobs:[]});};
 try{await m.show('boss',bounds,'https://www.zhipin.com/web/geek/jobs');m.layout(bounds);await new Promise(resolve=>setTimeout(resolve,0));
   m.boss.pause('risk_control');await m.show('liepin',bounds);m.selectTab(m.state().tabs.find(tab=>tab.sourceId==='boss').id);
   await new Promise(resolve=>setTimeout(resolve,0));
   assert.equal(m.boss.paused,'risk_control');assert.equal(flags.at(-1)?.explicit,false);assert.equal(flags.at(-1)?.revisit,true);
 }finally{FakeView.onCreate=undefined;m.destroy();}
});

test('checking BOSS reads its loaded tab after another platform becomes active',async()=>{
 let observed=0;const {w,m}=setup(async page=>{if(page.authenticated)observed++;});
 FakeView.onCreate=view=>{if(view.options.webPreferences.partition==='persist:jobfindsme-source-boss')view.webContents.executeJavaScript=async()=>({authenticated:true,readable:false,loginRequired:false,blocked:null,jobs:[]});};
 try{await m.show('boss',bounds,'https://www.zhipin.com/web/geek/jobs');await m.show('zhilian',bounds,'https://www.zhaopin.com/');const active=m.state().activeTabId;await m.refreshPlatformObservation('boss');assert.equal(observed,1);assert.equal(m.state().activeTabId,active);assert.equal(w.children[0].options.webPreferences.partition,'persist:jobfindsme-source-zhilian');}finally{FakeView.onCreate=undefined;m.destroy();}
});

test('search tab entering a registered source opens its persistent session',async()=>{
 const {w,m}=setup();await m.show('web',bounds,'https://www.bing.com/search?q=jobs');m.layout(bounds);
 const web=m.state().activeTabId;
 const result=await m.navigateTab(web,'https://www.zhaopin.com/');
 assert.equal(result.tabs.length,2);
 assert.equal(result.tabs.find(t=>t.id===web).sourceId,'web');
 assert.equal(result.tabs.find(t=>t.id===result.activeTabId).sourceId,'zhilian');
 assert.equal(w.children[0].options.webPreferences.partition,'persist:jobfindsme-source-zhilian');
 m.destroy();
});

test('ordinary links and redirects from web search route into platform sessions',async()=>{
 const {w,m}=setup();await m.show('web',bounds,'https://www.bing.com/search?q=jobs');m.layout(bounds);
 const web=w.children[0];let stopped=false;
 web.webContents.emit('will-navigate',{preventDefault(){stopped=true;}},'https://www.zhaopin.com/jobs');
 await new Promise(resolve=>setTimeout(resolve,0));
 assert.equal(stopped,true);assert.equal(w.children[0].options.webPreferences.partition,'persist:jobfindsme-source-zhilian');
 m.selectTab(m.state().tabs.find(tab=>tab.sourceId==='web').id);stopped=false;
 web.webContents.emit('will-redirect',{preventDefault(){stopped=true;}},'https://www.51job.com/',false,true);
 await new Promise(resolve=>setTimeout(resolve,0));
 assert.equal(stopped,true);assert.equal(w.children[0].options.webPreferences.partition,'persist:jobfindsme-source-wuyou');
 m.destroy();
});

test('Zhilian foreground and background user agents remove non-header characters for the login widget',async()=>{
 const {m}=setup();let used;
 FakeView.onCreate=view=>{view.webContents.getUserAgent=()=> 'Mozilla/5.0 JobFindsMe测试版/0.1 Chrome/152 Electron/44 Safari/537.36';view.webContents.setUserAgent=value=>{used=value;};};
 try{m.backgroundView('zhilian');assert.equal(used,'Mozilla/5.0 JobFindsMe/0.1 Chrome/152 Electron/44 Safari/537.36');used=undefined;await m.show('zhilian',bounds,'https://www.zhaopin.com/');assert.equal(used,'Mozilla/5.0 JobFindsMe/0.1 Chrome/152 Electron/44 Safari/537.36');}finally{FakeView.onCreate=undefined;m.destroy();}
});

test('51job background searches release their renderer on success and failure, preserving foreground',async()=>{
 const {m,w}=setup();const created=[];
 await m.show('wuyou',bounds);const foreground=w.children[0];
 FakeView.onCreate=view=>{created.push(view);view.webContents.executeJavaScript=async()=>({jobs:[],empty:true});};
 try{
  await m.searchPage('wuyou',{keyword:'test',city:'',page:1,forceRefresh:true});
  assert.equal(created[0].webContents.isDestroyed(),true);
  assert.equal(foreground.webContents.isDestroyed(),false);
  assert.equal(created[0].options.webPreferences.partition,foreground.options.webPreferences.partition);
  FakeView.onCreate=view=>{created.push(view);view.webContents.loadURL=async()=>{throw Error('load failed');};};
  await assert.rejects(m.searchPage('wuyou',{keyword:'test',city:'',page:1,forceRefresh:true}),/load failed/);
  assert.equal(created.length,2);assert.equal(created[1].webContents.isDestroyed(),true);
  assert.equal(foreground.webContents.isDestroyed(),false);
 }finally{FakeView.onCreate=undefined;m.destroy();}
});

test('source search reads at DOM readiness without waiting for late resources',async()=>{
 const {m}=setup();let background;
 FakeView.onCreate=view=>{if(view.options.webPreferences?.partition==='persist:jobfindsme-source-zhilian'){background=view;
  view.webContents.loadURL=url=>{view.webContents.getURL=()=>url;queueMicrotask(()=>view.webContents.emit('dom-ready'));return new Promise(()=>{});};
  view.webContents.executeJavaScript=async()=>({jobs:[{title:'工程师',company:'示例',url:'https://www.zhaopin.com/jobdetail/example.htm'}],hasNext:false});}};
 try{const began=Date.now();const page=await m.searchPage('zhilian',{keyword:'工程师',city:'',page:1,forceRefresh:true});
  assert.equal(page.records.length,1);assert.ok(Date.now()-began<1000);assert.equal(background.webContents.isDestroyed(),false);
 }finally{FakeView.onCreate=undefined;m.destroy();}
});

test('cancelling a loading background source stops and releases its renderer',async()=>{
 const {m}=setup();let background,rejectLoad,started;
 const loading=new Promise(resolve=>{started=resolve;});
 FakeView.onCreate=view=>{if(view.options.webPreferences?.partition==='persist:jobfindsme-source-wuyou'){background=view;
  view.webContents.isLoadingMainFrame=()=>true;
  view.webContents.loadURL=url=>{view.webContents.getURL=()=>url;started();return new Promise((_,reject)=>{rejectLoad=reject;});};
  view.webContents.stop=()=>rejectLoad(Error('cancelled'));
 }};
 try{const work=m.searchPage('wuyou',{keyword:'工程师',city:'',page:1,forceRefresh:true});await loading;m.cancelCareerSearch();
  await assert.rejects(work,/cancelled/);assert.equal(background.webContents.isDestroyed(),true);
 }finally{FakeView.onCreate=undefined;m.destroy();}
});

test('a cancelled DOM read exits promptly without caching its late result or cancelling another source',async()=>{
 const {m}=setup();let started,finish,zhilianViews=0;
 const reading=new Promise(resolve=>{started=resolve;});
 const job=(url)=>({jobs:[{title:'工程师',company:'示例',url}],hasNext:false});
 FakeView.onCreate=view=>{if(!view.options.webPreferences?.partition)return;
  const id=view.options.webPreferences.partition.includes('zhilian')?'zhilian':'wuyou';
  if(id==='zhilian')zhilianViews++;
  view.webContents.executeJavaScript=()=>id==='wuyou'?Promise.resolve(job('https://www.51job.com/job/123')):
    zhilianViews===1?new Promise(resolve=>{finish=resolve;started();}):Promise.resolve(job('https://www.zhaopin.com/jobdetail/123.htm'));
 };
 try{
  const first=m.searchPage('zhilian',{keyword:'工程师',city:'',page:1,forceRefresh:true});
  const second=m.searchPage('wuyou',{keyword:'工程师',city:'',page:1,forceRefresh:true});
  await reading;m.cancelCareerSearch('zhilian');
  await assert.rejects(first,/cancelled/);
  assert.equal((await second).records.length,1);
  finish(job('https://www.zhaopin.com/jobdetail/late.htm'));
  const retried=await m.searchPage('zhilian',{keyword:'工程师',city:'',page:1});
  assert.equal(retried.records.length,1);assert.equal(zhilianViews,2);
 }finally{FakeView.onCreate=undefined;m.destroy();}
});

test('visible Zhaopin inspection never opens background search and keeps normalized cards',async()=>{
 const {w,m}=setup();
 try{
  await m.show('zhilian',bounds,'https://www.zhaopin.com/jobs');m.layout(bounds);
  const wc=w.children[0].webContents;let reads=0;
  wc.executeJavaScript=async()=>{reads++;return {url:wc.getURL(),kind:'list',authenticated:true,cardCount:1,formCount:0,jobs:[{title:'大模型研发',company:'示例公司',location:'上海',url:'https://www.zhaopin.com/jobdetail/abc.htm'}]};};
  const result=await m.readVisibleZhilian();assert.equal(result.records.length,1);assert.equal(reads,1);assert.equal(m.backgrounds.size,0);assert.equal(wc.getURL(),'https://www.zhaopin.com/jobs');
  m.hide();assert.equal(await m.readVisibleZhilian(),undefined);assert.equal(reads,1);
 }finally{m.destroy();}
});

test('Zhaopin search keeps synonymous titles, rejects redirected recommendations and unknown city',async()=>{
 const {m}=setup();let redirect=false;
 FakeView.onCreate=view=>{const original=view.webContents.loadURL;view.webContents.loadURL=url=>original(redirect?'https://www.zhaopin.com/jobs':url);view.webContents.executeJavaScript=async()=>({jobs:[{title:'大模型应用研发',company:'示例',location:'上海',url:'https://www.zhaopin.com/jobdetail/abc.htm'},{title:'算法工程师',company:'示例',location:'',url:'https://www.zhaopin.com/jobdetail/def.htm'}]});};
 try{const result=await m.searchPage('zhilian',{keyword:'AI Agent',city:'上海',page:1,forceRefresh:true});assert.equal(result.records.length,1);assert.equal(result.records[0].payload.title,'大模型应用研发');
 redirect=true;await assert.rejects(m.searchPage('zhilian',{keyword:'AI Agent',city:'上海',page:1,forceRefresh:true}),/未保留本次关键词/);
 }finally{FakeView.onCreate=undefined;m.destroy();}
});


test('hidden Zhaopin tabs cannot overwrite the current source observation',async()=>{
 let seen=0;const {w,m}=setup(undefined,async()=>{seen++;});
 try{
  await m.show('zhilian',bounds,'https://www.zhaopin.com/jobs');const wc=w.children[0].webContents;
  wc.executeJavaScript=async()=>({url:wc.getURL(),kind:'list',authenticated:true,cardCount:0,formCount:0,jobs:[]});
  await m.refreshPlatformObservation('zhilian');assert.equal(seen,0);
  m.layout(bounds);await m.refreshPlatformObservation('zhilian');assert.ok(seen>0);
  await m.show('liepin',bounds);const before=seen;await m.refreshPlatformObservation('zhilian');assert.equal(seen,before);
 }finally{m.destroy();}
});


test('one-click Zhaopin check opens one persistent foreground page and waits for jobs without background requests',async()=>{
 const {w,m}=setup();let ready=false,loads=0;
 FakeView.onCreate=view=>{const load=view.webContents.loadURL;view.webContents.loadURL=async url=>{loads++;await load(url);};view.webContents.executeJavaScript=async()=>({url:view.webContents.getURL(),kind:ready?'list':'unknown',authenticated:ready,cardCount:ready?1:0,formCount:0,jobs:ready?[{title:'AI研发',company:'示例',location:'深圳',url:'https://www.zhaopin.com/jobdetail/fixture.htm'}]:[]});};
 try{
  m.prepareZhilianCheck(bounds);assert.equal(w.children[0].webContents.getURL(),'https://www.zhaopin.com/jobs/');assert.equal(w.children[0].options.webPreferences.partition,'persist:jobfindsme-source-zhilian');
  const timer=setTimeout(()=>{ready=true;},20);const result=await m.waitForVisibleZhilian(new AbortController().signal);clearTimeout(timer);
  assert.equal(result.records.length,1);m.prepareZhilianCheck(bounds);assert.equal(loads,1);assert.equal(m.state().tabs.length,1);assert.equal(m.backgrounds.size,0);
 }finally{FakeView.onCreate=undefined;m.destroy();}
});


test('Zhaopin async cards arriving after the old three-second cutoff are still read',async()=>{
 const {m}=setup();let reads=0;
 FakeView.onCreate=view=>{view.webContents.executeJavaScript=async()=>++reads<=13?{jobs:[]}:{jobs:[{title:'AI应用员',company:'示例',location:'深圳',url:'https://www.zhaopin.com/jobdetail/late.htm'}],searchKeyword:'AI Agent'};};
 try{const result=await m.searchPage('zhilian',{keyword:'AI Agent',city:'深圳',page:1});assert.equal(result.records.length,1);assert.equal(reads,14);}
 finally{FakeView.onCreate=undefined;m.destroy();}
});


test('Zhaopin list polling respects the caller deadline and identifies the failure stage',async()=>{
 const {m}=setup();FakeView.onCreate=view=>{view.webContents.executeJavaScript=async()=>({jobs:[]});};
 try{const start=Date.now();await assert.rejects(m.searchPage('zhilian',{keyword:'AI',city:'深圳',page:1,deadline:start+80}),/source_timeout:.*source_stage=extract/);assert.ok(Date.now()-start<500);}
 finally{FakeView.onCreate=undefined;m.destroy();}
});


test('an exact visible Zhaopin search is reused without navigation, duplicate renderer or bypassing scope',async()=>{
 const {m,w}=setup();const target='https://www.zhaopin.com/jobs/?pageMode=search&jl=765&kw=AI+Agent';
 try{await m.show('zhilian',bounds,target);m.layout(bounds);const view=w.children[0];let navigation=0;
 view.webContents.loadURL=async()=>{navigation++;};view.webContents.executeJavaScript=async()=>({searchKeyword:'AI Agent',jobs:[{title:'AI应用员',company:'示例',location:'深圳',url:'http://www.zhaopin.com/jobdetail/real.htm'}]});
 const page=await m.searchPage('zhilian',{keyword:'AI Agent',city:'深圳',page:1});assert.equal(page.records.length,1);assert.equal(navigation,0);assert.equal(m.backgrounds.size,0);assert.equal(view.webContents.isDestroyed(),false);
 let backgroundReads=0;FakeView.onCreate=v=>{v.webContents.executeJavaScript=async()=>{backgroundReads++;return {jobs:[],empty:true};};};
 await m.searchPage('zhilian',{keyword:'Java',city:'深圳',page:1});assert.equal(backgroundReads,1);assert.equal(m.state().tabs.length,2);
 m.hide();await m.searchPage('zhilian',{keyword:'AI Agent',city:'深圳',page:1,forceRefresh:true});assert.equal(backgroundReads,2);assert.equal(view.webContents.isDestroyed(),false);
 }finally{FakeView.onCreate=undefined;m.destroy();}
});


test('Zhaopin user searches open a new source tab and retain its failed page for diagnosis',async()=>{
 const {m,w}=setup();const events=[];w.webContents={send:(...args)=>events.push(args)};
 await m.show('zhilian',bounds,'https://www.zhaopin.com/jobdetail/original.htm');const original=w.children[0];
 FakeView.onCreate=view=>{view.webContents.executeJavaScript=async()=>({jobs:[],empty:true,searchKeyword:'AI Agent'});};
 try{await m.searchPage('zhilian',{keyword:'AI Agent',city:'深圳',page:1});assert.equal(m.state().tabs.length,2);assert.equal(original.webContents.isDestroyed(),false);assert.equal(original.webContents.getURL(),'https://www.zhaopin.com/jobdetail/original.htm');assert.equal(events[0][0],'desktop:source-browser-opened');assert.equal(m.backgrounds.size,0);assert.match(m.state().url,/jl=765/);}
 finally{FakeView.onCreate=undefined;m.destroy();}
});
