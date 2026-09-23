import {useState} from "react";
import type {ResearchReport,ResearchCorrectionInput} from "../../../shared/contracts";
import {userError} from "../../../shared/user-errors";

export const researchDirections = {role:"工作内容",workload:"工作强度",leave:"假期情况",care:"员工福利"};
export const reputationDisclaimer = "公开陈述只供参考；请核对原文、时间和适用范围，不据此为公司评分。";
const correctionKinds = {wrong_entity:"主体错误",broken_link:"链接失效",wrong_team:"团队不匹配",other:"其他信息有误"};
const sourceStatus:Record<string,string>={no_public_evidence:"暂无可核对的公开原文",restricted_or_unavailable:"访问受限，暂无法核对",retrieval_failed:"本次读取失败",login_required:"需要登录后核对",risk_control:"平台要求安全验证",source_error:"来源读取失败"};
const readableLimit=(value:string)=>value.replace(/no_public_evidence|restricted_or_unavailable|retrieval_failed|login_required|risk_control|source_error/g,key=>sourceStatus[key]);

export function ReputationEvidence({report,workspaceId,onReport}:{report?:ResearchReport;workspaceId:string;onReport(value:ResearchReport):void}) {
  const [editing,setEditing]=useState<string>();
  const [kind,setKind]=useState<ResearchCorrectionInput["kind"]>("wrong_entity");
  const [note,setNote]=useState("");
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");
  const entries=report?.evidence||[];
  const topics=report?.job_context?.research_topics||[];
  const groups=topics.length
    ? [...topics.map(topic=>({key:topic,label:topic==="company"?"公司评价":"岗位情况",items:entries.filter(item=>item.context?.research_topic===topic)})),
      ...(entries.some(item=>!item.context?.research_topic)?[{key:"other",label:"其他材料",items:entries.filter(item=>!item.context?.research_topic)}]:[])]
    : [{key:"legacy",label:"历史调查证据",items:entries}];
  async function save(){
    if(!report||!editing)return;
    setBusy(true);setMessage("");
    try{onReport(await window.jobfindsme!.correctResearch(report.report_id,{workspace_id:workspaceId,evidence_id:editing,kind,note}));setEditing(undefined);setNote("");setMessage("已在本机记录更正，未对外提交。");}
    catch(error){setMessage(userError(error).message);}finally{setBusy(false);}
  }
  return <section className="reputation-evidence">
    <p className="reputation-caution">{reputationDisclaimer}</p>
    {report?.job_context?.interest_question&&<p className="note">本次兴趣问题：{report.job_context.interest_question}</p>}
    {!entries.length&&<div className="research-empty" role="status"><strong>本次没有可核对的公开原文</strong><p>已检查所选主题；来源受限或没有结果，不代表不存在相关反馈。可用公司全称和团队名称到原网站核对。</p></div>}
    {groups.filter(group=>group.items.length>0||group.key==="job"&&!!report?.jd_facts.length).map(group=><section className="research-topic-result" key={group.key}>
      <h2>{group.label}</h2>
      {group.items.length>0&&<div className="evidence-grid">{group.items.map(item=>{
        const context=item.context||{};
        const publishedTime=item.published_at?Date.parse(item.published_at):NaN;
        const expired=Number.isFinite(publishedTime)&&publishedTime<Date.now()-730*86400000;
        const corrections=report?.corrections?.filter(c=>c.evidence_id===item.evidence_id)||[];
        return <article className="evidence-card" key={item.evidence_id}>
          <div className="evidence-head"><strong>{item.evidence_kind==="public_source"?item.platform:"用户提供的摘录"}</strong><span>{Number.isFinite(publishedTime)?new Date(publishedTime).toLocaleDateString():"发布时间未知"}{expired&&" · 超过两年"}</span></div>
          {item.excerpt&&<blockquote>{item.excerpt}</blockquote>}
          <div className="evidence-source"><span>{item.verification_status==="independently_retrieved"?"已读取原页 · 真实性未核实":"原文未独立读取"}</span>{item.url&&/^https?:\/\//i.test(item.url)&&<a href={item.url} target="_blank" rel="noreferrer">核对原始链接 ↗</a>}</div>
          <details><summary>适用范围与核验说明</summary><dl className="evidence-context"><dt>涉及公司</dt><dd>{item.company||"未知"}</dd><dt>部门 / 团队</dt><dd>{item.team||"未知"}</dd><dt>岗位 / 职级</dt><dd>{context.role||"未知"} / {context.level||"未知"}</dd><dt>地区 / 范围</dt><dd>{context.region||"未知"} / {item.relevance==="team"?"仅该来源所述团队":"其他范围未知"}</dd><dt>读取时间</dt><dd>{item.retrieved_at||"未知"}</dd><dt>链接状态</dt><dd>{{reachable:"读取时可访问；当前未复查",broken:"已失效",unavailable:"暂无法读取",unknown:"未知"}[context.link_status||"unknown"]}</dd></dl><p className="note">{item.limitations}</p></details>
          <button className="correction-trigger" onClick={()=>{setEditing(item.evidence_id);setNote("");setMessage("");}}>信息有误 / 记录更正</button>
          {!!corrections.length&&<p className="note">本机更正：{corrections.map(c=>`${correctionKinds[c.kind]}${c.note?`：${c.note}`:""}`).join("；")}</p>}
          {editing===item.evidence_id&&<form className="correction-form" onSubmit={event=>{event.preventDefault();void save();}}><p>更正只保存在本机，原陈述仍保留。</p><label>更正类型<select value={kind} onChange={event=>setKind(event.target.value as ResearchCorrectionInput["kind"])}>{Object.entries(correctionKinds).map(([key,value])=><option value={key} key={key}>{value}</option>)}</select></label><label>补充说明（可选）<textarea value={note} maxLength={1000} onChange={event=>setNote(event.target.value)}/></label><div className="button-row"><button type="submit" disabled={busy}>{busy?"保存中…":"保存本地记录"}</button><button type="button" disabled={busy} onClick={()=>setEditing(undefined)}>取消</button></div></form>}
        </article>;
      })}</div>}
      {group.key==="job"&&!!report?.jd_facts.length&&<details className="research-jd-facts"><summary>岗位 JD 线索 · 非员工反馈</summary>{report.jd_facts.map((fact,index)=><p key={index}>{fact}</p>)}</details>}
    </section>)}
    {message&&<p role="status">{message}</p>}
    {(!!report?.limitations.length||!topics.length&&!!report?.directions?.length)&&<details className="research-diagnostics"><summary>来源限制与调查说明</summary>{!topics.length&&!!report?.directions?.length&&<p>历史调查方向：{report.directions.map(key=>key==="salary"?"薪资（历史）":researchDirections[key]).join("、")}</p>}{report?.limitations.map((item,index)=><p key={index}>{readableLimit(item)}</p>)}</details>}
  </section>;
}
