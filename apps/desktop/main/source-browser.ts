import {publicAtsDetailEndpoint,parsePublicAtsDetail} from './public-detail';
import {canonicalJobUrl} from '../shared/research-reports';
import {careerPageScript,careerAdvanceScript,careerKeywordScript,careerRecords,careerEntryClickScript,careerClickableScript,type CareerPage} from './company-page';
import {BossCollector} from "./boss-collector";
import {bossPageScript,bossScrollScript,type BossPage} from "./boss-page";
import { researchExtractionScript } from "./research-extraction";
import { BrowserWindow, WebContentsView, dialog } from "electron";

import {
  clampSourceBrowserBounds,
  confirmAllowedNavigationAfterAbort,
  isAllowedSourceUrl,
  isPublicWebUrl,
  type ForegroundBrowserId,
  sourceBrowserSpecs,
  type SourceBrowserBounds,
  type SourceBrowserId,
} from "./source-browser-policy";
import {
  buildSourceSearchUrl,
  sanitizeSourceActionPage,
  sourceListExtractionScript,
  type ExtractedSourceJob,
  type SourceActionPage,
} from "./source-actions";

type BrowserTab = { id:string; sourceId:ForegroundBrowserId; view:WebContentsView; initialUrl:string; zoom:number; fitting?:boolean; error?:string; notice?:string };
export const MAX_BROWSER_TABS = 12;

export class SourceBrowserManager {
  private readonly backgrounds = new Map<SourceBrowserId, WebContentsView>();
  private readonly tabs:BrowserTab[] = [];
  private activeId?:string;
  private nextId=1;
  private attached?: WebContentsView;
  private requestedBounds?: SourceBrowserBounds;
  private visible=false;
  private notice="";
  private readonly configuredSessions=new WeakSet<Electron.Session>();
  private readonly downloadHandlers=new Map<Electron.Session,(event:Electron.Event,item:Electron.DownloadItem,contents:Electron.WebContents)=>void>();

  readonly boss = new BossCollector({
    load: (url,detail,signal) => this.loadBoss(url,detail,signal),
    read: detail => this.bossView(detail).webContents.executeJavaScript(bossPageScript()),
    scroll: async () => { await this.bossView(false).webContents.executeJavaScript(bossScrollScript()); },
  });
  private bossDetailView?:WebContentsView;
  private bossObservation?:ReturnType<typeof setInterval>;
  private observingBoss=false;
  private bossDocumentTime=0;
  private bossSawLogin=false;
  constructor(private readonly window: BrowserWindow, private readonly onBossPage?:(page:BossPage,explicit?:boolean)=>Promise<void>) {
    window.on("resize", () => this.applyBounds());
    // Local reads only while the user is looking at this platform; no periodic requests.
    if(onBossPage)this.bossObservation=setInterval(()=>{void this.observeBoss();},2500);
  }

