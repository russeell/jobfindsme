export type UserError={kind:'login'|'risk'|'source'|'service'|'partial'|'unknown';message:string;action:'source'|'retry'};
export function userError(error:unknown):UserError {
 const text=error instanceof Error?error.message:String(error||'');
 if(/model_configuration_busy/.test(text))return {kind:"service",message:"模型仍在使用或配置处理中，请结束当前任务后重试。",action:"retry"};
 if(/assistant_failure:interview_output/.test(text))return {kind:'service',message:'本轮面试回复未满足逐题练习要求，未将其作为完成的练习。提问已保留，可重试。',action:'retry'};
 const assistantPhase=text.match(/assistant_failure:(backend|input|model_config|model_key|runtime_load)/)?.[1];
 if(assistantPhase){const message={backend:'求职助手无法连接本地服务，请重启应用后重试。',input:'本轮材料超出可处理范围或会话格式无效。请减少附件或新建聊天重试。',model_config:'无法读取模型配置，请到“模型设置”检查连接。',model_key:'无法读取模型密钥。请到“模型设置”完成钥匙串授权后重试。',runtime_load:'求职助手组件未能加载，请重新安装完整的应用版本。'}[assistantPhase];return {kind:'service',message:message!,action:'retry'};}
 if(/模型请求失败|model_request_failed/.test(text)){
  const detail=/401|403|unauthorized|invalid.api.key|authentication/i.test(text)?'模型拒绝了当前密钥，请到“模型设置”重新测试连接。':/429|rate.limit|quota|余额|额度/i.test(text)?'模型调用受限或额度不足，请检查模型账户后重试。':/timeout|timed.out|超时/i.test(text)?'模型回复超时，提问和材料已保留，可重试。':/fetch failed|ECONN|ENOTFOUND|network|connection/i.test(text)?'无法连接模型服务，请检查网络后重试。':'模型未能完成本轮回答，请重新测试模型连接后重试。';
  return {kind:'service',message:detail,action:'retry'};
 }
 if(/当前模型缺少系统安全存储中的密钥|请先在模型设置中测试连接/.test(text))return {kind:'service',message:'当前模型尚未就绪，请到“模型设置”保存密钥并测试连接。',action:'retry'};
 if(/safeStorage\.decryptString|decrypting the ciphertext/i.test(text))return {kind:'service',message:'本机保存的模型密钥无法在当前应用解密。请到“模型设置”重新保存密钥并测试连接。',action:'retry'};
 if(/browser_navigation_failed/.test(text))return {kind:'source',message:'网页加载失败，请刷新或检查网络连接。',action:'retry'};
 const chatStorage=text.match(/research_chat_storage:(sqlite_busy|sqlite_readonly|sqlite_full|sqlite_constraint|sqlite_error)/);
 if(chatStorage){const message={sqlite_busy:'本地对话数据库繁忙',sqlite_readonly:'本地对话数据库不可写',sqlite_full:'本地对话数据库空间不足',sqlite_constraint:'本地对话数据库约束冲突',sqlite_error:'本地对话数据库读写失败'}[chatStorage[1]];return {kind:'service',message:`${message}（${chatStorage[1]}）`,action:'retry'};}
 if(/source_detail_unreadable:|没有读取到完整岗位信息/.test(text))return {kind:'source',message:'未能读取完整岗位详情。列表和登录状态保留，可打开原页查看或重试。',action:'retry'};
 if(/source_visible_page_required:/.test(text))return {kind:'source',message:'请在内置浏览器打开智联账号页面，确认登录状态后重试检查。',action:'source'};
 if(/login_required\b|\bverified login\b|登录.*(失效|过期)/.test(text))return {kind:'login',message:'该来源显示登录页，请在内置浏览器核对账号状态。已读取的岗位会保留。',action:'source'};
 if(/verification_required|risk_control|验证码|安全验证|限流|过于频繁/.test(text))return {kind:'risk',message:'该来源要求验证或暂时限制访问，采集已暂停。',action:'source'};
 if(/source_backoff:/.test(text))return {kind:'source',message:'该来源正在检查或刚完成检查，本次没有重复访问。',action:'retry'};
 if(/source_check_timeout|source_timeout:/.test(text))return {kind:'source',message:'本次来源读取超时，登录和检索能力尚未确认。',action:'retry'};
 if(/no_matching:/.test(text))return {kind:'source',message:'本次未读到匹配岗位，检索能力仍待验证。',action:'retry'};
 if(/source_scope_unconfirmed:/.test(text))return {kind:'source',message:'尚未确认列表属于本次搜索，未返回推荐或上一轮岗位。登录状态保留，可重试。',action:'retry'};
 if(/source_query_unconfirmed:/.test(text))return {kind:'source',message:'平台返回了无法确认关键词匹配的扩展岗位，已排除。上次成功结果和登录状态保留；请换一个明确的岗位关键词。',action:'retry'};
 if(/source_scope_mismatch:/.test(text))return {kind:'source',message:'站内页面未保留本次关键词、城市或页码，未将推荐岗位计作搜索结果。',action:'retry'};
 if(/source_contract_error:/.test(text))return {kind:'source',message:'本次未读到可验证的岗位列表，可能是页面结构变化；登录状态仍待确认。',action:'source'};
 if(/partial|部分失败/.test(text))return {kind:'partial',message:'部分来源未完成，已保留可用岗位。',action:'source'};
 if(/source_contract|来源|continuation_expired/.test(text))return {kind:'source',message:'来源暂时无法读取，请打开对应网站确认状态。',action:'source'};
 if(/chat_concurrency_limit/.test(text))return {kind:'service',message:'同时最多运行四条聊天，请等待其中一条完成或停止后再发送。',action:'retry'};
 if(/500|502|503|fetch failed|API.*(ready|failed)|ECONN|IPC|invoking remote/.test(text))return {kind:'service',message:'本次操作未完成，本地服务暂时异常，请稍后重试。',action:'retry'};
 if(/[\u4e00-\u9fff]/.test(text)&&text.length<=160&&!/Error|Exception|\n\s+at |https?:|Bearer|token|api.key/i.test(text))return {kind:'unknown',message:text,action:'retry'};
 return {kind:'unknown',message:'操作未完成，请稍后重试。',action:'retry'};
}
