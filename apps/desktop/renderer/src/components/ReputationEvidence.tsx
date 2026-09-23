import {useState} from "react";
import type {ResearchReport,ResearchCorrectionInput} from "../../../shared/contracts";
import {userError} from "../../../shared/user-errors";
export const researchDirections = {role:"岗位情况",workload:"工作强度",leave:"假期情况",care:"员工关怀 / 体验"};
export const reputationDisclaimer = "仅整理可访问的公开材料；个人陈述未核实真实性，也不代表公司或团队整体。请核对原链接、时间与适用范围；不作评分或推荐。";
const correctionKinds = {wrong_entity:"主体错误",broken_link:"链接失效",wrong_team:"团队不匹配",other:"其他信息有误"};
export function ReputationEvidence({report,workspaceId,onReport}:{report?:ResearchReport;workspaceId:string;onReport(value:ResearchReport):void}) {
 const [editing,setEditing]=useState<string>();const [kind,setKind]=useState<ResearchCorrectionInput["kind"]>("wrong_entity");const [note,setNote]=useState("");const [busy,setBusy]=useState(false);const [message,setMessage]=useState("");
 const entries=report?.evidence||[];
 const topics=report?.job_context?.research_topics||[];
 const groups=topics.length?[...topics.map(topic=>({key:topic,label:topic==="company"?"公司评价":"岗位情况",items:entries.filter(item=>item.context?.research_topic===topic)})),...(entries.some(item=>!item.context?.research_topic)?[{key:"other",label:"其他材料（未归类）",items:entries.filter(item=>!item.context?.research_topic)}]:[])]:[{key:"legacy",label:"历史调查证据",items:entries}];
 async function save(){if(!report||!editing)return;setBusy(true);setMessage("");try{onReport(await window.jobfindsme!.correctResearch(report.report_id,{workspace_id:workspaceId,evidence_id:editing,kind,note}));setEditing(undefined);setNote("");setMessage("已保存在本机，未向平台、公司或其他人提交。");}catch(e){setMessage(userError(e).message);}finally{setBusy(false);}}
 return <section className="reputation-evidence">
 <p className="notice">{reputationDisclaimer}</p>
 <p className="muted">不同来源的陈述分别保留；如有冲突，请并列查阅原文。公司名称匹配不代表主体身份或内容真实性已核实。</p>
 {report && <p>本次检索记录 {entries.length} 条，其中读取原文 {entries.filter(e=>e.verification_status==="independently_retrieved").length} 条。仅统计本次结果，不代表公司整体或员工总体。</p>}
 {!topics.length&&report?.directions && <p className="muted">本报告快捷调查方向：{report.directions.length?report.directions.map(key=>key==="salary"?"薪资（历史调查方向）":researchDirections[key]).join("、"):"未选择"}</p>}
 {report?.job_context?.interest_question&&<p className="notice">本次兴趣问题：{report.job_context.interest_question}</p>}
 {!entries.length && <p className="notice">暂无可展示的公开原文。来源受限或没有结果，不代表不存在相关陈述。</p>}
 {groups.map(group=><section className="research-topic-result" key={group.key}><h2>{group.label}</h2>{group.key==="company"&&<p className="note">分别检索正向与负向线索；检索角度不代表原文立场，以下陈述需逐条核对。</p>}{group.key==="job"&&<p className="note">围绕工作内容、工作强度、假期与员工福利查找；缺少原文的方面仍未查明。岗位 JD 单独列示，不算员工反馈。</p>}{group.key==="job"&&!!report?.jd_facts.length&&<details><summary>岗位 JD 线索（非员工反馈）</summary>{report.jd_facts.map((fact,index)=><p key={index}>{fact}</p>)}</details>}{!group.items.length&&<p className="note">本次未取得可展示的原始材料，不能据此判断不存在相关评价。</p>}<div className="evidence-grid">{group.items.map(item=>{const context=item.context||{};const expired=!!item.published_at&&Date.parse(item.published_at)<Date.now()-730*86400000;const corrections=report?.corrections?.filter(c=>c.evidence_id===item.evidence_id)||[];return <article className="evidence-card" key={item.evidence_id}>
 <h3>{item.evidence_kind==="public_source"?"公开来源中的用户陈述":"用户提供的摘录（未核实）"}</h3>
 <p>{item.platform} · {item.verification_status==="independently_retrieved"?"已读取原页，不代表真实性已核实":"未读取原文"}</p>
 {item.excerpt && <blockquote>{item.excerpt}</blockquote>}
 <dl className="evidence-context"><dt>涉及公司</dt><dd>{item.company||"未知"}</dd><dt>部门 / 团队</dt><dd>{item.team||"未知"}</dd><dt>岗位 / 职级</dt><dd>{context.role||"未知"} / {context.level||"未知"}</dd><dt>地区 / 适用范围</dt><dd>{context.region||"未知"} / {item.relevance==="team"?"仅该来源所述团队；其他范围未知":"其他适用范围未知"}</dd><dt>发布时间</dt><dd>{item.published_at||"未知"}{expired&&" · 距今超过两年，可能已过时"}</dd><dt>读取时间</dt><dd>{item.retrieved_at||"未知"}</dd><dt>链接状态</dt><dd>{{reachable:"读取时可访问；当前状态未复查",broken:"已失效（404 / 410）",unavailable:"暂无法读取，是否失效未知",unknown:"未知"}[context.link_status||"unknown"]}</dd></dl>
 <p className="muted">{item.limitations} 摘录仅供定位，请查看完整原文。</p>
 {item.url&&/^https?:\/\//i.test(item.url)&&<a href={item.url} target="_blank" rel="noreferrer">查看原始链接 ↗</a>}
 <button className="correction-trigger" onClick={()=>{setEditing(item.evidence_id);setNote("");setMessage("");}}>信息有误 / 申请更正</button>
 {!!corrections.length&&<p className="note">本机更正记录：{corrections.map(c=>`${correctionKinds[c.kind]}${c.note?`：${c.note}`:""}`).join("；")}。未对外提交，原始陈述保留。</p>}
 {editing===item.evidence_id&&<form className="correction-form" onSubmit={e=>{e.preventDefault();void save();}}><p>仅记录在本机，不会联系平台、公司或原发布者。</p><label>更正类型<select value={kind} onChange={e=>setKind(e.target.value as ResearchCorrectionInput["kind"])}>{Object.entries(correctionKinds).map(([key,value])=><option value={key} key={key}>{value}</option>)}</select></label><label>补充说明（可选）<textarea value={note} maxLength={1000} onChange={e=>setNote(e.target.value)}/></label><div className="button-row"><button type="submit" disabled={busy}>{busy?"保存中…":"保存本地记录"}</button><button type="button" disabled={busy} onClick={()=>setEditing(undefined)}>取消</button></div></form>}
 </article>})}</div></section>)}
 {message&&<p role="status">{message}</p>}
 {report?.limitations.map((item,index)=><p className="note" key={index}>{item}</p>)}
 </section>;
}