  async observeBoss(explicit=false):Promise<BossPage|undefined> {
    const tab=this.tabs.find(t=>t.id===this.activeId);
    if(this.observingBoss || this.boss.busy || !this.visible || !tab || tab.sourceId!=="boss" || tab.view.webContents.isDestroyed() || tab.view.webContents.isLoading() || !isAllowedSourceUrl("boss",tab.view.webContents.getURL()))return;
    this.observingBoss=true;
    try {const page=await tab.view.webContents.executeJavaScript(bossPageScript()) as BossPage;
      if(page.loginRequired)this.bossSawLogin=true;
      if(!explicit && this.boss.paused==="login_required" && page.authenticated && !this.bossSawLogin && this.bossDocumentTime<=this.boss.pausedAt)return page;
      if(explicit && page.authenticated && page.readable && !page.blocked && !page.loginRequired)this.boss.resume();
      await this.onBossPage?.(page,explicit);if(!this.boss.paused&&page.authenticated)this.bossSawLogin=false;return page;
    } catch {return;} finally {this.observingBoss=false;}
  }
  private bossView(detail:boolean):WebContentsView {
    if(!detail)return this.backgroundView("boss");
    if(!this.bossDetailView || this.bossDetailView.webContents.isDestroyed())this.bossDetailView=this.createView("boss");
    return this.bossDetailView;
  }
  private async loadBoss(url:string,detail:boolean,signal:AbortSignal) {
    if(!isAllowedSourceUrl("boss",url))throw Error("source_contract_error:不支持的来源跳转");
    const wc=this.bossView(detail).webContents;
    const stop=()=>{if(!wc.isDestroyed())wc.stop();};signal.addEventListener("abort",stop,{once:true});
    try {if(signal.aborted)throw Error("cancelled");
      try{await wc.loadURL(url);}catch(error){if(signal.aborted)throw Error("cancelled");if(!await confirmAllowedNavigationAfterAbort("boss",url,error,()=>({url:wc.getURL(),loading:wc.isLoadingMainFrame()})))throw Error("source_contract_error:页面加载失败");}
      if(!isAllowedSourceUrl("boss",wc.getURL()))throw Error("source_contract_error:来源跳转受限");
    }finally{signal.removeEventListener("abort",stop);}
  }
  async show(sourceId: ForegroundBrowserId, bounds: SourceBrowserBounds, requestedUrl?: string): Promise<void> {
    const target=requestedUrl ?? (sourceId === "web" ? "" : sourceBrowserSpecs[sourceId].loginUrl);
    if(!isPublicWebUrl(target))throw new Error("仅支持普通 HTTP/HTTPS 网页；本地或内部地址不可在此打开。");
    this.requestedBounds=bounds;
    const existing=this.tabs.find(tab=>tab.sourceId===sourceId && (tab.view.webContents.getURL()===target || (tab.view.webContents.isLoading() && tab.initialUrl===target)));
    if(existing){this.selectTab(existing.id);return;}
    if(this.tabs.length>=MAX_BROWSER_TABS)throw new Error(`最多打开${MAX_BROWSER_TABS}个标签，请先关闭不需要的页面。`);
    const tab=this.createForegroundTab(sourceId,target);
    await this.loadTab(tab,target);
  }

  private createForegroundTab(sourceId:ForegroundBrowserId,target:string,popupOptions?:Electron.BrowserWindowConstructorOptions):BrowserTab {
    const id=`tab-${this.nextId++}`;
    const view=this.createView(sourceId,true,popupOptions);
    const tab:BrowserTab={id,sourceId,view,initialUrl:target,zoom:1};
    this.tabs.push(tab);
    view.webContents.on("did-start-navigation",(_event,_url,_inPlace,isMain)=>{if(isMain)tab.error=undefined;});
    view.webContents.on("did-fail-load",(_event,code,description,_url,isMain)=>{if(isMain && code!==-3)tab.error=`页面加载失败：${description}`;});
    view.webContents.on("render-process-gone",()=>{tab.error="页面进程已退出，请刷新或关闭标签。";});
    this.selectTab(id);
    return tab;
  }

  async navigateTab(id:string,url:string) {
    if(!isPublicWebUrl(url))throw new Error("仅支持普通 HTTP/HTTPS 网页；本地或内部地址不可在此打开。");
    const tab=this.tabs.find(t=>t.id===id);
    if(!tab)throw new Error("标签已关闭");
    tab.error=undefined;tab.notice=undefined;tab.initialUrl=url;
    // Navigation stays in this tab's existing browsing context and history.
    await this.loadTab(tab,url);
    return this.state();
  }

  private async loadTab(tab:BrowserTab,target:string) {
    const view=tab.view;
    try {await view.webContents.loadURL(target);if(!view.webContents.isDestroyed() && !isPublicWebUrl(view.webContents.getURL()))tab.error="页面未返回有效招聘内容，请刷新或尝试岗位详情链接。";}
    catch(error){
      if(view.webContents.isDestroyed())return;
      const aborted=error && typeof error === "object" && "code" in error && error.code === "ERR_ABORTED";
      let completed=false;
      if(aborted)for(let i=0;i<80;i++){if(view.webContents.isDestroyed())return;if(!view.webContents.isLoadingMainFrame()&&isPublicWebUrl(view.webContents.getURL())){completed=true;break;}await new Promise(r=>setTimeout(r,100));}
      if(!completed){tab.error=String(error);throw error;}
    }
  }

  selectTab(id:string) {
    const tab=this.tabs.find(t=>t.id===id);
    if(!tab)throw new Error("标签已关闭");
    if(this.attached!==tab.view){
      if(this.attached){this.attached.setVisible(false);this.window.contentView.removeChildView(this.attached);}
      this.attached=tab.view;this.window.contentView.addChildView(tab.view);
    }
    this.activeId=id;tab.view.webContents.setZoomFactor(tab.zoom);this.notice="";this.applyBounds();this.attached.setVisible(this.visible);
    return this.state();
  }

