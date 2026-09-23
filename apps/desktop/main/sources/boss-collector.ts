import {randomUUID} from 'node:crypto';
import {bossSearchUrl,canonicalBossJob,type BossJob,type BossPage} from './boss-page';
import type {BrowserSourcePage,SourceCollectionProgress} from '../../shared/contracts';
export type BossDetail={title:string;company:string;location?:string;salary?:string;description:string;url:string;fetched_at:string};
export type BossDriver={load(url:string,detail:boolean,signal:AbortSignal):Promise<void>;read(detail:boolean):Promise<BossPage>;scroll():Promise<void>};
type Input={keyword:string;city:string;maxBatches:number;seconds:number;cursor?:string};
type Context={key:string;url:string;token:string;jobs:Map<string,BossJob>;details:Map<string,BossDetail>;at:number};
export class BossCollector {
  private tail:Promise<unknown>=Promise.resolve();
  private pending=new Map<string,{promise:Promise<BrowserSourcePage>;listeners:Set<(p:SourceCollectionProgress)=>void>}>();
  private cache=new Map<string,{at:number;page:BrowserSourcePage}>();
  private details=new Map<string,BossDetail>();
  private context?:Context;
  private controller?:AbortController;
  private generation=0;
  private lastAction=0;
  private backoffUntil=0;
  private failures=0;
  paused?:'risk_control'|'login_required';
  pausedAt=0;
  pause(reason:'risk_control'|'login_required'){this.paused=reason;this.pausedAt=this.now();this.cache.clear();}
  constructor(private driver:BossDriver,private interval=2500,private now=()=>Date.now()){}
  get busy(){return this.pending.size>0||!!this.controller;}
  cancel(){this.generation++;this.controller?.abort();}
  resume(){this.paused=undefined;this.pausedAt=0;this.cache.clear();}
  private serial<T>(run:()=>Promise<T>):Promise<T>{const p=this.tail.then(run,run);this.tail=p.catch(()=>{});return p;}
  private guard(page:BossPage){if(page.blocked){this.pause('risk_control');throw Error('risk_control:平台要求验证，已暂停 BOSS');}if(page.loginRequired){this.pause('login_required');throw Error('login_required:登录已过期，已暂停 BOSS');}}
  private async pace(signal:AbortSignal,deadline:number){
    const ms=Math.max(0,this.lastAction+this.interval-this.now());
    if(this.now()+ms>=deadline)throw Error('time_budget');
    if(signal.aborted)throw Error('cancelled');
    await new Promise<void>((resolve,reject)=>{const abort=()=>{clearTimeout(timer);signal.removeEventListener('abort',abort);reject(Error('cancelled'));};const timer=setTimeout(()=>{signal.removeEventListener('abort',abort);resolve();},ms);signal.addEventListener('abort',abort,{once:true});});
    if(signal.aborted)throw Error('cancelled');this.lastAction=this.now();
  }
  private async bounded<T>(action:()=>Promise<T>,signal:AbortSignal,deadline:number):Promise<T>{
    if(signal.aborted)throw Error('cancelled');if(this.now()>=deadline)throw Error('time_budget');
    return new Promise<T>((resolve,reject)=>{const finish=(error?:unknown,value?:T)=>{clearTimeout(timer);signal.removeEventListener('abort',abort);error?reject(error):resolve(value!);};const abort=()=>finish(Error('cancelled'));const timer=setTimeout(()=>{finish(Error('time_budget'));this.controller?.abort();},Math.min(12000,deadline-this.now()));signal.addEventListener('abort',abort,{once:true});action().then(v=>finish(undefined,v),finish);});
  }
  collect(input:Input,listener:(p:SourceCollectionProgress)=>void=()=>{}):Promise<BrowserSourcePage>{
    const url=bossSearchUrl(input.keyword,input.city),key=JSON.stringify([url,Math.min(3,input.maxBatches),input.cursor||'']);
    if(this.paused)return Promise.reject(Error(`${this.paused}:BOSS 已暂停，请在原页处理后点击恢复`));
    if(this.now()<this.backoffUntil)return Promise.reject(Error("source_backoff:来源暂时不可用，请稍后重试"));
    const running=this.pending.get(key);if(running){running.listeners.add(listener);listener({stage:'queued',count:0,message:'复用同一检索，等待已有采集'});return running.promise;}
    const cached=this.cache.get(key);if(!input.cursor&&cached&&this.now()-cached.at<120000){listener({stage:'cached',count:cached.page.records.length,message:'使用两分钟内的检索缓存'});const page=structuredClone(cached.page);if(page.collection&&this.context?.token!==page.collection.cursor)page.collection.cursor=null;return Promise.resolve(page);}
    const generation=this.generation,listeners=new Set([listener]);listener({stage:'queued',count:0,message:'等待 BOSS 采集队列'});
    const promise=this.serial(async()=>{
      if(generation!==this.generation)return this.result([],0,0,'cancelled',null);
      if(this.paused)throw Error(`${this.paused}:BOSS 已暂停`);
      const started=this.now(),deadline=started+Math.max(1,Math.min(60,input.seconds))*1000,controller=new AbortController();this.controller=controller;
      const emit=(stage:SourceCollectionProgress['stage'],message:string)=>{for(const cb of listeners)cb({stage,count:this.context?.jobs.size||0,message,titles:[...(this.context?.jobs.values()||[])].slice(0,5).map(j=>j.title)});};
      let context:Context|undefined,batches=0,stop='batch_budget',detailsRead=0;
      try{
        if(input.cursor){if(!this.context||this.context.token!==input.cursor||this.context.key!==url||this.now()-this.context.at>600000)throw Error('continuation_expired:上一批页面已变化，请重新检索');context=this.context;}
        else{context={key:url,url,token:randomUUID(),jobs:new Map(),details:new Map(),at:this.now()};this.context=context;emit('loading','正在读取 BOSS 岗位列表');await this.pace(controller.signal,deadline);await this.bounded(()=>this.driver.load(url,false,controller.signal),controller.signal,deadline);}
        let noGrowth=0;
        for(let batch=0;batch<Math.max(1,Math.min(3,input.maxBatches));batch++){
          if(batch>0||input.cursor){await this.pace(controller.signal,deadline);await this.bounded(()=>this.driver.scroll(),controller.signal,deadline);await this.pace(controller.signal,deadline);}
          let page=await this.bounded(()=>this.driver.read(false),controller.signal,deadline);this.guard(page);
          // Initial SPA render: bounded local DOM reads only, no reload or login request.
          for(let poll=0;!page.readable&&poll<3;poll++){await this.pace(controller.signal,deadline);page=await this.bounded(()=>this.driver.read(false),controller.signal,deadline);this.guard(page);}
          if(!page.authenticated)throw Error('login_required:没有读到已登录页面，请从岗位来源打开 BOSS');
          if(!page.readable)throw Error('source_contract_error:未读取到列表或明确空结果');
          batches++;const before=context.jobs.size;
          for(const job of page.jobs){const url=canonicalBossJob(job.url);if(url&&context.jobs.size<100)context.jobs.set(url,{...job,url,salary:/[\uE000-\uF8FF]/.test(job.salary)?'':job.salary});}
          noGrowth=context.jobs.size===before?noGrowth+1:0;emit('listing',`已读取 ${context.jobs.size} 个去重岗位（${batches} 批）`);
          if(page.empty||page.ended){stop='complete';break;}if(noGrowth>=2){stop='no_growth';break;}if(context.jobs.size>=100){stop='record_budget';break;}
        }
        // Enrich at most two keyword-relevant candidates, after the complete bounded list phase.
        const words=input.keyword.toLowerCase().split(/\s+/).filter(Boolean),score=(j:BossJob)=>words.filter(w=>j.title.toLowerCase().includes(w)).length;
        const candidates=[...context.jobs.values()].filter(j=>score(j)>0&&!context!.details.has(j.url)).sort((a,b)=>score(b)-score(a)).slice(0,2);
        for(const job of candidates){if(deadline-this.now()<6000)break;emit('details',`列表已就绪，补全候选 JD（${detailsRead+1}/${candidates.length}）`);try{context.details.set(job.url,await this.detail(job.url,controller.signal,deadline));detailsRead++;}catch(e){const message=String(e);if(this.paused||controller.signal.aborted||message.includes('time_budget'))throw e;/* list remains valid when one detail lacks a full JD */}}
      }catch(error){const message=error instanceof Error?error.message:String(error);stop=message.split(':')[0];if(stop==='login_required'){this.pause('login_required');}if(controller.signal.aborted&&stop!=='time_budget')stop='cancelled';if(stop==='continuation_expired')throw error;}
      finally{if(this.controller===controller)this.controller=undefined;}
      if(stop==="source_contract_error"){this.failures++;this.backoffUntil=this.now()+Math.min(300000,30000*2**(this.failures-1));}else if(stop==="complete"||stop==="batch_budget"){this.failures=0;}
      const records=context?[...context.jobs.values()].map(job=>{const detail=context!.details.get(job.url);return {external_id:new URL(job.url).pathname,source_name:'BOSS直聘',source_url:url,payload:{...job,title:detail?.title||job.title,company:detail?.company||job.company,location:detail?.location||job.location,salary:detail?.salary||job.salary,apply_url:job.url,description:detail?.description||'',detail_level:detail?'detail_page':'list_card',description_source_url:detail?.url,description_fetched_at:detail?.fetched_at,description_is_plaintext:!!detail,fetched_at:detail?.fetched_at||new Date(this.now()).toISOString()}};}):[];
      const cursor=context&&!this.paused&&['batch_budget','time_budget','cancelled','no_growth'].includes(stop)&&records.length?context.token:null;
      const page=this.result(records,batches,(this.now()-started)/1000,stop,cursor);emit('done',`${records.length} 个岗位；${({complete:'本次范围已读完',batch_budget:'达到批次上限，可继续下一批',record_budget:'达到数量上限',time_budget:'达到时间上限',cancelled:'已停止',no_growth:'暂未发现新增',risk_control:'平台要求验证，已暂停',login_required:'需要重新登录'} as Record<string,string>)[stop]||'来源暂时无法读取'}`);
      if(!this.paused&&['complete','batch_budget','no_growth','record_budget'].includes(stop)){this.cache.set(key,{at:this.now(),page});if(this.cache.size>10)this.cache.delete(this.cache.keys().next().value!);}
      return page;
    }).finally(()=>this.pending.delete(key));this.pending.set(key,{promise,listeners});return promise;
  }
  private result(records:BrowserSourcePage['records'],batches:number,elapsed:number,stop:string,cursor:string|null):BrowserSourcePage{return {records,next_cursor:null,collection:{batches,elapsed_seconds:elapsed,stop_reason:stop,cursor,complete:stop==='complete',failure:stop==='risk_control'||stop==='login_required'?stop:null}};}
  readDetail(url:string):Promise<BossDetail>{const generation=this.generation;return this.serial(async()=>{if(generation!==this.generation)throw Error("cancelled");if(this.paused)throw Error(`${this.paused}:BOSS 已暂停`);const c=new AbortController();this.controller=c;try{return await this.detail(url,c.signal,this.now()+20000);}finally{if(this.controller===c)this.controller=undefined;}});}
  private async detail(value:string,signal:AbortSignal,deadline:number):Promise<BossDetail>{
    const url=canonicalBossJob(value);if(!url)throw Error('不支持的 BOSS 岗位链接');const cached=this.details.get(url);if(cached&&this.now()-Date.parse(cached.fetched_at)<1800000)return cached;
    await this.pace(signal,deadline);await this.bounded(()=>this.driver.load(url,true,signal),signal,deadline);
    for(let poll=0;poll<3;poll++){const page=await this.bounded(()=>this.driver.read(true),signal,deadline);this.guard(page);if(page.detail?.url===url&&page.detail.description.length>=80){const detail={...page.detail,fetched_at:new Date(this.now()).toISOString()};this.details.set(url,detail);if(this.details.size>100)this.details.delete(this.details.keys().next().value!);return detail;}await this.pace(signal,deadline);}
    throw Error('未读到完整 JD，保留列表信息；可打开原页查看');
  }
}
