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
function setup(onBossPage){const w=new EventEmitter();w.children=[];w.contentView={addChildView:v=>w.children.push(v),removeChildView:v=>{w.children=w.children.filter(x=>x!==v);}};w.getContentSize=()=>[1240,800];w.isDestroyed=()=>false;return {w,m:new SourceBrowserManager(w,onBossPage)};}
const bounds={x:650,y:100,width:590,height:700};
const a='https://careers.tencent.com/jobdesc.html?postId=1';const b='https://careers.tencent.com/jobdesc.html?postId=2';
test('source buttons reopen public homepages without forcing sign-in pages',async()=>{
 const {m}=setup();
 await m.show('liepin',bounds);assert.equal(m.state().url,'https://www.liepin.com/');
 await m.show('wuyou',bounds);assert.equal(m.state().url,'https://www.51job.com/');
 await m.show('company_16',bounds);assert.equal(m.state().url,'https://app.mokahr.com/social-recruitment/step/94904#/');
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
test('zoom is bounded and restored per tab; fit width reads the document without rewriting it',async()=>{const {w,m}=setup();await m.show('company_01',bounds,a);const one=m.state().activeTabId;await m.command('fit-width');assert.equal(m.state().zoom,.5);await m.show('company_01',bounds,b);assert.equal(m.state().zoom,1);await m.command('zoom-in');assert.equal(m.state().zoom,1.1);m.selectTab(one);assert.equal(w.children[0].webContents.getZoomFactor(),.5);for(let i=0;i<10;i++)await m.command('zoom-out');assert.equal(m.state().zoom,.3);await m.command('zoom-reset');assert.equal(m.state().zoom,1);m.destroy();});
test('blocked navigation stays with its tab and removes query secrets from notices',async()=>{const {w,m}=setup();await m.show('company_01',bounds,a);const one=m.state().activeTabId;let prevented=false;w.children[0].webContents.emit('will-redirect',{preventDefault(){prevented=true;}},'file:///private/path?token=private',false,true);assert.equal(prevented,true);assert.match(m.state().notice,/重定向.*private\/path/);assert.doesNotMatch(m.state().notice,/token=private/);await m.show('company_01',bounds,b);assert.equal(m.state().notice,'');m.selectTab(one);assert.match(m.state().notice,/此协议/);await m.command('reload');assert.equal(m.state().notice,'');m.destroy();});
test('tabs preserve per-page history, reuse URL, share source partition and isolate background',async()=>{const {w,m}=setup();await m.show('company_01',bounds,a);m.layout(bounds);const one=m.state().activeTabId;const view=w.children[0];await view.webContents.loadURL(a+'&detail=1');await m.show('company_01',bounds,b);const two=m.state().activeTabId;const second=w.children[0];assert.equal(m.state().tabs.length,2);assert.equal(view.options.webPreferences.partition,second.options.webPreferences.partition);assert.equal(view.visible,false);assert.equal(w.children.length,1);assert.equal(m.state().canGoBack,false);m.selectTab(one);assert.equal(m.state().canGoBack,true);m.command('back');assert.equal(m.state().url,a);m.selectTab(two);assert.equal(m.state().url,b);await m.show('company_01',bounds,b);assert.equal(m.state().tabs.length,2);const background=m.backgroundView('company_01');await background.webContents.loadURL(a);assert.equal(m.state().url,b);assert.notEqual(background,second);m.layout(null);assert.equal(second.visible,false);m.selectTab(one);assert.equal(view.visible,false);m.layout(bounds);assert.equal(view.visible,true);m.closeTab(one);assert.equal(m.state().activeTabId,two);assert.equal(view.webContents.isDestroyed(),true);m.destroy();assert.equal(m.state().tabs.length,0);assert.equal(background.webContents.isDestroyed(),true);});
test('cross-site popups retain WindowProxy and secure opener partition while bounding resources',async()=>{
 const {w,m}=setup();await m.show('company_01',bounds,a);const handler=w.children[0].webContents.popup;
 const popup=handler({url:'about:blank'});assert.equal(popup.action,'allow');
 const adopted=new EventEmitter();adopted.getURL=()=>'';adopted.getTitle=()=>'';adopted.isLoading=adopted.isLoadingMainFrame=()=>false;adopted.isDestroyed=()=>false;adopted.close=()=>{};adopted.setWindowOpenHandler=()=>{};adopted.setZoomFactor=()=>{};adopted.getZoomFactor=()=>1;adopted.loadURL=async()=>{};adopted.executeJavaScript=async()=>({});adopted.navigationHistory={canGoBack:()=>false,canGoForward:()=>false};
 const options={webContents:adopted,webPreferences:{partition:'untrusted',preload:'/bad',nodeIntegration:true,sandbox:false}};const child=popup.createWindow(options);
 assert.equal(child,w.children[0].webContents);assert.equal(m.state().tabs.length,2);
 assert.equal(w.children[0].options,options);assert.equal(w.children[0].options.webContents,adopted);assert.equal(child,w.children[0].webContents);
 assert.equal(handler({url:'javascript:alert(1)'}).action,'deny');assert.equal(handler({url:'http://127.0.0.1/'}).action,'deny');
 for(let i=2;i<12;i++)await m.show('company_01',bounds,`https://careers.tencent.com/jobdesc.html?postId=${i+10}`);
 assert.equal(handler({url:'about:blank'}).action,'deny');assert.equal(m.state().tabs.length,12);m.destroy();
});
test('teardown after native window destruction closes contents without reading native layout',async()=>{const {w,m}=setup();await m.show('company_01',bounds,a);const view=w.children[0];const background=m.backgroundView('company_01');w.isDestroyed=()=>true;w.getContentSize=()=>{throw Error('window destroyed');};w.contentView.removeChildView=()=>{throw Error('native view destroyed');};assert.doesNotThrow(()=>m.destroy());assert.equal(view.webContents.isDestroyed(),true);assert.equal(background.webContents.isDestroyed(),true);assert.equal(m.state().tabs.length,0);});

test('research extraction follows an allowed SPA abort and always releases its temporary view',async()=>{const {m}=setup();let temporary;FakeView.onCreate=view=>{temporary=view;view.webContents.loadURL=async()=>{view.webContents.getURL=()=> 'https://tencent.wd1.myworkdayjobs.com/Tencent_Careers/job/example';throw Object.assign(new Error('redirect'),{code:'ERR_ABORTED'});};view.webContents.executeJavaScript=async()=>({title:'Test role',company:'Tencent',description:'Verified page text '.repeat(10)});};try{const result=await m.readResearchJob('company_01',a);assert.equal(result.title,'Test role');assert.match(result.url,/tencent.wd1/);assert.equal(temporary.webContents.isDestroyed(),true);assert.equal(m.state().tabs.length,0);}finally{FakeView.onCreate=undefined;m.destroy();}});

test('foreground permits arbitrary HTTP(S) but background remains source-scoped',async()=>{const {w,m}=setup();await m.show('web',bounds,'http://jobs.example.org/');assert.equal(w.children[0].options.webPreferences.partition,'persist:jobfindsme-web');const view=w.children[0];let prevented=false;view.webContents.emit('will-redirect',{preventDefault(){prevented=true;}},'https://sso.example.net/',false,true);assert.equal(prevented,false);const bg=m.backgroundView('company_03');bg.webContents.emit('will-redirect',{preventDefault(){prevented=true;}},'https://sso.example.net/',false,true);assert.equal(prevented,true);assert.deepEqual(view.options.webPreferences,{partition:'persist:jobfindsme-web',nodeIntegration:false,contextIsolation:true,sandbox:true,webSecurity:true,allowRunningInsecureContent:false});await assert.rejects(m.readResearchJob('company_03','https://sso.example.net/'),/未支持/);m.destroy();});

test('fit width is capped at 100 percent and idempotent from manual zoom levels',async()=>{const {w,m}=setup();await m.show('company_01',bounds,a);for(const start of [1.2,1,.6]){await m.command('zoom-reset');const command=start>1?'zoom-in':'zoom-out';for(let n=0;n<Math.round(Math.abs(start-1)*10);n++)await m.command(command);await m.command('fit-width');const fit=m.state().zoom;assert.equal(fit,.5);await m.command('fit-width');assert.equal(m.state().zoom,fit);}w.children[0].webContents.executeJavaScript=async()=>({width:640,viewport:640});await m.command('fit-width');assert.equal(m.state().zoom,1);m.destroy();});

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
 m.boss.pause('risk_control');await m.observeBoss();assert.equal(m.boss.paused,'risk_control');await m.observeBoss(true);assert.equal(m.boss.paused,undefined);
 const bg=m.backgroundView('boss');assert.equal(bg.options.webPreferences.partition,w.children[0].options.webPreferences.partition);assert.equal(bg.options.webPreferences.partition,'persist:jobfindsme-source-boss');
 }finally{FakeView.onCreate=undefined;m.destroy();}
});