  closeTab(id:string) {
    const index=this.tabs.findIndex(t=>t.id===id);if(index<0)return this.state();
    const tab=this.tabs[index];this.tabs.splice(index,1);
    if(this.attached===tab.view){tab.view.setVisible(false);this.window.contentView.removeChildView(tab.view);this.attached=undefined;this.activeId=undefined;}
    if(!tab.view.webContents.isDestroyed())tab.view.webContents.close();
    if(!this.activeId && this.tabs.length)this.selectTab(this.tabs[Math.min(index,this.tabs.length-1)].id);
    return this.state();
  }

  state() {
    const wc=this.attached?.webContents;
    const active=this.tabs.find(t=>t.id===this.activeId);
    return {url:wc?.getURL() || active?.initialUrl || "",canGoBack:wc?.navigationHistory.canGoBack()??false,canGoForward:wc?.navigationHistory.canGoForward()??false,loading:wc?.isLoading()??false,
      zoom:active?.zoom??1,fitting:!!active?.fitting,activeTabId:this.activeId??null,notice:active?.notice||this.notice,tabs:this.tabs.map(t=>({id:t.id,sourceId:t.sourceId,url:t.view.webContents.getURL()||t.initialUrl,title:t.view.webContents.getTitle()||new URL(t.initialUrl).hostname,loading:t.view.webContents.isLoading(),error:t.error}))};
  }

  layout(bounds: SourceBrowserBounds | null): void {
    if(this.window.isDestroyed())return;
    this.visible=Boolean(bounds);
    if(bounds)this.requestedBounds=bounds;
    this.attached?.setVisible(this.visible);this.applyBounds();
  }

  async command(command: string) {
    const wc=this.attached?.webContents;if(command!=="state")this.notice="";
    const tab=this.tabs.find(t=>t.id===this.activeId);
    if(tab?.fitting && command!=="state")return this.state();
    if(tab && command!=="state")tab.notice=undefined;
    if(wc&&!wc.isDestroyed()){
      if(command==="back"&&wc.navigationHistory.canGoBack())wc.navigationHistory.goBack();
      if(command==="forward"&&wc.navigationHistory.canGoForward())wc.navigationHistory.goForward();
      if(command==="reload")wc.reload();
      if(tab && ["zoom-in","zoom-out","zoom-reset","fit-width"].includes(command)) {
        let zoom=command==="zoom-reset"?1:tab.zoom+(command==="zoom-in"?.1:command==="zoom-out"?-.1:0);
        if(command==="fit-width") {
          const previous=tab.zoom;tab.fitting=true;
          try {
            // Measure CSS pixels only, starting from a reproducible 100% layout.
            for(let i=0;wc.isLoadingMainFrame()&&i<50;i++)await new Promise(r=>setTimeout(r,100));
            if(wc.isDestroyed()||wc.isLoadingMainFrame())throw new Error("页面尚未加载完成，请稍后再适应宽度。");
            const url=wc.getURL();wc.setZoomFactor(1);zoom=1;
            for(let attempt=0;attempt<3;attempt++){
              await new Promise(r=>setTimeout(r,120));
              if(wc.isDestroyed()||wc.getURL()!==url)throw new Error("页面正在跳转，请加载后再适应宽度。");
              const dimensions=await wc.executeJavaScript(`(()=>{
                const viewport=document.documentElement.clientWidth||window.innerWidth;
                let width=Math.max(document.documentElement.scrollWidth,document.body?.scrollWidth||0);
                // Some sites hide root overflow while retaining a fixed-width child.
                for(const el of Array.from(document.body?.querySelectorAll("*")||[]).slice(0,5000)){
                  const r=el.getBoundingClientRect();
                  if(r.width<=0||r.height<=0||r.right<=0||r.left>=viewport)continue;
                  const style=getComputedStyle(el);
                  if(style.display==="none"||style.visibility==="hidden"||Number(style.opacity)===0)continue;
                  width=Math.max(width,r.right-Math.min(0,r.left));
                }
                return {width,viewport};
              })()`);
              if(!Number.isFinite(dimensions?.width)||!Number.isFinite(dimensions?.viewport)||dimensions.width<=0||dimensions.viewport<=0)throw new Error("无法测量页面宽度，请使用手动缩放。");
              if(dimensions.width<=dimensions.viewport+2)break;
              const next=Math.max(.3,Math.floor(zoom*dimensions.viewport/dimensions.width*100)/100);
              if(next>=zoom)break;
              zoom=next;wc.setZoomFactor(zoom);
            }
            if(zoom===.3)tab.notice="已缩至30%；超宽内容仍可横向滚动查看。";
          } catch(error){if(!wc.isDestroyed())wc.setZoomFactor(previous);throw error;}finally{tab.fitting=false;}
        }
        if(!wc.isDestroyed()){tab.zoom=Math.max(.3,Math.min(2,Math.round(zoom*100)/100));wc.setZoomFactor(tab.zoom);}
      }
    }
    return this.state();
  }

