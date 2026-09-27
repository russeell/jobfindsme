import type {SourceCapability,SourceCheckResult} from "./contracts.js";

export type SourcePresentation={title:string;detail:string;action:"login"|"check"|"use";available:boolean};

export function presentSourceStatus(source:SourceCapability,check?:SourceCheckResult,now=Date.now()):SourcePresentation{
  const stale=Boolean(source.last_verified_at)&&now-Date.parse(source.last_verified_at!)>24*60*60*1000;
  if(check?.outcome==="login_required"||source.login_required&&source.session_status!=="verified")
    return {title:source.session_status==="expired"?"需要重新登录":"需要登录",detail:"在应用内登录后检查来源",action:"login",available:false};
  if(check?.outcome==="risk_control"||source.session_status==="blocked"||source.list_status==="blocked")
    return {title:"平台验证中",detail:"完成平台验证后再检查",action:"login",available:false};
  if(check?.outcome==="failed")return {title:"本次检查失败",detail:check.detail||"可稍后重试检查",action:"check",available:false};
  if(source.live_search_enabled){
    if(stale)return {title:"之前可检索，待复查",detail:"可尝试搜索，结果以本次读取为准",action:"check",available:true};
    if(source.fields_status!=="verified"||source.pagination_status!=="verified"||source.detail_status!=="verified")return {title:"可检索，部分覆盖",detail:"详情、字段或续页仍有限制",action:"use",available:true};
    return {title:"可检索",detail:"可加入本次搜索范围",action:"use",available:true};
  }
  if(source.list_status==="partial")return {title:"列表可见，检索待验",detail:"自动检索尚未确认",action:"check",available:false};
  return {title:"尚未确认",detail:"检查后确认是否可检索",action:"check",available:false};
}
