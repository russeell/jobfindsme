import type {ResearchEvidence} from '../../shared/contracts';
type Row=ResearchEvidence&{status:string};
/** Only successful originals are cached; workspace and session are part of the key. */
export function createOriginalReader(clock=Date.now){
  const cache=new Map<string,{at:number;row:Row}>();
  return async(input:{workspace:string;session:string;site:string;url:string;company:string;focus:string},http:(signal:AbortSignal,ms:number)=>Promise<Row>,browser:(signal:AbortSignal,ms:number)=>Promise<Row>,signal:AbortSignal,ms:number):Promise<Row>=>{
    const key=JSON.stringify(input),cached=cache.get(key);
    if(signal.aborted)throw Error('cancelled');
    if(cached&&clock()-cached.at<300000)return {...structuredClone(cached.row),context:{...cached.row.context,cache_status:'fresh',cached_at:new Date(cached.at).toISOString()}};
    const deadline=clock()+ms;
    const run=async(reader:typeof http,budget:number)=>{
      const controller=new AbortController();let timer:ReturnType<typeof setTimeout>|undefined;
      const abort=()=>controller.abort();signal.addEventListener('abort',abort,{once:true});
      try{return await Promise.race([reader(controller.signal,budget),new Promise<never>((_,reject)=>{controller.signal.addEventListener('abort',()=>reject(Error(signal.aborted?'cancelled':'original read timeout')),{once:true});timer=setTimeout(()=>controller.abort(),budget);})]);}
      finally{if(timer)clearTimeout(timer);signal.removeEventListener('abort',abort);controller.abort();}
    };
    let row:Row;
    try{row=await run(http,Math.min(4000,Math.max(1,ms)));}
    catch(error){if(signal.aborted||/unsafe|TLS|certificate|不安全|公网|private address/i.test(String(error)))throw error;row={status:'read_failed',url:input.url} as Row;}
    if(signal.aborted)throw Error('cancelled');
    const remaining=deadline-clock();
    if(row.status==='read_failed'&&/TLS|certificate|unsafe|private address/i.test(String((row as Row&{limit?:string}).limit||'')))return row;
    // Gate pages are presented for user recovery; nothing solves a CAPTCHA.
    if(['read_failed','empty_body','navigation_only','login_required','verification_required'].includes(row.status)&&remaining>200)row=await run(browser,remaining);
    if(signal.aborted)throw Error('cancelled');
    if(row.status==='read_original'&&row.evidence_id){cache.set(key,{at:clock(),row:structuredClone(row)});if(cache.size>100)cache.delete(cache.keys().next().value!);}
    return row;
  };
}