  hide():void {this.layout(null);}

  backgroundView(sourceId:SourceBrowserId):WebContentsView {
    let view=this.backgrounds.get(sourceId);
    if(!view||view.webContents.isDestroyed()){view=this.createView(sourceId);this.backgrounds.set(sourceId,view);}
    return view;
  }

  async readJobDescription(sourceId: SourceBrowserId, url: string): Promise<string> {
    return (await this.readResearchJob(sourceId,url)).description;
  }

  async readResearchJob(sourceId: SourceBrowserId, url: string): Promise<{title:string;company:string;description:string;url:string}> {
    if (!isAllowedSourceUrl(sourceId,url)) throw new Error("不安全或未支持的岗位链接");
    if(sourceId==="boss"){const detail=await this.boss.readDetail(url);return {...detail,company:detail.company||"公司未知"};}
    if(['company_09','company_13'].includes(sourceId)){
      const endpoint=publicAtsDetailEndpoint(url);
      if(endpoint)try {
        const response=await fetch(endpoint,{signal:AbortSignal.timeout(8000),redirect:'error'});
        if(response.status===429||response.status===403)throw Error('risk_control:官网要求原页确认');
        if(!response.ok)throw Error('public_detail_failed:'+response.status);
        const reader=response.body?.getReader();if(!reader)throw Error('source_contract_error:响应为空');
        const chunks:Uint8Array[]=[];let size=0;
        try{while(true){const part=await reader.read();if(part.done)break;size+=part.value.byteLength;if(size>200000)throw Error('source_contract_error:响应过大');chunks.push(part.value);}}
        finally{await reader.cancel();}
        const text=Buffer.concat(chunks).toString('utf8');
        return parsePublicAtsDetail(JSON.parse(text),url);
      }catch(error){if(String(error).includes('risk_control:'))throw error;}
    }
    const view=this.createView(sourceId);
    const detailDeadline=Date.now()+21000;
    let timeout:ReturnType<typeof setTimeout> | undefined;
    const companyNames=["腾讯","字节跳动","阿里巴巴","美团","百度","京东","网易","快手","小米","滴滴","拼多多","DeepSeek","MiniMax","智谱","月之暗面","阶跃星辰"];
    const hint=sourceId.startsWith("company_") ? companyNames[Number(sourceId.slice(8))-1] : "";
    try {
      const load=view.webContents.loadURL(url).catch(async error=>{
        if(!await confirmAllowedNavigationAfterAbort(sourceId,url,error,()=>({url:view.webContents.getURL(),loading:view.webContents.isLoadingMainFrame()})))throw error;
      });
      await Promise.race([load,new Promise((_,reject)=>{timeout=setTimeout(()=>reject(new Error("页面读取超时")),15000);})]);
      if (!isAllowedSourceUrl(sourceId,view.webContents.getURL())) throw new Error("页面跳转受限");
      for(let attempt=0;attempt<100&&Date.now()<detailDeadline;attempt++) {
        let evalTimer:ReturnType<typeof setTimeout>|undefined;
        const result=await Promise.race([view.webContents.executeJavaScript(researchExtractionScript(hint)),new Promise<any>((_,reject)=>{evalTimer=setTimeout(()=>reject(Error('页面读取超时')),Math.max(1,Math.min(3000,detailDeadline-Date.now())));})]).finally(()=>{if(evalTimer)clearTimeout(evalTimer);});
        if(result && typeof result.title === "string" && typeof result.company === "string" && typeof result.description === "string") {
          return {title:result.title.slice(0,300),company:result.company.slice(0,300),description:result.description.slice(0,30000),url:view.webContents.getURL()};
        }
        await new Promise(resolve=>setTimeout(resolve,150));
      }
      throw new Error("没有读取到完整岗位信息，请打开原页确认这是岗位详情，并在需要时登录后重试。");
    } finally {if(timeout)clearTimeout(timeout);if(!view.webContents.isDestroyed())view.webContents.close();}
  }

