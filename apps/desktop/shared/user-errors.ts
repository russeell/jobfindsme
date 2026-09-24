export type UserError={kind:'login'|'risk'|'source'|'service'|'partial'|'unknown';message:string;action:'source'|'retry'};
export function userError(error:unknown):UserError {
 const text=error instanceof Error?error.message:String(error||'');
 if(/login_required|verified login|登录.*(失效|过期)|请.*登录/.test(text))return {kind:'login',message:'该来源需要重新登录。已读取的岗位会保留。',action:'source'};
 if(/risk_control|验证码|安全验证|限流|过于频繁/.test(text))return {kind:'risk',message:'该来源要求验证或暂时限制访问，采集已暂停。',action:'source'};
 if(/partial|部分失败/.test(text))return {kind:'partial',message:'部分来源未完成，已保留可用岗位。',action:'source'};
 if(/source_contract|来源|continuation_expired/.test(text))return {kind:'source',message:'来源暂时无法读取，请打开对应网站确认状态。',action:'source'};
 if(/500|502|503|fetch failed|API.*(ready|failed)|ECONN|IPC|invoking remote/.test(text))return {kind:'service',message:'本次检索未完成，本地服务暂时异常。已有结果已保留，请稍后重试。',action:'retry'};
 if(/[\u4e00-\u9fff]/.test(text)&&text.length<=160&&!/Error|Exception|\n\s+at |https?:|Bearer|token|api.key/i.test(text))return {kind:'unknown',message:text,action:'retry'};
 return {kind:'unknown',message:'操作未完成，请稍后重试。已有数据会保留。',action:'retry'};
}
