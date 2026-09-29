import {normalizeZhilianJobUrl,zhilianCityCode,validateZhilianSearchScope,type ExtractedSourceJob} from './source-actions';

function identity(value:string):string|null{
  const normalized=normalizeZhilianJobUrl(value);if(!normalized)return null;
  const url=new URL(normalized);
  // The site's observed normalizePositionList performs this legacy-host rewrite.
  if(url.hostname==='jobs.zhaopin.com'){url.hostname='www.zhaopin.com';url.pathname='/jobdetail'+url.pathname;}
  return url.origin+url.pathname;
}

export type ZhilianInitialSearch={mode?:unknown;keyword?:unknown;city?:unknown;page?:unknown;count?:unknown;failed?:unknown;loading?:unknown;jobs?:unknown;scopeFields?:string};

// Observes only the search response already requested by this background page.
// Never initiates requests or retains headers, tokens, account data or other APIs.
export class ZhilianSearchEvidence {
  private requests=new Map<string,number>();
  private sequence=0;
  searchRequests=0;matchedRequests=0;initialStatus='absent';responseStatus='pending';
  private result?:{sequence:number;jobs:Map<string,ExtractedSourceJob>;empty:boolean;invalid:number};
  constructor(private input:{keyword:string;city:string;page:number}){}
  request(id:string,url:string,method:string,postData?:string):boolean{
    try{
      const target=new URL(url);
      if(target.origin!=='https://fe-api.zhaopin.com'||method!=='POST')return false;
      if(['/c/i/position/recommend-tag','/c/i/position/recommend-tag-newest','/c/i/job/recommend'].includes(target.pathname)){this.sequence++;this.result=undefined;return false;}
      if(target.pathname!=='/c/i/search/positions')return false;
      // Any newer search invalidates the old response, including another query.
      this.sequence++;this.searchRequests++;this.result=undefined;this.responseStatus="pending";
      const data=JSON.parse(postData||'{}');
      if(data.eventScenario!=='pcSearchedSouSearch'||data.S_SOU_FULL_INDEX!==this.input.keyword.trim()||String(data.S_SOU_WORK_CITY)!==zhilianCityCode(this.input.city)||Number(data.pageIndex)!==this.input.page)return false;
      if(this.requests.size>=10)this.requests.clear();
      this.matchedRequests++;this.requests.set(id,this.sequence);return true;
    }catch{return false;}
  }
  response(id:string,body:string):void{
    const sequence=this.requests.get(id);this.requests.delete(id);
    if(sequence===undefined||sequence!==this.sequence||body.length>2000000)return;
    try{
      const data=JSON.parse(body);
      if(data.code!==200||!Array.isArray(data.data?.list)||typeof data.data.count!=='number'||data.data.count<0||data.data.list.length>100)return;
      const echoed=typeof data.data.kw==='string'?data.data.kw.trim().toLowerCase():undefined;
      if(echoed&&echoed!==this.input.keyword.trim().toLowerCase()){this.responseStatus='echo_mismatch';return;}
      const terms=this.input.keyword.trim().toLowerCase().split(/\s+/).filter(Boolean);
      const supported=(job:unknown):boolean=>{
        if(!job||typeof job!=='object')return false;
        const item=job as Record<string,any>;
        // Inspect only public fields already returned by this normal search.
        // An explicitly blank echo can indicate expansion: each retained job
        // needs its own lexical support, not a matching sibling's support.
        const text=[item.name,item.companyName,item.jobSummary,item.jobDetailData?.position?.desc?.description].filter(value=>typeof value==='string').join(' ').slice(0,16000).replace(/<[^>]*>/g,' ').toLowerCase();
        return terms.some(term=>{
          if(!/^[a-z0-9+#.]+$/i.test(term))return text.includes(term);
          const escaped=term.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
          return new RegExp(`(^|[^a-z0-9])${escaped}(?=$|[^a-z0-9])`,'i').test(text);
        });
      };
      const expanded=echoed===''&&data.data.count>0;
      if(expanded&&!data.data.list.some(supported)){this.responseStatus='empty_keyword_expansion';return;}
      // A zero scoped total must never promote appended suggestions to hits.
      // A positive total smaller than the list cannot establish consistent scope.
      if(data.data.count===0){this.result={sequence,jobs:new Map(),empty:true,invalid:0};return;}
      if(data.data.count<data.data.list.length)return;
      this.responseStatus='verified';
      const jobs=new Map<string,ExtractedSourceJob>();let invalid=0;
      for(const job of data.data.list){
        try{
          if(!job||typeof job!=='object'||(expanded&&!supported(job))){invalid++;continue;}
          const url=identity(job.positionUrl||job.positionURL||'');
          if(url&&typeof job.name==='string'&&typeof job.companyName==='string'&&job.name.trim()&&job.companyName.trim())jobs.set(url,{title:job.name.trim(),company:job.companyName.trim(),url,location:[job.workCity,job.cityDistrict,job.streetName].filter(value=>typeof value==='string'&&value.trim()).join(' ').slice(0,200),salary:typeof job.salary60==='string'?job.salary60.slice(0,100):''});
          else invalid++;
        }catch{invalid++;/* A malformed individual record cannot discard valid siblings. */}
      }
      this.result={sequence,jobs,empty:data.data.list.length===0&&data.data.count===0,invalid};
    }catch{/* Malformed responses cannot establish provenance. */}
  }
  initial(state:ZhilianInitialSearch|undefined,url:string):void{
    if(this.sequence!==0||!state||this.result)return;
    try{validateZhilianSearchScope(url,this.input.keyword,this.input.city,this.input.page);}catch{this.initialStatus='url_mismatch';return;}
    if(state.mode!=='search'||state.keyword!==this.input.keyword.trim()||String(state.city)!==zhilianCityCode(this.input.city)||Number(state.page)!==this.input.page){this.initialStatus=`scope_mismatch(mode=${state.mode==='search'?'search':state.mode==='recommend'?'recommend':'unknown'},keyword=${state.keyword===this.input.keyword.trim()},city=${String(state.city)===zhilianCityCode(this.input.city)},page=${Number(state.page)===this.input.page},fields=${(state.scopeFields||"none").replace(/[^a-zA-Z,]/g,"").slice(0,60)})`;return;}
    if(state.failed===true||state.loading!==false||!Array.isArray(state.jobs)||typeof state.count!=='number'||state.count<state.jobs.length){this.initialStatus=`incomplete(loading=${state.loading===false?'false':state.loading===true?'true':'unknown'},countType=${typeof state.count},list=${Array.isArray(state.jobs)?state.jobs.length:'missing'},failed=${state.failed===true})`;return;}
    this.requests.set('server-bootstrap',0);
    this.response('server-bootstrap',JSON.stringify({code:200,data:{list:state.jobs,count:state.count}}));
    this.initialStatus=this.ready?'verified':'invalid';
  }
  get ready():boolean{return !!this.result;}
  get empty():boolean{return this.result?.empty===true;}
  get invalidRecords():number{return this.result?.invalid||0;}
  records(cards:ExtractedSourceJob[]):ExtractedSourceJob[]{
    return [...(this.result?.jobs.values()||[])].map(job=>{
      const card=cards.find(value=>this.matches(value)&&identity(value.url)===identity(job.url));
      return {...job,location:job.location||card?.location||'',salary:card?.salary||job.salary};
    });
  }
  matches(job:{url:string;title:string;company:string}):boolean{
    const url=identity(job.url);const expected=url&&this.result?.jobs.get(url);
    return !!expected&&job.title.trim()===expected.title&&job.company.trim()===expected.company;
  }
}