  private careerCache=new Map<string,{time:number;page:SourceActionPage}>();
  private careerBlocked=new Map<SourceBrowserId,number>();
  private careerEpoch=0;
  cancelCareerSearch(){this.careerEpoch++;}
  private careerPending=new Map<string,Promise<SourceActionPage>>();
  private careerTail:Promise<unknown>=Promise.resolve();
  collectCareer(sourceId:SourceBrowserId,input:{keyword:string;city:string;maxPages:number;seconds:number}):Promise<SourceActionPage>{
    const key=JSON.stringify([sourceId,input]),existing=this.careerPending.get(key);if(existing)return existing;
    const epoch=this.careerEpoch;
    const work=this.careerTail.then(()=>{if(epoch!==this.careerEpoch)throw Error('cancelled:检索已停止');return this.collectCareerRun(sourceId,input);});
    this.careerTail=work.catch(()=>{});this.careerPending.set(key,work);void work.finally(()=>this.careerPending.delete(key)).catch(()=>{});return work;
  }
  private async collectCareerRun(sourceId:SourceBrowserId,input:{keyword:string;city:string;maxPages:number;seconds:number}):Promise<SourceActionPage>{
    const key=JSON.stringify([sourceId,input]),now=Date.now(),cached=this.careerCache.get(key);
    if(cached&&now-cached.time<120000)return structuredClone(cached.page);
    if(now<(this.careerBlocked.get(sourceId)||0))throw Error('source_backoff:来源已暂停，请稍后重试');
    const epoch=this.careerEpoch,deadline=now+Math.min(60000,input.seconds*1000),view=this.backgroundView(sourceId),seen=new Set<string>(),records:SourceActionPage['records']=[];
    const check=()=>{if(epoch!==this.careerEpoch||Date.now()>deadline)throw Error('source_budget:已停止，保留已读取岗位');};
    const bounded=async <T>(task:Promise<T>):Promise<T>=>{let timer:ReturnType<typeof setTimeout>|undefined;try{return await Promise.race([task,new Promise<T>((_,reject)=>{timer=setTimeout(()=>reject(Error('source_timeout:读取超过预算')),Math.max(1,deadline-Date.now()));})]);}finally{if(timer)clearTimeout(timer);}};
    let batches=0,previousPage='';
    const pageIdentity=(page:CareerPage)=>page.jobs.map(j=>canonicalJobUrl(j.url)).sort().join('|');
    try{
      const url=sourceBrowserSpecs[sourceId].loginUrl;
      const ready=new Promise<void>(resolve=>view.webContents.once('dom-ready',()=>resolve()));
      await bounded(Promise.race([view.webContents.loadURL(url),ready]));
      check();if(!isAllowedSourceUrl(sourceId,view.webContents.getURL()))throw Error('source_contract_error:官网跳转超出已核验入口');
      let raw:CareerPage=await bounded(view.webContents.executeJavaScript(careerPageScript()));
      for(let wait=0;wait<12&&!raw.jobs.length&&!raw.entry&&!raw.blocked;wait++){check();await new Promise(r=>setTimeout(r,250));raw=await bounded(view.webContents.executeJavaScript(careerPageScript()));}
      for(let hop=0;hop<2&&!raw.jobs.length&&raw.entry&&!raw.blocked;hop++){
        if(!isAllowedSourceUrl(sourceId,raw.entry)||raw.entry===view.webContents.getURL())break;
        check();await bounded(view.webContents.loadURL(raw.entry));raw=await bounded(view.webContents.executeJavaScript(careerPageScript()));
      }
      if(!raw.jobs.length&&['company_01','company_03'].includes(sourceId)){
        await bounded(view.webContents.executeJavaScript(careerEntryClickScript(sourceId)));
        await new Promise(r=>setTimeout(r,700));
        if(sourceId==='company_03'){
          let entryPopup='';view.webContents.setWindowOpenHandler(({url})=>{if(isAllowedSourceUrl(sourceId,url))entryPopup=url;return {action:'deny'};});
          try{await bounded(view.webContents.executeJavaScript(careerEntryClickScript(sourceId)));await new Promise(r=>setTimeout(r,700));if(entryPopup)await bounded(view.webContents.loadURL(entryPopup));}
          finally{view.webContents.setWindowOpenHandler(()=>({action:'deny'}));}
        }
      }
      let searchPopup='',keywordApplied=false;
      view.webContents.setWindowOpenHandler(({url})=>{if(isAllowedSourceUrl(sourceId,url))searchPopup=url;return {action:'deny'};});
      try {
        check();keywordApplied=Boolean(await bounded(view.webContents.executeJavaScript(careerKeywordScript(input.keyword))));
        await new Promise(r=>setTimeout(r,800));
        if(searchPopup)await bounded(view.webContents.loadURL(searchPopup));
      } finally {view.webContents.setWindowOpenHandler(()=>({action:'deny'}));}
      for(let page=0;page<Math.min(input.maxPages,3);page++){
        for(let wait=0;wait<24;wait++){check();raw=await bounded(view.webContents.executeJavaScript(careerPageScript()));if(raw.blocked||(!raw.loading&&((raw.empty&&wait>=12)||(raw.jobs.length&&pageIdentity(raw)!==previousPage))))break;await new Promise(r=>setTimeout(r,250));}
        if(raw.loading)throw Error('source_loading:岗位列表未完成加载');
        if(raw.blocked){this.careerBlocked.set(sourceId,Date.now()+300000);throw Error('risk_control:'+raw.blocked);}
        if(!raw.jobs.length&&!keywordApplied&&!careerClickableScript(sourceId).includes('querySelectorAll'))throw Error('source_contract_error:官网尚未暴露可验证的岗位检索控件');
        if(!raw.jobs.length){
          const candidates=await bounded(view.webContents.executeJavaScript(careerClickableScript(sourceId))) as Array<{title:string;location:string}>;
          const listUrl=view.webContents.getURL();let clickedUrl='';
          view.webContents.setWindowOpenHandler(({url})=>{if(isAllowedSourceUrl(sourceId,url))clickedUrl=url;return {action:'deny'};});
          try{for(let i=0;i<Math.min(candidates.length,5);i++){
            if(!candidates[i].title.toLowerCase().includes(input.keyword.toLowerCase()))continue;
            check();clickedUrl='';await bounded(view.webContents.executeJavaScript(careerClickableScript(sourceId,i)));
            for(let wait=0;wait<8&&!clickedUrl&&view.webContents.getURL()===listUrl;wait++)await new Promise(r=>setTimeout(r,100));
            const target=clickedUrl||view.webContents.getURL();
            if(target!==listUrl&&isAllowedSourceUrl(sourceId,target))raw.jobs.push({...candidates[i],company:'',salary:'',url:target});
            if(view.webContents.getURL()!==listUrl)break;
          }}finally{view.webContents.setWindowOpenHandler(()=>({action:'deny'}));}
        }
        if(!raw.jobs.length&&!raw.empty)throw Error('source_contract_error:未读取到可验证岗位链接，请在官网手动浏览');
        const fingerprint=pageIdentity(raw);
        if(fingerprint&&fingerprint===previousPage)break;
        previousPage=fingerprint;batches++;
        const parsed=careerRecords(sourceId,view.webContents.getURL(),raw,input.keyword,input.city);
        for(const record of parsed.records)if(!seen.has(record.external_id)){seen.add(record.external_id);records.push(record);}
        if(!raw.next||records.length>=100||page+1>=Math.min(input.maxPages,3))break;
        check();if(!await bounded(view.webContents.executeJavaScript(careerAdvanceScript())))break;
        await new Promise(r=>setTimeout(r,500));
      }
      const result={records:records.slice(0,100),next_cursor:null,collection:{batches,elapsed_seconds:(Date.now()-now)/1000,stop_reason:'dom_sample',cursor:null,complete:false,failure:null}};
      this.careerCache.set(key,{time:Date.now(),page:result});if(this.careerCache.size>40)this.careerCache.delete(this.careerCache.keys().next().value!);
      return result;
    }catch(error){if(records.length)return {records:records.slice(0,100),next_cursor:null,collection:{batches,elapsed_seconds:(Date.now()-now)/1000,stop_reason:'stopped_partial',cursor:null,complete:false,failure:String(error).includes('risk_control:')?'risk_control':String(error).includes('login_required:')?'login_required':null}};throw error;}
    finally{if(view.webContents.isLoading())view.webContents.stop();}
  }

