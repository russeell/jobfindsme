import type {SourceCapability,SourceCheckResult} from "./contracts.js";
import {userError} from "./user-errors.js";

export type SourcePresentation={title:string;detail:string;action:"login"|"check"|"use";available:boolean};

export function mergeSourceChecks(current:SourceCheckResult[],incoming:SourceCheckResult[]):SourceCheckResult[]{
  const rows=new Map(current.map(row=>[row.source.source_id,row]));
  for(const row of incoming){
    // A skipped/cached check is not new evidence that an earlier failure recovered.
    if(row.evidence!=="live"&&rows.has(row.source.source_id))continue;
    rows.set(row.source.source_id,row);
  }
  return [...rows.values()];
}

export function sourceStatusRows(sources:SourceCapability[],checks:SourceCheckResult[]){
  return sources.map(source=>{
    const recorded=checks.find(row=>row.source.source_id===source.source_id);
    const checked=recorded?.attempted_at&&source.last_verified_at&&Date.parse(source.last_verified_at)>Date.parse(recorded.attempted_at)?undefined:recorded;
    return {source,checked,presented:presentSourceStatus(source,checked)};
  });
}

export function sourceCheckFailureOutcome(message:string):SourceCheckResult["outcome"]{
  if(/risk_control:|captcha|429|安全验证|风控/i.test(message))return "risk_control";
  if(/login_required:/.test(message))return "login_required";
  if(/source_backoff:/.test(message))return "skipped_cooldown";
  if(/no_matching:|没有读取到匹配岗位/.test(message))return "unverified";
  return "failed";
}

export function presentSourceStatus(source:SourceCapability,check?:SourceCheckResult,now=Date.now()):SourcePresentation{
  if(check?.attempted_at&&source.last_verified_at&&Date.parse(source.last_verified_at)>Date.parse(check.attempted_at))check=undefined;
  const stale=Boolean(source.last_verified_at)&&now-Date.parse(source.last_verified_at!)>24*60*60*1000;
  if(check?.outcome==="risk_control")return {title:"需要验证",detail:"请在内置浏览器完成平台验证，再检查",action:"login",available:false};
  if(check?.outcome==="login_required")return {title:"需要登录",detail:"本次读取遇到登录页，请在内置浏览器登录后再检查",action:"login",available:false};
  if(check?.outcome==="failed"){
    const detail=check.detail||"本次读取未成功，请重试检查";
    if(/source_visible_page_required:|内置浏览器打开智联账号页面/.test(detail))return {title:"需核对登录",detail:"请在内置浏览器打开智联账号页面，再检查",action:"login",available:false};
    const title=/source_check_timeout|source_timeout:|超时/.test(detail)?"检查超时":/source_unavailable:|无法连接或未接受请求/.test(detail)?"连接失败":"检查未通过";
    return {title,detail:userError(detail).message,action:"check",available:false};
  }
  if(source.session_status==="blocked"||source.list_status==="blocked")
    return {title:"需要验证",detail:"请在内置浏览器完成平台验证，再检查",action:"login",available:false};
  if(source.source_id==="zhilian"&&source.session_status==="verified"&&!source.live_search_enabled&&/后台有界检索未通过/.test(source.detail||""))return {title:"已登录，后台检索待修复",detail:"登录身份已确认，后台读取尚未成功；可重试或查看能力详情",action:"check",available:false};
  if(source.source_id==="zhilian"&&source.session_status==="verified"&&!source.live_search_enabled&&source.list_status==="partial")
    return {title:source.fields_status==="verified"?"已登录，列表可读":"已登录，检索待验",detail:source.detail||"输入关键词尝试搜索；检查会验证一次后台搜索",action:"use",available:false};
  if(source.session_status==="expired")return {title:"会话待复查",detail:"请在应用内核对登录状态",action:"check",available:false};
  if(source.login_required&&source.session_status!=="verified"&&source.list_status==="verified")
    return {title:"列表可读，登录未确认",detail:"本次读到了岗位；账号身份尚未确认，详情和续页仍需分别检查",action:"check",available:false};
  if(check?.outcome==="unverified")return {title:"本次未确认",detail:check.detail||"可稍后重试检查",action:"check",available:false};
  if(source.login_required&&source.session_status!=="verified")return {title:source.session_status==="expired"?"会话待复查":"登录状态待确认",detail:"可检查来源或在应用内打开官网",action:"check",available:false};
  if(source.live_search_enabled){
    if(stale)return {title:"之前可检索，待复查",detail:"可尝试搜索，结果以本次读取为准",action:"check",available:true};
    if(source.fields_status!=="verified"||source.pagination_status!=="verified"||source.detail_status!=="verified")return {title:"可检索，部分覆盖",detail:"详情、字段或续页仍有限制",action:"use",available:true};
    return {title:"可检索",detail:"可加入本次搜索范围",action:"use",available:true};
  }
  if(source.list_status==="partial")return {title:source.detail?.includes("显示已登录")?"已登录，检索待验":"列表可见，检索待验",detail:"自动检索尚未确认",action:"check",available:false};
  return {title:"尚未确认",detail:"检查后确认是否可检索",action:"check",available:false};
}
