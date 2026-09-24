import {useState} from "react";
import type {ResearchReport,ResearchCorrectionInput,ResearchEvidence} from "../../../shared/contracts";
import {userError} from "../../../shared/user-errors";

export const researchDirections = {role:"岗位内容",workload:"工作强度",leave:"假期情况",care:"日常福利"};
export const reputationDisclaimer = "公开陈述只供核对；时间、团队和岗位不同，结论可能不同。这里不为公司评分或推荐。";
const correctionKinds = {wrong_entity:"主体错误",broken_link:"链接失效",wrong_team:"团队不匹配",other:"其他信息有误"};
const sourceStatus:Record<string,string>={no_public_evidence:"暂无可核对的公开原文",restricted_or_unavailable:"访问受限，暂无法核对",retrieval_failed:"本次读取失败",login_required:"需要登录后核对",risk_control:"平台要求安全验证",source_error:"来源读取失败"};
const readableLimit=(value:string)=>value.replace(/no_public_evidence|restricted_or_unavailable|retrieval_failed|login_required|risk_control|source_error/g,key=>sourceStatus[key]);
const companyAngles=[['business','经营情况'],['listing','上市状态'],['positive','正面反馈'],['negative','负面反馈'],['workload','工作强度'],['benefits','日常福利']] as const;
const jobAngles=[['role','岗位内容'],['development','岗位发展']] as const;