  async searchPage(
    sourceId: "boss" | "zhilian" | "wuyou",
    input: { keyword: string; city: string; page: number },
  ): Promise<SourceActionPage> {
    if(sourceId==="boss")throw Error("请使用 BOSS 有界采集入口");
    const key=JSON.stringify([sourceId,input]),cached=this.careerCache.get(key),now=Date.now();
    if(cached&&now-cached.time<120000)return structuredClone(cached.page);
    if(now<(this.careerBlocked.get(sourceId)||0))throw Error('source_backoff:来源已暂停，请稍后重试');
    const view=this.backgroundView(sourceId),epoch=this.careerEpoch,deadline=now+18000;
    const bounded=async <T>(work:Promise<T>):Promise<T>=>{let timer:ReturnType<typeof setTimeout>|undefined;try{return await Promise.race([work,new Promise<T>((_,reject)=>{timer=setTimeout(()=>reject(Error('source_timeout:来源读取超时')),Math.max(1,deadline-Date.now()));})]);}finally{if(timer)clearTimeout(timer);}};
    const searchUrl=buildSourceSearchUrl(sourceId,input.keyword,input.city,input.page);
    try {
      await bounded(view.webContents.loadURL(searchUrl));
      let raw:{jobs?:ExtractedSourceJob[];hasNext?:boolean;blocked?:string|null;loginRequired?:boolean;empty?:boolean}|undefined;
      for(let attempt=0;attempt<32;attempt++){
        if(epoch!==this.careerEpoch)throw Error('cancelled:检索已停止');
        if(!isAllowedSourceUrl(sourceId,view.webContents.getURL()))throw Error('source_contract_error:来源页面跳转不受支持');
        raw=await bounded(view.webContents.executeJavaScript(sourceListExtractionScript(sourceId)));
        if(raw?.blocked){this.careerBlocked.set(sourceId,Date.now()+300000);throw Error('risk_control:'+raw.blocked);}
        if(raw?.loginRequired)throw Error('login_required:登录状态已失效');
        if(raw?.jobs?.length||raw?.empty)break;
        await new Promise(r=>setTimeout(r,250));
      }
      if(!raw?.jobs?.length&&!raw?.empty)throw Error('source_contract_error:未读取到岗位列表，请在原页确认');
      const result=sanitizeSourceActionPage(sourceId,searchUrl,input.page,raw!,new Map());
      // Site city parameters use opaque IDs. Apply named cities to observed fields locally.
      if(input.city&&!/^\d+$/.test(input.city))result.records=result.records.filter(r=>!r.payload.location||String(r.payload.location).includes(input.city));
      this.careerCache.set(key,{time:Date.now(),page:result});
      if(this.careerCache.size>40)this.careerCache.delete(this.careerCache.keys().next().value!);
      return result;
    } finally {if(view.webContents.isLoading())view.webContents.stop();}
  }