test('career searches merge identical work, cache results and cancel queued work before navigation',async()=>{
 const {m}=setup();let loads=0;
 FakeView.onCreate=v=>{const load=v.webContents.loadURL;v.webContents.loadURL=async url=>{loads++;await load(url);};v.webContents.executeJavaScript=async script=>script.includes('readCareerPage')?{jobs:[{title:'AI工程师',company:'智谱',location:'北京',salary:'',url:'https://app.mokahr.com/social-recruitment/zphz/148983#/job/one'}],next:false,empty:false,loading:false}:false;};
 try{
 const input={keyword:'AI',city:'北京',maxPages:1,seconds:5};
 const one=m.collectCareer('company_14',input),same=m.collectCareer('company_14',input);assert.equal(one,same);assert.equal((await one).records.length,1);
 assert.equal((await m.collectCareer('company_14',input)).records.length,1);assert.equal(loads,1);
 const queued=m.collectCareer('company_14',{...input,keyword:'other'});m.cancelCareerSearch();await assert.rejects(queued,/cancelled/);assert.equal(loads,1);
 }finally{FakeView.onCreate=undefined;m.destroy();}
});

test('career risk control pauses a source and never turns the failure into an empty result',async()=>{
 const {m}=setup();let loads=0;
 FakeView.onCreate=v=>{const load=v.webContents.loadURL;v.webContents.loadURL=async url=>{loads++;await load(url);};v.webContents.executeJavaScript=async script=>script.includes('readCareerPage')?{jobs:[],next:false,empty:false,loading:false,blocked:'访问过于频繁'}:false;};
 try{const input={keyword:'AI',city:'',maxPages:1,seconds:5};await assert.rejects(m.collectCareer('company_14',input),/risk_control/);await assert.rejects(m.collectCareer('company_14',input),/source_backoff/);assert.equal(loads,1);}finally{FakeView.onCreate=undefined;m.destroy();}
});

