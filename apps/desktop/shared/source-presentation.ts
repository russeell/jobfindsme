import type {SourceCapability,SourceCheckResult} from "./contracts.js";

export type SourcePresentation={title:string;detail:string;action:"login"|"check"|"use";available:boolean};

export function sourceCheckFailureOutcome(message:string):SourceCheckResult["outcome"]{
  if(/risk_control:|captcha|429|安全验证|风控/i.test(message))return "risk_control";
  if(/login_required:/.test(message))return "login_required";
  if(/no_matching:|没有读取到匹配岗位/.test(message))return "unverified";
  return "failed";
}

export function presentSourceStatus(source:SourceCapability,check?:SourceCheckResult,now=Date.now()):SourcePresentation{
  if(check?.attempted_at&&source.last_verified_at&&Date.parse(source.last_verified_at)>Date.parse(check.attempted_at))check=undefined;
  const stale=Boolean(source.last_verified_at)&&now-Date.parse(source.last_verified_at!)>24*60*60*1000;
  if(check?.outcome==="risk_control"||source.session_status==="blocked"||source.list_status==="blocked")
    return {title:"平台验证中",detail:"完成平台验证后再检查",action:"login",available:false};
  if(source.source_id==="zhilian"&&source.session_status==="verified"&&!source.live_search_enabled&&source.list_status==="partial")
    return {title:source.fields_status==="verified"?"已登录，列表可读":"已登录，检索待验",detail:source.detail||"输入关键词尝试搜索；手动检查用于排查当前页面",action:"use",available:false};
  if(check?.outcome==="failed"||check?.outcome==="unverified")return {title:"本次未确认",detail:check.detail||"可稍后重试检查",action:"check",available:false};
  if(check?.outcome==="login_required")return {title:"本次需要登录",detail:"来源本次显示登录页，请在应用内核对",action:"login",available:false};
  if(source.login_required&&source.session_status!=="verified")return {title:source.session_status==="expired"?"会话待复查":"登录状态待确认",detail:"可检查来源或在应用内打开官网",action:"check",available:false};
  if(source.live_search_enabled){
    if(stale)return {title:"之前可检索，待复查",detail:"可尝试搜索，结果以本次读取为准",action:"check",available:true};
    if(source.fields_status!=="verified"||source.pagination_status!=="verified"||source.detail_status!=="verified")return {title:"可检索，部分覆盖",detail:"详情、字段或续页仍有限制",action:"use",available:true};
    return {title:"可检索",detail:"可加入本次搜索范围",action:"use",available:true};
  }
  if(source.list_status==="partial")return {title:source.detail?.includes("显示已登录")?"已登录，检索待验":"列表可见，检索待验",detail:"自动检索尚未确认",action:"check",available:false};
  return {title:"尚未确认",detail:"检查后确认是否可检索",action:"check",available:false};
}
