import type {SourceCapability,SourceCheckResult} from "../shared/contracts";

type CheckOptions={
  sources:SourceCapability[];
  probe(source:SourceCapability,signal:AbortSignal):Promise<SourceCapability>;
  signal:AbortSignal;
  onProgress?(result:SourceCheckResult,done:number,total:number):void;
  totalMs?:number;
  perSourceMs?:number;
  cacheMs?:number;
  maxLiveProbes?:number;
  now?:()=>number;
};

export async function runSourceCheckQueue(options:CheckOptions):Promise<SourceCheckResult[]>{
  const now=options.now??Date.now;
  const started=now(),deadline=started+(options.totalMs??45000);
  const perSourceMs=options.perSourceMs??8000;
  const cacheMs=options.cacheMs??600000;
  const results:SourceCheckResult[]=[];
  let liveAttempts=0;
  const append=(result:SourceCheckResult)=>{results.push(result);options.onProgress?.(result,results.length,options.sources.length);};
  let stop:"cancelled"|"not_checked_budget"|undefined;
  for(const source of options.sources){
    if(options.signal.aborted)stop="cancelled";
    if(stop==="cancelled"){append({source,outcome:stop,evidence:"none",attempted_at:null,detail:"已取消，未轮到此来源。",duration_ms:0});continue;}
    const began=now(),attempted_at=new Date(began).toISOString();
    const base={source,attempted_at:null,duration_ms:0};
    if(source.login_required&&source.session_status!=="verified"){
      append({...base,outcome:source.session_status==="blocked"?"risk_control":"login_required",evidence:"history",detail:source.session_status==="blocked"?"来源要求平台验证；本次未发起检索。":"应用独立会话尚未确认登录；本次未发起检索。"});continue;
    }
    if(source.session_status==="blocked"||source.list_status==="blocked"){
      append({...base,outcome:"skipped_cooldown",evidence:"history",detail:"来源处于暂停或风控状态，本次跳过。"});continue;
    }
    const verifiedAt=source.last_verified_at?Date.parse(source.last_verified_at):NaN;
    if(source.live_search_enabled&&Number.isFinite(verifiedAt)&&began-verifiedAt>=0&&began-verifiedAt<cacheMs){
      append({...base,outcome:"cached_recent",evidence:"cache",detail:"最近验证仍在冷却期；本次未重复访问来源。"});continue;
    }
    if(stop==="not_checked_budget"||began>=deadline||liveAttempts>=(options.maxLiveProbes??Infinity)){
      stop="not_checked_budget";
      append({...base,outcome:stop,evidence:"none",detail:"本次检查预算已用尽，未访问此来源。"});continue;
    }
    const allowance=Math.min(perSourceMs,deadline-began);
    liveAttempts++;
    const controller=new AbortController();
    const abort=()=>controller.abort();options.signal.addEventListener("abort",abort,{once:true});
    let timer:ReturnType<typeof setTimeout>|undefined;
    try{
      const aborted=new Promise<never>((_,reject)=>{
          timer=setTimeout(()=>{controller.abort();reject(Error("source_check_timeout"));},allowance);
          controller.signal.addEventListener("abort",()=>reject(Error("source_check_cancelled")),{once:true});
      });
      const value=await Promise.race([options.probe(source,controller.signal),aborted]);
      append({source:value,outcome:"verified_now",evidence:"live",attempted_at,duration_ms:now()-began,detail:"本次有界检索读取到岗位列表；JD 与分页仍按各自状态展示。"});
    }catch(error){
      const message=String(error);
      const cancelled=options.signal.aborted;
      const timedOut=message.includes("source_check_timeout")||(!cancelled&&controller.signal.aborted);
      const outcome:SourceCheckResult["outcome"]=cancelled?"cancelled":timedOut?"failed":/risk_control:|captcha|429|访问过于频繁/i.test(message)?"risk_control":/login_required:/.test(message)?"login_required":/source_backoff:|cooldown/.test(message)?"skipped_cooldown":/未读取到|没有返回岗位|no_matching/.test(message)?"unverified":"failed";
      append({...base,outcome,evidence:"live",attempted_at,duration_ms:now()-began,detail:cancelled?"已取消当前来源。":timedOut?"本次探测超时；未开始后续来源。":message.slice(0,300)});
      if(cancelled)stop="cancelled";
      if(timedOut)stop="not_checked_budget";
    }finally{if(timer)clearTimeout(timer);options.signal.removeEventListener("abort",abort);}
  }
  return results;
}