  destroy(): void {
    this.boss.cancel();if(this.bossObservation)clearInterval(this.bossObservation);
    if(this.bossDetailView&&!this.bossDetailView.webContents.isDestroyed())this.bossDetailView.webContents.close();
    // The BrowserWindow closed event may run after its native contentView died.
    // Release web contents directly; never select a replacement tab during teardown.
    if(this.attached && !this.window.isDestroyed())this.window.contentView.removeChildView(this.attached);
    this.attached=undefined;this.activeId=undefined;this.requestedBounds=undefined;this.visible=false;
    for(const tab of this.tabs)if(!tab.view.webContents.isDestroyed())tab.view.webContents.close();
    this.tabs.length=0;
    for(const view of this.backgrounds.values())if(!view.webContents.isDestroyed())view.webContents.close();
    this.backgrounds.clear();
    for(const [session,handler] of this.downloadHandlers)session.removeListener("will-download",handler);
    this.downloadHandlers.clear();
  }

  private createView(sourceId: ForegroundBrowserId, foreground=false, popupOptions?:Electron.BrowserWindowConstructorOptions): WebContentsView {
    // For window.open, Electron creates the child WebContents before invoking
    // createWindow. Adopting the exact options preserves its native WindowProxy.
    const view = popupOptions
      ? new WebContentsView(popupOptions as Electron.WebContentsViewConstructorOptions)
      : new WebContentsView({webPreferences: {
        ...(!foreground?{backgroundThrottling:false}:{}),
        partition: sourceId === "web" ? "persist:jobfindsme-web" : sourceBrowserSpecs[sourceId].partition,
        nodeIntegration: false,
        contextIsolation: true,
        sandbox: true,
        webSecurity: true,
        allowRunningInsecureContent: false,
      }});
    if(sourceId==="boss"&&foreground){const navigated=()=>{this.bossDocumentTime=Date.now();};view.webContents.on("did-navigate",navigated);view.webContents.on("did-navigate-in-page",navigated);}
    if(!foreground)view.setBounds({x:0,y:0,width:1240,height:900});
    if(foreground)view.webContents.on("focus",()=>{if(!this.window.isDestroyed())this.window.webContents.send("desktop:source-browser-focused");});
    const session=view.webContents.session;
    if(session && !this.configuredSessions.has(session)){
      this.configuredSessions.add(session);
      session.setPermissionCheckHandler(()=>false);
      session.setPermissionRequestHandler((contents,permission,callback,details)=>{
        const tab=this.tabs.find(t=>t.view.webContents===contents);
        const url=details.requestingUrl || contents.getURL();
        if(!tab || !isPublicWebUrl(url) || this.window.isDestroyed() || !["media","geolocation","notifications","fullscreen"].includes(permission)){callback(false);return;}
        void dialog.showMessageBox(this.window,{type:"question",buttons:["不允许","允许此次"],defaultId:0,cancelId:0,message:`${new URL(url).origin} 请求 ${permission}`,detail:"仅在你同意后授予此次网页请求。"}).then(result=>callback(result.response===1),()=>callback(false));
      });
      session.webRequest.onBeforeRequest({urls:["http://*/*","https://*/*"]},(details,callback)=>callback({cancel:!isPublicWebUrl(details.url)}));
      const downloadHandler=(event:Electron.Event,item:Electron.DownloadItem,contents:Electron.WebContents)=>{
        if(!this.tabs.some(t=>t.view.webContents===contents)){event.preventDefault();return;}
        item.setSaveDialogOptions({title:"保存网页下载文件",buttonLabel:"保存"});
      };
      this.downloadHandlers.set(session,downloadHandler);
      session.on("will-download",downloadHandler);
    }
    view.webContents.setWindowOpenHandler(({url}) => {
      if(foreground){
        // Keep the real WindowProxy: some sites open a blank window and assign
        // its location afterward. Denying and opening a replacement loses that URL.
        if((isPublicWebUrl(url)||url==='about:blank') && this.requestedBounds && this.tabs.length<MAX_BROWSER_TABS)
          return {action:'allow',outlivesOpener:true,overrideBrowserWindowOptions:{webPreferences:{partition:sourceId==='web'?'persist:jobfindsme-web':sourceBrowserSpecs[sourceId].partition,nodeIntegration:false,contextIsolation:true,sandbox:true,webSecurity:true,allowRunningInsecureContent:false}},createWindow:options=>this.createForegroundTab(sourceId,url,options).view.webContents};
        this.notice=this.tabs.length>=MAX_BROWSER_TABS?'标签数量已达上限，请先关闭不需要的页面。':'此链接使用不支持的协议或指向本地地址，未打开。';
      }
      return {action:"deny"};
    });
    const guard = (event: {preventDefault():void}, url:string, kind:string, isMain=true) => {
      if(foreground ? isPublicWebUrl(url) : sourceId !== "web" && isAllowedSourceUrl(sourceId,url))return;
      event.preventDefault();
      if(foreground){
        let address="无效地址";try{const parsed=new URL(url);address=parsed.origin+parsed.pathname;}catch{}
        const tab=this.tabs.find(t=>t.view===view);
        if(tab)tab.notice=`已停止${isMain?"页面":"嵌入页面"}${kind}：${address}。此协议或本地地址不支持，可返回上一页。`;
      }
    };
    view.webContents.on("will-navigate", (event,url)=>guard(event,url,"跳转"));
    view.webContents.on("will-redirect", (event,url,_inPlace,isMain)=>guard(event,url,"重定向",isMain));
    return view;
  }

  private applyBounds(): void {
    if (this.window.isDestroyed() || !this.attached || !this.requestedBounds) return;
    const [width, height] = this.window.getContentSize();
    this.attached.setBounds(
      clampSourceBrowserBounds(this.requestedBounds, { width, height }),
    );
  }
}