test('career SPA navigation accepts an allowed abort and still reads the current page',async()=>{
 const {m}=setup();
 FakeView.onCreate=v=>{
  v.webContents.loadURL=async()=>{v.webContents.getURL=()=> 'https://app.mokahr.com/social-recruitment/step/94904#/jobs';throw Object.assign(Error('SPA navigation'),{code:'ERR_ABORTED'});};
  v.webContents.executeJavaScript=async script=>script.includes('readCareerPage')?{jobs:[{title:'模型工程师',company:'阶跃星辰',location:'北京',salary:'',url:'https://app.mokahr.com/social-recruitment/step/94904#/job/observed'}],next:false,empty:false,loading:false}:false;
 };
 try{const result=await m.collectCareer('company_16',{keyword:'工程师',city:'',maxPages:1,seconds:5});assert.equal(result.records.length,1);assert.match(result.records[0].payload.url,/observed/);}
 finally{FakeView.onCreate=undefined;m.destroy();}
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

test('Zhilian foreground user agent removes non-header characters for its login widget',async()=>{
 const {m}=setup();let used;
 FakeView.onCreate=view=>{view.webContents.getUserAgent=()=> 'Mozilla/5.0 JobFindsMe测试版/0.1 Chrome/152 Electron/44 Safari/537.36';view.webContents.setUserAgent=value=>{used=value;};};
 try{await m.show('zhilian',bounds,'https://www.zhaopin.com/');assert.equal(used,'Mozilla/5.0 JobFindsMe/0.1 Chrome/152 Electron/44 Safari/537.36');}finally{FakeView.onCreate=undefined;m.destroy();}
});