export function ReputationEvidence({report,workspaceId,onReport,onSource}:{report?:ResearchReport;workspaceId:string;onReport(value:ResearchReport):void;onSource?(url:string):void}) {
  const [editing,setEditing]=useState<string>();
  const [kind,setKind]=useState<ResearchCorrectionInput["kind"]>("wrong_entity");
  const [note,setNote]=useState("");
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");
  const entries=report?.evidence||[];
  const topics=report?.job_context?.research_topics||[];
  const questionEntries=entries.filter(item=>item.context?.search_angle==="question");
  const verifiedQuestionCount=questionEntries.filter(item=>item.verification_status==="independently_retrieved").length;
  const companyEntries=entries.filter(item=>item.context?.research_topic==="company"&&item.context?.search_angle!=="question");
  const jobEntries=entries.filter(item=>item.context?.research_topic==="job"&&item.context?.search_angle!=="question");
  const legacyEntries=entries.filter(item=>!item.context?.research_topic);
  const hasPositive=companyEntries.some(item=>item.context?.search_angle==="positive");
  const hasNegative=companyEntries.some(item=>item.context?.search_angle==="negative");
  const showCompanySection=topics.includes("company")&&!!entries.length&&(!!companyEntries.length||!questionEntries.length);
  const limitations=[...new Set(report?.limitations||[])];
  async function save(){
    if(!report||!editing)return;
    setBusy(true);setMessage("");
    try{onReport(await window.jobfindsme!.correctResearch(report.report_id,{workspace_id:workspaceId,evidence_id:editing,kind,note}));setEditing(undefined);setNote("");setMessage("已在本机记录更正，原文仍保留。");}
    catch(error){setMessage(userError(error).message);}finally{setBusy(false);}
  }
  function card(item:ResearchEvidence){
    const context=item.context||{};
    const publishedTime=item.published_at?Date.parse(item.published_at):NaN;
    const corrections=report?.corrections?.filter(c=>c.evidence_id===item.evidence_id)||[];
    const official=context.source_type==="official_disclosure";
    return <article className="evidence-card" key={item.evidence_id}>
      <div className="evidence-head"><strong>{item.platform}</strong><span>{official?"官方披露":"个人陈述"} · {Number.isFinite(publishedTime)?new Date(publishedTime).toLocaleDateString():"发布时间未知"}</span></div>
      {item.excerpt&&<blockquote>{item.excerpt}</blockquote>}
      <div className="evidence-source"><span>{item.verification_status==="independently_retrieved"?"已读取原页":"原页未核实"} · {item.relevance==="team"?"仅涉及所述团队":"团队范围未知"}</span>{item.url&&/^https?:\/\//i.test(item.url)&&(onSource?<button type="button" onClick={()=>onSource(item.url!)}>查看来源 ↗</button>:<a href={item.url} target="_blank" rel="noreferrer">查看来源 ↗</a>)}</div>
      <details><summary>来源范围与核验</summary><dl className="evidence-context"><dt>公司</dt><dd>{item.company||"未知"}</dd><dt>团队</dt><dd>{item.team||"未知"}</dd><dt>岗位 / 地区</dt><dd>{context.role||"未知"} / {context.region||"未知"}</dd><dt>读取时间</dt><dd>{item.retrieved_at||"未知"}</dd><dt>链接状态</dt><dd>{{reachable:"读取时可访问；当前未复查",broken:"已失效",unavailable:"暂无法读取",unknown:"未知"}[context.link_status||"unknown"]}</dd></dl><p className="note">{item.limitations}</p></details>
      {!!corrections.length&&<p className="note">本机更正：{corrections.map(c=>`${correctionKinds[c.kind]}${c.note?`：${c.note}`:""}`).join("；")}</p>}
      <button className="correction-trigger" onClick={()=>{setEditing(item.evidence_id);setNote("");setMessage("");}}>记录信息更正</button>
      {editing===item.evidence_id&&<form className="correction-form" onSubmit={event=>{event.preventDefault();void save();}}><p>更正只保存在本机，原陈述仍保留。</p><label>更正类型<select value={kind} onChange={event=>setKind(event.target.value as ResearchCorrectionInput["kind"])}>{Object.entries(correctionKinds).map(([key,value])=><option value={key} key={key}>{value}</option>)}</select></label><label>补充说明（可选）<textarea value={note} maxLength={1000} onChange={event=>setNote(event.target.value)}/></label><div className="button-row"><button type="submit" disabled={busy}>{busy?"保存中…":"保存更正"}</button><button type="button" disabled={busy} onClick={()=>setEditing(undefined)}>取消</button></div></form>}
    </article>;
  }
  return <div className="research-reading">
    <p className="research-overview">{entries.length?`已保存 ${entries.length} 条可追溯材料；结论仍需结合来源和适用范围。`:
      "暂无可核对的公开原文，相关结论保持未知。"}</p>
    {report?.job_context?.interest_question&&<section className="research-question-result" aria-label="本次问题的检索结果"><span className="research-eyebrow">本次问题</span><h2>{report.job_context.interest_question}</h2>{verifiedQuestionCount?<p>找到 {verifiedQuestionCount} 条相关原页陈述；团队与岗位适用性仍需核对。</p>:entries.length?<p>现有材料未直接回答这个问题。</p>:null}{questionEntries.map(card)}</section>}
    {showCompanySection&&<section className="research-reading-section"><div className="research-section-heading"><span>01</span><h2>公司情况</h2></div>
      <p className="research-section-intro">经营与上市信息优先看公开披露；工作体验来自个人陈述，不能代表整个公司。</p>
      {companyEntries.length?<div className="research-angles">{companyAngles.map(([angle,label])=>{const found=companyEntries.filter(item=>item.context?.search_angle===angle);return found.length?<section key={angle} className="research-angle"><h3>{label}</h3>{found.map(card)}</section>:null;})}</div>:<p className="research-unknown">现有材料未覆盖公司经营与员工体验。</p>}
      {companyEntries.length>0&&(!companyEntries.some(item=>item.context?.search_angle==="business")||!companyEntries.some(item=>item.context?.search_angle==="listing"))&&<p className="research-unknown">{!companyEntries.some(item=>item.context?.search_angle==="business")?"经营情况未核实。":""} {!companyEntries.some(item=>item.context?.search_angle==="listing")?"上市状态未核实。":""}</p>}
      {hasPositive&&hasNegative&&<p className="research-conflict">正面与负面陈述并存；请结合发表时间、团队及岗位范围分别阅读。</p>}
    </section>}
    {topics.includes("job")&&<section className="research-reading-section"><div className="research-section-heading"><span>{showCompanySection?"02":"01"}</span><h2>岗位内容与发展</h2></div>
      <p className="research-section-intro">以下岗位信息来自保存时的 JD；发展判断另看公司的业务证据。</p>
      {report?.job_context?.description?<div className="research-jd-excerpt"><h3>岗位原文</h3><p>{report.job_context.description}</p></div>:<p className="research-unknown">缺少完整岗位 JD，职责与发展暂不能核对。</p>}
      {jobAngles.map(([angle,label])=>{const found=jobEntries.filter(item=>item.context?.search_angle===angle);return found.length?<section className="research-angle" key={angle}><h3>{label}的公开材料</h3>{found.map(card)}</section>:null;})}
      {!!report?.job_context?.description&&report?.job_context?.development_analysis?.status==="limited"&&<div className="research-analysis"><h3>发展线索 · 基于现有证据的分析</h3><p>{report.job_context.development_analysis.text}</p>{!!report.job_context.development_analysis.basis_evidence_ids?.length&&<small>依据：本页公司经营材料；未核实晋升路径。</small>}</div>}
      {!!report?.job_context?.description&&report?.job_context?.development_analysis?.status!=="limited"&&<p className="research-unknown">发展路径仍缺少可核对的公司经营依据。</p>}
    </section>}
    {!!legacyEntries.length&&<section className="research-reading-section"><div className="research-section-heading"><span>旧</span><h2>历史材料</h2></div>{legacyEntries.map(card)}</section>}
    {message&&<p role="status">{message}</p>}
    <details className="research-diagnostics"><summary>来源与说明</summary><p>{reputationDisclaimer}</p>{!!limitations.length&&<details className="research-limitations"><summary>{limitations.length} 条检索限制与未知信息</summary><ul>{limitations.map((item,index)=><li key={index}>{readableLimit(item)}</li>)}</ul></details>}{!topics.length&&!!report?.directions?.length&&<p>历史方向：{report.directions.map(key=>key==="salary"?"薪资（历史）":researchDirections[key]).join("、")}</p>}</details>
  </div>;
}
